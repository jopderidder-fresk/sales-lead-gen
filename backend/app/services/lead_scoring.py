"""Lead Scoring Framework — composite 0-100 score per company.

Calculates a weighted score from four dimensions:

- **ICP Fit** (30%) — how well the company matches the active ICP profile.
- **Signal Strength** (35%) — aggregated from LLM-scored signals with recency decay.
- **Contact Quality** (20%) — verified contacts, decision-maker coverage.
- **Recency** (15%) — time since latest signal or enrichment activity.

Usage::

    service = LeadScoringService()
    score = await service.score_company(company_id, session)
    await service.score_all(session)
"""

from __future__ import annotations

import math
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.utils import utcnow
from app.models.company import Company
from app.models.contact import Contact
from app.models.enums import EmailStatus, SignalType
from app.models.icp_profile import ICPProfile
from app.models.signal import Signal

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Weight configuration
# ---------------------------------------------------------------------------

WEIGHT_ICP_FIT = 0.30
WEIGHT_SIGNAL_STRENGTH = 0.35
WEIGHT_CONTACT_QUALITY = 0.20
WEIGHT_RECENCY = 0.15

# Decision-maker title keywords (case-insensitive partial match)
_DECISION_MAKER_KEYWORDS = {
    "ceo", "cto", "cio", "cfo", "coo", "cmo", "vp", "vice president",
    "director", "head of", "chief", "founder", "owner", "partner",
    "managing", "president",
}

# Recency decay: signals older than this many days contribute 0 to the recency dimension
_RECENCY_MAX_DAYS = 90
# Half-life for signal recency decay (days)
_RECENCY_HALF_LIFE = 14.0


class ScoreBreakdown(TypedDict):
    icp_fit: float
    signal_strength: float
    contact_quality: float
    recency: float


