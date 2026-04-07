"""Action Orchestrator — dispatches actions based on LLM signal recommendations.

Connects the LLM intelligence layer's action recommendations to downstream
integrations (ClickUp, Slack, enrichment). Each action type maps to one or
more integration targets that are executed concurrently where possible.

Guarantees:
- Idempotency via ``Signal.action_executed_at`` — a signal is never dispatched twice.
- Partial failure tolerance — each integration target is handled independently.
- Full audit trail — every dispatch attempt is logged to the ``audit_logs`` table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.core.utils import today_start_utc, utcnow
from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.enrichment_job import EnrichmentJob
from app.models.enums import AuditLogStatus, AuditLogTarget, SignalAction
from app.models.signal import Signal
from app.services.crm.protocol import CRMProvider
from app.services.slack import SlackNotificationService

logger = get_logger(__name__)

COMPANY_NOTIFICATION_COOLDOWN_HOURS = 24


@dataclass
class ActionResult:
    signal_id: int
    action_type: SignalAction
    dispatched: bool = False
    skipped_reason: str | None = None
    audit_entries: list[AuditLog] = field(default_factory=list)

    def summary(self) -> str:
        if not self.dispatched:
            return f"signal={self.signal_id} skipped: {self.skipped_reason}"
        successes = sum(1 for a in self.audit_entries if a.status == AuditLogStatus.SUCCESS)
        failures = len(self.audit_entries) - successes
        return f"signal={self.signal_id} action={self.action_type.value} ok={successes} fail={failures}"


class ActionOrchestrator:
    """Dispatches actions based on the ``action_taken`` field on a Signal."""

    def __init__(
        self,
        *,
        crm_provider: CRMProvider | None = None,
        slack_service: SlackNotificationService | None = None,
        # Deprecated: use crm_provider instead
        clickup_service: object | None = None,
    ) -> None:
        self._crm = crm_provider
        self._slack = slack_service

    async def close(self) -> None:
        if self._crm:
            await self._crm.close()
        if self._slack:
            await self._slack.close()

    async def execute(self, signal_id: int, session: AsyncSession) -> ActionResult:
        """Execute the recommended action for a signal.

        Idempotent: if the signal has already been executed (``action_executed_at``
        is set), the call is a no-op.
        """
        signal = await self._load_signal(signal_id, session)
        if signal is None:
            return ActionResult(
                signal_id=signal_id,
                action_type=SignalAction.IGNORE,
                skipped_reason="signal not found",
            )

        if signal.action_executed_at is not None:
            return ActionResult(
                signal_id=signal_id,
                action_type=signal.action_taken or SignalAction.IGNORE,
                skipped_reason="already executed",
            )

        action = signal.action_taken
        if action is None:
            return ActionResult(
                signal_id=signal_id,
                action_type=SignalAction.IGNORE,
                skipped_reason="no action_taken set",
            )

        result = ActionResult(signal_id=signal_id, action_type=action, dispatched=True)

        if action == SignalAction.NOTIFY_IMMEDIATE:
            await self._dispatch_notify_immediate(signal, session, result)
        elif action == SignalAction.NOTIFY_DIGEST:
            await self._dispatch_notify_digest(signal, session, result)
        elif action == SignalAction.ENRICH_FURTHER:
            await self._dispatch_enrich_further(signal, session, result)
        elif action == SignalAction.IGNORE:
            self._record_ignore(signal, session, result)

        # Send an immediate Slack notification only for high-scoring signals
        if action == SignalAction.NOTIFY_IMMEDIATE and self._slack:
            await self._send_signal_notification(signal, session, result)

        signal.action_executed_at = utcnow()
        await session.commit()

        logger.info(
            "orchestrator.executed",
            signal_id=signal_id,
            action=action.value,
            summary=result.summary(),
        )
        return result

    # ------------------------------------------------------------------
    # Action dispatchers
    # ------------------------------------------------------------------

    async def _dispatch_notify_immediate(
        self,
        signal: Signal,
        session: AsyncSession,
        result: ActionResult,
    ) -> None:
        """Handle high-scoring signals. Slack notification is sent separately.

        CRM push is intentionally skipped here — companies should only be
        pushed to ClickUp manually via the API endpoint.
        """
        pass

    async def _dispatch_notify_digest(
        self,
        signal: Signal,
        session: AsyncSession,
        result: ActionResult,
    ) -> None:
        """Mark signal for inclusion in next daily digest — no immediate action needed.

        The daily digest Celery beat task already queries recent processed signals,
        so we just log the audit entry confirming the signal was triaged.
        """
        entry = AuditLog(
            signal_id=signal.id,
            action_type=SignalAction.NOTIFY_DIGEST,
            target=AuditLogTarget.SLACK,
            target_id=None,
            status=AuditLogStatus.SUCCESS,
        )
        session.add(entry)
        result.audit_entries.append(entry)

    async def _dispatch_enrich_further(
        self,
        signal: Signal,
        session: AsyncSession,
        result: ActionResult,
    ) -> None:
        """Trigger contact enrichment task and increase monitoring frequency."""
        from app.tasks.enrichment import enrich_company

        # Check daily enrichment limit before dispatching
        enrichments_today = (
            await session.execute(
                select(func.count()).select_from(EnrichmentJob).where(
                    EnrichmentJob.created_at >= today_start_utc(),
                )
            )
        ).scalar_one()
        if enrichments_today >= settings.max_enrichments_per_day:
            logger.warning(
                "orchestrator.enrich_daily_limit",
                signal_id=signal.id,
                limit=settings.max_enrichments_per_day,
            )
            entry = AuditLog(
                signal_id=signal.id,
                action_type=SignalAction.ENRICH_FURTHER,
                target=AuditLogTarget.ENRICHMENT,
                target_id=str(signal.company_id),
                status=AuditLogStatus.FAILURE,
                error_message=f"Daily enrichment limit reached ({settings.max_enrichments_per_day}/day)",
            )
            session.add(entry)
            result.audit_entries.append(entry)
            return

        try:
            enrich_company.delay(signal.company_id)
            entry = AuditLog(
                signal_id=signal.id,
                action_type=SignalAction.ENRICH_FURTHER,
                target=AuditLogTarget.ENRICHMENT,
                target_id=str(signal.company_id),
                status=AuditLogStatus.SUCCESS,
            )
        except Exception as exc:
            logger.error(
                "orchestrator.enrich_dispatch_failed",
                signal_id=signal.id,
                error=str(exc),
            )
            entry = AuditLog(
                signal_id=signal.id,
                action_type=SignalAction.ENRICH_FURTHER,
                target=AuditLogTarget.ENRICHMENT,
                target_id=str(signal.company_id),
                status=AuditLogStatus.FAILURE,
                error_message=str(exc)[:500],
            )

        session.add(entry)
        result.audit_entries.append(entry)

        company = signal.company
        if company and company.status not in ("monitoring", "qualified", "pushed"):
            company.status = "monitoring"

    def _record_ignore(
        self,
        signal: Signal,
        session: AsyncSession,
        result: ActionResult,
    ) -> None:
        """No external action — store for historical reference."""
        result.dispatched = False
        result.skipped_reason = "action is ignore"

    # ------------------------------------------------------------------
    # Integration helpers
    # ------------------------------------------------------------------

    async def _push_to_crm(
        self,
        signal: Signal,
        company: Company,
        session: AsyncSession,
        result: ActionResult,
    ) -> None:
        """Create or update a CRM task for the signal's company."""
        assert self._crm is not None
        try:
            task = await self._crm.push_company(session, company.id)
            entry = AuditLog(
                signal_id=signal.id,
                action_type=SignalAction.NOTIFY_IMMEDIATE,
                target=AuditLogTarget.CRM,
                target_id=task.id,
                status=AuditLogStatus.SUCCESS,
            )
        except Exception as exc:
            logger.error(
                "orchestrator.crm_failed",
                signal_id=signal.id,
                company_id=company.id,
                error=str(exc),
            )
            # Get external_id from CRM integration if available
            external_id = None
            crm = getattr(company, "crm_integration", None)
            if crm:
                external_id = crm.external_id
            entry = AuditLog(
                signal_id=signal.id,
                action_type=SignalAction.NOTIFY_IMMEDIATE,
                target=AuditLogTarget.CRM,
                target_id=external_id,
                status=AuditLogStatus.FAILURE,
                error_message=str(exc)[:500],
            )

        session.add(entry)
        result.audit_entries.append(entry)

    async def _send_signal_notification(
        self,
        signal: Signal,
        session: AsyncSession,
        result: ActionResult,
    ) -> None:
        """Send a consolidated Slack notification for a company's pending signals.

        Uses a row-level lock on the company to prevent concurrent workers from
        sending duplicate notifications. Applies a 24-hour cooldown per company:
        the first worker to acquire the lock sends one message covering all pending
        signals; subsequent workers within the cooldown window skip Slack entirely
        (the daily digest covers them).
        """
        assert self._slack is not None

        # Acquire a row-level lock on the company to serialize concurrent workers.
        # populate_existing=True forces SQLAlchemy to refresh attributes from DB
        # even if the Company is already in the identity map (from _load_signal).
        locked_company = (
            await session.execute(
                select(Company)
                .where(Company.id == signal.company_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

        if locked_company is None:
            return

        # Cooldown check — skip if we already notified within the window.
        cooldown_cutoff = utcnow() - timedelta(hours=COMPANY_NOTIFICATION_COOLDOWN_HOURS)
        if locked_company.slack_notified_at and locked_company.slack_notified_at >= cooldown_cutoff:
            logger.info(
                "slack.cooldown_active",
                company_id=signal.company_id,
                last_notified_at=locked_company.slack_notified_at.isoformat(),
                signal_id=signal.id,
            )
            return

        # Collect all pending signals for this company (including the current one,
        # which still has action_executed_at IS NULL at this point in the flow).
        pending_signals_result = await session.execute(
            select(Signal)
            .where(
                Signal.company_id == signal.company_id,
                Signal.is_processed.is_(True),
                Signal.action_taken == SignalAction.NOTIFY_IMMEDIATE,
                Signal.action_executed_at.is_(None),
            )
            .order_by(Signal.relevance_score.desc().nulls_last())
        )
        pending_signals = list(pending_signals_result.scalars().all())

        # Fall back to just the current signal if the query returns nothing.
        if not pending_signals:
            pending_signals = [signal]

        try:
            success = await self._slack.send_consolidated_notification(pending_signals, locked_company)
            if success:
                locked_company.slack_notified_at = utcnow()
            entry = AuditLog(
                signal_id=signal.id,
                action_type=signal.action_taken or SignalAction.NOTIFY_IMMEDIATE,
                target=AuditLogTarget.SLACK,
                target_id=None,
                status=AuditLogStatus.SUCCESS if success else AuditLogStatus.FAILURE,
                error_message=None if success else "webhook delivery failed",
            )
        except Exception as exc:
            logger.error(
                "orchestrator.slack_notification_failed",
                signal_id=signal.id,
                error=str(exc),
            )
            entry = AuditLog(
                signal_id=signal.id,
                action_type=signal.action_taken or SignalAction.NOTIFY_IMMEDIATE,
                target=AuditLogTarget.SLACK,
                target_id=None,
                status=AuditLogStatus.FAILURE,
                error_message=str(exc)[:500],
            )

        session.add(entry)
        result.audit_entries.append(entry)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def _load_signal(self, signal_id: int, session: AsyncSession) -> Signal | None:
        stmt = (
            select(Signal)
            .where(Signal.id == signal_id)
            .options(
                selectinload(Signal.company).selectinload(Company.crm_integration),
            )
        )
        return (await session.execute(stmt)).scalar_one_or_none()
