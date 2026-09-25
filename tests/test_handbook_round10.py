"""Round 10: generate-path contract over raw LLM pages with 25j defects."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.generator.compose_evidence import prose_role_contradictions
from repo_wiki.generator.composer import ComposerContext
from repo_wiki.generator.deterministic_sections import (
    cite_first_match,
    is_header_only_cite,
    page_has_meta_instruction,
)
from repo_wiki.generator.mermaid_planner import MermaidPlanner, MermaidRenderer
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory
from repo_wiki.verifier.handbook import (
    handbook_distinct_evidence_mermaid_count,
    has_architecture_core_citation,
    normalize_mermaid_block,
)


def _service(root: Path) -> RepoWikiService:
    cfg = RepoWikiConfig()
    cfg.project.root = str(root)
    return RepoWikiService(cfg)


def _page(
    page_id: str,
    title: str,
    category: WikiTaxonomyCategory,
    output: str,
) -> WikiPagePlan:
    return WikiPagePlan(
        page_id=page_id,
        title=title,
        category=category,
        output_path=output,
    )


def _go_repo(root: Path) -> Path:
    (root / "cmd" / "ccagent").mkdir(parents=True)
    (root / "cmd" / "probe-agent").mkdir(parents=True)
    (root / "cmd" / "ccprobe-control").mkdir(parents=True)
    (root / "internal" / "exporter").mkdir(parents=True)
    (root / "internal" / "services").mkdir(parents=True)
    (root / "internal" / "control").mkdir(parents=True)
    (root / "internal" / "repository").mkdir(parents=True)
    (root / "internal" / "agent").mkdir(parents=True)
    (root / "internal" / "models").mkdir(parents=True)
    (root / "internal" / "probe").mkdir(parents=True)
    (root / "db" / "migrations").mkdir(parents=True)
    (root / "cmd" / "ccagent" / "main.go").write_text(
        "package main\nfunc main() {}\n", encoding="utf-8"
    )
    (root / "cmd" / "probe-agent" / "main.go").write_text(
        "package main\nfunc main() {}\n", encoding="utf-8"
    )
    (root / "cmd" / "ccprobe-control" / "main.go").write_text(
        "package main\nfunc main() {}\n", encoding="utf-8"
    )
    (root / "cmd" / "ccprobe-control" / "serve.go").write_text(
        "package main\nfunc runGRPCServe() {}\n"
        'mux.HandleFunc("/force-resync", func(w http.ResponseWriter, r *http.Request) {\n'
        "    if r.Method != http.MethodPost { return }\n"
        "})\n"
        'mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {})\n',
        encoding="utf-8",
    )
    (root / "internal" / "agent" / "http_transport.go").write_text(
        "package agent\n"
        "func (t *Transport) Mount(mux *http.ServeMux) {\n"
        '    mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {})\n'
        "}\n"
        'const agentHeader = "X-Agent-Token"\n',
        encoding="utf-8",
    )
    (root / "internal" / "exporter" / "export.go").write_text(
        "package exporter\nfunc Export() {}\n", encoding="utf-8"
    )
    (root / "internal" / "services" / "probe.go").write_text(
        "package services\nfunc RunProbe() {}\n", encoding="utf-8"
    )
    (root / "internal" / "control" / "hub.go").write_text(
        "package control\nfunc NewTunnelHub() {}\n", encoding="utf-8"
    )
    (root / "internal" / "repository" / "store.go").write_text(
        "package repository\nfunc Save() {}\n", encoding="utf-8"
    )
    (root / "internal" / "models" / "endpoint.go").write_text(
        "package models\n\n"
        "type ProbeEndpoint struct {\n    ID int64\n}\n"
        "type ProbeResult struct {\n    OK bool\n}\n"
        "type ProbeTag struct {\n    Name string\n}\n"
        "type ProbeSecret struct {\n    Value string\n}\n",
        encoding="utf-8",
    )
    (root / "apiauth.go").write_text(
        "package ccagent\n"
        "// EnvAPIToken overrides Config.APIToken. When non-empty every management\n"
        "// route requires Authorization Bearer or X-Probe-Api-Token.\n"
        'const EnvAPIToken = "PROBE_API_TOKEN"\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "# probe_exporter\n\n"
        "curl http://localhost:1900/health\n"
        "GET /api/v1/agent/list is documented here only as an overview.\n",
        encoding="utf-8",
    )
    (root / "QUICKSTART.md").write_text("# Quickstart\n\nhello\n", encoding="utf-8")
    (root / "CONTRIBUTING.md").write_text("# Contributing\n\nbuild notes\n", encoding="utf-8")
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "CC_PROBE_PHASE6_DEPS.md").write_text("# deps\n\nlist\n", encoding="utf-8")
    (root / "db" / "schema.sql").write_text(
        "-- header\nCREATE TABLE t (id int);\n", encoding="utf-8"
    )
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text(
        "jobs:\n  build:\n    run: go build -o bin/ccagent ./cmd/ccagent\n",
        encoding="utf-8",
    )
    return root


def _fastapi_repo(root: Path) -> Path:
    versions = root / "app" / "db" / "migrations" / "versions"
    versions.mkdir(parents=True)
    (root / "app" / "api" / "routes").mkdir(parents=True)
    (root / "app" / "api" / "dependencies").mkdir(parents=True)
    (root / "app" / "api" / "errors").mkdir(parents=True)
    (root / "app" / "models" / "domain").mkdir(parents=True)
    (root / "app" / "core" / "settings").mkdir(parents=True)
    (root / "app" / "services").mkdir(parents=True)
    (root / "app" / "main.py").write_text("from app.api.routes import articles\n", encoding="utf-8")
    (root / "app" / "db" / "queries.py").write_text(
        "def fetch():\n    return []\n", encoding="utf-8"
    )
    (root / "app" / "api" / "dependencies" / "authentication.py").write_text(
        "from app.core.settings import Settings\n"
        "def get_current_user_authorizer():\n    return None\n",
        encoding="utf-8",
    )
    (root / "app" / "core" / "settings" / "__init__.py").write_text(
        "class Settings:\n    pass\n", encoding="utf-8"
    )
    (root / "app" / "services" / "articles.py").write_text(
        "from app.db import queries\n", encoding="utf-8"
    )
    (root / "app" / "api" / "errors" / "http_error.py").write_text(
        "from fastapi import HTTPException\n"
        "async def http_error_handler(_, exc: HTTPException):\n    return exc\n",
        encoding="utf-8",
    )
    (root / "app" / "api" / "routes" / "authentication.py").write_text(
        "@router.post('', name='auth:register')\n"
        "async def register():\n    return {}\n"
        "@router.post('/login', name='auth:login')\n"
        "async def login():\n    return {}\n",
        encoding="utf-8",
    )
    (root / "app" / "api" / "routes" / "articles.py").write_text(
        "from app.services import articles\nfrom app.db import queries\n"
        "@router.get('')\nasync def list_articles():\n    return []\n",
        encoding="utf-8",
    )
    (root / "app" / "api" / "routes" / "tags.py").write_text(
        "@router.get('')\nasync def get_tags():\n    return []\n",
        encoding="utf-8",
    )
    (root / "app" / "models" / "domain" / "users.py").write_text(
        "class User:\n    id = 1\n", encoding="utf-8"
    )
    (versions / "fdf8821871d7_main_tables.py").write_text(
        """
