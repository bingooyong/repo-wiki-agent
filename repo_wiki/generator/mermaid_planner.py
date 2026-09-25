"""Mermaid diagram planner and renderer for wiki pages.

This module provides:
- MermaidDiagramType: Enum of supported diagram types
- DiagramPlan: Plan for a diagram with evidence backing
- MermaidPlanner: Decides which diagram type to use based on page type and evidence
- MermaidRenderer: Renders valid Mermaid syntax
- validate_mermaid_syntax: Validates Mermaid syntax before writing

Phase 24 - Task 24.4: Mermaid diagram planner and renderer

Diagram types supported:
- flowchart: Process flows, architecture flows (TD/BT/LR/RL)
- sequenceDiagram: API calls, service interactions
- erDiagram: Entity relationships for data models
- classDiagram: Module/class relationships
- stateDiagram: State machine transitions
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from repo_wiki.evidence.ranking import PageEvidenceBinding
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.planner.rule_first import _is_filename_like_module_name

_WIKI_TOOL_LAYERS: tuple[tuple[str, str], ...] = (
    ("layer_docs", "docs/"),
    ("layer_ai", "ai/source-of-truth"),
    ("layer_repo_wiki", ".repo-wiki"),
)
_MERMAID_UNSAFE_ID = re.compile(r"[^A-Za-z0-9_]")
_MERMAID_RESERVED_IDS = frozenset(
    {
        "end",
        "subgraph",
        "style",
        "class",
        "click",
        "direction",
    }
)
_WIKI_PIPELINE_LABELS = frozenset(
    {"仓库扫描", "llm生成", "质量校验", "repo-wiki", "wiki生成", "llm generate"}
)


def mermaid_ident(value: str, prefix: str = "n") -> str:
    """Return a Mermaid 11-safe node/entity id."""
    text = _MERMAID_UNSAFE_ID.sub("_", (value or "").strip())
    text = re.sub(r"_+", "_", text).strip("_")
    if not text or text[0].isdigit():
        text = f"{prefix}_{text}" if text else prefix
    if text.casefold() in _MERMAID_RESERVED_IDS:
        text = f"{prefix}_{text}"
    return text[:48]


def mermaid_er_field(value: str) -> str:
    """Strip `{id}` / punctuation so ER attributes parse in Mermaid 11."""
    text = re.sub(r"[{}]", "", value or "").strip()
    text = _MERMAID_UNSAFE_ID.sub("_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "id"


def _mermaid_scalar_type(value: str) -> str:
    lowered = (value or "").split(".")[-1].lower().lstrip("*[]")
    if lowered in {"int", "int8", "int16", "int32", "int64", "uint", "uint64"}:
        return "int"
    if lowered in {"float", "float32", "float64"}:
        return "float"
    if lowered in {"bool"}:
        return "bool"
    if lowered in {"time", "datetime"}:
        return "datetime"
    return "string"


def _page_tokens(page_id: str) -> set[str]:
    return {part for part in re.split(r"[-_/]", (page_id or "").lower()) if len(part) >= 3}


def _endpoint_matches_page(endpoint: dict[str, Any], tokens: set[str]) -> bool:
    if not tokens:
        return True
    hay = " ".join(
        str(endpoint.get(key) or "") for key in ("path", "file_path", "service", "handler")
    ).lower()
    return any(token in hay for token in tokens)


_PY_APP_IMPORT_RE = re.compile(
    r"(?m)^\s*(?:from\s+(app(?:\.[A-Za-z_][\w]*)*)\s+import|import\s+(app(?:\.[A-Za-z_][\w]*)*))"
)


def python_app_package_label(path_or_module: str) -> str:
    """Map ``app/api/routes/articles.py`` / ``app.services.jwt`` to a package label."""
    text = (path_or_module or "").replace("\\", "/").strip()
    if text.endswith(".py"):
        text = text[:-3]
    text = text.replace(".", "/")
    parts = [part for part in text.split("/") if part and part != "__init__"]
    if not parts or parts[0] != "app":
        return ""
    if len(parts) >= 3 and parts[1] in {"api", "models"}:
        return "/".join(parts[:3])
    if len(parts) >= 2:
        return "/".join(parts[:2])
    return "app"


def extract_python_app_import_edges(files: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Return ``(from_pkg, to_pkg)`` edges among ``app/*`` packages."""
    edges: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for path, text in files:
        src = python_app_package_label(path)
        if not src:
            continue
        for match in _PY_APP_IMPORT_RE.finditer(text or ""):
            dest = python_app_package_label(match.group(1) or match.group(2) or "")
            if not dest or dest == src:
                continue
            key = (src, dest)
            if key in seen:
                continue
            seen.add(key)
            edges.append(key)
    return edges


_SCHEMA_NAME_SUFFIXES = (
    "request",
    "response",
    "schema",
    "in",
    "out",
    "create",
    "update",
    "config",
)


def _is_request_response_schema(model: dict[str, Any]) -> bool:
    name = str(model.get("name") or "")
    path = str(model.get("file_path") or "").replace("\\", "/").lower()
    if "models/schemas" in path or "/schemas/" in path:
        return True
    lowered = name.lower()
    return (
        any(lowered.endswith(suffix) for suffix in _SCHEMA_NAME_SUFFIXES)
        and str(model.get("type") or "") != "migration_table"
    )


def _package_from_file(path: str) -> str:
    parts = [part for part in path.replace("\\", "/").split("/") if part]
    if "internal" in parts:
        index = parts.index("internal")
        return "/".join(parts[index : index + 2])
    app_label = python_app_package_label(path)
    if app_label:
        return app_label
    if len(parts) >= 2:
        return parts[-2]
    return parts[-1] if parts else ""


def _endpoint_actor(endpoint: dict[str, Any]) -> str:
    handler = str(endpoint.get("handler") or endpoint.get("service") or "").strip()
    if handler:
        return handler
    file_path = str(endpoint.get("file_path") or "").replace("\\", "/")
    name = file_path.rsplit("/", 1)[-1]
    if "." in name:
        return name.rsplit(".", 1)[0]
    return _package_from_file(file_path) or "API"


# ============================================================================
# DIAGRAM TYPE DEFINITIONS
# ============================================================================


