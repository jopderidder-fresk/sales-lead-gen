"""Tests for ICP Profile CRUD endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from app.core.database import get_session
from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.main import app
from app.models.enums import UserRole
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_user(
    user_id: int = 1,
    username: str = "testuser",
    role: UserRole = UserRole.USER,
):
    user = type("User", (), {})()
    user.id = user_id
    user.username = username
    user.email = f"{username}@test.com"
    user.role = role
    user.password_hash = "fakehash"
    user.created_at = "2025-01-01T00:00:00"
    return user


def _auth_header(user_id: int = 1, role: str = "user") -> dict[str, str]:
    token = create_access_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


def _fake_profile(
    profile_id: int = 1,
    name: str = "Default ICP",
    is_active: bool = False,
):
    profile = type("ICPProfile", (), {})()
    profile.id = profile_id
    profile.name = name
    profile.industry_filter = ["SaaS", "FinTech"]
    profile.size_filter = {
        "min_employees": 10,
        "max_employees": 500,
        "min_revenue": None,
        "max_revenue": None,
    }
    profile.geo_filter = {"countries": ["US"], "regions": [], "cities": []}
    profile.tech_filter = ["Python", "AWS"]
    profile.negative_filters = {
        "excluded_industries": ["Gambling"],
        "excluded_domains": [],
    }
    profile.is_active = is_active
    profile.created_at = "2025-01-01T00:00:00"
    return profile


@pytest.fixture()
def _override_auth():
    """Override get_current_user and get_session to bypass DB/auth.

    Uses admin role so tests for admin-only endpoints (activate, delete) pass.
    """
    user = _fake_user(role=UserRole.ADMIN)
    mock_session = AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = lambda: mock_session
    yield user, mock_session
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/icp-profiles (Create)
# ---------------------------------------------------------------------------


class TestCreateProfile:
    def test_create_profile_success(
        self,
        client: TestClient,
        _override_auth,
    ) -> None:
        created = _fake_profile(profile_id=1)
        with patch(
            "app.api.v1.icp_profiles.icp_service.create_profile",
            return_value=created,
        ) as mock_create:
            response = client.post(
                "/api/v1/icp-profiles",
                json={
                    "name": "Default ICP",
                    "industry_filter": ["SaaS", "FinTech"],
                    "size_filter": {"min_employees": 10, "max_employees": 500},
                    "tech_filter": ["Python", "AWS"],
                },
                headers=_auth_header(),
            )
            mock_create.assert_called_once()

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Default ICP"
        assert data["industry_filter"] == ["SaaS", "FinTech"]
        assert data["is_active"] is False

    def test_create_profile_no_filters_fails(
        self,
        client: TestClient,
        _override_auth,
    ) -> None:
        response = client.post(
            "/api/v1/icp-profiles",
            json={"name": "Empty ICP"},
            headers=_auth_header(),
        )
        assert response.status_code == 422

    def test_create_profile_invalid_size_range(
        self,
        client: TestClient,
        _override_auth,
    ) -> None:
        response = client.post(
            "/api/v1/icp-profiles",
            json={
                "name": "Bad Range",
                "size_filter": {"min_employees": 500, "max_employees": 10},
            },
            headers=_auth_header(),
        )
        assert response.status_code == 422

    def test_create_profile_unauthenticated(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/icp-profiles",
            json={"name": "Test", "industry_filter": ["SaaS"]},
        )
        assert response.status_code in (401, 403)

    def test_create_profile_empty_name_fails(
        self,
        client: TestClient,
        _override_auth,
    ) -> None:
        response = client.post(
            "/api/v1/icp-profiles",
            json={"name": "", "industry_filter": ["SaaS"]},
            headers=_auth_header(),
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/icp-profiles (List)
# ---------------------------------------------------------------------------


class TestListProfiles:
    def test_list_profiles(
        self,
        client: TestClient,
        _override_auth,
    ) -> None:
        profiles = [_fake_profile(1, "ICP A"), _fake_profile(2, "ICP B")]
        with patch(
            "app.api.v1.icp_profiles.icp_service.list_profiles",
            return_value=profiles,
        ):
            response = client.get(
                "/api/v1/icp-profiles",
                headers=_auth_header(),
            )

        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_profiles_unauthenticated(self, client: TestClient) -> None:
        response = client.get("/api/v1/icp-profiles")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/v1/icp-profiles/{id} (Get single)
# ---------------------------------------------------------------------------


class TestGetProfile:
    def test_get_profile_success(
        self,
        client: TestClient,
        _override_auth,
    ) -> None:
        profile = _fake_profile(1)
        with patch(
            "app.api.v1.icp_profiles.icp_service.get_profile",
            return_value=profile,
        ):
            response = client.get(
                "/api/v1/icp-profiles/1",
                headers=_auth_header(),
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "Default ICP"

    def test_get_profile_not_found(
        self,
        client: TestClient,
        _override_auth,
    ) -> None:
        with patch(
            "app.api.v1.icp_profiles.icp_service.get_profile",
            return_value=None,
        ):
            response = client.get(
                "/api/v1/icp-profiles/999",
                headers=_auth_header(),
            )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/v1/icp-profiles/{id} (Update)
# ---------------------------------------------------------------------------


class TestUpdateProfile:
    def test_update_profile_success(
        self,
        client: TestClient,
        _override_auth,
    ) -> None:
        existing = _fake_profile(1)
        updated = _fake_profile(1, name="Updated ICP")

        with (
            patch(
                "app.api.v1.icp_profiles.icp_service.get_profile",
                return_value=existing,
            ),
            patch(
                "app.api.v1.icp_profiles.icp_service.update_profile",
                return_value=updated,
            ),
        ):
            response = client.put(
                "/api/v1/icp-profiles/1",
                json={"name": "Updated ICP"},
                headers=_auth_header(),
            )

        assert response.status_code == 200
        assert response.json()["name"] == "Updated ICP"

    def test_update_profile_not_found(
        self,
        client: TestClient,
        _override_auth,
    ) -> None:
        with patch(
            "app.api.v1.icp_profiles.icp_service.get_profile",
            return_value=None,
        ):
            response = client.put(
                "/api/v1/icp-profiles/999",
                json={"name": "Nope"},
                headers=_auth_header(),
            )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/icp-profiles/{id}/activate
# ---------------------------------------------------------------------------


class TestActivateProfile:
    def test_activate_profile_success(
        self,
        client: TestClient,
        _override_auth,
    ) -> None:
        profile = _fake_profile(1)
        activated = _fake_profile(1, is_active=True)

        with (
            patch(
                "app.api.v1.icp_profiles.icp_service.get_profile",
                return_value=profile,
            ),
            patch(
                "app.api.v1.icp_profiles.icp_service.activate_profile",
                return_value=activated,
            ),
        ):
            response = client.post(
                "/api/v1/icp-profiles/1/activate",
                headers=_auth_header(),
            )

        assert response.status_code == 200
        assert response.json()["is_active"] is True

    def test_activate_profile_not_found(
        self,
        client: TestClient,
        _override_auth,
    ) -> None:
        with patch(
            "app.api.v1.icp_profiles.icp_service.get_profile",
            return_value=None,
        ):
            response = client.post(
                "/api/v1/icp-profiles/999/activate",
                headers=_auth_header(),
            )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/icp-profiles/{id}
# ---------------------------------------------------------------------------


class TestDeleteProfile:
    def test_delete_profile_success(
        self,
        client: TestClient,
        _override_auth,
    ) -> None:
        profile = _fake_profile(1, is_active=False)

        with (
            patch(
                "app.api.v1.icp_profiles.icp_service.get_profile",
                return_value=profile,
            ),
            patch(
                "app.api.v1.icp_profiles.icp_service.delete_profile",
            ) as mock_delete,
        ):
            response = client.delete(
                "/api/v1/icp-profiles/1",
                headers=_auth_header(),
            )
            mock_delete.assert_called_once()

        assert response.status_code == 204

    def test_delete_active_profile_returns_409(
        self,
        client: TestClient,
        _override_auth,
    ) -> None:
        profile = _fake_profile(1, is_active=True)

        with patch(
            "app.api.v1.icp_profiles.icp_service.get_profile",
            return_value=profile,
        ):
            response = client.delete(
                "/api/v1/icp-profiles/1",
                headers=_auth_header(),
            )

        assert response.status_code == 409
        assert "active" in response.json()["detail"].lower()

    def test_delete_profile_not_found(
        self,
        client: TestClient,
        _override_auth,
    ) -> None:
        with patch(
            "app.api.v1.icp_profiles.icp_service.get_profile",
            return_value=None,
        ):
            response = client.delete(
                "/api/v1/icp-profiles/999",
                headers=_auth_header(),
            )

        assert response.status_code == 404

    def test_delete_profile_unauthenticated(self, client: TestClient) -> None:
        response = client.delete("/api/v1/icp-profiles/1")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Schema validation unit tests
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_size_filter_valid(self) -> None:
        from app.schemas.icp_profile import SizeFilter

        f = SizeFilter(min_employees=10, max_employees=500)
        assert f.min_employees == 10

    def test_size_filter_invalid_range(self) -> None:
        from app.schemas.icp_profile import SizeFilter

        with pytest.raises(ValueError, match="min_employees must be less than max_employees"):
            SizeFilter(min_employees=500, max_employees=10)

    def test_size_filter_equal_values_invalid(self) -> None:
        from app.schemas.icp_profile import SizeFilter

        with pytest.raises(ValueError, match="min_employees must be less than max_employees"):
            SizeFilter(min_employees=100, max_employees=100)

    def test_revenue_filter_invalid_range(self) -> None:
        from app.schemas.icp_profile import SizeFilter

        with pytest.raises(ValueError, match="min_revenue must be less than max_revenue"):
            SizeFilter(min_revenue=1_000_000, max_revenue=100)

    def test_create_requires_positive_filter(self) -> None:
        from app.schemas.icp_profile import ICPProfileCreate

        with pytest.raises(ValueError, match="At least one positive filter"):
            ICPProfileCreate(name="Empty")

    def test_create_with_only_negative_filter_fails(self) -> None:
        from app.schemas.icp_profile import ICPProfileCreate, NegativeFilters

        with pytest.raises(ValueError, match="At least one positive filter"):
            ICPProfileCreate(
                name="Negative Only",
                negative_filters=NegativeFilters(excluded_industries=["Gambling"]),
            )

    def test_create_with_geo_filter_succeeds(self) -> None:
        from app.schemas.icp_profile import GeoFilter, ICPProfileCreate

        profile = ICPProfileCreate(
            name="Geo Only",
            geo_filter=GeoFilter(countries=["US"]),
        )
        assert profile.name == "Geo Only"

    def test_create_with_empty_geo_filter_fails(self) -> None:
        from app.schemas.icp_profile import GeoFilter, ICPProfileCreate

        with pytest.raises(ValueError, match="At least one positive filter"):
            ICPProfileCreate(
                name="Empty Geo",
                geo_filter=GeoFilter(),
            )
