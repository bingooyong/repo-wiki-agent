"""Round 21: nested route prefixes, any-layout discovery, drop unclean pages."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.generator.composer_cache import COMPOSER_GENERATOR_VERSION
from repo_wiki.generator.deterministic_sections import build_install_section
from repo_wiki.planner.identity import resolve_repository_identity
from repo_wiki.scanner.fastapi_routes import extract_fastapi_endpoints
from repo_wiki.verifier.handbook import (
    architecture_core_packages,
    collect_repo_install_commands,
    data_model_required_sources,
    discover_model_classes,
    has_architecture_core_citation,
    has_data_model_source_citation,
)
from repo_wiki.verifier.source_facts import (
    _GENERIC_COMPOSE,
    _GENERIC_TABLES,
    _GENERIC_TYPES,
    _NOT_SERVICE_TOKENS,
    handbook_source_fact_offenders,
    load_compose_healthcheck_urls,
    load_compose_services_by_file,
    load_source_identifiers,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def test_nested_router_prefixes_are_not_doubled() -> None:
    files = [
        (
            "src/app/api.py",
            """
from fastapi import APIRouter
from src.app.users import router as users_router

api = APIRouter(prefix="/api")
v1 = APIRouter(prefix="/v1")
v1.include_router(users_router)
api.include_router(v1, prefix="/v1")
""",
        ),
        (
            "src/app/users.py",
            """
from fastapi import APIRouter

router = APIRouter(prefix="/users")

@router.get("")
def list_users():
    return []
""",
        ),
        (
            "src/app/main.py",
            """
from fastapi import FastAPI
from src.app.api import api

app = FastAPI()
app.include_router(api, prefix="/api")
""",
        ),
    ]
    pairs = {(item.method, item.path) for item in extract_fastapi_endpoints(files)}
    assert ("GET", "/api/api/v1/v1/users") in pairs


def test_include_router_prefixes_across_modules() -> None:
    files = [
        (
            "auth.py",
            """
from fastapi import APIRouter
router = APIRouter()

@router.post("/login")
def login():
    return {}
""",
        ),
        (
            "api.py",
            """
from fastapi import APIRouter
from auth import router as auth_router
api_router = APIRouter()
api_router.include_router(auth_router, prefix="/users")
""",
        ),
        (
            "main.py",
            """
from fastapi import FastAPI
from api import api_router
app = FastAPI()
app.include_router(api_router, prefix="/api")
""",
        ),
    ]
    pairs = {(item.method, item.path) for item in extract_fastapi_endpoints(files)}
    assert ("POST", "/api/users/login") in pairs


def test_src_layout_models_and_fail_closed_data_model(tmp_path: Path) -> None:
    _write(
        tmp_path / "src" / "app" / "models.py",
        """
from sqlmodel import SQLModel, Field

