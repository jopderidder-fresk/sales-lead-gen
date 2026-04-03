"""Action recommendation prompt — recommends specific outreach actions for a scored signal.

Not actively used in the pipeline (action is determined deterministically),
but follows the same configurable pattern for consistency.

Version: 3.0.0
"""

from __future__ import annotations

from prompts.config import CompanyIdentity, PromptConfigBundle

VERSION = "3.0.0"

# ---------------------------------------------------------------------------
# Static base
# ---------------------------------------------------------------------------

_SYSTEM_BASE = """\
You are a B2B sales strategist recommending outreach actions for {company_name}, \
{company_tagline}.

Given a scored buying signal, recommend a concrete next action with personalisation hooks.

Rules:
- Actions must be specific and actionable, not generic advice.
- Include 2-3 concrete personalisation angles the rep can reference, tied to the \
company's specific pain points and our relevant expertise.
- Match the outreach channel to urgency: linkedin_dm (low urgency), email (medium), phone (high).
- Frame outreach around understanding their operational challenges, not selling a product.
- Respond ONLY with valid JSON.\
"""


def build_system_message(
    company_identity: CompanyIdentity | None = None,
) -> str:
    """Assemble the system message from base template + configurable parts."""
    defaults = PromptConfigBundle.defaults()
    identity = company_identity or defaults.company_identity
    return _SYSTEM_BASE.format(
        company_name=identity.name,
        company_tagline=identity.tagline,
    )


# Module-level constant built from defaults — backward-compatible.
SYSTEM_MESSAGE = build_system_message()


# ---------------------------------------------------------------------------
# Few-shot examples (kept for documentation and testing, not sent to LLM)
# ---------------------------------------------------------------------------

FEW_SHOT_EXAMPLES = [
    {
        "input": {
            "signal_type": "digital_transformation",
            "relevance_score": 91,
            "company_context": "Strukton Worksphere — Technical maintenance & facility services, 2000 employees, Utrecht",
            "key_factors": [
                "Digitalisation programme for field service monteurs",
                "Legacy system replacement",
                "2000 employees in ICP size range",
            ],
        },
        "output": {
            "recommended_action": "Bel de COO of Hoofd Operations om een kennismakingsgesprek in te plannen over hun digitaliseringsprogramma",
            "urgency": "high",
            "personalisation_hooks": [
                "Refereer aan hun aangekondigde digitaliseringsprogramma voor monteurs",
                "Deel een voorbeeld van hoe we vergelijkbare field service bedrijven hebben geholpen",
                "Bied een vrijblijvende Discover-sessie aan om hun monteur-journey in kaart te brengen",
            ],
            "suggested_channel": "phone",
            "follow_up_trigger": "Bij geen reactie binnen 2 dagen opvolgen via LinkedIn DM aan de CIO/CDO",
        },
    },
    {
        "input": {
            "signal_type": "workforce_challenge",
            "relevance_score": 78,
            "company_context": "Kone BV — Lift installation & maintenance, 800 employees, Netherlands",
            "key_factors": [
                "Experienced lift monteur shortage",
                "Knowledge retention challenge due to aging workforce",
                "Dutch operations match geography",
            ],
        },
        "output": {
            "recommended_action": "Stuur een gepersonaliseerde LinkedIn DM aan de Hoofd Operations over kennisbehoud bij vergrijzing",
            "urgency": "high",
            "personalisation_hooks": [
                "Benoem het personeelstekort aan ervaren liftmonteurs en kennisbehoud-uitdaging",
                "Laat zien hoe AI-gedreven tools ervaringskennis kunnen vastleggen en ontsluiten",
                "Verwijs naar onze ervaring met kennisplatforms voor technische professionals",
            ],
            "suggested_channel": "linkedin_dm",
            "follow_up_trigger": "Bij geen reactie binnen 4 dagen opvolgen met email en case study",
        },
    },
    {
        "input": {
            "signal_type": "no_signal",
            "relevance_score": 8,
            "company_context": "Lokaal Loodgietersbedrijf — Plumbing services, 5 employees",
            "key_factors": ["Below minimum ICP size", "No field service complexity"],
        },
        "output": {
            "recommended_action": "Geen outreach aanbevolen — bedrijf valt buiten ICP qua omvang",
            "urgency": "low",
            "personalisation_hooks": [],
            "suggested_channel": "email",
            "follow_up_trigger": "Herbeoordeel als een relevant signaal verschijnt in de komende 90 dagen",
        },
    },
]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "recommended_action": {"type": "string"},
        "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
        "personalisation_hooks": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
        },
        "suggested_channel": {
            "type": "string",
            "enum": ["linkedin_dm", "email", "phone"],
        },
        "follow_up_trigger": {"type": "string"},
    },
    "required": [
        "recommended_action",
        "urgency",
        "personalisation_hooks",
        "suggested_channel",
        "follow_up_trigger",
    ],
}

def build_prompt(context: dict) -> str:
    """Build the user message for action recommendation.

    Args:
        context: dict with keys ``signal_type``, ``relevance_score``,
            ``company_context``, and optionally ``key_factors`` (list of strings).

    Returns:
        Formatted user message string.
    """
    key_factors = context.get("key_factors", [])
    if isinstance(key_factors, list):
        key_factors_str = "; ".join(key_factors) if key_factors else "Not specified"
    else:
        key_factors_str = str(key_factors)

    signal_type = context.get("signal_type") or "unknown"
    relevance_score = context.get("relevance_score", 0)
    company_context = context.get("company_context") or "Unknown company"
    return (
        f"Signal type: {signal_type}\n"
        f"Relevance score: {relevance_score}/100\n"
        f"Company: {company_context}\n"
        f"Key signal factors: {key_factors_str}\n\n"
        f"Recommend a specific outreach action. Respond with JSON only."
    )
