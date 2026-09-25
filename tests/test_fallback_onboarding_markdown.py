"""Unclean pages must be dropped, not rendered as fallback placeholders."""

from __future__ import annotations

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory


def test_unclean_page_is_dropped() -> None:
    service = RepoWikiService(RepoWikiConfig())
    page = WikiPagePlan(
        page_id="overview",
        title="项目概述",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
        output_path="docs/pages/overview.md",
    )
    assert service._should_drop_unclean_page(page, "Handbook evidence meta talk") is True
    assert not hasattr(service, "_fallback_markdown_for_failed_page")
    assert not hasattr(service, "_fallback_snippet_paragraphs")
