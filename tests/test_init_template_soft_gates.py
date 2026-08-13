from __future__ import annotations

from pathlib import Path

from repo_wiki.generator.cites import select_primary_cite
from repo_wiki.generator.engine import GenerationEngine, NarrativeBuilder
from repo_wiki.generator.io import write_json, write_text
from repo_wiki.generator.templates import TemplateRenderer
from repo_wiki.verifier.service import VerifierService
from tests.test_verifier import _write_minimum_with_sections


def _named_check(result: dict, name: str) -> dict:
    check = next((item for item in result["checks"] if item["name"] == name), None)
    assert check is not None
    return check


def test_select_primary_cite_uses_existing_entry_point(tmp_path: Path) -> None:
    entry = tmp_path / "pkg" / "main.py"
    entry.parent.mkdir(parents=True)
    entry.write_text("def main():\n    return 0\n", encoding="utf-8")
    snapshot = {
        "repository": {"entry_points": ["pkg/main.py"]},
        "modules": [{"path": "pkg"}],
    }

    assert select_primary_cite(tmp_path, snapshot) == "<cite>pkg/main.py:1</cite>"


def test_select_primary_cite_skips_missing_files(tmp_path: Path) -> None:
    nested = tmp_path / "lib" / "core.py"
    nested.parent.mkdir(parents=True)
    nested.write_text("value = 1\n", encoding="utf-8")
    missing_snapshot = {
        "repository": {"entry_points": ["repo_wiki/cli.py", "missing.py"]},
        "modules": [],
    }
    fallback_snapshot = {
        "repository": {"entry_points": ["repo_wiki/cli.py", "missing.py"]},
        "modules": [{"path": "lib"}],
    }

    assert select_primary_cite(tmp_path, missing_snapshot) == ""
    assert select_primary_cite(tmp_path, fallback_snapshot) == "<cite>lib/core.py:1</cite>"


def test_list_heavy_overview_is_content_list_only(tmp_path: Path) -> None:
    _write_minimum_with_sections(tmp_path)
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Overview

This is a project overview with substantial prose content that describes the system in detail.

## Project Description

The project solves the core problem of documentation generation.

## Core Problem

We need better way to document repositories.

## Core Capabilities

The system can scan, index, generate, and verify documentation.

## Environment Requirements

Python 3.10+ is required along with poetry.

## Startup Commands

Run poetry install to set up dependencies.

## Modules

- module-a
- module-b
- module-c
- module-d
- module-e
- module-f
- module-g
- module-h
- module-i
- module-j
- module-k
- module-l
- module-m
- module-n
- module-o
- module-p
- module-q
- module-r
- module-s
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    overview_check = _named_check(result, "overview-prose-quality")
    assert overview_check["status"] == "FAIL"
    assert overview_check["reason_code"] == "CONTENT_LIST_ONLY"


def test_overview_with_prose_and_cite_passes_list_and_citation(tmp_path: Path) -> None:
    _write_minimum_with_sections(tmp_path)
    src_dir = tmp_path / "src" / "billing"
    src_dir.mkdir(parents=True, exist_ok=True)
    write_text(src_dir / "api.py", "def health():\n    return 'ok'\n")
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Project Overview

This is the project overview page with substantial prose content.

See <cite>src/billing/api.py:1</cite> for the health check implementation.

## Project Description

The project solves the core problem of documentation generation.

## Core Problem

We need better way to document repositories.

## Core Capabilities

The system can scan, index, generate, and verify documentation.

## Environment Requirements

Python 3.10+ is required.

## Startup Commands

Run `poetry install` to install dependencies.

## Reading Navigation

See architecture for system design.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    overview_check = _named_check(result, "overview-prose-quality")
    citation_check = _named_check(result, "citation-coverage")
    assert overview_check["status"] == "PASS"
    assert citation_check["status"] == "PASS"


def test_missing_cite_on_substantial_overview(tmp_path: Path) -> None:
    _write_minimum_with_sections(tmp_path)
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Project Overview

This is the project overview page with substantial prose content and no citations.

## Project Description

The project solves the core problem of documentation generation.

## Core Problem

We need better way to document repositories.

## Core Capabilities

The system can scan, index, generate, and verify documentation.

## Environment Requirements

Python 3.10+ is required.

## Startup Commands

Run poetry install to install dependencies.

## Reading Navigation

See architecture for system design.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    citation_check = _named_check(result, "citation-coverage")
    assert citation_check["status"] == "FAIL"
    assert citation_check["reason_code"] == "CITATION_MISSING"


def test_broken_cite_path_is_not_used_as_success(tmp_path: Path) -> None:
    _write_minimum_with_sections(tmp_path)
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Project Overview

This overview cites a file that does not exist in the target repository.

See <cite>does-not-exist.py:1</cite> for a missing implementation.

## Project Description

The project solves the core problem of documentation generation.

## Core Problem

We need better way to document repositories.

## Core Capabilities

The system can scan, index, generate, and verify documentation.

## Environment Requirements

Python 3.10+ is required.

## Startup Commands

Run poetry install to install dependencies.

## Reading Navigation

See architecture for system design.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    validity_check = _named_check(result, "citation-validity")
    assert validity_check["status"] == "FAIL"
    assert validity_check["reason_code"] == "CITATION_BROKEN_PATH"


