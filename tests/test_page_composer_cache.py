"""Tests for page composer incremental cache.

Tests the composer_cache module (repo_wiki/generator/composer_cache.py) which provides:
- Input hash computation from page plans, evidence, prompts, model config
- Caching to avoid repeated LLM calls for unchanged pages
- Token/cost tracking per page
- Output hash persistence

Phase 24 - Task 24.6: Page composer incremental cache
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.evidence.ranking import EvidenceCandidate, PageEvidenceBinding
from repo_wiki.generator.composer import (
    ComposerContext,
    ComposerInput,
)
from repo_wiki.generator.composer_cache import (
    CachedComposerMixin,
    ComposerCache,
    ComposerCacheStats,
    compute_composer_input_hash,
    compute_context_hash,
    compute_evidence_hash,
    compute_output_hash,
    compute_page_plan_hash,
    compute_skeleton_hash,
    create_composer_cache,
    estimate_cost_from_tokens,
    estimate_tokens_from_markdown,
    format_cache_stats,
    lookup_composer_cache,
)
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.schema import (
    GenerationMode,
    SourceRequirement,
    WikiPagePlan,
    WikiTaxonomyCategory,
)
from repo_wiki.prompts.contracts import PagePromptType
from repo_wiki.prompts.skeleton import ArticleSkeleton, build_skeleton


def _pre_narrow_context_hash(context: ComposerContext) -> str:
    """Exact ``compute_context_hash`` before 8d6395c (snapshot dumps + root)."""
    parts = [
        context.repository_name,
        context.primary_language,
        context.framework,
        context.repository_root,
        context.product_description or "",
    ]
    modules = sorted(context.modules, key=lambda m: m.get("name", ""))
    parts.append(json.dumps(modules, sort_keys=True))
    endpoints = sorted(context.endpoints, key=lambda e: e.get("path", ""))
    parts.append(json.dumps(endpoints, sort_keys=True))
    models = sorted(context.models, key=lambda m: m.get("name", ""))
    parts.append(json.dumps(models, sort_keys=True))
    commands = json.dumps(dict(sorted(context.commands.items())), sort_keys=True)
    parts.append(commands)
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]


def _pre_narrow_composer_input_hash(
    input_data: ComposerInput,
    model_name: str = "mock-gpt",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Exact ``compute_composer_input_hash`` before 8d6395c (no contract_id)."""
    combined = "|".join(
        [
            compute_page_plan_hash(input_data.page_plan),
            compute_evidence_hash(input_data.evidence_binding),
            compute_skeleton_hash(input_data.skeleton),
            _pre_narrow_context_hash(input_data.context),
            model_name,
            str(temperature),
            str(max_tokens),
        ]
    )
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


def _noisy_composer_input(
    sample_page: WikiPagePlan,
    sample_skeleton: ArticleSkeleton,
) -> ComposerInput:
    """Composer input whose pre-8d6395c hash includes incidental snapshot noise."""
    from repo_wiki.prompts.contracts import get_contract_for_page_type

    contract = get_contract_for_page_type(PagePromptType.OVERVIEW)
    return ComposerInput(
        page_plan=sample_page,
        evidence_binding=None,
        skeleton=sample_skeleton,
        contract=contract,
        context=ComposerContext(
            repository_name="test-repo",
            primary_language="python",
            framework="fastapi",
            repository_root="/workspace/fastapi-realworld",
            product_description="A RealWorld FastAPI backend",
            modules=[
                {
                    "name": "auth",
                    "path": "app/api/routes/auth.py",
                    "exports": ["login", "register"],
                    "domain_confidence": 0.41,
                    "domain_classification_reason": "first-scan",
                }
            ],
            endpoints=[{"path": "/users/login", "method": "POST", "line_number": 12}],
            commands={"test": "pytest"},
        ),
    )


