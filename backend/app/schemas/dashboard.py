from datetime import datetime

from pydantic import BaseModel

from app.models.enums import CompanyStatus, SignalAction, SignalType


class DashboardStats(BaseModel):
    total_companies: int
    total_contacts: int
    signals_last_7d: int
    hot_leads: int  # lead_score >= 75
    warm_leads: int  # lead_score 50-74


class FunnelStage(BaseModel):
    stage: CompanyStatus
    count: int


class DashboardFunnel(BaseModel):
    stages: list[FunnelStage]


class TimelinePoint(BaseModel):
    week_start: datetime
    count: int


class DashboardTimeline(BaseModel):
    points: list[TimelinePoint]


class ConversionMetrics(BaseModel):
    discovery_to_enrichment: float | None  # percentage
    enrichment_to_qualified: float | None
    qualified_to_pushed: float | None


class RecentSignal(BaseModel):
    id: int
    company_id: int
    company_name: str
    signal_type: SignalType
    relevance_score: float | None
    action_taken: SignalAction | None
    created_at: datetime


class DashboardResponse(BaseModel):
    stats: DashboardStats
    funnel: DashboardFunnel
    timeline: DashboardTimeline
    conversions: ConversionMetrics
    recent_signals: list[RecentSignal]
