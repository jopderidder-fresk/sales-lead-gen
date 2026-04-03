"""Prompt configuration bundle — holds all configurable prompt parts.

The ``PromptConfigBundle`` is the single object that ``PromptManager`` needs
to assemble final system messages.  It can be built from DB records via
``config_loader.load_prompt_config`` or from hardcoded defaults when no DB
is available (tests, first boot).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SignalTypeDefinition:
    """One configurable signal type shown in the classification prompt."""

    key: str
    """Enum value, e.g. ``"hiring_surge"``."""

    description: str
    """One-line description used in the system message."""

    relevance_hints: str | None = None
    """Optional hint about why this signal is relevant to the ICP."""


@dataclass(frozen=True)
class CompanyIdentity:
    """Who 'we' are in prompts."""

    name: str
    tagline: str


# -- Defaults ----------------------------------------------------------------
# Extracted from the current hardcoded prompts so the system works without DB.

_DEFAULT_SIGNAL_TYPES: list[SignalTypeDefinition] = [
    SignalTypeDefinition(
        key="hiring_surge",
        description="Multiple open roles for field service professionals (monteurs, engineers, inspecteurs, service technici, planners) or rapid headcount growth in operations",
        relevance_hints="Look for monteurs, engineers, inspecteurs, werkvoorbereiders, planners",
    ),
    SignalTypeDefinition(
        key="technology_adoption",
        description="Migrating to or adopting new operational systems (ERP, CRM, FSM), cloud infrastructure, IoT platforms, or major tooling changes",
    ),
    SignalTypeDefinition(
        key="digital_transformation",
        description="Announcing digital transformation initiatives, innovation programmes, operational excellence projects, legacy system replacements, or AI/data strategy",
    ),
    SignalTypeDefinition(
        key="workforce_challenge",
        description="Mentions of personnel shortages, aging workforce, knowledge retention issues, difficulty finding qualified technicians/monteurs, or high employee turnover",
    ),
    SignalTypeDefinition(
        key="funding_round",
        description="Investment, acquisition, or capital announcement enabling growth",
    ),
    SignalTypeDefinition(
        key="leadership_change",
        description="New CIO, CDO, COO, or VP Operations/IT/Innovation appointment or departure",
    ),
    SignalTypeDefinition(
        key="expansion",
        description="New offices, service regions, entering new markets or geographies",
    ),
    SignalTypeDefinition(
        key="partnership",
        description="Strategic partnerships, integrations, or joint ventures with technology providers",
    ),
    SignalTypeDefinition(
        key="product_launch",
        description="New product, service proposition, or major feature release",
    ),
    SignalTypeDefinition(
        key="no_signal",
        description="Content does not indicate buying intent (e.g. team events, culture posts, generic news)",
    ),
]

_DEFAULT_COMPANY_IDENTITY = CompanyIdentity(
    name="fresk.digital",
    tagline="a digital product studio that builds intelligent tools for field service professionals and frontline knowledge workers",
)

_DEFAULT_DECISION_MAKER_ROLES: list[str] = [
    "COO",
    "CIO",
    "CDO",
    "CTO",
    "CEO",
    "VP Operations",
    "VP IT",
    "VP Digital",
    "VP Innovation",
    "Director Operations",
    "Director IT",
    "Director Digital",
    "Director Innovation",
    "Hoofd Operations",
    "Hoofd IT",
    "Hoofd Digital",
    "Hoofd Innovation",
    "HR/Employee Experience",
    "Divisie-/Afdelingsmanager Operations",
    "Innovatiemanager",
]

_DEFAULT_ICP_CRITERIA = """\
1. Industry fit: Technical maintenance/service/installation, TIC (Testing, Inspection & \
Certification), insurance, or agricultural supply chain. Companies where field service \
professionals (monteurs, engineers, inspecteurs, installateurs) or frontline knowledge \
workers (planners, schadebehandelaars, kwaliteitscontroleurs) are core to operations.
2. Geography: Netherlands (primary), Western/Central Europe (secondary).
3. Pain points: Legacy systems (ERP/CRM/FSM not optimised for end users), paper-based \
or fragmented field processes, workforce shortages, aging workforce with undocumented \
knowledge, low adoption of digital tools, inefficient workflows.
4. Digital maturity: Digitally aware but struggling with execution — they know digital \
transformation is needed but lack in-house capability to build user-centric solutions.
5. Budget: Able to invest €40k-€250k+ in digital product development."""


@dataclass
class PromptConfigBundle:
    """All configurable prompt parts needed by ``PromptManager``."""

    signal_types: list[SignalTypeDefinition] = field(default_factory=list)
    company_identity: CompanyIdentity = field(default_factory=lambda: _DEFAULT_COMPANY_IDENTITY)
    decision_maker_roles: list[str] = field(default_factory=list)
    icp_criteria: str = ""

    @classmethod
    def defaults(cls) -> PromptConfigBundle:
        """Return hardcoded defaults matching the current prompt behavior."""
        return cls(
            signal_types=list(_DEFAULT_SIGNAL_TYPES),
            company_identity=_DEFAULT_COMPANY_IDENTITY,
            decision_maker_roles=list(_DEFAULT_DECISION_MAKER_ROLES),
            icp_criteria=_DEFAULT_ICP_CRITERIA,
        )

    # -- Formatting helpers used by prompt modules ---------------------------

    def format_signal_types_block(self) -> str:
        """Render signal types as a bulleted list for system messages."""
        lines: list[str] = []
        for st in self.signal_types:
            lines.append(f"- {st.key}: {st.description}")
        return "\n".join(lines)

    def format_decision_maker_roles(self) -> str:
        """Render decision-maker roles as a comma-separated list."""
        return ", ".join(self.decision_maker_roles)