class MermaidDiagramType(str, Enum):
    """Supported Mermaid diagram types."""

    FLOWCHART = "flowchart"
    SEQUENCE_DIAGRAM = "sequenceDiagram"
    ER_DIAGRAM = "erDiagram"
    CLASS_DIAGRAM = "classDiagram"
    STATE_DIAGRAM = "stateDiagram"
    JOURNEY_DIAGRAM = "journey"


# Diagram type to Mermaid code block language
DIAGRAM_TYPE_TO_LANG = {
    MermaidDiagramType.FLOWCHART: "mermaid",
    MermaidDiagramType.SEQUENCE_DIAGRAM: "mermaid",
    MermaidDiagramType.ER_DIAGRAM: "mermaid",
    MermaidDiagramType.CLASS_DIAGRAM: "mermaid",
    MermaidDiagramType.STATE_DIAGRAM: "mermaid",
    MermaidDiagramType.JOURNEY_DIAGRAM: "mermaid",
}


# Page types that benefit from each diagram type
PAGE_TYPE_TO_DIAGRAM_PREFERENCE = {
    # Overview and architecture benefit from flowchart
    "overview": [MermaidDiagramType.FLOWCHART, MermaidDiagramType.STATE_DIAGRAM],
    "architecture": [MermaidDiagramType.FLOWCHART, MermaidDiagramType.CLASS_DIAGRAM],
    "section": [MermaidDiagramType.FLOWCHART, MermaidDiagramType.STATE_DIAGRAM],
    # Service pages benefit from sequence and flow
    "service": [MermaidDiagramType.SEQUENCE_DIAGRAM, MermaidDiagramType.FLOWCHART],
    # API pages benefit from sequence diagrams
    "api": [MermaidDiagramType.SEQUENCE_DIAGRAM, MermaidDiagramType.FLOWCHART],
    # Data model pages benefit from ER diagrams
    "data": [MermaidDiagramType.ER_DIAGRAM, MermaidDiagramType.CLASS_DIAGRAM],
    # Entity pages benefit from ER and class diagrams
    "entity": [MermaidDiagramType.ER_DIAGRAM, MermaidDiagramType.CLASS_DIAGRAM],
    # Ops pages benefit from flowcharts
    "ops": [MermaidDiagramType.FLOWCHART, MermaidDiagramType.STATE_DIAGRAM],
    # Development guides benefit from flowcharts
    "development": [MermaidDiagramType.FLOWCHART, MermaidDiagramType.JOURNEY_DIAGRAM],
}


# ============================================================================
# DIAGRAM PLAN AND EVIDENCE
# ============================================================================


@dataclass
class DiagramNode:
    """A node in a Mermaid diagram."""

    id: str
    label: str
    shape: str | None = None  # e.g., "round", "circle", "diamond"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagramEdge:
    """An edge/arrow in a Mermaid diagram."""

    from_node: str
    to_node: str
    label: str | None = None
    style: str | None = None  # e.g., "==>\" for thick arrow


@dataclass
class DiagramPlan:
    """Plan for generating a Mermaid diagram."""

    diagram_id: str
    diagram_type: MermaidDiagramType
    title: str
    description: str | None = None

    # For flowchart
    nodes: list[DiagramNode] = field(default_factory=list)
    edges: list[DiagramEdge] = field(default_factory=list)

    # For sequence diagram
    sequence_participants: list[str] = field(default_factory=list)
    sequence_messages: list[tuple[str, str, str]] = field(
        default_factory=list
    )  # (from, to, message)

    # For ER diagram
    er_entities: list[dict[str, Any]] = field(
        default_factory=list
    )  # {entity, attributes, primary_key}
    er_relationships: list[tuple[str, str, str]] = field(
        default_factory=list
    )  # (left, right, label)

    # For class diagram
    class_definitions: list[dict[str, Any]] = field(default_factory=list)

    # Source evidence backing this diagram
    evidence_spans: list[EvidenceSpanRecord] = field(default_factory=list)

    # Rendered mermaid code (populated after rendering)
    rendered_diagram: str | None = None


# ============================================================================
# MERMAID SYNTAX VALIDATOR
# ============================================================================


class MermaidSyntaxError(Exception):
    """Raised when Mermaid syntax is invalid."""

    pass


def validate_mermaid_syntax(
    diagram_code: str, diagram_type: MermaidDiagramType
) -> tuple[bool, str]:
    """Validate Mermaid diagram syntax.

    Args:
        diagram_code: The Mermaid diagram code (without ```mermaid wrapper)
        diagram_type: Type of diagram

    Returns:
        (is_valid, error_message) tuple
    """
    if not diagram_code or not diagram_code.strip():
        return False, "Diagram code is empty"

    errors: list[str] = []

    # Common validation for all diagram types
    lines = diagram_code.strip().split("\n")

    if diagram_type == MermaidDiagramType.FLOWCHART:
        errors.extend(_validate_flowchart_syntax(diagram_code, lines))
    elif diagram_type == MermaidDiagramType.SEQUENCE_DIAGRAM:
        errors.extend(_validate_sequence_syntax(diagram_code, lines))
    elif diagram_type == MermaidDiagramType.ER_DIAGRAM:
        errors.extend(_validate_er_syntax(diagram_code, lines))
    elif diagram_type == MermaidDiagramType.CLASS_DIAGRAM:
        errors.extend(_validate_class_syntax(diagram_code, lines))
    elif diagram_type == MermaidDiagramType.STATE_DIAGRAM:
        errors.extend(_validate_state_syntax(diagram_code, lines))

    reserved = _reserved_mermaid_ids(diagram_code)
    if reserved:
        errors.append("Reserved Mermaid node id: " + ", ".join(sorted(reserved)))

    if errors:
        return False, "; ".join(errors[:3])  # Limit to first 3 errors

    return True, "Valid"


_MERMAID_NODE_START_RE = re.compile(r"(?m)^\s*([A-Za-z][A-Za-z0-9_]*)\s*(\[|\()")
_MERMAID_ARROW = "-" + "->"


