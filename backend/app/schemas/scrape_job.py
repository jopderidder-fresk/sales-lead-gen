from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ScrapeJobStatus


class ScrapeJobResponse(BaseModel):
    id: int
    company_id: int
    target_url: str
    status: ScrapeJobStatus
    pages_scraped: int | None
    credits_used: float | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
