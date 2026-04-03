"""Audit log endpoint — paginated listing with filtering (LP-032)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.enums import AuditLogStatus, AuditLogTarget, SignalAction
from app.models.signal import Signal
from app.models.user import User
from app.schemas.audit_log import AuditLogWithSignalResponse
from app.schemas.company import PaginatedResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/audit-log", tags=["audit-log"])


@router.get("", response_model=PaginatedResponse[AuditLogWithSignalResponse])
async def list_audit_logs(
    action_type: Annotated[list[SignalAction], Query()] = [],  # noqa: B006
    target: Annotated[list[AuditLogTarget], Query()] = [],  # noqa: B006
    status: Annotated[list[AuditLogStatus], Query()] = [],  # noqa: B006
    signal_id: int | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[AuditLogWithSignalResponse]:
    """List audit log entries with optional filtering and pagination."""
    filters: list = []
    if action_type:
        filters.append(AuditLog.action_type.in_(action_type))
    if target:
        filters.append(AuditLog.target.in_(target))
    if status:
        filters.append(AuditLog.status.in_(status))
    if signal_id is not None:
        filters.append(AuditLog.signal_id == signal_id)
    if date_from is not None:
        filters.append(AuditLog.created_at >= date_from)
    if date_to is not None:
        filters.append(AuditLog.created_at <= date_to)

    count_stmt = select(func.count()).select_from(AuditLog)
    rows_stmt = (
        select(
            AuditLog,
            Company.name.label("company_name"),
            Company.domain.label("company_domain"),
        )
        .join(Signal, AuditLog.signal_id == Signal.id)
        .outerjoin(Company, Signal.company_id == Company.id)
    )

    if filters:
        where = and_(*filters)
        count_stmt = count_stmt.where(where)
        rows_stmt = rows_stmt.where(where)

    total: int = await session.scalar(count_stmt) or 0

    rows_stmt = rows_stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(rows_stmt)
    rows = result.all()

    items = [
        AuditLogWithSignalResponse(
            id=row.AuditLog.id,
            signal_id=row.AuditLog.signal_id,
            action_type=row.AuditLog.action_type,
            target=row.AuditLog.target,
            target_id=row.AuditLog.target_id,
            status=row.AuditLog.status,
            error_message=row.AuditLog.error_message,
            created_at=row.AuditLog.created_at,
            company_name=row.company_name,
            company_domain=row.company_domain,
        )
        for row in rows
    ]

    logger.info("audit_log_listed", total=total, offset=offset, limit=limit)
    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)
