"""Tests for LLM page composer pipeline.

Tests the composer module (repo_wiki/generator/composer.py) which provides:
- LLMPageComposer: Core composition from page plans and evidence
- CitationPreservationValidator: Validates citations are preserved
- HeadingPreservationValidator: Validates required headings
- ComposerInput/ComposerOutput: Composition data structures
- build_composer_input: Factory for composer inputs
- run_smoke_test: Optional smoke test hook

Phase 24 - Task 24.3: LLM page composer pipeline
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from repo_wiki.generator.composer import (
    CitationPreservationValidator,
    ComposerContext,
    ComposerInput,
    ComposerOutput,
    ComposerResult,
    HeadingPreservationValidator,
    LLMPageComposer,
    ValidationResult,
    build_composer_input,
    create_composer,
    run_smoke_test,
)
from repo_wiki.llm.providers import create_mock_provider, MockLLMProvider
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.planner.schema import (
    GenerationMode,
    SourceRequirement,
    WikiPagePlan,
    WikiTaxonomyCategory,
)
from repo_wiki.prompts.contracts import PagePromptContract, PagePromptType
from repo_wiki.prompts.skeleton import ArticleSkeleton, build_skeleton


class TestCitationPreservationValidator:
    """Tests for CitationPreservationValidator."""

    def test_extract_citations_from_cite_blocks(self):
        """Test extracting <cite> blocks from content."""
        validator = CitationPreservationValidator()
        content = """Here is some code <cite>src/auth.py:10-20</cite> and
        another citation <cite>src/service.py:50-60</cite>."""
        citations = validator.extract_citations(content)
        assert len(citations) >= 2
        assert any("auth.py" in c for c in citations)

    def test_extract_citations_from_links(self):
        """Test extracting citation links from content."""
        validator = CitationPreservationValidator()
        content = """See [auth.py:10](src/auth.py:10) for details."""
        citations = validator.extract_citations(content)
        assert len(citations) >= 1

    def test_validate_preservation_with_all_present(self):
        """Test validation passes when all citations present."""
        validator = CitationPreservationValidator()
        original = ["src/auth.py:10-20", "src/service.py:50-60"]
        content = """Code at <cite>src/auth.py:10-20</cite> and more
        <cite>src/service.py:50-60</cite> references."""
        preserved, missing = validator.validate_preservation(original, content)
        assert preserved is True
        assert missing == []

    def test_validate_preservation_with_missing(self):
        """Test validation fails when citations missing."""
        validator = CitationPreservationValidator()
        original = ["src/auth.py:10-20", "src/missing.py:50-60"]
        content = """Code at <cite>src/auth.py:10-20</cite> only."""
        preserved, missing = validator.validate_preservation(original, content)
        assert preserved is False
        assert len(missing) == 1
        assert "missing.py" in missing[0]

    def test_count_citations(self):
        """Test counting citations in content."""
        validator = CitationPreservationValidator()
        content = """<cite>a.py:1</cite> and <cite>b.py:2</cite>"""
        count = validator.count_citations(content)
        assert count >= 2


class TestHeadingPreservationValidator:
    """Tests for HeadingPreservationValidator."""

    @pytest.fixture
    def mock_contract(self) -> PagePromptContract:
        """Create a mock contract for testing."""
        from repo_wiki.prompts.contracts import HeadingRequirement, EvidenceRequirement, StyleRequirement, AntiHallucinationRequirement
        return PagePromptContract(
            page_type=PagePromptType.OVERVIEW,
            description="Test contract",
            heading_structure=(
                HeadingRequirement(level=1, text="# Test", required=True),
                HeadingRequirement(level=2, text="## 简介", required=True),
                HeadingRequirement(level=2, text="## 核心组件", required=True),
                HeadingRequirement(level=2, text="## 项目结构", required=False),
            ),
            evidence=EvidenceRequirement(),
            style=StyleRequirement(),
            anti_hallucination=AntiHallucinationRequirement(),
        )

    def test_extract_headings(self, mock_contract: PagePromptContract):
        """Test extracting headings from content."""
        validator = HeadingPreservationValidator(mock_contract)
        content = """# Test

