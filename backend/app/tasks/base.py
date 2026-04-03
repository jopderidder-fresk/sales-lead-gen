"""Base task class with structured logging, retries, and dead-letter handling."""

import structlog
from celery import Task

logger = structlog.get_logger(__name__)


def check_job_enabled(job_name: str) -> bool:
    """Check if a scheduled job is enabled, for use inside Celery tasks.

    Returns True if enabled, False if disabled.  Logs a warning when skipped.
    """
    from app.core.app_settings_store import is_job_enabled
    from app.core.database import async_session_factory, run_async

    async def _check() -> bool:
        async with async_session_factory() as session:
            return await is_job_enabled(session, job_name)

    enabled = run_async(_check())
    if not enabled:
        logger.info("task.skipped_disabled", job_name=job_name)
    return enabled


class BaseTask(Task):
    """Base task that all project tasks should inherit from.

    Provides:
    - Structured logging on start / success / failure / retry (includes task_id)
    - Automatic retry with exponential backoff (max 3 retries)
    - Dead-letter logging when all retries are exhausted
    """

    abstract = True

    # Retry policy — exponential backoff, max 3 attempts
    autoretry_for = (ConnectionError, TimeoutError, OSError)
    max_retries = 3
    retry_backoff = True        # 1 s → 2 s → 4 s …
    retry_backoff_max = 300     # cap at 5 minutes
    retry_jitter = True

    def before_start(self, task_id, args, kwargs):
        logger.info(
            "task.started",
            task_id=task_id,
            task_name=self.name,
        )

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(
            "task.success",
            task_id=task_id,
            task_name=self.name,
        )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        retries = self.request.retries if self.request else 0
        is_dead_letter = retries >= self.max_retries

        logger.error(
            "task.dead_letter" if is_dead_letter else "task.failed",
            task_id=task_id,
            task_name=self.name,
            error=str(exc),
            retries=retries,
            max_retries=self.max_retries,
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(
            "task.retry",
            task_id=task_id,
            task_name=self.name,
            error=str(exc),
            retry_number=self.request.retries if self.request else 0,
            max_retries=self.max_retries,
        )
