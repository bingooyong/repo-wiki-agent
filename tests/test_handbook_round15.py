"""Round 15: role negation, prompt echo, reader meta, cite realign, schema owner."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo_wiki.evidence.ranking import EvidenceCandidate, PageEvidenceBinding
from repo_wiki.generator.adjacent_cites import (
    attach_adjacent_cites,
    realign_irrelevant_cites,
    sentence_identifiers,
)
from repo_wiki.generator.compose_evidence import (
    generator_role_contradictions,
    prose_role_contradictions,
)
from repo_wiki.generator.composer import (
    build_composer_input,
    create_composer,
)
from repo_wiki.llm.models import ChatResponse
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory
from repo_wiki.verifier.handbook import handbook_reader_hygiene_offenders
from tests.test_handbook_round10 import _fastapi_repo, _page, _render, _service
from tests.test_handbook_round14 import _ARCH_WRONG, _arch_page, _context, _overview_page
from tests.test_llm_compose_retry import SequenceLLMProvider

# Real 25o cassette attempt-0 sentences (negated, should not trip the role check).
_EVENT_ARCH_ATTEMPT0 = (
    "ccagent 主循环只通过 `NewController(config).Run()` 触发后续事件处理，"
    "不在此入口承担隧道客户端或 DNS 解析以外的初始化职责"
)
_OVERVIEW_ATTEMPT0 = (
    "不要把 ccagent 误认为边缘 Agent 或隧道客户端：ccagent 是主 REST/Web 服务，"
    "并在 Alpine 容器中通过 `GODEBUG=netdns=go` 规避 musl libc 兼容性问题"
)
_EVENT_ARCH_HANDBOOK = "cmd/ccagent 也并不承担隧道客户端启动的角色"

_FORMER_LATTER_SWAP = (
    "仓库由两个核心二进制 `ccprobe-control` 与 `ccagent` 组成："
    "前者作为主 REST/Web 服务与管理入口，并以 gRPC 通道承载隧道接入；"
    "后者运行在受测主机侧，作为隧道客户端与采集/上报端点。"
)
_CCAGENT_STARTS_TUNNEL = "`cmd/ccagent/`：负责隧道客户端启动与初始化。"

_AUTH_META = """# 认证授权API

## 简介

本页聚焦平台的认证授权 API 抽象层。`apiauth.go` 提供 `BearerToken` 等解析工具用于从 HTTP 头提取令牌，控制器层负责把这些凭证接入路由与请求生命周期。当前证据覆盖的是承载这些认证行为的最小可观察面。页面继续用足够长的中文段落说明认证入口、令牌解析以及控制器如何把凭证接入请求生命周期，避免验证器因正文过短而拒绝。
"""

_AUTH_OK = """# 认证授权API

## 简介

