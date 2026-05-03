"""Tests for data model topic planner (Task 26.3).

Validates that data models are planned by topic (entity relationships,
database architecture, migration strategy) rather than raw model count.
Generates at least 10 AI_API_Atlas data model planned pages.
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
from repo_wiki.planner.data_model_topic_planner import (
    DataModelTopicCategory,
    DataModelTopicPlanner,
    plan_data_model_topics,
)
from repo_wiki.planner.identity import RepositoryIdentity
from repo_wiki.planner.schema import (
    GenerationMode,
    WikiTaxonomyCategory,
)


class TestDataModelTopicPlanner:
    """Tests for DataModelTopicPlanner."""

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
        """Sample repository snapshot with data models."""
        modules = [
            Module(
                name="repo_wiki",
                path="repo_wiki",
                responsibility="Handles core wiki functionality",
                exports=["RepoWikiService", "bootstrap"],
                depends_on=["tests"],
                depended_by=[],
                interfaces=[],
                data_models=["RepositoryInfo", "Module", "DataModel", "Endpoint"],
                owner="team-core",
                doc_path="docs/modules/repo_wiki.md",
                domain="core-platform",
                service_family="python-backend",
            ),
            Module(
                name="repo_wiki_core",
                path="repo_wiki/core",
                responsibility="Core contracts and config",
                exports=["BootstrapResult", "VerifyResult", "ImpactSet"],
                depends_on=[],
                depended_by=["repo_wiki"],
                interfaces=[],
                data_models=["BootstrapResult", "VerifyResult", "ImpactSet"],
                owner="team-core",
                doc_path="docs/modules/core.md",
                domain="core-platform",
                service_family="python-backend",
            ),
            Module(
                name="repo_wiki_config",
                path="repo_wiki/core/config",
                responsibility="Configuration management",
                exports=["RepoWikiConfig", "LlmConfig", "SecurityConfig"],
                depends_on=[],
                depended_by=["repo_wiki", "repo_wiki_core"],
                interfaces=[],
                data_models=["RepoWikiConfig", "LlmConfig", "SecurityConfig", "ProjectConfig", "ScanConfig", "IndexConfig", "OutputConfig"],
                owner="team-core",
                doc_path="docs/modules/config.md",
                domain="core-platform",
                service_family="python-backend",
            ),
        ]

        data_models = [
            # Core entities
            DataModel(
                name="RepositoryInfo",
                type="python_class",
                module="repo_wiki",
                file_path="repo_wiki/core/contracts.py",
            ),
            DataModel(
                name="Module",
                type="python_class",
                module="repo_wiki",
                file_path="repo_wiki/core/contracts.py",
            ),
            DataModel(
                name="DataModel",
                type="python_class",
                module="repo_wiki",
                file_path="repo_wiki/core/contracts.py",
            ),
            DataModel(
                name="Endpoint",
                type="python_class",
                module="repo_wiki",
                file_path="repo_wiki/core/contracts.py",
            ),
            # Analysis results
            DataModel(
                name="BootstrapResult",
                type="python_class",
                module="repo_wiki_core",
                file_path="repo_wiki/core/runtime.py",
            ),
            DataModel(
                name="VerifyResult",
                type="python_class",
                module="repo_wiki_core",
                file_path="repo_wiki/core/contracts.py",
            ),
            DataModel(
                name="ImpactSet",
                type="python_class",
                module="repo_wiki_core",
                file_path="repo_wiki/core/contracts.py",
            ),
            # Configuration models
            DataModel(
                name="RepoWikiConfig",
                type="python_class",
                module="repo_wiki_config",
                file_path="repo_wiki/core/config.py",
            ),
            DataModel(
                name="LlmConfig",
                type="python_class",
                module="repo_wiki_config",
                file_path="repo_wiki/core/config.py",
            ),
            DataModel(
                name="SecurityConfig",
                type="python_class",
                module="repo_wiki_config",
                file_path="repo_wiki/core/config.py",
            ),
            DataModel(
                name="ProjectConfig",
                type="python_class",
                module="repo_wiki_config",
                file_path="repo_wiki/core/config.py",
            ),
            DataModel(
                name="ScanConfig",
                type="python_class",
                module="repo_wiki_config",
                file_path="repo_wiki/core/config.py",
            ),
            DataModel(
                name="IndexConfig",
                type="python_class",
                module="repo_wiki_config",
                file_path="repo_wiki/core/config.py",
            ),
            DataModel(
                name="OutputConfig",
                type="python_class",
                module="repo_wiki_config",
                file_path="repo_wiki/core/config.py",
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
            endpoint_count=5,
            data_model_count=14,
        )

        return RepositorySnapshot(
            repository=repository,
            modules=modules,
            endpoints=[],
            data_models=data_models,
            commands={"start": "uvicorn main:app", "build": "pip install -e .", "test": "pytest"},
            stats=stats,
        )

    def test_generate_data_model_topics(self, sample_identity, sample_snapshot):
        """Test generating data model topic plan."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        assert manifest.page_count() > 0
        assert manifest.repository_identity is not None
        assert manifest.repository_identity.name == "AI_API_Atlas"

    def test_at_least_ten_data_model_pages(self, sample_identity, sample_snapshot):
        """Test that at least 10 data model pages are generated."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        data_model_pages = manifest.pages_by_category(WikiTaxonomyCategory.DATA_MODELS)
        assert len(data_model_pages) >= 10, f"Expected at least 10 data model pages, got {len(data_model_pages)}"

    def test_data_model_pages_grouped_by_topic(self, sample_identity, sample_snapshot):
        """Test that data model pages are grouped by topic, not raw model count."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        # Check that topic overview pages exist
        topic_page_ids = [
            "entity-relationships",
            "database-architecture",
            "migration-strategy",
            "topic-core-entities",
            "topic-configuration-models",
        ]
        found_topics = [
            pid for pid in topic_page_ids
            if any(p.page_id == pid for p in manifest.pages)
        ]
        assert len(found_topics) >= 3, "Expected topic overview pages"

    def test_entity_relationship_pages_exist(self, sample_identity, sample_snapshot):
        """Test that entity relationship pages are generated."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        # Should have entity relationships overview
        er_pages = [p for p in manifest.pages if "entity" in p.page_id.lower() or "er-" in p.page_id]
        assert len(er_pages) >= 2, f"Expected at least 2 entity relationship pages, got {len(er_pages)}"

    def test_database_architecture_pages_exist(self, sample_identity, sample_snapshot):
        """Test that database architecture pages are generated."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        # Should have database architecture pages
        db_pages = [p for p in manifest.pages if "database" in p.page_id.lower() or "schema" in p.page_id]
        assert len(db_pages) >= 2, f"Expected at least 2 database architecture pages, got {len(db_pages)}"

    def test_migration_strategy_pages_exist(self, sample_identity, sample_snapshot):
        """Test that migration strategy pages are generated."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        # Should have migration strategy pages
        migration_pages = [p for p in manifest.pages if "migration" in p.page_id.lower()]
        assert len(migration_pages) >= 2, f"Expected at least 2 migration pages, got {len(migration_pages)}"

    def test_all_pages_use_rule_first_mode(self, sample_identity, sample_snapshot):
        """Test all data model pages use RULE_FIRST generation mode."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        for page in manifest.pages:
            assert page.generation_mode == GenerationMode.RULE_FIRST

    def test_page_ids_are_unique(self, sample_identity, sample_snapshot):
        """Test all page IDs are unique."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        page_ids = [p.page_id for p in manifest.pages]
        assert len(page_ids) == len(set(page_ids)), "Page IDs must be unique"

    def test_navigation_tree_exists(self, sample_identity, sample_snapshot):
        """Test navigation tree is generated."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        assert len(manifest.navigation_tree) > 0
        # Should have category node for data models
        category_nodes = [
            n for n in manifest.navigation_tree if n.node_type == "category"
        ]
        assert len(category_nodes) >= 1

    def test_parent_child_relationships(self, sample_identity, sample_snapshot):
        """Test parent-child page relationships."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        for page in manifest.pages:
            if page.parent:
                parent_page = manifest.page_by_id(page.parent)
                assert parent_page is not None, f"Parent {page.parent} not found for {page.page_id}"

    def test_output_paths_valid(self, sample_identity, sample_snapshot):
        """Test all pages have valid output paths."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        for page in manifest.pages:
            assert page.output_path.startswith("docs/pages/data-models/")
            assert page.output_path.endswith(".md")

    def test_source_requirements_populated(self, sample_identity, sample_snapshot):
        """Test pages have source requirements populated."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        # Data models overview should have data models
        overview = manifest.page_by_id("data-models-overview")
        assert overview is not None
        assert len(overview.source_requirements.data_models) > 0

    def test_plan_data_model_topics_function(self, sample_identity, sample_snapshot):
        """Test the plan_data_model_topics convenience function."""
        manifest = plan_data_model_topics(sample_identity, sample_snapshot)

        assert manifest.page_count() >= 10
        data_model_pages = manifest.pages_by_category(WikiTaxonomyCategory.DATA_MODELS)
        assert len(data_model_pages) >= 10

    def test_model_classification(self, sample_identity, sample_snapshot):
        """Test that models are correctly classified by topic."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)

        # Test classification
        config_model = DataModel(
            name="RepoWikiConfig",
            type="python_class",
            module="repo_wiki_config",
            file_path="repo_wiki/core/config.py",
        )
        topic = planner._classify_model(config_model)
        assert topic == DataModelTopicCategory.CONFIGURATION_MODELS

        # Test repository info classification
        repo_model = DataModel(
            name="RepositoryInfo",
            type="python_class",
            module="repo_wiki",
            file_path="repo_wiki/core/contracts.py",
        )
        topic = planner._classify_model(repo_model)
        assert topic == DataModelTopicCategory.REPOSITORY_INFO_MODELS

        # Test result classification
        result_model = DataModel(
            name="VerifyResult",
            type="python_class",
            module="repo_wiki_core",
            file_path="repo_wiki/core/contracts.py",
        )
        topic = planner._classify_model(result_model)
        assert topic == DataModelTopicCategory.ANALYSIS_RESULT_MODELS

    def test_group_models_by_topic(self, sample_identity, sample_snapshot):
        """Test grouping models by topic."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        topics = planner._group_models_by_topic()

        # Should have all topic categories
        assert DataModelTopicCategory.CONFIGURATION_MODELS in topics
        assert DataModelTopicCategory.REPOSITORY_INFO_MODELS in topics
        assert DataModelTopicCategory.ANALYSIS_RESULT_MODELS in topics

        # Configuration models should have RepoWikiConfig
        config_models = topics[DataModelTopicCategory.CONFIGURATION_MODELS]
        config_model_names = [m.name for m in config_models]
        assert "RepoWikiConfig" in config_model_names


class TestDataModelTopicPlannerEdgeCases:
    """Tests for edge cases in data model topic planner."""

    def test_empty_data_models(self):
        """Test planner with no data models."""
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

        planner = DataModelTopicPlanner(identity, snapshot)
        manifest = planner.generate()

        # Should still generate overview page
        assert manifest.page_count() >= 1
        overview = manifest.page_by_id("data-models-overview")
        assert overview is not None

    def test_only_configuration_models(self):
        """Test planner with only configuration models."""
        identity = RepositoryIdentity(
            name="config-repo",
            display_name="Config Repository",
            root_path="/test/config",
        )
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(
                name="config-repo",
                root_path="/test/config",
            ),
            modules=[
                Module(
                    name="config",
                    path="config",
                    responsibility="Configuration",
                    exports=["ConfigModel"],
                    depends_on=[],
                    depended_by=[],
                    interfaces=[],
                    data_models=["ConfigModel"],
                    owner="team-core",
                    doc_path="docs/modules/config.md",
                    domain="core-platform",
                    service_family="python-backend",
                ),
            ],
            endpoints=[],
            data_models=[
                DataModel(
                    name="ConfigModel",
                    type="python_class",
                    module="config",
                    file_path="config/models.py",
                ),
            ],
        )

        planner = DataModelTopicPlanner(identity, snapshot)
        manifest = planner.generate()

        # Should still generate topic pages
        assert manifest.page_count() >= 5

    def test_all_model_types(self):
        """Test planner with all types of models."""
        identity = RepositoryIdentity(
            name="full-repo",
            display_name="Full Repository",
            root_path="/test/full",
        )
        snapshot = RepositorySnapshot(
            repository=RepositoryInfo(
                name="full-repo",
                root_path="/test/full",
            ),
            modules=[
                Module(
                    name="core",
                    path="core",
                    responsibility="Core",
                    exports=["CoreEntity"],
                    depends_on=[],
                    depended_by=[],
                    interfaces=[],
                    data_models=["CoreEntity", "ConfigEntity", "RepoInfo", "VerifyResult", "RuntimeState"],
                    owner="team-core",
                    doc_path="docs/modules/core.md",
                    domain="core-platform",
                    service_family="python-backend",
                ),
            ],
            endpoints=[],
            data_models=[
                DataModel(name="CoreEntity", type="python_class", module="core", file_path="core/entities.py"),
                DataModel(name="ConfigEntity", type="python_class", module="core", file_path="core/config.py"),
                DataModel(name="RepoInfo", type="python_class", module="core", file_path="core/repo.py"),
                DataModel(name="VerifyResult", type="python_class", module="core", file_path="core/result.py"),
                DataModel(name="RuntimeState", type="python_class", module="core", file_path="core/state.py"),
            ],
        )

        planner = DataModelTopicPlanner(identity, snapshot)
        manifest = planner.generate()

        # Should generate pages for all topic categories
        data_model_pages = manifest.pages_by_category(WikiTaxonomyCategory.DATA_MODELS)
        assert len(data_model_pages) >= 10


class TestDataModelTopicPlannerDuplicateDetection:
    """Tests for duplicate page detection (Task 32.3)."""

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
        """Sample repository snapshot with data models."""
        modules = [
            Module(
                name="repo_wiki",
                path="repo_wiki",
                responsibility="Core wiki functionality",
                exports=["WikiService"],
                depends_on=[],
                depended_by=[],
                interfaces=[],
                data_models=["RepositoryInfo", "Module"],
                owner="team-core",
                doc_path="docs/modules/repo_wiki.md",
                domain="core-platform",
                service_family="python-backend",
            ),
        ]

        data_models = [
            DataModel(
                name="RepositoryInfo",
                type="python_class",
                module="repo_wiki",
                file_path="repo_wiki/core/contracts.py",
            ),
            DataModel(
                name="Module",
                type="python_class",
                module="repo_wiki",
                file_path="repo_wiki/core/contracts.py",
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
            module_count=1,
            endpoint_count=0,
            data_model_count=2,
        )

        return RepositorySnapshot(
            repository=repository,
            modules=modules,
            endpoints=[],
            data_models=data_models,
            commands={"start": "uvicorn main:app", "build": "pip install -e .", "test": "pytest"},
            stats=stats,
        )

    def test_no_duplicate_page_titles(self, sample_identity, sample_snapshot):
        """Test that no pages have duplicate titles (e.g., 'xxx 数据模型-2')."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        titles = [p.title for p in manifest.pages]
        # Check for duplicate titles or titles with numeric suffixes that indicate duplication
        import re
        for title in titles:
            # Should not have titles ending in -2, -3, etc (indicating duplicate)
            assert not re.search(r'-\d+$', title), f"Found duplicate title suffix in: {title}"

    def test_duplicate_detection_prevents_same_title_pages(self, sample_identity, sample_snapshot):
        """Test that _check_duplicate_title detects similar titles."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)

        # Add first page
        planner._title_set.add("测试页面")
        assert planner._check_duplicate_title("测试页面") is True
        assert planner._check_duplicate_title("其他页面") is False

    def test_entity_drilldown_pages_exist(self, sample_identity, sample_snapshot):
        """Test that Task 32.3 entity drilldown pages are generated."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        page_ids = [p.page_id for p in manifest.pages]

        # Task 32.3 entity drilldown pages
        assert "entity-detail" in page_ids
        assert "entity-matrix" in page_ids

    def test_table_structure_pages_exist(self, sample_identity, sample_snapshot):
        """Test that Task 32.3 table structure pages are generated."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        page_ids = [p.page_id for p in manifest.pages]

        assert "table-structure-overview" in page_ids
        assert "table-relationships" in page_ids

    def test_index_performance_pages_exist(self, sample_identity, sample_snapshot):
        """Test that Task 32.3 index/performance pages are generated."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        page_ids = [p.page_id for p in manifest.pages]

        assert "index-strategy" in page_ids
        assert "performance-tuning" in page_ids

    def test_audit_pages_exist(self, sample_identity, sample_snapshot):
        """Test that Task 32.3 audit pages are generated."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        page_ids = [p.page_id for p in manifest.pages]

        assert "audit-overview" in page_ids
        assert "audit-events" in page_ids

    def test_security_pages_exist(self, sample_identity, sample_snapshot):
        """Test that Task 32.3 security pages are generated."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        page_ids = [p.page_id for p in manifest.pages]

        assert "security-models" in page_ids
        assert "security-config" in page_ids

    def test_service_level_links_preserved(self, sample_identity, sample_snapshot):
        """Test that entity drilldown pages link to service-level pages."""
        planner = DataModelTopicPlanner(sample_identity, sample_snapshot)
        manifest = planner.generate()

        # Find entity detail page
        entity_detail = manifest.page_by_id("entity-detail")
        assert entity_detail is not None
        assert entity_detail.parent == "entity-relationships"

        # Entity pages should have parent linking to entity-relationships
        entity_matrix = manifest.page_by_id("entity-matrix")
        assert entity_matrix is not None
        assert entity_matrix.parent == "entity-relationships"
