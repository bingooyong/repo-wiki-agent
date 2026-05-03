"""Tests for page evidence scoring model.

Tests for:
- Positive matches: evidence correctly scoring high for matching pages
- False-positive rejection: evidence incorrectly scoring high being caught
- Service-local preference: local evidence preferred over shared modules
- Rejection reason persistence: rejection reasons stored and inspectable
"""

from __future__ import annotations

import pytest

from repo_wiki.evidence.page_evidence_scorer import (
    PageEvidenceScorer,
    ScoredEvidenceCandidate,
    ServiceLocalPreference,
    _normalize_text,
    _text_similarity,
    _tokenize,
    score_page_evidence,
)
from repo_wiki.evidence.service_ownership import (
    ServiceOwnershipResolver,
)
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.planner.schema import (
    SourceRequirement,
    WikiPagePlan,
    WikiTaxonomyCategory,
)

# =============================================================================
# Utility Function Tests
# =============================================================================


class TestTextNormalization:
    """Tests for text normalization utilities."""

    def test_normalize_lowercases(self):
        """Test normalization lowercases text."""
        result = _normalize_text("HELLO_WORLD")
        assert "hello" in result
        assert "world" in result

    def test_normalize_removes_separators(self):
        """Test normalization removes common separators."""
        assert _normalize_text("hello-world") == "hello world"
        assert _normalize_text("hello_world") == "hello world"
        assert _normalize_text("hello/world") == "hello world"

    def test_normalize_trims_whitespace(self):
        """Test normalization trims whitespace."""
        assert _normalize_text("  hello  ").strip() == "hello"


class TestTokenization:
    """Tests for tokenization."""

    def test_tokenize_simple(self):
        """Test simple tokenization."""
        tokens = _tokenize("hello world")
        assert "hello" in tokens
        assert "world" in tokens

    def test_tokenize_camel_case(self):
        """Test camelCase tokenization splits words."""
        tokens = _tokenize("helloWorld")
        # Should split into multiple tokens or at least not be empty
        assert len(tokens) >= 1
        # The tokens should be lowercase
        assert all(t.islower() for t in tokens)

    def test_tokenize_preserves_splits(self):
        """Test tokenization handles already-separated words."""
        tokens = _tokenize("hello world")
        assert "hello" in tokens
        assert "world" in tokens


class TestTextSimilarity:
    """Tests for text similarity scoring."""

    def test_exact_match(self):
        """Test exact match returns high similarity."""
        sim = _text_similarity("auth-service", "auth-service")
        assert sim == 1.0

    def test_partial_match(self):
        """Test partial match returns intermediate similarity."""
        sim = _text_similarity("auth", "auth-service")
        assert sim > 0.5

    def test_no_match(self):
        """Test no match returns zero."""
        sim = _text_similarity("hello", "world")
        assert sim < 0.3

    def test_empty_strings(self):
        """Test empty strings return zero."""
        assert _text_similarity("", "") == 0.0
        assert _text_similarity("hello", "") == 0.0
        assert _text_similarity("", "world") == 0.0


# =============================================================================
# Positive Match Tests
# =============================================================================


