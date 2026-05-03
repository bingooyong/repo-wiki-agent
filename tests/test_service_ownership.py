"""Tests for service ownership resolver.

These tests verify that:
1. Evidence from unrelated services (GitLab, Jenkins, MCP) is rejected
2. Evidence from similarly named services is properly disambiguated
3. Confidence and rejection reasons are properly emitted
"""

import pytest

from repo_wiki.evidence.service_ownership import (
    OwnershipConfidence,
    OwnershipDecision,
    OwnershipVerifier,
    ServiceOwnershipResolver,
    _check_infrastructure_conflict,
    _extract_domain_from_path,
    filter_evidence_by_ownership,
)
from repo_wiki.planner.schema import (
    WikiPagePlan,
    WikiTaxonomyCategory,
)


class TestInfrastructureConflictDetection:
    """Tests for detecting infrastructure service conflicts."""

    def test_detects_gitlab_pattern_in_symbol(self):
        """Test that GitLab patterns in symbol are detected."""
        is_infra, service = _check_infrastructure_conflict(
            symbol="GitLabRunner",
            file_path=None,
            span_text=None,
        )
        assert is_infra is True
        assert service == "gitlab"

    def test_detects_gitlab_pattern_in_file_path(self):
        """Test that GitLab patterns in file path are detected."""
        is_infra, service = _check_infrastructure_conflict(
            symbol=None,
            file_path=".gitlab-ci/main.yml",
            span_text=None,
        )
        assert is_infra is True
        assert service == "gitlab"

    def test_detects_jenkins_pattern(self):
        """Test that Jenkins patterns are detected."""
        is_infra, service = _check_infrastructure_conflict(
            symbol="JenkinsPipeline",
            file_path=None,
            span_text=None,
        )
        assert is_infra is True
        assert service == "jenkins"

    def test_detects_mcp_pattern(self):
        """Test that MCP (Model Context Protocol) patterns are detected."""
        is_infra, service = _check_infrastructure_conflict(
            symbol="McpServer",
            file_path=None,
            span_text=None,
        )
        assert is_infra is True
        assert service == "mcp"

    def test_detects_mcp_in_span_text(self):
        """Test that MCP patterns in span text are detected."""
        is_infra, service = _check_infrastructure_conflict(
            symbol=None,
            file_path=None,
            span_text="Model Context Protocol server implementation",
        )
        assert is_infra is True
        assert service == "mcp"

    def test_no_conflict_for_normal_symbol(self):
        """Test that normal symbols don't trigger conflict detection."""
        is_infra, service = _check_infrastructure_conflict(
            symbol="UserService",
            file_path="src/service/user.py",
            span_text="class UserService:",
        )
        assert is_infra is False
        assert service == ""


class TestDomainExtractionFromPath:
    """Tests for extracting domain hints from file paths."""

    def test_extracts_ai_domain(self):
        """Test AI domain extraction from path."""
        assert _extract_domain_from_path("src/ai/service.py") == "ai-services"
        assert _extract_domain_from_path("src/ai/embedding.py") == "ai-services"
        assert _extract_domain_from_path("src/ml/model.py") == "ai-services"

    def test_extracts_core_platform_domain(self):
        """Test core-platform domain extraction."""
        assert _extract_domain_from_path("src/core-platform/api.py") == "core-platform"
        assert _extract_domain_from_path("src/platform/service.py") == "core-platform"

    def test_extracts_frontend_domain(self):
        """Test frontend domain extraction."""
        assert _extract_domain_from_path("src/frontend/component.tsx") == "frontend"
        assert _extract_domain_from_path("ui/button.js") == "frontend"

    def test_returns_none_for_unknown_path(self):
        """Test that unknown paths return None."""
        assert _extract_domain_from_path("src/unknown/module.py") is None


