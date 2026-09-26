"""Round 23: install render, routes, identity, data-model cites, reverted loosenings."""

from __future__ import annotations

import re
from pathlib import Path

from repo_wiki.generator.deterministic_sections import build_install_section, build_verify_section
from repo_wiki.generator.mermaid_planner import MermaidPlanner
from repo_wiki.orchestration.quality_artifacts import build_generation_quality_documents
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.identity import resolve_repository_identity
from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory
from repo_wiki.scanner.go_routes import extract_go_endpoints
from repo_wiki.verifier.handbook import (
    collect_repo_install_commands,
    discover_dto_classes,
    discover_model_classes,
    extract_readme_shell_commands,
    handbook_page_is_fallback_stub,
    install_page_render_errors,
    install_steps_invalid_reason,
    model_definition_cite_offenders,
)
from repo_wiki.verifier.handbook_routes import (
    ROUTE_COMPLETENESS_MIN,
    extract_handbook_http_paths,
    extract_source_http_paths,
    handbook_route_crosscheck_mismatches,
    route_completeness_gap,
    route_completeness_ratio,
    unsupported_route_languages,
)
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeSeverityThreshold
from repo_wiki.verifier.source_facts import (
    _GENERIC_COMPOSE,
    _GENERIC_TABLES,
    _NOT_SERVICE_TOKENS,
    handbook_source_fact_offenders,
    load_compose_health_map,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def test_1_install_render_keeps_cites_outside_code(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        """
# Lamp

```bash
$ git clone https://example.invalid/lamp.git
$ touch .env
```
""",
    )
    section = build_install_section(tmp_path)
    assert "<cite>" not in section.split("```")[1]
    assert "`<cite>" not in section
    assert section.count("```") % 2 == 0
    from repo_wiki.core.config import RepoWikiConfig

    folded = RepoWikiService(RepoWikiConfig())._fold_citation_only_lines(
        "1. `git clone x`\n\n```bash\ngit clone x\n```\n<cite>README.md:4-4</cite>\n",
    )
    assert folded.splitlines()[0] == "1. `git clone x`"
    assert "<cite>README.md:4-4</cite>" in folded
    assert install_page_render_errors(section) == []
    from repo_wiki.evidence.citation_renderer import normalize_citation_markup
    from repo_wiki.generator.adjacent_cites import attach_adjacent_cites

    stepped = (
        "## 安装步骤\n\n1. `git clone x`\n\n```bash\ngit clone x\n```\n<cite>README.md:4-4</cite>\n"
    )
    attached = attach_adjacent_cites(
        stepped,
        ["<cite>docs/note.md:2-8</cite>"],
        workspace_root=tmp_path,
    )
    normalized = normalize_citation_markup(attached, tmp_path)
    assert "``bash" not in normalized.replace("```bash", "")
    assert not re.search(r"`[^`\n]*<cite", re.sub(r"```.*?```", "", normalized))
    assert install_page_render_errors(normalized) == []


def test_1_install_gate_requires_balanced_steps() -> None:
    broken = "## 安装步骤\n\n1. `git clone x` <cite>README.md:1-1</cite>\n\n```bash\ngit clone x\n"
    assert install_page_render_errors(broken)
    gapped = "## 安装步骤\n\n1. `git clone x`\n\n```bash\ngit clone x\n```\n\n3. `touch .env`\n\n```bash\ntouch .env\n```\n"
    assert any("step" in item for item in install_page_render_errors(gapped))


def test_2_extractor_keeps_env_createdb_and_joins_backslash() -> None:
    text = """
# Demo

```bash
$ git clone https://example.invalid/demo.git
$ export TOKEN=$(cat secret)
$ createdb lantern
$ touch .env
$ curl -X POST http://127.0.0.1:9/ready \\
  -H 'Content-Type: application/json'
npx prisma generate
openssl rand -hex 8
```

between fences this is prose not a command

```make
install:
	@echo build
	go build $(FLAGS)
```

or use the other path:

```bash
pytest -q
```
"""
    commands = extract_readme_shell_commands(text)
    assert commands[0] == "git clone https://example.invalid/demo.git"
    assert any(item == "createdb lantern" for item in commands)
    assert any(item.startswith("export TOKEN=") and "$(cat secret)" in item for item in commands)
    assert any(item == "touch .env" for item in commands)
    assert any(
        "curl -X POST" in item and "-H" in item and not item.endswith("\\") for item in commands
    )
    assert "npx prisma generate" in commands
    assert "openssl rand -hex 8" in commands
    assert not any("prose" in item for item in commands)
    assert not any("echo build" in item or "$(FLAGS)" in item for item in commands)
    assert (
        install_steps_invalid_reason("1. `curl -X POST http://127.0.0.1:9/ready \\\n  -H x`\n")
        is None
    )
    assert "podman-compose up -d" in extract_readme_shell_commands(
        "# Demo\n\npodman-compose up -d\ncreatedb lantern\n"
    )


def test_2_readme_verbatim_does_not_drop_page(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        """
# Demo
```bash
$ curl http://127.0.0.1:9/ready \\
  -H 'X-Demo: 1'
$ createdb lantern
```
""",
    )
    commands = collect_repo_install_commands(tmp_path)
    assert any("curl" in item and "X-Demo" in item for item in commands)
    assert any("createdb" in item for item in commands)
    assert handbook_page_is_fallback_stub("# 安装\n\n短页。\n") is False


def test_3_only_http_healthchecks_become_curl(tmp_path: Path) -> None:
    _write(
        tmp_path / "docker-compose.yml",
        """
services:
  api:
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://127.0.0.1:8000/health"]
  db:
    ports:
      - "3306:3306"
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "127.0.0.1"]
""",
    )
    mapping = {(item.service, item.url) for item in load_compose_health_map(tmp_path)}
    assert ("api", "http://127.0.0.1:8000/health") in mapping
    assert not any(item[0] == "db" and "curl" in (item[1] or "") for item in mapping)
    assert not any("3306" in (item[1] or "") and "http" in (item[1] or "") for item in mapping)
    section = build_verify_section(tmp_path)
    assert "curl http://127.0.0.1:8000/health" in section
    assert "curl http://127.0.0.1:3306" not in section


def test_4_header_get_is_not_a_route() -> None:
    files = [
        (
            "httpx/router.go",
            """
package httpx
func Mount(r Router) {
    rg := r.Group("/v1")
    rg.Get("/items", ListItems)
    _ = req.Header.Get("X-Trace")
    _ = tags.Get("json")
}
""",
        )
    ]
    pairs = {(item.method, item.path) for item in extract_go_endpoints(files)}
    assert ("GET", "/v1/items") in pairs
    assert not any("X-Trace" in path or "json" in path for _method, path in pairs)
    source = extract_source_http_paths(files)
    assert ("GET", "/v1/items") in source
    assert not any(path in {"/X-Trace", "X-Trace", "/json"} for _method, path in source)


def test_5_crosscheck_is_exact_and_both_directions() -> None:
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
        ),
        (
            "web/router.ts",
            """
import { Router } from "express";
const router = Router();
router.get("/ready", ready);
export default router;
""",
        ),
    ]
    handbook = "# API\n\nGET `/api/v1/ping` 与 GET `/invented` 与 GET `/ready`。\n"
    mismatches = handbook_route_crosscheck_mismatches(handbook, files)
    assert any("invented" in item for item in mismatches)
    assert not any(
        item.endswith("/ping") and "invented" not in item
        for item in mismatches
        if "api/v1/ping" in item
    )
    assert ROUTE_COMPLETENESS_MIN == 0.5
    missing = route_completeness_gap(handbook, files)
    assert any("/ready" in item for item in missing) or (
        "GET",
        "/ready",
    ) in extract_source_http_paths(files)
    assert unsupported_route_languages([("svc.rb", "get '/x' do\nend\n")]) == ("rb",)
    assert not extract_handbook_http_paths("PUT /articles/:slug then DELETE /articles/:slug") & {
        ("PUT", "/DELETE")
    }
    one_of_four = "# API\n\nGET `/alpha`\n"
    four = [
        (
            "app.py",
            "@app.get('/alpha')\n@app.get('/beta')\n@app.get('/gamma')\n@app.get('/delta')\n",
        )
    ]
    assert route_completeness_ratio(one_of_four, four) == 0.25
    assert route_completeness_ratio(one_of_four, four) < ROUTE_COMPLETENESS_MIN


