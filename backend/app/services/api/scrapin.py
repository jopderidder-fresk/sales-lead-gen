"""ScrapIn API client — GDPR-compliant public professional data enrichment.

ScrapIn is the third provider in the waterfall enrichment chain.  It finds
and enriches contacts using publicly available professional data without
requiring LinkedIn login credentials.

Usage::

    client = ScrapInClient(api_key="your-key")
    results = await client.find_contacts("example.com", title_keywords=["CTO", "VP Engineering"])
    person  = await client.match_person(first_name="Jane", last_name="Doe", company_domain="example.com")
    await client.close()
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.services.api.base_client import BaseAPIClient
from app.services.api.errors import APIError

# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ScrapInContact(BaseModel):
    """A single contact result from ScrapIn enrichment."""

    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    title: str | None = Field(default=None, description="Job title / position")
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = Field(default=None, description="Public LinkedIn profile URL")
    company_name: str | None = None
    company_domain: str | None = None
    location: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Match confidence 0-1")

    @property
    def display_name(self) -> str:
        if self.full_name:
            return self.full_name
        parts = [p for p in (self.first_name, self.last_name) if p]
        return " ".join(parts) if parts else ""


class ScrapInSearchResponse(BaseModel):
    """Parsed response from a contact search."""

    domain: str
    results: list[ScrapInContact] = Field(default_factory=list)
    total: int = 0


class ScrapInPersonResponse(BaseModel):
    """Parsed response from the person-match endpoint."""

    person: ScrapInContact | None = None
    success: bool = False


# ---------------------------------------------------------------------------
# ScrapIn-specific errors
# ---------------------------------------------------------------------------


class ScrapInCreditsExhaustedError(APIError):
    """Raised when the ScrapIn account has run out of credits."""

    def __init__(self, message: str = "ScrapIn credits exhausted") -> None:
        super().__init__(message, provider="scrapin", status_code=402)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ScrapInClient(BaseAPIClient):
    """ScrapIn provider client for public professional data enrichment."""

    provider = "scrapin"
    base_url = "https://api.scrapin.io"

    # ScrapIn is pay-per-use — keep rate limits conservative.
    rate_limit_capacity: int = 10
    rate_limit_refill: float = 0.5  # 10 tokens / 20 sec

    def __init__(self, api_key: str) -> None:
        super().__init__(api_key=api_key)

    # ScrapIn uses apikey as a query parameter, not a header.
    def _build_headers(self) -> dict[str, str]:
        return {"Accept": "application/json"}

    def _auth_params(self) -> dict[str, str]:
        return {"apikey": self._api_key}

    def _check_response(self, response: httpx.Response) -> httpx.Response:
        """Extend base check with ScrapIn-specific error codes."""
        if response.status_code == 402:
            raise ScrapInCreditsExhaustedError()
        return super()._check_response(response)

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def find_contacts(
        self,
        company_domain: str,
        title_keywords: list[str] | None = None,
    ) -> ScrapInSearchResponse:
        """Search for contacts associated with a company domain.

        Uses the ScrapIn enrichment endpoint with company domain context
        to find matching professional contacts.

        Args:
            company_domain: Company domain to search (e.g. ``"example.com"``).
            title_keywords: Optional job-title keywords to filter by
                (e.g. ``["CTO", "VP Engineering"]``).

        Returns:
            ``ScrapInSearchResponse`` with matched contacts.

        Raises:
            ScrapInCreditsExhaustedError: If the account has no credits left.
        """
        params: dict[str, Any] = {
            **self._auth_params(),
            "companyDomain": company_domain,
        }

        response = await self.request(
            "GET",
            "/enrichment",
            params=params,
            credits_used=1.0,
            cost_estimate=Decimal("0.03"),
        )

        body = response.json()
        contacts = self._parse_contacts(body)

        # Client-side title filtering when keywords are provided.
        if title_keywords:
            contacts = self._filter_by_title(contacts, title_keywords)

        return ScrapInSearchResponse(
            domain=company_domain,
            results=contacts,
            total=len(contacts),
        )

    async def match_person(
        self,
        *,
        first_name: str,
        last_name: str,
        company_domain: str | None = None,
        company_name: str | None = None,
        email: str | None = None,
    ) -> ScrapInPersonResponse:
        """Match and enrich a specific person using partial data.

        This does not require a LinkedIn URL — ScrapIn identifies
        the profile from the provided attributes.

        Args:
            first_name: Person's first name.
            last_name: Person's last name.
            company_domain: Company domain for disambiguation.
            company_name: Company name for disambiguation.
            email: Known email address for higher match accuracy.

        Returns:
            ``ScrapInPersonResponse`` with the enriched person data.
        """
        params: dict[str, Any] = {
            **self._auth_params(),
            "firstName": first_name,
            "lastName": last_name,
        }
        if company_domain:
            params["companyDomain"] = company_domain
        if company_name:
            params["companyName"] = company_name
        if email:
            params["email"] = email

        response = await self.request(
            "GET",
            "/enrichment",
            params=params,
            credits_used=1.0,
            cost_estimate=Decimal("0.03"),
        )

        body = response.json()
        person = self._parse_person(body)

        return ScrapInPersonResponse(
            person=person,
            success=person is not None,
        )

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_person(body: dict[str, Any]) -> ScrapInContact | None:
        """Extract a single person from the API response."""
        person_data = body.get("person")
        if not person_data:
            return None

        # Extract nested identity fields.
        identity = person_data if isinstance(person_data, dict) else {}

        # Company context may be nested or at the top level.
        company = body.get("company") or identity.get("company") or {}
        positions = identity.get("positions", {})
        current_positions = positions.get("positionHistory", []) if isinstance(positions, dict) else []

        current_title = None
        if current_positions and isinstance(current_positions, list):
            current_title = current_positions[0].get("title")

        linkedin_url = identity.get("linkedInUrl") or identity.get("linkedinUrl")
        full_name = identity.get("fullName") or identity.get("full_name")
        first_name = identity.get("firstName") or identity.get("first_name")
        last_name = identity.get("lastName") or identity.get("last_name")

        return ScrapInContact(
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            title=current_title or identity.get("headline"),
            email=identity.get("email"),
            phone=identity.get("phone"),
            linkedin_url=linkedin_url,
            company_name=company.get("name") if isinstance(company, dict) else None,
            company_domain=company.get("domain") if isinstance(company, dict) else None,
            location=identity.get("location"),
            confidence=1.0 if linkedin_url else 0.5,
        )

    @classmethod
    def _parse_contacts(cls, body: dict[str, Any]) -> list[ScrapInContact]:
        """Extract contacts from the response.

        ScrapIn may return a single person match or a list depending on
        the query.  This normalises both shapes into a list.
        """
        # Single person result.
        person = cls._parse_person(body)
        if person:
            return [person]

        # Array of results (e.g. from company-scoped queries).
        results = body.get("results") or body.get("employees") or []
        contacts: list[ScrapInContact] = []
        for item in results:
            parsed = cls._parse_person(item if isinstance(item, dict) else {"person": item})
            if parsed:
                contacts.append(parsed)

        return contacts

    @staticmethod
    def _filter_by_title(
        contacts: list[ScrapInContact],
        keywords: list[str],
    ) -> list[ScrapInContact]:
        """Filter contacts whose title matches any of the given keywords."""
        lower_keywords = [kw.lower() for kw in keywords]
        return [
            c
            for c in contacts
            if c.title and any(kw in c.title.lower() for kw in lower_keywords)
        ]
