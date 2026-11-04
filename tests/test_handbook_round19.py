"""Phase E: thin-topic evidence, page plan, and re-ask coverage prompts."""

from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.evidence.ranking import (
    EvidenceCandidate,
    PageEvidenceBinding,
    wants_wide_evidence,
)
from repo_wiki.generator.composer import LLMPageComposer, build_composer_input, create_composer
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.planner.identity import resolve_repository_identity
from repo_wiki.planner.rule_first import RuleFirstPlanner
from repo_wiki.planner.schema import WikiTaxonomyCategory
from repo_wiki.scanner.repository_scanner import RepositoryScanner
from tests.test_llm_compose_retry import FENCE_HEAVY_MARKDOWN
from tests.test_page_prompts import _handbook_compact_prompt, _handbook_context, _handbook_page


def _span(file_path: str, text: str = "span") -> EvidenceSpanRecord:
    return EvidenceSpanRecord(
        digest=file_path,
        file_path=file_path,
        line_start=1,
        line_end=12,
        language="go" if file_path.endswith(".go") else "text",
        symbol=Path(file_path).stem,
        span_text=text,
    )


def _binding(page_id: str, count: int = 8) -> PageEvidenceBinding:
    candidates: list[EvidenceCandidate] = []
    for index in range(count):
        span = _span(f"internal/debug/file_{index}.go", f"func Debug{index}() {{}}")
        candidates.append(
            EvidenceCandidate(
                evidence_id=index + 1,
                span=span,
                score=1.0,
                match_signals=["thin_debug_source"],
                citation_order=index,
            )
        )
    return PageEvidenceBinding(
        page_id=page_id,
        doc_type="development-guide",
        candidates=candidates,
        bound_count=count,
    )


def test_wide_evidence_tokens_are_page_specific() -> None:
    assert wants_wide_evidence("debug-guide development-guide")
    assert wants_wide_evidence("git-workflow development-guide")
    assert wants_wide_evidence("database-migration data-models")
    assert wants_wide_evidence("健康检查 deployment")
    assert wants_wide_evidence("digital-signing api-reference") is False
    assert wants_wide_evidence("authentication security") is False


def test_debug_compact_prompt_asks_for_impl_cites_and_full_pages() -> None:
    prompt = _handbook_compact_prompt(
        _handbook_page("debug-guide", "调试指南", WikiTaxonomyCategory.DEVELOPMENT_GUIDE)
    )
    assert "调试指南" in prompt
    assert "每个可核对事实句都要带" in prompt
    assert "scaffold" in prompt
    assert "不要短页" in prompt


def test_git_compact_prompt_skips_missing_rules_without_process_talk() -> None:
    prompt = _handbook_compact_prompt(
        _handbook_page("git-workflow", "Git工作流", WikiTaxonomyCategory.DEVELOPMENT_GUIDE)
    )
    assert "CONTRIBUTING" in prompt
    assert "过程句" in prompt
    assert "每个可核对事实句都要带" in prompt


def test_debug_recovery_widens_evidence_and_bans_process_talk() -> None:
    composer = create_composer()
    page = _handbook_page("debug-guide", "调试指南", WikiTaxonomyCategory.DEVELOPMENT_GUIDE)
    binding = _binding("debug-guide", count=8)
    composer_input = build_composer_input(page, binding, _handbook_context())
    recovery = composer._build_prose_recovery_prompt(
        composer_input,
        composer._build_context(composer_input),
        FENCE_HEAVY_MARKDOWN,
    )
    assert "file_0.go" in recovery
    assert "file_7.go" in recovery
    assert "过程句" in recovery
    assert "900" in recovery
    assert "scaffold" in recovery
    assert "每个可核对事实句" in recovery


def test_generic_recovery_keeps_compact_four_span_window() -> None:
    composer = create_composer()
    page = _handbook_page("project-overview", "项目概述", WikiTaxonomyCategory.PROJECT_OVERVIEW)
    binding = _binding("project-overview", count=8)
    composer_input = build_composer_input(page, binding, _handbook_context())
    recovery = composer._build_prose_recovery_prompt(
        composer_input,
        composer._build_context(composer_input),
        FENCE_HEAVY_MARKDOWN,
    )
    assert "file_0.go" in recovery
    assert "file_7.go" not in recovery


def test_debug_evidence_context_includes_more_spans() -> None:
    composer = LLMPageComposer()
    wide = composer._build_evidence_context(_binding("debug-guide", count=16))
    narrow = composer._build_evidence_context(_binding("core-service-apis", count=16))
    assert "file_15.go" in wide
    assert "file_15.go" not in narrow
    assert "file_7.go" in narrow


def test_debug_and_git_pages_pin_impl_files(tmp_path: Path) -> None:
    (tmp_path / "xstats").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / "xstats" / "pprof.go").write_text(
        "package xstats\nfunc Register() {}\n", encoding="utf-8"
    )
    (tmp_path / "scripts" / "debug_container.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (tmp_path / "docs" / "README-scaffold.md").write_text("# scaffold pprof\n", encoding="utf-8")
    (tmp_path / "CONTRIBUTING.md").write_text("# Contribute\n", encoding="utf-8")
    (tmp_path / "Makefile").write_text("test:\n\tgo test ./...\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# sample\n", encoding="utf-8")
    (tmp_path / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")
    pages = (
        RuleFirstPlanner(
            resolve_repository_identity(tmp_path),
            RepositoryScanner(
                RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
            ).scan(),
        )
        .generate()
        .pages
    )
    debug = next(page for page in pages if page.page_id == "debug-guide")
    git_page = next(page for page in pages if page.page_id == "git-workflow")
    assert any("pprof.go" in item for item in debug.source_requirements.files)
    assert any("debug_container.sh" in item for item in debug.source_requirements.files)
    assert not any("scaffold" in item for item in debug.source_requirements.files)
    assert "CONTRIBUTING.md" in git_page.source_requirements.files
    assert any("workflow" in item for item in git_page.source_requirements.files)