def test_6_identity_readme_h1_and_sources(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        """
<h1 align="center">Harbor Lamp</h1>

> NOTE: ignore

- badge list

Harbor Lamp watches coastal beacons.
""",
    )
    _write(
        tmp_path / "package.json",
        '{"name":"pkg-slug","version":"3.2.1","description":"slug desc"}\n',
    )
    identity = resolve_repository_identity(tmp_path)
    assert identity.display_name == "Harbor Lamp"
    assert identity.version == "3.2.1"
    assert "Harbor Lamp watches" in (identity.description or "")
    sources = identity.identity_sources or {}
    assert sources.get("display_name") == "readme"
    assert sources.get("version") == "package.json"


def test_7_odm_and_definition_cites(tmp_path: Path) -> None:
    _write(
        tmp_path / "models" / "beacon.py",
        """
from sqlmodel import SQLModel
class Beacon(SQLModel, table=True):
    name: str

class BeaconIn:
    name: str
""",
    )
    _write(
        tmp_path / "models" / "node.js",
        """
const mongoose = require("mongoose");
const Lantern = mongoose.Schema({
  title: String,
});
""",
    )
    tables = {name for name, _rel in discover_model_classes(tmp_path)}
    assert "Beacon" in tables
    assert "Lantern" in tables
    dtos = {name for name, _rel in discover_dto_classes(tmp_path)}
    assert "BeaconIn" in dtos
    page = "# 数据模型\nBeacon 与 Lantern。\n"
    assert model_definition_cite_offenders(page, tmp_path)
    cited = (
        "# 数据模型\nBeacon <cite>models/beacon.py:2-3</cite>\n"
        "Lantern <cite>models/node.js:2-4</cite>\n"
    )
    assert model_definition_cite_offenders(cited, tmp_path) == []
    planner = MermaidPlanner(str(tmp_path))
    plan = planner._plan_data_model_diagram(
        "data-models",
        None,
        {
            "data_models": [
                {"name": "Beacon", "type": "python_class", "attributes": ["name"]},
                {"name": "BeaconIn", "type": "python_class", "attributes": ["name"]},
            ]
        },
    )
    entities = {str(item.get("entity")) for item in (plan.er_entities if plan else [])}
    assert "Beacon" in entities
    assert "BeaconIn" not in entities


