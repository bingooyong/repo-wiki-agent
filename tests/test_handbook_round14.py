"""Round 14: roles, page-relative links, prompt hygiene, cite gaps, cite relevance."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo_wiki.evidence.citation_renderer import normalize_citation_markup
from repo_wiki.evidence.ranking import EvidenceCandidate, PageEvidenceBinding
from repo_wiki.generator.adjacent_cites import attach_adjacent_cites
from repo_wiki.generator.composer import (
    ComposerContext,
    build_composer_input,
    create_composer,
)
from repo_wiki.generator.deterministic_sections import (
    rewrite_architecture_role_claims,
    strip_header_only_cites,
)
from repo_wiki.llm.models import ChatResponse
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory
from repo_wiki.verifier.handbook import handbook_reader_hygiene_offenders
from tests.test_handbook_round10 import _go_repo, _page, _render, _service
from tests.test_llm_compose_retry import SequenceLLMProvider

_ARCH_WRONG = """# 整体架构概览

## 简介

本页是 probe_exporter 仓库的架构总览。仓库由两个核心二进制 `ccprobe-control` 与 `ccagent` 组成：前者作为主 REST/Web 服务与管理入口，并以 gRPC 通道承载隧道接入；后者运行在受测主机侧，作为隧道客户端与采集/上报端点。`cmd/ccagent/`：负责隧道客户端启动与初始化。页面继续用足够长的中文段落说明模块边界、调用关系以及控制面与采集端如何协作，避免验证器因正文过短而拒绝。
"""

_ARCH_OK = """# 整体架构概览

## 简介

