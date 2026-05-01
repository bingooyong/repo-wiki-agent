"""repo-wiki viewer module for static wiki viewing and IDE integration."""

from repo_wiki.viewer.static_viewer import (
    build_toc_html,
    build_tree_html,
    build_viewer_html,
    build_nav_tree_from_manifest,
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

__all__ = [
    "build_toc_html",
    "build_tree_html",
    "build_viewer_html",
    "build_nav_tree_from_manifest",
    "create_viewer_for_directory",
    "extract_headings",
    "get_label_from_path",
    "get_mermaid_script",
    "get_nav_type_from_path",
    "inject_anchors",
    "inject_mermaid_support",
    "make_anchor",
    "render_mermaid_safely",
]
