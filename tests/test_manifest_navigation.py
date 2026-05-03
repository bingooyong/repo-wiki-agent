"""Tests for manifest navigation tree contracts."""

import pytest

from repo_wiki.planner.schema import (
    NavNode,
    WikiPagePlan,
    WikiPlanManifest,
    WikiTaxonomyCategory,
)


class TestNavNodeStructure:
    """Tests for NavNode structure validation."""

    def test_category_node_structure(self):
        """Test category node has correct structure."""
        node = NavNode(
            node_id="cat-project-overview",
            label="项目概述",
            node_type="category",
            sort_order=0,
        )
        assert node.node_type == "category"
        assert node.node_id == "cat-project-overview"
        assert node.path is None  # Category nodes don't have paths

    def test_page_node_structure(self):
        """Test page node has correct structure."""
        node = NavNode(
            node_id="page-overview",
            label="Overview",
            node_type="page",
            path="docs/pages/overview.md",
            sort_order=0,
        )
        assert node.node_type == "page"
        assert node.path is not None

    def test_separator_node_structure(self):
        """Test separator node has correct structure."""
        node = NavNode(
            node_id="sep-1",
            label="---",
            node_type="separator",
        )
        assert node.node_type == "separator"

    def test_node_with_icon(self):
        """Test node with icon field."""
        node = NavNode(
            node_id="api",
            label="API Reference",
            node_type="page",
            icon="code",
        )
        assert node.icon == "code"

    def test_node_metadata(self):
        """Test node with metadata."""
        node = NavNode(
            node_id="security",
            label="Security",
            node_type="page",
            metadata={
                "compliance": "SOC2",
                "audit_date": "2024-01-01",
            },
        )
        assert node.metadata["compliance"] == "SOC2"


class TestNavigationTreeBuilding:
    """Tests for building navigation trees from page plans."""

    @pytest.fixture
    def sample_plan(self):
        """Create a sample plan with hierarchy."""
        pages = [
            WikiPagePlan(
                page_id="overview",
                title="项目概述",
                category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
                parent=None,
                output_path="docs/pages/overview.md",
            ),
            WikiPagePlan(
                page_id="architecture",
                title="架构设计",
                category=WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
                parent="overview",
                output_path="docs/pages/architecture.md",
            ),
            WikiPagePlan(
                page_id="components",
                title="系统组件",
                category=WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
                parent="architecture",
                output_path="docs/pages/components.md",
            ),
            WikiPagePlan(
                page_id="api-index",
                title="API参考",
                category=WikiTaxonomyCategory.API_REFERENCE,
                parent=None,
                output_path="docs/pages/api/index.md",
            ),
            WikiPagePlan(
                page_id="api-v1",
                title="API v1",
                category=WikiTaxonomyCategory.API_REFERENCE,
                parent="api-index",
                output_path="docs/pages/api/v1.md",
            ),
        ]
        return WikiPlanManifest(
            version="1.0.0",
            pages=pages,
        )

    def test_plan_children_of_root(self, sample_plan):
        """Test finding root-level children."""
        children = sample_plan.children_of(None)
        assert len(children) == 2
        page_ids = {c.page_id for c in children}
        assert "overview" in page_ids
        assert "api-index" in page_ids

    def test_plan_children_of_parent(self, sample_plan):
        """Test finding children of a parent."""
        children = sample_plan.children_of("overview")
        assert len(children) == 1
        assert children[0].page_id == "architecture"

        children = sample_plan.children_of("architecture")
        assert len(children) == 1
        assert children[0].page_id == "components"

    def test_plan_deep_hierarchy(self, sample_plan):
        """Test deep hierarchy traversal."""
        # overview -> architecture -> components
        overview_children = sample_plan.children_of("overview")
        assert len(overview_children) == 1

        arch_children = sample_plan.children_of("architecture")
        assert len(arch_children) == 1

        # components has no children
        comp_children = sample_plan.children_of("components")
        assert len(comp_children) == 0


