"""Tests for the prompt configuration system.

Tests the PromptConfigBundle defaults, the config_loader, and the
PromptConfig model integration.  Uses in-memory structures (no DB needed
for unit tests).
"""

from __future__ import annotations

import pytest
from prompts.config import (
    CompanyIdentity,
    PromptConfigBundle,
    SignalTypeDefinition,
)


class TestPromptConfigBundleDefaults:
    """Test that defaults match the original hardcoded prompt values."""

    def test_defaults_returns_bundle(self) -> None:
        bundle = PromptConfigBundle.defaults()
        assert isinstance(bundle, PromptConfigBundle)

    def test_signal_types_count(self) -> None:
        bundle = PromptConfigBundle.defaults()
        assert len(bundle.signal_types) == 10

    def test_signal_types_all_have_key_and_description(self) -> None:
        bundle = PromptConfigBundle.defaults()
        for st in bundle.signal_types:
            assert st.key, "Signal type key must not be empty"
            assert st.description, "Signal type description must not be empty"

    def test_signal_type_keys_match_expected(self) -> None:
        bundle = PromptConfigBundle.defaults()
        keys = [st.key for st in bundle.signal_types]
        expected = [
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
        ]
        assert keys == expected

    def test_company_identity(self) -> None:
        bundle = PromptConfigBundle.defaults()
        assert bundle.company_identity.name == "fresk.digital"
        assert "field service" in bundle.company_identity.tagline.lower()

    def test_decision_maker_roles_non_empty(self) -> None:
        bundle = PromptConfigBundle.defaults()
        assert len(bundle.decision_maker_roles) >= 10
        assert "COO" in bundle.decision_maker_roles
        assert "CTO" in bundle.decision_maker_roles

    def test_icp_criteria_non_empty(self) -> None:
        bundle = PromptConfigBundle.defaults()
        assert len(bundle.icp_criteria) > 50
        assert "Industry" in bundle.icp_criteria


class TestPromptConfigBundleFormatting:
    """Test formatting helpers."""

    def test_format_signal_types_block(self) -> None:
        bundle = PromptConfigBundle(
            signal_types=[
                SignalTypeDefinition(key="a", description="Alpha"),
                SignalTypeDefinition(key="b", description="Beta"),
            ],
            company_identity=CompanyIdentity(name="X", tagline="y"),
            decision_maker_roles=["CEO"],
            icp_criteria="test",
        )
        block = bundle.format_signal_types_block()
        assert block == "- a: Alpha\n- b: Beta"

    def test_format_decision_maker_roles(self) -> None:
        bundle = PromptConfigBundle(
            signal_types=[],
            company_identity=CompanyIdentity(name="X", tagline="y"),
            decision_maker_roles=["CEO", "CTO", "CFO"],
            icp_criteria="test",
        )
        assert bundle.format_decision_maker_roles() == "CEO, CTO, CFO"

    def test_format_empty_roles(self) -> None:
        bundle = PromptConfigBundle(
            signal_types=[],
            company_identity=CompanyIdentity(name="X", tagline="y"),
            decision_maker_roles=[],
            icp_criteria="test",
        )
        assert bundle.format_decision_maker_roles() == ""


class TestPromptConfigBundleCustom:
    """Test constructing bundles with custom values."""

    def test_custom_signal_types(self) -> None:
        custom = PromptConfigBundle(
            signal_types=[SignalTypeDefinition(key="custom", description="Custom signal")],
            company_identity=CompanyIdentity(name="Test", tagline="test"),
            decision_maker_roles=["CEO"],
            icp_criteria="test criteria",
        )
        assert len(custom.signal_types) == 1
        assert custom.signal_types[0].key == "custom"

    def test_custom_identity(self) -> None:
        custom = PromptConfigBundle(
            signal_types=[],
            company_identity=CompanyIdentity(name="Acme", tagline="we test"),
            decision_maker_roles=[],
            icp_criteria="",
        )
        assert custom.company_identity.name == "Acme"

    def test_signal_type_definition_frozen(self) -> None:
        st = SignalTypeDefinition(key="test", description="test desc")
        with pytest.raises(AttributeError):
            st.key = "changed"  # type: ignore[misc]

    def test_company_identity_frozen(self) -> None:
        ci = CompanyIdentity(name="Test", tagline="test")
        with pytest.raises(AttributeError):
            ci.name = "changed"  # type: ignore[misc]
