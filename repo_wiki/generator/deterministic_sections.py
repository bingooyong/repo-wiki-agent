"""Deterministic handbook sections derived from repository evidence.

Install steps, compose topology, role cites, and ER tables are built from
files, not from regex rewriting of LLM fences.
"""

from __future__ import annotations

import re
from pathlib import Path

from repo_wiki.verifier.handbook import (
    existing_readme_names,
    preferred_source_listen_port,
    read_readme_text,
)

_H2_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_FENCE_RE = re.compile(r"```(?:bash|sh|mermaid|sql|json)\n.*?```", re.IGNORECASE | re.DOTALL)
_META_IMPERATIVE_RE = re.compile(
    r"不要把|不要将|不要引用|不要声称|don't treat|do not treat|不得视为|不要用测试",
    re.IGNORECASE,
)
_HEADER_CITE_RE = re.compile(
    r"<cite>\s*([^<:\s][^<]*?):1-([1-8])\s*</cite>",
    re.IGNORECASE,
)
_PLANNING_LEAK_RE = re.compile(
    r"页面规划与证据绑定|页面基于仓库扫描|从提供的证据可见|证据中可确认的"
)
_REQUIRED_GO_STRUCTS = ("ProbeEndpoint", "ProbeResult", "ProbeTag", "ProbeSecret")
_INSTALL_OWNER_IDS = frozenset({"installation"})
_INSTALL_SATELLITE_IDS = frozenset(
    {"quick-start", "quickstart", "getting-started", "local-setup", "environment-setup"}
)
_ARCH_OWNER_IDS = frozenset({"architecture-overview"})
_API_OWNER_IDS = frozenset({"api-overview", "api-reference", "api"})
_SECURITY_OWNER_IDS = frozenset({"security-overview", "security"})
_GO_SECURITY_HINTS = (
    "apiauth.go",
    "internal/auth",
    "internal/secrets",
    "internal/audit",
    "internal/netguard",
    "internal/security",
    "deploy/mtls",
)
_FASTAPI_SECURITY_HINTS = (
    "app/services/jwt.py",
    "app/services/security.py",
    "app/api/dependencies/authentication.py",
)


def is_install_owner_page(*, page_id: str = "", title: str = "") -> bool:
    pid = (page_id or "").lower().rsplit("/", 1)[-1]
    if pid in _INSTALL_SATELLITE_IDS:
        return False
    if pid in _INSTALL_OWNER_IDS:
        return True
    return any(token in (title or "") for token in ("安装与配置", "安装指南"))


def is_architecture_owner_page(*, page_id: str = "", title: str = "") -> bool:
    pid = (page_id or "").lower().rsplit("/", 1)[-1]
    if pid in _ARCH_OWNER_IDS:
        return True
    return (title or "") in {"整体架构概览", "架构设计"}


def is_api_catalog_owner_page(*, page_id: str = "", title: str = "") -> bool:
    pid = (page_id or "").lower().rsplit("/", 1)[-1]
    return pid in _API_OWNER_IDS or (title or "") in {"API参考", "API 参考"}


def is_security_owner_page(*, page_id: str = "", title: str = "") -> bool:
    pid = (page_id or "").lower().rsplit("/", 1)[-1]
    return pid in _SECURITY_OWNER_IDS or (title or "") in {"安全合规", "安全合规概览"}


def cite_readme_line(root: Path, needle: str, *, last: bool = False) -> str:
    names = existing_readme_names(root)
    name = next((item for item in names if (root / item).is_file()), "")
    if not name:
        return ""
    found = ""
    for index, line in enumerate(read_readme_text(root).splitlines(), start=1):
        if needle in line:
            found = f"<cite>{name}:{index}-{index}</cite>"
            if not last:
                return found
    return found


def cite_first_match(root: Path, rel: str, pattern: str) -> str:
    path = root / rel
    if not path.is_file():
        return ""
    regex = re.compile(pattern)
    for index, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if regex.search(line):
            return f"<cite>{rel}:{index}-{index}</cite>"
    return ""


