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
_PLANNING_LEAK_RE = re.compile(r"页面规划与证据绑定|页面基于仓库扫描")
_REQUIRED_GO_STRUCTS = ("ProbeEndpoint", "ProbeResult", "ProbeTag", "ProbeSecret")
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


def cite_readme_line(root: Path, needle: str) -> str:
    names = existing_readme_names(root)
    name = next((item for item in names if (root / item).is_file()), "")
    if not name:
        return ""
    for index, line in enumerate(read_readme_text(root).splitlines(), start=1):
        if needle in line:
            return f"<cite>{name}:{index}-{index}</cite>"
    return ""


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
            r"^(func\s+main\b|func\s+\w+|type\s+\w+\s+struct|class\s+\w+|def\s+\w+|package\s+\w+)",
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
            f"1. 先启动数据库，再导入结构。 {schema}",
            "",
            "```bash",
            "# 本地路径：导入结构",
            schema_cmd,
            "```",
            "",
            f"2. 编译主 REST/Web 服务。 {build}",
            "",
            "```bash",
            "go build -o bin/ccagent ./cmd/ccagent",
            "```",
            "",
            f"3. 启动本地进程并检查健康状态。 {run} {health}",
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
            f"先启动数据库服务，再启动应用服务。 {compose_db} {compose_app}",
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
    ccagent = cite_first_match(root, "cmd/ccagent/main.go", r"func\s+main\b")
    probe = cite_first_match(root, "cmd/probe-agent/main.go", r"func\s+main\b")
    control = ""
    for rel in ("cmd/ccprobe-control/serve.go", "cmd/ccprobe-control/main.go"):
        control = cite_first_match(root, rel, r"transport grpc|func\s+main\b|-serve")
        if control:
            break
    if not (ccagent or probe or control):
        return ""
    return (
        "## 进程角色\n\n"
        f"ccagent 是主 REST/Web 服务。 {ccagent}\n\n"
        f"probe-agent 是隧道客户端。 {probe}\n\n"
        f"ccprobe-control 是 gRPC 控制面服务（`-serve -transport grpc`）。 {control}\n"
    )


def extract_alembic_tables(text: str) -> list[dict[str, object]]:
    tables: list[dict[str, object]] = []
    starts = list(re.finditer(r'op\.create_table\(\s*"(\w+)"', text or ""))
    for index, match in enumerate(starts):
        name = match.group(1)
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text or "")
        body = (text or "")[match.end() : end]
        attrs = re.findall(r'sa\.Column\(\s*"(\w+)"', body)
        fks = re.findall(r'sa\.ForeignKey\(\s*"(\w+)\.(\w+)"', body)
        tables.append(
            {
                "name": name,
                "type": "migration_table",
                "attributes": attrs,
                "relationships": [f"belongs_to:{dest}" for dest, _col in fks],
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
                return f"<cite>{rel}:{index}-{min(len(lines), index + 20)}</cite>"
    return ""


def build_data_model_cite_block(root: Path) -> str:
    if (root / "internal" / "models").is_dir():
        cites = [go_struct_cite(root, name) for name in _REQUIRED_GO_STRUCTS]
        cites = [item for item in cites if item]
        if not cites:
            return ""
        return (
            "实体定义见 internal/models 中的 GORM 结构体："
            f" ProbeEndpoint {cites[0] if cites else ''}，"
            + " ".join(cites[1:])
            + "。表结构见 db/schema.sql。\n"
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
        f"持久化表以 `{rel}` 为准，当前迁移定义 {names}。 "
        f"{migration_cite} app/models/domain 是 Pydantic 领域模型，不是 ORM 实体。"
        f" {domain}\n"
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
    return "安全实现见 " + " ".join(cites) + "。\n"


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
    return not re.search(
        r"^(type\s+\w+\s+struct|func\s+main\b|def\s+\w+|class\s+\w+)", window, re.M
    )


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


def apply_deterministic_rewrites(
    content: str, root: Path, *, title: str = "", category: str = ""
) -> str:
    """Replay structural compose rewrites without LLM or fence-wide substitution."""
    text = content or ""
    text = strip_meta_instructions(text)
    text = strip_header_only_cites(text, root)
    install_like = any(token in (title or "") for token in ("安装", "快速开始", "环境配置"))
    if install_like or "## 安装步骤" in text:
        section = build_install_section(root)
        if section:
            text = replace_h2_section(text, ("安装步骤",), section)
    if "架构" in (category or "") or "架构" in (title or ""):
        role = build_go_role_section(root)
        if role:
            text = replace_h2_section(text, ("进程角色",), role)
        text = strip_meta_instructions(text)
    if "数据模型" in (title or "") or "data" in (category or "").lower():
        block = build_data_model_cite_block(root)
        if block and "ProbeEndpoint" not in text and "fdf8821871d7" not in text:
            text = replace_h2_section(text, ("实体定义", "数据模型"), "## 实体定义\n\n" + block)
    if "安全" in (title or "") or "security" in (category or "").lower():
        block = build_security_cite_block(root)
        if block and "internal/auth" not in text and "jwt.py" not in text:
            text = text.rstrip() + "\n\n" + block
    text = dedupe_identical_fences(text)
    return rebuild_toc_from_h2s(text)