本页聚焦平台的认证授权 API 抽象层。`apiauth.go` 提供 `BearerToken` 等解析工具用于从 HTTP 头提取令牌，控制器层负责把这些凭证接入路由与请求生命周期。页面继续用足够长的中文段落说明认证入口、令牌解析以及控制器如何把凭证接入请求生命周期，避免验证器因正文过短而拒绝。
"""


def _auth_page() -> WikiPagePlan:
    return WikiPagePlan(
        page_id="authentication-authorization-api",
        title="认证授权API",
        category=WikiTaxonomyCategory.API_REFERENCE,
        output_path="API参考/认证授权API.md",
    )


def test_role_check_accepts_25o_negated_sentences() -> None:
    for sentence in (_EVENT_ARCH_ATTEMPT0, _OVERVIEW_ATTEMPT0, _EVENT_ARCH_HANDBOOK):
        assert prose_role_contradictions(sentence) == [], sentence
        assert generator_role_contradictions(sentence, _arch_page()) == [], sentence
        assert generator_role_contradictions(sentence, _overview_page()) == [], sentence


def test_role_check_still_fails_genuine_former_latter_swap() -> None:
    assert "ccagent-as-tunnel-client" in prose_role_contradictions(_FORMER_LATTER_SWAP)
    assert generator_role_contradictions(_ARCH_WRONG, _arch_page())
    assert "ccagent-as-tunnel-client" in prose_role_contradictions(_CCAGENT_STARTS_TUNNEL)


def test_overview_negated_not_scheduled_does_not_flag() -> None:
    ok = "需要注意 probe-agent 不是被 ccagent 调度的拨测执行单元，它独立拨号到 ccprobe-control 维持长连。"
    treated = "不要把 probe-agent 当作被 ccagent 调度的拨测执行单元：probe-agent 是隧道客户端。"
    assert generator_role_contradictions(ok, _overview_page()) == []
    assert generator_role_contradictions(treated, _overview_page()) == []
    wrong = "probe-agent 被 ccagent 调度执行拨测任务。"
    assert "probe-agent-scheduled-by-ccagent" in generator_role_contradictions(
        wrong, _overview_page()
    )


def test_role_check_still_fails_rather_than_tunnel_client() -> None:
    text = "ccagent 不是边缘 Agent，而是隧道客户端并主动拨号。"
    assert "ccagent-as-tunnel-client" in prose_role_contradictions(text)


def test_role_facts_are_positive_without_checklist() -> None:
    composer = create_composer()
    facts = composer._process_role_facts()
    for banned in ("必须", "不要", "禁止", "前者", "后者"):
        assert banned not in facts
    assert "ccagent 是主 REST/Web" in facts
    assert "probe-agent 是隧道客户端" in facts
    assert "ccprobe-control 是 gRPC" in facts
    from repo_wiki.generator import composer as composer_mod

    source = Path(composer_mod.__file__).read_text(encoding="utf-8")
    assert "进程角色必须分句写清" not in source
    assert "禁止写 cmd/ccagent" not in source
    assert "禁止用「前者" not in source


def test_hygiene_flags_role_prompt_echo(tmp_path: Path) -> None:
    content = tmp_path / "zh" / "content"
    content.mkdir(parents=True)
    (content / "项目概述.md").write_text(
        "# 项目概述\n\n进程角色必须分开理解：ccagent 是主 REST/Web 服务。\n",
        encoding="utf-8",
    )
    (content / "事件驱动架构.md").write_text(
        "# 事件驱动架构\n\n## 附录：检查项\n\n- 禁止写 cmd/ccagent 负责隧道客户端启动。\n",
        encoding="utf-8",
    )
    offenders = handbook_reader_hygiene_offenders(content, tmp_path)
    assert offenders.get("instruction_voice")


@pytest.mark.asyncio
async def test_negated_role_sentence_does_not_reask(tmp_path: Path) -> None:
    root = tmp_path
    (root / "cmd" / "ccagent").mkdir(parents=True)
    body = (
        "# 事件驱动架构\n\n## 简介\n\n"
        f"{_EVENT_ARCH_HANDBOOK}。页面继续用足够长的中文段落说明事件如何从控制面下发到探针，"
        "以及结果如何回写到主 REST 服务，避免验证器因正文过短而拒绝。\n"
    )
    provider = SequenceLLMProvider([ChatResponse(content=body, model="mock")])
    composer = create_composer(provider=provider)
    composer.workspace_root = root
    page = WikiPagePlan(
        page_id="event-architecture",
        title="事件驱动架构",
        category=WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
        output_path="架构设计/事件驱动架构.md",
    )
    output = await composer.compose_page(build_composer_input(page, None, _context(root)))
    assert provider.call_count == 1
    assert output.rejected is False
    assert "并不承担隧道客户端" in output.markdown


@pytest.mark.asyncio
async def test_evidence_meta_talk_reasks_and_is_not_stripped(tmp_path: Path) -> None:
    root = tmp_path
    provider = SequenceLLMProvider(
        [
            ChatResponse(content=_AUTH_META, model="mock"),
            ChatResponse(content=_AUTH_META, model="mock"),
        ]
    )
    composer = create_composer(provider=provider)
    composer.workspace_root = root
    output = await composer.compose_page(build_composer_input(_auth_page(), None, _context(root)))
    assert provider.call_count == 2
    assert output.rejected is False
    assert "当前证据覆盖的是" in output.markdown


def test_auth_prompt_asks_for_reader_facing_prose(tmp_path: Path) -> None:
    composer = create_composer()
    composer.workspace_root = tmp_path
    prompt = composer._build_compose_prompt(
        build_composer_input(_auth_page(), None, _context(tmp_path)),
        composer._build_context(build_composer_input(_auth_page(), None, _context(tmp_path))),
    )
    assert "面向" in prompt and "读者" in prompt
    assert "当前证据" not in prompt
    assert "证据片段" not in prompt


def test_contract_does_not_silently_delete_evidence_meta(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    page = _auth_page()
    out = _render(_service(root), page, _AUTH_META, None, add_mermaid=False)
    assert "当前证据覆盖的是" in out


def test_sentence_identifiers_use_head_not_generic_probe() -> None:
    ids = sentence_identifiers("`DeepModule.Probe` 进一步执行数据库检查。")
    assert "DeepModule" in ids
    assert "Probe" not in ids


def _write_custom_probe_sources(root: Path) -> None:
    probe = root / "cmd" / "custom-probe"
    probe.mkdir(parents=True)
    lines = [""] * 280
    for idx in range(42, 60):
        lines[idx - 1] = "type QuickModule struct{}"
    for idx in range(61, 80):
        lines[idx - 1] = "type DefaultModule struct{}"
    for idx in range(105, 146):
        lines[idx - 1] = "type DeepModule struct{}"
    for idx in range(220, 276):
        lines[idx - 1] = "type HTTPModule struct{}"
    (probe / "main.go").write_text("\n".join(lines) + "\n", encoding="utf-8")
    reflect_lines = [""] * 40
    for idx in range(26, 32):
        reflect_lines[idx - 1] = "type API struct{ Method string }"
    (probe / "serv_reflect.go").write_text("\n".join(reflect_lines) + "\n", encoding="utf-8")


def test_file_line_links_become_bullet_own_cites_not_neighbour(tmp_path: Path) -> None:
    _write_custom_probe_sources(tmp_path)
    markdown = (
        "# 核心服务\n\n"
        "Custom Probe 以统一签名划分多档模块。\n\n"
        "- **QuickModule**：`QuickModule.Probe` 仅返回存活状态。"
        "`QuickModule` 实现见 [cmd/custom-probe/main.go:42-59](cmd/custom-probe/main.go:42-59)。\n"
        "- **DeepModule**：`DeepModule.Probe` 进一步检查依赖。"
        "`DeepModule` 实现见 [cmd/custom-probe/main.go:105-145](cmd/custom-probe/main.go:105-145)。\n"
        "- **HTTPModule**：`HTTPModule.Probe` 发起外部 HTTP 调用。"
        "`HTTPModule` 实现见 [cmd/custom-probe/main.go:220-275](cmd/custom-probe/main.go:220-275)。\n"
        "`type API struct` 见 [serv_reflect.go:26-31](serv_reflect.go:26-31)。\n\n"
        "### Custom Probe 拨测模块\n\n"
        "Custom Probe 以 `Probe(ctx, target) *ProbeResult` 为统一签名，按探测深度划分多档模块。\n"
    )
    from repo_wiki.generator.adjacent_cites import promote_file_line_links

    tags = [
        "<cite>cmd/custom-probe/main.go:42-59</cite>",
        "<cite>cmd/custom-probe/serv_reflect.go:26-31</cite>",
    ]
    promoted = promote_file_line_links(markdown, tmp_path)
    attached = attach_adjacent_cites(promoted, tags, workspace_root=tmp_path, strict_match=True)
    out = realign_irrelevant_cites(attached, tags, tmp_path)
    assert "<cite>cmd/custom-probe/main.go:105-145</cite>" in out
    assert "<cite>cmd/custom-probe/main.go:220-275</cite>" in out
    custom_section = out.split("### Custom Probe")[-1]
    assert "serv_reflect.go:26-31" not in custom_section
    assert "[cmd/custom-probe/main.go:105-145]" not in out
    assert "serv_reflect.go:26-31]" not in out


def test_realign_keeps_cite_when_no_better_match(tmp_path: Path) -> None:
    _write_custom_probe_sources(tmp_path)
    markdown = (
        "# 核心服务\n\n"
        "`DeepModule` 进一步执行数据库检查。<cite>cmd/custom-probe/main.go:42-59</cite>\n"
    )
    out = realign_irrelevant_cites(
        markdown,
        ["<cite>cmd/custom-probe/main.go:42-59</cite>"],
        tmp_path,
    )
    assert "<cite>cmd/custom-probe/main.go:42-59</cite>" in out
    assert "`cmd/custom-probe/main.go`" not in out or "<cite>" in out


def test_realign_replaces_with_better_matching_cite(tmp_path: Path) -> None:
    _write_custom_probe_sources(tmp_path)
    markdown = (
        "# 核心服务\n\n"
        "`DeepModule` 进一步执行数据库检查。<cite>cmd/custom-probe/main.go:42-59</cite>\n"
    )
    out = realign_irrelevant_cites(
        markdown,
        [
            "<cite>cmd/custom-probe/main.go:42-59</cite>",
            "<cite>cmd/custom-probe/main.go:105-145</cite>",
        ],
        tmp_path,
    )
    assert "<cite>cmd/custom-probe/main.go:105-145</cite>" in out
    assert "<cite>cmd/custom-probe/main.go:42-59</cite>" not in out


def test_schema_summary_owner_is_page_order_not_completion(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    service = _service(root)
    summary = "已扫描到请求或响应字段的端点：\n\n- POST /api/users: request_body=true"
    owner = _page(
        "api-overview",
        "API参考",
        WikiTaxonomyCategory.API_REFERENCE,
        "API参考/Python服务API.md",
    )
    other = _page(
        "core-service-apis",
        "核心服务API",
        WikiTaxonomyCategory.API_REFERENCE,
        "API参考/核心服务API.md",
    )
    md_owner = f"# API参考\n\n正文。\n\n## Schema 摘要\n\n{summary}\n"
    md_other = f"# 核心服务API\n\n正文。\n\n## Schema 摘要\n\n{summary}\n"
    # Completion order: other first, then owner.
    page_results = {
        1: (other.output_path, md_other),
        0: (owner.output_path, md_owner),
    }
    service._dedupe_schema_summaries_in_page_order([owner, other], page_results)
    assert summary in page_results[0][1]
    assert "字段摘要见 API参考。" in page_results[1][1]
    assert "避免重复粘贴" not in page_results[0][1]
    assert "避免重复粘贴" not in page_results[1][1]
    # Reverse completion order must keep the same owner.
    page_results_rev = {
        0: (owner.output_path, md_owner),
        1: (other.output_path, md_other),
    }
    service._dedupe_schema_summaries_in_page_order([owner, other], page_results_rev)
    assert summary in page_results_rev[0][1]
    assert "字段摘要见 API参考。" in page_results_rev[1][1]


def test_contract_schema_summary_never_uses_paste_meta(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    service = _service(root)
    page = _page(
        "core-service-apis",
        "核心服务API",
        WikiTaxonomyCategory.API_REFERENCE,
        "API参考/核心服务API.md",
    )
    first = _render(service, page, "# 核心服务API\n\n登录。\n", None, add_mermaid=False)
    second = _render(service, page, "# 核心服务API\n\n登录。\n", None, add_mermaid=False)
    assert "避免重复粘贴" not in first
    assert "避免重复粘贴" not in second


def test_fastapi_intro_cites_readme_and_migration(tmp_path: Path) -> None:
    root = _fastapi_repo(tmp_path)
    articles = root / "app" / "models" / "domain" / "articles.py"
    articles.write_text(
        "\n".join(["# pad"] * 7 + ["class Article:", "    slug = ''"] + ["# pad"] * 10),
        encoding="utf-8",
    )
    common = root / "app" / "models" / "common.py"
    common.parent.mkdir(parents=True, exist_ok=True)
    common.write_text(
        "\n".join(
            ["# pad"] * 5 + ["class DateTimeModelMixin:", "    created_at = None"] + ["# pad"] * 12
        ),
        encoding="utf-8",
    )
    page = _page(
        "database-architecture",
        "数据库架构",
        WikiTaxonomyCategory.DATA_MODELS,
        "数据模型/数据库架构/数据库架构.md",
    )
    markdown = (
        "# 数据库架构\n\n"
        "## 简介\n\n"
        "本仓库是 `fastapi-realworld-example-app` 的 RealWorld 示例应用，按照给定的产品身份说明："
        "仓库本身已不再积极维护，因为该示例已完整覆盖 Conduit 测试套件目标。\n"
        "<cite>app/models/common.py:6-17</cite>\n\n"
        "## 核心数据模型\n\n"
        "迁移文件建立了 7 张业务表：`users`、`articles`、`favorites`。\n"
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
            EvidenceCandidate(
                evidence_id=2,
                span=EvidenceSpanRecord(
                    digest="articles",
                    file_path="app/models/domain/articles.py",
                    line_start=8,
                    line_end=16,
                    language="python",
                    symbol="Article",
                    span_text="class Article",
                ),
                score=2.0,
                match_signals=["file"],
                citation_order=1,
            ),
        ],
        bound_count=2,
    )
    out = _service(root)._enforce_qoder_page_contract(page, markdown, binding, add_mermaid=False)
    intro = out.split("## 核心数据模型")[0]
    tables = out.split("## 核心数据模型")[1]
    assert "README.md" in intro
    assert "common.py:6-17" not in intro
    assert "fdf8821871d7_main_tables.py" in tables
    assert "articles.py:8-16" not in tables.split("7 张业务表")[1].split("\n\n")[0]
