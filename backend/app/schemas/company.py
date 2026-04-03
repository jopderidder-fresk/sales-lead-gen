from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.models.enums import CompanyStatus
from app.schemas.crm import CRMIntegrationResponse

T = TypeVar("T")


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    domain: str = Field(min_length=1, max_length=255)
    industry: str | None = Field(default=None, max_length=255)
    size: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=255)
    icp_score: float | None = Field(default=None, ge=0, le=100)
    linkedin_url: str | None = Field(default=None, max_length=500)
    kvk_number: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    website_url: str | None = Field(default=None, max_length=500)
    address: str | None = Field(default=None, max_length=255)
    postal_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=100)
    province: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=10)
    founded_year: int | None = None
    employee_count: int | None = None
    organization_type: str | None = Field(default=None, max_length=100)
    facebook_url: str | None = Field(default=None, max_length=500)
    twitter_url: str | None = Field(default=None, max_length=500)
    bedrijfsdata: dict | None = None
    monitor: bool = False
    monitor_pinned: bool = False
    status: CompanyStatus = CompanyStatus.DISCOVERED
    clickup_task_id: str | None = Field(default=None, max_length=100)
    clickup_task_url: str | None = Field(default=None, max_length=500)


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    domain: str | None = Field(default=None, min_length=1, max_length=255)
    industry: str | None = Field(default=None, max_length=255)
    size: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=255)
    icp_score: float | None = Field(default=None, ge=0, le=100)
    linkedin_url: str | None = Field(default=None, max_length=500)
    kvk_number: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    website_url: str | None = Field(default=None, max_length=500)
    address: str | None = Field(default=None, max_length=255)
    postal_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=100)
    province: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=10)
    founded_year: int | None = None
    employee_count: int | None = None
    organization_type: str | None = Field(default=None, max_length=100)
    facebook_url: str | None = Field(default=None, max_length=500)
    twitter_url: str | None = Field(default=None, max_length=500)
    bedrijfsdata: dict | None = None
    monitor: bool | None = None
    monitor_pinned: bool | None = None
    status: CompanyStatus | None = None
    clickup_task_id: str | None = Field(default=None, max_length=100)
    clickup_task_url: str | None = Field(default=None, max_length=500)


class ScoreBreakdown(BaseModel):
    icp_fit: float = Field(ge=0, le=100)
    signal_strength: float = Field(ge=0, le=100)
    contact_quality: float = Field(ge=0, le=100)
    recency: float = Field(ge=0, le=100)


class CompanyResponse(BaseModel):
    id: int
    name: str
    domain: str
    industry: str | None
    size: str | None
    location: str | None
    icp_score: float | None
    lead_score: float | None
    score_breakdown: ScoreBreakdown | None
    score_updated_at: datetime | None
    linkedin_url: str | None
    kvk_number: str | None = None
    phone: str | None = None
    email: str | None = None
    website_url: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    province: str | None = None
    country: str | None = None
    founded_year: int | None = None
    employee_count: int | None = None
    organization_type: str | None = None
    facebook_url: str | None = None
    twitter_url: str | None = None
    bedrijfsdata: dict | None = None
    monitor: bool
    monitor_pinned: bool
    status: CompanyStatus
    clickup_task_id: str | None
    clickup_task_url: str | None
    clickup_status: str | None
    crm_integration: CRMIntegrationResponse | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyInfoResponse(BaseModel):
    summary: str
    products_services: str | None = None
    target_market: str | None = None
    technologies: list[str] = []
    company_culture: str | None = None
    headquarters: str | None = None
    founded_year: int | None = None
    employee_count_estimate: str | None = None


class CompanyDetailResponse(CompanyResponse):
    contacts_count: int
    signals_count: int
    latest_signal_at: datetime | None
    company_info: CompanyInfoResponse | None = None


class LeadScoreResponse(BaseModel):
    company_id: int
    lead_score: float
    breakdown: ScoreBreakdown
    scored_at: datetime

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int


class ImportRowError(BaseModel):
    row: int
    error: str


class BulkImportResponse(BaseModel):
    imported: int
    skipped: int
    errors: list[ImportRowError]


class BulkDeleteRequest(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=100)


class BulkDeleteResponse(BaseModel):
    archived: int
