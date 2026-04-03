"""Tests for ActionOrchestrator — dispatches actions to ClickUp/Slack integrations."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.models.enums import AuditLogStatus, AuditLogTarget, SignalAction, SignalType
from app.services.action_orchestrator import ActionOrchestrator, ActionResult
from app.services.crm.protocol import CRMTask

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_company(
    company_id: int = 1,
    *,
    clickup_task_id: str | None = None,
    status: str = "qualified",
    slack_notified_at=None,
):
    c = type("Company", (), {})()
    c.id = company_id
    c.name = "Acme Corp"
    c.domain = "acme.com"
    c.lead_score = 80.0
    c.status = status
    c.clickup_task_id = clickup_task_id
    c.slack_notified_at = slack_notified_at
    return c


def _fake_signal(
    signal_id: int = 1,
    *,
    action_taken: SignalAction = SignalAction.NOTIFY_IMMEDIATE,
    action_executed_at=None,
    company=None,
):
    s = type("Signal", (), {})()
    s.id = signal_id
    s.company_id = 1
    s.signal_type = SignalType.HIRING_SURGE
    s.llm_summary = "Hiring 10 engineers"
    s.relevance_score = 85.0
    s.action_taken = action_taken
    s.action_executed_at = action_executed_at
    s.is_processed = True
    s.company = company or _fake_company()
    s.created_at = datetime(2025, 3, 15, 10, 30)
    return s


def _mock_session_with_signal(signal):
    """Build a mock session that returns the signal on first execute (with selectinload)."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = signal
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session


# ---------------------------------------------------------------------------
# NOTIFY_IMMEDIATE → ClickUp push
# ---------------------------------------------------------------------------


class TestNotifyImmediate:
    async def test_pushes_to_crm(self) -> None:
        """When action is NOTIFY_IMMEDIATE and CRM is configured, pushes company."""
        signal = _fake_signal(action_taken=SignalAction.NOTIFY_IMMEDIATE)
        task = CRMTask(
            id="task_123",
            name="Acme Corp",
            status="suspect",
            url="https://app.clickup.com/t/task_123",
            provider="clickup",
        )

        crm_provider = AsyncMock()
        crm_provider.push_company = AsyncMock(return_value=task)
        crm_provider.close = AsyncMock()

        orchestrator = ActionOrchestrator(crm_provider=crm_provider)
        session = _mock_session_with_signal(signal)

        result = await orchestrator.execute(signal.id, session)

        assert result.dispatched is True
        assert result.action_type == SignalAction.NOTIFY_IMMEDIATE
        crm_provider.push_company.assert_called_once_with(session, signal.company.id)

        # Should have a SUCCESS audit entry for CRM
        crm_audits = [a for a in result.audit_entries if a.target == AuditLogTarget.CRM]
        assert len(crm_audits) == 1
        assert crm_audits[0].status == AuditLogStatus.SUCCESS
        assert crm_audits[0].target_id == "task_123"

    async def test_skips_when_no_crm_provider(self) -> None:
        """When crm_provider is None, no CRM push happens."""
        signal = _fake_signal(action_taken=SignalAction.NOTIFY_IMMEDIATE)

        orchestrator = ActionOrchestrator(crm_provider=None)
        session = _mock_session_with_signal(signal)

        result = await orchestrator.execute(signal.id, session)

        assert result.dispatched is True
        # No CRM audit entries
        crm_audits = [a for a in result.audit_entries if a.target == AuditLogTarget.CRM]
        assert len(crm_audits) == 0

    async def test_creates_failure_audit_on_exception(self) -> None:
        """When CRM push fails, creates a FAILURE audit entry."""
        signal = _fake_signal(action_taken=SignalAction.NOTIFY_IMMEDIATE)

        crm_provider = AsyncMock()
        crm_provider.push_company = AsyncMock(side_effect=RuntimeError("API down"))
        crm_provider.close = AsyncMock()

        orchestrator = ActionOrchestrator(crm_provider=crm_provider)
        session = _mock_session_with_signal(signal)

        result = await orchestrator.execute(signal.id, session)

        assert result.dispatched is True
        crm_audits = [a for a in result.audit_entries if a.target == AuditLogTarget.CRM]
        assert len(crm_audits) == 1
        assert crm_audits[0].status == AuditLogStatus.FAILURE
        assert "API down" in crm_audits[0].error_message


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    async def test_skips_when_already_executed(self) -> None:
        """When signal.action_executed_at is set, returns without dispatching."""
        signal = _fake_signal(
            action_taken=SignalAction.NOTIFY_IMMEDIATE,
            action_executed_at=datetime(2025, 3, 15, 12, 0),
        )

        clickup_service = AsyncMock()
        orchestrator = ActionOrchestrator(clickup_service=clickup_service)
        session = _mock_session_with_signal(signal)

        result = await orchestrator.execute(signal.id, session)

        assert result.dispatched is False
        assert result.skipped_reason == "already executed"
        clickup_service.push_company.assert_not_called()

    async def test_skips_when_signal_not_found(self) -> None:
        """When signal doesn't exist, returns without dispatching."""
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        orchestrator = ActionOrchestrator()
        result = await orchestrator.execute(999, session)

        assert result.dispatched is False
        assert result.skipped_reason == "signal not found"

    async def test_skips_when_no_action_taken(self) -> None:
        """When signal.action_taken is None, returns without dispatching."""
        signal = _fake_signal()
        signal.action_taken = None

        orchestrator = ActionOrchestrator()
        session = _mock_session_with_signal(signal)

        result = await orchestrator.execute(signal.id, session)

        assert result.dispatched is False
        assert result.skipped_reason == "no action_taken set"


# ---------------------------------------------------------------------------
# Other action types
# ---------------------------------------------------------------------------


class TestOtherActions:
    async def test_notify_digest_creates_audit(self) -> None:
        """NOTIFY_DIGEST creates a SLACK audit entry for digest inclusion."""
        signal = _fake_signal(action_taken=SignalAction.NOTIFY_DIGEST)

        orchestrator = ActionOrchestrator()
        session = _mock_session_with_signal(signal)

        result = await orchestrator.execute(signal.id, session)

        assert result.dispatched is True
        slack_audits = [a for a in result.audit_entries if a.target == AuditLogTarget.SLACK]
        assert len(slack_audits) == 1
        assert slack_audits[0].action_type == SignalAction.NOTIFY_DIGEST

    async def test_ignore_is_not_dispatched(self) -> None:
        """IGNORE action is recorded as not dispatched."""
        signal = _fake_signal(action_taken=SignalAction.IGNORE)

        orchestrator = ActionOrchestrator()
        session = _mock_session_with_signal(signal)

        result = await orchestrator.execute(signal.id, session)

        assert result.dispatched is False
        assert result.skipped_reason == "action is ignore"
