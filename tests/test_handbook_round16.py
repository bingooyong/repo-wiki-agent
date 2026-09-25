"""Round 16: derived roles, clause negation, meta retry-fail, structure, cites."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo_wiki.evidence.ranking import EvidenceCandidate, PageEvidenceBinding
from repo_wiki.generator.adjacent_cites import (
    attach_adjacent_cites,
    realign_irrelevant_cites,
)
from repo_wiki.generator.compose_evidence import (
    generator_role_contradictions,
    prose_role_contradictions,
)
from repo_wiki.generator.composer import (
    build_composer_input,
    create_composer,
)
from repo_wiki.generator.composer_cache import COMPOSER_GENERATOR_VERSION
from repo_wiki.generator.process_roles import (
    derive_process_role_facts,
    derive_repo_process_names,
    strip_unknown_process_clauses,
    unknown_process_mentions,
)
from repo_wiki.llm.models import ChatResponse
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.planner.schema import WikiTaxonomyCategory
from repo_wiki.verifier.handbook import (
    EVIDENCE_META_REJECTION,
    handbook_reader_hygiene_offenders,
    handbook_unknown_process_offenders,
)
from tests.test_handbook_round10 import _fastapi_repo, _go_repo, _page, _render, _service
from tests.test_handbook_round14 import _arch_page, _context
from tests.test_handbook_round15 import (
    _EVENT_ARCH_ATTEMPT0,
    _EVENT_ARCH_HANDBOOK,
    _OVERVIEW_ATTEMPT0,
    _auth_page,
    _write_custom_probe_sources,
)
from tests.test_llm_compose_retry import SequenceLLMProvider

_COMMA_FALSE_NEG_A = "ccagent 不是 gRPC 控制面，它负责隧道客户端启动。"
_COMMA_FALSE_NEG_B = "ccagent 不作为控制面，而作为隧道客户端。"

_TINY_IDE = """# IDE配置

面向企业级的服务探针拨测与结果导出平台，IDE 配置需围绕双模式探测进行准备，开发者应先确认本地工具链与目标子命令一致，避免出现编译通过但无法与 Control/Agen
"""

_NO_H1_TOC = """## 目录

1. 简介

## 简介

