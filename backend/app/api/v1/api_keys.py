"""API-keys settings endpoints.

Allows admins to view and update external API keys through the UI.
Keys are stored encrypted at rest and never returned in full — only a
masked preview is shown.

GET  /settings/api-keys  — view current key status (set / not set + preview)
PUT  /settings/api-keys  — update one or more keys
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.app_settings_store import (
    DB_ANTHROPIC_API_KEY,
    DB_APIFY_API_TOKEN,
    DB_APOLLO_API_KEY,
    DB_BEDRIJFSDATA_API_KEY,
    DB_FIRECRAWL_API_KEY,
    DB_GEMINI_API_KEY,
    DB_HUNTER_IO_API_KEY,
    DB_LLM_PROVIDER,
    DB_OPENROUTER_API_KEY,
    DB_OPENROUTER_MODEL,
    DB_SCRAPIN_API_KEY,
    get_encrypted_setting,
    get_setting,
    set_encrypted_setting,
    set_setting,
)
from app.core.config import settings
from app.core.database import get_session
from app.core.deps import require_role
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.api_keys import (
    APIKeysSettingsResponse,
    APIKeysSettingsUpdate,
    APIKeyStatus,
)

logger = get_logger(__name__)

router = APIRouter(tags=["api-keys"])

_VALID_LLM_PROVIDERS = {"anthropic", "openrouter", "gemini", "google_vertex"}


def _mask(value: str | None) -> str | None:
    """Return a masked preview such as ``sk-abc1****``."""
    if not value:
        return None
    visible = min(8, len(value))
    return value[:visible] + "****"


async def _key_status(session: AsyncSession, db_key: str, env_fallback: str) -> APIKeyStatus:
    """Build an APIKeyStatus from DB (encrypted) with env-var fallback."""
    value = await get_encrypted_setting(session, db_key) or env_fallback
    return APIKeyStatus(key_set=bool(value), preview=_mask(value))


# ── GET ───────────────────────────────────────────────────────────


@router.get("/settings/api-keys", response_model=APIKeysSettingsResponse)
async def get_api_keys_settings(
    _user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> APIKeysSettingsResponse:
    """View current API-key configuration. Admin only.

    Returns which keys are set and a masked preview — never the full value.
    """
    llm_provider = (
        await get_setting(session, DB_LLM_PROVIDER)
        or settings.llm_provider
    )
    openrouter_model = (
        await get_setting(session, DB_OPENROUTER_MODEL)
        or settings.openrouter_model
    )

    ks = _key_status  # shorthand
    return APIKeysSettingsResponse(
        llm_provider=llm_provider,
        anthropic=await ks(session, DB_ANTHROPIC_API_KEY, settings.anthropic_api_key),
        openrouter=await ks(session, DB_OPENROUTER_API_KEY, settings.openrouter_api_key),
        openrouter_model=openrouter_model,
        gemini=await ks(session, DB_GEMINI_API_KEY, settings.gemini_api_key),
        firecrawl=await ks(session, DB_FIRECRAWL_API_KEY, settings.firecrawl_api_key),
        hunter_io=await ks(session, DB_HUNTER_IO_API_KEY, settings.hunter_io_api_key),
        apollo=await ks(session, DB_APOLLO_API_KEY, settings.apollo_api_key),
        scrapin=await ks(session, DB_SCRAPIN_API_KEY, settings.scrapin_api_key),
        bedrijfsdata=await ks(
            session, DB_BEDRIJFSDATA_API_KEY, settings.bedrijfsdata_api_key,
        ),
        apify=await ks(session, DB_APIFY_API_TOKEN, settings.apify_api_token),
    )


# ── PUT ───────────────────────────────────────────────────────────

# Map from body field → (db_key, settings attribute, is_encrypted)
_FIELD_MAP: dict[str, tuple[str, str, bool]] = {
    "anthropic_api_key":    (DB_ANTHROPIC_API_KEY,    "anthropic_api_key",    True),
    "openrouter_api_key":   (DB_OPENROUTER_API_KEY,   "openrouter_api_key",   True),
    "gemini_api_key":       (DB_GEMINI_API_KEY,       "gemini_api_key",       True),
    "firecrawl_api_key":    (DB_FIRECRAWL_API_KEY,    "firecrawl_api_key",    True),
    "hunter_io_api_key":    (DB_HUNTER_IO_API_KEY,    "hunter_io_api_key",    True),
    "apollo_api_key":       (DB_APOLLO_API_KEY,       "apollo_api_key",       True),
    "scrapin_api_key":      (DB_SCRAPIN_API_KEY,      "scrapin_api_key",      True),
    "bedrijfsdata_api_key": (DB_BEDRIJFSDATA_API_KEY, "bedrijfsdata_api_key", True),
    "apify_api_token":      (DB_APIFY_API_TOKEN,      "apify_api_token",      True),
    "openrouter_model":     (DB_OPENROUTER_MODEL,     "openrouter_model",     False),
}


@router.put("/settings/api-keys", response_model=APIKeysSettingsResponse)
async def update_api_keys_settings(
    body: APIKeysSettingsUpdate,
    _user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> APIKeysSettingsResponse:
    """Update API keys. Admin only.

    Only fields included in the request body are changed.
    Keys are encrypted at rest in the database.
    """
    update_data = body.model_dump(exclude_unset=True)

    # LLM provider (plain text, not a secret)
    if "llm_provider" in update_data:
        prov = update_data["llm_provider"] or ""
        if prov and prov not in _VALID_LLM_PROVIDERS:
            valid = sorted(_VALID_LLM_PROVIDERS)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown LLM provider: {prov!r}. "
                f"Choose from: {valid}",
            )
        await set_setting(session, DB_LLM_PROVIDER, prov or None)
        settings.llm_provider = prov

    # All other fields
    for body_field, (db_key, settings_attr, encrypted) in _FIELD_MAP.items():
        if body_field in update_data:
            value = update_data[body_field] or ""
            if encrypted:
                await set_encrypted_setting(session, db_key, value or None)
            else:
                await set_setting(session, db_key, value or None)
            setattr(settings, settings_attr, value)

    logger.info("api_keys.settings_updated", updated_fields=list(update_data.keys()))

    return await get_api_keys_settings(_user=_user, session=session)
