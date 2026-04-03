"""Slack notification service — immediate alerts, daily digests, weekly summaries.

Sends Block Kit formatted messages via Slack Incoming Webhooks. Three message types:
- Immediate alerts for high-scoring signals (score >= 75)
- Daily digests summarizing all signals from the past 24h
- Weekly summaries with pipeline statistics and top leads

Webhook URLs are stored in application settings (env vars).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.core.utils import utcnow
from app.models.company import Company
from app.models.contact import Contact
from app.models.signal import Signal

logger = get_logger(__name__)

SCORE_THRESHOLD_IMMEDIATE = 75
SCORE_THRESHOLD_CHANNEL_MENTION = 90


class SlackDeliveryError(Exception):
    """Raised when a webhook delivery fails after retry."""


class SlackNotificationService:
    """Sends Slack notifications via Incoming Webhooks."""

    def __init__(
        self,
        *,
        webhook_url: str = "",
        digest_webhook_url: str = "",
    ) -> None:
        self._webhook_url = webhook_url
        self._digest_webhook_url = digest_webhook_url or webhook_url
        self._client = httpx.AsyncClient(timeout=15.0)

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Immediate alert (Block Kit)
    # ------------------------------------------------------------------

    async def send_immediate_alert(
        self,
        session: AsyncSession,
        signal: Signal,
        company: Company,
        contact: Contact | None = None,
    ) -> bool:
        """Send a Block Kit alert for a high-scoring signal.

        Returns True if delivery succeeded, False otherwise.
        """
        if not self._webhook_url:
            logger.warning("slack.no_webhook", msg="Skipping alert — no webhook URL configured")
            return False

        blocks = build_immediate_alert_blocks(signal, company, contact)
        text = f"{company.name}: {signal.signal_type.value}"

        return await self._post_webhook(
            self._webhook_url,
            {"text": text, "blocks": blocks},
        )

    # ------------------------------------------------------------------
    # Signal found notification
    # ------------------------------------------------------------------

    async def send_signal_notification(
        self,
        signal: Signal,
        company: Company,
    ) -> bool:
        """Send a structured notification when a signal is detected.

        Fires for every real signal (not NO_SIGNAL / IGNORE). Includes the
        company name, signal type + summary, and a deep link to the company
        detail page in the frontend.

        Returns True if delivery succeeded, False otherwise.
        """
        if not self._webhook_url:
            logger.warning("slack.no_webhook", msg="Skipping signal notification — no webhook URL configured")
            return False

        blocks = build_signal_notification_blocks(signal, company)
        signal_label = signal.signal_type.value.replace("_", " ").title()
        text = f"Signal: {company.name} — {signal_label}"

        return await self._post_webhook(
            self._webhook_url,
            {"text": text, "blocks": blocks},
        )

    # ------------------------------------------------------------------
    # Consolidated signal notification (replaces per-signal sends)
    # ------------------------------------------------------------------

    async def send_consolidated_notification(
        self,
        signals: list[Signal],
        company: Company,
    ) -> bool:
        """Send one Slack message covering all pending signals for a company.

        When a single signal is pending, the message is visually equivalent to the
        previous per-signal notification. When multiple signals are pending, they are
        grouped under a single company header so the channel doesn't get spammed.

        Returns True if delivery succeeded, False otherwise.
        """
        if not self._webhook_url:
            logger.warning("slack.no_webhook", msg="Skipping consolidated notification — no webhook URL configured")
            return False

        blocks = build_consolidated_notification_blocks(signals, company)
        signal_count = len(signals)
        if signal_count == 1:
            signal_label = signals[0].signal_type.value.replace("_", " ").title()
            text = f"Signal: {company.name} — {signal_label}"
        else:
            text = f"{signal_count} signals: {company.name}"

        return await self._post_webhook(
            self._webhook_url,
            {"text": text, "blocks": blocks},
        )

    # ------------------------------------------------------------------
    # Daily digest
    # ------------------------------------------------------------------

    async def send_daily_digest(self, session: AsyncSession) -> bool:
        """Build and send a daily digest of signals from the past 24h."""
        if not self._digest_webhook_url:
            logger.warning("slack.no_digest_webhook", msg="Skipping digest — no webhook URL")
            return False

        since = utcnow() - timedelta(hours=24)
        stmt = (
            select(Signal)
            .where(Signal.created_at >= since, Signal.is_processed.is_(True))
            .options(selectinload(Signal.company))
            .order_by(Signal.created_at.desc())
        )
        signals = list((await session.execute(stmt)).scalars().all())

        if not signals:
            logger.info("slack.digest_empty", msg="No signals in last 24h — skipping digest")
            return False

        blocks = build_daily_digest_blocks(signals)
        text = f"Daily Digest: {len(signals)} signal(s) in the last 24h"

        return await self._post_webhook(
            self._digest_webhook_url,
            {"text": text, "blocks": blocks},
        )

    # ------------------------------------------------------------------
    # Weekly summary
    # ------------------------------------------------------------------

    async def send_weekly_summary(self, session: AsyncSession) -> bool:
        """Build and send a weekly pipeline summary."""
        if not self._digest_webhook_url:
            logger.warning("slack.no_digest_webhook", msg="Skipping weekly summary — no webhook URL")
            return False

        since = utcnow() - timedelta(days=7)

        signal_count = (
            await session.execute(
                select(func.count(Signal.id)).where(Signal.created_at >= since)
            )
        ).scalar() or 0

        new_companies = (
            await session.execute(
                select(func.count(Company.id)).where(Company.created_at >= since)
            )
        ).scalar() or 0

        qualified = (
            await session.execute(
                select(func.count(Company.id)).where(
                    Company.status.in_(["qualified", "pushed"]),
                    Company.updated_at >= since,
                )
            )
        ).scalar() or 0

        top_leads_stmt = (
            select(Company)
            .where(Company.lead_score.isnot(None), Company.created_at >= since)
            .order_by(Company.lead_score.desc())
            .limit(5)
        )
        top_leads = list((await session.execute(top_leads_stmt)).scalars().all())

        signal_type_counts: dict[str, int] = {}
        type_rows = (
            await session.execute(
                select(Signal.signal_type, func.count(Signal.id))
                .where(Signal.created_at >= since)
                .group_by(Signal.signal_type)
            )
        ).all()
        for stype, cnt in type_rows:
            signal_type_counts[stype.value if hasattr(stype, "value") else str(stype)] = cnt

        blocks = build_weekly_summary_blocks(
            signal_count=signal_count,
            new_companies=new_companies,
            qualified=qualified,
            top_leads=top_leads,
            signal_type_counts=signal_type_counts,
        )
        text = f"Weekly Summary: {signal_count} signals, {new_companies} new companies"

        return await self._post_webhook(
            self._digest_webhook_url,
            {"text": text, "blocks": blocks},
        )

    # ------------------------------------------------------------------
    # Webhook delivery
    # ------------------------------------------------------------------

    async def _post_webhook(
        self,
        url: str,
        payload: dict[str, Any],
    ) -> bool:
        """POST a JSON payload to a Slack webhook, retry once on failure."""
        for attempt in range(2):
            try:
                response = await self._client.post(url, json=payload)
                if response.status_code == 200:
                    return True
                logger.warning(
                    "slack.webhook_error",
                    status=response.status_code,
                    body=response.text[:200],
                    attempt=attempt + 1,
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "slack.webhook_http_error",
                    error=str(exc),
                    attempt=attempt + 1,
                )

        logger.error("slack.webhook_delivery_failed", url=url[:50])
        return False


# ======================================================================
# Block Kit builders (pure functions)
# ======================================================================


def _score_badge(score: float | None) -> str:
    """Return an emoji badge based on lead score."""
    if score is None:
        return ":white_circle: N/A"
    if score >= 75:
        return f":large_green_circle: {score:.0f}"
    if score >= 50:
        return f":large_yellow_circle: {score:.0f}"
    return f":white_circle: {score:.0f}"


def build_immediate_alert_blocks(
    signal: Signal,
    company: Company,
    contact: Contact | None = None,
) -> list[dict[str, Any]]:
    """Build Block Kit blocks for an immediate signal alert."""
    signal_label = signal.signal_type.value.replace("_", " ").title()
    header_text = f"{company.name} — {signal_label}"

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header_text[:150], "emoji": True},
        },
    ]

    # Mention @channel for critical signals
    mention = "<!channel> " if (signal.relevance_score or 0) >= SCORE_THRESHOLD_CHANNEL_MENTION else ""

    summary = signal.llm_summary or "No summary available."
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"{mention}{summary}"},
    })

    # Contact details
    if contact:
        fields = [
            {"type": "mrkdwn", "text": f"*Contact:*\n{contact.name}"},
        ]
        if contact.title:
            fields.append({"type": "mrkdwn", "text": f"*Title:*\n{contact.title}"})
        if contact.email:
            fields.append({"type": "mrkdwn", "text": f"*Email:*\n{contact.email}"})
        blocks.append({"type": "section", "fields": fields})

    # Score + metadata
    blocks.append({
        "type": "section",
        "fields": [
            {"type": "mrkdwn", "text": f"*Lead Score:*\n{_score_badge(company.lead_score)}"},
            {"type": "mrkdwn", "text": f"*Signal Type:*\n{signal_label}"},
            {"type": "mrkdwn", "text": f"*Domain:*\n{company.domain}"},
            {"type": "mrkdwn", "text": f"*Detected:*\n{signal.created_at.strftime('%Y-%m-%d %H:%M')} UTC"},
        ],
    })

    # Action buttons
    actions: list[dict[str, Any]] = []
    crm = getattr(company, "crm_integration", None)
    if crm and crm.external_url:
        actions.append({
            "type": "button",
            "text": {"type": "plain_text", "text": f"View in {crm.provider.title()}", "emoji": True},
            "url": crm.external_url,
        })
    actions.append({
        "type": "button",
        "text": {"type": "plain_text", "text": "View Company", "emoji": True},
        "url": f"https://{company.domain}",
    })
    blocks.append({"type": "actions", "elements": actions})

    blocks.append({"type": "divider"})

    return blocks


def _signal_type_emoji(signal_type_value: str) -> str:
    """Return an emoji for a signal type to make scanning easier."""
    return {
        "hiring_surge": ":busts_in_silhouette:",
        "technology_adoption": ":computer:",
        "digital_transformation": ":rocket:",
        "workforce_challenge": ":warning:",
        "funding_round": ":moneybag:",
        "leadership_change": ":tophat:",
        "expansion": ":chart_with_upwards_trend:",
        "partnership": ":handshake:",
        "product_launch": ":package:",
        "other": ":mag:",
    }.get(signal_type_value, ":bell:")


def build_signal_notification_blocks(
    signal: Signal,
    company: Company,
) -> list[dict[str, Any]]:
    """Build Block Kit blocks for a signal-found notification.

    Structured for quick scanning: company name, why it triggered,
    and a direct link to the company detail page.
    """
    signal_label = signal.signal_type.value.replace("_", " ").title()
    emoji = _signal_type_emoji(signal.signal_type.value)
    frontend_url = settings.frontend_url.rstrip("/")
    company_url = f"{frontend_url}/companies/{company.id}"

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{company.name}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Signal:*\n{emoji} {signal_label}"},
                {"type": "mrkdwn", "text": f"*Relevance:*\n{_score_badge(signal.relevance_score)}"},
            ],
        },
    ]

    # LLM summary — the "why"
    summary = signal.llm_summary or "No summary available."
    # Truncate long summaries to keep the message scannable
    if len(summary) > 500:
        summary = summary[:497] + "…"
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*Why:*\n{summary}"},
    })

    # Metadata row
    meta_fields = [
        {"type": "mrkdwn", "text": f"*Domain:*\n{company.domain}"},
        {"type": "mrkdwn", "text": f"*Detected:*\n{signal.created_at.strftime('%Y-%m-%d %H:%M')} UTC"},
    ]
    if signal.source_url:
        meta_fields.append({"type": "mrkdwn", "text": f"*Source:*\n<{signal.source_url}|View page>"})
    blocks.append({"type": "section", "fields": meta_fields})

    # Action buttons
    actions: list[dict[str, Any]] = [
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "View Company Details", "emoji": True},
            "url": company_url,
            "style": "primary",
        },
    ]
    if signal.source_url:
        actions.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "View Source", "emoji": True},
            "url": signal.source_url,
        })
    blocks.append({"type": "actions", "elements": actions})

    blocks.append({"type": "divider"})

    return blocks


def build_consolidated_notification_blocks(
    signals: list[Signal],
    company: Company,
) -> list[dict[str, Any]]:
    """Build Block Kit blocks for a consolidated company signal notification.

    One or more signals are grouped under a single company header. When only one
    signal is pending the layout is equivalent to build_signal_notification_blocks.
    """
    signal_count = len(signals)
    frontend_url = settings.frontend_url.rstrip("/")
    company_url = f"{frontend_url}/companies/{company.id}"

    header_text = company.name if signal_count == 1 else f"{company.name} — {signal_count} signals"
    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header_text[:150], "emoji": True},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Lead Score:*\n{_score_badge(company.lead_score)}"},
                {"type": "mrkdwn", "text": f"*Domain:*\n{company.domain}"},
            ],
        },
    ]

    # Render up to 5 signals; truncate the rest with a count.
    MAX_SIGNALS = 5
    for sig in signals[:MAX_SIGNALS]:
        label = sig.signal_type.value.replace("_", " ").title()
        emoji = _signal_type_emoji(sig.signal_type.value)
        summary = sig.llm_summary or "No summary available."
        if len(summary) > 200:
            summary = summary[:197] + "…"
        relevance = _score_badge(sig.relevance_score)
        sig_text = f"{emoji} *{label}* — {relevance}\n{summary}"
        if sig.source_url:
            sig_text += f"\n<{sig.source_url}|View source>"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": sig_text},
        })

    if signal_count > MAX_SIGNALS:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"_…and {signal_count - MAX_SIGNALS} more signal(s)_"},
        })

    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Company Details", "emoji": True},
                "url": company_url,
                "style": "primary",
            },
        ],
    })
    blocks.append({"type": "divider"})
    return blocks


def build_daily_digest_blocks(signals: list[Signal]) -> list[dict[str, Any]]:
    """Build Block Kit blocks for a daily digest of signals."""
    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Daily Digest — {len(signals)} Signal(s)", "emoji": True},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Signals detected in the last 24 hours ({utcnow().strftime('%Y-%m-%d')}).",
            },
        },
        {"type": "divider"},
    ]

    # Group signals by company
    by_company: dict[int, list[Signal]] = {}
    for sig in signals:
        by_company.setdefault(sig.company_id, []).append(sig)

    for company_id, sigs in list(by_company.items())[:15]:
        company = sigs[0].company
        company_name = company.name if company else f"Company #{company_id}"
        score = _score_badge(company.lead_score if company else None)

        signal_lines = []
        for s in sigs[:3]:
            label = s.signal_type.value.replace("_", " ").title()
            emoji = _signal_type_emoji(s.signal_type.value)
            relevance = f" ({s.relevance_score:.0f})" if s.relevance_score else ""
            line = f"• {emoji} *{label}*{relevance}"
            if s.llm_summary:
                summary = s.llm_summary if len(s.llm_summary) <= 120 else s.llm_summary[:117] + "…"
                line += f"\n  {summary}"
            if s.source_url:
                line += f"\n  <{s.source_url}|View source>"
            signal_lines.append(line)
        if len(sigs) > 3:
            signal_lines.append(f"  _…and {len(sigs) - 3} more_")

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{company_name}* {score}\n" + "\n".join(signal_lines),
            },
        })

    if len(by_company) > 15:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"_…and {len(by_company) - 15} more companies with signals._",
            },
        })

    blocks.append({"type": "divider"})
    return blocks


def build_weekly_summary_blocks(
    *,
    signal_count: int,
    new_companies: int,
    qualified: int,
    top_leads: list[Company],
    signal_type_counts: dict[str, int],
) -> list[dict[str, Any]]:
    """Build Block Kit blocks for a weekly pipeline summary."""
    now = utcnow()
    week_start = (now - timedelta(days=7)).strftime("%b %d")
    week_end = now.strftime("%b %d, %Y")

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Weekly Summary — {week_start} to {week_end}", "emoji": True},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Total Signals:*\n{signal_count}"},
                {"type": "mrkdwn", "text": f"*New Companies:*\n{new_companies}"},
                {"type": "mrkdwn", "text": f"*Qualified/Pushed:*\n{qualified}"},
            ],
        },
        {"type": "divider"},
    ]

    # Signal type breakdown
    if signal_type_counts:
        lines = [f"• {stype.replace('_', ' ').title()}: *{cnt}*" for stype, cnt in sorted(signal_type_counts.items(), key=lambda x: x[1], reverse=True)]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Signal Breakdown:*\n" + "\n".join(lines)},
        })

    # Top leads
    if top_leads:
        lead_lines = []
        for i, c in enumerate(top_leads, 1):
            lead_lines.append(f"{i}. *{c.name}* ({c.domain}) — {_score_badge(c.lead_score)}")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Top New Leads:*\n" + "\n".join(lead_lines)},
        })

    blocks.append({"type": "divider"})
    return blocks
