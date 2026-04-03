"""Apify actor client — LinkedIn company and profile scraping.

Uses the ``apify_client`` Python library (NOT BaseAPIClient) since Apify
provides its own client with built-in retry, authentication, and
dataset handling.

Usage::

    service = ApifyService(api_token="your-token")
    result = service.scrape_linkedin_company("https://www.linkedin.com/company/amazon")
    await service.close()
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from apify_client import ApifyClient

from app.core.logging import get_logger

logger = get_logger(__name__)

LINKEDIN_SCRAPER_ACTOR_ID = "Wpp1BZ6yGWjySadk3"


class ApifyError(Exception):
    """Raised when an Apify actor run fails."""

    def __init__(self, message: str, actor_id: str = "") -> None:
        super().__init__(message)
        self.actor_id = actor_id


@dataclass
class LinkedInPost:
    """A single LinkedIn post from the scrape."""

    post_url: str | None = None
    author_name: str | None = None
    content: str = ""
    posted_at: str | None = None  # ISO date string
    likes: int = 0
    comments: int = 0
    shares: int = 0
    post_type: str | None = None


@dataclass
class LinkedInCompanyData:
    """Enriched company data from LinkedIn."""

    name: str | None = None
    description: str | None = None
    follower_count: int | None = None
    employee_count: str | None = None
    industry: str | None = None
    website: str | None = None
    headquarters: str | None = None
    founded: int | None = None
    specialties: list[str] = field(default_factory=list)


@dataclass
class LinkedInProfileData:
    """Data from a personal LinkedIn profile scrape."""

    name: str | None = None
    headline: str | None = None
    posts: list[LinkedInPost] = field(default_factory=list)
    raw_items: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class LinkedInScrapeResult:
    """Full result from a LinkedIn company scrape."""

    linkedin_url: str
    company_data: LinkedInCompanyData | None = None
    posts: list[LinkedInPost] = field(default_factory=list)
    raw_items: list[dict[str, Any]] = field(default_factory=list)


class ApifyService:
    """Apify actor runner — extensible for multiple actors.

    All actor methods are synchronous because ``apify_client`` is a sync
    library. Call them from async code via ``asyncio.to_thread()``.
    """

    def __init__(self, api_token: str) -> None:
        self._client = ApifyClient(api_token)

    async def close(self) -> None:
        """No persistent connections to close for apify_client."""

    # ── Actor runners ─────────────────────────────────────────────────

    def _run_actor(self, actor_id: str, run_input: dict[str, Any]) -> list[dict[str, Any]]:
        """Run an Apify actor and return dataset items."""
        logger.info("apify.actor.start", actor_id=actor_id, input_urls=run_input.get("urls"))
        try:
            run = self._client.actor(actor_id).call(run_input=run_input)
        except Exception as exc:
            raise ApifyError(f"Actor {actor_id} failed: {exc}", actor_id=actor_id) from exc

        if not run or "defaultDatasetId" not in run:
            raise ApifyError(f"Actor {actor_id} returned no dataset", actor_id=actor_id)

        items = list(self._client.dataset(run["defaultDatasetId"]).iterate_items())
        logger.info("apify.actor.done", actor_id=actor_id, items_count=len(items))
        return items

    # ── LinkedIn company scraping ─────────────────────────────────────

    def scrape_linkedin_company(
        self,
        linkedin_url: str,
        *,
        limit_per_source: int = 10,
        deep_scrape: bool = True,
        scrape_until: str | None = None,
    ) -> LinkedInScrapeResult:
        """Scrape a LinkedIn company page for posts and company data.

        Args:
            linkedin_url: Full LinkedIn company URL.
            limit_per_source: Max posts to retrieve.
            deep_scrape: Enable deep scraping for more data.
            scrape_until: ISO date string — only scrape posts newer than this.

        Returns:
            LinkedInScrapeResult with company data and posts.
        """
        run_input: dict[str, Any] = {
            "urls": [linkedin_url],
            "limitPerSource": limit_per_source,
            "scrapeUntil": scrape_until,
            "deepScrape": deep_scrape,
            "rawData": False,
        }
        items = self._run_actor(LINKEDIN_SCRAPER_ACTOR_ID, run_input)
        return self._parse_company_results(linkedin_url, items)

    def scrape_linkedin_profile(
        self,
        profile_url: str,
        *,
        limit_per_source: int = 5,
    ) -> LinkedInProfileData:
        """Scrape a personal LinkedIn profile for recent posts.

        Args:
            profile_url: Full LinkedIn profile URL.
            limit_per_source: Max posts to retrieve.

        Returns:
            LinkedInProfileData with posts from the profile.
        """
        run_input: dict[str, Any] = {
            "urls": [profile_url],
            "limitPerSource": limit_per_source,
            "scrapeUntil": None,
            "deepScrape": True,
            "rawData": False,
        }
        items = self._run_actor(LINKEDIN_SCRAPER_ACTOR_ID, run_input)
        return self._parse_profile_results(profile_url, items)

    # ── Async wrappers ────────────────────────────────────────────────

    async def async_scrape_linkedin_company(
        self,
        linkedin_url: str,
        *,
        limit_per_source: int = 10,
        deep_scrape: bool = True,
        scrape_until: str | None = None,
    ) -> LinkedInScrapeResult:
        """Async wrapper around the sync scrape_linkedin_company."""
        return await asyncio.to_thread(
            self.scrape_linkedin_company,
            linkedin_url,
            limit_per_source=limit_per_source,
            deep_scrape=deep_scrape,
            scrape_until=scrape_until,
        )

    async def async_scrape_linkedin_profile(
        self,
        profile_url: str,
        *,
        limit_per_source: int = 5,
    ) -> LinkedInProfileData:
        """Async wrapper around the sync scrape_linkedin_profile."""
        return await asyncio.to_thread(
            self.scrape_linkedin_profile,
            profile_url,
            limit_per_source=limit_per_source,
        )

    # ── Result parsing ────────────────────────────────────────────────

    @staticmethod
    def _parse_post(item: dict[str, Any]) -> LinkedInPost:
        """Parse a single dataset item into a LinkedInPost."""
        return LinkedInPost(
            post_url=item.get("url") or item.get("postUrl"),
            author_name=item.get("authorName") or item.get("author", {}).get("name"),
            content=item.get("text") or item.get("content") or item.get("body") or "",
            posted_at=item.get("postedAt") or item.get("publishedAt") or item.get("date"),
            likes=_safe_int(item.get("likesCount") or item.get("likes")) or 0,
            comments=_safe_int(item.get("commentsCount")) or 0,
            shares=_safe_int(item.get("sharesCount") or item.get("shares")) or 0,
            post_type=item.get("type") or item.get("postType"),
        )

    @staticmethod
    def _parse_company_data(item: dict[str, Any]) -> LinkedInCompanyData:
        """Parse company metadata from a dataset item."""
        return LinkedInCompanyData(
            name=item.get("companyName") or item.get("name"),
            description=item.get("description") or item.get("about"),
            follower_count=_safe_int(item.get("followerCount") or item.get("followers")),
            employee_count=str(item.get("employeeCount") or item.get("employees") or ""),
            industry=item.get("industry"),
            website=item.get("website") or item.get("companyUrl"),
            headquarters=item.get("headquarters") or item.get("location"),
            founded=_safe_int(item.get("founded") or item.get("foundedYear")),
            specialties=item.get("specialties") or [],
        )

    def _parse_company_results(
        self, linkedin_url: str, items: list[dict[str, Any]]
    ) -> LinkedInScrapeResult:
        """Parse all dataset items into a LinkedInScrapeResult."""
        company_data: LinkedInCompanyData | None = None
        posts: list[LinkedInPost] = []

        for item in items:
            # Items with post content are posts; items with company metadata are company data
            text = item.get("text") or item.get("content") or item.get("body") or ""
            if text.strip():
                posts.append(self._parse_post(item))
            # Try to extract company data from any item that has it
            if not company_data and (item.get("companyName") or item.get("name")):
                company_data = self._parse_company_data(item)

        return LinkedInScrapeResult(
            linkedin_url=linkedin_url,
            company_data=company_data,
            posts=posts,
            raw_items=items,
        )

    def _parse_profile_results(
        self, profile_url: str, items: list[dict[str, Any]]
    ) -> LinkedInProfileData:
        """Parse dataset items from a profile scrape."""
        posts: list[LinkedInPost] = []
        name: str | None = None
        headline: str | None = None

        for item in items:
            text = item.get("text") or item.get("content") or item.get("body") or ""
            if text.strip():
                posts.append(self._parse_post(item))
            if not name:
                name = item.get("authorName") or item.get("author", {}).get("name")
            if not headline:
                headline = item.get("authorHeadline") or item.get("headline")

        return LinkedInProfileData(
            name=name,
            headline=headline,
            posts=posts,
            raw_items=items,
        )


def _safe_int(value: Any) -> int | None:
    """Convert a value to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
