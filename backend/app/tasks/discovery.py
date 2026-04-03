"""Company discovery Celery task.

Creates/updates DiscoveryJob records to track run progress and results.
"""

import structlog
from sqlalchemy import func, select, update

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import async_session_factory, run_async
from app.core.utils import today_start_utc, utcnow
from app.models.discovery_job import DiscoveryJob
from app.models.enums import DiscoveryJobStatus
from app.services.discovery import DiscoveryService
from app.tasks.base import BaseTask, check_job_enabled

logger = structlog.get_logger(__name__)


async def _run_discovery(job_id: int | None = None) -> str:
    """Async implementation for the discovery task."""
    # Enforce daily discovery run limit (also checked in the API trigger,
    # but the scheduled beat task bypasses the API).
    async with async_session_factory() as limit_session:
        runs_today = (
            await limit_session.execute(
                select(func.count()).select_from(DiscoveryJob).where(
                    DiscoveryJob.created_at >= today_start_utc(),
                )
            )
        ).scalar_one()
        if runs_today >= settings.max_discovery_runs_per_day:
            logger.warning(
                "discovery.daily_limit_reached",
                limit=settings.max_discovery_runs_per_day,
                runs_today=runs_today,
            )
            return f"daily discovery limit reached ({settings.max_discovery_runs_per_day}/day)"

    service = DiscoveryService(
        bedrijfsdata_api_key=settings.bedrijfsdata_api_key,
        max_companies=settings.max_companies_per_discovery_run,
    )
    try:
        async with async_session_factory() as session:
            job: DiscoveryJob | None = None

            if job_id:
                result = await session.execute(
                    select(DiscoveryJob).where(DiscoveryJob.id == job_id)
                )
                job = result.scalar_one_or_none()

            if job is None:
                job = DiscoveryJob(
                    status=DiscoveryJobStatus.PENDING,
                    trigger="scheduled",
                )
                session.add(job)
                await session.commit()
                await session.refresh(job)

            job.status = DiscoveryJobStatus.RUNNING
            job.started_at = utcnow()
            await session.commit()

            try:
                discovery_result = await service.run(session)

                # Use a direct SQL UPDATE to bypass ORM change-detection
                # which can get stale after the intermediate session.commit()
                # calls inside the discovery service processing methods.
                error_message = (
                    "; ".join(discovery_result.errors)
                    if discovery_result.errors
                    else None
                )
                await session.execute(
                    update(DiscoveryJob)
                    .where(DiscoveryJob.id == job.id)
                    .values(
                        status=DiscoveryJobStatus.COMPLETED,
                        completed_at=utcnow(),
                        companies_found=discovery_result.companies_found,
                        companies_added=discovery_result.companies_added,
                        companies_skipped=discovery_result.companies_skipped,
                        results={
                            "firecrawl_found": discovery_result.firecrawl_found,
                            "bedrijfsdata_found": discovery_result.bedrijfsdata_found,
                            "elapsed_seconds": discovery_result.elapsed_seconds,
                            "errors": discovery_result.errors,
                        },
                        error_message=error_message,
                    )
                )
                await session.commit()
                return discovery_result.summary()

            except Exception as exc:
                await session.execute(
                    update(DiscoveryJob)
                    .where(DiscoveryJob.id == job.id)
                    .values(
                        status=DiscoveryJobStatus.FAILED,
                        completed_at=utcnow(),
                        error_message=str(exc),
                    )
                )
                await session.commit()
                raise
    finally:
        await service.close()


@celery_app.task(
    base=BaseTask,
    name="app.tasks.discovery.discover_companies",
    acks_late=True,
    time_limit=1860,
    soft_time_limit=1800,
)
def discover_companies(job_id: int | None = None) -> str:
    """LP-015: Daily company discovery via Bedrijfsdata.

    Reads the active ICP profile, queries Bedrijfsdata,
    deduplicates results, and stores new companies with status "discovered".

    Scheduled daily at 02:00 UTC via Celery Beat.
    Can also be triggered manually via ``POST /api/v1/discovery/run``.
    """
    if job_id is None and not check_job_enabled("discover-companies"):
        return "discover-companies: skipped — job disabled"
    return run_async(_run_discovery(job_id))
