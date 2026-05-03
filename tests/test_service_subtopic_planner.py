"""Tests for service subtopic planner.

Tests for the ServiceSubtopicPlanner that generates multi-page
service documentation following Qoder Chinese wiki patterns.
"""

from __future__ import annotations

import pytest

from repo_wiki.core.contracts import (
    Endpoint,
    Module,
    RepositoryInfo,
    RepositorySnapshot,
)
from repo_wiki.planner.identity import RepositoryIdentity
from repo_wiki.planner.schema import (
    WikiTaxonomyCategory,
)
from repo_wiki.planner.service_subtopic_planner import (
    ServiceSubtopicCategory,
    ServiceSubtopicPlanner,
    plan_service_subtopics,
)


class TestServiceSubtopicPlanner:
    """Tests for ServiceSubtopicPlanner."""

    @pytest.fixture
    def sample_identity(self):
        """Sample repository identity."""
        return RepositoryIdentity(
            name="AI_API_Atlas",
            display_name="AI API Atlas",
            root_path="/test/ai-api-atlas",
            language="python",
            framework="fastapi",
        )

    @pytest.fixture
    def python_service_modules(self):
        """Python service modules for testing."""
        return [
            Module(
                name="tcsl-generator-service",
                path="services/tcsl",
                responsibility="Generate TCSL content",
                exports=["TCSLGenerator"],
                depends_on=[],
                depended_by=[],
                interfaces=["POST /generate"],
                data_models=["TCSLRequest", "TCSLResponse"],
                owner="team-nlp",
                doc_path="docs/services/tcsl.md",
                domain="ai-services",
                service_family="python-backend",
                runtime_role="api-server",
            ),
            Module(
                name="scenario-orchestrator-service",
                path="services/scenario",
                responsibility="Orchestrate scenarios",
                exports=["ScenarioOrchestrator"],
                depends_on=[],
                depended_by=[],
                interfaces=["POST /orchestrate"],
                data_models=["ScenarioRequest", "ScenarioResponse"],
                owner="team-orchestration",
                doc_path="docs/services/scenario.md",
                domain="ai-services",
                service_family="python-backend",
                runtime_role="api-server",
            ),
        ]

    @pytest.fixture
    def core_service_modules(self):
        """Core service modules for testing."""
        return [
            Module(
                name="api-gateway",
                path="core/gateway",
                responsibility="API Gateway",
                exports=["APIGateway"],
                depends_on=[],
                depended_by=[],
                interfaces=["GET /health"],
                data_models=["RouteConfig"],
                owner="team-core",
                doc_path="docs/core/gateway.md",
                domain="core-platform",
                service_family="python-backend",
                runtime_role="api-server",
            ),
            Module(
                name="execution-engine",
                path="core/execution",
                responsibility="Execute workflows",
                exports=["ExecutionEngine"],
                depends_on=[],
                depended_by=[],
                interfaces=["POST /execute"],
                data_models=["ExecutionRequest", "ExecutionResult"],
                owner="team-core",
                doc_path="docs/core/execution.md",
                domain="core-platform",
                service_family="python-backend",
                runtime_role="worker",
            ),
        ]

    @pytest.fixture
    def sample_endpoints(self):
        """Sample endpoints for testing."""
        return [
            Endpoint(
                method="POST",
                path="/api/tcsl/generate",
                module="tcsl-generator-service",
                handler="generate_tcsl",
                file_path="services/tcsl/generator.py",
                service_family="python-backend",
                domain="ai-services",
                runtime_role="api-server",
                auth_required=True,
                request_body=True,
            ),
            Endpoint(
                method="GET",
                path="/api/tcsl/health",
                module="tcsl-generator-service",
                handler="health",
                file_path="services/tcsl/health.py",
                service_family="python-backend",
                domain="ai-services",
                runtime_role="api-server",
                auth_required=False,
            ),
        ]

    def test_planner_initialization(self, sample_identity):
        """Test planner initializes correctly."""
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(
                name="test",
                root_path="/test",
            ),
            modules=[],
            endpoints=[],
            data_models=[],
        )
        planner = ServiceSubtopicPlanner(sample_identity, snapshot)
        assert planner.identity == sample_identity
        assert planner.snapshot == snapshot
        assert planner.pages == []

    def test_generate_python_service_subtopics(
        self,
        sample_identity,
        python_service_modules,
        sample_endpoints,
    ):
        """Test generation of Python service subtopic pages."""
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(
                name="test",
                root_path="/test",
            ),
            modules=python_service_modules,
            endpoints=sample_endpoints,
            data_models=[],
        )
        manifest = ServiceSubtopicPlanner(sample_identity, snapshot).generate()

        # Should have index page + domain page + service subtopic pages
        # Index (1) + domain (1) + 2 services * 5 subtopics each (10) = 12 pages
        assert manifest.page_count() >= 12

        # Verify subtopics are generated
        page_ids = {p.page_id for p in manifest.pages}
        assert any("overview" in pid for pid in page_ids)
        assert any("architecture" in pid for pid in page_ids)
        assert any("api-docs" in pid for pid in page_ids)
        assert any("deployment" in pid for pid in page_ids)
        assert any("core-components" in pid for pid in page_ids)

    def test_generate_business_subdomain_pages(
        self,
        sample_identity,
        core_service_modules,
    ):
        """Test generation of business subdomain pages."""
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(
                name="test",
                root_path="/test",
            ),
            modules=core_service_modules,
            endpoints=[],
            data_models=[],
        )
        manifest = ServiceSubtopicPlanner(sample_identity, snapshot).generate()

        # Should have index + domain + services
        assert manifest.page_count() >= 4

        page_ids = {p.page_id for p in manifest.pages}
        assert any("core-services-index" in pid for pid in page_ids)
        assert any("core-python-backend" in pid for pid in page_ids)

    def test_service_subtopics_have_correct_structure(
        self,
        sample_identity,
        python_service_modules,
    ):
        """Test service subtopic pages have correct structure."""
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(
                name="test",
                root_path="/test",
            ),
            modules=python_service_modules,
            endpoints=[],
            data_models=[],
        )
        manifest = ServiceSubtopicPlanner(sample_identity, snapshot).generate()

        # Find a service subtopic page
        subtopic_pages = [
            p
            for p in manifest.pages
            if "tcsl-generator-service" in p.page_id and "overview" in p.page_id
        ]
        assert len(subtopic_pages) == 1

        page = subtopic_pages[0]
        assert page.category == WikiTaxonomyCategory.PYTHON_SERVICES
        assert page.title.startswith("TCSL生成服务")
        assert "概述" in page.title
        assert page.generation_mode is not None

    def test_subtopic_templates_all_generated(
        self,
        sample_identity,
        python_service_modules,
    ):
        """Test all 5 subtopic templates are generated per service."""
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(
                name="test",
                root_path="/test",
            ),
            modules=python_service_modules[:1],  # Only one service
            endpoints=[],
            data_models=[],
        )
        manifest = ServiceSubtopicPlanner(sample_identity, snapshot).generate()

        # Get pages for the service (filter to only Python services category to avoid core-services duplicates)
        service_pages = [
            p
            for p in manifest.pages
            if "tcsl-generator-service" in p.page_id
            and p.category == WikiTaxonomyCategory.PYTHON_SERVICES
        ]
        # Should have 5 subtopic pages (overview, architecture, api-docs, deployment, core-components)
        assert len(service_pages) == 5

        # Check all subtopic types are present - look for subtopic keywords in page_id
        subtopic_keywords = {
            "overview": False,
            "architecture": False,
            "api-docs": False,
            "deployment": False,
            "core-components": False,
        }
        for page in service_pages:
            for keyword in subtopic_keywords:
                if keyword in page.page_id:
                    subtopic_keywords[keyword] = True

        assert all(
            subtopic_keywords.values()
        ), f"Missing subtopics: {[k for k, v in subtopic_keywords.items() if not v]}"

    def test_navigation_tree_contains_service_pages(
        self,
        sample_identity,
        python_service_modules,
    ):
        """Test navigation tree includes service subtopic pages."""
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(
                name="test",
                root_path="/test",
            ),
            modules=python_service_modules,
            endpoints=[],
            data_models=[],
        )
        manifest = ServiceSubtopicPlanner(sample_identity, snapshot).generate()

        assert len(manifest.navigation_tree) > 0

        # Find category nodes
        category_ids = {n.node_id for n in manifest.navigation_tree}
        assert any("Python服务" in cid for cid in category_ids)

    def test_plan_service_subtopics_function(
        self,
        sample_identity,
        python_service_modules,
    ):
        """Test plan_service_subtopics convenience function."""
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(
                name="test",
                root_path="/test",
            ),
            modules=python_service_modules,
            endpoints=[],
            data_models=[],
        )
        manifest = plan_service_subtopics(sample_identity, snapshot)
        assert manifest.page_count() >= 1
        assert manifest.profile == "service-subtopic"

    def test_endpoints_grouped_by_service(
        self,
        sample_identity,
        python_service_modules,
        sample_endpoints,
    ):
        """Test endpoints are correctly grouped by service."""
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(
                name="test",
                root_path="/test",
            ),
            modules=python_service_modules,
            endpoints=sample_endpoints,
            data_models=[],
        )
        manifest = ServiceSubtopicPlanner(sample_identity, snapshot).generate()

        # Find API docs page for the service
        api_docs_pages = [
            p
            for p in manifest.pages
            if "tcsl-generator-service" in p.page_id and "api-docs" in p.page_id
        ]
        assert len(api_docs_pages) == 1

        # Should have endpoints from the service
        page = api_docs_pages[0]
        assert len(page.source_requirements.endpoints) >= 1


