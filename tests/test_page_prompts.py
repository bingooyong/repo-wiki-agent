"""Tests for page prompt contracts and fragments.

Tests the prompt contracts defined in repo_wiki/prompts/contracts.py
and the prompt fragments in repo_wiki/prompts/fragments.py.

Phase 24 - Task 24.1
"""

from __future__ import annotations

import re

import pytest

from repo_wiki.prompts import (
    PagePromptType,
    CitationStyle,
    HeadingRequirement,
    EvidenceRequirement,
    StyleRequirement,
    AntiHallucinationRequirement,
    PagePromptContract,
    PAGE_PROMPT_CONTRACTS,
    get_contract_for_page_type,
    get_contract_for_doc_type,
    SYSTEM_PROMPT_FRAGMENT,
    OVERVIEW_PROMPT_FRAGMENT,
    SERVICE_PROMPT_FRAGMENT,
    API_PROMPT_FRAGMENT,
    DATA_PROMPT_FRAGMENT,
    ENTITY_PROMPT_FRAGMENT,
    OPS_PROMPT_FRAGMENT,
    DEVELOPMENT_PROMPT_FRAGMENT,
    get_prompt_fragment,
    render_prompt_fragment,
)
from repo_wiki.llm import redact_secrets


class TestPagePromptType:
    """Tests for PagePromptType enum."""

    def test_all_page_types_exist(self) -> None:
        """Test that all expected page types are defined."""
        expected_types = [
            "OVERVIEW",
            "SERVICE",
            "API",
            "DATA",
            "ENTITY",
            "OPS",
            "DEVELOPMENT",
        ]
        for type_name in expected_types:
            assert hasattr(PagePromptType, type_name)

    def test_page_type_values(self) -> None:
        """Test PagePromptType enum values are strings."""
        for page_type in PagePromptType:
            assert isinstance(page_type.value, str)


class TestCitationStyle:
    """Tests for CitationStyle enum."""

    def test_all_citation_styles_exist(self) -> None:
        """Test that all citation styles are defined."""
        expected_styles = ["CITE_BLOCK", "MARKDOWN_LINK", "SOURCE_FOOTER"]
        for style_name in expected_styles:
            assert hasattr(CitationStyle, style_name)


class TestPagePromptContracts:
    """Tests for PagePromptContract instances."""

    def test_all_contracts_defined(self) -> None:
        """Test that all expected contracts are defined."""
        expected_types = [
            PagePromptType.OVERVIEW,
            PagePromptType.SERVICE,
            PagePromptType.API,
            PagePromptType.DATA,
            PagePromptType.ENTITY,
            PagePromptType.OPS,
            PagePromptType.DEVELOPMENT,
        ]
        for page_type in expected_types:
            assert page_type in PAGE_PROMPT_CONTRACTS

    def test_overview_contract_structure(self) -> None:
        """Test overview contract has correct structure."""
        contract = PAGE_PROMPT_CONTRACTS[PagePromptType.OVERVIEW]
        assert contract.page_type == PagePromptType.OVERVIEW
        assert len(contract.heading_structure) >= 5
        assert contract.evidence.min_candidates >= 5
        assert contract.style.prose_density_min >= 0.3

    def test_service_contract_structure(self) -> None:
        """Test service contract has correct structure."""
        contract = PAGE_PROMPT_CONTRACTS[PagePromptType.SERVICE]
        assert contract.page_type == PagePromptType.SERVICE
        assert len(contract.heading_structure) >= 4

    def test_api_contract_structure(self) -> None:
        """Test API contract has correct structure."""
        contract = PAGE_PROMPT_CONTRACTS[PagePromptType.API]
        assert contract.page_type == PagePromptType.API
        assert contract.evidence.min_candidates >= 8
        assert contract.anti_hallucination.cite_all_claims is True

    def test_all_contracts_have_anti_hallucination(self) -> None:
        """Test that all contracts have anti-hallucination requirements."""
        for contract in PAGE_PROMPT_CONTRACTS.values():
            assert contract.anti_hallucination is not None
            assert hasattr(contract.anti_hallucination, "cite_all_symbols")
            assert hasattr(contract.anti_hallucination, "cite_all_claims")

    def test_all_contracts_have_style_requirements(self) -> None:
        """Test that all contracts have style requirements."""
        for contract in PAGE_PROMPT_CONTRACTS.values():
            assert contract.style is not None
            assert contract.style.prose_density_min > 0
            assert contract.style.max_list_ratio < 1.0

    def test_all_contracts_have_snapshot_patterns(self) -> None:
        """Test that all contracts have snapshot test patterns."""
        for contract in PAGE_PROMPT_CONTRACTS.values():
            assert contract.snapshot_test_pattern is not None
            # Verify it's a valid regex
            re.compile(contract.snapshot_test_pattern)

    def test_secret_redaction_required(self) -> None:
        """Test that secret redaction is enabled for all contracts."""
        for contract in PAGE_PROMPT_CONTRACTS.values():
            assert contract.secret_redaction_required is True


