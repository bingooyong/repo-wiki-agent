"""Round 7: deterministic compose, reader hygiene, replay fixtures."""

from __future__ import annotations

import re
from pathlib import Path

from repo_wiki.generator.deterministic_sections import (
    apply_deterministic_rewrites,
    extract_alembic_tables,
    page_has_meta_instruction,
    page_has_repeated_fences,
)
from repo_wiki.generator.mermaid_planner import MermaidPlanner
from repo_wiki.scanner.conflict_resolver import resolve_source_docs_conflicts
from repo_wiki.scanner.docs_scanner import (
    _is_current_system_run_doc,
    _is_non_blocking_stale_claim,
)
from repo_wiki.verifier.handbook import handbook_reader_hygiene_offenders
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeVerifierService

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "handbook_replay"

_ALEMBIC = """
op.create_table(
    "users",
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("username", sa.Text, unique=True, nullable=False),
)
op.create_table(
    "articles",
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("author_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL")),
)
op.create_table(
    "tags",
    sa.Column("tag", sa.Text, primary_key=True),
)
"""


def _go_root(tmp_path: Path) -> Path:
    (tmp_path / "cmd" / "ccagent").mkdir(parents=True)
    (tmp_path / "cmd" / "probe-agent").mkdir(parents=True)
    (tmp_path / "cmd" / "ccprobe-control").mkdir(parents=True)
    (tmp_path / "internal" / "models").mkdir(parents=True)
    (tmp_path / "db").mkdir()
    (tmp_path / "cmd" / "ccagent" / "main.go").write_text(
        "package main\nfunc main() {}\n", encoding="utf-8"
    )
    (tmp_path / "cmd" / "probe-agent" / "main.go").write_text(
        "package main\nfunc main() {}\n", encoding="utf-8"
    )
    (tmp_path / "cmd" / "ccprobe-control" / "main.go").write_text(
        "package main\nfunc main() {}\n", encoding="utf-8"
    )
    (tmp_path / "cmd" / "ccprobe-control" / "serve.go").write_text(
        'package main\nfunc run() { transport := "grpc" }\n', encoding="utf-8"
    )
    (tmp_path / "internal" / "models" / "endpoint.go").write_text(
        "package models\n\ntype ProbeEndpoint struct {\n    ID int64\n}\n",
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
    (tmp_path / "db" / "schema.sql").write_text("SELECT 1;\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "# demo\n\n"
        "## 快速开始\n\n"
        "podman-compose up -d\n"
        "mysql < db/schema.sql\n"
        "go build -o bin/ccagent ./cmd/ccagent\n"
        "./bin/ccagent\n"
        "curl http://localhost:1900/health\n",
        encoding="utf-8",
    )
    (tmp_path / "podman-compose.yml").write_text(
        "services:\n"
        "  mysql-db:\n    image: mysql\n"
        "  ccagent:\n    image: x\n    depends_on:\n      - mysql-db\n"
        "  probe-agent:\n    image: y\n    depends_on:\n      - ccagent\n",
        encoding="utf-8",
    )
    return tmp_path


def _fastapi_root(tmp_path: Path) -> Path:
    versions = tmp_path / "app" / "db" / "migrations" / "versions"
    versions.mkdir(parents=True)
    (tmp_path / "app" / "main.py").write_text("app = None\n", encoding="utf-8")
    (tmp_path / "app" / "core" / "settings").mkdir(parents=True)
    (tmp_path / "app" / "models" / "domain").mkdir(parents=True)
    (tmp_path / "app" / "models" / "domain" / "user.py").write_text(
        "class User:\n    pass\n", encoding="utf-8"
    )
    (versions / "fdf8821871d7_main_tables.py").write_text(_ALEMBIC, encoding="utf-8")
    (tmp_path / "README.rst").write_text(
        "APP_ENV=dev\nSECRET_KEY=x\nDATABASE_URL=postgresql://x\n"
        "poetry install\n"
        "alembic upgrade head\n"
        "uvicorn app.main:app --reload\n"
        "docker-compose up -d db\n"
        "docker-compose up -d app\n",
        encoding="utf-8",
    )
    return tmp_path


def test_25g_raw_hygiene_catches_install_mash_and_meta() -> None:
    content = _FIXTURES / "probe-25g"
    offenders = handbook_reader_hygiene_offenders(content, None)
    assert offenders.get("repeated_fences")
    arch = (content / "architecture.md").read_text(encoding="utf-8")
    assert page_has_meta_instruction(arch)
    install = (content / "install.md").read_text(encoding="utf-8")
    assert page_has_repeated_fences(install)


def test_replay_probe_25g_install_separates_paths(tmp_path: Path) -> None:
    root = _go_root(tmp_path)
    raw = (_FIXTURES / "probe-25g" / "install.md").read_text(encoding="utf-8")
    out = apply_deterministic_rewrites(raw, root, title="安装与配置")
    fences = re.findall(r"```bash\n(.*?)```", out, flags=re.S)
    assert sum("podman-compose up -d" in fence for fence in fences) == 1
    assert "路径 A：容器编排" in out
    assert "路径 B：本地编译" in out
    assert "go build -o bin/ccagent ./cmd/ccagent" in out
    assert "curl http://localhost:1900/health" in out
    assert "安装与启动步骤以仓库入口文档为准" not in out
    assert page_has_repeated_fences(out) is False
    assert "## 目录" in out
    assert "1. 安装步骤" in out or "1. 这是什么" in out
    toc_heading = next(line for line in out.splitlines() if line.startswith("1. "))
    assert toc_heading.split(". ", 1)[1] in out


def test_replay_fastapi_25g_install_env_before_alembic(tmp_path: Path) -> None:
    root = _fastapi_root(tmp_path)
    raw = (_FIXTURES / "fastapi-25g" / "install.md").read_text(encoding="utf-8")
    out = apply_deterministic_rewrites(raw, root, title="安装与配置")
    section = out.split("## 安装步骤", 1)[1].split("## 目录", 1)[0]
    env_at = section.find("APP_ENV")
    alembic_at = section.find("poetry run alembic upgrade head")
    uvicorn_at = section.find("poetry run uvicorn")
    compose_db = section.find("docker-compose up -d db")
    compose_app = section.find("docker-compose up -d app")
    assert 0 <= env_at < alembic_at < uvicorn_at
    assert 0 <= compose_db < compose_app
    assert "（可选）" not in out
    assert page_has_repeated_fences(out) is False


def test_replay_rounds_keep_fences_and_toc(tmp_path: Path) -> None:
    go_root = _go_root(tmp_path / "go")
    py_root = _fastapi_root(tmp_path / "py")
    cases = [
        (go_root, "probe-25e", "install.md", "安装与配置", ""),
        (go_root, "probe-25f", "install.md", "安装与配置", ""),
        (go_root, "probe-25g", "architecture.md", "整体架构概览", "架构设计"),
        (py_root, "fastapi-25e", "install.md", "安装与配置", ""),
        (py_root, "fastapi-25f", "install.md", "安装与配置", ""),
        (py_root, "fastapi-25g", "datamodel.md", "数据模型", "data"),
    ]
    for root, folder, name, title, category in cases:
        raw = (_FIXTURES / folder / name).read_text(encoding="utf-8")
        out = apply_deterministic_rewrites(raw, root, title=title, category=category)
        assert page_has_repeated_fences(out) is False
        assert "不要把 package main" not in out
        if "## 目录" in out:
            after_toc = out.split("## 目录", 1)[1]
            toc_titles = [
                line.split(". ", 1)[1]
                for line in after_toc.splitlines()
                if line[:3].rstrip(".").isdigit() and ". " in line
            ]
            for heading in toc_titles:
                assert f"## {heading}" in out


def test_alembic_extracts_seven_style_tables() -> None:
    text = Path(
        "/tmp/fastapi-src-25g/fastapi-realworld-example-app/app/db/migrations/versions/"
        "fdf8821871d7_main_tables.py"
    )
    sample = text.read_text(encoding="utf-8") if text.is_file() else _ALEMBIC * 3
    if text.is_file():
        tables = extract_alembic_tables(sample)
        assert {item["name"] for item in tables} >= {
            "users",
            "followers_to_followings",
            "articles",
            "tags",
            "articles_to_tags",
            "favorites",
            "commentaries",
        }
        fks = [rel for item in tables for rel in item["relationships"]]
        assert len(fks) == 9
    else:
        tables = extract_alembic_tables(_ALEMBIC)
        assert {item["name"] for item in tables} == {"users", "articles", "tags"}


def test_service_network_is_not_an_inventory_claim() -> None:
    verifier = QoderLikeVerifierService(Path("."), strict=True)
    claims = verifier._extract_structured_name_claims(
        "The service network is attached to the compose file.", "service"
    )
    assert "network" not in claims


def test_stale_example_and_suggestion_are_non_blocking() -> None:
    assert _is_non_blocking_stale_claim(
        "README-scaffold.md", "See `docs/api/readme.md` example.com sample.", "docs/api/readme.md"
    )
    assert _is_non_blocking_stale_claim(
        "docs/BUG_FIX_REPORT.md", "建议补充 docs/changelog.md", "docs/changelog.md"
    )
    assert _is_non_blocking_stale_claim(
        "docs/ENGINEERING_BEST_PRACTICES.md",
        "| docs/adr/ | 缺失 |",
        "docs/adr/",
    )
    assert _is_current_system_run_doc("README.md")
    assert _is_current_system_run_doc("QUICKSTART.md")
    assert not _is_current_system_run_doc("test/performance/README.md")
    assert not _is_current_system_run_doc("docs/progress/PROJECT_STATUS.md")


def test_scaffold_stale_is_not_flagged() -> None:
    report = resolve_source_docs_conflicts(
        {
            "services": [],
            "api_surfaces": [],
            "data_models": [],
            "frontend_callers": [],
            "deployment_assets": [],
            "tests": [],
        },
        {
            "documents": [
                {
                    "path": "README-scaffold.md",
                    "doc_type": "overview",
                    "conflict_level": "stale",
                    "stale_references": ["docs/api/readme.md"],
                    "conflicting_claims": [],
                }
            ]
        },
    )
    assert report["summary"]["flagged_count"] == 0


def test_compose_topology_uses_real_services(tmp_path: Path) -> None:
    root = _go_root(tmp_path)
    planner = MermaidPlanner(str(root))
    plan = planner._plan_compose_topology("overview", None, {})
    assert plan is not None
    assert len(plan.edges) >= 1


def test_no_mermaid_html_comment_regex_literal() -> None:
    text = Path("repo_wiki/verifier/handbook.py").read_text(encoding="utf-8")
    assert "_MERMAID_EDGE_RE" not in text
    assert 'r"-->' not in text
    assert "r'-->" not in text
