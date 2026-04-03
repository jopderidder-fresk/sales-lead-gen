"""Tests for ClickUpService — business logic for syncing companies to ClickUp."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models.enums import CompanyStatus, SignalType
from app.services.api.clickup import ClickUpNotFoundError, ClickUpTask
from app.services.clickup import ClickUpService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_company(
    company_id: int = 1,
    *,
    clickup_task_id: str | None = None,
    clickup_task_url: str | None = None,
    clickup_status: str | None = None,
    status: CompanyStatus = CompanyStatus.QUALIFIED,
    lead_score: float | None = 80.0,
    domain: str = "acme.com",
    name: str = "Acme Corp",
):
    c = type("Company", (), {})()
    c.id = company_id
    c.name = name
    c.domain = domain
    c.industry = "SaaS"
    c.size = "50-200"
    c.location = "Amsterdam"
    c.icp_score = 80.0
    c.lead_score = lead_score
    c.status = status
    c.clickup_task_id = clickup_task_id
    c.clickup_task_url = clickup_task_url
    c.clickup_status = clickup_status
    c.created_at = datetime(2025, 1, 1)
    c.updated_at = datetime(2025, 1, 1)
    return c


def _fake_contact(contact_id: int = 1, company_id: int = 1):
    c = type("Contact", (), {})()
    c.id = contact_id
    c.company_id = company_id
    c.name = "Jane Doe"
    c.title = "CTO"
    c.email = "jane@acme.com"
    c.phone = "+31612345678"
    c.linkedin_url = "https://linkedin.com/in/janedoe"
    c.confidence_score = 0.9
    return c


def _fake_signal(signal_id: int = 1, company_id: int = 1, *, crm_commented_at=None):
    s = type("Signal", (), {})()
    s.id = signal_id
    s.company_id = company_id
    s.signal_type = SignalType.HIRING_SURGE
    s.llm_summary = "Hiring 10 engineers"
    s.relevance_score = 85.0
    s.crm_commented_at = crm_commented_at
    s.created_at = datetime(2025, 3, 15, 10, 30)
    return s


def _mock_client() -> AsyncMock:
    client = AsyncMock()
    client.close = AsyncMock()
    return client


def _make_service(client: AsyncMock | None = None) -> ClickUpService:
    c = client or _mock_client()
    return ClickUpService(client=c, domain_field_id="field_domain_123")


def _mock_session_with_company(company):
    """Build a mock session where the first execute returns the company."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = company
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session


def _mock_task(task_id: str = "abc123", status: str | None = "suspect") -> ClickUpTask:
    return ClickUpTask(
        id=task_id,
        name="Acme Corp",
        status=status,
        url=f"https://app.clickup.com/t/{task_id}",
    )


# ---------------------------------------------------------------------------
# push_company — create path
# ---------------------------------------------------------------------------


class TestPushCompanyCreate:
    async def test_creates_task_with_suspect_status(self) -> None:
        """When company has no clickup_task_id, creates task with status='suspect'."""
        company = _fake_company(clickup_task_id=None)
        client = _mock_client()
        task = _mock_task()
        client.create_task = AsyncMock(return_value=task)
        client.find_task_by_custom_field = AsyncMock(return_value=None)

        service = _make_service(client)

        # Session: first execute → company, second → contact, third → signal, fourth → uncommented signals
        call_count = 0
        results = []

        company_result = MagicMock()
        company_result.scalar_one_or_none.return_value = company

        contact_result = MagicMock()
        contact_result.scalar_one_or_none.return_value = _fake_contact()

        signal_result = MagicMock()
        signal_result.scalar_one_or_none.return_value = None

        uncommented_result = MagicMock()
        uncommented_scalars = MagicMock()
        uncommented_scalars.all.return_value = []
        uncommented_result.scalars.return_value = uncommented_scalars

        results = [company_result, contact_result, signal_result, uncommented_result]

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=results)
        session.commit = AsyncMock()

        await service.push_company(session, company.id)

        # Verify create_task was called with status="suspect"
        client.create_task.assert_called_once()
        call_kwargs = client.create_task.call_args
        assert (
            call_kwargs.kwargs.get("status") == "suspect"
            or call_kwargs[1].get("status") == "suspect"
        )

        # Verify company fields were set
        assert company.clickup_task_id == task.id
        assert company.clickup_task_url == task.url
        assert company.clickup_status == "suspect"
        assert company.status == "pushed"

    async def test_deduplicates_by_domain(self) -> None:
        """When find_existing_task returns a match, skips creation."""
        company = _fake_company(clickup_task_id=None)
        existing_task = _mock_task(task_id="existing_123")
        client = _mock_client()
        client.find_task_by_custom_field = AsyncMock(return_value=existing_task)
        client.create_task = AsyncMock()

        service = _make_service(client)

        # We test via sync_qualified_companies which calls _create_new_task
        # which checks dedup before creating.
        company_result = MagicMock()
        companies_scalars = MagicMock()
        companies_scalars.all.return_value = [company]
        company_result.scalars.return_value = companies_scalars

        session = AsyncMock()
        session.execute = AsyncMock(return_value=company_result)
        session.commit = AsyncMock()

        result = await service.sync_qualified_companies(session)

        # create_task should NOT have been called
        client.create_task.assert_not_called()
        # Company should be linked to existing task
        assert company.clickup_task_id == "existing_123"
        assert len(result.skipped) == 1


