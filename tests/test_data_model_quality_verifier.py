"""Tests for Data Model Quality Verifier - Phase 26 Task 26.6.

These tests validate that data model documentation meets quality standards for:
- Raw model dump detection (detecting model listings without proper grouping)
- Entity grouping validation (core entities vs DTOs vs other types)
- Migration coverage validation
- Canonical model vs DTO distinction
- Strict profile enforcement

Phase 26 - Task 26.6: Data model quality verifier

Test coverage:
- Raw model dump detection
- Entity grouping validation
- Migration coverage validation
- Canonical model vs DTO distinction
- Strict profile enforcement for model dumps
"""

from __future__ import annotations

from pathlib import Path

from repo_wiki.generator.io import write_json, write_text
from repo_wiki.verifier.service import SeverityThreshold, VerifierService

# =============================================================================
# FIXTURES
# =============================================================================


def _write_minimum_artifacts(root: Path) -> None:
    """Write minimum artifacts for data model quality tests."""
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
        {
            "endpoints": [
                {
                    "method": "GET",
                    "path": "/health",
                    "module": "billing",
                    "handler": "h",
                    "file_path": "src/billing/api.py",
                },
            ]
        },
    )
    write_json(
        root / "ai/source-of-truth/data-models.yaml",
        {
            "models": [
                {
                    "name": "Invoice",
                    "type": "python_class",
                    "module": "billing",
                    "file_path": "src/billing/model.py",
                },
                {
                    "name": "InvoiceDTO",
                    "type": "dto",
                    "module": "billing",
                    "file_path": "src/billing/dto.py",
                },
                {
                    "name": "LineItem",
                    "type": "python_class",
                    "module": "billing",
                    "file_path": "src/billing/model.py",
                },
            ]
        },
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
    write_text(
        root / ".codex/config.toml",
        'project = "repo-wiki"\n[knowledge]\npath_1 = "docs/00-overview.md"\n',
    )
    write_json(root / ".codex/hooks.json", {"post_commands": []})


def _write_quality_artifacts(root: Path) -> None:
    """Write artifacts that pass data model quality checks."""
    # Create base structure first
    for d in [
        root / "ai/source-of-truth/prompt-fragments",
        root / "docs",
        root / "docs/sections/project",
        root / "docs/sections/architecture",
        root / "docs/sections/services",
        root / "docs/sections/data-model",
        root / "docs/sections/api",
        root / "docs/sections/operations",
        root / "docs/sections/development",
        root / "docs/sections/security",
        root / "docs/sections/troubleshooting",
        root / "docs/modules",
        root / "src/billing",
        root / ".claude",
        root / ".opencode",
        root / ".codex",
    ]:
        d.mkdir(parents=True, exist_ok=True)

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
        {
            "endpoints": [
                {
                    "method": "GET",
                    "path": "/health",
                    "module": "billing",
                    "handler": "h",
                    "file_path": "src/billing/api.py",
                },
                {
                    "method": "POST",
                    "path": "/billing",
                    "module": "billing",
                    "handler": "create_billing",
                    "file_path": "src/billing/api.py",
                },
            ]
        },
    )
    write_json(
        root / "ai/source-of-truth/data-models.yaml",
        {
            "models": [
                {
                    "name": "Invoice",
                    "type": "python_class",
                    "module": "billing",
                    "file_path": "src/billing/model.py",
                    "model_category": "core_entity",
                    "is_canonical": True,
                    "canonical_name": "Invoice",
                },
                {
                    "name": "InvoiceDTO",
                    "type": "dto",
                    "module": "billing",
                    "file_path": "src/billing/dto.py",
                    "model_category": "dto",
                    "is_canonical": False,
                },
                {
                    "name": "LineItem",
                    "type": "python_class",
                    "module": "billing",
                    "file_path": "src/billing/model.py",
                    "model_category": "core_entity",
                    "is_canonical": True,
                    "canonical_name": "LineItem",
                },
            ]
        },
    )
    write_json(root / "ai/source-of-truth/task-catalog.yaml", {"tasks": []})
    write_text(root / "ai/source-of-truth/prompt-fragments/overview.txt", "overview")
    write_text(root / "ai/source-of-truth/prompt-fragments/architecture.txt", "arch")

    # Create source files for citations
    write_text(
        root / "src/billing/api.py",
        "def health():\n    return 'ok'\n\ndef create_billing():\n    pass\n",
    )
    write_text(
        root / "src/billing/model.py",
        "class Invoice:\n    def __init__(self):\n        self.amount = 0\n\nclass LineItem:\n    def __init__(self):\n        self.quantity = 0\n",
    )
    write_text(
        root / "src/billing/dto.py",
        "class InvoiceDTO:\n    def __init__(self):\n        self.amount = 0\n",
    )

    # Write quality overview (200+ prose chars, 5+ sections, proper citations)
    write_text(
        root / "docs/00-overview.md",
        """# Project Overview

This is the project overview page with substantial prose content describing the system in detail.

See <cite>src/billing/api.py:1</cite> for the billing API implementation.

## Project Description

The project solves the core problem of documentation generation through automated scanning and wiki generation.

## Core Problem

We need better way to document repositories with minimal manual effort while maintaining high quality.

## Core Capabilities

The system can scan code, index modules and endpoints, generate documentation, and verify quality.

## Environment Requirements

Python 3.10+ is required along with uv package manager.

## Startup Commands

Run `uv install` to install dependencies.

## Reading Navigation

See [Architecture](01-architecture.md) for system design details.
""",
    )

    # Write quality architecture (2+ mermaid diagrams, three-layer explanation, citations)
    write_text(
        root / "docs/01-architecture.md",
        """# Architecture

See <cite>src/billing/api.py:1-5</cite> for the API implementation.

## System Layers

The system is organized into three distinct layers.

```mermaid
graph TD
    A[.repo-wiki/] --> B[ai/source-of-truth/]
    B --> C[docs/]
```

## Service Collaboration

Services work together to provide documentation generation.

```mermaid
graph LR
    A[Scanner] --> B[Indexer]
    B --> C[Generator]
    C --> D[Verifier]
```

## Core Data Flow

Data flows from source code through the pipeline to generated documentation.

## Storage and Retrieval Design

We store metadata in structured formats and retrieve via search when needed.

## Three Layer Architecture

1. .repo-wiki/ - runtime storage and execution
2. ai/source-of-truth/ - structured facts and source of truth
3. docs/ - human-readable documentation output
""",
    )

    # Write module map with citation
    write_text(
        root / "docs/03-module-map.md",
        """# Module Map

See <cite>src/billing/model.py:1</cite> for the Invoice model.

## Modules

The billing module handles all billing operations.
""",
    )

    # Write quality API contracts
    write_text(
        root / "docs/04-api-contracts.md",
        """# API Contracts

See <cite>src/billing/api.py:1</cite> for the health endpoint implementation.

## API Groups

| Service | Auth | Endpoints |
|---------|------|-----------|
| billing | Bearer | 2 |

## Call Conventions

### Authentication

Bearer token authentication is required for all endpoints except /health.
Token is passed in Authorization header: `Authorization: Bearer <token>`

### Error and Status Codes

- 400 Bad Request - Invalid input data
- 401 Unauthorized - Missing or invalid token
- 404 Not Found - Resource not found
- 500 Internal Server Error - Server error

## Key Entry APIs

These are the primary entry points for the billing API:

- GET /health - Health check (no auth required)
- POST /billing - Create billing record

## Full Endpoint Index

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| POST | /billing | Create billing |
""",
    )

    # Write quality data model with proper aggregation, canonical vs DTO distinction, and migration
    write_text(
        root / "docs/05-data-model.md",
        """# Data Models

See <cite>src/billing/model.py:1</cite> for the Invoice model.

## Core Data Models

### Core Model List

| Model | Type | Module | Category |
|-------|------|--------|----------|
| Invoice | python_class | billing | Core Entity |
| LineItem | python_class | billing | Core Entity |

## Service Data Models

### By Service

| Service | Models |
|---------|--------|
| billing | InvoiceDTO (DTO) |

### Canonical vs DTO Distinction

Canonical models represent core business entities:
- Invoice: Main billing entity with amount and status
- LineItem: Individual line items in an invoice

DTOs (Data Transfer Objects) are projections for API responses:
- InvoiceDTO: Simplified view of Invoice for API clients

## Database and Migration Strategy

### Database Shape

SQLite with JSON fields for flexibility.

### Migration Strategy

Alembic migrations are used for schema changes. See <cite>src/billing/model.py:1</cite> for model definitions.

### Cross-Module Boundaries

Invoices reference line items across services.
""",
    )

    # Create section pages
    sections = [
        "project",
        "architecture",
        "services",
        "data-model",
        "api",
        "operations",
        "development",
        "security",
        "troubleshooting",
    ]
    for section in sections:
        write_text(
            root / f"docs/sections/{section}/index.md",
            f"""# {section.title()}

This is the {section} section with substantial content.

## Content

Describing the {section} section in detail with prose.
""",
        )

    write_text(root / "docs/modules/billing.md", "module")
    write_json(root / ".claude/settings.json", {"knowledge_base": ["docs/00-overview.md"]})
    write_text(root / ".claude/CLAUDE.md", "`docs/00-overview.md`")
    write_text(root / "AGENTS.md", "`docs/01-architecture.md`\n`http://localhost:8007`")
    write_json(root / ".opencode/opencode.json", {"knowledge_paths": ["docs/00-overview.md"]})
    write_text(
        root / ".codex/config.toml",
        'project = "repo-wiki"\n[knowledge]\npath_1 = "docs/00-overview.md"\n',
    )
    write_json(root / ".codex/hooks.json", {"post_commands": []})


