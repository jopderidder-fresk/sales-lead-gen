"""LLM enrichment Celery tasks.

Provides tasks for LLM-based company enrichment:

- ``enrich_company``: Enrich a single company (generate profile + analyze signals).
- ``enrich_all_discovered``: Batch enrich all companies with status "discovered".
- ``cleanup_stale_jobs``: Mark lost/timed-out enrichment and scrape jobs as FAILED.
"""

import asyncio
from datetime import timedelta

import structlog
from sqlalchemy import func, select

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import async_session_factory, run_async
from app.core.utils import today_start_utc, utcnow
from app.models.company import Company
from app.models.enrichment_job import EnrichmentJob
from app.models.enums import CompanyStatus, EnrichmentJobStatus, ScrapeJobStatus
from app.models.scrape_job import ScrapeJob
from app.services.company_enrichment import CompanyEnrichmentService
from app.tasks.base import BaseTask, check_job_enabled

logger = structlog.get_logger(__name__)

# Jobs stuck in PENDING longer than this had their Celery task lost (e.g. worker restart).
_PENDING_STALE_AFTER = timedelta(minutes=10)
# Jobs stuck in RUNNING longer than this exceeded the task time_limit (360 s) plus a buffer.
_RUNNING_STALE_AFTER = timedelta(seconds=420)


async def _enrich_single(company_id: int, job_id: int | None = None) -> str:
    """Async implementation for single-company LLM enrichment."""

    async def _update_job(
        status: EnrichmentJobStatus,
        summary: str | None = None,
        error: str | None = None,
    ) -> None:
        if job_id is None:
            return
        async with async_session_factory() as session:
            job = (
                await session.execute(
                    select(EnrichmentJob).where(EnrichmentJob.id == job_id)
                )
            ).scalar_one_or_none()
            if job is None:
                return
            job.status = status
            if status == EnrichmentJobStatus.RUNNING:
                job.started_at = utcnow()
            else:
                job.completed_at = utcnow()
            if summary is not None:
                job.result_summary = summary[:500]
            if error is not None:
                job.error_message = error[:500]
            await session.commit()

    await _update_job(EnrichmentJobStatus.RUNNING)
    service = CompanyEnrichmentService()
    try:
        async with async_session_factory() as session:
            result = await service.enrich_company(company_id, session)
            summary = result.summary()
        await _update_job(EnrichmentJobStatus.COMPLETED, summary=summary)
        return summary
    except Exception as exc:
        await _update_job(EnrichmentJobStatus.FAILED, error=str(exc))
        raise
    finally:
        await service.close()


async def _enrich_all_discovered() -> str:
    """Async implementation for batch LLM enrichment of discovered companies."""
    async with async_session_factory() as session:
        enrichments_today = (
            await session.execute(
                select(func.count()).select_from(EnrichmentJob).where(
                    EnrichmentJob.created_at >= today_start_utc(),
                )
            )
        ).scalar_one()

        remaining_budget = max(0, settings.max_enrichments_per_day - enrichments_today)
        if remaining_budget == 0:
            logger.info("enrichment.batch.daily_limit_reached", limit=settings.max_enrichments_per_day)
            return f"daily enrichment limit reached ({settings.max_enrichments_per_day}/day)"

        query = select(Company.id).where(Company.status == CompanyStatus.DISCOVERED)
        result = await session.execute(query)
        company_ids = list(result.scalars().all())

    if not company_ids:
        return "no discovered companies to enrich"

    if len(company_ids) > remaining_budget:
        logger.info(
            "enrichment.batch.capped",
            found=len(company_ids),
            budget=remaining_budget,
        )
        company_ids = company_ids[:remaining_budget]

    logger.info("enrichment.batch.start", count=len(company_ids))

    enriched = 0
    failed = 0
    sem = asyncio.Semaphore(3)

    async def _enrich_one(cid: int) -> bool:
        async with sem:
            service = CompanyEnrichmentService()
            try:
                async with async_session_factory() as session:
                    await service.enrich_company(cid, session)
                return True
            except Exception as exc:
                logger.warning("enrichment.batch.company_failed", company_id=cid, error=str(exc))
                return False
            finally:
                await service.close()

    results = await asyncio.gather(
        *[_enrich_one(cid) for cid in company_ids],
        return_exceptions=True,
    )

    for r in results:
        if isinstance(r, BaseException) or r is False:
            failed += 1
        else:
            enriched += 1

    summary = f"total={len(company_ids)} enriched={enriched} failed={failed}"
    logger.info("enrichment.batch.done", summary=summary)
    return f"batch: {summary}"


