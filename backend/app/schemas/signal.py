from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import SignalAction, SignalType


class SignalResponse(BaseModel):
    id: int
    company_id: int
    signal_type: SignalType
    source_url: str | None
    source_title: str | None = None
    llm_summary: str | None
    relevance_score: float | None
    action_taken: SignalAction | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SignalWithCompanyResponse(SignalResponse):
    company_name: str
    company_domain: str


class ImportContentRequest(BaseModel):
    source_url: str = Field(description="URL the content was scraped from", max_length=2048)
    markdown: str = Field(description="Scraped page content as markdown", min_length=1, max_length=500_000)


class ImportContentResponse(BaseModel):
    signals_created: int
    company_id: int
    message: str