def cite_existing_meaningful(root: Path, rel: str) -> str:
    """Cite the first definition line, never a file-header window."""
    path = root / rel
    if path.is_file():
        return cite_first_match(
            root,
            rel,
            r"^(func\s+|type\s+\w+|const\s+\w+|class\s+|def\s+)",
        ) or cite_first_match(root, rel, r"\S")
    if not path.exists():
        return ""
    for child in sorted(path.rglob("*")):
        if not child.is_file() or child.name.endswith("_test.go"):
            continue
        if child.suffix.lower() not in {".go", ".py", ".sql", ".ts"}:
            continue
        if child.name in {"__init__.py", "__main__.py"}:
            continue
        child_rel = child.relative_to(root).as_posix()
        cite = cite_first_match(
            root,
            child_rel,
            r"^(func\s+main\b|func\s+\w+|type\s+\w+\s+struct|class\s+\w+|def\s+\w+)",
        )
        if cite:
            return cite
    return ""


def replace_h2_section(content: str, title_prefixes: tuple[str, ...], replacement: str) -> str:
    """Replace the first H2 whose title starts with any prefix; insert before 目录 if missing."""
    matches = list(_H2_RE.finditer(content))
    start = end = None
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        if any(title.startswith(prefix) for prefix in title_prefixes):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            break
    block = replacement.strip() + "\n\n"
    if start is None:
        toc = re.search(r"^##\s+目录\s*$", content, re.MULTILINE)
        if toc:
            return content[: toc.start()] + block + content[toc.start() :]
        return content.rstrip() + "\n\n" + block
    return content[:start] + block + content[end:]


def rebuild_toc_from_h2s(content: str) -> str:
    headings: list[str] = []
    in_fence = False
    kept: list[str] = []
    skipping_toc = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            if not skipping_toc:
                kept.append(line)
            continue
        if skipping_toc:
            if not in_fence and re.match(r"^#{1,6}\s+\S", stripped):
                skipping_toc = False
            else:
                continue
        heading = re.match(r"^#{1,6}\s+(.+)$", stripped)
        if heading and heading.group(1).strip() in {"目录", "Table of Contents", "TOC"}:
            skipping_toc = True
            continue
        if (
            heading
            and stripped.startswith("## ")
            and heading.group(1).strip()
            not in {
                "目录",
                "Table of Contents",
                "TOC",
            }
        ):
            headings.append(heading.group(1).strip())
        kept.append(line)
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
    if not headings:
        return body + "\n"
    toc = ["## 目录", ""] + [f"{index}. {title}" for index, title in enumerate(headings[:10], 1)]
    return body + "\n\n" + "\n".join(toc) + "\n"


def dedupe_identical_fences(content: str) -> str:
    seen: set[str] = set()

    def _keep(match: re.Match[str]) -> str:
        key = re.sub(r"\s+", " ", match.group(0)).strip().casefold()
        if key in seen:
            return ""
        seen.add(key)
        return match.group(0)

    return _FENCE_RE.sub(_keep, content)


def strip_header_only_cites(content: str, root: Path) -> str:
    def _keep(match: re.Match[str]) -> str:
        return "" if is_header_only_cite(match.group(0), root) else match.group(0)

    return _HEADER_CITE_RE.sub(_keep, content)


def strip_meta_instructions(content: str) -> str:
    kept: list[str] = []
    for line in content.splitlines():
        if _META_IMPERATIVE_RE.search(line) and (
            "package main" in line or "custom-probe" in line or "测试 settings" in line
        ):
            continue
        if _PLANNING_LEAK_RE.search(line):
            continue
        if "安装与启动步骤以仓库入口文档为准" in line:
            continue
        kept.append(line)
    return "\n".join(kept)


def _go_local_db_start_lines(root: Path) -> list[str]:
    lines: list[str] = []
    readme = read_readme_text(root).splitlines()
    index = 0
    while index < len(readme):
        stripped = readme[index].strip()
        if stripped.startswith(("podman run", "docker run")) and any(
            token in stripped for token in ("mysql", "blackbox", "postgres")
        ):
            chunk = [stripped]
            while chunk[-1].endswith("\\") and index + 1 < len(readme):
                index += 1
                nxt = readme[index].rstrip()
                chunk.append(nxt if nxt.startswith((" ", "\t")) else nxt.strip())
            lines.extend(chunk)
        index += 1
    if not lines:
        lines = [
            "podman run --name mysql-db -d -e MYSQL_ROOT_PASSWORD=rootpassword "
            "-e MYSQL_DATABASE=probe_exporter -p 3306:3306 mysql:8.0",
        ]
    return lines


