"""Pydantic AI-based LLM service — provider-agnostic structured extraction.

Replaces the manual JSON parsing and per-provider client implementations with
pydantic-ai agents that handle structured output via tool calling.

Usage::

    from app.services.llm import create_llm_client

    service = create_llm_client()  # reads LLM_PROVIDER from .env
    result = await service.classify_signal(content, company_context)
    await service.close()
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, TypeVar

from prompts.config import PromptConfigBundle
from prompts.manager import PromptManager
from pydantic_ai import Agent
from pydantic_ai.usage import RunUsage

from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.models.api_usage import APIUsage
from app.services.api.base_client import CircuitBreaker, _spawn_background
from app.services.api.errors import ProviderUnavailableError
from app.services.llm.base import (
    CompaniesResult,
    CompanyProfile,
    ContactsResult,
    ExtractedCompany,
    ExtractedContact,
    ScoreAndRecommendation,
    SignalClassification,
)

logger = get_logger(__name__)

_T = TypeVar("_T")

MAX_CONTENT_CHARS = 8_000
MAX_PROFILE_CONTENT_CHARS = 16_000


def _is_rate_limit(exc: BaseException) -> bool:
    """Return True if *exc* (or its cause chain) signals a 429 rate limit."""
    cur: BaseException | None = exc
    while cur is not None:
        if "429" in str(getattr(cur, "status_code", "")) or "rate limit" in str(cur).lower():
            return True
        cur = cur.__cause__
    return False


_TOKEN_COSTS: dict[str, dict[str, Decimal]] = {
    "claude-haiku-4-5-20251001": {
        "input": Decimal("0.00000025"),
        "output": Decimal("0.00000125"),
    },
    "claude-sonnet-4-6": {
        "input": Decimal("0.000003"),
        "output": Decimal("0.000015"),
    },
}


class LLMService:
    """Provider-agnostic LLM service powered by pydantic-ai.

    Each operation creates a lightweight ``Agent`` with the appropriate output
    type and system prompt. The model (OpenRouter, Anthropic, etc.) is injected
    at construction time via the factory.

    Supports two model tiers for Anthropic (fast model for classification/extraction,
    strong model for scoring). For single-model providers like OpenRouter, both
    point to the same model instance.
    """

    def __init__(
        self,
        *,
        fast_model: Any,
        strong_model: Any | None = None,
        provider: str,
        prompt_config: PromptConfigBundle | None = None,
    ) -> None:
        self._fast_model = fast_model
        self._strong_model = strong_model or fast_model
        self.provider = provider
        self._prompts = PromptManager(config=prompt_config)
        self._circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

    async def close(self) -> None:
        pass

    # ── Public API ──────────────────────────────────────────────────────────

    async def classify_signal(
        self,
        content: str,
        company_context: str = "",
    ) -> SignalClassification:
        system_msg, user_msg, _ = self._prompts.build_signal_classification(
            content=content[:MAX_CONTENT_CHARS],
            company_context=company_context,
        )
        agent = Agent(self._fast_model, output_type=SignalClassification, instructions=system_msg)
        return await self._run(agent, user_msg)

    async def score_and_recommend(
        self,
        content: str,
        signal_type: str,
        company_context: str = "",
        icp_context: str = "",
    ) -> ScoreAndRecommendation:
        system_msg, user_msg, _ = self._prompts.build_relevance_scoring(
            content=content[:MAX_CONTENT_CHARS],
            signal_type=signal_type,
            company_context=company_context,
            icp_context=icp_context,
        )
        agent = Agent(
            self._strong_model, output_type=ScoreAndRecommendation, instructions=system_msg
        )
        return await self._run(agent, user_msg)

    async def extract_companies(
        self,
        search_results: str,
    ) -> list[ExtractedCompany]:
        system_msg, user_msg, _ = self._prompts.build_company_extraction(
            search_results=search_results[:MAX_CONTENT_CHARS],
        )
        agent = Agent(self._fast_model, output_type=CompaniesResult, instructions=system_msg)
        result = await self._run(agent, user_msg)
        return result.companies

    async def extract_contacts(
        self,
        page_content: str,
    ) -> list[ExtractedContact]:
        system_msg, user_msg, _ = self._prompts.build_contact_extraction(
            page_content=page_content[:MAX_CONTENT_CHARS],
        )
        agent = Agent(self._fast_model, output_type=ContactsResult, instructions=system_msg)
        result = await self._run(agent, user_msg)
        return result.contacts

    async def generate_company_profile(
        self,
        page_content: str,
    ) -> CompanyProfile:
        system_msg, user_msg, _ = self._prompts.build_company_profile(
            page_content=page_content[:MAX_PROFILE_CONTENT_CHARS],
        )
        agent = Agent(self._strong_model, output_type=CompanyProfile, instructions=system_msg)
        return await self._run(agent, user_msg)

    # ── Internal helpers ────────────────────────────────────────────────────

    async def _run(self, agent: Agent[Any, _T], user_msg: str) -> _T:
        """Run an agent with circuit breaker protection and usage tracking."""
        if not self._circuit_breaker.allow_request():
            raise ProviderUnavailableError(
                f"Circuit breaker open for {self.provider}",
                provider=self.provider,
            )

        try:
            result = await agent.run(user_msg)
        except Exception as exc:
            # Rate-limit errors (429) mean the service is healthy but throttling
            # us — don't count them as circuit-breaker failures.
            if _is_rate_limit(exc):
                raise ProviderUnavailableError(str(exc), provider=self.provider) from exc
            self._circuit_breaker.record_failure()
            raise ProviderUnavailableError(str(exc), provider=self.provider) from exc

        self._circuit_breaker.record_success()

        usage = result.usage()
        model_name = getattr(agent.model, "model_name", None) or self.provider
        _spawn_background(self._track_usage(usage, model_name))

        return result.output

    async def _track_usage(self, usage: RunUsage, model: str) -> None:
        """Insert a usage record into ``api_usage`` without blocking the caller."""
        try:
            input_tokens = usage.input_tokens or 0
            output_tokens = usage.output_tokens or 0
            costs = _TOKEN_COSTS.get(model, {})
            cost = (
                costs.get("input", Decimal("0")) * input_tokens
                + costs.get("output", Decimal("0")) * output_tokens
            )
            async with async_session_factory() as session:
                record = APIUsage(
                    provider=self.provider,
                    endpoint=model,
                    tokens_used=input_tokens + output_tokens,
                    cost_estimate=cost,
                )
                session.add(record)
                await session.commit()
        except Exception:
            logger.warning("usage_tracking_failed", provider=self.provider, model=model)
