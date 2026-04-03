"""Dashboard endpoints — aggregated pipeline stats, funnel, timeline."""

import asyncio
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.core.utils import utcnow
from app.models.company import Company
from app.models.contact import Contact
from app.models.enums import CompanyStatus
from app.models.signal import Signal
from app.models.user import User
from app.schemas.dashboard import (
    ConversionMetrics,
    DashboardFunnel,
    DashboardResponse,
    DashboardStats,
    DashboardTimeline,
    FunnelStage,
    RecentSignal,
    TimelinePoint,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Ordered funnel stages (excludes archived)
_FUNNEL_STAGES = [
    CompanyStatus.DISCOVERED,
    CompanyStatus.ENRICHED,
    CompanyStatus.MONITORING,
    CompanyStatus.QUALIFIED,
    CompanyStatus.PUSHED,
]


async def _get_stats(session: AsyncSession) -> DashboardStats:
    """Aggregate pipeline statistics."""
    now = utcnow()
    seven_days_ago = now - timedelta(days=7)

    # Single query: total companies (non-archived), hot leads, warm leads
    company_result = await session.execute(
        select(
            func.count().label("total"),
            func.count().filter(Company.lead_score >= 75).label("hot"),
            func.count()
            .filter(Company.lead_score >= 50, Company.lead_score < 75)
            .label("warm"),
        ).where(Company.status != CompanyStatus.ARCHIVED)
    )
    row = company_result.one()

    total_contacts: int = await session.scalar(
        select(func.count())
        .select_from(Contact)
        .join(Company, Contact.company_id == Company.id)
        .where(Company.status != CompanyStatus.ARCHIVED)
    ) or 0

    signals_7d: int = await session.scalar(
        select(func.count())
        .select_from(Signal)
        .join(Company, Signal.company_id == Company.id)
        .where(
            Company.status != CompanyStatus.ARCHIVED,
            Signal.created_at >= seven_days_ago,
        )
    ) or 0

    return DashboardStats(
        total_companies=row.total,
        total_contacts=total_contacts,
        signals_last_7d=signals_7d,
        hot_leads=row.hot,
        warm_leads=row.warm,
    )


async def _get_funnel(session: AsyncSession) -> DashboardFunnel:
    """Count companies at each pipeline stage."""
    result = await session.execute(
        select(
            Company.status,
            func.count().label("cnt"),
        )
        .where(Company.status != CompanyStatus.ARCHIVED)
        .group_by(Company.status)
    )
    counts = {row.status: row.cnt for row in result.all()}

    stages = [
        FunnelStage(stage=stage, count=counts.get(stage, 0))
        for stage in _FUNNEL_STAGES
    ]
    return DashboardFunnel(stages=stages)


async def _get_timeline(session: AsyncSession) -> DashboardTimeline:
    """Companies discovered per week over the last 8 weeks."""
    now = utcnow()
    eight_weeks_ago = now - timedelta(weeks=8)

    week_start = func.date_trunc("week", Company.created_at)
    result = await session.execute(
        select(
            cast(week_start, Date).label("week"),
            func.count().label("cnt"),
        )
        .where(
            Company.status != CompanyStatus.ARCHIVED,
            Company.created_at >= eight_weeks_ago,
        )
        .group_by(week_start)
        .order_by(week_start)
    )
    points = [
        TimelinePoint(
            week_start=datetime.combine(row.week, datetime.min.time()),
            count=row.cnt,
        )
        for row in result.all()
    ]
    return DashboardTimeline(points=points)


async def _get_conversions(session: AsyncSession) -> ConversionMetrics:
    """Calculate stage-to-stage conversion rates."""
    result = await session.execute(
        select(
            Company.status,
            func.count().label("cnt"),
        )
        .where(Company.status != CompanyStatus.ARCHIVED)
        .group_by(Company.status)
    )
    counts = {row.status: row.cnt for row in result.all()}

    # Cumulative: companies that reached at least this stage
    discovered = sum(counts.get(s, 0) for s in _FUNNEL_STAGES)
    enriched = sum(counts.get(s, 0) for s in _FUNNEL_STAGES[1:])
    monitoring_plus = sum(counts.get(s, 0) for s in _FUNNEL_STAGES[2:])
    qualified = sum(counts.get(s, 0) for s in _FUNNEL_STAGES[3:])
    pushed = counts.get(CompanyStatus.PUSHED, 0)

    def _rate(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator * 100, 1) if denominator > 0 else None

    return ConversionMetrics(
        discovery_to_enrichment=_rate(enriched, discovered),
        enrichment_to_qualified=_rate(monitoring_plus, enriched),
        qualified_to_pushed=_rate(pushed, qualified),
    )


async def _get_recent_signals(session: AsyncSession) -> list[RecentSignal]:
    """Last 10 signals with company name."""
    result = await session.execute(
        select(Signal, Company.name.label("company_name"))
        .join(Company, Signal.company_id == Company.id)
        .where(Company.status != CompanyStatus.ARCHIVED)
        .order_by(Signal.created_at.desc())
        .limit(10)
    )
    return [
        RecentSignal(
            id=row.Signal.id,
            company_id=row.Signal.company_id,
            company_name=row.company_name,
            signal_type=row.Signal.signal_type,
            relevance_score=row.Signal.relevance_score,
            action_taken=row.Signal.action_taken,
            created_at=row.Signal.created_at,
        )
        for row in result.all()
    ]


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    """Return all dashboard data in a single request."""
    stats, funnel, timeline, conversions, recent_signals = await asyncio.gather(
        _get_stats(session),
        _get_funnel(session),
        _get_timeline(session),
        _get_conversions(session),
        _get_recent_signals(session),
    )

    logger.info("dashboard_loaded")
    return DashboardResponse(
        stats=stats,
        funnel=funnel,
        timeline=timeline,
        conversions=conversions,
        recent_signals=recent_signals,
    )
