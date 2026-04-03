"""Schemas for the prompt configuration API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PromptConfigResponse(BaseModel):
    """Response for a single prompt configuration entry."""

    config_key: str
    config_value: dict | list
    description: str | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PromptConfigListResponse(BaseModel):
    """Response listing all prompt configuration entries."""

    configs: list[PromptConfigResponse]


class PromptConfigUpdate(BaseModel):
    """Request body for updating a prompt configuration entry."""

    config_value: dict | list = Field(
        ...,
        description="The new configuration value. Shape depends on config_key.",
    )


class PromptPreviewResponse(BaseModel):
    """Response showing a fully assembled prompt for debugging."""

    prompt_name: str
    system_message: str
    sample_user_message: str
    version: str
    system_message_chars: int