class TestGetContractForPageType:
    """Tests for get_contract_for_page_type function."""

    def test_valid_page_types(self) -> None:
        """Test getting contracts for valid page types."""
        for page_type in PagePromptType:
            contract = get_contract_for_page_type(page_type)
            assert contract is not None
            assert contract.page_type == page_type

    def test_invalid_page_type_raises(self) -> None:
        """Test that invalid page type raises ValueError."""
        # Create an invalid page type (if possible) or use a mock
        class InvalidType:
            pass
        # We can't easily create an invalid enum value, so we test the function behavior
        # by checking that a ValueError is raised for truly invalid input
        with pytest.raises(ValueError):
            get_contract_for_page_type(None)  # type: ignore


class TestGetContractForDocType:
    """Tests for get_contract_for_doc_type function."""

    def test_overview_doc_type(self) -> None:
        """Test overview doc type mapping."""
        contract = get_contract_for_doc_type("overview")
        assert contract.page_type == PagePromptType.OVERVIEW

    def test_section_doc_type(self) -> None:
        """Test section doc type mapping."""
        contract = get_contract_for_doc_type("section")
        assert contract.page_type == PagePromptType.SERVICE

    def test_module_doc_type(self) -> None:
        """Test module doc type mapping."""
        contract = get_contract_for_doc_type("module")
        assert contract.page_type == PagePromptType.SERVICE

    def test_api_doc_type(self) -> None:
        """Test API doc type mapping."""
        contract = get_contract_for_doc_type("api")
        assert contract.page_type == PagePromptType.API

    def test_data_model_doc_type(self) -> None:
        """Test data-model doc type mapping."""
        contract = get_contract_for_doc_type("data-model")
        assert contract.page_type == PagePromptType.DATA

    def test_data_doc_type(self) -> None:
        """Test data doc type mapping."""
        contract = get_contract_for_doc_type("data")
        assert contract.page_type == PagePromptType.DATA

    def test_entity_doc_type(self) -> None:
        """Test entity doc type mapping."""
        contract = get_contract_for_doc_type("entity")
        assert contract.page_type == PagePromptType.ENTITY

    def test_ops_doc_type(self) -> None:
        """Test ops doc type mapping."""
        contract = get_contract_for_doc_type("ops")
        assert contract.page_type == PagePromptType.OPS

    def test_operations_doc_type(self) -> None:
        """Test operations doc type mapping."""
        contract = get_contract_for_doc_type("operations")
        assert contract.page_type == PagePromptType.OPS

    def test_development_doc_type(self) -> None:
        """Test development doc type mapping."""
        contract = get_contract_for_doc_type("development")
        assert contract.page_type == PagePromptType.DEVELOPMENT

    def test_invalid_doc_type_raises(self) -> None:
        """Test that invalid doc type raises ValueError."""
        with pytest.raises(ValueError):
            get_contract_for_doc_type("invalid_type")


