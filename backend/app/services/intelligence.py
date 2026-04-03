"""LLM Intelligence Layer — three-stage signal processing pipeline.

Processes unanalyzed signals through:

1. **Pre-filter** — skip very short content or duplicate hashes (LLM decides relevance).
2. **Classification** (Haiku) — identify the signal type.
3. **Scoring** (Sonnet) — score relevance 0-100 and recommend an action.

Usage::

    service = IntelligenceService()  # uses LLM_PROVIDER from .env
    result = await service.analyze(signal_id, session)
    await service.process_queue(session, daily_budget=5.00)
    await service.close()
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.utils import today_start_utc
from app.models.api_usage import APIUsage
from app.models.enums import SignalAction, SignalType
from app.models.icp_profile import ICPProfile
from app.models.signal import Signal
from app.services.api.errors import APIError
from app.services.llm import LLMService, create_llm_client

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Pre-filter constants
# ---------------------------------------------------------------------------

# Aligned with minimum markdown length used when creating signals from crawls.
_MIN_CONTENT_LENGTH = 50

# Score → action mapping (deterministic, no LLM needed).
_ACTION_THRESHOLDS: list[tuple[int, SignalAction]] = [
    (75, SignalAction.NOTIFY_IMMEDIATE),
    (50, SignalAction.NOTIFY_DIGEST),
    (25, SignalAction.ENRICH_FURTHER),
    (0, SignalAction.IGNORE),
]


def _score_to_action(score: int) -> SignalAction:
    """Map a relevance score to an action using fixed thresholds."""
    for threshold, action in _ACTION_THRESHOLDS:
        if score >= threshold:
            return action
    return SignalAction.IGNORE


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class IntelligenceService:
    """Orchestrates the LLM signal-processing pipeline.

    Holds an ``LLMService`` and exposes ``analyze`` (single signal) and
    ``process_queue`` (batch) as the public API.
    """

    def __init__(self, llm_client: LLMService | None = None) -> None:
        self._llm: LLMService | None = llm_client
        self._llm_initialized = llm_client is not None

    async def _ensure_llm(self) -> None:
        """Lazily create the LLM client (reads keys from DB at runtime)."""
        if self._llm_initialized:
            return
        self._llm_initialized = True
        self._llm = await create_llm_client()

    async def close(self) -> None:
        if self._llm is not None:
            await self._llm.close()

    # ── Public API ──────────────────────────────────────────────────────────

    async def analyze(
        self,
        signal_id: int,
        session: AsyncSession,
    ) -> bool:
        """Run the full pipeline on a single signal.

        Returns ``True`` if the signal was processed (or skipped by pre-filter),
        ``False`` if the signal was not found.
        """
        await self._ensure_llm()
        signal = await self._load_signal(signal_id, session)
        if signal is None:
            logger.warning("signal_not_found", signal_id=signal_id)
            return False

        if signal.is_processed:
            logger.debug("signal_already_processed", signal_id=signal_id)
            return True

        content = signal.raw_markdown or ""

        # --- Pre-filter ---
        skip_reason = self._pre_filter(content, signal, session)
        if skip_reason:
            logger.info(
                "signal_skipped",
                signal_id=signal_id,
                reason=skip_reason,
            )
            signal.is_processed = True
            signal.signal_type = SignalType.NO_SIGNAL
            signal.action_taken = SignalAction.IGNORE
            await session.commit()
            return True

        # --- Check duplicate content hash ---
        if signal.raw_content_hash and await self._hash_already_processed(
            signal.raw_content_hash, signal.company_id, signal.id, session
        ):
            logger.info(
                "signal_skipped",
                signal_id=signal_id,
                reason="duplicate_content_hash",
            )
            signal.is_processed = True
            signal.signal_type = SignalType.NO_SIGNAL
            signal.action_taken = SignalAction.IGNORE
            await session.commit()
            return True

        # --- Build context strings ---
        company_context = self._build_company_context(signal.company)
        icp_context = await self._build_icp_context(session)

        if self._llm is None:
            logger.error("llm_not_available")
            return False

        # --- Stage 1: Classification ---
        classification = await self._llm.classify_signal(
            content=content,
            company_context=company_context,
        )
        try:
            signal.signal_type = SignalType(classification.signal_type)
        except ValueError:
            logger.warning(
                "signal_type_unknown",
                signal_id=signal_id,
                raw_type=classification.signal_type,
            )
            signal.signal_type = SignalType.OTHER
        logger.info(
            "signal_classified",
            signal_id=signal_id,
            signal_type=signal.signal_type,
            confidence=classification.confidence,
        )

        # If classified as no_signal, skip scoring.
        if signal.signal_type == SignalType.NO_SIGNAL:
            signal.relevance_score = 0.0
            signal.action_taken = SignalAction.IGNORE
            signal.llm_summary = classification.reasoning
            signal.is_processed = True
            await session.commit()
            return True

        # --- Stage 2: Scoring ---
        score_result = await self._llm.score_and_recommend(
            content=content,
            signal_type=classification.signal_type,
            company_context=company_context,
            icp_context=icp_context,
        )
        signal.relevance_score = float(score_result.relevance_score)
        signal.llm_summary = score_result.reasoning
        logger.info(
            "signal_scored",
            signal_id=signal_id,
            relevance_score=score_result.relevance_score,
        )

        # --- Stage 3: Action recommendation (deterministic) ---
        signal.action_taken = _score_to_action(score_result.relevance_score)
        signal.is_processed = True

        await session.commit()

        logger.info(
            "signal_processed",
            signal_id=signal_id,
            signal_type=signal.signal_type,
            relevance_score=signal.relevance_score,
            action_taken=signal.action_taken,
        )
        return True

    async def process_queue(
        self,
        session: AsyncSession,
        *,
        daily_budget: Decimal | None = None,
    ) -> int:
        """Process all unprocessed signals, oldest first.

        Args:
            session: Async database session.
            daily_budget: Optional daily spend cap (EUR). Processing pauses if exceeded.

        Returns:
            Number of signals processed.
        """
        if daily_budget is not None and await self._daily_budget_exceeded(session, daily_budget):
            logger.warning("daily_budget_exceeded", budget=str(daily_budget))
            return 0

        signal_ids = await self._pending_signal_ids(session)
        if not signal_ids:
            logger.debug("no_pending_signals")
            return 0

        logger.info("processing_signal_queue", count=len(signal_ids))
        processed = 0

        for signal_id in signal_ids:
            # Re-check budget before each signal (costs accumulate).
            if daily_budget is not None and await self._daily_budget_exceeded(
                session, daily_budget
            ):
                logger.warning(
                    "daily_budget_exceeded_mid_batch",
                    budget=str(daily_budget),
                    processed=processed,
                )
                break

            try:
                await self.analyze(signal_id, session)
                processed += 1
            except APIError as exc:
                logger.error(
                    "signal_analysis_failed",
                    signal_id=signal_id,
                    error=str(exc),
                    provider=exc.provider,
                )
                # Don't mark as processed — let retry pick it up.
                break  # Stop the batch on API errors to avoid burning quota.
            except Exception:
                logger.exception("signal_analysis_unexpected_error", signal_id=signal_id)
                break

        logger.info("signal_queue_done", processed=processed)
        return processed

    # ── Pre-filter ──────────────────────────────────────────────────────────

    @staticmethod
    def _pre_filter(content: str, signal: Signal, session: AsyncSession) -> str | None:
        """Return a skip reason string, or ``None`` if the signal should be processed."""
        if len(content) < _MIN_CONTENT_LENGTH:
            return "content_too_short"
        return None

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    async def _load_signal(signal_id: int, session: AsyncSession) -> Signal | None:
        from app.models.company import Company  # noqa: E402 — avoid circular import at module level

        result = await session.execute(
            select(Signal)
            .where(Signal.id == signal_id)
            .join(Company)
            .options()  # company loaded via join
        )
        signal = result.scalar_one_or_none()
        if signal is not None:
            # Eagerly access the company to avoid lazy-load in async context.
            await session.refresh(signal, ["company"])
        return signal

    @staticmethod
    async def _hash_already_processed(
        content_hash: str,
        company_id: int,
        exclude_signal_id: int,
        session: AsyncSession,
    ) -> bool:
        """Check if we already processed a signal with the same hash for this company."""
        result = await session.execute(
            select(Signal.id)
            .where(
                Signal.raw_content_hash == content_hash,
                Signal.company_id == company_id,
                Signal.is_processed.is_(True),
                Signal.id != exclude_signal_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    def _build_company_context(company: Any) -> str:
        """Build a short context string from a Company model."""
        parts = [company.name]
        if company.industry:
            parts.append(company.industry)
        if company.size:
            parts.append(company.size)
        if company.location:
            parts.append(company.location)
        return " — ".join(parts)

    @staticmethod
    async def _build_icp_context(session: AsyncSession) -> str:
        """Load the active ICP profile and format it as context for scoring."""
        result = await session.execute(
            select(ICPProfile).where(ICPProfile.is_active.is_(True)).limit(1)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            return ""

        parts = [f"ICP Profile: {profile.name}"]
        if profile.industry_filter:
            industries = (
                profile.industry_filter if isinstance(profile.industry_filter, list) else []
            )
            if industries:
                parts.append(f"Target industries: {', '.join(industries)}")
        if profile.size_filter:
            sf = profile.size_filter
            if sf.get("min_employees") or sf.get("max_employees"):
                parts.append(
                    f"Company size: {sf.get('min_employees', '?')}-{sf.get('max_employees', '?')} employees"
                )
        if profile.geo_filter:
            countries = profile.geo_filter.get("countries", [])
            if countries:
                parts.append(f"Geography: {', '.join(countries)}")
        if profile.tech_filter:
            techs = profile.tech_filter if isinstance(profile.tech_filter, list) else []
            if techs:
                parts.append(f"Technology stack: {', '.join(techs)}")
        if profile.negative_filters:
            excluded = profile.negative_filters.get("excluded_industries", [])
            if excluded:
                parts.append(f"Excluded industries: {', '.join(excluded)}")

        return ". ".join(parts)

    @staticmethod
    async def _pending_signal_ids(session: AsyncSession) -> list[int]:
        """Return IDs of unprocessed signals, oldest first."""
        result = await session.execute(
            select(Signal.id)
            .where(Signal.is_processed.is_(False))
            .order_by(Signal.created_at.asc())
        )
        return list(result.scalars().all())

    async def _daily_budget_exceeded(
        self,
        session: AsyncSession,
        budget: Decimal,
    ) -> bool:
        """Check if today's LLM spend has exceeded the budget."""
        if self._llm is None:
            return False
        today_start = today_start_utc()
        result = await session.execute(
            select(func.coalesce(func.sum(APIUsage.cost_estimate), 0)).where(
                APIUsage.provider == self._llm.provider,
                APIUsage.timestamp >= today_start,
            )
        )
        total = result.scalar_one()
        return Decimal(str(total)) >= budget


async def analyze_signal_ids_inline(signal_ids: list[int]) -> None:
    """Run the intelligence pipeline for new signals and queue action execution.

    Used after manual scrape or content import so classifications appear in the UI
    without waiting for the scheduled ``process_signal_queue`` task.
    Analyzes up to 3 signals concurrently.
    """
    if not signal_ids:
        return

    import asyncio

    from app.core.database import async_session_factory
    from app.tasks.integrations import execute_action

    service = IntelligenceService()
    sem = asyncio.Semaphore(3)

    async def _analyze_one(signal_id: int) -> bool:
        async with sem, async_session_factory() as session:
            try:
                await service.analyze(signal_id, session)
                return True
            except APIError as exc:
                logger.error(
                    "signal_analysis_failed",
                    signal_id=signal_id,
                    error=str(exc),
                    provider=exc.provider,
                )
                return False
            except Exception:
                logger.exception(
                    "signal_analysis_unexpected_error",
                    signal_id=signal_id,
                )
                return False

    try:
        results = await asyncio.gather(*[_analyze_one(sid) for sid in signal_ids])
    finally:
        await service.close()

    for signal_id, success in zip(signal_ids, results):
        if success:
            execute_action.delay(signal_id)
