"""Signal feed endpoint — paginated listing with filtering."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.core.utils import LIKE_ESCAPE, escape_like
from app.models.company import Company
from app.models.enums import CompanyStatus, SignalAction, SignalType
from app.models.signal import Signal
from app.models.user import User
from app.schemas.company import PaginatedResponse
from app.schemas.signal import SignalWithCompanyResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=PaginatedResponse[SignalWithCompanyResponse])
async def list_signals(
    signal_type: Annotated[list[SignalType], Query()] = [],  # noqa: B006
    action_taken: Annotated[list[SignalAction], Query()] = [],  # noqa: B006
    min_score: float | None = Query(default=None, ge=0.0, le=100.0),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    company_search: str | None = Query(default=None, max_length=255),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[SignalWithCompanyResponse]:
    """List signals across all companies with optional filtering and pagination.

    ``min_score`` accepts values in the [0, 100] range (as stored in the database).
    """
    # Exclude signals belonging to archived companies
    filters = [Company.status != CompanyStatus.ARCHIVED]
    if signal_type:
        filters.append(Signal.signal_type.in_(signal_type))
    if action_taken:
        filters.append(Signal.action_taken.in_(action_taken))
    if min_score is not None:
        filters.append(Signal.relevance_score >= min_score)
    if date_from is not None:
        filters.append(Signal.created_at >= date_from)
    if date_to is not None:
        filters.append(Signal.created_at <= date_to)
    if company_search:
        pattern = f"%{escape_like(company_search)}%"
        filters.append(Company.name.ilike(pattern, escape=LIKE_ESCAPE))

    count_stmt = (
        select(func.count())
        .select_from(Signal)
        .join(Company, Signal.company_id == Company.id)
    )
    rows_stmt = (
        select(Signal, Company.name.label("company_name"), Company.domain.label("company_domain"))
        .join(Company, Signal.company_id == Company.id)
    )
    if filters:
        where = and_(*filters)
        count_stmt = count_stmt.where(where)
        rows_stmt = rows_stmt.where(where)

    total: int = await session.scalar(count_stmt) or 0

    rows_stmt = rows_stmt.order_by(Signal.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(rows_stmt)
    rows = result.all()

    items = [
        SignalWithCompanyResponse(
            id=row.Signal.id,
            company_id=row.Signal.company_id,
            signal_type=row.Signal.signal_type,
            source_url=row.Signal.source_url,
            llm_summary=row.Signal.llm_summary,
            relevance_score=row.Signal.relevance_score,
            action_taken=row.Signal.action_taken,
            created_at=row.Signal.created_at,
            company_name=row.company_name,
            company_domain=row.company_domain,
        )
        for row in rows
    ]

    logger.info("signals_listed", total=total, offset=offset, limit=limit)
    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)
