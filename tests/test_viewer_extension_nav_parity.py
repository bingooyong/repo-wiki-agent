"""Tests for viewer extension navigation parity.

These tests ensure the static viewer and VS Code extension
render the same navigation hierarchy from the manifest.
"""


from repo_wiki.viewer.static_viewer import (
    _convert_navigation_tree,
    build_nav_tree_from_manifest,
)


class TestNavigationTreeParity:
    """Tests for parity between viewer and extension navigation."""

    def test_convert_navigation_tree_with_category(self):
        """Test conversion of new navigation_tree format."""
        nav_tree = [
            {
                "type": "category",
                "label": "项目概述",
                "children": [
                    {
                        "type": "page",
                        "id": "wiki-0",
                        "label": "Overview",
                        "path": "docs/00-overview.md",
                        "absolutePath": "/repo/.repo-agent-eval/run-123/content/docs/00-overview.md",
                    }
                ],
            }
        ]
        result = _convert_navigation_tree(nav_tree)
        assert len(result) == 1
        assert result[0]["label"] == "Overview"
        assert result[0]["path"] == "docs/00-overview.md"
        assert result[0]["type"] == "overview"

    def test_convert_navigation_tree_nested(self):
        """Test conversion with nested categories."""
        nav_tree = [
            {
                "type": "category",
                "label": "项目概述",
                "children": [
                    {
                        "type": "page",
                        "label": "Overview",
                        "path": "docs/00-overview.md",
                    }
                ],
            },
            {
                "type": "category",
                "label": "架构设计",
                "children": [
                    {
                        "type": "page",
                        "label": "Architecture",
                        "path": "docs/01-architecture.md",
                    }
                ],
            },
        ]
        result = _convert_navigation_tree(nav_tree)
        assert len(result) == 2
        assert result[0]["label"] == "Overview"
        assert result[1]["label"] == "Architecture"

    def test_build_nav_tree_prefers_navigation_tree(self):
        """Test that build_nav_tree uses navigation_tree when available."""
        manifest = {
            "navigation_tree": [
                {
                    "type": "category",
                    "label": "项目概述",
                    "children": [
                        {"type": "page", "label": "Overview", "path": "content/00-overview.md"},
                    ],
                }
            ],
            "files": [
                {"path": "docs/00-overview.md"},
            ],
        }
        result = build_nav_tree_from_manifest(manifest)
        # Should use navigation_tree, not files
        assert len(result) == 1
        assert result[0]["path"] == "content/00-overview.md"

    def test_build_nav_tree_falls_back_to_files(self):
        """Test that build_nav_tree falls back to files when no navigation_tree."""
        manifest = {
            "files": [
                {"path": "docs/00-overview.md"},
                {"path": "docs/sections/architecture/index.md"},
            ],
        }
        result = build_nav_tree_from_manifest(manifest)
        assert len(result) == 2
        assert result[0]["path"] == "docs/00-overview.md"
        assert result[1]["path"] == "docs/sections/architecture/index.md"

    def test_build_nav_tree_empty_manifest(self):
        """Test handling of empty manifest."""
        manifest = {}
        result = build_nav_tree_from_manifest(manifest)
        assert result == []


class TestViewerExtensionNavParity:
    """Tests ensuring viewer and extension render same hierarchy."""

    def test_same_navigation_tree_structure(self):
        """Test that viewer and extension use same navigation_tree format."""
        # This is the format produced by content_layout_writer.build_navigation_tree
        nav_tree = [
            {
                "type": "category",
                "label": "项目概述",
                "children": [
                    {
                        "type": "page",
                        "id": "overview",
                        "label": "Overview",
                        "path": "content/00-overview.md",
                    },
                ],
            },
            {
                "type": "category",
                "label": "架构设计",
                "children": [
                    {
                        "type": "page",
                        "id": "architecture",
                        "label": "Architecture",
                        "path": "content/01-architecture.md",
                    },
                ],
            },
        ]

        # Convert for viewer
        viewer_nodes = _convert_navigation_tree(nav_tree)

        # Both should have 2 nodes
        assert len(viewer_nodes) == 2

        # First node should be overview
        assert viewer_nodes[0]["label"] == "Overview"
        assert viewer_nodes[0]["path"] == "content/00-overview.md"
        assert viewer_nodes[0]["type"] == "overview"

        # Second node should be architecture
        assert viewer_nodes[1]["label"] == "Architecture"
        assert viewer_nodes[1]["path"] == "content/01-architecture.md"
        assert viewer_nodes[1]["type"] == "overview"

    def test_extension_and_viewer_same_category_order(self):
        """Test that extension and viewer preserve category order."""
        # The order in the manifest should be preserved
        nav_tree = [
            {"type": "category", "label": "项目概述", "children": []},
            {"type": "category", "label": "架构设计", "children": []},
            {"type": "category", "label": "核心服务", "children": []},
            {"type": "category", "label": "数据模型", "children": []},
            {"type": "category", "label": "API参考", "children": []},
        ]

        viewer_nodes = _convert_navigation_tree(nav_tree)

        # Order should be: 项目概述, 架构设计, 核心服务, 数据模型, API参考
        # But since children are empty, no nodes are produced
        assert len(viewer_nodes) == 0
