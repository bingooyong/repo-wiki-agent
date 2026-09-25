"""Round 20: subtractive sacred-code, page-owned facts, fail-closed gates."""

from __future__ import annotations

import json
from pathlib import Path

from repo_wiki.evidence.citation_renderer import normalize_citation_markup
from repo_wiki.generator.code_safe import empty_inline_spans, sacred_code_offenders
from repo_wiki.generator.composer_cache import COMPOSER_GENERATOR_VERSION
from repo_wiki.generator.deterministic_sections import (
    apply_deterministic_rewrites,
    strip_header_only_cites,
)
from repo_wiki.planner.schema import WikiTaxonomyCategory
from repo_wiki.verifier.handbook import (
    EMPTY_SPAN_REJECTION,
    architecture_core_packages,
    handbook_code_integrity_offenders,
    handbook_reader_hygiene_offenders,
    has_architecture_core_citation,
    load_type_method_inventory,
)
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeVerifierService
from repo_wiki.verifier.source_facts import (
    handbook_source_fact_offenders,
    load_database_tables,
    load_health_routes,
    source_fact_prompt_block,
)
from tests.test_handbook_round10 import _go_context, _page, _render, _service

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "sacred_cassettes"
_REQUIRED_EXCERPTS = (
    "fastapi-25m-raw-cassette",
    "fastapi-25n-raw-cassette",
    "fastapi-25o-raw-cassette",
    "fastapi-25p-raw-cassette",
    "fastapi-25q-raw-cassette",
    "fastapi-25r-raw-cassette",
    "fastapi-25s-raw-cassette",
    "probe-25m-raw-cassette",
    "probe-25n-raw-cassette",
    "probe-25o-raw-cassette",
    "probe-25p-raw-cassette",
    "probe-25q-raw-cassette",
    "probe-25r-raw-cassette",
    "probe-25s-raw-cassette",
)


def test_header_only_cite_is_dropped_not_converted_to_code() -> None:
    text = "启动 `db`<cite>docker-compose.yml:1-2</cite> 服务。"
    out = strip_header_only_cites(normalize_citation_markup(text), Path("."))
    assert "`db``docker-compose.yml`" not in out
    assert "<cite>docker-compose.yml" not in out
    assert "`db`" in out


def test_install_stub_does_not_delete_fences(tmp_path: Path) -> None:
    raw = "# 本地开发环境\n\n## 安装步骤\n\n先同步依赖。\n\n```bash\npoetry install\n```\n"
    page = _page(
        "local-setup",
        "本地开发环境",
        WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
        "开发指南/本地开发环境.md",
    )
    out = _render(_service(tmp_path), page, raw, _go_context(tmp_path), add_mermaid=False)
    assert "```bash" in out
    assert "poetry install" in out
    assert "完整步骤见安装与配置" not in out


def test_empty_span_fails_integrity_even_if_raw_had_it(tmp_path: Path) -> None:
    content = tmp_path / "content"
    raw_dir = tmp_path / "meta" / "raw-replies"
    content.mkdir()
    raw_dir.mkdir(parents=True)
    (content / "page.md").write_text("# API\n\n见 `` 与代码。\n", encoding="utf-8")
    (raw_dir / "page.md").write_text("# API\n\n见 `` 与代码。\n", encoding="utf-8")
    (tmp_path / "main.go").write_text("package main\n", encoding="utf-8")
    found = handbook_code_integrity_offenders(content, tmp_path)
    assert found
    assert any("empty-span" in item for hits in found.values() for item in hits)


def test_changed_code_must_match_own_page_raw(tmp_path: Path) -> None:
    content = tmp_path / "content"
    raw_dir = tmp_path / "meta" / "raw-replies"
    content.mkdir()
    raw_dir.mkdir(parents=True)
    (content / "a.md").write_text("# A\n\n用 `POST /create`。\n", encoding="utf-8")
    (raw_dir / "a.md").write_text("# A\n\n用 `GET /list`。\n", encoding="utf-8")
    (raw_dir / "other.md").write_text("# Other\n\n用 `POST /create`。\n", encoding="utf-8")
    (tmp_path / "main.go").write_text("package main\n", encoding="utf-8")
    found = handbook_code_integrity_offenders(content, tmp_path)
    assert found


