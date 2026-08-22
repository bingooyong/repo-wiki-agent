"""Fallback pages must read as onboarding wiki, not generator meta."""

from __future__ import annotations

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.evidence.ranking import EvidenceCandidate, PageEvidenceBinding
from repo_wiki.generator.composer import (
    _HANDBOOK_ONBOARDING_HEADINGS,
    EMPTY_COMPOSER_STUB_PHRASE,
)
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory
from repo_wiki.verifier.handbook import has_fenced_install_run_command

GENERATOR_JARGON = (
    "fallback composer",
    "page_id",
    "repo-agent",
    "evidence ranking",
    "该页面对应",
)

README_QUICKSTART = """
Quickstart
==========

Install PostgreSQL, then set DATABASE_URL and run docker compose up.
After the stack is healthy, run the test suite with pytest.
"""

AUTH_TOKEN_SNIPPET = """
def get_current_user(authorization: str = Header(...)):
    token = authorization.removeprefix("Token ")
    return lookup_user_by_api_token(token)
"""


def _service() -> RepoWikiService:
    cfg = RepoWikiConfig()
    cfg.project.root = "."
    return RepoWikiService(cfg)


def _page(*, page_id: str, title: str, category: WikiTaxonomyCategory) -> WikiPagePlan:
    return WikiPagePlan(
        page_id=page_id,
        title=title,
        category=category,
        output_path=f"docs/pages/{page_id}.md",
    )


def _binding(
    *, file_path: str, span_text: str, symbol: str, line_end: int = 20
) -> PageEvidenceBinding:
    span = EvidenceSpanRecord(
        digest="fallback-onboarding",
        file_path=file_path,
        line_start=1,
        line_end=line_end,
        language="text",
        symbol=symbol,
        span_text=span_text,
    )
    candidate = EvidenceCandidate(
        evidence_id=1,
        span=span,
        score=1.0,
        match_signals=["file_proximity"],
        citation_order=0,
    )
    return PageEvidenceBinding(
        page_id="unused-binding-id",
        doc_type="overview",
        candidates=[candidate],
        bound_count=1,
    )


def _assert_no_generator_jargon(markdown: str) -> None:
    lowered = markdown.lower()
    for needle in GENERATOR_JARGON:
        assert needle.lower() not in lowered, f"fallback jargon leaked: {needle!r}"


def _assert_prose_floor(service: RepoWikiService, markdown: str) -> None:
    assert service._count_prose_chars(markdown) >= 260


def test_overview_fallback_uses_readme_quickstart_not_generator_meta() -> None:
    service = _service()
    page = _page(
        page_id="project-overview",
        title="项目概述",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
    )
    binding = _binding(file_path="README.rst", span_text=README_QUICKSTART, symbol="Quickstart")

    markdown = service._fallback_markdown_for_failed_page(page, binding)

    _assert_no_generator_jargon(markdown)
    _assert_prose_floor(service, markdown)
    assert "README.rst" in markdown
    assert "<cite>README.rst:" in markdown
    assert "PostgreSQL" in markdown
    assert "docker" in markdown.lower()
    assert "DATABASE_URL" in markdown


def test_installation_fallback_surfaces_how_to_run_evidence() -> None:
    service = _service()
    page = _page(
        page_id="installation",
        title="安装指南",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
    )
    binding = _binding(file_path="README.rst", span_text=README_QUICKSTART, symbol="Quickstart")

    markdown = service._fallback_markdown_for_failed_page(page, binding)

    _assert_no_generator_jargon(markdown)
    _assert_prose_floor(service, markdown)
    assert "README.rst" in markdown
    assert "PostgreSQL" in markdown
    assert "docker" in markdown.lower()
    assert "DATABASE_URL" in markdown
    assert "该证据用于限定本文的描述范围" not in markdown
    assert EMPTY_COMPOSER_STUB_PHRASE not in markdown
    for heading in _HANDBOOK_ONBOARDING_HEADINGS:
        assert heading in markdown
    assert "```bash" in markdown
    assert has_fenced_install_run_command(markdown)
    assert "docker compose" in markdown.lower() or "docker-compose" in markdown.lower()


def test_installation_fallback_has_fenced_run_clue() -> None:
    service = _service()
    page = _page(
        page_id="installation",
        title="安装指南",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
    )
    binding = _binding(file_path="README.rst", span_text=README_QUICKSTART, symbol="Quickstart")

    markdown = service._fallback_markdown_for_failed_page(page, binding)
    enriched = service._enforce_qoder_page_contract(
        page=page,
        markdown=markdown,
        binding=binding,
        add_mermaid=True,
        composition_context=None,
    )

    assert EMPTY_COMPOSER_STUB_PHRASE not in enriched
    assert has_fenced_install_run_command(enriched)
    assert "## 安装步骤" in enriched
    assert "## 启动与验证" in enriched


def test_security_fallback_avoids_composer_jargon() -> None:
    service = _service()
    page = _page(
        page_id="security-overview",
        title="安全合规概览",
        category=WikiTaxonomyCategory.SECURITY_COMPLIANCE,
    )
    binding = _binding(
        file_path="app/core/security.py",
        span_text=AUTH_TOKEN_SNIPPET,
        symbol="get_current_user",
        line_end=12,
    )

    markdown = service._fallback_markdown_for_failed_page(page, binding)

    _assert_no_generator_jargon(markdown)
    _assert_prose_floor(service, markdown)
    assert "app/core/security.py" in markdown
    assert "Token" in markdown
    assert "本页聚焦认证授权、审计记录和安全控制点" not in markdown


def test_empty_binding_has_no_jargon_and_invents_no_paths() -> None:
    service = _service()
    page = _page(
        page_id="project-overview",
        title="项目概述",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
    )

    markdown = service._fallback_markdown_for_failed_page(page, None)

    _assert_no_generator_jargon(markdown)
    _assert_prose_floor(service, markdown)
    assert "README.rst" not in markdown
    assert "app/core/security.py" not in markdown
    assert "<cite>" not in markdown
    assert "无法" in markdown or "不能" in markdown


def test_troubleshooting_fallback_is_readable_onboarding_stub() -> None:
    service = _service()
    page = _page(
        page_id="database-issues",
        title="数据库问题",
        category=WikiTaxonomyCategory.TROUBLESHOOTING,
    )
    binding = _binding(
        file_path="app/core/settings.py",
        span_text="DATABASE_URL = postgres://user:pass@localhost:5432/app",
        symbol="database_url",
        line_end=8,
    )

    markdown = service._fallback_markdown_for_failed_page(page, binding)

    _assert_no_generator_jargon(markdown)
    _assert_prose_floor(service, markdown)
    assert "app/core/settings.py" in markdown
    assert "<cite>app/core/settings.py:" in markdown
    assert "DATABASE_URL" in markdown
    assert "这是什么" in markdown or "定位" in markdown
