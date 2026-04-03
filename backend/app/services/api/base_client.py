"""Base HTTP client for all external API integrations.

Provides:
- Async HTTP via ``httpx.AsyncClient`` with connection pooling
- Automatic retries with exponential backoff + jitter
- Token-bucket rate limiting backed by Redis
- Circuit breaker (closed → open → half-open)
- Non-blocking usage tracking to the ``api_usage`` table
"""

from __future__ import annotations

import asyncio
import random
import time
from decimal import Decimal
from typing import Any

import httpx

from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.core.redis import redis_client
from app.models.api_usage import APIUsage
from app.services.api.errors import (
    APIError,
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

_CLOSED = "closed"
_OPEN = "open"
_HALF_OPEN = "half-open"


class CircuitBreaker:
    """Simple in-process circuit breaker.

    * **closed** — requests flow normally.
    * **open** — requests are rejected immediately after *failure_threshold*
      consecutive failures; stays open for *recovery_timeout* seconds.
    * **half-open** — a single probe request is allowed; success resets to
      closed, failure reopens.
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = _CLOSED
        self._failure_count = 0
        self._opened_at: float = 0.0
        self._half_open_probe_sent = False

    @property
    def state(self) -> str:
        if self._state == _OPEN and self._seconds_since_open() >= self.recovery_timeout:
            self._state = _HALF_OPEN
            self._half_open_probe_sent = False
        return self._state

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = _CLOSED
        self._half_open_probe_sent = False

    def record_failure(self) -> None:
        self._failure_count += 1
        if self._state == _HALF_OPEN or self._failure_count >= self.failure_threshold:
            self._state = _OPEN
            self._opened_at = time.monotonic()
            self._half_open_probe_sent = False

    def allow_request(self) -> bool:
        state = self.state  # triggers half-open check
        if state == _CLOSED:
            return True
        if state == _HALF_OPEN and not self._half_open_probe_sent:
            self._half_open_probe_sent = True
            return True
        return False

    def _seconds_since_open(self) -> float:
        return time.monotonic() - self._opened_at


# ---------------------------------------------------------------------------
# Token-bucket rate limiter (Redis-backed)
# ---------------------------------------------------------------------------


class RateLimiter:
    """Distributed token-bucket rate limiter using Redis.

    Each provider gets its own bucket identified by ``key``.  Tokens refill
    continuously at ``refill_rate`` tokens/second up to ``capacity``.
    """

    def __init__(self, key: str, capacity: int, refill_rate: float) -> None:
        self.key = f"ratelimit:{key}"
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens per second

    # Lua script for atomic token consumption.
    # KEYS[1] = bucket key, ARGV = [capacity, refill_rate, now, tokens_requested]
    _LUA_SCRIPT = """
    local key       = KEYS[1]
    local capacity  = tonumber(ARGV[1])
    local refill    = tonumber(ARGV[2])
    local now       = tonumber(ARGV[3])
    local requested = tonumber(ARGV[4])

    local data = redis.call('HMGET', key, 'tokens', 'last')
    local tokens = tonumber(data[1])
    local last   = tonumber(data[2])

    if tokens == nil then
        tokens = capacity
        last   = now
    end

    local elapsed = math.max(0, now - last)
    tokens = math.min(capacity, tokens + elapsed * refill)

    if tokens >= requested then
        tokens = tokens - requested
        redis.call('HMSET', key, 'tokens', tokens, 'last', now)
        redis.call('EXPIRE', key, 3600)
        return 1
    else
        redis.call('HMSET', key, 'tokens', tokens, 'last', now)
        redis.call('EXPIRE', key, 3600)
        return 0
    end
    """

    async def acquire(self, tokens: int = 1) -> bool:
        """Try to consume *tokens* from the bucket.  Returns True on success."""
        now = time.time()
        result = await redis_client.eval(  # type: ignore[misc]
            self._LUA_SCRIPT,
            1,
            self.key,
            str(self.capacity),
            str(self.refill_rate),
            str(now),
            str(tokens),
        )
        return bool(result)


# ---------------------------------------------------------------------------
# Base API client
# ---------------------------------------------------------------------------


_background_tasks: set[asyncio.Task[None]] = set()
"""Module-level set that keeps strong references to fire-and-forget tasks,
preventing 'Task was destroyed but it is pending' warnings."""


def _spawn_background(coro: Any) -> None:
    """Schedule a coroutine as a tracked background task."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def drain_background_tasks(timeout: float = 5.0) -> None:
    """Await all pending background tasks (call during shutdown)."""
    if _background_tasks:
        await asyncio.wait(_background_tasks, timeout=timeout)


class BaseAPIClient:
    """Abstract base for all external API provider clients.

    Subclasses must set ``provider`` and ``base_url`` (at minimum) and can
    override ``_build_headers`` to inject auth headers.

    Example::

        class HunterClient(BaseAPIClient):
            provider = "hunter"
            base_url = "https://api.hunter.io/v2"

            def _build_headers(self) -> dict[str, str]:
                return {"Authorization": f"Bearer {self._api_key}"}
    """

    # --- Override in subclasses ---
    provider: str = ""
    base_url: str = ""

    # Default timeout per request (seconds).
    timeout: float = 30.0

    # Retry configuration.
    max_retries: int = 3
    retry_base_delay: float = 1.0  # seconds; doubled each attempt
    retry_max_delay: float = 30.0  # cap on backoff
    retry_jitter: float = 0.5  # ± jitter factor

    # Circuit breaker defaults.
    cb_failure_threshold: int = 5
    cb_recovery_timeout: float = 60.0

    # Rate limiter defaults (tokens per second / bucket capacity).
    rate_limit_capacity: int = 10
    rate_limit_refill: float = 1.0  # tokens/sec

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None
        # Prevent accidental logging of full API keys.
        self._api_key_masked = f"{api_key[:4]}***" if len(api_key) > 4 else "***"
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=self.cb_failure_threshold,
            recovery_timeout=self.cb_recovery_timeout,
        )
        self._rate_limiter = RateLimiter(
            key=self.provider,
            capacity=self.rate_limit_capacity,
            refill_rate=self.rate_limit_refill,
        )

    def __repr__(self) -> str:
        return f"<{type(self).__name__}(provider={self.provider!r}, key={self._api_key_masked})>"

    # --- Lifecycle ---

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-init a pooled ``httpx.AsyncClient``."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                headers=self._build_headers(),
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # --- Hook points for subclasses ---

    def _build_headers(self) -> dict[str, str]:
        """Return default headers.  Override to add Authorization, etc."""
        return {"Accept": "application/json"}

    def _extract_error_message(self, response: httpx.Response) -> str:
        """Try to pull a human-readable error from the response body.

        Truncated to 200 chars to avoid leaking sensitive data from API
        responses into logs and exception messages.
        """
        try:
            body = response.json()
            for key in ("message", "error", "detail", "error_message"):
                if key in body:
                    val = body[key]
                    msg = val if isinstance(val, str) else str(val)
                    return msg[:200]
        except Exception:
            pass
        return f"HTTP {response.status_code}"

    # --- Core request method ---

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        credits_used: float | None = None,
        tokens_used: int | None = None,
        cost_estimate: Decimal | None = None,
    ) -> httpx.Response:
        """Send an HTTP request with retry, rate-limit and circuit-breaker protection.

        Args:
            method: HTTP method (GET, POST, …).
            path: URL path appended to ``base_url``.
            params: Query parameters.
            json: JSON body.
            headers: Extra headers merged with defaults.
            credits_used: Provider credits consumed (for usage tracking).
            tokens_used: LLM tokens consumed (for usage tracking).
            cost_estimate: Estimated cost in EUR (for usage tracking).

        Returns:
            The ``httpx.Response`` on success (2xx).

        Raises:
            RateLimitError: Bucket empty or provider returned 429.
            AuthenticationError: Provider returned 401/403.
            ProviderUnavailableError: Provider returned 5xx or network error
                after exhausting retries (or circuit is open).
            APIError: Any other non-2xx status after exhausting retries.
        """
        # Circuit breaker gate
        if not self._circuit_breaker.allow_request():
            raise ProviderUnavailableError(
                f"Circuit breaker open for {self.provider}",
                provider=self.provider,
            )

        # Rate limiter gate
        if not await self._rate_limiter.acquire():
            raise RateLimitError(
                f"Rate limit exceeded for {self.provider}",
                provider=self.provider,
            )

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self._send(method, path, params=params, json=json, headers=headers)
                self._circuit_breaker.record_success()

                # Fire-and-forget usage tracking (reference kept in _background_tasks)
                _spawn_background(
                    self._track_usage(
                        endpoint=f"{method} {path}",
                        credits_used=credits_used,
                        tokens_used=tokens_used,
                        cost_estimate=cost_estimate,
                    )
                )
                return response

            except (RateLimitError, AuthenticationError):
                # Never retry auth or rate-limit errors — surface immediately.
                raise

            except APIError as exc:
                last_exc = exc
                self._circuit_breaker.record_failure()
                if attempt < self.max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "api_retry",
                        provider=self.provider,
                        path=path,
                        attempt=attempt,
                        delay=round(delay, 2),
                        error=str(exc),
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted
        raise last_exc  # type: ignore[misc]

    async def _send(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Execute a single HTTP request and translate errors."""
        client = await self._get_client()
        try:
            response = await client.request(
                method,
                path,
                params=params,
                json=json,
                headers=headers or {},
            )
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError(
                f"Request timed out: {exc}",
                provider=self.provider,
            ) from exc
        except httpx.ConnectError as exc:
            raise ProviderUnavailableError(
                f"Connection failed: {exc}",
                provider=self.provider,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                f"HTTP error: {exc}",
                provider=self.provider,
            ) from exc

        return self._check_response(response)

    def _check_response(self, response: httpx.Response) -> httpx.Response:
        """Raise a typed error for non-2xx responses."""
        if 200 <= response.status_code < 300:
            return response

        msg = self._extract_error_message(response)

        if response.status_code == 429:
            retry_after: float | None = None
            raw_retry = response.headers.get("Retry-After")
            if raw_retry:
                try:
                    retry_after = float(raw_retry)
                except (ValueError, OverflowError):
                    pass  # Non-numeric Retry-After (e.g. HTTP-date) — ignore
            raise RateLimitError(
                msg,
                provider=self.provider,
                retry_after=retry_after,
            )

        if response.status_code in (401, 403):
            raise AuthenticationError(
                msg,
                provider=self.provider,
                status_code=response.status_code,
            )

        if response.status_code >= 500:
            raise ProviderUnavailableError(
                msg,
                provider=self.provider,
                status_code=response.status_code,
            )

        raise APIError(
            msg,
            provider=self.provider,
            status_code=response.status_code,
        )

    # --- Helpers ---

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter."""
        delay = min(self.retry_base_delay * (2 ** (attempt - 1)), self.retry_max_delay)
        jitter = delay * self.retry_jitter
        return delay + random.uniform(-jitter, jitter)  # noqa: S311

    async def _track_usage(
        self,
        endpoint: str,
        credits_used: float | None = None,
        tokens_used: int | None = None,
        cost_estimate: Decimal | None = None,
    ) -> None:
        """Insert a row into ``api_usage`` without blocking the caller."""
        try:
            async with async_session_factory() as session:
                usage = APIUsage(
                    provider=self.provider,
                    endpoint=endpoint,
                    credits_used=credits_used,
                    tokens_used=tokens_used,
                    cost_estimate=cost_estimate,
                )
                session.add(usage)
                await session.commit()
        except Exception:
            logger.warning("usage_tracking_failed", provider=self.provider, endpoint=endpoint)

    # --- Convenience wrappers ---

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", path, **kwargs)
