"""Tests for planner persistence into SQLite and manifest."""

import json
from pathlib import Path

import pytest

from repo_wiki.planner.persistence import (
    _category_to_doc_type,
    _nav_node_to_dict,
    load_plan_from_sqlite,
    persist_plan,
)
from repo_wiki.planner.schema import (
    GenerationMode,
    NavNode,
    RepositoryIdentity,
    WikiPagePlan,
    WikiPlanManifest,
    WikiTaxonomyCategory,
)


class TestPersistPlan:
    """Tests for persist_plan function."""

    @pytest.fixture
    def sample_manifest(self):
        """Create a sample manifest for testing."""
        pages = [
            WikiPagePlan(
                page_id="project-overview",
                title="项目概述",
                category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
                parent=None,
                output_path="docs/pages/overview/project-overview.md",
                generation_mode=GenerationMode.RULE_FIRST,
                sort_order=0,
            ),
            WikiPagePlan(
                page_id="architecture",
                title="架构设计",
                category=WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
                parent=None,
                output_path="docs/pages/architecture/architecture.md",
                generation_mode=GenerationMode.RULE_FIRST,
                sort_order=0,
            ),
            WikiPagePlan(
                page_id="api-docs",
                title="API参考",
                category=WikiTaxonomyCategory.API_REFERENCE,
                parent="architecture",
                output_path="docs/pages/api/docs.md",
                generation_mode=GenerationMode.LLM_ASSISTED,
                sort_order=1,
            ),
        ]
        identity = RepositoryIdentity(
            name="test-repo",
            display_name="Test Repository",
            root_path="/test/repo",
            language="python",
            framework="fastapi",
        )
        nav_tree = [
            NavNode(
                node_id="cat-项目概述",
                label="项目概述",
                node_type="category",
                sort_order=0,
                children=[
                    NavNode(
                        node_id="page-project-overview",
                        label="项目概述",
                        node_type="page",
                        path="docs/pages/overview/project-overview.md",
                        sort_order=0,
                    )
                ],
            ),
        ]
        return WikiPlanManifest(
            version="1.0.0",
            profile="qoder-chinese",
            repository_identity=identity,
            pages=pages,
            navigation_tree=nav_tree,
        )

    def test_persist_writes_manifest(self, tmp_path: Path, sample_manifest):
        """Test that persist writes manifest.json."""
        result = persist_plan(tmp_path, sample_manifest)

        assert result["status"] == "ok"
        assert "run_id" in result
        assert "manifest_path" in result

        manifest_path = Path(result["manifest_path"])
        assert manifest_path.exists()

    def test_persist_creates_eval_dir(self, tmp_path: Path, sample_manifest):
        """Test that persist creates .repo-agent-eval directory."""
        result = persist_plan(tmp_path, sample_manifest)

        eval_dir = tmp_path / ".repo-agent-eval"
        assert eval_dir.exists()

    def test_persist_writes_sqlite(self, tmp_path: Path, sample_manifest):
        """Test that persist writes to SQLite runtime store."""
        result = persist_plan(tmp_path, sample_manifest)

        runtime_db = tmp_path / ".repo-wiki" / "index" / "runtime.sqlite3"
        assert runtime_db.exists()

    def test_manifest_contains_pages(self, tmp_path: Path, sample_manifest):
        """Test manifest.json contains all pages."""
        result = persist_plan(tmp_path, sample_manifest)

        manifest_path = Path(result["manifest_path"])
        data = json.loads(manifest_path.read_text(encoding="utf-8"))

        assert data["page_count"] == len(sample_manifest.pages)
        assert data["profile"] == "qoder-chinese"

    def test_manifest_contains_navigation_tree(self, tmp_path: Path, sample_manifest):
        """Test manifest.json contains navigation tree."""
        result = persist_plan(tmp_path, sample_manifest)

        manifest_path = Path(result["manifest_path"])
        data = json.loads(manifest_path.read_text(encoding="utf-8"))

        assert "navigation_tree" in data
        assert len(data["navigation_tree"]) > 0

    def test_persist_with_custom_run_id(self, tmp_path: Path, sample_manifest):
        """Test persist with custom run_id."""
        result = persist_plan(tmp_path, sample_manifest, run_id="custom-run-123")

        assert result["run_id"] == "custom-run-123"
        manifest_path = Path(result["manifest_path"])
        assert "custom-run-123" in str(manifest_path)

    def test_persist_returns_page_count(self, tmp_path: Path, sample_manifest):
        """Test persist returns correct page count."""
        result = persist_plan(tmp_path, sample_manifest)

        assert result["page_count"] == sample_manifest.page_count()


