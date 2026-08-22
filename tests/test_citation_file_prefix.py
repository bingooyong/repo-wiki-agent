"""Writers must not emit file: citation prefixes that verify rejects.

R7 measured 18 HARD QODER_CITATION_INVALID cites, all file: / file does not exist.
Product files such as README.rst exist; the prefix is the bug.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from repo_wiki.evidence.citation_renderer import normalize_citation_markup
from repo_wiki.generator.composer import (
    ComposerContext,
    LLMPageComposer,
    build_composer_input,
    create_composer,
)
from repo_wiki.planner.schema import GenerationMode, WikiPagePlan, WikiTaxonomyCategory
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeVerifierService


def _write_release_candidate(root: Path, page_markdown: str) -> None:
    content_dir = root / "repowiki" / "zh" / "content"
    meta_dir = root / "repowiki" / "zh" / "meta"
    content_dir.mkdir(parents=True)
    meta_dir.mkdir(parents=True)
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "app.py").write_text("\n".join(f"line {i}" for i in range(1, 41)))
    page_rel = "项目概述/00-overview.md"
    page = content_dir / page_rel
    page.parent.mkdir()
    page.write_text(page_markdown, encoding="utf-8")
    (meta_dir / "quality-report.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.quality_report/1.0",
                "summary": {"profile": "qoder-like", "grade": "PASS", "strict_mode": True},
                "page_quality": [{"relative_path": page_rel, "quality_state": "READY"}],
            }
        ),
        encoding="utf-8",
    )
    (meta_dir / "page-registry.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.page_registry/1.0",
                "generated_at": "2026-07-15T00:00:00Z",
                "pages": [
                    {
                        "page_id": "overview",
                        "relative_path": page_rel,
                        "category": "overview",
                        "page_type": "content",
                        "quality_state": "READY",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (meta_dir / "api-inventory.json").write_text(
        json.dumps({"endpoints": [{"method": "GET", "path": "/health"}]}),
        encoding="utf-8",
    )
    (meta_dir / "service-registry.json").write_text(
        json.dumps({"services": [{"service_id": "api-gateway"}]}), encoding="utf-8"
    )
    (meta_dir / "data-model-inventory.json").write_text(
        json.dumps({"models": [{"model_id": "user-entity"}]}), encoding="utf-8"
    )
    (meta_dir / "runtime-inventory.json").write_text(
        json.dumps({"runtime_entrypoints": [{"entrypoint": "repo-wiki"}]}),
        encoding="utf-8",
    )
    (meta_dir / "source-inventory.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.source_inventory/1.0",
                "services": [{"service_id": "api-gateway"}],
                "api_surfaces": [{"method": "GET", "path": "/health"}],
                "data_models": [{"model_id": "user-entity"}],
                "runtime_entrypoints": [{"entrypoint": "repo-wiki"}],
            }
        ),
        encoding="utf-8",
    )
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "version": "1.1",
                "run_id": "run-cite-prefix",
                "readiness_state": "READY",
                "readiness_reasons": [],
                "target_dirty": False,
                "git_fresh": True,
                "candidate_repowiki_zh_root": str(root / "repowiki" / "zh"),
                "candidate_content_root": str(content_dir),
                "candidate_meta_root": str(meta_dir),
                "report_paths": {"strict_verify": "reports/strict-verify-output.json"},
                "files": [{"path": "reports/strict-verify-output.json"}],
                "evidence": [],
            }
        ),
        encoding="utf-8",
    )


def _citation_targets_check(result: dict) -> dict:
    return next(check for check in result["checks"] if check["name"] == "qoder-citation-targets")


def _overview_page(cite: str) -> str:
    return f"""# Project Overview

