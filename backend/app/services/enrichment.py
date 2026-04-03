"""Waterfall contact finding service.

Orchestrates providers in priority order to find decision-maker
contacts for a given company:

    1. Hunter.io        — domain search + email verification
    2. ScrapIn          — GDPR-compliant public professional data
    3. Scraped content   — LLM contact extraction from already-scraped Signal data

The waterfall stops as soon as at least one contact with a verified email
is found whose title matches the configured target titles.

This service never scrapes websites directly. It relies on content already
present in Signal records (created by the separate scrape task). This
means contact finding can run even when Firecrawl credits are exhausted.

Note: Company profile generation (company_info) has been moved to
``CompanyEnrichmentService``. This service only handles contacts.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.company import Company
from app.models.contact import Contact
from app.models.enums import EmailStatus
from app.models.signal import Signal
from app.services.api.errors import APIError
from app.services.api.hunter import HunterClient, VerificationStatus
from app.services.api.scrapin import ScrapInClient
from app.services.llm import LLMService, create_llm_client

logger = structlog.get_logger(__name__)

# Target titles — configurable default
DEFAULT_TARGET_TITLES: list[str] = [
    "CTO",
    "CIO",
    "VP Engineering",
    "VP of Engineering",
    "Head of Engineering",
    "Head of IT",
    "Chief Technology Officer",
    "Chief Information Officer",
]

# Maximum wall-clock time (seconds) for enriching a single company.
_ENRICHMENT_TIMEOUT_SECONDS = 60

# Paths to look up cached content for contact extraction
_TEAM_PATHS = ["/about", "/team", "/leadership", "/management", "/people"]


@dataclass
class EnrichmentResult:
    """Summary of a single-company enrichment run."""

    company_id: int
    contacts_added: int = 0
    provider_used: str | None = None
    providers_tried: list[str] = field(default_factory=list)
    verified_found: bool = False
    error: str | None = None

    def summary(self) -> str:
        if self.error:
            return f"company={self.company_id} error={self.error}"
        return (
            f"company={self.company_id} contacts_added={self.contacts_added} "
            f"provider={self.provider_used} tried={self.providers_tried} "
            f"verified={self.verified_found}"
        )


@dataclass
class BatchEnrichmentResult:
    """Summary of a batch enrichment run."""

    total: int = 0
    enriched: int = 0
    failed: int = 0
    results: list[EnrichmentResult] = field(default_factory=list)

    def summary(self) -> str:
        return f"total={self.total} enriched={self.enriched} failed={self.failed}"


class EnrichmentService:
    """Orchestrates the waterfall contact enrichment across providers."""

    def __init__(
        self,
        *,
        target_titles: list[str] | None = None,
    ) -> None:
        self._target_titles = target_titles or DEFAULT_TARGET_TITLES
        self._title_keywords = [t.lower() for t in self._target_titles]

        self._hunter: HunterClient | None = None
        self._scrapin: ScrapInClient | None = None
        self._llm: LLMService | None = None
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Lazily resolve API keys from the DB (set via Settings UI).

        Called once per service instance, before the first provider is used.
        This ensures Celery workers pick up keys updated at runtime.
        """
        if self._initialized:
            return
        self._initialized = True

        from app.core.app_settings_store import (
            DB_HUNTER_IO_API_KEY,
            DB_SCRAPIN_API_KEY,
            get_effective_secret,
        )

        hunter_key = await get_effective_secret(DB_HUNTER_IO_API_KEY, settings.hunter_io_api_key)
        if hunter_key:
            self._hunter = HunterClient(api_key=hunter_key)

        scrapin_key = await get_effective_secret(DB_SCRAPIN_API_KEY, settings.scrapin_api_key)
        if scrapin_key:
            self._scrapin = ScrapInClient(api_key=scrapin_key)

        try:
            self._llm = await create_llm_client()
        except ValueError:
            pass

    async def close(self) -> None:
        closers = [
            c.close()
            for c in (self._hunter, self._scrapin, self._llm)
            if c is not None
        ]
        await asyncio.gather(*closers, return_exceptions=True)

    # ── Public API ────────────────────────────────────────────────────

    async def enrich_company(
        self,
        company_id: int,
        session: AsyncSession,
    ) -> EnrichmentResult:
        """Run the contact waterfall for a single company."""
        await self._ensure_initialized()
        result = EnrichmentResult(company_id=company_id)

        company = await self._get_company(session, company_id)
        if company is None:
            result.error = "Company not found"
            return result

        if not company.domain:
            result.error = "Company has no domain"
            return result

        domain = company.domain
        log = logger.bind(company_id=company_id, domain=domain)
        log.info("contacts.start")

        start_time = time.monotonic()

        # Contact waterfall (sequential — stops on first verified contact)
        result = await self._run_contact_waterfall(
            company_id, domain, company, session, result, start_time,
        )

        log.info("contacts.done", summary=result.summary())
        return result

    async def _run_contact_waterfall(
        self,
        company_id: int,
        domain: str,
        company: Company,
        session: AsyncSession,
        result: EnrichmentResult,
        start_time: float,
    ) -> EnrichmentResult:
        """Run the contact provider waterfall sequentially."""
        log = logger.bind(company_id=company_id, domain=domain)

        def _remaining() -> float:
            return max(0.0, _ENRICHMENT_TIMEOUT_SECONDS - (time.monotonic() - start_time))

        providers: list[tuple[str, object]] = [
            ("hunter", self._hunter),
            ("scrapin", self._scrapin),
            ("scraped_content", self._llm),
        ]

        for provider_name, client in providers:
            if client is None:
                continue

            if _remaining() <= 0:
                log.warning(
                    "enrichment.timeout",
                    elapsed=round(time.monotonic() - start_time, 1),
                    providers_tried=result.providers_tried,
                )
                break

            result.providers_tried.append(provider_name)
            log.info("enrichment.trying_provider", provider=provider_name)

            try:
                contacts = await asyncio.wait_for(
                    self._try_provider(provider_name, domain, company),
                    timeout=_remaining(),
                )
            except TimeoutError:
                log.warning(
                    "enrichment.provider_timeout",
                    provider=provider_name,
                    elapsed=round(time.monotonic() - start_time, 1),
                )
                continue
            except APIError as exc:
                log.warning(
                    "enrichment.provider_error",
                    provider=provider_name,
                    error=str(exc),
                )
                continue
            except Exception as exc:
                log.warning(
                    "enrichment.provider_unexpected_error",
                    provider=provider_name,
                    error=str(exc),
                )
                continue

            if not contacts:
                log.info("enrichment.no_contacts", provider=provider_name)
                continue

            added = await self._store_contacts(session, company_id, contacts, provider_name)
            result.contacts_added += added
            result.provider_used = provider_name

            has_verified = any(
                c.email_status == EmailStatus.VERIFIED
                and c.title
                and self._title_matches(c.title)
                for c in contacts
            )
            if has_verified:
                result.verified_found = True
                log.info(
                    "enrichment.verified_found",
                    provider=provider_name,
                    contacts_added=added,
                )
                break

            log.info(
                "enrichment.contacts_found_no_verified",
                provider=provider_name,
                contacts_added=added,
            )

        return result

    async def enrich_batch(
        self,
        company_ids: list[int],
        session: AsyncSession | None = None,
    ) -> BatchEnrichmentResult:
        """Enrich multiple companies concurrently (up to 3 at a time)."""
        batch = BatchEnrichmentResult(total=len(company_ids))
        sem = asyncio.Semaphore(3)

        async def _enrich_one(cid: int) -> EnrichmentResult:
            async with sem, async_session_factory() as company_session:
                return await self.enrich_company(cid, company_session)

        results = await asyncio.gather(
            *[_enrich_one(cid) for cid in company_ids],
            return_exceptions=True,
        )

        for r in results:
            if isinstance(r, BaseException):
                batch.failed += 1
                batch.results.append(
                    EnrichmentResult(company_id=0, error=str(r))
                )
            else:
                batch.results.append(r)
                if r.error:
                    batch.failed += 1
                elif r.contacts_added > 0:
                    batch.enriched += 1

        return batch

    # ── Provider implementations ─────────────────────────────────────

    async def _try_provider(
        self,
        provider: str,
        domain: str,
        company: Company,
    ) -> list[Contact]:
        if provider == "hunter":
            return await self._try_hunter(domain)
        elif provider == "scrapin":
            return await self._try_scrapin(domain)
        elif provider == "scraped_content":
            return await self._try_scraped_content(domain, company)
        return []

    async def _try_hunter(self, domain: str) -> list[Contact]:
        """Hunter.io: domain search → filter by title → verify unverified emails."""
        assert self._hunter is not None
        response = await self._hunter.domain_search(domain)

        contacts: list[Contact] = []
        for email_result in response.results:
            if not email_result.value:
                continue

            # Filter by target title if position is known
            if email_result.position and not self._title_matches(email_result.position):
                continue

            # Determine email status
            email_status = EmailStatus.UNVERIFIED
            if email_result.confidence >= 90:
                # High confidence from Hunter ≈ verified
                email_status = EmailStatus.VERIFIED
            elif email_result.confidence >= 70:
                try:
                    verification = await self._hunter.verify_email(email_result.value)
                    if verification.status == VerificationStatus.DELIVERABLE:
                        email_status = EmailStatus.VERIFIED
                    elif verification.status == VerificationStatus.RISKY:
                        email_status = EmailStatus.CATCH_ALL
                except Exception:
                    pass

            contacts.append(
                Contact(
                    company_id=0,  # set later in _store_contacts
                    name=email_result.full_name or email_result.value.split("@")[0],
                    title=email_result.position,
                    email=email_result.value,
                    email_status=email_status,
                    phone=email_result.phone_number,
                    linkedin_url=email_result.linkedin,
                    source="hunter",
                    confidence_score=email_result.confidence / 100.0,
                )
            )
        return contacts

    async def _try_scrapin(self, domain: str) -> list[Contact]:
        """ScrapIn: find contacts by domain + title keywords."""
        assert self._scrapin is not None
        response = await self._scrapin.find_contacts(
            domain, title_keywords=self._target_titles
        )

        contacts: list[Contact] = []
        for sc in response.results:
            if not sc.display_name:
                continue

            contacts.append(
                Contact(
                    company_id=0,
                    name=sc.display_name,
                    title=sc.title,
                    email=sc.email,
                    email_status=EmailStatus.UNVERIFIED if sc.email else None,
                    phone=sc.phone,
                    linkedin_url=sc.linkedin_url,
                    source="scrapin",
                    confidence_score=sc.confidence,
                )
            )
        return contacts

    async def _try_scraped_content(self, domain: str, company: Company) -> list[Contact]:
        """Scraped-content fallback: extract contacts from already-scraped Signal data via LLM.

        This step never makes Firecrawl API calls — it only reads content
        previously stored in the Signal table by the separate scrape task.
        """
        assert self._llm is not None

        combined_content = await self._get_cached_content(
            domain, _TEAM_PATHS, company_id=company.id,
        )

        if not combined_content.strip():
            return []

        try:
            extracted = await self._llm.extract_contacts(combined_content)
        except Exception as exc:
            logger.warning("enrichment.scraped_content_llm_failed", error=str(exc))
            return []

        contacts: list[Contact] = []
        for ec in extracted:
            if not ec.name:
                continue
            # Only keep contacts matching target titles
            if ec.title and not self._title_matches(ec.title):
                continue

            contacts.append(
                Contact(
                    company_id=0,
                    name=ec.name,
                    title=ec.title,
                    email=ec.email,
                    email_status=EmailStatus.UNVERIFIED if ec.email else None,
                    phone=None,
                    linkedin_url=ec.linkedin_url,
                    source="scraped_content",
                    confidence_score=0.5,
                )
            )

        # Try to verify extracted emails via Hunter
        for contact in contacts:
            if contact.email and contact.email_status == EmailStatus.UNVERIFIED:
                contact.email_status = await self._verify_email(contact.email)

        return contacts

    async def _get_cached_content(
        self, domain: str, paths: list[str], company_id: int | None = None,
    ) -> str:
        """Return combined markdown from already-scraped Signal records.

        Only reads content previously stored by the separate scrape task.
        Never makes Firecrawl API calls, so this works even when scrape
        credits are exhausted.
        """
        if company_id is None:
            return ""

        urls = [f"https://{domain}{path}" for path in paths]

        cached: dict[str, str] = {}
        try:
            async with async_session_factory() as cache_session:
                result = await cache_session.execute(
                    select(Signal.source_url, Signal.raw_markdown).where(
                        Signal.company_id == company_id,
                        Signal.source_url.in_(urls),
                        Signal.raw_markdown.isnot(None),
                    )
                )
                for row in result:
                    if row.raw_markdown and len(row.raw_markdown.strip()) >= 50:
                        cached[row.source_url] = row.raw_markdown
        except Exception as exc:
            logger.warning(
                "enrichment.cache_lookup_failed",
                company_id=company_id,
                error=str(exc),
            )

        if cached:
            logger.info(
                "enrichment.using_cached_content",
                company_id=company_id,
                cached=len(cached),
            )

        combined = ""
        for url in urls:
            md = cached.get(url)
            if md:
                combined += f"\n\n--- {url} ---\n\n{md}"
        return combined

    # ── Helpers ───────────────────────────────────────────────────────

    def _title_matches(self, title: str) -> bool:
        """Check if a title matches any of the target title keywords."""
        title_lower = title.lower()
        return any(kw in title_lower for kw in self._title_keywords)

    async def _verify_email(self, email: str) -> EmailStatus:
        """Try to verify an email via Hunter."""
        if self._hunter:
            try:
                result = await self._hunter.verify_email(email)
                if result.status == VerificationStatus.DELIVERABLE:
                    return EmailStatus.VERIFIED
                if result.status == VerificationStatus.RISKY:
                    return EmailStatus.CATCH_ALL
            except Exception:
                pass

        return EmailStatus.UNVERIFIED

    async def _store_contacts(
        self,
        session: AsyncSession,
        company_id: int,
        contacts: list[Contact],
        source: str,
    ) -> int:
        """Store contacts, skipping duplicates (same email for same company)."""
        # Get existing emails for this company
        existing = await session.execute(
            select(Contact.email).where(
                Contact.company_id == company_id,
                Contact.email.isnot(None),
            )
        )
        existing_emails = {row[0].lower() for row in existing if row[0]}

        added = 0
        for contact in contacts:
            # Skip if email already exists for this company
            if contact.email and contact.email.lower() in existing_emails:
                continue

            contact.company_id = company_id
            session.add(contact)
            added += 1

            if contact.email:
                existing_emails.add(contact.email.lower())

        if added > 0:
            await session.commit()

        return added

    async def _get_company(
        self, session: AsyncSession, company_id: int
    ) -> Company | None:
        result = await session.execute(
            select(Company).where(Company.id == company_id)
        )
        return result.scalar_one_or_none()