def _reserved_mermaid_ids(diagram_code: str) -> set[str]:
    found: set[str] = set()
    for line in (diagram_code or "").splitlines():
        start = _MERMAID_NODE_START_RE.match(line)
        if start and start.group(1).casefold() in _MERMAID_RESERVED_IDS:
            found.add(start.group(1))
        if _MERMAID_ARROW not in line:
            continue
        left, _sep, right = line.partition(_MERMAID_ARROW)
        left_id = re.search(r"([A-Za-z][A-Za-z0-9_]*)\s*$", left)
        right_id = re.match(r"\s*([A-Za-z][A-Za-z0-9_]*)", right)
        for match in (left_id, right_id):
            if match and match.group(1).casefold() in _MERMAID_RESERVED_IDS:
                found.add(match.group(1))
    return found


def _validate_flowchart_syntax(code: str, lines: list[str]) -> list[str]:
    """Validate flowchart syntax."""
    errors = []

    # Check for proper direction indicator
    has_direction = any(
        re.match(r"^\s*(flowchart\s+[BTLR][R]?\s*|graph\s+[BTLR][R]?)", line) for line in lines
    )
    if not has_direction:
        # Also check for simple graph direction
        has_direction = any(re.match(r"^\s*(graph\s+[TDLR]\s*)", line) for line in lines)
    if not has_direction:
        errors.append("Flowchart missing direction (TD/BT/LR/RL)")

    # Check for node definitions (format: A[...] or A([...]) etc.)
    node_pattern = re.compile(r"^\s*([A-Za-z0-9_]+)(\[|\(|\{|\<|[\|])")
    has_nodes = any(node_pattern.match(line) for line in lines)

    # Alternative: edges can also define nodes implicitly
    edge_pattern = re.compile(r"^\s*([A-Za-z0-9_]+)\s*[-.]+[>=]")
    has_edges = any(edge_pattern.match(line) for line in lines)
    has_implicit_nodes = any(edge_pattern.match(line) for line in lines)

    if not has_nodes and not has_implicit_nodes and len(lines) > 1:
        errors.append("Flowchart has no visible node definitions")

    # Check for balanced brackets in node definitions
    for line in lines:
        # Skip direction and comment lines
        if line.strip().startswith("flowchart") or line.strip().startswith("graph"):
            continue
        if line.strip().startswith("%%"):
            continue

        # Count bracket balance
        open_brackets = line.count("[") + line.count("(") + line.count("{")
        close_brackets = line.count("]") + line.count(")") + line.count("}")

        if open_brackets != close_brackets:
            # Only warn if line has both types
            if open_brackets > 0 or close_brackets > 0:
                errors.append(f"Unbalanced brackets in: {line[:50]}")
                break

    return errors


def _validate_sequence_syntax(code: str, lines: list[str]) -> list[str]:
    """Validate sequence diagram syntax."""
    errors = []

    # Check for sequenceDiagram header
    has_header = any(re.match(r"^\s*sequenceDiagram\s*$", line) for line in lines)
    if not has_header:
        errors.append("Sequence diagram missing 'sequenceDiagram' header")

    # Check for participant declarations
    participant_pattern = re.compile(r"^\s*participant\s+")
    has_participants = any(participant_pattern.match(line) for line in lines)
    if not has_participants:
        errors.append("Sequence diagram has no participant declarations")

    # Check for message arrows (format: A->>B or A->B)
    message_pattern = re.compile(r"^\s*([A-Za-z0-9_]+)\s*[-.]+[>x-]", re.IGNORECASE)
    has_messages = any(message_pattern.match(line) for line in lines)
    if not has_messages:
        errors.append("Sequence diagram has no message arrows")

    return errors


def _validate_er_syntax(code: str, lines: list[str]) -> list[str]:
    """Validate ER diagram syntax."""
    errors = []

    # Check for erDiagram header
    has_header = any(re.match(r"^\s*erDiagram\s*$", line) for line in lines)
    if not has_header:
        errors.append("ER diagram missing 'erDiagram' header")

    # Check for entity declarations
    entity_pattern = re.compile(r"^\s*([A-Za-z0-9_]+)\s*\{", re.IGNORECASE)
    has_entities = any(entity_pattern.match(line) for line in lines)
    if not has_entities:
        errors.append("ER diagram has no entity declarations")
    if re.search(r"\{[A-Za-z0-9_]*\{", code) or "{id}" in code:
        errors.append("ER attribute names must not contain braces")

    return errors


def _validate_class_syntax(code: str, lines: list[str]) -> list[str]:
    """Validate class diagram syntax."""
    errors = []

    # Check for classDiagram header
    has_header = any(re.match(r"^\s*classDiagram\s*$", line) for line in lines)
    if not has_header:
        errors.append("Class diagram missing 'classDiagram' header")

    # Check for class declarations
    class_pattern = re.compile(r"^\s*class\s+", re.IGNORECASE)
    has_classes = any(class_pattern.match(line) for line in lines)
    if not has_classes:
        errors.append("Class diagram has no class declarations")

    return errors


def _validate_state_syntax(code: str, lines: list[str]) -> list[str]:
    """Validate state diagram syntax."""
    errors = []

    # Check for stateDiagram header (accept variants like stateDiagram-v2)
    has_header = any(
        re.match(r"^\s*stateDiagram[-a-z0-9]*\s*", line, re.IGNORECASE) for line in lines
    )
    if not has_header:
        errors.append("State diagram missing 'stateDiagram' header")

    # Check for state definitions or transitions
    state_pattern = re.compile(r"^\s*state\s+", re.IGNORECASE)
    has_states = any(state_pattern.match(line) for line in lines)
    has_transitions = any(_MERMAID_ARROW in line and "[" in line for line in lines)
    if not has_states and not has_transitions:
        errors.append("State diagram has no state definitions or transitions")

    return errors


def _module_name_and_path(module: Any, index: int) -> tuple[str, str]:
    if isinstance(module, dict):
        return str(module.get("name") or f"module_{index}"), str(module.get("path") or "")
    return str(module), ""


def _is_full_architecture_page(page_id: str) -> bool:
    pid = (page_id or "").lower().rsplit("/", 1)[-1]
    return pid in {"architecture-overview", "project-overview", "overview", "architecture"}


def _module_label(module: Any, index: int = 0) -> str:
    name, path = _module_name_and_path(module, index)
    parts = [part for part in path.replace("\\", "/").strip("/").split("/") if part]
    if len(parts) >= 2 and parts[0] in {"internal", "pkg", "cmd"}:
        return "/".join(parts[:2])
    return name