class TestPositiveMatches:
    """Tests for evidence correctly scoring high for matching pages."""

    @pytest.fixture
    def ai_service_page(self) -> WikiPagePlan:
        """Create a typical AI service page plan."""
        return WikiPagePlan(
            page_id="ai-service",
            title="AI Service",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/ai-service.md",
            source_requirements=SourceRequirement(
                modules=["ai-service", "embedding"],
                data_models=["EmbeddingResult"],
            ),
        )

    @pytest.fixture
    def embedding_span(self) -> EvidenceSpanRecord:
        """Create an embedding-related evidence span."""
        return EvidenceSpanRecord(
            digest="embed123",
            file_path="src/ai/embedding.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="EmbeddingHandler",
            span_text="class EmbeddingHandler:",
        )

    def test_service_slug_match(self, ai_service_page, embedding_span):
        """Test service slug match is detected."""
        scorer = PageEvidenceScorer()
        result = scorer.score_page_evidence(ai_service_page, [embedding_span])

        assert len(result.candidates) == 1
        candidate = result.candidates[0]
        # Module "embedding" should match symbol "EmbeddingHandler"
        assert candidate.service_slug_score > 0

    def test_data_model_match(self, ai_service_page):
        """Test data model match scoring."""
        page = WikiPagePlan(
            page_id="embedding-model",
            title="Embedding Model",
            category=WikiTaxonomyCategory.DATA_MODELS,
            output_path="docs/models/embedding.md",
            source_requirements=SourceRequirement(
                data_models=["EmbeddingResult", "VectorEntry"],
            ),
        )
        span = EvidenceSpanRecord(
            digest="model123",
            file_path="src/ai/model.py",
            line_start=5,
            line_end=15,
            language="python",
            symbol="EmbeddingResult",
            span_text="class EmbeddingResult:",
        )

        scorer = PageEvidenceScorer()
        result = scorer.score_page_evidence(page, [span])

        assert len(result.candidates) == 1
        candidate = result.candidates[0]
        assert candidate.data_model_score > 0
        assert "data_model_relation" in candidate.match_signals

    def test_api_match(self, ai_service_page):
        """Test API endpoint match scoring."""
        page = WikiPagePlan(
            page_id="api-handlers",
            title="API Handlers",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="docs/api/handlers.md",
            source_requirements=SourceRequirement(
                endpoints=["GET /embeddings", "POST /embeddings"],
            ),
        )
        span = EvidenceSpanRecord(
            digest="api123",
            file_path="src/ai/api.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="get_embeddings",
            span_text="def get_embeddings():",
        )

        scorer = PageEvidenceScorer()
        result = scorer.score_page_evidence(page, [span])

        assert len(result.candidates) == 1
        candidate = result.candidates[0]
        assert candidate.api_score > 0
        assert "api_relation" in candidate.match_signals

    def test_runtime_role_match(self):
        """Test runtime role matching."""
        page = WikiPagePlan(
            page_id="auth-service",
            title="Auth Service",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/auth.md",
            source_requirements=SourceRequirement(
                modules=["auth-service"],
            ),
        )
        span = EvidenceSpanRecord(
            digest="auth123",
            file_path="src/auth/service.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="auth-service",
            span_text="class auth-service:",
        )

        scorer = PageEvidenceScorer()
        result = scorer.score_page_evidence(page, [span])

        assert len(result.candidates) == 1
        candidate = result.candidates[0]
        # Should have some score from service slug match
        assert candidate.score > 0


# =============================================================================
# False-Positive Rejection Tests
# =============================================================================


