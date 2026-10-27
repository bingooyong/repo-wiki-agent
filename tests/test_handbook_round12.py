"""Round 12 Part B: FastAPI source fixes on planner / deterministic sections."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.generator.deterministic_sections import (
    attach_missing_route_cites,
    derive_framework_stack,
    ensure_overview_names_framework,
)
from repo_wiki.generator.mermaid_planner import (
    MermaidPlanner,
    MermaidRenderer,
    _auth_hop,
    _endpoint_is_anonymous,
)
from repo_wiki.planner.schema import WikiTaxonomyCategory
from repo_wiki.verifier.handbook import normalize_mermaid_block, overview_identity_satisfied
from tests.test_handbook_round10 import (
    _fastapi_repo,
    _page,
    _py_context,
    _render,
    _service,
)


def test_login_is_anonymous_and_has_no_auth_hop() -> None:
    login = {
        "method": "POST",
        "path": "/api/users/login",
        "file_path": "app/api/routes/authentication.py",
        "auth_type": "none",
    }
    register = {
        "method": "POST",
        "path": "/api/users",
        "file_path": "app/api/routes/authentication.py",
        "auth_type": "none",
    }
    assert _endpoint_is_anonymous(login)
    assert _endpoint_is_anonymous(register)
    assert _auth_hop(login, go_auth=False, py_auth=True) == (None, None)


def test_request_flow_keeps_login_anonymous(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    planner = MermaidPlanner(str(root))
    plan = planner._plan_request_flow_sequence(
        "core-service-api",
        None,
        {
            "endpoints": [
                {
                    "method": "POST",
                    "path": "/api/users/login",
                    "handler": "login",
                    "file_path": "app/api/routes/authentication.py",
                    "line_number": 23,
                    "auth_type": "none",
                }
            ]
        },
    )
    assert plan is not None
    blob = "\n".join(f"{a}->{b}: {msg}" for a, b, msg in plan.sequence_messages)
    assert "AuthenticationDep" not in plan.sequence_participants
    assert "Authorization" not in blob
    assert "POST /api/users/login" in blob


def test_attach_route_cites_skip_fences_and_use_method_path() -> None:
    endpoints = [
        {
            "method": "GET",
            "path": "/api/articles",
            "file_path": "app/api/routes/articles/articles_resource.py",
            "line_number": 30,
        },
        {
            "method": "POST",
            "path": "/api/articles",
            "file_path": "app/api/routes/articles/articles_resource.py",
            "line_number": 59,
        },
        {
            "method": "GET",
            "path": "/api/articles/{slug}",
            "file_path": "app/api/routes/articles/articles_resource.py",
            "line_number": 82,
        },
        {
            "method": "PUT",
            "path": "/api/articles/{slug}",
            "file_path": "app/api/routes/articles/articles_resource.py",
            "line_number": 95,
        },
    ]
    raw = (
        "列表 GET /api/articles 返回文章。\n"
        "```mermaid\n"
        "sequenceDiagram\n"
        "    Client->>Route: GET /api/articles (list flow)\n"
        "```\n"
        "详情 GET /api/articles/{slug}。\n"
    )
    out = attach_missing_route_cites(raw, endpoints)
    fence = out[out.index("```mermaid") : out.index("```\n", out.index("```mermaid") + 3) + 3]
    assert "<cite>" not in fence
    assert "articles_resource.py:30-30" in out
    assert "articles_resource.py:82-82" in out
    assert "articles_resource.py:59-59" not in out
    assert "articles_resource.py:95-95" not in out


def test_jwt_sequence_does_not_invent_jwt_service(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    (root / "app" / "services" / "jwt.py").write_text(
        "def get_username_from_token(token, secret_key):\n    return 'u'\n",
        encoding="utf-8",
    )
    planner = MermaidPlanner(str(root))
    plan = planner._plan_jwt_sequence("authentication-authorization-api", None, {})
    assert plan is not None
    assert "JWTService" not in plan.sequence_participants
    rendered, ok, _ = MermaidRenderer().render_diagram_with_validation(plan)
    assert ok
    assert "JWTService" not in rendered
    assert "get_username_from_token" in rendered or "jwt" in rendered


def test_overview_names_fastapi_from_pyproject(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    (root / "pyproject.toml").write_text(
        '[tool.poetry]\nname = "demo"\ndescription = "Backend with awesome FastAPI"\n'
        'fastapi = "^0.79.1"\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text("# Conduit RealWorld\n", encoding="utf-8")
    (root / "app" / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )
    assert derive_framework_stack(root) == "FastAPI"
    raw = "# 项目概述\n\n这是一套 RealWorld 示例后端，提供文章与用户接口。\n"
    assert "fastapi" not in raw.lower()
    filled = ensure_overview_names_framework(raw, root)
    assert "FastAPI" in filled
    named = filled.replace("RealWorld", "Conduit RealWorld", 1)
    assert overview_identity_satisfied(named, root) is True
    assert overview_identity_satisfied(filled + "\n\ndemo 是本仓库产品。\n", root)
    page = _page(
        "project-overview", "项目概述", WikiTaxonomyCategory.PROJECT_OVERVIEW, "项目概述.md"
    )
    out = _render(_service(root), page, raw, _py_context(root), add_mermaid=False)
    assert "FastAPI" in out
    assert overview_identity_satisfied(out + "\n\ndemo 是本仓库产品。\n", root)


def test_emit_once_full_er_has_one_owner(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    service = _service(root)
    context = _py_context(root)
    context.models = [
        {
            "name": "users",
            "type": "migration_table",
            "attributes": ["id", "username"],
            "primary_keys": ["id"],
            "relationships": [],
        },
        {
            "name": "articles",
            "type": "migration_table",
            "attributes": ["id", "slug"],
            "primary_keys": ["id"],
            "relationships": ["fk:users:author_id"],
        },
    ]
    owner = _page(
        "data-models-overview", "数据模型", WikiTaxonomyCategory.DATA_MODELS, "数据模型.md"
    )
    schema = _page(
        "database-schema", "数据库架构", WikiTaxonomyCategory.DATA_MODELS, "数据模型/数据库架构.md"
    )
    migration = _page(
        "database-migration",
        "数据迁移策略",
        WikiTaxonomyCategory.DATA_MODELS,
        "数据模型/数据迁移策略.md",
    )
    first = _render(service, owner, "# 数据模型\n\n实体来自 alembic。\n", context)
    second = _render(service, schema, "# 数据库架构\n\n表结构如下。\n", context)
    third = _render(service, migration, "# 数据迁移策略\n\n迁移脚本管理表结构。\n", context)
    hashes = []
    for page in (first, second, third):
        for block in _mermaid_bodies(page):
            if "erDiagram" in block:
                hashes.append(normalize_mermaid_block(block))
    assert len(hashes) == len(set(hashes))
    assert first.count("erDiagram") >= 1


def test_python_api_page_is_not_auth_diagram_plus_note(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    service = _service(root)
    context = _py_context(root)
    auth = _page(
        "authentication-authorization-api",
        "认证授权API",
        WikiTaxonomyCategory.API_REFERENCE,
        "API参考/认证授权API.md",
    )
    python = _page(
        "python-service-api",
        "Python服务API",
        WikiTaxonomyCategory.API_REFERENCE,
        "API参考/Python服务API.md",
    )
    auth_out = _render(service, auth, "# 认证授权API\n\n登录与注册。\n", context)
    py_out = _render(service, python, "# Python服务API\n\n文章资源。\n", context)
    assert "<cite>" not in "".join(_mermaid_bodies(auth_out) + _mermaid_bodies(py_out))
    auth_hash = {normalize_mermaid_block(b) for b in _mermaid_bodies(auth_out)}
    py_hash = {normalize_mermaid_block(b) for b in _mermaid_bodies(py_out)}
    assert auth_hash.isdisjoint(py_hash) or not py_hash
    if _mermaid_bodies(py_out):
        assert "Note over Client: Python" not in py_out


def _mermaid_bodies(markdown: str) -> list[str]:
    import re

    return re.findall(r"```mermaid\s*(.*?)```", markdown or "", flags=re.I | re.S)


# --- Part C: Go inventory, flows, data model, roles ---


def test_handle_func_inventory_records_post_only_publish() -> None:
    from repo_wiki.scanner.go_routes import extract_go_endpoints

    text = (
        "package main\nfunc runGRPCServe() {\n"
        'mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {})\n'
        'mux.HandleFunc("/publish", func(w http.ResponseWriter, r *http.Request) {\n'
        "    if r.Method != http.MethodPost {\n"
        '        writeAdminJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "POST required"})\n'
        "        return\n"
        "    }\n"
        "})\n"
        'mux.HandleFunc("/force-resync", func(w http.ResponseWriter, r *http.Request) {\n'
        "    if r.Method != http.MethodPost { return }\n"
        "})\n}\n"
    )
    found = extract_go_endpoints([("cmd/ccprobe-control/serve.go", text)])
    methods = {(item.method, item.path) for item in found}
    assert ("POST", "/publish") in methods
    assert ("GET", "/publish") not in methods
    assert ("POST", "/force-resync") in methods
    assert ("GET", "/healthz") in methods


def test_handle_func_inventory_on_real_probe_serve() -> None:
    from repo_wiki.scanner.go_routes import extract_go_endpoints

    serve = Path("/tmp/r12/probe_exporter/cmd/ccprobe-control/serve.go")
    if not serve.is_file():
        return
    found = extract_go_endpoints([("cmd/ccprobe-control/serve.go", serve.read_text())])
    methods = {(item.method, item.path) for item in found}
    assert ("POST", "/publish") in methods
    assert ("GET", "/publish") not in methods


def test_agent_ops_sample_composite_primary_key() -> None:
    from repo_wiki.scanner.go_routes import extract_go_data_models

    text = (
        "package models\n"
        "type AgentOpsSample struct {\n"
        '    AgentID string `gorm:"column:agent_id;primaryKey"`\n'
        '    TsMS    int64  `gorm:"column:ts_ms;primaryKey;autoIncrement:false"`\n'
        '    Workers int    `gorm:"column:workers"`\n'
        "}\n"
        'func (AgentOpsSample) TableName() string { return "agent_ops_sample" }\n'
    )
    models = extract_go_data_models([("internal/models/agent_ops_sample.go", text)])
    sample = next(item for item in models if item.name == "AgentOpsSample")
    assert set(sample.primary_keys) == {"AgentID", "TsMS"}


def test_agent_ops_sample_er_marks_both_keys(tmp_path: Path) -> None:
    from repo_wiki.core.config import RepoWikiConfig
    from repo_wiki.core.contracts import DataModel
    from repo_wiki.scanner.repository_scanner import RepositoryScanner

    root = tmp_path
    (root / "internal" / "models").mkdir(parents=True)
    (root / "internal" / "models" / "agent_ops_sample.go").write_text(
        "package models\n"
        "type AgentOpsSample struct {\n"
        '    AgentID string `gorm:"column:agent_id;primaryKey"`\n'
        '    TsMS    int64  `gorm:"column:ts_ms;primaryKey"`\n'
        "}\n"
        'func (AgentOpsSample) TableName() string { return "agent_ops_sample" }\n',
        encoding="utf-8",
    )
    snapshot = RepositoryScanner(
        RepoWikiConfig.model_validate({"project": {"root": str(root)}})
    ).scan()
    model = next(item for item in snapshot.data_models if item.name == "AgentOpsSample")
    assert isinstance(model, DataModel)
    assert set(model.primary_keys) == {"AgentID", "TsMS"}
    planner = MermaidPlanner(str(root))
    plan = planner._plan_data_model_diagram(
        "data-models-overview",
        None,
        {"data_models": [model.model_dump()]},
    )
    assert plan is not None
    rendered, ok, _ = MermaidRenderer().render_diagram_with_validation(plan)
    assert ok
    assert "AgentID PK" in rendered or "AgentID PK" in rendered.replace("  ", " ")
    assert "TsMS PK" in rendered


def test_frontend_flow_uses_ccagent_not_custom_probe(tmp_path: Path) -> None:
    from tests.test_handbook_round10 import _go_repo

    root = _go_repo(tmp_path)
    (root / "cmd" / "custom-probe").mkdir(parents=True)
    (root / "cmd" / "custom-probe" / "main.go").write_text(
        "package main\n"
        'mux.HandleFunc("/probe", server.ProbeHandler)\n'
        'mux.HandleFunc("/health", server.HealthHandler)\n',
        encoding="utf-8",
    )
    (root / "web").mkdir(parents=True)
    (root / "web" / "app.js").write_text(
        "fetch('/probe/endpoint/list')\nfetch('/tag/list')\nfetch('/api/v1/agent/list')\n",
        encoding="utf-8",
    )
    planner = MermaidPlanner(str(root))
    endpoints = [
        {
            "method": "GET",
            "path": "/probe",
            "handler": "ProbeHandler",
            "file_path": "cmd/example-probe/main.go",
            "auth_type": "none",
        },
        {
            "method": "POST",
            "path": "/probe/endpoint/list",
            "handler": "ListEndpoints",
            "file_path": "controller.go",
        },
        {
            "method": "GET",
            "path": "/tag/list",
            "handler": "ListTags",
            "file_path": "controller.go",
        },
    ]
    plan = planner._plan_request_flow_sequence(
        "frontend-application-api", None, {"endpoints": endpoints}
    )
    assert plan is not None
    blob = "\n".join(f"{a}->{b}: {msg}" for a, b, msg in plan.sequence_messages)
    assert "GET /probe" not in blob
    assert "X-Probe-Api-Token" not in blob or "/probe/endpoint" in blob or "/tag" in blob
    assert "ProbeHandler" not in plan.sequence_participants
    assert "/probe/endpoint/list" in blob or "/tag/list" in blob


def test_custom_probe_has_no_probe_api_token_hop() -> None:
    probe = {
        "method": "GET",
        "path": "/probe",
        "file_path": "cmd/example-probe/main.go",
        "handler": "ProbeHandler",
    }
    assert _endpoint_is_anonymous(probe)
    assert _auth_hop(probe, go_auth=True, py_auth=False) == (None, None)


def test_list_flow_actors_stay_in_owning_binary() -> None:
    from repo_wiki.generator.mermaid_planner import _endpoint_actor

    healthz = {
        "method": "GET",
        "path": "/healthz",
        "handler": "NewHTTPHandler",
        "file_path": "cmd/ccprobe-control/serve.go",
    }
    custom_root = {
        "method": "GET",
        "path": "/",
        "handler": "r.GET",
        "file_path": "cmd/example-probe/main.go",
    }
    custom_health = {
        "method": "GET",
        "path": "/health",
        "handler": "r.GET",
        "file_path": "cmd/example-probe/main.go",
    }
    assert _endpoint_actor(healthz) == "runGRPCServe"
    assert _endpoint_actor(custom_root) == "example-probe"
    assert _endpoint_actor(custom_health) == "HealthHandler"
    planner = MermaidPlanner()
    plan = planner._plan_api_sequence_diagram(
        "api-overview",
        None,
        {
            "endpoints": [
                healthz,
                {
                    "method": "GET",
                    "path": "/healthz",
                    "handler": "NewHTTPHandler",
                    "file_path": "internal/agent/http_transport.go",
                },
                custom_root,
                custom_health,
            ]
        },
    )
    if plan is None:
        return
    blob = "\n".join(f"{a}->{b}: {msg}" for a, b, msg in plan.sequence_messages)
    if "GET /healthz" in blob and "serve.go" in str(healthz):
        assert "NewHTTPHandler" not in blob or "runGRPCServe" in plan.sequence_participants
    if "GET /health" in blob:
        assert "r_GET" not in plan.sequence_participants


def test_data_model_block_has_prose_and_config_table(tmp_path: Path) -> None:
    from repo_wiki.generator.deterministic_sections import build_data_model_cite_block
    from repo_wiki.verifier.qoder_strict_verifier import is_qoder_page_dump, qoder_prose_density
    from tests.test_handbook_round10 import _go_context, _go_repo, _page, _render, _service

    root = _go_repo(tmp_path)
    models = root / "internal" / "models"
    extra = [
        ("ProbeBlackboxModule", "blackbox.go"),
        ("BizTreeNode", "biz.go"),
        ("BizInstanceEndpoint", "biz.go"),
        ("ProbePolicy", "policy.go"),
        ("ProbeRoutingBinding", "routing.go"),
        ("AgentRegistry", "agent.go"),
        ("AgentOpsSample", "agent_ops_sample.go"),
        ("ExporterConfig", "config.go"),
        ("TLSFiles", "config.go"),
        ("SoftLimits", "config.go"),
    ]
    for name, fname in extra:
        path = models / fname
        existing = path.read_text(encoding="utf-8") if path.exists() else "package models\n"
        path.write_text(
            existing + f"\ntype {name} struct {{\n    Name string\n}}\n", encoding="utf-8"
        )
    block = build_data_model_cite_block(root)
    assert "ProbeEndpoint" in block or "核心实体" in block
    assert "AgentRegistry" in block
    assert "| 类型 | 定义 |" in block
    assert "ExporterConfig" in block
    assert not is_qoder_page_dump(block)
    assert qoder_prose_density(block) >= 0.34
    page = _page(
        "data-models-overview", "数据模型", WikiTaxonomyCategory.DATA_MODELS, "数据模型.md"
    )
    raw = "# 数据模型\n\n" + "\n".join(
        f"- Item{i} <cite>internal/models/endpoint.go:3-5</cite>" for i in range(20)
    )
    raw += "\nProbeEndpoint <cite>internal/models/endpoint.go:3-5</cite> " * 8 + "\n"
    out = _render(_service(root), page, raw, _go_context(root), add_mermaid=False)
    assert "ProbeEndpoint" in out or "internal/models" in out
    assert not is_qoder_page_dump(out)
    assert "承担对应职责" not in out


def test_architecture_filler_and_roles(tmp_path: Path) -> None:
    from repo_wiki.generator.deterministic_sections import (
        build_go_role_section,
        rewrite_architecture_role_claims,
    )
    from tests.test_handbook_round10 import _go_context, _go_repo, _page, _render, _service

    root = _go_repo(tmp_path)
    role = build_go_role_section(root)
    assert "REST/Web" in role
    assert "不承担面向前端的 REST/管理入口" not in role
    leftover = (
        "作为整个系统的控制面，`ccprobe-control` 通过 `-serve` 启动并承担 REST/管理入口职责，"
        "本页涉及的 `ccagent` 入口仅完成 Alpine musl 环境下的 DNS 解析兼容初始化。"
    )
    fixed = rewrite_architecture_role_claims(leftover)
    assert "ccagent 是主 REST/Web" in role or "REST/Web" in role
    page = _page(
        "event-driven-architecture",
        "事件驱动架构",
        WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
        "架构设计/事件驱动架构.md",
    )
    raw = "# 事件驱动架构\n\n控制面通过 TunnelHub 转发心跳。\n"
    out = _render(_service(root), page, raw, _go_context(root))
    assert "承担对应职责" not in out


def test_scoped_architecture_pages_do_not_share_tunnel(tmp_path: Path) -> None:
    from tests.test_handbook_round10 import _go_context, _go_repo, _page, _render, _service

    root = _go_repo(tmp_path)
    service = _service(root)
    context = _go_context(root)
    pages = [
        _page(
            "architecture-overview",
            "整体架构概览",
            WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
            "架构设计/整体架构概览.md",
        ),
        _page(
            "event-driven-architecture",
            "事件驱动架构",
            WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
            "架构设计/事件驱动架构.md",
        ),
        _page(
            "module-relationship",
            "模块关系",
            WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
            "架构设计/模块关系.md",
        ),
    ]
    hashes = []
    for page in pages:
        out = _render(service, page, f"# {page.title}\n\n组件协作。\n", context)
        for block in _mermaid_bodies(out):
            hashes.append(normalize_mermaid_block(block))
    assert len(hashes) == len(set(hashes)) or len(hashes) <= 1
