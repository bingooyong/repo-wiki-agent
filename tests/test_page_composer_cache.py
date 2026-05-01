"""Tests for page composer incremental cache.

Tests the composer_cache module (repo_wiki/generator/composer_cache.py) which provides:
- Input hash computation from page plans, evidence, prompts, model config
- Caching to avoid repeated LLM calls for unchanged pages
- Token/cost tracking per page
- Output hash persistence

Phase 24 - Task 24.6: Page composer incremental cache
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from repo_wiki.generator.composer_cache import (
    ComposerCache,
    ComposerCacheRecord,
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
)
from repo_wiki.generator.composer import (
    ComposerContext,
    ComposerInput,
)
from repo_wiki.evidence.ranking import EvidenceCandidate, PageEvidenceBinding
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.planner.schema import (
    GenerationMode,
    SourceRequirement,
    WikiPagePlan,
    WikiTaxonomyCategory,
)
from repo_wiki.prompts.contracts import PagePromptContract, PagePromptType
from repo_wiki.prompts.skeleton import ArticleSkeleton, HeadingSection, build_skeleton


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