class TestPromptFragments:
    """Tests for prompt fragment templates."""

    def test_system_fragment_exists(self) -> None:
        """Test system prompt fragment exists."""
        assert SYSTEM_PROMPT_FRAGMENT is not None
        assert len(SYSTEM_PROMPT_FRAGMENT) > 0
        assert "证据引用" in SYSTEM_PROMPT_FRAGMENT
        assert "禁止幻觉" in SYSTEM_PROMPT_FRAGMENT

    def test_overview_fragment_exists(self) -> None:
        """Test overview fragment exists."""
        assert OVERVIEW_PROMPT_FRAGMENT is not None
        assert len(OVERVIEW_PROMPT_FRAGMENT) > 0
        assert "Overview Page Prompt Fragment" in OVERVIEW_PROMPT_FRAGMENT

    def test_service_fragment_exists(self) -> None:
        """Test service fragment exists."""
        assert SERVICE_PROMPT_FRAGMENT is not None
        assert len(SERVICE_PROMPT_FRAGMENT) > 0
        assert "Service Page Prompt Fragment" in SERVICE_PROMPT_FRAGMENT

    def test_api_fragment_exists(self) -> None:
        """Test API fragment exists."""
        assert API_PROMPT_FRAGMENT is not None
        assert len(API_PROMPT_FRAGMENT) > 0
        assert "API Page Prompt Fragment" in API_PROMPT_FRAGMENT

    def test_data_fragment_exists(self) -> None:
        """Test data fragment exists."""
        assert DATA_PROMPT_FRAGMENT is not None
        assert len(DATA_PROMPT_FRAGMENT) > 0
        assert "Data Model Page Prompt Fragment" in DATA_PROMPT_FRAGMENT

    def test_entity_fragment_exists(self) -> None:
        """Test entity fragment exists."""
        assert ENTITY_PROMPT_FRAGMENT is not None
        assert len(ENTITY_PROMPT_FRAGMENT) > 0
        assert "Entity Page Prompt Fragment" in ENTITY_PROMPT_FRAGMENT

    def test_ops_fragment_exists(self) -> None:
        """Test ops fragment exists."""
        assert OPS_PROMPT_FRAGMENT is not None
        assert len(OPS_PROMPT_FRAGMENT) > 0
        assert "Ops Page Prompt Fragment" in OPS_PROMPT_FRAGMENT

    def test_development_fragment_exists(self) -> None:
        """Test development fragment exists."""
        assert DEVELOPMENT_PROMPT_FRAGMENT is not None
        assert len(DEVELOPMENT_PROMPT_FRAGMENT) > 0
        assert "Development Page Prompt Fragment" in DEVELOPMENT_PROMPT_FRAGMENT


class TestGetPromptFragment:
    """Tests for get_prompt_fragment function."""

    def test_get_system_fragment(self) -> None:
        """Test getting system fragment."""
        fragment = get_prompt_fragment("system")
        assert fragment == SYSTEM_PROMPT_FRAGMENT

    def test_get_overview_fragment(self) -> None:
        """Test getting overview fragment."""
        fragment = get_prompt_fragment("overview")
        assert fragment == OVERVIEW_PROMPT_FRAGMENT

    def test_get_all_fragments(self) -> None:
        """Test getting all fragment types."""
        fragment_names = ["system", "overview", "service", "api", "data", "entity", "ops", "development"]
        for name in fragment_names:
            fragment = get_prompt_fragment(name)
            assert fragment is not None
            assert len(fragment) > 0

    def test_invalid_fragment_name_raises(self) -> None:
        """Test that invalid fragment name raises ValueError."""
        with pytest.raises(ValueError):
            get_prompt_fragment("invalid_fragment")


