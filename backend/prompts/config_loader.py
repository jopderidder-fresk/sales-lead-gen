"""Load configurable prompt parts from the database.

The main entry point is :func:`load_prompt_config`, which returns a
:class:`~prompts.config.PromptConfigBundle` hydrated from ``prompt_configs``
rows and the active ``ICPProfile``.  Missing DB rows fall back to hardcoded
defaults so the system works on first boot or in tests.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.icp_profile import ICPProfile
from app.models.prompt_config import PromptConfig

from prompts.config import (
    CompanyIdentity,
    PromptConfigBundle,
    SignalTypeDefinition,
)


async def load_prompt_config(session: AsyncSession) -> PromptConfigBundle:
    """Build a :class:`PromptConfigBundle` from DB state.

    1. Load all ``PromptConfig`` rows.
    2. Load the active ``ICPProfile`` and format it as ICP criteria text.
    3. Merge with :meth:`PromptConfigBundle.defaults` for any missing keys.
    """
    defaults = PromptConfigBundle.defaults()

    # -- Load prompt_configs rows -----------------------------------------
    result = await session.execute(select(PromptConfig))
    rows: dict[str, list | dict] = {row.config_key: row.config_value for row in result.scalars().all()}

    # Signal type definitions
    signal_types = defaults.signal_types
    raw_signals = rows.get("signal_type_definitions")
    if isinstance(raw_signals, list) and raw_signals:
        signal_types = [
            SignalTypeDefinition(
                key=s["key"],
                description=s["description"],
                relevance_hints=s.get("relevance_hints"),
            )
            for s in raw_signals
            if isinstance(s, dict) and "key" in s and "description" in s
        ]

    # Company identity
    company_identity = defaults.company_identity
    raw_identity = rows.get("company_identity")
    if isinstance(raw_identity, dict) and "name" in raw_identity and "tagline" in raw_identity:
        company_identity = CompanyIdentity(
            name=raw_identity["name"],
            tagline=raw_identity["tagline"],
        )

    # Decision-maker roles
    decision_maker_roles = defaults.decision_maker_roles
    raw_roles = rows.get("decision_maker_roles")
    if isinstance(raw_roles, list) and raw_roles:
        decision_maker_roles = [str(r) for r in raw_roles]

    # -- Load ICP criteria from active profile ----------------------------
    icp_criteria = await _build_icp_criteria(session)
    if not icp_criteria:
        icp_criteria = defaults.icp_criteria

    return PromptConfigBundle(
        signal_types=signal_types,
        company_identity=company_identity,
        decision_maker_roles=decision_maker_roles,
        icp_criteria=icp_criteria,
    )


async def _build_icp_criteria(session: AsyncSession) -> str:
    """Format the active ICPProfile as structured criteria text for prompts."""
    result = await session.execute(
        select(ICPProfile).where(ICPProfile.is_active.is_(True)).limit(1)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        return ""

    lines: list[str] = []

    if profile.industry_filter:
        industries = profile.industry_filter if isinstance(profile.industry_filter, list) else []
        if industries:
            lines.append(f"Industry fit: {', '.join(industries)}")

    if profile.size_filter:
        sf = profile.size_filter
        min_emp = sf.get("min_employees")
        max_emp = sf.get("max_employees")
        if min_emp or max_emp:
            lines.append(f"Company size: {min_emp or '?'}-{max_emp or '?'} employees")

    if profile.geo_filter:
        countries = profile.geo_filter.get("countries", [])
        if countries:
            lines.append(f"Geography: {', '.join(countries)}")

    if profile.tech_filter:
        techs = profile.tech_filter if isinstance(profile.tech_filter, list) else []
        if techs:
            lines.append(f"Key technologies: {', '.join(techs)}")

    if profile.negative_filters:
        excluded = profile.negative_filters.get("excluded_industries", [])
        if excluded:
            lines.append(f"Exclude: {', '.join(excluded)}")

    # Number dynamically so gaps don't appear when filters are missing.
    numbered = [f"{i}. {line}" for i, line in enumerate(lines, 1)]
    return "\n".join(numbered)