op.create_table(
    "users",
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("username", sa.Text),
    *timestamps(),
)
op.create_table(
    "followers_to_followings",
    sa.Column("follower_id", sa.Integer, sa.ForeignKey("users.id")),
    sa.Column("following_id", sa.Integer, sa.ForeignKey("users.id")),
)
op.create_primary_key(
    "pk_followers_to_followings",
    "followers_to_followings",
    ["follower_id", "following_id"],
)
op.create_table(
    "articles",
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("slug", sa.Text, unique=True, index=True),
    sa.Column("title", sa.Text),
    sa.Column("author_id", sa.Integer, sa.ForeignKey("users.id")),
    *timestamps(),
)
op.create_table(
    "articles_to_tags",
    sa.Column("article_id", sa.Integer, sa.ForeignKey("articles.id")),
    sa.Column("tag", sa.Text),
)
op.create_primary_key("pk_articles_to_tags", "articles_to_tags", ["article_id", "tag"])
op.create_table(
    "favorites",
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
    sa.Column("article_id", sa.Integer, sa.ForeignKey("articles.id")),
)
op.create_primary_key("pk_favorites", "favorites", ["user_id", "article_id"])
op.create_table(
    "commentaries",
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("body", sa.Text),
    *timestamps(),
)
def create_updated_at_trigger():
    pass