class TestServiceOwnershipResolver:
    """Tests for the ServiceOwnershipResolver class."""

    def test_resolver_initialization(self):
        """Test resolver can be initialized with service name."""
        resolver = ServiceOwnershipResolver(
            service_name="ai-service",
            domain="ai-services",
        )
        assert resolver.service_name == "ai-service"
        assert resolver.domain == "ai-services"

    def test_exact_service_name_match(self):
        """Test that exact service name in symbol gives high confidence."""
        resolver = ServiceOwnershipResolver(
            service_name="ai-service",
            domain="ai-services",
        )
        confidence = resolver.resolve_ownership(
            symbol="Aiservice",
            file_path=None,
            span_text=None,
        )
        assert confidence.decision in (
            OwnershipDecision.HIGH_CONFIDENCE,
            OwnershipDecision.MEDIUM_CONFIDENCE,
        )
        assert confidence.is_owned is True

    def test_rejects_gitlab_evidence(self):
        """Test that GitLab evidence is rejected for ai-service."""
        resolver = ServiceOwnershipResolver(
            service_name="ai-service",
            domain="ai-services",
        )
        confidence = resolver.resolve_ownership(
            symbol="GitLabRunner",
            file_path=".gitlab-ci/pipeline.py",
            span_text="class GitLabRunner:",
        )
        assert confidence.is_rejected is True
        assert any("gitlab" in r.lower() for r in confidence.rejection_reasons)

    def test_rejects_jenkins_evidence(self):
        """Test that Jenkins evidence is rejected for ai-service."""
        resolver = ServiceOwnershipResolver(
            service_name="ai-service",
            domain="ai-services",
        )
        confidence = resolver.resolve_ownership(
            symbol="JenkinsPipeline",
            file_path="jenkins/Jenkinsfile",
            span_text="pipeline {",
        )
        assert confidence.is_rejected is True
        assert any("jenkins" in r.lower() for r in confidence.rejection_reasons)

    def test_rejects_mcp_evidence(self):
        """Test that MCP evidence is rejected for ai-service."""
        resolver = ServiceOwnershipResolver(
            service_name="ai-service",
            domain="ai-services",
        )
        confidence = resolver.resolve_ownership(
            symbol="McpServer",
            file_path="mcp/server.py",
            span_text="class McpServer:",
        )
        assert confidence.is_rejected is True
        assert any("mcp" in r.lower() for r in confidence.rejection_reasons)

    def test_domain_mismatch_rejection(self):
        """Test that domain mismatch causes rejection."""
        resolver = ServiceOwnershipResolver(
            service_name="ai-service",
            domain="ai-services",
        )
        confidence = resolver.resolve_ownership(
            symbol="SomeClass",
            file_path="src/frontend/component.py",
            span_text="class SomeClass:",
            evidence_domain="frontend",  # Mismatch with ai-services
        )
        assert confidence.is_rejected is True
        assert any("domain" in r.lower() for r in confidence.rejection_reasons)

    def test_ai_pattern_recognition(self):
        """Test that AI-specific patterns are recognized."""
        resolver = ServiceOwnershipResolver(
            service_name="ai-service",
            domain="ai-services",
        )
        confidence = resolver.resolve_ownership(
            symbol="EmbeddingGenerator",
            file_path=None,
            span_text=None,
        )
        assert confidence.is_owned is True

    def test_path_domain_hint(self):
        """Test that path domain provides ownership hint."""
        resolver = ServiceOwnershipResolver(
            service_name="ai-service",
            domain="ai-services",
        )
        confidence = resolver.resolve_ownership(
            symbol="UnknownClass",
            file_path="src/ai/service.py",
            span_text=None,
        )
        assert confidence.is_owned is True
        assert confidence.matched_domain == "ai-services"

    def test_confidence_to_dict(self):
        """Test OwnershipConfidence serialization."""
        resolver = ServiceOwnershipResolver(
            service_name="ai-service",
            domain="ai-services",
        )
        confidence = resolver.resolve_ownership(
            symbol="Aiservice",
            file_path=None,
            span_text=None,
        )
        d = confidence.to_dict()
        assert "decision" in d
        assert "confidence" in d
        assert "signals" in d
        assert "rejection_reasons" in d