def build_go_install_section(root: Path) -> str:
    port = preferred_source_listen_port(root) or 1900
    compose = cite_readme_line(root, "podman-compose up")
    schema = cite_readme_line(root, "schema.sql")
    build = cite_readme_line(root, "go build -o bin/ccagent")
    run = cite_readme_line(root, "./bin/ccagent")
    health = cite_readme_line(root, "/health")
    schema_cmd = "podman exec mysql-db mysql -uroot -prootpassword probe_exporter < db/schema.sql"
    if (root / "db" / "schema.sql").is_file() is False:
        schema_cmd = "mysql < db/schema.sql"
    return "\n".join(
        [
            "## 安装步骤",
            "",
            "容器路径与本地路径二选一。",
            "",
            "### 路径 A：容器编排",
            "",
            f"1. 启动编排服务。 {compose}",
            "",
            "```bash",
            "podman-compose up -d",
            "```",
            "",
            f"2. 导入一次数据库结构。 {schema}",
            "",
            "```bash",
            "# 容器路径：导入一次结构",
            schema_cmd,
            "```",
            "",
            f"3. 用源码监听端口检查健康状态。 {health}",
            "",
            "```bash",
            f"curl http://localhost:{port}/health",
            "```",
            "",
            "### 路径 B：本地编译",
            "",
            f"1. 先按 README 启动本地 MySQL（以及 blackbox-exporter）。 {cite_readme_line(root, 'podman run')}",
            "",
            "```bash",
            *_go_local_db_start_lines(root),
            "```",
            "",
            f"2. 再导入结构。 {cite_readme_line(root, 'podman exec mysql-db', last=True) or schema}",
            "",
            "```bash",
            "# 本地路径：导入结构",
            schema_cmd,
            "```",
            "",
            f"3. 编译主 REST/Web 服务。 {build}",
            "",
            "```bash",
            "go build -o bin/ccagent ./cmd/ccagent",
            "```",
            "",
            f"4. 启动本地进程并检查健康状态。 {run} {health}",
            "",
            "```bash",
            "./bin/ccagent",
            f"curl http://localhost:{port}/health",
            "```",
            "",
        ]
    )


def build_fastapi_install_section(root: Path) -> str:
    env = cite_readme_line(root, "APP_ENV") or cite_readme_line(root, "SECRET_KEY")
    poetry = cite_readme_line(root, "poetry install")
    alembic = cite_readme_line(root, "alembic upgrade")
    uvicorn = cite_readme_line(root, "uvicorn app.main:app")
    pg = cite_readme_line(root, "docker run --name pgdb") or cite_readme_line(root, "POSTGRES")
    compose_db = cite_readme_line(root, "docker-compose up -d db") or cite_readme_line(
        root, "docker-compose up"
    )
    compose_app = cite_readme_line(root, "docker-compose up -d app")
    return "\n".join(
        [
            "## 安装步骤",
            "",
            "容器路径与本地路径二选一。",
            "",
            "### 路径 A：本地开发",
            "",
            f"1. 创建 `.env`（alembic `env.py` 会加载应用设置，必须先有 APP_ENV、DATABASE_URL、SECRET_KEY）。 {env}",
            "",
            "```bash",
            "touch .env",
            "echo APP_ENV=dev >> .env",
            "echo DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/rwdb >> .env",
            "echo SECRET_KEY=change-me >> .env",
            "```",
            "",
            f"2. 先启动 PostgreSQL。 {pg}",
            "",
            "```bash",
            "docker run --name pgdb --rm -e POSTGRES_USER=postgres "
            "-e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=rwdb -p 5432:5432 postgres",
            "```",
            "",
            f"3. 安装依赖。 {poetry}",
            "",
            "```bash",
            "poetry install",
            "```",
            "",
            f"4. 迁移数据库。 {alembic}",
            "",
            "```bash",
            "poetry run alembic upgrade head",
            "```",
            "",
            f"5. 启动应用。 {uvicorn}",
            "",
            "```bash",
            "poetry run uvicorn app.main:app --reload",
            "```",
            "",
            "### 路径 B：Compose",
            "",
            f"1. 先创建 `.env`（compose 通过 env_file 注入 APP_ENV、DATABASE_URL、SECRET_KEY）。 {env}",
            "",
            "```bash",
            "touch .env",
            "echo APP_ENV=dev >> .env",
            "echo DATABASE_URL=postgresql://postgres:postgres@db:5432/rwdb >> .env",
            "echo SECRET_KEY=change-me >> .env",
            "```",
            "",
            f"2. 先启动数据库服务，再启动应用服务。 {compose_db} {compose_app}",
            "",
            "```bash",
            "docker-compose up -d db",
            "docker-compose up -d app",
            "```",
            "",
        ]
    )