@celery_app.task(
    base=BaseTask,
    name="app.tasks.enrichment.enrich_company",
    acks_late=True,
    time_limit=360,
    soft_time_limit=300,
)
def enrich_company(company_id: int, job_id: int | None = None) -> str:
    """LLM enrichment: generate company profile + analyze signals.

    Uses existing scraped content from Signal records. Never scrapes.
    Triggered manually via ``POST /api/v1/companies/{id}/enrich``.
    """
    result = run_async(_enrich_single(company_id, job_id))

    from app.tasks.lead_scoring import recalculate_company_score

    recalculate_company_score.delay(company_id)

    return result


@celery_app.task(
    base=BaseTask,
    name="app.tasks.enrichment.enrich_all_discovered",
    acks_late=True,
    time_limit=3660,
    soft_time_limit=3600,
)
def enrich_all_discovered() -> str:
    """Batch LLM enrichment for all companies with status 'discovered'.

    Scheduled daily at 04:00 UTC via Celery Beat.
    """
    if not check_job_enabled("enrich-all-discovered"):
        return "enrich-all-discovered: skipped — job disabled"
    return run_async(_enrich_all_discovered())


# ── Stale job cleanup ─────────────────────────────────────────────────────


async def _cleanup_stale_jobs() -> str:
    """Mark lost PENDING and timed-out RUNNING enrichment/scrape jobs as FAILED."""
    now = utcnow()
    pending_cutoff = now - _PENDING_STALE_AFTER
    running_cutoff = now - _RUNNING_STALE_AFTER

    enrichment_failed = 0
    scrape_failed = 0

    async with async_session_factory() as session:
        stale = (await session.execute(
            select(EnrichmentJob).where(
                EnrichmentJob.status == EnrichmentJobStatus.PENDING,
                EnrichmentJob.created_at < pending_cutoff,
            )
        )).scalars().all()
        for job in stale:
            job.status = EnrichmentJobStatus.FAILED
            job.error_message = "Task lost: worker restart or queue overflow"
            job.completed_at = now
            enrichment_failed += 1

        timed_out = (await session.execute(
            select(EnrichmentJob).where(
                EnrichmentJob.status == EnrichmentJobStatus.RUNNING,
                EnrichmentJob.started_at < running_cutoff,
            )
        )).scalars().all()
        for job in timed_out:
            job.status = EnrichmentJobStatus.FAILED
            job.error_message = "Task timed out: no completion recorded within expected window"
            job.completed_at = now
            enrichment_failed += 1

        stale_scrape = (await session.execute(
            select(ScrapeJob).where(
                ScrapeJob.status == ScrapeJobStatus.PENDING,
                ScrapeJob.created_at < pending_cutoff,
            )
        )).scalars().all()
        for scrape_job in stale_scrape:
            scrape_job.status = ScrapeJobStatus.FAILED
            scrape_job.error_message = "Task lost: worker restart or queue overflow"
            scrape_job.completed_at = now
            scrape_failed += 1

        timed_out_scrape = (await session.execute(
            select(ScrapeJob).where(
                ScrapeJob.status == ScrapeJobStatus.RUNNING,
                ScrapeJob.started_at < running_cutoff,
            )
        )).scalars().all()
        for scrape_job in timed_out_scrape:
            scrape_job.status = ScrapeJobStatus.FAILED
            scrape_job.error_message = "Task timed out: no completion recorded within expected window"
            scrape_job.completed_at = now
            scrape_failed += 1

        await session.commit()

    total = enrichment_failed + scrape_failed
    if total == 0:
        return "no stale jobs"

    logger.warning(
        "cleanup.stale_jobs",
        enrichment_failed=enrichment_failed,
        scrape_failed=scrape_failed,
    )
    return f"marked stale: enrichment={enrichment_failed} scrape={scrape_failed}"


@celery_app.task(
    base=BaseTask,
    name="app.tasks.enrichment.cleanup_stale_jobs",
    acks_late=True,
    time_limit=60,
    soft_time_limit=55,
)
def cleanup_stale_jobs() -> str:
    """Periodically mark lost PENDING and timed-out RUNNING jobs as FAILED.

    Scheduled every 5 minutes via Celery Beat.
    """
    if not check_job_enabled("cleanup-stale-jobs"):
        return "cleanup-stale-jobs: skipped — job disabled"
    return run_async(_cleanup_stale_jobs())