""",
        encoding="utf-8",
    )
    (root / "docker-compose.yml").write_text(
        "services:\n  api:\n    image: app\n", encoding="utf-8"
    )
    (root / "README.md").write_text("# fastapi-realworld\n", encoding="utf-8")
    return root


def _go_context(root: Path) -> ComposerContext:
    return ComposerContext(
        repository_name="probe_exporter",
        primary_language="go",
        framework="gin",
        repository_root=str(root),
        endpoints=[
            {
                "method": "GET",
                "path": "/api/v1/agent/list",
                "handler": "ListAgents",
                "file_path": "controller.go",
                "line_number": 80,
                "service": "ccagent",
            },
            {
                "method": "GET",
                "path": "/healthz",
                "handler": "Mount",
                "file_path": "internal/agent/http_transport.go",
                "line_number": 3,
                "service": "probe-agent",
                "auth_type": "none",
            },
            {
                "method": "POST",
                "path": "/force-resync",
                "handler": "forceResync",
                "file_path": "cmd/ccprobe-control/serve.go",
                "line_number": 4,
                "service": "ccprobe-control",
            },
            {
                "method": "GET",
                "path": "/api/v1/web/assets",
                "handler": "StaticAssets",
                "file_path": "web/static.go",
                "line_number": 12,
                "service": "frontend",
            },
            {
                "method": "GET",
                "path": "/probe/list",
                "handler": "ListProbes",
                "file_path": "cmd/ccagent/probe.go",
                "line_number": 8,
                "service": "ccagent",
            },
        ],
        modules=[
            {"name": "internal/exporter", "path": "internal/exporter"},
            {"name": "internal/services", "path": "internal/services"},
            {"name": "internal/control", "path": "internal/control"},
        ],
        key_directories=["cmd", "internal"],
    )


def _py_context(root: Path) -> ComposerContext:
    return ComposerContext(
        repository_name="fastapi-realworld",
        primary_language="python",
        framework="fastapi",
        repository_root=str(root),
        endpoints=[
            {
                "method": "POST",
                "path": "/api/users",
                "handler": "register",
                "file_path": "app/api/routes/authentication.py",
                "line_number": 2,
                "auth_type": "none",
            },
            {
                "method": "POST",
                "path": "/api/users/login",
                "handler": "login",
                "file_path": "app/api/routes/authentication.py",
                "line_number": 5,
                "auth_type": "none",
            },
            {
                "method": "GET",
                "path": "/api/articles",
                "handler": "list_articles",
                "file_path": "app/api/routes/articles.py",
                "line_number": 2,
            },
            {
                "method": "GET",
                "path": "/api/tags",
                "handler": "get_tags",
                "file_path": "app/api/routes/tags.py",
                "line_number": 2,
            },
        ],
        models=[],
        key_directories=["app"],
    )


def _render(
    service: RepoWikiService,
    page: WikiPagePlan,
    markdown: str,
    context: ComposerContext | None,
    add_mermaid: bool = True,
) -> str:
    return service._enforce_qoder_page_contract(
        page=page,
        markdown=markdown,
        binding=None,
        add_mermaid=add_mermaid,
        composition_context=context,
    )


def test_normalize_mermaid_collapses_page_id_suffixes() -> None:
    a = (
        "sequenceDiagram\n"
        "    Client->>APIAuth: X-Probe-Api-Token [frontend-application-api]\n"
        "    APIAuth->>hListAgents: GET /api/v1/agent/list [frontend-application-api]\n"
    )
    b = (
        "sequenceDiagram\n"
        "    Client->>APIAuth: X-Probe-Api-Token [authentication-authorization-api]\n"
        "    APIAuth->>hListAgents: GET /api/v1/agent/list [authentication-authorization-api]\n"
    )
    assert normalize_mermaid_block(a) == normalize_mermaid_block(b)
    assert "[" not in normalize_mermaid_block(a)


def test_generate_strips_page_id_suffixes_and_replaces_template_flow(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    service = _service(root)
    raw = """# 前端应用API

## 简介

前端页面。

