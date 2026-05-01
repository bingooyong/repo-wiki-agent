from __future__ import annotations

from pathlib import Path

from repo_wiki.generator.io import write_json, write_text
from repo_wiki.verifier.service import VerifierService


def _write_minimum_artifacts(root: Path, with_module_doc: bool = True) -> None:
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

    if with_module_doc:
        write_text(root / "docs/modules/billing.md", "module")

    write_json(root / ".claude/settings.json", {"knowledge_base": ["docs/00-overview.md"]})
    write_text(root / ".claude/CLAUDE.md", "`docs/00-overview.md`")
    write_text(root / "AGENTS.md", "`docs/01-architecture.md`\n`http://localhost:8007`")
    write_json(root / ".opencode/opencode.json", {"knowledge_paths": ["docs/00-overview.md"]})
    write_text(root / ".codex/config.toml", 'project = "repo-wiki"\n[knowledge]\npath_1 = "docs/00-overview.md"\n')
    write_json(root / ".codex/hooks.json", {"post_commands": []})


def test_verifier_pass(tmp_path: Path) -> None:
    _write_quality_artifacts(tmp_path)  # Use full quality artifacts for PASS
    result = VerifierService(tmp_path).verify(ci=True)
    assert result["grade"] == "PASS"


def test_verifier_fail_for_missing_module_doc(tmp_path: Path) -> None:
    _write_minimum_artifacts(tmp_path, with_module_doc=False)
    result = VerifierService(tmp_path).verify(ci=True)
    assert result["grade"] == "FAIL"


# =============================================================================
# Phase 08: Content Quality Tests
# =============================================================================

def _write_minimum_with_sections(root: Path) -> None:
    """Write minimum artifacts plus proper section pages for Phase 08 tests."""
    _write_minimum_artifacts(root, with_module_doc=True)

    # Create required section pages with proper navigation
    sections = ["project", "architecture", "services", "data-model", "api", "operations", "development", "security", "troubleshooting"]
    for section in sections:
        section_dir = root / "docs/sections" / section
        section_dir.mkdir(parents=True, exist_ok=True)
        write_text(
            section_dir / "index.md",
            f"# {section.title()}\n\nThis is the {section} section.\n\n## Navigation\n\n- [Overview](../../00-overview.md)\n- [Architecture](../../01-architecture.md)\n\n## Content\n\nSome prose content here describing the {section} section in detail.\n",
        )


