"""Qoder-style navigation metadata adapter and import bridge.

This module provides:
- QoderNavMetadata: Schema for qoder-style navigation metadata
- QoderToRepoAgentMapper: Maps qoder metadata to repo-agent navigation format
- ImportBridge: Imports qoder metadata with validation and warnings
- Reason codes for unmapped or conflicting navigation nodes

The adapter is optional and isolated from canonical generation output.
It enables side-by-side evaluation of qoder-like navigation structures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# =============================================================================
# QODER NAVIGATION METADATA SCHEMA
# =============================================================================

QODER_NAV_TYPES = ("section", "overview", "module", "phase", "index", "toc")


@dataclass
class QoderNavNode:
    """A single navigation node in qoder-style metadata."""

    id: str  # Unique node identifier
    label: str  # Display label
    nav_type: str  # Type: section, overview, module, phase, index, toc
    path: str | None = None  # Optional path to content file
    children: list[QoderNavNode] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)  # Alternative IDs
    metadata: dict[str, Any] = field(default_factory=dict)  # Additional metadata


@dataclass
class QoderNavMetadata:
    """Qoder-style navigation metadata container."""

    version: str = "1.0"
    root_id: str | None = None  # Root node ID
    nodes: list[QoderNavNode] = field(default_factory=list)
    index_path: str | None = None  # Path to main index/TOC file
    generated_at: str | None = None  # Generation timestamp


# =============================================================================
# MAPPING AND VALIDATION
# =============================================================================

# Reason codes for validation issues
VALIDATION_REASON_CODES = {
    "QODER_NODE_UNMAPPED": "Qoder node has no corresponding canonical section/module",
    "QODER_PATH_MISSING": "Qoder node references a path that does not exist",
    "QODER_ALIAS_CONFLICT": "Qoder alias overlaps with existing canonical section",
    "QODER_DEPTH_MISMATCH": "Qoder node depth differs from canonical navigation depth",
    "QODER_CYCLE_DETECTED": "Circular reference detected in qoder navigation tree",
    "QODER_DUPLICATE_ID": "Duplicate node ID in qoder metadata",
}


@dataclass
class MappingResult:
    """Result of mapping a single qoder node to repo-agent format."""

    success: bool
    qoder_id: str
    repo_agent_path: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    """Result of importing full qoder metadata."""

    success: bool
    mapped_nodes: list[dict[str, Any]] = field(default_factory=list)
    unmapped_ids: list[str] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)  # {code, node_id, message}
    errors: list[dict[str, str]] = field(default_factory=list)
    total_qoder_nodes: int = 0
    total_mapped: int = 0


# =============================================================================
# QODER TO REPO-AGENT MAPPER
# =============================================================================

# Canonical section slugs for mapping
CANONICAL_SECTIONS: frozenset[str] = frozenset(
    [
        "project",
        "architecture",
        "services",
        "python-services",
        "data-model",
        "api",
        "operations",
        "development",
        "security",
        "troubleshooting",
    ]
)

# Map qoder-style names to canonical slugs
QODER_TO_CANONICAL: dict[str, str] = {
    # Q01/S01 prefixed sections
    "q01-architecture": "architecture",
    "q02-services": "services",
    "q03-python-services": "python-services",
    "q04-data-model": "data-model",
    "q05-api": "api",
    "q06-operations": "operations",
    "q07-development": "development",
    "q08-security": "security",
    "q09-troubleshooting": "troubleshooting",
    # S01/S02 prefixed sections
    "s01-architecture": "architecture",
    "s02-services": "services",
    "s03-python-services": "python-services",
    "s04-data-model": "data-model",
    "s05-api": "api",
    "s06-operations": "operations",
    "s07-development": "development",
    "s08-security": "security",
    "s09-troubleshooting": "troubleshooting",
    # Direct mappings
    "architecture": "architecture",
    "services": "services",
    "python-services": "python-services",
    "data-model": "data-model",
    "data_model": "data-model",
    "api": "api",
    "operations": "operations",
    "development": "development",
    "security": "security",
    "troubleshooting": "troubleshooting",
    "project": "project",
    # English variants
    "getting-started": "project",
    "intro": "project",
}


class QoderToRepoAgentMapper:
    """Maps qoder-style navigation metadata to repo-agent format."""

    def __init__(self, root_dir: Path | str | None = None) -> None:
        self.root_dir = Path(root_dir) if root_dir else Path.cwd()
        self._seen_ids: set[str] = set()
        self._seen_aliases: set[str] = set()

    def reset(self) -> None:
        """Reset internal state for fresh mapping."""
        self._seen_ids.clear()
        self._seen_aliases.clear()

    def map_node(self, node: QoderNavNode) -> MappingResult:
        """Map a single qoder node to repo-agent navigation format.

        Args:
            node: Qoder navigation node to map

        Returns:
            MappingResult with success status and mapped path (if any)
        """
        result = MappingResult(success=False, qoder_id=node.id)

        # Check for duplicate IDs
        if node.id in self._seen_ids:
            result.errors.append(f"{'QODER_DUPLICATE_ID'}: {node.id}")
            return result
        self._seen_ids.add(node.id)

        # Check aliases for conflicts
        for alias in node.aliases:
            if alias in self._seen_aliases:
                result.warnings.append(
                    f"{VALIDATION_REASON_CODES['QODER_ALIAS_CONFLICT']}: {alias}"
                )
            self._seen_aliases.add(alias)

        # Try to map the node ID or label to canonical slug
        canonical_slug = self._find_canonical_slug(node.id)

        if canonical_slug is None:
            # Also try label
            canonical_slug = self._find_canonical_slug(node.label)

        if canonical_slug is None:
            result.warnings.append(
                f"{VALIDATION_REASON_CODES['QODER_NODE_UNMAPPED']}: {node.id} ({node.label})"
            )
            return result

        # Build repo-agent path
        repo_agent_path = self._build_repo_agent_path(canonical_slug, node)

        # Verify path exists
        if node.path:
            full_path = self.root_dir / node.path
            if not full_path.exists() and not full_path.is_file():
                result.warnings.append(
                    f"{VALIDATION_REASON_CODES['QODER_PATH_MISSING']}: {node.path}"
                )

        result.success = True
        result.repo_agent_path = repo_agent_path
        return result

    def _find_canonical_slug(self, identifier: str) -> str | None:
        """Find canonical slug for a qoder identifier.

        Checks:
        1. Direct mapping in QODER_TO_CANONICAL
        2. Lowercase normalized match
        3. Section definitions match
        """
        normalized = identifier.strip().lower()

        # Direct mapping
        if normalized in QODER_TO_CANONICAL:
            return QODER_TO_CANONICAL[normalized]

        # Check against canonical section names
        if normalized in CANONICAL_SECTIONS:
            return normalized

        # Check for Q01/S01 prefix pattern
        q_pattern = re.compile(r"^[sq]\d+-(.+)$")
        match = q_pattern.match(normalized)
        if match:
            suffix = match.group(1)
            if suffix in QODER_TO_CANONICAL:
                return QODER_TO_CANONICAL[suffix]
            if suffix in CANONICAL_SECTIONS:
                return suffix

        return None

    def _build_repo_agent_path(self, canonical_slug: str, node: QoderNavNode) -> str:
        """Build repo-agent output path for a mapped node.

        Args:
            canonical_slug: Canonical section/module slug
            node: Original qoder node

        Returns:
            Repo-agent relative path (e.g., 'docs/sections/architecture/index.md')
        """
        if node.nav_type == "overview":
            # Overview pages are at docs/ level
            return f"docs/00-{canonical_slug}.md"
        elif node.nav_type == "module":
            return f"docs/modules/{canonical_slug}.md"
        elif node.nav_type == "phase":
            return f"docs/phases/{canonical_slug}.md"
        else:
            # Default to section path
            return f"docs/sections/{canonical_slug}/index.md"


# =============================================================================
# IMPORT BRIDGE
# =============================================================================


class QoderImportBridge:
    """Import bridge for qoder-style navigation metadata.

    This bridge:
    1. Parses qoder metadata from various formats
    2. Validates against canonical contracts
    3. Maps to repo-agent navigation format
    4. Emits warnings for unresolved mappings
    """

    def __init__(self, root_dir: Path | str | None = None) -> None:
        self.root_dir = Path(root_dir) if root_dir else Path.cwd()
        self.mapper = QoderToRepoAgentMapper(self.root_dir)

    def parse_qoder_metadata(self, data: dict[str, Any]) -> QoderNavMetadata:
        """Parse qoder metadata from dict format.

        Expected format:
        {
            "version": "1.0",
            "root_id": "root",
            "nodes": [
                {"id": "q01-architecture", "label": "Architecture", "type": "section", ...},
                ...
            ],
            "index_path": "docs/toc.md"
        }
        """
        metadata = QoderNavMetadata(
            version=data.get("version", "1.0"),
            root_id=data.get("root_id"),
            index_path=data.get("index_path"),
            generated_at=data.get("generated_at"),
        )

        nodes_data = data.get("nodes", [])
        for node_data in nodes_data:
            node = QoderNavNode(
                id=node_data["id"],
                label=node_data.get("label", node_data["id"]),
                nav_type=node_data.get("type", "section"),
                path=node_data.get("path"),
                aliases=node_data.get("aliases", []),
                metadata=node_data.get("metadata", {}),
            )
            # Recursively parse children
            node.children = self._parse_children(node_data.get("children", []))
            metadata.nodes.append(node)

        return metadata

    def _parse_children(self, children_data: list[dict[str, Any]]) -> list[QoderNavNode]:
        """Recursively parse child nodes."""
        children: list[QoderNavNode] = []
        for child_data in children_data:
            child = QoderNavNode(
                id=child_data["id"],
                label=child_data.get("label", child_data["id"]),
                nav_type=child_data.get("type", "section"),
                path=child_data.get("path"),
                aliases=child_data.get("aliases", []),
                metadata=child_data.get("metadata", {}),
            )
            child.children = self._parse_children(child_data.get("children", []))
            children.append(child)
        return children

    def import_metadata(self, metadata: QoderNavMetadata) -> ImportResult:
        """Import qoder metadata and map to repo-agent format.

        Args:
            metadata: Parsed qoder metadata

        Returns:
            ImportResult with mapping results, warnings, and errors
        """

        # Count all nodes including children recursively
        def count_all_nodes(nodes: list[QoderNavNode]) -> int:
            count = len(nodes)
            for node in nodes:
                count += count_all_nodes(node.children)
            return count

        total_nodes = count_all_nodes(metadata.nodes)
        result = ImportResult(success=True, total_qoder_nodes=total_nodes)
        self.mapper.reset()

        # Map all nodes recursively
        for node in metadata.nodes:
            self._map_node_recursive(node, result)

        # Check for cycles in the navigation tree
        self._check_for_cycles(metadata, result)

        result.success = len(result.errors) == 0
        return result

    def _map_node_recursive(self, node: QoderNavNode, result: ImportResult) -> None:
        """Recursively map a node and its children."""
        mapping = self.mapper.map_node(node)

        if mapping.success:
            result.mapped_nodes.append(
                {
                    "qoder_id": node.id,
                    "qoder_label": node.label,
                    "qoder_type": node.nav_type,
                    "repo_agent_path": mapping.repo_agent_path,
                    "children": [],
                }
            )
            result.total_mapped += 1
        else:
            result.unmapped_ids.append(node.id)
            for warning in mapping.warnings:
                result.warnings.append(
                    {
                        "code": self._extract_code(warning),
                        "node_id": node.id,
                        "message": warning,
                    }
                )
            for error in mapping.errors:
                result.errors.append(
                    {
                        "code": self._extract_code(error),
                        "node_id": node.id,
                        "message": error,
                    }
                )

        # Process children
        for child in node.children:
            self._map_node_recursive(child, result)

    def _extract_code(self, message: str) -> str:
        """Extract reason code from message."""
        for code, desc in VALIDATION_REASON_CODES.items():
            if code in message:
                return code
        return "UNKNOWN"

    def _check_for_cycles(self, metadata: QoderNavMetadata, result: ImportResult) -> None:
        """Check for circular references in navigation tree."""
        visited: set[str] = set()
        path: list[str] = []

        def visit(node: QoderNavNode) -> bool:
            if node.id in visited:
                result.warnings.append(
                    {
                        "code": VALIDATION_REASON_CODES["QODER_CYCLE_DETECTED"],
                        "node_id": node.id,
                        "message": f"Cycle detected: {' -> '.join(path)} -> {node.id}",
                    }
                )
                return True
            visited.add(node.id)
            path.append(node.id)
            for child in node.children:
                if visit(child):
                    return True
            path.pop()
            return False

        for node in metadata.nodes:
            if visit(node):
                break


# =============================================================================
# COMPATIBILITY CHECKS
# =============================================================================


def check_qoder_compatibility(
    qoder_data: dict[str, Any],
    root_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Check compatibility of qoder metadata with repo-agent navigation.

    This is a convenience function that combines parsing, mapping, and validation.

    Args:
        qoder_data: Qoder-style metadata as dict
        root_dir: Root directory for path validation

    Returns:
        Dict with keys: compatible (bool), import_result, summary
    """
    bridge = QoderImportBridge(root_dir)

    try:
        metadata = bridge.parse_qoder_metadata(qoder_data)
    except Exception as exc:
        return {
            "compatible": False,
            "error": str(exc),
            "import_result": None,
            "summary": f"Failed to parse qoder metadata: {exc}",
        }

    import_result = bridge.import_metadata(metadata)

    summary_parts = [
        f"Qoder nodes: {import_result.total_qoder_nodes}",
        f"Mapped: {import_result.total_mapped}",
        f"Unmapped: {len(import_result.unmapped_ids)}",
        f"Warnings: {len(import_result.warnings)}",
        f"Errors: {len(import_result.errors)}",
    ]

    return {
        "compatible": import_result.success,
        "import_result": import_result,
        "summary": "; ".join(summary_parts),
        "unmapped_ids": import_result.unmapped_ids,
    }


