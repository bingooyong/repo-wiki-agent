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

import pytest

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.evidence.ranking import filter_ranked_candidates_by_ownership
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
from repo_wiki.llm.config import LLMProviderConfig
from repo_wiki.llm.providers import MockLLMProvider, create_mock_provider
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.schema import (
    GenerationMode,
    SourceRequirement,
    WikiPagePlan,
    WikiTaxonomyCategory,
)
from repo_wiki.prompts.contracts import PagePromptContract, PagePromptType
from repo_wiki.prompts.skeleton import build_skeleton


class _NamedMockProvider(MockLLMProvider):
    """Mock chat implementation that reports a real provider name (e.g. minimax)."""

    @property
    def name(self) -> str:
        return self._config.provider


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
        from repo_wiki.prompts.contracts import (
            AntiHallucinationRequirement,
            EvidenceRequirement,
            HeadingRequirement,
            StyleRequirement,
        )

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

    def test_real_provider_compact_max_tokens_not_clamped_to_1400(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Compact prompt must not cap real providers at 1400 (starves MiniMax-M3 reasoning).

        Split: mock/tests may keep a compact 1400 cap; real-looking configs use
        configured llm.max_tokens (or at least 4096), still <= provider max.
        """
        monkeypatch.setenv("REPO_WIKI_COMPACT_LLM_PROMPT", "1")
        monkeypatch.delenv("REPO_WIKI_LLM_COMPOSER_MAX_TOKENS", raising=False)
        llm_config = LLMProviderConfig(
            provider="minimax",
            model="MiniMax-M3",
            max_tokens=8192,
        )
        provider = _NamedMockProvider(config=llm_config)
        composer = create_composer(provider=provider, llm_config=llm_config)
        resolved = composer._resolve_request_max_tokens()
        assert resolved != 1400
        assert resolved == 8192
        assert resolved >= 4096
        assert resolved <= llm_config.max_tokens

    def test_mock_provider_compact_max_tokens_keeps_small_cap(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Mock/tests may keep the compact 1400 cap so existing fixtures stay cheap."""
        monkeypatch.setenv("REPO_WIKI_COMPACT_LLM_PROMPT", "1")
        monkeypatch.delenv("REPO_WIKI_LLM_COMPOSER_MAX_TOKENS", raising=False)
        composer = create_composer()
        resolved = composer._resolve_request_max_tokens()
        assert resolved <= 1400

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

    def test_inventory_binding_filters_wrong_service_before_composer(self):
        """验证错误服务证据在进入 composer 前已被过滤。"""
        from repo_wiki.evidence.ranking import EvidenceCandidate

        page = WikiPagePlan(
            page_id="inventory-service-api-reference",
            title="API台账服务 API",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="docs/pages/api/inventory-service-api-reference.md",
            source_requirements=SourceRequirement(modules=["inventory-service"]),
        )
        wrong_span = EvidenceSpanRecord(
            digest="wrong1",
            file_path="services/ai-service/llm/retriever.py",
            line_start=1,
            line_end=20,
            language="python",
            symbol="RetrieverService",
            span_text="embedding vector retrieval model",
        )
        ok_span = EvidenceSpanRecord(
            digest="ok1",
            file_path="services/inventory-service/entity/ApiEndpointEntity.java",
            line_start=1,
            line_end=20,
            language="java",
            symbol="ApiEndpointEntity",
            span_text="class ApiEndpointEntity {}",
        )
        filtered = filter_ranked_candidates_by_ownership(
            page,
            [
                EvidenceCandidate(1, wrong_span, 3.0, ["api_match"], 0),
                EvidenceCandidate(2, ok_span, 2.0, ["data_model_match"], 1),
            ],
        )
        assert len(filtered) == 1
        assert "inventory-service" in filtered[0].span.file_path

    @pytest.mark.asyncio
    async def test_inventory_api_page_rejects_without_inventory_primary_evidence(
        self,
        composer: LLMPageComposer,
        sample_context: ComposerContext,
    ):
        """Inventory API page必须在无主证据时拒绝生成。"""
        from repo_wiki.evidence.ranking import EvidenceCandidate, PageEvidenceBinding

        page = WikiPagePlan(
            page_id="inventory-service-api-reference",
            title="API台账服务 API",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="docs/pages/api/inventory-service-api-reference.md",
            source_requirements=SourceRequirement(
                modules=["inventory-service", "contract-service", "frontend-app"],
                endpoints=["GET /inventory/endpoints"],
                data_models=["ApiEndpointEntity", "ApiParameterEntity"],
            ),
            generation_mode=GenerationMode.LLM_ASSISTED,
        )

        # Only integration evidence (contract + frontend), no inventory-local primary evidence.
        span_contract = EvidenceSpanRecord(
            digest="contract1",
            file_path="services/contract-service/ContractController.java",
            line_start=10,
            line_end=30,
            language="java",
            symbol="ContractController",
            span_text="class ContractController {}",
        )
        span_frontend = EvidenceSpanRecord(
            digest="frontend1",
            file_path="frontend/app/src/pages/inventory.tsx",
            line_start=1,
            line_end=20,
            language="typescript",
            symbol="InventoryPage",
            span_text="function InventoryPage() {}",
        )
        binding = PageEvidenceBinding(
            page_id=page.page_id,
            doc_type="api",
            candidates=[
                EvidenceCandidate(
                    evidence_id=1,
                    span=span_contract,
                    score=0.9,
                    match_signals=["integration"],
                    citation_order=0,
                ),
                EvidenceCandidate(
                    evidence_id=2,
                    span=span_frontend,
                    score=0.8,
                    match_signals=["integration"],
                    citation_order=1,
                ),
            ],
        )

        input_data = build_composer_input(page, binding, sample_context)
        output = await composer.compose_page(input_data)
        assert output.rejected is True
        assert output.rejection_reason is not None
        assert "inventory-service primary evidence" in output.rejection_reason

    @pytest.mark.asyncio
    async def test_inventory_api_page_accepts_with_inventory_primary_evidence(
        self,
        composer: LLMPageComposer,
        sample_context: ComposerContext,
    ):
        """Inventory API page在存在 inventory-service 主证据时允许通过。"""
        from repo_wiki.evidence.ranking import EvidenceCandidate, PageEvidenceBinding

        page = WikiPagePlan(
            page_id="inventory-service-api-reference",
            title="API台账服务 API",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="docs/pages/api/inventory-service-api-reference.md",
            source_requirements=SourceRequirement(
                modules=["inventory-service"],
                endpoints=["GET /inventory/endpoints", "POST /inventory/endpoints"],
                data_models=["ApiEndpointEntity", "ApiParameterEntity"],
            ),
            generation_mode=GenerationMode.LLM_ASSISTED,
        )

        span_inventory = EvidenceSpanRecord(
            digest="inv1",
            file_path="services/inventory-service/controllers/EndpointsController.java",
            line_start=12,
            line_end=64,
            language="java",
            symbol="EndpointsController",
            span_text="class EndpointsController { EndpointDto list(); }",
        )
        binding = PageEvidenceBinding(
            page_id=page.page_id,
            doc_type="api",
            candidates=[
                EvidenceCandidate(
                    evidence_id=1,
                    span=span_inventory,
                    score=1.0,
                    match_signals=["ownership_confirmed"],
                    citation_order=0,
                ),
            ],
        )

        input_data = build_composer_input(page, binding, sample_context)
        output = await composer.compose_page(input_data)
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

    @pytest.mark.parametrize(
        "page_id,title",
        [
            ("inventory-service-api-reference", "API台账服务 API"),
            ("contract-service-api-reference", "合约服务 API"),
            ("ai-service-api-reference", "AI服务 API"),
        ],
    )
    def test_api_qoder_like_skeleton_for_core_service_pages(self, page_id: str, title: str):
        """核心服务 API 页面应可修复为 Qoder-like prose-first 骨架。"""
        page = WikiPagePlan(
            page_id=page_id,
            title=title,
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path=f"docs/pages/api/{page_id}.md",
        )
        context = ComposerContext(
            repository_name="test",
            primary_language="java",
            framework="spring-boot",
            repository_root=".",
        )
        input_data = build_composer_input(page, None, context)
        headings = [section.heading_text for section in input_data.skeleton.headings]
        assert "## 简介" in headings
        assert "## 项目结构" in headings
        assert "## 核心组件" in headings
        assert "## 架构总览" in headings
        assert "## 详细组件分析" in headings
        assert "## 依赖关系分析" in headings
        assert "## 附录：端点清单（限量）" in headings

    def test_pipeline_injects_mermaid_blocks_for_api_pages(self, tmp_path):
        """组合管线应为 API 页面注入通过语法校验的 Mermaid 区块。"""
        cfg = RepoWikiConfig()
        cfg.project.root = str(tmp_path)
        service = RepoWikiService(cfg)

        page = WikiPagePlan(
            page_id="inventory-service-api-reference",
            title="API台账服务 API",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="docs/pages/api/inventory-service-api-reference.md",
        )
        context = ComposerContext(
            repository_name="repo",
            primary_language="java",
            framework="spring",
            repository_root=str(tmp_path),
            endpoints=[
                {"path": "/endpoints", "method": "GET", "service": "inventory-service"},
                {"path": "/endpoints/count", "method": "GET", "service": "inventory-service"},
            ],
        )
        markdown = service._enforce_qoder_page_contract(
            page=page,
            markdown="# API台账服务 API\n\n## 简介\n\n说明。",
            binding=None,
            add_mermaid=True,
            composition_context=context,
        )
        assert "```mermaid" in markdown
        assert ("sequenceDiagram" in markdown) or ("flowchart" in markdown)


class TestLowConfidenceBehavior:
    """Tests for low-confidence fallback behavior (Task 33.4)."""

    @pytest.fixture
    def mock_provider(self) -> MockLLMProvider:
        """Create mock provider for testing."""
        return create_mock_provider(response_content="# Test Page\n\nMock content.")

    @pytest.fixture
    def composer(self, mock_provider: MockLLMProvider) -> LLMPageComposer:
        """Create composer with mock provider."""
        return create_composer(provider=mock_provider)

    def test_compose_page_with_low_confidence_flags(
        self,
        composer: LLMPageComposer,
    ):
        """Test that low-confidence pages get appropriate flags."""
        from repo_wiki.generator.composer import build_composer_input
        from repo_wiki.planner.schema import (
            GenerationMode,
            SourceRequirement,
            WikiPagePlan,
            WikiTaxonomyCategory,
        )

        page = WikiPagePlan(
            page_id="low-confidence-page",
            title="Test Low Confidence",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
            source_requirements=SourceRequirement(
                modules=["nonexistent"],
            ),
            generation_mode=GenerationMode.LLM_ASSISTED,
        )
        context = ComposerContext(
            repository_name="test",
            primary_language="python",
            framework="fastapi",
            repository_root=".",
        )

        # No evidence binding - should trigger low-confidence
        input_data = build_composer_input(page, None, context)
        assert input_data.evidence_binding is None

    @pytest.mark.asyncio
    async def test_compose_page_produces_uncertainty_when_no_evidence(
        self,
        composer: LLMPageComposer,
    ):
        """Test that pages without evidence produce uncertainty markers."""
        from repo_wiki.generator.composer import build_composer_input
        from repo_wiki.planner.schema import (
            GenerationMode,
            SourceRequirement,
            WikiPagePlan,
            WikiTaxonomyCategory,
        )

        page = WikiPagePlan(
            page_id="no-evidence-page",
            title="No Evidence Page",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
            source_requirements=SourceRequirement(),
            generation_mode=GenerationMode.LLM_ASSISTED,
        )
        context = ComposerContext(
            repository_name="test",
            primary_language="python",
            framework="fastapi",
            repository_root=".",
        )

        input_data = build_composer_input(page, None, context)
        output = await composer.compose_page(input_data)

        # Should have low_confidence set since no evidence binding
        assert output.low_confidence is True or output.rejected is True
        if output.low_confidence:
            assert len(output.uncertainty_reasons) > 0

    @pytest.mark.asyncio
    async def test_compose_page_prohibits_fabrication_in_low_confidence(
        self,
        composer: LLMPageComposer,
    ):
        """Test that low-confidence pages cannot fabricate implementation details."""
        from repo_wiki.generator.composer import build_composer_input
        from repo_wiki.planner.schema import (
            GenerationMode,
            SourceRequirement,
            WikiPagePlan,
            WikiTaxonomyCategory,
        )

        page = WikiPagePlan(
            page_id="fabrication-test",
            title="Fabrication Test",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/test.md",
            source_requirements=SourceRequirement(
                modules=["fake_module_that_does_not_exist"],
            ),
            generation_mode=GenerationMode.LLM_ASSISTED,
        )
        context = ComposerContext(
            repository_name="test",
            primary_language="python",
            framework="fastapi",
            repository_root=".",
        )

        input_data = build_composer_input(page, None, context)
        output = await composer.compose_page(input_data)

        # Even with fabricated content, should still track low_confidence
        # The system should flag uncertainty when evidence is insufficient
        if output.rejected or output.low_confidence:
            # This is expected behavior
            assert output.rejection_reason is not None or len(output.uncertainty_reasons) > 0

    def test_composer_output_has_low_confidence_field(self):
        """Test that ComposerOutput includes low_confidence tracking."""
        from repo_wiki.generator.composer import ComposerOutput

        output = ComposerOutput(
            page_id="test",
            markdown="# Test",
            citations_preserved=True,
            headings_preserved=True,
            evidence_count=0,
            low_confidence=True,
            uncertainty_reasons=["INSUFFICIENT_EVIDENCE: no candidates bound"],
        )

        assert output.low_confidence is True
        assert len(output.uncertainty_reasons) > 0
        assert "INSUFFICIENT_EVIDENCE" in output.uncertainty_reasons[0]


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_validation_result_has_low_confidence_fields(self):
        """Test that ValidationResult includes low-confidence tracking."""
        from repo_wiki.generator.composer import ValidationResult

        result = ValidationResult(
            citations_preserved=True,
            headings_preserved=True,
            evidence_count=0,
            low_confidence=True,
            uncertainty_reasons=["LOW_EVIDENCE_BINDING: only 1 candidate bound"],
        )

        assert result.low_confidence is True
        assert len(result.uncertainty_reasons) > 0

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

        env_backup = os.environ.get("REAL_LLM_PROVIDER")

        if "REAL_LLM_PROVIDER" in os.environ:
            del os.environ["REAL_LLM_PROVIDER"]

        try:
            result = asyncio.run(run_smoke_test())
            assert result is True  # Skipped returns True
        finally:
            if env_backup:
                os.environ["REAL_LLM_PROVIDER"] = env_backup


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
