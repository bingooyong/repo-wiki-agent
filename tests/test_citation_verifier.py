"""Tests for citation verifier checks.

Tests for:
- Missing citation coverage
- Broken citation paths
- Invalid line ranges
- Empty source blocks
"""

from __future__ import annotations

from pathlib import Path

from repo_wiki.generator.io import write_json, write_text
from repo_wiki.verifier.service import VerifierService


def _write_minimum_artifacts(root: Path) -> None:
    """Write minimum artifacts for citation tests."""
    write_json(
        root / "ai/source-of-truth/repo-map.yaml",
        {"repository": {"name": "demo", "root_path": str(root)}, "commands": {}},
    )
    write_json(
        root / "ai/source-of-truth/module-index.yaml",
        {
            "modules": [
                {
                    "name": "billing",
                    "path": "src/billing",
                    "responsibility": "billing logic",
                    "exports": [],
                    "depends_on": [],
                    "depended_by": [],
                    "interfaces": [],
                    "data_models": [],
                    "owner": "unknown",
                    "doc_path": "docs/modules/billing.md",
                }
            ]
        },
    )
    write_json(
        root / "ai/source-of-truth/api-index.yaml",
        {"endpoints": [{"method": "GET", "path": "/health", "module": "billing", "handler": "h", "file_path": "src/billing/api.py"}]},
    )
    write_json(
        root / "ai/source-of-truth/data-models.yaml",
        {"models": [{"name": "Invoice", "type": "python_class", "module": "billing", "file_path": "src/billing/model.py"}]},
    )
    write_json(root / "ai/source-of-truth/task-catalog.yaml", {"tasks": []})
    write_text(root / "ai/source-of-truth/prompt-fragments/overview.txt", "overview")
    write_text(root / "ai/source-of-truth/prompt-fragments/architecture.txt", "arch")

    for path in [
        "docs/00-overview.md",
        "docs/01-architecture.md",
        "docs/03-module-map.md",
        "docs/04-api-contracts.md",
        "docs/05-data-model.md",
    ]:
        write_text(root / path, "ok")

    write_text(root / "docs/modules/billing.md", "module")

    write_json(root / ".claude/settings.json", {"knowledge_base": ["docs/00-overview.md"]})
    write_text(root / ".claude/CLAUDE.md", "`docs/00-overview.md`")
    write_text(root / "AGENTS.md", "`docs/01-architecture.md`\n`http://localhost:8007`")
    write_json(root / ".opencode/opencode.json", {"knowledge_paths": ["docs/00-overview.md"]})
    write_text(root / ".codex/config.toml", 'project = "repo-wiki"\n[knowledge]\npath_1 = "docs/00-overview.md"\n')
    write_json(root / ".codex/hooks.json", {"post_commands": []})


def _create_sections_dir(root: Path) -> None:
    """Create sections directory with required sections."""
    sections_dir = root / "docs/sections"
    sections_dir.mkdir(parents=True, exist_ok=True)
    for section in ["project", "architecture", "services", "data-model", "api", "operations", "development", "security", "troubleshooting"]:
        section_dir = sections_dir / section
        section_dir.mkdir(parents=True, exist_ok=True)
        write_text(section_dir / "index.md", f"# {section}\n")


# =============================================================================
# Citation Coverage Tests
# =============================================================================


def test_citation_coverage_pass_with_citations(tmp_path: Path) -> None:
    """Test that pages with proper citations pass citation coverage check."""
    _write_minimum_artifacts(tmp_path)
    _create_sections_dir(tmp_path)

    # Create source file that will be cited
    src_dir = tmp_path / "src" / "billing"
    src_dir.mkdir(parents=True, exist_ok=True)
    write_text(src_dir / "api.py", "def health():\n    return 'ok'\n")

    # Write overview with proper citation
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Project Overview

This is the project overview with a citation to <cite>src/billing/api.py:1</cite>.

## Project Description

The project solves the core problem.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    citation_check = next((c for c in result["checks"] if c["name"] == "citation-coverage"), None)
    assert citation_check is not None
    assert citation_check["status"] == "PASS"


def test_citation_coverage_fail_on_no_citations(tmp_path: Path) -> None:
    """Test that pages without any citations produce FAIL."""
    _write_minimum_artifacts(tmp_path)
    _create_sections_dir(tmp_path)

    # Write overview WITHOUT any citations
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Project Overview

