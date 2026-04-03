"""LLM intelligence pipeline tasks.

Replaces the placeholder ``process_signal_queue`` with a real implementation
and adds ``analyze_signal`` for processing individual signals on demand.
"""

from decimal import Decimal

import structlog

from app.core.celery_app import celery_app
from app.core.database import async_session_factory, run_async
from app.services.intelligence import IntelligenceService
from app.tasks.base import BaseTask, check_job_enabled

logger = structlog.get_logger(__name__)


async def _analyze_signal(signal_id: int) -> tuple[str, int | None]:
    """Async implementation for single-signal analysis.

    Returns (summary, company_id) — company_id is set when processed.
    """
    service = IntelligenceService()
    try:
        async with async_session_factory() as session:
            from sqlalchemy import select

            from app.models.signal import Signal

            result = await session.execute(
                select(Signal.company_id).where(Signal.id == signal_id)
            )
            company_id = result.scalar_one_or_none()

            ok = await service.analyze(signal_id, session)
            if ok:
                return f"signal {signal_id}: processed", company_id
            return f"signal {signal_id}: not found", None
    finally:
        await service.close()


async def _process_queue() -> tuple[str, list[int]]:
    """Async implementation for batch queue processing.

    Returns (summary, list of processed signal IDs) so the caller can
    trigger action execution for each.
    """
    service = IntelligenceService()
    try:
        async with async_session_factory() as session:
            # Grab the pending IDs before processing so we can dispatch actions afterwards.
            from sqlalchemy import select

            from app.models.signal import Signal

            pending_ids = list(
                (
                    await session.execute(
                        select(Signal.id)
                        .where(Signal.is_processed.is_(False))
                        .order_by(Signal.created_at.asc())
                    )
                ).scalars().all()
            )

            processed = await service.process_queue(
                session,
                daily_budget=Decimal("5.00"),
            )

            # The first `processed` IDs from the pending list were handled.
            processed_ids = pending_ids[:processed]
            return f"processed {processed} signal(s)", processed_ids
    finally:
        await service.close()


@celery_app.task(
    base=BaseTask,
    name="app.tasks.llm.analyze_signal",
    acks_late=True,
)
def analyze_signal(signal_id: int) -> str:
    """Process a single signal through the LLM intelligence pipeline.

    Can be called on demand, e.g. after a new signal is scraped::

        analyze_signal.delay(signal_id=42)
    """
    summary, company_id = run_async(_analyze_signal(signal_id))

    # Trigger lead score recalculation after signal processing
    if company_id is not None:
        from app.tasks.lead_scoring import recalculate_company_score

        recalculate_company_score.delay(company_id)

    # Dispatch the LLM-recommended action (LP-032)
    from app.tasks.integrations import execute_action

    execute_action.delay(signal_id)

    return summary


@celery_app.task(
    base=BaseTask,
    name="app.tasks.llm.process_signal_queue",
    acks_late=True,
)
def process_signal_queue() -> str:
    """Pick up all unprocessed signals and run the LLM pipeline.

    Scheduled every 15 minutes via Celery Beat.  Stops early if the daily
    Claude budget is exceeded or an API error occurs.
    """
    if not check_job_enabled("process-signal-queue"):
        return "process-signal-queue: skipped — job disabled"
    summary, processed_ids = run_async(_process_queue())

    # Dispatch action execution (Slack notifications, ClickUp, etc.) for each processed signal.
    from app.tasks.integrations import execute_action

    for signal_id in processed_ids:
        execute_action.delay(signal_id)

    return summary
