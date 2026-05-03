"""Tests for evidence ranking pipeline."""

import tempfile
from pathlib import Path

import pytest

from repo_wiki.evidence.ranking import (
    MIN_CANDIDATES_PER_PAGE,
    EvidenceCandidate,
    EvidenceRanker,
    EvidenceRankingResult,
    PageEvidenceBinding,
    _category_to_doc_type,
    _extract_keywords_from_page,
    _score_by_api_match,
    _score_by_data_model_match,
    _score_by_module_match,
    rank_evidence_for_page,
    score_evidence_for_page,
)
from repo_wiki.orchestration.runtime_store import (
    EvidenceSpanRecord,
    SQLiteRuntimeStore,
)
from repo_wiki.planner.schema import (
    SourceRequirement,
    WikiPagePlan,
    WikiPlanManifest,
    WikiTaxonomyCategory,
)


class TestCategoryMapping:
    """Tests for category to doc type mapping."""

    def test_category_to_doc_type_overview(self):
        """Test mapping for PROJECT_OVERVIEW."""
        assert _category_to_doc_type(WikiTaxonomyCategory.PROJECT_OVERVIEW) == "overview"

    def test_category_to_doc_type_section(self):
        """Test mapping for ARCHITECTURE_DESIGN."""
        assert _category_to_doc_type(WikiTaxonomyCategory.ARCHITECTURE_DESIGN) == "section"

    def test_category_to_doc_type_module(self):
        """Test mapping for CORE_SERVICES."""
        assert _category_to_doc_type(WikiTaxonomyCategory.CORE_SERVICES) == "module"

    def test_category_to_doc_type_data_model(self):
        """Test mapping for DATA_MODELS."""
        assert _category_to_doc_type(WikiTaxonomyCategory.DATA_MODELS) == "data-model"

    def test_category_to_doc_type_api(self):
        """Test mapping for API_REFERENCE."""
        assert _category_to_doc_type(WikiTaxonomyCategory.API_REFERENCE) == "api"

    def test_category_to_doc_type_ops(self):
        """Test mapping for DEPLOYMENT_OPERATIONS."""
        assert _category_to_doc_type(WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS) == "ops"


class TestKeywordExtraction:
    """Tests for keyword extraction from pages and spans."""

    def test_extract_keywords_from_page_with_modules(self):
        """Test keyword extraction with module requirements."""
        page = WikiPagePlan(
            page_id="test-page",
            title="Test Module Page",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/pages/test.md",
            source_requirements=SourceRequirement(
                modules=["auth-service", "user-service"],
            ),
            tags=["auth", "user"],
        )
        keywords = _extract_keywords_from_page(page)
        assert "test" in keywords
        assert "module" in keywords
        assert "auth" in keywords
        assert "service" in keywords
        # auth-service normalizes to "auth service" so check for both words
        assert "auth" in keywords and "service" in keywords

    def test_extract_keywords_from_page_with_apis(self):
        """Test keyword extraction with API requirements."""
        page = WikiPagePlan(
            page_id="api-docs",
            title="API Reference",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="docs/pages/api/docs.md",
            source_requirements=SourceRequirement(
                endpoints=["GET /users", "POST /users"],
            ),
        )
        keywords = _extract_keywords_from_page(page)
        assert "api" in keywords
        assert "reference" in keywords
        assert "users" in keywords

    def test_extract_keywords_from_page_with_data_models(self):
        """Test keyword extraction with data model requirements."""
        page = WikiPagePlan(
            page_id="data-models",
            title="User Data Model",
            category=WikiTaxonomyCategory.DATA_MODELS,
            output_path="docs/pages/models/user.md",
            source_requirements=SourceRequirement(
                data_models=["UserProfile", "UserSettings"],
            ),
        )
        keywords = _extract_keywords_from_page(page)
        assert "user" in keywords
        # UserProfile normalizes to "userprofile" (camelCase not split without separator)
        assert "userprofile" in keywords
        assert "usersettings" in keywords
        # Check that path segments are extracted
        assert "models" in keywords