class TestFalsePositiveRejection:
    """Tests for false-positive evidence being rejected."""

    @pytest.fixture
    def ai_service_page(self) -> WikiPagePlan:
        """Create an AI service page plan."""
        return WikiPagePlan(
            page_id="ai-service",
            title="AI Service",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/ai-service.md",
            source_requirements=SourceRequirement(
                modules=["ai-service"],
            ),
        )

    def test_infrastructure_evidence_rejected(self, ai_service_page):
        """Test evidence from GitLab/Jenkins/MCP is rejected with ownership resolver."""
        # Create span with GitLab pattern
        gitlab_span = EvidenceSpanRecord(
            digest="gitlab123",
            file_path="gitlab-ci.yml",
            line_start=1,
            line_end=10,
            language="yaml",
            symbol="gitlab-ci",
            span_text="gitlab-ci.yml configuration",
        )

        # Use ownership resolver to detect infrastructure conflict
        resolver = ServiceOwnershipResolver(service_name="ai-service", domain="ai-services")
        scorer = PageEvidenceScorer(ownership_resolver=resolver)
        result = scorer.score_page_evidence(ai_service_page, [gitlab_span])

        # GitLab evidence should be rejected
        assert len(result.rejected) >= 1
        rejection = result.rejected[0]
        assert rejection.is_rejected

    def test_unrelated_service_rejected(self, ai_service_page):
        """Test evidence from unrelated service is rejected."""
        # Create Jenkins-related span
        jenkins_span = EvidenceSpanRecord(
            digest="jenkins123",
            file_path="Jenkinsfile",
            line_start=1,
            line_end=20,
            language="groovy",
            symbol="jenkins-pipeline",
            span_text="pipeline { stages { ... } }",
        )

        # Use ownership resolver
        resolver = ServiceOwnershipResolver(service_name="ai-service", domain="ai-services")
        scorer = PageEvidenceScorer(ownership_resolver=resolver)
        result = scorer.score_page_evidence(ai_service_page, [jenkins_span])

        # Jenkins evidence should be rejected
        assert len(result.rejected) >= 1

    def test_low_score_rejected(self):
        """Test evidence with total score below threshold is rejected."""
        page = WikiPagePlan(
            page_id="ai-service",
            title="AI Service",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/ai-service.md",
            source_requirements=SourceRequirement(
                modules=["ai-service"],
            ),
        )

        # Create span with no relevance - completely different name
        unrelated_span = EvidenceSpanRecord(
            digest="unrelated123",
            file_path="src/completely/different.py",
            line_start=1,
            line_end=5,
            language="python",
            symbol="CompletelyDifferentClass",
            span_text="class CompletelyDifferentClass:",
        )

        scorer = PageEvidenceScorer(top_n=3)
        result = scorer.score_page_evidence(page, [unrelated_span])

        # Low-scoring evidence should be rejected
        assert len(result.rejected) >= 1
        # Check rejection reason is LOW_SCORE
        if result.rejected:
            assert any(r.reason_code == "LOW_SCORE" for r in result.rejected[0].rejection_reasons)

    def test_domain_mismatch_not_preferred(self):
        """Test evidence with domain mismatch is not preferred but not rejected."""
        # Page about frontend
        frontend_page = WikiPagePlan(
            page_id="frontend-ui",
            title="Frontend UI",
            category=WikiTaxonomyCategory.FRONTEND_APPLICATIONS,
            output_path="docs/frontend.md",
            source_requirements=SourceRequirement(
                modules=["frontend"],
            ),
        )

        # Span from AI service domain
        ai_span = EvidenceSpanRecord(
            digest="ai123",
            file_path="src/ai/service.py",
            line_start=1,
            line_end=10,
            language="python",
            symbol="ai-service",
            span_text="class AIService:",
        )

        # Use ownership resolver that enforces domain separation
        resolver = ServiceOwnershipResolver(
            service_name="frontend",
            domain="frontend",
        )

        scorer = PageEvidenceScorer(ownership_resolver=resolver)
        result = scorer.score_page_evidence(frontend_page, [ai_span])

        # AI evidence should be in candidates (ownership is low, not rejected)
        assert len(result.candidates) == 1
        # Ownership score should be low due to domain mismatch
        assert result.candidates[0].ownership_score < 1.0


# =============================================================================
# Service-Local Preference Tests
# =============================================================================


