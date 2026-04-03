"""Usage limits API — view and update cost management settings."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.app_settings_store import (
    DB_LIMITS_DAILY_API_COST_LIMIT,
    DB_LIMITS_MAX_COMPANIES_PER_DISCOVERY_RUN,
    DB_LIMITS_MAX_DISCOVERY_RUNS_PER_DAY,
    DB_LIMITS_MAX_ENRICHMENTS_PER_DAY,
    DB_LIMITS_MAX_MONITORING_COMPANIES_PER_RUN,
    DB_LIMITS_MAX_SCRAPES_PER_DAY,
    get_setting,
    set_setting,
)
from app.core.config import settings
from app.core.database import get_session
from app.core.deps import require_role
from app.core.logging import get_logger
from app.core.utils import today_start_utc
from app.models.api_usage import APIUsage
from app.models.discovery_job import DiscoveryJob
from app.models.enrichment_job import EnrichmentJob
from app.models.scrape_job import ScrapeJob
from app.models.user import User
from app.schemas.usage_limits import UsageLimitsResponse, UsageLimitsUpdate

logger = get_logger(__name__)

router = APIRouter(tags=["settings"])

# Maps schema field names to (DB key, type cast, settings attribute).
_LIMIT_FIELDS: dict[str, tuple[str, type, str]] = {
    "max_companies_per_discovery_run": (DB_LIMITS_MAX_COMPANIES_PER_DISCOVERY_RUN, int, "max_companies_per_discovery_run"),
    "max_discovery_runs_per_day": (DB_LIMITS_MAX_DISCOVERY_RUNS_PER_DAY, int, "max_discovery_runs_per_day"),
    "max_enrichments_per_day": (DB_LIMITS_MAX_ENRICHMENTS_PER_DAY, int, "max_enrichments_per_day"),
    "max_scrapes_per_day": (DB_LIMITS_MAX_SCRAPES_PER_DAY, int, "max_scrapes_per_day"),
    "max_monitoring_companies_per_run": (DB_LIMITS_MAX_MONITORING_COMPANIES_PER_RUN, int, "max_monitoring_companies_per_run"),
    "daily_api_cost_limit": (DB_LIMITS_DAILY_API_COST_LIMIT, float, "daily_api_cost_limit"),
}


async def _get_today_usage(session: AsyncSession) -> dict:
    """Count today's discovery runs, enrichments, scrapes, and API cost."""
    since = today_start_utc()

    discovery_runs = (
        await session.execute(
            select(func.count()).select_from(DiscoveryJob).where(
                DiscoveryJob.created_at >= since,
            )
        )
    ).scalar_one()

    enrichments = (
        await session.execute(
            select(func.count()).select_from(EnrichmentJob).where(
                EnrichmentJob.created_at >= since,
            )
        )
    ).scalar_one()

    scrapes = (
        await session.execute(
            select(func.count()).select_from(ScrapeJob).where(
                ScrapeJob.created_at >= since,
            )
        )
    ).scalar_one()

    api_cost = (
        await session.execute(
            select(func.coalesce(func.sum(APIUsage.cost_estimate), 0)).where(
                APIUsage.timestamp >= since,
            )
        )
    ).scalar_one()

    return {
        "discovery_runs_today": discovery_runs,
        "enrichments_today": enrichments,
        "scrapes_today": scrapes,
        "api_cost_today": float(api_cost or 0),
    }


async def _read_limits(session: AsyncSession) -> dict[str, int | float]:
    """Read limit values from DB, falling back to the settings singleton."""
    result: dict[str, int | float] = {}
    for field_name, (db_key, cast, attr) in _LIMIT_FIELDS.items():
        raw = await get_setting(session, db_key)
        result[field_name] = cast(raw) if raw is not None else getattr(settings, attr)
    return result


@router.get("/settings/usage-limits", response_model=UsageLimitsResponse)
async def get_usage_limits(
    _user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> UsageLimitsResponse:
    """View current usage limits and today's usage counters. Admin only."""
    limits = await _read_limits(session)
    usage = await _get_today_usage(session)
    return UsageLimitsResponse(**limits, **usage)


@router.put("/settings/usage-limits", response_model=UsageLimitsResponse)
async def update_usage_limits(
    body: UsageLimitsUpdate,
    _user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> UsageLimitsResponse:
    """Update usage limit settings. Admin only.

    Values are persisted to the database and also applied to the running
    process immediately (so Celery tasks in this process see the change).
    """
    update_data = body.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        if field_name in _LIMIT_FIELDS:
            db_key = _LIMIT_FIELDS[field_name][0]
            await set_setting(session, db_key, str(value))
        # Also update the in-memory singleton so tasks see changes immediately
        setattr(settings, field_name, value)

    logger.info("usage_limits.updated", updated_fields=list(update_data.keys()))

    limits = await _read_limits(session)
    usage = await _get_today_usage(session)
    return UsageLimitsResponse(**limits, **usage)
