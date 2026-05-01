"""Tests for static repo-wiki viewer with tree navigation and Mermaid rendering."""

import pytest

from repo_wiki.viewer.static_viewer import (
    build_nav_tree_from_manifest,
    build_toc_html,
    build_tree_html,
    build_viewer_html,
    create_viewer_for_directory,
    extract_headings,
    get_label_from_path,
    get_mermaid_script,
    get_nav_type_from_path,
    inject_anchors,
    inject_mermaid_support,
    make_anchor,
    render_mermaid_safely,
)


class TestExtractHeadings:
    """Tests for heading extraction from markdown."""

    def test_extracts_single_h1(self):
        content = "# Main Title"
        headings = extract_headings(content)
        assert len(headings) == 1
        assert headings[0]["level"] == 1
        assert headings[0]["text"] == "Main Title"
        assert headings[0]["anchor"] == "main-title"

    def test_extracts_multiple_headings(self):
        content = """# Main Title
## Section One
### Subsection
## Section Two
"""
        headings = extract_headings(content)
        assert len(headings) == 4
        assert headings[0]["level"] == 1
        assert headings[1]["level"] == 2
        assert headings[2]["level"] == 3

    def test_handles_empty_content(self):
        headings = extract_headings("")
        assert len(headings) == 0

    def test_handles_no_headings(self):
        content = "Just some plain text without any headings."
        headings = extract_headings(content)
        assert len(headings) == 0


class TestMakeAnchor:
    """Tests for anchor generation."""

    def test_lowercase(self):
        anchor = make_anchor("Hello World")
        assert anchor == "hello-world"

    def test_removes_special_chars(self):
        anchor = make_anchor("API (v2) Endpoints!")
        assert anchor == "api-v2-endpoints"

    def test_collapse_hyphens(self):
        anchor = make_anchor("module --- repository")
        assert anchor == "module-repository"

    def test_trim_hyphens(self):
        anchor = make_anchor("  Leading and trailing  ")
        assert anchor == "leading-and-trailing"


class TestInjectAnchors:
    """Tests for anchor injection into headings."""

    def test_injects_anchor_into_h1(self):
        content = "# Main Title"
        result = inject_anchors(content)
        assert '<span id="main-title">Main Title</span>' in result

    def test_injects_anchor_into_h2(self):
        content = "## Section Title"
        result = inject_anchors(content)
        assert '<span id="section-title">Section Title</span>' in result

    def test_preserves_heading_level(self):
        content = "### Deep Subsection"
        result = inject_anchors(content)
        assert result.startswith("### ")


class TestBuildTocHtml:
    """Tests for TOC HTML generation."""

    def test_empty_toc(self):
        html = build_toc_html([])
        assert html == ""

    def test_single_item_toc(self):
        headings = [{"level": 2, "text": "Section", "anchor": "section"}]
        html = build_toc_html(headings)
        assert '<div class="toc-title">Table of Contents</div>' in html
        assert 'href="#section"' in html

    def test_respects_min_level(self):
        headings = [
            {"level": 1, "text": "Title", "anchor": "title"},
            {"level": 2, "text": "Section", "anchor": "section"},
        ]
        html = build_toc_html(headings, min_level=2)
        assert 'href="#section"' in html
        # h1 should be excluded due to min_level=2
        assert "title" not in html or "Title" not in html.split("Table of Contents")[1]

    def test_nested_levels_indented(self):
        headings = [
            {"level": 2, "text": "Section", "anchor": "section"},
            {"level": 3, "text": "Subsection", "anchor": "subsection"},
        ]
        html = build_toc_html(headings, min_level=2)
        assert "margin-left" in html


class TestRenderMermaidSafely:
    """Tests for Mermaid block rendering."""

    def test_replaces_mermaid_block(self):
        content = """Some text
```mermaid
graph TD
    A --> B
```
More text
"""
        result = render_mermaid_safely(content)
        assert '<div class="mermaid">' in result
        assert "graph TD" in result
        assert "```mermaid" not in result

    def test_handles_multiple_mermaid_blocks(self):
        content = """```mermaid
graph A
```
Text
```mermaid
graph B
```
"""
        result = render_mermaid_safely(content)
        assert result.count('<div class="mermaid">') == 2

    def test_no_mermaid_blocks_unchanged(self):
        content = "Just regular markdown content"
        result = render_mermaid_safely(content)
        assert result == content

    def test_preserves_diagram_content(self):
        content = """```mermaid
sequenceDiagram
    Alice->>Bob: Hello
```
"""
        result = render_mermaid_safely(content)
        assert "sequenceDiagram" in result
        assert "Alice" in result


