"""Pydantic schemas for the analytics endpoints."""

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import CompanyStatus, SignalType


class DateRangeParams(BaseModel):
    range: str = "30d"


# ── Leads over time ──────────────────────────────────────────────────

class LeadsDataPoint(BaseModel):
    date: datetime
    count: int


class LeadsOverTimeResponse(BaseModel):
    points: list[LeadsDataPoint]
    total: int
    range: str


# ── Signals by type ──────────────────────────────────────────────────

class SignalTypeCount(BaseModel):
    signal_type: SignalType
    count: int


class SignalsByTypeResponse(BaseModel):
    breakdown: list[SignalTypeCount]
    total: int
    range: str


# ── API costs ────────────────────────────────────────────────────────

class ProviderCostPoint(BaseModel):
    date: datetime
    provider: str
    cost: float
    credits: float


class APICostsResponse(BaseModel):
    points: list[ProviderCostPoint]
    total_cost: float
    cost_per_lead: float | None
    range: str


# ── Conversion funnel ────────────────────────────────────────────────

class FunnelStage(BaseModel):
    stage: CompanyStatus
    count: int
    percentage: float


class ConversionFunnelResponse(BaseModel):
    stages: list[FunnelStage]
    total: int


# ── Enrichment rates ─────────────────────────────────────────────────

class ProviderEnrichmentRate(BaseModel):
    provider: str
    attempts: int
    successes: int
    rate: float


class EnrichmentRatesResponse(BaseModel):
    providers: list[ProviderEnrichmentRate]
    overall_rate: float
