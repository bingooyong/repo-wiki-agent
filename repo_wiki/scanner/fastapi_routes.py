"""Extract FastAPI/APIRouter HTTP routes and join include_router prefixes."""

from __future__ import annotations

import ast
from collections.abc import Sequence
from dataclasses import dataclass, field

_HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "options", "head"})
_ROUTER_CTORS = frozenset({"APIRouter", "FastAPI"})


@dataclass(frozen=True)
class FastAPIEndpoint:
    method: str
    path: str
    handler: str
    file_path: str
    lineno: int


@dataclass(frozen=True)
class _Mount:
    child_ref: str
    prefix: str = ""
    prefix_ref: str | None = None


@dataclass
class _FileFacts:
    class_str_attrs: dict[tuple[str, str], str] = field(default_factory=dict)
    instances: dict[str, str] = field(default_factory=dict)
    module_str_attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class _RouterDef:
    file_path: str
    var_name: str
    constructor_prefix: str = ""
    is_app: bool = False
    routes: list[tuple[str, str, str, int]] = field(default_factory=list)
    mounts: list[_Mount] = field(default_factory=list)


def join_http_paths(*parts: str) -> str:
    """Join mount prefixes and a handler path into a single HTTP path."""
    segments: list[str] = []
    for part in parts:
        text = str(part).strip()
        if not text or text == "/":
            continue
        segments.extend(segment for segment in text.split("/") if segment)
    return "/" + "/".join(segments) if segments else "/"


def extract_fastapi_endpoints(files: Sequence[tuple[str, str]]) -> list[FastAPIEndpoint]:
    """Return product HTTP routes with ``include_router`` prefixes joined.

    ``files`` is a sequence of ``(relative_path, source_text)`` pairs. Prefixes
    are joined at scan time so inventory paths match the mounted FastAPI app.
    """
    routers: dict[tuple[str, str], _RouterDef] = {}
    imports_by_file: dict[str, dict[str, str]] = {}
    aliases_by_file: dict[str, dict[str, tuple[str, str]]] = {}
    facts_by_file: dict[str, _FileFacts] = {}
    file_set = {path for path, _text in files}

    for path, text in files:
        parsed = _parse_file(path, text)
        if parsed is None:
            continue
        routers_in_file, imported_modules, imported_symbols, facts = parsed
        imports_by_file[path] = imported_modules
        aliases_by_file[path] = imported_symbols
        facts_by_file[path] = facts
        for router in routers_in_file:
            routers[(router.file_path, router.var_name)] = router

    mounted: set[tuple[str, str]] = set()
    endpoints: list[FastAPIEndpoint] = []
    seen_walks: set[tuple[tuple[str, str], str]] = set()

    def resolve_child(parent_file: str, child_ref: str) -> tuple[str, str] | None:
        return _resolve_router_ref(
            parent_file,
            child_ref,
            routers,
            imports_by_file.get(parent_file, {}),
            aliases_by_file.get(parent_file, {}),
            file_set,
        )

    def resolve_mount_prefix(parent_file: str, mount: _Mount) -> str:
        if mount.prefix:
            return mount.prefix
        if not mount.prefix_ref:
            return ""
        return (
            _resolve_prefix_ref(
                parent_file,
                mount.prefix_ref,
                facts_by_file,
                aliases_by_file,
                file_set,
            )
            or ""
        )

    def walk(node_id: tuple[str, str], prefix: str) -> None:
        walk_key = (node_id, prefix)
        if walk_key in seen_walks:
            return
        seen_walks.add(walk_key)
        router = routers.get(node_id)
        if router is None:
            return
        mounted.add(node_id)
        local_prefix = join_http_paths(prefix, router.constructor_prefix)
        for method, path, handler, lineno in router.routes:
            endpoints.append(
                FastAPIEndpoint(
                    method=method,
                    path=join_http_paths(local_prefix, path),
                    handler=handler,
                    file_path=router.file_path,
                    lineno=lineno,
                )
            )
        for mount in router.mounts:
            child = resolve_child(router.file_path, mount.child_ref)
            if child is None:
                continue
            walk(
                child, join_http_paths(local_prefix, resolve_mount_prefix(router.file_path, mount))
            )

    for node_id, router in routers.items():
        if router.is_app:
            walk(node_id, "")

    for node_id, router in routers.items():
        if node_id in mounted or router.is_app:
            continue
        if router.mounts:
            walk(node_id, router.constructor_prefix)
            continue
        local_prefix = router.constructor_prefix
        for method, path, handler, lineno in router.routes:
            endpoints.append(
                FastAPIEndpoint(
                    method=method,
                    path=join_http_paths(local_prefix, path),
                    handler=handler,
                    file_path=router.file_path,
                    lineno=lineno,
                )
            )

    dedup: dict[tuple[str, str, str, str], FastAPIEndpoint] = {}
    for endpoint in endpoints:
        key = (endpoint.method, endpoint.path, endpoint.handler, endpoint.file_path)
        dedup[key] = endpoint
    return list(dedup.values())


