"""Contact finding Celery task.

Finds decision-maker contacts for a company using the waterfall strategy:
Hunter.io → ScrapIn → LLM extraction from already-scraped Signal data.

Never scrapes websites directly.
"""

import structlog
from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import async_session_factory, run_async
from app.core.utils import utcnow
from app.models.enrichment_job import EnrichmentJob
from app.models.enums import EnrichmentJobStatus
from app.services.enrichment import EnrichmentService
from app.tasks.base import BaseTask

logger = structlog.get_logger(__name__)


async def _find_contacts(company_id: int, job_id: int | None = None) -> str:
    """Async implementation for contact finding."""

    async def _update_job(
        status: EnrichmentJobStatus,
        summary: str | None = None,
        error: str | None = None,
    ) -> None:
        if job_id is None:
            return
        async with async_session_factory() as session:
            job = (
                await session.execute(select(EnrichmentJob).where(EnrichmentJob.id == job_id))
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
    service = EnrichmentService()
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


@celery_app.task(
    base=BaseTask,
    name="app.tasks.contacts.find_company_contacts",
    acks_late=True,
    time_limit=360,
    soft_time_limit=300,
)
def find_company_contacts(company_id: int, job_id: int | None = None) -> str:
    """Find decision-maker contacts for a company using the waterfall strategy.

    Tries Hunter.io, ScrapIn, and LLM extraction from
    already-scraped Signal data. Never scrapes websites.
    """
    result = run_async(_find_contacts(company_id, job_id))

    from app.tasks.lead_scoring import recalculate_company_score

    recalculate_company_score.delay(company_id)  # type: ignore[attr-defined]

    return result
