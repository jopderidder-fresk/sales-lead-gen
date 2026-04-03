"""Tests for company sub-resource endpoints: contacts, signals, scrape jobs."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.database import get_session
from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.main import app
from app.models.enums import (
    CompanyStatus,
    EmailStatus,
    ScrapeJobStatus,
    SignalAction,
    SignalType,
    UserRole,
)
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


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


def _auth_header(user_id: int = 1, role: str = "user") -> dict[str, str]:
    token = create_access_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


def _fake_company(company_id: int = 1, status: CompanyStatus = CompanyStatus.DISCOVERED):
    c = type("Company", (), {})()
    c.id = company_id
    c.name = "Acme Corp"
    c.domain = "acme.com"
    c.industry = "SaaS"
    c.size = "50-200"
    c.location = "Amsterdam"
    c.icp_score = 80.0
    c.status = status
    c.clickup_task_id = None
    c.created_at = "2025-01-01T00:00:00"
    c.updated_at = "2025-01-01T00:00:00"
    return c


def _fake_contact(contact_id: int = 1, company_id: int = 1):
    c = type("Contact", (), {})()
    c.id = contact_id
    c.company_id = company_id
    c.name = "Jane Doe"
    c.title = "CTO"
    c.email = "jane@acme.com"
    c.email_status = EmailStatus.VERIFIED
    c.phone = "+31612345678"
    c.linkedin_url = "https://linkedin.com/in/janedoe"
    c.source = "hunter"
    c.confidence_score = 0.9
    c.created_at = "2025-01-01T00:00:00"
    return c


def _fake_signal(signal_id: int = 1, company_id: int = 1):
    s = type("Signal", (), {})()
    s.id = signal_id
    s.company_id = company_id
    s.signal_type = SignalType.HIRING_SURGE
    s.source_url = "https://acme.com/jobs"
    s.source_title = "Careers"
    s.llm_summary = "Company is hiring aggressively."
    s.relevance_score = 0.85
    s.action_taken = SignalAction.NOTIFY_IMMEDIATE
    s.created_at = "2025-01-01T00:00:00"
    return s


def _fake_scrape_job(job_id: int = 1, company_id: int = 1):
    j = type("ScrapeJob", (), {})()
    j.id = job_id
    j.company_id = company_id
    j.target_url = "https://acme.com"
    j.status = ScrapeJobStatus.COMPLETED
    j.pages_scraped = 5
    j.credits_used = 0.05
    j.error_message = None
    j.started_at = "2025-01-01T00:00:00"
    j.completed_at = "2025-01-01T00:01:00"
    j.created_at = "2025-01-01T00:00:00"
    return j


def _make_session_mock(company, items, count: int):
    """Build an AsyncMock session that returns company on first execute,
    count on second, and items on third."""
    company_result = MagicMock()
    company_result.scalar_one_or_none.return_value = company

    count_result = MagicMock()
    count_result.scalar_one.return_value = count

    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = items

    mock_session = AsyncMock()
    mock_session.execute.side_effect = [company_result, count_result, items_result]
    return mock_session


@pytest.fixture()
def _override_auth_contacts():
    user = _fake_user()
    company = _fake_company()
    contacts = [_fake_contact(1), _fake_contact(2)]
    mock_session = _make_session_mock(company, contacts, 2)

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = lambda: mock_session
    yield user, mock_session
    app.dependency_overrides.clear()


@pytest.fixture()
def _override_auth_signals():
    user = _fake_user()
    company = _fake_company()
    signals = [_fake_signal(1), _fake_signal(2)]
    mock_session = _make_session_mock(company, signals, 2)

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = lambda: mock_session
    yield user, mock_session
    app.dependency_overrides.clear()


@pytest.fixture()
def _override_auth_scrape_jobs():
    user = _fake_user()
    company = _fake_company()
    jobs = [_fake_scrape_job(1), _fake_scrape_job(2)]
    mock_session = _make_session_mock(company, jobs, 2)

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = lambda: mock_session
    yield user, mock_session
    app.dependency_overrides.clear()


def _override_auth_404():
    """Session that returns None for company lookup (404 scenario)."""
    user = _fake_user()
    not_found_result = MagicMock()
    not_found_result.scalar_one_or_none.return_value = None
    mock_session = AsyncMock()
    mock_session.execute.return_value = not_found_result
    return user, mock_session


def _override_auth_empty(model_class_name: str = "items"):
    """Session that returns a company but empty list."""
    user = _fake_user()
    company = _fake_company()
    mock_session = _make_session_mock(company, [], 0)
    return user, mock_session, company


# ---------------------------------------------------------------------------
# GET /api/v1/companies/{id}/contacts
# ---------------------------------------------------------------------------


class TestCompanyContacts:
    def test_list_contacts_success(self, client: TestClient, _override_auth_contacts) -> None:
        response = client.get("/api/v1/companies/1/contacts", headers=_auth_header())
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["name"] == "Jane Doe"
        assert data["items"][0]["email_status"] == "verified"

    def test_list_contacts_empty(self, client: TestClient) -> None:
        user, mock_session, _ = _override_auth_empty()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_session] = lambda: mock_session
        try:
            response = client.get("/api/v1/companies/1/contacts", headers=_auth_header())
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert data["items"] == []
        finally:
            app.dependency_overrides.clear()

    def test_list_contacts_company_not_found(self, client: TestClient) -> None:
        user, mock_session = _override_auth_404()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_session] = lambda: mock_session
        try:
            response = client.get("/api/v1/companies/999/contacts", headers=_auth_header())
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_list_contacts_archived_company_returns_404(self, client: TestClient) -> None:
        user = _fake_user()
        company = _fake_company(status=CompanyStatus.ARCHIVED)
        archived_result = MagicMock()
        archived_result.scalar_one_or_none.return_value = company
        mock_session = AsyncMock()
        mock_session.execute.return_value = archived_result
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_session] = lambda: mock_session
        try:
            response = client.get("/api/v1/companies/1/contacts", headers=_auth_header())
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_list_contacts_pagination(self, client: TestClient, _override_auth_contacts) -> None:
        response = client.get(
            "/api/v1/companies/1/contacts?offset=0&limit=1", headers=_auth_header()
        )
        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 0
        assert data["limit"] == 1

    def test_list_contacts_unauthenticated(self, client: TestClient) -> None:
        response = client.get("/api/v1/companies/1/contacts")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/v1/companies/{id}/signals
# ---------------------------------------------------------------------------


class TestCompanySignals:
    def test_list_signals_success(self, client: TestClient, _override_auth_signals) -> None:
        response = client.get("/api/v1/companies/1/signals", headers=_auth_header())
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["signal_type"] == "hiring_surge"
        assert data["items"][0]["action_taken"] == "notify_immediate"

    def test_list_signals_empty(self, client: TestClient) -> None:
        user, mock_session, _ = _override_auth_empty()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_session] = lambda: mock_session
        try:
            response = client.get("/api/v1/companies/1/signals", headers=_auth_header())
            assert response.status_code == 200
            assert response.json()["total"] == 0
        finally:
            app.dependency_overrides.clear()

    def test_list_signals_company_not_found(self, client: TestClient) -> None:
        user, mock_session = _override_auth_404()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_session] = lambda: mock_session
        try:
            response = client.get("/api/v1/companies/999/signals", headers=_auth_header())
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_list_signals_with_type_filter(self, client: TestClient) -> None:
        user = _fake_user()
        company = _fake_company()
        signals = [_fake_signal(1)]
        mock_session = _make_session_mock(company, signals, 1)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_session] = lambda: mock_session
        try:
            response = client.get(
                "/api/v1/companies/1/signals?signal_type=hiring_surge",
                headers=_auth_header(),
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_list_signals_unauthenticated(self, client: TestClient) -> None:
        response = client.get("/api/v1/companies/1/signals")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/v1/companies/{id}/scrape-jobs
# ---------------------------------------------------------------------------


class TestCompanyScrapeJobs:
    def test_list_scrape_jobs_success(self, client: TestClient, _override_auth_scrape_jobs) -> None:
        response = client.get("/api/v1/companies/1/scrape-jobs", headers=_auth_header())
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["status"] == "completed"
        assert data["items"][0]["target_url"] == "https://acme.com"

    def test_list_scrape_jobs_empty(self, client: TestClient) -> None:
        user, mock_session, _ = _override_auth_empty()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_session] = lambda: mock_session
        try:
            response = client.get("/api/v1/companies/1/scrape-jobs", headers=_auth_header())
            assert response.status_code == 200
            assert response.json()["total"] == 0
        finally:
            app.dependency_overrides.clear()

    def test_list_scrape_jobs_company_not_found(self, client: TestClient) -> None:
        user, mock_session = _override_auth_404()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_session] = lambda: mock_session
        try:
            response = client.get("/api/v1/companies/999/scrape-jobs", headers=_auth_header())
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_list_scrape_jobs_with_status_filter(self, client: TestClient) -> None:
        user = _fake_user()
        company = _fake_company()
        jobs = [_fake_scrape_job(1)]
        mock_session = _make_session_mock(company, jobs, 1)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_session] = lambda: mock_session
        try:
            response = client.get(
                "/api/v1/companies/1/scrape-jobs?status=completed",
                headers=_auth_header(),
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_list_scrape_jobs_unauthenticated(self, client: TestClient) -> None:
        response = client.get("/api/v1/companies/1/scrape-jobs")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /{company_id}/scrape | enrich | contacts | pipeline — ICP guard
# ---------------------------------------------------------------------------


class TestRequireActiveICP:
    """All pipeline-triggering endpoints must reject with 422 when no ICP is active."""

    ENDPOINTS = [
        "/api/v1/companies/1/scrape",
        "/api/v1/companies/1/enrich",
        "/api/v1/companies/1/contacts",
        "/api/v1/companies/1/pipeline",
    ]

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_returns_422_when_no_active_icp(self, client: TestClient, endpoint: str) -> None:
        user = _fake_user()
        # Session returns None for the ICP lookup (scalar_one_or_none)
        no_icp_result = MagicMock()
        no_icp_result.scalar_one_or_none.return_value = None
        mock_session = AsyncMock()
        mock_session.execute.return_value = no_icp_result

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_session] = lambda: mock_session
        try:
            response = client.post(endpoint, headers=_auth_header())
            assert response.status_code == 422
            assert "ICP" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()