# ---------------------------------------------------------------------------
# push_company — update path
# ---------------------------------------------------------------------------


class TestPushCompanyUpdate:
    async def test_updates_existing_task(self) -> None:
        """When company already has clickup_task_id, calls update_task."""
        company = _fake_company(clickup_task_id="task_456", clickup_task_url="https://old")
        client = _mock_client()
        updated_task = _mock_task(task_id="task_456", status="prospect")
        client.update_task = AsyncMock(return_value=updated_task)

        service = _make_service(client)

        # Session: company, contact, signal, uncommented signals
        company_result = MagicMock()
        company_result.scalar_one_or_none.return_value = company

        contact_result = MagicMock()
        contact_result.scalar_one_or_none.return_value = None

        signal_result = MagicMock()
        signal_result.scalar_one_or_none.return_value = None

        uncommented_result = MagicMock()
        uncommented_scalars = MagicMock()
        uncommented_scalars.all.return_value = []
        uncommented_result.scalars.return_value = uncommented_scalars

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[company_result, contact_result, signal_result, uncommented_result]
        )
        session.commit = AsyncMock()

        result = await service.push_company(session, company.id)

        client.update_task.assert_called_once()
        assert result.id == "task_456"


# ---------------------------------------------------------------------------
# sync_status_from_clickup
# ---------------------------------------------------------------------------


class TestSyncStatus:
    async def test_updates_when_different(self) -> None:
        """When ClickUp status differs from local, updates DB."""
        company = _fake_company(
            clickup_task_id="task_789",
            clickup_status="suspect",
        )
        client = _mock_client()
        task = _mock_task(task_id="task_789", status="prospect")
        client.get_task = AsyncMock(return_value=task)

        service = _make_service(client)
        session = _mock_session_with_company(company)

        result = await service.sync_status_from_clickup(session, company.id)

        assert result is not None
        assert company.clickup_status == "prospect"
        session.commit.assert_called_once()

    async def test_noop_when_same(self) -> None:
        """When ClickUp status matches local, no commit."""
        company = _fake_company(
            clickup_task_id="task_789",
            clickup_status="suspect",
        )
        client = _mock_client()
        task = _mock_task(task_id="task_789", status="suspect")
        client.get_task = AsyncMock(return_value=task)

        service = _make_service(client)
        session = _mock_session_with_company(company)

        result = await service.sync_status_from_clickup(session, company.id)

        assert result is not None
        assert company.clickup_status == "suspect"
        session.commit.assert_not_called()

    async def test_handles_not_found(self) -> None:
        """When ClickUp task is deleted, returns None."""
        company = _fake_company(clickup_task_id="deleted_task")
        client = _mock_client()
        client.get_task = AsyncMock(side_effect=ClickUpNotFoundError("task", "deleted_task"))

        service = _make_service(client)
        session = _mock_session_with_company(company)

        result = await service.sync_status_from_clickup(session, company.id)

        assert result is None

    async def test_returns_none_when_no_task_id(self) -> None:
        """When company has no clickup_task_id, returns None immediately."""
        company = _fake_company(clickup_task_id=None)
        client = _mock_client()

        service = _make_service(client)
        session = _mock_session_with_company(company)

        result = await service.sync_status_from_clickup(session, company.id)

        assert result is None
        client.get_task.assert_not_called()


# ---------------------------------------------------------------------------
# get_company_task
# ---------------------------------------------------------------------------


class TestGetCompanyTask:
    async def test_returns_task_when_linked(self) -> None:
        company = _fake_company(clickup_task_id="task_aaa")
        client = _mock_client()
        task = _mock_task(task_id="task_aaa")
        client.get_task = AsyncMock(return_value=task)

        service = _make_service(client)
        session = _mock_session_with_company(company)

        result = await service.get_company_task(session, company.id)

        assert result is not None
        assert result.id == "task_aaa"

    async def test_returns_none_when_no_link(self) -> None:
        company = _fake_company(clickup_task_id=None)
        client = _mock_client()

        service = _make_service(client)
        session = _mock_session_with_company(company)

        result = await service.get_company_task(session, company.id)

        assert result is None
        client.get_task.assert_not_called()

    async def test_returns_none_on_not_found(self) -> None:
        company = _fake_company(clickup_task_id="gone_task")
        client = _mock_client()
        client.get_task = AsyncMock(side_effect=ClickUpNotFoundError("task", "gone_task"))

        service = _make_service(client)
        session = _mock_session_with_company(company)

        result = await service.get_company_task(session, company.id)

        assert result is None