class TestRenderPromptFragment:
    """Tests for render_prompt_fragment function."""

    def test_render_overview_fragment(self) -> None:
        """Test rendering overview fragment with context."""
        context = {
            "repository_name": "test-repo",
            "primary_language": "python",
            "framework": "fastapi",
            "module_count": "5",
            "endpoint_count": "20",
            "model_count": "10",
            "repository_root": "/test/repo",
            "project_positioning": "Test positioning",
            "core_problem": "Test problem",
            "core_capabilities": "Test capabilities",
            "environment_requirements": "Test requirements",
            "startup_commands": "Test commands",
            "reading_navigation": "Test navigation",
            "domain_groups_markdown": "Test domains",
        }
        rendered = render_prompt_fragment("overview", context)
        assert "test-repo" in rendered
        assert "python" in rendered
        assert "fastapi" in rendered

    def test_render_service_fragment(self) -> None:
        """Test rendering service fragment with context."""
        context = {
            "section_title": "Test Section",
            "section_description": "Test description",
            "section_slug": "test-section",
            "section_modules": "Test modules",
            "section_apis": "Test APIs",
            "section_commands": "Test commands",
            "module_details": "Test module details",
            "section_data_models": "Test data models",
            "related_section": "related",
        }
        rendered = render_prompt_fragment("service", context)
        assert "Test Section" in rendered
        assert "Test description" in rendered

    def test_render_missing_key_raises(self) -> None:
        """Test that missing context key raises ValueError."""
        context = {"repository_name": "test-repo"}  # Missing other keys
        with pytest.raises(ValueError):
            render_prompt_fragment("overview", context)


class TestSnapshotTestPatterns:
    """Tests for snapshot test pattern validation."""

    def test_overview_snapshot_pattern_matches_overview(self) -> None:
        """Test overview pattern matches expected path."""
        contract = PAGE_PROMPT_CONTRACTS[PagePromptType.OVERVIEW]
        assert contract.snapshot_test_pattern is not None
        pattern = re.compile(contract.snapshot_test_pattern)
        assert pattern.match("docs/00-overview.md")
        assert not pattern.match("docs/01-architecture.md")

    def test_api_snapshot_pattern_matches_api_contracts(self) -> None:
        """Test API pattern matches expected path."""
        contract = PAGE_PROMPT_CONTRACTS[PagePromptType.API]
        assert contract.snapshot_test_pattern is not None
        pattern = re.compile(contract.snapshot_test_pattern)
        assert pattern.match("docs/04-api-contracts.md")

    def test_service_snapshot_pattern_matches_section(self) -> None:
        """Test service pattern matches section paths."""
        contract = PAGE_PROMPT_CONTRACTS[PagePromptType.SERVICE]
        assert contract.snapshot_test_pattern is not None
        pattern = re.compile(contract.snapshot_test_pattern)
        assert pattern.match("docs/sections/architecture/index.md")
        assert pattern.match("docs/sections/services/index.md")

    def test_data_snapshot_pattern_matches_data_model(self) -> None:
        """Test data pattern matches expected path."""
        contract = PAGE_PROMPT_CONTRACTS[PagePromptType.DATA]
        assert contract.snapshot_test_pattern is not None
        pattern = re.compile(contract.snapshot_test_pattern)
        assert pattern.match("docs/05-data-model.md")


class TestSecretRedaction:
    """Tests for secret redaction in prompt outputs."""

    def test_redact_api_key_in_overview_context(self) -> None:
        """Test API keys are redacted in rendered prompts."""
        context = {
            "repository_name": "test-repo",
            "primary_language": "python",
            "framework": "fastapi",
            "module_count": "5",
            "endpoint_count": "20",
            "model_count": "10",
            "repository_root": "/test/repo",
            "project_positioning": 'API_KEY="sk-1234567890abcdefghijklmnop"',
            "core_problem": "Test problem",
            "core_capabilities": "Test capabilities",
            "environment_requirements": "Test requirements",
            "startup_commands": "Test commands",
            "reading_navigation": "Test navigation",
            "domain_groups_markdown": "Test domains",
        }
        rendered = render_prompt_fragment("overview", context)
        redacted = redact_secrets(rendered)
        assert "sk-1234567890abcdefghijklmnop" not in redacted
        assert "[REDACTED]" in redacted

    def test_redact_bearer_token_in_context(self) -> None:
        """Test Bearer tokens are redacted in rendered prompts."""
        context = {
            "repository_name": "test-repo",
            "primary_language": "python",
            "framework": "fastapi",
            "module_count": "5",
            "endpoint_count": "20",
            "model_count": "10",
            "repository_root": "/test/repo",
            "project_positioning": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "core_problem": "Test problem",
            "core_capabilities": "Test capabilities",
            "environment_requirements": "Test requirements",
            "startup_commands": "Test commands",
            "reading_navigation": "Test navigation",
            "domain_groups_markdown": "Test domains",
        }
        rendered = render_prompt_fragment("overview", context)
        redacted = redact_secrets(rendered)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted


