from datetime import datetime

from pydantic import BaseModel

from app.models.enums import EmailStatus


class ContactResponse(BaseModel):
    id: int
    company_id: int
    name: str
    title: str | None
    email: str | None
    email_status: EmailStatus | None
    phone: str | None
    linkedin_url: str | None
    source: str | None
    confidence_score: float | None
    clickup_task_id: str | None = None
    clickup_task_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ContactWithCompanyResponse(BaseModel):
    """Contact with inline company name and domain for the global contacts list."""

    id: int
    company_id: int
    name: str
    title: str | None
    email: str | None
    email_status: EmailStatus | None
    phone: str | None
    linkedin_url: str | None
    source: str | None
    confidence_score: float | None
    clickup_task_id: str | None = None
    clickup_task_url: str | None = None
    created_at: datetime
    company_name: str
    company_domain: str

    model_config = {"from_attributes": True}
