"""Signal classification prompt — classifies web content as a buying signal type.

The system message is assembled from a static base template plus configurable
signal type definitions and company identity injected at runtime.

Version: 3.0.0
"""

from __future__ import annotations

from prompts.config import CompanyIdentity, PromptConfigBundle, SignalTypeDefinition

VERSION = "3.0.0"

# ---------------------------------------------------------------------------
# Static base — rules and structure that rarely change
# ---------------------------------------------------------------------------

_SYSTEM_BASE = """\
You are a B2B sales intelligence analyst specialising in identifying buying signals \
from company web content. You work for {company_name}, {company_tagline}.

Classify the scraped web content as one of these signal types:
{signal_type_definitions}

Rules:
- Choose exactly ONE signal type.
- Confidence is your certainty (0.0 = uncertain, 1.0 = certain).
- If multiple signals are present, choose the strongest one.
- Prioritise signals indicating operational challenges, field service complexity, \
or digital maturity gaps.
- RECENCY: only classify as a signal if the event is within ~6 months of today's \
date. Older content = no_signal with reasoning noting the content is outdated.
- Respond ONLY with valid JSON.\
"""


def build_system_message(
    signal_types: list[SignalTypeDefinition] | None = None,
    company_identity: CompanyIdentity | None = None,
) -> str:
    """Assemble the system message from base template + configurable parts."""
    defaults = PromptConfigBundle.defaults()
    types = signal_types or defaults.signal_types
    identity = company_identity or defaults.company_identity

    type_lines: list[str] = []
    for st in types:
        type_lines.append(f"- {st.key}: {st.description}")

    return _SYSTEM_BASE.format(
        company_name=identity.name,
        company_tagline=identity.tagline,
        signal_type_definitions="\n".join(type_lines),
    )


# Module-level constant built from defaults — backward-compatible.
SYSTEM_MESSAGE = build_system_message()


# ---------------------------------------------------------------------------
# Few-shot examples (kept for documentation and testing, not sent to LLM)
# ---------------------------------------------------------------------------

FEW_SHOT_EXAMPLES = [
    {
        "input": {
            "company_context": "VanDerTech Installaties BV — HVAC installation & maintenance, 200-500 employees, Rotterdam",
            "content": "We zoeken 12 nieuwe servicemonteurs en 3 werkvoorbereiders om onze groeiende klantenportefeuille te bedienen.",
        },
        "output": {
            "signal_type": "hiring_surge",
            "confidence": 0.94,
            "reasoning": "15 open field service roles indicates rapid operational growth and potential need for better field service tooling",
        },
    },
    {
        "input": {
            "company_context": "InspectieGroep Nederland — Testing, Inspection & Certification, 100-300 employees",
            "content": "We starten een ambitieus digitaliseringsprogramma om onze inspectieprocessen te moderniseren. Papieren rapportages worden vervangen door digitale workflows.",
        },
        "output": {
            "signal_type": "digital_transformation",
            "confidence": 0.97,
            "reasoning": "Explicit digitisation programme replacing paper-based inspection processes with digital workflows",
        },
    },
    {
        "input": {
            "company_context": "Koelmax BV — Industrial cooling maintenance, 50-150 employees",
            "content": "Door de vergrijzing verliezen we jaarlijks ervaren monteurs. Hun kennis over complexe installaties dreigt verloren te gaan.",
        },
        "output": {
            "signal_type": "workforce_challenge",
            "confidence": 0.95,
            "reasoning": "Aging workforce causing knowledge drain of experienced field technicians — key pain point for knowledge capture",
        },
    },
    {
        "input": {
            "company_context": "Achmea — Insurance, 10000+ employees",
            "content": "We migreren onze schadebehandeling naar een nieuw cloud-based platform en implementeren AI-ondersteuning voor onze schadebehandelaars.",
        },
        "output": {
            "signal_type": "technology_adoption",
            "confidence": 0.93,
            "reasoning": "Migration to cloud platform with AI support for frontline claims handlers signals major technology investment",
        },
    },
    {
        "input": {
            "company_context": "Breman Installatietechniek — Building installations, 500+ employees",
            "content": "We hebben een nieuwe COO aangesteld, Marieke de Vries, die vanuit haar achtergrond in digitale transformatie onze operatie gaat moderniseren.",
        },
        "output": {
            "signal_type": "leadership_change",
            "confidence": 0.96,
            "reasoning": "New COO with digital transformation background signals upcoming operational modernisation initiatives",
        },
    },
    {
        "input": {
            "company_context": "TechniekBedrijf Jansen — Electrical installations, 80 employees",
            "content": "Ons bedrijfsuitje naar de Efteling was een groot succes! Fijn om het hele team weer eens buiten het werk te zien.",
        },
        "output": {
            "signal_type": "no_signal",
            "confidence": 0.97,
            "reasoning": "Company outing / culture content with no indicators of growth or buying intent",
        },
    },
]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "signal_type": {
            "type": "string",
            "enum": [
                "hiring_surge",
                "technology_adoption",
                "digital_transformation",
                "workforce_challenge",
                "funding_round",
                "leadership_change",
                "expansion",
                "partnership",
                "product_launch",
                "no_signal",
            ],
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "reasoning": {"type": "string"},
    },
    "required": ["signal_type", "confidence", "reasoning"],
}

def build_prompt(context: dict) -> str:
    """Build the user message for signal classification.

    Args:
        context: dict with keys ``content`` and optionally ``company_context``
            and ``today_date`` (ISO format string, e.g. "2026-03-27").

    Returns:
        Formatted user message string.
    """
    content = context.get("content", "")
    company_context = context.get("company_context") or "Unknown company"
    today_date = context.get("today_date") or ""
    date_line = f"Today's date: {today_date}\n" if today_date else ""
    return (
        f"{date_line}"
        f"Company context: {company_context}\n\n"
        f"Content to classify:\n{content}\n\n"
        f"Classify this content and respond with JSON only."
    )
