"""Discovery API — job history, manual trigger, and schedule management."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.deps import get_current_user, require_role
from app.core.logging import get_logger
from app.core.utils import today_start_utc
from app.models.discovery_job import DiscoveryJob
from app.models.enums import DiscoveryJobStatus
from app.models.user import User
from app.schemas.company import PaginatedResponse
from app.schemas.discovery import (
    DiscoveryJobDetailResponse,
    DiscoveryJobResponse,
    DiscoveryScheduleResponse,
    DiscoveryScheduleUpdate,
    DiscoveryTriggerResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/discovery", tags=["discovery"])

SCHEDULE_PRESETS: dict[str, dict] = {
    "daily": {"hour": 2, "minute": 0},
    "twice_daily": {"hour": "2,14", "minute": 0},
    "weekly": {"hour": 2, "minute": 0, "day_of_week": "monday"},
}


def _crontab_field_to_str(field_set: set) -> str:
    """Convert a Celery crontab field (set of ints) to a display string."""
    sorted_vals = sorted(field_set)
    if len(sorted_vals) == 0:
        return "*"
    return ",".join(str(v) for v in sorted_vals)


_ALL_DAYS = {"0,1,2,3,4,5,6", "*", "0-6"}

_DAY_NAMES = {
    "0": "Sunday", "1": "Monday", "2": "Tuesday", "3": "Wednesday",
    "4": "Thursday", "5": "Friday", "6": "Saturday",
    "sunday": "Sunday", "monday": "Monday", "tuesday": "Tuesday",
    "wednesday": "Wednesday", "thursday": "Thursday",
    "friday": "Friday", "saturday": "Saturday",
}


def _cron_to_human(minute: str, hour: str, dow: str) -> str:
    """Convert parsed cron fields to plain-English schedule description."""
    hours = hour.split(",") if "," in hour else [hour]
    min_str = minute.zfill(2) if minute != "*" else "00"
    is_all_days = dow in _ALL_DAYS

    if not is_all_days:
        day_parts = dow.split(",")
        day_labels = [_DAY_NAMES.get(d.strip().lower(), d.capitalize()) for d in day_parts]
        days_str = ", ".join(day_labels)
        return f"Every {days_str} at {hours[0]}:{min_str} UTC"

    if len(hours) == 1 and hours[0] != "*":
        return f"Every day at {hours[0]}:{min_str} UTC"
    if len(hours) == 2:
        return f"Twice daily at {hours[0]}:{min_str} and {hours[1]}:{min_str} UTC"
    if len(hours) > 2:
        times = [f"{h}:{min_str}" for h in hours]
        return f"{len(hours)} times daily at {', '.join(times)} UTC"

    return f"Every {minute} minutes" if hour == "*" else "Custom schedule"


# ── Job history (paginated) ────────────────────────────────────────


@router.get(
    "/jobs",
    response_model=PaginatedResponse[DiscoveryJobResponse],
    summary="List discovery job history",
)
async def list_discovery_jobs(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    status_filter: DiscoveryJobStatus | None = Query(default=None, alias="status"),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[DiscoveryJobResponse]:
    query = select(DiscoveryJob)

    if status_filter:
        query = query.where(DiscoveryJob.status == status_filter)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    query = query.order_by(DiscoveryJob.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    jobs = result.scalars().all()

    return PaginatedResponse(
        items=[DiscoveryJobResponse.model_validate(j) for j in jobs],
        total=total,
        offset=offset,
        limit=limit,
    )


# ── Job detail ─────────────────────────────────────────────────────


@router.get(
    "/jobs/{job_id}",
    response_model=DiscoveryJobDetailResponse,
    summary="Get discovery job detail with results",
)
async def get_discovery_job(
    job_id: int,
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DiscoveryJobDetailResponse:
    result = await session.execute(
        select(DiscoveryJob).where(DiscoveryJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Discovery job not found")
    return DiscoveryJobDetailResponse.model_validate(job)


# ── Manual trigger ─────────────────────────────────────────────────


@router.post(
    "/run",
    response_model=DiscoveryTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a manual discovery run",
)
async def trigger_discovery(
    _user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> DiscoveryTriggerResponse:
    """Admin only. Creates a DiscoveryJob record and dispatches the Celery task."""
    from app.tasks.discovery import discover_companies

    # Check daily discovery runs limit
    runs_today = (
        await session.execute(
            select(func.count()).select_from(DiscoveryJob).where(
                DiscoveryJob.created_at >= today_start_utc(),
            )
        )
    ).scalar_one()
    if runs_today >= settings.max_discovery_runs_per_day:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily discovery run limit reached ({settings.max_discovery_runs_per_day}/day). "
                   "Adjust in Settings > Usage Limits.",
        )

    job = DiscoveryJob(
        status=DiscoveryJobStatus.PENDING,
        trigger="manual",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    try:
        task = discover_companies.delay(job.id)
    except Exception as exc:
        job.status = DiscoveryJobStatus.FAILED
        job.error_message = f"Failed to dispatch: {exc}"
        job.completed_at = datetime.now(UTC)
        await session.commit()
        logger.error("discovery.trigger_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to dispatch discovery task. Is the task queue running?",
        ) from exc

    job.celery_task_id = task.id
    await session.commit()

    logger.info("discovery.triggered", task_id=task.id, job_id=job.id)
    return DiscoveryTriggerResponse(
        task_id=task.id,
        job_id=job.id,
        message="Discovery task dispatched",
    )


# ── Schedule ───────────────────────────────────────────────────────


@router.get(
    "/schedule",
    response_model=DiscoveryScheduleResponse,
    summary="Get current discovery schedule",
)
async def get_schedule(
    _user: User = Depends(get_current_user),
) -> DiscoveryScheduleResponse:
    from app.core.celery_app import celery_app

    beat = celery_app.conf.beat_schedule.get("discover-companies", {})
    schedule = beat.get("schedule", None)

    if schedule is None:
        return DiscoveryScheduleResponse(
            task_name="discover-companies",
            schedule_expression="Not configured",
            human_readable="Not configured",
            enabled=False,
        )

    minute_str = _crontab_field_to_str(schedule.minute)
    hour_str = _crontab_field_to_str(schedule.hour)
    dow_str = _crontab_field_to_str(schedule.day_of_week)

    cron_expression = f"{minute_str} {hour_str} * * {dow_str}"

    return DiscoveryScheduleResponse(
        task_name="discover-companies",
        schedule_expression=cron_expression,
        human_readable=_cron_to_human(minute_str, hour_str, dow_str),
        enabled=True,
    )


@router.put(
    "/schedule",
    response_model=DiscoveryScheduleResponse,
    summary="Update discovery schedule",
)
async def update_schedule(
    body: DiscoveryScheduleUpdate,
    _user: User = Depends(require_role("admin")),
) -> DiscoveryScheduleResponse:
    from celery.schedules import crontab

    from app.core.celery_app import celery_app

    preset = SCHEDULE_PRESETS.get(body.frequency)
    if preset:
        cron_kwargs = preset
    else:
        parts = body.frequency.strip().split()
        if len(parts) != 5:
            raise HTTPException(
                status_code=400,
                detail="Invalid frequency. Use 'daily', 'twice_daily', 'weekly', or a 5-field cron expression.",
            )
        cron_kwargs = {
            "minute": parts[0],
            "hour": parts[1],
            "day_of_month": parts[2],
            "month_of_year": parts[3],
            "day_of_week": parts[4],
        }

    new_schedule = crontab(**cron_kwargs)
    celery_app.conf.beat_schedule["discover-companies"]["schedule"] = new_schedule

    minute_str = _crontab_field_to_str(new_schedule.minute)
    hour_str = _crontab_field_to_str(new_schedule.hour)
    dow_str = _crontab_field_to_str(new_schedule.day_of_week)
    cron_expression = f"{minute_str} {hour_str} * * {dow_str}"

    logger.info("discovery.schedule_updated", frequency=body.frequency)
    return DiscoveryScheduleResponse(
        task_name="discover-companies",
        schedule_expression=cron_expression,
        human_readable=_cron_to_human(minute_str, hour_str, dow_str),
        enabled=True,
    )
