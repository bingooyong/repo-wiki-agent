"""Mermaid planner and renderer."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from repo_wiki.evidence.ranking import PageEvidenceBinding
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.planner.rule_first import _is_filename_like_module_name

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
    return text


_SCALAR = {
    "int": "int",
    "int8": "int",
    "int16": "int",
    "int32": "int",
    "int64": "int",
    "uint": "int",
    "uint64": "int",
    "integer": "int",
    "bigint": "int",
    "smallint": "int",
    "float": "float",
    "float32": "float",
    "float64": "float",
    "bool": "bool",
    "boolean": "bool",
    "time": "datetime",
    "datetime": "datetime",
    "timestamp": "datetime",
    "index": "index",
    "unique": "index",
}


def _mermaid_scalar_type(value: str) -> str:
    return _SCALAR.get((value or "").split(".")[-1].lower().lstrip("*[]"), "string")


def _join_key_scalar(name: str, raw_type: str = "") -> str:
    if raw_type:
        return _mermaid_scalar_type(raw_type)
    lowered = (name or "").lower()
    if lowered in {"tag", "name", "slug", "title", "email", "username"}:
        return "string"
    if lowered.endswith("_at"):
        return "timestamp"
    return "int"


_PAGE_SCOPE_ALIASES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("auth", "jwt", "认证", "授权", "安全", "security"),
        ("auth", "jwt", "security", "secrets", "netguard", "audit"),
    ),
    (
        ("前端", "frontend", "web", "frontend-application"),
        ("web", "frontend", "static", "html"),
    ),
    (
        ("核心服务", "core", "service"),
        ("services", "repository", "exporter", "api", "routes"),
    ),
    (("python", "python-service"), ("services", "api", "/api/")),
    (("agent", "探针", "tunnel"), ("agent", "probe", "tunnel")),
    (("控制", "control", "grpc"), ("control", "grpc", "tunnel")),
    (("部署", "compose", "运维", "ops"), ("deploy", "compose")),
    (("错误", "error", "status"), ("error", "exception", "handler")),
    (("system-components", "system", "组件"), ("cmd", "control", "services")),
    (
        ("module-relationships", "module", "模块"),
        ("control", "services", "repository"),
    ),
    (
        ("data-flow", "数据流", "调用链"),
        ("services", "repository", "exporter"),
    ),
    (
        ("event-architecture", "event", "事件"),
        ("control", "agent"),
    ),
    (("database-schema", "数据库架构", "数据迁移"), ("migration", "models")),
)


def _page_tokens(page_id: str) -> set[str]:
    return {part for part in re.split(r"[-_/]", (page_id or "").lower()) if len(part) >= 3}


_GENERIC_SCOPE_TOKENS = frozenset(
    {
        "api",
        "ref",
        "reference",
        "overview",
        "page",
        "docs",
        "wiki",
        "service",
        "application",
    }
)


def _page_scope_needles(page_id: str) -> set[str]:
    tokens = set(_page_tokens(page_id))
    blob = (page_id or "").lower()
    for keys, aliases in _PAGE_SCOPE_ALIASES:
        if any(key in blob for key in keys) or tokens & set(keys):
            tokens.update(aliases)
    return tokens


def _specific_page_scope_needles(page_id: str) -> set[str]:
    """Page tokens that can scope a route list without matching every /api path."""
    return {token for token in _page_scope_needles(page_id) if token not in _GENERIC_SCOPE_TOKENS}


def _endpoint_matches_page(endpoint: dict[str, Any], tokens: set[str]) -> bool:
    if not tokens:
        return True
    hay = " ".join(
        str(endpoint.get(key) or "") for key in ("path", "file_path", "service", "handler")
    ).lower()
    return any(token in hay for token in tokens)


def _endpoint_is_anonymous(endpoint: dict[str, Any]) -> bool:
    path = str(endpoint.get("path") or "").rstrip("/")
    method = str(endpoint.get("method") or "").upper()
    auth = str(endpoint.get("auth_type") or endpoint.get("auth") or "").lower()
    file_path = str(endpoint.get("file_path") or "").replace("\\", "/")
    if auth in {"none", "anonymous", "public"}:
        return True
    from repo_wiki.generator.process_roles import path_looks_like_example_cmd

    if path_looks_like_example_cmd(file_path):
        return True
    if path in {"/healthz", "/health", "/readyz", "/ready", "/live"}:
        return True
    if method == "POST" and any(
        token in path.lower() for token in ("/login", "/register", "/signup", "/signin")
    ):
        return True
    return False


def load_route_method_table(root: Path | None) -> dict[str, str]:
    if root is None:
        return {}
    from repo_wiki.generator.deterministic_sections import load_route_method_table as _load

    return _load(root)


def frontend_fetch_paths(root: Path | None) -> list[str]:
    if root is None:
        return []
    found: list[str] = []
    fetch_re = re.compile(r"""fetch\(\s*['"](/[^'"]+)['"]""")
    for base in (root / "web", root / "static"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.suffix.lower() not in {".js", ".ts", ".html", ".go", ".vue"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            found.extend(fetch_re.findall(text))
    return list(dict.fromkeys(found))


def _honest_method_path(endpoint: dict[str, Any], root: Path | None = None) -> tuple[str, str]:
    path = str(endpoint.get("path") or "").strip()
    method = str(endpoint.get("method") or "").upper()
    table = load_route_method_table(root)
    if path in table:
        method = table[path]
    if not path:
        return "", ""
    return method or "GET", path


def _discover_auth_header_label(root: Path | None) -> str:
    """First documented auth header in source; no sample-repo default."""
    if root is None:
        return "Authorization"
    header_re = re.compile(r"""['"]((?:X-[A-Za-z0-9-]*Token)|Authorization)['"]""")
    skip = {".git", ".repo-agent-eval", "vendor", "node_modules", "__pycache__"}
    found: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".go", ".py"}:
            continue
        if any(part in skip for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in header_re.finditer(text):
            token = match.group(1)
            if token not in found:
                found.append(token)
    preferred = [item for item in found if item.startswith("X-")]
    return (preferred or found or ["Authorization"])[0]


def _discover_auth_node_label(root: Path | None, *, python: bool) -> str:
    """Auth hop name from source symbols; no sample-repo default."""
    if root is None:
        return "Auth"
    skip = {".git", ".repo-agent-eval", "vendor", "node_modules", "__pycache__"}
    go_re = re.compile(r"\bfunc\s+(\w*Auth\w*)\(")
    py_re = re.compile(r"\bdef\s+(\w*(?:auth|authorizer)\w*)\s*\(", re.I)
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".go", ".py"}:
            continue
        if any(part in skip for part in path.parts) or path.name.endswith("_test.go"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if python and path.suffix == ".py":
            match = py_re.search(text)
            if match:
                return match.group(1)
        if not python and path.suffix == ".go":
            match = go_re.search(text)
            if match:
                return match.group(1)
    return "Auth"


def _auth_hop(
    endpoint: dict[str, Any],
    *,
    go_auth: bool,
    py_auth: bool,
    root: Path | None = None,
) -> tuple[str, str] | tuple[None, None]:
    if _endpoint_is_anonymous(endpoint):
        return None, None
    file_path = str(endpoint.get("file_path") or "").replace("\\", "/")
    from repo_wiki.generator.process_roles import path_looks_like_example_cmd

    if path_looks_like_example_cmd(file_path):
        return None, None
    if go_auth:
        return _discover_auth_node_label(root, python=False), _discover_auth_header_label(root)
    if py_auth:
        return _discover_auth_node_label(root, python=True), "Authorization"
    return None, None


def _real_error_node(root: Path | None, endpoint: dict[str, Any]) -> str:
    file_path = str(endpoint.get("file_path") or "")
    if root and (root / "app" / "api" / "errors" / "http_error.py").is_file():
        return "HTTPException"
    try:
        text = Path(file_path).read_text(encoding="utf-8", errors="ignore") if file_path else ""
    except OSError:
        text = ""
    if "writeAdminJSON" in text:
        return "writeAdminJSON"
    if "writeJSON" in text:
        return "writeJSON"
    if root:
        for path in root.rglob("*.go"):
            if path.name.endswith("_test.go"):
                continue
            try:
                blob = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if re.search(r"\bfunc writeJSON\b", blob):
                return "writeJSON"
    return "HTTPException"


_GENERIC_GO_HANDLERS = frozenset(
    {"func", "anonymous", "Handle", "r_GET", "r.GET", "r_POST", "r.POST", "handler"}
)
_FRONTEND_ROUTE_PREFIXES = ("/api", "/web", "/static")


def _request_flow_score(endpoint: dict[str, Any], page_id: str, tokens: set[str]) -> int:
    path = str(endpoint.get("path") or "").lower()
    file_path = str(endpoint.get("file_path") or "").lower()
    hay = f"{path} {file_path} {endpoint.get('service') or ''} {endpoint.get('handler') or ''}"
    leaf = (page_id or "").lower()
    score = sum(3 for token in tokens if token in hay)
    if "agent" in leaf and "healthz" in path:
        score += 6
    if any(token in leaf for token in ("frontend", "前端", "web")):
        if "web" in path or "static" in hay:
            score += 6
        if any(path.startswith(prefix) for prefix in _FRONTEND_ROUTE_PREFIXES):
            score += 8
        from repo_wiki.generator.process_roles import path_looks_like_example_cmd

        if path_looks_like_example_cmd(file_path):
            score -= 12
        if "agent/list" in path:
            score -= 8
    if any(token in leaf for token in ("auth", "认证", "login")):
        if "login" in path or "auth" in file_path:
            score += 5
        if any(token in path.lower() for token in ("login", "register", "signup")):
            score += 4
    return score


_PY_APP_IMPORT_RE = re.compile(
    r"(?m)^\s*(?:from\s+(app(?:\.[A-Za-z_][\w]*)*)\s+import|import\s+(app(?:\.[A-Za-z_][\w]*)*))"
)


def python_app_package_label(path_or_module: str) -> str:
    """Map a Python route/module path to a package label."""
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
    "dto",
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
    """Actor for this route, scoped to the owning binary/file — never another mux."""
    file_path = str(endpoint.get("file_path") or "").replace("\\", "/")
    handler = str(endpoint.get("handler") or endpoint.get("service") or "").strip()
    path = str(endpoint.get("path") or "")
    if "control" in file_path and "cmd/" in file_path:
        if handler and handler not in _GENERIC_GO_HANDLERS and "NewHTTPHandler" not in handler:
            return handler
        return "runGRPCServe"
    from repo_wiki.generator.process_roles import cmd_dir_name, path_looks_like_example_cmd

    example_name = cmd_dir_name(file_path)
    if path_looks_like_example_cmd(file_path):
        if path.rstrip("/") in {"", "/"}:
            return example_name or "example"
        if path.rstrip("/") in {"/health", "/healthz"}:
            return "HealthHandler"
        leaf = handler.split(".")[-1] if handler else ""
        if leaf and leaf not in _GENERIC_GO_HANDLERS:
            return leaf
        return example_name or "example"
    if "internal/agent" in file_path or (
        cmd_dir_name(file_path) and "agent" in cmd_dir_name(file_path)
    ):
        if handler and handler not in _GENERIC_GO_HANDLERS:
            return handler
        return "NewHTTPHandler"
    if handler and handler not in _GENERIC_GO_HANDLERS:
        return handler
    name = file_path.rsplit("/", 1)[-1]
    if "." in name:
        return name.rsplit(".", 1)[0]
    return _package_from_file(file_path) or "API"


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


class MermaidSyntaxError(Exception):
    """Raised when Mermaid syntax is invalid."""

    pass


def validate_mermaid_syntax(
    diagram_code: str, diagram_type: MermaidDiagramType
) -> tuple[bool, str]:
    """Validate Mermaid diagram syntax. Returns (is_valid, error_message)."""
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
    pid = (page_id or "").lower()
    leaf = pid.rsplit("/", 1)[-1]
    return (
        leaf
        in {
            "architecture-overview",
            "architecture",
            "整体架构概览",
        }
        or "architecture-overview" in pid
        or "整体架构概览" in pid
    )


def _architecture_prefer_tokens(page_id: str) -> tuple[str, ...] | None:
    pid = (page_id or "").lower()
    if any(token in pid for token in ("event", "事件")):
        return ("control", "agent", "cmd/")
    if any(token in pid for token in ("data-flow", "数据流", "调用链")):
        return ("services", "repository", "exporter", "db")
    if any(token in pid for token in ("module", "模块")):
        return ("control", "services", "repository", "api", "models")
    if any(token in pid for token in ("system", "组件")):
        return ("cmd/", "api", "core", "control", "services")
    return None


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


_OVERVIEW_NODE_CAP = 12
_OVERVIEW_SKIP_PARTS = frozenset({"__init__.py", "tests", "test", "docs", "scripts"})
_OVERVIEW_COMPOSE_LABELS = frozenset({"app", "db", "mysql", "blackbox", "postgres"})


def _overview_node_id(label: str) -> str:
    """Prefix+suffix so node ids never collide with compose `app[` / `db[` labels."""
    return f"ovw_{mermaid_ident(label)}_n"


def _overview_package_label(raw: str) -> str | None:
    text = (raw or "").strip().replace("\\", "/")
    if not text or text in _OVERVIEW_SKIP_PARTS:
        return None
    parts = [part for part in text.split("/") if part and part not in _OVERVIEW_SKIP_PARTS]
    if not parts:
        return None
    leaf = parts[-1]
    if leaf.endswith(("_test.go", "_test.py")):
        parts = parts[:-1]
        if not parts:
            return None
        leaf = parts[-1]
    if _is_filename_like_module_name(leaf):
        parts = parts[:-1]
        if not parts:
            return None
    label = ""
    if (parts[0] in {"cmd", "internal", "pkg"} and len(parts) >= 2) or (
        parts[0] == "app" and len(parts) >= 2 and not _is_filename_like_module_name(parts[1])
    ):
        label = "/".join(parts[:2])
    elif parts[0] in {"cmd", "internal", "web"} and len(parts) == 1:
        label = parts[0]
    else:
        return None
    if label in _OVERVIEW_COMPOSE_LABELS:
        return None
    return label


def _overview_package_graph(context: dict[str, Any]) -> tuple[list[str], list[tuple[str, str]]]:
    seen: set[str] = set()
    counts: dict[str, int] = {}
    raw_edges: list[tuple[str, str]] = []

    def _touch(label: str) -> None:
        if label not in seen:
            seen.add(label)
            counts[label] = 0

    for index, module in enumerate(context.get("modules") or []):
        name, path = _module_name_and_path(module, index)
        label = _overview_package_label(path or name)
        if label:
            _touch(label)
        if isinstance(module, dict):
            for dest in module.get("depends_on") or module.get("dependencies") or []:
                other = _overview_package_label(str(dest))
                if label and other and label != other:
                    raw_edges.append((label, other))
                    _touch(other)
    for src, dst in _import_edges_from_context(context):
        left = _overview_package_label(str(src))
        right = _overview_package_label(str(dst))
        if left and right and left != right:
            raw_edges.append((left, right))
            _touch(left)
            _touch(right)
    for src, dst in raw_edges:
        counts[src] = counts.get(src, 0) + 1
        counts[dst] = counts.get(dst, 0) + 1

    def _rank(label: str) -> tuple[int, int, str]:
        bucket = 3
        if label.startswith("cmd/"):
            bucket = 0
        elif label.startswith("internal/"):
            bucket = 1
        elif label.startswith("app/"):
            bucket = 2
        return (bucket, -counts.get(label, 0), label)

    labels = sorted(seen, key=_rank)[:_OVERVIEW_NODE_CAP]
    keep = set(labels)
    edges = []
    seen_pairs: set[tuple[str, str]] = set()
    for src, dst in raw_edges:
        if src in keep and dst in keep and (src, dst) not in seen_pairs:
            seen_pairs.add((src, dst))
            edges.append((src, dst))
    return labels, edges


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


class MermaidPlanner:
    """Plans Mermaid diagrams for wiki pages."""

    def __init__(self, workspace_root: str | None = None) -> None:
        self.workspace_root = workspace_root

    def plan_diagram_for_page(
        self,
        page_id: str,
        page_type: str,
        evidence_binding: PageEvidenceBinding | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[DiagramPlan]:
        """Plan diagrams for a wiki page."""
        diagrams: list[DiagramPlan] = []
        context = context or {}

        if page_type == "security":
            auth = self._plan_auth_flow_diagram(page_id, evidence_binding, context)
            if auth:
                diagrams.append(auth)
        elif page_type == "overview":
            modules = self._plan_overview_module_flow(page_id, evidence_binding, context)
            if modules:
                diagrams.append(modules)
            else:
                diagram = self._plan_overview_architecture_diagram(
                    page_id, evidence_binding, context
                )
                if diagram:
                    diagrams.append(diagram)
        elif page_type == "architecture":
            diagram = self._plan_overview_architecture_diagram(page_id, evidence_binding, context)
            if diagram:
                diagrams.append(diagram)

        elif page_type in ("service", "section", "development"):
            diagram = self._plan_service_diagram(page_id, evidence_binding, context)
            if diagram:
                diagrams.append(diagram)

        elif page_type == "api":
            diagrams.extend(self.plan_api_diagrams(page_id, evidence_binding, context))
            pid = (page_id or "").lower()
            favorite = self._plan_favorite_follow_sequence(page_id, evidence_binding, context)
            if favorite:
                diagrams.append(favorite)
            request_flow = self._plan_request_flow_sequence(page_id, evidence_binding, context)
            if request_flow:
                diagrams.append(request_flow)
            if any(
                token in pid
                for token in ("auth", "认证", "授权", "jwt", "frontend", "前端", "error", "错误")
            ):
                auth = self._plan_auth_flow_diagram(page_id, evidence_binding, context)
                if auth:
                    diagrams.append(auth)
            if any(token in pid for token in ("auth", "认证", "jwt")):
                jwt = self._plan_jwt_sequence(page_id, evidence_binding, context)
                if jwt:
                    diagrams.append(jwt)

        elif page_type in ("data", "entity"):
            from repo_wiki.generator.deterministic_sections import (
                is_data_model_owner_page,
                is_join_er_owner_page,
            )

            pid = page_id or ""
            schema_page = any(
                token in pid.lower()
                for token in ("database-schema", "数据库架构", "database-architecture")
            )
            satellite = any(
                token in pid.lower()
                for token in (
                    "schema",
                    "database-architecture",
                    "database-migration",
                    "migration",
                    "迁移",
                )
            )
            if schema_page:
                schema = self._plan_database_schema_diagram(page_id, evidence_binding, context)
                if schema:
                    diagrams.append(schema)
                else:
                    diagram = self._plan_data_model_diagram(page_id, evidence_binding, context)
                    if diagram:
                        diagrams.append(diagram)
            elif is_data_model_owner_page(page_id=pid, title="") or not satellite:
                diagram = self._plan_data_model_diagram(page_id, evidence_binding, context)
                if diagram:
                    diagrams.append(diagram)
            if (not schema_page) and is_join_er_owner_page(page_id=pid, title=""):
                keys = self._plan_join_key_diagram(page_id, evidence_binding, context)
                if keys:
                    diagrams.append(keys)
            if any(token in pid.lower() for token in ("migration", "迁移")):
                core = self._plan_data_model_diagram(
                    page_id,
                    evidence_binding,
                    context,
                )
                if core:
                    diagrams.append(core)
                migration = self._plan_migration_flow(page_id, evidence_binding, context)
                if migration:
                    diagrams.append(migration)

        elif page_type == "ops":
            diagram = self._plan_ops_diagram(page_id, evidence_binding, context)
            if diagram:
                diagrams.append(diagram)
            compose = self._plan_compose_topology(page_id, evidence_binding, context)
            if compose:
                diagrams.append(compose)

        if not diagrams and page_type == "api":
            fallback = self._plan_request_flow_sequence(page_id, evidence_binding, context)
            if fallback:
                diagrams.append(fallback)

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
        all_import_edges = list(import_edges)
        if not labels and import_edges:
            labels = sorted(
                {src for src, _dst in import_edges} | {dst for _src, dst in import_edges}
            )
        tokens = _page_scope_needles(page_id)
        scoped = [
            label
            for label in labels
            if tokens
            and any(
                token in label.lower().replace("/", "-") or token in label.lower()
                for token in tokens
            )
        ]
        prefer_tokens = _architecture_prefer_tokens(page_id)
        if not _is_full_architecture_page(page_id):
            if prefer_tokens:
                token_scoped = [
                    label
                    for label in labels
                    if any(token in label.lower() for token in prefer_tokens)
                ]
                if not token_scoped:
                    if len(import_edges) < 2:
                        return None
                    idx = sum(ord(c) for c in (page_id or "x")) % (len(import_edges) - 1)
                    import_edges = import_edges[idx : idx + 2]
                    scoped = sorted(
                        {src for src, _dst in import_edges} | {dst for _src, dst in import_edges}
                    )
                else:
                    scoped = token_scoped
            if not scoped:
                scoped = [label for label in labels if label.startswith(("internal/", "app/"))]
            if not scoped:
                scoped = list(labels)
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
                    "agent",
                    "models",
                    "control",
                    "routes",
                    "domain",
                    "app",
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

        used = {edge.from_node for edge in edges} | {edge.to_node for edge in edges}
        nodes = [node for node in nodes if node.id in used]
        if len(edges) < 2 and len(all_import_edges) >= 2:
            idx = sum(ord(c) for c in (page_id or "x")) % (len(all_import_edges) - 1)
            slice_edges = all_import_edges[idx : idx + 2]
            nodes = [
                DiagramNode(id=mermaid_ident(label), label=label, shape="rectangle")
                for label in sorted(
                    {src for src, _d in slice_edges} | {dst for _s, dst in slice_edges}
                )
            ]
            edges = [
                DiagramEdge(from_node=mermaid_ident(src), to_node=mermaid_ident(dst))
                for src, dst in slice_edges
            ]
        if len(edges) < 1:
            return None
        if not _is_full_architecture_page(page_id) and len(edges) > 12:
            edges = edges[:12]
            used = {edge.from_node for edge in edges} | {edge.to_node for edge in edges}
            nodes = [node for node in nodes if node.id in used]

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
        if len(edges) >= 2:
            nodes = [
                DiagramNode(id=mermaid_ident(label), label=label, shape="rectangle")
                for label in chosen
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
        return self._plan_request_flow_sequence(page_id, evidence_binding, context)

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
        tokens = _page_scope_needles(page_id)
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
        """Catalog-only list/detail/count/parameter flows. Other API pages use request-flow."""
        from repo_wiki.generator.deterministic_sections import is_api_catalog_owner_page

        pid = (page_id or "").lower()
        if not (
            is_api_catalog_owner_page(page_id=page_id or "")
            or pid.endswith("api-reference")
            or pid.rsplit("/", 1)[-1] in {"api-ref", "api-reference", "api"}
        ):
            return None
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

        tokens = _specific_page_scope_needles(page_id)
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
                "api-overview",
            } or (page_id or "").lower().endswith("api-reference")
            typed = [endpoint for endpoint in endpoints if isinstance(endpoint, dict)]
            if general_api:
                selected = typed
        if not selected:
            return None

        for endpoint in selected[:16]:
            path = str(endpoint.get("path", "/unknown"))
            method, path = _honest_method_path(
                {"method": endpoint.get("method", "GET"), "path": path},
                Path(self.workspace_root) if self.workspace_root else None,
            )
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

            route = _add_participant("Route")
            messages.append(("Client", route, f"{flow_name} ({flow_tag})"))
            messages.append((route, target, "dispatch"))
            service = _package_from_file(str(endpoint.get("file_path") or ""))
            if service and service not in {handler, "Client", "Route"}:
                svc = _add_participant(service)
                messages.append((target, svc, "handle"))
        if len(participants) > 6:
            keep = participants[:6]
            participants[:] = keep
            allowed = set(keep)
            messages[:] = [item for item in messages if item[0] in allowed and item[1] in allowed]

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
        tokens = _page_scope_needles(page_id)
        selected = [item for item in endpoints if _endpoint_matches_page(item, tokens)]
        if not selected:
            selected = endpoints[:4]
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
                        "primary_key": "",
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

    def _plan_migration_flow(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        root = Path(self.workspace_root) if self.workspace_root else None
        if root is None:
            return None
        versions = root / "app" / "db" / "migrations" / "versions"
        if not versions.is_dir():
            return None
        files = sorted(path.name for path in versions.glob("*.py"))
        if not files:
            return None
        nodes = [
            DiagramNode(id="alembic_env", label="alembic env.py", shape="rectangle"),
            DiagramNode(id="versions_file", label=files[0][:32], shape="rectangle"),
            DiagramNode(id="tables", label="migration tables", shape="rectangle"),
        ]
        edges = [
            DiagramEdge(from_node="alembic_env", to_node="versions_file"),
            DiagramEdge(from_node="versions_file", to_node="tables"),
        ]
        return DiagramPlan(
            diagram_id=f"{page_id}-migration-flow",
            diagram_type=MermaidDiagramType.FLOWCHART,
            title="Migration flow",
            description="Alembic versions apply table DDL",
            nodes=nodes,
            edges=edges,
            evidence_spans=[c.span for c in evidence_binding.candidates]
            if evidence_binding
            else [],
        )

    def _plan_data_model_diagram(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
        allow_names: set[str] | None = None,
    ) -> DiagramPlan | None:
        """Plan data model ER diagram."""
        models = [item for item in (context.get("data_models") or []) if isinstance(item, dict)]
        if not models:
            root = Path(self.workspace_root) if self.workspace_root else None
            if root is not None:
                from repo_wiki.generator.deterministic_sections import load_alembic_migration_models

                models = load_alembic_migration_models(root)
        if allow_names:
            allowed = {name.lower() for name in allow_names}
            models = [
                item
                for item in models
                if mermaid_er_field(str(item.get("name") or item.get("table") or "")).lower()
                in allowed
            ]
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
                item for item in product_models if str(item.get("type") or "") == "migration_table"
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
            raw_pk = str(model.get("primary_key") or "").strip()
            primary_key = mermaid_er_field(raw_pk) if raw_pk else ""
            extra_pks = [
                mermaid_er_field(str(item))
                for item in (model.get("primary_keys") or [])
                if mermaid_er_field(str(item))
            ]
            er_entities.append(
                {
                    "entity": entity_name,
                    "attributes": attributes,
                    "primary_key": primary_key,
                    "primary_keys": extra_pks,
                    "file_path": str(model.get("file_path") or ""),
                }
            )
            for target in model.get("relationships") or []:
                raw = str(target)
                parts = raw.split(":")
                if len(parts) >= 3:
                    kind, dest, label = parts[0], parts[1], parts[2]
                elif len(parts) == 2:
                    kind, dest, label = parts[0], parts[1], parts[1]
                else:
                    dest, kind, label = raw, "belongs_to", "fk"
                dest_name = mermaid_er_field(dest)
                if not dest_name:
                    continue
                if kind == "has_many":
                    edge = (entity_name, dest_name, mermaid_er_field(label) or "fk")
                else:
                    edge = (dest_name, entity_name, mermaid_er_field(label) or "fk")
                if edge[0] == edge[1] and kind != "belongs_to":
                    continue
                if edge in relationships:
                    continue
                relationships.append(edge)

        have = {item["entity"] for item in er_entities}
        models_by_name = {
            mermaid_er_field(str(item.get("name") or item.get("table") or "")): item
            for item in models
            if isinstance(item, dict)
        }
        for left, right, _label in relationships:
            dest = left if left not in have else (right if right not in have else "")
            if not dest:
                continue
            source = models_by_name.get(dest) or {}
            dest_attrs: list[dict[str, str]] = []
            raw_types = [str(item) for item in (source.get("attribute_types") or [])]
            for index, item in enumerate(source.get("attributes") or []):
                name = mermaid_er_field(str(item))
                if not name:
                    continue
                raw = raw_types[index] if index < len(raw_types) else "string"
                dest_attrs.append({"name": name, "type": _join_key_scalar(name, raw)})
            er_entities.append(
                {
                    "entity": dest,
                    "attributes": dest_attrs,
                    "primary_key": mermaid_er_field(str(source.get("primary_key") or "")),
                    "primary_keys": [
                        mermaid_er_field(str(item))
                        for item in (source.get("primary_keys") or [])
                        if mermaid_er_field(str(item))
                    ],
                }
            )
            have.add(dest)

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
        """Plan ops flowchart from CI jobs only — never an invented start/build/test/lint chain."""
        return self._plan_ci_job_diagram(page_id, evidence_binding, context)

    def _plan_compose_topology(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        root = Path(self.workspace_root) if self.workspace_root else None
        if root is None:
            return None
        text = ""
        for name in (
            "podman-compose.yml",
            "docker-compose.yml",
            "docker-compose.yaml",
            "compose.yml",
        ):
            path = root / name
            if path.is_file():
                text = path.read_text(encoding="utf-8", errors="ignore")
                break
        if not text:
            return None
        from repo_wiki.generator.compose_evidence import parse_compose_topology

        services, depends = parse_compose_topology(text)
        if len(services) < 2 or len(depends) < 1:
            return None
        chosen = {name for name in services[:10]}
        nodes = [
            DiagramNode(id=mermaid_ident(name, prefix="svc"), label=name, shape="rectangle")
            for name in services[:10]
        ]
        edges: list[DiagramEdge] = []
        from repo_wiki.generator.compose_evidence import parse_compose_env_file_edges

        env_edges = parse_compose_env_file_edges(text)
        if env_edges:
            nodes.append(DiagramNode(id="env_file", label=".env", shape="rectangle"))
            for _src, dest in env_edges:
                if dest in chosen:
                    edges.append(
                        DiagramEdge(from_node="env_file", to_node=mermaid_ident(dest, prefix="svc"))
                    )
        for src, dest in depends:
            if src in chosen and dest in chosen and src != dest:
                edges.append(
                    DiagramEdge(
                        from_node=mermaid_ident(src, prefix="svc"),
                        to_node=mermaid_ident(dest, prefix="svc"),
                    )
                )
        if len(edges) < 1:
            return None
        used = {edge.from_node for edge in edges} | {edge.to_node for edge in edges}
        nodes = [node for node in nodes if node.id in used]
        return DiagramPlan(
            diagram_id=f"{page_id}-compose-topology",
            diagram_type=MermaidDiagramType.FLOWCHART,
            title="Compose topology",
            description="Services from compose evidence",
            nodes=nodes,
            edges=edges[:12],
            evidence_spans=[c.span for c in evidence_binding.candidates]
            if evidence_binding
            else [],
        )

    def _plan_overview_module_flow(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        """Top-level package map for 项目概述 — one granularity, no files/tests."""
        labels, raw_edges = _overview_package_graph(context)
        if len(labels) < 2 or not raw_edges:
            return None
        nodes = [
            DiagramNode(id=_overview_node_id(label), label=label, shape="rectangle")
            for label in labels
        ]
        edges = [
            DiagramEdge(from_node=_overview_node_id(src), to_node=_overview_node_id(dst))
            for src, dst in raw_edges
        ]
        return DiagramPlan(
            diagram_id=f"{page_id}-overview-modules",
            diagram_type=MermaidDiagramType.FLOWCHART,
            title="Product modules",
            description="Top-level packages named on the overview page",
            nodes=nodes,
            edges=edges,
            evidence_spans=[c.span for c in evidence_binding.candidates]
            if evidence_binding
            else [],
        )

    def _plan_favorite_follow_sequence(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        pid = (page_id or "").lower()
        if not any(token in pid for token in ("python", "python-service", "python服务")):
            return None
        root = Path(self.workspace_root) if self.workspace_root else None
        if root is None:
            return None
        routes = root / "app" / "api" / "routes"
        mutating: list[Path] = []
        if routes.is_dir():
            for path in sorted(routes.rglob("*.py")):
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if re.search(r"@(?:\w+\.)?(post|delete)\(", text, flags=re.I):
                    mutating.append(path)
        if len(mutating) < 2:
            return None
        participants = ["Client"]
        messages: list[tuple[str, str, str]] = []
        for path in mutating[:8]:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for match in re.finditer(
                r"@(?:\w+\.)?(post|delete|put|get)\(\s*[\"']([^\"']+)[\"']",
                text,
                flags=re.I,
            ):
                method = match.group(1).upper()
                route = match.group(2)
                after = text[match.end() : match.end() + 400]
                func = re.search(r"def\s+([A-Za-z_][A-Za-z0-9_]*)", after)
                if not func:
                    continue
                name = func.group(1)
                if name not in participants:
                    participants.append(name)
                messages.append(("Client", name, f"{method} {route}"))
        if len(messages) < 2:
            return None
        return DiagramPlan(
            diagram_id=f"{page_id}-route-dispatch",
            diagram_type=MermaidDiagramType.SEQUENCE_DIAGRAM,
            title="Route dispatch",
            description="Discovered handlers for mutating routes",
            sequence_participants=participants[:8],
            sequence_messages=messages[:8],
            evidence_spans=[c.span for c in evidence_binding.candidates]
            if evidence_binding
            else [],
        )

    def _plan_database_schema_diagram(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        """Alembic table / FK / index view — not the domain ER copy."""
        models = [item for item in (context.get("data_models") or []) if isinstance(item, dict)]
        if not models:
            root = Path(self.workspace_root) if self.workspace_root else None
            if root is not None:
                from repo_wiki.generator.deterministic_sections import load_alembic_migration_models

                models = load_alembic_migration_models(root)
        tables = [item for item in models if str(item.get("type") or "") in {"", "migration_table"}]
        tables = tables[:8]
        if not tables:
            return None
        er_entities = []
        relationships: list[tuple[str, str, str]] = []
        have: set[str] = set()
        for model in tables:
            entity_name = mermaid_er_field(str(model.get("name") or model.get("table") or ""))
            if entity_name.lower() in have:
                continue
            have.add(entity_name.lower())
            attr_types = [str(item) for item in (model.get("attribute_types") or [])]
            attributes = []
            for index, item in enumerate(model.get("attributes") or []):
                name = mermaid_er_field(str(item))
                if not name:
                    continue
                raw_type = attr_types[index] if index < len(attr_types) else "string"
                attributes.append({"name": name, "type": _mermaid_scalar_type(raw_type)})
            attributes = attributes[:8]
            extra_pks = [
                mermaid_er_field(str(item))
                for item in (model.get("primary_keys") or [])
                if mermaid_er_field(str(item))
            ]
            er_entities.append(
                {
                    "entity": entity_name,
                    "attributes": attributes,
                    "primary_key": mermaid_er_field(str(model.get("primary_key") or "")),
                    "primary_keys": extra_pks or [],
                }
            )
            for target in model.get("relationships") or []:
                raw = str(target)
                parts = raw.split(":")
                dest = mermaid_er_field(parts[1] if len(parts) >= 2 else raw)
                label = mermaid_er_field(parts[2] if len(parts) >= 3 else "fk")
                if dest and dest != entity_name:
                    relationships.append((dest, entity_name, label or "fk"))
        if not er_entities:
            return None
        root = Path(self.workspace_root) if self.workspace_root else None
        if root is not None and (
            (root / "app" / "db" / "migrations" / "versions").is_dir()
            or (root / "alembic").is_dir()
        ):
            er_entities.append(
                {
                    "entity": "alembic_version",
                    "attributes": [{"name": "version_num", "type": "string"}],
                    "primary_key": "version_num",
                    "primary_keys": ["version_num"],
                }
            )
        return DiagramPlan(
            diagram_id=f"{page_id}-schema-tables",
            diagram_type=MermaidDiagramType.ER_DIAGRAM,
            title="Migration tables",
            description="Alembic table, FK and index view",
            er_entities=er_entities,
            er_relationships=relationships,
            evidence_spans=[c.span for c in evidence_binding.candidates]
            if evidence_binding
            else [],
        )

    def _plan_jwt_sequence(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        root = Path(self.workspace_root) if self.workspace_root else None
        if root is None:
            return None
        jwt = root / "app" / "services" / "jwt.py"
        auth = root / "app" / "api" / "dependencies" / "authentication.py"
        if not (jwt.is_file() and auth.is_file()):
            return None
        try:
            jwt_text = jwt.read_text(encoding="utf-8", errors="ignore")
            auth_text = auth.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None
        auth_class = re.search(r"class\s+([A-Z][A-Za-z0-9]+)", auth_text)
        auth_fn = re.search(r"def\s+([A-Za-z_][A-Za-z0-9_]*)", auth_text)
        jwt_class = re.search(r"class\s+([A-Z][A-Za-z0-9]+)", jwt_text)
        jwt_fn = re.search(
            r"def\s+(get_\w+|decode_\w+|verify_\w+|[A-Za-z_][A-Za-z0-9_]*)", jwt_text
        )
        dep_match = auth_class or auth_fn or jwt_class
        if not dep_match:
            return None
        from repo_wiki.generator.compose_evidence import jwt_token_prefix

        prefix = jwt_token_prefix(root)
        dep_name = dep_match.group(1)
        fn_name = jwt_fn.group(1) if jwt_fn else dep_name
        return DiagramPlan(
            diagram_id=f"{page_id}-jwt-sequence",
            diagram_type=MermaidDiagramType.SEQUENCE_DIAGRAM,
            title="JWT authentication",
            description="Route dependency verifies JWT",
            sequence_participants=["Client", dep_name, "jwt"],
            sequence_messages=[
                ("Client", dep_name, f"{prefix} token"),
                (dep_name, "jwt", fn_name),
            ],
            evidence_spans=[c.span for c in evidence_binding.candidates]
            if evidence_binding
            else [],
        )

    def _plan_request_flow_sequence(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        """Derive Client → middleware → handler → service from this page's routes."""
        from repo_wiki.generator.process_roles import path_looks_like_example_cmd

        endpoints = [item for item in context.get("endpoints") or [] if isinstance(item, dict)]
        tokens = _specific_page_scope_needles(page_id)
        selected = [item for item in endpoints if _endpoint_matches_page(item, tokens)]
        leaf = (page_id or "").lower().rsplit("/", 1)[-1]
        root = Path(self.workspace_root) if self.workspace_root else None
        fetches = frontend_fetch_paths(root)
        if any(token in leaf for token in ("frontend", "前端", "web")):
            fetch_eps = [
                item
                for item in endpoints
                if not path_looks_like_example_cmd(str(item.get("file_path") or ""))
                and (
                    any(
                        str(item.get("path") or "").startswith(prefix)
                        for prefix in _FRONTEND_ROUTE_PREFIXES
                    )
                    or any(str(item.get("path") or "") == fetch for fetch in fetches)
                )
            ]
            selected = fetch_eps
        elif not selected:
            if any(token in leaf for token in ("auth", "认证", "授权", "jwt")):
                selected = (
                    [
                        item
                        for item in endpoints
                        if "auth" in str(item.get("file_path") or "").lower()
                        or "login" in str(item.get("path") or "")
                        or "authentication" in str(item.get("file_path") or "").lower()
                    ]
                    or [
                        item
                        for item in endpoints
                        if not _endpoint_is_anonymous(item)
                        and "health" not in str(item.get("path") or "").lower()
                    ][:1]
                    or list(endpoints[:1])
                )
            elif any(token in leaf for token in ("error", "错误")):
                selected = list(endpoints[:1])
            elif "python" in leaf:
                selected = [
                    item
                    for item in endpoints
                    if any(
                        part in {"api", "routes", "routers", "app"}
                        for part in Path(str(item.get("file_path") or "")).parts
                    )
                ]
            elif "core" in leaf or "核心" in leaf:
                selected = [
                    item
                    for item in endpoints
                    if any(
                        part in {"api", "routes", "routers", "controller"}
                        for part in Path(str(item.get("file_path") or "")).parts
                    )
                    or "controller" in str(item.get("file_path") or "")
                ]
            elif leaf in {"api-overview", "api-reference", "api", "api-ref"}:
                selected = list(endpoints[:1])
        if (
            not selected
            and endpoints
            and not any(token in leaf for token in ("frontend", "前端", "web"))
        ):
            selected = [endpoints[sum(ord(c) for c in (page_id or "x")) % len(endpoints)]]
        if not selected:
            return None
        selected.sort(key=lambda item: _request_flow_score(item, page_id, tokens), reverse=True)
        if any(token in leaf for token in ("core", "核心")):
            sample = selected[-1]
            first_app = next(
                (item for item in endpoints if "app/" in str(item.get("file_path") or "")),
                None,
            )
            if (
                first_app
                and str(sample.get("path") or "") == str(first_app.get("path") or "")
                and len(endpoints) > 1
            ):
                sample = endpoints[-1]
        elif "python" in leaf:
            sample = next(
                (
                    item
                    for item in selected
                    if "article" in str(item.get("path") or "").lower()
                    or "tag" in str(item.get("path") or "").lower()
                ),
                selected[0],
            )
        else:
            sample = selected[0]
        method, path = _honest_method_path(sample, root)
        if not method or not path:
            return None
        root = Path(self.workspace_root) if self.workspace_root else None
        go_auth = bool(
            root and (any(root.glob("*auth*.go")) or (root / "internal" / "auth").is_dir())
        )
        py_auth = bool(
            root and (root / "app" / "api" / "dependencies" / "authentication.py").is_file()
        )
        pid = (page_id or "").lower()
        if any(token in pid for token in ("error", "错误")):
            error_node = _real_error_node(root, sample)
            participants = ["Client", "Route", "Handler", error_node]
            messages = [
                ("Client", "Route", f"{method} {path}"),
                ("Route", "Handler", "dispatch"),
                ("Handler", error_node, "map status"),
            ]
        else:
            handler = mermaid_ident(_endpoint_actor(sample), prefix="h")
            auth_name, auth_label = _auth_hop(sample, go_auth=go_auth, py_auth=py_auth, root=root)
            if auth_name and auth_label:
                service = mermaid_ident(
                    _package_from_file(str(sample.get("file_path") or "")) or "Service",
                    prefix="svc",
                )
                if go_auth:
                    participants = ["Client", auth_name, handler, service]
                    messages = [
                        ("Client", auth_name, auth_label),
                        (auth_name, handler, f"{method} {path}"),
                        (handler, service, "handle"),
                    ]
                else:
                    participants = ["Client", auth_name, handler]
                    messages = [
                        ("Client", auth_name, auth_label),
                        (auth_name, handler, f"{method} {path}"),
                    ]
            else:
                participants = ["Client", "Route", handler]
                messages = [
                    ("Client", "Route", f"{method} {path}"),
                    ("Route", handler, "dispatch"),
                ]
        return DiagramPlan(
            diagram_id=f"{page_id}-request-flow",
            diagram_type=MermaidDiagramType.SEQUENCE_DIAGRAM,
            title="Request flow",
            description="Route registration and handler call chain",
            sequence_participants=participants,
            sequence_messages=messages,
            evidence_spans=[c.span for c in evidence_binding.candidates]
            if evidence_binding
            else [],
        )

    def _plan_join_key_diagram(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        models = [item for item in (context.get("data_models") or []) if isinstance(item, dict)]
        joins = [
            item
            for item in models
            if str(item.get("type") or "") == "migration_table"
            and len(item.get("primary_keys") or []) >= 2
        ]
        if not joins:
            return None
        er_entities = []
        relationships: list[tuple[str, str, str]] = []
        for model in joins[:6]:
            keys = [
                mermaid_er_field(str(item))
                for item in (model.get("primary_keys") or [])
                if mermaid_er_field(str(item))
            ]
            attrs = [str(item) for item in (model.get("attributes") or [])]
            raw_types = [str(item) for item in (model.get("attribute_types") or [])]
            type_by_name = {
                attrs[index]: raw_types[index] for index in range(min(len(attrs), len(raw_types)))
            }
            stamps = [
                mermaid_er_field(str(item))
                for item in attrs
                if str(item) in {"created_at", "updated_at"}
            ]
            entity = mermaid_er_field(str(model.get("name") or "join"))
            er_entities.append(
                {
                    "entity": entity,
                    "attributes": [
                        {"name": name, "type": _join_key_scalar(name, type_by_name.get(name, ""))}
                        for name in keys
                    ]
                    + [{"name": name, "type": "timestamp"} for name in stamps],
                    "primary_key": "",
                    "primary_keys": keys,
                }
            )
            for target in model.get("relationships") or []:
                raw = str(target)
                parts = raw.split(":")
                dest = parts[1] if len(parts) >= 2 else raw
                label = parts[2] if len(parts) >= 3 else (parts[0] if parts else "fk")
                dest_name = mermaid_er_field(dest)
                if dest_name and dest_name != entity:
                    edge = (dest_name, entity, mermaid_er_field(label) or "fk")
                    if edge not in relationships:
                        relationships.append(edge)
        have = {item["entity"] for item in er_entities}
        models_by_name = {
            mermaid_er_field(str(item.get("name") or item.get("table") or "")): item
            for item in models
            if isinstance(item, dict)
        }
        for dest, _entity, _label in relationships:
            if dest not in have:
                source = models_by_name.get(dest) or {}
                dest_attrs: list[dict[str, str]] = []
                raw_types = [str(item) for item in (source.get("attribute_types") or [])]
                for index, item in enumerate(source.get("attributes") or []):
                    name = mermaid_er_field(str(item))
                    if not name:
                        continue
                    raw = raw_types[index] if index < len(raw_types) else "string"
                    dest_attrs.append({"name": name, "type": _join_key_scalar(name, raw)})
                er_entities.append(
                    {
                        "entity": dest,
                        "attributes": dest_attrs,
                        "primary_key": mermaid_er_field(str(source.get("primary_key") or "")),
                        "primary_keys": [
                            mermaid_er_field(str(item))
                            for item in (source.get("primary_keys") or [])
                            if mermaid_er_field(str(item))
                        ],
                    }
                )
                have.add(dest)
        if len(er_entities) < 1:
            return None
        return DiagramPlan(
            diagram_id=f"{page_id}-join-keys",
            diagram_type=MermaidDiagramType.ER_DIAGRAM,
            title="Join table keys",
            description="Composite keys and timestamps from migrations",
            er_entities=er_entities,
            er_relationships=relationships,
            evidence_spans=[c.span for c in evidence_binding.candidates]
            if evidence_binding
            else [],
        )

    def _plan_ci_job_diagram(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        root = Path(self.workspace_root) if self.workspace_root else None
        if root is None:
            return None
        ci = root / ".github" / "workflows" / "ci.yml"
        if not ci.is_file():
            return None
        text = ci.read_text(encoding="utf-8", errors="ignore")
        blocks = re.split(r"(?m)^  ([A-Za-z0-9_-]+):\s*$", text)
        needs_edges: list[tuple[str, str]] = []
        names: list[str] = []
        index = 1
        while index + 1 < len(blocks):
            name, body = blocks[index], blocks[index + 1]
            index += 2
            if name in {"jobs", "on", "env", "defaults", "permissions", "concurrency"}:
                continue
            names.append(name)
            for dep in re.findall(r"needs:\s*\[?([A-Za-z0-9_, \-]+)\]?", body):
                for item in re.split(r"[,\s]+", dep):
                    if item and item != name:
                        needs_edges.append((item, name))
        if len(needs_edges) < 1:
            return None
        used = {src for src, dest in needs_edges} | {dest for src, dest in needs_edges}
        nodes = [
            DiagramNode(id=mermaid_ident(name, prefix="job"), label=name, shape="rectangle")
            for name in names
            if name in used
        ]
        edges = [
            DiagramEdge(
                from_node=mermaid_ident(src, prefix="job"),
                to_node=mermaid_ident(dest, prefix="job"),
            )
            for src, dest in needs_edges
            if src in used and dest in used
        ]
        return DiagramPlan(
            diagram_id=f"{page_id}-ci-jobs",
            diagram_type=MermaidDiagramType.FLOWCHART,
            title="CI jobs",
            description="Jobs declared in .github/workflows/ci.yml",
            nodes=nodes,
            edges=edges,
            evidence_spans=[c.span for c in evidence_binding.candidates]
            if evidence_binding
            else [],
        )


class MermaidRenderer:
    """Renders Mermaid diagram plans to valid Mermaid syntax."""

    def __init__(self) -> None:
        pass

    def render_diagram(self, plan: DiagramPlan) -> str:
        """Render a DiagramPlan to Mermaid syntax."""
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
            if to_p == "Client":
                continue
            label = re.sub(r"<cite>[^<]*</cite>", "", str(message or "")).strip()
            if not label:
                continue
            lines.append(f"    {from_p}->>{to_p}: {label}")

        return "\n".join(lines)

    def _render_er(self, plan: DiagramPlan) -> str:
        """Render ER diagram."""
        lines = ["erDiagram"]

        for entity in plan.er_entities:
            entity_name = mermaid_er_field(str(entity.get("entity") or "Unknown"))
            attributes = entity.get("attributes") or []
            raw_pk = str(entity.get("primary_key") or "").strip()
            primary_key = mermaid_er_field(raw_pk) if raw_pk else ""
            pk_set = {
                mermaid_er_field(str(item))
                for item in (entity.get("primary_keys") or [])
                if str(item).strip() and mermaid_er_field(str(item))
            }
            if primary_key:
                pk_set.add(primary_key)
            lines.append(f"    {entity_name} {{")
            seen: set[str] = set()
            for attr in attributes[:10]:
                if isinstance(attr, dict):
                    field = mermaid_er_field(str(attr.get("name") or ""))
                    field_type = _mermaid_scalar_type(str(attr.get("type") or "string"))
                else:
                    field = mermaid_er_field(str(attr))
                    field_type = "string"
                if not field or field in seen:
                    continue
                seen.add(field)
                suffix = " PK" if field in pk_set else ""
                lines.append(f"        {field_type} {field}{suffix}")
            for extra in pk_set - seen:
                if extra == "id" and (pk_set - {"id"}):
                    continue
                lines.append(f"        string {extra} PK")
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


def create_planner(workspace_root: str | None = None) -> MermaidPlanner:
    """Create a Mermaid planner."""
    return MermaidPlanner(workspace_root=workspace_root)


def create_renderer() -> MermaidRenderer:
    return MermaidRenderer()


def plan_and_render_diagram(
    page_id: str,
    page_type: str,
    evidence_binding: PageEvidenceBinding | None = None,
    context: dict[str, Any] | None = None,
    workspace_root: str | None = None,
) -> tuple[str | None, bool, str]:
    """Plan and render a diagram for a wiki page."""
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
    """Link a diagram plan to evidence spans."""
    if not evidence_binding:
        return diagram_plan

    existing_digests = {span.digest for span in diagram_plan.evidence_spans}
    for candidate in evidence_binding.candidates:
        if candidate.span.digest not in existing_digests:
            diagram_plan.evidence_spans.append(candidate.span)
            existing_digests.add(candidate.span.digest)

    return diagram_plan