```mermaid
sequenceDiagram
    Client->>APIAuth: X-Probe-Api-Token [frontend-application-api]
    APIAuth->>hListAgents: GET /api/v1/agent/list [frontend-application-api]
    hListAgents->>svcController: handle [frontend-application-api]
```
"""
    page = _page(
        "frontend-application-api",
        "前端应用API",
        WikiTaxonomyCategory.API_REFERENCE,
        "API参考/前端应用API.md",
    )
    out = _render(service, page, raw, _go_context(root))
    assert "[frontend-application-api]" not in out
    assert "GET /api/v1/agent/list" not in out or "GET /api/v1/web/assets" in out


def test_generate_request_flows_are_page_scoped_and_honest(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    planner = MermaidPlanner(str(root))
    ctx = {
        "endpoints": _go_context(root).endpoints,
        "modules": [],
        "import_edges": [],
    }
    frontend = planner._plan_request_flow_sequence("frontend-application-api", None, ctx)
    agent = planner._plan_request_flow_sequence("agent-proxy-api", None, ctx)
    control = planner._plan_request_flow_sequence("ccprobe-control-api", None, ctx)
    renderer = MermaidRenderer()
    front_txt = renderer.render_diagram(frontend) if frontend else ""
    agent_txt = renderer.render_diagram(agent) if agent else ""
    control_txt = renderer.render_diagram(control) if control else ""
    for text in (front_txt, agent_txt, control_txt):
        assert "[" not in text or "sequenceDiagram" in text
        assert "[frontend-application-api]" not in text
        assert "[agent-proxy-api]" not in text
        assert "ErrorWrapper" not in text
    if agent_txt:
        assert "X-Probe-Api-Token" not in agent_txt
        assert "/healthz" in agent_txt
    if control_txt:
        assert "GET /force-resync" not in control_txt
        if "/force-resync" in control_txt:
            assert "POST /force-resync" in control_txt


def test_generate_fastapi_register_and_error_nodes_are_real(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    planner = MermaidPlanner(str(root))
    ctx = {
        "endpoints": _py_context(root).endpoints,
        "modules": [],
        "import_edges": [],
    }
    register = planner._plan_request_flow_sequence("authentication-authorization-api", None, ctx)
    errors = planner._plan_request_flow_sequence("error-handling-status-codes", None, ctx)
    renderer = MermaidRenderer()
    auth_txt = renderer.render_diagram(register) if register else ""
    err_txt = renderer.render_diagram(errors) if errors else ""
    assert "ErrorWrapper" not in auth_txt
    assert "ErrorWrapper" not in err_txt
    if (
        "POST /api/users" in auth_txt
        and "/login" not in auth_txt.split("POST /api/users", 1)[1][:20]
    ):
        assert "AuthenticationDep" not in auth_txt
    leftover = """# 身份认证

```mermaid
sequenceDiagram
    Client->>AuthenticationDep: Authorization [security-compliance]
    AuthenticationDep->>hregister: POST /api/users [security-compliance]
```
"""
    page = _page(
        "identity-authentication",
        "身份认证",
        WikiTaxonomyCategory.SECURITY_COMPLIANCE,
        "安全合规/身份认证.md",
    )
    out = _render(_service(root), page, leftover, _py_context(root))
    assert "ErrorWrapper" not in out
    assert "[security-compliance]" not in out
    if "POST /api/users" in out and "login" not in out:
        assert not ("AuthenticationDep" in out and "hregister" in out)


def test_generate_strips_leftover_invented_join_id_pk(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    raw = """# 数据模型

## 实体定义

```mermaid
erDiagram
    followers_to_followings {
        int follower_id PK
        string id PK
    }
    articles_to_tags {
        int article_id PK
        string id PK
        int tag PK
    }
    favorites {
        int user_id PK
        string id PK
    }
```
"""
    page = _page(
        "data-models-overview",
        "数据模型",
        WikiTaxonomyCategory.DATA_MODELS,
        "数据模型/数据模型.md",
    )
    out = _render(_service(root), page, raw, _py_context(root), add_mermaid=False)
    assert "string id PK" not in out


def test_generate_join_tag_is_string_and_migration_has_diagram(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    planner = MermaidPlanner(str(root))
    models = [
        {
            "name": "articles_to_tags",
            "type": "migration_table",
            "attributes": ["article_id", "tag"],
            "attribute_types": ["Integer", "Text"],
            "primary_key": "",
            "primary_keys": ["article_id", "tag"],
        }
    ]
    plan = planner._plan_join_key_diagram("database-schema", None, {"data_models": models})
    rendered = MermaidRenderer().render_diagram(plan)
    assert "string tag" in rendered
    assert "int tag" not in rendered
    page = _page(
        "database-migration-strategy",
        "数据迁移策略",
        WikiTaxonomyCategory.DATA_MODELS,
        "数据模型/数据迁移策略.md",
    )
    out = _render(
        _service(root),
        page,
        "# 数据迁移策略\n\n## 简介\n\n迁移顺序以 alembic versions 为准。\n",
        _py_context(root),
    )
    assert "```mermaid" in out
    assert "erDiagram" in out or "alembic" in out.lower() or "migration" in out.lower()


def test_generate_rewrites_roles_rejects_securities_and_checker_skips_contrast(
    tmp_path: Path,
) -> None:
    root = _go_repo(tmp_path)
    raw = """# 整体架构概览

