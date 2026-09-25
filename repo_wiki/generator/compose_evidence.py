"""Deterministic compose / import / install evidence — no invented edges."""

from __future__ import annotations

import re
from pathlib import Path

_DEP_CLAIM_RE = re.compile(
    r"`?(internal/[A-Za-z0-9_-]+|cmd/[A-Za-z0-9_-]+|app/[A-Za-z0-9_/-]+)`?"
    r"\s*(?:依赖|depends(?:\s+on)?)\s*"
    r"`?(internal/[A-Za-z0-9_-]+|cmd/[A-Za-z0-9_-]+|app/[A-Za-z0-9_/-]+)`?",
    re.IGNORECASE,
)
_PLACEHOLDER_OPS_RE = re.compile(
    r"cmd_start\[start\].*cmd_build\[build\].*cmd_test\[test\].*cmd_lint\[lint\]",
    re.IGNORECASE | re.DOTALL,
)
_GENERIC_OPS_LABEL_RE = re.compile(r"\[(start|build|test|lint)\]", re.IGNORECASE)
_ROLE_CCAGENT_TUNNEL_RE = re.compile(
    r"ccagent(?:(?!probe-agent|探针|才是)[^。\n]){0,80}"
    r"(?<!不)(?<!不作为)(?<!探针)(?<!才是)隧道客户端"
    r"(?![^。\n]{0,60}(?:由|交由)\s*`?probe-agent)",
    re.IGNORECASE,
)
_ROLE_CCAGENT_REVERSE_RE = re.compile(
    r"ccagent[^。\n]{0,120}建立反向控制链路|"
    r"ccagent[^。\n]{0,80}通过\s*`?-agent-url",
    re.IGNORECASE,
)
_ROLE_CUSTOM_SUBPROCESS_RE = re.compile(
    r"custom-probe[^。\n]{0,80}(?:子进程|外部进程被拉起|作为外部进程|subprocess)",
    re.IGNORECASE,
)
_SVC_NODE_RE = re.compile(r"^\s*([A-Za-z][\w-]*)\[([^\]]+)\]\s*$", re.MULTILINE)
_FLOW_EDGE_RE = re.compile(r"^\s*([A-Za-z][\w-]*)\s*-->\s*([A-Za-z][\w-]*)\s*$", re.MULTILINE)
_STARTED_RE = re.compile(
    r"(?:podman-compose|docker-compose|docker\s+compose)\s+up(?:\s+-d)?(?:\s+([A-Za-z0-9_-]+))?"
    r"|podman\s+run\b[^\n]*--name\s+([A-Za-z0-9_-]+)"
    r"|docker\s+run\b[^\n]*(?:--name\s+)?([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)
_REFERENCED_RE = re.compile(
    r"(?:podman\s+exec|docker\s+exec)\s+([A-Za-z0-9_-]+)"
    r"|(?:podman-compose|docker-compose|docker\s+compose)\s+up(?:\s+-d)?\s+([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)


def parse_compose_env_file_edges(text: str) -> list[tuple[str, str]]:
    """Return (.env, service) edges only when that service declares env_file."""
    if not (text or "").strip():
        return []
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
    except Exception:
        data = None
    edges: list[tuple[str, str]] = []
    if isinstance(data, dict) and isinstance(data.get("services"), dict):
        for name, spec in data["services"].items():
            if not isinstance(spec, dict):
                continue
            env_file = spec.get("env_file")
            if env_file:
                edges.append((".env", str(name)))
        return edges
    current = ""
    for raw in (text or "").splitlines():
        svc = re.match(r"^  ([A-Za-z][A-Za-z0-9_-]*):\s*$", raw)
        if svc:
            current = svc.group(1)
            continue
        if current and re.match(r"^    env_file:\s*", raw):
            edges.append((".env", current))
    return edges


def parse_compose_topology(text: str) -> tuple[list[str], list[tuple[str, str]]]:
    """Return service names and real depends_on edges. Networks/volumes are omitted."""
    if not (text or "").strip():
        return [], []
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
    except Exception:
        data = None
    if not isinstance(data, dict):
        return _parse_compose_fallback(text)
    services = data.get("services")
    if not isinstance(services, dict):
        return [], []
    names = [str(name) for name in services if str(name).strip()]
    name_set = set(names)
    edges: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for src, spec in services.items():
        src_s = str(src)
        deps = spec.get("depends_on") if isinstance(spec, dict) else None
        dests: list[str] = []
        if isinstance(deps, dict):
            dests = [str(item) for item in deps]
        elif isinstance(deps, list):
            for item in deps:
                dests.append(str(item) if not isinstance(item, dict) else next(iter(item), ""))
        elif isinstance(deps, str):
            dests = [deps]
        for dest in dests:
            dest_s = dest.strip()
            if dest_s in name_set and dest_s != src_s and (src_s, dest_s) not in seen:
                seen.add((src_s, dest_s))
                edges.append((src_s, dest_s))
    return names, edges


def _parse_compose_fallback(text: str) -> tuple[list[str], list[tuple[str, str]]]:
    """Indent-aware fallback when YAML is unavailable or invalid."""
    names: list[str] = []
    edges: list[tuple[str, str]] = []
    section = ""
    current = ""
    in_depends = False
    for raw in text.splitlines():
        if re.match(r"^[A-Za-z][A-Za-z0-9_-]*:\s*$", raw):
            section = raw.split(":", 1)[0]
            current = ""
            in_depends = False
            continue
        svc = re.match(r"^  ([A-Za-z][A-Za-z0-9_-]*):\s*$", raw)
        if svc and section == "services":
            current = svc.group(1)
            names.append(current)
            in_depends = False
            continue
        if current and re.match(r"^    depends_on:\s*$", raw):
            in_depends = True
            continue
        if in_depends:
            listed = re.match(r"^      - ([A-Za-z][A-Za-z0-9_-]+)\s*$", raw)
            mapped = re.match(r"^      ([A-Za-z][A-Za-z0-9_-]+):\s*$", raw)
            dest = listed.group(1) if listed else (mapped.group(1) if mapped else "")
            if dest and dest != current:
                edges.append((current, dest))
            elif raw.startswith("    ") and not raw.startswith("      ") and raw.strip():
                in_depends = False
    name_set = set(names)
    return names, [(src, dest) for src, dest in edges if dest in name_set]


def load_compose_from_root(root: Path) -> tuple[list[str], list[tuple[str, str]]]:
    for name in (
        "podman-compose.yml",
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
    ):
        path = root / name
        if path.is_file():
            raw = path.read_text(encoding="utf-8", errors="ignore")
            names, depends = parse_compose_topology(raw)
            return names, [*depends, *parse_compose_env_file_edges(raw)]
    return [], []


def mermaid_compose_edges(block: str) -> list[tuple[str, str]]:
    labels = {node: label for node, label in _SVC_NODE_RE.findall(block)}
    edges: list[tuple[str, str]] = []
    for src, dest in _FLOW_EDGE_RE.findall(block):
        left = labels.get(src, src)
        right = labels.get(dest, dest)
        edges.append((left, right))
    return edges


def invented_compose_edges(markdown: str, allowed: list[tuple[str, str]]) -> list[tuple[str, str]]:
    allowed_set = {(src, dest) for src, dest in allowed}
    allowed_names = {src for src, dest in allowed} | {dest for src, dest in allowed}
    compose_names = {name for name in allowed_names if name != ".env"}
    found: list[tuple[str, str]] = []
    for block in re.findall(r"```mermaid\s*(.*?)```", markdown or "", flags=re.I | re.S):
        if "erDiagram" in block or "sequenceDiagram" in block:
            continue
        if "ccagent" not in block and "mysql" not in block and "blackbox" not in block:
            if "app[" not in block and "db[" not in block:
                continue
        for src, dest in mermaid_compose_edges(block):
            if src in {"start", "finish"} or dest in {"start", "finish"}:
                continue
            if src == ".env" and dest not in compose_names:
                continue
            if (
                (src, dest) not in allowed_set
                and {src, dest} & (allowed_names | {"probe-network", "mysql-data", "ccagent-logs"})
                or src.endswith("-network")
                or dest.endswith("-data")
                or dest.endswith("-logs")
            ):
                found.append((src, dest))
    return found


def is_placeholder_ops_diagram(markdown: str) -> bool:
    """True for invented Start→build→test→lint chains, even without a start node."""
    for block in re.findall(r"```mermaid\s*(.*?)```", markdown or "", flags=re.I | re.S):
        compact = re.sub(r"\s+", " ", block)
        generic = _GENERIC_OPS_LABEL_RE.findall(block)
        if _PLACEHOLDER_OPS_RE.search(block) or (
            "cmd_start[start]" in compact
            and "cmd_build[build]" in compact
            and "cmd_test[test]" in compact
            and "cmd_lint[lint]" in compact
        ):
            return True
        if len(generic) >= 2 and re.search(
            r"start\s*-->|-->\s*(cmd_)?(build|test|lint)", compact, re.I
        ):
            return True
    return False


def install_path_gaps(markdown: str) -> list[str]:
    """Each ### 路径 must start every container it later execs/up's."""
    gaps: list[str] = []
    if "## 安装步骤" not in (markdown or ""):
        return gaps
    body = (markdown or "").split("## 安装步骤", 1)[1]
    body = re.split(r"^##\s+", body, maxsplit=1, flags=re.M)[0]
    chunks = re.split(r"^###\s+", body, flags=re.M)
    for chunk in chunks[1:]:
        title, _, rest = chunk.partition("\n")
        started = set()
        for match in _STARTED_RE.finditer(rest):
            name = next((item for item in match.groups() if item), "")
            if name:
                started.add(name)
            elif "compose up" in match.group(0) and "-d" in match.group(0):
                started.add("*compose*")
        if "podman-compose up" in rest or re.search(r"docker-compose up -d\s*$", rest, re.M):
            started.add("*compose*")
        for match in _REFERENCED_RE.finditer(rest):
            ref = next((item for item in match.groups() if item), "")
            if not ref:
                continue
            if ref not in started and "*compose*" not in started:
                gaps.append(f"{title.strip()}:{ref}")
    return gaps


def load_repo_import_edges(root: Path) -> set[tuple[str, str]]:
    from repo_wiki.generator.mermaid_planner import extract_python_app_import_edges
    from repo_wiki.scanner.go_routes import extract_go_internal_import_edges

    edges: set[tuple[str, str]] = set()
    go_files: list[tuple[str, str]] = []
    for base in (root / "cmd", root / "internal", root / "pkg"):
        if not base.is_dir():
            continue
        for path in base.rglob("*.go"):
            if path.name.endswith("_test.go"):
                continue
            go_files.append(
                (
                    path.relative_to(root).as_posix(),
                    path.read_text(encoding="utf-8", errors="ignore"),
                )
            )
    if go_files:
        edges.update(extract_go_internal_import_edges(go_files))
    py_files: list[tuple[str, str]] = []
    app = root / "app"
    if app.is_dir():
        for path in app.rglob("*.py"):
            py_files.append(
                (
                    path.relative_to(root).as_posix(),
                    path.read_text(encoding="utf-8", errors="ignore"),
                )
            )
    if py_files:
        edges.update(extract_python_app_import_edges(py_files))
    return edges


def prose_import_contradictions(markdown: str, edges: set[tuple[str, str]]) -> list[str]:
    """Flag 'A 依赖 B' when the import graph has no A->B (and often has B->A)."""
    if not edges:
        return []
    found: list[str] = []
    for match in _DEP_CLAIM_RE.finditer(markdown or ""):
        src, dest = match.group(1), match.group(2)
        if (src, dest) in edges:
            continue
        found.append(f"{src}->{dest}")
    return found


def rewrite_false_import_claims(markdown: str, edges: set[tuple[str, str]]) -> str:
    """Rewrite machine-checkable 'A 依赖 B' claims that contradict the import graph."""
    if not edges:
        return markdown or ""
    text = markdown or ""
    for match in reversed(list(_DEP_CLAIM_RE.finditer(text))):
        src, dest = match.group(1), match.group(2)
        if (src, dest) in edges:
            continue
        if (dest, src) in edges:
            repl = f"{dest} 依赖 {src}"
        else:
            repl = f"{src} 不依赖 {dest}"
        text = text[: match.start()] + repl + text[match.end() :]
    return text


def prose_role_contradictions(markdown: str) -> list[str]:
    """Flag architecture prose that contradicts the deterministic process roles."""
    text = markdown or ""
    found: list[str] = []
    if _ROLE_CCAGENT_TUNNEL_RE.search(text):
        found.append("ccagent-as-tunnel-client")
    if _ROLE_CCAGENT_REVERSE_RE.search(text):
        found.append("ccagent-reverse-agent-url")
    if _ROLE_CUSTOM_SUBPROCESS_RE.search(text):
        found.append("custom-probe-as-subprocess")
    return found


_FORMER_LATTER_ROLE_SWAP_RE = re.compile(
    r"ccprobe-control[^。\n]{0,80}ccagent[^。\n]{0,40}前者[^。\n]{0,80}"
    r"(?:主 REST|REST/Web)[^。\n]{0,80}后者[^。\n]{0,80}隧道客户端",
    re.IGNORECASE,
)
_PROBE_AGENT_SCHEDULED_BY_CCAGENT_RE = re.compile(
    r"probe-agent[^。\n]{0,48}被\s*`?ccagent`?\s*调度",
    re.IGNORECASE,
)


def generator_role_contradictions(markdown: str, page: object | None = None) -> list[str]:
    """Composer-only role checks, including 前者/后者 swaps. Does not change the verifier."""
    title = str(getattr(page, "title", "") or "")
    page_id = str(getattr(page, "page_id", "") or "")
    category = getattr(page, "category", None)
    category_text = str(getattr(category, "value", category) or "")
    output_path = str(getattr(page, "output_path", "") or "")
    blob = f"{title} {page_id} {category_text} {output_path}"
    architecture = "架构" in blob or "architecture" in blob.lower()
    overview = page_id in {"project-overview"} or title in {
        "项目概述",
        "项目概览",
        "project overview",
    }
    found: list[str] = []
    if architecture:
        found.extend(prose_role_contradictions(markdown))
        if _FORMER_LATTER_ROLE_SWAP_RE.search(markdown or ""):
            found.append("former-latter-role-swap")
    if overview and _PROBE_AGENT_SCHEDULED_BY_CCAGENT_RE.search(markdown or ""):
        found.append("probe-agent-scheduled-by-ccagent")
    return found


def derive_product_name(root: Path) -> str:
    """Name the product from README / go.mod / pyproject / remote, never the checkout dir."""
    readme_md = root / "README.md"
    if readme_md.is_file():
        for line in readme_md.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                title = re.sub(r"^#+\s*", "", stripped)
                title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", title).strip()
                title = re.sub(r"[`*]", "", title).strip()
                if title and len(title) < 80:
                    return title.split()[0]
    go_mod = root / "go.mod"
    if go_mod.is_file():
        for line in go_mod.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("module "):
                module = line.split()[1].strip().rstrip("/")
                return module.split("/")[-1]
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        hit = re.search(
            r'(?m)^name\s*=\s*["\']([^"\']+)["\']',
            pyproject.read_text(encoding="utf-8", errors="ignore"),
        )
        if hit:
            return hit.group(1)
    git_config = root / ".git" / "config"
    if git_config.is_file():
        text = git_config.read_text(encoding="utf-8", errors="ignore")
        hit = re.search(r"url\s*=\s*.+[/:]([^/\s]+?)(?:\.git)?\s*$", text, re.M)
        if hit and hit.group(1) not in {".", "origin"}:
            return hit.group(1)
    return ""


def jwt_token_prefix(root: Path) -> str:
    settings = root / "app" / "core" / "settings"
    if settings.is_dir():
        for path in settings.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            hit = re.search(r'jwt_token_prefix\s*[:=]\s*["\']([^"\']+)["\']', text)
            if hit:
                return hit.group(1)
    auth = root / "app" / "api" / "dependencies" / "authentication.py"
    if auth.is_file():
        text = auth.read_text(encoding="utf-8", errors="ignore")
        hit = re.search(r'["\'](Token|Bearer)["\']', text)
        if hit:
            return hit.group(1)
    return "Token" if (root / "app" / "services" / "jwt.py").is_file() else "Bearer"
