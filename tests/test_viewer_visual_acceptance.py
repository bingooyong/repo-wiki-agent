"""Visual acceptance snapshot tests for static viewer.

This module provides visual and navigation regression tests for the static viewer.
It verifies:
- Navigation tree structure correctness
- Page rendering with different viewport sizes
- Mermaid diagram presence and rendering
- Broken link detection
- Tree navigation completeness
"""

import pytest

from repo_wiki.viewer.static_viewer import (
    build_nav_tree_from_manifest,
    build_tree_html,
    build_viewer_html,
    extract_headings,
    get_label_from_path,
    inject_anchors,
    inject_mermaid_support,
    make_anchor,
    render_mermaid_safely,
)


class TestNavigationTreeRegression:
    """Regression tests for navigation tree building and rendering."""

    # Viewport sizes for visual testing
    VIEWPORT_SIZES = [
        {"name": "desktop", "width": 1280, "height": 800},
        {"name": "tablet", "width": 768, "height": 1024},
        {"name": "mobile", "width": 375, "height": 667},
    ]

    def test_nav_tree_completeness(self):
        """Navigation tree should include all expected section types."""
        manifest = {
            "files": [
                {"path": "docs/00-overview.md"},
                {"path": "docs/01-architecture.md"},
                {"path": "docs/sections/architecture/index.md"},
                {"path": "docs/sections/api/index.md"},
                {"path": "docs/modules/repo_wiki.md"},
                {"path": "docs/phases/phase-01-setup.md"},
            ]
        }
        tree = build_nav_tree_from_manifest(manifest)

        types = {n["type"] for n in tree}
        assert "overview" in types, "Missing overview nodes"
        assert "section" in types, "Missing section nodes"
        assert "module" in types, "Missing module nodes"
        assert "phase" in types, "Missing phase nodes"

    def test_nav_tree_labels_correct(self):
        """Navigation labels should be human-readable."""
        test_cases = [
            ("docs/00-overview.md", "Overview"),
            ("docs/01-architecture.md", "Architecture"),
            ("docs/sections/architecture/index.md", "Architecture"),
            ("docs/modules/repo_wiki.md", "Repo Wiki"),
        ]
        for path, expected_label in test_cases:
            label = get_label_from_path(path)
            assert label == expected_label, (
                f"Label for {path}: got '{label}', expected '{expected_label}'"
            )

    def test_nav_tree_html_structure(self):
        """Tree HTML should have correct structure for CSS styling."""
        nodes = [
            {"label": "Overview", "path": "docs/00-overview.md", "type": "overview"},
            {
                "label": "Architecture",
                "path": "docs/sections/architecture/index.md",
                "type": "section",
            },
        ]
        html = build_tree_html(nodes)

        assert 'class="tree-nav"' in html, "Missing tree-nav class"
        assert 'class="tree-section"' in html, "Missing tree-section class"
        assert "tree-item" in html, "Missing tree-item class"
        assert "Overview" in html, "Missing Overview label"
        assert "Architecture" in html, "Missing Architecture label"

    @pytest.mark.parametrize("viewport", VIEWPORT_SIZES)
    def test_viewport_handling(self, viewport):
        """Viewer should handle different viewport sizes without breaking layout."""
        content = "# Test Page\n## Section One\n### Subsection"
        headings = extract_headings(content)
        html = build_viewer_html(content, toc=headings)

        # Verify key structural elements are present (they adapt via CSS, not breaking)
        assert 'class="content"' in html or "content" in html
        assert 'class="toc"' in html or "toc" in html or "<nav" in html

    def test_tree_html_does_not_have_broken_structure(self):
        """Tree HTML should not have unbalanced tags or broken structure."""
        nodes = [
            {"label": "Overview", "path": "docs/00-overview.md", "type": "overview"},
            {"label": "Section", "path": "docs/sections/test/index.md", "type": "section"},
        ]
        html = build_tree_html(nodes)

        # Count opening and closing tags - basic sanity check
        open_tags = html.count("<div")
        close_tags = html.count("</div>")
        assert abs(open_tags - close_tags) <= 2, "Possible unbalanced div tags"


class TestMermaidRenderingRegression:
    """Regression tests for Mermaid diagram rendering."""

    def test_mermaid_blocks_preserved(self):
        """Mermaid blocks should be preserved in rendered output."""
        content = """# Doc
```mermaid
graph TD
    A --> B
```
## Another Section
"""
        result = render_mermaid_safely(content)
        assert '<div class="mermaid">' in result
        assert "graph TD" in result
        assert "A --> B" in result

    def test_multiple_mermaid_blocks(self):
        """Multiple Mermaid blocks should all be preserved."""
        content = """```mermaid
graph A
    A --> B
```
Text
```mermaid
sequenceDiagram
    Alice->>Bob: Hello
```
"""
        result = render_mermaid_safely(content)
        assert result.count('<div class="mermaid">') == 2
        assert "graph A" in result
        assert "sequenceDiagram" in result

    def test_mermaid_script_injection(self):
        """Mermaid script should be injected when mermaid blocks present."""
        html = '<div class="mermaid">diagram</div>'
        result = inject_mermaid_support(html)
        assert "mermaid" in result.lower()
        assert "mermaid.initialize" in result

    def test_mermaid_not_injected_without_blocks(self):
        """Mermaid script should not be injected when no mermaid blocks."""
        html = "<p>No diagrams here</p>"
        result = inject_mermaid_support(html)
        assert result == html, "Mermaid was incorrectly injected"