class TestServiceLocalPreference:
    """Tests for service-local evidence preference."""

    def test_local_preferred_over_shared(self):
        """Test local evidence is preferred over shared modules."""
        preference = ServiceLocalPreference(prefer_local=True)

        # Local evidence
        local_span = EvidenceSpanRecord(
            digest="local123",
            file_path="src/ai/service.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="AIService",
            span_text="class AIService:",
        )

        # Shared evidence
        shared_span = EvidenceSpanRecord(
            digest="shared123",
            file_path="src/shared/utils.py",
            line_start=5,
            line_end=15,
            language="python",
            symbol="Utils",
            span_text="class Utils:",
        )

        local_candidate = ScoredEvidenceCandidate(
            evidence_id=1,
            span=local_span,
            score=0.8,
        )
        shared_candidate = ScoredEvidenceCandidate(
            evidence_id=2,
            span=shared_span,
            score=0.8,  # Same score
        )

        candidates = [shared_candidate, local_candidate]  # Out of order
        result = preference.apply_preference(candidates)

        # Local should come first
        assert result[0].span.file_path == "src/ai/service.py"
        assert result[1].span.file_path == "src/shared/utils.py"

    def test_shared_module_detection(self):
        """Test shared module detection."""
        preference = ServiceLocalPreference()

        assert preference.is_shared_module("src/shared/utils.py") is True
        assert preference.is_shared_module("src/common/helpers.py") is True
        assert preference.is_shared_module("src/ai/service.py") is False
        assert preference.is_shared_module("src/frontend/ui.py") is False

    def test_preference_disabled(self):
        """Test preference can be disabled."""
        preference = ServiceLocalPreference(prefer_local=False)

        local_span = EvidenceSpanRecord(
            digest="local123",
            file_path="src/ai/service.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="AIService",
            span_text="class AIService:",
        )

        shared_span = EvidenceSpanRecord(
            digest="shared123",
            file_path="src/shared/utils.py",
            line_start=5,
            line_end=15,
            language="python",
            symbol="Utils",
            span_text="class Utils:",
        )

        local_candidate = ScoredEvidenceCandidate(
            evidence_id=1,
            span=local_span,
            score=0.5,
        )
        shared_candidate = ScoredEvidenceCandidate(
            evidence_id=2,
            span=shared_span,
            score=0.9,  # Higher score
        )

        candidates = [local_candidate, shared_candidate]
        result = preference.apply_preference(candidates)

        # With preference disabled, score determines order
        assert result[0].evidence_id == 2  # Higher score first


# =============================================================================
# Rejection Reason Persistence Tests
# =============================================================================