class TestContractEvidenceRequirements:
    """Tests for evidence requirement validation."""

    def test_overview_min_candidates(self) -> None:
        """Test overview contract has sufficient min_candidates."""
        contract = PAGE_PROMPT_CONTRACTS[PagePromptType.OVERVIEW]
        assert contract.evidence.min_candidates >= 8

    def test_api_min_candidates(self) -> None:
        """Test API contract has high min_candidates."""
        contract = PAGE_PROMPT_CONTRACTS[PagePromptType.API]
        assert contract.evidence.min_candidates >= 10

    def test_all_citation_styles_used(self) -> None:
        """Test that all citation styles are used across contracts."""
        styles_used = set()
        for contract in PAGE_PROMPT_CONTRACTS.values():
            styles_used.add(contract.evidence.citation_style)
        assert CitationStyle.CITE_BLOCK in styles_used
        assert CitationStyle.MARKDOWN_LINK in styles_used
        assert CitationStyle.SOURCE_FOOTER in styles_used


class TestAntiHallucinationRequirements:
    """Tests for anti-hallucination requirement coverage."""

    def test_overview_cite_all_symbols(self) -> None:
        """Test overview requires all symbols to be cited."""
        contract = PAGE_PROMPT_CONTRACTS[PagePromptType.OVERVIEW]
        assert contract.anti_hallucination.cite_all_symbols is True

    def test_overview_validate_file_paths(self) -> None:
        """Test overview requires file path validation."""
        contract = PAGE_PROMPT_CONTRACTS[PagePromptType.OVERVIEW]
        assert contract.anti_hallucination.validate_file_paths is True

    def test_entity_forbid_out_of_scope(self) -> None:
        """Test entity page allows out-of-scope content."""
        contract = PAGE_PROMPT_CONTRACTS[PagePromptType.ENTITY]
        assert contract.anti_hallucination.forbid_out_of_scope is False

    def test_ops_require_version_lock(self) -> None:
        """Test ops requires version locking."""
        contract = PAGE_PROMPT_CONTRACTS[PagePromptType.OPS]
        assert contract.anti_hallucination.require_version_lock is True


class TestHeadingStructure:
    """Tests for heading structure requirements."""

    def test_overview_has_h1(self) -> None:
        """Test overview has level 1 heading."""
        contract = PAGE_PROMPT_CONTRACTS[PagePromptType.OVERVIEW]
        h1_headings = [h for h in contract.heading_structure if h.level == 1]
        assert len(h1_headings) == 1

    def test_overview_has_multiple_h2(self) -> None:
        """Test overview has multiple level 2 headings."""
        contract = PAGE_PROMPT_CONTRACTS[PagePromptType.OVERVIEW]
        h2_headings = [h for h in contract.heading_structure if h.level == 2]
        assert len(h2_headings) >= 4

    def test_service_heading_count(self) -> None:
        """Test service page has sufficient heading structure."""
        contract = PAGE_PROMPT_CONTRACTS[PagePromptType.SERVICE]
        assert len(contract.heading_structure) >= 6

    def test_all_page_types_have_h1(self) -> None:
        """Test that all page types require a level 1 heading."""
        for contract in PAGE_PROMPT_CONTRACTS.values():
            h1_headings = [h for h in contract.heading_structure if h.level == 1]
            assert len(h1_headings) >= 1, f"{contract.page_type} missing H1 heading"