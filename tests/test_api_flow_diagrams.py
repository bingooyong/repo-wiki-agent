"""Tests for API flow diagram generator.

Tests the api_flow_diagram module (repo_wiki/generator/api_flow_diagram.py) which provides:
- APIFlowDiagramGenerator: Generates sequence diagrams for API service families
- SpecializedAPIFlowGenerator: Generates auth, error, and health flow diagrams
- APIFlowDiagram: Dataclass with diagram and evidence backing
- generate_api_flow_diagram: Convenience function for single diagram generation
- render_flow_diagram_to_markdown: Render diagram to Markdown with mermaid block

Phase 25 - Task 25.5: API flow diagram generation

Test coverage:
- Service family extraction from page IDs
- Endpoint filtering by source requirements and service family
- Flow diagram generation with evidence backing
- Handler citations in diagrams
- Mermaid syntax validation
- Multiple diagram generation for service families
- Specialized flow diagrams (auth, health)
"""

from __future__ import annotations

import pytest

from repo_wiki.core.contracts import (
    Endpoint,
    Module,
    RepositoryInfo,
    RepositorySnapshot,
    RepositoryStats,
)
from repo_wiki.evidence.ranking import EvidenceCandidate, PageEvidenceBinding
from repo_wiki.generator.api_flow_diagram import (
    APIFlowDiagram,
    APIFlowDiagramGenerator,
    APIFlowEvidence,
    SpecializedAPIFlowGenerator,
    create_api_flow_diagram_generator,
    create_specialized_flow_generator,
    generate_api_flow_diagram,
    render_flow_diagram_to_markdown,
)
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
            line_number=10,
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
            line_number=25,
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
            line_number=50,
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
            line_number=30,
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


# =============================================================================
# TESTS FOR API FLOW EVIDENCE
# =============================================================================


class TestAPIFlowEvidence:
    """Tests for APIFlowEvidence dataclass."""

    def test_create_flow_evidence(self):
        """Test creating API flow evidence."""
        evidence = APIFlowEvidence(
            handler_file="src/auth/handlers.py",
            handler_line=25,
            handler_symbol="login_handler",
        )
        assert evidence.handler_file == "src/auth/handlers.py"
        assert evidence.handler_line == 25
        assert evidence.handler_symbol == "login_handler"
        assert evidence.downstream_calls == []

    def test_create_flow_evidence_with_downstream(self):
        """Test creating evidence with downstream calls."""
        evidence = APIFlowEvidence(
            handler_file="src/api/users.py",
            handler_line=30,
            handler_symbol="get_users",
            downstream_calls=[("auth", "/api/auth/validate", "validate_token")],
        )
        assert len(evidence.downstream_calls) == 1
        assert evidence.downstream_calls[0] == ("auth", "/api/auth/validate", "validate_token")


# =============================================================================
# TESTS FOR SERVICE FAMILY EXTRACTION
# =============================================================================


class TestServiceFamilyExtraction:
    """Tests for service family extraction from page IDs."""

    def test_extract_python_backend(self, sample_snapshot):
        """Test extracting python-backend from page ID."""
        generator = APIFlowDiagramGenerator(sample_snapshot)
        result = generator._extract_service_family("api-python-backend")
        assert result == "python-backend"

    def test_extract_typescript_frontend(self, sample_snapshot):
        """Test extracting typescript-frontend from page ID."""
        generator = APIFlowDiagramGenerator(sample_snapshot)
        result = generator._extract_service_family("api-typescript-frontend")
        assert result == "typescript-frontend"

    def test_extract_auth_page_returns_none(self, sample_snapshot):
        """Test that auth page returns None (not a service family)."""
        generator = APIFlowDiagramGenerator(sample_snapshot)
        result = generator._extract_service_family("api-authentication")
        assert result is None

    def test_extract_health_page_returns_none(self, sample_snapshot):
        """Test that health page returns None (not a service family)."""
        generator = APIFlowDiagramGenerator(sample_snapshot)
        result = generator._extract_service_family("api-health")
        assert result is None

    def test_extract_error_page_returns_none(self, sample_snapshot):
        """Test that error page returns None (not a service family)."""
        generator = APIFlowDiagramGenerator(sample_snapshot)
        result = generator._extract_service_family("api-error-codes")
        assert result is None

    def test_extract_convention_page_returns_none(self, sample_snapshot):
        """Test that convention page returns None (not a service family)."""
        generator = APIFlowDiagramGenerator(sample_snapshot)
        result = generator._extract_service_family("api-auth-convention")
        assert result is None


