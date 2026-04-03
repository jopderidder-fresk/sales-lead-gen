"""Schemas for the API-keys settings endpoint."""

from pydantic import BaseModel


class APIKeyStatus(BaseModel):
    """Status of a single API key — never exposes the actual value."""

    key_set: bool
    preview: str | None = None  # e.g. "sk-abc1****"


class APIKeysSettingsResponse(BaseModel):
    """Full API-keys settings payload returned by GET /settings/api-keys."""

    # LLM
    llm_provider: str  # "anthropic" | "openrouter" | "gemini" | "google_vertex"
    anthropic: APIKeyStatus
    openrouter: APIKeyStatus
    openrouter_model: str
    gemini: APIKeyStatus

    # Enrichment / scraping
    firecrawl: APIKeyStatus
    hunter_io: APIKeyStatus
    apollo: APIKeyStatus
    scrapin: APIKeyStatus
    bedrijfsdata: APIKeyStatus
    apify: APIKeyStatus


class APIKeysSettingsUpdate(BaseModel):
    """Payload for PUT /settings/api-keys.  Only send the fields you want to change."""

    # LLM
    llm_provider: str | None = None
    anthropic_api_key: str | None = None
    openrouter_api_key: str | None = None
    openrouter_model: str | None = None
    gemini_api_key: str | None = None

    # Enrichment / scraping
    firecrawl_api_key: str | None = None
    hunter_io_api_key: str | None = None
    apollo_api_key: str | None = None
    scrapin_api_key: str | None = None
    bedrijfsdata_api_key: str | None = None
    apify_api_token: str | None = None
