"""Round 13: overview map, cites, cassette, emit-once, hygiene."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo_wiki.evidence.citation_renderer import normalize_citation_markup
from repo_wiki.generator.compose_evidence import (
    invented_compose_edges,
    load_compose_from_root,
    prose_role_contradictions,
)
from repo_wiki.generator.deterministic_sections import rewrite_route_cites_from_endpoints
from repo_wiki.generator.mermaid_planner import MermaidPlanner, MermaidRenderer
from repo_wiki.planner.schema import WikiTaxonomyCategory
from repo_wiki.verifier.handbook import (
    handbook_reader_hygiene_offenders,
    normalize_mermaid_block,
)
from tests.test_handbook_round10 import (
    _fastapi_repo,
    _go_repo,
    _page,
    _py_context,
    _render,
    _service,
)


def _mermaid_bodies(markdown: str) -> list[str]:
    import re

    return re.findall(r"```mermaid\s*(.*?)```", markdown or "", flags=re.I | re.S)


def test_overview_module_map_caps_nodes_and_skips_tests(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    (root / "podman-compose.yml").write_text(
        "services:\n"
        "  ccagent:\n    image: x\n    depends_on: [mysql]\n"
        "  mysql:\n    image: mysql\n",
        encoding="utf-8",
    )
    planner = MermaidPlanner(str(root))
    modules = [
        {"name": "config_security_test.go", "path": "config_security_test.go"},
        {"name": "web_routes_test.go", "path": "web/web_routes_test.go"},
        {"name": "ccagent", "path": "cmd/ccagent/main.go"},
        {"name": "probe-agent", "path": "cmd/probe-agent/main.go"},
        {"name": "ccprobe-control", "path": "cmd/ccprobe-control/main.go"},
        {"name": "services", "path": "internal/services/serv.go"},
        {"name": "control", "path": "internal/control/expand.go"},
        {"name": "repository", "path": "internal/repository/repo.go"},
        {"name": "exporter", "path": "internal/exporter/exporter.go"},
        {"name": "models", "path": "internal/models/endpoint.go"},
        {"name": "agent", "path": "internal/agent/grpc.go"},
        {"name": "probe", "path": "internal/probe/probe.go"},
        {"name": "auth", "path": "internal/auth/auth.go"},
        {"name": "secrets", "path": "internal/secrets/box.go"},
        {"name": "controller.go", "path": "controller.go"},
        {"name": "config.go", "path": "config.go"},
    ]
    edges = [
        ("cmd/ccagent", "internal/services"),
        ("cmd/ccagent", "internal/control"),
        ("internal/services", "internal/repository"),
        ("internal/services", "internal/exporter"),
        ("cmd/probe-agent", "internal/agent"),
        ("cmd/ccprobe-control", "internal/control"),
        ("internal/repository", "internal/models"),
        ("internal/exporter", "internal/probe"),
        ("config_security_test.go", "config.go"),
        ("web_routes_test.go", "web"),
    ]
    plan = planner._plan_overview_module_flow(
        "project-overview",
        None,
        {"modules": modules, "import_edges": edges},
    )
    assert plan is not None
    assert len(plan.nodes) <= 12
    labels = {node.label for node in plan.nodes}
    ids = {node.id for node in plan.nodes}
    assert "config_security_test.go" not in labels
    assert "web_routes_test.go" not in labels
    assert "app" not in ids
    assert "db" not in ids
    assert "ccagent" not in ids
    rendered, ok, _ = MermaidRenderer().render_diagram_with_validation(plan)
    assert ok
    assert "app[" not in rendered
    assert "db[" not in rendered
    _names, allowed = load_compose_from_root(root)
    assert invented_compose_edges(f"```mermaid\n{rendered}\n```", allowed) == []


def test_overview_module_map_avoids_fastapi_compose_ids(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    (root / "docker-compose.yml").write_text(
        "services:\n"
        "  app:\n    image: api\n    depends_on: [db]\n    env_file: [.env]\n"
        "  db:\n    image: postgres\n    env_file: [.env]\n",
        encoding="utf-8",
    )
    planner = MermaidPlanner(str(root))
    plan = planner._plan_overview_module_flow(
        "project-overview",
        None,
        {
            "modules": [
                {"name": "app", "path": "app/main.py"},
                {"name": "api", "path": "app/api/routes/articles.py"},
                {"name": "core", "path": "app/core/settings/__init__.py"},
                {"name": "db", "path": "app/db/queries.py"},
                {"name": "models", "path": "app/models/domain/users.py"},
                {"name": "services", "path": "app/services/articles.py"},
            ],
            "import_edges": [
                ("app/api", "app/models"),
                ("app/api", "app/services"),
                ("app/services", "app/db"),
                ("app/core", "app/db"),
            ],
        },
    )
    assert plan is not None
    assert len(plan.nodes) <= 12
    assert "app" not in {node.id for node in plan.nodes}
    assert "db" not in {node.id for node in plan.nodes}
    rendered, ok, _ = MermaidRenderer().render_diagram_with_validation(plan)
    assert ok
    assert "app[" not in rendered
    assert "db[" not in rendered
    _names, allowed = load_compose_from_root(root)
    blob = f"```mermaid\n{rendered}\n```"
    assert invented_compose_edges(blob, allowed) == []
    page = _page(
        "project-overview", "项目概述", WikiTaxonomyCategory.PROJECT_OVERVIEW, "项目概述.md"
    )
    out = _render(
        _service(root), page, "# 项目概述\n\n这是 FastAPI 示例后端。\n", _py_context(root)
    )
    assert invented_compose_edges(out, allowed) == []


def test_python_api_page_gets_favorite_follow_sequence(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    common = root / "app" / "api" / "routes" / "articles" / "articles_common.py"
    common.parent.mkdir(parents=True, exist_ok=True)
    common.write_text(
        "@router.post('/{slug}/favorite')\n"
        "async def mark_article_as_favorite():\n    return {}\n"
        "@router.delete('/{slug}/favorite')\n"
        "async def remove_article_from_favorites():\n    return {}\n",
        encoding="utf-8",
    )
    (root / "app" / "api" / "routes" / "profiles.py").write_text(
        "@router.post('/{username}/follow')\n"
        "async def follow_for_user():\n    return {}\n"
        "@router.delete('/{username}/follow')\n"
        "async def unsubscribe_from_user():\n    return {}\n",
        encoding="utf-8",
    )
    planner = MermaidPlanner(str(root))
    plan = planner._plan_favorite_follow_sequence("python-service-api", None, {})
    assert plan is not None
    rendered, ok, _ = MermaidRenderer().render_diagram_with_validation(plan)
    assert ok
    assert "remove_article_from_favorites" in rendered
    assert "mark_article_as_favorite" in rendered
    assert "follow_for_user" in rendered
    assert "unsubscribe_from_user" in rendered
    assert "articles_common" not in rendered
    assert "DELETE /api/articles/{slug}/favorite" in rendered
    page = _page(
        "python-service-api",
        "Python服务API",
        WikiTaxonomyCategory.API_REFERENCE,
        "API参考/Python服务API.md",
    )
    out = _render(_service(root), page, "# Python服务API\n\n文章收藏与关注。\n", _py_context(root))
    bodies = _mermaid_bodies(out)
    assert bodies
    blob = "\n".join(bodies)
    assert "remove_article_from_favorites" in blob or "DELETE /api/articles" in blob


def test_rewrite_route_cites_keys_method_and_path(tmp_path: Path) -> None:
    def _write_at(path: Path, line_no: int, method: str, handler: str, route: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        lines = existing.splitlines()
        while len(lines) < line_no + 1:
            lines.append("")
        lines[line_no - 1] = f"@router.{method}('{route}')"
        lines[line_no] = f"async def {handler}():"
        if len(lines) < line_no + 2:
            lines.append("    return {}")
        else:
            lines[line_no + 1] = "    return {}"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    common = tmp_path / "app" / "api" / "routes" / "articles" / "articles_common.py"
    _write_at(common, 47, "post", "mark_article_as_favorite", "/{slug}/favorite")
    _write_at(common, 77, "delete", "remove_article_from_favorites", "/{slug}/favorite")
    profiles = tmp_path / "app" / "api" / "routes" / "profiles.py"
    _write_at(profiles, 27, "post", "follow_for_user", "/{username}/follow")
    _write_at(profiles, 57, "delete", "unsubscribe_from_user", "/{username}/follow")
    auth = tmp_path / "app" / "api" / "routes" / "authentication.py"
    _write_at(auth, 56, "post", "register", "")
    endpoints = [
        {
            "method": "POST",
            "path": "/api/articles/{slug}/favorite",
            "file_path": "app/api/routes/articles/articles_common.py",
            "line_number": 52,
            "handler": "mark_article_as_favorite",
        },
        {
            "method": "DELETE",
            "path": "/api/articles/{slug}/favorite",
            "file_path": "app/api/routes/articles/articles_common.py",
            "line_number": 82,
            "handler": "remove_article_from_favorites",
        },
        {
            "method": "DELETE",
            "path": "/api/profiles/{username}/follow",
            "file_path": "app/api/routes/profiles.py",
            "line_number": 62,
            "handler": "unsubscribe_from_user",
        },
        {
            "method": "POST",
            "path": "/api/users",
            "file_path": "app/api/routes/authentication.py",
            "line_number": 62,
            "handler": "register",
        },
    ]
    raw = (
        "收藏路由：POST /api/articles/{slug}/favorite 与 "
        "DELETE /api/articles/{slug}/favorite 由 `mark_article_as_favorite` 处理"
        "<cite>app/api/routes/articles/articles_common.py:52-55</cite>。\n"
        "DELETE /api/profiles/{username}/follow 取消关注"
        "<cite>app/api/routes/profiles.py:32-35</cite>。\n"
        "未携带凭据访问 POST /api/users 时返回错误"
        "<cite>app/api/routes/articles/articles_common.py:27-31</cite>。\n"
    )
    out = rewrite_route_cites_from_endpoints(raw, endpoints, tmp_path)
    assert "articles_common.py:77" in out
    assert "remove_article_from_favorites" in out
    assert "profiles.py:57" in out
    assert "authentication.py:56" in out


def test_host_port_backticks_are_not_turned_into_cites() -> None:
    text = "绑定 `127.0.0.1:3306` 与 `0.0.0.0:8200`，再看 `internal/models/endpoint.go:12`。"
    out = normalize_citation_markup(text)
    assert "`127.0.0.1:3306`" in out
    assert "`0.0.0.0:8200`" in out
    assert "<cite>127.0.0.1:3306</cite>" not in out
    assert "<cite>0.0.0.0:8200</cite>" not in out
    assert "<cite>internal/models/endpoint.go:12</cite>" in out


def test_role_regex_accepts_25m_probe_agent_after_tunnel_client() -> None:
    s1 = (
        "管理面由 `ccagent` 主进程承担，并非由 `ccprobe-control` 承担，"
        "边缘隧道客户端的角色则交由 `probe-agent` 负责。"
    )
    s2 = (
        "本页面以 `cmd/ccagent`、`cmd/ccprobe-control`、`cmd/probe-agent` 三大入口为切入点，"
        "明确了管理面与控制面的边界：主 REST/Web 管理入口是 `ccagent`，"
        "控制面 gRPC/HTTP 双通道由 `ccprobe-control` 承担，隧道客户端由 `probe-agent` 承载。"
    )
    assert prose_role_contradictions(s1) == []
    assert prose_role_contradictions(s2) == []
    still_wrong = "后续 ccagent 作为隧道客户端连向 ccprobe-control。"
    assert "ccagent-as-tunnel-client" in prose_role_contradictions(still_wrong)


def test_hygiene_flags_instruction_voice_and_evidence_meta(tmp_path: Path) -> None:
    content = tmp_path / "zh" / "content"
    content.mkdir(parents=True)
    (content / "数据模型.md").write_text(
        "# 数据模型\n\n主键写成 TsMS（不要只标 `TsMS`）。\n",
        encoding="utf-8",
    )
    (content / "测试指南.md").write_text(
        "# 测试指南\n\n如果证据不足，不要在此凭空扩展测试矩阵。\n",
        encoding="utf-8",
    )
    (content / "架构.md").write_text(
        "# 架构\n\n当前证据只覆盖控制面，证据片段不足以推断导出器。提供的证据见下。\n",
        encoding="utf-8",
    )
    offenders = handbook_reader_hygiene_offenders(content, tmp_path)
    assert offenders.get("instruction_voice")
    assert offenders.get("evidence_meta_talk")


def test_prompts_do_not_contain_quotable_instruction_voice() -> None:
    from repo_wiki.generator import composer

    text = Path(composer.__file__).read_text(encoding="utf-8")
    assert "不要只标" not in text
    assert "不要在此凭空扩展" not in text
    assert "如果证据不足，省略该事实，不要用套话填空" not in text


def test_emit_once_ownership_follows_page_order_not_completion(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    service = _service(root)
    context = _py_context(root)
    first = _page("aaa-early-page", "认证授权API", WikiTaxonomyCategory.API_REFERENCE, "a.md")
    second = _page("zzz-late-page", "Python服务API", WikiTaxonomyCategory.API_REFERENCE, "z.md")
    raw_a = _render(service, first, "# 认证授权API\n\n登录。\n", context, add_mermaid=True)
    service._seen_mermaid_hashes.clear()
    raw_z = _render(service, second, "# Python服务API\n\n文章。\n", context, add_mermaid=True)
    # Simulate completion order z then a, then finalize by page_id/page order.
    page_results = {1: (second.output_path, raw_z), 0: (first.output_path, raw_a)}
    service._seen_mermaid_hashes.clear()
    service._inject_planner_mermaid_in_page_order([first, second], page_results, {}, context)
    ordered = [page_results[idx][1] for idx in sorted(page_results)]
    hashes: list[str] = []
    for markdown in ordered:
        for block in _mermaid_bodies(markdown):
            hashes.append(normalize_mermaid_block(block))
    assert len(hashes) == len(set(hashes))


def test_data_model_pages_keep_required_er_after_emit_once(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    versions = root / "app" / "db" / "migrations" / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    (versions / "fdf8821871d7_main_tables.py").write_text(
        'op.create_table("users", sa.Column("id", sa.Integer, primary_key=True))\n'
        'op.create_table("articles", sa.Column("id", sa.Integer, primary_key=True), '
        'sa.Column("author_id", sa.Integer, sa.ForeignKey("users.id")))\n',
        encoding="utf-8",
    )
    service = _service(root)
    context = _py_context(root)
    owner = _page(
        "data-models-overview", "数据模型", WikiTaxonomyCategory.DATA_MODELS, "数据模型.md"
    )
    satellite = _page(
        "database-migration-strategy",
        "数据迁移策略",
        WikiTaxonomyCategory.DATA_MODELS,
        "数据迁移策略.md",
    )
    raw_owner = "# 数据模型\n\nusers 与 articles 有 author_id 外键关系。\n"
    raw_sat = "# 数据迁移策略\n\nAlembic 迁移建立 users 与 articles 的关联。\n"
    page_results = {0: (owner.output_path, raw_owner), 1: (satellite.output_path, raw_sat)}
    service._inject_planner_mermaid_in_page_order([owner, satellite], page_results, {}, context)
    assert any("erDiagram" in block for block in _mermaid_bodies(page_results[0][1]))
    assert any("erDiagram" in block for block in _mermaid_bodies(page_results[1][1]))


def test_database_schema_er_includes_author_id_and_differs(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    versions = root / "app" / "db" / "migrations" / "versions"
    (versions / "fdf8821871d7_main_tables.py").write_text(
        'op.create_table("users", sa.Column("id", sa.Integer, primary_key=True))\n'
        "op.create_table(\n"
        '    "articles",\n'
        '    sa.Column("id", sa.Integer, primary_key=True),\n'
        '    sa.Column("slug", sa.Text, unique=True, index=True),\n'
        '    sa.Column("author_id", sa.Integer, sa.ForeignKey("users.id")),\n'
        ")\n"
        'op.create_table("favorites", sa.Column("user_id", sa.Integer, '
        'sa.ForeignKey("users.id")), sa.Column("article_id", sa.Integer, '
        'sa.ForeignKey("articles.id")))\n',
        encoding="utf-8",
    )
    planner = MermaidPlanner(str(root))
    models = [
        {
            "name": "users",
            "type": "migration_table",
            "attributes": ["id"],
            "primary_keys": ["id"],
            "relationships": [],
        },
        {
            "name": "articles",
            "type": "migration_table",
            "attributes": ["id", "slug", "author_id"],
            "primary_keys": ["id"],
            "relationships": ["belongs_to:users:author_id"],
        },
        {
            "name": "favorites",
            "type": "migration_table",
            "attributes": ["user_id", "article_id"],
            "primary_keys": ["user_id", "article_id"],
            "relationships": ["belongs_to:users:user_id", "belongs_to:articles:article_id"],
        },
    ]
    data = planner._plan_data_model_diagram("data-models-overview", None, {"data_models": models})
    schema = planner._plan_database_schema_diagram("database-schema", None, {"data_models": models})
    assert schema is not None
    data_txt, ok1, _ = MermaidRenderer().render_diagram_with_validation(data)
    schema_txt, ok2, _ = MermaidRenderer().render_diagram_with_validation(schema)
    assert ok1 and ok2
    assert "author_id" in schema_txt
    assert "users" in schema_txt and "articles" in schema_txt
    assert "favorites" not in schema_txt
    assert "followers_to_followings" not in schema_txt
    assert normalize_mermaid_block(data_txt) != normalize_mermaid_block(schema_txt)
    planned = planner.plan_diagram_for_page(
        "database-architecture",
        "data",
        None,
        {"data_models": models},
    )
    planned_txt = "\n".join(
        MermaidRenderer().render_diagram_with_validation(item)[0] or "" for item in planned
    )
    assert "author_id" in planned_txt
    assert "favorites" not in planned_txt
    assert "followers_to_followings" not in planned_txt


@pytest.mark.asyncio
async def test_cassette_mismatch_prefers_same_attempt(tmp_path: Path) -> None:
    from repo_wiki.llm.cassette import CassetteLLMProvider, set_cassette_call_context
    from repo_wiki.llm.models import ChatMessage, ChatRequest

    rows = [
        {
            "page_id": "overview",
            "attempt": 0,
            "prompt_hash": "old-0",
            "raw_reply": "attempt-zero",
            "model": "cassette-model",
        },
        {
            "page_id": "overview",
            "attempt": 1,
            "prompt_hash": "old-1",
            "raw_reply": "attempt-one",
            "model": "cassette-model",
        },
    ]
    (tmp_path / "llm-cassette.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    provider = CassetteLLMProvider.from_dir(tmp_path)
    set_cassette_call_context(page_id="overview", attempt=0, prompt_hash="new-hash")
    response = await provider.chat(
        ChatRequest(messages=[ChatMessage(role="user", content="x")], model="cassette-model")
    )
    assert response.content == "attempt-zero"


def test_cassette_replay_does_not_append_to_source_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from repo_wiki.llm.cassette import record_cassette_attempt

    source = tmp_path / "handbook-2026-09-25m.jsonl"
    source.write_text(
        json.dumps({"page_id": "overview", "attempt": 0, "raw_reply": "kept"}) + "\n",
        encoding="utf-8",
    )
    before = source.read_text(encoding="utf-8")
    monkeypatch.setenv("LLM_PROVIDER", "cassette")
    monkeypatch.setenv("REPO_WIKI_LLM_CASSETTE_DIR", str(tmp_path))
    monkeypatch.delenv("REPO_WIKI_LLM_CASSETTE_WRITE_DIR", raising=False)
    record_cassette_attempt(
        page_id="other",
        attempt=0,
        input_hash="i",
        prompt_hash="p",
        generator_version="handbook-r13-20260925",
        model="cassette",
        messages=[{"role": "user", "content": "x"}],
        raw_reply="should-not-land",
    )
    assert source.read_text(encoding="utf-8") == before
    extras = [path for path in tmp_path.glob("*.jsonl") if path != source]
    assert extras == []
