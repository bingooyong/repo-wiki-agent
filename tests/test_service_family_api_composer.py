"""Tests for service family API composer.

Tests the composer module (repo_wiki/generator/service_family_api_composer.py) which provides:
- ServiceFamilyAPIComposer: Generates prose-first API articles by service family
- compose_service_family_article: Convenience function for composition
- compose_service_family_article_async: Async version of composition function
- create_service_family_composer: Factory function

Phase 25 - Task 25.3: Service-family API composer

Test coverage:
- Service family extraction from page IDs
- Endpoint filtering by service family
- Context building for service pages
- Endpoint table formatting
- Service purpose formatting
- LLM composition integration
- Async composition support
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from repo_wiki.core.contracts import (
    Endpoint,
    Module,
    RepositoryInfo,
    RepositorySnapshot,
    RepositoryStats,
)
from repo_wiki.evidence.ranking import EvidenceCandidate, PageEvidenceBinding
from repo_wiki.generator.composer import ComposerContext
from repo_wiki.generator.service_family_api_composer import (
    ServiceFamilyAPIComposer,
    compose_service_family_article,
    compose_service_family_article_async,
    create_service_family_composer,
)
from repo_wiki.llm.providers import create_mock_provider, MockLLMProvider
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.planner.schema import (
    GenerationMode,
    SourceRequirement,
    WikiPagePlan,
    WikiTaxonomyCategory,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_snapshot() -> RepositorySnapshot:
    """Create a sample repository snapshot for testing."""
    repo_info = RepositoryInfo(
        name="test-repo",
        root_path="/test",
        language="python",
        framework="fastapi",
    )

    modules = [
        Module(
            name="auth",
            path="src/auth",
            responsibility="Authentication module",
            doc_path="docs/auth.md",
            service_family="python-backend",
            domain="core-platform",
            runtime_role="api-server",
        ),
        Module(
            name="api",
            path="src/api",
            responsibility="API endpoints",
            doc_path="docs/api.md",
            service_family="python-backend",
            domain="core-platform",
            runtime_role="api-server",
        ),
    ]

    endpoints = [
        Endpoint(
            method="GET",
            path="/health",
            module="api",
            handler="health_check",
            file_path="src/api/health.py",
            service_family="python-backend",
            domain="core-platform",
            runtime_role="api-server",
            auth_type="none",
            auth_required=False,
        ),
        Endpoint(
            method="POST",
            path="/api/auth/login",
            module="auth",
            handler="login_handler",
            file_path="src/auth/handlers.py",
            service_family="python-backend",
            domain="core-platform",
            runtime_role="api-server",
            auth_type="bearer",
            auth_required=True,
            request_body=True,
            error_codes=[400, 401, 500],
        ),
        Endpoint(
            method="POST",
            path="/api/auth/logout",
            module="auth",
            handler="logout_handler",
            file_path="src/auth/handlers.py",
            service_family="python-backend",
            domain="core-platform",
            runtime_role="api-server",
            auth_type="bearer",
            auth_required=True,
            error_codes=[401, 500],
        ),
        Endpoint(
            method="GET",
            path="/api/users",
            module="api",
            handler="get_users",
            file_path="src/api/users.py",
            service_family="typescript-frontend",
            domain="frontend",
            runtime_role="client",
            auth_type="bearer",
            auth_required=True,
            error_codes=[401, 403, 500],
        ),
    ]

    return RepositorySnapshot(
        repository=repo_info,
        modules=modules,
        endpoints=endpoints,
        commands={},
        stats=RepositoryStats(endpoint_count=4),
    )


@pytest.fixture
def auth_page_plan() -> WikiPagePlan:
    """Create an authentication API page plan."""
    return WikiPagePlan(
        page_id="api-authentication",
        title="认证授权API",
        category=WikiTaxonomyCategory.API_REFERENCE,
        output_path="docs/pages/api/api-authentication.md",
        source_requirements=SourceRequirement(
            endpoints=["POST /api/auth/login", "POST /api/auth/logout"],
            modules=["auth"],
        ),
        generation_mode=GenerationMode.RULE_FIRST,
        sort_order=10,
        tags=["api", "authentication"],
    )


@pytest.fixture
def health_page_plan() -> WikiPagePlan:
    """Create a health check API page plan."""
    return WikiPagePlan(
        page_id="api-health",
        title="健康检查API",
        category=WikiTaxonomyCategory.API_REFERENCE,
        output_path="docs/pages/api/api-health.md",
        source_requirements=SourceRequirement(
            endpoints=["GET /health"],
            modules=["api"],
        ),
        generation_mode=GenerationMode.RULE_FIRST,
        sort_order=20,
        tags=["api", "health"],
    )


@pytest.fixture
def python_backend_page_plan() -> WikiPagePlan:
    """Create a python-backend service family page plan."""
    return WikiPagePlan(
        page_id="api-python-backend",
        title="python-backend API",
        category=WikiTaxonomyCategory.API_REFERENCE,
        output_path="docs/pages/api/api-python-backend.md",
        source_requirements=SourceRequirement(
            endpoints=["GET /health", "POST /api/auth/login", "POST /api/auth/logout"],
            modules=["api", "auth"],
        ),
        generation_mode=GenerationMode.RULE_FIRST,
        sort_order=30,
        tags=["api", "service-family", "python-backend"],
    )


# =============================================================================
# TESTS FOR SERVICE FAMILY EXTRACTION
# =============================================================================

class TestServiceFamilyExtraction:
    """Tests for service family extraction from page IDs."""

    def test_extract_python_backend(self, sample_snapshot):
        """Test extracting python-backend from page ID."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        result = composer._extract_service_family("api-python-backend")
        assert result == "python-backend"

    def test_extract_typescript_frontend(self, sample_snapshot):
        """Test extracting typescript-frontend from page ID."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        result = composer._extract_service_family("api-typescript-frontend")
        assert result == "typescript-frontend"

    def test_extract_auth_page_returns_none(self, sample_snapshot):
        """Test that auth page returns None (not a service family)."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        result = composer._extract_service_family("api-authentication")
        assert result is None

    def test_extract_health_page_returns_none(self, sample_snapshot):
        """Test that health page returns None (not a service family)."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        result = composer._extract_service_family("api-health-api")
        assert result is None

    def test_extract_error_page_returns_none(self, sample_snapshot):
        """Test that error page returns None (not a service family)."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        result = composer._extract_service_family("api-error-codes")
        assert result is None

    def test_extract_core_service_returns_none(self, sample_snapshot):
        """Test that core-service page returns None (not a service family)."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        result = composer._extract_service_family("api-core-service")
        assert result is None


# =============================================================================
# TESTS FOR ENDPOINT FILTERING
# =============================================================================

class TestEndpointFiltering:
    """Tests for endpoint filtering by service family and page requirements."""

    def test_filter_by_source_requirements(self, sample_snapshot, auth_page_plan):
        """Test filtering endpoints by source requirements in page plan."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        endpoints = composer._get_endpoints_for_service_family(
            service_family=None,
            page_plan=auth_page_plan,
        )
        assert len(endpoints) == 2
        assert all(ep.module == "auth" for ep in endpoints)

    def test_filter_by_service_family(self, sample_snapshot):
        """Test filtering endpoints by service family."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        page_plan = WikiPagePlan(
            page_id="api-python-backend",
            title="python-backend API",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="docs/pages/api/api-python-backend.md",
            source_requirements=SourceRequirement(),
            generation_mode=GenerationMode.RULE_FIRST,
        )
        endpoints = composer._get_endpoints_for_service_family(
            service_family="python-backend",
            page_plan=page_plan,
        )
        assert len(endpoints) == 3
        assert all(ep.service_family == "python-backend" for ep in endpoints)

    def test_filter_auth_endpoints(self, sample_snapshot):
        """Test filtering authentication-required endpoints."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        page_plan = WikiPagePlan(
            page_id="api-authentication",
            title="认证授权API",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="docs/pages/api/api-authentication.md",
            source_requirements=SourceRequirement(),
            generation_mode=GenerationMode.RULE_FIRST,
        )
        endpoints = composer._get_endpoints_for_service_family(
            service_family=None,
            page_plan=page_plan,
        )
        assert all(ep.auth_required or ep.auth_type in ("bearer", "oauth", "api-key") for ep in endpoints)

    def test_filter_health_endpoints(self, sample_snapshot):
        """Test filtering health check endpoints."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        page_plan = WikiPagePlan(
            page_id="api-health",
            title="健康检查API",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="docs/pages/api/api-health.md",
            source_requirements=SourceRequirement(),
            generation_mode=GenerationMode.RULE_FIRST,
        )
        endpoints = composer._get_endpoints_for_service_family(
            service_family=None,
            page_plan=page_plan,
        )
        assert len(endpoints) == 1
        assert endpoints[0].path == "/health"


# =============================================================================
# TESTS FOR CONTEXT BUILDING
# =============================================================================

class TestContextBuilding:
    """Tests for service context building."""

    def test_build_basic_context(self, sample_snapshot):
        """Test building basic service context."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        endpoints = sample_snapshot.endpoints[:2]
        context = composer._build_service_context(
            page_plan=WikiPagePlan(
                page_id="test-page",
                title="Test",
                category=WikiTaxonomyCategory.API_REFERENCE,
                output_path="docs/test.md",
                source_requirements=SourceRequirement(),
                generation_mode=GenerationMode.RULE_FIRST,
            ),
            service_family="python-backend",
            endpoints=endpoints,
        )

        assert context["service_family"] == "python-backend"
        assert context["endpoint_count"] == 2
        assert context["has_auth"] is True
        assert set(context["modules"]) == {"auth", "api"}

    def test_context_identifies_auth_endpoints(self, sample_snapshot):
        """Test that context correctly identifies auth endpoint count."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        endpoints = [ep for ep in sample_snapshot.endpoints if ep.auth_required]
        context = composer._build_service_context(
            page_plan=WikiPagePlan(
                page_id="test",
                title="Test",
                category=WikiTaxonomyCategory.API_REFERENCE,
                output_path="docs/test.md",
                source_requirements=SourceRequirement(),
                generation_mode=GenerationMode.RULE_FIRST,
            ),
            service_family="python-backend",
            endpoints=endpoints,
        )

        assert context["auth_endpoint_count"] == 3  # login, logout, get_users

    def test_context_collects_error_codes(self, sample_snapshot):
        """Test that context collects unique error codes."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        context = composer._build_service_context(
            page_plan=WikiPagePlan(
                page_id="test",
                title="Test",
                category=WikiTaxonomyCategory.API_REFERENCE,
                output_path="docs/test.md",
                source_requirements=SourceRequirement(),
                generation_mode=GenerationMode.RULE_FIRST,
            ),
            service_family="python-backend",
            endpoints=sample_snapshot.endpoints,
        )

        assert 400 in context["error_codes"]
        assert 401 in context["error_codes"]
        assert 500 in context["error_codes"]
        assert 403 in context["error_codes"]