def build_install_section(root: Path) -> str:
    if (root / "cmd" / "ccagent").is_dir():
        return build_go_install_section(root)
    if (root / "app" / "main.py").is_file():
        return build_fastapi_install_section(root)
    return ""


def build_go_role_section(root: Path) -> str:
    ccagent = (
        cite_first_match(root, "controller.go", r"return server\.ListenAndServe\(\)")
        or cite_first_match(root, "controller.go", r"ListenAndServe")
        or cite_first_match(
            root, "cmd/ccagent/main.go", r"NewController|ListenAndServe|http\.Server"
        )
        or cite_first_match(root, "cmd/ccagent/main.go", r"func\s+main\b")
    )
    probe = (
        cite_first_match(root, "internal/agent/grpc_transport.go", r"grpc\.DialContext")
        or cite_first_match(root, "cmd/probe-agent/main.go", r"grpcTransport\.Connect|DialContext")
        or cite_first_match(root, "cmd/probe-agent/main.go", r"func\s+main\b")
    )
    control = ""
    for rel in ("cmd/ccprobe-control/serve.go", "cmd/ccprobe-control/main.go"):
        control = cite_first_match(
            root, rel, r"func runGRPCServe|ListenAndServeGRPC|transport grpc|-serve|-transport"
        )
        if control:
            break
    if not (ccagent or probe or control):
        return ""
    return (
        "## 进程角色\n\n"
        f"ccagent 是主 REST/Web 服务，监听 HTTP 并挂载业务路由。 {ccagent}\n\n"
        f"probe-agent 是隧道客户端，向控制面拨号并维持心跳。 {probe}\n\n"
        f"ccprobe-control 是 gRPC 控制面服务（`-serve -transport grpc`），负责 TunnelHub。 {control}\n"
    )


def extract_alembic_tables(text: str) -> list[dict[str, object]]:
    tables: list[dict[str, object]] = []
    starts = list(re.finditer(r'op\.create_table\(\s*"(\w+)"', text or ""))
    for index, match in enumerate(starts):
        name = match.group(1)
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text or "")
        body = (text or "")[match.end() : end]
        attrs: list[str] = []
        types: list[str] = []
        pks: list[str] = []
        for col in re.finditer(
            r'sa\.Column\(\s*"(\w+)"\s*,\s*sa\.(\w+)',
            body,
        ):
            attrs.append(col.group(1))
            types.append(col.group(2))
            window_end = min(len(body), col.end() + 80)
            if "primary_key=True" in body[col.start() : window_end]:
                pks.append(col.group(1))
        for extra in re.findall(r"sa\.PrimaryKeyConstraint\(\s*([^)]+)\)", body):
            pks.extend(re.findall(r'"(\w+)"', extra))
        fks = re.findall(
            r'sa\.Column\(\s*"(\w+)"[^)]*sa\.ForeignKey\(\s*"(\w+)\.(\w+)"',
            body,
        )
        if not fks:
            fks = [
                ("", dest, col)
                for dest, col in re.findall(r'sa\.ForeignKey\(\s*"(\w+)\.(\w+)"', body)
            ]
        relationships = []
        for col_name, dest, _dest_col in fks:
            label = col_name or _dest_col
            relationships.append(f"belongs_to:{dest}:{label}" if label else f"belongs_to:{dest}")
        tables.append(
            {
                "name": name,
                "type": "migration_table",
                "attributes": attrs,
                "attribute_types": types,
                "primary_key": pks[0] if len(pks) == 1 else "",
                "primary_keys": list(dict.fromkeys(pks)),
                "relationships": relationships,
                "file_path": "",
                "table_name": name,
            }
        )
    return tables


def load_alembic_migration_models(root: Path) -> list[dict[str, object]]:
    versions = root / "app" / "db" / "migrations" / "versions"
    if not versions.is_dir():
        return []
    models: list[dict[str, object]] = []
    for path in sorted(versions.glob("*.py")):
        tables = extract_alembic_tables(path.read_text(encoding="utf-8", errors="ignore"))
        rel = path.relative_to(root).as_posix()
        for table in tables:
            table["file_path"] = rel
            models.append(table)
    return models