def test_8_no_silent_drop_and_health_port_path(tmp_path: Path) -> None:
    assert handbook_page_is_fallback_stub("# 概述\n\n" + ("段落。" * 20) + "\n") is False
    _write(
        tmp_path / "docker-compose.yml",
        """
services:
  api:
    ports: ["8000:8000"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://127.0.0.1:8000/health"]
""",
    )
    content = tmp_path / "pages"
    _write(content / "健康检查.md", "api 使用 `:8000`。\n")
    found = handbook_source_fact_offenders(content, tmp_path)
    assert any("health:" in hit for hits in found.values() for hit in hits)
    _write(content / "健康检查.md", "api 使用 `http://127.0.0.1:8000/health`。\n")
    assert handbook_source_fact_offenders(content, tmp_path) == {}


def test_8_orm_path_is_exact(tmp_path: Path) -> None:
    versions = tmp_path / "db" / "migrations"
    versions.mkdir(parents=True)
    _write(tmp_path / "db" / "migrations" / "env.py", "target_metadata = None\n")
    _write(tmp_path / "store" / "models" / "item.py", "class Item:\n    __tablename__ = 'items'\n")
    content = tmp_path / "pages"
    _write(content / "数据库迁移.md", "模型在 `app/db/models/`。\n")
    found = handbook_source_fact_offenders(content, tmp_path)
    flat = [item for hits in found.values() for item in hits]
    assert any(item.startswith("orm:") and "app/db/models" in item for item in flat)


def test_8_dropped_page_without_replacement_fails(tmp_path: Path) -> None:
    page = WikiPagePlan(
        page_id="installation",
        title="安装指南",
        category=WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
        output_path="docs/pages/installation.md",
    )
    content = tmp_path / "content"
    content.mkdir()
    _registry, report = build_generation_quality_documents(
        run_id="r23",
        profile_name="qoder-like",
        content_dir=content,
        plan_pages=[page],
        written_files=[],
        content_stats={"path_mappings": []},
        composition_page_metadata=[],
        failed_pages=[{"page_id": "installation", "title": "安装指南", "dropped": True}],
        quality_warnings=[],
        llm_summary={"dropped_page_count": 1, "dropped_page_ids": ["installation"]},
    )
    assert report["summary"]["dropped_count"] == 1
    assert report["summary"]["dropped_page_ids"] == ["installation"]
    assert "QODER_HANDBOOK_DROPPED_CORE" in QoderLikeSeverityThreshold.STRICT_HARD_CODES


def test_9_generic_sets_are_full_equality() -> None:
    assert (
        frozenset(
            {
                "alembic",
                "env",
                "head",
                "upgrade",
                "downgrade",
                "revision",
                "postgres",
                "postgresql",
                "sqlalchemy",
                "metadata",
                "versions",
                "schema",
                "base",
            }
        )
        == _GENERIC_TABLES
    )
    assert (
        frozenset(
            {
                "docker-compose",
                "podman-compose",
                "docker",
                "compose",
                "podman",
                "env-file",
                "health-check",
                "readyz",
                "livez",
                "yaml",
                "yml",
                "localhost",
                "restart",
                "unless-stopped",
                "healthcheck",
                "networks",
                "volumes",
                "environment",
                "dockerfile",
                "bind-addr",
                "container-name",
            }
        )
        == _GENERIC_COMPOSE
    )
    assert (
        frozenset(
            {
                "depends",
                "handle",
                "true",
                "false",
                "none",
                "self",
                "return",
                "import",
                "class",
                "async",
                "await",
                "const",
                "func",
            }
        )
        == _NOT_SERVICE_TOKENS
    )
    assert ROUTE_COMPLETENESS_MIN == 0.5
