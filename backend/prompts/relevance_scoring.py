"""Relevance scoring prompt — scores a signal 0-100 against the ICP and recommends action.

The system message is assembled from a static base template plus configurable
ICP criteria and company identity injected at runtime.  ICP criteria come from
the active ``ICPProfile`` in the database — no longer hardcoded.

Version: 3.0.0
"""

from __future__ import annotations

from prompts.config import CompanyIdentity, PromptConfigBundle

VERSION = "3.0.0"

# ---------------------------------------------------------------------------
# Static base — scoring guide, action definitions, rules
# ---------------------------------------------------------------------------

_SYSTEM_BASE = """\
You are a B2B sales intelligence analyst evaluating buying signals for {company_name}, \
{company_tagline}.

Score signal relevance (0-100) against this Ideal Customer Profile:
{icp_criteria}

Scoring guide:
- 75-100: Strong match — company squarely fits ICP on industry, size, and pain points → notify_immediate
- 50-74:  Moderate match — partial ICP fit or signal needs more context → notify_digest
- 25-49:  Weak match — borderline ICP fit or insufficient data → enrich_further
- 0-24:   Not relevant — outside ICP on multiple criteria → ignore

Rules:
- Score reflects BOTH signal strength AND ICP fit — both must be high to score 75+.
- Weigh industry fit and the presence of field service / frontline workers heavily.
- RECENCY: penalise signals >6 months old. Cap outdated content at score 24 (ignore).
- List up to 5 specific, actionable key factors that drove the score.
- Respond ONLY with valid JSON.\
"""


def build_system_message(
    company_identity: CompanyIdentity | None = None,
    icp_criteria: str | None = None,
) -> str:
    """Assemble the system message from base template + configurable parts."""
    defaults = PromptConfigBundle.defaults()
    identity = company_identity or defaults.company_identity
    criteria = icp_criteria if icp_criteria is not None else defaults.icp_criteria

    return _SYSTEM_BASE.format(
        company_name=identity.name,
        company_tagline=identity.tagline,
        icp_criteria=criteria,
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
            "company_context": "Cofely — Technical maintenance & facility services, 3000 employees, Netherlands",
            "icp_context": "Technical maintenance/service/installation companies, 100-5000 employees, Netherlands, with field service professionals",
            "content": "We starten een grootschalig programma om onze 1500 servicemonteurs te voorzien van een nieuw digitaal werkplatform.",
        },
        "output": {
            "relevance_score": 92,
            "action": "notify_immediate",
            "reasoning": "Large-scale digital platform initiative for 1500 field service professionals — perfectly aligned with fresk.digital's core proposition",
            "key_factors": [
                "1500 field service monteurs need new digital platform",
                "Explicit legacy system replacement initiative",
                "Technical maintenance industry — primary ICP segment",
                "Dutch company with 3000 employees in ICP size range",
                "Pain points match: duplicate work and reporting errors",
            ],
        },
    },
    {
        "input": {
            "signal_type": "hiring_surge",
            "company_context": "Bakkerij Van der Berg — Artisanal bakery chain, 30 employees, Gouda",
            "icp_context": "Technical maintenance/service/installation companies, 100-5000 employees, Netherlands, with field service professionals",
            "content": "We zoeken 3 nieuwe bakkers en een winkelmedewerker voor onze vestiging in Gouda.",
        },
        "output": {
            "relevance_score": 5,
            "action": "ignore",
            "reasoning": "Small bakery outside ICP on industry, size, and role type",
            "key_factors": [
                "Not a field service or technical industry",
                "30 employees well below ICP minimum",
                "Hiring for retail roles, not field professionals",
            ],
        },
    },
    {
        "input": {
            "signal_type": "technology_adoption",
            "company_context": "Nationale-Nederlanden — Insurance, 5000+ employees, The Hague",
            "icp_context": "Insurance companies with frontline knowledge workers, 100-5000+ employees, Netherlands",
            "content": "We implementeren een nieuw AI-gedreven platform voor onze schadebehandelaars om sneller en nauwkeuriger claims te verwerken.",
        },
        "output": {
            "relevance_score": 68,
            "action": "notify_digest",
            "reasoning": "Major Dutch insurer replacing legacy claims system with AI — strong fit but enterprise size may limit scope",
            "key_factors": [
                "Insurance industry — secondary ICP segment",
                "Legacy system replacement for frontline knowledge workers",
                "AI-driven platform matches our expertise",
                "Dutch HQ matches geography",
                "Enterprise size may limit engagement scope",
            ],
        },
    },
]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "relevance_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "action": {
            "type": "string",
            "enum": ["notify_immediate", "notify_digest", "enrich_further", "ignore"],
        },
        "reasoning": {"type": "string"},
        "key_factors": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
        },
    },
    "required": ["relevance_score", "action", "reasoning", "key_factors"],
}

def build_prompt(context: dict) -> str:
    """Build the user message for relevance scoring.

    Args:
        context: dict with keys ``content``, ``signal_type``, and optionally
            ``company_context``, ``icp_context``, and ``today_date``
            (ISO format string, e.g. "2026-03-27").

    Returns:
        Formatted user message string.
    """
    content = context.get("content", "")
    signal_type = context.get("signal_type") or "unknown"
    company_context = context.get("company_context") or "Unknown company"
    icp_context = context.get("icp_context") or "No ICP context provided"
    today_date = context.get("today_date") or ""
    date_line = f"Today's date: {today_date}\n" if today_date else ""
    return (
        f"{date_line}"
        f"Signal type: {signal_type}\n"
        f"Company: {company_context}\n"
        f"ICP: {icp_context}\n\n"
        f"Signal content:\n{content}\n\n"
        f"Score this signal and recommend an action. Respond with JSON only."
    )
