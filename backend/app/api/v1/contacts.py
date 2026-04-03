from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.deps import get_current_user
from app.core.utils import LIKE_ESCAPE, escape_like
from app.models.company import Company
from app.models.contact import Contact
from app.models.enums import EmailStatus
from app.models.user import User
from app.schemas.company import PaginatedResponse
from app.schemas.contact import ContactWithCompanyResponse

router = APIRouter(prefix="/contacts", tags=["contacts"])

_SORT_COLUMNS = {
    "name": Contact.name,
    "email": Contact.email,
    "title": Contact.title,
    "created_at": Contact.created_at,
    "company_name": Company.name,
}


@router.get("", response_model=PaginatedResponse[ContactWithCompanyResponse])
async def list_contacts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=255),
    email_status: EmailStatus | None = Query(default=None),
    company_id: int | None = Query(default=None),
    sort: str = Query(default="created_at"),
    order: Literal["asc", "desc"] = Query(default="desc"),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[ContactWithCompanyResponse]:
    """List all contacts across companies with filtering, search, and pagination."""
    query = select(Contact).join(Company, Contact.company_id == Company.id)

    # Filters
    if email_status is not None:
        query = query.where(Contact.email_status == email_status)
    if company_id is not None:
        query = query.where(Contact.company_id == company_id)
    if search is not None:
        escaped = escape_like(search)
        pattern = f"%{escaped}%"
        query = query.where(
            Contact.name.ilike(pattern, escape=LIKE_ESCAPE)
            | Contact.email.ilike(pattern, escape=LIKE_ESCAPE)
            | Contact.title.ilike(pattern, escape=LIKE_ESCAPE)
            | Company.name.ilike(pattern, escape=LIKE_ESCAPE)
        )

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    # Sorting
    sort_column = _SORT_COLUMNS.get(sort)
    if sort_column is None:
        sort_column = Contact.created_at
    sort_clause = sort_column.desc() if order == "desc" else sort_column.asc()
    query = query.order_by(sort_clause, Contact.id.asc())

    # Pagination
    query = query.offset(offset).limit(limit).options(selectinload(Contact.company))
    result = await session.execute(query)
    contacts = result.scalars().all()

    items = [
        ContactWithCompanyResponse(
            id=c.id,
            company_id=c.company_id,
            name=c.name,
            title=c.title,
            email=c.email,
            email_status=c.email_status,
            phone=c.phone,
            linkedin_url=c.linkedin_url,
            source=c.source,
            confidence_score=c.confidence_score,
            created_at=c.created_at,
            company_name=c.company.name,
            company_domain=c.company.domain,
        )
        for c in contacts
    ]

    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)