## 进程角色

ccagent 是主 REST/Web 服务。
probe-agent 是隧道客户端。

## 简介

agent 侧由 ccagent 主进程负责隧道客户端与运行环境适配。

## 项目结构

`cmd/ccagent` 作为隧道客户端入口，周边包如 `audit`、`probe`、`securities`、`validator` 被组合使用。

## 详细分析

控制面是带隧道能力的主 REST/Web 服务。后续 ccagent 作为隧道客户端连向 ccprobe-control。
"""
    page = _page(
        "architecture-overview",
        "整体架构概览",
        WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
        "架构设计/整体架构概览.md",
    )
    out = _render(_service(root), page, raw, _go_context(root))
    assert "负责隧道客户端" not in out
    assert "作为隧道客户端入口" not in out
    assert "作为隧道客户端连向" not in out
    assert "带隧道能力的主 REST/Web 服务" not in out
    assert "securities" not in out
    assert not prose_role_contradictions(out)
    contrast = (
        "需要强调的是，`ccagent` 是主 REST/Web 服务，`probe-agent` 才是隧道客户端，"
        "二者并非同一角色。"
    )
    assert prose_role_contradictions(contrast) == []


def test_generate_architecture_core_cites_internal_packages(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    raw = """# 整体架构概览

## 进程角色

ccagent 是主 REST/Web 服务。

## 简介

只引用了入口二进制。
<cite>cmd/ccagent/main.go:2-2</cite>
"""
    page = _page(
        "architecture-overview",
        "整体架构概览",
        WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
        "架构设计/整体架构概览.md",
    )
    out = _render(_service(root), page, raw, _go_context(root))
    assert has_architecture_core_citation(out, root)
    assert "internal/exporter" in out
    assert "internal/" in out


def test_generate_strips_header_cites_and_keeps_compose_advice(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    raw = """# 环境配置

## 简介

入口文档 <cite>QUICKSTART.md:1-2</cite> <cite>CONTRIBUTING.md:1-6</cite>
<cite>docs/CC_PROBE_PHASE6_DEPS.md:1-6</cite> <cite>db/schema.sql:1-1</cite>。

**HA compose 与基础 compose 不要把它当作独立 Compose 入口**，
Custom Probe 源码入口为 `cmd/custom-probe/main.go`。
"""
    page = _page(
        "environment-setup",
        "环境配置",
        WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS,
        "部署运维/环境配置.md",
    )
    out = _render(_service(root), page, raw, _go_context(root), add_mermaid=False)
    assert "QUICKSTART.md:1-2" not in out
    assert "CONTRIBUTING.md:1-6" not in out
    assert "CC_PROBE_PHASE6_DEPS.md:1-6" not in out
    assert "schema.sql:1-1" not in out
    assert page_has_meta_instruction(out) is False
    assert "不要把它当作独立 Compose" in out
    assert is_header_only_cite("<cite>docker-compose.yml:1-2</cite>", root) is True
    missing = tmp_path / "empty"
    missing.mkdir()
    assert is_header_only_cite("<cite>QUICKSTART.md:1-2</cite>", missing) is True


def test_generate_agent_api_uses_registration_cites_and_lists_structs(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    raw = """# Agent代理API

## 简介

- GET /healthz 健康检查 <cite>README.md:1-20</cite>
- POST /force-resync 强制同步 <cite>README.md:1-20</cite>

## 实体定义