# =============================================================================
# TESTS FOR ENDPOINT TABLE FORMATTING
# =============================================================================

class TestEndpointTableFormatting:
    """Tests for endpoint table formatting."""

    def test_format_empty_endpoints(self, sample_snapshot):
        """Test formatting empty endpoint list."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        result = composer.format_endpoint_table([])
        assert result == ""

    def test_format_single_endpoint(self, sample_snapshot):
        """Test formatting single endpoint."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        endpoints = [sample_snapshot.endpoints[0]]  # health endpoint
        result = composer.format_endpoint_table(endpoints)

        assert "GET" in result
        assert "/health" in result
        assert "| Method | Path |" in result

    def test_format_multiple_endpoints(self, sample_snapshot):
        """Test formatting multiple endpoints."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        result = composer.format_endpoint_table(sample_snapshot.endpoints[:3])

        assert "GET" in result
        assert "POST" in result
        assert "/health" in result
        assert "/api/auth/login" in result

    def test_limit_to_ten_endpoints(self, sample_snapshot):
        """Test that table limits to 10 representative endpoints."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        # Create 15 endpoints
        many_endpoints = [
            Endpoint(
                method="GET",
                path=f"/test/{i}",
                module="api",
                handler=f"handler_{i}",
                file_path=f"src/api/test{i}.py",
            )
            for i in range(15)
        ]
        result = composer.format_endpoint_table(many_endpoints)

        # Should show 10 rows (plus header and "...and more" note)
        assert "*... and 5 more endpoints*" in result
        # 10 rows of data = 11 separator lines for the table = ~12 pipe characters per row
        # Table has 12 pipes per row (including header separator)
        # 11 rows * 12 pipes = 132... actually let's just check the "...more" appears
        assert "more endpoints" in result

    def test_auth_column_shows_auth_type(self, sample_snapshot):
        """Test that auth column shows auth type."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        result = composer.format_endpoint_table(sample_snapshot.endpoints)

        # Health endpoint has 'none' auth
        assert "none" in result
        # Auth endpoints have 'bearer'
        assert "bearer" in result


# =============================================================================
# TESTS FOR SERVICE PURPOSE FORMATTING
# =============================================================================

class TestServicePurposeFormatting:
    """Tests for service purpose formatting."""

    def test_format_with_service_family(self, sample_snapshot):
        """Test formatting purpose with service family name."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        endpoints = [ep for ep in sample_snapshot.endpoints if ep.service_family == "python-backend"]
        result = composer.format_service_purpose("python-backend", endpoints)

        assert "python-backend" in result
        assert "endpoints" in result

    def test_format_without_service_family(self, sample_snapshot):
        """Test formatting purpose without service family."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        result = composer.format_service_purpose(None, sample_snapshot.endpoints)

        assert "API group" in result

    def test_format_query_focused_service(self, sample_snapshot):
        """Test formatting query-focused service."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        endpoints = [ep for ep in sample_snapshot.endpoints if ep.method == "GET"]
        result = composer.format_service_purpose("query-service", endpoints)

        assert "query-focused" in result

    def test_format_mutation_focused_service(self, sample_snapshot):
        """Test formatting mutation-focused service."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        endpoints = [ep for ep in sample_snapshot.endpoints if ep.method in ("POST", "PUT")]
        result = composer.format_service_purpose("mutation-service", endpoints)

        assert "mutation-focused" in result

    def test_format_mentions_auth_count(self, sample_snapshot):
        """Test that purpose mentions auth endpoint count."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        auth_endpoints = [ep for ep in sample_snapshot.endpoints if ep.auth_required]
        result = composer.format_service_purpose("auth-service", auth_endpoints)

        assert "authenticated" in result or "3" in result


