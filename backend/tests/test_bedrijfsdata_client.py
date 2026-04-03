"""Tests for the Bedrijfsdata.nl API client."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from app.services.api.bedrijfsdata import (
    BedrijfsdataClient,
    BedrijfsdataNotFoundError,
    BedrijfsdataQuotaExceededError,
    CompanySearchResponse,
    CorporateFamilyResponse,
    EnrichResponse,
    industries_to_sbi_codes,
)
from app.services.api.errors import AuthenticationError

if TYPE_CHECKING:
    from collections.abc import Iterator


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> BedrijfsdataClient:
    return BedrijfsdataClient(api_key="test-key")


def _mock_response(
    status_code: int = 200,
    json_data: dict | None = None,
) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_data or {},
        request=httpx.Request("GET", "https://api.bedrijfsdata.nl/v1.2/test"),
    )


@contextmanager
def _patch_client(
    client: BedrijfsdataClient,
    response: httpx.Response | None = None,
    *,
    side_effect: Exception | None = None,
) -> Iterator[AsyncMock]:
    """Patch _send, rate limiter, and usage tracker on *client*.

    Yields the ``_send`` mock so callers can inspect ``call_args``.
    """
    send_kwargs: dict = {"new_callable": AsyncMock}
    if side_effect is not None:
        send_kwargs["side_effect"] = side_effect
    else:
        send_kwargs["return_value"] = response

    with (
        patch.object(client, "_send", **send_kwargs) as mock_send,
        patch.object(
            client._rate_limiter,
            "acquire",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch.object(client, "_track_usage", new_callable=AsyncMock),
    ):
        yield mock_send


def _sent_params(mock_send: AsyncMock) -> dict:
    """Extract the ``params`` dict from the most recent mock_send call."""
    kw = mock_send.call_args.kwargs
    return kw.get("params") or mock_send.call_args[1].get("params", {})


# ---------------------------------------------------------------------------
# SBI code mapping
# ---------------------------------------------------------------------------


class TestSbiCodeMapping:
    def test_known_industry(self) -> None:
        codes = industries_to_sbi_codes(["SaaS"])
        assert "6201" in codes
        assert "6202" in codes

    def test_case_insensitive(self) -> None:
        assert industries_to_sbi_codes(["FINTECH"]) == industries_to_sbi_codes(["fintech"])

    def test_multiple_industries(self) -> None:
        codes = industries_to_sbi_codes(["SaaS", "Healthcare"])
        assert "6201" in codes  # from SaaS
        assert "8610" in codes  # from Healthcare

    def test_unknown_industry_skipped(self) -> None:
        codes = industries_to_sbi_codes(["nonexistent_industry_xyz"])
        assert codes == []

    def test_mixed_known_unknown(self) -> None:
        codes = industries_to_sbi_codes(["SaaS", "nonexistent"])
        assert len(codes) > 0
        assert "6201" in codes

    def test_deduplication(self) -> None:
        # "saas" and "software" share the same SBI codes
        codes = industries_to_sbi_codes(["SaaS", "Software"])
        assert len(codes) == len(set(codes))

    def test_empty_list(self) -> None:
        assert industries_to_sbi_codes([]) == []

    def test_whitespace_handling(self) -> None:
        codes = industries_to_sbi_codes(["  saas  "])
        assert "6201" in codes


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestBedrijfsdataErrors:
    def test_quota_exceeded_error(self) -> None:
        err = BedrijfsdataQuotaExceededError()
        assert err.status_code == 402
        assert err.provider == "bedrijfsdata"

    def test_not_found_error(self) -> None:
        err = BedrijfsdataNotFoundError()
        assert err.status_code == 404
        assert err.provider == "bedrijfsdata"

    def test_402_raises_quota(self, client: BedrijfsdataClient) -> None:
        resp = _mock_response(402, {"error": "Quota exceeded"})
        with pytest.raises(BedrijfsdataQuotaExceededError):
            client._check_response(resp)

    def test_404_raises_not_found(self, client: BedrijfsdataClient) -> None:
        resp = _mock_response(404, {"error": "Not found"})
        with pytest.raises(BedrijfsdataNotFoundError):
            client._check_response(resp)

    def test_401_raises_auth(self, client: BedrijfsdataClient) -> None:
        resp = _mock_response(401, {"error": "Invalid API key"})
        with pytest.raises(AuthenticationError):
            client._check_response(resp)


# ---------------------------------------------------------------------------
# build_search_params
# ---------------------------------------------------------------------------


class TestBuildSearchParams:
    def test_sbi_codes(self) -> None:
        p = BedrijfsdataClient.build_search_params(sbi=["6201", "6202"])
        assert p["sbi"] == "6201,6202"

    def test_employee_range(self) -> None:
        p = BedrijfsdataClient.build_search_params(employees_min=10, employees_max=200)
        assert p["employees"] == "10:200"

    def test_employee_min_only(self) -> None:
        p = BedrijfsdataClient.build_search_params(employees_min=50)
        assert p["employees"] == "50:"

    def test_employee_max_only(self) -> None:
        p = BedrijfsdataClient.build_search_params(employees_max=100)
        assert p["employees"] == ":100"

    def test_revenue_range(self) -> None:
        p = BedrijfsdataClient.build_search_params(revenue_min=500000, revenue_max=5000000)
        assert p["revenue"] == "500000:5000000"

    def test_city_list(self) -> None:
        p = BedrijfsdataClient.build_search_params(city=["Amsterdam", "Rotterdam"])
        assert p["city"] == "Amsterdam,Rotterdam"

    def test_province_list(self) -> None:
        p = BedrijfsdataClient.build_search_params(province=["Noord-Holland"])
        assert p["province"] == "Noord-Holland"

    def test_apps_list(self) -> None:
        p = BedrijfsdataClient.build_search_params(apps=["React", "Python"])
        assert p["apps"] == "React,Python"

    def test_text_search(self) -> None:
        p = BedrijfsdataClient.build_search_params(text="cloud hosting")
        assert p["text"] == "cloud hosting"

    def test_pagination(self) -> None:
        p = BedrijfsdataClient.build_search_params(rows=50, page=3)
        assert p["rows"] == "50"
        assert p["page"] == "3"

    def test_defaults_pagination(self) -> None:
        p = BedrijfsdataClient.build_search_params()
        assert p["rows"] == "25"
        assert p["page"] == "1"

    def test_founded_range(self) -> None:
        p = BedrijfsdataClient.build_search_params(founded_min=2015, founded_max=2023)
        assert p["founded"] == "2015:2023"

    def test_data_exists(self) -> None:
        p = BedrijfsdataClient.build_search_params(data_exists=["url", "email"])
        assert p["data_exists"] == "url,email"

    def test_empty_params_only_pagination(self) -> None:
        p = BedrijfsdataClient.build_search_params()
        assert set(p.keys()) == {"rows", "page"}


# ---------------------------------------------------------------------------
# icp_to_search_params
# ---------------------------------------------------------------------------


class TestIcpToSearchParams:
    def test_industry_filter(self) -> None:
        p = BedrijfsdataClient.icp_to_search_params(industry_filter=["SaaS"])
        assert "sbi" in p
        assert "6201" in p["sbi"]

    def test_size_filter(self) -> None:
        p = BedrijfsdataClient.icp_to_search_params(
            size_filter={
                "min_employees": 10,
                "max_employees": 200,
                "min_revenue": 500000,
                "max_revenue": 5000000,
            }
        )
        assert p["employees"] == "10:200"
        assert p["revenue"] == "500000:5000000"

    def test_geo_filter(self) -> None:
        p = BedrijfsdataClient.icp_to_search_params(
            geo_filter={
                "cities": ["Amsterdam", "Utrecht"],
                "regions": ["Noord-Holland"],
                "countries": ["NL"],
            }
        )
        assert p["city"] == "Amsterdam,Utrecht"
        assert p["province"] == "Noord-Holland"

    def test_tech_filter(self) -> None:
        p = BedrijfsdataClient.icp_to_search_params(tech_filter=["React", "Python"])
        assert p["apps"] == "React,Python"

    def test_combined_filters(self) -> None:
        p = BedrijfsdataClient.icp_to_search_params(
            industry_filter=["SaaS"],
            size_filter={"min_employees": 50},
            geo_filter={"cities": ["Amsterdam"]},
            tech_filter=["React"],
        )
        assert "sbi" in p
        assert p["employees"] == "50:"
        assert p["city"] == "Amsterdam"
        assert p["apps"] == "React"

    def test_unknown_industry_no_sbi(self) -> None:
        p = BedrijfsdataClient.icp_to_search_params(industry_filter=["unknown_xyz"])
        assert "sbi" not in p

    def test_empty_filters(self) -> None:
        p = BedrijfsdataClient.icp_to_search_params()
        assert set(p.keys()) == {"rows", "page"}

    def test_pagination_params(self) -> None:
        p = BedrijfsdataClient.icp_to_search_params(rows=50, page=2)
        assert p["rows"] == "50"
        assert p["page"] == "2"


# ---------------------------------------------------------------------------
# search_companies
# ---------------------------------------------------------------------------

_SEARCH_RESPONSE_BODY = {
    "status": "ok",
    "found": 2,
    "companies": [
        {
            "id": 1001,
            "coc": "12345678",
            "name": "TechCo B.V.",
            "domain": "techco.nl",
            "city": "Amsterdam",
            "province": "Noord-Holland",
            "employees": 85,
            "revenue": 2500000,
            "sbi": [
                {
                    "code": "6201",
                    "description": "Computer programming",
                }
            ],
            "apps": ["React", "Python", "AWS"],
            "social": {"linkedin": "https://linkedin.com/company/techco"},
            "orgtype": "BV",
            "founded": 2018,
        },
        {
            "id": 1002,
            "coc": "87654321",
            "name": "DataFlow NV",
            "domain": "dataflow.nl",
            "city": "Rotterdam",
            "province": "Zuid-Holland",
            "employees": 150,
            "revenue": 8000000,
            "sbi": [
                {
                    "code": "6201",
                    "description": "Computer programming",
                },
                {
                    "code": "6311",
                    "description": "Data processing",
                },
            ],
            "apps": ["Java", "Kubernetes"],
            "social": {"linkedin": "https://linkedin.com/company/dataflow"},
            "orgtype": "NV",
            "founded": 2015,
        },
    ],
}


class TestSearchCompanies:
    @pytest.mark.asyncio
    async def test_returns_parsed_results(self, client: BedrijfsdataClient) -> None:
        resp = _mock_response(200, _SEARCH_RESPONSE_BODY)
        with _patch_client(client, resp):
            result = await client.search_companies(
                BedrijfsdataClient.build_search_params(sbi=["6201"])
            )

        assert isinstance(result, CompanySearchResponse)
        assert result.total == 2
        assert len(result.companies) == 2

        co = result.companies[0]
        assert co.name == "TechCo B.V."
        assert co.coc == "12345678"
        assert co.domain == "techco.nl"
        assert co.city == "Amsterdam"
        assert co.employees == 85
        assert co.revenue == 2500000
        assert "6201" in co.sbi_codes
        assert "Computer programming" in co.industry_labels
        assert "React" in co.apps
        assert co.linkedin_url == ("https://linkedin.com/company/techco")
        assert co.orgtype == "BV"
        assert co.founded == 2018

    @pytest.mark.asyncio
    async def test_passes_auth_params(self, client: BedrijfsdataClient) -> None:
        resp = _mock_response(200, _SEARCH_RESPONSE_BODY)
        with _patch_client(client, resp) as mock_send:
            await client.search_companies()

        assert _sent_params(mock_send)["api_key"] == "test-key"

    @pytest.mark.asyncio
    async def test_empty_response(self, client: BedrijfsdataClient) -> None:
        body = {"status": "ok", "found": 0, "companies": []}
        resp = _mock_response(200, body)
        with _patch_client(client, resp):
            result = await client.search_companies()

        assert result.total == 0
        assert result.companies == []

    @pytest.mark.asyncio
    async def test_pagination_params_forwarded(self, client: BedrijfsdataClient) -> None:
        body = {"status": "ok", "found": 0, "companies": []}
        resp = _mock_response(200, body)
        with _patch_client(client, resp) as mock_send:
            await client.search_companies(rows=50, page=3)

        params = _sent_params(mock_send)
        assert params["rows"] == "50"
        assert params["page"] == "3"


# ---------------------------------------------------------------------------
# enrich_company
# ---------------------------------------------------------------------------

_ENRICH_RESPONSE_BODY = {
    "status": "ok",
    "found": 1,
    "companies": [
        {
            "id": 1001,
            "coc": "12345678",
            "name": "TechCo B.V.",
            "domain": "techco.nl",
            "city": "Amsterdam",
            "employees": 85,
            "sbi": [
                {
                    "code": "6201",
                    "description": "Computer programming",
                }
            ],
            "apps": ["React"],
            "social": {},
        },
    ],
}


class TestEnrichCompany:
    @pytest.mark.asyncio
    async def test_returns_matched_company(self, client: BedrijfsdataClient) -> None:
        resp = _mock_response(200, _ENRICH_RESPONSE_BODY)
        with _patch_client(client, resp):
            result = await client.enrich_company(domain="techco.nl")

        assert isinstance(result, EnrichResponse)
        assert result.matched is True
        assert result.company is not None
        assert result.company.name == "TechCo B.V."
        assert result.company.coc == "12345678"

    @pytest.mark.asyncio
    async def test_no_match_returns_false(self, client: BedrijfsdataClient) -> None:
        body = {"status": "ok", "found": 0, "companies": []}
        resp = _mock_response(200, body)
        with _patch_client(client, resp):
            result = await client.enrich_company(domain="unknown.nl")

        assert result.matched is False
        assert result.company is None

    @pytest.mark.asyncio
    async def test_404_returns_not_matched(self, client: BedrijfsdataClient) -> None:
        resp = _mock_response(404, {"error": "Not found"})
        with _patch_client(client, resp):
            result = await client.enrich_company(name="Unknown Corp")

        assert result.matched is False

    @pytest.mark.asyncio
    async def test_no_criteria_returns_not_matched(self, client: BedrijfsdataClient) -> None:
        result = await client.enrich_company()
        assert result.matched is False

    @pytest.mark.asyncio
    async def test_multiple_criteria(self, client: BedrijfsdataClient) -> None:
        resp = _mock_response(200, _ENRICH_RESPONSE_BODY)
        with _patch_client(client, resp) as mock_send:
            await client.enrich_company(
                name="TechCo",
                domain="techco.nl",
                city="Amsterdam",
            )

        params = _sent_params(mock_send)
        assert params["name"] == "TechCo"
        assert params["domain"] == "techco.nl"
        assert params["city"] == "Amsterdam"


# ---------------------------------------------------------------------------
# get_corporate_family
# ---------------------------------------------------------------------------

_CORPORATE_FAMILY_BODY = {
    "status": "ok",
    "found": 3,
    "companies": [
        {
            "coc": "12345678",
            "name": "Holding B.V.",
            "role": "parent",
        },
        {
            "coc": "12345679",
            "name": "TechCo B.V.",
            "role": "subsidiary",
        },
        {
            "coc": "12345680",
            "name": "TechCo Services B.V.",
            "role": "subsidiary",
        },
    ],
}


class TestGetCorporateFamily:
    @pytest.mark.asyncio
    async def test_returns_family_members(self, client: BedrijfsdataClient) -> None:
        resp = _mock_response(200, _CORPORATE_FAMILY_BODY)
        with _patch_client(client, resp):
            result = await client.get_corporate_family("12345678")

        assert isinstance(result, CorporateFamilyResponse)
        assert result.coc == "12345678"
        assert result.total == 3
        assert len(result.members) == 3
        assert result.members[0].name == "Holding B.V."
        assert result.members[0].role == "parent"
        assert result.members[1].role == "subsidiary"

    @pytest.mark.asyncio
    async def test_passes_coc_param(self, client: BedrijfsdataClient) -> None:
        resp = _mock_response(200, _CORPORATE_FAMILY_BODY)
        with _patch_client(client, resp) as mock_send:
            await client.get_corporate_family("12345678")

        params = _sent_params(mock_send)
        assert params["coc"] == "12345678"
        assert params["api_key"] == "test-key"

    @pytest.mark.asyncio
    async def test_not_found_raises(self, client: BedrijfsdataClient) -> None:
        with (
            _patch_client(
                client,
                side_effect=BedrijfsdataNotFoundError(),
            ),
            pytest.raises(BedrijfsdataNotFoundError),
        ):
            await client.get_corporate_family("00000000")


# ---------------------------------------------------------------------------
# _parse_company edge cases
# ---------------------------------------------------------------------------


class TestParseCompany:
    def test_sbi_as_plain_strings(self) -> None:
        co = BedrijfsdataClient._parse_company({"name": "Test", "sbi": ["6201", "6202"]})
        assert co.sbi_codes == ["6201", "6202"]
        assert co.industry_labels == []

    def test_missing_social(self) -> None:
        co = BedrijfsdataClient._parse_company({"name": "Test"})
        assert co.linkedin_url is None
        assert co.facebook_url is None

    def test_url_fallback_for_domain(self) -> None:
        co = BedrijfsdataClient._parse_company({"name": "Test", "url": "example.nl"})
        assert co.domain == "example.nl"

    def test_empty_apps(self) -> None:
        co = BedrijfsdataClient._parse_company({"name": "Test", "apps": None})
        assert co.apps == []

    def test_full_company_parsing(self) -> None:
        co = BedrijfsdataClient._parse_company(
            {
                "id": 42,
                "coc": "99999999",
                "name": "Full B.V.",
                "domain": "full.nl",
                "address": "Keizersgracht 1",
                "city": "Amsterdam",
                "province": "Noord-Holland",
                "postal_code": "1015AA",
                "phone": "+31201234567",
                "email": "info@full.nl",
                "employees": 500,
                "revenue": 10000000,
                "sbi": [{"code": "6201", "description": "Programming"}],
                "apps": ["Python"],
                "social": {
                    "linkedin": "https://linkedin.com/company/full",
                    "facebook": "https://facebook.com/full",
                    "twitter": "https://twitter.com/full",
                },
                "lat": 52.3676,
                "lng": 4.9041,
                "orgtype": "BV",
                "founded": 2010,
            }
        )
        assert co.id == 42
        assert co.coc == "99999999"
        assert co.postal_code == "1015AA"
        assert co.email == "info@full.nl"
        assert co.latitude == 52.3676
        assert co.longitude == 4.9041
        assert co.facebook_url == "https://facebook.com/full"
        assert co.twitter_url == "https://twitter.com/full"
