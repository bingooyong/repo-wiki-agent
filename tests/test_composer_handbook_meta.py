"""Composer rejects generator-meta pages as a page-local quality fail."""

from __future__ import annotations

from repo_wiki.generator.composer import (
    ComposerContext,
    ComposerInput,
    LLMPageComposer,
    create_composer,
)
from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory
from repo_wiki.prompts.contracts import PagePromptType, get_contract_for_page_type
from repo_wiki.prompts.skeleton import build_skeleton
from repo_wiki.verifier.handbook import (
    GENERATOR_META_REJECTION,
    is_page_local_quality_rejection,
)

ENOUGH_PROSE = (
    "Conduit 是 RealWorld 规范的 FastAPI 后端示例。"
    "仓库 README 说明了 PostgreSQL、DATABASE_URL 和 docker compose 启动步骤。"
    "接手仓库的人应该先按这些步骤把服务跑起来，再去改登录或文章接口。"
    "本页只复述仓库里已经出现的产品身份和运行方式，不解释生成器内部实现。"
)


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
    content = (
        f"# 项目概述\n\n{ENOUGH_PROSE}\n\n"
        "本页由 fallback composer 生成，并附带 evidence ranking 说明。\n"
    )
    result = composer._validate_output(content, _composer_input())
    assert result.rejected is True
    assert result.rejection_reason == GENERATOR_META_REJECTION


def test_validate_output_accepts_handbook_prose_without_meta() -> None:
    composer: LLMPageComposer = create_composer()
    content = f"# 项目概述\n\n{ENOUGH_PROSE}\n"
    result = composer._validate_output(content, _composer_input())
    assert result.rejection_reason != GENERATOR_META_REJECTION
    assert result.rejected is False or result.rejection_reason == "Insufficient prose content"


def test_generator_meta_rejection_is_page_local_like_insufficient_prose() -> None:
    assert is_page_local_quality_rejection("Insufficient prose content") is True
    assert is_page_local_quality_rejection(GENERATOR_META_REJECTION) is True
    assert is_page_local_quality_rejection("Composition error: 529") is False
    assert is_page_local_quality_rejection(None) is False