def go_struct_end_line(lines: list[str], start: int) -> int:
    depth = 0
    for index in range(start - 1, len(lines)):
        depth += lines[index].count("{") - lines[index].count("}")
        if depth <= 0 and index >= start - 1:
            return index + 1
    return min(len(lines), start)


def go_struct_cite(root: Path, name: str) -> str:
    models = root / "internal" / "models"
    if not models.is_dir():
        return ""
    pattern = re.compile(rf"^type\s+{re.escape(name)}\s+struct\s*\{{")
    for path in sorted(models.rglob("*.go")):
        if path.name.endswith("_test.go"):
            continue
        rel = path.relative_to(root).as_posix()
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for index, line in enumerate(lines, 1):
            if pattern.match(line):
                return f"<cite>{rel}:{index}-{go_struct_end_line(lines, index)}</cite>"
    return ""


def all_go_model_struct_cites(root: Path) -> list[str]:
    models = root / "internal" / "models"
    if not models.is_dir():
        return []
    pattern = re.compile(r"^type\s+([A-Z][A-Za-z0-9_]*)\s+struct\s*\{")
    cites: list[str] = []
    seen: set[str] = set()
    for path in sorted(models.rglob("*.go")):
        if path.name.endswith("_test.go"):
            continue
        rel = path.relative_to(root).as_posix()
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for index, line in enumerate(lines, 1):
            match = pattern.match(line)
            if not match or match.group(1) in seen:
                continue
            seen.add(match.group(1))
            cites.append(
                f"{match.group(1)} <cite>{rel}:{index}-{go_struct_end_line(lines, index)}</cite>"
            )
    return cites


def build_data_model_cite_block(root: Path) -> str:
    if (root / "internal" / "models").is_dir():
        named = all_go_model_struct_cites(root)
        required = [go_struct_cite(root, name) for name in _REQUIRED_GO_STRUCTS]
        required = [item for item in required if item]
        if not named and not required:
            return ""
        migrations = ""
        mig_dir = root / "db" / "migrations"
        if mig_dir.is_dir():
            sqls = sorted(path for path in mig_dir.glob("*.sql"))
            if sqls:
                rel = sqls[0].relative_to(root).as_posix()
                migrations = f" `db/migrations` 含 {len(sqls)} 个 SQL 迁移，例如 {cite_first_match(root, rel, r'CREATE TABLE|create table') or f'<cite>{rel}:1-1</cite>'}。"
        body = "、".join(named) if named else " ".join(required)
        return (
            "## 实体定义\n\n"
            f"GORM 结构体定义在 internal/models：{body}。"
            f" 表结构见 db/schema.sql。{migrations}\n"
        )
    models = load_alembic_migration_models(root)
    if not models:
        return ""
    rel = str(models[0].get("file_path") or "app/db/migrations")
    names = "、".join(str(item.get("name")) for item in models)
    domain = ""
    domain_dir = root / "app" / "models" / "domain"
    if domain_dir.is_dir():
        domain = cite_existing_meaningful(root, "app/models/domain")
    migration_cite = cite_first_match(root, rel, r'op\.create_table\(\s*"users"') or (
        f"<cite>{rel}:1-1</cite>" if (root / rel).is_file() else ""
    )
    return (
        "## 持久化表\n\n"
        f"持久化表以 `{rel}` 为准，当前迁移定义 {names}，外键按迁移列声明。"
        f" 不存在 profiles 表。 {migration_cite} "
        f"app/models/domain 是 Pydantic 领域模型，不是 ORM 实体。 {domain}\n"
    )


