"""Facts checked against parsed repository sources, not handbook prose."""

from __future__ import annotations

import re
from pathlib import Path

from repo_wiki.generator.compose_evidence import parse_compose_topology
from repo_wiki.verifier.handbook import _CITE_RE, iter_markdown_pages, read_readme_text

_COMPOSE_FILES = (
    "compose.yaml",
    "compose.yml",
    "docker-compose.yml",
    "docker-compose.yaml",
    "podman-compose.yml",
    "podman-compose.yaml",
)
_KEBAB_RE = re.compile(r"\b([a-z][a-z0-9]*(?:-[a-z0-9]+)+)\b")
_BACKTICK_TOKEN_RE = re.compile(r"`([A-Za-z][A-Za-z0-9_.-]{1,64})`")
_TABLE_RE = re.compile(
    r"""(?:CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?|op\.create_table\(\s*|Table\(\s*)['\"`]?([A-Za-z_][A-Za-z0-9_]*)""",
    re.I,
)
_FLAG_DEF_RE = re.compile(
    r"""(?:flag\.(?:String|StringVar|Bool)|Flags\(\)\.String)\(\s*(?:&[A-Za-z0-9_.]+,\s*)?["']-?([^"']+)["']\s*,\s*["'][^"']*["']\s*,\s*["']([^"']+)["']""",
    re.S,
)
_ARGPARSE_RE = re.compile(
    r"""add_argument\(\s*["']--([^"']+)["'][^)]*help\s*=\s*["']([^"']+)["']""",
    re.S,
)
_FLAG_MENTION_RE = re.compile(r"`--?([A-Za-z0-9-]+)`")
_TYPE_RE = re.compile(r"`([A-Z][A-Za-z0-9]{5,})`")
_HEALTH_ROUTE_RE = re.compile(r"""["'](/(?:healthz?|readyz|livez)[^"']*)["']""")
_GENERIC_COMPOSE = frozenset(
    {
        "docker-compose",
        "podman-compose",
        "docker",
        "compose",
        "podman",
        "env-file",
        "health-check",
        "readyz",
        "livez",
        "yaml",
        "yml",
        "localhost",
        "restart",
        "unless-stopped",
        "healthcheck",
        "networks",
        "volumes",
        "environment",
        "dockerfile",
        "bind-addr",
        "container-name",
    }
)
_GENERIC_TABLES = frozenset(
    {
        "alembic",
        "env",
        "head",
        "upgrade",
        "downgrade",
        "revision",
        "postgres",
        "postgresql",
        "sqlalchemy",
        "metadata",
        "versions",
        "schema",
        "base",
    }
)
_GENERIC_TYPES = frozenset(
    {
        "Readme",
        "Bearer",
        "Docker",
        "GitHub",
        "FastAPI",
        "PostgreSQL",
        "SQLAlchemy",
        "Alembic",
        "HTTPException",
    }
)
_SAMPLE_QUALIFIER_RE = re.compile(r"示例|README|文档样例|仅出现在")
_API_PRESENTATION_RE = re.compile(r"接口|类型|依赖|触发|handler|工厂|合同")


def load_compose_service_names(root: Path) -> set[str]:
    names: set[str] = set()
    for rel in _COMPOSE_FILES:
        path = root / rel
        if not path.is_file():
            continue
        parsed, _edges = parse_compose_topology(path.read_text(encoding="utf-8", errors="ignore"))
        names.update(parsed)
    return names


def load_database_tables(root: Path) -> set[str]:
    tables: set[str] = set()
    for folder in (
        root / "app" / "db" / "migrations",
        root / "alembic" / "versions",
        root / "db" / "migrations",
        root / "db",
    ):
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".py", ".sql"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            tables.update(match.group(1) for match in _TABLE_RE.finditer(text))
    schema = root / "db" / "schema.sql"
    if schema.is_file():
        tables.update(
            match.group(1)
            for match in _TABLE_RE.finditer(schema.read_text(encoding="utf-8", errors="ignore"))
        )
    return {name for name in tables if name.lower() not in {"if", "table", "exists"}}


