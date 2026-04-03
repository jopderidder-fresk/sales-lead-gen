"""Tests for prompt template modules and PromptManager.

Validates that each prompt module exports the required interface, that
``build_system_message()`` correctly injects configurable parts, and that
PromptManager correctly assembles system + user messages with injected context.
No LLM calls are made — these are pure unit tests.
"""

from __future__ import annotations

import re

import pytest
from prompts import (
    action_recommendation,
    company_extraction,
    company_profile,
    contact_extraction,
    relevance_scoring,
    signal_classification,
)
from prompts.config import (
    CompanyIdentity,
    PromptConfigBundle,
    SignalTypeDefinition,
)
from prompts.manager import PromptManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALL_MODULES = [
    signal_classification,
    relevance_scoring,
    action_recommendation,
    company_extraction,
    contact_extraction,
    company_profile,
]

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


# ---------------------------------------------------------------------------
# Module interface contract
# ---------------------------------------------------------------------------


class TestModuleInterface:
    """Each prompt module must export a consistent interface."""

    @pytest.mark.parametrize("module", _ALL_MODULES)
    def test_has_version(self, module) -> None:
        assert hasattr(module, "VERSION"), f"{module.__name__} missing VERSION"
        assert _SEMVER_RE.match(module.VERSION), f"{module.__name__}.VERSION is not semver"

    @pytest.mark.parametrize("module", _ALL_MODULES)
    def test_has_system_message(self, module) -> None:
        assert hasattr(module, "SYSTEM_MESSAGE"), f"{module.__name__} missing SYSTEM_MESSAGE"
        assert isinstance(module.SYSTEM_MESSAGE, str)
        assert len(module.SYSTEM_MESSAGE) > 50, "SYSTEM_MESSAGE suspiciously short"

    @pytest.mark.parametrize("module", _ALL_MODULES)
    def test_has_few_shot_examples(self, module) -> None:
        assert hasattr(module, "FEW_SHOT_EXAMPLES"), f"{module.__name__} missing FEW_SHOT_EXAMPLES"
        assert isinstance(module.FEW_SHOT_EXAMPLES, list)
        assert len(module.FEW_SHOT_EXAMPLES) >= 2, "Expected at least 2 few-shot examples"
        for ex in module.FEW_SHOT_EXAMPLES:
            assert "input" in ex and "output" in ex, (
                "Each example must have 'input' and 'output' keys"
            )

    @pytest.mark.parametrize("module", _ALL_MODULES)
    def test_has_output_schema(self, module) -> None:
        assert hasattr(module, "OUTPUT_SCHEMA"), f"{module.__name__} missing OUTPUT_SCHEMA"
        schema = module.OUTPUT_SCHEMA
        assert isinstance(schema, dict)
        assert "type" in schema
        assert "properties" in schema
        assert "required" in schema

    @pytest.mark.parametrize("module", _ALL_MODULES)
    def test_has_build_prompt(self, module) -> None:
        assert callable(getattr(module, "build_prompt", None)), (
            f"{module.__name__} missing callable build_prompt"
        )

    @pytest.mark.parametrize("module", _ALL_MODULES)
    def test_has_build_system_message(self, module) -> None:
        assert callable(getattr(module, "build_system_message", None)), (
            f"{module.__name__} missing callable build_system_message"
        )


# ---------------------------------------------------------------------------
# signal_classification
# ---------------------------------------------------------------------------


class TestSignalClassification:
    def test_build_prompt_injects_content(self) -> None:
        result = signal_classification.build_prompt(
            {"content": "We are hiring 10 engineers", "company_context": "Acme Corp"}
        )
        assert "We are hiring 10 engineers" in result
        assert "Acme Corp" in result

    def test_build_prompt_defaults_company_context(self) -> None:
        result = signal_classification.build_prompt({"content": "some content"})
        assert "Unknown company" in result

    def test_build_prompt_empty_context(self) -> None:
        result = signal_classification.build_prompt({})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_output_schema_has_signal_type_enum(self) -> None:
        enum_values = signal_classification.OUTPUT_SCHEMA["properties"]["signal_type"]["enum"]
        assert "hiring_surge" in enum_values
        assert "no_signal" in enum_values
        assert len(enum_values) == 10

    def test_system_message_lists_all_signal_types(self) -> None:
        for signal_type in [
            "hiring_surge",
            "technology_adoption",
            "digital_transformation",
            "workforce_challenge",
            "funding_round",
            "leadership_change",
            "expansion",
            "partnership",
            "product_launch",
            "no_signal",
        ]:
            assert signal_type in signal_classification.SYSTEM_MESSAGE

    def test_build_system_message_with_custom_types(self) -> None:
        custom_types = [
            SignalTypeDefinition(key="custom_signal", description="A custom signal"),
            SignalTypeDefinition(key="no_signal", description="No signal"),
        ]
        result = signal_classification.build_system_message(signal_types=custom_types)
        assert "custom_signal" in result
        assert "A custom signal" in result
        assert "hiring_surge" not in result

    def test_build_system_message_with_custom_identity(self) -> None:
        identity = CompanyIdentity(name="TestCo", tagline="a test company")
        result = signal_classification.build_system_message(company_identity=identity)
        assert "TestCo" in result
        assert "a test company" in result
        assert "fresk.digital" not in result


