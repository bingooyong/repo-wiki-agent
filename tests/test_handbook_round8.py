"""Round 8: owner-only sections, real compose edges, path completeness."""

from __future__ import annotations

import re
from pathlib import Path

from repo_wiki.generator.compose_evidence import (
    install_path_gaps,
    invented_compose_edges,
    is_placeholder_ops_diagram,
    jwt_token_prefix,
    parse_compose_topology,
    prose_import_contradictions,
)
from repo_wiki.generator.deterministic_sections import (
    apply_deterministic_rewrites,
    extract_alembic_tables,
    go_struct_cite,
    go_struct_end_line,
)
from repo_wiki.generator.mermaid_planner import MermaidPlanner, MermaidRenderer
from repo_wiki.scanner.go_routes import extract_go_endpoints
from repo_wiki.verifier.handbook import handbook_reader_hygiene_offenders
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeSeverityThreshold

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "handbook_replay"
_PROBE_25H = Path("/tmp/probe-25h/probe-handbook-2026-09-25h/repowiki/zh/content")
_FASTAPI_25H = Path("/tmp/fastapi-25h/handbook-2026-09-25h/repowiki/zh/content")

_COMPOSE_MAPPING = """
services:
  mysql:
    image: mysql
  blackbox-exporter:
    image: prom/blackbox-exporter
  ccagent:
    image: ccagent
    depends_on:
      mysql:
        condition: service_healthy
      blackbox-exporter:
        condition: service_started
networks:
  probe-network:
volumes:
  mysql-data:
  ccagent-logs:
"""


