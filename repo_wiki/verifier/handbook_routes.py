"""Independent handbook-vs-source HTTP routes. No scanner resolvers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

_HTTP = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD", "ANY"})
_HANDBOOK_ROUTE_RE = re.compile(
    r"\b(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|ANY)\b\s*`?(/(?:[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]|\{[^}]+\}|:[A-Za-z0-9_]+)+)",
    re.I,
)
_TABLE_ROW_RE = re.compile(
    r"^\|\s*(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|ANY)\s*\|\s*`?(/(?:[^|`]+))`?",
    re.I | re.M,
)
_CURL_RE = re.compile(
    r"\bcurl\b[^\n]*?(?:-X|--request)\s+(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\b[^\n]*?(https?://[^\s`]+|/[\w:.{}/-]*)",
    re.I,
)
_PATH_ONLY_RE = re.compile(r"`(/[A-Za-z0-9._~:/{}\-]+)`")
_TABLE_PATH_RE = re.compile(r"^\|\s*`?(/(?:[^|`]+))`?", re.M)
_PY_DECO_RE = re.compile(
    r"""@(\w+)\.(get|post|put|patch|delete|options|head)\(\s*['\"]([^'\"]*)['\"]""",
    re.I,
)
_PY_ROUTE_DECO_RE = re.compile(
    r"""@(\w+)\.(?:route|api_route)\(\s*['\"]([^'\"]*)['\"]([^)]*)\)""",
    re.I,
)
_PY_ROUTER_RE = re.compile(
    r"""(\w+)\s*=\s*(?:APIRouter|FastAPI|Flask|Blueprint)\((?:[^)]*prefix\s*=\s*['\"]([^'\"]*)['\"])?""",
)
_PY_INCLUDE_RE = re.compile(
    r"""(\w+)\.include_router\(\s*([\w.]+)(?:[^)]*prefix\s*=\s*(?:['\"]([^'\"]*)['\"]|([\w.]+)))?""",
)
_PREFIX_CONST_RE = re.compile(r"""(\w+)\s*(?::[^=\n]+)?=\s*['\"](/[^'\"]*)['\"]""")
_IMPORT_RE = re.compile(r"from\s+([\w.]+)\s+import\s+(\([^)]+\)|[^\n#]+)", re.S)
_ADD_RESOURCE_RE = re.compile(
    r"""(\w+)\.add_resource\(\s*\w+\s*((?:,\s*['\"][^'\"]+['\"])+)""",
)
_AS_VIEW_RE = re.compile(
    r"""(?:path|re_path|url)\(\s*['\"]([^'\"]+)['\"]\s*,\s*\w+\.as_view\(""",
)
_CHAIN_RE = re.compile(
    r"""(\w+)\.route\(\s*['\"]([^'\"]+)['\"]\s*\)((?:\s*\.\s*(?:get|post|put|patch|delete|options|head)\([^;]*)+)""",
    re.I,
)
_GROUP_RE = re.compile(r"""(\w+)\s*:?=\s*(\w+)\.Group\(\s*['\"]([^'\"]+)['\"]""")
_TO_RE = re.compile(
    r"""(\w+)\.To\(\s*['\"]([A-Z]+(?:\s*,\s*[A-Z]+)*)['\"]\s*,\s*['\"]([^'\"]+)['\"]"""
)
_GO_METHOD_RE = re.compile(
    r"""(\w+)\.(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|Get|Post|Put|Patch|Delete|Head|Any)\(\s*['\"](/[^'\"]+)['\"]"""
)
_NON_ROUTE_RECV = frozenset({"Header", "Tag", "Query", "Form", "Cookie"})
_GO_CTOR_RE = re.compile(
    r"""(\w+)\s*:?=\s*(?:gin\.(?:Default|New)|chi\.NewRouter|echo\.New|http\.NewServeMux|mux\.NewRouter|fiber\.New)\("""
)
_GO_TYPE_METHOD_RE = re.compile(
    r"func\s+\((?:\w+\s+)?\*?([A-Z]\w*)\)\s+([A-Z][A-Za-z0-9]*)\s*\((?:\w+\s+\*?([A-Z]\w*))?"
)
_STRUCT_BODY_RE = re.compile(r"type\s+(\w+)\s+struct\s*\{([^}]*)\}", re.S)
_REQ_PATH_RE = re.compile(r'path:"([^"]+)"(?:[^`]*seq:"(\d+)")?')
_REG_SVC_RE = re.compile(
    r"""RegisterService\(\s*['\"](/[^'\"]+)['\"]\s*,\s*(?:New(\w+)\(|&?(\w+)\{)"""
)
_REG_RAW_RE = re.compile(
    r"""RegisterRawRoute\(\s*(?:http\.Method(\w+)|['\"]([A-Z]+)['\"])\s*,\s*['\"](/[^'\"]+)['\"]"""
)
_HANDLE_FUNC_RE = re.compile(r"""HandleFunc\(\s*['\"](?:([A-Z]+)\s+)?(/[^'\"]+)['\"]""")
_SKIP_REFLECT = frozenset({"Init", "Register", "ServeHTTP"})
_JS_ROUTE_RE = re.compile(
    r"""(\w+)\.(get|post|put|patch|delete|options|head)\(\s*['\"](/[^'\"]+)['\"]""",
    re.I,
)
_JS_ROUTER_RE = re.compile(r"""(?:const|let|var)\s+(\w+)\s*=\s*(?:Router|express)\s*\(""")
_UNSUPPORTED_ROUTE_SUFFIXES = frozenset({".rb", ".java", ".php", ".rs", ".kt"})
_FRAMEWORK_MARK = re.compile(
    r"\b(?:fastapi|flask|django|starlette|gin-gonic|labstack/echo|go-chi|"
    r"gofiber|gorilla/mux|express|fastify|koa|hapi)\b",
    re.I,
)
_IDIOM_MARK = re.compile(r"add_resource\(|\.as_view\(|\.route\([^)]*\)\s*\.\s*(?:get|post)\(")
_ACTION_SEGS = frozenset(
    {"create", "delete", "list", "get", "update", "remove", "add", "edit", "show", "index", "new"}
)
ROUTE_COMPLETENESS_MIN = 0.5


def _norm_path(path: str) -> str:
    text = (path or "").rstrip("。，、):")
    text = re.sub(r"\{([^}]+)\}", r":\1", text)
    text = re.sub(r"<([^>]+)>", r":\1", text)
    if len(text) > 1:
        text = text.rstrip("/")
    return text or "/"


def concat_http_paths(*parts: str) -> str:
    segs = [s for part in parts for s in str(part).strip().split("/") if s]
    return "/" + "/".join(segs) if segs else "/"


def _methods_from_blob(blob: str) -> list[str]:
    found = [
        item.upper()
        for item in re.findall(r"\b(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\b", blob, flags=re.I)
    ]
    return found or ["GET"]


def _reflect_method_path(base: str, name: str, req_body: str) -> str:
    leaf = name[5:] if name.startswith("Serve") and len(name) > 5 else name
    if leaf.startswith("Handle") and len(leaf) > 6:
        leaf = leaf[6:]
    route = concat_http_paths(base, leaf.lower())
    present = {seg.lstrip(":*") for seg in route.split("/") if seg}
    extras: list[tuple[int, str]] = []
    star = ""
    for match in _REQ_PATH_RE.finditer(req_body or ""):
        token = match.group(1)
        if token.startswith("*"):
            star = token[1:]
            continue
        extras.append((int(match.group(2) or 0), token.lstrip(":")))
    for _seq, token in sorted(extras):
        if token and token not in present:
            route = concat_http_paths(route, ":" + token)
    if star and star not in present:
        route = route.rstrip("/") + "/*" + star
    return route


def extract_handbook_http_paths(markdown: str, *, api_page: bool = False) -> set[tuple[str, str]]:
    text = markdown or ""
    found: set[tuple[str, str]] = set()
    for match in _HANDBOOK_ROUTE_RE.finditer(text):
        path = _norm_path(match.group(2))
        first = path.strip("/").split("/", 1)[0].upper()
        if path.startswith("/") and first not in _HTTP:
            found.add((match.group(1).upper(), path))
    for match in _TABLE_ROW_RE.finditer(text):
        found.add((match.group(1).upper(), _norm_path(match.group(2))))
    for match in _CURL_RE.finditer(text):
        raw = match.group(2)
        path = raw.split("://", 1)[-1]
        path = "/" + path.split("/", 1)[-1] if "/" in path else path
        found.add((match.group(1).upper(), _norm_path(path)))
    if api_page:
        stripped = re.sub(r"```.*?```", " ", text, flags=re.S)
        for match in _PATH_ONLY_RE.finditer(stripped):
            path = _norm_path(match.group(1))
            if "." in path.rsplit("/", 1)[-1] or not _path_only_is_route(path):
                continue
            found.add(("ANY", path))
        for match in _TABLE_PATH_RE.finditer(stripped):
            path = _norm_path(match.group(1))
            if path.startswith("/") and path.strip("/").split("/", 1)[0].upper() not in _HTTP:
                if _path_only_is_route(path) or "|" in match.group(0):
                    found.add(("ANY", path))
    return found


def _path_only_is_route(path: str) -> bool:
    segs = [item for item in _norm_path(path).strip("/").split("/") if item]
    static = [item for item in segs if not item.startswith((":", "{"))]
    if not static:
        return False
    return not all(item.lower() in _ACTION_SEGS for item in static)


def _path_shape(path: str) -> tuple[str, ...]:
    shaped: list[str] = []
    for seg in _norm_path(path).split("/"):
        if not seg:
            continue
        if seg.startswith(":") or re.fullmatch(r"\d+", seg):
            shaped.append("*")
        else:
            shaped.append(seg.lower())
    return tuple(shaped)


def _prefix_constants(files: Sequence[tuple[str, str]]) -> dict[str, str]:
    found: dict[str, str] = {}
    for _path, text in files:
        for match in _PREFIX_CONST_RE.finditer(text):
            found[match.group(1)] = match.group(2)
    return found


def _resolve_attr_prefix(expr: str, constants: dict[str, str]) -> str:
    if not expr:
        return ""
    if expr.startswith("/"):
        return expr
    leaf = expr.rsplit(".", 1)[-1]
    return constants.get(leaf) or constants.get(expr) or ""


def iter_route_source_files(root: Path) -> list[tuple[str, str]]:
    skip = {".git", ".repo-agent-eval", "vendor", "node_modules", "__pycache__"}
    suffixes = {".py", ".go", ".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx"}
    extra = {".rb", ".java", ".php", ".rs"}
    found: list[tuple[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in suffixes | extra:
            continue
        if any(part in skip for part in path.parts):
            continue
        found.append(
            (path.relative_to(root).as_posix(), path.read_text(encoding="utf-8", errors="ignore"))
        )
    return found


def extract_source_http_paths(files: Sequence[tuple[str, str]]) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    prefixes: dict[tuple[str, str], str] = {}
    mounts: list[tuple[str, str, str, str]] = []
    routes: list[tuple[str, str, str, str]] = []
    apps: set[tuple[str, str]] = set()
    constants = _prefix_constants(files)
    by_stem: dict[str, str] = {}
    file_set = {path for path, _text in files}
    aliases: dict[tuple[str, str], tuple[str, str]] = {}
    type_methods: dict[str, list[tuple[str, str, str]]] = {}
    structs: dict[tuple[str, str], str] = {}
    for path, text in files:
        if path.endswith(".go") and not path.endswith("_test.go"):
            for match in _GO_TYPE_METHOD_RE.finditer(text):
                type_methods.setdefault(match.group(1), []).append(
                    (match.group(2), match.group(3) or "", path)
                )
            for match in _STRUCT_BODY_RE.finditer(text):
                structs[(path, match.group(1))] = match.group(2)

    def _module_file(module: str, name: str = "") -> str | None:
        for cand in (
            module.replace(".", "/") + ".py",
            module.replace(".", "/") + "/" + name + ".py" if name else "",
            module.replace(".", "/") + "/__init__.py",
        ):
            if cand and cand in file_set:
                return cand
            hits = [
                item for item in file_set if cand and (item == cand or item.endswith("/" + cand))
            ]
            if len(hits) == 1:
                return hits[0]
        return by_stem.get(name) or by_stem.get(module.rsplit(".", 1)[-1])

    for path, text in files:
        if path.endswith(".py"):
            by_stem[path.rsplit("/", 1)[-1].removesuffix(".py")] = path
            for match in _IMPORT_RE.finditer(text):
                for part in match.group(2).replace("(", " ").replace(")", " ").split(","):
                    names = [
                        item.strip() for item in re.split(r"\s+as\s+", part.strip()) if item.strip()
                    ]
                    if not names or not names[0].isidentifier():
                        continue
                    dest = _module_file(match.group(1), names[0])
                    if dest:
                        aliases[(path, names[-1])] = (dest, names[0])
            for match in _PY_ROUTER_RE.finditer(text):
                prefixes[(path, match.group(1))] = match.group(2) or ""
                if re.search(r"FastAPI|Flask\(", match.group(0)):
                    apps.add((path, match.group(1)))
            for match in _PY_INCLUDE_RE.finditer(text):
                prefix = match.group(3) or _resolve_attr_prefix(match.group(4) or "", constants)
                mounts.append((path, match.group(1), match.group(2), prefix))
            for match in _PY_DECO_RE.finditer(text):
                routes.append((path, match.group(1), match.group(2).upper(), match.group(3)))
            for match in _PY_ROUTE_DECO_RE.finditer(text):
                for method in _methods_from_blob(match.group(3)):
                    routes.append((path, match.group(1), method, match.group(2)))
            for match in _ADD_RESOURCE_RE.finditer(text):
                for raw in re.findall(r"['\"]([^'\"]+)['\"]", match.group(2)):
                    found.add(("ANY", _norm_path(concat_http_paths(raw))))
            for match in _AS_VIEW_RE.finditer(text):
                found.add(("ANY", _norm_path(concat_http_paths(match.group(1)))))
            for match in _CHAIN_RE.finditer(text):
                for method in _methods_from_blob(match.group(3)):
                    routes.append((path, match.group(1), method, match.group(2)))
        if path.endswith(".go") and not path.endswith("_test.go"):
            group: dict[str, str] = {}
            routers = set(_GO_CTOR_RE.findall(text))
            for match in _GROUP_RE.finditer(text):
                group[match.group(1)] = concat_http_paths(
                    group.get(match.group(2), ""), match.group(3)
                )
                routers.add(match.group(1))
                routers.add(match.group(2))
            for match in _GO_METHOD_RE.finditer(text):
                if match.group(1) in _NON_ROUTE_RECV:
                    continue
                if routers and match.group(1) not in routers and match.group(1) not in group:
                    continue
                found.add(
                    (
                        match.group(2).upper(),
                        concat_http_paths(group.get(match.group(1), ""), match.group(3)),
                    )
                )
            for match in _TO_RE.finditer(text):
                route = concat_http_paths(group.get(match.group(1), ""), match.group(3))
                for method in (item.strip().upper() for item in match.group(2).split(",")):
                    if method in _HTTP:
                        found.add((method, route))
            for match in _REG_SVC_RE.finditer(text):
                base = match.group(1)
                kind = match.group(2) or match.group(3) or ""
                for name, req, method_file in type_methods.get(kind, ()):
                    if name in _SKIP_REFLECT:
                        continue
                    body = structs.get((method_file, req), "") or next(
                        (item for (src, typ), item in structs.items() if typ == req),
                        "",
                    )
                    found.add(("ANY", _reflect_method_path(base, name, body)))
            for match in _REG_RAW_RE.finditer(text):
                found.add(
                    (
                        (match.group(1) or match.group(2) or "ANY").upper(),
                        concat_http_paths(match.group(3)),
                    )
                )
            for match in _HANDLE_FUNC_RE.finditer(text):
                found.add(((match.group(1) or "ANY").upper(), concat_http_paths(match.group(2))))
        if path.endswith((".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx")):
            js_router = set(_JS_ROUTER_RE.findall(text)) | {"app", "router", "server"}
            for match in _JS_ROUTE_RE.finditer(text):
                if match.group(1) not in js_router:
                    continue
                found.add((match.group(2).upper(), concat_http_paths(match.group(3))))
            for match in _CHAIN_RE.finditer(text):
                if match.group(1) not in js_router:
                    continue
                for method in _methods_from_blob(match.group(3)):
                    found.add((method, concat_http_paths(match.group(2))))
    by_name: dict[str, list[tuple[str, str]]] = {}
    for key in prefixes:
        by_name.setdefault(key[1], []).append(key)
    children = {child for _f, _p, child, _pref in mounts}

    def resolve(parent_file: str, name: str) -> tuple[str, str] | None:
        local = (parent_file, name)
        if local in prefixes:
            return local
        hits = by_name.get(name) or []
        if len(hits) == 1:
            return hits[0]
        if (parent_file, name) in aliases:
            dest_file, dest_var = aliases[(parent_file, name)]
            if dest_var == dest_file.rsplit("/", 1)[-1].removesuffix(".py"):
                dest_var = "router" if (dest_file, "router") in prefixes else dest_var
            if (dest_file, dest_var) in prefixes:
                return (dest_file, dest_var)
            if (dest_file, "router") in prefixes:
                return (dest_file, "router")
        if "." in name:
            mod, attr = name.rsplit(".", 1)
            if (parent_file, mod) in aliases:
                dest_file, _dest_var = aliases[(parent_file, mod)]
                if (dest_file, attr) in prefixes:
                    return (dest_file, attr)
            dest = _module_file(mod, attr) or by_stem.get(mod.rsplit(".", 1)[-1])
            if dest and (dest, attr) in prefixes:
                return (dest, attr)
            if dest and (dest, "router") in prefixes:
                return (dest, "router")
        return None

    def walk(node: tuple[str, str], prefix: str, seen: set[tuple[str, str]]) -> None:
        if node in seen:
            return
        seen.add(node)
        local = concat_http_paths(prefix, prefixes.get(node, ""))
        for file_path, var, method, route in routes:
            if (file_path, var) == node:
                found.add((method, concat_http_paths(local, route)))
        for file_path, parent, child, mount_prefix in mounts:
            if (file_path, parent) != node:
                continue
            dest = resolve(file_path, child)
            if dest:
                walk(dest, concat_http_paths(local, mount_prefix), seen)

    seen: set[tuple[str, str]] = set()
    routed = {(file_path, var) for file_path, var, _method, _route in routes}
    roots = apps or {key for key in (set(prefixes) | routed) if key[1] not in children}
    for app in roots:
        walk(app, "", seen)
    return found


def _pair_matches(method: str, path: str, source: set[tuple[str, str]]) -> bool:
    path = _norm_path(path)
    method = method.upper()
    if (method, path) in source:
        return True
    if method == "ANY":
        return any(sp == path for _sm, sp in source)
    return ("ANY", path) in source


def handbook_route_crosscheck_mismatches(
    markdown: str, files: Sequence[tuple[str, str]], *, api_page: bool = False
) -> list[str]:
    source = {(_m, _norm_path(_p)) for _m, _p in extract_source_http_paths(files)}
    bad: list[str] = []
    for method, path in extract_handbook_http_paths(markdown, api_page=api_page):
        if not _pair_matches(method, path, source):
            bad.append(f"{method} {path}")
    return sorted(bad)


def route_completeness_gap(markdown: str, files: Sequence[tuple[str, str]]) -> list[str]:
    handbook = extract_handbook_http_paths(markdown, api_page=True)
    missing: list[str] = []
    for method, path in extract_source_http_paths(files):
        path = _norm_path(path)
        if not _pair_matches(method, path, handbook) and not _pair_matches("ANY", path, handbook):
            missing.append(f"{method} {path}")
    return sorted(missing)


def route_completeness_ratio(markdown: str, files: Sequence[tuple[str, str]]) -> float:
    source = {(_m, _norm_path(_p)) for _m, _p in extract_source_http_paths(files)}
    if not source:
        return 0.0 if source_extraction_is_unsupported(files) else 1.0
    handbook = extract_handbook_http_paths(markdown, api_page=True)
    covered = sum(1 for method, path in source if _pair_matches(method, path, handbook))
    return covered / len(source)


def unsupported_route_languages(files: Sequence[tuple[str, str]]) -> tuple[str, ...]:
    found: list[str] = []
    for path, _text in files:
        suffix = Path(path).suffix.lower() if "." in path else ""
        if suffix in _UNSUPPORTED_ROUTE_SUFFIXES:
            found.append(suffix.lstrip("."))
    return tuple(sorted(set(found)))


def has_web_framework_dependency(files: Sequence[tuple[str, str]]) -> bool:
    return any(_FRAMEWORK_MARK.search(text) for _path, text in files)


def source_extraction_is_unsupported(files: Sequence[tuple[str, str]]) -> bool:
    if unsupported_route_languages(files):
        return True
    routes = extract_source_http_paths(files)
    if routes:
        return False
    return has_web_framework_dependency(files) or any(
        _IDIOM_MARK.search(text) for _p, text in files
    )


def upgrade_handbook_route_paths(markdown: str, files: Sequence[tuple[str, str]]) -> str:
    """Rewrite unique short/param-mismatched handbook paths to the source spelling."""
    raw = list(extract_source_http_paths(files))
    if not raw:
        return markdown or ""
    indexed = [(method, _norm_path(path), path) for method, path in raw]
    source = {(method, norm) for method, norm, _orig in indexed}

    def _full(method: str, path: str) -> str | None:
        path = _norm_path(path)
        method = method.upper()
        if _pair_matches(method, path, source):
            return None
        shape = _path_shape(path)
        hits = [
            orig
            for sm, sn, orig in indexed
            if (sm == method or method == "ANY" or sm == "ANY")
            and (
                sn.endswith("/" + path.lstrip("/"))
                or _path_shape(sn) == shape
            )
        ]
        uniq = list(dict.fromkeys(hits))
        return uniq[0] if len(uniq) == 1 else None

    def _verb_repl(match: re.Match[str]) -> str:
        full = _full(match.group(1), match.group(2))
        return match.group(0) if not full else match.group(0).replace(match.group(2), full, 1)

    def _tick_repl(match: re.Match[str]) -> str:
        if not _path_only_is_route(match.group(1)):
            return match.group(0)
        full = _full("ANY", match.group(1))
        return match.group(0) if not full else match.group(0).replace(match.group(1), full, 1)

    def _curl_repl(match: re.Match[str]) -> str:
        raw = match.group(2)
        path = raw.split("://", 1)[-1]
        path = "/" + path.split("/", 1)[-1] if "/" in path else path
        full = _full(match.group(1), path)
        return match.group(0) if not full else match.group(0).replace(path, full, 1)

    text = _HANDBOOK_ROUTE_RE.sub(_verb_repl, markdown or "")
    text = _PATH_ONLY_RE.sub(_tick_repl, text)
    return _CURL_RE.sub(_curl_repl, text)


def drop_unmatched_handbook_routes(markdown: str, files: Sequence[tuple[str, str]]) -> str:
    source = {(_m, _norm_path(_p)) for _m, _p in extract_source_http_paths(files)}
    if not source:
        return markdown or ""

    def _verb_drop(match: re.Match[str]) -> str:
        if _pair_matches(match.group(1), match.group(2), source):
            return match.group(0)
        return ""

    def _tick_drop(match: re.Match[str]) -> str:
        if not _path_only_is_route(match.group(1)):
            return match.group(0)
        if _pair_matches("ANY", match.group(1), source):
            return match.group(0)
        return ""

    text = _HANDBOOK_ROUTE_RE.sub(_verb_drop, markdown or "")
    text = _PATH_ONLY_RE.sub(_tick_drop, text)
    kept: list[str] = []
    for line in text.splitlines():
        hits = extract_handbook_http_paths(line, api_page=True)
        if hits and not any(_pair_matches(method, path, source) for method, path in hits):
            continue
        if re.fullmatch(r"[-*]\s*", line.strip()):
            continue
        kept.append(line)
    return "\n".join(kept)
