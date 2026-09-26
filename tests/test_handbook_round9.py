"""Round 9: emit-once, request-flow, roles, product name, registration cites."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.generator.compose_evidence import (
    derive_product_name,
    is_placeholder_ops_diagram,
    prose_role_contradictions,
)
from repo_wiki.generator.deterministic_sections import (
    apply_deterministic_rewrites,
    extract_alembic_tables,
    is_header_only_cite,
    page_has_meta_instruction,
    strip_invented_join_id_pk,
    strip_reader_unresolved_markers,
)
from repo_wiki.generator.mermaid_planner import MermaidPlanner, MermaidRenderer
from repo_wiki.scanner.go_routes import extract_go_endpoints
from repo_wiki.scanner.repository_scanner import RepositoryScanner
from repo_wiki.verifier.handbook import handbook_reader_hygiene_offenders
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeSeverityThreshold


def test_hygiene_floor_is_four_pages(tmp_path: Path) -> None:
    block = (
        "按资源分组的接口：GET /api/articles 列出文章，GET /api/articles/{slug} 读取单篇，"
        "这是超过八十字的确定性目录正文，用来验证卫生门槛不得抄到卫星页。"
    )
    assert len(block) >= 80
    content = tmp_path / "content"
    content.mkdir()
    for name in ("a.md", "b.md"):
        (content / name).write_text(f"# {name}\n\n{block}\n", encoding="utf-8")
    assert not handbook_reader_hygiene_offenders(content, None).get("repeated_paragraphs")
    for name in ("c.md", "d.md"):
        (content / name).write_text(f"# {name}\n\n{block}\n", encoding="utf-8")
    names = {
        Path(path).name
        for path in handbook_reader_hygiene_offenders(content, None)["repeated_paragraphs"]
    }
    assert names == {"a.md", "b.md", "c.md", "d.md"}


def test_meta_instruction_ignores_operational_compose_advice() -> None:
    line = (
        "**HA compose 与基础 compose 不要混用**：使用普通 `podman-compose up -d` 时"
        "不要把这些文件当作默认入口。Custom Probe 的源码入口为 `cmd/custom-probe/main.go`。"
    )
    assert page_has_meta_instruction(line) is False


def test_alembic_parses_create_primary_key_and_timestamps() -> None:
    sample = """
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
"""
    tables = extract_alembic_tables(sample)
    by_name = {str(item["name"]): item for item in tables}
    assert "created_at" in by_name["users"]["attributes"]
    assert "updated_at" in by_name["users"]["attributes"]
    assert set(by_name["followers_to_followings"]["primary_keys"]) == {
        "follower_id",
        "following_id",
    }
    assert by_name["followers_to_followings"]["primary_key"] == ""


def test_join_key_diagram_does_not_invent_id_pk() -> None:
    planner = MermaidPlanner()
    plan = planner._plan_join_key_diagram(
        "database-schema",
        None,
        {
            "data_models": [
                {
                    "name": "followers_to_followings",
                    "type": "migration_table",
                    "attributes": ["follower_id", "following_id"],
                    "primary_key": "",
                    "primary_keys": ["follower_id", "following_id"],
                }
            ]
        },
    )
    assert plan is not None
    rendered = MermaidRenderer().render_diagram(plan)
    assert "follower_id PK" in rendered
    assert "following_id PK" in rendered
    assert "string id PK" not in rendered
    cleaned = strip_invented_join_id_pk(
        "```mermaid\nerDiagram\n    followers_to_followings {\n"
        "        int follower_id PK\n        string id PK\n    }\n```"
    )
    assert "string id PK" not in cleaned


def test_auth_flow_falls_back_to_request_sequence(tmp_path: Path) -> None:
    (tmp_path / "apiauth.go").write_text(
        'package ccagent\nconst EnvAPIToken = "PROBE_API_TOKEN"\n', encoding="utf-8"
    )
    planner = MermaidPlanner(str(tmp_path))
    plan = planner._plan_auth_flow_diagram(
        "authentication-authorization-api",
        None,
        {
            "modules": [],
            "import_edges": [],
            "endpoints": [{"method": "GET", "path": "/health", "handler": "Mount"}],
        },
    )
    assert plan is not None
    assert plan.sequence_messages


def test_ops_planner_skips_generic_command_chain(tmp_path: Path) -> None:
    planner = MermaidPlanner(str(tmp_path))
    plan = planner._plan_ops_diagram(
        "ops",
        None,
        {"commands": {"start": "python -m app", "test": "pytest -q", "lint": "ruff check ."}},
    )
    assert plan is None
    assert is_placeholder_ops_diagram(
        "```mermaid\nflowchart TD\n    start((Start))\n    cmd_build[build]\n"
        "    cmd_test[test]\n    cmd_lint[lint]\n    start --> cmd_build\n"
        "    cmd_build --> cmd_test\n    cmd_test --> cmd_lint\n```\n"
    )


def test_product_name_from_readme_not_directory(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# probe_exporter\n\nhello\n", encoding="utf-8")
    clone = tmp_path / "probe_exporter-eval"
    clone.mkdir()
    (clone / "README.md").write_text("# probe_exporter\n\nhello\n", encoding="utf-8")
    assert derive_product_name(clone) == "probe_exporter"
    out = apply_deterministic_rewrites(
        "probe_exporter-eval 是面向企业级的服务探针拨测与结果导出平台。",
        clone,
        title="项目概述",
        page_id="project-overview",
    )
    assert "probe_exporter-eval" not in out
    assert "probe_exporter" in out


def test_role_contradictions_and_rewrite(tmp_path: Path) -> None:
    from tests.test_handbook_round15 import _write_role_repo

    _write_role_repo(tmp_path)
    example = tmp_path / "cmd" / "custom-probe"
    example.mkdir(parents=True)
    (example / "README.md").write_text("# 示例工具\n", encoding="utf-8")
    (example / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")
    text = (
        "`cmd/ccagent`（探针 Agent，作为隧道客户端连接到控制面）\n"
        "ccagent 通过 `-agent-url`/`-agent-token` 与 `ccprobe-control` 建立反向控制链路。\n"
        "custom-probe 作为外部进程被拉起以返回 JSON 探针结果。\n"
    )
    assert prose_role_contradictions(text, tmp_path)
    out = apply_deterministic_rewrites(
        text, tmp_path, title="整体架构概览", category="架构设计", page_id="architecture-overview"
    )
    assert "隧道客户端连接到控制面" not in out
    assert "建立反向控制链路" not in out
    assert not prose_role_contradictions(out)


def test_unresolved_markers_are_stripped() -> None:
    text = "说明\n\nUNRESOLVED_API_FLOW：缺少可验证调用链证据，不生成占位流程图。\n"
    assert "UNRESOLVED_API" not in strip_reader_unresolved_markers(text)


def test_markdown_header_cite_is_always_header_only(tmp_path: Path) -> None:
    (tmp_path / "CONTRIBUTING.md").write_text(
        "# Contributing\n\n## 构建\n\ngo build -o bin/ccagent cmd/ccagent/main.go\n",
        encoding="utf-8",
    )
    assert is_header_only_cite("<cite>CONTRIBUTING.md:1-6</cite>", tmp_path)


def test_handle_func_keeps_registration_line() -> None:
    text = (
        "package agent\n"
        "func (t *Transport) Mount(mux *http.ServeMux) {\n"
        '    mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {})\n'
        "}\n"
    )
    found = extract_go_endpoints([("internal/agent/http_transport.go", text)])
    assert found
    assert found[0].lineno == 3
    scanner = RepositoryScanner.__new__(RepositoryScanner)
    assert scanner._line_is_route_registration(text, 3)


def test_probe_agent_tunnel_sentence_is_not_a_role_conflict() -> None:
    text = (
        "分别是主 REST/Web 服务 `cmd/ccagent`、探针隧道客户端 `cmd/probe-agent` "
        "和控制面 `cmd/ccprobe-control`。"
    )
    assert prose_role_contradictions(text) == []


def test_role_consistency_is_hard() -> None:
    assert "QODER_HANDBOOK_ROLE_CONSISTENCY" in QoderLikeSeverityThreshold.STRICT_HARD_CODES