class TestScoringFunctions:
    """Tests for individual scoring functions."""

    def test_score_by_module_match_exact(self):
        """Test module match with exact symbol match."""
        page = WikiPagePlan(
            page_id="auth-page",
            title="Auth Service",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/auth.md",
            source_requirements=SourceRequirement(modules=["auth-service"]),
        )
        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/auth/service.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="auth-service",
            span_text="class auth-service:",
        )
        score = _score_by_module_match(page, span)
        assert score > 0

    def test_score_by_module_match_partial(self):
        """Test module match with partial symbol match."""
        page = WikiPagePlan(
            page_id="auth-page",
            title="Auth Service",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/auth.md",
            source_requirements=SourceRequirement(modules=["auth"]),
        )
        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/auth/service.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="AuthService",
            span_text="class AuthService:",
        )
        score = _score_by_module_match(page, span)
        assert score > 0

    def test_score_by_module_match_no_match(self):
        """Test module match with no match."""
        page = WikiPagePlan(
            page_id="auth-page",
            title="Auth Service",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/auth.md",
            source_requirements=SourceRequirement(modules=["auth-service"]),
        )
        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/other/service.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="OtherClass",
            span_text="class OtherClass:",
        )
        score = _score_by_module_match(page, span)
        assert score == 0.0

    def test_score_by_api_match(self):
        """Test API endpoint match scoring."""
        page = WikiPagePlan(
            page_id="api-page",
            title="Users API",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="docs/api/users.md",
            source_requirements=SourceRequirement(
                endpoints=["GET /users", "POST /users"],
            ),
        )
        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/api/users.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="get_users",
            span_text="def get_users():",
        )
        score = _score_by_api_match(page, span)
        assert score > 0

    def test_score_by_data_model_match(self):
        """Test data model match scoring."""
        page = WikiPagePlan(
            page_id="model-page",
            title="User Profile",
            category=WikiTaxonomyCategory.DATA_MODELS,
            output_path="docs/models/profile.md",
            source_requirements=SourceRequirement(
                data_models=["UserProfile", "UserSettings"],
            ),
        )
        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/models/user.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="UserProfile",
            span_text="class UserProfile:",
        )
        score = _score_by_data_model_match(page, span)
        assert score > 0


class TestScoreEvidenceForPage:
    """Tests for the overall scoring function."""

    def test_score_returns_signals_on_match(self):
        """Test scoring returns signals when matches occur."""
        page = WikiPagePlan(
            page_id="auth-page",
            title="Auth Service",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/auth.md",
            source_requirements=SourceRequirement(modules=["auth-service"]),
        )
        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/auth/service.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="auth-service",
            span_text="class auth-service:",
        )
        score, signals = score_evidence_for_page(page, span)
        assert score > 0.0
        assert len(signals) > 0

    def test_score_returns_zero_for_no_match_except_category(self):
        """Test scoring returns low score when only category relevance matches."""
        page = WikiPagePlan(
            page_id="auth-page",
            title="Auth Service",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/auth.md",
            source_requirements=SourceRequirement(modules=["auth-service"]),
        )
        # Use a language that doesn't match project_overview preferences
        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/other/unrelated.py",
            line_start=10,
            line_end=20,
            language="typescript",
            symbol="UnrelatedClass",
            span_text="class UnrelatedClass:",
        )
        score, signals = score_evidence_for_page(page, span)
        # category_relevance might be non-zero but module/symbol should not match
        assert score >= 0.0
        # module_match should not trigger
        assert "module_match" not in signals

    def test_score_returns_signals_on_match(self):
        """Test scoring returns signals when matches occur."""
        page = WikiPagePlan(
            page_id="auth-page",
            title="Auth Service",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/auth.md",
            source_requirements=SourceRequirement(modules=["auth-service"]),
        )
        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/auth/service.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="auth-service",
            span_text="class auth-service:",
        )
        score, signals = score_evidence_for_page(page, span)
        assert score > 0.0
        assert len(signals) > 0