This is the project overview with no citations at all.

## Project Description

The project solves the core problem.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    citation_check = next((c for c in result["checks"] if c["name"] == "citation-coverage"), None)
    assert citation_check is not None
    assert citation_check["status"] == "FAIL"
    assert citation_check["reason_code"] == "CITATION_MISSING"


def test_citation_coverage_soft_gate_for_missing_citations(tmp_path: Path) -> None:
    """Test that missing citation coverage is a SOFT gate by default."""
    _write_minimum_artifacts(tmp_path)
    _create_sections_dir(tmp_path)

    # Write overview WITHOUT any citations
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Project Overview

This is the project overview with no citations.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    citation_check = next((c for c in result["checks"] if c["name"] == "citation-coverage"), None)
    assert citation_check is not None
    assert citation_check["status"] == "FAIL"
    assert citation_check["gate_type"] == "SOFT"


# =============================================================================
# Broken Citation Path Tests
# =============================================================================


def test_citation_validity_fail_on_broken_path(tmp_path: Path) -> None:
    """Test that citations with broken file paths produce FAIL."""
    _write_minimum_artifacts(tmp_path)
    _create_sections_dir(tmp_path)

    # Write overview with citation to non-existent file
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Project Overview

Citation to broken path: <cite>nonexistent/file.py:1</cite>

## Project Description

The project solves the core problem.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    citation_check = next((c for c in result["checks"] if c["name"] == "citation-validity"), None)
    assert citation_check is not None
    assert citation_check["status"] == "FAIL"
    assert citation_check["reason_code"] == "CITATION_BROKEN_PATH"


def test_citation_validity_fail_on_invalid_line_range(tmp_path: Path) -> None:
    """Test that citations with invalid line ranges produce FAIL."""
    _write_minimum_artifacts(tmp_path)
    _create_sections_dir(tmp_path)

    # Create source file
    src_dir = tmp_path / "src" / "billing"
    src_dir.mkdir(parents=True, exist_ok=True)
    write_text(src_dir / "api.py", "def health():\n    return 'ok'\n")

    # Write overview with citation to non-existent line
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Project Overview

Citation to invalid line: <cite>src/billing/api.py:999</cite>

## Project Description

The project solves the core problem.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    citation_check = next((c for c in result["checks"] if c["name"] == "citation-validity"), None)
    assert citation_check is not None
    assert citation_check["status"] == "FAIL"
    assert citation_check["reason_code"] == "CITATION_BAD_LINES"


def test_citation_validity_fail_on_reversed_line_range(tmp_path: Path) -> None:
    """Test that citations with reversed line ranges (end < start) produce FAIL."""
    _write_minimum_artifacts(tmp_path)
    _create_sections_dir(tmp_path)

    # Create source file
    src_dir = tmp_path / "src" / "billing"
    src_dir.mkdir(parents=True, exist_ok=True)
    write_text(src_dir / "api.py", "def health():\n    return 'ok'\n")

    # Write overview with reversed line range
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Project Overview

Citation to reversed range: <cite>src/billing/api.py:10-5</cite>

## Project Description

The project solves the core problem.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    citation_check = next((c for c in result["checks"] if c["name"] == "citation-validity"), None)
    assert citation_check is not None
    assert citation_check["status"] == "FAIL"
    assert citation_check["reason_code"] == "CITATION_BAD_LINES"


def test_citation_validity_fail_on_negative_line(tmp_path: Path) -> None:
    """Test that citations with negative line numbers produce FAIL."""
    _write_minimum_artifacts(tmp_path)
    _create_sections_dir(tmp_path)

    # Write overview with negative line number
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Project Overview

Citation to negative line: <cite>src/billing/api.py:-1</cite>

## Project Description

The project solves the core problem.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    citation_check = next((c for c in result["checks"] if c["name"] == "citation-validity"), None)
    assert citation_check is not None
    assert citation_check["status"] == "FAIL"
    assert citation_check["reason_code"] == "CITATION_BAD_LINES"


# =============================================================================
# Empty Source Block Tests
# =============================================================================


def test_citation_source_empty_fail(tmp_path: Path) -> None:
    """Test that pages with empty source blocks produce FAIL."""
    _write_minimum_artifacts(tmp_path)
    _create_sections_dir(tmp_path)

    # Write overview with empty source block
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Project Overview

!!! cite "sources"

## Project Description

