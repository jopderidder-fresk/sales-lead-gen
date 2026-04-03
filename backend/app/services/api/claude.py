"""Backward-compatibility re-exports.

The canonical implementations now live in :mod:`app.services.llm`.
Import from there for new code.
"""

from app.services.llm.base import (
    ExtractedCompany,
    ExtractedContact,
    ScoreAndRecommendation,
    SignalClassification,
)
from app.services.llm.client import LLMService

__all__ = [
    "LLMService",
    "SignalClassification",
    "ScoreAndRecommendation",
    "ExtractedCompany",
    "ExtractedContact",
]
