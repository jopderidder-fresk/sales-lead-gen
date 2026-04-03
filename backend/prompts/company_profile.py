"""Company profile extraction prompt — generates a structured profile from scraped pages.

Extracts field service indicators, digital maturity signals, and operational
complexity markers alongside standard company profile data.

Version: 3.0.0
"""

from __future__ import annotations

from prompts.config import CompanyIdentity, PromptConfigBundle

VERSION = "3.0.0"

# ---------------------------------------------------------------------------
# Static base
# ---------------------------------------------------------------------------

_SYSTEM_BASE = """\
You are a B2B company research analyst working for {company_name}, {company_tagline}. \
Analyse the provided scraped website content and produce a structured company profile.

Rules:
- The "summary" field is ALWAYS required — write 2-3 concise sentences describing what the company does.
- For all other fields, set to null if the information is not clearly present in the content.
- For "technologies", only list technologies explicitly mentioned on the site — do not infer.
- For "employee_count_estimate", use the exact phrasing from the website.
- For "founded_year", only include if a specific year is mentioned.
- For "products_services", summarise the key offerings in 1-3 sentences.
- For "target_market", describe who they sell to.
- For "company_culture", summarise values, mission, or culture statements if present.
- For "field_service_indicators", identify any mentions of field workers, monteurs, technici, \
inspecteurs, engineers in het veld, service professionals, planners, or other frontline/field roles. \
Note the approximate scale if mentioned. Null if no field service component is evident.
- For "digital_maturity_signals", note mentions of digital transformation, legacy system \
replacement, innovation programmes, paperless goals, or technology investment. Also note signs \
of low digital maturity. Null if no signals present.
- For "operational_complexity", briefly describe operational complexity if evident (e.g. \
multi-site, regulated industry, complex logistics, certification requirements). Null if not evident.
- Keep all text concise and factual — no speculation or marketing language.
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
            "content": (
                "--- https://breman.nl/ ---\n\n"
                "Breman Installatietechniek — Specialist in klimaat-, elektro- en sanitaire installaties "
                "voor utiliteit en industrie. Met ruim 1600 medewerkers, waarvan 1100 monteurs in het veld, "
                "zijn we actief door heel Nederland.\n\n"
                "--- https://breman.nl/over-ons ---\n\n"
                "Opgericht in 1926 in Genemuiden. We werken met SAP als ERP en hebben "
                "recent een nieuw workforce management systeem geïmplementeerd. "
                "We geloven in vakmanschap en investeren in de ontwikkeling van onze mensen."
            ),
        },
        "output": {
            "summary": "Breman Installatietechniek is a specialist in climate, electrical, and sanitary installations for commercial and industrial buildings. They operate nationwide in the Netherlands with over 1600 employees.",
            "products_services": "Climate control, electrical, and sanitary installation services for commercial and industrial sectors.",
            "target_market": "Commercial real estate and industrial companies in the Netherlands.",
            "technologies": ["SAP"],
            "company_culture": "Focus on craftsmanship and investment in employee development.",
            "headquarters": "Genemuiden",
            "founded_year": 1926,
            "employee_count_estimate": "1600+",
            "field_service_indicators": "1100 monteurs working in the field out of 1600 total — field service is core to operations.",
            "digital_maturity_signals": "Recently implemented new workforce management system alongside SAP ERP — actively investing in operational tooling.",
            "operational_complexity": "Multi-site operations across the Netherlands covering climate, electrical, and sanitary disciplines.",
        },
    },
    {
        "input": {
            "content": (
                "--- https://dekra.nl/ ---\n\n"
                "DEKRA — Uw partner in testing, inspection en certification. "
                "We helpen organisaties veilig en duurzaam te opereren.\n\n"
                "--- https://dekra.nl/over-dekra ---\n\n"
                "DEKRA is actief in meer dan 60 landen. In Nederland werken ruim 800 inspecteurs "
                "en specialisten. Onze inspectieprocessen worden grotendeels digitaal ondersteund, "
                "maar er is nog veel ruimte voor verbetering in de mobiele tooling voor onze veld-inspecteurs."
            ),
        },
        "output": {
            "summary": "DEKRA is a testing, inspection, and certification organisation helping companies operate safely and sustainably. Active in 60+ countries with 800+ inspectors and specialists in the Netherlands.",
            "products_services": "Testing, inspection, and certification services across safety, sustainability, and compliance.",
            "target_market": "Organisations requiring safety certification, compliance, and inspection services globally.",
            "technologies": [],
            "company_culture": None,
            "headquarters": None,
            "founded_year": None,
            "employee_count_estimate": "800+ (Netherlands)",
            "field_service_indicators": "800+ inspectors and specialists, with field inspectors as a key operational role.",
            "digital_maturity_signals": "Inspection processes are partially digital but mobile tooling for field inspectors needs improvement — acknowledged gap.",
            "operational_complexity": "Multi-country operations with strict certification and compliance requirements. Field inspectors follow regulated protocols.",
        },
    },
]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "products_services": {"type": ["string", "null"]},
        "target_market": {"type": ["string", "null"]},
        "technologies": {"type": "array", "items": {"type": "string"}},
        "company_culture": {"type": ["string", "null"]},
        "headquarters": {"type": ["string", "null"]},
        "founded_year": {"type": ["integer", "null"]},
        "employee_count_estimate": {"type": ["string", "null"]},
        "field_service_indicators": {"type": ["string", "null"]},
        "digital_maturity_signals": {"type": ["string", "null"]},
        "operational_complexity": {"type": ["string", "null"]},
    },
    "required": [
        "summary",
        "products_services",
        "target_market",
        "technologies",
        "company_culture",
        "headquarters",
        "founded_year",
        "employee_count_estimate",
        "field_service_indicators",
        "digital_maturity_signals",
        "operational_complexity",
    ],
}


def build_prompt(context: dict) -> str:
    """Build the user message for company profile extraction.

    Args:
        context: dict with key ``content`` (combined scraped page content).

    Returns:
        Formatted user message string.
    """
    content = context.get("content", "")
    return (
        f"Analyse the following scraped website content and produce a structured company profile:\n\n"
        f"{content}\n\n"
        f"Respond with JSON only."
    )
