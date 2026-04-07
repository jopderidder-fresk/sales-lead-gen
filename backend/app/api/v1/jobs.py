"""Job schedule API — view and toggle scheduled background jobs."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.app_settings_store import get_all_job_states, set_job_enabled
from app.core.database import get_session
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.jobs import JobInfo, JobsResponse, JobToggle

logger = get_logger(__name__)

router = APIRouter(tags=["settings"])

# All scheduled beat jobs with human-readable metadata.
# Order matches the beat_schedule in celery_app.py.
_JOBS: list[dict[str, str]] = [
    {
        "name": "discover-companies",
        "schedule": "Daily at 02:00",
        "description": "Discover new companies via Bedrijfsdata",
    },
    {
        "name": "enrich-all-discovered",
        "schedule": "Daily at 04:00",
        "description": "Batch enrich all discovered companies",
    },
    {
        "name": "monitor-high-priority",
        "schedule": "Every 4 hours",
        "description": "Monitor high-priority companies for signals",
    },
    {
        "name": "monitor-standard",
        "schedule": "Daily at 06:00",
        "description": "Monitor standard-priority companies for signals",
    },
    {
        "name": "process-signal-queue",
        "schedule": "Every 15 minutes",
        "description": "Process signals through LLM pipeline",
    },
    {
        "name": "recalculate-all-scores",
        "schedule": "Daily at 08:00",
        "description": "Recalculate lead scores for all companies",
    },
    {
        "name": "deduplicate-companies",
        "schedule": "Weekly Sunday 01:00",
        "description": "Weekly deduplication pass",
    },
    {
        "name": "sync-to-crm",
        "schedule": "Daily at 09:00",
        "description": "Sync qualifying leads to CRM",
    },
    {
        "name": "slack-daily-digest",
        "schedule": "Daily at 09:00",
        "description": "Send daily signal digest to Slack",
    },
    {
        "name": "slack-weekly-summary",
        "schedule": "Monday at 09:00",
        "description": "Send weekly pipeline summary to Slack",
    },
    {
        "name": "scrape-linkedin-batch",
        "schedule": "Daily at 05:00 (uses interval setting)",
        "description": "LinkedIn scrape via Apify (frequency configured in LinkedIn settings)",
    },
    {
        "name": "cleanup-stale-jobs",
        "schedule": "Every 5 minutes",
        "description": "Mark lost/timed-out jobs as failed",
    },
]

_JOB_NAMES = [j["name"] for j in _JOBS]


@router.get("/settings/jobs", response_model=JobsResponse)
async def get_jobs(
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> JobsResponse:
    """List all scheduled jobs with their enabled state. Admin only."""
    states = await get_all_job_states(session, _JOB_NAMES)
    return JobsResponse(
        jobs=[
            JobInfo(
                name=j["name"],
                enabled=states.get(j["name"], True),
                schedule=j["schedule"],
                description=j["description"],
            )
            for j in _JOBS
        ]
    )


@router.put("/settings/jobs/{job_name}", response_model=JobInfo)
async def toggle_job(
    job_name: str,
    body: JobToggle,
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> JobInfo:
    """Enable or disable a scheduled job. Admin only."""
    job_meta = next((j for j in _JOBS if j["name"] == job_name), None)
    if job_meta is None:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_name}")

    await set_job_enabled(session, job_name, body.enabled)
    logger.info("job.toggled", job_name=job_name, enabled=body.enabled)

    return JobInfo(
        name=job_meta["name"],
        enabled=body.enabled,
        schedule=job_meta["schedule"],
        description=job_meta["description"],
    )
