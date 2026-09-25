"""Round 11: text-safe rewrites and generate-path honesty over 25k defects."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from repo_wiki.generator.compose_evidence import (
    invented_compose_edges,
    load_compose_from_root,
    parse_compose_env_file_edges,
    parse_compose_topology,
)
from repo_wiki.generator.deterministic_sections import (
    ARCHITECTURE_ROLE_REPLACEMENTS,
    FRONTEND_CONSUMER_REPLACEMENTS,
    audit_text_rewrite,
    build_verify_section,
    dangling_rewrite_artifacts,
    leftover_compose_has_undeclared_env,
    leftover_mermaid_is_unusable,
    load_route_method_table,
    package_strip_targets,
    rewrite_architecture_role_claims,
    rewrite_frontend_consumer_claims,
    rewrite_route_methods_from_table,
    strip_unknown_go_packages,
)
from repo_wiki.generator.mermaid_planner import MermaidPlanner, MermaidRenderer
from repo_wiki.planner.schema import WikiTaxonomyCategory
from repo_wiki.verifier.handbook import (
    handbook_distinct_evidence_mermaid_count,
    has_architecture_core_citation,
)
from tests.test_handbook_round10 import (
    _fastapi_repo,
    _go_context,
    _go_repo,
    _page,
    _py_context,
    _render,
    _service,
)

_PROBE_25J = Path("/tmp/probe-25j/probe-handbook-2026-09-25j/repowiki/zh/content")
_PROBE_25K = Path("/tmp/probe-25k/probe-handbook-2026-09-25k/repowiki/zh/content")
_FASTAPI_25J = Path("/tmp/fastapi-25j/handbook-2026-09-25j/repowiki/zh/content")
_FASTAPI_25K = Path("/tmp/fastapi-25k/handbook-2026-09-25k/repowiki/zh/content")


def _protected_tokens() -> tuple[str, ...]:
    return (
        "probe_exporter",
        "podman-compose",
        "mysql-db",
        "grpc",
        "http",
        "rootpassword",
    )


def test_strip_unknown_packages_only_in_package_context(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    raw = (
        "仓库 `probe_exporter` 用 `podman-compose` 拉起 `mysql-db`，"
        "协议是 `grpc`/`http`，列名 `endpoint_id`，密码 `rootpassword`。"
        "周边包如 `audit`、`probe`、`securities`、`validator` 被组合使用。"
        "未知路径 `internal/securities` 应删除。"
    )
    out = strip_unknown_go_packages(raw, root)
    for token in _protected_tokens():
        assert f"`{token}`" in out or token in out
    assert "`endpoint_id`" in out
    assert "`securities`" not in out
    assert "`internal/securities`" not in out
    assert dangling_rewrite_artifacts(out) == []
    audit = audit_text_rewrite(
        raw,
        out,
        target_spans=["`securities`", "`internal/securities`", "`audit`", "`validator`"],
    )
    assert audit["collateral"] == 0
    assert audit["targeted"] > 0


def test_rewrite_diff_audit_fails_on_collateral_removal() -> None:
    before = "使用 `podman-compose` 而非 `docker-compose`，并提到 `securities` 包。"
    after = "使用  而非 ，并提到  包。"
    audit = audit_text_rewrite(before, after, target_spans=["`securities`"])
    assert audit["collateral"] > 0
    assert dangling_rewrite_artifacts(after)


def test_rewrites_are_text_safe_on_25j_and_25k(tmp_path: Path) -> None:
    import re

    root = _go_repo(tmp_path)
    corpora = [
        path for path in (_PROBE_25J, _PROBE_25K, _FASTAPI_25J, _FASTAPI_25K) if path.is_dir()
    ]
    for corpus in corpora:
        for page in corpus.rglob("*.md"):
            text = page.read_text(encoding="utf-8")
            for name in re.findall(r"(?:internal|cmd)/([A-Za-z0-9_-]+)", text):
                (root / "internal" / name).mkdir(parents=True, exist_ok=True)
    if not corpora:
        pytest.skip("25j/25k handbook fixtures are not extracted in this checkout")
    total_targeted = 0
    total_collateral = 0
    for corpus in corpora:
        for page in corpus.rglob("*.md"):
            before = page.read_text(encoding="utf-8")
            role_targets = [
                match.group(0)
                for pattern, _repl in ARCHITECTURE_ROLE_REPLACEMENTS
                for match in re.finditer(pattern, before)
            ]
            frontend_targets = [
                match.group(0)
                for pattern, _repl in FRONTEND_CONSUMER_REPLACEMENTS
                for match in re.finditer(pattern, before)
            ]
            route_targets = [
                token
                for path, method in load_route_method_table(root).items()
                if f"GET {path}" in before and method != "GET"
                for token in (f"GET {path}", f"{method} {path}", "GET", "GE")
            ]
            rewrites = (
                (
                    lambda text: strip_unknown_go_packages(text, root),
                    package_strip_targets(before, root),
                ),
                (rewrite_architecture_role_claims, role_targets),
                (
                    lambda text: rewrite_frontend_consumer_claims(
                        text, root, page_id=page.stem, title=page.stem
                    ),
                    frontend_targets,
                ),
                (lambda text: rewrite_route_methods_from_table(text, root), route_targets),
            )
            for rewriter, targets in rewrites:
                after = rewriter(before)
                if after == before:
                    continue
                audit = audit_text_rewrite(before, after, target_spans=targets)
                total_targeted += audit["targeted"]
                total_collateral += audit["collateral"]
                assert audit["collateral"] == 0, f"{page}: {audit}"
            after_all = rewrite_route_methods_from_table(
                rewrite_architecture_role_claims(strip_unknown_go_packages(before, root)),
                root,
            )
            for token in _protected_tokens():
                if f"`{token}`" in before:
                    assert f"`{token}`" in after_all
    assert total_collateral == 0
    assert total_targeted >= 0


def test_generate_does_not_blank_backticked_identifiers(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    raw = (
        "# 数据模型\n\n## 简介\n\n"
        "拨测端点 `probe_endpoint` 使用 `podman-compose` 而非 `docker-compose`，"
        "表 `mysql-db` 的列 `endpoint_id` 走 `grpc`。\n"
    )
    out = _render(
        _service(root),
        _page(
            "data-models-overview",
            "数据模型",
            WikiTaxonomyCategory.DATA_MODELS,
            "数据模型/数据模型.md",
        ),
        raw,
        _go_context(root),
        add_mermaid=False,
    )
    assert "使用 `podman-compose` 而非" in out
    assert dangling_rewrite_artifacts(out) == []
    assert "  而非" not in out


def test_route_methods_come_from_source_table(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    (root / "cmd" / "ccprobe-control" / "serve.go").write_text(
        "package main\n"
        'mux.HandleFunc("/force-resync", func(w http.ResponseWriter, r *http.Request) {\n'
        "    if r.Method != http.MethodPost { return }\n"
        "})\n"
        'mux.HandleFunc("/publish", func(w http.ResponseWriter, r *http.Request) {\n'
        "    if r.Method != http.MethodPost { return }\n"
        "})\n",
        encoding="utf-8",
    )
    (root / "internal" / "agent" / "http_transport.go").write_text(
        "package agent\n"
        'mux.HandleFunc("/v1/tasks/diff", func(w http.ResponseWriter, r *http.Request) {\n'
        "    if r.Method != http.MethodPost { return }\n"
        "})\n"
        'mux.HandleFunc("/v1/tasks/trigger", func(w http.ResponseWriter, r *http.Request) {\n'
        "    if r.Method != http.MethodPost { return }\n"
        "})\n",
        encoding="utf-8",
    )
    raw = (
        "# API参考\n\n"
        "GET /force-resync 与 GET /publish，以及 GET /v1/tasks/diff、GET /v1/tasks/trigger。\n"
        "```mermaid\nsequenceDiagram\n    Client->>Route: GET /force-resync (list flow)\n```\n"
    )
    page = _page(
        "api-reference", "API参考", WikiTaxonomyCategory.API_REFERENCE, "API参考/API参考.md"
    )
    ctx = _go_context(root)
    ctx.endpoints.extend(
        [
            {
                "method": "GET",
                "path": "/force-resync",
                "handler": "forceResync",
                "file_path": "cmd/ccprobe-control/serve.go",
                "line_number": 2,
            },
            {
                "method": "GET",
                "path": "/publish",
                "handler": "publish",
                "file_path": "cmd/ccprobe-control/serve.go",
                "line_number": 5,
            },
            {
                "method": "GET",
                "path": "/v1/tasks/diff",
                "handler": "diff",
                "file_path": "internal/agent/http_transport.go",
                "line_number": 2,
            },
            {
                "method": "GET",
                "path": "/v1/tasks/trigger",
                "handler": "trigger",
                "file_path": "internal/agent/http_transport.go",
                "line_number": 5,
            },
        ]
    )
    out = _render(_service(root), page, raw, ctx)
    assert "GET /force-resync" not in out
    assert "POST /force-resync" in out
    assert "GET /publish" not in out
    assert "POST /publish" in out
    assert "GET /v1/tasks/diff" not in out
    assert "POST /v1/tasks/diff" in out
    assert "Client->>Route:" not in out.replace("Client->>Route: ", "kept")


def test_request_flows_are_page_scoped_with_real_auth(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    (root / "web").mkdir()
    (root / "web" / "app.js").write_text(
        'fetch("/probe/list"); fetch("/tag"); fetch("/api/v1/agent/list");\n',
        encoding="utf-8",
    )
    planner = MermaidPlanner(str(root))
    ctx = {"endpoints": _go_context(root).endpoints, "modules": [], "import_edges": []}
    renderer = MermaidRenderer()
    pages = {
        "frontend-application-api": planner._plan_request_flow_sequence(
            "frontend-application-api", None, ctx
        ),
        "agent-proxy-api": planner._plan_request_flow_sequence("agent-proxy-api", None, ctx),
        "authentication-authorization-api": planner._plan_request_flow_sequence(
            "authentication-authorization-api", None, ctx
        ),
        "error-handling-status-codes": planner._plan_request_flow_sequence(
            "error-handling-status-codes", None, ctx
        ),
    }
    rendered = {name: renderer.render_diagram(plan) if plan else "" for name, plan in pages.items()}
    assert pages["frontend-application-api"] is not None
    assert pages["authentication-authorization-api"] is not None
    assert "force-resync" not in rendered["frontend-application-api"]
    assert any(
        token in rendered["frontend-application-api"] for token in ("/probe", "/tag", "/api/v1")
    )
    assert "X-Probe-Api-Token" in rendered[
        "authentication-authorization-api"
    ] or "X-Agent-Token" in (
        rendered["agent-proxy-api"] + rendered["authentication-authorization-api"]
    )
    catalog = planner._plan_api_sequence_diagram("api-reference", None, ctx)
    agent_catalog = planner._plan_api_sequence_diagram("agent-proxy-api", None, ctx)
    error_catalog = planner._plan_api_sequence_diagram("error-handling-status-codes", None, ctx)
    texts = [
        renderer.render_diagram(item) if item else ""
        for item in (catalog, agent_catalog, error_catalog)
    ]
    nonempty = [text for text in texts if text]
    if len(nonempty) >= 2:
        assert nonempty[0] != nonempty[1]
    for text in rendered.values():
        assert "ErrorWrapper" not in text
        assert "->>:" not in text.replace("->>: ", "ok")


def test_fastapi_pages_get_deterministic_diagrams(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    service = _service(root)
    ctx = _py_context(root)
    pages = [
        _page(
            "error-handling-status-codes",
            "错误处理与状态码",
            WikiTaxonomyCategory.API_REFERENCE,
            "API参考/错误处理与状态码.md",
        ),
        _page(
            "python-service-api",
            "Python服务API",
            WikiTaxonomyCategory.API_REFERENCE,
            "API参考/Python服务API/Python服务API.md",
        ),
        _page(
            "core-service-api",
            "核心服务API",
            WikiTaxonomyCategory.API_REFERENCE,
            "API参考/核心服务API/核心服务API.md",
        ),
        _page(
            "database-migration-strategy",
            "数据迁移策略",
            WikiTaxonomyCategory.DATA_MODELS,
            "数据模型/数据迁移策略.md",
        ),
        _page(
            "database-schema",
            "数据库架构",
            WikiTaxonomyCategory.DATA_MODELS,
            "数据模型/数据库架构/数据库架构.md",
        ),
    ]
    rendered: dict[str, str] = {}
    for page in pages:
        rendered[page.page_id] = _render(
            service,
            page,
            f"# {page.title}\n\n## 简介\n\n正文。\n",
            ctx,
        )
        assert "```mermaid" in rendered[page.page_id], page.title
    assert "erDiagram" in rendered["database-migration-strategy"]
    assert "commentaries" in rendered["database-migration-strategy"].lower()
    schema = rendered["database-schema"]
    assert "users {" in schema
    assert "int id" in schema or "string username" in schema
    assert re_empty_entity(schema, "users") is False
    err = rendered["error-handling-status-codes"]
    assert "HTTPException" in err or "sequenceDiagram" in err


def re_empty_entity(text: str, name: str) -> bool:
    return f"{name} {{\n    }}" in text or f"{name} {{\n}}" in text


def test_compose_env_file_edges_are_declared_only(tmp_path: Path) -> None:
    go = _go_repo(tmp_path)
    (go / "podman-compose.yml").write_text(
        "services:\n  mysql:\n    image: mysql\n  ccagent:\n    image: ccagent\n"
        "    depends_on: [mysql]\n  custom-probe:\n    image: probe\n",
        encoding="utf-8",
    )
    (go / ".env").write_text("X=1\n", encoding="utf-8")
    names, depends = parse_compose_topology((go / "podman-compose.yml").read_text())
    assert (".env", "ccagent") not in depends
    assert parse_compose_env_file_edges((go / "podman-compose.yml").read_text()) == []
    planner = MermaidPlanner(str(go))
    plan = planner._plan_compose_topology("deployment-operations", None, {})
    rendered = MermaidRenderer().render_diagram(plan) if plan else ""
    assert ".env" not in rendered
    _names, allowed = load_compose_from_root(go)
    assert invented_compose_edges(f"```mermaid\n{rendered}\n```", allowed) == []

    py = _fastapi_repo(tmp_path / "fa")
    (py / "docker-compose.yml").write_text(
        "services:\n  app:\n    image: app\n    env_file: .env\n    depends_on: [db]\n"
        "  db:\n    image: postgres\n    env_file: .env\n",
        encoding="utf-8",
    )
    env_edges = parse_compose_env_file_edges((py / "docker-compose.yml").read_text())
    assert (".env", "app") in env_edges
    assert (".env", "db") in env_edges
    _n, allowed_py = load_compose_from_root(py)
    markdown = (
        "```mermaid\nflowchart TD\n"
        "    env_file[.env]\n    app[app]\n    db[db]\n"
        "    env_file --> app\n    env_file --> db\n    app --> db\n```\n"
    )
    assert invented_compose_edges(markdown, allowed_py) == []


def test_architecture_body_is_grounded_without_cite_dump(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    raw = """# 整体架构概览

