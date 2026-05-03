"""Tests for wiki plan schema and navigation tree contracts."""

from repo_wiki.planner.schema import (
    DEFAULT_CHINESE_TAXONOMY,
    GenerationMode,
    NavNode,
    RepositoryIdentity,
    SourceRequirement,
    WikiPagePlan,
    WikiPlanManifest,
    WikiTaxonomyCategory,
    current_schema_version,
)


class TestWikiPagePlan:
    """Tests for WikiPagePlan model."""

    def test_create_page_plan(self):
        """Test creating a basic page plan."""
        page = WikiPagePlan(
            page_id="test-page",
            title="Test Page",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/pages/test-page.md",
        )
        assert page.page_id == "test-page"
        assert page.title == "Test Page"
        assert page.category == WikiTaxonomyCategory.PROJECT_OVERVIEW
        assert page.generation_mode == GenerationMode.RULE_FIRST
        assert page.parent is None

    def test_page_plan_with_source_requirements(self):
        """Test page plan with source requirements."""
        source = SourceRequirement(
            modules=["repo_wiki", "tests"],
            endpoints=["GET /users"],
            data_models=["UserModel"],
        )
        page = WikiPagePlan(
            page_id="api-docs",
            title="API文档",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="docs/pages/api/api-docs.md",
            source_requirements=source,
            generation_mode=GenerationMode.LLM_ASSISTED,
        )
        assert len(page.source_requirements.modules) == 2
        assert "GET /users" in page.source_requirements.endpoints

    def test_page_plan_sort_order(self):
        """Test page plan sort order."""
        page = WikiPagePlan(
            page_id="index",
            title="Index",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/pages/index.md",
            sort_order=5,
        )
        assert page.sort_order == 5


class TestWikiPlanManifest:
    """Tests for WikiPlanManifest model."""

    def test_create_empty_manifest(self):
        """Test creating an empty manifest."""
        manifest = WikiPlanManifest()
        assert manifest.version == "1.0.0"
        assert manifest.profile == "qoder-chinese"
        assert len(manifest.pages) == 0

    def test_add_pages_to_manifest(self):
        """Test adding pages to manifest."""
        manifest = WikiPlanManifest()
        page1 = WikiPagePlan(
            page_id="overview",
            title="Overview",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/pages/overview.md",
        )
        page2 = WikiPagePlan(
            page_id="architecture",
            title="Architecture",
            category=WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
            output_path="docs/pages/architecture.md",
            parent="overview",
        )
        manifest.pages.extend([page1, page2])

        assert manifest.page_count() == 2
        assert len(manifest.pages_by_category(WikiTaxonomyCategory.PROJECT_OVERVIEW)) == 1

    def test_find_page_by_id(self):
        """Test finding a page by ID."""
        manifest = WikiPlanManifest()
        page = WikiPagePlan(
            page_id="test-page",
            title="Test",
            category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
            output_path="docs/pages/test.md",
        )
        manifest.pages.append(page)

        found = manifest.page_by_id("test-page")
        assert found is not None
        assert found.page_id == "test-page"

        not_found = manifest.page_by_id("nonexistent")
        assert not_found is None

    def test_children_of_parent(self):
        """Test finding children of a parent page."""
        manifest = WikiPlanManifest()
        pages = [
            WikiPagePlan(
                page_id="parent",
                title="Parent",
                category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
                output_path="docs/pages/parent.md",
            ),
            WikiPagePlan(
                page_id="child1",
                title="Child 1",
                category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
                output_path="docs/pages/child1.md",
                parent="parent",
            ),
            WikiPagePlan(
                page_id="child2",
                title="Child 2",
                category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
                output_path="docs/pages/child2.md",
                parent="parent",
            ),
        ]
        manifest.pages.extend(pages)

        children = manifest.children_of("parent")
        assert len(children) == 2

        root_pages = manifest.children_of(None)
        assert len(root_pages) == 1


class TestNavNode:
    """Tests for NavNode model."""

    def test_create_nav_node(self):
        """Test creating a navigation node."""
        node = NavNode(
            node_id="overview",
            label="Overview",
            node_type="page",
            path="docs/pages/overview.md",
        )
        assert node.node_id == "overview"
        assert node.children == []

    def test_nav_node_with_children(self):
        """Test navigation node with children."""
        child = NavNode(
            node_id="child",
            label="Child Page",
            node_type="page",
            path="docs/pages/child.md",
            sort_order=1,
        )
        parent = NavNode(
            node_id="parent",
            label="Parent",
            node_type="category",
            children=[child],
        )
        assert len(parent.children) == 1
        assert parent.children[0].node_id == "child"

    def test_nav_node_metadata(self):
        """Test navigation node metadata."""
        node = NavNode(
            node_id="api",
            label="API",
            node_type="page",
            metadata={"version": "1.0", "deprecated": "false"},
        )
        assert node.metadata["version"] == "1.0"


class TestWikiTaxonomyCategory:
    """Tests for WikiTaxonomyCategory enum."""

    def test_all_categories_present(self):
        """Test all expected categories are present."""
        expected = [
            "项目概述",
            "架构设计",
            "核心服务",
            "Python服务",
            "前端应用",
            "数据模型",
            "API参考",
            "部署运维",
            "开发指南",
            "安全合规",
            "故障排除",
        ]
        actual = [cat.value for cat in WikiTaxonomyCategory]
        assert set(actual) == set(expected)

    def test_default_taxonomy(self):
        """Test default Chinese taxonomy."""
        assert len(DEFAULT_CHINESE_TAXONOMY) == 11


class TestRepositoryIdentity:
    """Tests for RepositoryIdentity model."""

    def test_create_identity(self):
        """Test creating a repository identity."""
        identity = RepositoryIdentity(
            name="repo-wiki",
            display_name="Repo Wiki",
            root_path="/path/to/repo",
        )
        assert identity.name == "repo-wiki"
        assert identity.language == "unknown"
        assert identity.framework == "unknown"

    def test_identity_with_metadata(self):
        """Test identity with full metadata."""
        identity = RepositoryIdentity(
            name="my-project",
            display_name="My Project",
            root_path="/path/to/project",
            language="python",
            framework="fastapi",
            package_manager="pip",
            version="1.0.0",
            description="A sample project",
            entry_points=["python -m myproject"],
        )
        assert identity.version == "1.0.0"
        assert identity.description == "A sample project"


class TestSourceRequirement:
    """Tests for SourceRequirement model."""

    def test_empty_requirement(self):
        """Test empty source requirement."""
        req = SourceRequirement()
        assert len(req.modules) == 0
        assert len(req.endpoints) == 0

    def test_requirement_with_data(self):
        """Test requirement with data."""
        req = SourceRequirement(
            modules=["module1", "module2"],
            endpoints=["GET /api/users"],
            data_models=["User", "Order"],
            commands=["npm run build"],
            files=["README.md", "LICENSE"],
        )
        assert len(req.modules) == 2
        assert len(req.endpoints) == 1


class TestGenerationMode:
    """Tests for GenerationMode enum."""

    def test_generation_modes(self):
        """Test generation mode values."""
        assert GenerationMode.RULE_FIRST.value == "rule-first"
        assert GenerationMode.LLM_ASSISTED.value == "llm-assisted"


def test_current_schema_version():
    """Test schema version function."""
    assert current_schema_version() == "1.0.0"
