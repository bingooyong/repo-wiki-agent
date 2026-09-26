"""Round 22: install extractor, identity, independent routes, tables, health, verify pins."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.generator.deterministic_sections import (
    apply_deterministic_rewrites,
    build_install_section,
    strip_empty_numbered_steps,
)
from repo_wiki.planner.identity import resolve_repository_identity
from repo_wiki.scanner.fastapi_routes import extract_fastapi_endpoints, join_http_paths
from repo_wiki.scanner.go_routes import extract_go_endpoints
from repo_wiki.verifier.handbook import (
    _SKIP_DISCOVERY_DIRS,
    MIN_HANDBOOK_BODY_CHARS,
    collect_repo_install_commands,
    data_model_absence_offenders,
    data_model_required_sources,
    discover_dto_classes,
    discover_model_classes,
    extract_readme_shell_commands,
    handbook_page_body_len,
    handbook_page_is_fallback_stub,
    has_data_model_source_citation,
    install_steps_invalid_reason,
)
from repo_wiki.verifier.handbook_routes import (
    extract_handbook_http_paths,
    extract_source_http_paths,
    handbook_route_crosscheck_mismatches,
)
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeSeverityThreshold
from repo_wiki.verifier.source_facts import (
    _GENERIC_COMPOSE,
    _GENERIC_TABLES,
    _GENERIC_TYPES,
    _NOT_SERVICE_TOKENS,
    _SKIP_DIRS,
    handbook_source_fact_offenders,
    load_compose_health_map,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def test_a_readme_shell_extractor_strips_prompts_and_rejects_makefile() -> None:
    text = """
# Demo

Install it:

```bash
$ git clone https://example.invalid/demo.git
> cp *.env .env
$ alembic upgrade head
$ uv run demo
$ curl http://127.0.0.1:8000/health
```

Makefile noise:

```make
install:
	@echo build
	go build $(FLAGS) $$HOME
```

Prose: you should probably run tests after that.
"""
    commands = extract_readme_shell_commands(text)
    assert commands == [
        "git clone https://example.invalid/demo.git",
        "cp *.env .env",
        "alembic upgrade head",
        "uv run demo",
        "curl http://127.0.0.1:8000/health",
    ]
    assert not any(item.startswith("@") or "$(FLAGS)" in item or "$$" in item for item in commands)


def test_a_install_builder_is_wired_and_never_deletes_steps(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        """
# Demo

```sh
$ git clone https://example.invalid/demo.git
$ cp *.env .env
uv run demo
curl http://127.0.0.1:9/ready
```
""",
    )
    commands = collect_repo_install_commands(tmp_path)
    assert commands[0] == "git clone https://example.invalid/demo.git"
    assert "cp *.env .env" in commands
    section = build_install_section(tmp_path)
    assert "git clone https://example.invalid/demo.git" in section

    from repo_wiki.core.config import RepoWikiConfig
    from repo_wiki.orchestration.service import RepoWikiService
    from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory

    service = RepoWikiService(RepoWikiConfig())
    service.root = tmp_path
    install = WikiPagePlan(
        page_id="installation",
        title="安装与配置",
        category=WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
        output_path="docs/pages/installation.md",
    )
    quick = WikiPagePlan(
        page_id="quick-start",
        title="快速开始",
        category=WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
        output_path="docs/pages/quick-start.md",
    )
    draft = "# 安装\n\n## 安装步骤\n\n1. leftover\n"
    rewritten = service._rewrite_install_page_contract(install, draft)
    assert "git clone https://example.invalid/demo.git" in rewritten
    assert "leftover" not in rewritten
    satellite = service._rewrite_install_page_contract(quick, draft)
    assert "git clone https://example.invalid/demo.git" in satellite
    assert "leftover" not in satellite

    numbered = "## 安装步骤\n\n1. `git clone x`\n\n```bash\ngit clone x\n```\n\n4. `uv sync`\n"
    assert strip_empty_numbered_steps(numbered) == numbered
    kept = apply_deterministic_rewrites(
        numbered + "\n", tmp_path, title="架构设计", page_id="architecture-overview"
    )
    assert "1. `git clone x`" in kept
    assert "4. `uv sync`" in kept
    assert install_steps_invalid_reason("1. `@echo build`\n") == "invalid-install-step"


def test_b_identity_html_h1_skips_numbered_and_version_bullets(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        """
<h1 align="center">Harbor Lamp</h1>

## 0. About

**NOTE:** ignore this callout

**v4**: master branch

A stray 1 appears in the changelog tease.

