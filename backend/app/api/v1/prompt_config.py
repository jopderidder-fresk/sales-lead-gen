"""Prompt configuration endpoints.

Admin-only endpoints to view, update, reset, and preview configurable
LLM prompt parts (signal definitions, company identity, decision-maker roles).

GET  /settings/prompt-config                       — list all config entries
GET  /settings/prompt-config/{key}                  — get one config entry
PUT  /settings/prompt-config/{key}                  — update one config entry
POST /settings/prompt-config/reset/{key}            — reset to defaults
GET  /settings/prompt-config/preview/{prompt_name}  — preview assembled prompt
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import require_role
from app.core.logging import get_logger
from app.models.prompt_config import PromptConfig
from app.models.user import User
from app.schemas.prompt_config import (
    PromptConfigListResponse,
    PromptConfigResponse,
    PromptConfigUpdate,
    PromptPreviewResponse,
)
from prompts.config import PromptConfigBundle
from prompts.config_loader import load_prompt_config
from prompts.manager import PromptManager

logger = get_logger(__name__)

router = APIRouter(tags=["prompt-config"])

# Keys that may be stored in the prompt_configs table.
_VALID_KEYS = {"signal_type_definitions", "company_identity", "decision_maker_roles"}

_PREVIEW_PROMPTS = {
    "signal_classification",
    "relevance_scoring",
    "action_recommendation",
    "company_extraction",
    "contact_extraction",
    "company_profile",
}


# ── Validation helpers ─────────────────────────────────────────────


def _validate_signal_types(value: list | dict) -> None:
    if not isinstance(value, list) or not value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="signal_type_definitions must be a non-empty list",
        )
    for item in value:
        if not isinstance(item, dict) or "key" not in item or "description" not in item:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Each signal type must have 'key' and 'description' fields",
            )


def _validate_company_identity(value: list | dict) -> None:
    if not isinstance(value, dict) or "name" not in value or "tagline" not in value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="company_identity must have 'name' and 'tagline' fields",
        )


def _validate_decision_maker_roles(value: list | dict) -> None:
    if not isinstance(value, list) or not value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="decision_maker_roles must be a non-empty list of strings",
        )


_VALIDATORS = {
    "signal_type_definitions": _validate_signal_types,
    "company_identity": _validate_company_identity,
    "decision_maker_roles": _validate_decision_maker_roles,
}


# ── GET list ───────────────────────────────────────────────────────


@router.get("/settings/prompt-config", response_model=PromptConfigListResponse)
async def list_prompt_configs(
    _user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> PromptConfigListResponse:
    result = await session.execute(
        select(PromptConfig).order_by(PromptConfig.config_key)
    )
    rows = result.scalars().all()
    return PromptConfigListResponse(
        configs=[
            PromptConfigResponse(
                config_key=r.config_key,
                config_value=r.config_value,
                description=r.description,
                updated_at=r.updated_at,
            )
            for r in rows
        ]
    )


# ── GET preview (must be before /{config_key} to avoid route shadowing) ──


@router.get("/settings/prompt-config/preview/{prompt_name}", response_model=PromptPreviewResponse)
async def preview_prompt(
    prompt_name: str,
    _user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> PromptPreviewResponse:
    if prompt_name not in _PREVIEW_PROMPTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown prompt: {prompt_name!r}. Valid: {sorted(_PREVIEW_PROMPTS)}",
        )

    config = await load_prompt_config(session)
    manager = PromptManager(config=config)

    sample_content = "<sample content would appear here>"
    sample_company = "Acme Corp — Installation services, 500 employees, Netherlands"

    builders: dict[str, tuple] = {
        "signal_classification": (
            manager.build_signal_classification,
            {"content": sample_content, "company_context": sample_company},
        ),
        "relevance_scoring": (
            manager.build_relevance_scoring,
            {"content": sample_content, "signal_type": "hiring_surge", "company_context": sample_company},
        ),
        "action_recommendation": (
            manager.build_action_recommendation,
            {"signal_type": "hiring_surge", "relevance_score": 80, "company_context": sample_company},
        ),
        "company_extraction": (
            manager.build_company_extraction,
            {"search_results": sample_content},
        ),
        "contact_extraction": (
            manager.build_contact_extraction,
            {"page_content": sample_content},
        ),
        "company_profile": (
            manager.build_company_profile,
            {"page_content": sample_content},
        ),
    }

    build_fn, kwargs = builders[prompt_name]
    system_msg, user_msg, version = build_fn(**kwargs)

    return PromptPreviewResponse(
        prompt_name=prompt_name,
        system_message=system_msg,
        sample_user_message=user_msg,
        version=version,
        system_message_chars=len(system_msg),
    )


# ── GET single ─────────────────────────────────────────────────────


@router.get("/settings/prompt-config/{config_key}", response_model=PromptConfigResponse)
async def get_prompt_config(
    config_key: str,
    _user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> PromptConfigResponse:
    result = await session.execute(
        select(PromptConfig).where(PromptConfig.config_key == config_key)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config key not found")
    return PromptConfigResponse(
        config_key=row.config_key,
        config_value=row.config_value,
        description=row.description,
        updated_at=row.updated_at,
    )


# ── PUT update ─────────────────────────────────────────────────────


@router.put("/settings/prompt-config/{config_key}", response_model=PromptConfigResponse)
async def update_prompt_config(
    config_key: str,
    body: PromptConfigUpdate,
    _user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> PromptConfigResponse:
    if config_key not in _VALID_KEYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown config key: {config_key!r}. Valid keys: {sorted(_VALID_KEYS)}",
        )

    validator = _VALIDATORS.get(config_key)
    if validator:
        validator(body.config_value)

    result = await session.execute(
        select(PromptConfig).where(PromptConfig.config_key == config_key)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = PromptConfig(config_key=config_key, config_value=body.config_value)
        session.add(row)
    else:
        row.config_value = body.config_value

    await session.commit()
    await session.refresh(row)
    logger.info("prompt_config_updated", config_key=config_key)

    return PromptConfigResponse(
        config_key=row.config_key,
        config_value=row.config_value,
        description=row.description,
        updated_at=row.updated_at,
    )


# ── POST reset ─────────────────────────────────────────────────────


@router.post("/settings/prompt-config/reset/{config_key}", response_model=PromptConfigResponse)
async def reset_prompt_config(
    config_key: str,
    _user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
) -> PromptConfigResponse:
    if config_key not in _VALID_KEYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown config key: {config_key!r}",
        )

    defaults = PromptConfigBundle.defaults()
    default_values: dict[str, list | dict] = {
        "signal_type_definitions": [
            {"key": st.key, "description": st.description, "relevance_hints": st.relevance_hints}
            for st in defaults.signal_types
        ],
        "company_identity": {
            "name": defaults.company_identity.name,
            "tagline": defaults.company_identity.tagline,
        },
        "decision_maker_roles": defaults.decision_maker_roles,
    }

    result = await session.execute(
        select(PromptConfig).where(PromptConfig.config_key == config_key)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = PromptConfig(config_key=config_key, config_value=default_values[config_key])
        session.add(row)
    else:
        row.config_value = default_values[config_key]

    await session.commit()
    await session.refresh(row)
    logger.info("prompt_config_reset", config_key=config_key)

    return PromptConfigResponse(
        config_key=row.config_key,
        config_value=row.config_value,
        description=row.description,
        updated_at=row.updated_at,
    )