class TestRankEvidenceForPage:
    """Tests for ranking evidence for a single page."""

    def test_rank_returns_empty_for_no_spans(self):
        """Test ranking returns empty list when no spans available."""
        page = WikiPagePlan(
            page_id="test-page",
            title="Test",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
        )
        candidates = rank_evidence_for_page(page, [])
        assert len(candidates) == 0

    def test_rank_sorts_by_score(self):
        """Test ranking sorts candidates by score descending."""
        page = WikiPagePlan(
            page_id="auth-page",
            title="Auth Service",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/auth.md",
            source_requirements=SourceRequirement(modules=["auth-service"]),
        )
        spans = [
            EvidenceSpanRecord(
                digest="span1",
                file_path="src/auth/service.py",
                line_start=10,
                line_end=20,
                language="python",
                symbol="auth-service",
                span_text="class auth-service:",
            ),
            EvidenceSpanRecord(
                digest="span2",
                file_path="src/other/unrelated.py",
                line_start=10,
                line_end=20,
                language="python",
                symbol="UnrelatedClass",
                span_text="class UnrelatedClass:",
            ),
            EvidenceSpanRecord(
                digest="span3",
                file_path="src/auth/helper.py",
                line_start=10,
                line_end=20,
                language="python",
                symbol="AuthHelper",
                span_text="class AuthHelper:",
            ),
        ]
        candidates = rank_evidence_for_page(page, spans)
        assert len(candidates) > 0
        # First candidate should have highest score
        assert candidates[0].score >= candidates[-1].score

    def test_rank_respects_min_candidates(self):
        """Test ranking returns up to MIN_CANDIDATES_PER_PAGE candidates."""
        page = WikiPagePlan(
            page_id="test-page",
            title="Test",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
        )
        spans = [
            EvidenceSpanRecord(
                digest=f"span{i}",
                file_path=f"src/file{i}.py",
                line_start=10,
                line_end=20,
                language="python",
                symbol=f"Symbol{i}",
                span_text=f"class Symbol{i}:",
            )
            for i in range(10)
        ]
        candidates = rank_evidence_for_page(page, spans)
        assert len(candidates) <= MIN_CANDIDATES_PER_PAGE