# =============================================================================
# SIDE-BY-SIDE COMPARISON
# =============================================================================


@dataclass
class SideBySideNode:
    """A node in the side-by-side comparison."""

    qoder_id: str | None
    qoder_label: str | None
    qoder_type: str | None
    qoder_path: str | None
    repo_agent_path: str | None
    status: str  # "mapped", "unmapped", "conflict", "missing"
    warnings: list[str] = field(default_factory=list)


@dataclass
class SideBySideComparisonResult:
    """Result of side-by-side navigation comparison."""

    success: bool
    qoder_nav: list[SideBySideNode]
    repo_agent_nav: list[dict[str, Any]]  # Actual canonical sections
    unmatched_qoder: list[SideBySideNode]
    alias_conflicts: list[SideBySideNode]
    depth_mismatches: list[SideBySideNode]
    summary: str


def generate_side_by_side_comparison(
    qoder_data: dict[str, Any],
    root_dir: Path | str | None = None,
) -> SideBySideComparisonResult:
    """Generate side-by-side comparison of qoder navigation with canonical sections.

    This function:
    1. Imports and maps qoder metadata
    2. Compares against actual canonical sections
    3. Reports unmatched nodes, alias conflicts, and depth mismatches
    4. Produces read-only comparison output for manual review

    Args:
        qoder_data: Qoder-style metadata as dict
        root_dir: Root directory for path validation

    Returns:
        SideBySideComparisonResult with comparison details
    """
    bridge = QoderImportBridge(root_dir)

    try:
        metadata = bridge.parse_qoder_metadata(qoder_data)
    except Exception as exc:
        return SideBySideComparisonResult(
            success=False,
            qoder_nav=[],
            repo_agent_nav=[],
            unmatched_qoder=[],
            alias_conflicts=[],
            depth_mismatches=[],
            summary=f"Failed to parse qoder metadata: {exc}",
        )

    import_result = bridge.import_metadata(metadata)

    # Build side-by-side nodes
    qoder_nav: list[SideBySideNode] = []
    unmatched_qoder: list[SideBySideNode] = []
    alias_conflicts: list[SideBySideNode] = []
    depth_mismatches: list[SideBySideNode] = []

    for mapped in import_result.mapped_nodes:
        qoder_nav.append(
            SideBySideNode(
                qoder_id=mapped.get("qoder_id"),
                qoder_label=mapped.get("qoder_label"),
                qoder_type=mapped.get("qoder_type"),
                qoder_path=mapped.get("qoder_path"),
                repo_agent_path=mapped.get("repo_agent_path"),
                status="mapped",
                warnings=[],
            )
        )

    for unmapped_id in import_result.unmapped_ids:
        # Find the original node data
        node_found = None
        for node in metadata.nodes:
            if node.id == unmapped_id:
                node_found = node
                break
            for child in _flatten_children(node.children):
                if child.id == unmapped_id:
                    node_found = child
                    break

        if node_found:
            warnings = [
                w["message"] for w in import_result.warnings if w.get("node_id") == unmapped_id
            ]
            status = "unmapped"
            for w in warnings:
                if "ALIAS_CONFLICT" in w:
                    status = "conflict"
                    alias_conflicts.append(
                        SideBySideNode(
                            qoder_id=node_found.id,
                            qoder_label=node_found.label,
                            qoder_type=node_found.nav_type,
                            qoder_path=node_found.path,
                            repo_agent_path=None,
                            status=status,
                            warnings=[w],
                        )
                    )
                elif "DEPTH_MISMATCH" in w:
                    status = "depth_mismatch"
                    depth_mismatches.append(
                        SideBySideNode(
                            qoder_id=node_found.id,
                            qoder_label=node_found.label,
                            qoder_type=node_found.nav_type,
                            qoder_path=node_found.path,
                            repo_agent_path=None,
                            status=status,
                            warnings=[w],
                        )
                    )
                elif status != "conflict" and status != "depth_mismatch":
                    unmatched_qoder.append(
                        SideBySideNode(
                            qoder_id=node_found.id,
                            qoder_label=node_found.label,
                            qoder_type=node_found.nav_type,
                            qoder_path=node_found.path,
                            repo_agent_path=None,
                            status=status,
                            warnings=[w],
                        )
                    )

    # Get actual repo-agent canonical sections from qoder data
    repo_agent_nav: list[dict[str, Any]] = [
        {"slug": slug, "path": f"docs/sections/{slug}/index.md"}
        for slug in sorted(CANONICAL_SECTIONS)
    ]

    summary_parts = [
        f"Qoder nodes: {import_result.total_qoder_nodes}",
        f"Mapped: {len(qoder_nav)}",
        f"Unmapped: {len(unmatched_qoder)}",
        f"Alias conflicts: {len(alias_conflicts)}",
        f"Depth mismatches: {len(depth_mismatches)}",
    ]

    return SideBySideComparisonResult(
        success=import_result.success,
        qoder_nav=qoder_nav,
        repo_agent_nav=repo_agent_nav,
        unmatched_qoder=unmatched_qoder,
        alias_conflicts=alias_conflicts,
        depth_mismatches=depth_mismatches,
        summary="; ".join(summary_parts),
    )


