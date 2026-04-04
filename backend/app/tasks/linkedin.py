"""LinkedIn intelligence Celery tasks.

Priority-ranked daily rotation batch task that:
1. Picks the top N companies ordered by ICP score + staleness
2. Scrapes their LinkedIn pages via Apify
3. Creates Signal records for LLM analysis
4. The existing process-signal-queue task handles classification & Slack

High-ICP companies get scraped most frequently, new/never-scraped
companies bubble up immediately, and low-ICP companies still get
coverage on a longer cadence — all within a fixed daily budget.
"""

from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.sql.expression import case, extract, func

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import async_session_factory, run_async
from app.models.company import Company
from app.models.enums import CompanyStatus
from app.services.linkedin_intelligence import LinkedInIntelligenceService
from app.tasks.base import BaseTask, check_job_enabled

logger = structlog.get_logger(__name__)

# Priority scoring constants for the daily rotation query
_NEVER_SCRAPED_STALENESS_DAYS = 999.0
_ICP_SCORE_DIVISOR = 10.0


async def _get_apify_token() -> str:
    """Read Apify token from DB settings, fall back to env."""
    from app.core.app_settings_store import DB_APIFY_API_TOKEN, get_effective_secret

    return await get_effective_secret(DB_APIFY_API_TOKEN, settings.apify_api_token)


async def _get_linkedin_settings() -> tuple[int, int]:
    """Read days_back and daily_scrape_limit from DB, with defaults."""
    from app.core.app_settings_store import (
        DB_LINKEDIN_DAILY_SCRAPE_LIMIT,
        DB_LINKEDIN_DAYS_BACK,
        LINKEDIN_DEFAULT_DAILY_SCRAPE_LIMIT,
        LINKEDIN_DEFAULT_DAYS_BACK,
        get_setting,
    )

    async with async_session_factory() as session:
        days_back_raw = await get_setting(session, DB_LINKEDIN_DAYS_BACK)
        limit_raw = await get_setting(session, DB_LINKEDIN_DAILY_SCRAPE_LIMIT)

    days_back = int(days_back_raw) if days_back_raw else LINKEDIN_DEFAULT_DAYS_BACK
    daily_limit = int(limit_raw) if limit_raw else LINKEDIN_DEFAULT_DAILY_SCRAPE_LIMIT
    return days_back, daily_limit


async def _scrape_linkedin_single(company_id: int) -> str:
    """Async implementation for single-company LinkedIn scrape."""
    apify_token = await _get_apify_token()
    if not apify_token:
        return "linkedin_scrape: skipped — no Apify API token configured"

    days_back, _ = await _get_linkedin_settings()

    service = LinkedInIntelligenceService(apify_token=apify_token)
    try:
        async with async_session_factory() as session:
            result = await service.process_company(company_id, session, days_back=days_back)

            # Run inline signal analysis for immediate feedback
            if result.signal_ids:
                from app.services.intelligence import analyze_signal_ids_inline

                try:
                    await analyze_signal_ids_inline(result.signal_ids)
                except Exception:
                    logger.exception(
                        "linkedin.intelligence_failed",
                        company_id=company_id,
                        signal_count=len(result.signal_ids),
                    )

            return result.summary()
    finally:
        await service.close()