# ---------------------------------------------------------------------------
# relevance_scoring
# ---------------------------------------------------------------------------


class TestRelevanceScoring:
    def test_build_prompt_injects_all_context(self) -> None:
        result = relevance_scoring.build_prompt(
            {
                "content": "signal content",
                "signal_type": "hiring_surge",
                "company_context": "Acme Corp — SaaS",
                "icp_context": "50-500 employees, Netherlands",
            }
        )
        assert "signal content" in result
        assert "hiring_surge" in result
        assert "Acme Corp — SaaS" in result
        assert "50-500 employees, Netherlands" in result

    def test_build_prompt_defaults_missing_keys(self) -> None:
        result = relevance_scoring.build_prompt({})
        assert "Unknown company" in result
        assert "No ICP context provided" in result
        assert "unknown" in result

    def test_output_schema_has_action_enum(self) -> None:
        actions = relevance_scoring.OUTPUT_SCHEMA["properties"]["action"]["enum"]
        assert set(actions) == {"notify_immediate", "notify_digest", "enrich_further", "ignore"}

    def test_output_schema_score_range(self) -> None:
        score_schema = relevance_scoring.OUTPUT_SCHEMA["properties"]["relevance_score"]
        assert score_schema["minimum"] == 0
        assert score_schema["maximum"] == 100

    def test_build_system_message_with_custom_icp(self) -> None:
        result = relevance_scoring.build_system_message(icp_criteria="Custom ICP: only SaaS companies")
        assert "Custom ICP: only SaaS companies" in result

    def test_build_system_message_with_custom_identity(self) -> None:
        identity = CompanyIdentity(name="TestCo", tagline="test tagline")
        result = relevance_scoring.build_system_message(company_identity=identity)
        assert "TestCo" in result
        assert "fresk.digital" not in result

    def test_default_system_message_has_icp(self) -> None:
        """Default SYSTEM_MESSAGE should contain the default ICP criteria."""
        assert "Industry fit" in relevance_scoring.SYSTEM_MESSAGE
        assert "Geography" in relevance_scoring.SYSTEM_MESSAGE


# ---------------------------------------------------------------------------
# action_recommendation
# ---------------------------------------------------------------------------


class TestActionRecommendation:
    def test_build_prompt_injects_score_and_type(self) -> None:
        result = action_recommendation.build_prompt(
            {
                "signal_type": "funding_round",
                "relevance_score": 72,
                "company_context": "FinFlow BV",
                "key_factors": ["Series A closed", "matches ICP size"],
            }
        )
        assert "funding_round" in result
        assert "72" in result
        assert "FinFlow BV" in result
        assert "Series A closed" in result

    def test_build_prompt_handles_empty_key_factors(self) -> None:
        result = action_recommendation.build_prompt(
            {"signal_type": "expansion", "relevance_score": 50}
        )
        assert "Not specified" in result

    def test_build_prompt_handles_missing_context(self) -> None:
        result = action_recommendation.build_prompt({})
        assert "Unknown company" in result
        assert "0" in result

    def test_output_schema_urgency_enum(self) -> None:
        urgency = action_recommendation.OUTPUT_SCHEMA["properties"]["urgency"]["enum"]
        assert set(urgency) == {"low", "medium", "high"}

    def test_output_schema_channel_enum(self) -> None:
        channels = action_recommendation.OUTPUT_SCHEMA["properties"]["suggested_channel"]["enum"]
        assert set(channels) == {"linkedin_dm", "email", "phone"}


# ---------------------------------------------------------------------------
# company_extraction
# ---------------------------------------------------------------------------


class TestCompanyExtraction:
    def test_build_prompt_injects_content(self) -> None:
        result = company_extraction.build_prompt(
            {"content": "TechFlow BV provides cloud monitoring."}
        )
        assert "TechFlow BV provides cloud monitoring." in result

    def test_build_prompt_empty_content(self) -> None:
        result = company_extraction.build_prompt({})
        assert isinstance(result, str)

    def test_output_schema_companies_array(self) -> None:
        companies = company_extraction.OUTPUT_SCHEMA["properties"]["companies"]
        assert companies["type"] == "array"
        item_props = companies["items"]["properties"]
        assert "name" in item_props
        assert "domain" in item_props
        assert "industry" in item_props
        assert "description" in item_props


