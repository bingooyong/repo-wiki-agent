"""Handbook prompt contract: README same/next-line cites and API routes cites."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.evidence.ranking import EvidenceCandidate, PageEvidenceBinding
from repo_wiki.generator.composer import (
    ComposerContext,
    LLMPageComposer,
    build_composer_input,
)
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.planner.schema import GenerationMode, WikiPagePlan, WikiTaxonomyCategory
from repo_wiki.prompts import API_PROMPT_FRAGMENT, OVERVIEW_PROMPT_FRAGMENT
from repo_wiki.prompts.fragments import DEVELOPMENT_PROMPT_FRAGMENT
from repo_wiki.verifier.citation_fact_coverage import build_claim_coverage
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeSeverityThreshold


def _context() -> ComposerContext:
    return ComposerContext(
        repository_name="fastapi-realworld-example-app",
        primary_language="python",
        framework="fastapi",
        repository_root=".",
    )


def _page(page_id: str, title: str, category: WikiTaxonomyCategory) -> WikiPagePlan:
    return WikiPagePlan(
        page_id=page_id,
        title=title,
        category=category,
        output_path=f"docs/pages/{page_id}.md",
        generation_mode=GenerationMode.LLM_ASSISTED,
    )


def _compact_prompt(page: WikiPagePlan, binding: PageEvidenceBinding | None = None) -> str:
    composer = LLMPageComposer()
    composer_input = build_composer_input(page, binding, _context())
    return composer._build_compact_prompt(composer_input, composer._build_context(composer_input))


def _readme_cite_required(prompt: str) -> None:
    lowered = prompt.lower()
    assert "readme" in lowered
    assert ("同一行" in prompt or "同行" in prompt or "same-line" in lowered) and (
        "下一行" in prompt or "next-line" in lowered or "次行" in prompt
    )


def test_overview_prompt_requires_same_or_next_line_readme_cite() -> None:
    prompt = _compact_prompt(
        _page("project-overview", "项目概述", WikiTaxonomyCategory.PROJECT_OVERVIEW)
    )
    _readme_cite_required(prompt)
    assert "<cite>" in prompt
    assert "同一行" in OVERVIEW_PROMPT_FRAGMENT or "下一行" in OVERVIEW_PROMPT_FRAGMENT


def test_installation_prompt_requires_same_or_next_line_readme_cite() -> None:
    prompt = _compact_prompt(
        _page("installation", "安装指南", WikiTaxonomyCategory.PROJECT_OVERVIEW)
    )
    _readme_cite_required(prompt)
    assert "同一行" in DEVELOPMENT_PROMPT_FRAGMENT or "下一行" in DEVELOPMENT_PROMPT_FRAGMENT


def test_api_prompt_requires_routes_cite_when_routes_evidence_exists() -> None:
    span = EvidenceSpanRecord(
        digest="routes",
        file_path="app/api/routes/authentication.py",
        line_start=10,
        line_end=40,
        language="python",
        symbol="login",
        span_text="def login():",
    )
    binding = PageEvidenceBinding(
        page_id="core-service-apis",
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
    prompt = _compact_prompt(
        _page("core-service-apis", "核心服务API", WikiTaxonomyCategory.API_REFERENCE),
        binding,
    )
    assert "api/routes" in prompt.replace("\\", "/")
    assert "api/routes" in API_PROMPT_FRAGMENT


def test_citation_fact_coverage_window_unchanged() -> None:
    markdown = (
        "The service uses FastAPI.\n<cite>app/main.py:1-4</cite>\nLogin is implemented here.\n"
    )
    covered_next = build_claim_coverage(markdown, page="api.md", valid_repo_citation_lines={2})
    assert covered_next["total"] >= 1
    assert int(covered_next["covered"]) >= 1

    source = Path("repo_wiki/verifier/qoder_strict_verifier.py").read_text(encoding="utf-8")
    assert "ratio < 0.95" in source
    assert "QODER_CITATION_FACT_COVERAGE_LOW" in QoderLikeSeverityThreshold.STRICT_HARD_CODES
    window_src = Path("repo_wiki/verifier/citation_fact_coverage.py").read_text(encoding="utf-8")
    assert "claim.line - 1" in window_src
    assert "claim.line + 1" in window_src
