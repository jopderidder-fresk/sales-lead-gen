"""Slack notification API endpoints.

Provides:
- GET/PUT /settings/slack — view/update webhook configuration
- POST /slack/test — send a test notification
- POST /slack/digest — trigger manual daily digest
- POST /slack/weekly — trigger manual weekly summary
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.app_settings_store import (
    DB_SLACK_DIGEST_HOUR,
    DB_SLACK_WEEKLY_DAY,
    get_setting,
    set_setting,
)
from app.core.config import settings
from app.core.database import get_session
from app.core.deps import require_role
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.slack import (
    SlackDigestResponse,
    SlackSettingsResponse,
    SlackSettingsUpdate,
    SlackTestResponse,
)
from app.services.slack import SlackNotificationService

_WEBHOOK_URL_KEY = "slack.webhook_url"
_DIGEST_WEBHOOK_URL_KEY = "slack.digest_webhook_url"


logger = get_logger(__name__)


def _mask_url(url: str | None) -> str | None:
    if not url:
        return None
    preview_len = min(34, len(url))
    return url[:preview_len] + "****"


router = APIRouter(tags=["slack"])


# ---------------------------------------------------------------------------
# Settings endpoints
# ---------------------------------------------------------------------------


async def _read_slack_timing(session: AsyncSession) -> tuple[int, int]:
    """Read digest_hour and weekly_day from DB, falling back to settings."""
    raw_hour = await get_setting(session, DB_SLACK_DIGEST_HOUR)
    raw_day = await get_setting(session, DB_SLACK_WEEKLY_DAY)
    digest_hour = int(raw_hour) if raw_hour is not None else settings.slack_digest_hour
    weekly_day = int(raw_day) if raw_day is not None else settings.slack_weekly_day
    return digest_hour, weekly_day


@router.get("/settings/slack", response_model=SlackSettingsResponse)
async def get_slack_settings(
    _user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> SlackSettingsResponse:
    """View current Slack notification settings. Admin only."""
    webhook_url = await get_setting(session, _WEBHOOK_URL_KEY) or settings.slack_webhook_url
    digest_webhook_url = (
        await get_setting(session, _DIGEST_WEBHOOK_URL_KEY) or settings.slack_digest_webhook_url
    )
    digest_hour, weekly_day = await _read_slack_timing(session)
    return SlackSettingsResponse(
        configured=bool(webhook_url or digest_webhook_url),
        webhook_url_set=bool(webhook_url),
        digest_webhook_url_set=bool(digest_webhook_url),
        digest_hour=digest_hour,
        weekly_day=weekly_day,
        webhook_url_preview=_mask_url(webhook_url),
        digest_webhook_url_preview=_mask_url(digest_webhook_url),
    )


@router.put("/settings/slack", response_model=SlackSettingsResponse)
async def update_slack_settings(
    body: SlackSettingsUpdate,
    _user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> SlackSettingsResponse:
    """Update Slack notification settings. Admin only.

    Webhook URLs are persisted to the database so they survive restarts.
    Environment variables act as fallback defaults.
    """
    update_data = body.model_dump(exclude_unset=True)
    if "webhook_url" in update_data:
        url = update_data["webhook_url"] or ""
        await set_setting(session, _WEBHOOK_URL_KEY, url or None)
        settings.slack_webhook_url = url
    if "digest_webhook_url" in update_data:
        url = update_data["digest_webhook_url"] or ""
        await set_setting(session, _DIGEST_WEBHOOK_URL_KEY, url or None)
        settings.slack_digest_webhook_url = url
    if "digest_hour" in update_data:
        await set_setting(session, DB_SLACK_DIGEST_HOUR, str(update_data["digest_hour"]))
        settings.slack_digest_hour = update_data["digest_hour"]
    if "weekly_day" in update_data:
        await set_setting(session, DB_SLACK_WEEKLY_DAY, str(update_data["weekly_day"]))
        settings.slack_weekly_day = update_data["weekly_day"]

    logger.info("slack.settings_updated", updated_fields=list(update_data.keys()))

    webhook_url = await get_setting(session, _WEBHOOK_URL_KEY) or settings.slack_webhook_url
    digest_webhook_url = (
        await get_setting(session, _DIGEST_WEBHOOK_URL_KEY) or settings.slack_digest_webhook_url
    )
    digest_hour, weekly_day = await _read_slack_timing(session)
    return SlackSettingsResponse(
        configured=bool(webhook_url or digest_webhook_url),
        webhook_url_set=bool(webhook_url),
        digest_webhook_url_set=bool(digest_webhook_url),
        digest_hour=digest_hour,
        weekly_day=weekly_day,
        webhook_url_preview=_mask_url(webhook_url),
        digest_webhook_url_preview=_mask_url(digest_webhook_url),
    )


# ---------------------------------------------------------------------------
# Manual triggers
# ---------------------------------------------------------------------------


async def _get_slack_urls(session: AsyncSession) -> tuple[str, str]:
    """Return (webhook_url, digest_webhook_url) from DB, falling back to env vars."""
    webhook_url = await get_setting(session, _WEBHOOK_URL_KEY) or settings.slack_webhook_url
    digest_webhook_url = (
        await get_setting(session, _DIGEST_WEBHOOK_URL_KEY) or settings.slack_digest_webhook_url
    )
    return webhook_url, digest_webhook_url


@router.post("/slack/test", response_model=SlackTestResponse)
async def send_test_notification(
    _user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> SlackTestResponse:
    """Send a test message to the configured Slack webhook. Admin only."""
    webhook_url, digest_webhook_url = await _get_slack_urls(session)
    if not webhook_url and not digest_webhook_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack integration is not configured.",
        )

    service = SlackNotificationService(
        webhook_url=webhook_url, digest_webhook_url=digest_webhook_url
    )
    try:
        success = await service._post_webhook(
            webhook_url,
            {
                "text": "LeadPulse test notification",
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": "LeadPulse Test", "emoji": True},
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ":white_check_mark: Slack integration is working correctly.",
                        },
                    },
                ],
            },
        )
    except Exception as exc:
        logger.error("slack.test_failed", error=str(exc))
        return SlackTestResponse(success=False, message=f"Delivery failed: {exc}")
    finally:
        await service.close()

    if success:
        return SlackTestResponse(success=True, message="Test notification sent successfully")
    return SlackTestResponse(success=False, message="Webhook delivery failed (check logs)")


@router.post(
    "/slack/digest",
    response_model=SlackDigestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_daily_digest(
    _user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> SlackDigestResponse:
    """Trigger a manual daily digest. Dispatches a Celery task. Admin only."""
    webhook_url, digest_webhook_url = await _get_slack_urls(session)
    if not webhook_url and not digest_webhook_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack integration is not configured.",
        )

    from app.tasks.integrations import slack_daily_digest

    try:
        task = slack_daily_digest.delay()
    except Exception as exc:
        logger.error("slack.digest_trigger_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to dispatch digest task. Is the task queue running?",
        ) from exc

    logger.info("slack.digest_triggered", celery_task_id=task.id)
    return SlackDigestResponse(task_id=task.id, message="Daily digest task dispatched")


@router.post(
    "/slack/weekly",
    response_model=SlackDigestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_weekly_summary(
    _user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> SlackDigestResponse:
    """Trigger a manual weekly summary. Dispatches a Celery task. Admin only."""
    webhook_url, digest_webhook_url = await _get_slack_urls(session)
    if not webhook_url and not digest_webhook_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Slack integration is not configured.",
        )

    from app.tasks.integrations import slack_weekly_summary

    try:
        task = slack_weekly_summary.delay()
    except Exception as exc:
        logger.error("slack.weekly_trigger_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to dispatch weekly summary task. Is the task queue running?",
        ) from exc

    logger.info("slack.weekly_triggered", celery_task_id=task.id)
    return SlackDigestResponse(task_id=task.id, message="Weekly summary task dispatched")
