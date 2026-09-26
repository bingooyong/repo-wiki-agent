"""Derive process/binary role facts from the repository being documented."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_DATA_PLANE_RE = re.compile(
    r"data-plane|dataplane|execution pool|execution-pool|probe execution|executionPool",
    re.IGNORECASE,
)
_CONTROL_PLANE_RE = re.compile(
    r"control-plane|control plane|EstablishTunnel|grpc-listen|\b\w*Tunnel\w*Hub\b",
    re.IGNORECASE,
)
_TUNNEL_CLIENT_RE = re.compile(
    r"tunnel client|DialContext|grpc\.Dial\b",
    re.IGNORECASE,
)
_HTTP_SERVER_RE = re.compile(
    r"ListenAndServe|http\.Handle|http\.Server|gin\.Default|gin\.New|fastapi\b|NewController",
    re.IGNORECASE,
)
_ROUTE_RE = re.compile(
    r"""(?:HandleFunc|Handle|RegisterService|RegisterRawRoute|GET|POST|PUT|DELETE|PATCH|OPTIONS)"""
    r"""\s*\(\s*(?:[A-Za-z0-9_.,\s]+,\s*)?['\"](/[^'\"]*)['\"]"""
    r"""|(?:@\w+\.(?:get|post|put|delete|patch)\(\s*['\"](/[^'\"]*)['\"])""",
    re.IGNORECASE,
)
_KEBAB_NAME_RE = re.compile(
    r"\b[a-z][a-z0-9]*-(?:agent|control|probe|server|daemon|exporter|worker)"
    r"(?:-[a-z0-9]+)*\b"
)
_PROCESS_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_/])([A-Za-z][A-Za-z0-9]*-(?:agent|control|probe|server|daemon|exporter|worker)"
    r"(?:-[A-Za-z0-9]+)*)(?![A-Za-z0-9_])"
)
_PROCESS_NOUN_RE = re.compile(
    r"(?<![A-Za-z0-9_/])([A-Za-z][A-Za-z0-9]*-(?:agent|control|probe|server|daemon|exporter|worker)"
    r"(?:-[A-Za-z0-9]+)*|[A-Za-z][A-Za-z0-9_-]*(?:agent|control|probe|server|daemon|exporter|worker))"
    r"\s*(?:进程|二进制|服务)\b"
)
_ROLE_PROCESS_CLAIM_RE = re.compile(
    r"(?<![A-Za-z0-9_/])([A-Za-z][A-Za-z0-9_-]{2,})"
    r"(?:\s*(?:是|承担|负责|作为))"
    r"(?:\s*(?:主\s*)?(?:REST|数据面|控制面|隧道|gRPC))"
)
_FENCE_STRIP_RE = re.compile(r"```.*?```", re.S)
_CMD_PATH_RE = re.compile(r"cmd/([A-Za-z][A-Za-z0-9_-]+)")
_EXAMPLE_HINT_RE = re.compile(r"example|示例|demo|scaffold|sample", re.IGNORECASE)
_GENERIC_ROLE_SUBJECTS = frozenset(
    {
        "this",
        "that",
        "app",
        "api",
        "web",
        "http",
        "grpc",
        "rest",
        "main",
        "core",
        "the",
        "and",
        "for",
        "with",
        "from",
        "service",
        "server",
        "client",
        "router",
        "fastapi",
        "python",
        "readme",
        "alembic",
        "uvicorn",
        "controller",
        "exporter",
        "worker",
        "probe",
        "agent",
        "control",
    }
)


@dataclass(frozen=True)
class RepoProcess:
    name: str
    rel_main: str
    text: str
    docs: str = ""
    route_count: int = 0
    example: bool = False
    in_compose: bool = False
    in_readme_run: bool = False
    kinds: frozenset[str] = field(default_factory=frozenset)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _route_count(text: str) -> int:
    return len(_ROUTE_RE.findall(text or ""))


