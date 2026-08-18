"""Accepted LLM pages should place leftover evidence cites next to claims."""

from __future__ import annotations

import re

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.evidence.ranking import EvidenceCandidate, PageEvidenceBinding
from repo_wiki.generator.adjacent_cites import attach_adjacent_cites
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory
from repo_wiki.verifier.citation_fact_coverage import build_claim_coverage


def test_attach_adjacent_cites_covers_uncovered_claim() -> None:
    markdown = (
        "# API\n\n"
        "The service uses FastAPI to expose article endpoints.\n\n"
        "Login is implemented in the authentication router.\n"
    )
    rewritten = attach_adjacent_cites(
        markdown,
        ["<cite>app/main.py:1-4</cite>", "<cite>app/api/routes/authentication.py:10-40</cite>"],
    )
    coverage = build_claim_coverage(
        rewritten,
        page="api.md",
        valid_repo_citation_lines={
            idx for idx, line in enumerate(rewritten.splitlines(), start=1) if "<cite>" in line
        },
    )
    assert coverage["total"] >= 1
    assert float(coverage["ratio"]) == 1.0
    assert "app/main.py" in rewritten
    assert "app/api/routes/authentication.py" in rewritten


def test_page_contract_attaches_cites_beside_claims_not_only_footer() -> None:
    service = RepoWikiService(RepoWikiConfig())
    page = WikiPagePlan(
        page_id="python-service-apis",
        title="Python服务API",
        category=WikiTaxonomyCategory.API_REFERENCE,
        output_path="docs/pages/python-service-apis.md",
    )
    span = EvidenceSpanRecord(
        digest="routes",
        file_path="app/api/routes/articles.py",
        line_start=12,
        line_end=40,
        language="python",
        symbol="create_article",
        span_text="def create_article():",
    )
    binding = PageEvidenceBinding(
        page_id=page.page_id,
        doc_type="api",
        candidates=[
            EvidenceCandidate(
                evidence_id=1,
                span=span,
                score=2.0,
                match_signals=["file_proximity"],
                citation_order=0,
            )
        ],
        bound_count=1,
    )
    markdown = (
        "# Python服务API\n\nThe service uses FastAPI to create articles for authenticated users.\n"
    )
    rendered = service._enforce_qoder_page_contract(page, markdown, binding, add_mermaid=False)
    lines = rendered.splitlines()
    cite_lines = {idx for idx, line in enumerate(lines, start=1) if "<cite>" in line}
    coverage = build_claim_coverage(rendered, page="api.md", valid_repo_citation_lines=cite_lines)
    assert "app/api/routes/articles.py" in rendered
    assert float(coverage["ratio"]) >= 0.95 or int(coverage["covered"]) >= 1
    claim_line = next(
        idx
        for idx, line in enumerate(lines, start=1)
        if "create articles" in line.lower() or "FastAPI" in line
    )
    assert cite_lines & {claim_line - 1, claim_line, claim_line + 1}


def _contract_service_with_article_span(tmp_path):
    cfg = RepoWikiConfig()
    cfg.project.root = str(tmp_path)
    service = RepoWikiService(cfg)
    page = WikiPagePlan(
        page_id="python-service-apis",
        title="Python服务API",
        category=WikiTaxonomyCategory.API_REFERENCE,
        output_path="docs/pages/python-service-apis.md",
    )
    span = EvidenceSpanRecord(
        digest="routes",
        file_path="app/foo.py",
        line_start=10,
        line_end=20,
        language="python",
        symbol="symbol",
        span_text="def symbol():",
    )
    binding = PageEvidenceBinding(
        page_id=page.page_id,
        doc_type="api",
        candidates=[
            EvidenceCandidate(
                evidence_id=1,
                span=span,
                score=2.0,
                match_signals=["file_proximity"],
                citation_order=0,
            )
        ],
        bound_count=1,
    )
    return service, page, binding


def test_page_contract_strips_cite_block_symbol_parenthetical_before_write(tmp_path) -> None:
    """Generate-time CiteBlock ``path:N-M (symbol)`` must be sanitized before write."""
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "foo.py").write_text("\n".join(f"line {i}" for i in range(1, 31)), encoding="utf-8")
    service, page, binding = _contract_service_with_article_span(tmp_path)
    markdown = (
        "# Python服务API\n\nThe service uses FastAPI to create articles for authenticated users.\n"
    )
    rendered = service._enforce_qoder_page_contract(page, markdown, binding, add_mermaid=False)
    assert "<cite>app/foo.py:10-20</cite>" in rendered
    assert "(symbol)" not in rendered
    assert not re.search(r"<cite>[^<]*\([^)]*\)", rendered)


def test_page_contract_sanitizes_llm_ranged_parenthetical_left_in_markdown(tmp_path) -> None:
    """Contract must sanitize leftover ``path:start-end (label)`` even if compose skipped it."""
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "foo.py").write_text("\n".join(f"line {i}" for i in range(1, 31)), encoding="utf-8")
    cfg = RepoWikiConfig()
    cfg.project.root = str(tmp_path)
    service = RepoWikiService(cfg)
    page = WikiPagePlan(
        page_id="project-overview",
        title="项目概述",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
        output_path="docs/pages/overview/project-overview.md",
    )
    markdown = (
        "# 项目概述\n\n"
        "The service uses FastAPI to create articles for authenticated users.\n"
        "<cite>app/foo.py:10-20 (symbol)</cite>\n"
    )
    rendered = service._enforce_qoder_page_contract(page, markdown, None, add_mermaid=False)
    assert "<cite>app/foo.py:10-20</cite>" in rendered
    assert "(symbol)" not in rendered
    assert not re.search(r"<cite>[^<]*\([^)]*\)", rendered)