def _write_quality_artifacts(root: Path) -> None:
    """Write artifacts that pass content quality checks."""
    _write_minimum_with_sections(root)

    # Create source files for citations
    src_dir = root / "src" / "billing"
    src_dir.mkdir(parents=True, exist_ok=True)
    write_text(src_dir / "api.py", "def health():\n    return 'ok'\n\ndef create_billing():\n    pass\n")
    write_text(src_dir / "model.py", "class Invoice:\n    def __init__(self):\n        self.amount = 0\n\nclass LineItem:\n    def __init__(self):\n        self.quantity = 0\n")

    # Write overview with proper prose and citations
    write_text(
        root / "docs/00-overview.md",
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

See [Architecture](01-architecture.md) for system design.
""",
    )

    # Write architecture with Mermaid diagrams and citations
    write_text(
        root / "docs/01-architecture.md",
        """# Architecture

See <cite>src/billing/api.py:1-3</cite> for core API implementation.

## System Layers

The system has three layers.

```mermaid
graph TD
    A[.repo-wiki/] --> B[ai/source-of-truth/]
    B --> C[docs/]
```

## Service Collaboration

Services work together.

```mermaid
graph LR
    A[Scanner] --> B[Indexer]
    B --> C[Generator]
```

## Core Data Flow

Data flows from code to docs.

## Storage and Retrieval Design

We store in SQLite and retrieve via search.

## Three Layer Architecture

1. .repo-wiki/ - runtime storage
2. ai/source-of-truth/ - structured facts
3. docs/ - human-readable output

## Incremental Update Governance

Updates are tracked and validated.
""",
    )

    # Write API contracts with proper aggregation
    write_text(
        root / "docs/04-api-contracts.md",
        """# API Contracts

See <cite>src/billing/api.py:1</cite> for the health endpoint implementation.

## API Groups

| Service | Auth | Endpoints |
|---------|------|-----------|
| billing | Bearer | 5 |

## Call Conventions

### Authentication

Bearer token authentication is used.

### Error and Status Codes

Standard HTTP status codes apply.

### Key Entry APIs

- GET /health - health check
- POST /billing - create billing

## Full Endpoint Index

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
""",
    )

    # Write data model with proper aggregation
    write_text(
        root / "docs/05-data-model.md",
        """# Data Models

See <cite>src/billing/model.py:1</cite> for the Invoice model.

## Core Data Models

### Core Model List

| Model | Module | Description |
|-------|--------|-------------|
| Invoice | billing | Billing entity |

## Service Data Models

### By Service

| Service | Models |
|---------|--------|
| billing | Invoice, LineItem |

## Database and Migration Strategy

### Database Shape

SQLite with JSON fields.

### Migration Strategy

Alembic migrations are used.

### Cross-Module Boundaries

Invoices reference line items across services.
""",
    )


def test_overview_prose_quality_fail_on_empty(tmp_path: Path) -> None:
    """Test that empty overview produces FAIL with CONTENT_EMPTY reason code."""
    _write_minimum_with_sections(root=tmp_path)
    write_text(tmp_path / "docs/00-overview.md", "")

    result = VerifierService(tmp_path).verify(ci=True)
    # Find the overview-prose-quality check
    overview_check = next((c for c in result["checks"] if c["name"] == "overview-prose-quality"), None)
    assert overview_check is not None
    assert overview_check["status"] == "FAIL"
    assert "reason_code" in overview_check


def test_overview_prose_quality_fail_on_list_only(tmp_path: Path) -> None:
    """Test that list-only overview produces FAIL with CONTENT_LIST_ONLY reason code."""
    _write_minimum_with_sections(root=tmp_path)
    # Write overview with 5+ sections and >200 prose chars, but >70% list items
    # Need more list items to push ratio above 70%
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
    overview_check = next((c for c in result["checks"] if c["name"] == "overview-prose-quality"), None)
    assert overview_check is not None
    assert overview_check["status"] == "FAIL"
    # Should fail for list ratio, not prose length or sections
    assert overview_check.get("reason_code") == "CONTENT_LIST_ONLY"


def test_architecture_prose_quality_fail_on_missing_mermaid(tmp_path: Path) -> None:
    """Test that architecture without Mermaid produces FAIL with ARCH_MERMAID_MISSING reason code."""
    _write_minimum_with_sections(root=tmp_path)
    write_text(
        tmp_path / "docs/01-architecture.md",
        """# Architecture

## System Layers

No diagrams here, just text.

## Service Collaboration

More text without diagrams.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    arch_check = next((c for c in result["checks"] if c["name"] == "architecture-prose-quality"), None)
    assert arch_check is not None
    assert arch_check["status"] == "FAIL"
    assert arch_check.get("reason_code") == "ARCH_MERMAID_MISSING"


def test_architecture_prose_quality_fail_on_missing_layer_explanation(tmp_path: Path) -> None:
    """Test that architecture missing three-layer explanation produces FAIL."""
    _write_minimum_with_sections(root=tmp_path)
    # Provide 2 mermaid blocks to pass ARCH_MERMAID_INSUFFICIENT check
    # but don't reference the three-layer terms
    write_text(
        tmp_path / "docs/01-architecture.md",
        """# Architecture

```mermaid
graph TD
    A[Layer1] --> B[Layer2]
```

```mermaid
graph LR
    C[Service] --> D[Database]
```

## System Layers

Just some text describing the layers without specific references.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    arch_check = next((c for c in result["checks"] if c["name"] == "architecture-prose-quality"), None)
    assert arch_check is not None
    assert arch_check["status"] == "FAIL"
    assert arch_check.get("reason_code") == "ARCH_LAYER_EXPLANATION_MISSING"


def test_sections_exist_fail_on_missing_sections_dir(tmp_path: Path) -> None:
    """Test that missing docs/sections/ produces FAIL with STRUCT_SECTION_DIR_MISSING reason code."""
    _write_minimum_artifacts(tmp_path, with_module_doc=True)
    # Don't create docs/sections/

    result = VerifierService(tmp_path).verify(ci=True)
    sections_check = next((c for c in result["checks"] if c["name"] == "sections-exist"), None)
    assert sections_check is not None
    assert sections_check["status"] == "FAIL"
    assert sections_check.get("reason_code") == "STRUCT_SECTION_DIR_MISSING"


def test_sections_exist_fail_on_partial_sections(tmp_path: Path) -> None:
    """Test that partial section pages produce FAIL with STRUCT_MISSING_SECTIONS reason code."""
    _write_minimum_artifacts(tmp_path, with_module_doc=True)
    # Create only some section pages
    sections_dir = tmp_path / "docs/sections"
    sections_dir.mkdir(parents=True, exist_ok=True)

    # Only create project section
    project_dir = sections_dir / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    write_text(project_dir / "index.md", "# Project\n")

    result = VerifierService(tmp_path).verify(ci=True)
    sections_check = next((c for c in result["checks"] if c["name"] == "sections-exist"), None)
    assert sections_check is not None
    assert sections_check["status"] == "FAIL"
    assert sections_check.get("reason_code") == "STRUCT_MISSING_SECTIONS"


def test_sections_exist_pass_on_legacy_qs_flat_sections(tmp_path: Path) -> None:
    """Legacy Qxx/Sxx flat section files should pass section coverage in compatibility mode."""
    _write_minimum_artifacts(tmp_path, with_module_doc=True)
    sections_dir = tmp_path / "docs/sections"
    sections_dir.mkdir(parents=True, exist_ok=True)

    # Meet compatibility thresholds: >=8 total, >=4 Q, >=4 S
    for name in [
        "Q01-代码质量.md",
        "Q02-弹性.md",
        "Q03-性能.md",
        "Q04-并发.md",
        "S01-注入.md",
        "S02-认证.md",
        "S03-授权.md",
        "S04-数据安全.md",
    ]:
        write_text(sections_dir / name, f"# {name}\n")

    result = VerifierService(tmp_path).verify(ci=True)
    sections_check = next((c for c in result["checks"] if c["name"] == "sections-exist"), None)
    assert sections_check is not None
    assert sections_check["status"] == "PASS"
    assert sections_check["details"]["mode"] == "legacy_qs_compatibility"


def test_sections_exist_pass_on_alias_flat_markdown(tmp_path: Path) -> None:
    """Alias slugs in flat markdown form should satisfy canonical section checks."""
    _write_minimum_artifacts(tmp_path, with_module_doc=True)
    sections_dir = tmp_path / "docs/sections"
    sections_dir.mkdir(parents=True, exist_ok=True)

    # canonical project section
    write_text(sections_dir / "project.md", "# project\n")
    # alias files for remaining required sections
    alias_files = [
        "q01-architecture.md",
        "q02-services.md",
        "q04-data-model.md",
        "q05-api.md",
        "q06-operations.md",
        "q07-development.md",
        "q08-security.md",
        "q09-troubleshooting.md",
    ]
    for name in alias_files:
        write_text(sections_dir / name, f"# {name}\n")

    result = VerifierService(tmp_path).verify(ci=True)
    sections_check = next((c for c in result["checks"] if c["name"] == "sections-exist"), None)
    assert sections_check is not None
    assert sections_check["status"] == "PASS"


def test_api_aggregated_fail_on_endpoint_dump(tmp_path: Path) -> None:
    """Test that API contract with too many raw endpoints produces FAIL."""
    _write_minimum_with_sections(root=tmp_path)
    # Write API contract with >50 raw endpoints AND proper grouping sections
    endpoints = "\n".join([f"| GET | /api/item{i} | desc{i} |" for i in range(60)])
    write_text(
        tmp_path / "docs/04-api-contracts.md",
        f"""# API Contracts

## API Groups

## Call Conventions

### Authentication

Bearer token.

### Key Entry APIs

GET /health.

## Full Endpoint Index

{endpoints}
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    api_check = next((c for c in result["checks"] if c["name"] == "api-aggregated"), None)
    assert api_check is not None
    assert api_check["status"] == "FAIL"
    assert api_check.get("reason_code") == "AGG_API_ENDPOINT_DUMP"


def test_api_aggregated_fail_on_missing_grouping(tmp_path: Path) -> None:
    """Test that API contract without grouping section produces FAIL."""
    _write_minimum_with_sections(root=tmp_path)
    write_text(
        tmp_path / "docs/04-api-contracts.md",
        """# API Contracts

Just some text without proper sections.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    api_check = next((c for c in result["checks"] if c["name"] == "api-aggregated"), None)
    assert api_check is not None
    assert api_check["status"] == "FAIL"


def test_data_model_aggregated_fail_on_missing_sections(tmp_path: Path) -> None:
    """Test that data model without three sections produces FAIL."""
    _write_minimum_with_sections(root=tmp_path)
    write_text(
        tmp_path / "docs/05-data-model.md",
        """# Data Models

Only one section here.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    dm_check = next((c for c in result["checks"] if c["name"] == "data-model-aggregated"), None)
    assert dm_check is not None
    assert dm_check["status"] == "FAIL"
    assert dm_check.get("reason_code") == "AGG_DM_NOT_GROUPED"


def test_navigation_links_fail_on_broken_nav(tmp_path: Path) -> None:
    """Test that section page with broken navigation links produces FAIL."""
    _write_minimum_artifacts(tmp_path, with_module_doc=True)
    sections_dir = tmp_path / "docs/sections"
    sections_dir.mkdir(parents=True, exist_ok=True)

    # Create section with BROKEN navigation links (pointing to non-existent files)
    project_dir = sections_dir / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    write_text(
        project_dir / "index.md",
        """# Project

## Navigation

- [Overview](../../nonexistent-overview.md)
- [Architecture](../../nonexistent-architecture.md)
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    nav_check = next((c for c in result["checks"] if c["name"] == "navigation-links"), None)
    assert nav_check is not None
    assert nav_check["status"] == "FAIL"
    assert nav_check.get("reason_code") == "STRUCT_NAVIGATION_BROKEN"


def test_quality_pass_with_proper_content(tmp_path: Path) -> None:
    """Test that proper content passes all Phase 08 quality checks."""
    _write_quality_artifacts(root=tmp_path)

    result = VerifierService(tmp_path).verify(ci=True)

    # All Phase 08 checks should pass
    phase_08_checks = [
        "overview-prose-quality",
        "architecture-prose-quality",
        "sections-exist",
        "api-aggregated",
        "data-model-aggregated",
        "navigation-links",
    ]
    for check_name in phase_08_checks:
        check = next((c for c in result["checks"] if c["name"] == check_name), None)
        assert check is not None, f"Missing check: {check_name}"
        assert check["status"] == "PASS", f"Check {check_name} failed: {check['message']}"


def test_ci_output_includes_reason_codes(tmp_path: Path) -> None:
    """Test that CI mode output includes reason codes for WARN/FAIL."""
    _write_minimum_artifacts(tmp_path, with_module_doc=False)
    # Don't create sections - this should cause FAIL

    result = VerifierService(tmp_path).verify(ci=True)

    assert result["ci_mode"] is True
    assert "reason_codes" in result
    # Should have reason codes since we have failures
    assert len(result["reason_codes"]) > 0


def test_reason_codes_are_precise(tmp_path: Path) -> None:
    """Test that reason codes precisely identify the failure type."""
    _write_minimum_with_sections(root=tmp_path)
    # Write overview with only lists
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Overview

## Items

- item1
- item2
- item3
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)

    # Find the overview check with FAIL
    overview_check = next(
        (c for c in result["checks"] if c["name"] == "overview-prose-quality" and c["status"] == "FAIL"),
        None,
    )
    assert overview_check is not None
    # Should have a specific reason code
    assert "reason_code" in overview_check
    # Should be CONTENT_TOO_SHORT or CONTENT_LIST_ONLY
    assert overview_check["reason_code"] in ("CONTENT_TOO_SHORT", "CONTENT_LIST_ONLY")


# =============================================================================
# Phase 11: Hard Gate vs Soft Gate Tests
# =============================================================================


def test_hard_gate_failure_blocks_acceptance(tmp_path: Path) -> None:
    """Test that HARD gate failures block acceptance even with passing soft gates."""
    _write_minimum_with_sections(root=tmp_path)
    # Remove required files to trigger HARD gate failure
    (tmp_path / "ai/source-of-truth/repo-map.yaml").unlink()

    result = VerifierService(tmp_path).verify(ci=True)

    # Should have HARD gate failure
    assert result["summary"]["hard_gate_failures"] > 0
    # Acceptance should be blocked
    assert result["gate_summary"]["acceptance_blocked"] is True
    # Exit code should be 1 (hard gate failure)
    assert result["exit_code"] == 1
    # Grade should be FAIL
    assert result["grade"] == "FAIL"


def test_soft_gate_warning_with_passing_hard_gates(tmp_path: Path) -> None:
    """Test that SOFT gate failures produce WARN when hard gates pass."""
    _write_quality_artifacts(root=tmp_path)
    # Override overview to have low prose (soft gate failure)
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Overview

## Items

- item1
- item2
- item3
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)

    # Should have soft gate failures but no hard gate failures
    assert result["summary"]["soft_gate_failures"] > 0
    assert result["summary"]["hard_gate_failures"] == 0
    # Acceptance should NOT be blocked
    assert result["gate_summary"]["acceptance_blocked"] is False
    # Exit code should be 0 (soft gates don't block by default)
    assert result["exit_code"] == 0
    # Grade should be WARN (soft gate failures present)
    assert result["grade"] == "WARN"


def test_hard_gate_codes_are_correctly_classified(tmp_path: Path) -> None:
    """Test that specific reason codes are classified as HARD gates."""
    _write_minimum_artifacts(tmp_path, with_module_doc=True)
    # Don't create docs/sections/ to trigger STRUCT_SECTION_DIR_MISSING

    result = VerifierService(tmp_path).verify(ci=True)

    # Find the sections-exist check
    sections_check = next((c for c in result["checks"] if c["name"] == "sections-exist"), None)
    assert sections_check is not None
    assert sections_check["status"] == "FAIL"
    assert sections_check["gate_type"] == "HARD"


def test_soft_gate_codes_are_correctly_classified(tmp_path: Path) -> None:
    """Test that quality reason codes are classified as SOFT gates."""
    _write_quality_artifacts(root=tmp_path)
    # Override overview to have low prose
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Overview

## Items

- item1
- item2
- item3
- item4
- item5
- item6
- item7
- item8
- item9
- item10
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)

    # Find the overview-prose-quality check
    overview_check = next((c for c in result["checks"] if c["name"] == "overview-prose-quality"), None)
    assert overview_check is not None
    assert overview_check["status"] == "FAIL"
    # Should be soft gate (list-only content)
    assert overview_check["gate_type"] == "SOFT"


def test_empty_content_is_hard_gate(tmp_path: Path) -> None:
    """Test that empty/missing content files trigger HARD gate failures."""
    _write_minimum_with_sections(root=tmp_path)
    # Create empty overview
    write_text(tmp_path / "docs/00-overview.md", "")

    result = VerifierService(tmp_path).verify(ci=True)

    # Find the overview-prose-quality check
    overview_check = next((c for c in result["checks"] if c["name"] == "overview-prose-quality"), None)
    assert overview_check is not None
    assert overview_check["status"] == "FAIL"
    # Empty content is HARD gate
    assert overview_check["gate_type"] == "HARD"


def test_gate_summary_accurate(tmp_path: Path) -> None:
    """Test that gate_summary reflects actual gate status."""
    _write_quality_artifacts(root=tmp_path)

    result = VerifierService(tmp_path).verify(ci=True)

    # With all quality content, no gates should fail
    assert result["gate_summary"]["hard_gate_blocking"] is False
    assert result["gate_summary"]["soft_gate_warnings"] is False
    assert result["gate_summary"]["acceptance_blocked"] is False


def test_custom_severity_thresholds_fail_on_soft(tmp_path: Path) -> None:
    """Test that custom severity thresholds can make soft gates fail."""
    _write_quality_artifacts(root=tmp_path)
    # Override overview with 5+ sections but short prose (<200 chars) to trigger CONTENT_TOO_SHORT
    write_text(
        tmp_path / "docs/00-overview.md",
        """# Overview

## Project Description

## Core Problem

## Core Capabilities

## Environment Requirements

## Startup Commands

X.
""",
    )

    # Create thresholds that treat CONTENT_TOO_SHORT as blocking
    # Also include CITATION_MISSING in soft codes to prevent it from being HARD gate
    from repo_wiki.verifier.service import SeverityThreshold
    custom_thresholds = SeverityThreshold(
        soft_gate_codes={"CONTENT_TOO_SHORT", "CITATION_MISSING"},  # Make CONTENT_TOO_SHORT blocking
        warn_on_soft=False,  # Don't warn, fail
    )

    result = VerifierService(tmp_path, severity_thresholds=custom_thresholds).verify(ci=True)

    # Should now have exit_code 2 for soft gate failure (since soft gates are now blocking)
    assert result["exit_code"] == 2
    assert result["grade"] == "FAIL"


def test_verify_result_includes_gate_type_in_checks(tmp_path: Path) -> None:
    """Test that verify result includes gate_type in each check."""
    _write_minimum_artifacts(tmp_path, with_module_doc=False)

    result = VerifierService(tmp_path).verify(ci=True)

    for check in result["checks"]:
        assert "gate_type" in check
        assert check["gate_type"] in ("HARD", "SOFT")


def test_hard_gate_cannot_be_overridden(tmp_path: Path) -> None:
    """Test that hard gate failures cannot be overridden by soft gate passes."""
    _write_quality_artifacts(root=tmp_path)
    # Remove a critical file to cause HARD gate failure
    (tmp_path / "docs/00-overview.md").unlink()

    result = VerifierService(tmp_path).verify(ci=True)

    # Even though other soft gates might pass, hard gate failure blocks
    assert result["summary"]["hard_gate_failures"] > 0
    assert result["gate_summary"]["acceptance_blocked"] is True
    assert result["grade"] == "FAIL"


def test_severity_threshold_is_blocking(tmp_path: Path) -> None:
    """Test SeverityThreshold.is_blocking method."""
    from repo_wiki.verifier.service import SeverityThreshold

    thresholds = SeverityThreshold()

    # HARD gate codes should be blocking
    assert thresholds.is_blocking("STRUCT_SECTION_DIR_MISSING") is True
    assert thresholds.is_blocking("STRUCT_NAV_TARGET_MISSING") is True
    assert thresholds.is_blocking("CONTENT_EMPTY") is True

    # SOFT gate codes should NOT be blocking by default
    assert thresholds.is_blocking("CONTENT_TOO_SHORT") is False
    assert thresholds.is_blocking("CONTENT_LIST_ONLY") is False
    assert thresholds.is_blocking("ARCH_MERMAID_MISSING") is False


def test_gate_type_enum_values(tmp_path: Path) -> None:
    """Test GateType enum has correct values."""
    from repo_wiki.verifier.service import GateType

    assert GateType.HARD.value == "HARD"
    assert GateType.SOFT.value == "SOFT"


# =============================================================================
# Phase 13: Section Compatibility Bridge Tests
# =============================================================================


def test_alias_resolution_evidence_in_details(tmp_path: Path) -> None:
    """Test that alias resolution evidence is included in sections-exist check details."""
    _write_minimum_artifacts(tmp_path, with_module_doc=True)
    sections_dir = tmp_path / "docs/sections"
    sections_dir.mkdir(parents=True, exist_ok=True)

    # Create some canonical sections and some alias sections
    # Canonical: project
    project_dir = sections_dir / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    write_text(project_dir / "index.md", "# Project\n")

    # Alias: q01-architecture (alias for architecture)
    write_text(sections_dir / "q01-architecture.md", "# Architecture\n")

    # No sections for services, data-model, api, etc. -> will be missing

    result = VerifierService(tmp_path).verify(ci=True)
    sections_check = next((c for c in result["checks"] if c["name"] == "sections-exist"), None)

    assert sections_check is not None
    # Should have alias_resolutions in details
    assert "alias_resolutions" in sections_check["details"]
    assert "alias_details" in sections_check["details"]

    # project should be resolved via canonical
    assert sections_check["details"]["alias_resolutions"].get("project") == "canonical"
    # q01-architecture should be resolved via alias (if checked)
    # Missing sections should have "missing" resolution


def test_alias_resolution_evidence_in_legacy_mode(tmp_path: Path) -> None:
    """Test that alias resolution evidence is included in legacy Qxx/Sxx compatibility mode."""
    _write_minimum_artifacts(tmp_path, with_module_doc=True)
    sections_dir = tmp_path / "docs/sections"
    sections_dir.mkdir(parents=True, exist_ok=True)

    # Create qualified legacy profile (>=8 total, >=4 Q, >=4 S)
    for name in [
        "Q01-代码质量.md",
        "Q02-弹性.md",
        "Q03-性能.md",
        "Q04-并发.md",
        "S01-注入.md",
        "S02-认证.md",
        "S03-授权.md",
        "S04-数据安全.md",
    ]:
        write_text(sections_dir / name, f"# {name}\n")

    result = VerifierService(tmp_path).verify(ci=True)
    sections_check = next((c for c in result["checks"] if c["name"] == "sections-exist"), None)

    assert sections_check is not None
    assert sections_check["status"] == "PASS"
    assert sections_check["details"]["mode"] == "legacy_qs_compatibility"
    # Should have alias_resolutions showing all as "missing"
    assert "alias_resolutions" in sections_check["details"]
    # Should have legacy_file_mapping
    assert "legacy_file_mapping" in sections_check["details"]
    assert len(sections_check["details"]["legacy_file_mapping"]) >= 8


def test_canonical_only_mode(tmp_path: Path) -> None:
    """Test verification with only canonical section directories (no aliases)."""
    _write_minimum_artifacts(tmp_path, with_module_doc=True)
    sections_dir = tmp_path / "docs/sections"
    sections_dir.mkdir(parents=True, exist_ok=True)

    # Create all required canonical sections as directories
    for section in ["project", "architecture", "services", "data-model", "api", "operations", "development", "security", "troubleshooting"]:
        section_dir = sections_dir / section
        section_dir.mkdir(parents=True, exist_ok=True)
        write_text(section_dir / "index.md", f"# {section}\n")

    result = VerifierService(tmp_path).verify(ci=True)
    sections_check = next((c for c in result["checks"] if c["name"] == "sections-exist"), None)

    assert sections_check is not None
    assert sections_check["status"] == "PASS"
    # Should not be legacy mode when all canonical sections exist
    assert sections_check["details"].get("mode") != "legacy_qs_compatibility"
    # All should be resolved via canonical
    for section in ["project", "architecture", "services", "data-model", "api", "operations", "development", "security"]:
        assert sections_check["details"]["alias_resolutions"].get(section) == "canonical"


def test_alias_only_mode(tmp_path: Path) -> None:
    """Test verification with only alias section files (no canonical directories)."""
    _write_minimum_artifacts(tmp_path, with_module_doc=True)
    sections_dir = tmp_path / "docs/sections"
    sections_dir.mkdir(parents=True, exist_ok=True)

    # Create alias files for all required sections (flat markdown, not directories)
    alias_files = [
        "q01-architecture.md",
        "q02-services.md",
        "q03-python-services.md",
        "q04-data-model.md",
        "q05-api.md",
        "q06-operations.md",
        "q07-development.md",
        "q08-security.md",
        "q09-troubleshooting.md",
        "project.md",  # project has no alias, so use canonical flat
    ]
    for name in alias_files:
        write_text(sections_dir / name, f"# {name}\n")

    result = VerifierService(tmp_path).verify(ci=True)
    sections_check = next((c for c in result["checks"] if c["name"] == "sections-exist"), None)

    assert sections_check is not None
    assert sections_check["status"] == "PASS"
    # Should have some alias resolutions
    assert "alias_resolutions" in sections_check["details"]


def test_mixed_mode_canonical_and_alias(tmp_path: Path) -> None:
    """Test verification with mixed canonical directories and alias files."""
    _write_minimum_artifacts(tmp_path, with_module_doc=True)
    sections_dir = tmp_path / "docs/sections"
    sections_dir.mkdir(parents=True, exist_ok=True)

    # Canonical: project, architecture
    for section in ["project", "architecture"]:
        section_dir = sections_dir / section
        section_dir.mkdir(parents=True, exist_ok=True)
        write_text(section_dir / "index.md", f"# {section}\n")

    # Alias: q02-services, q04-data-model, q05-api, q06-operations, q07-development, q08-security, q09-troubleshooting
    alias_files = [
        "q02-services.md",
        "q04-data-model.md",
        "q05-api.md",
        "q06-operations.md",
        "q07-development.md",
        "q08-security.md",
        "q09-troubleshooting.md",
    ]
    for name in alias_files:
        write_text(sections_dir / name, f"# {name}\n")

    result = VerifierService(tmp_path).verify(ci=True)
    sections_check = next((c for c in result["checks"] if c["name"] == "sections-exist"), None)

    assert sections_check is not None
    assert sections_check["status"] == "PASS"
    # Check mixed resolutions
    resolutions = sections_check["details"]["alias_resolutions"]
    assert resolutions.get("project") == "canonical"
    assert resolutions.get("architecture") == "canonical"
    assert resolutions.get("services") == "alias"
    assert resolutions.get("data-model") == "alias"
    assert resolutions.get("api") == "alias"


def test_legacy_mode_with_some_aliases(tmp_path: Path) -> None:
    """Test legacy mode still works when some canonical/alias sections also exist."""
    _write_minimum_artifacts(tmp_path, with_module_doc=True)
    sections_dir = tmp_path / "docs/sections"
    sections_dir.mkdir(parents=True, exist_ok=True)

    # Create some canonical/alias sections
    project_dir = sections_dir / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    write_text(project_dir / "index.md", "# Project\n")

    # Create legacy Qxx/Sxx files to meet threshold
    for name in [
        "Q01-代码质量.md",
        "Q02-弹性.md",
        "Q03-性能.md",
        "Q04-并发.md",
        "S01-注入.md",
        "S02-认证.md",
        "S03-授权.md",
        "S04-数据安全.md",
    ]:
        write_text(sections_dir / name, f"# {name}\n")

    result = VerifierService(tmp_path).verify(ci=True)
    sections_check = next((c for c in result["checks"] if c["name"] == "sections-exist"), None)

    assert sections_check is not None
    assert sections_check["status"] == "PASS"
    # Should still use legacy mode since not all canonical sections exist
    assert sections_check["details"]["mode"] == "legacy_qs_compatibility"


def test_legacy_profile_not_qualified_falls_back_to_fail(tmp_path: Path) -> None:
    """Test that unqualified legacy profile falls back to FAIL when canonical sections missing."""
    _write_minimum_artifacts(tmp_path, with_module_doc=True)
    sections_dir = tmp_path / "docs/sections"
    sections_dir.mkdir(parents=True, exist_ok=True)

    # Create ONLY 2 Qxx files and 1 Sxx file - NOT qualified (<8 total, <4 Q, <4 S)
    for name in [
        "Q01-代码质量.md",
        "Q02-弹性.md",
        "S01-注入.md",
    ]:
        write_text(sections_dir / name, f"# {name}\n")

    result = VerifierService(tmp_path).verify(ci=True)
    sections_check = next((c for c in result["checks"] if c["name"] == "sections-exist"), None)

    assert sections_check is not None
    assert sections_check["status"] == "FAIL"
    # Should not be legacy mode since not qualified
    assert sections_check["details"].get("mode") != "legacy_qs_compatibility"
    assert sections_check.get("reason_code") == "STRUCT_MISSING_SECTIONS"
