"""Prompt manager — assembles prompt templates and injects runtime context.

Each ``build_*`` method returns a ``(system_message, user_message, version)``
tuple ready for direct use in an LLM API call.

The manager accepts an optional :class:`~prompts.config.PromptConfigBundle`
to customise signal definitions, ICP criteria, company identity, and
decision-maker roles.  When no config is provided it falls back to
hardcoded defaults.

Usage::

    manager = PromptManager()                      # uses defaults
    manager = PromptManager(config=my_bundle)       # uses DB config

    system_msg, user_msg, version = manager.build_signal_classification(
        content="We're hiring 10 engineers",
        company_context="Acme Corp — SaaS, 50-200 employees",
    )
"""

from __future__ import annotations

from datetime import date

from prompts import (
    action_recommendation,
    company_extraction,
    company_profile,
    contact_extraction,
    relevance_scoring,
    signal_classification,
)
from prompts.config import PromptConfigBundle


class PromptManager:
    """Loads prompt templates and injects runtime context.

    Accepts a ``PromptConfigBundle`` for customisation; defaults are used
    when *config* is ``None``.
    """

    def __init__(self, config: PromptConfigBundle | None = None) -> None:
        self._config = config or PromptConfigBundle.defaults()

    def build_signal_classification(
        self,
        content: str,
        company_context: str = "",
    ) -> tuple[str, str, str]:
        """Build prompts for signal type classification.

        Args:
            content: Scraped web content to classify.
            company_context: Short description of the company.

        Returns:
            ``(system_message, user_message, version)`` tuple.
        """
        system_msg = signal_classification.build_system_message(
            signal_types=self._config.signal_types,
            company_identity=self._config.company_identity,
        )
        user_msg = signal_classification.build_prompt(
            {"content": content, "company_context": company_context, "today_date": date.today().isoformat()}
        )
        return (system_msg, user_msg, signal_classification.VERSION)

    def build_relevance_scoring(
        self,
        content: str,
        signal_type: str,
        company_context: str = "",
        icp_context: str = "",
    ) -> tuple[str, str, str]:
        """Build prompts for relevance scoring and action recommendation.

        Args:
            content: Scraped web content that triggered the signal.
            signal_type: Classified signal type (from signal_classification).
            company_context: Short description of the company.
            icp_context: Description of the active ICP profile (for user message).

        Returns:
            ``(system_message, user_message, version)`` tuple.
        """
        system_msg = relevance_scoring.build_system_message(
            company_identity=self._config.company_identity,
            icp_criteria=self._config.icp_criteria,
        )
        user_msg = relevance_scoring.build_prompt(
            {
                "content": content,
                "signal_type": signal_type,
                "company_context": company_context,
                "icp_context": icp_context,
                "today_date": date.today().isoformat(),
            }
        )
        return (system_msg, user_msg, relevance_scoring.VERSION)

    def build_action_recommendation(
        self,
        signal_type: str,
        relevance_score: int,
        company_context: str = "",
        key_factors: list[str] | None = None,
    ) -> tuple[str, str, str]:
        """Build prompts for standalone action recommendation given a scored signal.

        Args:
            signal_type: Classified signal type.
            relevance_score: Pre-computed relevance score (0-100).
            company_context: Short description of the company.
            key_factors: List of key factors that drove the score.

        Returns:
            ``(system_message, user_message, version)`` tuple.
        """
        system_msg = action_recommendation.build_system_message(
            company_identity=self._config.company_identity,
        )
        user_msg = action_recommendation.build_prompt(
            {
                "signal_type": signal_type,
                "relevance_score": relevance_score,
                "company_context": company_context,
                "key_factors": key_factors or [],
            }
        )
        return (system_msg, user_msg, action_recommendation.VERSION)

    def build_company_extraction(
        self,
        search_results: str,
    ) -> tuple[str, str, str]:
        """Build prompts for company extraction from search results.

        Args:
            search_results: Combined text from one or more search results.

        Returns:
            ``(system_message, user_message, version)`` tuple.
        """
        system_msg = company_extraction.build_system_message(
            company_identity=self._config.company_identity,
        )
        user_msg = company_extraction.build_prompt({"content": search_results})
        return (system_msg, user_msg, company_extraction.VERSION)

    def build_contact_extraction(
        self,
        page_content: str,
    ) -> tuple[str, str, str]:
        """Build prompts for contact extraction from a team or about page.

        Args:
            page_content: Markdown or text scraped from a /team or /about page.

        Returns:
            ``(system_message, user_message, version)`` tuple.
        """
        system_msg = contact_extraction.build_system_message(
            company_identity=self._config.company_identity,
            decision_maker_roles=self._config.decision_maker_roles,
        )
        user_msg = contact_extraction.build_prompt({"content": page_content})
        return (system_msg, user_msg, contact_extraction.VERSION)

    def build_company_profile(
        self,
        page_content: str,
    ) -> tuple[str, str, str]:
        """Build prompts for company profile extraction from scraped pages.

        Args:
            page_content: Combined markdown from scraped company pages.

        Returns:
            ``(system_message, user_message, version)`` tuple.
        """
        system_msg = company_profile.build_system_message(
            company_identity=self._config.company_identity,
        )
        user_msg = company_profile.build_prompt({"content": page_content})
        return (system_msg, user_msg, company_profile.VERSION)