# ---------------------------------------------------------------------------
# contact_extraction
# ---------------------------------------------------------------------------


class TestContactExtraction:
    def test_build_prompt_injects_content(self) -> None:
        result = contact_extraction.build_prompt({"content": "Jane Doe — CTO, jane@acme.com"})
        assert "Jane Doe — CTO, jane@acme.com" in result

    def test_build_prompt_empty_content(self) -> None:
        result = contact_extraction.build_prompt({})
        assert isinstance(result, str)

    def test_output_schema_contacts_array(self) -> None:
        contacts = contact_extraction.OUTPUT_SCHEMA["properties"]["contacts"]
        assert contacts["type"] == "array"
        item_props = contacts["items"]["properties"]
        assert "name" in item_props
        assert "title" in item_props
        assert "email" in item_props
        assert "linkedin_url" in item_props

    def test_build_system_message_with_custom_roles(self) -> None:
        result = contact_extraction.build_system_message(
            decision_maker_roles=["CEO", "VP Sales"]
        )
        assert "CEO, VP Sales" in result


# ---------------------------------------------------------------------------
# company_profile
# ---------------------------------------------------------------------------


class TestCompanyProfile:
    def test_build_prompt_injects_content(self) -> None:
        result = company_profile.build_prompt({"content": "Breman Installatietechniek..."})
        assert "Breman Installatietechniek..." in result

    def test_build_prompt_empty_content(self) -> None:
        result = company_profile.build_prompt({})
        assert isinstance(result, str)

    def test_output_schema_has_required_fields(self) -> None:
        required = company_profile.OUTPUT_SCHEMA["required"]
        assert "summary" in required
        assert "field_service_indicators" in required
        assert "digital_maturity_signals" in required


# ---------------------------------------------------------------------------
# PromptConfigBundle
# ---------------------------------------------------------------------------


class TestPromptConfigBundle:
    def test_defaults_has_signal_types(self) -> None:
        defaults = PromptConfigBundle.defaults()
        assert len(defaults.signal_types) == 10
        keys = {st.key for st in defaults.signal_types}
        assert "hiring_surge" in keys
        assert "no_signal" in keys

    def test_defaults_has_company_identity(self) -> None:
        defaults = PromptConfigBundle.defaults()
        assert defaults.company_identity.name == "fresk.digital"
        assert len(defaults.company_identity.tagline) > 10

    def test_defaults_has_decision_maker_roles(self) -> None:
        defaults = PromptConfigBundle.defaults()
        assert "COO" in defaults.decision_maker_roles
        assert "CIO" in defaults.decision_maker_roles

    def test_defaults_has_icp_criteria(self) -> None:
        defaults = PromptConfigBundle.defaults()
        assert "Industry fit" in defaults.icp_criteria

    def test_format_signal_types_block(self) -> None:
        bundle = PromptConfigBundle.defaults()
        block = bundle.format_signal_types_block()
        assert "- hiring_surge:" in block
        assert "- no_signal:" in block

    def test_format_decision_maker_roles(self) -> None:
        bundle = PromptConfigBundle.defaults()
        roles_str = bundle.format_decision_maker_roles()
        assert "COO" in roles_str
        assert ", " in roles_str


# ---------------------------------------------------------------------------
# PromptManager
# ---------------------------------------------------------------------------


