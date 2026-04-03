"""Signal monitoring service — scrapes tracked companies for changes.

Discovers candidate URLs via Firecrawl ``/map``, keeps pages whose paths look
like **news** or **vacancies** (language-agnostic heuristics), then scrapes only
those URLs. Falls back to common path guesses when mapping returns nothing.
Uses SHA-256 content hashing for change detection.  Does **not** create Signal
records — signals are generated exclusively from LinkedIn post data.

Usage::

    service = SignalMonitorService(firecrawl_api_key="...")
    async with async_session_factory() as session:
        result = await service.monitor_company(company_id, session)
    await service.close()
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.core.redis import redis_client
from app.core.utils import today_start_utc, utcnow
from app.models.api_usage import APIUsage
from app.models.company import Company
from app.models.enums import CompanyStatus, ScrapeJobStatus
from app.models.scrape_job import ScrapeJob
from app.services.api.firecrawl import FirecrawlClient
from app.services.intel_target_urls import (
    fallback_intel_paths,
    select_intel_urls,
)

logger = structlog.get_logger(__name__)

# Redis key prefix for content hashes.
_HASH_PREFIX = "content_hash"

# Maximum runtime per company (seconds).
_MAX_RUNTIME = 300  # 5 minutes

# Delay between requests to the same domain (seconds).
_INTER_REQUEST_DELAY = 2.0

# Redis TTL for cached content hashes (90 days).
_HASH_TTL = 90 * 24 * 3600


@dataclass
class MonitorResult:
    """Summary of a single company monitoring run."""

    company_id: int
    company_domain: str = ""
    pages_scraped: int = 0
    pages_changed: int = 0
    pages_skipped: int = 0
    pages_failed: int = 0
    signals_created: int = 0
    credits_used: float = 0.0
    elapsed_seconds: float = 0.0
    error: str | None = None

    def summary(self) -> str:
        parts = [
            f"company={self.company_domain}",
            f"scraped={self.pages_scraped}",
            f"changed={self.pages_changed}",
            f"signals={self.signals_created}",
            f"credits={self.credits_used:.1f}",
            f"elapsed={self.elapsed_seconds:.1f}s",
        ]
        if self.error:
            parts.append(f"error={self.error}")
        return " | ".join(parts)


@dataclass
class BatchMonitorResult:
    """Summary of a batch monitoring run."""

    companies_processed: int = 0
    total_signals_created: int = 0
    total_credits_used: float = 0.0
    elapsed_seconds: float = 0.0
    results: list[MonitorResult] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"companies={self.companies_processed} "
            f"signals={self.total_signals_created} "
            f"credits={self.total_credits_used:.1f} "
            f"elapsed={self.elapsed_seconds:.1f}s"
        )


def _content_hash(content: str) -> str:
    """SHA-256 hash of whitespace-normalized content."""
    normalized = " ".join(content.split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def _redis_hash_key(company_id: int, url: str) -> str:
    """Redis key for storing a content hash."""
    return f"{_HASH_PREFIX}:{company_id}:{url}"


async def _get_cached_hash(company_id: int, url: str) -> str | None:
    """Retrieve the last-seen content hash from Redis."""
    try:
        return await redis_client.get(_redis_hash_key(company_id, url))
    except Exception:
        return None


async def _set_cached_hash(company_id: int, url: str, content_hash: str) -> None:
    """Store a content hash in Redis with TTL."""
    try:
        await redis_client.setex(
            _redis_hash_key(company_id, url),
            _HASH_TTL,
            content_hash,
        )
    except Exception:
        pass  # non-critical; monitoring continues without cache


def _parse_robots_txt(robots_txt: str, base_url: str) -> RobotFileParser:
    """Parse a robots.txt string into a RobotFileParser."""
    parser = RobotFileParser()
    parser.set_url(f"{base_url}/robots.txt")
    parser.parse(robots_txt.splitlines())
    return parser


class SignalMonitorService:
    """Scrapes company websites and creates Signal records for changed content."""

    def __init__(
        self,
        firecrawl_api_key: str,
        *,
        additional_seed_paths: list[str] | None = None,
        max_scrape_urls: int = 22,
        map_limit: int = 400,
    ) -> None:
        self._firecrawl = FirecrawlClient(api_key=firecrawl_api_key)
        self._additional_seed_paths = additional_seed_paths or []
        self._max_scrape_urls = max_scrape_urls
        self._map_limit = map_limit

    async def close(self) -> None:
        """Release underlying HTTP clients."""
        await self._firecrawl.close()

    async def monitor_company(
        self,
        company_id: int,
        session: AsyncSession,
    ) -> MonitorResult:
        """Scrape all configured pages for a company, detect changes, create signals."""
        start = time.monotonic()
        result = MonitorResult(company_id=company_id)

        # Load company
        row = await session.execute(
            select(Company).where(Company.id == company_id)
        )
        company = row.scalar_one_or_none()
        if company is None or company.status == CompanyStatus.ARCHIVED:
            result.error = "company not found or archived"
            return result

        result.company_domain = company.domain
        base_url = f"https://{company.domain}"

        log = logger.bind(company_id=company_id, domain=company.domain)
        log.info("monitor.start")

        # Create a ScrapeJob to track this monitoring run
        scrape_job = ScrapeJob(
            company_id=company_id,
            target_url=base_url,
            status=ScrapeJobStatus.RUNNING,
            started_at=utcnow(),
        )
        session.add(scrape_job)
        await session.flush()

        # Fetch and parse robots.txt
        robots_parser = await self._fetch_robots_txt(base_url, log)

        targets: list[str] = []
        try:
            raw_links = await self._firecrawl.map_site(
                base_url,
                limit=self._map_limit,
                include_subdomains=False,
                ignore_sitemap=False,
            )
            picked, url_stats = select_intel_urls(
                raw_links,
                company.domain,
                max_total=self._max_scrape_urls,
            )
            targets.extend(picked)
            result.credits_used += 1.0  # map call
            log.info(
                "monitor.url_map",
                map_links=len(raw_links),
                picked=len(picked),
                **url_stats,
            )
        except Exception as exc:
            log.warning("monitor.map_failed", error=str(exc))

        if not targets:
            targets = [
                urljoin(base_url + "/", p.lstrip("/"))
                for p in fallback_intel_paths()
            ]
            log.info("monitor.fallback_paths", count=len(targets))

        for extra in self._additional_seed_paths:
            u = urljoin(base_url + "/", extra.lstrip("/"))
            if u not in targets:
                targets.append(u)

        targets = targets[: self._max_scrape_urls]

        for page_url in targets:
            # Runtime guard
            elapsed = time.monotonic() - start
            if elapsed > _MAX_RUNTIME:
                log.warning("monitor.timeout", elapsed=round(elapsed, 1))
                result.error = "timeout after 5 minutes"
                break

            # robots.txt compliance
            if robots_parser and not robots_parser.can_fetch("*", page_url):
                log.info("monitor.robots_blocked", url=page_url)
                result.pages_skipped += 1
                continue

            try:
                scrape_result = await self._firecrawl.scrape(page_url)
                result.credits_used += 1.0
                result.pages_scraped += 1
            except Exception as exc:
                log.warning("monitor.scrape_failed", url=page_url, error=str(exc))
                result.pages_failed += 1
                await asyncio.sleep(_INTER_REQUEST_DELAY)
                continue

            markdown = scrape_result.markdown
            if not markdown or len(markdown.strip()) < 50:
                log.debug("monitor.empty_content", url=page_url)
                result.pages_skipped += 1
                await asyncio.sleep(_INTER_REQUEST_DELAY)
                continue

            # Change detection via content hash
            new_hash = _content_hash(markdown)
            cached_hash = await _get_cached_hash(company_id, page_url)

            if cached_hash == new_hash:
                log.debug("monitor.no_change", url=page_url)
                await asyncio.sleep(_INTER_REQUEST_DELAY)
                continue

            # Content has changed — log it and update hash, but do not
            # create a Signal.  Signals are now generated exclusively from
            # LinkedIn post data (see linkedin_intelligence.py).
            result.pages_changed += 1

            # Update cached hash
            await _set_cached_hash(company_id, page_url, new_hash)

            log.info("monitor.change_detected", url=page_url)
            await asyncio.sleep(_INTER_REQUEST_DELAY)

        # Finalize scrape job
        result.elapsed_seconds = time.monotonic() - start
        scrape_job.status = (
            ScrapeJobStatus.COMPLETED if result.error is None else ScrapeJobStatus.FAILED
        )
        scrape_job.completed_at = utcnow()
        scrape_job.pages_scraped = result.pages_scraped
        scrape_job.credits_used = result.credits_used
        scrape_job.error_message = result.error

        await session.commit()
        log.info("monitor.done", **{"result": result.summary()})
        return result

    async def monitor_batch(
        self,
        company_ids: list[int],
        session: AsyncSession,
    ) -> BatchMonitorResult:
        """Monitor multiple companies sequentially."""
        start = time.monotonic()
        batch = BatchMonitorResult()

        for company_id in company_ids:
            # Check daily cost limit before each company to prevent runaway bills
            if await self._daily_cost_exceeded(session):
                logger.warning(
                    "monitor.batch.daily_cost_limit",
                    processed=batch.companies_processed,
                    total_credits=batch.total_credits_used,
                )
                break

            company_result = await self.monitor_company(company_id, session)
            batch.results.append(company_result)
            batch.companies_processed += 1
            batch.total_signals_created += company_result.signals_created
            batch.total_credits_used += company_result.credits_used

        batch.elapsed_seconds = time.monotonic() - start
        return batch

    @staticmethod
    async def _daily_cost_exceeded(session: AsyncSession) -> bool:
        """Check if today's total API spend exceeds the configured daily limit."""
        limit = app_settings.daily_api_cost_limit
        if limit <= 0:
            return False
        today_start = today_start_utc()
        total = (
            await session.execute(
                select(func.coalesce(func.sum(APIUsage.cost_estimate), 0)).where(
                    APIUsage.timestamp >= today_start,
                )
            )
        ).scalar_one()
        return float(total or 0) >= limit

    async def _fetch_robots_txt(
        self,
        base_url: str,
        log: structlog.stdlib.BoundLogger,
    ) -> RobotFileParser | None:
        """Try to fetch and parse robots.txt. Returns None on failure."""
        robots_url = f"{base_url}/robots.txt"
        try:
            response = await self._firecrawl.scrape(robots_url)
            if response.markdown:
                return _parse_robots_txt(response.markdown, base_url)
        except Exception:
            log.debug("monitor.robots_fetch_failed", url=robots_url)
        return None