class TestOwnershipVerifier:
    """Tests for the OwnershipVerifier class."""

    def test_verifier_allows_valid_binding(self):
        """Test that valid evidence bindings pass verification."""
        verifier = OwnershipVerifier(
            ServiceOwnershipResolver(service_name="ai-service", domain="ai-services")
        )
        evidence_spans = [
            {
                "symbol": "EmbeddingGenerator",
                "file_path": "src/ai/embedding.py",
                "span_text": "class EmbeddingGenerator:",
            }
        ]
        page = WikiPagePlan(
            page_id="ai-service-docs",
            title="AI Service",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/ai-service.md",
        )
        result = verifier.verify_binding(page, evidence_spans)
        assert result["is_valid"] is True
        assert result["owned_count"] == 1
        assert result["rejected_count"] == 0

    def test_verifier_rejects_infrastructure_evidence(self):
        """Test that infrastructure evidence is rejected."""
        verifier = OwnershipVerifier(
            ServiceOwnershipResolver(service_name="ai-service", domain="ai-services")
        )
        evidence_spans = [
            {
                "symbol": "GitLabRunner",
                "file_path": ".gitlab-ci/runner.py",
                "span_text": "class GitLabRunner:",
            }
        ]
        page = WikiPagePlan(
            page_id="gitlab-page",
            title="GitLab CI",
            category=WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS,
            output_path="docs/gitlab.md",
        )
        result = verifier.verify_binding(page, evidence_spans)
        assert result["is_valid"] is False
        assert result["rejected_count"] == 1
        assert len(result["errors"]) > 0

    def test_verifier_warns_about_uncertain_ratio(self):
        """Test that high uncertain ratio triggers warning."""
        verifier = OwnershipVerifier(
            ServiceOwnershipResolver(service_name="ai-service", domain="ai-services")
        )
        # Create evidence with low confidence (but not rejected)
        evidence_spans = [
            {
                "symbol": "UnknownClass",
                "file_path": "src/utils/helper.py",  # No clear domain
                "span_text": "class UnknownClass:",
            }
            for _ in range(10)
        ]
        page = WikiPagePlan(
            page_id="ai-service-docs",
            title="AI Service",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/ai-service.md",
        )
        result = verifier.verify_binding(page, evidence_spans)
        # Should be valid but with warnings about uncertain ratio
        assert len(result["warnings"]) > 0


class TestFilterEvidenceByOwnership:
    """Tests for the filter_evidence_by_ownership function."""

    def test_filters_correctly(self):
        """Test that evidence is properly filtered into owned/rejected/uncertain."""
        resolver = ServiceOwnershipResolver(
            service_name="ai-service",
            domain="ai-services",
        )
        evidence_spans = [
            {
                "id": 1,
                "symbol": "EmbeddingGenerator",
                "file_path": "src/ai/embedding.py",
                "span_text": "class EmbeddingGenerator:",
            },
            {
                "id": 2,
                "symbol": "GitLabRunner",
                "file_path": ".gitlab-ci/runner.py",
                "span_text": "class GitLabRunner:",
            },
            {
                "id": 3,
                "symbol": "Helper",
                "file_path": "src/utils/helper.py",
                "span_text": "class Helper:",  # Uncertain
            },
        ]
        page = WikiPagePlan(
            page_id="ai-service-docs",
            title="AI Service",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/ai-service.md",
        )

        owned, uncertain, rejected = filter_evidence_by_ownership(page, evidence_spans, resolver)

        assert len(owned) == 1
        assert owned[0]["id"] == 1

        assert len(rejected) == 1
        assert rejected[0]["id"] == 2

        # Helper might be owned or uncertain depending on confidence
        assert len(uncertain) <= 1

    def test_preserves_evidence_data(self):
        """Test that original evidence data is preserved with ownership added."""
        resolver = ServiceOwnershipResolver(
            service_name="ai-service",
            domain="ai-services",
        )
        evidence_span = {
            "id": 1,
            "symbol": "EmbeddingGenerator",
            "file_path": "src/ai/embedding.py",
            "span_text": "class EmbeddingGenerator:",
            "custom_field": "value",
        }
        page = WikiPagePlan(
            page_id="ai-service-docs",
            title="AI Service",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/ai-service.md",
        )

        owned, uncertain, rejected = filter_evidence_by_ownership(page, [evidence_span], resolver)

        assert len(owned) == 1
        assert owned[0]["id"] == 1
        assert owned[0]["symbol"] == "EmbeddingGenerator"
        assert owned[0]["custom_field"] == "value"
        assert "_ownership" in owned[0]