Harbor Lamp watches coastal beacons.
""",
    )
    identity = resolve_repository_identity(tmp_path)
    assert identity.name == "Harbor Lamp"
    assert identity.display_name == "Harbor Lamp"
    assert "0." not in (identity.name or "")
    assert "v4" not in (identity.name or "")
    assert identity.version is None
    assert "Harbor Lamp watches" in (identity.description or "")


def test_b_identity_version_comes_from_metadata_not_prose(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "# Tool\n\nThe current master is v9.\n\nTool ships binaries.\n")
    _write(tmp_path / "pyproject.toml", '[project]\nname = "tool"\nversion = "2.3.1"\n')
    identity = resolve_repository_identity(tmp_path)
    assert identity.version == "2.3.1"


def test_c_join_http_paths_concatenates_without_overlap_drop() -> None:
    assert join_http_paths("/api", "/api") == "/api/api"
    assert join_http_paths("/api", "/v1", "/users") == "/api/v1/users"


def test_c_go_group_and_to_routes_are_discovered() -> None:
    files = [
        (
            "httpx/router.go",
            """
package httpx

func Mount(r Router) {
    rg := r.Group("/v1")
    rg.Get("/items", ListItems)
    admin := rg.Group("/admin")
    admin.Post("/purge", Purge)
    r.To("GET,HEAD", "/ready", Ready)
}
""",
        )
    ]
    pairs = {(item.method, item.path) for item in extract_go_endpoints(files)}
    assert ("GET", "/v1/items") in pairs
    assert ("POST", "/v1/admin/purge") in pairs
    assert ("GET", "/ready") in pairs
    assert ("HEAD", "/ready") in pairs
    source = extract_source_http_paths(files)
    assert ("GET", "/v1/items") in source
    assert ("HEAD", "/ready") in source


def test_c_route_crosscheck_reads_handbook_and_is_independent() -> None:
    files = [
        (
            "app.py",
            """
from fastapi import FastAPI, APIRouter
app = FastAPI()
inner = APIRouter(prefix="/v1")
@inner.get("/ping")
def ping():
    return {}
app.include_router(inner, prefix="/api")
""",
        )
    ]
    endpoints = extract_fastapi_endpoints(files)
    assert ("GET", "/api/v1/ping") in {(item.method, item.path) for item in endpoints}
    handbook = "# API\n\nGET `/api/v1/ping` 与 GET `/invented/nope`。\n"
    assert ("GET", "/api/v1/ping") in extract_handbook_http_paths(handbook)
    assert ("GET", "/invented/nope") in extract_handbook_http_paths(handbook)
    mismatches = handbook_route_crosscheck_mismatches(handbook, files)
    assert any("invented/nope" in item for item in mismatches)
    assert not any("/api/v1/ping" in item for item in mismatches)
    import repo_wiki.scanner.fastapi_routes as scanner
    import repo_wiki.verifier.handbook_routes as independent

    assert independent.concat_http_paths is not scanner.join_http_paths
    assert not hasattr(independent, "_resolve_router_ref")


def test_c_independent_extractor_joins_attr_prefix_and_module_router() -> None:
    files = [
        (
            "main.py",
            """
from fastapi import FastAPI
from pkg.httpx import api as api_router
class Settings:
    api_prefix: str = "/api"
application = FastAPI()
application.include_router(api_router.router, prefix=settings.api_prefix)
""",
        ),
        (
            "pkg/httpx/api.py",
            """
from fastapi import APIRouter
router = APIRouter()
router.include_router(users.router, prefix="/users")
""",
        ),
        (
            "pkg/httpx/users.py",
            """
from fastapi import APIRouter
router = APIRouter()
@router.post("/login")
def login():
    return {}
""",
        ),
        (
            "svc.go",
            """
package svc
func Mount(r Router) {
    r.POST("/hello/echo", Echo)
}
""",
        ),
    ]
    source = extract_source_http_paths(files)
    assert ("POST", "/api/users/login") in source
    assert ("POST", "/hello/echo") in source
    handbook = "POST `/api/users/login` 与 POST `/hello/echo` 与 GET `/invented`。"
    mismatches = handbook_route_crosscheck_mismatches(handbook, files)
    assert not any("api/users/login" in item or "hello/echo" in item for item in mismatches)
    assert any("invented" in item for item in mismatches)


def test_d_models_are_tables_dtos_are_labeled(tmp_path: Path) -> None:
    _write(
        tmp_path / "models.py",
        """
from sqlmodel import SQLModel
from pydantic import BaseModel

class Account(SQLModel, table=True):
    id: int | None = None

class AccountIn(BaseModel):
    name: str
""",
    )
    _write(
        tmp_path / "orm.py",
        """
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class Note(Base):
    __tablename__ = "notes"
""",
    )
    _write(
        tmp_path / "store.go",
        """
package store

type Widget struct {
    Name string
}

func Boot(db *DB) { db.AutoMigrate(&Widget{}) }
""",
    )
    _write(
        tmp_path / "query.go",
        """
package store

type ResultFilter struct {
    Name string
}