# =============================================================================
# RAW MODEL DUMP DETECTION TESTS
# =============================================================================


def test_model_dump_detection_raw_models_only(tmp_path: Path) -> None:
    """Test that data model doc with only raw models (no grouping) is flagged as model dump."""
    _write_minimum_artifacts(root=tmp_path)

    # Create model dump content - raw model tables without any grouping or prose
    models = "\n".join([f"| Model{i} | python_class | module{i} |" for i in range(40)])
    write_text(
        tmp_path / "docs/05-data-model.md",
        f"""# Data Models

{models}
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    dm_check = next((c for c in result["checks"] if c["name"] == "data-model-aggregated"), None)
    assert dm_check is not None
    assert dm_check["status"] == "FAIL"
    assert dm_check.get("reason_code") == "AGG_DM_NOT_GROUPED"


def test_model_dump_detection_too_many_models(tmp_path: Path) -> None:
    """Test that data model doc with >30 raw models (but proper sections) is flagged as model dump."""
    _write_minimum_artifacts(root=tmp_path)

    # Create content with all required sections but too many raw models
    models = "\n".join([f"| Model{i} | python_class | module{i} |" for i in range(40)])
    write_text(
        tmp_path / "docs/05-data-model.md",
        f"""# Data Models

## Core Data Models

### Core Model List

| Model | Type | Module | Description |
|-------|------|--------|-------------|
| Invoice | python_class | billing | Billing entity |

## Service Data Models

### By Service

| Service | Models |
|---------|--------|
| billing | BillingService |

## Database and Migration Strategy

### Database Shape

SQLite with JSON fields.

### Migration Strategy

Alembic migrations are used.

## Model Index

{models}
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    dm_check = next((c for c in result["checks"] if c["name"] == "data-model-aggregated"), None)
    assert dm_check is not None
    assert dm_check["status"] == "FAIL"
    assert dm_check.get("reason_code") == "AGG_DM_MODEL_DUMP"


def test_model_dump_detection_missing_grouping(tmp_path: Path) -> None:
    """Test that data model doc missing required sections fails."""
    _write_minimum_artifacts(root=tmp_path)

    write_text(
        tmp_path / "docs/05-data-model.md",
        """# Data Models

This is a data model document without proper grouping.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    dm_check = next((c for c in result["checks"] if c["name"] == "data-model-aggregated"), None)
    assert dm_check is not None
    assert dm_check["status"] == "FAIL"
    assert dm_check.get("reason_code") == "AGG_DM_NOT_GROUPED"


def test_model_dump_detection_missing_core_section(tmp_path: Path) -> None:
    """Test that data model doc missing core data models section fails."""
    _write_minimum_artifacts(root=tmp_path)

    write_text(
        tmp_path / "docs/05-data-model.md",
        """# Data Models

## Service Data Models

### By Service

| Service | Models |
|---------|--------|
| billing | Invoice |

## Database and Migration Strategy

### Migration Strategy

Alembic migrations are used.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    dm_check = next((c for c in result["checks"] if c["name"] == "data-model-aggregated"), None)
    assert dm_check is not None
    assert dm_check["status"] == "FAIL"


def test_model_dump_detection_missing_service_section(tmp_path: Path) -> None:
    """Test that data model doc missing service data models section fails."""
    _write_minimum_artifacts(root=tmp_path)

    write_text(
        tmp_path / "docs/05-data-model.md",
        """# Data Models

## Core Data Models

### Core Model List

| Model | Type | Module | Description |
|-------|------|--------|-------------|
| Invoice | python_class | billing | Billing entity |

## Database and Migration Strategy

### Migration Strategy

Alembic migrations are used.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    dm_check = next((c for c in result["checks"] if c["name"] == "data-model-aggregated"), None)
    assert dm_check is not None
    assert dm_check["status"] == "FAIL"


def test_model_dump_detection_missing_migration(tmp_path: Path) -> None:
    """Test that data model doc missing migration strategy fails."""
    _write_minimum_artifacts(root=tmp_path)

    write_text(
        tmp_path / "docs/05-data-model.md",
        """# Data Models

## Core Data Models

### Core Model List

| Model | Type | Module | Description |
|-------|------|--------|-------------|
| Invoice | python_class | billing | Billing entity |

## Service Data Models

### By Service

| Service | Models |
|---------|--------|
| billing | Invoice |
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    dm_check = next((c for c in result["checks"] if c["name"] == "data-model-aggregated"), None)
    assert dm_check is not None
    assert dm_check["status"] == "FAIL"
    assert dm_check.get("reason_code") == "AGG_DM_NOT_GROUPED"


# =============================================================================
# CANONICAL VS DTO DISTINCTION TESTS
# =============================================================================


def test_canonical_vs_dto_distinction_present(tmp_path: Path) -> None:
    """Test that data model doc with canonical vs DTO distinction passes."""
    _write_quality_artifacts(root=tmp_path)

    result = VerifierService(tmp_path).verify(ci=True)
    dm_check = next((c for c in result["checks"] if c["name"] == "data-model-aggregated"), None)
    assert dm_check is not None
    assert dm_check["status"] == "PASS"


def test_data_model_refs_validates_model_types(tmp_path: Path) -> None:
    """Test that data model refs check validates model types."""
    _write_minimum_artifacts(root=tmp_path)

    result = VerifierService(tmp_path).verify(ci=True)
    dm_refs_check = next((c for c in result["checks"] if c["name"] == "data-model-refs"), None)
    assert dm_refs_check is not None
    assert dm_refs_check["status"] == "PASS"


def test_data_model_refs_detects_dangling(tmp_path: Path) -> None:
    """Test that data model refs check detects dangling module references."""
    _write_minimum_artifacts(root=tmp_path)

    # Update data-models.yaml to have a model with unknown module
    write_json(
        tmp_path / "ai/source-of-truth/data-models.yaml",
        {
            "models": [
                {
                    "name": "Invoice",
                    "type": "python_class",
                    "module": "billing",
                    "file_path": "src/billing/model.py",
                },
                {
                    "name": "UnknownModel",
                    "type": "python_class",
                    "module": "nonexistent",
                    "file_path": "src/nonexistent/model.py",
                },
            ]
        },
    )

    result = VerifierService(tmp_path).verify(ci=True)
    dm_refs_check = next((c for c in result["checks"] if c["name"] == "data-model-refs"), None)
    assert dm_refs_check is not None
    assert dm_refs_check["status"] == "FAIL"


def test_model_type_classification_in_data_models_yaml(tmp_path: Path) -> None:
    """Test that model type classification (canonical vs DTO) is preserved in data-models.yaml."""
    _write_quality_artifacts(root=tmp_path)

    import yaml

    data_models_path = tmp_path / "ai/source-of-truth/data-models.yaml"
    with open(data_models_path) as f:
        data = yaml.safe_load(f)

    models = data.get("models", [])
    invoice = next((m for m in models if m.get("name") == "Invoice"), None)
    invoice_dto = next((m for m in models if m.get("name") == "InvoiceDTO"), None)

    assert invoice is not None
    assert invoice_dto is not None
    # Invoice should be canonical core entity
    assert invoice.get("model_category") == "core_entity"
    assert invoice.get("is_canonical") is True
    # InvoiceDTO should be a DTO
    assert invoice_dto.get("model_category") == "dto"
    assert invoice_dto.get("is_canonical") is False


# =============================================================================
# MIGRATION COVERAGE TESTS
# =============================================================================


def test_migration_coverage_alembic_documented(tmp_path: Path) -> None:
    """Test that Alembic migration strategy is properly documented."""
    _write_quality_artifacts(root=tmp_path)

    result = VerifierService(tmp_path).verify(ci=True)
    dm_check = next((c for c in result["checks"] if c["name"] == "data-model-aggregated"), None)
    assert dm_check is not None
    assert dm_check["status"] == "PASS"


def test_migration_coverage_missing_in_data_model(tmp_path: Path) -> None:
    """Test that missing migration documentation is flagged."""
    _write_minimum_artifacts(root=tmp_path)

    write_text(
        tmp_path / "docs/05-data-model.md",
        """# Data Models

## Core Data Models

### Core Model List

| Model | Type | Module | Description |
|-------|------|--------|-------------|
| Invoice | python_class | billing | Billing entity |

## Service Data Models

### By Service

| Service | Models |
|---------|--------|
| billing | Invoice |
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    dm_check = next((c for c in result["checks"] if c["name"] == "data-model-aggregated"), None)
    assert dm_check is not None
    assert dm_check["status"] == "FAIL"


def test_migration_strategy_documented(tmp_path: Path) -> None:
    """Test that migration strategy is properly documented in data model."""
    _write_quality_artifacts(root=tmp_path)

    dm_path = tmp_path / "docs/05-data-model.md"
    content = dm_path.read_text()

    # Should mention migration
    assert "migration" in content.lower() or "迁移" in content


# =============================================================================
# CITATION VALIDATION FOR DATA MODEL
# =============================================================================


def test_citation_present_in_data_model_doc(tmp_path: Path) -> None:
    """Test that data model doc with citations passes citation coverage check."""
    _write_quality_artifacts(root=tmp_path)

    result = VerifierService(tmp_path).verify(ci=True)
    citation_check = next((c for c in result["checks"] if c["name"] == "citation-coverage"), None)
    assert citation_check is not None
    assert citation_check["status"] == "PASS"


def test_citation_missing_in_data_model_doc(tmp_path: Path) -> None:
    """Test that data model doc without citations fails citation coverage check."""
    _write_minimum_artifacts(root=tmp_path)

    write_text(
        tmp_path / "docs/05-data-model.md",
        """# Data Models

## Core Data Models

### Core Model List

| Model | Type | Module | Description |
|-------|------|--------|-------------|
| Invoice | python_class | billing | Billing entity |

## Service Data Models

### By Service

| Service | Models |
|---------|--------|
| billing | InvoiceDTO |

## Database and Migration Strategy

### Migration Strategy

Alembic migrations are used.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)
    citation_check = next((c for c in result["checks"] if c["name"] == "citation-coverage"), None)
    assert citation_check is not None
    assert citation_check["status"] == "FAIL"


# =============================================================================
# STRICT PROFILE TESTS
# =============================================================================


def test_strict_profile_model_dump_fails(tmp_path: Path) -> None:
    """Test that model dump fails in strict profile (soft gates become blocking)."""
    _write_minimum_artifacts(root=tmp_path)

    # Create endpoint dump content with all sections but too many raw models
    models = "\n".join([f"| Model{i} | python_class | module{i} |" for i in range(40)])
    write_text(
        tmp_path / "docs/05-data-model.md",
        f"""# Data Models

## Core Data Models

### Core Model List

| Model | Type | Module | Description |
|-------|------|--------|-------------|
| Invoice | python_class | billing | Billing entity |

## Service Data Models

### By Service

| Service | Models |
|---------|--------|
| billing | InvoiceDTO |

## Database and Migration Strategy

### Migration Strategy

Alembic migrations are used.

## Model Index

{models}
""",
    )

    # Use strict profile - soft gates become blocking
    strict_thresholds = SeverityThreshold(
        soft_gate_codes={"AGG_DM_MODEL_DUMP", "AGG_DM_NOT_GROUPED"},
        warn_on_soft=False,  # Fail instead of warn
    )

    result = VerifierService(tmp_path, severity_thresholds=strict_thresholds).verify(ci=True)

    # Should have model dump failure
    dm_check = next((c for c in result["checks"] if c["name"] == "data-model-aggregated"), None)
    assert dm_check is not None
    assert dm_check["status"] == "FAIL"
    assert dm_check.get("reason_code") == "AGG_DM_MODEL_DUMP"

    # In strict mode with warn_on_soft=False, soft gate becomes blocking
    soft_failures = result["summary"]["soft_gate_failures"]
    assert soft_failures > 0


def test_strict_profile_quality_artifacts_pass(tmp_path: Path) -> None:
    """Test that quality data model artifacts pass even in strict profile."""
    _write_quality_artifacts(root=tmp_path)

    # Use strict profile
    strict_thresholds = SeverityThreshold(
        soft_gate_codes={"AGG_DM_MODEL_DUMP", "AGG_DM_NOT_GROUPED"},
        warn_on_soft=False,
    )

    result = VerifierService(tmp_path, severity_thresholds=strict_thresholds).verify(ci=True)

    dm_check = next((c for c in result["checks"] if c["name"] == "data-model-aggregated"), None)
    assert dm_check is not None
    assert dm_check["status"] == "PASS"


# =============================================================================
# REASON CODES TESTS
# =============================================================================


def test_reason_code_model_dump(tmp_path: Path) -> None:
    """Test that AGG_DM_MODEL_DUMP reason code is returned for model dumps."""
    _write_minimum_artifacts(root=tmp_path)

    # Create model dump content
    models = "\n".join([f"| Model{i} | python_class | module{i} |" for i in range(40)])
    write_text(
        tmp_path / "docs/05-data-model.md",
        f"""# Data Models

## Core Data Models

### Core Model List

| Model | Type | Module | Description |
|-------|------|--------|-------------|
| Invoice | python_class | billing | Billing entity |

## Service Data Models

### By Service

| Service | Models |
|---------|--------|
| billing | InvoiceDTO |

## Database and Migration Strategy

### Migration Strategy

Alembic migrations are used.

## Model Index

{models}
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)

    assert "AGG_DM_MODEL_DUMP" in result["reason_codes"]


def test_reason_code_dm_not_grouped(tmp_path: Path) -> None:
    """Test that AGG_DM_NOT_GROUPED reason code is returned when grouping is missing."""
    _write_minimum_artifacts(root=tmp_path)

    write_text(
        tmp_path / "docs/05-data-model.md",
        """# Data Models

This is a data model document without proper grouping.
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)

    assert "AGG_DM_NOT_GROUPED" in result["reason_codes"]


# =============================================================================
# DATA MODEL QUALITY GATE INTEGRATION TESTS
# =============================================================================


def test_data_model_quality_gates_all_pass_with_quality_content(tmp_path: Path) -> None:
    """Test that all data model quality gates pass when content meets quality standards."""
    _write_quality_artifacts(root=tmp_path)

    result = VerifierService(tmp_path).verify(ci=True)

    # All data model related checks should pass
    dm_check = next((c for c in result["checks"] if c["name"] == "data-model-aggregated"), None)
    citation_check = next((c for c in result["checks"] if c["name"] == "citation-coverage"), None)
    dm_refs_check = next((c for c in result["checks"] if c["name"] == "data-model-refs"), None)

    assert dm_check is not None
    assert dm_check["status"] == "PASS"
    assert citation_check is not None
    assert citation_check["status"] == "PASS"
    assert dm_refs_check is not None
    assert dm_refs_check["status"] == "PASS"

    # Overall grade should be PASS
    assert result["grade"] == "PASS"


def test_data_model_quality_gates_ci_output_includes_reason_codes(tmp_path: Path) -> None:
    """Test that CI output includes reason codes for data model quality failures."""
    _write_minimum_artifacts(root=tmp_path)

    # Create model dump content
    models = "\n".join([f"| Model{i} | python_class | module{i} |" for i in range(40)])
    write_text(
        tmp_path / "docs/05-data-model.md",
        f"""# Data Models

{models}
""",
    )

    result = VerifierService(tmp_path).verify(ci=True)

    assert result["ci_mode"] is True
    assert "reason_codes" in result
    assert len(result["reason_codes"]) > 0
    assert any(code.startswith("AGG_") for code in result["reason_codes"])


def test_gate_summary_shows_data_model_quality_status(tmp_path: Path) -> None:
    """Test that gate summary accurately reflects data model quality status."""
    _write_quality_artifacts(root=tmp_path)

    result = VerifierService(tmp_path).verify(ci=True)

    # With quality content, acceptance should not be blocked
    assert result["gate_summary"]["acceptance_blocked"] is False


def test_gate_summary_shows_blocking_on_model_dump(tmp_path: Path) -> None:
    """Test that gate summary shows blocking when model dump is treated as hard."""
    _write_minimum_artifacts(root=tmp_path)

    # Create model dump content
    models = "\n".join([f"| Model{i} | python_class | module{i} |" for i in range(40)])
    write_text(
        tmp_path / "docs/05-data-model.md",
        f"""# Data Models

## Core Data Models

### Core Model List

| Model | Type | Module | Description |
|-------|------|--------|-------------|
| Invoice | python_class | billing | Billing entity |

## Service Data Models

### By Service

| Service | Models |
|---------|--------|
| billing | InvoiceDTO |

## Database and Migration Strategy

### Migration Strategy

Alembic migrations are used.

## Model Index

{models}
""",
    )

    # Treat model dump as hard gate
    hard_thresholds = SeverityThreshold(
        hard_gate_codes={
            "AGG_DM_MODEL_DUMP",
            "AGG_DM_NOT_GROUPED",
            "STRUCT_NAV_TARGET_MISSING",
            "STRUCT_SECTION_DIR_MISSING",
            "STRUCT_MISSING_SECTIONS",
            "CONTENT_EMPTY",
        },
        warn_on_soft=True,
    )

    result = VerifierService(tmp_path, severity_thresholds=hard_thresholds).verify(ci=True)

    # Should have hard gate failure for model dump
    assert result["gate_summary"]["hard_gate_blocking"] is True
    assert result["gate_summary"]["acceptance_blocked"] is True
    assert result["exit_code"] == 1


# =============================================================================
# COMPREHENSIVE DATA MODEL QUALITY TESTS
# =============================================================================


def test_data_model_has_all_required_sections(tmp_path: Path) -> None:
    """Test that data model document has all required sections."""
    _write_quality_artifacts(root=tmp_path)

    dm_path = tmp_path / "docs/05-data-model.md"
    content = dm_path.read_text()

    # Check for all required sections
    assert "## Core Data Models" in content or "## 核心数据模型" in content
    assert "## Service Data Models" in content or "## 服务数据模型" in content
    assert "## Database" in content or "## 数据库" in content


def test_data_model_migration_strategy_mentioned(tmp_path: Path) -> None:
    """Test that data model document mentions migration strategy."""
    _write_quality_artifacts(root=tmp_path)

    dm_path = tmp_path / "docs/05-data-model.md"
    content = dm_path.read_text()

    assert "migration" in content.lower() or "迁移" in content


def test_data_model_distinguishes_canonical_from_dto(tmp_path: Path) -> None:
    """Test that data model document distinguishes canonical models from DTOs."""
    _write_quality_artifacts(root=tmp_path)

    dm_path = tmp_path / "docs/05-data-model.md"
    content = dm_path.read_text()

    # Should mention canonical vs DTO distinction
    assert "Canonical" in content or "DTO" in content or "dto" in content.lower()


def test_data_model_cross_module_boundaries_documented(tmp_path: Path) -> None:
    """Test that cross-module boundaries are documented."""
    _write_quality_artifacts(root=tmp_path)

    dm_path = tmp_path / "docs/05-data-model.md"
    content = dm_path.read_text()

    # Should mention cross-module boundaries
    assert "Cross-Module" in content or "cross-module" in content or "模块" in content
