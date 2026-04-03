"""Lead scoring Celery tasks.

Provides tasks for single-company and batch lead score recalculation.
Replaces the placeholder ``recalculate_all_scores`` task.
"""


import structlog

from app.core.celery_app import celery_app
from app.core.database import async_session_factory, run_async
from app.services.lead_scoring import LeadScoringService
from app.tasks.base import BaseTask, check_job_enabled

logger = structlog.get_logger(__name__)


async def _recalculate_company(company_id: int) -> str:
    """Async implementation for single-company score recalculation."""
    service = LeadScoringService()
    async with async_session_factory() as session:
        result = await service.score_company(company_id, session)
        if result is None:
            return f"company {company_id}: not found"
        return f"company {company_id}: score={result['lead_score']}"


async def _recalculate_all() -> str:
    """Async implementation for batch recalculation."""
    service = LeadScoringService()
    async with async_session_factory() as session:
        scored = await service.score_all(session)
        return f"recalculated {scored} company score(s)"


@celery_app.task(
    base=BaseTask,
    name="app.tasks.lead_scoring.recalculate_company_score",
    acks_late=True,
)
def recalculate_company_score(company_id: int) -> str:
    """Recalculate the lead score for a single company.

    Intended for on-demand recalculation after signals or contacts change::

        recalculate_company_score.delay(company_id=42)
    """
    return run_async(_recalculate_company(company_id))


@celery_app.task(
    base=BaseTask,
    name="app.tasks.lead_scoring.recalculate_all_lead_scores",
    acks_late=True,
)
def recalculate_all_lead_scores() -> str:
    """Recalculate lead scores for all non-archived companies.

    Scheduled daily at 08:00 UTC via Celery Beat.
    """
    if not check_job_enabled("recalculate-all-scores"):
        return "recalculate-all-scores: skipped — job disabled"
    return run_async(_recalculate_all())