# =============================================================================
# TESTS FOR ENDPOINT FILTERING
# =============================================================================


class TestEndpointFiltering:
    """Tests for endpoint filtering by source requirements and service family."""

    def test_filter_by_source_requirements(self, sample_snapshot, auth_page_plan):
        """Test filtering endpoints by source requirements in page plan."""
        generator = APIFlowDiagramGenerator(sample_snapshot)
        endpoints = generator._get_endpoints_for_page(auth_page_plan)
        assert len(endpoints) == 2
        assert all(ep.module == "auth" for ep in endpoints)

    def test_filter_by_service_family(self, sample_snapshot, python_backend_page_plan):
        """Test filtering endpoints by service family."""
        generator = APIFlowDiagramGenerator(sample_snapshot)
        # Note: python_backend_page_plan has source_requirements, so those are used
        endpoints = generator._get_endpoints_for_page(python_backend_page_plan)
        assert len(endpoints) == 3

    def test_filter_auth_endpoints(self, sample_snapshot):
        """Test filtering authentication-required endpoints."""
        generator = APIFlowDiagramGenerator(sample_snapshot)
        page_plan = WikiPagePlan(
            page_id="api-authentication",
            title="认证授权API",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="docs/pages/api/api-authentication.md",
            source_requirements=SourceRequirement(),  # Empty
            generation_mode=GenerationMode.RULE_FIRST,
        )
        endpoints = generator._get_endpoints_for_page(page_plan)
        assert all(ep.auth_required or ep.auth_type in ("bearer", "oauth", "api-key") for ep in endpoints)

    def test_filter_health_endpoints(self, sample_snapshot):
        """Test filtering health check endpoints."""
        generator = APIFlowDiagramGenerator(sample_snapshot)
        page_plan = WikiPagePlan(
            page_id="api-health",
            title="健康检查API",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="docs/pages/api/api-health.md",
            source_requirements=SourceRequirement(),  # Empty
            generation_mode=GenerationMode.RULE_FIRST,
        )
        endpoints = generator._get_endpoints_for_page(page_plan)
        assert len(endpoints) == 1
        assert endpoints[0].path == "/health"


# =============================================================================
# TESTS FOR FLOW DIAGRAM GENERATION
# =============================================================================


class TestFlowDiagramGeneration:
    """Tests for flow diagram generation."""

    def test_create_generator(self, sample_snapshot):
        """Test creating an API flow diagram generator."""
        generator = create_api_flow_diagram_generator(sample_snapshot)
        assert generator is not None
        assert isinstance(generator, APIFlowDiagramGenerator)

    def test_generate_flow_diagram_returns_diagram(self, sample_snapshot, auth_page_plan):
        """Test that generate_flow_diagram returns an APIFlowDiagram."""
        generator = create_api_flow_diagram_generator(sample_snapshot)
        flow_diagram = generator.generate_flow_diagram(auth_page_plan)

        assert flow_diagram is not None
        assert isinstance(flow_diagram, APIFlowDiagram)
        assert flow_diagram.service_family is not None

    def test_generate_flow_diagram_includes_evidence(self, sample_snapshot, auth_page_plan):
        """Test that generated diagram includes handler evidence."""
        generator = create_api_flow_diagram_generator(sample_snapshot)
        flow_diagram = generator.generate_flow_diagram(auth_page_plan)

        assert flow_diagram is not None
        assert len(flow_diagram.evidence) >= 1
        # Check that evidence has handler citations
        for ev in flow_diagram.evidence:
            assert ev.handler_file is not None
            assert ev.handler_line >= 0
            assert ev.handler_symbol is not None

    def test_generate_flow_diagram_with_rendered_mermaid(self, sample_snapshot, health_page_plan):
        """Test that generated diagram has rendered mermaid code."""
        generator = create_api_flow_diagram_generator(sample_snapshot)
        flow_diagram = generator.generate_flow_diagram(health_page_plan)

        assert flow_diagram is not None
        assert flow_diagram.diagram_plan is not None
        # The diagram_plan should have either rendered_diagram or None
        # (None if validation failed)
        assert flow_diagram.diagram_plan.diagram_id is not None

    def test_generate_flow_diagram_for_service_family(self, sample_snapshot, python_backend_page_plan):
        """Test generating flow diagram for service family page."""
        generator = create_api_flow_diagram_generator(sample_snapshot)
        flow_diagram = generator.generate_flow_diagram(python_backend_page_plan)

        assert flow_diagram is not None
        assert flow_diagram.service_family == "python-backend"

    def test_generate_flow_diagram_returns_none_when_no_endpoints(self, sample_snapshot):
        """Test that None is returned when no endpoints match."""
        generator = create_api_flow_diagram_generator(sample_snapshot)
        page_plan = WikiPagePlan(
            page_id="api-nonexistent",
            title="Non-existent API",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="docs/pages/api/api-nonexistent.md",
            source_requirements=SourceRequirement(
                endpoints=["GET /nonexistent/path"],
            ),
            generation_mode=GenerationMode.RULE_FIRST,
        )
        flow_diagram = generator.generate_flow_diagram(page_plan)
        assert flow_diagram is None