class TestNavNodeDictSerialization:
    """Tests for nav node to dict serialization."""

    def test_nav_node_to_dict(self):
        """Test converting nav node to dict."""
        node = NavNode(
            node_id="test-node",
            label="Test Node",
            node_type="page",
            path="docs/test.md",
            icon="file",
            sort_order=1,
            metadata={"key": "value"},
            children=[
                NavNode(
                    node_id="child-node",
                    label="Child",
                    node_type="page",
                    path="docs/child.md",
                )
            ],
        )

        result = _nav_node_to_dict([node])

        assert len(result) == 1
        assert result[0]["node_id"] == "test-node"
        assert result[0]["label"] == "Test Node"
        assert result[0]["node_type"] == "page"
        assert result[0]["path"] == "docs/test.md"
        assert result[0]["icon"] == "file"
        assert result[0]["sort_order"] == 1
        assert result[0]["metadata"] == {"key": "value"}
        assert len(result[0]["children"]) == 1

    def test_nav_node_to_dict_nested(self):
        """Test converting nested nav nodes to dict."""
        grandchild = NavNode(
            node_id="grandchild",
            label="Grandchild",
            node_type="page",
        )
        child = NavNode(
            node_id="child",
            label="Child",
            node_type="page",
            children=[grandchild],
        )
        parent = NavNode(
            node_id="parent",
            label="Parent",
            node_type="category",
            children=[child],
        )

        result = _nav_node_to_dict([parent])

        assert len(result) == 1
        assert result[0]["node_id"] == "parent"
        assert len(result[0]["children"]) == 1
        assert result[0]["children"][0]["node_id"] == "child"
        assert len(result[0]["children"][0]["children"]) == 1


class TestCategoryMapping:
    """Tests for category to doc type mapping."""

    def test_category_to_doc_type(self):
        """Test mapping categories to doc types."""
        assert _category_to_doc_type(WikiTaxonomyCategory.PROJECT_OVERVIEW) == "overview"
        assert _category_to_doc_type(WikiTaxonomyCategory.ARCHITECTURE_DESIGN) == "section"
        assert _category_to_doc_type(WikiTaxonomyCategory.CORE_SERVICES) == "module"
        assert _category_to_doc_type(WikiTaxonomyCategory.DATA_MODELS) == "data-model"
        assert _category_to_doc_type(WikiTaxonomyCategory.API_REFERENCE) == "api"
        assert _category_to_doc_type(WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS) == "ops"

    def test_unknown_category_maps_to_page(self):
        """Test unknown category defaults to page type."""
        # Should not raise, returns "page" as fallback
        from repo_wiki.planner.schema import WikiTaxonomyCategory

        # This test ensures the mapping doesn't crash on any category
        for cat in WikiTaxonomyCategory:
            result = _category_to_doc_type(cat)
            assert result in (
                "overview",
                "section",
                "module",
                "data-model",
                "api",
                "ops",
                "guide",
                "security",
                "troubleshooting",
                "page",
            )


class TestLoadPlanFromSQLite:
    """Tests for loading plan from SQLite."""

    def test_load_from_empty_store(self, tmp_path: Path):
        """Test loading from empty runtime store."""
        # Create minimal runtime store
        result = load_plan_from_sqlite(tmp_path)
        # Empty store returns None
        assert result is None

    def test_load_after_persist(self, tmp_path: Path):
        """Test loading plan after persisting."""
        pages = [
            WikiPagePlan(
                page_id="test-page",
                title="Test",
                category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
                output_path="docs/pages/test.md",
            )
        ]
        manifest = WikiPlanManifest(
            version="1.0.0",
            pages=pages,
        )

        # Persist first
        persist_plan(tmp_path, manifest)

        # Then load
        loaded = load_plan_from_sqlite(tmp_path)
        assert loaded is not None
        assert loaded.page_count() >= 1


class TestManifestCompatibility:
    """Tests for manifest compatibility with plugins."""

    def test_manifest_is_valid_json(self, tmp_path: Path):
        """Test manifest is valid JSON."""
        pages = [
            WikiPagePlan(
                page_id="test",
                title="Test",
                category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
                output_path="docs/test.md",
            )
        ]
        manifest = WikiPlanManifest(version="1.0.0", pages=pages)

        result = persist_plan(tmp_path, manifest)
        manifest_path = Path(result["manifest_path"])

        # Should be valid JSON
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_manifest_has_required_fields(self, tmp_path: Path):
        """Test manifest has required fields for plugins."""
        pages = [
            WikiPagePlan(
                page_id="test",
                title="Test",
                category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
                output_path="docs/test.md",
            )
        ]
        identity = RepositoryIdentity(
            name="test-repo",
            display_name="Test",
            root_path="/test",
        )
        manifest = WikiPlanManifest(
            version="1.0.0",
            repository_identity=identity,
            pages=pages,
        )

        result = persist_plan(tmp_path, manifest)
        manifest_path = Path(result["manifest_path"])
        data = json.loads(manifest_path.read_text(encoding="utf-8"))

        # Required fields for plugin compatibility
        assert "version" in data
        assert "run_id" in data
        assert "page_count" in data
        assert "navigation_tree" in data
        assert "pages" in data

    def test_manifest_pages_have_required_fields(self, tmp_path: Path):
        """Test manifest pages have required fields."""
        pages = [
            WikiPagePlan(
                page_id="test-page",
                title="Test Page",
                category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
                output_path="docs/pages/test.md",
                parent=None,
            )
        ]
        manifest = WikiPlanManifest(version="1.0.0", pages=pages)

        result = persist_plan(tmp_path, manifest)
        manifest_path = Path(result["manifest_path"])
        data = json.loads(manifest_path.read_text(encoding="utf-8"))

        for page in data["pages"]:
            assert "page_id" in page
            assert "title" in page
            assert "category" in page
            assert "output_path" in page
            assert "generation_mode" in page
