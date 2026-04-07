"""LinkedIn scraping settings API — configure batch scrape frequency and scope."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.app_settings_store import (
    DB_LINKEDIN_DAILY_SCRAPE_LIMIT,
    DB_LINKEDIN_DAYS_BACK,
    DB_LINKEDIN_INTERVAL_DAYS,
    DB_LINKEDIN_LAST_BATCH_RUN,
    LINKEDIN_DEFAULT_DAILY_SCRAPE_LIMIT,
    LINKEDIN_DEFAULT_DAYS_BACK,
    LINKEDIN_DEFAULT_INTERVAL_DAYS,
    get_setting,
    is_job_enabled,
    set_job_enabled,
    set_setting,
)
from app.core.database import get_session
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.linkedin import LinkedInSettingsResponse, LinkedInSettingsUpdate

logger = get_logger(__name__)

router = APIRouter(tags=["settings"])


@router.get("/settings/linkedin", response_model=LinkedInSettingsResponse)
async def get_linkedin_settings(
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LinkedInSettingsResponse:
    """View current LinkedIn scraping settings. Admin only."""
    enabled = await is_job_enabled(session, "scrape-linkedin-batch")
    interval_raw = await get_setting(session, DB_LINKEDIN_INTERVAL_DAYS)
    days_back_raw = await get_setting(session, DB_LINKEDIN_DAYS_BACK)
    limit_raw = await get_setting(session, DB_LINKEDIN_DAILY_SCRAPE_LIMIT)
    last_run = await get_setting(session, DB_LINKEDIN_LAST_BATCH_RUN)

    return LinkedInSettingsResponse(
        enabled=enabled,
        interval_days=int(interval_raw) if interval_raw else LINKEDIN_DEFAULT_INTERVAL_DAYS,
        days_back=int(days_back_raw) if days_back_raw else LINKEDIN_DEFAULT_DAYS_BACK,
        daily_scrape_limit=int(limit_raw) if limit_raw else LINKEDIN_DEFAULT_DAILY_SCRAPE_LIMIT,
        last_batch_run=last_run,
    )


@router.put("/settings/linkedin", response_model=LinkedInSettingsResponse)
async def update_linkedin_settings(
    body: LinkedInSettingsUpdate,
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LinkedInSettingsResponse:
    """Update LinkedIn scraping settings. Admin only."""
    update_data = body.model_dump(exclude_unset=True)

    if "enabled" in update_data:
        await set_job_enabled(session, "scrape-linkedin-batch", update_data["enabled"])
    if "interval_days" in update_data:
        await set_setting(session, DB_LINKEDIN_INTERVAL_DAYS, str(update_data["interval_days"]))
    if "days_back" in update_data:
        await set_setting(session, DB_LINKEDIN_DAYS_BACK, str(update_data["days_back"]))
    if "daily_scrape_limit" in update_data:
        await set_setting(session, DB_LINKEDIN_DAILY_SCRAPE_LIMIT, str(update_data["daily_scrape_limit"]))

    logger.info("linkedin.settings_updated", updated_fields=list(update_data.keys()))

    return await get_linkedin_settings(_user=_user, session=session)