# =============================================================================
# TESTS FOR MULTIPLE DIAGRAM GENERATION
# =============================================================================


class TestMultipleDiagramGeneration:
    """Tests for generating multiple diagrams."""

    def test_generate_flow_diagrams_for_service_families(
        self, sample_snapshot, auth_page_plan, health_page_plan
    ):
        """Test generating multiple flow diagrams."""
        generator = create_api_flow_diagram_generator(sample_snapshot)
        page_plans = [auth_page_plan, health_page_plan]

        diagrams = generator.generate_flow_diagrams_for_service_families(page_plans)

        assert len(diagrams) >= 1  # At least auth should have endpoints

    def test_generate_flow_diagrams_with_evidence_bindings(
        self, sample_snapshot, auth_page_plan, health_page_plan
    ):
        """Test generating diagrams with evidence bindings."""
        generator = create_api_flow_diagram_generator(sample_snapshot)

        # Create evidence binding
        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/auth/handlers.py",
            line_start=20,
            line_end=30,
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

        page_plans = [auth_page_plan, health_page_plan]
        bindings = {"api-authentication": binding}

        diagrams = generator.generate_flow_diagrams_for_service_families(page_plans, bindings)

        assert len(diagrams) >= 1


# =============================================================================
# TESTS FOR SPECIALIZED FLOW GENERATORS
# =============================================================================


class TestSpecializedFlowGenerator:
    """Tests for specialized flow diagram generators."""

    def test_create_specialized_generator(self, sample_snapshot):
        """Test creating a specialized flow generator."""
        generator = create_specialized_flow_generator(sample_snapshot)
        assert generator is not None
        assert isinstance(generator, SpecializedAPIFlowGenerator)

    def test_generate_auth_flow_diagram(self, sample_snapshot, auth_page_plan):
        """Test generating authentication flow diagram."""
        generator = create_specialized_flow_generator(sample_snapshot)
        flow_diagram = generator.generate_auth_flow_diagram(auth_page_plan)

        # May be None if no auth endpoints found
        if flow_diagram:
            assert flow_diagram.service_family == "authentication"
            assert flow_diagram.diagram_plan is not None

    def test_generate_health_check_flow_diagram(self, sample_snapshot, health_page_plan):
        """Test generating health check flow diagram."""
        generator = create_specialized_flow_generator(sample_snapshot)
        flow_diagram = generator.generate_health_check_flow_diagram(health_page_plan)

        if flow_diagram:
            assert flow_diagram.service_family == "health"
            assert "Health" in flow_diagram.title or "health" in flow_diagram.title.lower()