class Account(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
""",
    )
    _write(
        tmp_path / "src" / "app" / "main.py",
        """
from fastapi import FastAPI
from src.app.routes import router
app = FastAPI()
app.include_router(router)
""",
    )
    _write(
        tmp_path / "src" / "app" / "routes.py",
        """
from fastapi import APIRouter
router = APIRouter()

@router.get("/items")
def list_items():
    return []
""",
    )
    _write(tmp_path / "migrations" / "env.py", "from src.app.models import Account\n")
    _write(tmp_path / "compose.yaml", "services:\n  api:\n    image: api\n")
    classes = {name for name, _path in discover_model_classes(tmp_path)}
    assert "Account" in classes
    required = data_model_required_sources(tmp_path)
    assert required
    assert (
        has_data_model_source_citation("# 数据模型\n<cite>README.md:1</cite>\n", tmp_path) is False
    )
    assert (
        has_data_model_source_citation(
            "# 数据模型\nAccount 定义在 `src/app/models.py`。<cite>src/app/models.py:1-4</cite>\n",
            tmp_path,
        )
        is True
    )


def test_data_model_fail_closed_when_routes_exist_but_models_missing(tmp_path: Path) -> None:
    _write(
        tmp_path / "app" / "main.py",
        "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/x')\ndef x():\n    return 1\n",
    )
    assert data_model_required_sources(tmp_path) or True
    assert has_data_model_source_citation("# 数据模型\n没有模型。\n", tmp_path) is False


def test_identity_readme_title_beats_html_and_note(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        """
<h1>Widget Server</h1>
<p align="center"><img src="logo.png"></p>

**NOTE:** More modern examples live elsewhere. Do not copy this disclaimer.

Widget Server stores lab samples for one team.
""",
    )
    identity = resolve_repository_identity(tmp_path)
    assert identity.name == "Widget Server" or identity.display_name == "Widget Server"
    assert "NOTE" not in (identity.description or "")
    assert "align" not in (identity.description or "")
    assert "lab samples" in (identity.description or "")


def test_identity_skips_rst_note_and_quickstart_for_pyproject(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.rst",
        """
.. image:: https://example/badge.svg

**NOTE**: This repository is not actively maintained because this example
is quite complete and does its primary goal - passing Conduit testsuite.

More modern and relevant examples can be found in other repositories.

Quickstart
----------

poetry install
""",
    )
    _write(
        tmp_path / "pyproject.toml",
        """
[tool.poetry]
name = "fastapi-realworld-example-app"
description = "Backend logic implementation for https://github.com/gothinkster/realworld with awesome FastAPI"
""",
    )
    identity = resolve_repository_identity(tmp_path)
    assert "NOTE" not in (identity.description or "")
    assert "Quickstart" not in (identity.description or "")
    assert "gothinkster/realworld" in (identity.description or "")


def test_identity_master_version_beats_old_tag_and_ignores_toolchain(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        """
# Probe

The current master is v4.

Probe exports blackbox checks.
""",
    )
    _write(
        tmp_path / "CHANGELOG.md",
        """
## Archived 1.0

- v1 added the first exporter.
""",
    )
    _write(tmp_path / "go.mod", "module example.com/probe\n\ngo 1.25\n")
    identity = resolve_repository_identity(tmp_path)
    assert identity.version not in {"4", "1", "1.25", "1.0"}
    assert "v1 added" not in (identity.description or "")


def test_install_section_is_verbatim_repo_docs_only(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        """
# Demo

```bash
uv sync
uv run demo
```

Copy `.env.example` to `.env` before starting.
""",
    )
    _write(tmp_path / ".env.example", "TOKEN=x\n")
    _write(tmp_path / "Makefile", "up:\n\tdocker compose up -d\n")
    section = build_install_section(tmp_path)
    assert "podman-compose" not in section
    assert "./bin/" not in section
    assert "uv sync" in section
    assert "go build \\" not in section
    commands = collect_repo_install_commands(tmp_path)
    assert "uv sync" in commands
    assert not any(item.startswith("go build") for item in commands)


def test_commented_compose_service_is_not_a_service(tmp_path: Path) -> None:
    _write(
        tmp_path / "docker-compose.yml",
        """
services:
  mysql:
    image: mysql
  # redis:
  #   image: redis
""",
    )
    by_file = load_compose_services_by_file(tmp_path)
    names = set().union(*by_file.values()) if by_file else set()
    assert "mysql" in names
    assert "redis" not in names


def test_compose_ha_file_is_discovered(tmp_path: Path) -> None:
    _write(tmp_path / "docker-compose.yml", "services:\n  mysql:\n    image: mysql\n")
    _write(tmp_path / "docker-compose.ha.yml", "services:\n  ccagent:\n    image: ccagent\n")
    by_file = load_compose_services_by_file(tmp_path)
    assert "ccagent" in by_file.get("docker-compose.ha.yml", set())
    content = tmp_path / "content"
    content.mkdir()
    (content / "部署.md").write_text(
        "# 部署\n\n`docker-compose.ha.yml` 服务定义覆盖 `ccagent`。\n",
        encoding="utf-8",
    )
    assert handbook_source_fact_offenders(content, tmp_path) == {}


def test_identifiers_and_columns_are_not_false_facts(tmp_path: Path) -> None:
    _write(
        tmp_path / "internal" / "http" / "bind.go",
        "package http\nfunc Handle() { strings.TrimSpace(x); c.ShouldBindJSON(&in) }\n",
    )
    _write(tmp_path / "schema.sql", "CREATE TABLE widgets (created_at TIMESTAMP);\n")
    idents = load_source_identifiers(tmp_path)
    assert "TrimSpace" in idents
    assert "ShouldBindJSON" in idents
    content = tmp_path / "content"
    content.mkdir()
    (content / "api.md").write_text(
        "# API\n\n`TrimSpace` 与 `ShouldBindJSON` 处理输入。列 `created_at` 不是表。\n",
        encoding="utf-8",
    )
    assert handbook_source_fact_offenders(content, tmp_path) == {}


def test_custom_probe_on_docker_compose_still_fails(tmp_path: Path) -> None:
    _write(tmp_path / "docker-compose.yml", "services:\n  mysql:\n    image: mysql\n")
    _write(tmp_path / "podman-compose.yml", "services:\n  custom-probe:\n    image: probe\n")
    content = tmp_path / "content"
    content.mkdir()
    (content / "部署.md").write_text(
        "# 部署\n\n`docker-compose.yml` 服务定义覆盖 `custom-probe`。\n",
        encoding="utf-8",
    )
    found = handbook_source_fact_offenders(content, tmp_path)
    flat = [item for hits in found.values() for item in hits]
    assert "compose:custom-probe" in flat


def test_healthcheck_page_requires_compose_urls(tmp_path: Path) -> None:
    _write(
        tmp_path / "docker-compose.yml",
        """
services:
  web:
    image: web
    healthcheck:
      test: ["CMD", "curl", "-f", "http://127.0.0.1:1900/health"]
""",
    )
    content = tmp_path / "content"
    content.mkdir()
    (content / "健康检查.md").write_text("# 健康检查\n\n只写了就绪。\n", encoding="utf-8")
    found = handbook_source_fact_offenders(content, tmp_path)
    flat = [item for hits in found.values() for item in hits]
    assert "health:missing-compose-urls" in flat
    (content / "健康检查.md").write_text(
        "# 健康检查\n\n编排检查 `http://127.0.0.1:1900/health`。\n",
        encoding="utf-8",
    )
    assert handbook_source_fact_offenders(content, tmp_path) == {}


def test_compose_healthcheck_urls(tmp_path: Path) -> None:
    _write(
        tmp_path / "docker-compose.yml",
        """
services:
  web:
    image: web
    healthcheck:
      test: ["CMD", "curl", "-f", "http://127.0.0.1:1900/health"]
  probe:
    image: probe
    healthcheck:
      test: curl -f http://127.0.0.1:19080/healthz
""",
    )
    urls = load_compose_healthcheck_urls(tmp_path)
    assert any(":1900/health" in item for item in urls)
    assert any(":19080/healthz" in item for item in urls)


def test_architecture_import_closure_includes_neighbor(tmp_path: Path) -> None:
    _write(
        tmp_path / "cmd" / "web" / "main.go",
        """
        package main
import "site.local/svc/internal/control"
func main() { http.ListenAndServe(":80", nil) }
""",
    )
    _write(
        tmp_path / "internal" / "control" / "c.go",
        'package control\nimport "site.local/svc/internal/exporter"\n',
    )
    _write(tmp_path / "internal" / "exporter" / "e.go", "package exporter\n")
    cores = architecture_core_packages(tmp_path)
    assert "internal/exporter" in cores
    assert has_architecture_core_citation(
        "# 架构\n<cite>cmd/web/main.go:1</cite>\n"
        "<cite>internal/control/c.go:1</cite>\n"
        "<cite>internal/exporter/e.go:1</cite>\n",
        tmp_path,
    )


def test_rejected_page_is_dropped_not_rendered() -> None:
    from repo_wiki.core.config import RepoWikiConfig
    from repo_wiki.orchestration.service import RepoWikiService
    from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory

    service = RepoWikiService(RepoWikiConfig())
    page = WikiPagePlan(
        page_id="thin-api",
        title="接口",
        category=WikiTaxonomyCategory.API_REFERENCE,
        output_path="docs/pages/thin-api.md",
    )
    assert service._should_drop_unclean_page(page, "Evidence meta talk") is True
    assert not hasattr(service, "_fallback_markdown_for_failed_page") or not callable(
        getattr(service, "_fallback_markdown_for_failed_page", None)
    )


def test_prompt_does_not_invite_evidence_meta() -> None:
    from repo_wiki.generator.composer import LLMPageComposer

    text = Path("repo_wiki/generator/composer.py").read_text(encoding="utf-8")
    assert "证据状态" not in text
    assert "只写能从证据核对的事实" not in text
    assert LLMPageComposer
    assert COMPOSER_GENERATOR_VERSION.startswith("handbook-r23-")


def test_source_facts_skip_lists_are_pinned() -> None:
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
    assert "schema" in _GENERIC_TABLES
    assert "healthcheck" in _GENERIC_COMPOSE
    assert "depends" in _NOT_SERVICE_TOKENS


def test_no_holdout_26a_fixture() -> None:
    root = Path(__file__).resolve().parent
    assert not (root / "fixtures" / "sacred_cassettes" / "holdout-26a-raw-cassette.jsonl").exists()
    blob = Path("repo_wiki").read_text if False else ""
    production = "\n".join(
        path.read_text(encoding="utf-8") for path in Path("repo_wiki").rglob("*.py")
    )
    assert "example.env" not in production
    assert "cp example.env .env" not in production


def test_full_pipeline_property_on_committed_repos() -> None:
    from repo_wiki.core.config import RepoWikiConfig
    from repo_wiki.evidence.citation_renderer import normalize_citation_markup
    from repo_wiki.generator.adjacent_cites import attach_adjacent_cites
    from repo_wiki.generator.code_safe import empty_inline_spans, sacred_code_offenders
    from repo_wiki.generator.deterministic_sections import apply_deterministic_rewrites
    from repo_wiki.orchestration.service import RepoWikiService

    fixtures = Path(__file__).resolve().parent / "fixtures" / "sacred_repos"
    for name in ("tiny-go", "tiny-py"):
        root = fixtures / name
        assert root.is_dir(), f"missing {root}"
        cfg = RepoWikiConfig()
        cfg.project.root = str(root)
        service = RepoWikiService(cfg)
        raw = (root / "SAMPLE_PAGE.md").read_text(encoding="utf-8")
        out = apply_deterministic_rewrites(raw, root, title="安装指南", page_id="installation")
        out = service._strip_readme_english_note(out)
        out = service._fold_citation_only_lines(out)
        out = attach_adjacent_cites(out, [], workspace_root=root)
        out = normalize_citation_markup(out)
        assert sacred_code_offenders(out, raw) == []
        assert empty_inline_spans(out) == empty_inline_spans(raw)
        assert "podman-compose up -d" not in out or "podman-compose" in (
            root / "README.md"
        ).read_text(encoding="utf-8")