The project solves the core problem.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    citation_check = next((c for c in result["checks"] if c["name"] == "citation-source-empty"), None)
    assert citation_check is not None
    assert citation_check["status"] == "FAIL"
    assert citation_check["reason_code"] == "CITATION_SOURCE_EMPTY"
    assert citation_check["gate_type"] == "HARD"


def test_citation_source_empty_pass_with_citations(tmp_path: Path) -> None:
    """Test that pages with non-empty source blocks pass."""
    _write_minimum_artifacts(tmp_path)
    _create_sections_dir(tmp_path)

    # Create source file
    src_dir = tmp_path / "src" / "billing"
    src_dir.mkdir(parents=True, exist_ok=True)
    write_text(src_dir / "api.py", "def health():\n    return 'ok'\n")

    # Write overview with non-empty source block
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Project Overview

!!! cite "sources"
    <cite>src/billing/api.py:1</cite>

## Project Description

The project solves the core problem.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    citation_check = next((c for c in result["checks"] if c["name"] == "citation-source-empty"), None)
    assert citation_check is not None
    assert citation_check["status"] == "PASS"


# =============================================================================
# Valid Citation Tests
# =============================================================================


def test_valid_citation_single_line(tmp_path: Path) -> None:
    """Test valid single-line citation is accepted."""
    _write_minimum_artifacts(tmp_path)
    _create_sections_dir(tmp_path)

    # Create source file
    src_dir = tmp_path / "src" / "billing"
    src_dir.mkdir(parents=True, exist_ok=True)
    write_text(src_dir / "api.py", "def health():\n    return 'ok'\n")

    # Write overview with valid single-line citation
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Project Overview

See <cite>src/billing/api.py:1</cite> for the health check.

## Project Description

The project solves the core problem.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    coverage_check = next((c for c in result["checks"] if c["name"] == "citation-coverage"), None)
    validity_check = next((c for c in result["checks"] if c["name"] == "citation-validity"), None)
    assert coverage_check is not None
    assert coverage_check["status"] == "PASS"
    assert validity_check is not None
    assert validity_check["status"] == "PASS"


def test_valid_citation_multi_line(tmp_path: Path) -> None:
    """Test valid multi-line citation is accepted."""
    _write_minimum_artifacts(tmp_path)
    _create_sections_dir(tmp_path)

    # Create source file with multiple lines
    src_dir = tmp_path / "src" / "billing"
    src_dir.mkdir(parents=True, exist_ok=True)
    write_text(src_dir / "api.py", "def health():\n    return 'ok'\ndef other():\n    pass\n")

    # Write overview with valid multi-line citation
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Project Overview

See <cite>src/billing/api.py:1-3</cite> for the functions.

## Project Description

The project solves the core problem.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    coverage_check = next((c for c in result["checks"] if c["name"] == "citation-coverage"), None)
    validity_check = next((c for c in result["checks"] if c["name"] == "citation-validity"), None)
    assert coverage_check is not None
    assert coverage_check["status"] == "PASS"
    assert validity_check is not None
    assert validity_check["status"] == "PASS"


def test_valid_citation_with_symbol(tmp_path: Path) -> None:
    """Test valid citation with symbol is accepted."""
    _write_minimum_artifacts(tmp_path)
    _create_sections_dir(tmp_path)

    # Create source file
    src_dir = tmp_path / "src" / "billing"
    src_dir.mkdir(parents=True, exist_ok=True)
    write_text(src_dir / "api.py", "def health():\n    return 'ok'\n")

    # Write overview with valid citation including symbol
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Project Overview

See <cite>src/billing/api.py:1 (health)</cite> for the function.

## Project Description

The project solves the core problem.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    coverage_check = next((c for c in result["checks"] if c["name"] == "citation-coverage"), None)
    validity_check = next((c for c in result["checks"] if c["name"] == "citation-validity"), None)
    assert coverage_check is not None
    assert coverage_check["status"] == "PASS"
    assert validity_check is not None
    assert validity_check["status"] == "PASS"


# =============================================================================
# Multiple Citations Tests
# =============================================================================


def test_multiple_citations_mixed_validity(tmp_path: Path) -> None:
    """Test that mixed valid and invalid citations are detected."""
    _write_minimum_artifacts(tmp_path)
    _create_sections_dir(tmp_path)

    # Create source file
    src_dir = tmp_path / "src" / "billing"
    src_dir.mkdir(parents=True, exist_ok=True)
    write_text(src_dir / "api.py", "def health():\n    return 'ok'\n")

    # Write overview with mixed valid and invalid citations
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Project Overview