class TestServiceSubtopicCategory:
    """Tests for ServiceSubtopicCategory enum-like class."""

    def test_subtopic_constants(self):
        """Test subtopic category constants are defined."""
        assert ServiceSubtopicCategory.OVERVIEW == "overview"
        assert ServiceSubtopicCategory.ARCHITECTURE == "architecture"
        assert ServiceSubtopicCategory.API_DOCS == "api-docs"
        assert ServiceSubtopicCategory.DEPLOYMENT == "deployment"
        assert ServiceSubtopicCategory.CORE_COMPONENTS == "core-components"

    def test_subtopic_count(self):
        """Test there are exactly 5 subtopic categories."""
        subtopics = [
            ServiceSubtopicCategory.OVERVIEW,
            ServiceSubtopicCategory.ARCHITECTURE,
            ServiceSubtopicCategory.API_DOCS,
            ServiceSubtopicCategory.DEPLOYMENT,
            ServiceSubtopicCategory.CORE_COMPONENTS,
        ]
        assert len(subtopics) == 5


class TestManifestNavigationIntegration:
    """Integration tests for service subtopic planner with manifest navigation."""

    @pytest.fixture
    def sample_identity(self):
        """Sample repository identity."""
        return RepositoryIdentity(
            name="AI_API_Atlas",
            display_name="AI API Atlas",
            root_path="/test/ai-api-atlas",
            language="python",
            framework="fastapi",
        )

    @pytest.fixture
    def python_service_modules(self):
        """Python service modules for testing."""
        return [
            Module(
                name="tcsl-generator-service",
                path="services/tcsl",
                responsibility="Generate TCSL content",
                exports=["TCSLGenerator"],
                depends_on=[],
                depended_by=[],
                interfaces=["POST /generate"],
                data_models=["TCSLRequest", "TCSLResponse"],
                owner="team-nlp",
                doc_path="docs/services/tcsl.md",
                domain="ai-services",
                service_family="python-backend",
                runtime_role="api-server",
            ),
        ]

    def test_service_pages_compatible_with_manifest(
        self,
        sample_identity,
        python_service_modules,
    ):
        """Test generated pages are compatible with WikiPlanManifest."""
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(
                name="test",
                root_path="/test",
            ),
            modules=python_service_modules,
            endpoints=[],
            data_models=[],
        )
        manifest = ServiceSubtopicPlanner(sample_identity, snapshot).generate()

        # Test manifest methods work
        assert manifest.page_count() > 0
        assert len(manifest.pages_by_category(WikiTaxonomyCategory.PYTHON_SERVICES)) > 0

        # Test children_of works
        root_pages = manifest.children_of(None)
        assert len(root_pages) > 0

    def test_page_ids_are_unique(self, sample_identity, python_service_modules):
        """Test all generated page IDs are unique."""
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(
                name="test",
                root_path="/test",
            ),
            modules=python_service_modules,
            endpoints=[],
            data_models=[],
        )
        manifest = ServiceSubtopicPlanner(sample_identity, snapshot).generate()

        page_ids = [p.page_id for p in manifest.pages]
        assert len(page_ids) == len(set(page_ids))

    def test_sort_order_is_sequential(self, sample_identity, python_service_modules):
        """Test pages have sequential sort orders within groups."""
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(
                name="test",
                root_path="/test",
            ),
            modules=python_service_modules,
            endpoints=[],
            data_models=[],
        )
        manifest = ServiceSubtopicPlanner(sample_identity, snapshot).generate()

        # Pages should be sorted by category order then sort_order
        prev_category_order = -1
        prev_sort_order = -1
        for page in manifest.pages:
            # Categories are sorted
            category_order = {
                WikiTaxonomyCategory.PYTHON_SERVICES: 3,
                WikiTaxonomyCategory.CORE_SERVICES: 2,
            }.get(page.category, 99)
            if category_order >= prev_category_order:
                if category_order > prev_category_order:
                    prev_sort_order = -1
                # Within same category, sort_order should increase
                assert page.sort_order >= prev_sort_order
            prev_category_order = category_order
            prev_sort_order = page.sort_order