def load_cli_flag_help(root: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    search_roots = [root / "cmd", root / "app", root]
    seen: set[Path] = set()
    for folder in search_roots:
        if not folder.exists():
            continue
        pattern = "*.go" if folder.name == "cmd" else "*"
        iterator = folder.rglob(pattern) if folder.is_dir() else []
        for path in iterator:
            resolved = path.resolve()
            if resolved in seen or not path.is_file():
                continue
            if path.suffix.lower() not in {".go", ".py"}:
                continue
            if path.name.endswith("_test.go") or path.name.startswith("test_"):
                continue
            seen.add(resolved)
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in _FLAG_DEF_RE.finditer(text):
                found[match.group(1).lstrip("-")] = match.group(2)
            for match in _ARGPARSE_RE.finditer(text):
                found[match.group(1).lstrip("-")] = match.group(2)
    return found


def load_source_identifiers(root: Path) -> set[str]:
    names: set[str] = set()
    skip = {".git", ".repo-agent-eval", "vendor", "node_modules", "__pycache__"}
    simple = re.compile(r"\b(?:type|class|def|func)\s+([A-Za-z_][A-Za-z0-9_]+)")
    method = re.compile(r"\bfunc\s+\([^)]+\)\s+([A-Za-z_][A-Za-z0-9_]+)")
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".go", ".py"}:
            continue
        if any(part in skip for part in path.parts) or path.name.endswith("_test.go"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        names.update(simple.findall(text))
        names.update(method.findall(text))
    return names


def load_cmd_names(root: Path) -> set[str]:
    cmd = root / "cmd"
    if not cmd.is_dir():
        return set()
    return {child.name for child in cmd.iterdir() if child.is_dir()}


def load_health_routes(root: Path) -> list[str]:
    blob = ""
    controller = root / "controller.go"
    if controller.is_file():
        blob += controller.read_text(encoding="utf-8", errors="ignore")
    cmd = root / "cmd"
    if cmd.is_dir():
        for child in cmd.rglob("*.go"):
            if child.name.endswith("_test.go"):
                continue
            if "health" in child.name.lower() or child.name == "main.go":
                blob += child.read_text(encoding="utf-8", errors="ignore")
    for rel in ("app/main.py", "app/api/routes/health.py"):
        path = root / rel
        if path.is_file():
            blob += path.read_text(encoding="utf-8", errors="ignore")
    return list(dict.fromkeys(_HEALTH_ROUTE_RE.findall(blob)))


def alembic_uses_model_metadata(root: Path) -> bool:
    for rel in (
        Path("app") / "db" / "migrations" / "env.py",
        Path("alembic") / "env.py",
    ):
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"target_metadata\s*=\s*None\b", text):
            return False
        if re.search(r"target_metadata\s*=\s*\w+", text):
            return True
    return False


def _mentioned_compose_services(text: str) -> set[str]:
    if not re.search(r"compose|docker|podman", text, flags=re.I):
        return set()
    names: set[str] = set()
    blob = text or ""
    for match in _KEBAB_RE.finditer(blob):
        token = match.group(1)
        if token in _GENERIC_COMPOSE:
            continue
        lo, hi = match.start(), match.end()
        if lo > 0 and blob[lo - 1] in "/\\-":
            continue
        if hi < len(blob) and blob[hi] in "/\\":
            continue
        names.add(token)
    for token in _BACKTICK_TOKEN_RE.findall(blob):
        lowered = token.lower()
        if lowered in _GENERIC_COMPOSE:
            continue
        if any(lowered.endswith(ext) for ext in (".yml", ".yaml", ".md", ".sql", ".go", ".py")):
            continue
        if re.fullmatch(r"[a-z][a-z0-9_-]{1,32}", lowered):
            names.add(lowered)
    return names


def _mentioned_tables(text: str) -> set[str]:
    names: set[str] = set()
    for token in re.findall(r"`([a-z][a-z0-9_]{2,})`", text or ""):
        if token in _GENERIC_TABLES:
            continue
        if "_" in token or (token.endswith("s") and len(token) >= 5):
            names.add(token)
    return names


def _sentence_window(text: str, index: int) -> str:
    start = max(text.rfind("。", 0, index), text.rfind("\n", 0, index))
    end_candidates = [pos for pos in (text.find("。", index), text.find("\n", index)) if pos >= 0]
    end = min(end_candidates) if end_candidates else len(text)
    return text[start + 1 : end]


def _flag_target_mismatches(text: str, flags: dict[str, str], cmd_names: set[str]) -> list[str]:
    hits: list[str] = []
    leaves = {name.split("/")[-1] for name in cmd_names}
    for match in _FLAG_MENTION_RE.finditer(text or ""):
        flag = match.group(1)
        help_text = flags.get(flag, "")
        if not help_text:
            continue
        sentence = _sentence_window(text, match.start())
        mentioned = [leaf for leaf in leaves if re.search(rf"\b{re.escape(leaf)}\b", sentence)]
        if not mentioned:
            continue
        help_l = help_text.lower().replace("_", "-")
        if any(leaf.lower().replace("_", "-") in help_l for leaf in mentioned):
            continue
        help_cmds = [leaf for leaf in leaves if leaf.lower().replace("_", "-") in help_l]
        if help_cmds or "probe-agent" in help_l or "control url" in help_l:
            hits.append(f"flag:{flag}")
    return hits


def _ident_offenders(text: str, idents: set[str], readme: str) -> list[str]:
    hits: list[str] = []
    for name in _TYPE_RE.findall(text or ""):
        if name in _GENERIC_TYPES or name in idents:
            continue
        window = _sentence_window(text, text.find(f"`{name}`"))
        if name in readme and _SAMPLE_QUALIFIER_RE.search(window):
            continue
        if name not in idents:
            if name not in readme or _API_PRESENTATION_RE.search(window):
                hits.append(f"ident:{name}")
    return hits