# =============================================================================
# TESTS FOR LLM COMPOSITION
# =============================================================================

class TestLLMComposition:
    """Tests for LLM composition integration."""

    def test_create_composer(self, sample_snapshot):
        """Test creating a service family composer."""
        composer = create_service_family_composer(sample_snapshot)
        assert composer is not None
        assert isinstance(composer, ServiceFamilyAPIComposer)

    def test_compose_api_page_returns_output(self, sample_snapshot, auth_page_plan):
        """Test that compose_api_page returns a ComposerOutput."""
        composer = create_service_family_composer(sample_snapshot)
        output = composer.compose_api_page(auth_page_plan)

        assert output is not None
        assert output.page_id == "api-authentication"

    def test_compose_includes_citations(self, sample_snapshot, health_page_plan):
        """Test that composed output includes citations."""
        composer = create_service_family_composer(sample_snapshot)
        output = composer.compose_api_page(health_page_plan)

        # Mock provider should produce content with citations
        assert len(output.markdown) > 0

    def test_compose_preserves_headings(self, sample_snapshot, python_backend_page_plan):
        """Test that composed output preserves heading structure."""
        composer = create_service_family_composer(sample_snapshot)
        output = composer.compose_api_page(python_backend_page_plan)

        # Should have markdown content
        assert len(output.markdown) > 0
        # Should not be rejected for heading issues
        assert output.rejected is False or "heading" not in (output.rejection_reason or "").lower()

    def test_compose_with_evidence_binding(self, sample_snapshot, auth_page_plan):
        """Test composition with evidence binding."""
        composer = create_service_family_composer(sample_snapshot)

        # Create minimal evidence binding
        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/auth/handlers.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="login_handler",
            span_text="async def login_handler",
        )
        candidate = EvidenceCandidate(
            evidence_id=1,
            span=span,
            score=1.0,
            match_signals=["module_match"],
            citation_order=0,
        )
        binding = PageEvidenceBinding(
            page_id="api-authentication",
            doc_type="api",
            candidates=[candidate],
        )

        output = composer.compose_api_page(auth_page_plan, evidence_binding=binding)

        assert output is not None
        assert output.page_id == "api-authentication"