class TestInjectMermaidSupport:
    """Tests for Mermaid script injection."""

    def test_injects_when_mermaid_present(self):
        html = '<div class="mermaid">diagram</div>'
        result = inject_mermaid_support(html)
        assert "mermaid@10" in result
        assert "mermaid.initialize" in result

    def test_no_injection_without_mermaid(self):
        html = "<p>No diagrams here</p>"
        result = inject_mermaid_support(html)
        assert result == html

    def test_injects_before_head_close(self):
        html = "<html><head></head><body><div class='mermaid'></div></body></html>"
        result = inject_mermaid_support(html)
        assert "mermaid@10" in result


class TestGetNavTypeFromPath:
    """Tests for navigation type detection from paths."""

    def test_overview_type(self):
        assert get_nav_type_from_path("docs/00-overview.md") == "overview"
        assert get_nav_type_from_path("docs/01-architecture.md") == "overview"

    def test_section_type(self):
        assert get_nav_type_from_path("docs/sections/architecture/index.md") == "section"
        assert get_nav_type_from_path("docs/sections/api/index.md") == "section"

    def test_module_type(self):
        assert get_nav_type_from_path("docs/modules/repo_wiki.md") == "module"

    def test_phase_type(self):
        assert get_nav_type_from_path("docs/phases/phase-01-setup.md") == "phase"

    def test_unknown_type(self):
        assert get_nav_type_from_path("README.md") == "other"


class TestGetLabelFromPath:
    """Tests for label extraction from paths."""

    def test_overview_label(self):
        label = get_label_from_path("docs/00-overview.md")
        assert label == "Overview"

    def test_architecture_label(self):
        label = get_label_from_path("docs/01-architecture.md")
        assert label == "Architecture"

    def test_section_label(self):
        label = get_label_from_path("docs/sections/architecture/index.md")
        assert label == "Architecture"

    def test_module_label(self):
        label = get_label_from_path("docs/modules/repo_wiki.md")
        assert label == "Repo Wiki"

    def test_phase_label(self):
        label = get_label_from_path("docs/phases/phase-01-setup.md")
        assert "Phase" in label and "Setup" in label


class TestBuildNavTreeFromManifest:
    """Tests for navigation tree building from manifest."""

    def test_empty_manifest(self):
        manifest = {}
        tree = build_nav_tree_from_manifest(manifest)
        assert tree == []

    def test_builds_tree_from_files(self):
        manifest = {
            "files": [
                {"path": "docs/00-overview.md"},
                {"path": "docs/sections/architecture/index.md"},
                {"path": "docs/modules/repo_wiki.md"},
            ]
        }
        tree = build_nav_tree_from_manifest(manifest)
        assert len(tree) == 3
        types = [n["type"] for n in tree]
        assert "overview" in types
        assert "section" in types
        assert "module" in types

    def test_sorted_by_type(self):
        manifest = {
            "files": [
                {"path": "docs/modules/repo_wiki.md"},
                {"path": "docs/00-overview.md"},
                {"path": "docs/sections/architecture/index.md"},
            ]
        }
        tree = build_nav_tree_from_manifest(manifest)
        assert tree[0]["type"] == "overview"
        assert tree[1]["type"] == "section"
        assert tree[2]["type"] == "module"


class TestBuildTreeHtml:
    """Tests for tree navigation HTML generation."""

    def test_empty_tree(self):
        html = build_tree_html([])
        assert html == ""

    def test_single_node(self):
        nodes = [{"label": "Overview", "path": "docs/00-overview.md", "type": "overview"}]
        html = build_tree_html(nodes)
        assert "Overview" in html
        assert "docs/00-overview.md" in html
        assert "tree-overview" in html

    def test_multiple_sections(self):
        nodes = [
            {"label": "Overview", "path": "docs/00-overview.md", "type": "overview"},
            {"label": "Architecture", "path": "docs/sections/architecture/index.md", "type": "section"},
        ]
        html = build_tree_html(nodes)
        assert "Overview" in html
        assert "Sections" in html
        assert "Architecture" in html

    def test_tree_icons(self):
        nodes = [
            {"label": "Overview", "path": "docs/00-overview.md", "type": "overview"},
        ]
        html = build_tree_html(nodes)
        assert "📋" in html


