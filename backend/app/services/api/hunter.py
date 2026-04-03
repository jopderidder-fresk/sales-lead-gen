"""Hunter.io API client — domain search and email verification.

This is the first provider in the waterfall enrichment chain.  It finds
contacts by company domain and verifies individual email addresses.

Usage::

    client = HunterClient(api_key="your-key")
    results = await client.domain_search("example.com")
    status  = await client.verify_email("user@example.com")
    await client.close()
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.services.api.base_client import BaseAPIClient
from app.services.api.errors import APIError

# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class VerificationStatus(StrEnum):
    DELIVERABLE = "deliverable"
    RISKY = "risky"
    UNDELIVERABLE = "undeliverable"
    UNKNOWN = "unknown"


class HunterEmail(BaseModel):
    """A single email result from the domain-search endpoint."""

    value: str = Field(description="Email address")
    first_name: str | None = None
    last_name: str | None = None
    position: str | None = Field(default=None, description="Job title")
    department: str | None = None
    confidence: int = Field(ge=0, le=100, description="Hunter confidence score 0-100")
    linkedin: str | None = Field(default=None, description="LinkedIn profile URL")
    phone_number: str | None = None

    @property
    def full_name(self) -> str:
        parts = [p for p in (self.first_name, self.last_name) if p]
        return " ".join(parts)


class DomainSearchResponse(BaseModel):
    """Parsed response from ``GET /domain-search``."""

    domain: str
    results: list[HunterEmail] = Field(default_factory=list)
    total: int = 0
    organization: str | None = None


class EmailVerificationResponse(BaseModel):
    """Parsed response from ``GET /email-verifier``."""

    email: str
    status: VerificationStatus
    score: int = Field(ge=0, le=100)
    regexp: bool = True
    mx_records: bool = True


# ---------------------------------------------------------------------------
# Hunter-specific errors
# ---------------------------------------------------------------------------


class HunterQuotaExceededError(APIError):
    """Raised when the Hunter.io account has exhausted its plan quota."""

    def __init__(self, message: str = "Hunter.io quota exceeded") -> None:
        super().__init__(message, provider="hunter", status_code=402)


class HunterInvalidDomainError(APIError):
    """Raised when the domain provided is invalid or not found."""

    def __init__(self, domain: str) -> None:
        super().__init__(
            f"Invalid or unknown domain: {domain}",
            provider="hunter",
            status_code=400,
        )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

# Default departments that map to CTO / CIO / VP-level roles.
_DEFAULT_DEPARTMENTS = ("executive", "it")


class HunterClient(BaseAPIClient):
    """Hunter.io provider client for contact enrichment."""

    provider = "hunter"
    base_url = "https://api.hunter.io/v2"

    # Hunter rate limits vary by plan (30-150 req/min).
    # Default to conservative 30 req/min.
    rate_limit_capacity: int = 30
    rate_limit_refill: float = 0.5  # 30 tokens / 60 sec

    def __init__(self, api_key: str) -> None:
        super().__init__(api_key=api_key)

    # Hunter uses api_key as a query parameter, not a header.
    def _build_headers(self) -> dict[str, str]:
        return {"Accept": "application/json"}

    def _auth_params(self) -> dict[str, str]:
        return {"api_key": self._api_key}

    def _check_response(self, response: httpx.Response) -> httpx.Response:
        """Extend base check with Hunter-specific error codes."""
        if response.status_code == 402:
            raise HunterQuotaExceededError()
        return super()._check_response(response)

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def domain_search(
        self,
        domain: str,
        *,
        departments: tuple[str, ...] = _DEFAULT_DEPARTMENTS,
        type_filter: str = "personal",
        limit: int = 10,
    ) -> DomainSearchResponse:
        """Search for email contacts associated with a domain.

        Args:
            domain: Company domain to search (e.g. ``"example.com"``).
            departments: Hunter department filters (default: executive, it).
            type_filter: ``"personal"`` or ``"generic"``.
            limit: Max results to return (Hunter max 100).

        Returns:
            ``DomainSearchResponse`` with matched emails.

        Raises:
            HunterInvalidDomainError: If the domain is invalid.
            HunterQuotaExceededError: If the plan quota is exhausted.
        """
        params: dict[str, Any] = {
            **self._auth_params(),
            "domain": domain,
            "type": type_filter,
            "limit": min(limit, 100),
        }
        # Hunter accepts a single department param per request; we send the
        # first one and let callers refine.  For multi-department, the
        # enrichment service can call multiple times.
        if departments:
            params["department"] = departments[0]

        response = await self.request(
            "GET",
            "/domain-search",
            params=params,
            credits_used=1.0,
            cost_estimate=Decimal("0.01"),
        )

        body = response.json()
        data = body.get("data", {})

        emails = [HunterEmail.model_validate(e) for e in data.get("emails", [])]

        return DomainSearchResponse(
            domain=data.get("domain", domain),
            results=emails,
            total=data.get("available_results", len(emails)),
            organization=data.get("organization"),
        )

    async def verify_email(self, email: str) -> EmailVerificationResponse:
        """Verify the deliverability of an email address.

        Args:
            email: The email address to verify.

        Returns:
            ``EmailVerificationResponse`` with status and score.
        """
        response = await self.request(
            "GET",
            "/email-verifier",
            params={**self._auth_params(), "email": email},
            credits_used=1.0,
            cost_estimate=Decimal("0.01"),
        )

        body = response.json()
        data = body.get("data", {})

        return EmailVerificationResponse(
            email=data.get("email", email),
            status=data.get("status", "unknown"),
            score=data.get("score", 0),
            regexp=data.get("regexp", True),
            mx_records=data.get("mx_records", True),
        )
