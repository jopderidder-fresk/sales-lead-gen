"""LinkedIn intelligence Celery tasks.

Batch task that:
1. Checks interval setting to decide whether to run
2. Finds companies with linkedin_url set
3. Scrapes their LinkedIn pages via Apify
4. Creates Signal records for LLM analysis
5. The existing process-signal-queue task handles classification & Slack
"""

from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import async_session_factory, run_async
from app.models.company import Company
from app.models.enums import CompanyStatus
from app.services.linkedin_intelligence import LinkedInIntelligenceService
from app.tasks.base import BaseTask, check_job_enabled

logger = structlog.get_logger(__name__)

_DEFAULT_INTERVAL_DAYS = 7
_DEFAULT_DAYS_BACK = 7


async def _get_apify_token() -> str:
    """Read Apify token from DB settings, fall back to env."""
    from app.core.app_settings_store import DB_APIFY_API_TOKEN, get_effective_secret

    return await get_effective_secret(DB_APIFY_API_TOKEN, settings.apify_api_token)


async def _get_linkedin_settings() -> tuple[int, int]:
    """Read interval_days and days_back from DB, with defaults."""
    from app.core.app_settings_store import (
        DB_LINKEDIN_DAYS_BACK,
        DB_LINKEDIN_INTERVAL_DAYS,
        get_setting,
    )

    async with async_session_factory() as session:
        interval_raw = await get_setting(session, DB_LINKEDIN_INTERVAL_DAYS)
        days_back_raw = await get_setting(session, DB_LINKEDIN_DAYS_BACK)

    interval_days = int(interval_raw) if interval_raw else _DEFAULT_INTERVAL_DAYS
    days_back = int(days_back_raw) if days_back_raw else _DEFAULT_DAYS_BACK
    return interval_days, days_back


async def _scrape_linkedin_single(company_id: int) -> str:
    """Async implementation for single-company LinkedIn scrape."""
    apify_token = await _get_apify_token()
    if not apify_token:
        return "linkedin_scrape: skipped — no Apify API token configured"

    _, days_back = await _get_linkedin_settings()

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
    """Async implementation for LinkedIn batch scrape with dynamic settings."""
    from app.core.app_settings_store import (
        DB_LINKEDIN_LAST_BATCH_RUN,
        get_setting,
        set_setting,
    )

    # Read dynamic settings
    interval_days, days_back = await _get_linkedin_settings()

    # Check if enough time has passed since last run
    async with async_session_factory() as session:
        last_run_raw = await get_setting(session, DB_LINKEDIN_LAST_BATCH_RUN)

    if last_run_raw:
        last_run = datetime.fromisoformat(last_run_raw)
        elapsed = datetime.now(UTC) - last_run
        if elapsed.total_seconds() < (interval_days - 0.5) * 86400:
            return (
                f"linkedin_batch: skipped — last ran {elapsed.days}d ago, "
                f"interval is {interval_days}d"
            )

    apify_token = await _get_apify_token()
    if not apify_token:
        return "linkedin_batch: skipped — no Apify API token configured"

    # Find companies with LinkedIn URLs that aren't archived
    async with async_session_factory() as session:
        query = select(Company.id).where(
            Company.linkedin_url.isnot(None),
            Company.status != CompanyStatus.ARCHIVED,
        )
        result = await session.execute(query)
        company_ids = list(result.scalars().all())

    if not company_ids:
        return "linkedin_batch: no companies with LinkedIn URLs to scrape"

    logger.info("linkedin.batch.start", count=len(company_ids), days_back=days_back)

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
        summary = f"companies={len(results)} signals={total_signals} errors={errors}"
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
    name="app.tasks.linkedin.scrape_linkedin_batch",
    acks_late=True,
    time_limit=7260,  # 121 min hard kill
    soft_time_limit=7200,  # 120 min soft limit
)
def scrape_linkedin_batch() -> str:
    """LinkedIn batch scrape for all companies with LinkedIn URLs.

    Scheduled daily via Celery Beat; self-throttles based on
    linkedin.interval_days setting (default: every 7 days).
    """
    if not check_job_enabled("scrape-linkedin-batch"):
        return "scrape-linkedin-batch: skipped — job disabled"
    return run_async(_scrape_linkedin_batch())