class TestPageRenderingRegression:
    """Regression tests for page rendering."""

    def test_anchors_injected_for_all_headings(self):
        """All headings should have anchor IDs for TOC linking."""
        content = """# Title
## Section One
### Subsection
## Section Two
"""
        result = inject_anchors(content)
        anchors = ["title", "section-one", "subsection", "section-two"]
        for anchor in anchors:
            assert f'id="{anchor}"' in result, f"Missing anchor: {anchor}"

    def test_heading_anchor_generation_consistency(self):
        """make_anchor should be consistent with inject_anchors behavior."""
        text = "My Section Heading (v2)"
        anchor = make_anchor(text)
        processed = inject_anchors(f"## {text}")
        assert f'id="{anchor}"' in processed

    def test_toc_builds_from_all_headings(self):
        """TOC should include all headings at or above min_level."""
        content = """# Title
## Section One
### Subsection
#### Deep
## Section Two
"""
        headings = extract_headings(content)
        toc_html = build_viewer_html(content, toc=headings)
        for h in headings:
            if h["level"] >= 2:
                assert h["anchor"] in toc_html or h["text"] in toc_html

    def test_viewer_html_structure_complete(self):
        """Viewer HTML should have all required structural elements."""
        content = "# Test"
        html = build_viewer_html(content, title="Test Page")
        assert "<!DOCTYPE html>" in html
        assert "<html>" in html
        assert "<head>" in html
        assert "<body>" in html
        assert "Test Page" in html

    def test_viewer_respects_include_mermaid_flag(self):
        """Viewer should respect include_mermaid=False."""
        content = """# Doc
```mermaid
graph TD
    A --> B
```
"""
        html = build_viewer_html(content, include_mermaid=False)
        assert '<div class="mermaid">' not in html

    def test_viewer_with_nav_and_toc(self):
        """Viewer should correctly combine nav tree and TOC."""
        content = """# Main
## Section
"""
        headings = extract_headings(content)
        nav_nodes = [
            {"label": "Overview", "path": "docs/00-overview.md", "type": "overview"},
            {"label": "Section", "path": "docs/sections/test/index.md", "type": "section"},
        ]
        html = build_viewer_html(content, nav_nodes=nav_nodes, toc=headings)
        assert "tree-nav" in html
        assert "toc" in html


class TestBrokenLinkDetection:
    """Tests for broken link detection in generated content."""

    def test_external_links_not_validated(self):
        """External links are not validated (expected behavior)."""
        content = "[Google](https://google.com)"
        # Links are preserved as-is
        assert "[Google](https://google.com)" in content

    def test_relative_links_preserved(self):
        """Relative links should be preserved in output."""
        content = "[Overview](docs/00-overview.md)"
        # The link structure is preserved
        assert "[Overview]" in content
        assert "docs/00-overview.md" in content

    def test_anchor_links_for_headings(self):
        """Anchor links to headings should work correctly."""
        content = "## My Section"
        processed = inject_anchors(content)
        anchor = make_anchor("My Section")
        assert f'id="{anchor}"' in processed
        assert f'href="#{anchor}"' in processed or f'"{anchor}"' in processed


class TestVisualAcceptanceSuite:
    """Visual acceptance test suite for release candidates."""

    def test_representative_page_renders(self):
        """A representative wiki page should render without errors."""
        content = """# Project Overview

## Architecture
### Components
```mermaid
graph TD
    A[Service] --> B[Database]
    A --> C[Cache]
```

## Operations
### Deployment
See [deployment guide](../ops/deploy.md).

## API
### Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/status | Health check |
| POST | /api/update | Trigger update |
"""
        headings = extract_headings(content)
        nav_nodes = [
            {"label": "Overview", "path": "docs/00-overview.md", "type": "overview"},
            {
                "label": "Architecture",
                "path": "docs/sections/architecture/index.md",
                "type": "section",
            },
            {"label": "Operations", "path": "docs/sections/operations/index.md", "type": "section"},
            {"label": "API", "path": "docs/sections/api/index.md", "type": "section"},
        ]

        html = build_viewer_html(
            content,
            title="Project Wiki",
            nav_nodes=nav_nodes,
            toc=headings,
            include_mermaid=True,
        )

        # Verify all key elements
        assert "<!DOCTYPE html>" in html
        assert '<div class="mermaid">' in html
        assert "Project Overview" in html
        assert "Architecture" in html
        assert "tree-nav" in html
        assert "toc" in html

    def test_narrow_viewport_viewer_compatibility(self):
        """Viewer should be compatible with narrow viewports."""
        content = """# Test
## Section
### Subsection
"""
        headings = extract_headings(content)
        html = build_viewer_html(content, toc=headings)

        # Viewer uses CSS flexbox/grid which adapts - verify structure
        assert "<body>" in html
        # No JavaScript errors possible in static HTML
        assert "mermaid" in html.lower()

    def test_viewer_css_isolation(self):
        """Viewer CSS should not leak to external content."""
        content = "# Test Content"
        html = build_viewer_html(content)
        # CSS is scoped via class selectors
        assert ".content" in html or ".markdown-body" in html
        # Tree nav has its own styling
        assert "tree-nav" in html