class TestComputePagePlanHash:
    """Tests for compute_page_plan_hash function."""

    def test_same_page_same_hash(self):
        """Test that same page plan produces same hash."""
        page1 = WikiPagePlan(
            page_id="test-page",
            title="Test Page",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
        )
        page2 = WikiPagePlan(
            page_id="test-page",
            title="Test Page",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
        )

        hash1 = compute_page_plan_hash(page1)
        hash2 = compute_page_plan_hash(page2)

        assert hash1 == hash2

    def test_different_page_different_hash(self):
        """Test that different page plans produce different hashes."""
        page1 = WikiPagePlan(
            page_id="test-page-1",
            title="Test Page 1",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test1.md",
        )
        page2 = WikiPagePlan(
            page_id="test-page-2",
            title="Test Page 2",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test2.md",
        )

        hash1 = compute_page_plan_hash(page1)
        hash2 = compute_page_plan_hash(page2)

        assert hash1 != hash2

    def test_different_category_different_hash(self):
        """Test that different categories produce different hashes."""
        page1 = WikiPagePlan(
            page_id="test-page",
            title="Test Page",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
        )
        page2 = WikiPagePlan(
            page_id="test-page",
            title="Test Page",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="docs/test.md",
        )

        hash1 = compute_page_plan_hash(page1)
        hash2 = compute_page_plan_hash(page2)

        assert hash1 != hash2

    def test_with_source_requirements(self):
        """Test hash with source requirements."""
        page1 = WikiPagePlan(
            page_id="test-page",
            title="Test Page",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
            source_requirements=SourceRequirement(
                modules=["auth", "api"],
                endpoints=["GET /users"],
            ),
        )
        page2 = WikiPagePlan(
            page_id="test-page",
            title="Test Page",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
            source_requirements=SourceRequirement(
                modules=["auth", "api"],
                endpoints=["GET /users"],
            ),
        )

        hash1 = compute_page_plan_hash(page1)
        hash2 = compute_page_plan_hash(page2)

        assert hash1 == hash2

    def test_different_source_requirements_different_hash(self):
        """Test that different source requirements produce different hashes."""
        page1 = WikiPagePlan(
            page_id="test-page",
            title="Test Page",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
            source_requirements=SourceRequirement(
                modules=["auth"],
            ),
        )
        page2 = WikiPagePlan(
            page_id="test-page",
            title="Test Page",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
            source_requirements=SourceRequirement(
                modules=["api"],
            ),
        )

        hash1 = compute_page_plan_hash(page1)
        hash2 = compute_page_plan_hash(page2)

        assert hash1 != hash2


class TestComputeEvidenceHash:
    """Tests for compute_evidence_hash function."""

    def test_none_binding_hash(self):
        """Test hash for None evidence binding."""
        hash1 = compute_evidence_hash(None)
        hash2 = compute_evidence_hash(None)

        assert hash1 == hash2
        assert len(hash1) == 24

    def test_same_evidence_same_hash(self):
        """Test that same evidence binding produces same hash."""
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
        binding1 = PageEvidenceBinding(
            page_id="test-page",
            doc_type="overview",
            candidates=[candidate],
        )
        binding2 = PageEvidenceBinding(
            page_id="test-page",
            doc_type="overview",
            candidates=[candidate],
        )

        hash1 = compute_evidence_hash(binding1)
        hash2 = compute_evidence_hash(binding2)

        assert hash1 == hash2

    def test_different_evidence_different_hash(self):
        """Test that different evidence bindings produce different hashes."""
        span1 = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/auth.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="AuthService",
            span_text="class AuthService:",
        )
        span2 = EvidenceSpanRecord(
            digest="def456",
            file_path="src/api.py",
            line_start=30,
            line_end=40,
            language="python",
            symbol="APIService",
            span_text="class APIService:",
        )
        candidate1 = EvidenceCandidate(
            evidence_id=1,
            span=span1,
            score=1.0,
            match_signals=["module_match"],
            citation_order=0,
        )
        candidate2 = EvidenceCandidate(
            evidence_id=2,
            span=span2,
            score=0.9,
            match_signals=["api_match"],
            citation_order=1,
        )
        binding1 = PageEvidenceBinding(
            page_id="test-page",
            doc_type="overview",
            candidates=[candidate1],
        )
        binding2 = PageEvidenceBinding(
            page_id="test-page",
            doc_type="overview",
            candidates=[candidate1, candidate2],
        )

        hash1 = compute_evidence_hash(binding1)
        hash2 = compute_evidence_hash(binding2)

        assert hash1 != hash2