class TestBuildViewerHtml:
    """Tests for complete viewer HTML generation."""

    def test_basic_viewer(self):
        content = "# Hello World"
        html = build_viewer_html(content, title="Test Page")
        assert "<!DOCTYPE html>" in html
        assert "Hello World" in html
        assert "Test Page" in html

    def test_viewer_with_mermaid(self):
        content = """# Doc
```mermaid
graph TD
    A --> B
```
"""
        html = build_viewer_html(content, include_mermaid=True)
        assert '<div class="mermaid">' in html

    def test_viewer_without_mermaid(self):
        content = """# Doc
```mermaid
graph TD
```
"""
        html = build_viewer_html(content, include_mermaid=False)
        assert '<div class="mermaid">' not in html

    def test_viewer_with_nav_nodes(self):
        content = "# Content"
        nodes = [{"label": "Overview", "path": "docs/00-overview.md", "type": "overview"}]
        html = build_viewer_html(content, nav_nodes=nodes)
        assert "tree-nav" in html

    def test_viewer_with_toc(self):
        content = """# Title
## Section
### Subsection
"""
        headings = extract_headings(content)
        html = build_viewer_html(content, toc=headings)
        assert "toc" in html


class TestCreateViewerForDirectory:
    """Tests for viewer creation from directory."""

    def test_creates_empty_config_for_nonexistent_dir(self, tmp_path):
        result = create_viewer_for_directory(tmp_path)
        assert result["root_dir"] == str(tmp_path)
        assert result["nav_nodes"] == []


class TestMermaidOfflineSupport:
    """Tests for offline Mermaid configuration."""

    def test_get_mermaid_script_uses_cdn_by_default(self):
        """By default, Mermaid script points to CDN."""
        from repo_wiki.viewer.static_viewer import (
            get_mermaid_script,
            MERMAID_CDN_URL,
            MERMAID_LOCAL_PATH,
        )
        # Reset to default state
        import repo_wiki.viewer.static_viewer as viewer_module
        viewer_module.MERMAID_LOCAL_PATH = None
        script = get_mermaid_script()
        assert MERMAID_CDN_URL in script
        assert "mermaid.min.js" in script

    def test_get_mermaid_script_uses_local_when_configured(self):
        """When MERMAID_LOCAL_PATH is set, use local bundle."""
        import repo_wiki.viewer.static_viewer as viewer_module
        from repo_wiki.viewer.static_viewer import get_mermaid_script
        original = viewer_module.MERMAID_LOCAL_PATH
        try:
            viewer_module.MERMAID_LOCAL_PATH = "/local/path/mermaid.min.js"
            script = get_mermaid_script()
            assert "/local/path/mermaid.min.js" in script
            assert "cdn.jsdelivr" not in script
        finally:
            viewer_module.MERMAID_LOCAL_PATH = original

    def test_inject_mermaid_support_respects_local_path(self):
        """inject_mermaid_support uses current MERMAID_LOCAL_PATH setting."""
        import repo_wiki.viewer.static_viewer as viewer_module
        original = viewer_module.MERMAID_LOCAL_PATH
        try:
            viewer_module.MERMAID_LOCAL_PATH = "/offline/mermaid.min.js"
            html = '<div class="mermaid">diagram</div>'
            result = inject_mermaid_support(html)
            assert "/offline/mermaid.min.js" in result
        finally:
            viewer_module.MERMAID_LOCAL_PATH = original


class TestIntegration:
    """Integration tests for the viewer."""

    def test_full_page_render(self, tmp_path):
        """Test complete page rendering with TOC and Mermaid."""
        content = """# Main Document
## Architecture
### Components
```mermaid
graph TD
    A --> B
```
## Operations
"""
        headings = extract_headings(content)
        nav_nodes = [
            {"label": "Main", "path": "docs/00-overview.md", "type": "overview"},
            {"label": "Architecture", "path": "docs/sections/architecture/index.md", "type": "section"},
        ]

        html = build_viewer_html(
            content,
            title="Test Document",
            nav_nodes=nav_nodes,
            toc=headings,
            include_mermaid=True,
        )

        # Check structural elements
        assert "<!DOCTYPE html>" in html
        assert '<div class="toc-title">Table of Contents</div>' in html
        assert '<div class="mermaid">' in html
        assert "tree-nav" in html
        assert "Main" in html

    def test_heading_anchors_work(self):
        """Test that heading anchors are correctly generated and injected."""
        content = "## My Section Heading"
        processed = inject_anchors(content)
        anchor = make_anchor("My Section Heading")

        assert f'id="{anchor}"' in processed
        assert "My Section Heading" in processed

    def test_mermaid_blocks_are_safe(self):
        """Test that Mermaid blocks are properly wrapped for safe rendering."""
        content = """```mermaid
graph TD
    A["<script>alert('xss')</script>"] --> B
```
"""
        result = render_mermaid_safely(content)
        assert '<div class="mermaid">' in result
        # The content should be preserved as-is in the div
        assert "alert" in result