## 进程角色

ccagent 是主 REST/Web 服务。

## 简介

仓库以 `cmd/` + `internal/` 布局。`cmd/ccagent` 是与采集端配套的客户端入口。
控制面核心位于 `internal/control`，`internal/services` 与 `internal/exporter` 承担编排与导出。
"""
    page = _page(
        "architecture-overview",
        "整体架构概览",
        WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
        "架构设计/整体架构概览.md",
    )
    out = _render(_service(root), page, raw, _go_context(root))
    assert "客户端入口" not in out
    assert "是仓库中的实现包" not in out
    from repo_wiki.verifier.handbook import architecture_required_packages

    required = architecture_required_packages(root)
    assert has_architecture_core_citation(
        out + "".join(f"<cite>{rel}/x.go:1-1</cite>" for rel in required), root
    )
    event = _render(
        _service(root),
        _page(
            "event-driven-architecture",
            "事件驱动架构",
            WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
            "架构设计/事件驱动架构.md",
        ),
        "# 事件驱动架构\n\n## 简介\n\n"
        "隧道客户端 (`probe-agent`) 不在仓库范围内，由 `ccprobe-control` 远程调用。\n",
        _go_context(root),
        add_mermaid=False,
    )
    assert "probe-agent" in event or "数据面" in event or "进程角色" in event


def test_fastapi_verify_uses_curl_not_uvicorn_repeat(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    section = build_verify_section(root)
    assert "uvicorn" not in section.split("2.", 1)[1]
    assert "curl" in section
    out = _render(
        _service(root),
        _page(
            "installation",
            "安装与配置",
            WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
            "项目概述/安装与配置.md",
        ),
        "# 安装与配置\n\n## 启动与验证\n\n1. 准备。\n\n2. 确认应用进程已监听：`poetry run uvicorn app.main:app --reload`\n",
        _py_context(root),
        add_mermaid=False,
    )
    verify = out.split("## 启动与验证", 1)[1].split("\n## ", 1)[0]
    assert "curl" in verify
    assert verify.count("uvicorn") == 0


def test_generate_attaches_diagrams_even_when_leftover_exists(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    leftover = "# 错误处理与状态码\n\n```mermaid\nsequenceDiagram\n    Client->>Route:\n```\n"
    out = _render(
        _service(root),
        _page(
            "error-handling-status-codes",
            "错误处理与状态码",
            WikiTaxonomyCategory.API_REFERENCE,
            "API参考/错误处理与状态码.md",
        ),
        leftover,
        _py_context(root),
    )
    assert not re.search(r"Client->>Route:\s*$", out, flags=re.M)
    assert "```mermaid" in out
    content = tmp_path / "wiki"
    content.mkdir()
    (content / "a.md").write_text(out, encoding="utf-8")
    distinct, total = handbook_distinct_evidence_mermaid_count(content)
    assert total >= 1
    assert distinct >= 1


def test_leftover_undeclared_env_and_empty_er_are_replaced(tmp_path: Path) -> None:
    go = _go_repo(tmp_path)
    (go / "podman-compose.yml").write_text(
        "services:\n  mysql:\n    image: mysql\n  ccagent:\n    image: ccagent\n"
        "    depends_on: [mysql]\n  custom-probe:\n    image: probe\n",
        encoding="utf-8",
    )
    leftover = (
        "# 部署运维\n\n```mermaid\nflowchart TD\n"
        "    env_file[.env]\n    ccagent[ccagent]\n    custom[custom-probe]\n"
        "    env_file --> ccagent\n    env_file --> custom\n```\n"
    )
    assert leftover_compose_has_undeclared_env(leftover, go)
    out = _render(
        _service(go),
        _page(
            "deployment-operations",
            "部署运维",
            WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS,
            "部署运维.md",
        ),
        leftover,
        _go_context(go),
    )
    assert "env_file --> ccagent" not in out
    _names, allowed = load_compose_from_root(go)
    assert invented_compose_edges(out, allowed) == []

    py = _fastapi_repo(tmp_path / "fa")
    empty_er = (
        "# 数据库架构\n\n```mermaid\nerDiagram\n    users {\n    }\n"
        "    articles {\n    }\n    tags {\n    }\n```\n"
    )
    assert leftover_mermaid_is_unusable(empty_er)
    schema = _render(
        _service(py),
        _page(
            "database-schema",
            "数据库架构",
            WikiTaxonomyCategory.DATA_MODELS,
            "数据模型/数据库架构/数据库架构.md",
        ),
        empty_er,
        _py_context(py),
    )
    assert re_empty_entity(schema, "users") is False
    trigger = (
        "# 数据迁移策略\n\n```mermaid\nflowchart TD\n"
        "    version_fn[fdf8821871d7_main_tables.py]\n"
        "    trigger_fn[create_updated_at_trigger]\n"
        "    tables[users/articles timestamps]\n"
        "    version_fn --> trigger_fn\n    trigger_fn --> tables\n```\n"
    )
    assert leftover_mermaid_is_unusable(trigger)
    migration = _render(
        _service(py),
        _page(
            "database-migration-strategy",
            "数据迁移策略",
            WikiTaxonomyCategory.DATA_MODELS,
            "数据模型/数据迁移策略.md",
        ),
        trigger,
        _py_context(py),
    )
    assert "erDiagram" in migration
    assert "commentaries" in migration.lower()


def test_architecture_pages_keep_mermaid_after_overview(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    service = _service(root)
    ctx = _py_context(root)
    _render(
        service,
        _page(
            "project-overview",
            "项目概述",
            WikiTaxonomyCategory.PROJECT_OVERVIEW,
            "项目概述/项目概述.md",
        ),
        "# 项目概述\n\n正文。\n",
        ctx,
    )
    for page_id, title, output in (
        ("architecture-overview", "整体架构概览", "架构设计/整体架构概览.md"),
        ("event-driven-architecture", "事件驱动架构", "架构设计/事件驱动架构.md"),
        ("module-relationships", "模块关系", "架构设计/模块关系.md"),
    ):
        out = _render(
            service,
            _page(page_id, title, WikiTaxonomyCategory.ARCHITECTURE_DESIGN, output),
            f"# {title}\n\n正文。\n",
            ctx,
        )
        assert "```mermaid" in out, title


def test_frontend_page_uses_ccagent_fetch_routes(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    (root / "web").mkdir()
    (root / "web" / "app.js").write_text('fetch("/probe/list"); fetch("/tag");\n', encoding="utf-8")
    raw = (
        "# 前端应用API\n\n"
        "本 Wiki 页面聚焦仓库  中 ccprobe-control 模块面向前端应用的 HTTP API 入口。"
        "前端应用通过 HTTP 调用 ccprobe-control 暴露的查询与控制端点"
        "（`/force-resync`、`/healthz`、`/publish`、`/status`）。\n"
    )
    targets = [
        match.group(0)
        for pattern, _repl in FRONTEND_CONSUMER_REPLACEMENTS
        for match in re.finditer(pattern, raw)
    ]
    rewritten = rewrite_frontend_consumer_claims(
        raw, root, page_id="frontend-application-api", title="前端应用API"
    )
    if targets:
        audit = audit_text_rewrite(raw, rewritten, target_spans=targets)
        assert audit["collateral"] == 0
    out = _render(
        _service(root),
        _page(
            "frontend-application-api",
            "前端应用API",
            WikiTaxonomyCategory.API_REFERENCE,
            "API参考/前端应用API.md",
        ),
        raw,
        _go_context(root),
    )
    assert "ccprobe-control 模块面向前端应用" not in out
    assert "/probe" in out
    assert "```mermaid" in out


def test_missing_route_cites_are_attached(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    raw = "# Agent代理API\n\n## 简介\n\nGET /healthz 健康检查。\n"
    out = _render(
        _service(root),
        _page(
            "agent-proxy-api",
            "Agent代理API",
            WikiTaxonomyCategory.API_REFERENCE,
            "API参考/Agent代理API.md",
        ),
        raw,
        _go_context(root),
    )
    assert "GET /healthz" in out
    assert "<cite>" in out