# ---------------------------------------------------------------------------
# sync_qualified_companies
# ---------------------------------------------------------------------------


class TestSyncQualifiedCompanies:
    async def test_creates_and_updates(self) -> None:
        """Batch sync creates tasks for new companies, updates existing ones."""
        new_company = _fake_company(company_id=1, clickup_task_id=None)
        existing_company = _fake_company(
            company_id=2,
            clickup_task_id="existing_task",
            status=CompanyStatus.PUSHED,
        )

        client = _mock_client()
        new_task = _mock_task(task_id="new_task_id")
        updated_task = _mock_task(task_id="existing_task")
        client.create_task = AsyncMock(return_value=new_task)
        client.update_task = AsyncMock(return_value=updated_task)
        client.find_task_by_custom_field = AsyncMock(return_value=None)

        service = _make_service(client)

        # First call: query for qualifying companies
        companies_result = MagicMock()
        companies_scalars = MagicMock()
        companies_scalars.all.return_value = [new_company, existing_company]
        companies_result.scalars.return_value = companies_scalars

        # For the new company: contact, signal, uncommented signals queries
        contact_result = MagicMock()
        contact_result.scalar_one_or_none.return_value = None
        signal_result = MagicMock()
        signal_result.scalar_one_or_none.return_value = None
        uncommented_result = MagicMock()
        uncommented_scalars = MagicMock()
        uncommented_scalars.all.return_value = []
        uncommented_result.scalars.return_value = uncommented_scalars

        # For the existing company: same queries
        contact_result2 = MagicMock()
        contact_result2.scalar_one_or_none.return_value = None
        signal_result2 = MagicMock()
        signal_result2.scalar_one_or_none.return_value = None
        uncommented_result2 = MagicMock()
        uncommented_scalars2 = MagicMock()
        uncommented_scalars2.all.return_value = []
        uncommented_result2.scalars.return_value = uncommented_scalars2

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                companies_result,
                # new company: contact, signal, uncommented
                contact_result,
                signal_result,
                uncommented_result,
                # existing company: contact, signal, uncommented
                contact_result2,
                signal_result2,
                uncommented_result2,
            ]
        )
        session.commit = AsyncMock()

        result = await service.sync_qualified_companies(session)

        assert len(result.created) == 1
        assert len(result.updated) == 1
        assert result.created[0] == (1, "new_task_id")
        assert result.updated[0] == (2, "existing_task")


# ---------------------------------------------------------------------------
# Signal comments
# ---------------------------------------------------------------------------


class TestSignalComments:
    async def test_posts_uncommented_signals(self) -> None:
        """After creating a task, posts uncommented signals as comments."""
        company = _fake_company(clickup_task_id=None)
        sig1 = _fake_signal(signal_id=1, crm_commented_at=None)
        sig2 = _fake_signal(signal_id=2, crm_commented_at=None)

        client = _mock_client()
        task = _mock_task()
        client.create_task = AsyncMock(return_value=task)
        client.find_task_by_custom_field = AsyncMock(return_value=None)
        client.add_comment = AsyncMock(return_value=MagicMock(id="comment_1"))

        service = _make_service(client)

        # Session calls for push_company → _create_company_task
        company_result = MagicMock()
        company_result.scalar_one_or_none.return_value = company

        contact_result = MagicMock()
        contact_result.scalar_one_or_none.return_value = None

        signal_result = MagicMock()
        signal_result.scalar_one_or_none.return_value = None

        uncommented_result = MagicMock()
        uncommented_scalars = MagicMock()
        uncommented_scalars.all.return_value = [sig1, sig2]
        uncommented_result.scalars.return_value = uncommented_scalars

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[company_result, contact_result, signal_result, uncommented_result]
        )
        session.commit = AsyncMock()

        await service.push_company(session, company.id)

        # Two signals should have been commented on
        assert client.add_comment.call_count == 2
        assert sig1.crm_commented_at is not None
        assert sig2.crm_commented_at is not None


# ---------------------------------------------------------------------------
# Description builder
# ---------------------------------------------------------------------------


class TestBuildDescription:
    def test_includes_company_info(self) -> None:
        """Description includes company name, domain, industry, and scores."""
        company = _fake_company()
        service = _make_service()

        description = service._build_description(company, None, None)

        assert "Acme Corp" in description
        assert "acme.com" in description
        assert "SaaS" in description

    def test_includes_contact_info(self) -> None:
        """Description includes contact details when provided."""
        company = _fake_company()
        contact = _fake_contact()
        service = _make_service()

        description = service._build_description(company, contact, None)

        assert "Jane Doe" in description
        assert "CTO" in description
        assert "jane@acme.com" in description

    def test_includes_signal_info(self) -> None:
        """Description includes signal details when provided."""
        company = _fake_company()
        signal = _fake_signal()
        service = _make_service()

        description = service._build_description(company, None, signal)

        assert "hiring_surge" in description
        assert "Hiring 10 engineers" in description
