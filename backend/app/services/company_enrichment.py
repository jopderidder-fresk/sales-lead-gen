"""LLM-based company enrichment service.

Generates company profiles and analyzes signals using existing scraped
content stored in Signal records. Never makes Firecrawl API calls.

Two main responsibilities:
1. Generate ``company.company_info`` via ``LLMService.generate_company_profile()``
2. Analyze unprocessed signals via ``IntelligenceService`` (classify, score, map action)
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.company import Company
from app.models.enums import CompanyStatus
from app.models.signal import Signal
from app.services.llm import LLMService, create_llm_client

logger = structlog.get_logger(__name__)

# Paths to look up cached content for company profile generation
_COMPANY_INFO_PATHS = ["/", "/about", "/products", "/services"]


@dataclass
class CompanyEnrichmentResult:
    """Summary of a single-company LLM enrichment run."""

    company_id: int
    company_info_generated: bool = False
    signals_analyzed: int = 0
    signals_total: int = 0
    error: str | None = None

    def summary(self) -> str:
        if self.error:
            return f"company={self.company_id} error={self.error}"
        return (
            f"company={self.company_id} "
            f"company_info={'generated' if self.company_info_generated else 'skipped'} "
            f"signals_analyzed={self.signals_analyzed}/{self.signals_total}"
        )


class CompanyEnrichmentService:
    """Enriches companies using LLM analysis of already-scraped content."""

    def __init__(self) -> None:
        self._llm: LLMService | None = None
        self._llm_initialized = False

    async def _ensure_llm(self) -> None:
        """Lazily create the LLM client (reads keys from DB at runtime)."""
        if self._llm_initialized:
            return
        self._llm_initialized = True
        try:
            self._llm = await create_llm_client()
        except ValueError:
            pass

    async def close(self) -> None:
        if self._llm is not None:
            await self._llm.close()

    async def enrich_company(
        self,
        company_id: int,
        session: AsyncSession,
    ) -> CompanyEnrichmentResult:
        """Run LLM enrichment for a single company.

        1. Generate company_info from scraped content (if not already present)
        2. Analyze all unprocessed signals for this company
        3. Set company status to ENRICHED
        """
        result = CompanyEnrichmentResult(company_id=company_id)

        company = (
            await session.execute(select(Company).where(Company.id == company_id))
        ).scalar_one_or_none()

        if company is None:
            result.error = "Company not found"
            return result

        log = logger.bind(company_id=company_id, domain=company.domain)
        log.info("company_enrichment.start")

        await self._ensure_llm()

        # Step 1: Generate company_info if not already present
        if not company.company_info and self._llm is not None:
            try:
                result.company_info_generated = await self._generate_company_info(company, session)
            except Exception as exc:
                log.warning("company_enrichment.company_info_failed", error=str(exc))

        # Step 2: Analyze unprocessed signals for this company
        unprocessed_signal_ids = list(
            (
                await session.execute(
                    select(Signal.id).where(
                        Signal.company_id == company_id,
                        Signal.is_processed.is_(False),
                        Signal.raw_markdown.isnot(None),
                    )
                )
            ).scalars().all()
        )
        result.signals_total = len(unprocessed_signal_ids)

        if unprocessed_signal_ids:
            from app.services.intelligence import analyze_signal_ids_inline

            try:
                await analyze_signal_ids_inline(unprocessed_signal_ids)
                result.signals_analyzed = len(unprocessed_signal_ids)
            except Exception as exc:
                log.warning(
                    "company_enrichment.signal_analysis_failed",
                    error=str(exc),
                    signal_count=len(unprocessed_signal_ids),
                )

        # Step 3: Set company status to ENRICHED
        # Refresh to pick up any changes from signal analysis
        await session.refresh(company)
        if company.status == CompanyStatus.DISCOVERED:
            company.status = CompanyStatus.ENRICHED
            await session.commit()

        log.info("company_enrichment.done", summary=result.summary())
        return result

    async def _generate_company_info(
        self,
        company: Company,
        session: AsyncSession,
    ) -> bool:
        """Generate an LLM company profile from already-scraped content.

        Returns True if a profile was actually generated, False otherwise.
        """
        if self._llm is None:
            return False

        if company.company_info:
            return False

        log = logger.bind(company_id=company.id, domain=company.domain)

        combined_content = await self._get_cached_content(
            company.domain, company_id=company.id,
        )

        if not combined_content.strip():
            log.warning("company_enrichment.no_content")
            return False

        profile = await self._llm.generate_company_profile(combined_content)
        company.company_info = profile.model_dump()
        await session.commit()
        log.info("company_enrichment.company_info_generated")
        return True

    async def _get_cached_content(
        self, domain: str, company_id: int,
    ) -> str:
        """Return combined markdown from already-scraped Signal records.

        Only reads content previously stored by the scrape task.
        Never makes Firecrawl API calls.
        """
        urls = [f"https://{domain}{path}" for path in _COMPANY_INFO_PATHS]

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
                "company_enrichment.cache_lookup_failed",
                company_id=company_id,
                error=str(exc),
            )

        if cached:
            logger.info(
                "company_enrichment.using_cached_content",
                company_id=company_id,
                cached=len(cached),
            )

        combined = ""
        for url in urls:
            md = cached.get(url)
            if md:
                combined += f"\n\n--- {url} ---\n\n{md}"
        return combined