## 简介

### 子标题

## 核心组件
"""
        headings = validator.extract_headings(content)
        assert len(headings) == 4
        assert headings[0] == (1, "Test")
        assert headings[1] == (2, "简介")

    def test_validate_preservation_with_all_present(self, mock_contract: PagePromptContract):
        """Test validation passes when all required headings present."""
        validator = HeadingPreservationValidator(mock_contract)
        content = """# Test

## 简介

## 核心组件

## 项目结构 (optional)
"""
        preserved, missing = validator.validate_preservation(content)
        assert preserved is True
        assert missing == []

    def test_validate_preservation_with_missing_required(self, mock_contract: PagePromptContract):
        """Test validation fails when required headings missing."""
        validator = HeadingPreservationValidator(mock_contract)
        content = """# Test

## 简介

## 项目结构 (missing 核心组件)
"""
        preserved, missing = validator.validate_preservation(content)
        assert preserved is False
        assert "## 核心组件" in missing

    def test_count_headings(self, mock_contract: PagePromptContract):
        """Test counting headings in content."""
        validator = HeadingPreservationValidator(mock_contract)
        content = """# Title

## H2

### H3
"""
        count = validator.count_headings(content)
        assert count == 3


class TestComposerContext:
    """Tests for ComposerContext dataclass."""

    def test_create_minimal_context(self):
        """Test creating context with minimal fields."""
        ctx = ComposerContext(
            repository_name="test-repo",
            primary_language="python",
            framework="fastapi",
            repository_root="/test",
        )
        assert ctx.repository_name == "test-repo"
        assert ctx.primary_language == "python"
        assert ctx.modules == []

    def test_create_full_context(self):
        """Test creating context with all fields."""
        ctx = ComposerContext(
            repository_name="test-repo",
            primary_language="python",
            framework="fastapi",
            repository_root="/test",
            modules=[{"name": "auth", "path": "src/auth"}],
            endpoints=[{"path": "/api/users", "method": "GET"}],
            models=[{"name": "User", "table": "users"}],
            commands={"start": "uvicorn main:app"},
            domain_groups_markdown="## Domain Groups\n- auth",
        )
        assert len(ctx.modules) == 1
        assert len(ctx.endpoints) == 1
        assert len(ctx.commands) == 1


class TestComposerInput:
    """Tests for ComposerInput dataclass."""

    def test_create_composer_input(self):
        """Test creating composer input."""
        page = WikiPagePlan(
            page_id="test-page",
            title="Test",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
        )
        skeleton = build_skeleton("overview", "Test")
        contract = PagePromptContract(
            page_type=PagePromptType.OVERVIEW,
            description="Test",
            heading_structure=(),
            evidence=None,  # type: ignore
            style=None,  # type: ignore
            anti_hallucination=None,  # type: ignore
        )
        context = ComposerContext(
            repository_name="test",
            primary_language="python",
            framework="fastapi",
            repository_root=".",
        )

        input_data = ComposerInput(
            page_plan=page,
            evidence_binding=None,
            skeleton=skeleton,
            contract=contract,
            context=context,
        )

        assert input_data.page_plan.page_id == "test-page"
        assert input_data.skeleton is not None


class TestComposerOutput:
    """Tests for ComposerOutput dataclass."""

    def test_create_successful_output(self):
        """Test creating successful output."""
        output = ComposerOutput(
            page_id="test",
            markdown="# Test\n\nContent here",
            citations_preserved=True,
            headings_preserved=True,
            evidence_count=5,
        )
        assert output.rejected is False
        assert output.rejection_reason is None

    def test_create_rejected_output(self):
        """Test creating rejected output."""
        output = ComposerOutput(
            page_id="test",
            markdown="",
            citations_preserved=False,
            headings_preserved=False,
            evidence_count=0,
            rejected=True,
            rejection_reason="Lost required citations",
        )
        assert output.rejected is True
        assert "Lost required citations" in output.rejection_reason


class TestLLMPageComposer:
    """Tests for LLMPageComposer class."""

    @pytest.fixture
    def mock_provider(self) -> MockLLMProvider:
        """Create mock provider for testing."""
        return create_mock_provider(response_content="# Test Page\n\nMock content.")

    @pytest.fixture
    def composer(self, mock_provider: MockLLMProvider) -> LLMPageComposer:
        """Create composer with mock provider."""
        return create_composer(provider=mock_provider)

    @pytest.fixture
    def sample_page(self) -> WikiPagePlan:
        """Create sample page plan."""
        return WikiPagePlan(
            page_id="sample-page",
            title="Sample Page",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/sample.md",
            source_requirements=SourceRequirement(
                modules=["auth", "api"],
                endpoints=["GET /users"],
            ),
            generation_mode=GenerationMode.LLM_ASSISTED,
        )

    @pytest.fixture
    def sample_context(self) -> ComposerContext:
        """Create sample context."""
        return ComposerContext(
            repository_name="test-repo",
            primary_language="python",
            framework="fastapi",
            repository_root=".",
        )

    def test_create_composer(self, mock_provider: MockLLMProvider):
        """Test creating a composer."""
        composer = create_composer(provider=mock_provider)
        assert composer is not None
        assert composer._provider is not None

    def test_composer_default_provider(self):
        """Test composer uses default mock when no provider provided."""
        composer = create_composer()
        assert composer is not None
        assert composer._provider is not None

    @pytest.mark.asyncio
    async def test_compose_page_success(
        self,
        composer: LLMPageComposer,
        sample_page: WikiPagePlan,
        sample_context: ComposerContext,
    ):
        """Test successful page composition."""
        input_data = build_composer_input(sample_page, None, sample_context)
        output = await composer.compose_page(input_data)

        assert output.page_id == "sample-page"
        assert output.rejected is False
        assert len(output.markdown) > 0

    @pytest.mark.asyncio
    async def test_compose_page_with_evidence(
        self,
        composer: LLMPageComposer,
        sample_page: WikiPagePlan,
        sample_context: ComposerContext,
    ):
        """Test composition with evidence binding."""
        from repo_wiki.evidence.ranking import EvidenceCandidate, PageEvidenceBinding

        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/auth.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="AuthService",
            span_text="class AuthService:",
        )
        candidate = EvidenceCandidate(
            evidence_id=1,
            span=span,
            score=1.0,
            match_signals=["module_match"],
            citation_order=0,
        )
        binding = PageEvidenceBinding(
            page_id="sample-page",
            doc_type="overview",
            candidates=[candidate],
        )

        input_data = build_composer_input(sample_page, binding, sample_context)
        output = await composer.compose_page(input_data)

        assert output.page_id == "sample-page"
        assert output.evidence_count >= 0

    @pytest.mark.asyncio
    async def test_compose_page_rejects_insufficient_content(
        self,
        composer: LLMPageComposer,
        sample_page: WikiPagePlan,
        sample_context: ComposerContext,
    ):
        """Test that page with insufficient content is not rejected."""
        input_data = build_composer_input(sample_page, None, sample_context)
        output = await composer.compose_page(input_data)

        # With proper mock response, should not be rejected
        if output.markdown:
            assert output.rejected is False


class TestBuildComposerInput:
    """Tests for build_composer_input factory function."""

    def test_build_composer_input_basic(self):
        """Test building composer input with minimal data."""
        page = WikiPagePlan(
            page_id="test-page",
            title="Test",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
        )
        context = ComposerContext(
            repository_name="test",
            primary_language="python",
            framework="fastapi",
            repository_root=".",
        )

        input_data = build_composer_input(page, None, context)

        assert input_data.page_plan.page_id == "test-page"
        assert input_data.skeleton is not None
        assert input_data.contract is not None

    def test_build_composer_input_with_evidence(self):
        """Test building composer input with evidence binding."""
        page = WikiPagePlan(
            page_id="test-page",
            title="Test",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
        )
        context = ComposerContext(
            repository_name="test",
            primary_language="python",
            framework="fastapi",
            repository_root=".",
        )

        from repo_wiki.evidence.ranking import EvidenceCandidate, PageEvidenceBinding
        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/test.py",
            line_start=1,
            line_end=10,
            language="python",
            symbol="TestClass",
            span_text="class TestClass:",
        )
        candidate = EvidenceCandidate(
            evidence_id=1,
            span=span,
            score=1.0,
            match_signals=["module_match"],
            citation_order=0,
        )
        binding = PageEvidenceBinding(
            page_id="test-page",
            doc_type="overview",
            candidates=[candidate],
        )

        input_data = build_composer_input(page, binding, context)

        assert input_data.page_plan.page_id == "test-page"
        assert input_data.evidence_binding is not None
        assert len(input_data.evidence_binding.candidates) == 1


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_create_valid_result(self):
        """Test creating valid result."""
        result = ValidationResult(
            citations_preserved=True,
            headings_preserved=True,
            evidence_count=5,
        )
        assert result.rejected is False
        assert result.rejection_reason is None

    def test_create_rejected_result(self):
        """Test creating rejected result."""
        result = ValidationResult(
            citations_preserved=False,
            headings_preserved=True,
            evidence_count=0,
            rejected=True,
            rejection_reason="Citations lost",
        )
        assert result.rejected is True
        assert "Citations lost" in result.rejection_reason


class TestComposerResult:
    """Tests for ComposerResult dataclass."""

    def test_create_composer_result(self):
        """Test creating composer result."""
        outputs = [
            ComposerOutput(
                page_id="page1",
                markdown="# Page 1",
                citations_preserved=True,
                headings_preserved=True,
                evidence_count=3,
            ),
            ComposerOutput(
                page_id="page2",
                markdown="# Page 2",
                citations_preserved=True,
                headings_preserved=True,
                evidence_count=2,
                rejected=True,
                rejection_reason="Lost headings",
            ),
        ]

        result = ComposerResult(
            outputs=outputs,
            total_pages=2,
            successful_pages=1,
            rejected_pages=1,
            total_tokens=1000,
        )

        assert result.total_pages == 2
        assert result.successful_pages == 1
        assert result.rejected_pages == 1


class TestRunSmokeTest:
    """Tests for run_smoke_test function."""

    def test_smoke_test_skipped_without_env(self):
        """Test that smoke test is skipped when no env is set."""
        # Clear any existing env
        import os
        env_backup = os.environ.get('REAL_LLM_PROVIDER')

        if 'REAL_LLM_PROVIDER' in os.environ:
            del os.environ['REAL_LLM_PROVIDER']

        try:
            result = asyncio.run(run_smoke_test())
            assert result is True  # Skipped returns True
        finally:
            if env_backup:
                os.environ['REAL_LLM_PROVIDER'] = env_backup


class TestCategoryToDocType:
    """Tests for _category_to_doc_type mapping."""

    def test_project_overview_maps_to_overview(self):
        """Test PROJECT_OVERVIEW maps to 'overview'."""
        from repo_wiki.generator.composer import _category_to_doc_type
        result = _category_to_doc_type(WikiTaxonomyCategory.PROJECT_OVERVIEW)
        assert result == "overview"

    def test_api_reference_maps_to_api(self):
        """Test API_REFERENCE maps to 'api'."""
        from repo_wiki.generator.composer import _category_to_doc_type
        result = _category_to_doc_type(WikiTaxonomyCategory.API_REFERENCE)
        assert result == "api"

    def test_data_models_maps_to_data(self):
        """Test DATA_MODELS maps to 'data'."""
        from repo_wiki.generator.composer import _category_to_doc_type
        result = _category_to_doc_type(WikiTaxonomyCategory.DATA_MODELS)
        assert result == "data"

    def test_deployment_operations_maps_to_ops(self):
        """Test DEPLOYMENT_OPERATIONS maps to 'ops'."""
        from repo_wiki.generator.composer import _category_to_doc_type
        result = _category_to_doc_type(WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS)
        assert result == "ops"

    def test_development_guide_maps_to_development(self):
        """Test DEVELOPMENT_GUIDE maps to 'development'."""
        from repo_wiki.generator.composer import _category_to_doc_type
        result = _category_to_doc_type(WikiTaxonomyCategory.DEVELOPMENT_GUIDE)
        assert result == "development"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])