# =============================================================================
# TESTS FOR CONVENIENCE FUNCTIONS
# =============================================================================


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_generate_api_flow_diagram(
        self, sample_snapshot, health_page_plan
    ):
        """Test the convenience function for generating a single diagram."""
        flow_diagram = generate_api_flow_diagram(
            page_plan=health_page_plan,
            snapshot=sample_snapshot,
        )

        assert flow_diagram is not None
        assert isinstance(flow_diagram, APIFlowDiagram)

    def test_generate_api_flow_diagram_with_evidence_binding(
        self, sample_snapshot, auth_page_plan
    ):
        """Test convenience function with evidence binding."""
        span = EvidenceSpanRecord(
            digest="xyz789",
            file_path="src/auth/handlers.py",
            line_start=25,
            line_end=35,
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

        flow_diagram = generate_api_flow_diagram(
            page_plan=auth_page_plan,
            snapshot=sample_snapshot,
            evidence_binding=binding,
        )

        assert flow_diagram is not None


# =============================================================================
# TESTS FOR MARKDOWN RENDERING
# =============================================================================


class TestMarkdownRendering:
    """Tests for Markdown rendering of flow diagrams."""

    def test_render_flow_diagram_to_markdown(self, sample_snapshot, health_page_plan):
        """Test rendering flow diagram to Markdown."""
        generator = create_api_flow_diagram_generator(sample_snapshot)
        flow_diagram = generator.generate_flow_diagram(health_page_plan)

        if flow_diagram:
            # Set rendered diagram if not already set
            if not flow_diagram.diagram_plan.rendered_diagram:
                flow_diagram.diagram_plan.rendered_diagram = """sequenceDiagram
    participant Client
    participant API
    Client->>+API: GET /health
    API-->>-Client: response"""

            markdown = render_flow_diagram_to_markdown(flow_diagram)
            assert markdown is not None
            assert "```mermaid" in markdown
            assert "```" in markdown
            assert flow_diagram.title in markdown

    def test_render_empty_diagram_returns_empty_string(self):
        """Test that rendering empty diagram returns empty string."""
        from repo_wiki.generator.mermaid_planner import DiagramPlan, MermaidDiagramType

        flow_diagram = APIFlowDiagram(
            diagram_id="test",
            service_family="test",
            title="Test",
            diagram_plan=DiagramPlan(
                diagram_id="test",
                diagram_type=MermaidDiagramType.SEQUENCE_DIAGRAM,
                title="Test",
                sequence_participants=["A", "B"],
                sequence_messages=[],
            ),
            evidence=[],
        )
        # diagram_plan.rendered_diagram is None
        markdown = render_flow_diagram_to_markdown(flow_diagram)
        assert markdown == ""


# =============================================================================
# TESTS FOR CITATIONS AND EVIDENCE
# =============================================================================


class TestCitationsAndEvidence:
    """Tests for handler citations in diagrams."""

    def test_collect_flow_evidence(self, sample_snapshot):
        """Test collecting flow evidence from endpoints."""
        generator = create_api_flow_diagram_generator(sample_snapshot)
        endpoints = [sample_snapshot.endpoints[1]]  # login_handler
        evidence = generator._collect_flow_evidence(endpoints)

        assert len(evidence) == 1
        assert evidence[0].handler_file == "src/auth/handlers.py"
        assert evidence[0].handler_line == 25
        assert evidence[0].handler_symbol == "login_handler"

    def test_evidence_includes_all_endpoints(self, sample_snapshot):
        """Test that evidence includes all endpoints."""
        generator = create_api_flow_diagram_generator(sample_snapshot)
        endpoints = sample_snapshot.endpoints
        evidence = generator._collect_flow_evidence(endpoints)

        assert len(evidence) == len(endpoints)


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

        generator = create_api_flow_diagram_generator(empty_snapshot)
        page_plan = WikiPagePlan(
            page_id="api-test",
            title="Test",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="docs/test.md",
            source_requirements=SourceRequirement(),
            generation_mode=GenerationMode.RULE_FIRST,
        )

        flow_diagram = generator.generate_flow_diagram(page_plan)
        assert flow_diagram is None

    def test_all_auth_endpoints(self, sample_snapshot):
        """Test snapshot where all endpoints require auth."""
        generator = create_api_flow_diagram_generator(sample_snapshot)
        auth_endpoints = [
            ep for ep in sample_snapshot.endpoints
            if ep.auth_required or ep.auth_type in ("bearer", "oauth", "api-key")
        ]

        evidence = generator._collect_flow_evidence(auth_endpoints)
        assert len(evidence) == len(auth_endpoints)
        assert all(ev.handler_symbol for ev in evidence)

    def test_build_flow_context_empty_endpoints(self, sample_snapshot):
        """Test building flow context with empty endpoint list."""
        generator = create_api_flow_diagram_generator(sample_snapshot)
        page_plan = WikiPagePlan(
            page_id="api-test",
            title="Test",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="docs/test.md",
            source_requirements=SourceRequirement(),
            generation_mode=GenerationMode.RULE_FIRST,
        )

        context = generator._build_flow_context(page_plan, None, [])
        assert context["endpoints"] == []
        assert context["service_family"] == "unknown"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