def _flatten_children(children: list[QoderNavNode]) -> list[QoderNavNode]:
    """Recursively flatten child nodes."""
    result: list[QoderNavNode] = []
    for child in children:
        result.append(child)
        result.extend(_flatten_children(child.children))
    return result


def format_side_by_side_report(result: SideBySideComparisonResult) -> str:
    """Format side-by-side comparison result as a readable report.

    Args:
        result: SideBySideComparisonResult from generate_side_by_side_comparison

    Returns:
        Formatted report string
    """
    lines = [
        "# Qoder vs Repo-Agent Navigation Comparison",
        "",
        f"Status: {'PASS' if result.success else 'FAIL'}",
        "",
        "## Summary",
        result.summary,
        "",
        "## Mapped Nodes",
        "| Qoder ID | Qoder Label | Repo-Agent Path |",
        "|----------|-------------|-----------------|",
    ]

    for node in result.qoder_nav:
        lines.append(
            f"| {node.qoder_id or ''} | {node.qoder_label or ''} | {node.repo_agent_path or ''} |"
        )

    if result.unmatched_qoder:
        lines.extend(["", "## Unmatched Qoder Nodes", ""])
        for node in result.unmatched_qoder:
            lines.append(
                f"- **{node.qoder_id}** ({node.qoder_label}): {', '.join(node.warnings) if node.warnings else 'no mapping'}"
            )

    if result.alias_conflicts:
        lines.extend(["", "## Alias Conflicts", ""])
        for node in result.alias_conflicts:
            lines.append(f"- **{node.qoder_id}**: {', '.join(node.warnings)}")

    if result.depth_mismatches:
        lines.extend(["", "## Depth Mismatches", ""])
        for node in result.depth_mismatches:
            lines.append(f"- **{node.qoder_id}**: {', '.join(node.warnings)}")

    lines.extend(
        [
            "",
            "## Canonical Sections",
            "",
        ]
    )
    for section in result.repo_agent_nav:
        lines.append(f"- {section['slug']}: {section['path']}")

    return "\n".join(lines)
