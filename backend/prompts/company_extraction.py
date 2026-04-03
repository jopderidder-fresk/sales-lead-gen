"""Company extraction prompt — extracts company records from search result text.

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
Extract company names and domains from search result text.

Rules:
- Extract every distinct company mentioned in a business context.
- Do NOT extract individuals, government agencies, or non-commercial organisations \
unless clearly a business.
- For domain: extract the primary web domain if clearly stated; otherwise null.
- For industry: infer from context if obvious; otherwise null.
- For description: one sentence focused on what the company does; null if unknown.
- Return an empty "companies" array if no companies are found.
- Respond ONLY with valid JSON.\
"""


def build_system_message(
    company_identity: CompanyIdentity | None = None,
) -> str:
    """Assemble the system message from base template + configurable parts."""
    defaults = PromptConfigBundle.defaults()
    identity = company_identity or defaults.company_identity
    return _SYSTEM_BASE.format(company_name=identity.name)


# Module-level constant built from defaults — backward-compatible.
SYSTEM_MESSAGE = build_system_message()


# ---------------------------------------------------------------------------
# Few-shot examples (kept for documentation and testing, not sent to LLM)
# ---------------------------------------------------------------------------

FEW_SHOT_EXAMPLES = [
    {
        "input": {
            "content": "Hoppenbrouwers Techniek (hoppenbrouwers.nl) is een van de grootste installatiebedrijven van Nederland. Kiwa (kiwa.com) is specialist in testing, inspection en certification.",
        },
        "output": {
            "companies": [
                {
                    "name": "Hoppenbrouwers Techniek",
                    "domain": "hoppenbrouwers.nl",
                    "industry": "Installation & Technical Services",
                    "description": "One of the largest installation companies in the Netherlands",
                },
                {
                    "name": "Kiwa",
                    "domain": "kiwa.com",
                    "industry": "Testing, Inspection & Certification",
                    "description": "Specialist in testing, inspection and certification services",
                },
            ]
        },
    },
    {
        "input": {
            "content": "Achmea (achmea.nl) is de grootste verzekeraar van Nederland. Lely (lely.com) ontwikkelt robotica voor de melkveehouderij.",
        },
        "output": {
            "companies": [
                {
                    "name": "Achmea",
                    "domain": "achmea.nl",
                    "industry": "Insurance",
                    "description": "Largest insurance company in the Netherlands",
                },
                {
                    "name": "Lely",
                    "domain": "lely.com",
                    "industry": "Agricultural Technology",
                    "description": "Develops robotics and automation solutions for dairy farming",
                },
            ]
        },
    },
    {
        "input": {"content": "No company names or business information present here."},
        "output": {"companies": []},
    },
]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "companies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "domain": {"type": ["string", "null"]},
                    "industry": {"type": ["string", "null"]},
                    "description": {"type": ["string", "null"]},
                },
                "required": ["name", "domain", "industry", "description"],
            },
        }
    },
    "required": ["companies"],
}

def build_prompt(context: dict) -> str:
    """Build the user message for company extraction.

    Args:
        context: dict with key ``content`` (search result text).

    Returns:
        Formatted user message string.
    """
    content = context.get("content", "")
    return (
        f"Extract all companies from the following search results:\n\n"
        f"{content}\n\n"
        f"Respond with JSON only."
    )