async def _scrape_linkedin_batch() -> str:
    """Priority-ranked daily rotation batch scrape.

    Instead of scraping all monitored companies on a fixed interval,
    pick the top N companies each day ordered by:
      1. ICP score (high-value first)
      2. Staleness (longest since last scrape, never-scraped first)

    This keeps the daily Apify budget fixed while ensuring high-ICP
    companies are scraped frequently and new companies are discovered.
    """
    from app.core.app_settings_store import (
        DB_LINKEDIN_LAST_BATCH_RUN,
        set_setting,
    )

    days_back, daily_limit = await _get_linkedin_settings()

    apify_token = await _get_apify_token()
    if not apify_token:
        return "linkedin_batch: skipped — no Apify API token configured"

    # Select top N companies by weighted priority score:
    #   priority = staleness_days + (icp_score / 10)
    #
    # This means a company with ICP 100 scraped 1 day ago (priority 11)
    # beats a company with ICP 0 scraped 10 days ago (priority 10).
    # Never-scraped companies get staleness=999, so they always go first
    # (with higher ICP winning among never-scraped).
    staleness_days = case(
        (Company.linkedin_last_scraped_at.is_(None), _NEVER_SCRAPED_STALENESS_DAYS),
        else_=extract("epoch", func.now() - Company.linkedin_last_scraped_at) / 86400.0,
    )
    icp_bonus = case(
        (Company.icp_score.is_(None), 0.0),
        else_=Company.icp_score / _ICP_SCORE_DIVISOR,
    )
    priority_score = staleness_days + icp_bonus

    async with async_session_factory() as session:
        query = (
            select(Company.id)
            .where(
                Company.linkedin_url.isnot(None),
                Company.status != CompanyStatus.ARCHIVED,
            )
            .order_by(priority_score.desc())
            .limit(daily_limit)
        )
        result = await session.execute(query)
        company_ids = list(result.scalars().all())

    if not company_ids:
        return "linkedin_batch: no companies with LinkedIn URLs to scrape"

    logger.info(
        "linkedin.batch.start",
        count=len(company_ids),
        daily_limit=daily_limit,
        days_back=days_back,
    )

    service = LinkedInIntelligenceService(apify_token=apify_token)
    all_signal_ids: list[int] = []
    try:
        async with async_session_factory() as session:
            results = await service.process_batch(company_ids, session, days_back=days_back)
            for r in results:
                all_signal_ids.extend(r.signal_ids)

        # Run inline signal analysis for all new signals
        if all_signal_ids:
            from app.services.intelligence import analyze_signal_ids_inline

            try:
                await analyze_signal_ids_inline(all_signal_ids)
            except Exception:
                logger.exception(
                    "linkedin.batch.intelligence_failed",
                    signal_count=len(all_signal_ids),
                )

        total_signals = sum(r.signals_created for r in results)
        errors = sum(1 for r in results if r.error)
        summary = f"companies={len(results)} signals={total_signals} errors={errors} daily_limit={daily_limit}"
        logger.info("linkedin.batch.done", summary=summary)

        # Record successful run timestamp
        async with async_session_factory() as session:
            await set_setting(
                session, DB_LINKEDIN_LAST_BATCH_RUN, datetime.now(UTC).isoformat()
            )

        return f"linkedin_batch: {summary}"
    finally:
        await service.close()


@celery_app.task(
    base=BaseTask,
    name="app.tasks.linkedin.scrape_company_linkedin",
    acks_late=True,
    time_limit=300,
    soft_time_limit=240,
)
def scrape_company_linkedin(company_id: int) -> str:
    """Scrape a single company's LinkedIn page via Apify.

    Triggered manually via API endpoint.
    """
    result = run_async(_scrape_linkedin_single(company_id))

    from app.tasks.lead_scoring import recalculate_company_score

    recalculate_company_score.delay(company_id)

    return result


@celery_app.task(
    base=BaseTask,
    name="app.tasks.linkedin.scrape_company_linkedin_safe",
    acks_late=True,
    time_limit=300,
    soft_time_limit=240,
)
def scrape_company_linkedin_safe(company_id: int) -> str:
    """Pipeline-safe LinkedIn scrape: never raises, never triggers score recalc.

    Used inside the pipeline chain so a LinkedIn failure cannot prevent
    the subsequent enrich and contacts steps from running.
    """
    try:
        return run_async(_scrape_linkedin_single(company_id))
    except Exception:
        logger.exception("linkedin.pipeline_safe_failed", company_id=company_id)
        return f"linkedin_scrape: failed (non-fatal) for company {company_id}"


@celery_app.task(
    base=BaseTask,
    name="app.tasks.linkedin.scrape_linkedin_batch",
    acks_late=True,
    time_limit=7260,  # 121 min hard kill
    soft_time_limit=7200,  # 120 min soft limit
)
def scrape_linkedin_batch() -> str:
    """Priority-ranked daily LinkedIn batch scrape.

    Runs daily via Celery Beat. Picks the top N companies (daily_scrape_limit,
    default 50) ordered by staleness and ICP score. High-ICP companies get
    scraped most frequently; new/never-scraped companies bubble up immediately.
    """
    if not check_job_enabled("scrape-linkedin-batch"):
        return "scrape-linkedin-batch: skipped — job disabled"
    return run_async(_scrape_linkedin_batch())
