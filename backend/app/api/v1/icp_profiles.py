from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import get_current_user, require_role
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.icp_profile import (
    ICPProfileCreate,
    ICPProfileResponse,
    ICPProfileUpdate,
)
from app.services import icp_profile as icp_service

logger = get_logger(__name__)

router = APIRouter(prefix="/icp-profiles", tags=["icp-profiles"])


@router.get("", response_model=list[ICPProfileResponse])
async def list_profiles(
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ICPProfileResponse]:
    """List all ICP profiles."""
    profiles = await icp_service.list_profiles(session)
    return [ICPProfileResponse.model_validate(p) for p in profiles]


@router.get("/{profile_id}", response_model=ICPProfileResponse)
async def get_profile(
    profile_id: int,
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ICPProfileResponse:
    """Get a single ICP profile with all filters."""
    profile = await icp_service.get_profile(session, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ICP profile not found"
        )
    return ICPProfileResponse.model_validate(profile)


@router.post(
    "",
    response_model=ICPProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    body: ICPProfileCreate,
    user: User = Depends(require_role("admin", "user")),
    session: AsyncSession = Depends(get_session),
) -> ICPProfileResponse:
    """Create a new ICP profile."""
    profile = await icp_service.create_profile(session, body)
    logger.info(
        "ICP profile created",
        profile_id=profile.id,
        name=profile.name,
        created_by=user.username,
    )
    return ICPProfileResponse.model_validate(profile)


@router.put("/{profile_id}", response_model=ICPProfileResponse)
async def update_profile(
    profile_id: int,
    body: ICPProfileUpdate,
    user: User = Depends(require_role("admin", "user")),
    session: AsyncSession = Depends(get_session),
) -> ICPProfileResponse:
    """Update an existing ICP profile."""
    profile = await icp_service.get_profile(session, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ICP profile not found"
        )
    updated = await icp_service.update_profile(session, profile, body)
    logger.info(
        "ICP profile updated",
        profile_id=updated.id,
        updated_by=user.username,
    )

    # Recalculate scores if the updated profile is the active one
    if updated.is_active:
        from app.tasks.lead_scoring import recalculate_all_lead_scores

        try:
            recalculate_all_lead_scores.delay()
        except Exception:
            logger.warning("icp.score_recalc_trigger_failed")

    return ICPProfileResponse.model_validate(updated)


@router.post("/{profile_id}/activate", response_model=ICPProfileResponse)
async def activate_profile(
    profile_id: int,
    user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> ICPProfileResponse:
    """Set an ICP profile as active (deactivates all others)."""
    profile = await icp_service.get_profile(session, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ICP profile not found"
        )
    activated = await icp_service.activate_profile(session, profile)
    logger.info(
        "ICP profile activated",
        profile_id=activated.id,
        activated_by=user.username,
    )

    # Trigger score recalculation so ICP scores reflect the new active profile
    from app.tasks.lead_scoring import recalculate_all_lead_scores

    try:
        recalculate_all_lead_scores.delay()
    except Exception:
        logger.warning("icp.score_recalc_trigger_failed")

    return ICPProfileResponse.model_validate(activated)


@router.post("/{profile_id}/deactivate", response_model=ICPProfileResponse)
async def deactivate_profile(
    profile_id: int,
    user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> ICPProfileResponse:
    """Deactivate an ICP profile without activating another one."""
    profile = await icp_service.get_profile(session, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ICP profile not found"
        )
    if not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile is already inactive",
        )
    deactivated = await icp_service.deactivate_profile(session, profile)
    logger.info(
        "ICP profile deactivated",
        profile_id=deactivated.id,
        deactivated_by=user.username,
    )
    return ICPProfileResponse.model_validate(deactivated)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: int,
    user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete an ICP profile. Cannot delete the active profile."""
    profile = await icp_service.get_profile(session, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ICP profile not found"
        )
    if profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete the active ICP profile",
        )
    await icp_service.delete_profile(session, profile)
    logger.info(
        "ICP profile deleted",
        profile_id=profile_id,
        deleted_by=user.username,
    )