def _orm_offenders(text: str, root: Path) -> list[str]:
    if alembic_uses_model_metadata(root):
        return []
    env_exists = any(
        (root / rel).is_file()
        for rel in (
            Path("app") / "db" / "migrations" / "env.py",
            Path("alembic") / "env.py",
        )
    )
    if not env_exists:
        return []
    hits: list[str] = []
    if re.search(r"Base\.metadata", text):
        hits.append("orm:Base.metadata")
    if re.search(r"--autogenerate|Autogenerate", text):
        hits.append("orm:autogenerate")
    models_dir = root / "app" / "db" / "models"
    if re.search(r"app\.db\.models", text) and not models_dir.exists():
        hits.append("orm:app.db.models")
    return hits


def _route_cite_offenders(text: str, endpoints: list[dict] | None) -> list[str]:
    if not endpoints:
        return []
    by_route = {
        (str(item.get("method") or "").upper(), str(item.get("path") or "")): item
        for item in endpoints
        if isinstance(item, dict)
    }
    hits: list[str] = []
    for match in _CITE_RE.finditer(text or ""):
        cite_path = match.group(1).split(":", 1)[0].replace("\\", "/")
        window = text[max(0, match.start() - 80) : match.start()]
        route = re.search(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/\S+)", window)
        if not route:
            continue
        item = by_route.get((route.group(1), route.group(2).rstrip("。，、")))
        if not item:
            continue
        handler_file = str(
            item.get("file_path") or item.get("handler_file") or item.get("evidence_path") or ""
        ).replace("\\", "/")
        if handler_file and cite_path != handler_file:
            hits.append(f"route-cite:{route.group(1)} {route.group(2)}->{cite_path}")
    return hits


def handbook_source_fact_offenders(
    content_dir: Path | None,
    repo_root: Path | None,
    endpoints: list[dict] | None = None,
) -> dict[str, list[str]]:
    if content_dir is None or not content_dir.exists() or repo_root is None:
        return {}
    services = load_compose_service_names(repo_root)
    tables = load_database_tables(repo_root)
    flags = load_cli_flag_help(repo_root)
    idents = load_source_identifiers(repo_root)
    cmd_names = load_cmd_names(repo_root)
    health_routes = load_health_routes(repo_root)
    readme = read_readme_text(repo_root)
    found: dict[str, list[str]] = {}
    for path in iter_markdown_pages(content_dir):
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits: list[str] = []
        if services:
            invented = _mentioned_compose_services(text) - services
            hits.extend(f"compose:{name}" for name in sorted(invented)[:8])
        migration_page = any(
            token in f"{path.name} {text[:240]}" for token in ("迁移", "表", "migration")
        )
        if tables and migration_page:
            claimed = _mentioned_tables(text)
            hits.extend(f"table:{name}" for name in sorted(claimed - tables)[:8])
            hits.extend(_orm_offenders(text, repo_root)[:4])
        hits.extend(_flag_target_mismatches(text, flags, cmd_names)[:4])
        hits.extend(_ident_offenders(text, idents, readme)[:6])
        hits.extend(_route_cite_offenders(text, endpoints)[:8])
        if "健康检查" in path.name and health_routes:
            if not any(route in text for route in health_routes):
                hits.append("health:missing-source-routes")
        if hits:
            found[path.as_posix()] = hits[:12]
    return found


def source_fact_prompt_block(root: Path) -> str:
    """Positive facts for the page prompt so the model does not invent them."""
    lines: list[str] = []
    services = sorted(load_compose_service_names(root))
    if services:
        lines.append(
            "编排服务名（只能写这些）：" + "、".join(f"`{name}`" for name in services[:12])
        )
    tables = sorted(load_database_tables(root))
    if tables:
        lines.append("数据表（只能写这些）：" + "、".join(f"`{name}`" for name in tables[:20]))
    flags = load_cli_flag_help(root)
    if flags:
        bits = [f"`--{name}`：{help_text}" for name, help_text in list(flags.items())[:8]]
        lines.append("CLI 旗标含义：" + "；".join(bits))
    health = load_health_routes(root)
    if health:
        lines.append("健康检查路由：" + "、".join(f"`{item}`" for item in health[:6]))
    if not alembic_uses_model_metadata(root):
        for rel in (
            Path("app") / "db" / "migrations" / "env.py",
            Path("alembic") / "env.py",
        ):
            if (root / rel).is_file():
                lines.append(
                    "迁移运行时：`env.py` 里 `target_metadata = None`，"
                    "不要写 `Base.metadata`、`app.db.models` 或 `--autogenerate`。"
                )
                break
    return "\n".join(f"- {line}" for line in lines)