class TestComputeSkeletonHash:
    """Tests for compute_skeleton_hash function."""

    def test_same_skeleton_same_hash(self):
        """Test that same skeleton produces same hash."""
        skeleton1 = build_skeleton("overview", "Test")
        skeleton2 = build_skeleton("overview", "Test")

        hash1 = compute_skeleton_hash(skeleton1)
        hash2 = compute_skeleton_hash(skeleton2)

        assert hash1 == hash2

    def test_different_title_different_hash(self):
        """Test that different titles produce different hashes."""
        skeleton1 = build_skeleton("overview", "Test Title 1")
        skeleton2 = build_skeleton("overview", "Test Title 2")

        hash1 = compute_skeleton_hash(skeleton1)
        hash2 = compute_skeleton_hash(skeleton2)

        assert hash1 != hash2


class TestComputeContextHash:
    """Tests for compute_context_hash function."""

    def test_same_context_same_hash(self):
        """Test that same context produces same hash."""
        ctx1 = ComposerContext(
            repository_name="test-repo",
            primary_language="python",
            framework="fastapi",
            repository_root="/test",
        )
        ctx2 = ComposerContext(
            repository_name="test-repo",
            primary_language="python",
            framework="fastapi",
            repository_root="/test",
        )

        hash1 = compute_context_hash(ctx1)
        hash2 = compute_context_hash(ctx2)

        assert hash1 == hash2

    def test_different_framework_different_hash(self):
        """Test that different frameworks produce different hashes."""
        ctx1 = ComposerContext(
            repository_name="test-repo",
            primary_language="python",
            framework="fastapi",
            repository_root="/test",
        )
        ctx2 = ComposerContext(
            repository_name="test-repo",
            primary_language="python",
            framework="django",
            repository_root="/test",
        )

        hash1 = compute_context_hash(ctx1)
        hash2 = compute_context_hash(ctx2)

        assert hash1 != hash2