def _import_edges_from_context(context: dict[str, Any]) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    raw = context.get("import_edges") or []
    for item in raw:
        src = dst = ""
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            src, dst = str(item[0]), str(item[1])
        elif isinstance(item, dict):
            src = str(item.get("from") or item.get("source") or "")
            dst = str(item.get("to") or item.get("target") or "")
        if src and dst and src != dst and (src, dst) not in seen:
            seen.add((src, dst))
            edges.append((src, dst))
    if edges:
        return edges
    labels = set(_product_module_labels(context.get("modules") or []))
    for index, module in enumerate(context.get("modules") or []):
        if not isinstance(module, dict):
            continue
        src_labels = _product_module_labels([module])
        src = src_labels[0] if src_labels else _module_label(module, index)
        if not src:
            continue
        for dep in module.get("depends_on") or []:
            dep_s = str(dep)
            dst = dep_s
            if dst not in labels:
                matches = [
                    label for label in labels if label.endswith("/" + dep_s) or label == dep_s
                ]
                if len(matches) != 1:
                    continue
                dst = matches[0]
            if src != dst and (src, dst) not in seen:
                seen.add((src, dst))
                edges.append((src, dst))
    return edges


def _product_module_labels(modules: list[Any]) -> list[str]:
    """Return scanned product packages, not __init__.py / main.go filename dumps."""
    labels: list[str] = []
    seen: set[str] = set()
    for index, module in enumerate(modules):
        name, path = _module_name_and_path(module, index)
        parts = [part for part in path.replace("\\", "/").strip("/").split("/") if part]
        candidates: list[str] = []
        if len(parts) >= 2 and parts[0] in {"internal", "pkg", "cmd"}:
            candidates.append("/".join(parts[:2]))
        elif (
            len(parts) >= 3
            and parts[0] == "app"
            and parts[1] == "api"
            and not _is_filename_like_module_name(parts[2])
        ):
            candidates.append("/".join(parts[:3]))
        elif len(parts) >= 2 and parts[0] == "app" and not _is_filename_like_module_name(parts[1]):
            candidates.append("/".join(parts[:2]))
        elif name and not _is_filename_like_module_name(name):
            candidates.append(name)
        elif len(parts) >= 2:
            parent = parts[-2]
            if parent and not _is_filename_like_module_name(parent):
                candidates.append(parent)
        for label in candidates:
            if label not in seen:
                seen.add(label)
                labels.append(label)
    return labels


