"""Tests for the Hunter.io API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from app.services.api.errors import AuthenticationError
from app.services.api.hunter import (
    DomainSearchResponse,
    EmailVerificationResponse,
    HunterClient,
    HunterEmail,
    HunterInvalidDomainError,
    HunterQuotaExceededError,
    VerificationStatus,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> HunterClient:
    return HunterClient(api_key="test-key")


def _mock_response(status_code: int = 200, json_data: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_data or {},
        request=httpx.Request("GET", "https://api.hunter.io/v2/test"),
    )


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestHunterEmail:
    def test_full_name_both_parts(self) -> None:
        e = HunterEmail(value="j@x.com", first_name="Jane", last_name="Doe", confidence=90)
        assert e.full_name == "Jane Doe"

    def test_full_name_first_only(self) -> None:
        e = HunterEmail(value="j@x.com", first_name="Jane", confidence=80)
        assert e.full_name == "Jane"

    def test_full_name_empty(self) -> None:
        e = HunterEmail(value="j@x.com", confidence=50)
        assert e.full_name == ""


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestHunterErrors:
    def test_quota_exceeded_error(self) -> None:
        err = HunterQuotaExceededError()
        assert err.status_code == 402
        assert err.provider == "hunter"

    def test_invalid_domain_error(self) -> None:
        err = HunterInvalidDomainError("bad.xyz")
        assert err.status_code == 400
        assert "bad.xyz" in err.message

    def test_402_response_raises_quota_error(self, client: HunterClient) -> None:
        resp = _mock_response(402, {"errors": [{"details": "Over quota"}]})
        with pytest.raises(HunterQuotaExceededError):
            client._check_response(resp)

    def test_401_response_raises_auth_error(self, client: HunterClient) -> None:
        resp = _mock_response(401, {"error": "Invalid API key"})
        with pytest.raises(AuthenticationError):
            client._check_response(resp)


# ---------------------------------------------------------------------------
# domain_search
# ---------------------------------------------------------------------------


_DOMAIN_SEARCH_BODY = {
    "data": {
        "domain": "example.com",
        "organization": "Example Inc",
        "available_results": 2,
        "emails": [
            {
                "value": "cto@example.com",
                "first_name": "Alice",
                "last_name": "Smith",
                "position": "CTO",
                "department": "executive",
                "confidence": 95,
                "linkedin": "https://linkedin.com/in/alice",
                "phone_number": "+1234567890",
            },
            {
                "value": "dev@example.com",
                "first_name": "Bob",
                "last_name": "Jones",
                "position": "Developer",
                "department": "it",
                "confidence": 72,
                "linkedin": None,
                "phone_number": None,
            },
        ],
    }
}


class TestDomainSearch:
    @pytest.mark.asyncio
    async def test_returns_parsed_results(self, client: HunterClient) -> None:
        mock_resp = _mock_response(200, _DOMAIN_SEARCH_BODY)

        with (
            patch.object(client, "_send", new_callable=AsyncMock, return_value=mock_resp),
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
        ):
            result = await client.domain_search("example.com")

        assert isinstance(result, DomainSearchResponse)
        assert result.domain == "example.com"
        assert result.organization == "Example Inc"
        assert result.total == 2
        assert len(result.results) == 2
        assert result.results[0].value == "cto@example.com"
        assert result.results[0].full_name == "Alice Smith"
        assert result.results[0].confidence == 95

    @pytest.mark.asyncio
    async def test_empty_data_returns_empty_results(self, client: HunterClient) -> None:
        mock_resp = _mock_response(200, {"data": {}})

        with (
            patch.object(client, "_send", new_callable=AsyncMock, return_value=mock_resp),
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
        ):
            result = await client.domain_search("nonexistent.xyz")

        assert isinstance(result, DomainSearchResponse)
        assert result.results == []
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_passes_auth_params(self, client: HunterClient) -> None:
        mock_resp = _mock_response(200, _DOMAIN_SEARCH_BODY)

        with (
            patch.object(
                client, "_send", new_callable=AsyncMock, return_value=mock_resp
            ) as mock_send,
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
        ):
            await client.domain_search("example.com")

        # Verify api_key was in the params
        call_kwargs = mock_send.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params", {})
        assert params["api_key"] == "test-key"
        assert params["domain"] == "example.com"

    @pytest.mark.asyncio
    async def test_limit_capped_at_100(self, client: HunterClient) -> None:
        mock_resp = _mock_response(200, _DOMAIN_SEARCH_BODY)

        with (
            patch.object(
                client, "_send", new_callable=AsyncMock, return_value=mock_resp
            ) as mock_send,
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
        ):
            await client.domain_search("example.com", limit=500)

        params = mock_send.call_args.kwargs.get("params") or mock_send.call_args[1].get(
            "params", {}
        )
        assert params["limit"] == 100


# ---------------------------------------------------------------------------
# verify_email
# ---------------------------------------------------------------------------

_VERIFY_BODY = {
    "data": {
        "email": "cto@example.com",
        "status": "deliverable",
        "score": 91,
        "regexp": True,
        "mx_records": True,
    }
}


class TestVerifyEmail:
    @pytest.mark.asyncio
    async def test_returns_parsed_result(self, client: HunterClient) -> None:
        mock_resp = _mock_response(200, _VERIFY_BODY)

        with (
            patch.object(client, "_send", new_callable=AsyncMock, return_value=mock_resp),
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
        ):
            result = await client.verify_email("cto@example.com")

        assert isinstance(result, EmailVerificationResponse)
        assert result.email == "cto@example.com"
        assert result.status == VerificationStatus.DELIVERABLE
        assert result.score == 91
        assert result.mx_records is True

    @pytest.mark.asyncio
    async def test_handles_unknown_status(self, client: HunterClient) -> None:
        body = {"data": {"email": "x@x.com", "status": "unknown", "score": 0}}
        mock_resp = _mock_response(200, body)

        with (
            patch.object(client, "_send", new_callable=AsyncMock, return_value=mock_resp),
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
        ):
            result = await client.verify_email("x@x.com")

        assert result.status == VerificationStatus.UNKNOWN