def _is_example_text(*parts: str) -> bool:
    blob = "\n".join(part or "" for part in parts)
    if not blob:
        return False
    heading = next((line.strip() for line in blob.splitlines() if line.strip()), "")
    return bool(_EXAMPLE_HINT_RE.search(heading) or _EXAMPLE_HINT_RE.search(blob[:400]))


def _compose_service_names(root: Path) -> set[str]:
    names: set[str] = set()
    for rel in (
        "compose.yaml",
        "compose.yml",
        "docker-compose.yml",
        "docker-compose.yaml",
        "podman-compose.yml",
        "podman-compose.yaml",
    ):
        path = root / rel
        if not path.is_file():
            continue
        current = ""
        for raw in _read_text(path).splitlines():
            match = re.match(r"^  ([A-Za-z][A-Za-z0-9_-]*):\s*$", raw)
            if match:
                current = match.group(1)
                names.add(current)
    return names


def _readme_run_blob(root: Path) -> str:
    chunks: list[str] = []
    for name in ("README.md", "README.rst", "README.txt", "README", "QUICKSTART.md"):
        path = root / name
        if path.is_file():
            chunks.append(_read_text(path))
    return "\n".join(chunks)


def _imported_route_text(root: Path, main_text: str) -> str:
    extra: list[str] = []
    seen: set[Path] = set()
    for match in re.finditer(r'"([A-Za-z0-9._/-]+)"', main_text or ""):
        spec = match.group(1)
        if spec.startswith("."):
            continue
        local = spec.split("/")[-1]
        candidates = [
            root / f"{local}.go",
            root / local / "controller.go",
            root / "controller.go",
        ]
        if "/" in spec:
            suffix = spec.split("/", 1)[-1]
            candidates.append(root / f"{suffix}.go")
            candidates.append(root / suffix)
        for candidate in candidates:
            if not candidate.is_file() or candidate in seen:
                continue
            seen.add(candidate)
            extra.append(_read_text(candidate)[:12000])
    controller = root / "controller.go"
    if controller.is_file() and controller not in seen:
        extra.append(_read_text(controller)[:12000])
    return "\n".join(extra)


def _process_from_main(
    base: Path,
    main: Path,
    name: str,
    compose_names: set[str],
    readme_run: str,
) -> RepoProcess | None:
    text = _read_text(main)
    if not text:
        return None
    docs = ""
    for readme in ("README.md", "README.rst", "README.txt"):
        candidate = main.parent / readme
        if candidate.is_file():
            docs = _read_text(candidate)
            break
    combined = "\n".join([text, docs, _imported_route_text(base, text)])
    kinds: set[str] = set()
    if _DATA_PLANE_RE.search(combined):
        kinds.add("data_plane")
    if _CONTROL_PLANE_RE.search(combined):
        kinds.add("control_plane")
    if _TUNNEL_CLIENT_RE.search(combined):
        kinds.add("tunnel_client")
    if _HTTP_SERVER_RE.search(combined):
        kinds.add("http_server")
    return RepoProcess(
        name=name,
        rel_main=main.relative_to(base).as_posix(),
        text=combined,
        docs=docs,
        route_count=_route_count(combined),
        example=_is_example_text(docs, text[:800]),
        in_compose=name.lower() in {item.lower() for item in compose_names},
        in_readme_run=name.lower() in readme_run,
        kinds=frozenset(kinds),
    )


def discover_cmd_processes(root: Path | str | None) -> list[RepoProcess]:
    """Return Go entry binaries from any product ``main.go``."""
    if root is None:
        return []
    base = Path(root)
    compose_names = _compose_service_names(base)
    readme_run = _readme_run_blob(base).lower()
    found: list[RepoProcess] = []
    skip = {".git", ".repo-agent-eval", "vendor", "node_modules", "testdata"}
    seen: set[str] = set()
    for main in sorted(base.rglob("main.go")):
        if any(part in skip for part in main.parts) or main.name.endswith("_test.go"):
            continue
        rel = main.relative_to(base).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        name = main.parent.name or "main"
        item = _process_from_main(base, main, name, compose_names, readme_run)
        if item is not None:
            found.append(item)
    return found


