"""Independent handbook-vs-source HTTP paths. No scanner resolvers."""

from __future__ import annotations

import re
from collections.abc import Sequence

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
    r"""(\w+)\.include_router\(\s*(\w+)(?:[^)]*prefix\s*=\s*['\"]([^'\"]*)['\"])?""",
)
_GROUP_RE = re.compile(r"""(\w+)\s*:?=\s*(\w+)\.Group\(\s*['\"]([^'\"]+)['\"]""")
_TO_RE = re.compile(
    r"""(\w+)\.To\(\s*['\"]([A-Z]+(?:\s*,\s*[A-Z]+)*)['\"]\s*,\s*['\"]([^'\"]+)['\"]"""
)
_GO_METHOD_RE = re.compile(
    r"""(\w+)\.(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|Get|Post|Put|Patch|Delete|Head|Any)\(\s*['\"]([^'\"]+)['\"]"""
)


def concat_http_paths(*parts: str) -> str:
    segs = [s for part in parts for s in str(part).strip().split("/") if s]
    return "/" + "/".join(segs) if segs else "/"


def extract_handbook_http_paths(markdown: str) -> set[tuple[str, str]]:
    return {
        (m.group(1).upper(), m.group(2).rstrip("。，、)"))
        for m in _HANDBOOK_ROUTE_RE.finditer(markdown or "")
    }


def extract_source_http_paths(files: Sequence[tuple[str, str]]) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    prefixes: dict[tuple[str, str], str] = {}
    mounts: list[tuple[str, str, str, str]] = []
    routes: list[tuple[str, str, str, str]] = []
    apps: set[tuple[str, str]] = set()
    for path, text in files:
        if path.endswith(".py"):
            for match in _PY_ROUTER_RE.finditer(text):
                prefixes[(path, match.group(1))] = match.group(2) or ""
                if "FastAPI" in match.group(0):
                    apps.add((path, match.group(1)))
            for match in _PY_INCLUDE_RE.finditer(text):
                mounts.append((path, match.group(1), match.group(2), match.group(3) or ""))
            for match in _PY_DECO_RE.finditer(text):
                routes.append((path, match.group(1), match.group(2).upper(), match.group(3)))
        if path.endswith(".go") and not path.endswith("_test.go"):
            group: dict[str, str] = {}
            for match in _GROUP_RE.finditer(text):
                group[match.group(1)] = concat_http_paths(
                    group.get(match.group(2), ""), match.group(3)
                )
            for match in _GO_METHOD_RE.finditer(text):
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
    by_name: dict[str, list[tuple[str, str]]] = {}
    for key in prefixes:
        by_name.setdefault(key[1], []).append(key)

    def resolve(parent_file: str, name: str) -> tuple[str, str] | None:
        local = (parent_file, name)
        if local in prefixes:
            return local
        hits = by_name.get(name) or []
        return hits[0] if len(hits) == 1 else None

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
    if not found:
        for file_path, var, method, route in routes:
            found.add((method, concat_http_paths(prefixes.get((file_path, var), ""), route)))
    return found


def handbook_route_crosscheck_mismatches(
    markdown: str, files: Sequence[tuple[str, str]]
) -> list[str]:
    source = extract_source_http_paths(files)
    paths = {path for _method, path in source}
    bad: list[str] = []
    for method, path in extract_handbook_http_paths(markdown):
        if (method, path) in source or path in paths:
            continue
        if any(path.endswith(src) or src.endswith(path) for src in paths if src not in {"", "/"}):
            continue
        bad.append(f"{method} {path}")
    return sorted(bad)