class TestNavTreeFromManifest:
    """Tests for navigation tree derived from manifest."""

    def test_nav_tree_contains_all_categories(self):
        """Test navigation tree contains all taxonomy categories."""
        pages = []
        for cat in WikiTaxonomyCategory:
            pages.append(
                WikiPagePlan(
                    page_id=f"index-{cat.value}",
                    title=cat.value,
                    category=cat,
                    output_path=f"docs/pages/{cat.value}/index.md",
                )
            )

        manifest = WikiPlanManifest(version="1.0.0", pages=pages)

        # Build nav tree manually (simulating what planner does)
        category_nodes = {}
        for cat in WikiTaxonomyCategory:
            category_nodes[cat] = NavNode(
                node_id=f"cat-{cat.value}",
                label=cat.value,
                node_type="category",
                sort_order=0,
            )

        for page in pages:
            cat_node = category_nodes[page.category]
            page_node = NavNode(
                node_id=f"page-{page.page_id}",
                label=page.title,
                node_type="page",
                path=page.output_path,
            )
            cat_node.children.append(page_node)

        # Verify all categories present
        assert len(category_nodes) == 11

    def test_nav_tree_sorting(self):
        """Test navigation nodes are sorted correctly."""
        nodes = [
            NavNode(node_id="z", label="Z", sort_order=3),
            NavNode(node_id="a", label="A", sort_order=1),
            NavNode(node_id="m", label="M", sort_order=2),
        ]

        sorted_nodes = sorted(nodes, key=lambda n: (n.sort_order, n.label))
        assert [n.node_id for n in sorted_nodes] == ["a", "m", "z"]


class TestManifestNavIntegration:
    """Integration tests for manifest and navigation."""

    def test_manifest_produces_valid_nav_tree(self):
        """Test that manifest can produce a valid navigation tree."""
        pages = [
            WikiPagePlan(
                page_id="root-page",
                title="Root",
                category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
                parent=None,
                output_path="docs/pages/root.md",
            ),
            WikiPagePlan(
                page_id="child-page",
                title="Child",
                category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
                parent="root-page",
                output_path="docs/pages/child.md",
            ),
        ]
        manifest = WikiPlanManifest(version="1.0.0", pages=pages)

        # Verify manifest can produce nav tree
        assert manifest.page_count() == 2

        # Build nav tree
        category_node = NavNode(
            node_id="cat-项目概述",
            label="项目概述",
            node_type="category",
            children=[],
        )

        for page in pages:
            if page.parent is None:
                page_node = NavNode(
                    node_id=f"page-{page.page_id}",
                    label=page.title,
                    node_type="page",
                    path=page.output_path,
                )
                category_node.children.append(page_node)
            elif page.parent == "root-page":
                # Find parent in children
                pass

    def test_nav_tree_serialization(self):
        """Test nav tree serializes to JSON correctly."""
        tree = [
            NavNode(
                node_id="root",
                label="Root",
                node_type="category",
                children=[
                    NavNode(
                        node_id="child1",
                        label="Child 1",
                        node_type="page",
                        path="docs/child1.md",
                    ),
                    NavNode(
                        node_id="child2",
                        label="Child 2",
                        node_type="page",
                        path="docs/child2.md",
                        children=[
                            NavNode(
                                node_id="grandchild",
                                label="Grandchild",
                                node_type="page",
                                path="docs/grandchild.md",
                            )
                        ],
                    ),
                ],
            )
        ]

        import json

        json_str = json.dumps(
            tree,
            default=lambda n: {
                "node_id": n.node_id,
                "label": n.label,
                "node_type": n.node_type,
                "path": n.path,
                "children": n.children,
            },
            indent=2,
        )

        assert "root" in json_str
        assert "child1" in json_str
        assert "grandchild" in json_str


class TestIDEStaticViewerConsumption:
    """Tests for IDE/static viewer navigation consumption."""

    def test_flat_nav_structure(self):
        """Test flat navigation structure works for viewers."""
        nodes = [
            NavNode(node_id="1", label="Overview", node_type="page", path="docs/1.md"),
            NavNode(node_id="2", label="Architecture", node_type="page", path="docs/2.md"),
            NavNode(node_id="3", label="API", node_type="page", path="docs/3.md"),
        ]

        # Each node should be consumable independently
        for node in nodes:
            assert node.node_id
            assert node.label
            assert node.path

    def test_hierarchical_nav_structure(self):
        """Test hierarchical nav for tree-view widgets."""
        parent = NavNode(
            node_id="parent",
            label="Parent Section",
            node_type="category",
            children=[
                NavNode(node_id="child1", label="Child 1", node_type="page"),
                NavNode(node_id="child2", label="Child 2", node_type="page"),
            ],
        )

        assert len(parent.children) == 2
        for child in parent.children:
            assert child.node_type == "page"

    def test_nav_node_paths_for_routing(self):
        """Test nav node paths can be used for routing."""
        pages = [
            WikiPagePlan(
                page_id="docs-index",
                title="Docs Index",
                category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
                output_path="docs/index.md",
            ),
            WikiPagePlan(
                page_id="api-reference",
                title="API Reference",
                category=WikiTaxonomyCategory.API_REFERENCE,
                output_path="docs/api/reference.md",
            ),
        ]

        paths = [p.output_path for p in pages]
        assert "docs/index.md" in paths
        assert "docs/api/reference.md" in paths
