"""LLM response types and service interface.

Pydantic models used as ``output_type`` for pydantic-ai agents. These define
the structured output schemas that models are forced to produce via tool calling.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Output schemas (used as Agent output_type)
# ---------------------------------------------------------------------------


class SignalClassification(BaseModel):
    """Structured output from signal classification."""

    signal_type: str = Field(
        description=(
            "One of: hiring_surge, technology_adoption, digital_transformation, "
            "workforce_challenge, funding_round, leadership_change, expansion, "
            "partnership, product_launch, no_signal"
        )
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the classification (0-1)")
    reasoning: str = Field(description="Brief explanation of why this signal type was chosen")


class ScoreAndRecommendation(BaseModel):
    """Structured output from relevance scoring."""

    relevance_score: int = Field(ge=0, le=100, description="Overall relevance score 0-100")
    action: str = Field(
        description=(
            "One of: notify_immediate (score>=75), notify_digest (50-74), "
            "enrich_further (25-49), ignore (<25)"
        )
    )
    reasoning: str = Field(description="Explanation of the score and recommended action")
    key_factors: list[str] = Field(
        default_factory=list,
        description="Up to 5 specific factors that drove the score",
    )


class ExtractedCompany(BaseModel):
    """A company extracted from search results."""

    name: str
    domain: str | None = None
    industry: str | None = None
    description: str | None = None


class ExtractedContact(BaseModel):
    """A contact extracted from a team or about page."""

    name: str
    title: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    is_decision_maker: bool = False


class CompanyProfile(BaseModel):
    """Structured company profile generated from scraped website content."""

    summary: str = Field(description="2-3 sentence overview of what the company does")
    products_services: str | None = Field(
        default=None, description="Key products or services offered"
    )
    target_market: str | None = Field(
        default=None, description="Who they sell to / target audience"
    )
    technologies: list[str] = Field(
        default_factory=list, description="Key technologies mentioned on the site"
    )
    company_culture: str | None = Field(
        default=None, description="Culture, values, or mission if mentioned"
    )
    headquarters: str | None = Field(default=None, description="HQ location if found")
    founded_year: int | None = Field(default=None, description="Year founded if mentioned")
    employee_count_estimate: str | None = Field(
        default=None, description="Employee count or range if mentioned"
    )
    field_service_indicators: str | None = Field(
        default=None, description="Field service roles and scale if evident"
    )
    digital_maturity_signals: str | None = Field(
        default=None, description="Digital transformation or legacy system signals"
    )
    operational_complexity: str | None = Field(
        default=None, description="Operational complexity markers if evident"
    )


class CompaniesResult(BaseModel):
    """Wrapper for list extraction — forces the model to return a structured list."""

    companies: list[ExtractedCompany] = Field(default_factory=list)


class ContactsResult(BaseModel):
    """Wrapper for list extraction — forces the model to return a structured list."""

    contacts: list[ExtractedContact] = Field(default_factory=list)
