"""Tests for ClickUp API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.database import get_session
from app.core.deps import get_current_user, require_role
from app.core.security import create_access_token
from app.main import app
from app.models.enums import CompanyStatus, UserRole
from app.services.api.clickup import ClickUpTask
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_user(user_id: int = 1, role: UserRole = UserRole.USER):
    user = type("User", (), {})()
    user.id = user_id
    user.username = "testuser"
    user.email = "testuser@test.com"
    user.role = role
    user.password_hash = "fakehash"
    user.created_at = "2025-01-01T00:00:00"
    return user


def _fake_admin():
    return _fake_user(role=UserRole.ADMIN)


def _auth_header(user_id: int = 1, role: str = "user") -> dict[str, str]:
    token = create_access_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


def _fake_company(
    company_id: int = 1,
    *,
    clickup_task_id: str | None = None,
    clickup_task_url: str | None = None,
    clickup_status: str | None = None,
    status: CompanyStatus = CompanyStatus.QUALIFIED,
):
    c = type("Company", (), {})()
    c.id = company_id
    c.name = "Acme Corp"
    c.domain = "acme.com"
    c.industry = "SaaS"
    c.size = "50-200"
    c.location = "Amsterdam"
    c.icp_score = 80.0
    c.lead_score = 75.0
    c.status = status
    c.clickup_task_id = clickup_task_id
    c.clickup_task_url = clickup_task_url
    c.clickup_status = clickup_status
    c.created_at = "2025-01-01T00:00:00"
    c.updated_at = "2025-01-01T00:00:00"
    return c


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /companies/{id}/clickup/push
# ---------------------------------------------------------------------------


class TestPushToClickUp:
    def test_returns_202_on_success(self, client: TestClient) -> None:
        company = _fake_company()
        task = ClickUpTask(
            id="task_123",
            name="Acme Corp",
            status="suspect",
            url="https://app.clickup.com/t/task_123",
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = company
        mock_session.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_session] = lambda: mock_session
        app.dependency_overrides[get_current_user] = lambda: _fake_user()

        with (
            patch("app.api.v1.clickup.settings") as mock_settings,
            patch("app.api.v1.clickup.ClickUpService") as MockService,
        ):
            mock_settings.clickup_api_key = "pk_test"
            mock_settings.clickup_list_id = "list_123"

            mock_service = AsyncMock()
            mock_service.push_company = AsyncMock(return_value=task)
            mock_service.close = AsyncMock()
            MockService.return_value = mock_service

            with patch("app.api.v1.clickup._build_clickup_service", return_value=mock_service):
                response = client.post(
                    "/api/v1/companies/1/clickup/push",
                    headers=_auth_header(),
                )

        app.dependency_overrides.clear()

        assert response.status_code == 202
        data = response.json()
        assert data["task_id"] == "task_123"
        assert data["task_url"] == "https://app.clickup.com/t/task_123"

    def test_returns_404_for_missing_company(self, client: TestClient) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_session] = lambda: mock_session
        app.dependency_overrides[get_current_user] = lambda: _fake_user()

        with patch("app.api.v1.clickup.settings") as mock_settings:
            mock_settings.clickup_api_key = "pk_test"
            mock_settings.clickup_list_id = "list_123"

            response = client.post(
                "/api/v1/companies/999/clickup/push",
                headers=_auth_header(),
            )

        app.dependency_overrides.clear()

        assert response.status_code == 404

    def test_returns_503_when_not_configured(self, client: TestClient) -> None:
        app.dependency_overrides[get_current_user] = lambda: _fake_user()

        with patch("app.api.v1.clickup.settings") as mock_settings:
            mock_settings.clickup_api_key = ""
            mock_settings.clickup_list_id = ""

            response = client.post(
                "/api/v1/companies/1/clickup/push",
                headers=_auth_header(),
            )

        app.dependency_overrides.clear()

        assert response.status_code == 503


# ---------------------------------------------------------------------------
# GET /companies/{id}/clickup/task
# ---------------------------------------------------------------------------


class TestGetClickUpTask:
    def test_returns_task_data(self, client: TestClient) -> None:
        company = _fake_company(clickup_task_id="task_abc")
        task = ClickUpTask(
            id="task_abc",
            name="Acme Corp",
            status="prospect",
            url="https://app.clickup.com/t/task_abc",
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = company
        mock_session.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_session] = lambda: mock_session
        app.dependency_overrides[get_current_user] = lambda: _fake_user()

        mock_service = AsyncMock()
        mock_service.sync_status_from_clickup = AsyncMock(return_value=task)
        mock_service.close = AsyncMock()

        with (
            patch("app.api.v1.clickup.settings") as mock_settings,
            patch("app.api.v1.clickup._build_clickup_service", return_value=mock_service),
        ):
            mock_settings.clickup_api_key = "pk_test"
            mock_settings.clickup_list_id = "list_123"

            response = client.get(
                "/api/v1/companies/1/clickup/task",
                headers=_auth_header(),
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "task_abc"
        assert data["status"] == "prospect"

    def test_returns_404_when_no_task_linked(self, client: TestClient) -> None:
        company = _fake_company(clickup_task_id=None)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = company
        mock_session.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_session] = lambda: mock_session
        app.dependency_overrides[get_current_user] = lambda: _fake_user()

        with patch("app.api.v1.clickup.settings") as mock_settings:
            mock_settings.clickup_api_key = "pk_test"
            mock_settings.clickup_list_id = "list_123"

            response = client.get(
                "/api/v1/companies/1/clickup/task",
                headers=_auth_header(),
            )

        app.dependency_overrides.clear()

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /settings/clickup
# ---------------------------------------------------------------------------


class TestClickUpSettings:
    def test_get_settings_as_admin(self, client: TestClient) -> None:
        app.dependency_overrides[get_current_user] = lambda: _fake_admin()

        # require_role returns a dependency that itself returns the user
        def _override_require_role(*roles):
            def _dep():
                return _fake_admin()

            return _dep

        with (
            patch("app.api.v1.clickup.settings") as mock_settings,
            patch("app.api.v1.clickup.require_role", _override_require_role),
        ):
            mock_settings.clickup_api_key = "pk_test"
            mock_settings.clickup_workspace_id = "ws_1"
            mock_settings.clickup_space_id = "sp_1"
            mock_settings.clickup_folder_id = "fold_1"
            mock_settings.clickup_list_id = "list_1"

            response = client.get(
                "/api/v1/settings/clickup",
                headers=_auth_header(role="admin"),
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is True
        assert data["workspace_id"] == "ws_1"

    def test_update_settings(self, client: TestClient) -> None:
        app.dependency_overrides[get_current_user] = lambda: _fake_admin()

        def _override_require_role(*roles):
            def _dep():
                return _fake_admin()

            return _dep

        with (
            patch("app.api.v1.clickup.settings") as mock_settings,
            patch("app.api.v1.clickup.require_role", _override_require_role),
        ):
            mock_settings.clickup_api_key = "pk_test"
            mock_settings.clickup_workspace_id = "old_ws"
            mock_settings.clickup_space_id = "old_sp"
            mock_settings.clickup_folder_id = "old_fold"
            mock_settings.clickup_list_id = "old_list"

            response = client.put(
                "/api/v1/settings/clickup",
                headers=_auth_header(role="admin"),
                json={"workspace_id": "new_ws"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert mock_settings.clickup_workspace_id == "new_ws"


# ---------------------------------------------------------------------------
# POST /clickup/sync
# ---------------------------------------------------------------------------


class TestClickUpSync:
    def test_dispatches_celery_task(self, client: TestClient) -> None:
        app.dependency_overrides[get_current_user] = lambda: _fake_admin()

        def _override_require_role(*roles):
            def _dep():
                return _fake_admin()

            return _dep

        with (
            patch("app.api.v1.clickup.settings") as mock_settings,
            patch("app.api.v1.clickup.require_role", _override_require_role),
            patch("app.tasks.integrations.sync_to_crm") as mock_task,
        ):
            mock_settings.clickup_api_key = "pk_test"
            mock_settings.clickup_list_id = "list_123"

            mock_celery_result = MagicMock()
            mock_celery_result.id = "celery_task_abc"
            mock_task.delay.return_value = mock_celery_result

            response = client.post(
                "/api/v1/clickup/sync",
                headers=_auth_header(role="admin"),
            )

        app.dependency_overrides.clear()

        assert response.status_code == 202
        data = response.json()
        assert data["task_id"] == "celery_task_abc"
