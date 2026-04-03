"""Analytics endpoints — leads over time, signal breakdown, API costs, funnel, enrichment rates."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.core.utils import utcnow
from app.models.api_usage import APIUsage
from app.models.company import Company
from app.models.contact import Contact
from app.models.enums import CompanyStatus, EmailStatus
from app.models.signal import Signal
from app.models.user import User
from app.schemas.analytics import (
    APICostsResponse,
    ConversionFunnelResponse,
    EnrichmentRatesResponse,
    FunnelStage,
    LeadsDataPoint,
    LeadsOverTimeResponse,
    ProviderCostPoint,
    ProviderEnrichmentRate,
    SignalsByTypeResponse,
    SignalTypeCount,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])

_FUNNEL_STAGES = [
    CompanyStatus.DISCOVERED,
    CompanyStatus.ENRICHED,
    CompanyStatus.MONITORING,
    CompanyStatus.QUALIFIED,
    CompanyStatus.PUSHED,
]


def _parse_range(range_str: str) -> datetime:
    """Convert a range string like '7d', '30d', '90d' to a cutoff datetime."""
    range_str = range_str.strip().lower()
    if range_str.endswith("d"):
        days = int(range_str[:-1])
    elif range_str.endswith("w"):
        days = int(range_str[:-1]) * 7
    else:
        days = 30
    return utcnow() - timedelta(days=max(1, min(days, 365)))


@router.get("/leads-over-time", response_model=LeadsOverTimeResponse)
async def leads_over_time(
    range_str: str = Query("30d", alias="range", pattern=r"^\d{1,3}[dw]$"),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LeadsOverTimeResponse:
    """New companies added per day within the given range."""
    cutoff = _parse_range(range_str)

    result = await session.execute(
        select(
            cast(Company.created_at, Date).label("day"),
            func.count().label("cnt"),
        )
        .where(
            Company.status != CompanyStatus.ARCHIVED,
            Company.created_at >= cutoff,
        )
        .group_by("day")
        .order_by("day")
    )
    rows = result.all()
    points = [
        LeadsDataPoint(date=datetime.combine(r.day, datetime.min.time()), count=r.cnt) for r in rows
    ]
    total = sum(p.count for p in points)

    return LeadsOverTimeResponse(points=points, total=total, range=range_str)


@router.get("/signals-by-type", response_model=SignalsByTypeResponse)
async def signals_by_type(
    range_str: str = Query("30d", alias="range", pattern=r"^\d{1,3}[dw]$"),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SignalsByTypeResponse:
    """Distribution of signal types in the given range."""
    cutoff = _parse_range(range_str)

    result = await session.execute(
        select(
            Signal.signal_type,
            func.count().label("cnt"),
        )
        .where(Signal.created_at >= cutoff)
        .group_by(Signal.signal_type)
        .order_by(func.count().desc())
    )
    breakdown = [SignalTypeCount(signal_type=r.signal_type, count=r.cnt) for r in result.all()]
    total = sum(s.count for s in breakdown)

    return SignalsByTypeResponse(breakdown=breakdown, total=total, range=range_str)


@router.get("/api-costs", response_model=APICostsResponse)
async def api_costs(
    range_str: str = Query("30d", alias="range", pattern=r"^\d{1,3}[dw]$"),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> APICostsResponse:
    """API spend per provider per day, plus cost-per-lead metric."""
    cutoff = _parse_range(range_str)

    cost_result = await session.execute(
        select(
            cast(APIUsage.timestamp, Date).label("day"),
            APIUsage.provider,
            func.coalesce(func.sum(APIUsage.cost_estimate), 0).label("cost"),
            func.coalesce(func.sum(APIUsage.credits_used), 0).label("credits"),
        )
        .where(APIUsage.timestamp >= cutoff)
        .group_by("day", APIUsage.provider)
        .order_by("day")
    )
    points = [
        ProviderCostPoint(
            date=datetime.combine(r.day, datetime.min.time()),
            provider=r.provider,
            cost=float(r.cost),
            credits=float(r.credits),
        )
        for r in cost_result.all()
    ]
    total_cost = sum(p.cost for p in points)

    qualified_count: int = (
        await session.scalar(
            select(func.count())
            .select_from(Company)
            .where(
                Company.status.in_([CompanyStatus.QUALIFIED, CompanyStatus.PUSHED]),
                Company.created_at >= cutoff,
            )
        )
        or 0
    )

    cost_per_lead = round(total_cost / qualified_count, 2) if qualified_count > 0 else None

    return APICostsResponse(
        points=points,
        total_cost=round(total_cost, 2),
        cost_per_lead=cost_per_lead,
        range=range_str,
    )


@router.get("/conversion-funnel", response_model=ConversionFunnelResponse)
async def conversion_funnel(
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConversionFunnelResponse:
    """Conversion funnel with cumulative counts and percentages at each stage."""
    result = await session.execute(
        select(Company.status, func.count().label("cnt"))
        .where(Company.status != CompanyStatus.ARCHIVED)
        .group_by(Company.status)
    )
    counts = {r.status: r.cnt for r in result.all()}
    total = sum(counts.values())

    cumulative: list[FunnelStage] = []
    for i, stage in enumerate(_FUNNEL_STAGES):
        reached = sum(counts.get(s, 0) for s in _FUNNEL_STAGES[i:])
        pct = round(reached / total * 100, 1) if total > 0 else 0.0
        cumulative.append(FunnelStage(stage=stage, count=reached, percentage=pct))

    return ConversionFunnelResponse(stages=cumulative, total=total)


@router.get("/enrichment-rates", response_model=EnrichmentRatesResponse)
async def enrichment_rates(
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EnrichmentRatesResponse:
    """Enrichment hit-rate per provider: % of contacts with a verified email."""
    provider_result = await session.execute(
        select(
            Contact.source,
            func.count().label("total"),
            func.count().filter(Contact.email_status == EmailStatus.VERIFIED).label("verified"),
        )
        .where(Contact.source.isnot(None))
        .group_by(Contact.source)
        .order_by(func.count().desc())
    )

    providers: list[ProviderEnrichmentRate] = []
    total_attempts = 0
    total_successes = 0
    for r in provider_result.all():
        rate = round(r.verified / r.total * 100, 1) if r.total > 0 else 0.0
        providers.append(
            ProviderEnrichmentRate(
                provider=r.source,
                attempts=r.total,
                successes=r.verified,
                rate=rate,
            )
        )
        total_attempts += r.total
        total_successes += r.verified

    overall = round(total_successes / total_attempts * 100, 1) if total_attempts > 0 else 0.0

    return EnrichmentRatesResponse(providers=providers, overall_rate=overall)