func List(db *DB) { db.Find(&ResultFilter{}) }
""",
    )
    _write(tmp_path / "sql" / "001_up.sql", "CREATE TABLE beacons (id INT);\n")
    _write(tmp_path / "sql" / "001_down.sql", "DROP TABLE beacons;\n")
    tables = {name for name, _rel in discover_model_classes(tmp_path)}
    dtos = {name for name, _rel in discover_dto_classes(tmp_path)}
    assert "Account" in tables
    assert "Note" in tables
    assert "Widget" in tables
    assert "beacons" in tables
    assert "ResultFilter" not in tables
    assert "AccountIn" in dtos
    assert "AccountIn" not in tables
    required = data_model_required_sources(tmp_path)
    assert any("001_up.sql" in item or "sql/001_up.sql" in item for item in required)
    assert not any("001_down.sql" in item for item in required)
    page = (
        "# 数据模型\nAccount 与 Note、Widget 是表。<cite>models.py:4-5</cite>"
        "<cite>orm.py:6-7</cite><cite>store.go:3-5</cite>\n"
        "AccountIn 是 DTO，没有 int id。\n"
        "<cite>sql/001_up.sql:1-1</cite>\n"
    )
    assert has_data_model_source_citation(page, tmp_path) is True
    absent = "# 数据模型\n仓库没有 sql 目录。\n<cite>models.py:1</cite>\n"
    assert data_model_absence_offenders(absent, tmp_path)


def test_e_health_map_from_compose_and_gate_checks_mapping(tmp_path: Path) -> None:
    _write(
        tmp_path / "docker-compose.yml",
        """
services:
  api:
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://127.0.0.1:8000/health"]
  blackbox:
    ports:
      - "9115:9115"
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://127.0.0.1:9115/metrics"]
""",
    )
    mapping = {(item.service, item.url) for item in load_compose_health_map(tmp_path)}
    assert ("api", "http://127.0.0.1:8000/health") in mapping
    assert any(svc == "blackbox" and "9115" in url for svc, url in mapping)
    content = tmp_path / "pages"
    _write(
        content / "健康检查.md",
        "api 使用 `http://127.0.0.1:8000/health`。blackbox 使用 `http://127.0.0.1:9115/metrics`。\n",
    )
    assert handbook_source_fact_offenders(content, tmp_path) == {}
    _write(
        content / "健康检查.md",
        "api 使用 `:9115`。blackbox 使用 `http://127.0.0.1:8000/health`。\n",
    )
    found = handbook_source_fact_offenders(content, tmp_path)
    assert any("health:service-url-mismatch" in hit for hits in found.values() for hit in hits)


def test_f_dropped_core_and_short_skeleton_cannot_hide(tmp_path: Path) -> None:
    from repo_wiki.orchestration.quality_artifacts import (
        _is_core_handbook_page,
        build_generation_quality_documents,
    )
    from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory

    assert _is_core_handbook_page("project-overview", "项目概述")
    assert _is_core_handbook_page("installation", "安装与配置")
    assert not _is_core_handbook_page("deployment-overview", "部署概览")
    assert not _is_core_handbook_page("api-development", "API开发指南")

    page = WikiPagePlan(
        page_id="project-overview",
        title="项目概述",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
        output_path="docs/pages/project-overview.md",
    )
    content = tmp_path / "content"
    content.mkdir()
    registry, report = build_generation_quality_documents(
        run_id="r22",
        profile_name="qoder-like",
        content_dir=content,
        plan_pages=[page],
        written_files=[],
        content_stats={"path_mappings": []},
        composition_page_metadata=[],
        failed_pages=[{"page_id": "project-overview", "title": "项目概述", "dropped": True}],
        quality_warnings=[],
        llm_summary={"dropped_page_count": 1, "dropped_page_ids": ["project-overview"]},
    )
    del registry
    assert report["summary"]["dropped_count"] >= 1
    assert report["summary"]["dropped_core_count"] >= 1
    assert report["summary"]["grade"] == "FAIL"
    assert MIN_HANDBOOK_BODY_CHARS == 800
    skeleton = "# 概述\n\n短页。\n"
    assert handbook_page_body_len(skeleton) < 800
    assert handbook_page_is_fallback_stub(skeleton) is False
    assert handbook_page_body_len(skeleton) < 800
    assert "QODER_HANDBOOK_DROPPED_CORE" in QoderLikeSeverityThreshold.STRICT_HARD_CODES


def test_g_generic_and_skip_lists_are_full_sets() -> None:
    assert "SessionLocal" not in _GENERIC_TYPES
    assert (
        frozenset(
            {
                "FastAPI",
                "PostgreSQL",
                "SQLAlchemy",
                "Alembic",
                "HTTPException",
                "Depends",
                "Docker",
                "GitHub",
                "Dockerfile",
                "Makefile",
                "Handle",
            }
        )
        == _GENERIC_TYPES
    )
    assert (
        frozenset({".git", ".repo-agent-eval", "vendor", "node_modules", "__pycache__", "testdata"})
        == _SKIP_DIRS
    )
    assert (
        frozenset({".git", ".repo-agent-eval", "vendor", "node_modules", "__pycache__", "testdata"})
        == _SKIP_DISCOVERY_DIRS
    )
    assert "schema" in _GENERIC_TABLES
    assert "healthcheck" in _GENERIC_COMPOSE
    assert "depends" in _NOT_SERVICE_TOKENS