Valid: <cite>src/billing/api.py:1</cite>
Invalid: <cite>nonexistent/file.py:1</cite>

## Project Description

The project solves the core problem.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    validity_check = next((c for c in result["checks"] if c["name"] == "citation-validity"), None)
    assert validity_check is not None
    assert validity_check["status"] == "FAIL"
    assert validity_check["reason_code"] == "CITATION_BROKEN_PATH"
    # Should have details about which citations are broken
    assert "broken_citations" in validity_check["details"]
    assert len(validity_check["details"]["broken_citations"]) > 0


# =============================================================================
# Architecture Citation Tests
# =============================================================================


def test_architecture_citation_validity(tmp_path: Path) -> None:
    """Test that architecture page citations are validated."""
    _write_minimum_artifacts(tmp_path)
    _create_sections_dir(tmp_path)

    # Create source file
    src_dir = tmp_path / "src" / "billing"
    src_dir.mkdir(parents=True, exist_ok=True)
    write_text(src_dir / "api.py", "def health():\n    return 'ok'\n")

    # Write architecture with valid citation and mermaid
    write_text(
        tmp_path / "docs/01-architecture.md",
        """# Architecture

See <cite>src/billing/api.py:1</cite> for details.

```mermaid
graph TD
    A[.repo-wiki/] --> B[ai/source-of-truth/]
```
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    # Citation validity check should pass for architecture
    validity_check = next((c for c in result["checks"] if c["name"] == "citation-validity"), None)
    assert validity_check is not None
    assert validity_check["status"] == "PASS"


# =============================================================================
# Section Source Block Tests
# =============================================================================


def test_section_source_block_empty_is_hard_gate(tmp_path: Path) -> None:
    """Test that empty section source blocks are HARD gate failures."""
    _write_minimum_artifacts(tmp_path)
    _create_sections_dir(tmp_path)

    # Create section page with empty source block
    section_dir = tmp_path / "docs/sections" / "project"
    write_text(
        section_dir / "index.md",
        """# Project

!!! cite "sources"

## Content

Some content here.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    citation_check = next((c for c in result["checks"] if c["name"] == "citation-source-empty"), None)
    assert citation_check is not None
    assert citation_check["status"] == "FAIL"
    assert citation_check["gate_type"] == "HARD"


# =============================================================================
# Severity Threshold Override Tests
# =============================================================================


def test_citation_missing_can_be_hard_gate(tmp_path: Path) -> None:
    """Test that CITATION_MISSING can be configured as HARD gate."""
    from repo_wiki.verifier.service import SeverityThreshold

    _write_minimum_artifacts(tmp_path)
    _create_sections_dir(tmp_path)

    # Write overview WITHOUT any citations
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Project Overview

This is the project overview with no citations.
""",
    )

    # Configure CITATION_MISSING as hard gate
    custom_thresholds = SeverityThreshold(
        hard_gate_codes={"CITATION_MISSING"},
    )

    result = VerifierService(tmp_path, severity_thresholds=custom_thresholds).verify(ci=True)
    citation_check = next((c for c in result["checks"] if c["name"] == "citation-coverage"), None)
    assert citation_check is not None
    assert citation_check["status"] == "FAIL"
    assert citation_check["gate_type"] == "HARD"
    # With hard gate failure, acceptance should be blocked
    assert result["gate_summary"]["acceptance_blocked"] is True


# =============================================================================
# Reason Codes Tests
# =============================================================================


def test_reason_codes_include_citation_failures(tmp_path: Path) -> None:
    """Test that citation failures are included in reason codes."""
    _write_minimum_artifacts(tmp_path)
    _create_sections_dir(tmp_path)

    # Write overview with broken citation
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Project Overview

Citation to broken path: <cite>nonexistent/file.py:1</cite>
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)

    # Should have citation-validity failure in reason codes
    validity_failure = next(
        (c for c in result["checks"] if c["name"] == "citation-validity" and c["status"] == "FAIL"),
        None,
    )
    assert validity_failure is not None
    assert validity_failure["reason_code"] == "CITATION_BROKEN_PATH"
    assert validity_failure["reason_code"] in result["reason_codes"]
