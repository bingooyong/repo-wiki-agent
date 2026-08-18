"""Composer rejects generator-meta pages as a page-local quality fail."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo_wiki.generator.composer import (
    ComposerContext,
    ComposerInput,
    LLMPageComposer,
    create_composer,
)
from repo_wiki.llm.config import LLMProviderConfig
from repo_wiki.llm.models import ChatRequest, ChatResponse, LLMProvider, ProviderCapabilities
from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory
from repo_wiki.prompts.contracts import PagePromptType, get_contract_for_page_type
from repo_wiki.prompts.skeleton import build_skeleton
from repo_wiki.verifier.handbook import (
    GENERATOR_META_REJECTION,
    is_page_local_quality_rejection,
)
from tests.test_compose_circuit_break import (
    ENOUGH_TOKENS,
    PAGE_COUNT,
    SUCCESS_MARKDOWN,
    _install_provider,
    _plan,
    _service,
    _snapshot,
    compose_env,  # noqa: F401 — pytest fixture reused by the circuit-break test
)

ENOUGH_PROSE = (
    "Conduit 是 RealWorld 规范的 FastAPI 后端示例。"
    "仓库 README 说明了 PostgreSQL、DATABASE_URL 和 docker compose 启动步骤。"
    "接手仓库的人应该先按这些步骤把服务跑起来，再去改登录或文章接口。"
    "本页只复述仓库里已经出现的产品身份和运行方式，不解释生成器内部实现。"
)

GENERATOR_META_MARKDOWN = (
    f"{SUCCESS_MARKDOWN}\n\n本页由 fallback composer 生成，并附带 evidence ranking 说明。\n"
)


class GeneratorMetaThenHealthyProvider(LLMProvider):
    """First N chats are HTTP 200 + enough prose, but contain generator meta."""

    def __init__(self, reject_count: int) -> None:
        self._reject_count = reject_count
        self._call_count = 0
        self._config = LLMProviderConfig(
            provider="mock",
            model="mock-gpt",
            timeout=1.5,
            max_retries=0,
        )

    @property
    def name(self) -> str:
        return "generator-meta-fake"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities()

    @property
    def call_count(self) -> int:
        return self._call_count

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self._call_count += 1
        if self._call_count <= self._reject_count:
            return ChatResponse(
                content=GENERATOR_META_MARKDOWN,
                model="mock-gpt",
                usage=dict(ENOUGH_TOKENS),
            )
        return ChatResponse(content=SUCCESS_MARKDOWN, model="mock-gpt")

    def validate_config(self) -> list[tuple[str, str | None, str]]:
        return []


def _composer_input() -> ComposerInput:
    page = WikiPagePlan(
        page_id="project-overview",
        title="项目概述",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
        output_path="docs/pages/overview/project-overview.md",
    )
    return ComposerInput(
        page_plan=page,
        evidence_binding=None,
        skeleton=build_skeleton("overview", page.title),
        contract=get_contract_for_page_type(PagePromptType.OVERVIEW),
        context=ComposerContext(
            repository_name="fastapi-realworld-example-app",
            primary_language="python",
            framework="fastapi",
            repository_root=".",
        ),
    )


def test_validate_output_rejects_generator_meta_after_sufficient_prose() -> None:
    composer: LLMPageComposer = create_composer()
    result = composer._validate_output(GENERATOR_META_MARKDOWN, _composer_input())
    assert result.rejected is True
    assert result.rejection_reason == "Handbook generator meta content"


def test_validate_output_accepts_handbook_prose_without_meta() -> None:
    composer: LLMPageComposer = create_composer()
    content = f"# 项目概述\n\n{ENOUGH_PROSE}\n"
    result = composer._validate_output(content, _composer_input())
    assert result.rejection_reason != "Handbook generator meta content"


@pytest.mark.asyncio
async def test_generator_meta_rejection_is_page_local_like_insufficient_prose(
    compose_env: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Mirror test_insufficient_prose_rejects_do_not_trip_circuit_breaker
    monkeypatch.setenv("REPO_WIKI_LLM_MAX_FAILURES", "3")
    root = compose_env / "repo"
    root.mkdir()
    output_dir = compose_env / "run"
    output_dir.mkdir()
    provider = GeneratorMetaThenHealthyProvider(reject_count=3)
    service = _service(root)
    _install_provider(monkeypatch, service, provider)

    result = await service._compose_qoder_like_pages(
        plan=_plan(),
        evidence_bindings={},
        snapshot=_snapshot(root),
        output_dir=output_dir,
    )
    assert result["llm"]["provider_disabled_after_failures"] is False
    assert provider.call_count == PAGE_COUNT
    assert result["llm"]["llm_call_count"] == PAGE_COUNT
    assert result["llm"]["fallback_page_count"] == 3
    meta_rejects = [
        reason
        for meta in result["page_metadata"]
        for reason in meta["reasons"]
        if GENERATOR_META_REJECTION in reason
    ]
    disabled_reasons = [
        reason
        for meta in result["page_metadata"]
        for reason in meta["reasons"]
        if "provider disabled after" in reason
    ]
    assert len(meta_rejects) == 3
    assert not disabled_reasons
    assert is_page_local_quality_rejection("Insufficient prose content") is True
    assert is_page_local_quality_rejection(GENERATOR_META_REJECTION) is True
    assert is_page_local_quality_rejection("Empty LLM assistant content") is True
    assert is_page_local_quality_rejection("Unclosed fenced code block") is True
    assert is_page_local_quality_rejection("LLM page timeout after 180.0s") is True
    assert is_page_local_quality_rejection("LLM page server error 529: Server error: 529") is True
    assert is_page_local_quality_rejection("Composition error: 529") is False