class TestSimilarServiceNames:
    """Tests for disambiguating similarly named services."""

    def test_ai_service_vs_analytics_service(self):
        """Test that 'ai-service' and 'analytics-service' are distinguished."""
        ai_resolver = ServiceOwnershipResolver(
            service_name="ai-service",
            domain="ai-services",
        )
        analytics_resolver = ServiceOwnershipResolver(
            service_name="analytics-service",
            domain="analytics",
        )

        # Evidence with 'analytics' in name should not be owned by ai-service
        confidence = ai_resolver.resolve_ownership(
            symbol="AnalyticsDashboard",
            file_path=None,
            span_text=None,
        )
        assert confidence.is_owned is False

        # Evidence with 'ai' but analytics context should not be owned by ai-service
        confidence = ai_resolver.resolve_ownership(
            symbol="AnalyticsAI",
            file_path="src/analytics/ai_helper.py",
            span_text=None,
            evidence_domain="analytics",
        )
        assert confidence.is_rejected is True

    def test_ai_embedding_vs_data_embedding(self):
        """Test disambiguation between AI embeddings and data embeddings."""
        ai_resolver = ServiceOwnershipResolver(
            service_name="ai-service",
            domain="ai-services",
        )

        # Pure embedding service with ai context
        confidence = ai_resolver.resolve_ownership(
            symbol="EmbeddingService",
            file_path="src/ai/embedding.py",
            span_text=None,
            evidence_domain="ai-services",
        )
        assert confidence.is_owned is True

        # Data/ETL embedding should not be owned by ai-service
        confidence = ai_resolver.resolve_ownership(
            symbol="DataEmbedder",
            file_path="src/etl/embedder.py",
            span_text=None,
            evidence_domain="data-platform",
        )
        assert confidence.is_rejected is True


class TestOwnershipConfidenceModel:
    """Tests for the OwnershipConfidence dataclass."""

    def test_is_owned_properties(self):
        """Test is_owned property for different decisions."""
        high_conf = OwnershipConfidence(
            decision=OwnershipDecision.HIGH_CONFIDENCE,
            confidence=0.9,
        )
        assert high_conf.is_owned is True
        assert high_conf.is_rejected is False

        medium_conf = OwnershipConfidence(
            decision=OwnershipDecision.MEDIUM_CONFIDENCE,
            confidence=0.6,
        )
        assert medium_conf.is_owned is True
        assert medium_conf.is_rejected is False

        low_conf = OwnershipConfidence(
            decision=OwnershipDecision.LOW_CONFIDENCE,
            confidence=0.3,
        )
        assert low_conf.is_owned is False
        assert low_conf.is_rejected is False

        rejected = OwnershipConfidence(
            decision=OwnershipDecision.REJECTED,
            confidence=0.0,
            rejection_reasons=["Domain mismatch"],
        )
        assert rejected.is_owned is False
        assert rejected.is_rejected is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