def test_architecture_fail_closed_when_nothing_discovered(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")
    assert architecture_core_packages(tmp_path) == []
    assert has_architecture_core_citation("# 架构\n<cite>README.md:1-2</cite>\n", tmp_path) is False


def test_architecture_discovers_app_main_and_domain(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "domain").mkdir()
    (tmp_path / "app" / "main.go").write_text(
        'package main\nfunc main() { http.ListenAndServe(":80", mux) }\n'
        'mux.HandleFunc("/health", h)\n',
        encoding="utf-8",
    )
    cores = architecture_core_packages(tmp_path)
    assert "app" in cores
    assert "domain" in cores
    assert has_architecture_core_citation(
        "# 架构\n<cite>app/main.go:1-3</cite>\n<cite>domain/user.go:1-2</cite>\n",
        tmp_path,
    )


def test_type_method_inventory_owned_label(tmp_path: Path) -> None:
    (tmp_path / "svc.go").write_text(
        "package svc\n"
        "type ServiceProbeEndpoint struct{}\n"
        "func (s *ServiceProbeEndpoint) ServeList() {}\n",
        encoding="utf-8",
    )
    assert "ServiceProbeEndpoint.ServeList" in load_type_method_inventory(tmp_path)
    content = tmp_path / "content"
    raw_dir = tmp_path / "meta" / "raw-replies"
    content.mkdir()
    raw_dir.mkdir(parents=True)
    (content / "api.md").write_text(
        "# API\n\n处理函数是 `ServiceProbeEndpoint.ServeList`。\n",
        encoding="utf-8",
    )
    (raw_dir / "api.md").write_text("# API\n\n处理函数见下。\n", encoding="utf-8")
    assert handbook_code_integrity_offenders(content, tmp_path) == {}
    (content / "api.md").write_text(
        "# API\n\n处理函数是 `MissingType.ServeNope`。\n", encoding="utf-8"
    )
    found = handbook_code_integrity_offenders(content, tmp_path)
    assert found


def test_disclaimer_and_raw_artefact_fail_hygiene(tmp_path: Path) -> None:
    content = tmp_path / "content"
    content.mkdir()
    (content / "a.md").write_text(
        "# A\n\n"
        + "X、Y 仅出现在说明文档，正文不应把它们当作源码接口合同。\n"
        + ("段 " * 80)
        + "\n",
        encoding="utf-8",
    )
    (content / "b.md").write_text(
        "# B\n\n<!-- raw HTML omitted -->\n" + ("段 " * 80) + "\n",
        encoding="utf-8",
    )
    found = handbook_reader_hygiene_offenders(content, tmp_path)
    assert found.get("fact_disclaimer")
    assert found.get("raw_artefact")


def test_page_owned_facts_are_not_global(tmp_path: Path) -> None:
    (tmp_path / "docker-compose.yml").write_text(
        "services:\n  mysql:\n    image: mysql\n    healthcheck:\n      test: mysqladmin\n",
        encoding="utf-8",
    )
    (tmp_path / "cmd" / "web").mkdir(parents=True)
    (tmp_path / "cmd" / "web" / "main.go").write_text(
        'package main\nfunc main() { http.HandleFunc("/healthz", h) }\n',
        encoding="utf-8",
    )
    assert source_fact_prompt_block(tmp_path) == ""
    health = source_fact_prompt_block(tmp_path, page_id="health-check", title="健康检查")
    assert "/healthz" in health
    assert "mysql" in health
    assert "只能使用下列" not in health
    assert "CLI 旗标" not in health
    model = source_fact_prompt_block(tmp_path, page_id="data-model", title="数据模型")
    assert "编排" not in model


def test_compose_depends_handle_pass_redis_fails(tmp_path: Path) -> None:
    (tmp_path / "docker-compose.yml").write_text(
        "services:\n  mysql:\n    image: mysql\n",
        encoding="utf-8",
    )
    content = tmp_path / "content"
    content.mkdir()
    (content / "部署.md").write_text(
        "# 部署\n\n`docker-compose.yml` 里注入 `Depends` 与 `handle`。\n",
        encoding="utf-8",
    )
    assert handbook_source_fact_offenders(content, tmp_path) == {}
    (content / "部署.md").write_text(
        "# 部署\n\n`docker-compose.yml` 服务定义覆盖 `redis`。\n",
        encoding="utf-8",
    )
    found = handbook_source_fact_offenders(content, tmp_path)
    flat = [item for hits in found.values() for item in hits]
    assert "compose:redis" in flat


def test_compose_checked_per_file(tmp_path: Path) -> None:
    (tmp_path / "docker-compose.yml").write_text(
        "services:\n  mysql:\n    image: mysql\n",
        encoding="utf-8",
    )
    (tmp_path / "podman-compose.yml").write_text(
        "services:\n  custom-probe:\n    image: probe\n",
        encoding="utf-8",
    )
    content = tmp_path / "content"
    content.mkdir()
    (content / "部署.md").write_text(
        "# 部署\n\n`docker-compose.yml` 服务定义覆盖 `custom-probe`。\n",
        encoding="utf-8",
    )
    found = handbook_source_fact_offenders(content, tmp_path)
    flat = [item for hits in found.values() for item in hits]
    assert "compose:custom-probe" in flat


def test_slash_orm_path_and_root_sql_and_healthz(tmp_path: Path) -> None:
    versions = tmp_path / "app" / "db" / "migrations"
    versions.mkdir(parents=True)
    (tmp_path / "app" / "db" / "migrations" / "env.py").write_text(
        "target_metadata = None\n",
        encoding="utf-8",
    )
    (tmp_path / "schema.sql").write_text("CREATE TABLE widgets (id INT);\n", encoding="utf-8")
    (tmp_path / "internal" / "http").mkdir(parents=True)
    (tmp_path / "internal" / "http" / "ready.go").write_text(
        'mux.HandleFunc("/healthz", ready)\n',
        encoding="utf-8",
    )
    assert "widgets" in load_database_tables(tmp_path)
    assert "/healthz" in load_health_routes(tmp_path)
    content = tmp_path / "content"
    content.mkdir()
    (content / "数据库迁移.md").write_text(
        "# 数据库迁移\n\n模型在 `app/db/models/`。\n",
        encoding="utf-8",
    )
    found = handbook_source_fact_offenders(content, tmp_path)
    flat = [item for hits in found.values() for item in hits]
    assert "orm:app.db.models" in flat


def test_claim_floor_uses_constant() -> None:
    import inspect

    source = inspect.getsource(QoderLikeVerifierService._check_qoder_claim_citation_coverage)
    assert "self.CLAIM_CITATION_FLOOR" in source
    assert "ratio < 0.95" not in source


def test_generator_version_is_r20() -> None:
    assert COMPOSER_GENERATOR_VERSION.startswith("handbook-r21-")


def test_empty_span_rejection_constant() -> None:
    assert EMPTY_SPAN_REJECTION


def test_fallback_rst_inline_is_not_empty_span() -> None:
    from repo_wiki.orchestration.service import RepoWikiService

    assert not hasattr(RepoWikiService, "_fallback_snippet_paragraphs")


def test_sacred_cassette_excerpts_run_real_post_processing(tmp_path: Path) -> None:
    from repo_wiki.core.config import RepoWikiConfig
    from repo_wiki.generator.adjacent_cites import attach_adjacent_cites
    from repo_wiki.orchestration.service import RepoWikiService

    assert _FIXTURE_DIR.is_dir(), "committed sacred cassette excerpts are missing"
    missing = [
        name for name in _REQUIRED_EXCERPTS if not (_FIXTURE_DIR / f"{name}.jsonl").is_file()
    ]
    assert missing == [], f"missing cassette excerpts: {missing}"
    cfg = RepoWikiConfig()
    cfg.project.root = str(tmp_path)
    service = RepoWikiService(cfg)
    checked = 0
    for name in _REQUIRED_EXCERPTS:
        path = _FIXTURE_DIR / f"{name}.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            raw = str(record.get("raw_reply") or "")
            if not raw.strip():
                continue
            out = apply_deterministic_rewrites(raw, tmp_path, title="", page_id="")
            out = service._strip_readme_english_note(out)
            out = service._fold_citation_only_lines(out)
            out = attach_adjacent_cites(out, [], workspace_root=tmp_path)
            out = normalize_citation_markup(out)
            assert sacred_code_offenders(out, raw) == [], name
            assert empty_inline_spans(out) == empty_inline_spans(raw), name
            checked += 1
    assert checked >= 14