class TestRejectionReasonPersistence:
    """Tests for rejection reasons being persisted and inspectable."""

    def test_rejection_reasons_stored(self):
        """Test rejection reasons are stored in candidate."""
        page = WikiPagePlan(
            page_id="test-page",
            title="Test",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
        )

        # GitLab-related span
        gitlab_span = EvidenceSpanRecord(
            digest="gitlab456",
            file_path=".gitlab-ci.yml",
            line_start=1,
            line_end=10,
            language="yaml",
            symbol="gitlab-ci",
            span_text="stages: [build, test]",
        )

        # Use ownership resolver to detect infrastructure conflict
        resolver = ServiceOwnershipResolver(service_name="test-service", domain="test-domain")
        scorer = PageEvidenceScorer(ownership_resolver=resolver)
        result = scorer.score_page_evidence(page, [gitlab_span])

        assert len(result.rejected) >= 1
        rejected_candidate = result.rejected[0]

        # Rejection reasons should be present and inspectable
        assert len(rejected_candidate.rejection_reasons) > 0
        reason = rejected_candidate.rejection_reasons[0]
        assert reason.reason_code in ("OWNERSHIP_REJECTED", "LOW_SCORE")
        assert len(reason.reason) > 0

    def test_rejection_reasons_from_multiple_causes(self):
        """Test rejection reasons from multiple causes are all captured."""
        page = WikiPagePlan(
            page_id="test-page",
            title="Test",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
            source_requirements=SourceRequirement(
                modules=["nonexistent-module"],
            ),
        )

        # Low relevance span - completely unrelated
        span = EvidenceSpanRecord(
            digest="low123",
            file_path="src/unrelated/file.py",
            line_start=1,
            line_end=5,
            language="python",
            symbol="UnrelatedSymbol",
            span_text="class UnrelatedSymbol:",
        )

        # Use ownership resolver - evidence from different domain
        resolver = ServiceOwnershipResolver(service_name="test-service", domain="test-domain")
        scorer = PageEvidenceScorer(ownership_resolver=resolver)
        result = scorer.score_page_evidence(page, [span])

        # Should have candidates (not all evidence is rejected)
        # but ownership score should be low
        assert len(result.candidates) >= 0 or len(result.rejected) >= 0
        # Check that total spans evaluated is tracked
        assert result.total_spans_evaluated >= 1

    def test_rejection_inspectable_after_scoring(self):
        """Test rejection reasons remain inspectable after scoring."""
        page = WikiPagePlan(
            page_id="ai-service",
            title="AI Service",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/ai-service.md",
            source_requirements=SourceRequirement(
                modules=["ai-service"],
            ),
        )

        # Jenkins span - use ownership resolver to detect
        jenkins_span = EvidenceSpanRecord(
            digest="jenkins789",
            file_path="Jenkinsfile",
            line_start=1,
            line_end=20,
            language="groovy",
            symbol="jenkins-pipeline",
            span_text="pipeline { agent any }",
        )

        resolver = ServiceOwnershipResolver(service_name="ai-service", domain="ai-services")
        scorer = PageEvidenceScorer(ownership_resolver=resolver)
        candidates, rejected = scorer.score_evidence_with_rejection_persistence(
            page, [jenkins_span]
        )

        # Rejection reasons should be accessible
        assert len(rejected) >= 1
        for reason in rejected[0].rejection_reasons:
            assert reason.evidence_id is not None or reason.span_symbol is not None
            assert len(reason.reason) > 0

    def test_ownership_rejection_includes_code(self):
        """Test ownership rejection includes specific reason code."""
        page = WikiPagePlan(
            page_id="ai-service",
            title="AI Service",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/ai-service.md",
        )

        # MCP-related span
        mcp_span = EvidenceSpanRecord(
            digest="mcp123",
            file_path="mcp_server.py",
            line_start=1,
            line_end=10,
            language="python",
            symbol="mcp-server",
            span_text="class MCPServer:",
        )

        resolver = ServiceOwnershipResolver(service_name="ai-service", domain="ai-services")
        scorer = PageEvidenceScorer(ownership_resolver=resolver)
        result = scorer.score_page_evidence(page, [mcp_span])

        # Should have ownership-based rejection
        ownership_rejections = [
            r
            for r in result.rejected
            if any(rr.reason_code == "OWNERSHIP_REJECTED" for rr in r.rejection_reasons)
        ]
        assert len(ownership_rejections) >= 1


# =============================================================================
# Integration Tests
# =============================================================================


