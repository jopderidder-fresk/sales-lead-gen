"""Rate-limit-aware concurrency utilities for parallel API calls.

Provides ``gather_rate_limited`` which wraps ``asyncio.gather`` with:

- An ``asyncio.Semaphore`` to cap concurrency.
- Retry with exponential backoff on ``RateLimitError``.
- Error isolation (one failure does not cancel others).
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.core.logging import get_logger
from app.services.api.errors import RateLimitError

logger = get_logger(__name__)

T = TypeVar("T")

# Defaults
_MAX_CONCURRENCY = 5
_MAX_RATE_RETRIES = 4
_RATE_RETRY_BASE_DELAY = 1.5  # seconds
_RATE_RETRY_JITTER = 0.3


async def gather_rate_limited(
    coros: list[Callable[[], Awaitable[T]]],
    *,
    max_concurrency: int = _MAX_CONCURRENCY,
    max_rate_retries: int = _MAX_RATE_RETRIES,
    rate_retry_base_delay: float = _RATE_RETRY_BASE_DELAY,
) -> list[T | BaseException]:
    """Run coroutine factories concurrently with rate-limit-aware retry.

    Each item in *coros* is a **zero-arg callable** that returns an awaitable
    (i.e. a coroutine factory, not a bare coroutine).  This avoids accidentally
    starting coroutines before the semaphore is acquired.

    On ``RateLimitError`` the individual task backs off exponentially and
    retries up to *max_rate_retries* times.  All other exceptions are captured
    and returned in the result list (same semantics as
    ``asyncio.gather(return_exceptions=True)``).

    Returns a list in the same order as *coros*.
    """
    sem = asyncio.Semaphore(max_concurrency)

    async def _run(factory: Callable[[], Awaitable[T]]) -> T:
        async with sem:
            last_exc: BaseException | None = None
            for attempt in range(max_rate_retries + 1):
                try:
                    return await factory()
                except RateLimitError as exc:
                    last_exc = exc
                    if attempt < max_rate_retries:
                        delay = rate_retry_base_delay * (2 ** attempt)
                        jitter = delay * _RATE_RETRY_JITTER
                        wait = delay + random.uniform(-jitter, jitter)  # noqa: S311
                        logger.debug(
                            "rate_limit_retry",
                            attempt=attempt + 1,
                            delay=round(wait, 2),
                        )
                        await asyncio.sleep(wait)
            raise last_exc  # type: ignore[misc]

    results: list[T | BaseException] = list(
        await asyncio.gather(
            *[_run(c) for c in coros],
            return_exceptions=True,
        )
    )
    return results
