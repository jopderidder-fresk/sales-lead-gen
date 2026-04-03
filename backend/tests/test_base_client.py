"""Tests for BaseAPIClient — circuit breaker, retry, rate limiter, usage tracking."""

from __future__ import annotations

import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from app.services.api.base_client import BaseAPIClient, CircuitBreaker, RateLimiter
from app.services.api.errors import (
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
)

# ---------------------------------------------------------------------------
# CircuitBreaker unit tests
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_starts_closed(self) -> None:
        cb = CircuitBreaker()
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_opens_after_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == "open"
        assert cb.allow_request() is False

    def test_stays_closed_below_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_success_resets_failures(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        assert cb.state == "closed"

    def test_transitions_to_half_open(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        assert cb._state == "open"  # internal state is open
        assert cb.allow_request() is False
        # After recovery timeout, should transition to half-open
        time.sleep(0.15)
        assert cb.state == "half-open"
        assert cb.allow_request() is True

    def test_half_open_failure_reopens(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()  # open
        time.sleep(0.15)
        assert cb.state == "half-open"
        cb.record_failure()  # back to open
        assert cb._state == "open"
        assert cb.allow_request() is False

    def test_half_open_success_closes(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.0)
        cb.record_failure()
        time.sleep(0.01)
        assert cb.state == "half-open"
        cb.record_success()
        assert cb.state == "closed"

    def test_half_open_allows_only_single_probe(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == "half-open"
        assert cb.allow_request() is True  # first probe allowed
        assert cb.allow_request() is False  # second probe blocked


# ---------------------------------------------------------------------------
# RateLimiter unit tests
# ---------------------------------------------------------------------------


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_acquire_succeeds(self) -> None:
        with patch("app.services.api.base_client.redis_client") as mock_redis:
            mock_redis.eval = AsyncMock(return_value=1)
            rl = RateLimiter(key="test", capacity=10, refill_rate=1.0)
            assert await rl.acquire() is True

    @pytest.mark.asyncio
    async def test_acquire_fails_when_empty(self) -> None:
        with patch("app.services.api.base_client.redis_client") as mock_redis:
            mock_redis.eval = AsyncMock(return_value=0)
            rl = RateLimiter(key="test", capacity=10, refill_rate=1.0)
            assert await rl.acquire() is False


# ---------------------------------------------------------------------------
# BaseAPIClient integration tests
# ---------------------------------------------------------------------------


class _TestClient(BaseAPIClient):
    provider = "test_provider"
    base_url = "https://api.test.local"
    max_retries = 2
    retry_base_delay = 0.01
    rate_limit_capacity = 100
    rate_limit_refill = 100.0


def _mock_response(status_code: int = 200, json_data: dict | None = None) -> httpx.Response:
    resp = httpx.Response(
        status_code=status_code,
        json=json_data or {},
        request=httpx.Request("GET", "https://api.test.local/test"),
    )
    return resp


class TestBaseAPIClientRepr:
    def test_repr_masks_api_key(self) -> None:
        client = _TestClient(api_key="sk-live-super-secret-key-12345")
        r = repr(client)
        assert "sk-l***" in r
        assert "super-secret" not in r

    def test_repr_masks_short_key(self) -> None:
        client = _TestClient(api_key="ab")
        r = repr(client)
        assert "ab" not in r or "***" in r


class TestBaseAPIClientRequest:
    @pytest.mark.asyncio
    async def test_successful_request(self) -> None:
        client = _TestClient(api_key="key")
        mock_resp = _mock_response(200, {"ok": True})

        with (
            patch.object(client, "_send", new_callable=AsyncMock, return_value=mock_resp),
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
            patch.object(client, "_track_usage", new_callable=AsyncMock),
        ):
            resp = await client.request("GET", "/test")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_when_open(self) -> None:
        client = _TestClient()
        # Force the circuit breaker open
        client._circuit_breaker._state = "open"
        client._circuit_breaker._opened_at = time.monotonic()
        client._circuit_breaker.recovery_timeout = 9999

        with pytest.raises(ProviderUnavailableError, match="Circuit breaker open"):
            await client.request("GET", "/test")

    @pytest.mark.asyncio
    async def test_rate_limit_blocks(self) -> None:
        client = _TestClient()
        with patch.object(
            client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=False
        ):
            with pytest.raises(RateLimitError, match="Rate limit exceeded"):
                await client.request("GET", "/test")

    @pytest.mark.asyncio
    async def test_auth_error_not_retried(self) -> None:
        client = _TestClient()
        call_count = 0
        original_send = client._send

        async def _send_auth_fail(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise AuthenticationError(provider="test_provider")

        with (
            patch.object(client, "_send", side_effect=_send_auth_fail),
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
        ):
            with pytest.raises(AuthenticationError):
                await client.request("GET", "/test")
            assert call_count == 1  # No retries for auth errors

    @pytest.mark.asyncio
    async def test_retries_on_provider_unavailable(self) -> None:
        client = _TestClient()
        call_count = 0

        async def _send_fail(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise ProviderUnavailableError(provider="test_provider", status_code=503)

        with (
            patch.object(client, "_send", side_effect=_send_fail),
            patch.object(
                client._rate_limiter, "acquire", new_callable=AsyncMock, return_value=True
            ),
        ):
            with pytest.raises(ProviderUnavailableError):
                await client.request("GET", "/test")
            assert call_count == client.max_retries  # Retried max_retries times


class TestCheckResponse:
    def test_2xx_passes_through(self) -> None:
        client = _TestClient()
        resp = _mock_response(200)
        assert client._check_response(resp).status_code == 200

    def test_429_raises_rate_limit(self) -> None:
        client = _TestClient()
        resp = _mock_response(429, {"message": "too fast"})
        with pytest.raises(RateLimitError):
            client._check_response(resp)

    def test_429_with_non_numeric_retry_after(self) -> None:
        client = _TestClient()
        resp = httpx.Response(
            status_code=429,
            json={"message": "slow down"},
            headers={"Retry-After": "Thu, 01 Jan 2099 00:00:00 GMT"},
            request=httpx.Request("GET", "https://api.test.local/test"),
        )
        with pytest.raises(RateLimitError) as exc_info:
            client._check_response(resp)
        assert exc_info.value.retry_after is None  # Gracefully ignored

    def test_401_raises_auth(self) -> None:
        client = _TestClient()
        resp = _mock_response(401, {"error": "invalid key"})
        with pytest.raises(AuthenticationError):
            client._check_response(resp)

    def test_500_raises_provider_unavailable(self) -> None:
        client = _TestClient()
        resp = _mock_response(500, {"error": "internal"})
        with pytest.raises(ProviderUnavailableError):
            client._check_response(resp)

    def test_400_raises_api_error(self) -> None:
        from app.services.api.errors import APIError

        client = _TestClient()
        resp = _mock_response(400, {"message": "bad input"})
        with pytest.raises(APIError) as exc_info:
            client._check_response(resp)
        assert exc_info.value.status_code == 400


class TestUsageTracking:
    @pytest.mark.asyncio
    async def test_track_usage_inserts_record(self) -> None:
        client = _TestClient()

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.api.base_client.async_session_factory",
            return_value=mock_session,
        ):
            await client._track_usage(
                endpoint="GET /test",
                credits_used=1.0,
                tokens_used=100,
                cost_estimate=Decimal("0.01"),
            )
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_track_usage_swallows_errors(self) -> None:
        client = _TestClient()

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock(side_effect=Exception("db down"))

        with patch(
            "app.services.api.base_client.async_session_factory",
            return_value=mock_session,
        ):
            # Should not raise
            await client._track_usage(endpoint="GET /test")