`ccagent` 是主 REST/Web 服务与管理入口，对外提供 HTTP。`probe-agent` 是隧道客户端，主动拨号连向 `ccprobe-control`。`ccprobe-control` 是 gRPC 控制面，不承担 REST 管理入口。三大入口各自独立启动，不要把隧道客户端写到 ccagent 上。页面继续补充模块边界与调用关系，使正文超过验证器要求的最短篇幅。
"""


def _arch_page() -> WikiPagePlan:
    return WikiPagePlan(
        page_id="architecture-overview",
        title="整体架构概览",
        category=WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
        output_path="架构设计/整体架构概览.md",
    )


def _overview_page() -> WikiPagePlan:
    return WikiPagePlan(
        page_id="project-overview",
        title="项目概述",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
        output_path="项目概述/项目概述.md",
    )


def _context(root: Path) -> ComposerContext:
    return ComposerContext(
        repository_name="probe_exporter",
        primary_language="go",
        framework="go",
        repository_root=str(root),
    )


def test_architecture_and_overview_prompts_state_roles(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    composer = create_composer()
    composer.workspace_root = root
    arch_input = build_composer_input(_arch_page(), None, _context(root))
    arch_prompt = composer._build_compose_prompt(arch_input, composer._build_context(arch_input))
    assert "前者" in arch_prompt and "后者" in arch_prompt
    assert "主 REST/Web" in arch_prompt
    assert "probe-agent" in arch_prompt and "隧道客户端" in arch_prompt
    assert "ccprobe-control" in arch_prompt
    overview_input = build_composer_input(_overview_page(), None, _context(root))
    overview_prompt = composer._build_compose_prompt(
        overview_input, composer._build_context(overview_input)
    )
    assert "被 ccagent 调度" in overview_prompt
    assert "不是被 ccagent 调度" in overview_prompt or "并非被 ccagent 调度" in overview_prompt
    assert "拨号" in overview_prompt or "连向" in overview_prompt


@pytest.mark.asyncio
async def test_architecture_role_contradiction_reasks_instead_of_regex(
    tmp_path: Path,
) -> None:
    root = _go_repo(tmp_path)
    provider = SequenceLLMProvider(
        [
            ChatResponse(content=_ARCH_WRONG, model="mock"),
            ChatResponse(content=_ARCH_OK, model="mock"),
        ]
    )
    composer = create_composer(provider=provider)
    composer.workspace_root = root
    output = await composer.compose_page(build_composer_input(_arch_page(), None, _context(root)))
    assert provider.call_count == 2
    assert output.rejected is False
    assert "后者" not in output.markdown or "隧道客户端" not in output.markdown.split("后者")[-1]
    assert rewrite_architecture_role_claims(_ARCH_WRONG) == _ARCH_WRONG


@pytest.mark.asyncio
async def test_architecture_role_retry_keeps_markdown_without_fallback(
    tmp_path: Path,
) -> None:
    root = _go_repo(tmp_path)
    provider = SequenceLLMProvider(
        [
            ChatResponse(content=_ARCH_WRONG, model="mock"),
            ChatResponse(content=_ARCH_WRONG, model="mock"),
        ]
    )
    composer = create_composer(provider=provider)
    composer.workspace_root = root
    output = await composer.compose_page(build_composer_input(_arch_page(), None, _context(root)))
    assert provider.call_count == 2
    assert output.rejected is False
    assert "前者作为主 REST/Web" in output.markdown
    assert "负责隧道客户端启动" in output.markdown


def test_architecture_contract_does_not_regex_rewrite_former_latter(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    page = _page(
        "architecture-overview",
        "整体架构概览",
        WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
        "架构设计/整体架构概览.md",
    )
    out = _render(_service(root), page, _ARCH_WRONG, _context(root), add_mermaid=False)
    assert "前者作为主 REST/Web" in out
    assert "负责隧道客户端启动" in out


def test_page_relative_repo_links_become_code_spans(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    (root / "docs").mkdir(exist_ok=True)
    (root / "test").mkdir(exist_ok=True)
    (root / "test" / "FINAL_TESTING_REPORT.md").write_text("# report\n", encoding="utf-8")
    page = _page(
        "testing-guide",
        "测试指南",
        WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
        "开发指南/测试指南.md",
    )
    markdown = (
        "# 测试指南\n\n"
        "打开 [docs/](./docs/) 与 "
        "[test/FINAL_TESTING_REPORT.md](./test/FINAL_TESTING_REPORT.md) 核对用例。\n"
    )
    out = _render(_service(root), page, markdown, _context(root), add_mermaid=False)
    assert "](./docs/)" not in out
    assert "](./test/FINAL_TESTING_REPORT.md)" not in out
    assert "`docs/`" in out
    assert "`test/FINAL_TESTING_REPORT.md`" in out


def test_root_readme_rule_cannot_be_echoed() -> None:
    from repo_wiki.generator import composer

    text = Path(composer.__file__).read_text(encoding="utf-8")
    assert "引用时写" not in text
    assert "引用时使用" not in text


def test_hygiene_flags_cite_instruction_echo(tmp_path: Path) -> None:
    content = tmp_path / "zh" / "content"
    content.mkdir(parents=True)
    (content / "核心服务.md").write_text(
        "# 核心服务\n\n> NOTE：本仓库根 README 是 `README.rst`，引用时使用 cite 形式。\n",
        encoding="utf-8",
    )
    (content / "概述.md").write_text(
        "# 概述\n\n引用时写 `<cite>README.rst:1-3</cite>`。\n",
        encoding="utf-8",
    )
    offenders = handbook_reader_hygiene_offenders(content, tmp_path)
    assert offenders.get("instruction_voice")


def test_contract_strips_readme_cite_instruction_note(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    (root / "README.rst").write_text("hello\n", encoding="utf-8")
    (root / "README.md").unlink()
    page = _page(
        "core-service",
        "核心服务",
        WikiTaxonomyCategory.CORE_SERVICES,
        "核心服务/核心服务.md",
    )
    markdown = (
        "# 核心服务\n\n"
        "应用以 FastAPI 为运行时，连接 PostgreSQL 作为后端存储。\n\n"
        "> NOTE：本仓库根 README 是 `README.rst`，引用时使用  形式。\n"
    )
    out = _render(_service(root), page, markdown, None, add_mermaid=False)
    assert "引用时使用" not in out
    assert "本仓库根 README 是" not in out


def test_backtick_file_line_keeps_filename_and_dropped_cite_leaves_no_gap(
    tmp_path: Path,
) -> None:
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("version: '3'\nservices:\n  app:\n    image: x\n", encoding="utf-8")
    text = "若 CI 与本地表现不一致，则需注意 `docker-compose.yml:1-2` 指定的 Compose 文件版本。"
    out = normalize_citation_markup(text, tmp_path)
    out = strip_header_only_cites(out, tmp_path)
    assert "需注意 `docker-compose.yml`" in out
    assert "需注意  指定的" not in out
    dropped = normalize_citation_markup(
        "部署前需按其说明应用 <cite>missing.md:1-3</cite>。", tmp_path
    )
    assert "应用 。" not in dropped
    assert "应用。" in dropped or "应用 `" in dropped


def test_attach_adjacent_cites_requires_identifier_in_range(tmp_path: Path) -> None:
    events = tmp_path / "app" / "db"
    users = tmp_path / "app" / "models" / "domain"
    events.mkdir(parents=True)
    users.mkdir(parents=True)
    (events / "events.py").write_text(
        "\n".join(
            ["# pad"] * 7 + ["async def connect_to_db(app):", "    return 1"] + ["# pad"] * 15
        ),
        encoding="utf-8",
    )
    (users / "users.py").write_text(
        "\n".join(
            ["# pad"] * 14
            + [
                "class UserInDB:",
                "    def check_password(self, password):",
                "        return verify_password(password)",
            ]
            + ["# pad"] * 10
        ),
        encoding="utf-8",
    )
    markdown = (
        "# 核心服务\n\n`UserInDB.check_password` 使用 `security.verify_password` 校验哈希。\n"
    )
    rewritten = attach_adjacent_cites(
        markdown,
        ["<cite>app/db/events.py:8-19</cite>", "<cite>app/models/domain/users.py:15-24</cite>"],
        workspace_root=tmp_path,
    )
    assert "app/models/domain/users.py" in rewritten
    assert "app/db/events.py" not in rewritten


def test_realign_core_service_cites_to_matching_evidence(tmp_path: Path) -> None:
    events = tmp_path / "app" / "db"
    users = tmp_path / "app" / "models" / "domain"
    events.mkdir(parents=True)
    users.mkdir(parents=True)
    (events / "events.py").write_text(
        "\n".join(
            ["# pad"] * 7 + ["async def connect_to_db(app):", "    return 1"] + ["# pad"] * 15
        ),
        encoding="utf-8",
    )
    (users / "users.py").write_text(
        "\n".join(
            ["# pad"] * 14
            + ["class UserInDB:", "    def check_password(self, password):", "        return True"]
            + ["# pad"] * 10
        ),
        encoding="utf-8",
    )
    markdown = (
        "# 核心服务\n\n"
        "`UserInDB.check_password` 使用 `security.verify_password` 校验哈希。"
        "<cite>app/db/events.py:8-19</cite>\n"
    )
    from repo_wiki.generator.adjacent_cites import realign_irrelevant_cites

    out = realign_irrelevant_cites(
        markdown,
        ["<cite>app/db/events.py:8-19</cite>", "<cite>app/models/domain/users.py:15-24</cite>"],
        tmp_path,
    )
    assert "app/models/domain/users.py" in out
    assert "app/db/events.py:8-19" not in out


def test_contract_realigns_core_service_and_schema_cites(tmp_path: Path) -> None:
    root = tmp_path
    events = root / "app" / "db"
    users = root / "app" / "models" / "domain"
    comments = root / "app" / "models" / "domain"
    versions = root / "app" / "db" / "migrations" / "versions"
    events.mkdir(parents=True)
    users.mkdir(parents=True)
    versions.mkdir(parents=True)
    (events / "events.py").write_text(
        "\n".join(
            ["# pad"] * 7 + ["async def connect_to_db(app):", "    return 1"] + ["# pad"] * 15
        ),
        encoding="utf-8",
    )
    (users / "users.py").write_text(
        "\n".join(
            ["# pad"] * 14
            + ["class UserInDB:", "    def check_password(self, password):", "        return True"]
            + ["# pad"] * 10
        ),
        encoding="utf-8",
    )
    (comments / "comments.py").write_text(
        "\n".join(["# pad"] * 5 + ["class Comment:", "    body = ''"] + ["# pad"] * 10),
        encoding="utf-8",
    )
    (versions / "fdf8821871d7_main_tables.py").write_text(
        "\n".join(["favorites = Table('favorites')"] + ["# pad"] * 30),
        encoding="utf-8",
    )
    (root / "README.md").write_text("# demo\n", encoding="utf-8")
    service = _service(root)
    users_span = EvidenceSpanRecord(
        digest="users",
        file_path="app/models/domain/users.py",
        line_start=15,
        line_end=24,
        language="python",
        symbol="check_password",
        span_text="def check_password",
    )
    events_span = EvidenceSpanRecord(
        digest="events",
        file_path="app/db/events.py",
        line_start=8,
        line_end=19,
        language="python",
        symbol="connect_to_db",
        span_text="async def connect_to_db",
    )
    fav_span = EvidenceSpanRecord(
        digest="fav",
        file_path="app/db/migrations/versions/fdf8821871d7_main_tables.py",
        line_start=1,
        line_end=20,
        language="python",
        symbol="favorites",
        span_text="favorites",
    )
    comments_span = EvidenceSpanRecord(
        digest="comments",
        file_path="app/models/domain/comments.py",
        line_start=6,
        line_end=8,
        language="python",
        symbol="Comment",
        span_text="class Comment",
    )
    core_page = _page(
        "core-service",
        "核心服务",
        WikiTaxonomyCategory.CORE_SERVICES,
        "核心服务/核心服务.md",
    )
    core_binding = PageEvidenceBinding(
        page_id=core_page.page_id,
        doc_type="core",
        candidates=[
            EvidenceCandidate(
                evidence_id=1,
                span=events_span,
                score=2.0,
                match_signals=["file"],
                citation_order=0,
            ),
            EvidenceCandidate(
                evidence_id=2,
                span=users_span,
                score=2.0,
                match_signals=["file"],
                citation_order=1,
            ),
        ],
        bound_count=2,
    )
    core_md = (
        "# 核心服务\n\n"
        "`UserInDB.check_password` 使用 `security.verify_password` 校验哈希。"
        "<cite>app/db/events.py:8-19</cite>\n"
    )
    core_out = service._enforce_qoder_page_contract(
        core_page, core_md, core_binding, add_mermaid=False
    )
    assert "app/models/domain/users.py" in core_out
    assert "app/db/events.py:8-19" not in core_out
    schema_page = _page(
        "database-schema",
        "数据库架构",
        WikiTaxonomyCategory.DATA_MODELS,
        "数据模型/数据库架构/数据库架构.md",
    )
    schema_binding = PageEvidenceBinding(
        page_id=schema_page.page_id,
        doc_type="schema",
        candidates=[
            EvidenceCandidate(
                evidence_id=1,
                span=comments_span,
                score=2.0,
                match_signals=["file"],
                citation_order=0,
            ),
            EvidenceCandidate(
                evidence_id=2,
                span=fav_span,
                score=2.0,
                match_signals=["file"],
                citation_order=1,
            ),
        ],
        bound_count=2,
    )
    schema_md = (
        "# 数据库架构\n\n"
        "`favorites` 记录用户对文章的收藏，使用复合主键避免重复收藏。"
        "<cite>app/models/domain/comments.py:6-8</cite>\n"
    )
    schema_out = service._enforce_qoder_page_contract(
        schema_page, schema_md, schema_binding, add_mermaid=False
    )
    assert "fdf8821871d7_main_tables.py" in schema_out
    assert "app/models/domain/comments.py:6-8" not in schema_out
