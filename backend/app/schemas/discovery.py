from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import DiscoveryJobStatus


class DiscoveryJobResponse(BaseModel):
    id: int
    status: DiscoveryJobStatus
    trigger: str
    started_at: datetime | None
    completed_at: datetime | None
    companies_found: int
    companies_added: int
    companies_skipped: int
    error_message: str | None
    duration_seconds: float | None
    celery_task_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DiscoveryJobDetailResponse(DiscoveryJobResponse):
    results: dict[str, Any] | None


class DiscoveryTriggerResponse(BaseModel):
    task_id: str
    job_id: int
    message: str


class DiscoveryScheduleResponse(BaseModel):
    task_name: str
    schedule_expression: str
    human_readable: str
    enabled: bool


class DiscoveryScheduleUpdate(BaseModel):
    frequency: str = Field(
        description="Preset: 'daily', 'twice_daily', 'weekly', or a cron expression"
    )