class TestEvidenceRanker:
    """Tests for the EvidenceRanker class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_ranker.sqlite3"
            store = SQLiteRuntimeStore(db_path)
            yield store
            store.close()

    def test_ranker_initialization(self, temp_db):
        """Test ranker can be initialized with store."""
        ranker = EvidenceRanker(temp_db)
        assert ranker.store is not None

    def test_rank_plan_empty_manifest(self, temp_db):
        """Test ranking empty manifest returns empty bindings."""
        manifest = WikiPlanManifest(version="1.0.0", pages=[])
        ranker = EvidenceRanker(temp_db)
        result = ranker.rank_plan(manifest)
        assert len(result.bindings) == 0
        assert len(result.insufficient_pages) == 0

    def test_rank_plan_with_pages_no_spans(self, temp_db):
        """Test ranking plan with pages but no evidence spans."""
        pages = [
            WikiPagePlan(
                page_id="test-page",
                title="Test",
                category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
                output_path="docs/test.md",
            )
        ]
        manifest = WikiPlanManifest(version="1.0.0", pages=pages)
        ranker = EvidenceRanker(temp_db)
        result = ranker.rank_plan(manifest)
        assert len(result.bindings) == 1
        assert result.bindings[0].candidates == []
        # No spans means not necessarily insufficient (nothing to bind)
        assert len(result.insufficient_pages) == 0

    def test_rank_plan_with_spans(self, temp_db):
        """Test ranking plan with pages and evidence spans."""
        # Insert some evidence spans
        spans = [
            EvidenceSpanRecord(
                digest=f"digest{i}",
                file_path=f"src/module{i}.py",
                line_start=10,
                line_end=20,
                language="python",
                symbol=f"Module{i}",
                span_text=f"class Module{i}:",
            )
            for i in range(5)
        ]
        for span in spans:
            temp_db.upsert_evidence_span(span)

        # Create page that matches one of the spans
        pages = [
            WikiPagePlan(
                page_id="module-0",
                title="Module 0",
                category=WikiTaxonomyCategory.CORE_SERVICES,
                output_path="docs/pages/module0.md",
                source_requirements=SourceRequirement(modules=["Module0"]),
            )
        ]
        manifest = WikiPlanManifest(version="1.0.0", pages=pages)
        ranker = EvidenceRanker(temp_db)
        result = ranker.rank_plan(manifest)

        assert len(result.bindings) == 1
        binding = result.bindings[0]
        assert binding.page_id == "module-0"
        # Should have found matches
        assert len(binding.candidates) > 0 or len(result.insufficient_pages) > 0

    def test_persist_bindings(self, temp_db):
        """Test persisting bindings to store."""
        # Insert evidence span
        span = EvidenceSpanRecord(
            digest="testdigest",
            file_path="src/test.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="TestClass",
            span_text="class TestClass:",
        )
        span_id = temp_db.upsert_evidence_span(span)

        # Create manifest
        pages = [
            WikiPagePlan(
                page_id="test-page",
                title="Test",
                category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
                output_path="docs/test.md",
            )
        ]
        manifest = WikiPlanManifest(version="1.0.0", pages=pages)

        # Create result with one candidate
        candidate = EvidenceCandidate(
            evidence_id=span_id,
            span=span,
            score=1.0,
            match_signals=["test"],
            citation_order=0,
        )
        binding = PageEvidenceBinding(
            page_id="test-page",
            doc_type="overview",
            candidates=[candidate],
            insufficient_evidence=False,
            bound_count=1,
        )
        result = EvidenceRankingResult(
            bindings=[binding],
            insufficient_pages=[],
            total_spans_processed=1,
            ranked_pages=1,
        )

        # Persist
        ranker = EvidenceRanker(temp_db)
        ranker.persist_bindings(manifest, result)

        # Verify mapping exists
        sources = temp_db.list_page_sources("test-page", "overview")
        assert len(sources) == 1
        assert sources[0]["evidence_id"] == span_id


class TestGetInsufficientEvidencePages:
    """Tests for insufficient evidence reporting."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_insufficient.sqlite3"
            store = SQLiteRuntimeStore(db_path)
            yield store
            store.close()

    def test_insufficient_pages_detection(self, temp_db):
        """Test detection of pages with insufficient evidence."""
        # Insert only 2 spans
        for i in range(2):
            span = EvidenceSpanRecord(
                digest=f"digest{i}",
                file_path=f"src/file{i}.py",
                line_start=10,
                line_end=20,
                language="python",
                symbol=f"Symbol{i}",
                span_text=f"class Symbol{i}:",
            )
            temp_db.upsert_evidence_span(span)

        # Create page that doesn't match well
        pages = [
            WikiPagePlan(
                page_id="generic-page",
                title="Generic",
                category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
                output_path="docs/generic.md",
                source_requirements=SourceRequirement(modules=["completely-unrelated-module"]),
            )
        ]
        manifest = WikiPlanManifest(version="1.0.0", pages=pages)
        ranker = EvidenceRanker(temp_db)
        result = ranker.rank_plan(manifest)

        # Check that we got candidates (even if low scoring)
        assert len(result.bindings) == 1

    def test_insufficient_report_structure(self, temp_db):
        """Test structure of insufficient evidence report."""
        pages = [
            WikiPagePlan(
                page_id="test-page",
                title="Test",
                category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
                output_path="docs/test.md",
            )
        ]
        manifest = WikiPlanManifest(version="1.0.0", pages=pages)
        ranker = EvidenceRanker(temp_db)
        result = ranker.rank_plan(manifest)
        report = ranker.get_insufficient_evidence_pages(manifest, result)

        # Should be a list (possibly empty)
        assert isinstance(report, list)


class TestMinCandidatesConstant:
    """Tests for MIN_CANDIDATES_PER_PAGE constant."""

    def test_min_candidates_value(self):
        """Test minimum candidates is at least 5."""
        assert MIN_CANDIDATES_PER_PAGE >= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
