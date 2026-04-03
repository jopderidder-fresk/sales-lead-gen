from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.icp_profile import ICPProfile
from app.schemas.icp_profile import ICPProfileCreate, ICPProfileUpdate


async def list_profiles(session: AsyncSession) -> list[ICPProfile]:
    result = await session.execute(
        select(ICPProfile).order_by(ICPProfile.created_at.desc())
    )
    return list(result.scalars().all())


async def get_profile(session: AsyncSession, profile_id: int) -> ICPProfile | None:
    result = await session.execute(
        select(ICPProfile).where(ICPProfile.id == profile_id)
    )
    return result.scalar_one_or_none()


async def create_profile(
    session: AsyncSession, data: ICPProfileCreate
) -> ICPProfile:
    profile = ICPProfile(
        name=data.name,
        industry_filter=data.industry_filter,
        size_filter=data.size_filter.model_dump() if data.size_filter else None,
        geo_filter=data.geo_filter.model_dump() if data.geo_filter else None,
        tech_filter=data.tech_filter,
        negative_filters=data.negative_filters.model_dump()
        if data.negative_filters
        else None,
        is_active=False,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


async def update_profile(
    session: AsyncSession, profile: ICPProfile, data: ICPProfileUpdate
) -> ICPProfile:
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        setattr(profile, field, value)
    await session.commit()
    await session.refresh(profile)
    return profile


async def activate_profile(
    session: AsyncSession, profile: ICPProfile
) -> ICPProfile:
    # Lock all ICP rows to prevent concurrent activations from leaving
    # multiple profiles active (SELECT FOR UPDATE serialises the UPDATEs).
    await session.execute(
        text("SELECT id FROM icp_profiles FOR UPDATE")
    )
    await session.execute(update(ICPProfile).values(is_active=False))
    await session.execute(
        update(ICPProfile).where(ICPProfile.id == profile.id).values(is_active=True)
    )
    await session.commit()
    await session.refresh(profile)
    return profile


async def deactivate_profile(
    session: AsyncSession, profile: ICPProfile
) -> ICPProfile:
    profile.is_active = False
    await session.commit()
    await session.refresh(profile)
    return profile


async def delete_profile(session: AsyncSession, profile: ICPProfile) -> None:
    await session.delete(profile)
    await session.commit()


async def get_active_icp(session: AsyncSession) -> ICPProfile | None:
    result = await session.execute(
        select(ICPProfile).where(ICPProfile.is_active.is_(True))
    )
    return result.scalar_one_or_none()