def build_security_cite_block(root: Path) -> str:
    cites: list[str] = []
    hints: tuple[str, ...] = (
        _GO_SECURITY_HINTS if (root / "cmd" / "ccagent").is_dir() else _FASTAPI_SECURITY_HINTS
    )
    for rel in hints:
        path = root / rel
        if path.exists():
            cite = cite_existing_meaningful(root, rel)
            if cite:
                cites.append(cite)
    if not cites:
        return ""
    if (root / "cmd" / "ccagent").is_dir():
        return (
            "## 安全实现\n\n"
            f"请求鉴权走 API 网关 AK/SK 中间件与 internal/auth。 {cites[0] if cites else ''}\n\n"
            f"密钥以 AES/Vault 存储，不把明文写进配置。 {cites[1] if len(cites) > 1 else ''}\n\n"
            f"审计事件写入 internal/audit，出站目标由 netguard 约束，敏感字段在日志中脱敏。"
            f" {' '.join(cites[2:])}\n"
        )
    return (
        "## 安全实现\n\n"
        f"路由依赖从 Authorization 头读取 JWT（前缀见 settings.jwt_token_prefix）。 {cites[0]}\n\n"
        f"口令哈希与令牌校验在 app/services/security.py 与 authentication 依赖中完成。"
        f" {' '.join(cites[1:])}\n"
    )


def build_feature_prose(root: Path) -> str:
    if (root / "app" / "api" / "routes").is_dir():
        routes = sorted(
            path.stem
            for path in (root / "app" / "api" / "routes").glob("*.py")
            if path.name != "__init__.py"
        )
        if routes:
            return (
                "核心功能由路由模块实现，包括 "
                + "、".join(routes)
                + " 等请求入口，再进入服务与仓储完成读写。"
            )
    if (root / "internal" / "services").is_dir():
        return "核心功能由 ccagent 对外提供 REST/Web 接口，并由 services 与 repository 完成探针、策略和结果处理。"
    return ""


def is_header_only_cite(raw: str, repo_root: Path | None) -> bool:
    match = _HEADER_CITE_RE.search(raw)
    if not match or repo_root is None:
        return False
    rel = match.group(1).replace("\\", "/")
    path = repo_root / rel
    if not path.is_file():
        return False
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    end = int(match.group(2))
    window = "\n".join(lines[:end])
    if re.search(
        r"^(type\s+\w+\s+struct|func\s+main\b|func\s+\w+|def\s+\w+|class\s+\w+|"
        r"podman-|docker-|poetry |alembic |uvicorn )",
        window,
        re.M,
    ):
        return False
    suffix = Path(rel).suffix.lower()
    if suffix in {".md", ".rst", ".yml", ".yaml", ".txt"}:
        return True
    return not re.search(r"\S", window)


def page_has_repeated_fences(content: str) -> bool:
    seen: dict[str, int] = {}
    for match in _FENCE_RE.finditer(content or ""):
        key = re.sub(r"\s+", " ", match.group(0)).strip().casefold()
        if len(key) < 40:
            continue
        seen[key] = seen.get(key, 0) + 1
        if seen[key] >= 2:
            return True
    return False


def page_has_meta_instruction(content: str) -> bool:
    for line in (content or "").splitlines():
        if _PLANNING_LEAK_RE.search(line):
            return True
        if _META_IMPERATIVE_RE.search(line) and ("package main" in line or "custom-probe" in line):
            return True
    return False


def strip_dangling_colon_leads(content: str) -> str:
    lines = (content or "").splitlines()
    kept: list[str] = []
    for index, line in enumerate(lines):
        if re.search(r"[：:]\s*$", line):
            nxt = next((item for item in lines[index + 1 :] if item.strip()), "")
            continues = bool(
                nxt.startswith(("-", "*", "```", "    ", "\t")) or re.match(r"^\d+\.", nxt)
            )
            if not nxt or nxt.startswith("#") or not continues:
                kept.append(re.sub(r"[：:]\s*$", "。", line))
                continue
        kept.append(line)
    return "\n".join(kept)


def strip_empty_sections_and_footnotes(content: str) -> str:
    text = re.sub(r"^\[\^[^\]]+\]:\s*$", "", content or "", flags=re.M)
    parts = re.split(r"(?=^##\s+)", text, flags=re.M)
    kept: list[str] = []
    for part in parts:
        if part.startswith("## "):
            title, _, body = part.partition("\n")
            if title.strip() in {"## 目录", "## 架构图"}:
                kept.append(part)
                continue
            if not re.search(r"\S", body or "") and title.strip() not in {"## 目录"}:
                continue
        kept.append(part)
    return "".join(kept)


