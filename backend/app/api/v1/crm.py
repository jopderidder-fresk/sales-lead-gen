"""Generic CRM integration API endpoints.

Provides:
- GET/PUT /settings/crm — view/update CRM provider and credentials
- POST /companies/{id}/crm/push — push a company to the configured CRM
- GET /companies/{id}/crm/task — get linked CRM task details (syncs status)
- POST /crm/sync — trigger bulk sync of all qualifying companies
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.app_settings_store import (
    get_encrypted_setting,
    get_setting,
    set_encrypted_setting,
    set_setting,
)
from app.core.config import settings
from app.core.database import get_session
from app.core.deps import get_current_user, require_role
from app.core.logging import get_logger
from app.models.company import Company
from app.models.crm_integration import CRMIntegration
from app.models.enums import CompanyStatus
from app.models.user import User
from app.schemas.crm import (
    ClickUpCRMSettings,
    CRMPushResponse,
    CRMSettingsResponse,
    CRMSettingsUpdate,
    CRMSyncResponse,
    CRMTaskResponse,
)
from app.services.crm import build_crm_provider_from_db
from app.services.crm.protocol import CRMProvider

logger = get_logger(__name__)

router = APIRouter(tags=["crm"])

_VALID_PROVIDERS = {"clickup", ""}

# DB keys for CRM settings
_CRM_PROVIDER_KEY = "crm.provider"
_CRM_CLICKUP_API_KEY = "crm.clickup.api_key"
_CRM_CLICKUP_WORKSPACE_ID = "crm.clickup.workspace_id"
_CRM_CLICKUP_SPACE_ID = "crm.clickup.space_id"
_CRM_CLICKUP_FOLDER_ID = "crm.clickup.folder_id"
_CRM_CLICKUP_LIST_ID = "crm.clickup.list_id"
_CRM_CLICKUP_DOMAIN_FIELD_ID = "crm.clickup.domain_field_id"
# Person-task field names — db key = f"crm.clickup.{f}", settings attr = f"clickup_{f}"
_CLICKUP_PERSON_FIELDS = [
    "person_list_id",
    "person_email_field_id",
    "person_phone_field_id",
    "person_linkedin_field_id",
    "person_surname_field_id",
    "person_lastname_field_id",
    "person_role_field_id",
    "contact_relationship_field_id",
    "company_contact_field_id",
]


def _mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    visible = min(8, len(value))
    return value[:visible] + "****"


async def require_crm_provider(session: AsyncSession = Depends(get_session)) -> CRMProvider:
    """FastAPI dependency — return the configured CRM provider or raise 503."""
    provider = await build_crm_provider_from_db(session)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No CRM integration is configured.",
        )
    return provider


# ---------------------------------------------------------------------------
# Settings endpoints
# ---------------------------------------------------------------------------


@router.get("/settings/crm", response_model=CRMSettingsResponse)
async def get_crm_settings(
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CRMSettingsResponse:
    """View current CRM integration settings. Admin only."""
    provider = await get_setting(session, _CRM_PROVIDER_KEY) or settings.crm_provider

    clickup_cfg = None
    if provider == "clickup" or settings.clickup_api_key:
        api_key = (
            await get_encrypted_setting(session, _CRM_CLICKUP_API_KEY) or settings.clickup_api_key
        )
        clickup_cfg = ClickUpCRMSettings(
            api_key_set=bool(api_key),
            api_key_preview=_mask_secret(api_key),
            workspace_id=(
                await get_setting(session, _CRM_CLICKUP_WORKSPACE_ID)
                or settings.clickup_workspace_id
            ),
            space_id=(
                await get_setting(session, _CRM_CLICKUP_SPACE_ID) or settings.clickup_space_id
            ),
            folder_id=(
                await get_setting(session, _CRM_CLICKUP_FOLDER_ID) or settings.clickup_folder_id
            ),
            list_id=(await get_setting(session, _CRM_CLICKUP_LIST_ID) or settings.clickup_list_id),
            domain_field_id=(
                await get_setting(session, _CRM_CLICKUP_DOMAIN_FIELD_ID)
                or settings.clickup_domain_field_id
            ),
        )
        for f in _CLICKUP_PERSON_FIELDS:
            setattr(clickup_cfg, f, await get_setting(session, f"crm.clickup.{f}") or getattr(settings, f"clickup_{f}"))

    configured = await build_crm_provider_from_db(session) is not None
    return CRMSettingsResponse(
        provider=provider,
        configured=configured,
        clickup=clickup_cfg,
    )


@router.put("/settings/crm", response_model=CRMSettingsResponse)
async def update_crm_settings(
    body: CRMSettingsUpdate,
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CRMSettingsResponse:
    """Update CRM provider and credentials. Admin only.

    Settings are persisted to the database so they survive restarts.
    Environment variables act as fallback defaults.
    """
    update_data = body.model_dump(exclude_unset=True)

    if "provider" in update_data:
        prov = update_data["provider"] or ""
        if prov and prov not in _VALID_PROVIDERS:
            valid = sorted(_VALID_PROVIDERS - {""})
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown CRM provider: {prov!r}. "
                f"Choose from: {valid}",
            )
        await set_setting(session, _CRM_PROVIDER_KEY, prov or None)
        settings.crm_provider = prov

    # ClickUp API key — encrypted at rest
    if "clickup_api_key" in update_data:
        value = update_data["clickup_api_key"] or ""
        await set_encrypted_setting(session, _CRM_CLICKUP_API_KEY, value or None)
        settings.clickup_api_key = value

    # ClickUp non-secret fields
    _clickup_field_map = {
        "clickup_workspace_id": (_CRM_CLICKUP_WORKSPACE_ID, "clickup_workspace_id"),
        "clickup_space_id": (_CRM_CLICKUP_SPACE_ID, "clickup_space_id"),
        "clickup_folder_id": (_CRM_CLICKUP_FOLDER_ID, "clickup_folder_id"),
        "clickup_list_id": (_CRM_CLICKUP_LIST_ID, "clickup_list_id"),
        "clickup_domain_field_id": (_CRM_CLICKUP_DOMAIN_FIELD_ID, "clickup_domain_field_id"),
    }
    for f in _CLICKUP_PERSON_FIELDS:
        _clickup_field_map[f"clickup_{f}"] = (f"crm.clickup.{f}", f"clickup_{f}")

    for body_field, (db_key, settings_attr) in _clickup_field_map.items():
        if body_field in update_data:
            value = update_data[body_field] or ""
            await set_setting(session, db_key, value or None)
            setattr(settings, settings_attr, value)

    logger.info("crm.settings_updated", updated_fields=list(update_data.keys()))

    return await get_crm_settings(_user=_user, session=session)


@router.post(
    "/companies/{company_id}/crm/push",
    response_model=CRMPushResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def push_company_to_crm(
    company_id: int,
    _user: User = Depends(require_role("admin", "user")),
    session: AsyncSession = Depends(get_session),
    provider: CRMProvider = Depends(require_crm_provider),
) -> CRMPushResponse:
    """Push a single company to the configured CRM (create or update task)."""

    result = await session.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if company is None or company.status == CompanyStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    try:
        task = await provider.push_company(session, company_id)
    except Exception as exc:
        logger.error("crm.push_failed", company_id=company_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to push to CRM: {exc}",
        ) from exc
    finally:
        await provider.close()

    return CRMPushResponse(
        company_id=company_id,
        task_id=task.id,
        task_url=task.url,
        provider=task.provider,
        message=f"Company pushed to {task.provider}",
    )


@router.get(
    "/companies/{company_id}/crm/task",
    response_model=CRMTaskResponse,
)
async def get_company_crm_task(
    company_id: int,
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    provider: CRMProvider = Depends(require_crm_provider),
) -> CRMTaskResponse:
    """Get the CRM task linked to a company (syncs status from external system)."""

    result = await session.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if company is None or company.status == CompanyStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    # Check if there's a CRM integration for this company
    integration_result = await session.execute(
        select(CRMIntegration).where(CRMIntegration.company_id == company_id)
    )
    integration = integration_result.scalar_one_or_none()
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No CRM task linked to this company",
        )

    try:
        task = await provider.sync_status(session, company_id)
    except Exception as exc:
        logger.error("crm.get_task_failed", company_id=company_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch CRM task: {exc}",
        ) from exc
    finally:
        await provider.close()

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CRM task not found (may have been deleted)",
        )

    return CRMTaskResponse(
        id=task.id,
        name=task.name,
        status=task.status,
        url=task.url,
        provider=task.provider,
    )


@router.post(
    "/crm/sync",
    response_model=CRMSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_crm_sync(
    _user: User = Depends(require_role("admin")),
    _provider: CRMProvider = Depends(require_crm_provider),
) -> CRMSyncResponse:
    """Trigger a bulk sync of all qualifying companies to the configured CRM."""
    from app.tasks.integrations import sync_to_crm

    try:
        task = sync_to_crm.delay()  # type: ignore[attr-defined]
    except Exception as exc:
        logger.error("crm.sync_trigger_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to dispatch sync task. Is the task queue running?",
        ) from exc

    logger.info("crm.sync_triggered", celery_task_id=task.id)
    return CRMSyncResponse(
        task_id=task.id,
        message="CRM sync task dispatched",
    )
