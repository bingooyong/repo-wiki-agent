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
    assert overview_identity_satisfied(filled, root)
    page = _page(
        "project-overview", "项目概述", WikiTaxonomyCategory.PROJECT_OVERVIEW, "项目概述.md"
    )
    out = _render(_service(root), page, raw, _py_context(root), add_mermaid=False)
    assert "FastAPI" in out
    assert overview_identity_satisfied(out, root)


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
