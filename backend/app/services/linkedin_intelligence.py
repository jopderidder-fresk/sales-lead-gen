"""LinkedIn intelligence service — scrapes LinkedIn posts and creates signals.

Orchestrates:
1. Apify scrape of company LinkedIn page
2. Store enriched LinkedIn company data in company_info["linkedin"]
3. Create Signal records for each post (deduplicated by content hash)
4. Optionally scrape contact LinkedIn profiles

Signals are created with ``is_processed=False`` so the existing
``process-signal-queue`` task picks them up for LLM classification,
scoring, and action dispatch (including Slack notifications).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.company import Company
from app.models.contact import Contact
from app.models.enums import SignalType
from app.models.signal import Signal
from app.services.api.apify import ApifyError, ApifyService, LinkedInScrapeResult

logger = get_logger(__name__)

_MIN_CONTENT_LENGTH = 50


def _content_hash(content: str) -> str:
    """SHA-256 hash of whitespace-normalized content."""
    normalized = " ".join(content.split())
    return hashlib.sha256(normalized.encode()).hexdigest()


@dataclass
class LinkedInIntelResult:
    """Summary of a single company's LinkedIn intelligence run."""

    company_id: int
    company_domain: str = ""
    posts_scraped: int = 0
    signals_created: int = 0
    contacts_scraped: int = 0
    company_data_updated: bool = False
    error: str | None = None
    signal_ids: list[int] = field(default_factory=list)

    def summary(self) -> str:
        parts = [f"company={self.company_id}"]
        if self.company_domain:
            parts.append(f"domain={self.company_domain}")
        parts.append(f"posts={self.posts_scraped}")
        parts.append(f"signals={self.signals_created}")
        if self.contacts_scraped:
            parts.append(f"contacts_scraped={self.contacts_scraped}")
        if self.error:
            parts.append(f"error={self.error}")
        return " ".join(parts)