class ScoringResult(TypedDict):
    lead_score: float
    breakdown: ScoreBreakdown


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class LeadScoringService:
    """Stateless service that computes lead scores from database state."""

    async def score_company(
        self,
        company_id: int,
        session: AsyncSession,
    ) -> ScoringResult | None:
        """Calculate and persist the lead score for a single company.

        Returns the result dict or ``None`` if the company doesn't exist.
        """
        company = await self._load_company(company_id, session)
        if company is None:
            logger.warning("lead_scoring.company_not_found", company_id=company_id)
            return None

        icp_fit = await self._calc_icp_fit(company, session)
        signal_strength = await self._calc_signal_strength(company_id, session)
        contact_quality = await self._calc_contact_quality(company_id, session)
        recency = await self._calc_recency(company_id, session)

        lead_score = (
            WEIGHT_ICP_FIT * icp_fit
            + WEIGHT_SIGNAL_STRENGTH * signal_strength
            + WEIGHT_CONTACT_QUALITY * contact_quality
            + WEIGHT_RECENCY * recency
        )
        lead_score = round(min(100.0, max(0.0, lead_score)), 2)

        breakdown: ScoreBreakdown = {
            "icp_fit": round(icp_fit, 2),
            "signal_strength": round(signal_strength, 2),
            "contact_quality": round(contact_quality, 2),
            "recency": round(recency, 2),
        }

        now = utcnow()
        company.lead_score = lead_score
        company.score_breakdown = breakdown  # type: ignore[assignment]
        company.score_updated_at = now
        await session.commit()

        logger.info(
            "lead_scoring.scored",
            company_id=company_id,
            lead_score=lead_score,
            breakdown=breakdown,
        )

        return {"lead_score": lead_score, "breakdown": breakdown}

    async def score_all(
        self,
        session: AsyncSession,
        *,
        batch_size: int = 100,
    ) -> int:
        """Recalculate lead scores for all non-archived companies.

        Returns the number of companies scored.
        """
        from app.models.enums import CompanyStatus

        result = await session.execute(
            select(Company.id).where(Company.status != CompanyStatus.ARCHIVED)
        )
        company_ids = list(result.scalars().all())

        if not company_ids:
            logger.debug("lead_scoring.no_companies")
            return 0

        logger.info("lead_scoring.batch_start", total=len(company_ids))
        scored = 0

        for company_id in company_ids:
            try:
                await self.score_company(company_id, session)
                scored += 1
            except Exception:
                logger.exception(
                    "lead_scoring.score_failed",
                    company_id=company_id,
                )

        logger.info("lead_scoring.batch_done", scored=scored, total=len(company_ids))
        return scored

    # ── Dimension calculators ────────────────────────────────────────────

    @staticmethod
    async def _calc_icp_fit(company: Company, session: AsyncSession) -> float:
        """Score 0-100 based on how well the company matches the active ICP profile.

        Uses the existing icp_score if set, otherwise estimates from ICP filters.
        """
        # If discovery already computed an ICP score, use it directly
        if company.icp_score is not None:
            return min(100.0, max(0.0, company.icp_score))

        # Otherwise, compute a basic match against the active ICP profile
        result = await session.execute(
            select(ICPProfile).where(ICPProfile.is_active.is_(True)).limit(1)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            return 50.0  # Neutral score when no ICP is configured

        score = 0.0
        checks = 0

        # Industry match
        if profile.industry_filter and company.industry:
            industries = (
                profile.industry_filter
                if isinstance(profile.industry_filter, list)
                else []
            )
            if industries:
                checks += 1
                company_ind = company.industry.lower()
                if any(ind.lower() in company_ind or company_ind in ind.lower() for ind in industries):
                    score += 100.0

        # Geography match
        if profile.geo_filter and company.location:
            countries = profile.geo_filter.get("countries", []) if isinstance(profile.geo_filter, dict) else []
            if countries:
                checks += 1
                loc_lower = company.location.lower()
                if any(c.lower() in loc_lower for c in countries):
                    score += 100.0

        # Negative filters
        if profile.negative_filters and company.industry:
            excluded = (
                profile.negative_filters.get("excluded_industries", [])
                if isinstance(profile.negative_filters, dict)
                else []
            )
            if excluded:
                company_ind = company.industry.lower()
                if any(ex.lower() in company_ind for ex in excluded):
                    return 0.0  # Hard disqualify

        if checks == 0:
            return 50.0
        return score / checks

    @staticmethod
    async def _calc_signal_strength(company_id: int, session: AsyncSession) -> float:
        """Score 0-100 based on signal relevance scores with recency weighting.

        Recent, high-relevance signals contribute more. Uses exponential decay.
        """
        now = utcnow()

        result = await session.execute(
            select(Signal.relevance_score, Signal.created_at, Signal.signal_type).where(
                Signal.company_id == company_id,
                Signal.is_processed.is_(True),
                Signal.signal_type != SignalType.NO_SIGNAL,
            )
        )
        signals = result.all()

        if not signals:
            return 0.0

        weighted_sum = 0.0
        weight_total = 0.0

        for relevance, created_at, _signal_type in signals:
            if relevance is None:
                continue

            # Age in days (handle both naive and aware datetimes)
            if created_at.tzinfo is None:
                age_days = (now.replace(tzinfo=None) - created_at).total_seconds() / 86400
            else:
                age_days = (now - created_at).total_seconds() / 86400

            if age_days > _RECENCY_MAX_DAYS:
                continue

            # Exponential decay weight
            decay = math.exp(-0.693 * age_days / _RECENCY_HALF_LIFE)
            weighted_sum += relevance * decay
            weight_total += decay

        if weight_total == 0:
            return 0.0

        return min(100.0, weighted_sum / weight_total)

    @staticmethod
    async def _calc_contact_quality(company_id: int, session: AsyncSession) -> float:
        """Score 0-100 based on contact count, verification, and decision-maker coverage."""
        result = await session.execute(
            select(Contact.title, Contact.email, Contact.email_status).where(
                Contact.company_id == company_id
            )
        )
        contacts = result.all()

        if not contacts:
            return 0.0

        total = len(contacts)
        verified = 0
        has_email = 0
        decision_makers = 0

        for title, email, email_status in contacts:
            if email:
                has_email += 1
            if email_status == EmailStatus.VERIFIED:
                verified += 1
            if title:
                title_lower = title.lower()
                if any(kw in title_lower for kw in _DECISION_MAKER_KEYWORDS):
                    decision_makers += 1

        # Sub-scores (each 0-100)
        # Contact count: 1 contact = 20, 2 = 40, 3 = 60, 5+ = 100
        count_score = min(100.0, total * 20.0)

        # Email coverage
        email_score = (has_email / total * 100.0) if total > 0 else 0.0

        # Verification rate
        verify_score = (verified / has_email * 100.0) if has_email > 0 else 0.0

        # Decision-maker presence: at least 1 = 60, 2+ = 100
        dm_score = min(100.0, decision_makers * 60.0) if decision_makers > 0 else 0.0

        # Weighted combination of sub-scores
        return (
            count_score * 0.25
            + email_score * 0.25
            + verify_score * 0.25
            + dm_score * 0.25
        )

    @staticmethod
    async def _calc_recency(company_id: int, session: AsyncSession) -> float:
        """Score 0-100 based on how recently we have signal or contact activity."""
        now = utcnow()

        # Latest signal
        sig_result = await session.execute(
            select(func.max(Signal.created_at)).where(Signal.company_id == company_id)
        )
        latest_signal = sig_result.scalar_one()

        # Latest contact
        contact_result = await session.execute(
            select(func.max(Contact.created_at)).where(Contact.company_id == company_id)
        )
        latest_contact = contact_result.scalar_one()

        # Pick the most recent activity
        candidates = [d for d in [latest_signal, latest_contact] if d is not None]
        if not candidates:
            return 0.0

        latest = max(candidates)
        if latest.tzinfo is None:
            age_days = (now.replace(tzinfo=None) - latest).total_seconds() / 86400
        else:
            age_days = (now - latest).total_seconds() / 86400

        if age_days <= 0:
            return 100.0
        if age_days >= _RECENCY_MAX_DAYS:
            return 0.0

        # Linear decay from 100 to 0 over RECENCY_MAX_DAYS
        return max(0.0, 100.0 * (1.0 - age_days / _RECENCY_MAX_DAYS))

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    async def _load_company(company_id: int, session: AsyncSession) -> Company | None:
        result = await session.execute(
            select(Company).where(Company.id == company_id)
        )
        return result.scalar_one_or_none()
