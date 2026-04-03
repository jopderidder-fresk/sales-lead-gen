"""Schemas for signal monitoring endpoints."""

from pydantic import BaseModel


class MonitorTriggerResponse(BaseModel):
    task_id: str
    company_id: int
    message: str
