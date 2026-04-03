"""LLM service factory — creates the right pydantic-ai model based on configuration.

Switch providers by setting ``LLM_PROVIDER`` in your ``.env`` or via the
Settings UI (persisted in the database and picked up by Celery workers)::

    LLM_PROVIDER=anthropic      # default — uses ANTHROPIC_API_KEY
    LLM_PROVIDER=openrouter     # uses OPENROUTER_API_KEY + OPENROUTER_MODEL
    LLM_PROVIDER=gemini         # uses GEMINI_API_KEY + GEMINI_MODEL
    LLM_PROVIDER=google_vertex  # uses GOOGLE_SERVICE_ACCOUNT_KEY_PATH
"""

from __future__ import annotations

from typing import Any

from prompts.config import PromptConfigBundle
from prompts.config_loader import load_prompt_config

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.services.llm.client import LLMService

logger = get_logger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

CLAUDE_HAIKU = "claude-haiku-4-5-20251001"
CLAUDE_SONNET = "claude-sonnet-4-6"

GEMINI_FLASH = "gemini-2.5-flash"
GEMINI_PRO = "gemini-2.5-pro"


async def create_llm_client(provider: str | None = None) -> LLMService:
    """Create an LLM service for the configured (or specified) provider.

    Reads API keys from the database first (set via the Settings UI),
    falling back to environment variables. This ensures Celery workers
    pick up keys updated at runtime without a restart.

    Args:
        provider: Override the default provider from settings.
                  One of: ``"anthropic"``, ``"openrouter"``, ``"gemini"``, ``"google_vertex"``.

    Returns:
        An ``LLMService`` instance ready for use.

    Raises:
        ValueError: If the provider is unknown or the required API key is not set.
    """
    from app.core.app_settings_store import (
        DB_ANTHROPIC_API_KEY,
        DB_GEMINI_API_KEY,
        DB_LLM_PROVIDER,
        DB_OPENROUTER_API_KEY,
        DB_OPENROUTER_MODEL,
        get_effective_secret,
        get_effective_setting,
    )

    if provider is None:
        provider = await get_effective_setting(DB_LLM_PROVIDER, settings.llm_provider)

    # Load configurable prompt parts (signal definitions, ICP, etc.) from DB.
    prompt_config: PromptConfigBundle
    try:
        async with async_session_factory() as session:
            prompt_config = await load_prompt_config(session)
    except Exception:
        logger.warning("prompt_config_load_failed_using_defaults")
        prompt_config = PromptConfigBundle.defaults()

    if provider == "anthropic":
        api_key = await get_effective_secret(DB_ANTHROPIC_API_KEY, settings.anthropic_api_key)
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY must be set when using the 'anthropic' LLM provider"
            )
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        anthropic_provider = AnthropicProvider(api_key=api_key)
        fast_model = AnthropicModel(CLAUDE_HAIKU, provider=anthropic_provider)
        strong_model = AnthropicModel(CLAUDE_SONNET, provider=anthropic_provider)

        logger.info("llm_service_created", provider="anthropic")
        return LLMService(
            fast_model=fast_model,
            strong_model=strong_model,
            provider="claude",
            prompt_config=prompt_config,
        )

    if provider == "openrouter":
        api_key = await get_effective_secret(DB_OPENROUTER_API_KEY, settings.openrouter_api_key)
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY must be set when using the 'openrouter' LLM provider"
            )
        from openai import AsyncOpenAI
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        model_name = await get_effective_setting(DB_OPENROUTER_MODEL, settings.openrouter_model)

        openai_client = AsyncOpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://sales-platform.local",
            },
        )
        model = OpenAIChatModel(
            model_name,
            provider=OpenAIProvider(openai_client=openai_client),
        )

        logger.info(
            "llm_service_created",
            provider="openrouter",
            model=model_name,
        )
        return LLMService(fast_model=model, provider="openrouter", prompt_config=prompt_config)

    if provider == "gemini":
        api_key = await get_effective_secret(DB_GEMINI_API_KEY, settings.gemini_api_key)
        if not api_key:
            raise ValueError("GEMINI_API_KEY must be set when using the 'gemini' LLM provider")
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider

        google_provider = GoogleProvider(api_key=api_key)
        fast_model_name = settings.gemini_fast_model or GEMINI_FLASH
        strong_model_name = settings.gemini_strong_model or GEMINI_PRO
        gemini_fast: Any = GoogleModel(fast_model_name, provider=google_provider)
        gemini_strong: Any = GoogleModel(strong_model_name, provider=google_provider)

        logger.info(
            "llm_service_created",
            provider="gemini",
            fast_model=fast_model_name,
            strong_model=strong_model_name,
        )
        return LLMService(
            fast_model=gemini_fast,
            strong_model=gemini_strong,
            provider="gemini",
            prompt_config=prompt_config,
        )

    if provider == "google_vertex":
        if (
            not settings.google_service_account_key_path
            and not settings.google_service_account_key_json
        ):
            raise ValueError(
                "GOOGLE_SERVICE_ACCOUNT_KEY_PATH or GOOGLE_SERVICE_ACCOUNT_KEY_JSON "
                "must be set when using the 'google_vertex' LLM provider"
            )
        import json

        from google.oauth2.service_account import Credentials as ServiceAccountCredentials
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider

        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        if settings.google_service_account_key_json:
            info = json.loads(settings.google_service_account_key_json)
            credentials = ServiceAccountCredentials.from_service_account_info(info, scopes=scopes)
        else:
            credentials = ServiceAccountCredentials.from_service_account_file(
                settings.google_service_account_key_path,
                scopes=scopes,
            )

        # Auto-detect project ID from the service account key if not explicitly set
        project_id = settings.google_vertex_project_id
        if not project_id:
            project_id = credentials.project_id

        google_provider = GoogleProvider(
            credentials=credentials,
            project=project_id or None,
            location=settings.google_vertex_location or "europe-west1",
        )
        fast_model_name = settings.google_vertex_fast_model or GEMINI_FLASH
        strong_model_name = settings.google_vertex_strong_model or GEMINI_PRO
        vertex_fast: Any = GoogleModel(fast_model_name, provider=google_provider)
        vertex_strong: Any = GoogleModel(strong_model_name, provider=google_provider)

        logger.info(
            "llm_service_created",
            provider="google_vertex",
            fast_model=fast_model_name,
            strong_model=strong_model_name,
        )
        return LLMService(
            fast_model=vertex_fast,
            strong_model=vertex_strong,
            provider="google_vertex",
            prompt_config=prompt_config,
        )

    raise ValueError(
        f"Unknown LLM provider: {provider!r}. "
        f"Supported providers: 'anthropic', 'openrouter', 'gemini', 'google_vertex'"
    )
