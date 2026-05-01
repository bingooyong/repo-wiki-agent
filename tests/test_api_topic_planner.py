"""Tests for API topic planner (Task 25.2).

Validates that API endpoints are planned by service family and topic
rather than raw endpoint count. Generates at least 15 API planned pages.
"""

from __future__ import annotations

import pytest

from repo_wiki.core.contracts import (
    DataModel,
    Endpoint,
    Module,
    RepositoryInfo,
    RepositorySnapshot,
    RepositoryStats,
)
from repo_wiki.planner.api_topic_planner import (
    APITopicCategory,
    APITopicPlanner,
    plan_api_topics,
)
from repo_wiki.planner.identity import RepositoryIdentity
from repo_wiki.planner.schema import (
    GenerationMode,
    WikiTaxonomyCategory,
)


class TestAPITopicPlanner:
    """Tests for APITopicPlanner."""

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
    def sample_snapshot(self):
        """Sample repository snapshot with enriched endpoints."""
        modules = [
            Module(
                name="repo_wiki",
                path="repo_wiki",
                responsibility="Handles core wiki functionality",
                exports=["RepoWikiService", "bootstrap"],
                depends_on=["tests"],
                depended_by=[],
                interfaces=[],
                data_models=["RepositoryInfo", "Module"],
                owner="team-core",
                doc_path="docs/modules/repo_wiki.md",
                domain="core-platform",
                service_family="python-backend",
            ),
            Module(
                name="ai_services",
                path="repo_wiki/ai_services",
                responsibility="Handles AI model integrations",
                exports=["EmbeddingProvider", "LLMProvider"],
                depends_on=[],
                depended_by=["repo_wiki"],
                interfaces=["POST /embed", "POST /complete"],
                data_models=["EmbeddingResult", "CompletionResult"],
                owner="team-ai",
                doc_path="docs/modules/ai_services.md",
                domain="ai-services",
                service_family="python-backend",
            ),
            Module(
                name="auth_service",
                path="repo_wiki/auth",
                responsibility="Handles authentication and authorization",
                exports=["AuthService", "TokenValidator"],
                depends_on=[],
                depended_by=["repo_wiki"],
                interfaces=["POST /login", "POST /refresh", "GET /verify"],
                data_models=["Token", "User"],
                owner="team-security",
                doc_path="docs/modules/auth.md",
                domain="security",
                service_family="api-server",
            ),
            Module(
                name="health_service",
                path="repo_wiki/health",
                responsibility="Health check endpoints",
                exports=["HealthService"],
                depends_on=[],
                depended_by=[],
                interfaces=["GET /health", "GET /ready"],
                data_models=[],
                owner="team-ops",
                doc_path="docs/modules/health.md",
                domain="operations",
                service_family="api-server",
            ),
        ]

        endpoints = [
            # Auth endpoints (require authentication)
            Endpoint(
                method="POST",
                path="/api/auth/login",
                module="auth_service",
                handler="login",
                file_path="repo_wiki/auth/service.py",
                service_family="api-server",
                domain="security",
                runtime_role="api-server",
                auth_type="bearer",
                auth_required=True,
                request_body=True,
                response_type="json",
                error_codes=[400, 401, 500],
                line_number=10,
                line_end=25,
            ),
            Endpoint(
                method="POST",
                path="/api/auth/refresh",
                module="auth_service",
                handler="refresh_token",
                file_path="repo_wiki/auth/service.py",
                service_family="api-server",
                domain="security",
                runtime_role="api-server",
                auth_type="bearer",
                auth_required=True,
                request_body=True,
                response_type="json",
                error_codes=[400, 401, 500],
                line_number=30,
                line_end=45,
            ),
            Endpoint(
                method="GET",
                path="/api/auth/verify",
                module="auth_service",
                handler="verify_token",
                file_path="repo_wiki/auth/service.py",
                service_family="api-server",
                domain="security",
                runtime_role="api-server",
                auth_type="bearer",
                auth_required=True,
                request_body=False,
                response_type="json",
                error_codes=[401, 403, 500],
                line_number=50,
                line_end=65,
            ),
            # Health endpoints (no auth required)
            Endpoint(
                method="GET",
                path="/health",
                module="health_service",
                handler="health_check",
                file_path="repo_wiki/health/service.py",
                service_family="api-server",
                domain="operations",
                runtime_role="api-server",
                auth_type="none",
                auth_required=False,
                request_body=False,
                response_type="json",
                error_codes=[500],
                line_number=10,
                line_end=20,
            ),
            Endpoint(
                method="GET",
                path="/ready",
                module="health_service",
                handler="readiness_check",
                file_path="repo_wiki/health/service.py",
                service_family="api-server",
                domain="operations",
                runtime_role="api-server",
                auth_type="none",
                auth_required=False,
                request_body=False,
                response_type="json",
                error_codes=[500],
                line_number=25,
                line_end=35,
            ),
            # AI service endpoints
            Endpoint(
                method="POST",
                path="/api/embed",
                module="ai_services",
                handler="embed_text",
                file_path="repo_wiki/ai_services/embeddings.py",
                service_family="python-backend",
                domain="ai-services",
                runtime_role="worker",
                auth_type="bearer",
                auth_required=True,
                request_body=True,
                response_type="json",
                error_codes=[400, 500],
                line_number=15,
                line_end=30,
            ),
            Endpoint(
                method="POST",
                path="/api/complete",
                module="ai_services",
                handler="complete_text",
                file_path="repo_wiki/ai_services/completion.py",
                service_family="python-backend",
                domain="ai-services",
                runtime_role="worker",
                auth_type="bearer",
                auth_required=True,
                request_body=True,
                response_type="json",
                error_codes=[400, 500],
                line_number=20,
                line_end=40,
            ),
            # Core wiki endpoints
            Endpoint(
                method="GET",
                path="/api/wiki/pages",
                module="repo_wiki",
                handler="list_pages",
                file_path="repo_wiki/service.py",
                service_family="python-backend",
                domain="core-platform",
                runtime_role="api-server",
                auth_type="bearer",
                auth_required=True,
                request_body=False,
                response_type="json",
                error_codes=[401, 404, 500],
                line_number=50,
                line_end=70,
            ),
            Endpoint(
                method="POST",
                path="/api/wiki/pages",
                module="repo_wiki",
                handler="create_page",
                file_path="repo_wiki/service.py",
                service_family="python-backend",
                domain="core-platform",
                runtime_role="api-server",
                auth_type="bearer",
                auth_required=True,
                request_body=True,
                response_type="json",
                error_codes=[400, 401, 500],
                line_number=75,
                line_end=95,
            ),
        ]

        data_models = [
            DataModel(
                name="EmbeddingResult",
                type="python_class",
                module="ai_services",
                file_path="repo_wiki/ai_services/embeddings.py",
            ),
            DataModel(
                name="CompletionResult",
                type="python_class",
                module="ai_services",
                file_path="repo_wiki/ai_services/completion.py",
            ),
            DataModel(
                name="Token",
                type="python_class",
                module="auth_service",
                file_path="repo_wiki/auth/service.py",
            ),
            DataModel(
                name="User",
                type="python_class",
                module="auth_service",
                file_path="repo_wiki/auth/service.py",
            ),
        ]

        repository = RepositoryInfo(
            name="AI_API_Atlas",
            root_path="/test/ai-api-atlas",
            language="python",
            framework="fastapi",
            package_manager="pip",
            entry_points=["uvicorn main:app"],
            key_directories=["repo_wiki", "tests", "docs"],
        )

        stats = RepositoryStats(
            total_files=100,
            scanned_files=80,
            skipped_files=20,
            module_count=4,
            endpoint_count=9,
            data_model_count=4,
        )

        return RepositorySnapshot(
            repository=repository,
            modules=modules,
            endpoints=endpoints,
            data_models=data_models,
            commands={"start": "uvicorn main:app", "build": "pip install -e .", "test": "pytest"},
            stats=stats,
        )

    def test_generate_api_topics(self, sample_identity, sample_snapshot):
        """Test generating API topic plan."""
        planner = APITopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        assert manifest.page_count() > 0
        assert manifest.repository_identity is not None
        assert manifest.repository_identity.name == "AI_API_Atlas"

    def test_at_least_fifteen_api_pages(self, sample_identity, sample_snapshot):
        """Test that at least 15 API pages are generated."""
        planner = APITopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        api_pages = manifest.pages_by_category(WikiTaxonomyCategory.API_REFERENCE)
        assert len(api_pages) >= 15, f"Expected at least 15 API pages, got {len(api_pages)}"

    def test_api_pages_grouped_by_service_family(
        self, sample_identity, sample_snapshot
    ):
        """Test that API pages are grouped by service family, not raw endpoint count."""
        planner = APITopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        # Check that service family pages exist
        service_family_ids = [
            "api-python-backend",
            "api-api-server",
        ]
        found_families = [
            pid for pid in service_family_ids
            if any(p.page_id == pid for p in manifest.pages)
        ]
        assert len(found_families) >= 1, "Expected service family API pages"

    def test_auth_api_pages_exist(self, sample_identity, sample_snapshot):
        """Test that auth/authz API pages are generated."""
        planner = APITopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        # Should have authentication page
        auth_pages = [p for p in manifest.pages if "auth" in p.page_id.lower()]
        assert len(auth_pages) >= 2, f"Expected at least 2 auth pages, got {len(auth_pages)}"

    def test_error_handling_pages_exist(self, sample_identity, sample_snapshot):
        """Test that error handling pages are generated."""
        planner = APITopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        # Should have error handling pages
        error_pages = [
            p for p in manifest.pages
            if "error" in p.page_id.lower() or p.title in ("错误处理API", "错误码参考")
        ]
        assert len(error_pages) >= 2, f"Expected error handling pages, got {len(error_pages)}"

    def test_health_api_pages_exist(self, sample_identity, sample_snapshot):
        """Test that health check API pages are generated."""
        planner = APITopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        # Should have health topic page
        health_pages = [
            p for p in manifest.pages
            if "health" in p.page_id.lower() or p.title in ("健康检查API",)
        ]
        assert len(health_pages) >= 1, f"Expected health API pages, got {len(health_pages)}"

    def test_all_pages_use_rule_first_mode(self, sample_identity, sample_snapshot):
        """Test all API pages use RULE_FIRST generation mode."""
        planner = APITopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        for page in manifest.pages:
            assert page.generation_mode == GenerationMode.RULE_FIRST

    def test_page_ids_are_unique(self, sample_identity, sample_snapshot):
        """Test all page IDs are unique."""
        planner = APITopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        page_ids = [p.page_id for p in manifest.pages]
        assert len(page_ids) == len(set(page_ids)), "Page IDs must be unique"

    def test_navigation_tree_exists(self, sample_identity, sample_snapshot):
        """Test navigation tree is generated."""
        planner = APITopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        assert len(manifest.navigation_tree) > 0
        # Should have category node for API
        category_nodes = [
            n for n in manifest.navigation_tree if n.node_type == "category"
        ]
        assert len(category_nodes) >= 1

    def test_parent_child_relationships(self, sample_identity, sample_snapshot):
        """Test parent-child page relationships."""
        planner = APITopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        for page in manifest.pages:
            if page.parent:
                parent_page = manifest.page_by_id(page.parent)
                assert parent_page is not None, f"Parent {page.parent} not found for {page.page_id}"

    def test_output_paths_valid(self, sample_identity, sample_snapshot):
        """Test all pages have valid output paths."""
        planner = APITopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        for page in manifest.pages:
            assert page.output_path.startswith("docs/pages/api/")
            assert page.output_path.endswith(".md")

    def test_source_requirements_populated(self, sample_identity, sample_snapshot):
        """Test pages have source requirements populated."""
        planner = APITopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        # API overview should have endpoints
        overview = manifest.page_by_id("api-reference")
        assert overview is not None
        assert len(overview.source_requirements.endpoints) > 0

    def test_plan_api_topics_function(self, sample_identity, sample_snapshot):
        """Test the plan_api_topics convenience function."""
        manifest = plan_api_topics(sample_identity, sample_snapshot)

        assert manifest.page_count() >= 15
        api_pages = manifest.pages_by_category(WikiTaxonomyCategory.API_REFERENCE)
        assert len(api_pages) >= 15


