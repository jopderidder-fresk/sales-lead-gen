from datetime import datetime

from pydantic import BaseModel

from app.models.enums import EnrichmentJobStatus


class EnrichmentJobResponse(BaseModel):
    id: int
    company_id: int
    status: EnrichmentJobStatus
    result_summary: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
