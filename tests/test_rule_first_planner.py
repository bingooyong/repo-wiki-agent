"""Tests for rule-first page planner."""

import pytest

from repo_wiki.core.contracts import (
    DataModel,
    Endpoint,
    Module,
    RepositoryInfo,
    RepositorySnapshot,
    RepositoryStats,
)
from repo_wiki.planner.identity import RepositoryIdentity
from repo_wiki.planner.rule_first import RuleFirstPlanner, plan_pages_from_snapshot
from repo_wiki.planner.schema import (
    GenerationMode,
    WikiTaxonomyCategory,
)


class TestRuleFirstPlanner:
    """Tests for RuleFirstPlanner."""

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
        """Sample repository snapshot with modules."""
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
                name="scanner",
                path="repo_wiki/scanner",
                responsibility="Handles repository scanning",
                exports=["RepositoryScanner"],
                depends_on=[],
                depended_by=[],
                interfaces=[],
                data_models=["ScannedFile"],
                owner="team-core",
                doc_path="docs/modules/scanner.md",
                domain="tooling",
                service_family="python-backend",
            ),
        ]

        endpoints = [
            Endpoint(
                method="POST",
                path="/api/embed",
                module="ai_services",
                handler="embed_text",
                file_path="repo_wiki/ai_services/embeddings.py",
            ),
            Endpoint(
                method="POST",
                path="/api/complete",
                module="ai_services",
                handler="complete_text",
                file_path="repo_wiki/ai_services/completion.py",
            ),
            Endpoint(
                method="GET",
                path="/api/scan",
                module="scanner",
                handler="scan_repo",
                file_path="repo_wiki/scanner/repository_scanner.py",
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
                name="ScannedFile",
                type="python_class",
                module="scanner",
                file_path="repo_wiki/scanner/repository_scanner.py",
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
            module_count=3,
            endpoint_count=3,
            data_model_count=3,
        )

        return RepositorySnapshot(
            repository=repository,
            modules=modules,
            endpoints=endpoints,
            data_models=data_models,
            commands={"start": "uvicorn main:app", "build": "pip install -e .", "test": "pytest"},
            stats=stats,
        )

    def test_generate_plan(self, sample_identity, sample_snapshot):
        """Test generating a complete plan."""
        planner = RuleFirstPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        assert manifest.page_count() > 0
        assert manifest.repository_identity is not None
        assert manifest.repository_identity.name == "AI_API_Atlas"

    def test_plan_has_overview_pages(self, sample_identity, sample_snapshot):
        """Test plan includes overview pages."""
        planner = RuleFirstPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        overview_pages = manifest.pages_by_category(WikiTaxonomyCategory.PROJECT_OVERVIEW)
        assert len(overview_pages) >= 2  # at least project-overview and readme

        arch_pages = manifest.pages_by_category(WikiTaxonomyCategory.ARCHITECTURE_DESIGN)
        assert len(arch_pages) >= 1

    def test_plan_has_module_pages(self, sample_identity, sample_snapshot):
        """Test plan includes module pages."""
        planner = RuleFirstPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        core_pages = manifest.pages_by_category(WikiTaxonomyCategory.CORE_SERVICES)
        assert len(core_pages) >= len(sample_snapshot.modules)

    def test_plan_has_api_pages(self, sample_identity, sample_snapshot):
        """Test plan includes API reference pages."""
        planner = RuleFirstPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        api_pages = manifest.pages_by_category(WikiTaxonomyCategory.API_REFERENCE)
        assert len(api_pages) > 0

    def test_plan_uses_rule_first_mode(self, sample_identity, sample_snapshot):
        """Test all pages use RULE_FIRST generation mode."""
        planner = RuleFirstPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        for page in manifest.pages:
            assert page.generation_mode == GenerationMode.RULE_FIRST

    def test_page_ids_are_unique(self, sample_identity, sample_snapshot):
        """Test all page IDs are unique."""
        planner = RuleFirstPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        page_ids = [p.page_id for p in manifest.pages]
        assert len(page_ids) == len(set(page_ids))

    def test_page_ids_are_stable(self, sample_identity, sample_snapshot):
        """Test page IDs are stable across multiple generations."""
        planner1 = RuleFirstPlanner(sample_identity, sample_snapshot)
        manifest1 = planner1.generate()

        planner2 = RuleFirstPlanner(sample_identity, sample_snapshot)
        manifest2 = planner2.generate()

        ids1 = sorted([p.page_id for p in manifest1.pages])
        ids2 = sorted([p.page_id for p in manifest2.pages])
        assert ids1 == ids2

    def test_navigation_tree_exists(self, sample_identity, sample_snapshot):
        """Test navigation tree is generated."""
        planner = RuleFirstPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        assert len(manifest.navigation_tree) > 0
        # Should have category nodes
        category_nodes = [n for n in manifest.navigation_tree if n.node_type == "category"]
        assert len(category_nodes) > 0

    def test_parent_child_relationships(self, sample_identity, sample_snapshot):
        """Test parent-child page relationships."""
        planner = RuleFirstPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        # Find a page with children
        parent_page = None
        for page in manifest.pages:
            children = manifest.children_of(page.page_id)
            if children:
                parent_page = page
                break

        if parent_page:
            assert parent_page.parent is None or manifest.page_by_id(parent_page.parent) is not None

    def test_ai_api_atlas_eighty_pages(self, sample_identity, sample_snapshot):
        """Test AI_API_Atlas rule-only plan has at least 80 pages."""
        planner = RuleFirstPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        # AI_API_Atlas should have substantial documentation
        # With 3 modules, 3 endpoints, 3 data models, should generate 80+ pages
        assert (
            manifest.page_count() >= 80
        ), f"Expected at least 80 pages, got {manifest.page_count()}"


class TestPlanPagesFromSnapshot:
    """Tests for plan_pages_from_snapshot function."""

    def test_plan_from_snapshot(self):
        """Test planning from snapshot."""
        identity = RepositoryIdentity(
            name="test-repo",
            display_name="Test Repository",
            root_path="/test",
        )

        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(
                name="test-repo",
                root_path="/test",
            ),
            modules=[],
            endpoints=[],
            data_models=[],
        )

        manifest = plan_pages_from_snapshot(identity, snapshot)
        assert manifest.page_count() >= 10  # At least overview + some index pages


class TestPageStructure:
    """Tests for page structure and relationships."""

    def test_pages_have_output_paths(self):
        """Test all pages have valid output paths."""
        identity = RepositoryIdentity(name="test", display_name="Test", root_path="/test")
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(name="test", root_path="/test"),
            modules=[],
            endpoints=[],
            data_models=[],
        )

        planner = RuleFirstPlanner(identity, snapshot)
        manifest = planner.generate()

        for page in manifest.pages:
            assert page.output_path.startswith("docs/")
            assert page.output_path.endswith(".md")

    def test_pages_have_categories(self):
        """Test all pages have valid categories."""
        identity = RepositoryIdentity(name="test", display_name="Test", root_path="/test")
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(name="test", root_path="/test"),
            modules=[],
            endpoints=[],
            data_models=[],
        )

        planner = RuleFirstPlanner(identity, snapshot)
        manifest = planner.generate()

        for page in manifest.pages:
            assert isinstance(page.category, WikiTaxonomyCategory)
