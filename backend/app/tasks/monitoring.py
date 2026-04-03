"""Signal monitoring Celery tasks.

Provides three tasks:

- ``monitor_company_task``: Monitor a single company (manual trigger).
- ``monitor_high_priority``: Batch monitor high-priority companies (every 4h).
- ``monitor_standard``: Batch monitor standard-priority companies (daily 06:00 UTC).
"""


import structlog
from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import async_session_factory, run_async
from app.models.company import Company
from app.models.enums import CompanyStatus
from app.services.signal_monitor import SignalMonitorService
from app.tasks.base import BaseTask, check_job_enabled

logger = structlog.get_logger(__name__)

_HIGH_PRIORITY_SCORE_THRESHOLD = 50.0
_HIGH_PRIORITY_STATUSES = {CompanyStatus.QUALIFIED, CompanyStatus.MONITORING}
_STANDARD_STATUSES = {CompanyStatus.DISCOVERED, CompanyStatus.ENRICHED}


async def _monitor_single(company_id: int) -> str:
    """Async implementation for single-company monitoring."""
    from app.core.app_settings_store import DB_FIRECRAWL_API_KEY, get_effective_secret
    firecrawl_key = await get_effective_secret(DB_FIRECRAWL_API_KEY, settings.firecrawl_api_key)
    service = SignalMonitorService(firecrawl_api_key=firecrawl_key)
    try:
        async with async_session_factory() as session:
            result = await service.monitor_company(company_id, session)
            return result.summary()
    finally:
        await service.close()


async def _monitor_high_priority() -> str:
    """Async implementation for high-priority batch monitoring."""
    async with async_session_factory() as session:
        query = (
            select(Company.id)
            .where(Company.status != CompanyStatus.ARCHIVED)
            .where(
                (Company.status.in_(_HIGH_PRIORITY_STATUSES))
                | (Company.icp_score >= _HIGH_PRIORITY_SCORE_THRESHOLD)
            )
        )
        result = await session.execute(query)
        company_ids = list(result.scalars().all())

    if not company_ids:
        return "no high-priority companies to monitor"

    # Cap to prevent runaway Firecrawl credit usage
    cap = settings.max_monitoring_companies_per_run
    if cap > 0 and len(company_ids) > cap:
        logger.warning(
            "monitor.high_priority.capped",
            total=len(company_ids),
            cap=cap,
        )
        company_ids = company_ids[:cap]

    logger.info("monitor.high_priority.start", count=len(company_ids))

    from app.core.app_settings_store import DB_FIRECRAWL_API_KEY, get_effective_secret
    firecrawl_key = await get_effective_secret(DB_FIRECRAWL_API_KEY, settings.firecrawl_api_key)
    service = SignalMonitorService(firecrawl_api_key=firecrawl_key)
    try:
        async with async_session_factory() as session:
            batch_result = await service.monitor_batch(company_ids, session)
            summary = batch_result.summary()
            logger.info("monitor.high_priority.done", summary=summary)
            return f"high_priority: {summary}"
    finally:
        await service.close()


async def _monitor_standard() -> str:
    """Async implementation for standard batch monitoring."""
    async with async_session_factory() as session:
        query = (
            select(Company.id)
            .where(Company.status.in_(_STANDARD_STATUSES))
            .where(
                (Company.icp_score.is_(None))
                | (Company.icp_score < _HIGH_PRIORITY_SCORE_THRESHOLD)
            )
        )
        result = await session.execute(query)
        company_ids = list(result.scalars().all())

    if not company_ids:
        return "no standard companies to monitor"

    # Cap to prevent runaway Firecrawl credit usage
    cap = settings.max_monitoring_companies_per_run
    if cap > 0 and len(company_ids) > cap:
        logger.warning(
            "monitor.standard.capped",
            total=len(company_ids),
            cap=cap,
        )
        company_ids = company_ids[:cap]

    logger.info("monitor.standard.start", count=len(company_ids))

    from app.core.app_settings_store import DB_FIRECRAWL_API_KEY, get_effective_secret
    firecrawl_key = await get_effective_secret(DB_FIRECRAWL_API_KEY, settings.firecrawl_api_key)
    service = SignalMonitorService(firecrawl_api_key=firecrawl_key)
    try:
        async with async_session_factory() as session:
            batch_result = await service.monitor_batch(company_ids, session)
            summary = batch_result.summary()
            logger.info("monitor.standard.done", summary=summary)
            return f"standard: {summary}"
    finally:
        await service.close()


@celery_app.task(
    base=BaseTask,
    name="app.tasks.monitoring.monitor_company_task",
    acks_late=True,
    time_limit=360,       # 6 min hard kill (5 min runtime guard + buffer)
    soft_time_limit=300,  # 5 min soft limit
)
def monitor_company_task(company_id: int) -> str:
    """LP-023: Monitor a single company for signal changes.

    Scrapes configured pages via Firecrawl, detects content changes via
    SHA-256 hashing, and creates unprocessed Signal records for the LLM
    pipeline to pick up.

    Triggered manually via ``POST /api/v1/companies/{id}/monitor``.
    """
    result = run_async(_monitor_single(company_id))

    # Trigger lead score recalculation after new signals may have been created
    from app.tasks.lead_scoring import recalculate_company_score

    recalculate_company_score.delay(company_id)

    return result


@celery_app.task(
    base=BaseTask,
    name="app.tasks.monitoring.monitor_high_priority",
    acks_late=True,
    time_limit=3660,       # 61 min hard kill
    soft_time_limit=3600,  # 60 min soft limit
)
def monitor_high_priority() -> str:
    """LP-023: Monitor high-priority companies (qualified / score >= 50).

    Scheduled every 4 hours via Celery Beat. Scrapes all configured pages
    for companies with status 'qualified'/'monitoring' or ICP score >= 50.
    """
    if not check_job_enabled("monitor-high-priority"):
        return "monitor-high-priority: skipped — job disabled"
    return run_async(_monitor_high_priority())


@celery_app.task(
    base=BaseTask,
    name="app.tasks.monitoring.monitor_standard",
    acks_late=True,
    time_limit=7260,       # 121 min hard kill
    soft_time_limit=7200,  # 120 min soft limit
)
def monitor_standard() -> str:
    """LP-023: Daily monitoring for standard-priority companies.

    Scheduled daily at 06:00 UTC via Celery Beat. Processes companies
    with status 'discovered'/'enriched' and ICP score < 50.
    """
    if not check_job_enabled("monitor-standard"):
        return "monitor-standard: skipped — job disabled"
    return run_async(_monitor_standard())