class TestPromptManager:
    def setup_method(self) -> None:
        self.manager = PromptManager()

    def test_build_signal_classification_returns_tuple(self) -> None:
        system_msg, user_msg, version = self.manager.build_signal_classification(
            content="We're hiring 10 engineers",
            company_context="Acme Corp — SaaS",
        )
        assert isinstance(system_msg, str) and len(system_msg) > 0
        assert isinstance(user_msg, str) and len(user_msg) > 0
        assert _SEMVER_RE.match(version)

    def test_build_signal_classification_injects_content(self) -> None:
        _, user_msg, _ = self.manager.build_signal_classification(
            content="Series B announcement", company_context="Beta Inc"
        )
        assert "Series B announcement" in user_msg
        assert "Beta Inc" in user_msg

    def test_build_relevance_scoring_returns_tuple(self) -> None:
        system_msg, user_msg, version = self.manager.build_relevance_scoring(
            content="20 new hires",
            signal_type="hiring_surge",
            company_context="Acme Corp",
            icp_context="SaaS 50-500",
        )
        assert isinstance(system_msg, str) and len(system_msg) > 0
        assert "20 new hires" in user_msg
        assert "hiring_surge" in user_msg
        assert _SEMVER_RE.match(version)

    def test_build_relevance_scoring_defaults(self) -> None:
        system_msg, user_msg, version = self.manager.build_relevance_scoring(
            content="content", signal_type="expansion"
        )
        assert "Unknown company" in user_msg
        assert "No ICP context provided" in user_msg

    def test_build_action_recommendation_returns_tuple(self) -> None:
        system_msg, user_msg, version = self.manager.build_action_recommendation(
            signal_type="funding_round",
            relevance_score=75,
            company_context="FinFlow BV",
            key_factors=["Series A closed"],
        )
        assert isinstance(system_msg, str) and len(system_msg) > 0
        assert "75" in user_msg
        assert "funding_round" in user_msg
        assert _SEMVER_RE.match(version)

    def test_build_action_recommendation_none_key_factors(self) -> None:
        _, user_msg, _ = self.manager.build_action_recommendation(
            signal_type="expansion", relevance_score=60
        )
        assert "Not specified" in user_msg

    def test_build_company_extraction_returns_tuple(self) -> None:
        system_msg, user_msg, version = self.manager.build_company_extraction(
            search_results="TechFlow BV (techflow.io) cloud monitoring"
        )
        assert isinstance(system_msg, str) and len(system_msg) > 0
        assert "TechFlow BV" in user_msg
        assert _SEMVER_RE.match(version)

    def test_build_contact_extraction_returns_tuple(self) -> None:
        system_msg, user_msg, version = self.manager.build_contact_extraction(
            page_content="Jane Doe — CTO, jane@acme.com"
        )
        assert isinstance(system_msg, str) and len(system_msg) > 0
        assert "Jane Doe" in user_msg
        assert _SEMVER_RE.match(version)

    def test_build_company_profile_returns_tuple(self) -> None:
        system_msg, user_msg, version = self.manager.build_company_profile(
            page_content="Breman Installatietechniek..."
        )
        assert isinstance(system_msg, str) and len(system_msg) > 0
        assert "Breman Installatietechniek..." in user_msg
        assert _SEMVER_RE.match(version)

    def test_system_messages_differ_per_method(self) -> None:
        """Each method should use a distinct system message."""
        results = {
            self.manager.build_signal_classification("c")[0],
            self.manager.build_relevance_scoring("c", "hiring_surge")[0],
            self.manager.build_action_recommendation("hiring_surge", 80)[0],
            self.manager.build_company_extraction("c")[0],
            self.manager.build_contact_extraction("c")[0],
            self.manager.build_company_profile("c")[0],
        }
        assert len(results) == 6, "All six prompts should have distinct system messages"

    def test_versions_are_semver(self) -> None:
        for build_fn, kwargs in [
            (self.manager.build_signal_classification, {"content": "x"}),
            (self.manager.build_relevance_scoring, {"content": "x", "signal_type": "expansion"}),
            (
                self.manager.build_action_recommendation,
                {"signal_type": "expansion", "relevance_score": 50},
            ),
            (self.manager.build_company_extraction, {"search_results": "x"}),
            (self.manager.build_contact_extraction, {"page_content": "x"}),
            (self.manager.build_company_profile, {"page_content": "x"}),
        ]:
            _, _, version = build_fn(**kwargs)
            assert _SEMVER_RE.match(version), f"Version '{version}' is not semver"


# ---------------------------------------------------------------------------
# PromptManager with custom config
# ---------------------------------------------------------------------------


class TestPromptManagerWithConfig:
    def setup_method(self) -> None:
        self.custom_config = PromptConfigBundle(
            signal_types=[
                SignalTypeDefinition(key="custom_signal", description="A custom signal"),
                SignalTypeDefinition(key="no_signal", description="No signal detected"),
            ],
            company_identity=CompanyIdentity(name="TestCo", tagline="a test company"),
            decision_maker_roles=["CEO", "VP Sales"],
            icp_criteria="Only SaaS companies with 50+ employees",
        )
        self.manager = PromptManager(config=self.custom_config)

    def test_signal_classification_uses_custom_types(self) -> None:
        system_msg, _, _ = self.manager.build_signal_classification(content="test")
        assert "custom_signal" in system_msg
        assert "A custom signal" in system_msg
        assert "hiring_surge" not in system_msg

    def test_signal_classification_uses_custom_identity(self) -> None:
        system_msg, _, _ = self.manager.build_signal_classification(content="test")
        assert "TestCo" in system_msg
        assert "fresk.digital" not in system_msg

    def test_relevance_scoring_uses_custom_icp(self) -> None:
        system_msg, _, _ = self.manager.build_relevance_scoring(
            content="test", signal_type="custom_signal"
        )
        assert "Only SaaS companies with 50+ employees" in system_msg

    def test_contact_extraction_uses_custom_roles(self) -> None:
        system_msg, _, _ = self.manager.build_contact_extraction(page_content="test")
        assert "CEO, VP Sales" in system_msg

    def test_company_profile_uses_custom_identity(self) -> None:
        system_msg, _, _ = self.manager.build_company_profile(page_content="test")
        assert "TestCo" in system_msg
        assert "a test company" in system_msg