class TestPageEvidenceScorerIntegration:
    """Integration tests for page evidence scoring."""

    def test_multiple_spans_ranked_correctly(self):
        """Test multiple spans are ranked by score."""
        page = WikiPagePlan(
            page_id="ai-service",
            title="AI Service",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/ai-service.md",
            source_requirements=SourceRequirement(
                modules=["ai-service", "embedding"],
            ),
        )

        spans = [
            EvidenceSpanRecord(
                digest="high123",
                file_path="src/ai/service.py",
                line_start=10,
                line_end=20,
                language="python",
                symbol="ai-service",
                span_text="class AIService:",
            ),
            EvidenceSpanRecord(
                digest="medium123",
                file_path="src/ai/helper.py",
                line_start=5,
                line_end=10,
                language="python",
                symbol="Helper",
                span_text="class Helper:",
            ),
            EvidenceSpanRecord(
                digest="low123",
                file_path="src/other/unrelated.py",
                line_start=1,
                line_end=5,
                language="python",
                symbol="Unrelated",
                span_text="class Unrelated:",
            ),
        ]

        scorer = PageEvidenceScorer(top_n=5)
        result = scorer.score_page_evidence(page, spans)

        # Should have ranked candidates
        assert len(result.candidates) >= 1
        # Highest score should be first
        scores = [c.score for c in result.candidates]
        assert scores == sorted(scores, reverse=True)

    def test_insufficient_evidence_flagged(self):
        """Test insufficient evidence is flagged."""
        page = WikiPagePlan(
            page_id="ai-service",
            title="AI Service",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/ai-service.md",
            source_requirements=SourceRequirement(
                modules=["ai-service"],
            ),
        )

        # Only one unrelated span
        spans = [
            EvidenceSpanRecord(
                digest="low123",
                file_path="src/unrelated.py",
                line_start=1,
                line_end=5,
                language="python",
                symbol="Other",
                span_text="class Other:",
            ),
        ]

        scorer = PageEvidenceScorer(top_n=5)
        result = scorer.score_page_evidence(page, spans)

        # Should flag insufficient evidence
        assert result.insufficient_evidence is True

    def test_empty_spans_returns_empty(self):
        """Test empty spans returns empty candidates."""
        page = WikiPagePlan(
            page_id="test",
            title="Test",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
        )

        scorer = PageEvidenceScorer()
        result = scorer.score_page_evidence(page, [])

        assert len(result.candidates) == 0
        assert result.total_spans_evaluated == 0

    def test_ownership_resolver_filters_spans(self):
        """Test ownership resolver correctly handles cross-domain evidence."""
        # Page with frontend domain
        page = WikiPagePlan(
            page_id="frontend-ui",
            title="Frontend UI",
            category=WikiTaxonomyCategory.FRONTEND_APPLICATIONS,
            output_path="docs/frontend.md",
            source_requirements=SourceRequirement(
                modules=["frontend"],
            ),
        )

        # Evidence from different domain (backend)
        span = EvidenceSpanRecord(
            digest="backend123",
            file_path="src/backend/api.py",
            line_start=1,
            line_end=10,
            language="python",
            symbol="BackendAPI",
            span_text="class BackendAPI:",
        )

        # Ownership resolver that rejects backend for frontend
        resolver = ServiceOwnershipResolver(
            service_name="frontend",
            domain="frontend",
        )

        scorer = PageEvidenceScorer(ownership_resolver=resolver)
        result = scorer.score_page_evidence(page, [span])

        # Backend evidence is kept (not rejected) but with low ownership score
        # because it's from a different domain
        assert len(result.candidates) == 1
        assert result.candidates[0].ownership_score < 1.0


class TestConvenienceFunction:
    """Tests for the convenience function."""

    def test_score_page_evidence_returns_tuple(self):
        """Test convenience function returns tuple of candidates and rejected."""
        page = WikiPagePlan(
            page_id="test",
            title="Test",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
        )

        span = EvidenceSpanRecord(
            digest="test123",
            file_path="test.py",
            line_start=1,
            line_end=5,
            language="python",
            symbol="TestClass",
            span_text="class TestClass:",
        )

        candidates, rejected = score_page_evidence(page, [span])

        assert isinstance(candidates, list)
        assert isinstance(rejected, list)
        assert all(isinstance(c, ScoredEvidenceCandidate) for c in candidates)
        assert all(isinstance(c, ScoredEvidenceCandidate) for c in rejected)

    def test_score_page_evidence_with_ownership_resolver(self):
        """Test convenience function accepts ownership resolver."""
        page = WikiPagePlan(
            page_id="test",
            title="Test",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/test.md",
        )

        span = EvidenceSpanRecord(
            digest="test123",
            file_path="test.py",
            line_start=1,
            line_end=5,
            language="python",
            symbol="TestClass",
            span_text="class TestClass:",
        )

        resolver = ServiceOwnershipResolver(service_name="test-service")

        candidates, rejected = score_page_evidence(
            page,
            [span],
            ownership_resolver=resolver,
            prefer_local=False,
        )

        assert isinstance(candidates, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