ProbeEndpoint <cite>internal/models/endpoint.go:3-5</cite> ProbeResult <cite>internal/models/endpoint.go:6-8</cite> ProbeTag <cite>internal/models/endpoint.go:9-11</cite> ProbeSecret <cite>internal/models/endpoint.go:12-14</cite> ProbeEndpoint <cite>internal/models/endpoint.go:3-5</cite> ProbeResult <cite>internal/models/endpoint.go:6-8</cite> ProbeTag <cite>internal/models/endpoint.go:9-11</cite> ProbeSecret <cite>internal/models/endpoint.go:12-14</cite> extra1 <cite>internal/models/endpoint.go:3-5</cite> extra2 <cite>internal/models/endpoint.go:6-8</cite>
"""
    page = _page(
        "agent-proxy-api",
        "Agent代理API",
        WikiTaxonomyCategory.API_REFERENCE,
        "API参考/Agent代理API.md",
    )
    out = _render(_service(root), page, raw, _go_context(root))
    assert "README.md:1-20" not in out
    assert "internal/agent/http_transport.go" in out
    model_page = _page(
        "data-models-overview",
        "数据模型",
        WikiTaxonomyCategory.DATA_MODELS,
        "数据模型/数据模型.md",
    )
    model_out = _render(_service(root), model_page, raw.replace("Agent代理API", "数据模型"), None)
    long_lines = [line for line in model_out.splitlines() if line.count("<cite>") >= 8]
    assert long_lines == []
    assert "- " in model_out and "ProbeEndpoint" in model_out


def test_generate_verify_step_command_build_token_and_toc(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    raw = """# 安装与配置

## 安装步骤

```bash
curl http://localhost:1900/health
```

## 启动与验证

1. 按安装步骤完成编排或本地编译。

2. 用源码健康检查确认进程存活。

## 开发指南

本地构建：`go build -o bin/...`

## 身份认证

管理接口读取 PROBE_API_TOKEN。
"""
    install = _page(
        "installation",
        "安装与配置",
        WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
        "开发指南/安装与配置.md",
    )
    out = _render(_service(root), install, raw, _go_context(root), add_mermaid=False)
    verify = out.split("## 启动与验证", 1)[1].split("## ", 1)[0]
    assert "curl" in verify
    ide = _page(
        "ide-configuration",
        "IDE配置",
        WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
        "开发指南/IDE配置.md",
    )
    ide_out = _render(
        _service(root),
        ide,
        "# IDE配置\n\n## 构建\n\n`go build -o bin/...`\n",
        _go_context(root),
        add_mermaid=False,
    )
    assert "go build -o bin/..." not in ide_out
    assert "bin/ccagent" in ide_out
    auth = _page(
        "identity-authentication",
        "身份认证",
        WikiTaxonomyCategory.SECURITY_COMPLIANCE,
        "安全合规/身份认证.md",
    )
    auth_out = _render(_service(root), auth, "# 身份认证\n\n## 认证实现\n\n说明。\n", None)
    assert "apiauth.go:4-4" in auth_out or "apiauth.go:4" in auth_out
    assert "apiauth.go:3-3" not in auth_out
    cite = cite_first_match(root, "apiauth.go", r"EnvAPIToken|PROBE_API_TOKEN")
    assert cite.endswith(":4-4</cite>")
    title_at = out.find("# ")
    toc_at = out.find("## 目录")
    last_h2 = out.rfind("\n## ")
    assert toc_at > title_at
    assert toc_at < last_h2 or out.strip().endswith("## 目录") is False
    assert not out.rstrip().endswith("1. 安装步骤") or toc_at < out.find("## 安装步骤")


def test_honest_distinct_mermaid_count_ignores_suffix_only_copies(tmp_path: Path) -> None:
    content = tmp_path / "content"
    content.mkdir()
    for name, suffix in (
        ("a.md", "frontend-application-api"),
        ("b.md", "authentication-authorization-api"),
        ("c.md", "api-reference"),
    ):
        (content / name).write_text(
            "# p\n\n```mermaid\nsequenceDiagram\n"
            f"    Client->>APIAuth: X-Probe-Api-Token [{suffix}]\n"
            f"    APIAuth->>h: GET /api/v1/agent/list [{suffix}]\n"
            "```\n",
            encoding="utf-8",
        )
    distinct, total = handbook_distinct_evidence_mermaid_count(content)
    assert total == 3
    assert distinct == 0
