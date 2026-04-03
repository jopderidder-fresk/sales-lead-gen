"""Contact extraction prompt — extracts contact records from team or about pages.

Decision-maker roles are configurable via the ``PromptConfigBundle``.

Version: 3.0.0
"""

from __future__ import annotations

from prompts.config import CompanyIdentity, PromptConfigBundle

VERSION = "3.0.0"

# ---------------------------------------------------------------------------
# Static base
# ---------------------------------------------------------------------------

_SYSTEM_BASE = """\
You are a B2B data extraction specialist working for {company_name}. \
Extract people and their contact information from company team or about pages.

Rules:
- Extract every named individual with a professional context.
- For title: extract exact job title if stated; infer from context if obvious; otherwise null.
- For email: only include clearly stated email addresses — do not guess or construct.
- For linkedin_url: only include full LinkedIn profile URLs (linkedin.com/in/...); do not guess.
- For is_decision_maker: set to true if the person's role matches one of these decision-making \
unit roles: {decision_maker_roles}. Set to false for all other roles.
- Exclude company descriptions, product information, and non-person content.
- Return an empty "contacts" array if no people are found.
- Respond ONLY with valid JSON.\
"""


def build_system_message(
    company_identity: CompanyIdentity | None = None,
    decision_maker_roles: list[str] | None = None,
) -> str:
    """Assemble the system message from base template + configurable parts."""
    defaults = PromptConfigBundle.defaults()
    identity = company_identity or defaults.company_identity
    roles = decision_maker_roles or defaults.decision_maker_roles
    return _SYSTEM_BASE.format(
        company_name=identity.name,
        decision_maker_roles=", ".join(roles),
    )


# Module-level constant built from defaults — backward-compatible.
SYSTEM_MESSAGE = build_system_message()


# ---------------------------------------------------------------------------
# Few-shot examples (kept for documentation and testing, not sent to LLM)
# ---------------------------------------------------------------------------

FEW_SHOT_EXAMPLES = [
    {
        "input": {
            "content": "Ons managementteam: Pieter van Dam — COO, pieter@strukton.nl | Marieke de Vries — Hoofd IT | Tom Bakker — Servicemonteur Coördinator | Lisa Jansen — Innovatiemanager https://linkedin.com/in/lisajansen",
        },
        "output": {
            "contacts": [
                {
                    "name": "Pieter van Dam",
                    "title": "COO",
                    "email": "pieter@strukton.nl",
                    "linkedin_url": None,
                    "is_decision_maker": True,
                },
                {
                    "name": "Marieke de Vries",
                    "title": "Hoofd IT",
                    "email": None,
                    "linkedin_url": None,
                    "is_decision_maker": True,
                },
                {
                    "name": "Tom Bakker",
                    "title": "Servicemonteur Coördinator",
                    "email": None,
                    "linkedin_url": None,
                    "is_decision_maker": False,
                },
                {
                    "name": "Lisa Jansen",
                    "title": "Innovatiemanager",
                    "email": None,
                    "linkedin_url": "https://linkedin.com/in/lisajansen",
                    "is_decision_maker": True,
                },
            ]
        },
    },
    {
        "input": {
            "content": "Directie: Jan de Groot (CEO) jan@kiwa.com en Sandra Vermeer (CDO) linkedin.com/in/sandravermeer"
        },
        "output": {
            "contacts": [
                {
                    "name": "Jan de Groot",
                    "title": "CEO",
                    "email": "jan@kiwa.com",
                    "linkedin_url": None,
                    "is_decision_maker": True,
                },
                {
                    "name": "Sandra Vermeer",
                    "title": "CDO",
                    "email": None,
                    "linkedin_url": None,
                    "is_decision_maker": True,
                },
            ]
        },
    },
    {
        "input": {"content": "Wij zijn een team van ervaren monteurs en technici die dagelijks in het veld staan."},
        "output": {"contacts": []},
    },
]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "contacts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "title": {"type": ["string", "null"]},
                    "email": {"type": ["string", "null"]},
                    "linkedin_url": {"type": ["string", "null"]},
                    "is_decision_maker": {"type": "boolean"},
                },
                "required": ["name", "title", "email", "linkedin_url", "is_decision_maker"],
            },
        }
    },
    "required": ["contacts"],
}

def build_prompt(context: dict) -> str:
    """Build the user message for contact extraction.

    Args:
        context: dict with key ``content`` (page text or markdown).

    Returns:
        Formatted user message string.
    """
    content = context.get("content", "")
    return (
        f"Extract all people and contact information from the following page:\n\n"
        f"{content}\n\n"
        f"Respond with JSON only."
    )