## Table of Contents
- [Intro](#intro)

## Intro

GET /health is the supported health endpoint for Service `api-gateway` and Model `user-entity`.

```mermaid
graph LR
  A --> B
```

<cite>{cite}</cite>
"""


def test_normalize_file_prefix_readme_rst_cite_is_accepted_by_verifier(tmp_path: Path) -> None:
    """Emit/normalize file:README.rst so verify looks up README.rst, not file:README.rst."""
    (tmp_path / "README.rst").write_text("RealWorld Conduit example app\n" * 8, encoding="utf-8")
    composer = create_composer(workspace_root=tmp_path)
    raw = _overview_page("file:README.rst:1")
    normalized = composer._normalize_markdown_response(raw, "Project Overview")

    assert "file:README.rst" not in normalized
    assert "<cite>README.rst:1</cite>" in normalized

    _write_release_candidate(tmp_path, normalized)
    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    citation_check = _citation_targets_check(result)
    assert citation_check["status"] == "PASS"
    assert citation_check["details"]["invalid_count"] == 0
    assert "QODER_CITATION_INVALID" not in result.get("hard_gate_codes", [])
    invalid = citation_check["details"].get("invalid") or []
    assert not any("file does not exist" in str(item.get("problem", "")) for item in invalid)


def test_existing_valid_citation_schemes_remain_accepted(tmp_path: Path) -> None:
    """Bare paths and source: cites that already pass must stay valid."""
    (tmp_path / "README.rst").write_text("RealWorld Conduit example app\n" * 8, encoding="utf-8")
    composer = create_composer(workspace_root=tmp_path)
    page = composer._normalize_markdown_response(
        """# Project Overview

## Table of Contents
- [Intro](#intro)

## Intro

GET /health is the supported health endpoint for Service `api-gateway` and Model `user-entity`.

```mermaid
graph LR
  A --> B
```

<cite>source:src/app.py:1-10</cite>
<cite>README.rst:1</cite>
""",
        "Project Overview",
    )
    assert "<cite>source:src/app.py:1-10</cite>" in page
    assert "<cite>README.rst:1</cite>" in page

    _write_release_candidate(tmp_path, page)
    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    citation_check = _citation_targets_check(result)
    assert citation_check["status"] == "PASS"
    assert "QODER_CITATION_INVALID" not in result.get("hard_gate_codes", [])


def test_missing_citation_target_still_qoder_citation_invalid(tmp_path: Path) -> None:
    """Do not weaken QODER_CITATION_INVALID for paths that truly do not exist."""
    (tmp_path / "README.rst").write_text("RealWorld Conduit example app\n" * 8, encoding="utf-8")
    composer = create_composer(workspace_root=tmp_path)
    page = composer._normalize_markdown_response(
        _overview_page("file:missing/nope.py:1"),
        "Project Overview",
    )
    _write_release_candidate(tmp_path, page)
    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    assert "QODER_CITATION_INVALID" in result.get("hard_gate_codes", [])
    citation_check = _citation_targets_check(result)
    assert citation_check["status"] == "FAIL"
    assert citation_check["reason_code"] == "QODER_CITATION_INVALID"
    assert citation_check["gate_type"] == "HARD"


def test_compact_prompt_does_not_teach_file_scheme_cites() -> None:
    """Composer must not instruct writers to emit <cite>file:...</cite>."""
    composer = LLMPageComposer()
    context = ComposerContext(
        repository_name="demo",
        primary_language="python",
        framework="fastapi",
        repository_root=".",
    )
    page = WikiPagePlan(
        page_id="project-overview",
        title="项目概述",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
        output_path="docs/pages/overview/project-overview.md",
        generation_mode=GenerationMode.LLM_ASSISTED,
    )
    composer_input = build_composer_input(page, None, context)
    prompt = composer._build_compact_prompt(composer_input, composer._build_context(composer_input))
    assert "<cite>file:" not in prompt
    assert "file:start-end" not in prompt


def test_normalize_relpath_prefix_readme_rst_cite_is_accepted_by_verifier(tmp_path: Path) -> None:
    """Emit/normalize relpath:README.rst so verify looks up README.rst, not relpath:README.rst."""
    (tmp_path / "README.rst").write_text("RealWorld Conduit example app\n" * 8, encoding="utf-8")
    composer = create_composer(workspace_root=tmp_path)
    raw = _overview_page("relpath:README.rst:1-3")
    normalized = composer._normalize_markdown_response(raw, "Project Overview")

    assert "relpath:README.rst" not in normalized
    assert "<cite>README.rst:1-3</cite>" in normalized

    _write_release_candidate(tmp_path, normalized)
    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    citation_check = _citation_targets_check(result)
    assert citation_check["status"] == "PASS"
    assert citation_check["details"]["invalid_count"] == 0
    assert "QODER_CITATION_INVALID" not in result.get("hard_gate_codes", [])
    invalid = citation_check["details"].get("invalid") or []
    assert not any("file does not exist" in str(item.get("problem", "")) for item in invalid)


def test_placeholder_relpath_start_end_cite_is_dropped(tmp_path: Path) -> None:
    """Literal <cite>relpath:start-end</cite> is a prompt leftover, not a file path."""
    (tmp_path / "README.rst").write_text("RealWorld Conduit example app\n" * 8, encoding="utf-8")
    composer = create_composer(workspace_root=tmp_path)
    raw = _overview_page("README.rst:1-3") + "\n<cite>relpath:start-end</cite>\n"
    normalized = composer._normalize_markdown_response(raw, "Project Overview")

    assert "<cite>relpath:start-end</cite>" not in normalized
    assert "relpath:start-end" not in normalized
    assert "<cite>README.rst:1-3</cite>" in normalized

    # Already-published pages may still contain the template token.
    _write_release_candidate(tmp_path, raw)
    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    citation_check = _citation_targets_check(result)
    assert citation_check["status"] == "PASS"
    assert citation_check["details"]["invalid_count"] == 0
    assert "QODER_CITATION_INVALID" not in result.get("hard_gate_codes", [])
    invalid = citation_check["details"].get("invalid") or []
    assert not any("relpath:start-end" in str(item.get("citation", "")) for item in invalid)
    assert not any(
        "relpath:start-end" in str(item) or item.get("citation") == "relpath:start-end"
        for item in invalid
    )


def test_compact_prompt_does_not_teach_relpath_scheme_cites() -> None:
    """Composer must not instruct writers to emit <cite>relpath:...</cite>."""
    composer = LLMPageComposer()
    context = ComposerContext(
        repository_name="demo",
        primary_language="python",
        framework="fastapi",
        repository_root=".",
    )
    page = WikiPagePlan(
        page_id="project-overview",
        title="项目概述",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
        output_path="docs/pages/overview/project-overview.md",
        generation_mode=GenerationMode.LLM_ASSISTED,
    )
    composer_input = build_composer_input(page, None, context)
    prompt = composer._build_compact_prompt(composer_input, composer._build_context(composer_input))
    assert "<cite>relpath:" not in prompt
    assert "relpath:start-end" not in prompt


def test_normalize_readme_md_cite_to_readme_rst_when_only_rst_exists(tmp_path: Path) -> None:
    """R9 leftover: LLM cites README.md on a README.rst-only repo; remap, do not invent README.md."""
    (tmp_path / "README.rst").write_text("RealWorld Conduit example app\n" * 8, encoding="utf-8")
    assert not (tmp_path / "README.md").exists()
    composer = create_composer(workspace_root=tmp_path)
    raw = _overview_page("README.md:1-3")
    normalized = composer._normalize_markdown_response(raw, "Project Overview")

    assert "<cite>README.rst:1-3</cite>" in normalized
    assert "<cite>README.md:1-3</cite>" not in normalized
    assert not (tmp_path / "README.md").exists()

    _write_release_candidate(tmp_path, normalized)
    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    citation_check = _citation_targets_check(result)
    assert citation_check["status"] == "PASS"
    assert citation_check["details"]["invalid_count"] == 0
    assert "QODER_CITATION_INVALID" not in result.get("hard_gate_codes", [])
    invalid = citation_check["details"].get("invalid") or []
    assert not any("file does not exist" in str(item.get("problem", "")) for item in invalid)


def test_normalize_readme_md_cite_to_readme_txt_when_only_txt_exists(tmp_path: Path) -> None:
    """Same alias when the only root readme is README.txt."""
    (tmp_path / "README.txt").write_text("Conduit example app\n" * 8, encoding="utf-8")
    assert not (tmp_path / "README.md").exists()
    composer = create_composer(workspace_root=tmp_path)
    normalized = composer._normalize_markdown_response(
        _overview_page("README.md:1-3"),
        "Project Overview",
    )

    assert "<cite>README.txt:1-3</cite>" in normalized
    assert "<cite>README.md:1-3</cite>" not in normalized

    _write_release_candidate(tmp_path, normalized)
    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    citation_check = _citation_targets_check(result)
    assert citation_check["status"] == "PASS"
    assert citation_check["details"]["invalid_count"] == 0
    assert "QODER_CITATION_INVALID" not in result.get("hard_gate_codes", [])


def test_readme_md_cite_stays_when_both_md_and_rst_exist(tmp_path: Path) -> None:
    """Do not steal a real README.md cite when both README.md and README.rst exist."""
    (tmp_path / "README.md").write_text("# Conduit\n\nFastAPI RealWorld.\n" * 4, encoding="utf-8")
    (tmp_path / "README.rst").write_text("RealWorld Conduit example app\n" * 8, encoding="utf-8")
    composer = create_composer(workspace_root=tmp_path)
    normalized = composer._normalize_markdown_response(
        _overview_page("README.md:1-3"),
        "Project Overview",
    )

    assert "<cite>README.md:1-3</cite>" in normalized
    assert "<cite>README.rst:1-3</cite>" not in normalized

    _write_release_candidate(tmp_path, normalized)
    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    citation_check = _citation_targets_check(result)
    assert citation_check["status"] == "PASS"
    assert citation_check["details"]["invalid_count"] == 0
    assert "QODER_CITATION_INVALID" not in result.get("hard_gate_codes", [])


def test_missing_app_nope_py_cite_still_hard_invalid(tmp_path: Path) -> None:
    """A truly missing file stays HARD QODER_CITATION_INVALID; do not relax gates."""
    (tmp_path / "README.rst").write_text("RealWorld Conduit example app\n" * 8, encoding="utf-8")
    composer = create_composer(workspace_root=tmp_path)
    page = composer._normalize_markdown_response(
        _overview_page("app/nope.py:1"),
        "Project Overview",
    )
    assert "<cite>app/nope.py:1</cite>" in page

    _write_release_candidate(tmp_path, page)
    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    assert "QODER_CITATION_INVALID" in result.get("hard_gate_codes", [])
    citation_check = _citation_targets_check(result)
    assert citation_check["status"] == "FAIL"
    assert citation_check["reason_code"] == "QODER_CITATION_INVALID"
    assert citation_check["gate_type"] == "HARD"


def test_compact_prompt_teaches_actual_readme_rst_filename(tmp_path: Path) -> None:
    """Composer should name the real root README so writers do not invent README.md."""
    (tmp_path / "README.rst").write_text("RealWorld Conduit example app\n" * 8, encoding="utf-8")
    composer = LLMPageComposer(workspace_root=tmp_path)
    context = ComposerContext(
        repository_name="demo",
        primary_language="python",
        framework="fastapi",
        repository_root=str(tmp_path),
    )
    page = WikiPagePlan(
        page_id="project-overview",
        title="项目概述",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
        output_path="docs/pages/overview/project-overview.md",
        generation_mode=GenerationMode.LLM_ASSISTED,
    )
    composer_input = build_composer_input(page, None, context)
    prompt = composer._build_compact_prompt(composer_input, composer._build_context(composer_input))
    assert "README.rst" in prompt
    assert "<cite>README.md" not in prompt
    assert "<cite>file:" not in prompt
    assert "<cite>relpath:" not in prompt


def _long_readme_rst(root: Path) -> None:
    (root / "README.rst").write_text(
        "\n".join(f"readme line {i}" for i in range(1, 121)),
        encoding="utf-8",
    )


def test_parenthetical_readme_rst_cite_without_lines_is_dropped(tmp_path: Path) -> None:
    """``README.rst（产品身份声明）`` has no line range; drop it, keep a valid sibling."""
    _long_readme_rst(tmp_path)
    composer = create_composer(workspace_root=tmp_path)
    raw = (
        _overview_page("README.rst（产品身份声明）")
        + "\nThe health endpoint is documented in application code.\n"
        + "<cite>src/app.py:1-10</cite>\n"
    )
    normalized = composer._normalize_markdown_response(raw, "Project Overview")

    assert "README.rst（" not in normalized
    assert "<cite>README.rst</cite>" not in normalized
    assert "<cite>src/app.py:1-10</cite>" in normalized

    _write_release_candidate(tmp_path, normalized)
    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    assert "QODER_CITATION_INVALID" not in result.get("hard_gate_codes", [])


def test_comma_joined_readme_cites_split_into_two_valid_cites(tmp_path: Path) -> None:
    _long_readme_rst(tmp_path)
    composer = create_composer(workspace_root=tmp_path)
    normalized = composer._normalize_markdown_response(
        _overview_page("README.rst:32-73, README.rst:74-115"),
        "Project Overview",
    )

    assert "<cite>README.rst:32-73</cite>" in normalized
    assert "<cite>README.rst:74-115</cite>" in normalized
    assert "README.rst:32-73, README.rst:74-115" not in normalized

    _write_release_candidate(tmp_path, normalized)
    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    citation_check = _citation_targets_check(result)
    assert citation_check["status"] == "PASS"
    assert citation_check["details"]["invalid_count"] == 0
    assert "QODER_CITATION_INVALID" not in result.get("hard_gate_codes", [])


def test_readme_parenthetical_without_lines_is_dropped_not_invented(tmp_path: Path) -> None:
    """``README（项目身份说明）`` must not grow invented ``README.rst:N-M`` lines."""
    _long_readme_rst(tmp_path)
    composer = create_composer(workspace_root=tmp_path)
    raw = _overview_page("README（项目身份说明）") + "\n<cite>src/app.py:1-10</cite>\n"
    normalized = composer._normalize_markdown_response(raw, "Project Overview")

    assert "（项目身份说明）" not in normalized
    assert "<cite>README</cite>" not in normalized
    assert not re.search(r"<cite>README(?:\.rst|\.md)?:\d", normalized)
    assert "<cite>src/app.py:1-10</cite>" in normalized

    _write_release_candidate(tmp_path, normalized)
    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    assert "QODER_CITATION_INVALID" not in result.get("hard_gate_codes", [])


def test_ranged_parenthetical_cite_keeps_path_and_lines(tmp_path: Path) -> None:
    """``app/foo.py:10-20 (symbol)`` must become ``app/foo.py:10-20``, not drop or invent."""
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "foo.py").write_text("\n".join(f"line {i}" for i in range(1, 31)), encoding="utf-8")
    (tmp_path / "README.rst").write_text("RealWorld Conduit example app\n" * 8, encoding="utf-8")

    assert (
        normalize_citation_markup("<cite>app/foo.py:10-20 (symbol)</cite>")
        == "<cite>app/foo.py:10-20</cite>"
    )

    composer = create_composer(workspace_root=tmp_path)
    normalized = composer._normalize_markdown_response(
        _overview_page("app/foo.py:10-20 (symbol)"),
        "Project Overview",
    )
    assert "<cite>app/foo.py:10-20</cite>" in normalized
    assert "(symbol)" not in normalized
    assert not re.search(r"<cite>app/foo\.py:\d+-\d+\s+\(", normalized)

    _write_release_candidate(tmp_path, normalized)
    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    citation_check = _citation_targets_check(result)
    assert citation_check["status"] == "PASS"
    assert citation_check["details"]["invalid_count"] == 0
    assert "QODER_CITATION_INVALID" not in result.get("hard_gate_codes", [])


def test_readme_note_cite_is_dropped(tmp_path: Path) -> None:
    _long_readme_rst(tmp_path)
    composer = create_composer(workspace_root=tmp_path)
    raw = _overview_page("README:NOTE") + "\n<cite>src/app.py:1-10</cite>\n"
    normalized = composer._normalize_markdown_response(raw, "Project Overview")

    assert "README:NOTE" not in normalized
    assert "<cite>src/app.py:1-10</cite>" in normalized

    _write_release_candidate(tmp_path, normalized)
    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    assert "QODER_CITATION_INVALID" not in result.get("hard_gate_codes", [])