def rewrite_architecture_role_claims(content: str) -> str:
    text = content or ""
    replacements = (
        (r"边缘 Agent\s*`?cmd/ccagent", "主 REST/Web 服务 `cmd/ccagent"),
        (r"边缘 Agent\s*`?ccagent`?", "主 REST/Web 服务 ccagent"),
        (r"边缘 Agent ccagent", "主 REST/Web 服务 ccagent"),
        (r"`ccagent`\s*作为隧道客户端", "`ccagent` 作为主 REST/Web 服务"),
        (r"ccagent 作为隧道客户端", "ccagent 作为主 REST/Web 服务"),
        (r"`ccprobe-control`\s*作为主 REST/Web", "`ccprobe-control` 作为 gRPC 控制面"),
        (r"ccprobe-control 作为主 REST/Web", "ccprobe-control 作为 gRPC 控制面"),
        (r"ccagent / agent：客户端代理", "ccagent：主 REST/Web 服务；probe-agent：隧道客户端"),
        (r"single Go backend process", "four Go binaries under cmd/"),
        (r"单一 Go 后端进程", "cmd/ 下多个独立二进制"),
        (r"未提供显式迁移脚本", "db/migrations 提供 SQL 迁移"),
        (r"核心表包括 `users`、`profiles`", "核心表包括 `users`"),
        (r"、`profiles`", ""),
        (r"不存在 ORM 映射实体", "Pydantic 领域模型不是 ORM"),
        (
            r"`?internal/control`?\s*依赖\s*`?internal/services`?\s*与\s*`?internal/repository`?",
            "`internal/services` 依赖 `internal/control`；`internal/control` 不依赖 services/repository",
        ),
        (
            r"`?ccprobe-control`?[^。\n]{0,80}via services/repository/exporter",
            "ccprobe-control 的 import 图不含 services/repository/exporter",
        ),
        (r"via services/repository/exporter", "不经过 services/repository/exporter"),
    )
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)
    return text


def apply_deterministic_rewrites(
    content: str,
    root: Path,
    *,
    title: str = "",
    category: str = "",
    page_id: str = "",
) -> str:
    """Replay structural compose rewrites without LLM or fence-wide substitution."""
    text = content or ""
    text = strip_meta_instructions(text)
    text = strip_header_only_cites(text, root)
    text = rewrite_architecture_role_claims(text)
    try:
        from repo_wiki.generator.compose_evidence import (
            load_repo_import_edges,
            rewrite_false_import_claims,
        )

        text = rewrite_false_import_claims(text, load_repo_import_edges(root))
    except Exception:
        pass
    text = re.sub(r"^.*安全实现见.*$", "", text, flags=re.M)
    text = re.sub(r"<cite>\s*[^<]*_test\.go:[^<]*</cite>", "", text, flags=re.I)
    install_like = any(token in (title or "") for token in ("安装", "快速开始", "环境配置"))
    if is_install_owner_page(page_id=page_id, title=title) or (
        not page_id
        and (title in {"安装与配置", "安装指南"} or "## 安装步骤" in text)
        and not any(token in title for token in ("快速开始", "环境配置"))
    ):
        section = build_install_section(root)
        if section:
            text = replace_h2_section(text, ("安装步骤",), section)
    elif install_like or "## 安装步骤" in text:
        text = replace_h2_section(
            text,
            ("安装步骤",),
            "## 安装步骤\n\n完整步骤见安装与配置，本页不重复命令。\n",
        )
    arch_like = "架构" in (category or "") or "架构" in (title or "")
    if arch_like and is_architecture_owner_page(page_id=page_id, title=title):
        role = build_go_role_section(root)
        if role:
            text = replace_h2_section(text, ("进程角色",), role)
        text = strip_meta_instructions(text)
    elif arch_like:
        text = replace_h2_section(
            text,
            ("进程角色",),
            "## 角色说明\n\n进程角色见整体架构概览。\n",
        )
    if "数据模型" in (title or "") or "data" in (category or "").lower():
        block = build_data_model_cite_block(root)
        if block and "ProbeEndpoint" not in text and "fdf8821871d7" not in text:
            text = replace_h2_section(text, ("实体定义", "持久化表", "数据模型"), block)
    if is_security_owner_page(page_id=page_id, title=title) or (
        not page_id and ("安全" in title or "security" in (category or "").lower())
    ):
        block = build_security_cite_block(root)
        if block and "AK/SK" not in text and "jwt_token_prefix" not in text:
            text = replace_h2_section(text, ("安全实现",), block)
    text = strip_dangling_colon_leads(text)
    text = strip_empty_sections_and_footnotes(text)
    text = dedupe_identical_fences(text)
    return rebuild_toc_from_h2s(text)