class TestComputeComposerInputHash:
    """Tests for compute_composer_input_hash function."""

    @pytest.fixture
    def sample_page(self) -> WikiPagePlan:
        """Create sample page plan."""
        return WikiPagePlan(
            page_id="test-page",
            title="Test Page",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
            source_requirements=SourceRequirement(
                modules=["auth", "api"],
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
            repository_root="/test",
        )

    @pytest.fixture
    def sample_skeleton(self) -> ArticleSkeleton:
        """Create sample skeleton."""
        return build_skeleton("overview", "Test Page")

    def test_same_input_same_hash(
        self,
        sample_page: WikiPagePlan,
        sample_context: ComposerContext,
        sample_skeleton: ArticleSkeleton,
    ):
        """Test that same input produces same hash."""
        from repo_wiki.prompts.contracts import get_contract_for_page_type

        contract = get_contract_for_page_type(PagePromptType.OVERVIEW)

        input1 = ComposerInput(
            page_plan=sample_page,
            evidence_binding=None,
            skeleton=sample_skeleton,
            contract=contract,
            context=sample_context,
        )
        input2 = ComposerInput(
            page_plan=sample_page,
            evidence_binding=None,
            skeleton=sample_skeleton,
            contract=contract,
            context=sample_context,
        )

        hash1 = compute_composer_input_hash(input1)
        hash2 = compute_composer_input_hash(input2)

        assert hash1 == hash2

    def test_different_model_different_hash(
        self,
        sample_page: WikiPagePlan,
        sample_context: ComposerContext,
        sample_skeleton: ArticleSkeleton,
    ):
        """Test that different model names produce different hashes."""
        from repo_wiki.prompts.contracts import get_contract_for_page_type

        contract = get_contract_for_page_type(PagePromptType.OVERVIEW)

        input1 = ComposerInput(
            page_plan=sample_page,
            evidence_binding=None,
            skeleton=sample_skeleton,
            contract=contract,
            context=sample_context,
        )
        input2 = ComposerInput(
            page_plan=sample_page,
            evidence_binding=None,
            skeleton=sample_skeleton,
            contract=contract,
            context=sample_context,
        )

        hash1 = compute_composer_input_hash(input1, model_name="gpt-4o")
        hash2 = compute_composer_input_hash(input2, model_name="gpt-4o-mini")

        assert hash1 != hash2

    def test_incidental_snapshot_fields_do_not_change_hash(
        self,
        sample_page: WikiPagePlan,
        sample_skeleton: ArticleSkeleton,
    ):
        """Rescan noise must not invalidate page-local composer cache.

        The compact prompt uses repository name, product description, and
        page source_requirements — not full module/endpoint dumps, scanner
        confidence, export list order, or the absolute repository_root.
        A second generate/improve against an unchanged page must hash-hit.
        """
        from repo_wiki.prompts.contracts import get_contract_for_page_type

        contract = get_contract_for_page_type(PagePromptType.OVERVIEW)
        context_first = ComposerContext(
            repository_name="test-repo",
            primary_language="python",
            framework="fastapi",
            repository_root="/workspace/fastapi-realworld",
            product_description="A RealWorld FastAPI backend",
            modules=[
                {
                    "name": "auth",
                    "path": "app/api/routes/auth.py",
                    "exports": ["login", "register"],
                    "domain_confidence": 0.41,
                    "domain_classification_reason": "first-scan",
                }
            ],
            endpoints=[{"path": "/users/login", "method": "POST", "line_number": 12}],
        )
        context_rescan = ComposerContext(
            repository_name="test-repo",
            primary_language="python",
            framework="fastapi",
            repository_root="/tmp/other-checkout/fastapi-realworld",
            product_description="A RealWorld FastAPI backend",
            modules=[
                {
                    "name": "auth",
                    "path": "app/api/routes/auth.py",
                    "exports": ["register", "login"],
                    "domain_confidence": 0.93,
                    "domain_classification_reason": "second-scan",
                }
            ],
            endpoints=[{"path": "/users/login", "method": "POST", "line_number": 40}],
        )
        input_first = ComposerInput(
            page_plan=sample_page,
            evidence_binding=None,
            skeleton=sample_skeleton,
            contract=contract,
            context=context_first,
        )
        input_rescan = ComposerInput(
            page_plan=sample_page,
            evidence_binding=None,
            skeleton=sample_skeleton,
            contract=contract,
            context=context_rescan,
        )

        assert compute_composer_input_hash(input_first, model_name="minimax") == (
            compute_composer_input_hash(input_rescan, model_name="minimax")
        )

    def test_product_description_change_does_change_hash(
        self,
        sample_page: WikiPagePlan,
        sample_skeleton: ArticleSkeleton,
    ):
        """Prompt-affecting context must still invalidate the cache."""
        from repo_wiki.prompts.contracts import get_contract_for_page_type

        contract = get_contract_for_page_type(PagePromptType.OVERVIEW)
        shared = {
            "repository_name": "test-repo",
            "primary_language": "python",
            "framework": "fastapi",
            "repository_root": "/test",
        }
        input_a = ComposerInput(
            page_plan=sample_page,
            evidence_binding=None,
            skeleton=sample_skeleton,
            contract=contract,
            context=ComposerContext(**shared, product_description="Service A"),
        )
        input_b = ComposerInput(
            page_plan=sample_page,
            evidence_binding=None,
            skeleton=sample_skeleton,
            contract=contract,
            context=ComposerContext(**shared, product_description="Service B"),
        )

        assert compute_composer_input_hash(input_a) != compute_composer_input_hash(input_b)

    def test_new_writes_use_narrowed_hash_only(
        self,
        sample_page: WikiPagePlan,
        sample_skeleton: ArticleSkeleton,
    ):
        """Post-upgrade puts must store the narrowed hash, never the legacy key."""
        input_data = _noisy_composer_input(sample_page, sample_skeleton)
        new_hash = compute_composer_input_hash(input_data, model_name="minimax")
        legacy_hash = _pre_narrow_composer_input_hash(input_data, model_name="minimax")
        assert new_hash != legacy_hash

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ComposerCache(Path(tmpdir) / "cache.sqlite3")
            cache.put(
                page_id=sample_page.page_id,
                input_hash=new_hash,
                output_markdown="# Fresh page",
                tokens_used=40,
            )
            assert cache.get(sample_page.page_id, new_hash) is not None
            assert cache.get(sample_page.page_id, legacy_hash) is None

    def test_legacy_hash_row_hits_after_upgrade_and_rewrites_new_key(
        self,
        sample_page: WikiPagePlan,
        sample_skeleton: ArticleSkeleton,
    ):
        """Pre-8d6395c sqlite rows must still hit when page-local inputs match."""
        input_data = _noisy_composer_input(sample_page, sample_skeleton)
        new_hash = compute_composer_input_hash(input_data, model_name="minimax")
        legacy_hash = _pre_narrow_composer_input_hash(input_data, model_name="minimax")
        assert new_hash != legacy_hash

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ComposerCache(Path(tmpdir) / "cache.sqlite3")
            cache.put(
                page_id=sample_page.page_id,
                input_hash=legacy_hash,
                output_markdown="# Cached before hash narrow",
                tokens_used=88,
                doc_type="overview",
            )
            assert cache.get(sample_page.page_id, new_hash) is None

            current_hash, record = lookup_composer_cache(
                cache,
                sample_page.page_id,
                input_data,
                model_name="minimax",
            )
            assert current_hash == new_hash
            assert record is not None
            assert record.output_markdown == "# Cached before hash narrow"
            assert record.tokens_used == 88

            migrated = cache.get(sample_page.page_id, new_hash)
            assert migrated is not None
            assert migrated.output_markdown == "# Cached before hash narrow"
            assert cache.get(sample_page.page_id, legacy_hash) is None


class TestComputeOutputHash:
    """Tests for compute_output_hash function."""

    def test_same_output_same_hash(self):
        """Test that same markdown produces same hash."""
        markdown1 = "# Test\n\nSome content here."
        markdown2 = "# Test\n\nSome content here."

        hash1 = compute_output_hash(markdown1)
        hash2 = compute_output_hash(markdown2)

        assert hash1 == hash2

    def test_different_output_different_hash(self):
        """Test that different markdown produces different hash."""
        markdown1 = "# Test\n\nContent A"
        markdown2 = "# Test\n\nContent B"

        hash1 = compute_output_hash(markdown1)
        hash2 = compute_output_hash(markdown2)

        assert hash1 != hash2


class TestEstimateTokens:
    """Tests for token and cost estimation."""

    def test_estimate_tokens(self):
        """Test token estimation from markdown."""
        markdown = "Hello world this is a test. " * 100
        tokens = estimate_tokens_from_markdown(markdown)

        assert tokens > 0
        assert tokens == len(markdown) // 4

    def test_estimate_cost_mock(self):
        """Test cost estimation for mock model."""
        cost = estimate_cost_from_tokens(1000, model_name="mock-gpt")
        assert cost == 0.0

    def test_estimate_cost_gpt4o(self):
        """Test cost estimation for gpt-4o."""
        cost = estimate_cost_from_tokens(1000, model_name="gpt-4o")
        assert cost > 0
        assert cost == 0.005  # 1000 * $0.005/1K


class TestComposerCache:
    """Tests for ComposerCache class."""

    @pytest.fixture
    def cache(self) -> ComposerCache:
        """Create a test cache with temporary database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "test_cache.sqlite3"
            yield ComposerCache(cache_path)

    def test_cache_put_and_get(self, cache: ComposerCache):
        """Test putting and getting from cache."""
        page_id = "test-page"
        input_hash = "abc123def456"
        markdown = "# Test Page\n\nContent here."
        tokens = 100

        cache.put(
            page_id=page_id,
            input_hash=input_hash,
            output_markdown=markdown,
            tokens_used=tokens,
        )

        record = cache.get(page_id, input_hash)
        assert record is not None
        assert record.page_id == page_id
        assert record.input_hash == input_hash
        assert record.output_markdown == markdown
        assert record.tokens_used == tokens

    def test_cache_get_for_page(self, cache: ComposerCache):
        """Test get_for_page convenience method."""
        page_id = "test-page"
        input_hash = "abc123def456"
        markdown = "# Test Page\n\nContent here."
        tokens = 100

        cache.put(
            page_id=page_id,
            input_hash=input_hash,
            output_markdown=markdown,
            tokens_used=tokens,
        )

        result_markdown, result_tokens = cache.get_for_page(page_id, input_hash)
        assert result_markdown == markdown
        assert result_tokens == tokens

    def test_cache_miss(self, cache: ComposerCache):
        """Test cache miss returns None."""
        result = cache.get("nonexistent-page", "nonexistent-hash")
        assert result is None

    def test_cache_invalidate(self, cache: ComposerCache):
        """Test invalidating cache entries."""
        page_id = "test-page"
        input_hash = "abc123def456"
        markdown = "# Test Page\n\nContent here."
        tokens = 100

        cache.put(
            page_id=page_id,
            input_hash=input_hash,
            output_markdown=markdown,
            tokens_used=tokens,
        )

        # Verify it's there
        record = cache.get(page_id, input_hash)
        assert record is not None

        # Invalidate
        count = cache.invalidate(page_id)
        assert count == 1

        # Verify it's gone
        record = cache.get(page_id, input_hash)
        assert record is None

    def test_cache_invalidate_by_hash(self, cache: ComposerCache):
        """Test invalidating specific hash."""
        page_id = "test-page"
        hash1 = "abc123def456"
        hash2 = "def456abc789"
        markdown = "# Test Page\n\nContent here."

        cache.put(
            page_id=page_id,
            input_hash=hash1,
            output_markdown=markdown,
            tokens_used=100,
        )
        cache.put(
            page_id=page_id,
            input_hash=hash2,
            output_markdown=markdown,
            tokens_used=200,
        )

        # Invalidate only hash1
        count = cache.invalidate_by_hash(page_id, hash1)
        assert count == 1

        # hash1 should be gone
        assert cache.get(page_id, hash1) is None

        # hash2 should still be there
        assert cache.get(page_id, hash2) is not None

    def test_cache_clear(self, cache: ComposerCache):
        """Test clearing all cache entries."""
        cache.put(
            page_id="page1",
            input_hash="hash1",
            output_markdown="# Page 1",
            tokens_used=100,
        )
        cache.put(
            page_id="page2",
            input_hash="hash2",
            output_markdown="# Page 2",
            tokens_used=200,
        )

        assert cache.stats().total_entries == 2

        cache.clear()

        assert cache.stats().total_entries == 0

    def test_cache_stats(self, cache: ComposerCache):
        """Test cache statistics."""
        cache.put(
            page_id="page1",
            input_hash="hash1",
            output_markdown="# Page 1",
            tokens_used=100,
        )
        cache.put(
            page_id="page2",
            input_hash="hash2",
            output_markdown="# Page 2",
            tokens_used=200,
        )

        # First get hits cache
        cache.get("page1", "hash1")
        cache.get("page1", "hash1")
        cache.get("page2", "hash2")
        cache.get("nonexistent", "hash")

        stats = cache.stats()
        assert stats.total_entries == 2
        assert stats.cache_hits >= 2
        assert stats.cache_misses >= 1
        assert stats.total_tokens_saved == 300

    def test_cache_list_entries(self, cache: ComposerCache):
        """Test listing cache entries."""
        cache.put(
            page_id="page1",
            input_hash="hash1",
            output_markdown="# Page 1",
            tokens_used=100,
            doc_type="overview",
        )
        cache.put(
            page_id="page2",
            input_hash="hash2",
            output_markdown="# Page 2",
            tokens_used=200,
            doc_type="section",
        )

        entries = cache.list_entries()
        assert len(entries) == 2

        entries = cache.list_entries(page_id="page1")
        assert len(entries) == 1
        assert entries[0].page_id == "page1"

    def test_cache_update_existing(self, cache: ComposerCache):
        """Test updating existing cache entry."""
        page_id = "test-page"
        input_hash = "abc123def456"

        cache.put(
            page_id=page_id,
            input_hash=input_hash,
            output_markdown="# Original",
            tokens_used=100,
        )

        # Update with new content
        cache.put(
            page_id=page_id,
            input_hash=input_hash,
            output_markdown="# Updated",
            tokens_used=150,
        )

        record = cache.get(page_id, input_hash)
        assert record is not None
        assert record.output_markdown == "# Updated"
        assert record.tokens_used == 150

    def test_stats_exposes_skipped_and_regenerated_observations(self, cache: ComposerCache):
        """Cache stats should expose page-level skip/regeneration observations."""
        cache.record_skipped_page()
        cache.record_regenerated_page()
        cache.get("missing", "hash")
        cache.put(
            page_id="page1",
            input_hash="hash1",
            output_markdown="# Page 1",
            tokens_used=100,
        )
        assert cache.get("page1", "hash1") is not None

        stats = cache.stats()
        assert stats.cache_hits == 1
        assert stats.cache_misses == 1
        assert stats.skipped_pages == 1
        assert stats.regenerated_pages == 1

    def test_qoder_like_service_records_real_cache_hit_and_store_observations(self, tmp_path: Path):
        """Service qoder-like cache helpers should expose skip/regeneration counters."""
        cfg = RepoWikiConfig()
        cfg.project.root = str(tmp_path)
        service = RepoWikiService(cfg)
        cache = ComposerCache(tmp_path / "composer.sqlite3")

        service._store_composer_cache_page(
            cache,
            page_id="page1",
            input_hash="hash1",
            output_markdown="# Page 1",
            tokens_used=40,
            model_name="mock-gpt",
            doc_type="overview",
            cost_usd=0.0,
        )
        cached = service._observe_composer_cache_hit(cache, "page1", "hash1")

        assert cached is not None
        assert cached.output_markdown == "# Page 1"
        stats = cache.stats()
        assert stats.cache_hits == 1
        assert stats.cache_misses == 0
        assert stats.skipped_pages == 1
        assert stats.regenerated_pages == 1

    def test_service_observe_hits_legacy_hash_row_after_upgrade(self, tmp_path: Path):
        """qoder-like observe must reuse a pre-narrow sqlite row and migrate it."""
        sample_page = WikiPagePlan(
            page_id="test-page",
            title="Test Page",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
            source_requirements=SourceRequirement(modules=["auth", "api"]),
            generation_mode=GenerationMode.LLM_ASSISTED,
        )
        sample_skeleton = build_skeleton("overview", "Test Page")
        input_data = _noisy_composer_input(sample_page, sample_skeleton)
        new_hash = compute_composer_input_hash(input_data, model_name="minimax")
        legacy_hash = _pre_narrow_composer_input_hash(input_data, model_name="minimax")
        assert new_hash != legacy_hash

        cfg = RepoWikiConfig()
        cfg.project.root = str(tmp_path)
        service = RepoWikiService(cfg)
        cache = ComposerCache(tmp_path / "composer.sqlite3")
        cache.put(
            page_id=sample_page.page_id,
            input_hash=legacy_hash,
            output_markdown="# Legacy handbook page",
            tokens_used=64,
            doc_type="overview",
        )

        cached = service._observe_composer_cache_hit(
            cache,
            sample_page.page_id,
            new_hash,
            input_data=input_data,
            model_name="minimax",
        )
        assert cached is not None
        assert cached.output_markdown == "# Legacy handbook page"
        stats = cache.stats()
        assert stats.cache_hits == 1
        assert stats.skipped_pages == 1
        assert cache.get(sample_page.page_id, new_hash) is not None
        assert cache.get(sample_page.page_id, legacy_hash) is None

    def test_cached_composer_mixin_records_real_hit_miss_and_store_observations(
        self, cache: ComposerCache
    ):
        """Production cache helpers should update skip/regeneration counters."""

        class DummyCachedComposer(CachedComposerMixin):
            pass

        composer = DummyCachedComposer(cache=cache)

        miss_markdown, miss_tokens = composer._check_cache("page1", "hash1")
        assert (miss_markdown, miss_tokens) == (None, 0)
        composer._store_cache("page1", "hash1", "# Page 1", 40)
        hit_markdown, hit_tokens = composer._check_cache("page1", "hash1")

        assert hit_markdown == "# Page 1"
        assert hit_tokens == 40
        stats = cache.stats()
        assert stats.cache_hits == 1
        assert stats.cache_misses == 1
        assert stats.skipped_pages == 1
        assert stats.regenerated_pages == 1


class TestCreateComposerCache:
    """Tests for create_composer_cache factory."""

    def test_create_composer_cache(self):
        """Test creating composer cache at standard location."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cache = create_composer_cache(root)

            assert cache is not None
            assert isinstance(cache, ComposerCache)

            expected_path = root / ".repo-wiki" / "index" / "cache" / "composer_cache.sqlite3"
            assert expected_path.exists()


class TestFormatCacheStats:
    """Tests for format_cache_stats function."""

    def test_format_stats(self):
        """Test formatting cache statistics."""
        stats = ComposerCacheStats(
            total_entries=10,
            cache_hits=8,
            cache_misses=2,
            total_tokens_saved=5000,
            total_cost_saved_usd=0.025,
        )

        formatted = format_cache_stats(stats)
        assert "Total entries: 10" in formatted
        assert "Cache hits: 8" in formatted
        assert "Cache misses: 2" in formatted
        assert "Hit rate: 80.0%" in formatted
        assert "Tokens saved: 5000" in formatted
        assert "$0.025000" in formatted or "$0.025" in formatted
        assert "Skipped pages: 0" in formatted
        assert "Regenerated pages: 0" in formatted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