def _go_root(tmp_path: Path) -> Path:
    (tmp_path / "cmd" / "ccagent").mkdir(parents=True)
    (tmp_path / "cmd" / "probe-agent").mkdir(parents=True)
    (tmp_path / "cmd" / "ccprobe-control").mkdir(parents=True)
    (tmp_path / "internal" / "models").mkdir(parents=True)
    (tmp_path / "internal" / "services").mkdir(parents=True)
    (tmp_path / "internal" / "control").mkdir(parents=True)
    (tmp_path / "internal" / "agent").mkdir(parents=True)
    (tmp_path / "db" / "migrations").mkdir(parents=True)
    (tmp_path / "cmd" / "ccagent" / "main.go").write_text(
        'package main\nfunc main() { http.ListenAndServe(":1900", mux) }\n',
        encoding="utf-8",
    )
    (tmp_path / "cmd" / "probe-agent" / "main.go").write_text(
        "package main\nfunc main() { dialTunnel() }\n",
        encoding="utf-8",
    )
    (tmp_path / "cmd" / "ccprobe-control" / "main.go").write_text(
        'package main\nfunc main() { runServe("-serve", "-transport", "grpc") }\n',
        encoding="utf-8",
    )
    (tmp_path / "cmd" / "ccprobe-control" / "serve.go").write_text(
        "package main\nfunc runGRPCServe() { lis.Listen() }\n",
        encoding="utf-8",
    )
    (tmp_path / "internal" / "models" / "endpoint.go").write_text(
        "package models\n\ntype ProbeEndpoint struct {\n    ID int64\n    Name string\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "internal" / "models" / "result.go").write_text(
        "package models\n\ntype ProbeResult struct {\n    ID int64\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "internal" / "models" / "tag.go").write_text(
        "package models\n\ntype ProbeTag struct {\n    ID int64\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "internal" / "models" / "secret.go").write_text(
        "package models\n\ntype ProbeSecret struct {\n    ID int64\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "internal" / "control" / "hub.go").write_text("package control\n", encoding="utf-8")
    (tmp_path / "internal" / "services" / "svc.go").write_text(
        'package services\nimport "x/internal/control"\n',
        encoding="utf-8",
    )
    (tmp_path / "cmd" / "ccagent" / "wire.go").write_text(
        'package main\nimport "x/internal/services"\n',
        encoding="utf-8",
    )
    (tmp_path / "cmd" / "probe-agent" / "wire.go").write_text(
        'package main\nimport "x/internal/agent"\n',
        encoding="utf-8",
    )
    (tmp_path / "db" / "schema.sql").write_text("SELECT 1;\n", encoding="utf-8")
    (tmp_path / "db" / "migrations" / "001_init.sql").write_text(
        "CREATE TABLE t(id int);\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text(
        "# demo\n\n"
        "podman-compose up -d\n"
        "schema.sql\n"
        "podman exec mysql-db mysql < db/schema.sql\n"
        "podman run --name mysql-db -d \\\n"
        "  -e MYSQL_ROOT_PASSWORD=rootpassword \\\n"
        "  -e MYSQL_DATABASE=probe_exporter \\\n"
        "  -p 3306:3306 mysql:8.0\n"
        "podman run --name blackbox-exporter -d -p 9115:9115 prom/blackbox-exporter\n"
        "podman exec mysql-db mysql < db/schema.sql\n"
        "go build -o bin/ccagent ./cmd/ccagent\n"
        "./bin/ccagent\n"
        "curl http://localhost:1900/health\n",
        encoding="utf-8",
    )
    (tmp_path / "podman-compose.yml").write_text(_COMPOSE_MAPPING, encoding="utf-8")
    return tmp_path


def test_25h_hygiene_catches_repeated_deterministic_blocks(tmp_path: Path) -> None:
    """Same 进程角色 dump on ≥4 pages trips the hygiene gate (25h CI-repro)."""
    block = (
        "## 进程角色\n\n"
        "ccagent 是主 REST/Web 服务；probe-agent 是隧道客户端；"
        "ccprobe-control 是 gRPC 控制面服务。这是 25h 插到全部架构页上的"
        "同一段确定性正文，长度必须超过卫生检查的 80 字门槛。\n"
    )
    content = tmp_path / "content"
    content.mkdir()
    for name in ("overview.md", "components.md", "modules.md", "events.md"):
        (content / name).write_text(f"# {name}\n\n{block}\n", encoding="utf-8")
    offenders = handbook_reader_hygiene_offenders(content, None)
    assert offenders.get("repeated_paragraphs")
    fixture_hits = handbook_reader_hygiene_offenders(_FIXTURES / "probe-25h", None)
    assert fixture_hits.get("meta_instructions")
    fixture_repeated = {Path(path).name for path in (fixture_hits.get("repeated_paragraphs") or [])}
    assert "api.md" in fixture_repeated
    assert "auth-api.md" in fixture_repeated


def test_hygiene_flags_owner_block_copied_to_one_satellite(tmp_path: Path) -> None:
    content = tmp_path / "content"
    content.mkdir()
    block = (
        "按资源分组的接口：GET /api/articles 列出文章，"
        "GET /api/articles/{slug} 读取单篇，这是产品路由目录中的真实接口说明，不得抄到卫星页。"
    )
    assert len(block) >= 80
    (content / "api.md").write_text(f"# API参考\n\n{block}\n", encoding="utf-8")
    (content / "auth-api.md").write_text(f"# 认证授权API\n\n{block}\n", encoding="utf-8")
    (content / "install.md").write_text("# 安装指南\n\n独立安装说明，没有重复目录。\n", encoding="utf-8")
    offenders = handbook_reader_hygiene_offenders(content, None)
    names = {Path(path).name for path in (offenders.get("repeated_paragraphs") or [])}
    assert names == {"api.md", "auth-api.md"}


def test_25h_dry_verify_catches_invented_compose_and_placeholder() -> None:
    overview = (
        (_PROBE_25H / "项目概述" / "项目概述.md")
        if (_PROBE_25H / "项目概述" / "项目概述.md").is_file()
        else None
    )
    text = (
        overview.read_text(encoding="utf-8")
        if overview
        else """```mermaid
flowchart TD
    ccagent[ccagent]
    probe_network[probe-network]
    mysql_data[mysql-data]
    ccagent --> probe_network
    probe_network --> mysql_data
```
"""
    )
    names, edges = parse_compose_topology(_COMPOSE_MAPPING)
    assert "probe-network" not in names
    assert "mysql-data" not in names
    assert ("ccagent", "mysql") in edges
    assert ("ccagent", "blackbox-exporter") in edges
    invented = invented_compose_edges(text, edges)
    assert invented
    deploy = (
        (_FASTAPI_25H / "部署运维.md").read_text(encoding="utf-8")
        if (_FASTAPI_25H / "部署运维.md").is_file()
        else "```mermaid\nflowchart TD\n    start((Start))\n    cmd_start[start]\n"
        "    cmd_build[build]\n    cmd_test[test]\n    cmd_lint[lint]\n"
        "    start --> cmd_start\n    cmd_start --> cmd_build\n"
        "    cmd_build --> cmd_test\n    cmd_test --> cmd_lint\n```\n"
    )
    assert is_placeholder_ops_diagram(deploy)


def test_25h_install_path_b_is_incomplete() -> None:
    raw = (_FIXTURES / "probe-25h" / "install.md").read_text(encoding="utf-8")
    assert any("mysql-db" in gap for gap in install_path_gaps(raw))
    fa = (_FIXTURES / "fastapi-25h" / "install.md").read_text(encoding="utf-8")
    assert "：" in fa


def test_25h_architecture_prose_contradicts_imports() -> None:
    raw = (_FIXTURES / "probe-25h" / "architecture.md").read_text(encoding="utf-8")
    edges = {("internal/services", "internal/control")}
    found = prose_import_contradictions(raw, edges)
    assert any(item.startswith("internal/control->") for item in found)


def test_compose_parser_no_zip_fallback() -> None:
    names, edges = parse_compose_topology(
        "services:\n  a:\n    image: x\n  b:\n    image: y\nnetworks:\n  n:\n"
    )
    assert names == ["a", "b"]
    assert edges == []
    planner = MermaidPlanner("/tmp")
    plan = planner._plan_compose_topology("overview", None, {})
    # workspace without compose file
    assert plan is None or plan.edges


def test_compose_planner_uses_mapping_depends(tmp_path: Path) -> None:
    root = _go_root(tmp_path)
    planner = MermaidPlanner(str(root))
    plan = planner._plan_compose_topology("overview", None, {})
    assert plan is not None
    labels = {node.label for node in plan.nodes}
    assert "probe-network" not in labels
    assert "mysql-data" not in labels
    edge_labels = {(src, dest) for src, dest in [(e.from_node, e.to_node) for e in plan.edges]}
    assert edge_labels
    text = Path(__file__).resolve().parents[1].joinpath("repo_wiki/generator/mermaid_planner.py")
    src = text.read_text(encoding="utf-8")
    assert "zip(ordered" not in src


def test_ops_placeholder_skipped_when_commands_empty(tmp_path: Path) -> None:
    planner = MermaidPlanner(str(tmp_path))
    plan = planner._plan_ops_diagram(
        "ops", None, {"commands": {"start": "", "build": "", "test": "", "lint": ""}}
    )
    assert plan is None


def test_replay_probe_25h_install_path_b_starts_db(tmp_path: Path) -> None:
    root = _go_root(tmp_path)
    raw = (_FIXTURES / "probe-25h" / "install.md").read_text(encoding="utf-8")
    out = apply_deterministic_rewrites(raw, root, title="安装与配置", page_id="installation")
    section = out.split("### 路径 B", 1)[1].split("## ", 1)[0]
    assert "podman run" in section
    assert "mysql-db" in section
    assert "MYSQL_ROOT_PASSWORD" in section or "-p 3306" in section
    assert install_path_gaps(out) == []
    assert "## 进程角色" not in out


def test_replay_security_replaces_cite_dump(tmp_path: Path) -> None:
    root = _go_root(tmp_path)
    (root / "apiauth.go").write_text(
        "package ccagent\n\nfunc TokensEqual(got, want string) bool { return got == want }\n",
        encoding="utf-8",
    )
    (root / "internal" / "auth").mkdir(parents=True, exist_ok=True)
    (root / "internal" / "auth" / "api_gateway_aksk_auth.go").write_text(
        "package auth\n\ntype AKSK struct{}\n", encoding="utf-8"
    )
    raw = (_FIXTURES / "probe-25h" / "security.md").read_text(encoding="utf-8")
    out = apply_deterministic_rewrites(raw, root, title="安全合规", page_id="security-overview")
    assert "安全实现见" not in out
    assert "AK/SK" in out or "internal/auth" in out


def test_replay_owner_only_role_and_routes(tmp_path: Path) -> None:
    root = _go_root(tmp_path)
    raw = (_FIXTURES / "probe-25h" / "architecture.md").read_text(encoding="utf-8")
    owner = apply_deterministic_rewrites(
        raw, root, title="整体架构概览", category="架构设计", page_id="architecture-overview"
    )
    other = apply_deterministic_rewrites(
        raw, root, title="系统组件", category="架构设计", page_id="system-components"
    )
    assert owner.count("## 进程角色") == 1
    assert "ListenAndServe" in owner or "cmd/ccagent/main.go" in owner
    assert "## 进程角色" not in other
    assert "整体架构概览" in other
    assert "边缘 Agent" not in owner or "ccagent 是主 REST" in owner
    assert "internal/control 依赖" not in owner
    assert "internal/control->internal/services" not in prose_import_contradictions(
        owner, {("internal/services", "internal/control")}
    )


def test_replay_fastapi_25h_compose_creates_env(tmp_path: Path) -> None:
    versions = tmp_path / "app" / "db" / "migrations" / "versions"
    versions.mkdir(parents=True)
    (tmp_path / "app" / "main.py").write_text("app = None\n", encoding="utf-8")
    (tmp_path / "app" / "core" / "settings").mkdir(parents=True)
    (tmp_path / "app" / "core" / "settings" / "app.py").write_text(
        'jwt_token_prefix = "Token"\n', encoding="utf-8"
    )
    (tmp_path / "app" / "models" / "domain").mkdir(parents=True)
    (tmp_path / "app" / "models" / "domain" / "user.py").write_text("class User:\n    pass\n")
    (versions / "fdf8821871d7_main_tables.py").write_text(
        Path(
            "/tmp/fastapi-src-25g/fastapi-realworld-example-app/app/db/migrations/versions/"
            "fdf8821871d7_main_tables.py"
        ).read_text(encoding="utf-8")
        if Path(
            "/tmp/fastapi-src-25g/fastapi-realworld-example-app/app/db/migrations/versions/"
            "fdf8821871d7_main_tables.py"
        ).is_file()
        else (
            'op.create_table("users", sa.Column("id", sa.Integer, primary_key=True))\n'
            'op.create_table("followers_to_followings",\n'
            ' sa.Column("follower_id", sa.Integer, sa.ForeignKey("users.id")),\n'
            ' sa.Column("following_id", sa.Integer, sa.ForeignKey("users.id")),\n'
            ' sa.PrimaryKeyConstraint("follower_id", "following_id"))\n'
        ),
        encoding="utf-8",
    )
    (tmp_path / "README.rst").write_text(
        "APP_ENV=dev\nSECRET_KEY=x\nDATABASE_URL=postgresql://x\n"
        "poetry install\nalembic upgrade head\nuvicorn app.main:app --reload\n"
        "docker-compose up -d db\ndocker-compose up -d app\n",
        encoding="utf-8",
    )
    raw = (_FIXTURES / "fastapi-25h" / "install.md").read_text(encoding="utf-8")
    out = apply_deterministic_rewrites(raw, tmp_path, title="安装与配置", page_id="installation")
    path_b = out.split("### 路径 B", 1)[1].split("## ", 1)[0]
    assert ".env" in path_b.split("docker-compose", 1)[0]
    verify = out.split("## 启动与验证", 1)[1].split("## ", 1)[0]
    assert not re.search(r"：\s*$", verify, re.M)
    assert jwt_token_prefix(tmp_path) == "Token"


def test_alembic_keeps_ninth_fk_and_real_pks() -> None:
    sample = """
op.create_table(
    "users",
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("username", sa.Text),
)
op.create_table(
    "followers_to_followings",
    sa.Column("follower_id", sa.Integer, sa.ForeignKey("users.id")),
    sa.Column("following_id", sa.Integer, sa.ForeignKey("users.id")),
    sa.PrimaryKeyConstraint("follower_id", "following_id"),
)
op.create_table(
    "tags",
    sa.Column("tag", sa.Text, primary_key=True),
)
"""
    tables = extract_alembic_tables(sample)
    by_name = {str(item["name"]): item for item in tables}
    fks = [rel for item in tables for rel in item["relationships"]]
    assert len(fks) >= 2
    assert any("following_id" in str(rel) for rel in fks)
    assert by_name["tags"]["primary_key"] == "tag"
    assert "id" not in (by_name["followers_to_followings"].get("primary_keys") or [])
    types = by_name["users"].get("attribute_types") or []
    assert any("int" in str(item).lower() for item in types)


def test_go_struct_cite_is_exact_brace_range(tmp_path: Path) -> None:
    root = _go_root(tmp_path)
    lines = (root / "internal" / "models" / "endpoint.go").read_text(encoding="utf-8").splitlines()
    end = go_struct_end_line(lines, 3)
    cite = go_struct_cite(root, "ProbeEndpoint")
    assert cite == f"<cite>internal/models/endpoint.go:3-{end}</cite>"
    assert end == 6


def test_sequence_renderer_does_not_bounce_to_client() -> None:
    from repo_wiki.generator.mermaid_planner import DiagramPlan, MermaidDiagramType

    plan = DiagramPlan(
        diagram_id="x",
        diagram_type=MermaidDiagramType.SEQUENCE_DIAGRAM,
        title="t",
        description="d",
        sequence_participants=["Client", "Handler", "Service"],
        sequence_messages=[
            ("Client", "Handler", "GET /x"),
            ("Handler", "Service", "load"),
        ],
    )
    rendered = MermaidRenderer().render_diagram(plan)
    assert "Handler->>+Client" not in rendered
    assert "Client-->>-Handler" not in rendered


def test_jwt_sequence_uses_token_prefix(tmp_path: Path) -> None:
    (tmp_path / "app" / "services").mkdir(parents=True)
    (tmp_path / "app" / "api" / "dependencies").mkdir(parents=True)
    (tmp_path / "app" / "core" / "settings").mkdir(parents=True)
    (tmp_path / "app" / "services" / "jwt.py").write_text("class JWT:\n    pass\n")
    (tmp_path / "app" / "api" / "dependencies" / "authentication.py").write_text(
        "prefix = settings.jwt_token_prefix\n"
    )
    (tmp_path / "app" / "core" / "settings" / "app.py").write_text('jwt_token_prefix = "Token"\n')
    planner = MermaidPlanner(str(tmp_path))
    plan = planner._plan_jwt_sequence("authentication-authorization-api", None, {})
    assert plan is not None
    assert any("Token" in msg[2] for msg in plan.sequence_messages)
    assert all("Bearer" not in msg[2] for msg in plan.sequence_messages)


def test_anonymous_handler_uses_registering_function() -> None:
    text = (
        "package agent\n"
        "func (t *Transport) Mount(mux *http.ServeMux) {\n"
        '    mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {})\n'
        "}\n"
    )
    found = extract_go_endpoints([("internal/agent/http_transport.go", text)])
    assert found
    assert found[0].handler != "func"
    assert "Mount" in found[0].handler or found[0].handler == "Transport.Mount"


def test_package_graph_keeps_real_cmd_edges(tmp_path: Path) -> None:
    root = _go_root(tmp_path)
    planner = MermaidPlanner(str(root))
    context = {
        "modules": [
            {"name": "ccagent", "path": "cmd/ccagent"},
            {"name": "probe-agent", "path": "cmd/probe-agent"},
            {"name": "services", "path": "internal/services"},
            {"name": "agent", "path": "internal/agent"},
            {"name": "control", "path": "internal/control"},
        ],
        "import_edges": [
            ("cmd/ccagent", "internal/services"),
            ("cmd/probe-agent", "internal/agent"),
        ],
        "snapshot_paths": [],
    }
    plan = planner._plan_overview_architecture_diagram("architecture-overview", None, context)
    assert plan is not None
    labels = {node.label for node in plan.nodes}
    assert "docs/" not in labels
    edge_pairs = {(e.from_node, e.to_node) for e in plan.edges}
    assert edge_pairs


def test_verifier_registers_round8_hard_checks() -> None:
    codes = QoderLikeSeverityThreshold.STRICT_HARD_CODES
    assert "QODER_HANDBOOK_DIAGRAM_EVIDENCE" in codes
    assert "QODER_HANDBOOK_INSTALL_PATH" in codes
    assert "QODER_HANDBOOK_IMPORT_CONSISTENCY" in codes