def derive_repo_identity_names(root: Path | str | None) -> set[str]:
    """Product and module names: README H1, go.mod module, repo slug."""
    names: set[str] = set()
    if root is None:
        return names
    base = Path(root)
    names.add(base.name)
    names.add(base.name.replace("-", "_"))
    names.add(base.name.replace("_", "-"))
    for name in ("README.md", "README.rst", "README.txt", "README"):
        path = base / name
        if not path.is_file():
            continue
        rows = _read_text(path).splitlines()
        for index, line in enumerate(rows):
            stripped = line.strip()
            if stripped.startswith("# "):
                title = re.sub(r"[`*]", "", stripped[2:]).strip()
                if title:
                    names.add(title.split()[0])
                    names.update(re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", title))
                break
            if index + 1 < len(rows) and re.fullmatch(r"[-=]{3,}", rows[index + 1].strip()):
                title = re.sub(r"[`*]", "", stripped).strip()
                if title and not title.startswith(".."):
                    names.add(title.split()[0])
                    names.update(re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", title))
                break
    go_mod = base / "go.mod"
    if go_mod.is_file():
        for line in _read_text(go_mod).splitlines():
            if line.startswith("module "):
                module = line.split()[1].strip().rstrip("/")
                names.add(module.split("/")[-1])
                names.add(module.split("/")[-1].replace("-", "_"))
    pyproject = base / "pyproject.toml"
    if pyproject.is_file():
        hit = re.search(r'(?m)^name\s*=\s*["\']([^"\']+)["\']', _read_text(pyproject))
        if hit:
            names.add(hit.group(1))
            names.add(hit.group(1).split("/")[-1])
    return {item for item in names if item and item.lower() not in _GENERIC_ROLE_SUBJECTS}


def derive_repo_process_names(root: Path | str | None) -> set[str]:
    """Names of binaries, packages, product tokens, and process-like tokens."""
    names = {item.name for item in discover_cmd_processes(root)}
    names.update(derive_repo_identity_names(root))
    if root is None:
        return names
    base = Path(root)
    for folder in ("internal", "pkg", "app"):
        path = base / folder
        if not path.is_dir():
            continue
        names.add(folder)
        for child in path.iterdir():
            if child.is_dir() and child.name not in {"__pycache__", "tests", "test"}:
                names.add(child.name)
    for path in base.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {
            ".go",
            ".py",
            ".md",
            ".rst",
            ".yml",
            ".yaml",
            ".toml",
            ".sh",
        }:
            continue
        rel = path.relative_to(base).as_posix()
        if rel.startswith(".") or "/." in rel or ".repo-agent-eval" in rel.split("/"):
            continue
        if any(part in {"vendor", "node_modules", "__pycache__", ".git"} for part in path.parts):
            continue
        text = _read_text(path)
        names.update(_KEBAB_NAME_RE.findall(text))
    return names


def _main_entry_candidates(processes: list[RepoProcess]) -> list[RepoProcess]:
    """HTTP server + real routes is the REST/Web entry even if it also embeds gRPC."""
    eligible = [
        item
        for item in processes
        if not item.example and "http_server" in item.kinds and item.route_count > 0
    ]
    if eligible:
        return eligible
    return [item for item in processes if not item.example and "http_server" in item.kinds]


def _score_main_entry(item: RepoProcess) -> tuple[int, int, int, str]:
    score = item.route_count
    if item.in_compose:
        score += 50
    if item.in_readme_run:
        score += 30
    return (score, item.route_count, int(item.in_compose), item.name)


def derive_process_roles(root: Path | str | None) -> list[RepoProcess]:
    """Ranked process list with kinds filled in after example/main-entry rules."""
    processes = list(discover_cmd_processes(root))
    if not processes:
        return []
    main_entry = None
    candidates = _main_entry_candidates(processes)
    if candidates:
        main_entry = max(candidates, key=_score_main_entry)
    ranked: list[RepoProcess] = []
    for item in processes:
        kinds = set(item.kinds)
        if item.example:
            kinds.discard("http_server")
            kinds.add("example")
        if main_entry is not None and item.name == main_entry.name:
            kinds.add("rest_entry")
        ranked.append(
            RepoProcess(
                name=item.name,
                rel_main=item.rel_main,
                text=item.text,
                docs=item.docs,
                route_count=item.route_count,
                example=item.example,
                in_compose=item.in_compose,
                in_readme_run=item.in_readme_run,
                kinds=frozenset(kinds),
            )
        )
    return ranked


def derive_process_role_facts(root: Path | str | None) -> str:
    """Positive role facts derived from cmd/* comments, routes, and docs."""
    processes = derive_process_roles(root)
    if not processes:
        return ""
    control = next((item for item in processes if "control_plane" in item.kinds), None)
    facts: list[str] = []
    for item in processes:
        fact = _fact_for(item, control)
        if fact:
            facts.append(fact)
    return "；".join(facts) + "。" if facts else ""


def cmd_dir_name(file_path: str) -> str:
    """Return the cmd/<name> directory leaf from a repository-relative path."""
    parts = Path(str(file_path or "")).parts
    if "cmd" not in parts:
        return ""
    index = parts.index("cmd")
    if index + 1 >= len(parts):
        return ""
    return parts[index + 1]


def path_looks_like_example_cmd(file_path: str) -> bool:
    """True when a cmd/* path is an example/demo/scaffold tool."""
    name = cmd_dir_name(file_path)
    blob = name or str(file_path or "")
    return bool(_EXAMPLE_HINT_RE.search(blob))


def repo_has_go_cmd_binaries(root: Path | str | None) -> bool:
    return bool(discover_cmd_processes(root))


def unknown_process_mentions(markdown: str, allowed: set[str]) -> list[str]:
    """Process/binary names claimed in prose that are not in the documented repo.

    Standalone kebab tokens such as volume names or generic slugs are
    ignored. Only ``cmd/X``,
    ``X 进程/二进制/服务``, and explicit REST/data-plane/control-plane role
    claims are considered.
    """
    text = _FENCE_STRIP_RE.sub("", markdown or "")
    found: set[str] = set()
    allowed_l = {item.lower() for item in allowed}

    def _consider(name: str) -> None:
        if not name or name.lower() in _GENERIC_ROLE_SUBJECTS:
            return
        if "_" in name:
            return
        if name in allowed or name.lower() in allowed_l:
            return
        lowered = name.lower()
        if any(
            lowered == item.lower()
            or item.lower().endswith(lowered)
            or item.lower().endswith(f"-{lowered}")
            for item in allowed
        ):
            return
        found.add(name)

    for match in _CMD_PATH_RE.finditer(text):
        _consider(match.group(1))
    for match in _PROCESS_NOUN_RE.finditer(text):
        _consider(match.group(1))
    for match in _ROLE_PROCESS_CLAIM_RE.finditer(text):
        _consider(match.group(1))
    return sorted(found)


def strip_unknown_process_clauses(markdown: str, allowed: set[str]) -> str:
    """Verifier helper only: do not call this on the generate path.

    Rewrites must not delete reader prose. Keep the function for tests that
    still exercise the historical clause splitter.
    """
    return markdown


def _execution_pool_label(text: str) -> str:
    if re.search(r"execution pool|execution-pool", text or "", re.IGNORECASE):
        return "运行执行池"
    return ""


def _fact_for(item: RepoProcess, control: RepoProcess | None) -> str:
    bits: list[str] = []
    if item.example:
        bits.append("是示例工具")
    elif "rest_entry" in item.kinds:
        bits.append("是主 REST/Web 服务与管理入口")
    elif "data_plane" in item.kinds:
        bits.append("是数据面进程")
        pool = _execution_pool_label(item.text)
        if pool:
            bits.append(pool)
        if "tunnel_client" in item.kinds and control is not None:
            bits.append(f"并拨号连向 {control.name} 的隧道")
    elif "control_plane" in item.kinds:
        if re.search(r"gRPC|grpc", item.text):
            bits.append("是 gRPC 控制面")
        else:
            bits.append("是控制面")
    if not bits:
        return ""
    return f"{item.name} {'，'.join(bits)}"
