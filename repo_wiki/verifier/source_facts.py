"""Facts checked against parsed repository sources, not handbook prose."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from repo_wiki.generator.compose_evidence import parse_compose_topology
from repo_wiki.verifier.handbook import _CITE_RE, iter_markdown_pages, read_readme_text

_COMPOSE_NAME_RE = re.compile(
    r"^(?:docker-compose|podman-compose|compose)(?:\.[A-Za-z0-9_-]+)*\.ya?ml$",
    re.IGNORECASE,
)
_SKIP_DIRS = frozenset(
    {".git", ".repo-agent-eval", "vendor", "node_modules", "__pycache__", "testdata"}
)
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
        "FastAPI",
        "PostgreSQL",
        "SQLAlchemy",
        "Alembic",
        "HTTPException",
        "Depends",
        "Docker",
        "GitHub",
        "Dockerfile",
        "Makefile",
        "Handle",
    }
)
_SAMPLE_QUALIFIER_RE = re.compile(r"示例|README|文档样例|仅出现在")
_API_PRESENTATION_RE = re.compile(r"接口|类型|依赖|触发|handler|工厂|合同")


def iter_compose_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in _SKIP_DIRS for part in path.parts):
            continue
        if _COMPOSE_NAME_RE.match(path.name):
            found.append(path)
    return found


def load_compose_services_by_file(root: Path) -> dict[str, set[str]]:
    """Service names keyed by the compose filename that declares them."""
    found: dict[str, set[str]] = {}
    for path in iter_compose_files(root):
        parsed, _edges = parse_compose_topology(path.read_text(encoding="utf-8", errors="ignore"))
        found[path.name] = set(parsed) | found.get(path.name, set())
    return found


def load_compose_service_names(root: Path) -> set[str]:
    names: set[str] = set()
    for parsed in load_compose_services_by_file(root).values():
        names.update(parsed)
    return names


def load_compose_healthcheck_services(root: Path) -> set[str]:
    names: set[str] = set()
    for path in iter_compose_files(root):
        current = ""
        in_health = False
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if raw.lstrip().startswith("#"):
                continue
            service = re.match(r"^  ([A-Za-z][A-Za-z0-9_-]*):\s*$", raw)
            if service:
                current = service.group(1)
                in_health = False
                continue
            if current and re.match(r"^    healthcheck:\s*$", raw):
                in_health = True
                names.add(current)
                continue
            if in_health and raw.startswith("  ") and not raw.startswith("      "):
                in_health = False
    return names


_HEALTHCHECK_URL_RE = re.compile(
    r"(https?://[^\s\"']+|:\d+/(?:healthz?|readyz|livez|metrics)[^\s\"']*)"
)


@dataclass(frozen=True)
class ComposeHealthBinding:
    service: str
    url: str
    compose_file: str


def load_compose_health_map(root: Path) -> list[ComposeHealthBinding]:
    """Map each compose service to its health URL from ports + healthcheck test."""
    found: list[ComposeHealthBinding] = []
    seen: set[tuple[str, str]] = set()
    for path in iter_compose_files(root):
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            data = None
        services = data.get("services") if isinstance(data, dict) else None
        if not isinstance(services, dict):
            continue
        for name, spec in services.items():
            if not isinstance(spec, dict):
                continue
            check = spec.get("healthcheck")
            test = check.get("test") if isinstance(check, dict) else check
            items = test if isinstance(test, list) else [test]
            blob = " ".join(str(item) for item in items if item)
            urls = [m.group(1).rstrip('",]') for m in _HEALTHCHECK_URL_RE.finditer(blob)]
            ports = [
                m.group(1)
                for item in (spec.get("ports") or [] if isinstance(spec.get("ports"), list) else [])
                for m in [re.search(r"(\d+):\d+", str(item))]
                if m
            ]
            if check and not urls:
                urls = [f":{port}" for port in ports]
            for url in urls:
                key = (str(name), url)
                if key in seen:
                    continue
                seen.add(key)
                found.append(ComposeHealthBinding(str(name), url, path.name))
    return found


def load_compose_healthcheck_urls(root: Path) -> list[str]:
    """Healthcheck test URLs copied from compose files, never invented."""
    return list(dict.fromkeys(item.url for item in load_compose_health_map(root)))


def load_database_tables(root: Path) -> set[str]:
    tables: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file() or any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in {".py", ".sql"}:
            continue
        if (
            path.suffix.lower() == ".py"
            and "alembic" not in path.as_posix()
            and "migration" not in path.as_posix()
        ):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        tables.update(match.group(1) for match in _TABLE_RE.finditer(text))
    return {name for name in tables if name.lower() not in {"if", "table", "exists"}}


def load_cli_flag_help(root: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    for _cmd, flags in load_cli_flags_by_cmd(root).items():
        for name, help_text in flags.items():
            found.setdefault(name, help_text)
    return found


def load_cli_flags_by_cmd(root: Path) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    cmd_root = root / "cmd"
    if not cmd_root.is_dir():
        return found
    for path in cmd_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".go", ".py"}:
            continue
        if path.name.endswith("_test.go") or path.name.startswith("test_"):
            continue
        leaf = path.relative_to(cmd_root).parts[0] if path.relative_to(cmd_root).parts else ""
        if not leaf:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        bucket = found.setdefault(leaf, {})
        for match in _FLAG_DEF_RE.finditer(text):
            bucket[match.group(1).lstrip("-")] = match.group(2)
        for match in _ARGPARSE_RE.finditer(text):
            bucket[match.group(1).lstrip("-")] = match.group(2)
    return found


def load_source_identifiers(root: Path) -> set[str]:
    names: set[str] = set()
    skip = _SKIP_DIRS
    simple = re.compile(r"\b(?:type|class|def|func)\s+([A-Za-z_][A-Za-z0-9_]+)")
    method = re.compile(r"\bfunc\s+\([^)]+\)\s+([A-Za-z_][A-Za-z0-9_]+)")
    token = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]{2,})\b")
    for path in root.rglob("*"):
        if not path.is_file() or any(part in skip for part in path.parts):
            continue
        names.add(path.name)
        names.add(path.stem)
        if path.suffix.lower() not in {".go", ".py", ".sql"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        names.update(simple.findall(text))
        names.update(method.findall(text))
        names.update(token.findall(text))
    return names


def load_cmd_names(root: Path) -> set[str]:
    cmd = root / "cmd"
    if not cmd.is_dir():
        return set()
    return {child.name for child in cmd.iterdir() if child.is_dir()}


def load_health_routes(root: Path) -> list[str]:
    blob = ""
    skip = {".git", ".repo-agent-eval", "vendor", "node_modules", "__pycache__"}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".go", ".py"}:
            continue
        if any(part in skip for part in path.parts) or path.name.endswith("_test.go"):
            continue
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "/health" in text or "healthz" in text or "readyz" in text or "livez" in text:
            blob += text + "\n"
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


_COMPOSE_FILE_RE = re.compile(
    r"`?((?:docker-|podman-)?compose(?:\.[A-Za-z0-9_-]+)*\.ya?ml)`?",
    re.IGNORECASE,
)
_SERVICE_CONTEXT_RE = re.compile(
    r"(?:服务|容器|编排|compose\s+service|container)[^`\n]{0,40}`([A-Za-z][A-Za-z0-9_-]{1,32})`"
    r"|`([A-Za-z][A-Za-z0-9_-]{1,32})`\s*(?:服务|容器|service)\b"
    r"|(?:services?[:：]\s*|编排服务[^。\n]{0,40})`([A-Za-z][A-Za-z0-9_-]{1,32})`",
    re.IGNORECASE,
)
_NOT_SERVICE_TOKENS = frozenset(
    {
        "depends",
        "handle",
        "true",
        "false",
        "none",
        "self",
        "return",
        "import",
        "class",
        "async",
        "await",
        "const",
        "func",
    }
)


def _mentioned_compose_filenames(text: str) -> list[str]:
    found: list[str] = []
    for match in _COMPOSE_FILE_RE.finditer(text or ""):
        name = match.group(1)
        if _COMPOSE_NAME_RE.match(name):
            found.append(name)
    return found


def _mentioned_compose_services(text: str) -> set[str]:
    """Names used as compose/container services, not every lowercase token."""
    names: set[str] = set()
    for sentence in re.split(r"[。\n]", text or ""):
        if not re.search(r"compose|docker|podman|编排服务|容器服务|服务定义", sentence, flags=re.I):
            continue
        for match in _SERVICE_CONTEXT_RE.finditer(sentence):
            token = next((group for group in match.groups() if group), "")
            lowered = token.lower()
            if _looks_like_compose_service(lowered):
                names.add(lowered)
        for match in re.finditer(
            r"(?:服务|容器)[^`\n]{0,80}((?:`[A-Za-z][A-Za-z0-9_-]{1,32}`[、,，与和\s]*)+)",
            sentence,
            flags=re.I,
        ):
            for token in re.findall(r"`([A-Za-z][A-Za-z0-9_-]{1,32})`", match.group(1)):
                lowered = token.lower()
                if not _looks_like_compose_service(lowered):
                    continue
                names.add(lowered)
    return names


def _looks_like_compose_service(token: str) -> bool:
    lowered = (token or "").lower()
    if not lowered or lowered in _GENERIC_COMPOSE or lowered in _NOT_SERVICE_TOKENS:
        return False
    if "_" in lowered:
        return False
    if lowered.endswith(("-data", "-net", "-volume", "-root", "-logs")):
        return False
    return True


_TABLE_CLAIM_RE = re.compile(
    r"(?:表名[:：]\s*)((?:`[a-z][a-z0-9_]+`[、,，与和\s]*)+)"
    r"|`([a-z][a-z0-9_]+)`\s*(?:表|table)\b"
    r"|create_table\(\s*[\"']([a-z][a-z0-9_]+)"
    r"|CREATE TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?([a-z][a-z0-9_]+)",
    re.IGNORECASE,
)


def _healthcheck_url_mentioned(text: str, url: str) -> bool:
    blob = text or ""
    if url in blob:
        return True
    port = re.search(r":(\d+)", url)
    if port and f":{port.group(1)}" in blob:
        return True
    path = re.search(r"/(?:healthz?|readyz|livez|metrics)[A-Za-z0-9_/?&=-]*", url)
    return bool(path and path.group(0) in blob)


def _health_binding_mentioned(text: str, binding: ComposeHealthBinding) -> bool:
    for sentence in re.split(r"[。\n]", text or ""):
        if binding.service not in sentence:
            continue
        if _healthcheck_url_mentioned(sentence, binding.url):
            return True
        port = re.search(r":(\d+)", binding.url)
        if port and (f":{port.group(1)}" in sentence or port.group(1) in sentence):
            return True
    return False


def _health_map_conflicts(text: str, bindings: list[ComposeHealthBinding]) -> bool:
    if len(bindings) < 2:
        return False
    for sentence in re.split(r"[。\n]", text or ""):
        svcs = [item for item in bindings if item.service in sentence]
        if not svcs:
            continue
        for item in svcs:
            others = [other for other in bindings if other.service != item.service]
            if any(_healthcheck_url_mentioned(sentence, other.url) for other in others):
                if not _health_binding_mentioned(sentence, item):
                    return True
    return False


def _mentioned_tables(text: str) -> set[str]:
    names: set[str] = set()
    for sentence in re.split(r"[。\n]", text or ""):
        if re.search(r"不是表|not a table|列 `|column `", sentence, flags=re.I):
            continue
        for match in _TABLE_CLAIM_RE.finditer(sentence):
            window = match.group(0)
            tokens = [group for group in match.groups() if group]
            tokens.extend(re.findall(r"`([a-z][a-z0-9_]+)`", window))
            for token in tokens:
                if not token or token in _GENERIC_TABLES:
                    continue
                if re.search(
                    rf"(?:列|字段|column|columns)\s*`{re.escape(token)}`|`{re.escape(token)}`\s*(?:列|字段|column)",
                    sentence,
                    flags=re.I,
                ):
                    continue
                names.add(token)
    return names


def _sentence_window(text: str, index: int) -> str:
    start = max(text.rfind("。", 0, index), text.rfind("\n", 0, index))
    end_candidates = [pos for pos in (text.find("。", index), text.find("\n", index)) if pos >= 0]
    end = min(end_candidates) if end_candidates else len(text)
    return text[start + 1 : end]


def _flag_target_mismatches(
    text: str, flags_by_cmd: dict[str, dict[str, str]], cmd_names: set[str]
) -> list[str]:
    """Fail when a backticked binary is paired with a flag whose help names another."""
    flags: dict[str, str] = {}
    for bucket in flags_by_cmd.values():
        flags.update(bucket)
    hits: list[str] = []
    leaves = {name.split("/")[-1] for name in cmd_names}
    for match in _FLAG_MENTION_RE.finditer(text or ""):
        flag = match.group(1)
        help_text = flags.get(flag, "")
        if not help_text:
            continue
        sentence = _sentence_window(text, match.start())
        mentioned = [
            leaf
            for leaf in leaves
            if re.search(rf"`{re.escape(leaf)}`|cmd/{re.escape(leaf)}\b", sentence)
        ]
        if not mentioned:
            continue
        help_l = help_text.lower().replace("_", "-")
        if any(leaf.lower().replace("_", "-") in help_l for leaf in mentioned):
            continue
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
        path.name == "env.py"
        and any(part in {"alembic", "migrations", "migration"} for part in path.parts)
        for path in root.rglob("env.py")
        if not any(part in _SKIP_DIRS for part in path.parts)
    )
    if not env_exists:
        return []
    hits: list[str] = []
    if re.search(r"Base\.metadata", text):
        hits.append("orm:Base.metadata")
    if re.search(r"--autogenerate|Autogenerate", text):
        hits.append("orm:autogenerate")
    models_dirs = [
        path
        for path in root.rglob("models")
        if path.is_dir() and not any(part in _SKIP_DIRS for part in path.parts)
    ]
    if re.search(r"[A-Za-z0-9_.]+(?:\.|/)models\b", text) and not models_dirs:
        hits.append("orm:missing-models")
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
        route = re.search(r"\b(GET|POST|PUT|PATCH|DELETE|ANY)?\s*(/\S+)", window)
        if not route:
            continue
        method = (route.group(1) or "").upper()
        path = route.group(2).rstrip("。，、`")
        item = by_route.get((method, path)) if method else None
        if item is None and path:
            item = next(
                (
                    value
                    for (mth, pth), value in by_route.items()
                    if pth.rstrip("/") == path.rstrip("/")
                ),
                None,
            )
        if re.search(r"^/(?:healthz?|readyz|livez)", path) and re.match(
            r"readme", Path(cite_path).name, flags=re.I
        ):
            hits.append(f"route-cite:{method or 'GET'} {path}->{cite_path}")
            continue
        if not item:
            continue
        handler_file = str(
            item.get("file_path") or item.get("handler_file") or item.get("evidence_path") or ""
        ).replace("\\", "/")
        if handler_file and cite_path != handler_file:
            hits.append(f"route-cite:{method or item.get('method')} {path}->{cite_path}")
    return hits


def handbook_source_fact_offenders(
    content_dir: Path | None,
    repo_root: Path | None,
    endpoints: list[dict] | None = None,
) -> dict[str, list[str]]:
    if content_dir is None or not content_dir.exists() or repo_root is None:
        return {}
    services_by_file = load_compose_services_by_file(repo_root)
    services = set().union(*services_by_file.values()) if services_by_file else set()
    tables = load_database_tables(repo_root)
    flags_by_cmd = load_cli_flags_by_cmd(repo_root)
    idents = load_source_identifiers(repo_root)
    cmd_names = load_cmd_names(repo_root)
    health_routes = load_health_routes(repo_root)
    readme = read_readme_text(repo_root)
    found: dict[str, list[str]] = {}
    for path in iter_markdown_pages(content_dir):
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits: list[str] = []
        invented = _mentioned_compose_services(text)
        if invented and services_by_file:
            mentioned_files = _mentioned_compose_filenames(text)
            allowed: set[str] = set()
            for name in mentioned_files:
                for rel, names in services_by_file.items():
                    if rel.lower() == name.lower():
                        allowed.update(names)
            if not allowed:
                allowed = set(services)
            hits.extend(f"compose:{name}" for name in sorted(invented - allowed)[:8])
        migration_page = any(
            token in f"{path.name} {text[:240]}" for token in ("迁移", "表", "migration")
        )
        if tables and migration_page:
            claimed = _mentioned_tables(text)
            hits.extend(f"table:{name}" for name in sorted(claimed - tables)[:8])
            hits.extend(_orm_offenders(text, repo_root)[:4])
        hits.extend(_flag_target_mismatches(text, flags_by_cmd, cmd_names)[:4])
        hits.extend(_ident_offenders(text, idents, readme)[:6])
        hits.extend(_route_cite_offenders(text, endpoints)[:8])
        if "健康检查" in path.name:
            if health_routes and not any(route in text for route in health_routes):
                hits.append("health:missing-source-routes")
            bindings = load_compose_health_map(repo_root)
            urls = [item.url for item in bindings]
            if any(not _healthcheck_url_mentioned(text, url) for url in urls):
                hits.append("health:missing-compose-urls")
            if _health_map_conflicts(text, bindings):
                hits.append("health:service-url-mismatch")
        if hits:
            found[path.as_posix()] = hits[:12]
    return found


def source_fact_prompt_block(root: Path, *, page_id: str = "", title: str = "") -> str:
    """Page-owned facts only. Parsed inventories stay in the verifier."""
    blob = f"{page_id} {title}"
    lines: list[str] = []
    if any(token in blob for token in ("健康", "health")):
        health = load_health_routes(root)
        if health:
            lines.append("本页健康检查路由：" + "、".join(f"`{item}`" for item in health[:6]))
        mapped = load_compose_health_map(root)
        if mapped:
            lines.append(
                "本页编排 healthcheck 映射："
                + "、".join(f"`{item.service}`→`{item.url}`" for item in mapped[:8])
            )
        else:
            services = sorted(load_compose_healthcheck_services(root))
            if services:
                lines.append(
                    "本页编排 healthcheck 服务：" + "、".join(f"`{name}`" for name in services[:8])
                )
    if any(token in blob for token in ("数据模型", "data-model", "data_model", "data model")):
        tables = sorted(load_database_tables(root))
        if tables:
            lines.append("本页数据表：" + "、".join(f"`{name}`" for name in tables[:20]))
    return "\n".join(f"- {line}" for line in lines)
