"""Independent handbook-vs-source HTTP paths. No scanner resolvers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

_HTTP = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD", "ANY"})
_HANDBOOK_ROUTE_RE = re.compile(
    r"\b(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|ANY)\b\s*`?(/(?:[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]|\{[^}]+\}|:[A-Za-z0-9_]+)+)",
    re.I,
)
_PY_DECO_RE = re.compile(
    r"""@(\w+)\.(get|post|put|patch|delete|options|head)\(\s*['\"]([^'\"]*)['\"]""",
    re.I,
)
_PY_ROUTER_RE = re.compile(
    r"""(\w+)\s*=\s*(?:APIRouter|FastAPI)\((?:[^)]*prefix\s*=\s*['\"]([^'\"]*)['\"])?""",
)
_PY_INCLUDE_RE = re.compile(
    r"""(\w+)\.include_router\(\s*([\w.]+)(?:[^)]*prefix\s*=\s*(?:['\"]([^'\"]*)['\"]|([\w.]+)))?""",
)
_PREFIX_CONST_RE = re.compile(
    r"""(\w+)\s*(?::[^=\n]+)?=\s*['\"](/[^'\"]*)['\"]""",
)
_IMPORT_AS_RE = re.compile(r"from\s+([\w.]+)\s+import\s+(\w+)(?:\s+as\s+(\w+))?")
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
_GO_PATH_TAG_RE = re.compile(r'path:"(/[^"]+)"')
_GO_REGISTER_RE = re.compile(
    r"""(?:RegisterService|RegisterRawRoute|HandleFunc)\(\s*['\"](/[^'\"]+)['\"]"""
)
_JS_ROUTE_RE = re.compile(
    r"""(\w+)\.(get|post|put|patch|delete|options|head)\(\s*['\"](/[^'\"]+)['\"]""",
    re.I,
)
_JS_ROUTER_RE = re.compile(r"""(?:const|let|var)\s+(\w+)\s*=\s*(?:Router|express)\s*\(""")
_UNSUPPORTED_ROUTE_SUFFIXES = frozenset({".rb", ".java", ".php", ".rs", ".kt"})
ROUTE_COMPLETENESS_MIN = 0.5


def _norm_path(path: str) -> str:
    text = (path or "").rstrip("。，、):")
    text = re.sub(r"\{([^}]+)\}", r":\1", text)
    return text or "/"


def concat_http_paths(*parts: str) -> str:
    segs = [s for part in parts for s in str(part).strip().split("/") if s]
    return "/" + "/".join(segs) if segs else "/"


def extract_handbook_http_paths(markdown: str) -> set[tuple[str, str]]:
    return {
        (m.group(1).upper(), _norm_path(m.group(2)))
        for m in _HANDBOOK_ROUTE_RE.finditer(markdown or "")
    }


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
            for match in _IMPORT_AS_RE.finditer(text):
                dest = _module_file(match.group(1), match.group(2))
                if dest:
                    aliases[(path, match.group(3) or match.group(2))] = (dest, match.group(2))
            for match in _PY_ROUTER_RE.finditer(text):
                prefixes[(path, match.group(1))] = match.group(2) or ""
                if "FastAPI" in match.group(0):
                    apps.add((path, match.group(1)))
            for match in _PY_INCLUDE_RE.finditer(text):
                prefix = match.group(3) or _resolve_attr_prefix(match.group(4) or "", constants)
                mounts.append((path, match.group(1), match.group(2), prefix))
            for match in _PY_DECO_RE.finditer(text):
                routes.append((path, match.group(1), match.group(2).upper(), match.group(3)))
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
                method = match.group(2).upper()
                found.add(
                    (
                        method,
                        concat_http_paths(group.get(match.group(1), ""), match.group(3)),
                    )
                )
            for match in _TO_RE.finditer(text):
                route = concat_http_paths(group.get(match.group(1), ""), match.group(3))
                for method in (item.strip().upper() for item in match.group(2).split(",")):
                    if method in _HTTP:
                        found.add((method, route))
            for match in _GO_PATH_TAG_RE.finditer(text):
                found.add(("ANY", match.group(1)))
            for match in _GO_REGISTER_RE.finditer(text):
                found.add(("ANY", match.group(1)))
        if path.endswith((".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx")):
            js_router = set(_JS_ROUTER_RE.findall(text)) | {"app", "router", "server"}
            for match in _JS_ROUTE_RE.finditer(text):
                if match.group(1) not in js_router:
                    continue
                found.add((match.group(2).upper(), concat_http_paths(match.group(3))))
    by_name: dict[str, list[tuple[str, str]]] = {}
    for key in prefixes:
        by_name.setdefault(key[1], []).append(key)

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

    def walk(node: tuple[str, str], prefix: str, seen: set[tuple[tuple[str, str], str]]) -> None:
        key = (node, prefix)
        if key in seen:
            return
        seen.add(key)
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

    seen: set[tuple[tuple[str, str], str]] = set()
    for app in apps or {key for key, _pfx in prefixes.items()}:
        walk(app, "", seen)
    for file_path, _parent, child, mount_prefix in mounts:
        mounted = resolve(file_path, child)
        if mounted:
            walk(mounted, mount_prefix, seen)
    if not found:
        for file_path, var, method, route in routes:
            found.add((method, concat_http_paths(prefixes.get((file_path, var), ""), route)))
    return found


def handbook_route_crosscheck_mismatches(
    markdown: str, files: Sequence[tuple[str, str]]
) -> list[str]:
    source = {(_m, _norm_path(_p)) for _m, _p in extract_source_http_paths(files)}
    paths = {path for _method, path in source}
    bad: list[str] = []
    for method, path in extract_handbook_http_paths(markdown):
        if (method, path) in source or path in paths:
            continue
        bad.append(f"{method} {path}")
    return sorted(bad)


def route_completeness_gap(markdown: str, files: Sequence[tuple[str, str]]) -> list[str]:
    handbook = extract_handbook_http_paths(markdown)
    handbook_paths = {path for _method, path in handbook}
    missing: list[str] = []
    for method, path in extract_source_http_paths(files):
        path = _norm_path(path)
        if (method, path) in handbook or path in handbook_paths:
            continue
        missing.append(f"{method} {path}")
    return sorted(missing)


def route_completeness_ratio(markdown: str, files: Sequence[tuple[str, str]]) -> float:
    source = {(_m, _norm_path(_p)) for _m, _p in extract_source_http_paths(files)}
    if not source:
        return 1.0
    handbook = extract_handbook_http_paths(markdown)
    paths = {path for _method, path in handbook}
    covered = sum(1 for method, path in source if (method, path) in handbook or path in paths)
    return covered / len(source)


def unsupported_route_languages(files: Sequence[tuple[str, str]]) -> tuple[str, ...]:
    found: list[str] = []
    for path, _text in files:
        suffix = Path(path).suffix.lower() if "." in path else ""
        if suffix in _UNSUPPORTED_ROUTE_SUFFIXES:
            found.append(suffix.lstrip("."))
    return tuple(sorted(set(found)))