本页说明认证授权入口如何从 HTTP 头提取令牌，并继续用足够长的中文段落覆盖控制器注册、中间件与错误透传，避免验证器因结构残缺而拒绝。
"""

_META_AVAILABLE = (
    "# 认证授权API\n\n## 简介\n\n"
    "当前可用源码证据只覆盖 Bearer Token 解析。"
    "页面继续用足够长的中文段落说明认证入口、令牌解析以及控制器如何把凭证接入请求生命周期，"
    "并补充路由注册、错误透传与调用关系，避免验证器因正文过短而拒绝。\n"
)

_META_SCOPE = (
    "# 数据库迁移\n\n## 简介\n\n"
    "本页限定在提供的证据范围内描述迁移。"
    "仓库未在提供的证据中体现的会话管理不在本页展开。"
    "页面继续用足够长的中文段落说明 upgrade、create_table 与回滚顺序，"
    "并补充表之间的外键与时间戳策略，避免验证器因正文过短而拒绝。\n"
)


def _pad(text: str, minimum: int = 820) -> str:
    extra = "页面继续用足够长的中文段落说明模块边界、调用关系以及控制面与采集端如何协作。"
    body = text.rstrip()
    while len(body) < minimum:
        body += extra
    return body + "\n"


def _write_probe_mains(root: Path) -> None:
    (root / "cmd" / "ccagent").mkdir(parents=True, exist_ok=True)
    (root / "cmd" / "probe-agent").mkdir(parents=True, exist_ok=True)
    (root / "cmd" / "ccprobe-control").mkdir(parents=True, exist_ok=True)
    (root / "cmd" / "ccagent" / "main.go").write_text(
        "package main\n\nfunc main() {\n    ccagent.NewController(config).Run()\n}\n",
        encoding="utf-8",
    )
    (root / "cmd" / "probe-agent" / "main.go").write_text(
        "// probe-agent is the database-independent CC-Probe data-plane process.\n"
        "package main\n\n"
        "// schedulerConfig sizes the probe execution pool.\n"
        "type schedulerConfig struct{}\n\n"
        "// Transport selects grpc (tunnel client) or http.\n"
        "func DialContext() {}\n"
        "func main() {}\n",
        encoding="utf-8",
    )
    (root / "cmd" / "ccprobe-control" / "main.go").write_text(
        "// ccprobe-control is a small control-plane publisher.\n"
        "package main\n\n"
        'var grpcListen = "gRPC EstablishTunnel listen address"\n'
        "func main() {}\n",
        encoding="utf-8",
    )


def test_role_facts_are_derived_from_cmd_comments(tmp_path: Path) -> None:
    _write_probe_mains(tmp_path)
    facts = derive_process_role_facts(tmp_path)
    assert "probe-agent" in facts
    assert "数据面" in facts
    assert "探测执行池" in facts
    assert "ccprobe-control" in facts and "隧道" in facts
    assert "ccagent" in facts and "REST/Web" in facts
    assert "必须" not in facts and "禁止" not in facts and "前者" not in facts
    composer = create_composer()
    composer.workspace_root = tmp_path
    assert composer._process_role_facts() == facts
    # Hard-coded binary names stay out of the composer role-fact helper.
    from repo_wiki.generator import composer as composer_mod
    from repo_wiki.generator import process_roles as roles_mod

    composer_src = Path(composer_mod.__file__).read_text(encoding="utf-8")
    roles_src = Path(roles_mod.__file__).read_text(encoding="utf-8")
    for banned in ('"ccagent"', "'ccagent'", '"probe-agent"', '"ccprobe-control"'):
        assert banned not in roles_src
        assert banned not in composer_src.split("def _process_role_facts")[1].split("def ")[0]


def test_fastapi_repo_has_no_process_role_facts(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    assert derive_process_role_facts(root) == ""
    composer = create_composer()
    composer.workspace_root = root
    page = _page(
        "event-architecture",
        "事件驱动架构",
        WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
        "架构设计/事件驱动架构.md",
    )
    prompt = composer._build_compose_prompt(
        build_composer_input(page, None, _context(root)),
        composer._build_context(build_composer_input(page, None, _context(root))),
    )
    for name in ("ccagent", "probe-agent", "ccprobe-control"):
        assert name not in prompt


def test_unknown_process_verifier_uses_repo_name_list(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    content = tmp_path / "zh" / "content"
    content.mkdir(parents=True)
    (content / "事件驱动架构.md").write_text(
        "# 事件驱动架构\n\n在本仓库内，ccagent 承担主 REST/Web 服务。\n",
        encoding="utf-8",
    )
    (content / "模块关系.md").write_text(
        "# 模块关系\n\n本仓库并不存在独立的 probe-agent 或 ccprobe-control 组件。\n",
        encoding="utf-8",
    )
    allowed = derive_repo_process_names(root)
    assert "ccagent" not in allowed
    offenders = handbook_unknown_process_offenders(content, root)
    assert offenders
    cleaned = strip_unknown_process_clauses(
        "在本仓库内，ccagent 承担主 REST/Web 服务与管理入口职责。本页只讲 FastAPI 表结构。\n",
        allowed,
    )
    assert "ccagent" not in cleaned
    assert "FastAPI" in cleaned
    assert unknown_process_mentions(cleaned, allowed) == []


def test_role_negation_is_clause_scoped() -> None:
    for sentence in (_EVENT_ARCH_ATTEMPT0, _OVERVIEW_ATTEMPT0, _EVENT_ARCH_HANDBOOK):
        assert prose_role_contradictions(sentence) == [], sentence
        assert generator_role_contradictions(sentence, _arch_page()) == [], sentence
    for sentence in (_COMMA_FALSE_NEG_A, _COMMA_FALSE_NEG_B):
        assert "ccagent-as-tunnel-client" in prose_role_contradictions(sentence), sentence


@pytest.mark.asyncio
async def test_meta_talk_second_retry_then_fails(tmp_path: Path) -> None:
    provider = SequenceLLMProvider(
        [
            ChatResponse(content=_pad(_META_AVAILABLE), model="mock"),
            ChatResponse(content=_pad(_META_AVAILABLE), model="mock"),
            ChatResponse(content=_pad(_META_AVAILABLE), model="mock"),
        ]
    )
    composer = create_composer(provider=provider)
    composer.workspace_root = tmp_path
    output = await composer.compose_page(
        build_composer_input(_auth_page(), None, _context(tmp_path))
    )
    assert provider.call_count == 3
    assert output.rejected is True
    assert output.rejection_reason == EVIDENCE_META_REJECTION


def test_hygiene_flags_available_source_evidence_and_scope(tmp_path: Path) -> None:
    content = tmp_path / "zh" / "content"
    content.mkdir(parents=True)
    (content / "认证授权API.md").write_text(_pad(_META_AVAILABLE), encoding="utf-8")
    (content / "数据库迁移.md").write_text(_pad(_META_SCOPE), encoding="utf-8")
    offenders = handbook_reader_hygiene_offenders(content, tmp_path)
    assert offenders.get("evidence_meta_talk")


def test_truncation_is_mid_word_not_missing_period() -> None:
    from repo_wiki.verifier.handbook import handbook_page_is_truncated

    cut = "# IDE配置\n\n准备本地工具链，避免编译通过但无法与 Control/Agen"
    complete = "# 健康检查\n\n" + ("探针周期上报健康状态，控制面按心跳判断在线。" * 10)
    assert handbook_page_is_truncated(cut) is True
    assert handbook_page_is_truncated(complete) is False


def test_hygiene_flags_missing_h1_and_tiny_body(tmp_path: Path) -> None:
    content = tmp_path / "zh" / "content"
    content.mkdir(parents=True)
    (content / "认证授权API.md").write_text(_NO_H1_TOC, encoding="utf-8")
    (content / "IDE配置.md").write_text(_TINY_IDE, encoding="utf-8")
    offenders = handbook_reader_hygiene_offenders(content, tmp_path)
    assert offenders.get("missing_h1")
    assert offenders.get("tiny_body")


def test_normalize_repairs_h1_when_reply_starts_with_toc() -> None:
    composer = create_composer()
    out = composer._normalize_markdown_response(_NO_H1_TOC, "认证授权API")
    assert out.lstrip().startswith("# 认证授权API")


@pytest.mark.asyncio
async def test_tiny_truncated_reply_is_rejected(tmp_path: Path) -> None:
    provider = SequenceLLMProvider(
        [
            ChatResponse(content=_TINY_IDE, model="mock"),
            ChatResponse(content=_TINY_IDE, model="mock"),
            ChatResponse(content=_TINY_IDE, model="mock"),
        ]
    )
    composer = create_composer(provider=provider)
    composer.workspace_root = tmp_path
    page = _page(
        "ide-setup",
        "IDE配置",
        WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
        "开发指南/IDE配置.md",
    )
    output = await composer.compose_page(build_composer_input(page, None, _context(tmp_path)))
    assert provider.call_count == 3
    assert output.rejected is True


def test_realign_drops_cite_when_identifier_missing(tmp_path: Path) -> None:
    _write_custom_probe_sources(tmp_path)
    markdown = (
        "# 核心服务\n\n`AuthGateway` 负责认证与安全。<cite>cmd/custom-probe/main.go:42-59</cite>\n"
    )
    out = realign_irrelevant_cites(
        markdown,
        [
            "<cite>cmd/custom-probe/main.go:42-59</cite>",
            "<cite>cmd/custom-probe/main.go:105-145</cite>",
        ],
        tmp_path,
    )
    assert "cmd/custom-probe/main.go:42-59" not in out
    assert "cmd/custom-probe/main.go:105-145" not in out
    assert "认证与安全" in out


def test_summary_paragraph_does_not_get_citation_only_line(tmp_path: Path) -> None:
    _write_custom_probe_sources(tmp_path)
    markdown = (
        "# 核心服务\n\n"
        "服务的总体入口分别落在 `controller.go` 与 `cmd/ccagent/main.go`，"
        "再由多个内部包分担路由与探测。\n"
    )
    out = attach_adjacent_cites(
        markdown,
        ["<cite>cmd/custom-probe/serv_reflect.go:26-31</cite>"],
        workspace_root=tmp_path,
        strict_match=False,
    )
    assert "serv_reflect.go:26-31" not in out


def test_intro_cites_search_readme_and_upgrade_range(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    (root / "README.rst").write_text(
        ".. image:: logo.png\n\n"
        + "\n".join(f"badge {i}" for i in range(1, 26))
        + "\n\n**NOTE**: This repository is not actively maintained "
        "because this example is quite complete and does its primary goal "
        "- passing Conduit testsuite.\n",
        encoding="utf-8",
    )
    versions = root / "app" / "db" / "migrations" / "versions"
    mig = versions / "fdf8821871d7_main_tables.py"
    pad = ["# pad"] * 53
    body = (
        pad
        + ['    op.create_table("users")']
        + ["    more = 1"] * 140
        + ["", "def upgrade():", "    create_users_table()", "", "def downgrade():", "    pass"]
    )
    mig.write_text("\n".join(body) + "\n", encoding="utf-8")
    page = _page(
        "database-architecture",
        "数据库架构",
        WikiTaxonomyCategory.DATA_MODELS,
        "数据模型/数据库架构/数据库架构.md",
    )
    markdown = (
        "# 数据库架构\n\n"
        "## 简介\n\n"
        "仓库本身已不再积极维护，因为该示例已完整覆盖 Conduit 测试套件目标。\n"
        "<cite>app/models/common.py:6-17</cite>\n\n"
        "## 核心数据模型\n\n"
        "迁移文件建立了 7 张业务表。\n"
        "<cite>app/models/domain/articles.py:8-16</cite>\n"
    )
    binding = PageEvidenceBinding(
        page_id=page.page_id,
        doc_type="schema",
        candidates=[
            EvidenceCandidate(
                evidence_id=1,
                span=EvidenceSpanRecord(
                    digest="common",
                    file_path="app/models/common.py",
                    line_start=6,
                    line_end=17,
                    language="python",
                    symbol="DateTimeModelMixin",
                    span_text="class DateTimeModelMixin",
                ),
                score=2.0,
                match_signals=["file"],
                citation_order=0,
            ),
        ],
        bound_count=1,
    )
    out = _service(root)._enforce_qoder_page_contract(page, markdown, binding, add_mermaid=False)
    intro = out.split("## 核心数据模型")[0]
    assert "README.rst:1-10" not in intro
    assert "README.rst:28" in intro or "NOTE" in (root / "README.rst").read_text()
    assert "fdf8821871d7_main_tables.py:1-19" not in out
    assert "fdf8821871d7_main_tables.py:54-" in out


def test_empty_cite_parens_are_stripped() -> None:
    from repo_wiki.evidence.citation_renderer import strip_empty_cite_parens

    assert "界面。" in strip_empty_cite_parens("完整的 Web 管理界面（）。")
    assert "（）" not in strip_empty_cite_parens("完整的 Web 管理界面（）。")


def test_prompt_does_not_echo_reader_facing_line(tmp_path: Path) -> None:
    composer = create_composer()
    composer.workspace_root = tmp_path
    prompt = composer._build_compose_prompt(
        build_composer_input(_auth_page(), None, _context(tmp_path)),
        composer._build_context(build_composer_input(_auth_page(), None, _context(tmp_path))),
    )
    assert "正文面向仓库读者" not in prompt
    assert "本页面向仓库读者" not in prompt
    assert "当前证据" not in prompt
    assert "证据范围" not in prompt
    assert COMPOSER_GENERATOR_VERSION.startswith("handbook-r16-")


def test_contract_keeps_labeled_bullet_lists(tmp_path: Path) -> None:
    root = _go_repo(tmp_path)
    page = _page(
        "core-services",
        "核心服务",
        WikiTaxonomyCategory.CORE_SERVICES,
        "核心功能/核心服务.md",
    )
    markdown = (
        "# 核心服务\n\n## 简介\n\n"
        + ("仓库提供双模式探测与结果导出。" * 12)
        + "\n\n- **数据库依赖**：探测结果写入关系库。\n"
        "- **导出通道**：支持文件与远程接收端。\n"
    )
    out = _render(_service(root), page, markdown, None, add_mermaid=False)
    assert "\n- **数据库依赖**" in out
    assert "。 **数据库依赖**" not in out


def test_generator_version_is_r16() -> None:
    assert COMPOSER_GENERATOR_VERSION == "handbook-r16-20260925"