def test_rendered_init_overview_passes_list_and_citation(tmp_path: Path) -> None:
    _write_minimum_with_sections(tmp_path)
    source = tmp_path / "pkg" / "main.py"
    source.parent.mkdir(parents=True)
    source.write_text("def main():\n    return 0\n", encoding="utf-8")

    prose = (
        "This repository is a local-first wiki generator that scans source trees, "
        "indexes modules and APIs, generates reader-facing documentation, and verifies "
        "that the output stays tied to real files in the target repository. The pages "
        "are written as prose so engineers can understand the system without a list wall."
    )
    renderer = TemplateRenderer(Path(__file__).resolve().parents[1] / "templates")
    content = renderer.render(
        "docs/00-overview.md.j2",
        {
            "repository_name": "demo",
            "primary_cite": "<cite>pkg/main.py:1</cite>",
            "project_description": prose,
            "project_positioning": prose,
            "architecture_description": prose,
            "core_problem": prose,
            "core_capabilities": (
                "The system scans repositories, indexes source-of-truth artifacts, "
                "generates wiki pages, and verifies citation and prose quality."
            ),
            "environment_requirements": "Python 3.11 or newer is required.",
            "startup_commands": "Run repo-wiki init then repo-wiki index.",
            "reading_navigation": "Start with architecture, then the module map.",
            "repository_root": str(tmp_path),
            "primary_language": "python",
            "framework": "typer",
            "module_count": "1",
            "endpoint_count": "0",
            "model_count": "0",
            "domain_groups_markdown": "Core tooling lives in the pkg package.",
        },
    )
    write_text(tmp_path / "docs/00-overview.md", content)

    result = VerifierService(tmp_path).verify(ci=True)
    overview_check = _named_check(result, "overview-prose-quality")
    citation_check = _named_check(result, "citation-coverage")
    assert overview_check["status"] == "PASS"
    assert citation_check["status"] == "PASS"


def test_select_primary_cite_reads_engine_snapshot_and_absolute_paths(tmp_path: Path) -> None:
    source = tmp_path / "pkg" / "main.py"
    source.parent.mkdir(parents=True)
    source.write_text("def main():\n    return 0\n", encoding="utf-8")
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "notes.txt").write_text("not source\n", encoding="utf-8")
    (empty / "subdir").mkdir()
    nested_dir = tmp_path / "web"
    nested_dir.mkdir()
    (nested_dir / "app.ts").write_text("export {}\n", encoding="utf-8")
    outside = tmp_path.parent / f"{tmp_path.name}-outside.py"
    outside.write_text("escaped = True\n", encoding="utf-8")
    (nested_dir / "escape.py").symlink_to(outside)

    engine_snapshot = {
        "repo_map": {"repository": {"entry_points": [" ", str(source.resolve())]}},
        "module_index": {"modules": [{"name": "pkg", "path": ""}]},
    }
    assert select_primary_cite(tmp_path, engine_snapshot) == "<cite>pkg/main.py:1</cite>"

    string_module = {
        "repository": {"entry_points": ["/etc/hosts", str(empty)]},
        "modules": ["web"],
    }
    assert select_primary_cite(tmp_path, string_module) == "<cite>web/app.ts:1</cite>"
    assert select_primary_cite(tmp_path, {"repo_map": "invalid"}) == ""
    assert select_primary_cite(tmp_path, {"repo_map": {"repository": None}}) == ""
    assert select_primary_cite(tmp_path, {"module_index": "invalid"}) == ""
    assert select_primary_cite(tmp_path, {"module_index": {"modules": {}}}) == ""


def test_build_core_context_feeds_primary_cite_from_target_repo(tmp_path: Path) -> None:
    source = tmp_path / "pkg" / "main.py"
    source.parent.mkdir(parents=True)
    source.write_text("def main():\n    return 0\n", encoding="utf-8")
    write_json(
        tmp_path / "ai/source-of-truth/repo-map.yaml",
        {
            "repository": {
                "name": "demo",
                "primary_language": "python",
                "entry_points": ["pkg/main.py"],
            },
            "commands": {},
        },
    )
    write_json(
        tmp_path / "ai/source-of-truth/module-index.yaml",
        {"modules": [{"name": "pkg", "path": "pkg"}]},
    )
    write_json(tmp_path / "ai/source-of-truth/api-index.yaml", {"endpoints": []})
    write_json(tmp_path / "ai/source-of-truth/data-models.yaml", {"models": []})

    templates = Path(__file__).resolve().parents[1] / "templates"
    engine = GenerationEngine(tmp_path, template_root=templates)
    context = engine._build_core_context(engine._load_snapshot())
    assert context["primary_cite"] == "<cite>pkg/main.py:1</cite>"
    assert not str(context["core_capabilities"]).lstrip().startswith("- ")


def test_capabilities_as_prose_rewrites_bullet_wall() -> None:
    builder = NarrativeBuilder(
        repo_name="demo",
        primary_language="python",
        framework="typer",
        modules=[],
        endpoints=[],
        models=[],
        commands={},
    )
    rewritten = builder._capabilities_as_prose("- scan\n- index\n- generate\n- verify\n")
    assert not rewritten.lstrip().startswith("- ")
    assert "扫描" in rewritten
    assert "校验" in rewritten
    assert builder._capabilities_as_prose("   \n") == rewritten
    assert builder._capabilities_as_prose("already prose") == "already prose"
    empty_caps = NarrativeBuilder(
        repo_name="demo",
        primary_language="unknown",
        framework="unknown",
        modules=[],
        endpoints=[],
        models=[],
        commands={},
    ).build_core_capabilities()
    assert "基础的代码分析" in empty_caps
    assert not empty_caps.lstrip().startswith("- ")
