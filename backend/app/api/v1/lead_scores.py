from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import get_current_user, require_role
from app.core.logging import get_logger
from app.models.company import Company
from app.models.enums import CompanyStatus
from app.models.user import User
from app.schemas.company import LeadScoreResponse, ScoreBreakdown
from app.services.lead_scoring import LeadScoringService

logger = get_logger(__name__)

router = APIRouter(prefix="/companies", tags=["lead-scores"])

_scoring_service = LeadScoringService()


@router.get("/{company_id}/score", response_model=LeadScoreResponse)
async def get_company_score(
    company_id: int,
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LeadScoreResponse:
    """Get the current lead score for a company."""
    result = await session.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()

    if company is None or company.status == CompanyStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    if company.lead_score is None or company.score_updated_at is None:
        # Score hasn't been calculated yet — calculate it now
        scoring_result = await _scoring_service.score_company(company_id, session)
        if scoring_result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )
        await session.refresh(company)

    breakdown = ScoreBreakdown(**(company.score_breakdown or {}))
    return LeadScoreResponse(
        company_id=company.id,
        lead_score=company.lead_score or 0.0,
        breakdown=breakdown,
        scored_at=company.score_updated_at,
    )


@router.post(
    "/{company_id}/score/recalculate",
    response_model=LeadScoreResponse,
    status_code=status.HTTP_200_OK,
)
async def recalculate_company_score(
    company_id: int,
    _user: User = Depends(require_role("admin", "user")),
    session: AsyncSession = Depends(get_session),
) -> LeadScoreResponse:
    """Force recalculation of a company's lead score."""
    result = await session.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()

    if company is None or company.status == CompanyStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    scoring_result = await _scoring_service.score_company(company_id, session)
    if scoring_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    await session.refresh(company)

    logger.info("lead_score.recalculated", company_id=company_id)
    breakdown = ScoreBreakdown(**(company.score_breakdown or {}))
    return LeadScoreResponse(
        company_id=company.id,
        lead_score=company.lead_score or 0.0,
        breakdown=breakdown,
        scored_at=company.score_updated_at,
    )


@router.post(
    "/scores/recalculate-all",
    status_code=status.HTTP_202_ACCEPTED,
)
async def recalculate_all_scores(
    _user: User = Depends(require_role("admin")),
) -> dict[str, str]:
    """Trigger batch recalculation of all lead scores via Celery task. Admin only."""
    from app.tasks.lead_scoring import recalculate_all_lead_scores

    try:
        task = recalculate_all_lead_scores.delay()
    except Exception as exc:
        logger.error("lead_score.batch_trigger_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to dispatch scoring task. Is the task queue running?",
        ) from exc

    logger.info("lead_score.batch_triggered", task_id=task.id)
    return {"task_id": task.id, "message": "Batch recalculation dispatched"}
