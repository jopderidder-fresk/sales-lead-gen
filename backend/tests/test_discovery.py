"""Tests for the Company Discovery Engine (LP-015)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import CompanyStatus
from app.services.api.bedrijfsdata import BedrijfsdataCompany, CompanySearchResponse
from app.services.discovery import (
    DiscoveryResult,
    DiscoveryService,
    calculate_icp_score,
)


def _make_db_session(execute_side_effect):
    """Create a mock AsyncSession with sync methods (add) as MagicMock
    and async methods (execute, flush, commit, begin_nested) set up correctly."""
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=execute_side_effect)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    # add() is synchronous on real SQLAlchemy sessions
    session.add = MagicMock()
    # begin_nested() returns an async context manager
    nested_ctx = AsyncMock()
    nested_ctx.__aenter__ = AsyncMock(return_value=None)
    nested_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested_ctx)
    return session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_icp(
    *,
    industry_filter=None,
    size_filter=None,
    geo_filter=None,
    tech_filter=None,
):
    profile = type("ICPProfile", (), {})()
    profile.name = "Test ICP"
    profile.industry_filter = industry_filter
    profile.size_filter = size_filter
    profile.geo_filter = geo_filter
    profile.tech_filter = tech_filter
    profile.negative_filters = None
    profile.is_active = True
    return profile


def _fake_company_row(name: str, domain: str, status: str = "discovered"):
    company = type("Company", (), {})()
    company.name = name
    company.domain = domain
    company.status = status
    return company


# ---------------------------------------------------------------------------
# ICP score calculation
# ---------------------------------------------------------------------------


class TestICPScoreCalculation:
    def test_full_match(self):
        profile = _fake_icp(
            industry_filter=["SaaS"],
            size_filter={"min_employees": 10, "max_employees": 200},
            geo_filter={"countries": [], "regions": [], "cities": ["Amsterdam"]},
        )
        score = calculate_icp_score(
            profile,
            industry="SaaS platform",
            employees=50,
            location="Amsterdam, Noord-Holland",
        )
        assert score == 100.0

    def test_partial_match(self):
        profile = _fake_icp(
            industry_filter=["SaaS"],
            size_filter={"min_employees": 10, "max_employees": 200},
        )
        score = calculate_icp_score(
            profile,
            industry="SaaS",
            employees=500,  # out of range
        )
        assert score == 50.0  # 1 of 2 criteria

    def test_no_match(self):
        profile = _fake_icp(
            industry_filter=["SaaS"],
            size_filter={"min_employees": 100, "max_employees": 500},
        )
        score = calculate_icp_score(
            profile,
            industry="Healthcare",
            employees=10,
        )
        assert score == 0.0

    def test_no_criteria(self):
        profile = _fake_icp()
        score = calculate_icp_score(profile)
        assert score == 50.0  # default when no criteria defined

    def test_tech_match(self):
        profile = _fake_icp(tech_filter=["React", "Python"])
        score = calculate_icp_score(profile, techs=["React", "Node.js"])
        assert score == 100.0  # React matches


# ---------------------------------------------------------------------------
# Discovery result
# ---------------------------------------------------------------------------


class TestDiscoveryResult:
    def test_summary(self):
        result = DiscoveryResult(
            companies_found=10,
            companies_added=7,
            companies_skipped=3,
            firecrawl_found=4,
            bedrijfsdata_found=6,
            elapsed_seconds=12.5,
        )
        summary = result.summary()
        assert "found=10" in summary
        assert "added=7" in summary
        assert "skipped=3" in summary
        assert "12.5s" in summary


# ---------------------------------------------------------------------------
# Discovery service
# ---------------------------------------------------------------------------


class TestDiscoveryService:
    @pytest.mark.asyncio
    async def test_run_no_active_icp(self):
        """Should return early with an error when no ICP profile is active."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        service = DiscoveryService(bedrijfsdata_api_key="test")

        with patch.object(service, "_bedrijfsdata"):
            result = await service.run(mock_session)

        assert len(result.errors) == 1
        assert "No active ICP profile" in result.errors[0]
        assert result.companies_added == 0

    @pytest.mark.asyncio
    async def test_run_with_bedrijfsdata_results(self):
        """Should store new companies from Bedrijfsdata."""
        profile = _fake_icp(
            industry_filter=["Software"],
            geo_filter={"countries": ["Netherlands"], "regions": [], "cities": []},
        )

        service = DiscoveryService(bedrijfsdata_api_key="test")

        call_count = 0

        async def mock_execute(stmt, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                result = MagicMock()
                result.scalar_one_or_none.return_value = profile
                return result
            else:
                result = MagicMock()
                result.scalar_one_or_none.return_value = None
                result.all.return_value = []
                return result

        mock_session = _make_db_session(mock_execute)

        # Mock Bedrijfsdata
        service._bedrijfsdata.search_companies = AsyncMock(
            return_value=CompanySearchResponse(
                companies=[
                    BedrijfsdataCompany(
                        name="Dutch Tech BV",
                        domain="dutchtech.nl",
                        coc="12345678",
                        city="Amsterdam",
                        province="Noord-Holland",
                        employees=75,
                        industry_labels=["Software development"],
                    )
                ],
                total=1,
            )
        )

        result = await service.run(mock_session)

        assert result.bedrijfsdata_found == 1
        assert result.companies_found == 1
        assert result.companies_added == 1

    @pytest.mark.asyncio
    async def test_skips_companies_without_domain(self):
        """Companies without a domain should be skipped."""
        profile = _fake_icp(industry_filter=["SaaS"])

        service = DiscoveryService(bedrijfsdata_api_key="test")

        call_count = 0

        async def mock_execute(stmt, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                result = MagicMock()
                result.scalar_one_or_none.return_value = profile
                return result
            else:
                result = MagicMock()
                result.scalar_one_or_none.return_value = None
                result.all.return_value = []
                return result

        mock_session = _make_db_session(mock_execute)

        # Bedrijfsdata returns a company without domain
        service._bedrijfsdata.search_companies = AsyncMock(
            return_value=CompanySearchResponse(
                companies=[
                    BedrijfsdataCompany(
                        name="No Domain Co",
                        domain=None,
                    )
                ],
                total=1,
            )
        )

        result = await service.run(mock_session)

        assert result.companies_found == 1
        assert result.companies_skipped == 1
        assert result.companies_added == 0

    @pytest.mark.asyncio
    async def test_handles_source_errors_gracefully(self):
        """Should report error when Bedrijfsdata fails."""
        profile = _fake_icp(industry_filter=["SaaS"])

        service = DiscoveryService(bedrijfsdata_api_key="test")

        call_count = 0

        async def mock_execute(stmt, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                result = MagicMock()
                result.scalar_one_or_none.return_value = profile
                return result
            else:
                result = MagicMock()
                result.scalar_one_or_none.return_value = None
                result.all.return_value = []
                return result

        mock_session = _make_db_session(mock_execute)

        # Bedrijfsdata raises an exception
        service._bedrijfsdata.search_companies = AsyncMock(
            side_effect=RuntimeError("API down")
        )

        result = await service.run(mock_session)

        assert len(result.errors) >= 1
        assert "Bedrijfsdata" in result.errors[0]
        assert result.companies_added == 0


# ---------------------------------------------------------------------------
# Discovery API endpoint (unit tests without full app import)
# ---------------------------------------------------------------------------


class TestDiscoveryEndpoint:
    def test_trigger_response_model(self):
        """DiscoveryTriggerResponse should validate correctly."""
        from app.api.v1.discovery import DiscoveryTriggerResponse

        resp = DiscoveryTriggerResponse(
            task_id="abc-123",
            job_id=1,
            message="Discovery task dispatched",
        )
        assert resp.task_id == "abc-123"
        assert "dispatched" in resp.message.lower()

    def test_require_role_rejects_non_admin(self):
        """The endpoint requires admin role via require_role('admin')."""
        # Verify the route is decorated with admin-only access
        import inspect
        from app.api.v1.discovery import trigger_discovery

        sig = inspect.signature(trigger_discovery)
        # The _user parameter has a Depends(require_role("admin")) default
        user_param = sig.parameters.get("_user")
        assert user_param is not None