class TestAPITopicPlannerEdgeCases:
    """Tests for edge cases in API topic planner."""

    def test_empty_endpoints(self):
        """Test planner with no endpoints."""
        identity = RepositoryIdentity(
            name="empty-repo",
            display_name="Empty Repository",
            root_path="/test/empty",
        )
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(
                name="empty-repo",
                root_path="/test/empty",
            ),
            modules=[],
            endpoints=[],
            data_models=[],
        )

        planner = APITopicPlanner(identity, snapshot)
        manifest = planner.generate()

        # Should still generate overview page
        assert manifest.page_count() >= 1
        overview = manifest.page_by_id("api-reference")
        assert overview is not None

    def test_all_health_endpoints(self):
        """Test planner with only health endpoints."""
        identity = RepositoryIdentity(
            name="health-repo",
            display_name="Health Repository",
            root_path="/test/health",
        )
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(
                name="health-repo",
                root_path="/test/health",
            ),
            modules=[
                Module(
                    name="health",
                    path="health",
                    responsibility="Health checks",
                    exports=["HealthService"],
                    depends_on=[],
                    depended_by=[],
                    interfaces=[],
                    data_models=[],
                    owner="team-ops",
                    doc_path="docs/modules/health.md",
                    domain="operations",
                    service_family="api-server",
                ),
            ],
            endpoints=[
                Endpoint(
                    method="GET",
                    path="/health",
                    module="health",
                    handler="health_check",
                    file_path="health/service.py",
                    service_family="api-server",
                    domain="operations",
                    runtime_role="api-server",
                    auth_type="none",
                    auth_required=False,
                    request_body=False,
                    response_type="json",
                    error_codes=[500],
                    line_number=10,
                    line_end=20,
                ),
            ],
            data_models=[],
        )

        planner = APITopicPlanner(identity, snapshot)
        manifest = planner.generate()

        # Should still generate some pages
        assert manifest.page_count() >= 5

    def test_mixed_auth_types(self):
        """Test planner with mixed authentication types."""
        identity = RepositoryIdentity(
            name="mixed-auth-repo",
            display_name="Mixed Auth Repository",
            root_path="/test/mixed",
        )
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(
                name="mixed-auth-repo",
                root_path="/test/mixed",
            ),
            modules=[
                Module(
                    name="api",
                    path="api",
                    responsibility="API service",
                    exports=["APIService"],
                    depends_on=[],
                    depended_by=[],
                    interfaces=[],
                    data_models=[],
                    owner="team-core",
                    doc_path="docs/modules/api.md",
                    domain="core-platform",
                    service_family="api-server",
                ),
            ],
            endpoints=[
                Endpoint(
                    method="GET",
                    path="/public/data",
                    module="api",
                    handler="get_public_data",
                    file_path="api/service.py",
                    service_family="api-server",
                    domain="core-platform",
                    runtime_role="api-server",
                    auth_type="none",
                    auth_required=False,
                    request_body=False,
                    response_type="json",
                    error_codes=[500],
                    line_number=10,
                    line_end=20,
                ),
                Endpoint(
                    method="POST",
                    path="/private/data",
                    module="api",
                    handler="create_private_data",
                    file_path="api/service.py",
                    service_family="api-server",
                    domain="core-platform",
                    runtime_role="api-server",
                    auth_type="bearer",
                    auth_required=True,
                    request_body=True,
                    response_type="json",
                    error_codes=[400, 401, 500],
                    line_number=25,
                    line_end=40,
                ),
            ],
            data_models=[],
        )

        planner = APITopicPlanner(identity, snapshot)
        manifest = planner.generate()

        # Should generate auth and non-auth pages
        api_pages = manifest.pages_by_category(WikiTaxonomyCategory.API_REFERENCE)
        assert len(api_pages) >= 10