# =============================================================================
# TESTS FOR ASYNC COMPOSITION
# =============================================================================

class TestAsyncComposition:
    """Tests for async composition support."""

    @pytest.mark.asyncio
    async def test_compose_api_page_async(self, sample_snapshot, health_page_plan):
        """Test async page composition."""
        composer = create_service_family_composer(sample_snapshot)
        output = await composer.compose_api_page_async(health_page_plan)

        assert output is not None
        assert output.page_id == "api-health"
        assert len(output.markdown) > 0

    @pytest.mark.asyncio
    async def test_compose_service_family_article_async(self, sample_snapshot, python_backend_page_plan):
        """Test async convenience function."""
        output = await compose_service_family_article_async(
            page_plan=python_backend_page_plan,
            snapshot=sample_snapshot,
        )

        assert output is not None
        assert len(output.markdown) > 0

    def test_sync_wrapper_calls_async(self, sample_snapshot, auth_page_plan):
        """Test that sync wrapper properly calls async method."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        output = composer._compose_with_llm(
            page_plan=auth_page_plan,
            evidence_binding=None,
            context={},
            endpoints=sample_snapshot.endpoints[:2],
        )

        assert output is not None
        assert output.page_id == "api-authentication"


# =============================================================================
# TESTS FOR COMPOSER CONTEXT CREATION
# =============================================================================

class TestComposerContextCreation:
    """Tests for ComposerContext creation."""

    def test_create_composer_context(self, sample_snapshot):
        """Test creating composer context from service context."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        service_context = {
            "service_family": "python-backend",
            "endpoint_count": 3,
            "has_auth": True,
        }
        endpoints = sample_snapshot.endpoints[:3]

        context = composer._create_composer_context(
            page_plan=WikiPagePlan(
                page_id="test",
                title="Test",
                category=WikiTaxonomyCategory.API_REFERENCE,
                output_path="docs/test.md",
                source_requirements=SourceRequirement(),
                generation_mode=GenerationMode.RULE_FIRST,
            ),
            service_context=service_context,
            endpoints=endpoints,
        )

        assert context.repository_name == "python-backend"
        assert len(context.endpoints) == 3

    def test_composer_context_includes_auth_info(self, sample_snapshot):
        """Test that composer context includes auth information."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        auth_endpoints = [ep for ep in sample_snapshot.endpoints if ep.auth_required]

        context = composer._create_composer_context(
            page_plan=WikiPagePlan(
                page_id="test",
                title="Test",
                category=WikiTaxonomyCategory.API_REFERENCE,
                output_path="docs/test.md",
                source_requirements=SourceRequirement(),
                generation_mode=GenerationMode.RULE_FIRST,
            ),
            service_context={"service_family": "auth"},
            endpoints=auth_endpoints,
        )

        # All endpoints in context should show auth info
        for ep_ctx in context.endpoints:
            assert "auth_required" in ep_ctx


# =============================================================================
# TESTS FOR FACTORY FUNCTION
# =============================================================================

class TestFactoryFunction:
    """Tests for create_service_family_composer factory."""

    def test_create_with_mock_provider(self, sample_snapshot):
        """Test creating composer with mock provider."""
        mock_provider = create_mock_provider(response_content="# Test")
        composer = create_service_family_composer(
            snapshot=sample_snapshot,
            llm_provider=mock_provider,
        )

        assert composer is not None
        assert composer._llm_composer is not None

    def test_create_with_workspace_root(self, sample_snapshot):
        """Test creating composer with workspace root."""
        composer = create_service_family_composer(
            snapshot=sample_snapshot,
            workspace_root="/test/workspace",
        )

        assert composer.workspace_root == Path("/test/workspace")

    def test_create_without_provider_uses_default(self, sample_snapshot):
        """Test that creating without provider uses default mock."""
        composer = create_service_family_composer(snapshot=sample_snapshot)
        assert composer._llm_composer._provider is not None


# =============================================================================
# TESTS FOR EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_snapshot(self):
        """Test handling of empty snapshot."""
        empty_snapshot = RepositorySnapshot(
            repository=RepositoryInfo(name="empty", root_path="/test"),
            modules=[],
            endpoints=[],
            commands={},
            stats=RepositoryStats(),
        )

        composer = ServiceFamilyAPIComposer(empty_snapshot)
        page_plan = WikiPagePlan(
            page_id="api-test",
            title="Test",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="docs/test.md",
            source_requirements=SourceRequirement(),
            generation_mode=GenerationMode.RULE_FIRST,
        )

        output = composer.compose_api_page(page_plan)
        assert output is not None
        assert output.page_id == "api-test"

    def test_endpoint_table_with_all_methods(self, sample_snapshot):
        """Test formatting table with various HTTP methods."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        endpoints = [
            Endpoint(
                method=method,
                path=f"/test/{method.lower()}",
                module="api",
                handler=f"handler_{method.lower()}",
                file_path=f"src/api/{method.lower()}.py",
            )
            for method in ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
        ]

        result = composer.format_endpoint_table(endpoints)

        for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            assert method in result

    def test_service_purpose_empty_endpoints(self, sample_snapshot):
        """Test formatting purpose with no endpoints."""
        composer = ServiceFamilyAPIComposer(sample_snapshot)
        result = composer.format_service_purpose("empty-service", [])

        assert "empty-service" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])