class LinkedInIntelligenceService:
    """Orchestrates LinkedIn scraping and signal creation for companies."""

    def __init__(self, apify_token: str) -> None:
        self._apify = ApifyService(api_token=apify_token)

    async def close(self) -> None:
        await self._apify.close()

    async def process_company(
        self,
        company_id: int,
        session: AsyncSession,
        *,
        scrape_contacts: bool = True,
        days_back: int = 7,
    ) -> LinkedInIntelResult:
        """Full LinkedIn intelligence pipeline for one company.

        1. Scrape company LinkedIn page via Apify
        2. Store LinkedIn company data in company_info
        3. Create Signal records for posts
        4. Optionally scrape contact LinkedIn profiles
        """
        company = (
            await session.execute(select(Company).where(Company.id == company_id))
        ).scalar_one_or_none()

        if company is None:
            return LinkedInIntelResult(company_id=company_id, error="company not found")

        result = LinkedInIntelResult(
            company_id=company_id,
            company_domain=company.domain,
        )

        if not company.linkedin_url:
            result.error = "no linkedin_url set"
            return result

        # Calculate scrape_until date (7 days ago)
        scrape_until = (
            datetime.now(UTC) - timedelta(days=days_back)
        ).strftime("%Y-%m-%d")

        # Scrape LinkedIn company page
        try:
            scrape_result = await self._apify.async_scrape_linkedin_company(
                company.linkedin_url,
                limit_per_source=10,
                deep_scrape=True,
                scrape_until=scrape_until,
            )
        except ApifyError as exc:
            logger.error(
                "linkedin.scrape_failed",
                company_id=company_id,
                error=str(exc),
            )
            result.error = str(exc)
            return result

        result.posts_scraped = len(scrape_result.posts)

        # Update company_info with LinkedIn data
        if scrape_result.company_data:
            self._update_company_info(company, scrape_result)
            result.company_data_updated = True

        # Store raw items in company_info for reference
        self._store_raw_linkedin_data(company, scrape_result)

        # Create signals from posts
        signal_ids = await self._create_signals_from_posts(
            company_id, scrape_result, session
        )
        result.signals_created = len(signal_ids)
        result.signal_ids = signal_ids

        # Optionally scrape contact LinkedIn profiles
        if scrape_contacts:
            contacts_scraped = await self._scrape_contact_profiles(
                company_id, session
            )
            result.contacts_scraped = contacts_scraped

        company.linkedin_last_scraped_at = datetime.now(UTC)
        await session.commit()

        logger.info("linkedin.process_company.done", **{
            "company_id": company_id,
            "posts_scraped": result.posts_scraped,
            "signals_created": result.signals_created,
            "contacts_scraped": result.contacts_scraped,
        })
        return result

    async def process_batch(
        self,
        company_ids: list[int],
        session: AsyncSession,
        *,
        days_back: int = 7,
    ) -> list[LinkedInIntelResult]:
        """Process multiple companies sequentially."""
        results: list[LinkedInIntelResult] = []
        for cid in company_ids:
            result = await self.process_company(
                cid, session, days_back=days_back
            )
            results.append(result)
        return results

    # ── Private helpers ───────────────────────────────────────────────

    @staticmethod
    def _update_company_info(
        company: Company,
        scrape_result: LinkedInScrapeResult,
    ) -> None:
        """Merge LinkedIn company data into company_info JSONB."""
        cd = scrape_result.company_data
        if not cd:
            return

        company_info = dict(company.company_info) if company.company_info else {}
        company_info["linkedin"] = {
            "name": cd.name,
            "description": cd.description,
            "follower_count": cd.follower_count,
            "employee_count": cd.employee_count,
            "industry": cd.industry,
            "website": cd.website,
            "headquarters": cd.headquarters,
            "founded": cd.founded,
            "specialties": cd.specialties,
            "scraped_at": datetime.now(UTC).isoformat(),
        }
        company.company_info = company_info

    @staticmethod
    def _store_raw_linkedin_data(
        company: Company,
        scrape_result: LinkedInScrapeResult,
        *,
        max_items: int = 20,
    ) -> None:
        """Store the raw Apify dataset items in company_info for reference.

        Caps stored items to avoid bloating the JSONB column.
        """
        company_info = dict(company.company_info) if company.company_info else {}
        company_info["linkedin_raw_items"] = scrape_result.raw_items[:max_items]
        company.company_info = company_info

    async def _create_signals_from_posts(
        self,
        company_id: int,
        scrape_result: LinkedInScrapeResult,
        session: AsyncSession,
    ) -> list[int]:
        """Create Signal records for LinkedIn posts, with deduplication."""
        # Load existing content hashes for this company
        existing_hashes_result = await session.execute(
            select(Signal.raw_content_hash).where(
                Signal.company_id == company_id,
                Signal.raw_content_hash.isnot(None),
            )
        )
        existing_hashes = set(existing_hashes_result.scalars().all())

        signal_ids: list[int] = []
        for post in scrape_result.posts:
            content = post.content.strip()
            if len(content) < _MIN_CONTENT_LENGTH:
                continue

            content_hash = _content_hash(content)
            if content_hash in existing_hashes:
                continue
            existing_hashes.add(content_hash)

            # Build a descriptive source title
            preview = content[:80].replace("\n", " ")
            source_title = f"LinkedIn: {preview}..."

            signal = Signal(
                company_id=company_id,
                source_url=post.post_url,
                source_title=source_title,
                signal_type=SignalType.NO_SIGNAL,
                raw_markdown=content,
                raw_content_hash=content_hash,
                is_processed=False,
            )
            session.add(signal)
            await session.flush()
            signal_ids.append(signal.id)

        return signal_ids

    async def _scrape_contact_profiles(
        self,
        company_id: int,
        session: AsyncSession,
    ) -> int:
        """Scrape LinkedIn profiles of contacts that have a linkedin_url."""
        contacts_result = await session.execute(
            select(Contact).where(
                Contact.company_id == company_id,
                Contact.linkedin_url.isnot(None),
            )
        )
        contacts = contacts_result.scalars().all()

        if not contacts:
            return 0

        # Load existing content hashes
        existing_hashes_result = await session.execute(
            select(Signal.raw_content_hash).where(
                Signal.company_id == company_id,
                Signal.raw_content_hash.isnot(None),
            )
        )
        existing_hashes = set(existing_hashes_result.scalars().all())

        scraped = 0
        for contact in contacts:
            if not contact.linkedin_url:
                continue
            try:
                profile_data = await self._apify.async_scrape_linkedin_profile(
                    contact.linkedin_url,
                    limit_per_source=5,
                )
            except ApifyError as exc:
                logger.warning(
                    "linkedin.contact_scrape_failed",
                    contact_id=contact.id,
                    error=str(exc),
                )
                continue

            for post in profile_data.posts:
                content = post.content.strip()
                if len(content) < _MIN_CONTENT_LENGTH:
                    continue
                content_hash = _content_hash(content)
                if content_hash in existing_hashes:
                    continue
                existing_hashes.add(content_hash)

                preview = content[:80].replace("\n", " ")
                signal = Signal(
                    company_id=company_id,
                    source_url=post.post_url,
                    source_title=f"LinkedIn ({contact.name}): {preview}...",
                    signal_type=SignalType.NO_SIGNAL,
                    raw_markdown=content,
                    raw_content_hash=content_hash,
                    is_processed=False,
                )
                session.add(signal)

            scraped += 1

        return scraped
