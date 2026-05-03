"""Static repo-wiki viewer with tree navigation and Mermaid rendering.

This module provides:
- StaticViewer: Static HTML viewer for generated wiki content
- TreeNavigation: Left-side navigation tree from manifest/section hierarchy
- MermaidRenderer: Safe Mermaid diagram rendering
- TableOfContents: In-page heading navigation with anchor jumps

The viewer is designed to work with static local files without external service dependency.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# =============================================================================
# MERMAID RENDERING
# =============================================================================

MERMAID_BLOCK_PATTERN = re.compile(r"```mermaid\s*(.*?)\s*```", re.DOTALL)

# Configurable Mermaid source - supports both CDN and local bundle
# Set MERMAID_LOCAL_PATH to a local file path to use bundled Mermaid
MERMAID_CDN_URL = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"
MERMAID_LOCAL_PATH: str | None = None  # Set to local path for offline use


def get_mermaid_script() -> str:
    """Get the Mermaid initialization script with current configuration."""
    if MERMAID_LOCAL_PATH:
        script_src = MERMAID_LOCAL_PATH
    else:
        script_src = MERMAID_CDN_URL
    return f"""
<script src="{script_src}"></script>
<script>
mermaid.initialize({{
    startOnLoad: true,
    theme: 'default',
    securityLevel: 'loose',
    flowchart: {{ useMaxWidth: true, htmlLabels: true }},
    sequenceDiagram: {{ useMaxWidth: true }}
}});
</script>
"""


MERMAID_SCRIPT = get_mermaid_script()


def render_mermaid_safely(content: str) -> str:
    """Render Mermaid blocks by wrapping them in proper HTML.

    This replaces ```mermaid blocks with HTML that Mermaid.js can render.
    The output is safe for static HTML files.
    """

    def replace_mermaid_block(match: re.Match) -> str:
        diagram_code = match.group(1).strip()
        return f'<div class="mermaid">\n{diagram_code}\n</div>'

    return MERMAID_BLOCK_PATTERN.sub(replace_mermaid_block, content)


def inject_mermaid_support(html_content: str) -> str:
    """Inject Mermaid.js CDN and initialization into HTML content."""
    # Check if Mermaid blocks exist (single or double quotes)
    if 'class="mermaid">' not in html_content and "class='mermaid'>" not in html_content:
        return html_content

    # Get current Mermaid script (respects MERMAID_LOCAL_PATH setting)
    mermaid_script = get_mermaid_script()

    # Inject Mermaid script before </head> or at start if no </head>
    if "</head>" in html_content:
        return html_content.replace("</head>", f"{mermaid_script}</head>")
    elif "<head>" in html_content:
        # Replace opening head tag with head + script
        return html_content.replace("<head>", f"<head>{mermaid_script}")
    else:
        # No head tag at all, prepend before body or at start
        if "<body>" in html_content:
            return html_content.replace("<body>", f"{mermaid_script}<body>")
        return mermaid_script + html_content


# =============================================================================
# TABLE OF CONTENTS
# =============================================================================

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def extract_headings(content: str) -> list[dict[str, Any]]:
    """Extract headings from markdown content for TOC generation.

    Returns list of dicts with: level, text, anchor
    """
    headings: list[dict[str, Any]] = []
    for match in HEADING_PATTERN.finditer(content):
        level = len(match.group(1))
        text = match.group(2).strip()
        anchor = make_anchor(text)
        headings.append({"level": level, "text": text, "anchor": anchor})
    return headings


def make_anchor(text: str) -> str:
    """Convert heading text to an anchor ID.

    - Lowercase
    - Replace spaces with hyphens
    - Remove non-alphanumeric characters (except hyphens)
    - Collapse multiple hyphens
    """
    # GitHub-style anchor generation
    anchor = text.lower()
    anchor = re.sub(r"[^\w\s-]", "", anchor)
    anchor = re.sub(r"[-\s]+", "-", anchor)
    anchor = anchor.strip("-")
    return anchor


def inject_anchors(content: str) -> str:
    """Inject HTML anchor IDs into headings.

    This enables in-page jumping from TOC links.
    """

    def replace_heading(match: re.Match) -> str:
        hashes = match.group(1)
        text = match.group(2).strip()
        anchor = make_anchor(text)
        return f'{hashes} <span id="{anchor}">{text}</span>'

    return HEADING_PATTERN.sub(replace_heading, content)


def build_toc_html(headings: list[dict[str, Any]], min_level: int = 2) -> str:
    """Build HTML for table of contents from heading list.

    Args:
        headings: List of heading dicts from extract_headings()
        min_level: Minimum heading level to include (default 2 = ##)

    Returns:
        HTML string for the TOC
    """
    if not headings:
        return ""

    lines = ['<nav class="toc" id="toc">', '<div class="toc-title">Table of Contents</div>']

    current_level = 0
    for h in headings:
        if h["level"] < min_level:
            continue

        indent = (h["level"] - min_level) * 2
        lines.append(
            f'<a class="toc-level-{h["level"]}" href="#{h["anchor"]}" '
            f'style="margin-left: {indent}em">{h["text"]}</a>'
        )

    lines.append("</nav>")
    return "\n".join(lines)


# =============================================================================
# TREE NAVIGATION
# =============================================================================

NAV_NODE_TYPES = ("overview", "section", "module", "phase")


def build_nav_tree_from_manifest(manifest_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Build navigation tree from eval manifest data.

    Uses navigation_tree field as the canonical navigation contract.
    Falls back to files field for legacy manifests.

    New manifest structure (preferred):
    {
        "navigation_tree": [
            {"type": "category", "label": "项目概述", "children": [...]},
            ...
        ],
        ...
    }

    Legacy manifest structure:
    {
        "files": [
            {"path": "docs/00-overview.md"},
            ...
        ]
    }

    Returns a tree structure suitable for HTML rendering.
    """
    if "navigation_tree" in manifest_data and manifest_data["navigation_tree"]:
        return _convert_navigation_tree(manifest_data["navigation_tree"])

    # Fallback to legacy files field
    if "files" in manifest_data:
        return _build_tree_from_files(manifest_data)

    return []


def _convert_navigation_tree(nav_tree: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert new navigation_tree format to flat list for viewer.

    Args:
        nav_tree: Navigation tree from manifest

    Returns:
        Flat list of nodes suitable for viewer
    """
    result: list[dict[str, Any]] = []

    def flatten(node: dict[str, Any]) -> None:
        if node.get("type") == "page" and node.get("path"):
            result.append(
                {
                    "label": node.get("label", node.get("path", "")),
                    "path": node.get("path", ""),
                    "type": get_nav_type_from_path(node.get("path", "")),
                }
            )
        if "children" in node:
            for child in node["children"]:
                flatten(child)

    for category in nav_tree:
        flatten(category)

    return result


def _build_tree_from_files(manifest_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Build navigation tree from files field (legacy format).

    Args:
        manifest_data: Manifest data with files field

    Returns:
        Tree structure built from files
    """
    tree: list[dict[str, Any]] = []
    sections: dict[str, list[dict[str, Any]]] = {
        "overview": [],
        "section": [],
        "module": [],
        "phase": [],
    }

    if "files" not in manifest_data:
        return tree

    for file_entry in manifest_data["files"]:
        path = file_entry.get("path", "")
        node = {
            "label": get_label_from_path(path),
            "path": path,
            "type": get_nav_type_from_path(path),
        }

        if path.startswith("docs/00-"):
            sections["overview"].append(node)
        elif path.startswith("docs/sections/"):
            sections["section"].append(node)
        elif path.startswith("docs/modules/"):
            sections["module"].append(node)
        elif path.startswith("docs/phases/"):
            sections["phase"].append(node)

    # Build ordered tree
    for overview_node in sorted(sections["overview"], key=lambda n: n["path"]):
        tree.append(overview_node)

    for section_node in sorted(sections["section"], key=lambda n: n["path"]):
        tree.append(section_node)

    for module_node in sorted(sections["module"], key=lambda n: n["path"]):
        tree.append(module_node)

    for phase_node in sorted(sections["phase"], key=lambda n: n["path"]):
        tree.append(phase_node)

    return tree


def get_nav_type_from_path(path: str) -> str:
    """Determine navigation type from file path."""
    # Handle both docs/ and content/ prefixes (qoder-like output uses content/)
    # Handle docs/00-overview.md, docs/01-architecture.md, etc.
    # Pattern: docs/0X-<name>.md where X is a digit (at positions 5 and 6)
    # docs/ 0 0 - o v e r v i e w . m d
    #       4 5 6 7 ...

    # Normalize: if path starts with "content/", treat as "docs/" equivalent
    normalized = path
    if normalized.startswith("content/"):
        normalized = "docs/" + normalized[8:]

    if (
        normalized.startswith("docs/0")
        and len(normalized) >= 8
        and normalized[7] == "-"
        and normalized[5].isdigit()
        and normalized[6].isdigit()
    ):
        return "overview"
    elif normalized.startswith("docs/sections/"):
        return "section"
    elif normalized.startswith("docs/modules/"):
        return "module"
    elif normalized.startswith("docs/phases/"):
        return "phase"
    return "other"


def get_label_from_path(path: str) -> str:
    """Extract human-readable label from file path."""
    # docs/00-overview.md -> Overview
    # docs/01-architecture.md -> Architecture
    # docs/sections/architecture/index.md -> Architecture
    # docs/modules/repo_wiki.md -> repo_wiki
    # docs/phases/phase-01-setup.md -> Phase 01: Setup

    parts = Path(path).parts
    if parts[0] == "docs":
        if len(parts) == 2:
            # docs/00-overview.md
            stem = Path(parts[1]).stem
            return stem.lstrip("0123456789-").replace("-", " ").title()
        elif len(parts) == 4 and parts[1] == "sections":
            # docs/sections/architecture/index.md
            return parts[2].replace("-", " ").title()
        elif len(parts) == 3 and parts[1] == "modules":
            # docs/modules/repo_wiki.md -> repo wiki
            return Path(parts[2]).stem.replace("-", " ").replace("_", " ").title()
        elif len(parts) == 3 and parts[1] == "phases":
            # docs/phases/phase-01-setup.md
            stem = Path(parts[2]).stem
            return stem.replace("-", " ").title()

    return path


def build_tree_html(nodes: list[dict[str, Any]], base_path: str = "") -> str:
    """Build HTML for left-side tree navigation.

    Args:
        nodes: List of navigation node dicts from build_nav_tree_from_manifest
        base_path: Base path prefix for links (e.g., "../" for depth)

    Returns:
        HTML string for the navigation tree
    """
    if not nodes:
        return ""

    lines = ['<nav class="tree-nav" id="tree-nav">']

    current_section = None
    for node in nodes:
        node_type = node.get("type", "other")
        label = node.get("label", node.get("path", ""))
        path = node.get("path", "")

        # Section header
        if node_type != current_section:
            section_label = {
                "overview": "Overview",
                "section": "Sections",
                "module": "Modules",
                "phase": "Phases",
            }.get(node_type, node_type.title())
            if current_section is not None:
                lines.append("</div>")
            lines.append(f'<div class="tree-section">{section_label}</div>')
            lines.append('<div class="tree-items">')
            current_section = node_type

        # Tree item
        link = f"{base_path}{path}" if base_path else path
        icon = get_tree_icon(node_type)
        lines.append(f'<a class="tree-item tree-{node_type}" href="{link}">{icon} {label}</a>')

    if current_section is not None:
        lines.append("</div>")
    lines.append("</nav>")

    return "\n".join(lines)


def get_tree_icon(node_type: str) -> str:
    """Get icon character for node type."""
    icons = {
        "overview": "📋",
        "section": "📑",
        "module": "📦",
        "phase": "🎯",
        "other": "📄",
    }
    return icons.get(node_type, "📄")


# =============================================================================
# STATIC VIEWER
# =============================================================================

VIEWER_CSS = """
<style>
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    margin: 0;
    padding: 0;
    display: flex;
    height: 100vh;
}
.toc {
    position: fixed;
    top: 0;
    right: 0;
    width: 250px;
    height: 100vh;
    overflow-y: auto;
    background: #f8f9fa;
    border-left: 1px solid #e0e0e0;
    padding: 1em;
    font-size: 0.9em;
}
.toc-title {
    font-weight: bold;
    margin-bottom: 0.5em;
    padding-bottom: 0.5em;
    border-bottom: 1px solid #e0e0e0;
}
.toc a {
    display: block;
    color: #333;
    text-decoration: none;
    padding: 0.25em 0.5em;
}
.toc a:hover {
    background: #e9ecef;
    border-radius: 4px;
}
.tree-nav {
    width: 280px;
    height: 100vh;
    overflow-y: auto;
    background: #2d2d2d;
    color: #fff;
    padding: 1em 0;
}
.tree-section {
    padding: 0.5em 1em;
    font-size: 0.8em;
    text-transform: uppercase;
    color: #888;
    border-bottom: 1px solid #444;
    margin-top: 0.5em;
}
.tree-item {
    display: block;
    padding: 0.5em 1em;
    color: #ccc;
    text-decoration: none;
    font-size: 0.9em;
}
.tree-item:hover {
    background: #404040;
    color: #fff;
}
.content {
    flex: 1;
    margin-right: 250px;
    padding: 2em 3em;
    overflow-y: auto;
    max-width: 900px;
}
.content .mermaid {
    background: #fff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 1em;
    margin: 1em 0;
}
.markdown-body {
    line-height: 1.6;
}
.markdown-body h1, .markdown-body h2, .markdown-body h3 {
    border-bottom: 1px solid #e0e0e0;
    padding-bottom: 0.3em;
}
.markdown-body table {
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
}
.markdown-body table th, .markdown-body table td {
    border: 1px solid #ddd;
    padding: 0.5em 1em;
    text-align: left;
}
.markdown-body pre {
    background: #f6f8fa;
    border-radius: 6px;
    padding: 1em;
    overflow-x: auto;
}
.markdown-body code {
    background: #f6f8fa;
    padding: 0.2em 0.4em;
    border-radius: 3px;
}
</style>
"""


def build_viewer_html(
    content: str,
    title: str = "Repo Wiki",
    nav_nodes: list[dict[str, Any]] | None = None,
    toc: list[dict[str, Any]] | None = None,
    include_mermaid: bool = True,
) -> str:
    """Build complete static HTML viewer for a wiki page.

    Args:
        content: Markdown content to render
        title: Page title
        nav_nodes: Navigation tree nodes
        toc: Table of contents headings
        include_mermaid: Whether to include Mermaid rendering support

    Returns:
        Complete HTML string
    """
    # Process content
    processed = inject_anchors(content)

    # Build navigation tree
    nav_html = build_tree_html(nav_nodes or []) if nav_nodes else ""

    # Build TOC
    toc_html = build_toc_html(toc or []) if toc else ""

    # Apply Mermaid rendering
    if include_mermaid:
        processed = render_mermaid_safely(processed)
        processed = inject_mermaid_support(processed)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    {VIEWER_CSS}
</head>
<body>
{nav_html}
<div class="content">
    <div class="markdown-body">
{processed}
    </div>
</div>
{toc_html}
</body>
</html>"""

    return html


def render_markdown_to_html(markdown_content: str) -> str:
    """Simple markdown to HTML conversion for static viewer.

    This handles the most common markdown elements. For full markdown
    rendering, a library like mistune or markdown2 would be needed.
    """
    # Apply anchor injection first (works on markdown)
    content = inject_anchors(markdown_content)

    # Convert to HTML - basic transformation
    # Headers
    content = re.sub(r"^###### (.+)$", r"<h6>\1</h6>", content, flags=re.MULTILINE)
    content = re.sub(r"^##### (.+)$", r"<h5>\1</h5>", content, flags=re.MULTILINE)
    content = re.sub(r"^#### (.+)$", r"<h4>\1</h4>", content, flags=re.MULTILINE)
    content = re.sub(r"^### (.+)$", r"<h3>\1</h3>", content, flags=re.MULTILINE)
    content = re.sub(r"^## (.+)$", r"<h2>\1</h2>", content, flags=re.MULTILINE)
    content = re.sub(r"^# (.+)$", r"<h1>\1</h1>", content, flags=re.MULTILINE)

    # Bold/italic
    content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", content)
    content = re.sub(r"\*(.+?)\*", r"<em>\1</em>", content)

    # Code blocks (must be done before inline code)
    content = re.sub(
        r"```(\w+)?\s*(.*?)\s*```", r"<pre><code>\2</code></pre>", content, flags=re.DOTALL
    )

    # Inline code
    content = re.sub(r"`([^`]+)`", r"<code>\1</code>", content)

    # Links
    content = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', content)

    # Images
    content = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', content)

    # Blockquotes
    content = re.sub(r"^&gt; (.+)$", r"<blockquote>\1</blockquote>", content, flags=re.MULTILINE)

    # Horizontal rules
    content = re.sub(r"^---+$", "<hr>", content, flags=re.MULTILINE)

    # Unordered lists
    content = re.sub(r"^- (.+)$", r"<li>\1</li>", content, flags=re.MULTILINE)
    content = re.sub(r"(<li>.*</li>\n?)+", r"<ul>\n\g<0></ul>", content)

    # Paragraphs - wrap loose text
    lines = content.split("\n\n")
    processed_lines = []
    for line in lines:
        if line.strip() and not line.strip().startswith("<"):
            processed_lines.append(f"<p>{line.strip()}</p>")
        else:
            processed_lines.append(line)

    return "\n\n".join(processed_lines)


# =============================================================================
# VIEWER SERVICE
# =============================================================================


def create_viewer_for_directory(
    root_dir: Path,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Create viewer configuration for a wiki directory.

    Args:
        root_dir: Root directory containing wiki files
        manifest_path: Optional path to eval manifest

    Returns:
        Viewer configuration dict with nav_nodes, files, etc.
    """
    import repo_wiki.generator.io as io

    # Load manifest if available
    manifest_data: dict[str, Any] = {}
    if manifest_path and manifest_path.exists():
        manifest_data = io.read_json(manifest_path, {})

    # Build navigation tree
    nav_nodes = build_nav_tree_from_manifest(manifest_data)

    # Discover files if no manifest
    if not nav_nodes:
        docs_dir = root_dir / "docs"
        if docs_dir.exists():
            for md_file in sorted(docs_dir.rglob("*.md")):
                rel_path = str(md_file.relative_to(root_dir))
                node_type = get_nav_type_from_path(rel_path)
                nav_nodes.append(
                    {
                        "label": get_label_from_path(rel_path),
                        "path": rel_path,
                        "type": node_type,
                    }
                )

    return {
        "root_dir": str(root_dir),
        "nav_nodes": nav_nodes,
        "manifest_path": str(manifest_path) if manifest_path else None,
    }
