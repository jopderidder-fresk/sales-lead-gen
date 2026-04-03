"""Integration Celery tasks — ClickUp sync, Slack notifications, and action orchestration.

ClickUp: pushes qualifying companies to ClickUp as tasks.
Slack: sends daily digests and weekly summaries via webhooks.
Orchestrator: dispatches LLM-recommended actions to integrations (LP-032).
"""

import structlog

from app.core.app_settings_store import get_setting
from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import async_session_factory, run_async
from app.services.action_orchestrator import ActionOrchestrator
from app.services.crm import build_crm_provider_from_db
from app.services.slack import SlackNotificationService
from app.tasks.base import BaseTask, check_job_enabled

logger = structlog.get_logger(__name__)


async def _run_sync_to_crm() -> str:
    """Async implementation for the CRM sync task."""
    async with async_session_factory() as session:
        provider = await build_crm_provider_from_db(session)
        if provider is None:
            return "sync_to_crm: skipped — no CRM provider configured"

        try:
            result = await provider.sync_qualified_companies(session)
            return result.summary()
        finally:
            await provider.close()


async def _run_push_company_to_crm(company_id: int) -> str:
    """Async implementation for pushing a single company to the CRM."""
    async with async_session_factory() as session:
        provider = await build_crm_provider_from_db(session)
        if provider is None:
            return "push_to_crm: skipped — no CRM provider configured"

        try:
            task = await provider.push_company(session, company_id)
            return f"push_to_crm: company_id={company_id}, task_id={task.id}"
        finally:
            await provider.close()


@celery_app.task(
    base=BaseTask,
    name="app.tasks.integrations.sync_to_crm",
    acks_late=True,
    time_limit=600,        # 10 min hard kill
    soft_time_limit=540,   # 9 min soft limit
)
def sync_to_crm() -> str:
    """LP-030: Push all qualifying leads to the configured CRM.

    Scheduled via Celery Beat or triggered manually.
    Finds companies with lead_score >= threshold and status 'qualified'/'pushed',
    creates new CRM tasks or updates existing ones.
    """
    if not check_job_enabled("sync-to-crm"):
        return "sync-to-crm: skipped — job disabled"
    return run_async(_run_sync_to_crm())


@celery_app.task(
    base=BaseTask,
    name="app.tasks.integrations.push_company_to_crm",
    acks_late=True,
    time_limit=120,
    soft_time_limit=90,
)
def push_company_to_crm(company_id: int) -> str:
    """Push a single company to the configured CRM (triggered manually via API)."""
    return run_async(_run_push_company_to_crm(company_id))


# ---------------------------------------------------------------------------
# Slack notification tasks
# ---------------------------------------------------------------------------


async def _load_slack_urls() -> tuple[str, str]:
    """Load Slack webhook URLs from the DB, falling back to env vars."""
    async with async_session_factory() as session:
        webhook_url = await get_setting(session, "slack.webhook_url") or settings.slack_webhook_url
        digest_webhook_url = (
            await get_setting(session, "slack.digest_webhook_url")
            or settings.slack_digest_webhook_url
        )
    return webhook_url, digest_webhook_url


async def _run_slack_daily_digest() -> str:
    """Async implementation for the Slack daily digest."""
    webhook_url, digest_webhook_url = await _load_slack_urls()
    if not webhook_url and not digest_webhook_url:
        return "slack_daily_digest: skipped — no webhook URLs configured"

    service = SlackNotificationService(webhook_url=webhook_url, digest_webhook_url=digest_webhook_url)
    try:
        async with async_session_factory() as session:
            success = await service.send_daily_digest(session)
            return f"slack_daily_digest: sent={success}"
    finally:
        await service.close()


async def _run_slack_weekly_summary() -> str:
    """Async implementation for the Slack weekly summary."""
    webhook_url, digest_webhook_url = await _load_slack_urls()
    if not webhook_url and not digest_webhook_url:
        return "slack_weekly_summary: skipped — no webhook URLs configured"

    service = SlackNotificationService(webhook_url=webhook_url, digest_webhook_url=digest_webhook_url)
    try:
        async with async_session_factory() as session:
            success = await service.send_weekly_summary(session)
            return f"slack_weekly_summary: sent={success}"
    finally:
        await service.close()


@celery_app.task(
    base=BaseTask,
    name="app.tasks.integrations.slack_daily_digest",
    acks_late=True,
    time_limit=120,
    soft_time_limit=90,
)
def slack_daily_digest() -> str:
    """LP-031: Send daily digest of signals from the past 24h to Slack.

    Scheduled via Celery Beat (default 09:00 UTC) or triggered manually.
    """
    if not check_job_enabled("slack-daily-digest"):
        return "slack-daily-digest: skipped — job disabled"
    return run_async(_run_slack_daily_digest())


@celery_app.task(
    base=BaseTask,
    name="app.tasks.integrations.slack_weekly_summary",
    acks_late=True,
    time_limit=120,
    soft_time_limit=90,
)
def slack_weekly_summary() -> str:
    """LP-031: Send weekly pipeline summary to Slack.

    Scheduled via Celery Beat (default Monday 09:00 UTC) or triggered manually.
    """
    if not check_job_enabled("slack-weekly-summary"):
        return "slack-weekly-summary: skipped — job disabled"
    return run_async(_run_slack_weekly_summary())


# ---------------------------------------------------------------------------
# Action orchestration tasks (LP-032)
# ---------------------------------------------------------------------------


async def _build_orchestrator() -> ActionOrchestrator:
    """Construct an ActionOrchestrator with available integrations."""
    async with async_session_factory() as session:
        crm_provider = await build_crm_provider_from_db(session)

    webhook_url, digest_webhook_url = await _load_slack_urls()
    slack_service = None
    if webhook_url or digest_webhook_url:
        slack_service = SlackNotificationService(
            webhook_url=webhook_url,
            digest_webhook_url=digest_webhook_url,
        )

    return ActionOrchestrator(
        crm_provider=crm_provider,
        slack_service=slack_service,
    )


async def _run_execute_action(signal_id: int) -> str:
    """Async implementation for action execution."""
    orchestrator = await _build_orchestrator()
    try:
        async with async_session_factory() as session:
            result = await orchestrator.execute(signal_id, session)
            return result.summary()
    finally:
        await orchestrator.close()


@celery_app.task(
    base=BaseTask,
    name="app.tasks.integrations.execute_action",
    acks_late=True,
    time_limit=300,
    soft_time_limit=240,
)
def execute_action(signal_id: int) -> str:
    """LP-032: Execute the LLM-recommended action for a processed signal.

    Reads ``Signal.action_taken`` and dispatches to the appropriate
    integrations (ClickUp, Slack, enrichment). Idempotent — skips if
    ``Signal.action_executed_at`` is already set.
    """
    return run_async(_run_execute_action(signal_id))
