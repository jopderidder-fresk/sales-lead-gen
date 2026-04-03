"""LLM service layer — provider-agnostic interface for language model operations.

Switch providers by setting ``LLM_PROVIDER`` in ``.env``::

    LLM_PROVIDER=anthropic      # default — uses ANTHROPIC_API_KEY
    LLM_PROVIDER=openrouter     # uses OPENROUTER_API_KEY + OPENROUTER_MODEL
    LLM_PROVIDER=google_vertex  # uses GOOGLE_SERVICE_ACCOUNT_KEY_PATH

Usage::

    from app.services.llm import create_llm_client

    service = create_llm_client()
    result = await service.classify_signal(content, company_context)
    await service.close()
"""

from app.services.llm.base import (
    CompaniesResult,
    CompanyProfile,
    ContactsResult,
    ExtractedCompany,
    ExtractedContact,
    ScoreAndRecommendation,
    SignalClassification,
)
from app.services.llm.client import LLMService
from app.services.llm.factory import create_llm_client

__all__ = [
    "LLMService",
    "SignalClassification",
    "ScoreAndRecommendation",
    "CompanyProfile",
    "ExtractedCompany",
    "ExtractedContact",
    "CompaniesResult",
    "ContactsResult",
    "create_llm_client",
]
