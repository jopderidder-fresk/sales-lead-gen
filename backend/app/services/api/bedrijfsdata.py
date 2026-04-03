"""Bedrijfsdata.nl API client — Dutch company search and enrichment.

Bedrijfsdata provides KvK-sourced company data for the Netherlands with
30+ filter parameters, technology stack detection, and revenue data.

Supports three core operations:

- **search_companies**: Search NL companies with ICP-aligned filters.
- **enrich_company**: Match/complete partial company data.
- **get_corporate_family**: Find related companies in the same group.

Usage::

    client = BedrijfsdataClient(api_key="your-key")
    results = await client.search_companies({"sbi": "6201,6202", "employees": "10:200"})
    enriched = await client.enrich_company(domain="example.nl")
    family = await client.get_corporate_family(coc="12345678")
    await client.close()
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services.api.base_client import BaseAPIClient
from app.services.api.errors import APIError

if TYPE_CHECKING:
    import httpx

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# SBI code mapping — maps human-readable industry names to SBI codes.
# This covers the most common B2B-relevant sectors. The full SBI taxonomy
# has 1,283 codes; extend as needed for niche verticals.
# ---------------------------------------------------------------------------

SBI_CODE_MAP: dict[str, list[str]] = {
    "saas": ["6201", "6202", "6209"],
    "software": ["6201", "6202", "6209"],
    "it": ["6201", "6202", "6209", "6311", "6312"],
    "it services": ["6202", "6209"],
    "cloud": ["6311", "6202"],
    "cybersecurity": ["6209"],
    "fintech": ["6201", "6419", "6499"],
    "financial services": ["6411", "6419", "6491", "6492", "6499"],
    "banking": ["6411", "6419"],
    "insurance": ["6511", "6512"],
    "healthtech": ["6201", "8610"],
    "healthcare": ["8610", "8621", "8622", "8623"],
    "biotech": ["7211", "7219"],
    "pharma": ["2110", "2120"],
    "manufacturing": ["1011", "2410", "2511", "2599", "2811", "2899"],
    "logistics": ["4941", "5210", "5229"],
    "transport": ["4941", "4942", "5010", "5110"],
    "retail": ["4711", "4719", "4791"],
    "e-commerce": ["4791"],
    "wholesale": ["4619", "4690"],
    "construction": ["4110", "4120", "4211", "4299"],
    "real estate": ["6810", "6820"],
    "consulting": ["7022"],
    "management consulting": ["7022"],
    "marketing": ["7311", "7312"],
    "advertising": ["7311"],
    "media": ["5811", "5813", "5814", "6010", "6020"],
    "telecommunications": ["6110", "6120", "6130"],
    "energy": ["3511", "3512", "3513", "3514"],
    "renewable energy": ["3511", "3514"],
    "food": ["1011", "1012", "1013", "1020", "1039"],
    "agriculture": ["0111", "0113", "0119", "0150"],
    "education": ["8510", "8520", "8530", "8541", "8542"],
    "edtech": ["6201", "8542"],
    "legal": ["6910"],
    "accounting": ["6920"],
    "hr": ["7810", "7820", "7830"],
    "recruitment": ["7810", "7820"],
    "automotive": ["2910", "2920", "4511", "4519"],
    "aerospace": ["3030"],
    "gaming": ["5821"],
    "travel": ["7911", "7912"],
    "hospitality": ["5510", "5520", "5590"],
}


def industries_to_sbi_codes(industries: list[str]) -> list[str]:
    """Convert human-readable industry names to SBI codes.

    Unknown industries are silently skipped — the caller should validate
    upstream if strict matching is required.
    """
    codes: set[str] = set()
    for industry in industries:
        key = industry.lower().strip()
        if key in SBI_CODE_MAP:
            codes.update(SBI_CODE_MAP[key])
    return sorted(codes)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class BedrijfsdataCompany(BaseModel):
    """A single company result from Bedrijfsdata."""

    id: int | None = Field(default=None, description="Bedrijfsdata internal ID")
    coc: str | None = Field(default=None, description="KvK (Chamber of Commerce) number")
    name: str = Field(description="Company legal name")
    domain: str | None = Field(default=None, description="Primary website domain")
    address: str | None = None
    city: str | None = None
    province: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    email: str | None = None
    employees: int | None = Field(default=None, description="Number of employees")
    revenue: float | None = Field(default=None, description="Annual revenue in EUR")
    sbi_codes: list[str] = Field(default_factory=list, description="SBI industry codes")
    industry_labels: list[str] = Field(
        default_factory=list, description="Human-readable industry labels"
    )
    apps: list[str] = Field(default_factory=list, description="Detected technologies")
    linkedin_url: str | None = None
    facebook_url: str | None = None
    twitter_url: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    orgtype: str | None = Field(default=None, description="Organization type (BV, NV, VOF, etc.)")
    founded: int | None = Field(default=None, description="Year founded")


class CompanySearchResponse(BaseModel):
    """Parsed response from ``GET /companies``."""

    companies: list[BedrijfsdataCompany] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    rows: int = 25


class EnrichResponse(BaseModel):
    """Parsed response from ``GET /enrich``."""

    matched: bool = False
    company: BedrijfsdataCompany | None = None


class CorporateFamilyMember(BaseModel):
    """A single entity in a corporate group."""

    coc: str | None = None
    name: str = ""
    role: str | None = Field(
        default=None, description="Role in the group (parent, subsidiary, etc.)"
    )


class CorporateFamilyResponse(BaseModel):
    """Parsed response from ``GET /corporate_family``."""

    coc: str
    members: list[CorporateFamilyMember] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Bedrijfsdata-specific errors
# ---------------------------------------------------------------------------


class BedrijfsdataQuotaExceededError(APIError):
    """Raised when the Bedrijfsdata monthly quota is exhausted."""

    def __init__(self, message: str = "Bedrijfsdata quota exceeded") -> None:
        super().__init__(message, provider="bedrijfsdata", status_code=402)


class BedrijfsdataNotFoundError(APIError):
    """Raised when the requested resource is not found."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, provider="bedrijfsdata", status_code=404)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class BedrijfsdataClient(BaseAPIClient):
    """Bedrijfsdata.nl provider client for NL company search and enrichment."""

    provider = "bedrijfsdata"
    base_url = "https://api.bedrijfsdata.nl/v1.2"

    # Conservative rate limiting — adjust based on plan.
    rate_limit_capacity: int = 10
    rate_limit_refill: float = 1.0  # 10 tokens / 10 sec

    def __init__(self, api_key: str) -> None:
        super().__init__(api_key=api_key)

    # Bedrijfsdata uses api_key as a query parameter.
    def _build_headers(self) -> dict[str, str]:
        return {"Accept": "application/json"}

    def _auth_params(self) -> dict[str, str]:
        return {"api_key": self._api_key}

    def _check_response(self, response: httpx.Response) -> httpx.Response:
        """Extend base check with Bedrijfsdata-specific error codes."""
        if response.status_code == 402:
            raise BedrijfsdataQuotaExceededError()
        if response.status_code == 404:
            raise BedrijfsdataNotFoundError()
        return super()._check_response(response)

    # ------------------------------------------------------------------
    # ICP filter mapping
    # ------------------------------------------------------------------

    @staticmethod
    def build_search_params(
        *,
        sbi: list[str] | None = None,
        employees_min: int | None = None,
        employees_max: int | None = None,
        revenue_min: float | None = None,
        revenue_max: float | None = None,
        city: list[str] | None = None,
        province: list[str] | None = None,
        apps: list[str] | None = None,
        text: str | None = None,
        orgtype: str | None = None,
        data_exists: list[str] | None = None,
        social_exists: list[str] | None = None,
        founded_min: int | None = None,
        founded_max: int | None = None,
        rows: int = 25,
        page: int = 1,
    ) -> dict[str, str]:
        """Build Bedrijfsdata query parameters from structured filters.

        Range filters use colon syntax (``min:max``), multi-value filters
        are comma-separated.
        """
        params: dict[str, str] = {}

        if sbi:
            params["sbi"] = ",".join(sbi)

        # Employee range — colon syntax
        if employees_min is not None or employees_max is not None:
            lo = str(employees_min) if employees_min is not None else ""
            hi = str(employees_max) if employees_max is not None else ""
            params["employees"] = f"{lo}:{hi}"

        # Revenue range — colon syntax
        if revenue_min is not None or revenue_max is not None:
            lo = str(int(revenue_min)) if revenue_min is not None else ""
            hi = str(int(revenue_max)) if revenue_max is not None else ""
            params["revenue"] = f"{lo}:{hi}"

        if city:
            params["city"] = ",".join(city)

        if province:
            params["province"] = ",".join(province)

        if apps:
            params["apps"] = ",".join(apps)

        if text:
            params["text"] = text

        if orgtype:
            params["orgtype"] = orgtype

        if data_exists:
            params["data_exists"] = ",".join(data_exists)

        if social_exists:
            params["social_exists"] = ",".join(social_exists)

        if founded_min is not None or founded_max is not None:
            lo = str(founded_min) if founded_min is not None else ""
            hi = str(founded_max) if founded_max is not None else ""
            params["founded"] = f"{lo}:{hi}"

        params["rows"] = str(rows)
        params["page"] = str(page)

        return params

    @staticmethod
    def icp_to_search_params(
        *,
        industry_filter: list[str] | None = None,
        size_filter: dict[str, Any] | None = None,
        geo_filter: dict[str, Any] | None = None,
        tech_filter: list[str] | None = None,
        negative_filters: dict[str, Any] | None = None,
        rows: int = 25,
        page: int = 1,
    ) -> dict[str, str]:
        """Map ICP profile filters to Bedrijfsdata query parameters.

        This bridges the gap between the ICP profile schema and the
        Bedrijfsdata API, translating industry names to SBI codes and
        normalizing filter formats.
        """
        sbi_codes: list[str] | None = None
        if industry_filter:
            sbi_codes = industries_to_sbi_codes(industry_filter) or None

        employees_min: int | None = None
        employees_max: int | None = None
        revenue_min: float | None = None
        revenue_max: float | None = None
        if size_filter:
            employees_min = size_filter.get("min_employees")
            employees_max = size_filter.get("max_employees")
            revenue_min = size_filter.get("min_revenue")
            revenue_max = size_filter.get("max_revenue")

        city: list[str] | None = None
        province: list[str] | None = None
        if geo_filter:
            city = geo_filter.get("cities") or None
            province = geo_filter.get("regions") or None

        return BedrijfsdataClient.build_search_params(
            sbi=sbi_codes,
            employees_min=employees_min,
            employees_max=employees_max,
            revenue_min=revenue_min,
            revenue_max=revenue_max,
            city=city,
            province=province,
            apps=tech_filter or None,
            rows=rows,
            page=page,
        )

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def search_companies(
        self,
        filters: dict[str, str] | None = None,
        *,
        rows: int = 25,
        page: int = 1,
    ) -> CompanySearchResponse:
        """Search for Dutch companies matching the given filters.

        Args:
            filters: Pre-built query params (from ``build_search_params``
                or ``icp_to_search_params``). If ``None``, returns first
                page of all companies.
            rows: Results per page (default 25).
            page: Page number (1-indexed).

        Returns:
            ``CompanySearchResponse`` with matched companies.

        Raises:
            BedrijfsdataQuotaExceededError: If the monthly quota is exhausted.
        """
        params: dict[str, str] = {**self._auth_params()}
        if filters:
            params.update(filters)
        # Ensure pagination params are set (caller may have included them
        # in filters already; explicit args take precedence).
        params.setdefault("rows", str(rows))
        params.setdefault("page", str(page))

        response = await self.get(
            "/companies",
            params=params,
            credits_used=1.0,
            cost_estimate=Decimal("0.06"),  # ~EUR 0.06/profile at mid-tier plan
        )

        body = response.json()
        companies = [
            self._parse_company(c) for c in body.get("companies", [])
        ]

        return CompanySearchResponse(
            companies=companies,
            total=body.get("found", len(companies)),
            page=int(params.get("page", "1")),
            rows=int(params.get("rows", "25")),
        )

    async def enrich_company(
        self,
        *,
        name: str | None = None,
        domain: str | None = None,
        city: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        linkedin_link: str | None = None,
    ) -> EnrichResponse:
        """Enrich/match a partial company record.

        Provide at least one identifier (name, domain, city, phone, email,
        or LinkedIn URL). Bedrijfsdata will attempt to match it to a known
        Dutch company.

        Returns:
            ``EnrichResponse`` with the matched company, or
            ``matched=False`` if no match was found.
        """
        params: dict[str, str] = {**self._auth_params()}
        if name:
            params["name"] = name
        if domain:
            params["domain"] = domain
        if city:
            params["city"] = city
        if phone:
            params["phone"] = phone
        if email:
            params["email"] = email
        if linkedin_link:
            params["linkedin_link"] = linkedin_link

        if len(params) <= 1:
            # Only api_key — no actual search criteria.
            return EnrichResponse(matched=False)

        try:
            response = await self.get(
                "/enrich",
                params=params,
                credits_used=1.0,
                cost_estimate=Decimal("0.06"),
            )
        except BedrijfsdataNotFoundError:
            return EnrichResponse(matched=False)

        body = response.json()
        companies = body.get("companies", [])

        if not companies:
            return EnrichResponse(matched=False)

        return EnrichResponse(
            matched=True,
            company=self._parse_company(companies[0]),
        )

    async def get_corporate_family(self, coc: str) -> CorporateFamilyResponse:
        """Find related companies in the same corporate group.

        Args:
            coc: KvK (Chamber of Commerce) number.

        Returns:
            ``CorporateFamilyResponse`` with related entities.

        Raises:
            BedrijfsdataNotFoundError: If the KvK number is unknown.
        """
        params: dict[str, str] = {
            **self._auth_params(),
            "coc": coc,
        }

        response = await self.get(
            "/corporate_family",
            params=params,
            credits_used=1.0,
            cost_estimate=Decimal("0.06"),
        )

        body = response.json()
        raw_members = body.get("companies", [])

        members = [
            CorporateFamilyMember(
                coc=m.get("coc"),
                name=m.get("name", ""),
                role=m.get("role"),
            )
            for m in raw_members
        ]

        return CorporateFamilyResponse(
            coc=coc,
            members=members,
            total=body.get("found", len(members)),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_company(data: dict[str, Any]) -> BedrijfsdataCompany:
        """Parse a raw company dict from the API into a typed model."""
        # Extract social links from the nested structure.
        social = data.get("social", {}) or {}

        # SBI codes can arrive as a list of dicts or plain strings.
        raw_sbi = data.get("sbi", [])
        sbi_codes: list[str] = []
        industry_labels: list[str] = []
        if isinstance(raw_sbi, list):
            for item in raw_sbi:
                if isinstance(item, dict):
                    if "code" in item:
                        sbi_codes.append(str(item["code"]))
                    if "description" in item:
                        industry_labels.append(item["description"])
                else:
                    sbi_codes.append(str(item))

        return BedrijfsdataCompany(
            id=data.get("id"),
            coc=data.get("coc"),
            name=data.get("name", ""),
            domain=data.get("domain") or data.get("url"),
            address=data.get("address"),
            city=data.get("city"),
            province=data.get("province"),
            postal_code=data.get("postal_code"),
            phone=data.get("phone"),
            email=data.get("email"),
            employees=data.get("employees"),
            revenue=data.get("revenue"),
            sbi_codes=sbi_codes,
            industry_labels=industry_labels,
            apps=data.get("apps", []) or [],
            linkedin_url=social.get("linkedin"),
            facebook_url=social.get("facebook"),
            twitter_url=social.get("twitter"),
            latitude=data.get("lat"),
            longitude=data.get("lng"),
            orgtype=data.get("orgtype"),
            founded=data.get("founded"),
        )
