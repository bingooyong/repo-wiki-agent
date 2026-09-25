"""Extract Go HTTP routes (gin + RegisterService reflection) and GORM models."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from repo_wiki.scanner.fastapi_routes import join_http_paths

_HTTP_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD", "ANY"})
_GIN_METHOD_NAMES = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD", "Any"})
_REGISTER_SERVICE_RE = re.compile(
    r'(?:^|[^\w.])(?:\w+\.)?RegisterService\(\s*"([^"]+)"\s*,\s*(?:&)?(\w+)\s*[\({]',
    re.MULTILINE,
)
_REGISTER_RAW_ROUTE_RE = re.compile(
    r'(?:^|[^\w.])(?:\w+\.)?RegisterRawRoute\(\s*([^,]+?)\s*,\s*"([^"]+)"',
    re.MULTILINE,
)
_HTTP_METHOD_CONST_RE = re.compile(r"http\.Method(Get|Post|Put|Patch|Delete|Options|Head)")
_SERVE_METHOD_RE = re.compile(
    r"func\s+\(\s*\w+\s+\*?(\w+)\s*\)\s+(Serve[A-Z]\w*)\s*\(\s*\w+\s+\*?(\w+)\s*\)",
    re.MULTILINE,
)
_TYPE_STRUCT_RE = re.compile(
    r"type\s+(\w+)\s+struct\s*\{",
    re.MULTILINE,
)
_PATH_TAG_RE = re.compile(r'`[^`]*\bpath:"([^"]+)"[^`]*`')
_GIN_ROUTE_RE = re.compile(
    r"""\b([A-Za-z_]\w*)\.(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|Any|Handle)\(\s*"""
    r"""(?:((?:http\.Method\w+)|(?:"[A-Z]+"))\s*,\s*)?["']([^"']+)["']""",
)
_HANDLE_FUNC_RE = re.compile(r"""(?:http\.)?HandleFunc\(\s*["']([^"']+)["']\s*,\s*([A-Za-z_]\w*)""")
_MUX_HANDLE_RE = re.compile(
    r"""(?:^|[^\w.])(?:\w+\.)?Handle\(\s*["']([^"']+)["']""",
    re.MULTILINE,
)
_ROUTE_TABLE_PAIR_RE = re.compile(
    r"""\{\s*"(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|ANY)"\s*,\s*"(/[^"]*)"(?:\s*,)?""",
    re.IGNORECASE,
)
_METHOD_PATH_LITERAL_RE = re.compile(
    r"^(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|ANY)\s+(/.+)$",
    re.IGNORECASE,
)
_GORM_TAG_RE = re.compile(r"`[^`]*\bgorm:")
_DB_TAG_RE = re.compile(r"`[^`]*\bdb:")
_GORM_MODEL_EMBED_RE = re.compile(r"\bgorm\.Model\b")
_TABLE_NAME_RE = re.compile(
    r"func\s+\(\s*(?:\w+\s+)?\*?(\w+)\s*\)\s+TableName\s*\(\s*\)\s+string",
    re.MULTILINE,
)
_NEW_CTOR_RE = re.compile(r"^New(.+)$")
_SKIP_DIR_PARTS = frozenset({"testdata", "tests", "vendor", "node_modules"})
_GO_IMPORT_BLOCK_RE = re.compile(r"import\s*\(\s*([\s\S]*?)\)")
_GO_IMPORT_SINGLE_RE = re.compile(r'^\s*import\s+(?:\w+\s+)?"([^"]+)"', re.MULTILINE)
_GO_IMPORT_PATH_RE = re.compile(r'"([^"]+)"')
_GO_FIELD_RE = re.compile(
    r"^\s*([A-Za-z_]\w*)\s+(\*?\[\]\*?|\*|\[]\*)?([A-Za-z_]\w*(?:\.\w+)?)\s*(`[^`]*`)?",
    re.MULTILINE,
)
_NON_MODEL_NAME_RE = re.compile(r"(Config|Options|Settings|Writer|Reader|Logger|Client|Conn)$")
_PRODUCT_PKG_ROOTS = frozenset({"internal", "pkg", "cmd"})


@dataclass(frozen=True)
class GoEndpoint:
    method: str
    path: str
    handler: str
    file_path: str
    lineno: int
    kind: str = "go_http"


@dataclass(frozen=True)
class GoDataModel:
    name: str
    file_path: str
    lineno: int
    kind: str = "go_gorm"
    table_name: str | None = None
    attributes: tuple[str, ...] = ()
    primary_key: str | None = None
    relations: tuple[str, ...] = ()


def is_go_test_path(path: str) -> bool:
    """True for ``*_test.go``, testdata/, or a tests/ tree — not product routes."""
    if not path:
        return False
    rel = path.replace("\\", "/")
    name = Path(rel).name.lower()
    if name.endswith("_test.go"):
        return True
    parts = [part.lower() for part in Path(rel).parts]
    return any(part in _SKIP_DIR_PARTS for part in parts)


def http_method_from_request_type(type_name: str) -> str:
    """Mirror ccagent ``parseMethod``: suffix GET/POST/PUT/DELETE else ANY."""
    name = type_name.strip()
    if not name:
        return "ANY"
    upper = name.upper()
    if upper.endswith("REQUEST"):
        upper = upper[: -len("REQUEST")]
    elif upper.endswith("REQ"):
        upper = upper[: -len("REQ")]
    for suffix, method in (
        ("DELETE", "DELETE"),
        ("PATCH", "PATCH"),
        ("POST", "POST"),
        ("PUT", "PUT"),
        ("GET", "GET"),
    ):
        if upper.endswith(suffix):
            return method
    return "ANY"


def _ctor_type_name(expr: str) -> str:
    match = _NEW_CTOR_RE.match(expr)
    if match:
        return match.group(1)
    return expr


def _struct_body_at(text: str, brace_index: int) -> str:
    if brace_index < 0 or brace_index >= len(text) or text[brace_index] != "{":
        return ""
    depth = 0
    for i in range(brace_index, len(text)):
        char = text[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[brace_index + 1 : i]
    return ""


def _iter_struct_defs(text: str) -> list[tuple[str, str, int]]:
    found: list[tuple[str, str, int]] = []
    for match in _TYPE_STRUCT_RE.finditer(text):
        brace = text.find("{", match.end() - 1)
        body = _struct_body_at(text, brace)
        lineno = text[: match.start()].count("\n") + 1
        found.append((match.group(1), body, lineno))
    return found


def go_package_label(path: str) -> str | None:
    """Return ``internal/foo`` / ``cmd/bar`` for a product Go path."""
    parts = [part for part in path.replace("\\", "/").split("/") if part]
    for root in _PRODUCT_PKG_ROOTS:
        if root in parts:
            index = parts.index(root)
            if index + 1 < len(parts):
                return "/".join(parts[index : index + 2])
    return None


def go_quoted_imports(text: str) -> list[str]:
    """Return quoted import paths from single-line and block imports."""
    found: list[str] = []
    for match in _GO_IMPORT_BLOCK_RE.finditer(text):
        found.extend(_GO_IMPORT_PATH_RE.findall(match.group(1)))
    found.extend(_GO_IMPORT_SINGLE_RE.findall(text))
    return found


def extract_go_internal_import_edges(
    files: Sequence[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Return ``(from_pkg, to_pkg)`` edges among ``internal/*`` / ``cmd/*``."""
    edges: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for path, text in files:
        if is_go_test_path(path):
            continue
        src = go_package_label(path)
        if not src:
            continue
        for imported in go_quoted_imports(text):
            dst = go_package_label(imported)
            if not dst or dst == src:
                continue
            key = (src, dst)
            if key in seen:
                continue
            seen.add(key)
            edges.append(key)
    return edges


def _parse_gorm_fields(
    body: str, known_models: set[str]
) -> tuple[tuple[str, ...], str | None, tuple[str, ...]]:
    attrs: list[str] = []
    pk: str | None = None
    rels: list[str] = []
    seen_rel: set[str] = set()
    for name, _indirection, typ, tag in _GO_FIELD_RE.findall(body):
        if not name or name[0].islower():
            continue
        tag = tag or ""
        if name not in attrs:
            attrs.append(name)
        if "primaryKey" in tag or "primary_key" in tag:
            pk = name
        type_name = typ.split(".")[-1]
        if type_name in known_models and type_name not in seen_rel:
            seen_rel.add(type_name)
            rels.append(type_name)
        if name.endswith("ID") and name[:-2] in known_models and name[:-2] not in seen_rel:
            seen_rel.add(name[:-2])
            rels.append(name[:-2])
    if pk is None and "ID" in attrs:
        pk = "ID"
    return tuple(attrs), pk, tuple(rels)


def _is_non_model_struct(name: str, body: str, table_names: dict[str, str]) -> bool:
    if not name or name[0].islower():
        return True
    if name in table_names:
        return False
    if _GORM_MODEL_EMBED_RE.search(body):
        return False
    return bool(_NON_MODEL_NAME_RE.search(name)) and not _GORM_TAG_RE.search(body)


def _path_params_from_struct(body: str) -> tuple[list[str], str | None]:
    params: list[str] = []
    star: str | None = None
    for raw in _PATH_TAG_RE.findall(body):
        tag = raw.strip()
        if not tag:
            continue
        if tag.startswith("*"):
            star = tag[1:] or star
            continue
        params.append(tag.lstrip(":"))
    return params, star


def _base_path_param_names(path: str) -> set[str]:
    names: set[str] = set()
    for segment in path.split("/"):
        if len(segment) < 2 or segment[0] not in {":", "*"}:
            continue
        names.add(segment.lstrip(":*"))
    return names


def _join_reflected_path(base: str, method_name: str, req_body: str) -> str:
    leaf = method_name[5:].lower() if method_name.startswith("Serve") else method_name.lower()
    path = join_http_paths(base, leaf)
    present = _base_path_param_names(base)
    params, star = _path_params_from_struct(req_body)
    extras = [name for name in params if name and name not in present]
    if extras:
        path = join_http_paths(path, *(":" + name for name in extras))
    if star and star not in present:
        path = f"{path.rstrip('/')}/*{star}"
    return path


def _split_method_path(raw: str, default_method: str = "GET") -> tuple[str, str]:
    """Split Go 1.22 ``GET /debug/pprof/`` patterns from a single string."""
    text = (raw or "").strip()
    match = _METHOD_PATH_LITERAL_RE.match(text)
    if match:
        return match.group(1).upper(), match.group(2)
    path = text if text.startswith("/") else "/" + text.lstrip()
    return default_method, path


def _resolve_http_method_expr(expr: str | None) -> str:
    if not expr:
        return "GET"
    const = _HTTP_METHOD_CONST_RE.fullmatch(expr.strip())
    if const:
        return const.group(1).upper()
    stripped = expr.strip().strip('"').strip("'")
    upper = stripped.upper()
    if upper in _HTTP_METHODS:
        return upper
    return "GET"


def extract_go_endpoints(files: Sequence[tuple[str, str]]) -> list[GoEndpoint]:
    """Return product Go HTTP routes, excluding ``*_test.go`` registrations.

    Covers gin ``GET``/``Handle``, ``http.HandleFunc``, ``RegisterRawRoute``,
    and the ccagent ``RegisterService(base, svc)`` + ``Serve*`` reflection
    convention (``base/<method lower>`` plus ``path`` struct tags).
    """
    product_files = [(path, text) for path, text in files if not is_go_test_path(path)]
    structs: dict[str, tuple[str, str, int]] = {}
    methods_by_recv: dict[str, list[tuple[str, str, str, int]]] = {}
    endpoints: list[GoEndpoint] = []
    seen: set[tuple[str, str, str]] = set()

    def _add(method: str, path: str, handler: str, file_path: str, lineno: int, kind: str) -> None:
        method_u = method.upper()
        if method_u not in _HTTP_METHODS:
            method_u = "ANY"
        path_n = path if path.startswith("/") else "/" + path
        key = (method_u, path_n, file_path)
        if key in seen:
            return
        seen.add(key)
        endpoints.append(
            GoEndpoint(
                method=method_u,
                path=path_n,
                handler=handler,
                file_path=file_path,
                lineno=lineno,
                kind=kind,
            )
        )

    for path, text in product_files:
        for name, body, lineno in _iter_struct_defs(text):
            structs[name] = (body, path, lineno)
        for match in _SERVE_METHOD_RE.finditer(text):
            recv, method_name, req_type = match.group(1), match.group(2), match.group(3)
            lineno = text[: match.start()].count("\n") + 1
            methods_by_recv.setdefault(recv, []).append((method_name, req_type, path, lineno))

        for match in _HANDLE_FUNC_RE.finditer(text):
            lineno = text[: match.start()].count("\n") + 1
            method, route_path = _split_method_path(match.group(1))
            _add(method, route_path, match.group(2), path, lineno, "go_nethttp")

        for match in _MUX_HANDLE_RE.finditer(text):
            raw = match.group(1)
            if not _METHOD_PATH_LITERAL_RE.match(raw.strip()):
                continue
            lineno = text[: match.start()].count("\n") + 1
            method, route_path = _split_method_path(raw)
            _add(method, route_path, "Handle", path, lineno, "go_nethttp")

        for match in _ROUTE_TABLE_PAIR_RE.finditer(text):
            lineno = text[: match.start()].count("\n") + 1
            _add(match.group(1).upper(), match.group(2), "pprof", path, lineno, "go_pprof")

        for match in _GIN_ROUTE_RE.finditer(text):
            call = match.group(2)
            method_expr = match.group(3)
            route_path = match.group(4)
            lineno = text[: match.start()].count("\n") + 1
            if _METHOD_PATH_LITERAL_RE.match(route_path.strip()):
                method, route_path = _split_method_path(route_path)
            elif call == "Handle":
                method = _resolve_http_method_expr(method_expr)
            elif call == "Any":
                method = "ANY"
            else:
                method = call.upper()
            handler = f"{match.group(1)}.{call}"
            _add(method, route_path, handler, path, lineno, "go_gin")

        for match in _REGISTER_RAW_ROUTE_RE.finditer(text):
            method = _resolve_http_method_expr(match.group(1).strip())
            route_path = match.group(2)
            lineno = text[: match.start()].count("\n") + 1
            _add(method, route_path, "RegisterRawRoute", path, lineno, "go_raw_route")

    for path, text in product_files:
        for match in _REGISTER_SERVICE_RE.finditer(text):
            base = match.group(1)
            ctor = match.group(2)
            recv = _ctor_type_name(ctor)
            lineno = text[: match.start()].count("\n") + 1
            for method_name, req_type, method_file, method_lineno in methods_by_recv.get(recv, []):
                req_body = structs.get(req_type, ("", "", 0))[0]
                route = _join_reflected_path(base, method_name, req_body)
                method = http_method_from_request_type(req_type)
                _add(
                    method,
                    route,
                    f"{recv}.{method_name}",
                    method_file,
                    method_lineno or lineno,
                    "go_register_service",
                )

    return endpoints


def extract_go_data_models(files: Sequence[tuple[str, str]]) -> list[GoDataModel]:
    """Return GORM / ``db:`` tagged structs. Skip test files and untagged DTOs."""
    table_names: dict[str, str] = {}
    raw: list[tuple[str, str, str, int, str]] = []
    seen: set[tuple[str, str]] = set()
    for path, text in files:
        if is_go_test_path(path):
            continue
        for match in _TABLE_NAME_RE.finditer(text):
            recv = match.group(1)
            after = text[match.end() :]
            table_match = re.search(r'return\s+"([^"]+)"', after[:400])
            if table_match:
                table_names[recv] = table_match.group(1)
        for name, body, lineno in _iter_struct_defs(text):
            if _is_non_model_struct(name, body, table_names):
                continue
            if not (
                _GORM_TAG_RE.search(body)
                or _DB_TAG_RE.search(body)
                or _GORM_MODEL_EMBED_RE.search(body)
                or name in table_names
            ):
                continue
            key = (name, path)
            if key in seen:
                continue
            seen.add(key)
            kind = (
                "go_gorm" if (_GORM_TAG_RE.search(body) or name in table_names) else "go_struct_db"
            )
            raw.append((name, path, body, lineno, kind))
    known = {name for name, _path, _body, _lineno, _kind in raw}
    models: list[GoDataModel] = []
    for name, path, body, lineno, kind in raw:
        attributes, primary_key, relations = _parse_gorm_fields(body, known - {name})
        models.append(
            GoDataModel(
                name=name,
                file_path=path,
                lineno=lineno,
                kind=kind,
                table_name=table_names.get(name),
                attributes=attributes,
                primary_key=primary_key,
                relations=relations,
            )
        )
    return models