def _iter_snapshot_paths(context: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for module in context.get("modules") or []:
        if isinstance(module, dict):
            paths.append(str(module.get("path") or ""))
    for model in context.get("data_models") or []:
        if isinstance(model, dict):
            paths.append(str(model.get("file_path") or ""))
    for endpoint in context.get("endpoints") or []:
        if isinstance(endpoint, dict):
            paths.append(str(endpoint.get("file_path") or ""))
    for item in context.get("key_directories") or []:
        paths.append(str(item))
    for item in context.get("snapshot_paths") or []:
        paths.append(str(item))
    return [path for path in paths if path]


def _snapshot_contains_path(paths: list[str], target: str) -> bool:
    needle = target.strip("/").replace("\\", "/")
    for path in paths:
        normalized = path.replace("\\", "/").strip("/")
        if not normalized:
            continue
        if normalized == needle or normalized.startswith(f"{needle}/"):
            return True
        if "/" not in needle and normalized.split("/")[0] == needle:
            return True
    return False


def _wiki_tool_layers_present(context: dict[str, Any]) -> list[tuple[str, str]]:
    paths = _iter_snapshot_paths(context)
    layers: list[tuple[str, str]] = []
    for layer_id, layer_label in _WIKI_TOOL_LAYERS:
        if _snapshot_contains_path(paths, layer_label):
            layers.append((layer_id, layer_label))
    return layers


# ============================================================================
# MERMAID PLANNER
# ============================================================================


class MermaidPlanner:
    """Plans Mermaid diagrams for wiki pages based on page type and evidence.

    The planner decides:
    1. Which diagram type is most appropriate for the page
    2. What content should go in the diagram
    3. Which evidence spans back the diagram elements
    """

    def __init__(self, workspace_root: str | None = None) -> None:
        self.workspace_root = workspace_root

    def plan_diagram_for_page(
        self,
        page_id: str,
        page_type: str,
        evidence_binding: PageEvidenceBinding | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[DiagramPlan]:
        """Plan diagrams for a wiki page.

        Args:
            page_id: Unique page identifier
            page_type: Page type string (e.g., "overview", "api", "data")
            evidence_binding: Evidence binding with candidates
            context: Additional context (modules, endpoints, etc.)

        Returns:
            List of DiagramPlan objects for this page
        """
        diagrams: list[DiagramPlan] = []
        context = context or {}

        # Get preferred diagram types for this page type
        preferred_types = PAGE_TYPE_TO_DIAGRAM_PREFERENCE.get(
            page_type, [MermaidDiagramType.FLOWCHART]
        )

        # Plan based on page type
        if page_type == "security":
            auth = self._plan_auth_flow_diagram(page_id, evidence_binding, context)
            if auth:
                diagrams.append(auth)
        elif page_type == "architecture" or (
            page_type == "overview" and _is_full_architecture_page(page_id)
        ):
            diagram = self._plan_overview_architecture_diagram(page_id, evidence_binding, context)
            if diagram:
                diagrams.append(diagram)

        elif page_type in ("service", "section"):
            diagram = self._plan_service_diagram(page_id, evidence_binding, context)
            if diagram:
                diagrams.append(diagram)

        elif page_type == "api":
            diagrams.extend(self.plan_api_diagrams(page_id, evidence_binding, context))

        elif page_type in ("data", "entity"):
            diagram = self._plan_data_model_diagram(page_id, evidence_binding, context)
            if diagram:
                diagrams.append(diagram)

        elif page_type == "ops":
            diagram = self._plan_ops_diagram(page_id, evidence_binding, context)
            if diagram:
                diagrams.append(diagram)

        return diagrams

    def _plan_overview_architecture_diagram(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        """Plan architecture/overview flowchart from import-derived package edges."""
        labels = _product_module_labels(context.get("modules") or [])
        import_edges = _import_edges_from_context(context)
        tokens = _page_tokens(page_id)
        scoped = [
            label
            for label in labels
            if tokens
            and any(
                token in label.lower().replace("/", "-") or token in label.lower()
                for token in tokens
            )
        ]
        if not _is_full_architecture_page(page_id):
            if not scoped:
                return None
            labels = scoped
        preferred = {
            label
            for label in labels
            if any(
                token in label
                for token in (
                    "repository",
                    "services",
                    "probe",
                    "exporter",
                    "agent",
                    "models",
                    "control",
                    "routes",
                )
            )
        }
        connected = {src for src, dst in import_edges if src in labels}
        connected.update(dst for src, dst in import_edges if dst in labels)
        if import_edges:
            chosen = [label for label in labels if label in preferred or label in connected]
        else:
            chosen = list(labels)
        if not chosen:
            chosen = [label for label in labels if label.startswith(("internal/", "app/"))]
        nodes = [
            DiagramNode(id=mermaid_ident(label), label=label, shape="rectangle") for label in chosen
        ]
        chosen_set = set(chosen)
        edges: list[DiagramEdge] = []
        seen_edges: set[tuple[str, str]] = set()
        for src, dst in import_edges:
            if src in chosen_set and dst in chosen_set and (src, dst) not in seen_edges:
                seen_edges.add((src, dst))
                edges.append(DiagramEdge(from_node=mermaid_ident(src), to_node=mermaid_ident(dst)))

        for layer_id, layer_label in _wiki_tool_layers_present(context):
            nodes.append(DiagramNode(id=layer_id, label=layer_label, shape="rectangle"))

        evidence_spans = []
        if evidence_binding:
            for candidate in evidence_binding.candidates:
                evidence_spans.append(candidate.span)

        return DiagramPlan(
            diagram_id=f"{page_id}-architecture",
            diagram_type=MermaidDiagramType.FLOWCHART,
            title="Repository Architecture",
            description="Product module architecture",
            nodes=nodes,
            edges=edges,
            evidence_spans=evidence_spans,
        )

    def _plan_auth_flow_diagram(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        import_edges = _import_edges_from_context(context)
        auth_tokens = ("auth", "jwt", "security", "dependenc", "password")
        labels = _product_module_labels(context.get("modules") or [])
        chosen = [label for label in labels if any(token in label.lower() for token in auth_tokens)]
        for path in _iter_snapshot_paths(context):
            low = path.replace("\\", "/").lower()
            if any(token in low for token in auth_tokens):
                label = _package_from_file(path) or python_app_package_label(path)
                if label and label not in chosen:
                    chosen.append(label)
        chosen_set = set(chosen)
        edges: list[DiagramEdge] = []
        seen: set[tuple[str, str]] = set()
        for src, dst in import_edges:
            if src in chosen_set and dst in chosen_set and (src, dst) not in seen:
                seen.add((src, dst))
                edges.append(DiagramEdge(from_node=mermaid_ident(src), to_node=mermaid_ident(dst)))
        if len(edges) < 2:
            return None
        nodes = [
            DiagramNode(id=mermaid_ident(label), label=label, shape="rectangle") for label in chosen
        ]
        evidence_spans = []
        if evidence_binding:
            evidence_spans = [candidate.span for candidate in evidence_binding.candidates]
        return DiagramPlan(
            diagram_id=f"{page_id}-auth-flow",
            diagram_type=MermaidDiagramType.FLOWCHART,
            title="Authentication flow",
            description="Request authentication path",
            nodes=nodes,
            edges=edges,
            evidence_spans=evidence_spans,
        )

    def _plan_service_diagram(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        """Plan service/section flow diagram."""
        nodes = []
        edges: list[DiagramEdge] = []

        labels = _product_module_labels(context.get("modules") or [])
        tokens = _page_tokens(page_id)
        related = [label for label in labels if any(token in label.lower() for token in tokens)]
        import_edges = _import_edges_from_context(context)
        neighbors = set(related)
        for src, dst in import_edges:
            if src in related:
                neighbors.add(dst)
            if dst in related:
                neighbors.add(src)
        chosen = [label for label in labels if label in neighbors][:8]
        if not chosen:
            chosen = related[:8]
        for label in chosen:
            nodes.append(DiagramNode(id=mermaid_ident(label), label=label, shape="rectangle"))
        chosen_set = set(chosen)
        for src, dst in import_edges:
            if src in chosen_set and dst in chosen_set:
                edges.append(DiagramEdge(from_node=mermaid_ident(src), to_node=mermaid_ident(dst)))

        evidence_spans = []
        if evidence_binding:
            for candidate in evidence_binding.candidates:
                evidence_spans.append(candidate.span)

        return DiagramPlan(
            diagram_id=f"{page_id}-service-flow",
            diagram_type=MermaidDiagramType.FLOWCHART,
            title="Service Flow",
            description="Product module relationships",
            nodes=nodes,
            edges=edges,
            evidence_spans=evidence_spans,
        )

    def _plan_api_diagram(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        """Plan primary API sequence diagram (legacy single-plan entrypoint)."""
        plans = self.plan_api_diagrams(page_id, evidence_binding, context)
        return plans[0] if plans else None

    def plan_api_diagrams(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> list[DiagramPlan]:
        """Plan API diagram contract:
        1) endpoint lifecycle sequence diagram
        2) service/controller/repository/entity flowchart
        3) ER diagram when relationship evidence exists
        """
        plans: list[DiagramPlan] = []
        sequence_plan = self._plan_api_sequence_diagram(page_id, evidence_binding, context)
        if sequence_plan:
            plans.append(sequence_plan)
        relation_plan = self._plan_api_relationship_flowchart(page_id, evidence_binding, context)
        if relation_plan:
            plans.append(relation_plan)
        er_plan = self._plan_api_er_diagram(page_id, evidence_binding, context)
        if er_plan:
            plans.append(er_plan)
        return plans

    def _plan_api_sequence_diagram(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        """Map endpoint list/detail/count/parameter retrieval flows into sequence diagram."""
        endpoints = context.get("endpoints", [])

        participants: list[str] = ["Client"]
        messages: list[tuple[str, str, str]] = []
        participants_seen: set[str] = {"Client"}

        def _add_participant(name: str) -> str:
            normalized = mermaid_ident(name.strip() or "API", prefix="api")
            if normalized not in participants_seen:
                participants.append(normalized)
                participants_seen.add(normalized)
            return normalized

        tokens = _page_tokens(page_id)
        selected: list[dict[str, Any]] = []
        for endpoint in endpoints:
            if not isinstance(endpoint, dict):
                continue
            if not _endpoint_matches_page(endpoint, tokens):
                continue
            selected.append(endpoint)
        if not selected:
            general_api = (page_id or "").lower().rsplit("/", 1)[-1] in {
                "api-ref",
                "api-reference",
                "api",
            } or (page_id or "").lower().endswith("api-reference")
            if not general_api:
                return None
            selected = [endpoint for endpoint in endpoints if isinstance(endpoint, dict)]
        if not selected:
            return None

        for endpoint in selected[:16]:
            path = str(endpoint.get("path", "/unknown"))
            method = str(endpoint.get("method", "GET")).upper()
            handler = _endpoint_actor(endpoint)
            target = _add_participant(handler)
            flow_name = f"{method} {path}"
            path_lower = path.lower()

            if "count" in path_lower:
                flow_tag = "count flow"
            elif "param" in path_lower or "query" in path_lower:
                flow_tag = "parameter flow"
            elif path_lower.endswith("}") or "/{" in path_lower or "/:" in path_lower:
                flow_tag = "detail flow"
            else:
                flow_tag = "list flow"

            messages.append(("Client", target, f"{flow_name} ({flow_tag})"))
            messages.append((target, "Client", "response"))

        evidence_spans = []
        if evidence_binding:
            for candidate in evidence_binding.candidates:
                evidence_spans.append(candidate.span)

        return DiagramPlan(
            diagram_id=f"{page_id}-endpoint-lifecycle-sequence",
            diagram_type=MermaidDiagramType.SEQUENCE_DIAGRAM,
            title="Endpoint Lifecycle Sequence",
            description="Endpoint list/detail/count/parameter retrieval flows",
            sequence_participants=participants,
            sequence_messages=messages,
            evidence_spans=evidence_spans,
        )

    def _plan_api_relationship_flowchart(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        """Map real handler/package relationships; skip the generic MVC stencil."""
        endpoints = [item for item in context.get("endpoints") or [] if isinstance(item, dict)]
        tokens = _page_tokens(page_id)
        selected = [item for item in endpoints if _endpoint_matches_page(item, tokens)]
        labels: list[str] = []
        seen: set[str] = set()
        for endpoint in selected:
            raw = str(
                _package_from_file(str(endpoint.get("file_path") or ""))
                or endpoint.get("service")
                or ""
            ).strip()
            if not raw or raw.lower() in _WIKI_PIPELINE_LABELS:
                continue
            if raw not in seen:
                seen.add(raw)
                labels.append(raw)
        import_edges = _import_edges_from_context(context)
        neighbors = set(labels)
        for src, dst in import_edges:
            if src in neighbors:
                neighbors.add(dst)
            if dst in labels:
                neighbors.add(src)
        labels = [label for label in labels if label in neighbors]
        for src, dst in import_edges:
            if src in neighbors and dst not in labels:
                labels.append(dst)
            if dst in neighbors and src not in labels:
                labels.append(src)
        if len(labels) < 2:
            return None
        nodes = [
            DiagramNode(id=mermaid_ident(label, prefix="svc"), label=label, shape="rectangle")
            for label in labels[:8]
        ]
        chosen_set = set(labels[:8])
        edges = [
            DiagramEdge(
                from_node=mermaid_ident(src, prefix="svc"),
                to_node=mermaid_ident(dst, prefix="svc"),
            )
            for src, dst in import_edges
            if src in chosen_set and dst in chosen_set
        ]
        if len(edges) < 2:
            return None

        return DiagramPlan(
            diagram_id=f"{page_id}-service-relationship-flow",
            diagram_type=MermaidDiagramType.FLOWCHART,
            title="Service Relationship Flow",
            description="Service/controller/repository/entity relationship flow",
            nodes=nodes,
            edges=edges,
            evidence_spans=[c.span for c in evidence_binding.candidates]
            if evidence_binding
            else [],
        )

    def _plan_api_er_diagram(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        """Map entity relationships into ER diagram when evidence supports them."""
        if not evidence_binding:
            return None

        relationship_tokens = (
            "relation",
            "relationship",
            "foreign",
            "references",
            "join",
            "关联",
            "关系",
        )
        entity_markers = ("entity", "dto", "model")

        candidates = evidence_binding.candidates
        has_relation_evidence = any(
            any(token in (c.span.span_text or "").lower() for token in relationship_tokens)
            for c in candidates
        )
        if not has_relation_evidence:
            return None

        er_entities: list[dict[str, Any]] = []
        for candidate in candidates[:8]:
            symbol = (candidate.span.symbol or "").strip()
            symbol_lower = symbol.lower()
            if symbol and any(marker in symbol_lower for marker in entity_markers):
                er_entities.append(
                    {
                        "entity": symbol.replace(" ", "_"),
                        "attributes": [],
                        "primary_key": "id",
                    }
                )

        if len(er_entities) < 2:
            return None

        return DiagramPlan(
            diagram_id=f"{page_id}-entity-relationship-er",
            diagram_type=MermaidDiagramType.ER_DIAGRAM,
            title="Entity Relationship Diagram",
            description="Entity relationships inferred from evidence",
            er_entities=er_entities,
            evidence_spans=[c.span for c in candidates],
        )

    def _plan_data_model_diagram(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        """Plan data model ER diagram."""
        models = [item for item in (context.get("data_models") or []) if isinstance(item, dict)]
        product_models = [
            item
            for item in models
            if str(item.get("type") or "")
            in {
                "",
                "go_gorm",
                "go_struct_db",
                "python_class",
                "ts_definition",
                "jvm_class",
                "migration_table",
            }
            and not _is_request_response_schema(item)
        ]
        if any(
            str(item.get("type") or "") in {"go_gorm", "go_struct_db"} for item in product_models
        ):
            product_models = [
                item
                for item in product_models
                if str(item.get("type") or "") in {"go_gorm", "go_struct_db"}
            ]
        elif any(str(item.get("type") or "") == "migration_table" for item in product_models):
            product_models = [
                item
                for item in product_models
                if str(item.get("type") or "") == "migration_table"
                or (
                    str(item.get("type") or "") == "python_class"
                    and "models/domain" in str(item.get("file_path") or "").replace("\\", "/")
                )
            ]

        er_entities = []
        seen_names: set[str] = set()
        relationships: list[tuple[str, str, str]] = []
        for model in product_models[:12]:
            entity_name = mermaid_er_field(
                str(model.get("name") or model.get("table") or "unknown")
            )
            if entity_name.lower() in seen_names:
                continue
            seen_names.add(entity_name.lower())
            attr_types = [str(item) for item in (model.get("attribute_types") or [])]
            attributes = []
            for index, item in enumerate(model.get("attributes") or []):
                name = mermaid_er_field(str(item))
                if not name:
                    continue
                raw_type = attr_types[index] if index < len(attr_types) else "string"
                attributes.append({"name": name, "type": _mermaid_scalar_type(raw_type)})
            primary_key = mermaid_er_field(str(model.get("primary_key") or "")) or ""
            er_entities.append(
                {
                    "entity": entity_name,
                    "attributes": attributes,
                    "primary_key": primary_key,
                    "file_path": str(model.get("file_path") or ""),
                }
            )
            for target in model.get("relationships") or []:
                raw = str(target)
                kind, sep, dest = raw.partition(":")
                if not sep:
                    dest, kind = kind, "belongs_to"
                dest_name = mermaid_er_field(dest)
                if not dest_name:
                    continue
                if kind == "has_many":
                    edge = (entity_name, dest_name, "fk")
                else:
                    edge = (dest_name, entity_name, "fk")
                if edge[0] == edge[1] and kind != "belongs_to":
                    continue
                if edge in relationships:
                    continue
                relationships.append(edge)

        if not er_entities:
            return None

        evidence_spans = []
        if evidence_binding:
            for candidate in evidence_binding.candidates:
                evidence_spans.append(candidate.span)

        return DiagramPlan(
            diagram_id=f"{page_id}-er-diagram",
            diagram_type=MermaidDiagramType.ER_DIAGRAM,
            title="Data Model",
            description="Entity relationships",
            er_entities=er_entities,
            er_relationships=relationships,
            evidence_spans=evidence_spans,
        )

    def _plan_ops_diagram(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        """Plan ops flowchart."""
        commands = context.get("commands", {})

        nodes = []
        edges = []

        # Add command nodes
        cmd_list = list(commands.items())[:8]
        if cmd_list:
            # Start node
            start_id = mermaid_ident("start", prefix="ops")
            nodes.append(DiagramNode(id=start_id, label="Start", shape="circle"))
            prev_node = start_id
            for cmd, _ in cmd_list:
                cmd_id = mermaid_ident(f"cmd_{cmd}", prefix="ops")
                nodes.append(DiagramNode(id=cmd_id, label=cmd, shape="rectangle"))
                edges.append(DiagramEdge(from_node=prev_node, to_node=cmd_id))
                prev_node = cmd_id
            # End node
            end_id = mermaid_ident("finish", prefix="ops")
            nodes.append(DiagramNode(id=end_id, label="End", shape="circle"))
            edges.append(DiagramEdge(from_node=prev_node, to_node=end_id))

        evidence_spans = []
        if evidence_binding:
            for candidate in evidence_binding.candidates:
                evidence_spans.append(candidate.span)

        return DiagramPlan(
            diagram_id=f"{page_id}-ops-flow",
            diagram_type=MermaidDiagramType.FLOWCHART,
            title="Operations Flow",
            description="Command execution flow",
            nodes=nodes,
            edges=edges,
            evidence_spans=evidence_spans,
        )


# ============================================================================
# MERMAID RENDERER
# ============================================================================


class MermaidRenderer:
    """Renders Mermaid diagram plans to valid Mermaid syntax."""

    def __init__(self) -> None:
        pass

    def render_diagram(self, plan: DiagramPlan) -> str:
        """Render a DiagramPlan to Mermaid syntax string.

        Args:
            plan: DiagramPlan to render

        Returns:
            Mermaid code string (without ```mermaid wrapper)
        """
        if plan.diagram_type == MermaidDiagramType.FLOWCHART:
            return self._render_flowchart(plan)
        elif plan.diagram_type == MermaidDiagramType.SEQUENCE_DIAGRAM:
            return self._render_sequence(plan)
        elif plan.diagram_type == MermaidDiagramType.ER_DIAGRAM:
            return self._render_er(plan)
        elif plan.diagram_type == MermaidDiagramType.CLASS_DIAGRAM:
            return self._render_class(plan)
        elif plan.diagram_type == MermaidDiagramType.STATE_DIAGRAM:
            return self._render_state(plan)
        elif plan.diagram_type == MermaidDiagramType.JOURNEY_DIAGRAM:
            return self._render_journey(plan)
        else:
            return self._render_flowchart(plan)  # Default to flowchart

    def _render_flowchart(self, plan: DiagramPlan) -> str:
        """Render flowchart diagram."""
        lines = ["flowchart TD"]

        # Render nodes
        for node in plan.nodes:
            if node.shape == "circle":
                lines.append(f"    {node.id}(({node.label}))")
            elif node.shape == "diamond":
                lines.append(f"    {node.id}{{{node.label}}}")
            elif node.shape == "rounded" or node.shape == "round":
                lines.append(f"    {node.id}(({node.label}))")
            elif node.shape == "rectangle":
                lines.append(f"    {node.id}[{node.label}]")
            else:
                lines.append(f"    {node.id}[{node.label}]")

        # Render edges
        for edge in plan.edges:
            if edge.style:
                lines.append(f"    {edge.from_node} {edge.style} {edge.to_node}")
            elif edge.label:
                lines.append(f"    {edge.from_node} -->|{edge.label}| {edge.to_node}")
            else:
                lines.append(f"    {edge.from_node} --> {edge.to_node}")

        return "\n".join(lines)

    def _render_sequence(self, plan: DiagramPlan) -> str:
        """Render sequence diagram."""
        lines = ["sequenceDiagram"]

        # Render participants
        for participant in plan.sequence_participants:
            lines.append(f"    participant {participant}")

        # Render messages
        for from_p, to_p, message in plan.sequence_messages:
            lines.append(f"    {from_p}->>+{to_p}: {message}")
            lines.append(f"    {to_p}-->>-{from_p}: response")

        return "\n".join(lines)

    def _render_er(self, plan: DiagramPlan) -> str:
        """Render ER diagram."""
        lines = ["erDiagram"]

        for entity in plan.er_entities:
            entity_name = mermaid_er_field(str(entity.get("entity") or "Unknown"))
            attributes = entity.get("attributes") or []
            primary_key = mermaid_er_field(str(entity.get("primary_key") or ""))
            lines.append(f"    {entity_name} {{")
            seen: set[str] = set()
            if primary_key:
                pk_type = "string"
                for attr in attributes:
                    if (
                        isinstance(attr, dict)
                        and mermaid_er_field(str(attr.get("name") or "")) == primary_key
                    ):
                        pk_type = _mermaid_scalar_type(str(attr.get("type") or "string"))
                        break
                lines.append(f"        {pk_type} {primary_key} PK")
                seen.add(primary_key)
            for attr in attributes[:8]:
                if isinstance(attr, dict):
                    field = mermaid_er_field(str(attr.get("name") or ""))
                    field_type = _mermaid_scalar_type(str(attr.get("type") or "string"))
                else:
                    field = mermaid_er_field(str(attr))
                    field_type = "string"
                if field in seen:
                    continue
                seen.add(field)
                lines.append(f"        {field_type} {field}")
            lines.append("    }")
        known = {mermaid_er_field(str(entity.get("entity") or "")) for entity in plan.er_entities}
        for rel in plan.er_relationships:
            if len(rel) < 2:
                continue
            left = mermaid_er_field(str(rel[0]))
            right = mermaid_er_field(str(rel[1]))
            label = mermaid_er_field(str(rel[2] if len(rel) > 2 else "fk")) or "fk"
            if left in known and right in known:
                lines.append(f"    {left} ||--o{{ {right} : {label}")

        return "\n".join(lines)

    def _render_class(self, plan: DiagramPlan) -> str:
        """Render class diagram."""
        lines = ["classDiagram"]

        for class_def in plan.class_definitions:
            class_name = class_def.get("name", "Unknown")
            lines.append(f"    class {class_name}")

            # Add methods if present
            methods = class_def.get("methods", [])
            for method in methods:
                lines.append(f"    {class_name} : {method}")

        return "\n".join(lines)

    def _render_state(self, plan: DiagramPlan) -> str:
        """Render state diagram."""
        lines = ["stateDiagram-v2"]
        lines.append("    [*] --> start")

        for node in plan.nodes:
            if node.id not in ("start", "end"):
                lines.append(f"    state {node.id} {{ {node.label} }}")
                lines.append(f"    start --> {node.id}")
                lines.append(f"    {node.id} --> [*]")

        return "\n".join(lines)

    def _render_journey(self, plan: DiagramPlan) -> str:
        """Render journey diagram."""
        lines = ["journey"]
        lines.append("    title TODO")

        for i, node in enumerate(plan.nodes[:5]):
            lines.append(f"    section {node.label}")
            lines.append(f"      {node.id}: {i + 1}")

        return "\n".join(lines)

    def render_diagram_with_validation(self, plan: DiagramPlan) -> tuple[str | None, bool, str]:
        """Render a diagram and validate its syntax.

        Returns:
            (rendered_diagram, is_valid, error_message) tuple
        """
        rendered = self.render_diagram(plan)
        is_valid, error_msg = validate_mermaid_syntax(rendered, plan.diagram_type)

        if is_valid:
            return rendered, True, "Valid"
        else:
            return None, False, error_msg

    def render_diagram_block(self, plan: DiagramPlan) -> str:
        """Render a diagram as a complete Markdown code block.

        Args:
            plan: DiagramPlan to render

        Returns:
            Complete Markdown code block with ```mermaid wrapper
        """
        rendered = self.render_diagram(plan)
        return f"```mermaid\n{rendered}\n```"


# ============================================================================
# FACTORY AND HELPERS
# ============================================================================


def create_planner(workspace_root: str | None = None) -> MermaidPlanner:
    """Create a Mermaid planner.

    Args:
        workspace_root: Optional workspace root for path resolution

    Returns:
        MermaidPlanner instance
    """
    return MermaidPlanner(workspace_root=workspace_root)


def create_renderer() -> MermaidRenderer:
    """Create a Mermaid renderer.

    Returns:
        MermaidRenderer instance
    """
    return MermaidRenderer()


def plan_and_render_diagram(
    page_id: str,
    page_type: str,
    evidence_binding: PageEvidenceBinding | None = None,
    context: dict[str, Any] | None = None,
    workspace_root: str | None = None,
) -> tuple[str | None, bool, str]:
    """Plan and render a diagram for a wiki page.

    This is a convenience function that combines planning and rendering
    with syntax validation.

    Args:
        page_id: Unique page identifier
        page_type: Page type string
        evidence_binding: Evidence binding with candidates
        context: Additional context
        workspace_root: Optional workspace root

    Returns:
        (rendered_diagram, is_valid, error_message) tuple
    """
    planner = create_planner(workspace_root)
    renderer = create_renderer()

    diagrams = planner.plan_diagram_for_page(page_id, page_type, evidence_binding, context)

    if not diagrams:
        return None, False, "No diagram could be planned for this page type"

    # Render first diagram
    plan = diagrams[0]
    return renderer.render_diagram_with_validation(plan)


def link_diagram_to_evidence(
    diagram_plan: DiagramPlan,
    evidence_binding: PageEvidenceBinding | None,
) -> DiagramPlan:
    """Link a diagram plan to evidence spans.

    Args:
        diagram_plan: Diagram plan to update
        evidence_binding: Evidence binding with candidates

    Returns:
        Updated diagram plan with evidence links
    """
    if not evidence_binding:
        return diagram_plan

    existing_digests = {span.digest for span in diagram_plan.evidence_spans}
    for candidate in evidence_binding.candidates:
        if candidate.span.digest not in existing_digests:
            diagram_plan.evidence_spans.append(candidate.span)
            existing_digests.add(candidate.span.digest)

    return diagram_plan
