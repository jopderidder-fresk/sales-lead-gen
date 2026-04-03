"""ClickUp integration API endpoints.

Provides:
- GET/PUT /settings/clickup — view/update workspace mapping
- POST /companies/{id}/clickup/push — push a single company to ClickUp
- GET /companies/{id}/clickup/task — get linked ClickUp task details
- POST /clickup/sync — trigger bulk sync of all qualifying companies
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.deps import get_current_user, require_role
from app.core.logging import get_logger
from app.models.company import Company
from app.models.enums import CompanyStatus
from app.models.user import User
from app.schemas.clickup import (
    ClickUpPushResponse,
    ClickUpSettingsResponse,
    ClickUpSettingsUpdate,
    ClickUpSyncResponse,
    ClickUpTaskResponse,
)
from app.services.api.clickup import ClickUpClient
from app.services.clickup import ClickUpService

logger = get_logger(__name__)

router = APIRouter(tags=["clickup"])


# ---------------------------------------------------------------------------
# Settings endpoints
# ---------------------------------------------------------------------------


@router.get("/settings/clickup", response_model=ClickUpSettingsResponse)
async def get_clickup_settings(
    _user: User = Depends(require_role("admin")),
) -> ClickUpSettingsResponse:
    """View current ClickUp integration settings. Admin only."""
    return ClickUpSettingsResponse(
        configured=bool(settings.clickup_api_key),
        workspace_id=settings.clickup_workspace_id,
        space_id=settings.clickup_space_id,
        folder_id=settings.clickup_folder_id,
        list_id=settings.clickup_list_id,
    )


@router.put("/settings/clickup", response_model=ClickUpSettingsResponse)
async def update_clickup_settings(
    body: ClickUpSettingsUpdate,
    _user: User = Depends(require_role("admin")),
) -> ClickUpSettingsResponse:
    """Update ClickUp workspace mapping settings. Admin only.

    Note: The API key itself is managed via environment variables, not this endpoint.
    This endpoint updates the workspace/space/folder/list IDs at runtime.
    """
    update_data = body.model_dump(exclude_unset=True)
    if "workspace_id" in update_data:
        settings.clickup_workspace_id = update_data["workspace_id"]
    if "space_id" in update_data:
        settings.clickup_space_id = update_data["space_id"]
    if "folder_id" in update_data:
        settings.clickup_folder_id = update_data["folder_id"]
    if "list_id" in update_data:
        settings.clickup_list_id = update_data["list_id"]

    logger.info("clickup.settings_updated", updated_fields=list(update_data.keys()))

    return ClickUpSettingsResponse(
        configured=bool(settings.clickup_api_key),
        workspace_id=settings.clickup_workspace_id,
        space_id=settings.clickup_space_id,
        folder_id=settings.clickup_folder_id,
        list_id=settings.clickup_list_id,
    )


# ---------------------------------------------------------------------------
# Company-level endpoints
# ---------------------------------------------------------------------------


def _build_clickup_service() -> ClickUpService:
    """Construct the ClickUp service from current settings."""
    client = ClickUpClient(
        api_key=settings.clickup_api_key,
        list_id=settings.clickup_list_id,
    )
    return ClickUpService(client=client)


def _require_clickup_configured() -> None:
    """Raise 503 if ClickUp is not configured."""
    if not settings.clickup_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ClickUp integration is not configured. Set CLICKUP_API_KEY.",
        )
    if not settings.clickup_list_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ClickUp list ID is not configured. Set CLICKUP_LIST_ID or update settings.",
        )


@router.post(
    "/companies/{company_id}/clickup/push",
    response_model=ClickUpPushResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def push_company_to_clickup(
    company_id: int,
    _user: User = Depends(require_role("admin", "user")),
    session: AsyncSession = Depends(get_session),
) -> ClickUpPushResponse:
    """Push a single company to ClickUp (create or update task).

    If the company already has a linked ClickUp task, it will be updated.
    Otherwise, a new task will be created.
    """
    _require_clickup_configured()

    # Verify company exists
    result = await session.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if company is None or company.status == CompanyStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    service = _build_clickup_service()
    try:
        task = await service.push_company(session, company_id)
    except Exception as exc:
        logger.error("clickup.push_failed", company_id=company_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to push to ClickUp: {exc}",
        ) from exc
    finally:
        await service.close()

    return ClickUpPushResponse(
        company_id=company_id,
        task_id=task.id,
        task_url=task.url,
        message="Company pushed to ClickUp",
    )


@router.get(
    "/companies/{company_id}/clickup/task",
    response_model=ClickUpTaskResponse,
)
async def get_company_clickup_task(
    company_id: int,
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ClickUpTaskResponse:
    """Get the ClickUp task linked to a company."""
    _require_clickup_configured()

    # Verify company exists
    result = await session.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if company is None or company.status == CompanyStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    if not company.clickup_task_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ClickUp task linked to this company",
        )

    service = _build_clickup_service()
    try:
        task = await service.sync_status_from_clickup(session, company_id)
    except Exception as exc:
        logger.error("clickup.get_task_failed", company_id=company_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch ClickUp task: {exc}",
        ) from exc
    finally:
        await service.close()

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ClickUp task not found (may have been deleted)",
        )

    return ClickUpTaskResponse(
        id=task.id,
        name=task.name,
        status=task.status,
        url=task.url,
    )


# ---------------------------------------------------------------------------
# Bulk sync
# ---------------------------------------------------------------------------


@router.post(
    "/clickup/sync",
    response_model=ClickUpSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_clickup_sync(
    _user: User = Depends(require_role("admin")),
) -> ClickUpSyncResponse:
    """Trigger a bulk sync of all qualifying companies to ClickUp.

    Dispatches a Celery task that processes all companies with
    lead_score >= threshold and status 'qualified'/'pushed'.
    """
    _require_clickup_configured()

    from app.tasks.integrations import sync_to_crm

    try:
        task = sync_to_crm.delay()
    except Exception as exc:
        logger.error("clickup.sync_trigger_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to dispatch sync task. Is the task queue running?",
        ) from exc

    logger.info("clickup.sync_triggered", celery_task_id=task.id)
    return ClickUpSyncResponse(
        task_id=task.id,
        message="ClickUp sync task dispatched",
    )
