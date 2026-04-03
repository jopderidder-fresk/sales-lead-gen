"""Unit tests for LLMService (pydantic-ai based).

Tests the service layer that wraps pydantic-ai agents with circuit breaker
protection and usage tracking.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.api.errors import ProviderUnavailableError
from app.services.llm import (
    ExtractedCompany,
    ExtractedContact,
    LLMService,
    ScoreAndRecommendation,
    SignalClassification,
)
from app.services.llm.base import CompaniesResult, ContactsResult
from pydantic_ai.usage import RunUsage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service() -> LLMService:
    """Create an LLMService with a mock model."""
    return LLMService(
        fast_model=MagicMock(),
        strong_model=MagicMock(),
        provider="test",
    )


def _mock_agent_result(output, *, input_tokens: int = 100, output_tokens: int = 50):
    """Build a mock AgentRunResult."""
    result = MagicMock()
    result.output = output
    result.usage.return_value = RunUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        requests=1,
    )
    return result


# ---------------------------------------------------------------------------
# classify_signal
# ---------------------------------------------------------------------------


class TestClassifySignal:
    @pytest.mark.asyncio
    async def test_returns_classification(self) -> None:
        service = _make_service()
        expected = SignalClassification(
            signal_type="hiring_surge",
            confidence=0.88,
            reasoning="12 engineering roles posted",
        )

        with patch("app.services.llm.client.Agent") as MockAgent:
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value=_mock_agent_result(expected))
            MockAgent.return_value = mock_agent

            with patch("app.services.llm.client._spawn_background"):
                result = await service.classify_signal("We're hiring 10 engineers", "Acme — SaaS")

        assert isinstance(result, SignalClassification)
        assert result.signal_type == "hiring_surge"
        assert result.confidence == pytest.approx(0.88)

    @pytest.mark.asyncio
    async def test_uses_fast_model(self) -> None:
        service = _make_service()
        expected = SignalClassification(
            signal_type="no_signal", confidence=0.5, reasoning="nothing"
        )

        with patch("app.services.llm.client.Agent") as MockAgent:
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value=_mock_agent_result(expected))
            MockAgent.return_value = mock_agent

            with patch("app.services.llm.client._spawn_background"):
                await service.classify_signal("content")

        MockAgent.assert_called_once()
        call_args = MockAgent.call_args
        assert call_args[0][0] is service._fast_model


# ---------------------------------------------------------------------------
# score_and_recommend
# ---------------------------------------------------------------------------


class TestScoreAndRecommend:
    @pytest.mark.asyncio
    async def test_returns_score_and_action(self) -> None:
        service = _make_service()
        expected = ScoreAndRecommendation(
            relevance_score=82,
            action="notify_immediate",
            reasoning="Strong ICP match",
            key_factors=["50+ hires", "matches size range"],
        )

        with patch("app.services.llm.client.Agent") as MockAgent:
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value=_mock_agent_result(expected))
            MockAgent.return_value = mock_agent

            with patch("app.services.llm.client._spawn_background"):
                result = await service.score_and_recommend(
                    "content", "hiring_surge", "Acme Corp", "SaaS 50-200"
                )

        assert isinstance(result, ScoreAndRecommendation)
        assert result.relevance_score == 82
        assert result.action == "notify_immediate"
        assert len(result.key_factors) == 2

    @pytest.mark.asyncio
    async def test_uses_strong_model(self) -> None:
        service = _make_service()
        expected = ScoreAndRecommendation(
            relevance_score=30, action="enrich_further", reasoning="ok", key_factors=[]
        )

        with patch("app.services.llm.client.Agent") as MockAgent:
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value=_mock_agent_result(expected))
            MockAgent.return_value = mock_agent

            with patch("app.services.llm.client._spawn_background"):
                await service.score_and_recommend("content", "expansion")

        MockAgent.assert_called_once()
        call_args = MockAgent.call_args
        assert call_args[0][0] is service._strong_model


# ---------------------------------------------------------------------------
# extract_companies
# ---------------------------------------------------------------------------


class TestExtractCompanies:
    @pytest.mark.asyncio
    async def test_returns_company_list(self) -> None:
        service = _make_service()
        expected = CompaniesResult(
            companies=[
                ExtractedCompany(name="Acme Corp", domain="acme.com", industry="SaaS"),
                ExtractedCompany(name="Beta Inc", domain="beta.io"),
            ]
        )

        with patch("app.services.llm.client.Agent") as MockAgent:
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value=_mock_agent_result(expected))
            MockAgent.return_value = mock_agent

            with patch("app.services.llm.client._spawn_background"):
                results = await service.extract_companies("search results text")

        assert len(results) == 2
        assert all(isinstance(r, ExtractedCompany) for r in results)
        assert results[0].name == "Acme Corp"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_companies(self) -> None:
        service = _make_service()
        expected = CompaniesResult(companies=[])

        with patch("app.services.llm.client.Agent") as MockAgent:
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value=_mock_agent_result(expected))
            MockAgent.return_value = mock_agent

            with patch("app.services.llm.client._spawn_background"):
                results = await service.extract_companies("irrelevant content")

        assert results == []


# ---------------------------------------------------------------------------
# extract_contacts
# ---------------------------------------------------------------------------


class TestExtractContacts:
    @pytest.mark.asyncio
    async def test_returns_contact_list(self) -> None:
        service = _make_service()
        expected = ContactsResult(
            contacts=[
                ExtractedContact(
                    name="Jane Doe",
                    title="CTO",
                    email="jane@acme.com",
                    linkedin_url="https://linkedin.com/in/janedoe",
                ),
                ExtractedContact(name="John Smith", title="VP Engineering"),
            ]
        )

        with patch("app.services.llm.client.Agent") as MockAgent:
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value=_mock_agent_result(expected))
            MockAgent.return_value = mock_agent

            with patch("app.services.llm.client._spawn_background"):
                results = await service.extract_contacts("team page content")

        assert len(results) == 2
        assert all(isinstance(r, ExtractedContact) for r in results)
        assert results[0].name == "Jane Doe"
        assert results[0].email == "jane@acme.com"
        assert results[1].email is None


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_opens_after_failures(self) -> None:
        service = _make_service()

        with patch("app.services.llm.client.Agent") as MockAgent:
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(side_effect=Exception("provider down"))
            MockAgent.return_value = mock_agent

            for _ in range(service._circuit_breaker.failure_threshold):
                with pytest.raises(ProviderUnavailableError):
                    await service.classify_signal("content")

            with pytest.raises(ProviderUnavailableError, match="Circuit breaker open"):
                await service.classify_signal("content")


# ---------------------------------------------------------------------------
# Usage tracking
# ---------------------------------------------------------------------------


class TestUsageTracking:
    @pytest.mark.asyncio
    async def test_track_usage_logs_tokens_and_cost(self) -> None:
        service = _make_service()
        service.provider = "claude"
        usage = RunUsage(input_tokens=200, output_tokens=100, requests=1)

        with patch("app.services.llm.client.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = mock_session

            await service._track_usage(usage, "claude-haiku-4-5-20251001")

            mock_session.add.assert_called_once()
            usage_record = mock_session.add.call_args[0][0]
            assert usage_record.provider == "claude"
            assert usage_record.endpoint == "claude-haiku-4-5-20251001"
            assert usage_record.tokens_used == 300

            expected_cost = Decimal("200") * Decimal("0.00000025") + Decimal("100") * Decimal(
                "0.00000125"
            )
            assert usage_record.cost_estimate == expected_cost

    @pytest.mark.asyncio
    async def test_track_usage_silently_ignores_errors(self) -> None:
        service = _make_service()

        with patch(
            "app.services.llm.client.async_session_factory", side_effect=Exception("db down")
        ):
            await service._track_usage(
                RunUsage(input_tokens=100, output_tokens=50, requests=1),
                "some-model",
            )
