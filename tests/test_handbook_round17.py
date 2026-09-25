"""Round 17: no prose/code deletion, derived roles, best-attempt keep, no hard-coded literals."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo_wiki.evidence.citation_renderer import strip_empty_cite_parens
from repo_wiki.generator.adjacent_cites import (
    cite_readme_supporting_line,
    find_alembic_revision_rel,
    realign_route_registration_cites,
)
from repo_wiki.generator.composer import build_composer_input, create_composer
from repo_wiki.generator.composer_cache import COMPOSER_GENERATOR_VERSION
from repo_wiki.generator.process_roles import (
    derive_process_role_facts,
    derive_repo_process_names,
    unknown_process_mentions,
)
from repo_wiki.llm.models import ChatResponse
from repo_wiki.planner.schema import WikiTaxonomyCategory
from repo_wiki.verifier.handbook import (
    EVIDENCE_META_REJECTION,
    handbook_reader_hygiene_offenders,
    handbook_unknown_process_offenders,
)
from tests.test_handbook_round10 import _fastapi_repo, _page, _service
from tests.test_handbook_round14 import _context
from tests.test_handbook_round15 import _auth_page
from tests.test_handbook_round16 import _pad, _write_probe_mains
from tests.test_llm_compose_retry import SequenceLLMProvider

_FORBIDDEN_SOURCE = (
    "repo_wiki/generator/process_roles.py",
    "repo_wiki/generator/adjacent_cites.py",
    "repo_wiki/verifier/handbook.py",
    "repo_wiki/generator/compose_evidence.py",
    "repo_wiki/orchestration/service.py",
)
_FORBIDDEN_LITERALS = (
    "conduit",
    "realworld",
    "fdf8821871d7",
    "cmd/ccagent",
    "cmd/ccprobe-control",
    "custom-probe",
    "not actively maintained",
    "不再积极维护",
    "拨测执行",
    "探测执行池",
)


def test_empty_cite_parens_keep_code_calls() -> None:
    text = (
        "注入 `Depends(get_current_user_authorizer())` 与 `Depends(f())`，"
        "并在围栏中保留时间戳。\n"
        "```go\nnow := time.Now()\npool.close()\n```\n"
        "完整的 Web 管理界面（）。\n"
    )
    cleaned = strip_empty_cite_parens(text)
    assert "Depends(get_current_user_authorizer())" in cleaned
    assert "Depends(f())" in cleaned
    assert "time.Now()" in cleaned
    assert "pool.close()" in cleaned
    assert "（）" not in cleaned


def test_unknown_process_does_not_delete_identity(tmp_path: Path) -> None:
    _write_probe_mains(tmp_path)
    (tmp_path / "README.md").write_text("# probe_exporter\n\n平台。\n", encoding="utf-8")
    (tmp_path / "go.mod").write_text("module github.com/x/probe_exporter\n", encoding="utf-8")
    allowed = derive_repo_process_names(tmp_path)
    assert "probe_exporter" in allowed
    text = "probe_exporter 是面向企业级的服务探针平台，支持**双模式探测**。\n"
    assert unknown_process_mentions(text, allowed) == []


def test_unknown_process_skips_types_and_databases(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    content = tmp_path / "zh" / "content"
    content.mkdir(parents=True)
    (content / "认证问题.md").write_text(
        "# 认证问题\n\n`UsersRepository` 负责读用户。"
        "PostgreSQL 是主数据库。Controller 作为请求入口。"
        "`ApplyAuth` 在 README 示例里出现。\n",
        encoding="utf-8",
    )
    offenders = handbook_unknown_process_offenders(content, root)
    flat = [name for names in offenders.values() for name in names]
    assert "UsersRepository" not in flat
    assert "PostgreSQL" not in flat
    assert "Controller" not in flat
    assert "ApplyAuth" not in flat


def test_example_binary_is_not_main_entry(tmp_path: Path) -> None:
    _write_probe_mains(tmp_path)
    example = tmp_path / "cmd" / "custom-probe"
    example.mkdir(parents=True)
    (example / "README.md").write_text("# Custom Probe 示例工具\n\n学习用。\n", encoding="utf-8")
    (example / "main.go").write_text(
        "package main\nfunc main() {\n"
        '    mux.HandleFunc("/probe", h)\n    http.ListenAndServe(":8080", mux)\n}\n',
        encoding="utf-8",
    )
    (tmp_path / "cmd" / "ccagent" / "main.go").write_text(
        "package main\nfunc main() {\n"
        "    ccagent.NewController(config).Run()\n"
        '    mux.HandleFunc("/healthz", h)\n    mux.HandleFunc("/api/v1/x", h)\n}\n',
        encoding="utf-8",
    )
    facts = derive_process_role_facts(tmp_path)
    assert "custom-probe" in facts
    assert "示例" in facts
    assert facts.count("主 REST/Web") == 1
    assert "ccagent" in facts and "REST/Web" in facts
    assert "不是被" not in facts
    assert "拨测" not in facts


def test_best_structured_attempt_is_kept(tmp_path: Path) -> None:
    (tmp_path / "apiauth.go").write_text("package api\nfunc Apply() {}\n", encoding="utf-8")
    good = _pad(
        "# 认证授权API\n\n## 简介\n\n"
        "当前可见的源码证据只覆盖令牌解析。"
        "完整说明令牌解析与控制器注册。<cite>apiauth.go:1-2</cite>\n"
        "## 核心组件\n\n控制器把凭证接入请求生命周期。\n",
        minimum=1100,
    )
    bad = "# 认证授权API\n\n没有结构。\n"
    provider = SequenceLLMProvider(
        [
            ChatResponse(content=good, model="mock"),
            ChatResponse(content=good, model="mock"),
            ChatResponse(content=bad, model="mock"),
        ]
    )
    composer = create_composer(provider=provider)
    composer.workspace_root = tmp_path
    output = None

    async def _run() -> None:
        nonlocal output
        output = await composer.compose_page(
            build_composer_input(_auth_page(), None, _context(tmp_path))
        )

    import asyncio

    asyncio.run(_run())
    assert output is not None
    assert output.rejected is False
    assert "## 简介" in output.markdown
    assert "<cite>" in output.markdown
    assert "没有结构" not in output.markdown


def test_meta_optional_de_is_flagged(tmp_path: Path) -> None:
    content = tmp_path / "zh" / "content"
    content.mkdir(parents=True)
    (content / "认证授权API.md").write_text(
        _pad("# 认证授权API\n\n## 简介\n\n当前可见的源码证据只覆盖令牌解析。\n"),
        encoding="utf-8",
    )
    offenders = handbook_reader_hygiene_offenders(content, tmp_path)
    assert offenders.get("evidence_meta_talk")


def test_role_section_gated_on_derived_facts(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    page = _page(
        "module-relationships",
        "模块关系",
        WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
        "架构设计/模块关系.md",
    )
    markdown = _pad("# 模块关系\n\n## 简介\n\nFastAPI 路由与仓储协作。\n")
    out = _service(root)._enforce_qoder_page_contract(page, markdown, None, add_mermaid=False)
    assert "角色说明" not in out
    assert "进程角色见整体架构概览" not in out


def test_readme_note_is_found_by_structure(tmp_path: Path) -> None:
    (tmp_path / "README.rst").write_text(
        ".. image:: logo.png\n\n----------\n\n"
        "**NOTE**: This repository is complete.\n\nQuickstart\n----------\n",
        encoding="utf-8",
    )
    cite = cite_readme_supporting_line(tmp_path, "README.rst", "产品身份不再积极维护")
    assert cite == "<cite>README.rst:5-5</cite>"


def test_alembic_revision_is_discovered(tmp_path: Path) -> None:
    versions = tmp_path / "app" / "db" / "migrations" / "versions"
    versions.mkdir(parents=True)
    (versions / "aaaa_small.py").write_text("def upgrade():\n    pass\n", encoding="utf-8")
    (versions / "bbbb_main.py").write_text(
        "def upgrade():\n    op.create_table('a')\n    op.create_table('b')\n",
        encoding="utf-8",
    )
    assert find_alembic_revision_rel(tmp_path).endswith("bbbb_main.py")


def test_route_cite_realigns_to_registration(tmp_path: Path) -> None:
    (tmp_path / "controller.go").write_text(
        "\n" * 54
        + 'mux.HandleFunc("/probe/result/list", list)\n'
        + "\n" * 80
        + 'path := "/probe/result/list"\n',
        encoding="utf-8",
    )
    markdown = "查询 `/probe/result/list` <cite>controller.go:136-136</cite>\n"
    out = realign_route_registration_cites(markdown, tmp_path)
    assert "<cite>controller.go:55-55</cite>" in out


def test_no_repo_specific_literals_in_audited_source() -> None:
    repo = Path(__file__).resolve().parents[1]
    hits: list[str] = []
    for rel in _FORBIDDEN_SOURCE:
        text = (repo / rel).read_text(encoding="utf-8")
        for token in _FORBIDDEN_LITERALS:
            if token in text:
                hits.append(f"{rel}:{token}")
    assert hits == []


def test_generator_version_is_r17() -> None:
    assert COMPOSER_GENERATOR_VERSION.startswith("handbook-r17-")


@pytest.mark.asyncio
async def test_meta_still_rejects_after_retries(tmp_path: Path) -> None:
    meta = _pad("# 认证授权API\n\n## 简介\n\n当前可见的源码证据只覆盖 Bearer。\n")
    provider = SequenceLLMProvider([ChatResponse(content=meta, model="mock") for _ in range(3)])
    composer = create_composer(provider=provider)
    composer.workspace_root = tmp_path
    output = await composer.compose_page(
        build_composer_input(_auth_page(), None, _context(tmp_path))
    )
    assert provider.call_count == 3
    assert output.rejected is True
    assert output.rejection_reason == EVIDENCE_META_REJECTION