def _parse_file(
    path: str, text: str
) -> tuple[list[_RouterDef], dict[str, str], dict[str, tuple[str, str]], _FileFacts] | None:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None

    routers: dict[str, _RouterDef] = {}
    imported_modules: dict[str, str] = {}
    imported_symbols: dict[str, tuple[str, str]] = {}
    facts = _FileFacts()

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[-1]
                imported_modules[local] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = _absolute_module(path, node.module, node.level)
            for alias in node.names:
                local = alias.asname or alias.name
                if module:
                    imported_modules[local] = f"{module}.{alias.name}"
                    imported_symbols[local] = (module, alias.name)
                else:
                    imported_modules[local] = alias.name
                    imported_symbols[local] = (alias.name, alias.name)

    for walked in ast.walk(tree):
        if isinstance(walked, ast.Assign):
            _maybe_bind_router(walked.targets, walked.value, path, routers)
            _maybe_bind_instance(walked.targets, walked.value, facts)
            _maybe_bind_module_str(walked.targets, walked.value, facts)
        elif (
            isinstance(walked, ast.AnnAssign)
            and walked.value is not None
            and walked.target is not None
        ):
            _maybe_bind_router([walked.target], walked.value, path, routers)
            _maybe_bind_instance([walked.target], walked.value, facts)
            _maybe_bind_module_str([walked.target], walked.value, facts)
        elif isinstance(walked, ast.ClassDef):
            _collect_class_str_attrs(walked, facts)

    for walked in ast.walk(tree):
        if isinstance(walked, ast.Call) and _is_include_router(walked):
            parent_var = (
                _name_of(walked.func.value) if isinstance(walked.func, ast.Attribute) else None
            )
            if parent_var is None:
                continue
            if parent_var not in routers:
                routers[parent_var] = _RouterDef(file_path=path, var_name=parent_var)
            child_ref = _expr_ref(walked.args[0]) if walked.args else None
            if not child_ref:
                continue
            prefix, prefix_ref = _prefix_from_call(walked)
            routers[parent_var].mounts.append(
                _Mount(child_ref=child_ref, prefix=prefix, prefix_ref=prefix_ref)
            )
        elif isinstance(walked, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in walked.decorator_list:
                parsed = _decorator_route(decorator)
                if parsed is None:
                    continue
                router_var, method, route_path = parsed
                if router_var not in routers:
                    continue
                routers[router_var].routes.append((method, route_path, walked.name, walked.lineno))

    return list(routers.values()), imported_modules, imported_symbols, facts


def _maybe_bind_router(
    targets: list[ast.expr], value: ast.AST, path: str, routers: dict[str, _RouterDef]
) -> None:
    ctor = _call_ctor_name(value)
    if ctor not in _ROUTER_CTORS or not isinstance(value, ast.Call):
        return
    prefix = _keyword_str(value, "prefix") or ""
    for target in targets:
        if not isinstance(target, ast.Name):
            continue
        routers[target.id] = _RouterDef(
            file_path=path,
            var_name=target.id,
            constructor_prefix=prefix,
            is_app=ctor == "FastAPI",
        )


def _maybe_bind_instance(targets: list[ast.expr], value: ast.AST, facts: _FileFacts) -> None:
    ctor = _call_ctor_name(value)
    if ctor is None or ctor in _ROUTER_CTORS:
        return
    for target in targets:
        if isinstance(target, ast.Name):
            facts.instances[target.id] = ctor


def _maybe_bind_module_str(targets: list[ast.expr], value: ast.AST, facts: _FileFacts) -> None:
    text = _const_str(value)
    if text is None:
        return
    for target in targets:
        if isinstance(target, ast.Name):
            facts.module_str_attrs[target.id] = text


def _collect_class_str_attrs(node: ast.ClassDef, facts: _FileFacts) -> None:
    for stmt in node.body:
        if isinstance(stmt, ast.Assign):
            text = _const_str(stmt.value)
            if text is None:
                continue
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    facts.class_str_attrs[(node.name, target.id)] = text
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            text = _const_str(stmt.value)
            if text is None or not isinstance(stmt.target, ast.Name):
                continue
            facts.class_str_attrs[(node.name, stmt.target.id)] = text


def _prefix_from_call(call: ast.Call) -> tuple[str, str | None]:
    for keyword in call.keywords:
        if keyword.arg != "prefix":
            continue
        literal = _const_str(keyword.value)
        if literal is not None:
            return literal, None
        ref = _expr_ref(keyword.value)
        if ref is not None:
            return "", ref
    return "", None


def _resolve_prefix_ref(
    parent_file: str,
    prefix_ref: str,
    facts_by_file: dict[str, _FileFacts],
    aliases_by_file: dict[str, dict[str, tuple[str, str]]],
    file_set: set[str],
) -> str | None:
    if "." not in prefix_ref:
        return None
    owner, attr = prefix_ref.split(".", 1)

    def lookup(file_path: str, name: str) -> str | None:
        facts = facts_by_file.get(file_path)
        if facts is None:
            return None
        if name in facts.instances:
            class_name = facts.instances[name]
            found = facts.class_str_attrs.get((class_name, attr))
            if found is not None:
                return found
        found = facts.class_str_attrs.get((name, attr))
        if found is not None:
            return found
        if name == attr:
            return facts.module_str_attrs.get(attr)
        return None

    local = lookup(parent_file, owner)
    if local is not None:
        return local

    imported = aliases_by_file.get(parent_file, {}).get(owner)
    if imported is None:
        return None
    module, orig = imported
    target = _find_module_file(module, file_set)
    if target is None:
        return None
    found = lookup(target, orig)
    if found is not None:
        return found
    facts = facts_by_file.get(target)
    if facts is None:
        return None
    values = {value for (cls, name), value in facts.class_str_attrs.items() if name == attr}
    values.update(value for name, value in facts.module_str_attrs.items() if name == attr)
    if len(values) == 1:
        return next(iter(values))
    return None


def _find_module_file(module: str, file_set: set[str]) -> str | None:
    for candidate in _module_file_candidates(module):
        if candidate in file_set:
            return candidate
    stem = module.rsplit(".", 1)[-1]
    matches = [
        path
        for path in file_set
        if path.replace("\\", "/").endswith(f"/{stem}.py") or path == f"{stem}.py"
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _decorator_route(decorator: ast.AST) -> tuple[str, str, str] | None:
    if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
        return None
    method = decorator.func.attr.lower()
    if method not in _HTTP_METHODS:
        return None
    router_var = _name_of(decorator.func.value)
    if router_var is None:
        return None
    path = ""
    if decorator.args:
        extracted = _const_str(decorator.args[0])
        if extracted is not None:
            path = extracted
    for keyword in decorator.keywords:
        if keyword.arg in {"path", "url"}:
            extracted = _const_str(keyword.value)
            if extracted is not None:
                path = extracted
    return router_var, method.upper(), path


def _is_include_router(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Attribute) and node.func.attr == "include_router"


def _resolve_router_ref(
    parent_file: str,
    child_ref: str,
    routers: dict[tuple[str, str], _RouterDef],
    imported_modules: dict[str, str],
    imported_symbols: dict[str, tuple[str, str]],
    file_set: set[str],
) -> tuple[str, str] | None:
    if "." not in child_ref:
        local_key = (parent_file, child_ref)
        if local_key in routers:
            return local_key
        if child_ref in imported_symbols:
            module, orig = imported_symbols[child_ref]
            return _find_router(module, orig, routers, file_set)
        return None

    module_local, attr = child_ref.split(".", 1)
    module_candidates: list[str] = []
    if module_local in imported_modules:
        module_candidates.append(imported_modules[module_local])
    if module_local in imported_symbols:
        module, orig = imported_symbols[module_local]
        module_candidates.append(f"{module}.{orig}")
        module_candidates.append(module)
    for module in module_candidates:
        found = _find_router(module, attr, routers, file_set)
        if found is not None:
            return found
    return None


def _find_router(
    module: str,
    var_name: str,
    routers: dict[tuple[str, str], _RouterDef],
    file_set: set[str],
) -> tuple[str, str] | None:
    for candidate in _module_file_candidates(module):
        if candidate in file_set and (candidate, var_name) in routers:
            return candidate, var_name
    stem = module.rsplit(".", 1)[-1]
    matches = [
        key
        for key in routers
        if key[1] == var_name and key[0].replace("\\", "/").endswith(f"/{stem}.py")
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _module_file_candidates(module: str) -> list[str]:
    path = module.replace(".", "/")
    return [f"{path}.py", f"{path}/__init__.py"]


def _absolute_module(file_path: str, module: str | None, level: int) -> str:
    if level <= 0:
        return module or ""
    parts = list(file_path.replace("\\", "/").removesuffix(".py").split("/"))
    if parts:
        parts = parts[:-1]
    if level > 1:
        parts = parts[: -(level - 1)] if len(parts) >= (level - 1) else []
    extra = module.split(".") if module else []
    return ".".join([*parts, *extra])


def _call_ctor_name(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _keyword_str(call: ast.Call, name: str) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return _const_str(keyword.value)
    return None


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _name_of(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    return None


def _expr_ref(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    return None
