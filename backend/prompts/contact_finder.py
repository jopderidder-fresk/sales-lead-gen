"""Contact finder prompt — supplements Hunter with LLM-based contact discovery.

Used as a backup/supplement to Hunter.io in the enrichment waterfall. Receives
already-found contacts (from Hunter) so the LLM can avoid duplicates, plus
all available company context (profile, industry, location, scraped pages)
so it can identify decision-makers without making things up.

Version: 1.0.0
"""

from __future__ import annotations

import json

from prompts.config import CompanyIdentity, PromptConfigBundle

VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Static base
# ---------------------------------------------------------------------------

_SYSTEM_BASE = """\
You are a B2B contact research specialist working for {company_name}. \
Your task is to identify decision-makers at a target company that should be approached for sales outreach.

You will receive:
- Identity of the target company (name, domain, industry, location, profile).
- Optional content already scraped from the company's own website (team / about / leadership pages).
- A list of contacts that have ALREADY been found by another data provider (Hunter.io). You MUST NOT \
return any of these contacts again — they are duplicates. Use the list strictly for de-duplication.
- A list of decision-maker roles we are looking for.

Rules:
- Only return people you can justify from the provided context (scraped content, public company \
profile, or well-known leadership of the company that you have high confidence about). When in \
doubt, do not include the person.
- For email: only include the email if it is explicitly present in the provided content. Never \
guess, construct, or pattern-match an email (e.g. do NOT generate "first.last@domain.com"). \
If you do not have an explicit email from the content, set email to null. \
We verify emails downstream — a null email is fine, a fabricated email is not.
- For linkedin_url: only include full LinkedIn profile URLs (linkedin.com/in/...) that are \
explicitly stated in the content. Otherwise null.
- For title: extract the exact job title if stated; otherwise the closest accurate description. \
If you cannot determine a title, set it to null.
- For is_decision_maker: set to true only if the person's role matches one of these decision-maker \
roles: {decision_maker_roles}. Otherwise false. Prefer returning decision-makers.
- DEDUPLICATION: do not return any person whose name OR email matches an entry in the \
"already_found_contacts" list (case-insensitive name match, normalised email match). If the \
already_found_contacts list already covers all the decision-makers you can identify, return an \
empty array. Returning fewer high-quality contacts is better than padding with duplicates or guesses.
- Return an empty "contacts" array if you cannot confidently identify any new decision-makers \
beyond what was already found.
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
# Output schema (mirrors contact_extraction for downstream compatibility)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# User-message helpers
# ---------------------------------------------------------------------------

def _format_existing_contacts(existing: list[dict]) -> str:
    """Render the already-found contacts list as a compact JSON block."""
    if not existing:
        return "[] (no contacts found yet — return any decision-makers you can identify)"
    return json.dumps(existing, ensure_ascii=False, indent=2)


def _format_company_block(company: dict) -> str:
    """Render the structured company context as a readable block."""
    lines: list[str] = []
    for key in (
        "name",
        "domain",
        "industry",
        "size",
        "employee_count",
        "location",
        "city",
        "country",
        "website_url",
        "linkedin_url",
        "founded_year",
        "organization_type",
    ):
        value = company.get(key)
        if value is None or value == "":
            continue
        lines.append(f"- {key}: {value}")

    profile = company.get("company_info") or {}
    if isinstance(profile, dict) and profile:
        lines.append("- profile:")
        for pkey in (
            "summary",
            "products_services",
            "target_market",
            "company_culture",
            "headquarters",
            "employee_count_estimate",
        ):
            pval = profile.get(pkey)
            if pval:
                lines.append(f"    {pkey}: {pval}")
        techs = profile.get("technologies") or []
        if techs:
            lines.append(f"    technologies: {', '.join(str(t) for t in techs)}")

    return "\n".join(lines) if lines else "(no structured company data available)"


def build_prompt(context: dict) -> str:
    """Build the user message for contact finding.

    Args:
        context: dict with keys:
            - ``company`` (dict): company facts (name, domain, industry, etc.) and ``company_info``.
            - ``existing_contacts`` (list[dict]): already-found contacts to dedupe against.
              Each item should have at least ``name``; ``email`` and ``title`` are recommended.
            - ``scraped_content`` (str): combined markdown from /team /about /leadership pages.

    Returns:
        Formatted user message string.
    """
    company = context.get("company") or {}
    existing = context.get("existing_contacts") or []
    scraped = (context.get("scraped_content") or "").strip()

    company_block = _format_company_block(company)
    existing_block = _format_existing_contacts(existing)
    scraped_block = scraped if scraped else "(no scraped pages cached for this company)"

    return (
        "Target company:\n"
        f"{company_block}\n\n"
        "Already-found contacts (DO NOT RETURN THESE — used for de-duplication):\n"
        f"{existing_block}\n\n"
        "Scraped website content (team / about / leadership pages, may be empty):\n"
        f"--- BEGIN SCRAPED CONTENT ---\n{scraped_block}\n--- END SCRAPED CONTENT ---\n\n"
        "Identify any ADDITIONAL decision-makers at this company that are not already in the "
        "already-found list. Prefer names that appear in the scraped content. Do not invent "
        "emails. Respond with JSON only."
    )
