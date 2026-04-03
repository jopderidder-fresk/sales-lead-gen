"""Firecrawl API client — web search, scraping, and crawling.

Supports three core operations:

- **search**: Natural-language web search returning URLs + content.
- **scrape**: Single-page scrape returning clean markdown.
- **crawl**: Async multi-page crawl with polling for completion.

Usage::

    client = FirecrawlClient(api_key="your-key")
    results = await client.search("AI startups in Amsterdam", limit=5)
    page    = await client.scrape("https://example.com/about")
    pages   = await client.crawl("https://example.com", max_pages=10)
    await client.close()
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from enum import StrEnum

import httpx
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services.api.base_client import BaseAPIClient
from app.services.api.errors import APIError

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class SearchResult(BaseModel):
    """A single result from the Firecrawl ``/search`` endpoint."""

    url: str = Field(description="URL of the page")
    title: str | None = Field(default=None, description="Page title")
    markdown: str | None = Field(default=None, description="Page content as markdown")


class SearchResponse(BaseModel):
    """Parsed response from ``POST /search``."""

    query: str
    results: list[SearchResult] = Field(default_factory=list)
    total: int = 0


class ScrapeResponse(BaseModel):
    """Parsed response from ``POST /scrape``."""

    url: str
    markdown: str = Field(default="", description="Scraped content as markdown")
    title: str | None = None
    status_code: int | None = Field(default=None, description="HTTP status of the scraped page")


class CrawlStatus(StrEnum):
    SCRAPING = "scraping"
    COMPLETED = "completed"
    FAILED = "failed"


class CrawlPage(BaseModel):
    """A single page from a crawl result."""

    url: str
    markdown: str = ""
    title: str | None = None
    status_code: int | None = None


class CrawlResponse(BaseModel):
    """Parsed response from a completed crawl job."""

    crawl_id: str
    status: CrawlStatus
    pages: list[CrawlPage] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Firecrawl-specific errors
# ---------------------------------------------------------------------------


class FirecrawlCreditsExhaustedError(APIError):
    """Raised when the Firecrawl account has run out of credits."""

    def __init__(self, message: str = "Firecrawl credits exhausted") -> None:
        super().__init__(message, provider="firecrawl", status_code=402)


class FirecrawlScrapeFailedError(APIError):
    """Raised when Firecrawl fails to scrape the target URL."""

    def __init__(self, url: str, detail: str = "") -> None:
        msg = f"Scrape failed for {url}"
        if detail:
            msg = f"{msg}: {detail}"
        super().__init__(msg, provider="firecrawl", status_code=500)


class FirecrawlCrawlFailedError(APIError):
    """Raised when an async crawl job ends with status 'failed'."""

    def __init__(self, crawl_id: str, detail: str = "") -> None:
        msg = f"Crawl job {crawl_id} failed"
        if detail:
            msg = f"{msg}: {detail}"
        super().__init__(msg, provider="firecrawl")


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class FirecrawlClient(BaseAPIClient):
    """Firecrawl provider client for web search, scraping, and crawling."""

    provider = "firecrawl"
    base_url = "https://api.firecrawl.dev/v1"

    # Firecrawl pages can take a long time to render; use a generous timeout.
    timeout: float = 60.0

    # Firecrawl default rate limits — conservative starting point.
    rate_limit_capacity: int = 10
    rate_limit_refill: float = 1.0  # 10 tokens / 10 sec

    # Crawl polling configuration.
    crawl_poll_interval: float = 2.0  # seconds between polls
    crawl_max_poll_time: float = 300.0  # max seconds to wait for a crawl

    def __init__(self, api_key: str) -> None:
        super().__init__(api_key=api_key)

    def _build_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

    def _check_response(self, response: httpx.Response) -> httpx.Response:
        """Extend base check with Firecrawl-specific error codes."""
        if response.status_code == 402:
            raise FirecrawlCreditsExhaustedError()
        return super()._check_response(response)

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> SearchResponse:
        """Search the web for pages matching a natural-language query.

        Args:
            query: Natural-language search query.
            limit: Maximum number of results (default 5).

        Returns:
            ``SearchResponse`` with matched pages and content.
        """
        payload: dict = {
            "query": query,
            "limit": limit,
            "scrapeOptions": {"formats": ["markdown"]},
        }

        response = await self.post(
            "/search",
            json=payload,
            credits_used=float(limit),
            cost_estimate=Decimal("0.01") * limit,
        )

        body = response.json()
        data = body.get("data", [])

        results = [
            SearchResult(
                url=item.get("url", ""),
                title=item.get("metadata", {}).get("title"),
                markdown=item.get("markdown"),
            )
            for item in data
        ]

        return SearchResponse(
            query=query,
            results=results,
            total=len(results),
        )

    async def map_site(
        self,
        url: str,
        *,
        limit: int = 500,
        search: str | None = None,
        include_subdomains: bool = False,
        ignore_sitemap: bool = False,
    ) -> list[str]:
        """Discover URLs on a site (sitemap + crawl). Returns link strings.

        Used to find news- and jobs-related paths before targeted scrapes.
        """
        payload: dict = {
            "url": url,
            "limit": min(max(limit, 1), 30_000),
            "includeSubdomains": include_subdomains,
            "ignoreSitemap": ignore_sitemap,
        }
        if search:
            payload["search"] = search

        response = await self.post(
            "/map",
            json=payload,
            credits_used=1.0,
            cost_estimate=Decimal("0.01"),
        )

        body = response.json()
        links = body.get("links") or []
        if not body.get("success", True) and not links:
            return []
        return [str(u) for u in links if u]

    async def scrape(
        self,
        url: str,
        *,
        formats: list[str] | None = None,
    ) -> ScrapeResponse:
        """Scrape a single URL and return its content.

        Args:
            url: The URL to scrape.
            formats: Content formats to request (default ``["markdown"]``).

        Returns:
            ``ScrapeResponse`` with the page content.

        Raises:
            FirecrawlScrapeFailedError: If the scrape fails server-side.
        """
        payload: dict = {
            "url": url,
            "formats": formats or ["markdown"],
        }

        response = await self.post(
            "/scrape",
            json=payload,
            credits_used=1.0,
            cost_estimate=Decimal("0.01"),
        )

        body = response.json()
        data = body.get("data", {})

        if not data:
            raise FirecrawlScrapeFailedError(url, "Empty response data")

        return ScrapeResponse(
            url=url,
            markdown=data.get("markdown", ""),
            title=data.get("metadata", {}).get("title"),
            status_code=data.get("metadata", {}).get("statusCode"),
        )

    async def crawl(
        self,
        url: str,
        *,
        max_pages: int = 10,
        include_paths: list[str] | None = None,
    ) -> CrawlResponse:
        """Start an async crawl job and poll until completion.

        Args:
            url: The starting URL to crawl.
            max_pages: Maximum number of pages to crawl.
            include_paths: Optional glob patterns to restrict crawled paths
                (e.g. ``["/blog/*", "/about"]``).

        Returns:
            ``CrawlResponse`` with all crawled pages.

        Raises:
            FirecrawlCrawlFailedError: If the crawl job fails.
            TimeoutError: If the crawl exceeds ``crawl_max_poll_time``.
        """
        # Start the crawl job.
        payload: dict = {
            "url": url,
            "limit": max_pages,
            "scrapeOptions": {"formats": ["markdown"]},
        }
        if include_paths:
            payload["includePaths"] = include_paths

        start_response = await self.post(
            "/crawl",
            json=payload,
            credits_used=float(max_pages),
            cost_estimate=Decimal("0.01") * max_pages,
        )

        start_body = start_response.json()
        crawl_id = start_body.get("id", "")

        if not crawl_id:
            raise FirecrawlCrawlFailedError("unknown", "No crawl ID returned")

        # Poll for completion.
        return await self._poll_crawl(crawl_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _poll_crawl(self, crawl_id: str) -> CrawlResponse:
        """Poll the crawl status endpoint until the job completes or fails."""
        import time as _time

        deadline = _time.monotonic() + self.crawl_max_poll_time

        while _time.monotonic() < deadline:
            await asyncio.sleep(self.crawl_poll_interval)

            response = await self.get(f"/crawl/{crawl_id}")
            body = response.json()

            status = body.get("status", "scraping")

            if status == "completed":
                return self._parse_crawl_response(crawl_id, body)

            if status == "failed":
                raise FirecrawlCrawlFailedError(
                    crawl_id,
                    body.get("error", "Unknown error"),
                )

            logger.debug(
                "crawl_polling",
                crawl_id=crawl_id,
                status=status,
                elapsed=round(self.crawl_max_poll_time - (deadline - _time.monotonic()), 1),
            )

        raise TimeoutError(
            f"Crawl {crawl_id} did not complete within {self.crawl_max_poll_time}s"
        )

    @staticmethod
    def _parse_crawl_response(crawl_id: str, body: dict) -> CrawlResponse:
        """Parse the completed crawl response into a ``CrawlResponse``."""
        data = body.get("data", [])

        pages = [
            CrawlPage(
                url=item.get("metadata", {}).get("sourceURL", item.get("url", "")),
                markdown=item.get("markdown", ""),
                title=item.get("metadata", {}).get("title"),
                status_code=item.get("metadata", {}).get("statusCode"),
            )
            for item in data
        ]

        return CrawlResponse(
            crawl_id=crawl_id,
            status=CrawlStatus.COMPLETED,
            pages=pages,
            total=body.get("total", len(pages)),
        )
