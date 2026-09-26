"""Template contracts for the frozen MVP outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class DocumentLayer(Enum):
    """Document output layer classification for repo-wiki document center."""

    OVERVIEW = "overview"  # Fixed reader-facing entry points (00-05)
    SECTION = "section"  # Thematic section layer (docs/sections/)
    MODULE = "module"  # Individual module documentation (docs/modules/)
    PHASE = "phase"  # Stage-governance layer (docs/phases/) - REPO-AGENT INTERNAL ONLY


@dataclass(frozen=True)
class DocumentContract:
    """A document generation contract defining template, output path, and required context keys."""

    name: str
    template_path: str
    output_path: str
    required_keys: tuple[str, ...] = field(default_factory=tuple)
    layer: DocumentLayer = DocumentLayer.OVERVIEW


# =============================================================================
# CORE OVERVIEW CONTRACTS (Layer 1: Reader-facing fixed entry points)
# =============================================================================

CORE_DOCUMENT_CONTRACTS: tuple[DocumentContract, ...] = (
    DocumentContract(
        "overview",
        "docs/00-overview.md.j2",
        "docs/00-overview.md",
        (
            "repository_name",
            "project_description",
            "project_positioning",
            "core_problem",
            "core_capabilities",
            "environment_requirements",
            "startup_commands",
            "reading_navigation",
            "module_count",
            "endpoint_count",
            "model_count",
        ),
        DocumentLayer.OVERVIEW,
    ),
    DocumentContract(
        "architecture",
        "docs/01-architecture.md.j2",
        "docs/01-architecture.md",
        (
            "repository_name",
            "graph_summary",
            "system_layers",
            "service_collaboration",
            "core_data_flow",
            "storage_retrieval_design",
            "incremental_update_governance",
            "three_layer_diagram",
            "layer_descriptions",
        ),
        DocumentLayer.OVERVIEW,
    ),
    DocumentContract(
        "module_map",
        "docs/03-module-map.md.j2",
        "docs/03-module-map.md",
        (
            "repository_name",
            "domain_overview_table",
            "domain_groups_detail",
            "module_index_table",
            "cross_domain_dependencies",
        ),
        DocumentLayer.OVERVIEW,
    ),
    DocumentContract(
        "api_contracts",
        "docs/04-api-contracts.md.j2",
        "docs/04-api-contracts.md",
        (
            "repository_name",
            "api_groups_table",
            "api_groups_detail",
            "authentication_patterns",
            "error_status_behavior",
            "key_entry_apis",
            "endpoint_index_table",
        ),
        DocumentLayer.OVERVIEW,
    ),
    DocumentContract(
        "data_models",
        "docs/05-data-model.md.j2",
        "docs/05-data-model.md",
        (
            "repository_name",
            "core_models_section",
            "core_models_table",
            "service_models_section",
            "service_models_by_module",
            "database_migration_section",
            "database_shape",
            "migration_strategy",
            "cross_module_boundaries",
            "model_index_table",
        ),
        DocumentLayer.OVERVIEW,
    ),
)


# =============================================================================
# SECTION LAYER CONTRACTS (Layer 2: Thematic section docs under docs/sections/)
# =============================================================================
# Stable section names and their output paths under docs/sections/
# Naming rules:
#   - Section slug: lowercase, hyphenated, descriptive
#   - Output path: docs/sections/<section-slug>/index.md
#   - Template path: docs/section.md.j2
#
# ALIAS SUPPORT:
#   Some repositories (like reference-repo) use Q01/S01 prefixed section names.
#   The alias system allows canonical section slugs to coexist with
#   repository-specific topical layers. Aliases are transparent - generation
#   always uses canonical slugs, but validation recognizes aliases.


@dataclass(frozen=True)
class SectionDefinition:
    """A section definition with optional alias support.

    Canonical naming:
      - canonical_slug: lowercase, hyphenated (e.g., 'project', 'architecture')
      - title: Human-readable title

    Alias support:
      - aliases: Tuple of alternative slugs that map to this canonical section
      - Examples: Q01-xxx, S01-xxx, or other repository-specific naming conventions
    """

    canonical_slug: str
    title: str
    aliases: tuple[str, ...] = field(default_factory=tuple)

    def matches(self, slug: str) -> bool:
        """Check if a slug matches this section definition (canonical or alias)."""
        s = slug.strip().lower()
        return s == self.canonical_slug.lower() or s in [a.lower() for a in self.aliases]


SECTION_DEFINITIONS: tuple[SectionDefinition, ...] = (
    SectionDefinition("project", "Project Overview and Getting Started"),
    SectionDefinition(
        "architecture", "Architecture and System Design", ("q01-architecture", "s01-architecture")
    ),
    SectionDefinition(
        "services", "Core Services and Business Logic", ("q02-services", "s02-services")
    ),
    SectionDefinition(
        "python-services", "Python Service Layer", ("q03-python-services", "s03-python-services")
    ),
    SectionDefinition(
        "data-model", "Data Models and Persistence", ("q04-data-model", "s04-data-model")
    ),
    SectionDefinition("api", "API Reference and Contracts", ("q05-api", "s05-api")),
    SectionDefinition(
        "operations", "Deployment and Operations", ("q06-operations", "s06-operations")
    ),
    SectionDefinition("development", "Development Guide", ("q07-development", "s07-development")),
    SectionDefinition("security", "Security and Compliance", ("q08-security", "s08-security")),
    SectionDefinition(
        "troubleshooting",
        "Troubleshooting and Maintenance",
        ("q09-troubleshooting", "s09-troubleshooting"),
    ),
)


def get_section_by_slug(slug: str) -> SectionDefinition | None:
    """Find a section definition by canonical slug or alias.

    This enables the registry to recognize Q01/S01 formatted sections
    from repositories like reference-repo while maintaining canonical naming.
    """
    s = slug.strip().lower()
    for section in SECTION_DEFINITIONS:
        if section.matches(s):
            return section
    return None


def get_canonical_slug(slug: str) -> str | None:
    """Get the canonical slug for a given slug (canonical or alias).

    Returns the canonical slug if found, None otherwise.
    """
    section = get_section_by_slug(slug)
    return section.canonical_slug if section else None


def section_contract(section_slug: str) -> DocumentContract:
    """Generate a section layer contract for a given section slug.

    Naming rules:
    - section_slug: lowercase, hyphenated (e.g., 'python-services')
    - output: docs/sections/<section_slug>/index.md
    - template: docs/section.md.j2
    """
    slug = section_slug.strip().lower()
    return DocumentContract(
        name=f"section:{slug}",
        template_path="docs/section.md.j2",
        output_path=f"docs/sections/{slug}/index.md",
        required_keys=(
            "section_title",
            "section_description",
            "section_content",
            "section_modules",
            "section_apis",
            "section_commands",
            "section_nav",
            "reading_paths",
            "related_sections",
        ),
        layer=DocumentLayer.SECTION,
    )


# =============================================================================
# PHASE LAYER CONTRACTS (Layer 3: Stage-governance layer under docs/phases/)
# =============================================================================
# Stable phase names representing project stages or milestones
# Naming rules:
#   - Phase slug: lowercase, hyphenated (e.g., 'phase-01-setup')
#   - Output path: docs/phases/<phase_slug>.md
#   - Template path: docs/phase.md.j2

PHASE_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("phase-01-setup", "Phase 01: Initial Setup and Configuration"),
    ("phase-02-scanning", "Phase 02: Repository Scanning and Indexing"),
    ("phase-03-generation", "Phase 03: Documentation Generation"),
    ("phase-04-adaptation", "Phase 04: Tool Adaptation Layer"),
    ("phase-05-verification", "Phase 05: Governance and Verification"),
    ("phase-06-architecture", "Phase 06: Information Architecture Recovery"),
    ("phase-07-aggregation", "Phase 07: Domain Aggregation Intelligence"),
    ("phase-08-quality", "Phase 08: Quality Governance and Baseline Comparison"),
    ("phase-09-navigation", "Phase 09: Output Contract and Navigation Hardening"),
    ("phase-10-narrative", "Phase 10: Narrative and Aggregation Intelligence"),
    ("phase-11-acceptance", "Phase 11: Acceptance and Baseline Governance Hardening"),
    ("phase-12-sqlite", "Phase 12: SQLite-First Local Knowledge Runtime"),
)


def phase_contract(phase_slug: str) -> DocumentContract:
    """Generate a phase layer contract for a given phase slug.

    Naming rules:
    - phase_slug: lowercase, hyphenated (e.g., 'phase-06-architecture')
    - output: docs/phases/<phase_slug>.md
    - template: docs/phase.md.j2
    """
    slug = phase_slug.strip().lower()
    return DocumentContract(
        name=f"phase:{slug}",
        template_path="docs/phase.md.j2",
        output_path=f"docs/phases/{slug}.md",
        required_keys=(
            "phase_title",
            "phase_objectives",
            "phase_deliverables",
            "phase_dependencies",
            "phase_status",
        ),
        layer=DocumentLayer.PHASE,
    )


PROMPT_FRAGMENT_CONTRACTS: tuple[DocumentContract, ...] = (
    DocumentContract(
        "overview_prompt",
        "prompt-fragments/overview.txt.j2",
        "ai/source-of-truth/prompt-fragments/overview.txt",
    ),
    DocumentContract(
        "architecture_prompt",
        "prompt-fragments/architecture.txt.j2",
        "ai/source-of-truth/prompt-fragments/architecture.txt",
    ),
)

TASK_CATALOG_CONTRACT = DocumentContract(
    "task_catalog",
    "task-catalog.yaml.j2",
    "ai/source-of-truth/task-catalog.yaml",
    ("task_catalog_json",),
)


def module_document_contract(module_name: str) -> DocumentContract:
    """Generate a module layer contract for a given module name.

    Naming rules:
    - module_name: the discovered module name (e.g., 'repo_wiki', 'scripts')
    - output: docs/modules/<slugified-name>.md
    - template: docs/module.md.j2
    """
    slug = module_name.strip().replace("/", "-")
    return DocumentContract(
        name=f"module:{slug}",
        template_path="docs/module.md.j2",
        output_path=f"docs/modules/{slug}.md",
        required_keys=("module_name", "module_path", "context_strategy"),
        layer=DocumentLayer.MODULE,
    )


def all_section_contracts() -> tuple[DocumentContract, ...]:
    """Generate all section layer contracts based on SECTION_DEFINITIONS.

    Uses canonical slugs for contract generation.
    """
    return tuple(section_contract(section.canonical_slug) for section in SECTION_DEFINITIONS)


def all_phase_contracts() -> tuple[DocumentContract, ...]:
    """Generate all phase layer contracts based on PHASE_DEFINITIONS."""
    return tuple(phase_contract(slug) for slug, _ in PHASE_DEFINITIONS)


def validate_contract_coverage(template_root: Path) -> list[str]:
    """Validate that all required templates exist for MVP and new layer contracts.

    This validates:
    - CORE (Layer 1): 00-overview, 01-architecture, 03-module-map, 04-api-contracts, 05-data-model
    - Section (Layer 2): section.md.j2 (shared template for all sections)
    - Phase (Layer 3): phase.md.j2 (shared template for all phases)
    - Module (Layer 4): module.md.j2
    - Prompt fragments and task catalog

    Additive validation: This does NOT break existing contracts - it only adds
    new template requirements alongside the existing ones.
    """
    missing: list[str] = []

    # Core overview layer templates (existing MVP)
    for contract in CORE_DOCUMENT_CONTRACTS:
        if not (template_root / contract.template_path).exists():
            missing.append(contract.template_path)

    # Section layer - shared template
    if not (template_root / "docs/section.md.j2").exists():
        missing.append("docs/section.md.j2")

    # Phase layer - shared template
    if not (template_root / "docs/phase.md.j2").exists():
        missing.append("docs/phase.md.j2")

    # Module layer template (existing)
    if not (template_root / "docs/module.md.j2").exists():
        missing.append("docs/module.md.j2")

    # Prompt fragments and task catalog (existing)
    for contract in PROMPT_FRAGMENT_CONTRACTS + (TASK_CATALOG_CONTRACT,):
        if not (template_root / contract.template_path).exists():
            missing.append(contract.template_path)

    return missing


# =============================================================================
# VALIDATION RULES (Phase 06 - Prose-first contracts)
# =============================================================================

# Minimum prose requirements for overview contract
OVERVIEW_MIN_PROSE_CHARS = 200  # Minimum characters of prose content
OVERVIEW_MIN_SECTIONS = 5  # Minimum number of sections required
OVERVIEW_REJECT_LIST_ONLY = True  # Reject pages that are primarily lists


def validate_overview_prose(content: str) -> tuple[bool, str]:
    """Validate that overview content meets minimum prose requirements.

    Returns (is_valid, reason) tuple.
    - is_valid: True if content meets requirements
    - reason: Human-readable validation message
    """
    if not content or len(content.strip()) == 0:
        return False, "Overview content is empty"

    # Strip markdown formatting for basic text analysis
    lines = content.split("\n")
    prose_lines = []
    in_code_block = False

    for line in lines:
        # Track code blocks
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # Skip headers, list items, table rows, and blank lines
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("-"):
            continue
        if stripped.startswith("|"):
            continue
        if stripped.startswith("!"):
            continue

        prose_lines.append(stripped)

    # Join prose lines and check length
    prose_text = " ".join(prose_lines)

    if len(prose_text) < OVERVIEW_MIN_PROSE_CHARS:
        return (
            False,
            f"Overview has only {len(prose_text)} chars of prose, need at least {OVERVIEW_MIN_PROSE_CHARS}",
        )

    # Count sections (## headers)
    section_count = sum(1 for line in lines if line.strip().startswith("## "))
    if section_count < OVERVIEW_MIN_SECTIONS:
        return (
            False,
            f"Overview has only {section_count} sections, need at least {OVERVIEW_MIN_SECTIONS}",
        )

    return True, "Overview content passes prose validation"


def validate_overview_not_list_only(content: str) -> tuple[bool, str]:
    """Validate that overview is not primarily a list or stats page.

    Returns (is_valid, reason) tuple.
    """
    lines = [l.strip() for l in content.split("\n") if l.strip()]

    # Count list items, table rows, and prose lines
    list_items = sum(1 for l in lines if l.startswith("-"))
    table_rows = sum(1 for l in lines if l.startswith("|"))
    prose_lines = sum(
        1
        for l in lines
        if not l.startswith("#")
        and not l.startswith("-")
        and not l.startswith("|")
        and not l.startswith("```")
    )

    total_content_lines = list_items + table_rows + prose_lines
    if total_content_lines == 0:
        return False, "Overview has no content lines"

    # If more than 70% are list/table items, it's list-only
    list_ratio = (list_items + table_rows) / total_content_lines if total_content_lines > 0 else 1.0
    if list_ratio > 0.7:
        return (
            False,
            f"Overview is {list_ratio * 100:.0f}% list/table content, must be less than 70%",
        )

    return True, "Overview is not list-only"


def validate_architecture_has_mermaid(content: str) -> tuple[bool, str]:
    """Validate that architecture document contains Mermaid diagrams.

    Requirements:
    - Must contain at least one Mermaid code block
    - Must explain the three-layer architecture (.repo-wiki, ai/source-of-truth, docs)

    Returns (is_valid, reason) tuple.
    """
    if not content or len(content.strip()) == 0:
        return False, "Architecture content is empty"

    # Check for mermaid code blocks
    has_mermaid = "```mermaid" in content

    if not has_mermaid:
        return False, "Architecture must contain at least one Mermaid diagram"

    # Count mermaid blocks
    mermaid_blocks = content.count("```mermaid")

    if mermaid_blocks < 2:
        return (
            False,
            f"Architecture has only {mermaid_blocks} Mermaid block(s), should have at least 2 for three-layer explanation",
        )

    # Check for three-layer explanation
    has_repo_wiki_ref = ".repo-wiki" in content
    has_source_of_truth_ref = "source-of-truth" in content or "source-of-truth/" in content
    has_docs_ref = "docs/" in content

    missing_refs = []
    if not has_repo_wiki_ref:
        missing_refs.append(".repo-wiki")
    if not has_source_of_truth_ref:
        missing_refs.append("ai/source-of-truth")
    if not has_docs_ref:
        missing_refs.append("docs/")

    if missing_refs:
        return False, f"Architecture missing explanation of: {', '.join(missing_refs)}"

    return True, "Architecture passes Mermaid and three-layer validation"


# =============================================================================
# VALIDATION HELPERS (Phase 06 - Architecture contract)
# =============================================================================


def validate_architecture_not_module_enum(content: str) -> tuple[bool, str]:
    """Validate that architecture is not just a raw module or API enumeration.

    Returns (is_valid, reason) tuple.
    """
    lines = [l.strip() for l in content.split("\n") if l.strip()]

    # Count lines that look like module/API enumeration
    enum_lines = 0
    for line in lines:
        # Lines that are just bullets with module names/paths
        if line.startswith("- `") and ("->" in line or "module" in line.lower()):
            enum_lines += 1
        # Lines that are table rows with just names
        if line.startswith("|") and line.count("|") >= 2:
            # Check if it's a simple name table
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 3 and len(parts[1]) < 30:
                enum_lines += 1

    total_lines = len(lines)
    if total_lines > 0:
        enum_ratio = enum_lines / total_lines
        if enum_ratio > 0.6:
            return (
                False,
                f"Architecture is {enum_ratio * 100:.0f}% module/API enumeration, should focus on design reasoning",
            )

    return True, "Architecture is not just module enumeration"


# =============================================================================
# VALIDATION HELPERS (Phase 07 - Domain-centered Module Map)
# =============================================================================

MODULE_MAP_MIN_DOMAINS = 3  # Minimum number of top-level domain groups required


def validate_module_map_domain_grouped(content: str) -> tuple[bool, str]:
    """Validate that module map is organized by business domain, not flat directory listing.

    This validation rejects outputs that:
    - List modules purely by physical directory path
    - Have no domain grouping metadata
    - Don't show upstream/downstream relationships within domains

    Requirements when domain metadata is available:
    - Must have at least 3 top-level domain groups
    - Must show domain > service_family > runtime_role hierarchy
    - Must include module responsibilities and relationships

    Returns (is_valid, reason) tuple.
    """
    if not content or len(content.strip()) == 0:
        return False, "Module map content is empty"

    # Check for domain grouping indicators
    has_domain_header = "## " in content and any(
        domain in content
        for domain in [
            "core-platform",
            "ai-services",
            "api-gateway",
            "data-pipeline",
            "frontend",
            "persistence",
            "tooling",
            "testing",
            "operations",
        ]
    )

    if not has_domain_header:
        return False, "Module map is not organized by business domain - missing domain headers"

    # Count domain sections (### headers with domain names or ## domain overview)
    domain_sections = sum(
        1
        for line in content.split("\n")
        if line.strip().startswith("### ") and "服务族" not in line
    )
    domain_overview = 1 if "| 业务域 |" in content or "| Domain |" in content else 0

    if (domain_sections + domain_overview) < 1:
        return False, "Module map missing domain overview table"

    # Check for domain grouping structure (service_family, runtime_role hierarchy)
    has_service_family = "service_family" in content.lower() or "服务族" in content
    has_runtime_role = "runtime_role" in content.lower() or "运行时角色" in content

    if not (has_service_family and has_runtime_role):
        return False, "Module map missing service_family or runtime_role hierarchy"

    # Check for module responsibilities
    has_responsibility = "responsibility" in content.lower() or "职责" in content
    if not has_responsibility:
        return False, "Module map missing module responsibilities"

    return True, "Module map passes domain-grouped validation"


def validate_module_map_not_directory_flat(
    content: str, has_domain_metadata: bool = True
) -> tuple[bool, str]:
    """Validate that module map is NOT a flat directory listing.

    This rejects outputs that:
    - Simply enumerate modules by directory path
    - Don't leverage domain classification metadata
    - Lack upstream/downstream relationship indicators

    Parameters:
    - content: The rendered module map content
    - has_domain_metadata: True if domain classification is available in source data

    Returns (is_valid, reason) tuple.
    """
    if not content:
        return False, "Module map content is empty"

    lines = [l.strip() for l in content.split("\n") if l.strip()]

    if has_domain_metadata:
        # When domain metadata is available, check it IS being used
        # Count lines that look like flat directory listing vs domain grouping
        flat_enum_patterns = [
            "- `",  # Bullet list entries
            "-> `",  # Arrow notation for module -> path
        ]

        # If most lines are just flat enumeration without context, reject
        potential_flat_lines = sum(
            1 for line in lines if any(pattern in line for pattern in flat_enum_patterns)
        )

        # Check for structured domain grouping markers
        has_domain_overview = "| 业务域 |" in content or "| Domain |" in content
        has_detailed_domains = "### " in content and any(
            d in content for d in ["core-platform", "ai-services", "unknown"]
        )

        if not (has_domain_overview and has_detailed_domains):
            return False, "Module map appears to be flat directory listing, not domain-organized"

        # Check for navigation links
        if "../00-overview.md" not in content and "../../00-overview.md" not in content:
            return False, "Module map missing navigation links to overview docs"

    return True, "Module map is not flat directory listing"


# =============================================================================
# VALIDATION HELPERS (Phase 07 - Aggregated API Contracts)
# =============================================================================

API_CONTRACT_MAX_RAW_ENDPOINTS = 50  # Maximum raw endpoints before aggregation is required


def validate_api_contract_grouped(content: str) -> tuple[bool, str]:
    """Validate that API contracts page is grouped by service family/domain, not raw endpoint list.

    This rejects outputs that:
    - Simply dump all endpoints without grouping
    - Don't summarize authentication or error behavior
    - Lack call convention documentation

    Requirements:
    - Must have service/API grouping section
    - Must have call convention section (authentication, errors)
    - Must have key entry APIs summary (not all endpoints verbatim)

    Returns (is_valid, reason) tuple.
    """
    if not content or len(content.strip()) == 0:
        return False, "API contracts content is empty"

    # Check for required sections
    has_grouping = "## 服务/API 分组" in content or "## API Groups" in content
    has_conventions = "## 调用约定" in content or "## Call Conventions" in content

    if not has_grouping:
        return False, "API contracts missing service/API grouping section"

    if not has_conventions:
        return False, "API contracts missing call convention section"

    # Check for authentication patterns summary
    has_auth = "认证" in content or "authentication" in content.lower()
    if not has_auth:
        return False, "API contracts missing authentication pattern documentation"

    # Check for error/status behavior
    has_errors = "错误" in content or "error" in content.lower() or "状态码" in content
    if not has_errors:
        return False, "API contracts missing error/status behavior documentation"

    # Check for key entry APIs summary
    has_key_apis = "关键入口" in content or "key entry" in content.lower()
    if not has_key_apis:
        return False, "API contracts missing key entry APIs summary"

    return True, "API contracts passes grouped validation"


def validate_api_contract_not_endpoint_dump(content: str) -> tuple[bool, str]:
    """Validate that API contracts is NOT an unbounded raw endpoint list.

    This rejects outputs that:
    - Render every endpoint verbatim without aggregation
    - Have no summary or grouping layer
    - Don't provide navigation to source-of-truth

    Parameters:
    - content: The rendered API contracts content

    Returns (is_valid, reason) tuple.
    """
    if not content:
        return False, "API contracts content is empty"

    lines = [l.strip() for l in content.split("\n") if l.strip()]

    # Count raw endpoint lines (lines that look like endpoint entries)
    endpoint_line_patterns = [
        "| GET |",
        "| POST |",
        "| PUT |",
        "| PATCH |",
        "| DELETE |",
        "| *GET* |",
        "| *POST* |",
        "| *PUT* |",
        "| *PATCH* |",
        "| *DELETE* |",
    ]

    raw_endpoint_lines = sum(
        1 for line in lines if any(pattern in line for pattern in endpoint_line_patterns)
    )

    # If there are more than API_CONTRACT_MAX_RAW_ENDPOINTS raw endpoints, it's a dump
    if raw_endpoint_lines > API_CONTRACT_MAX_RAW_ENDPOINTS:
        return (
            False,
            f"API contracts has {raw_endpoint_lines} raw endpoints (>{API_CONTRACT_MAX_RAW_ENDPOINTS}), should aggregate instead",
        )

    # Check for summary content (分组, 调用约定, 认证)
    has_summary_sections = ("分组" in content or "group" in content.lower()) and (
        "调用约定" in content or "convention" in content.lower()
    )

    if not has_summary_sections:
        return False, "API contracts missing summary/grouping sections"

    # Check for source-of-truth reference
    has_source_ref = "api-index.yaml" in content or "source-of-truth" in content
    if not has_source_ref:
        return False, "API contracts should reference source-of-truth for detailed endpoint list"

    return True, "API contracts is not endpoint dump"


# =============================================================================
# VALIDATION HELPERS (Phase 07 - Domain-aggregated Data Model)
# =============================================================================

DATA_MODEL_MIN_CORE_MODELS = 1  # Minimum number of core models expected
DATA_MODEL_MAX_RAW_MODELS = 30  # Maximum raw models before aggregation is required


def validate_data_model_grouped(content: str) -> tuple[bool, str]:
    """Validate that data model page is organized into core/service/database sections.

    This rejects outputs that:
    - Simply dump all models without grouping
    - Don't separate core models from service models
    - Lack database/migration strategy documentation

    Requirements:
    - Must have "## 核心数据模型" or "## Core Data Models" section
    - Must have "## 服务数据模型" or "## Service Data Models" section
    - Must have "## 数据库与迁移策略" or "## Database & Migration" section

    Returns (is_valid, reason) tuple.
    """
    if not content or len(content.strip()) == 0:
        return False, "Data model content is empty"

    # Check for required sections
    has_core_section = "## 核心数据模型" in content or "## Core Data Models" in content
    has_service_section = "## 服务数据模型" in content or "## Service Data Models" in content
    has_db_section = "## 数据库与迁移策略" in content or "## Database" in content

    missing_sections = []
    if not has_core_section:
        missing_sections.append("核心数据模型")
    if not has_service_section:
        missing_sections.append("服务数据模型")
    if not has_db_section:
        missing_sections.append("数据库与迁移策略")

    if missing_sections:
        return False, f"Data model missing required sections: {', '.join(missing_sections)}"

    # Check for migration strategy content
    has_migration = "迁移" in content or "migration" in content.lower()
    if not has_migration:
        return False, "Data model missing migration strategy documentation"

    return True, "Data model passes three-section validation"


def validate_data_model_not_dump(content: str) -> tuple[bool, str]:
    """Validate that data model page is NOT a raw model dump with no aggregation.

    This rejects outputs that:
    - List every model without categorization
    - Don't surface core entities
    - Lack cross-module boundary documentation

    Parameters:
    - content: The rendered data model content

    Returns (is_valid, reason) tuple.
    """
    if not content:
        return False, "Data model content is empty"

    lines = [l.strip() for l in content.split("\n") if l.strip()]

    # Count raw model lines (lines that look like model entries in a simple list)
    raw_model_lines = sum(1 for line in lines if line.startswith("| ") and "model" in line.lower())

    # If there are more than DATA_MODEL_MAX_RAW_MODELS raw model entries, it's likely a dump
    if raw_model_lines > DATA_MODEL_MAX_RAW_MODELS:
        return (
            False,
            f"Data model has {raw_model_lines} raw model entries (>{DATA_MODEL_MAX_RAW_MODELS}), should aggregate instead",
        )

    # Check for aggregation markers
    has_core_indicator = "核心" in content or "core" in content.lower()
    has_service_indicator = "服务" in content or "service" in content.lower()
    has_db_indicator = (
        "数据库" in content or "database" in content.lower() or "db" in content.lower()
    )

    if not (has_core_indicator and has_service_indicator and has_db_indicator):
        return False, "Data model missing aggregation indicators (core/service/database)"

    # Check for cross-module boundary documentation
    has_boundaries = "边界" in content or "boundary" in content.lower() or "跨模块" in content
    if not has_boundaries:
        return False, "Data model missing cross-module boundary documentation"

    # Check for source-of-truth reference
    has_source_ref = "data-models.yaml" in content or "source-of-truth" in content
    if not has_source_ref:
        return False, "Data model should reference source-of-truth for detailed model definitions"

    return True, "Data model is not a dump"


# =============================================================================
# VALIDATION HELPERS (Phase 07 - Section Pages and Navigation)
# =============================================================================

# Minimum sections required for a valid document center
SECTION_MIN_REQUIRED = 8
SECTION_NAVIGATION_LINKS = 2  # Minimum navigation links per section


def validate_section_page_exists(section_slug: str, section_dir: Path) -> tuple[bool, str]:
    """Validate that a section page exists at the expected path.

    Parameters:
    - section_slug: The section identifier (e.g., 'project', 'architecture')
    - section_dir: The root directory containing docs/sections/

    Returns (is_valid, reason) tuple.
    """
    expected_path = section_dir / section_slug / "index.md"
    if not expected_path.exists():
        return False, f"Section page missing: {expected_path}"
    return True, f"Section page exists: {expected_path}"


def validate_section_page_content(content: str, section_slug: str) -> tuple[bool, str]:
    """Validate that a section page has proper content and navigation.

    Requirements:
    - Must have section title
    - Must have section description
    - Must have navigation links to other sections
    - Must not be empty

    Parameters:
    - content: The rendered section page content
    - section_slug: The section identifier

    Returns (is_valid, reason) tuple.
    """
    if not content or len(content.strip()) == 0:
        return False, f"Section {section_slug} content is empty"

    # Check for required elements
    has_title = "# " in content  # Markdown title
    has_description = len(content) > 100  # Non-trivial content
    has_nav = "../../00-overview.md" in content or "../" in content  # Navigation links

    if not has_title:
        return False, f"Section {section_slug} missing title"

    if not has_description:
        return False, f"Section {section_slug} content too short"

    if not has_nav:
        return False, f"Section {section_slug} missing navigation links"

    return True, f"Section {section_slug} passes validation"


def validate_section_cross_links(content: str, section_slug: str) -> tuple[bool, str]:
    """Validate that section page links correctly to overview and related sections.

    Requirements:
    - Must link to 00-overview.md
    - Must link to at least one related section
    - Links must be properly formatted

    Parameters:
    - content: The rendered section page content
    - section_slug: The section identifier

    Returns (is_valid, reason) tuple.
    """
    if not content:
        return False, f"Section {section_slug} content is empty"

    # Check for overview link
    has_overview_link = "../../00-overview.md" in content or "../../00-overview.md" in content

    if not has_overview_link:
        return False, f"Section {section_slug} missing link to overview"

    # Count internal section links
    internal_links = content.count("../")
    if internal_links < SECTION_NAVIGATION_LINKS:
        return (
            False,
            f"Section {section_slug} has only {internal_links} navigation links, need at least {SECTION_NAVIGATION_LINKS}",
        )

    return True, f"Section {section_slug} has proper cross-links"


class DocType(Enum):
    OVERVIEW = "overview"
    SECTION = "section"
    MODULE = "module"


def build_relative_link(
    from_doc: str,
    to_doc: str,
    from_type: DocType | None = None,
    to_type: DocType | None = None,
) -> str:
    from_parts = Path(from_doc).parts
    to_parts = Path(to_doc).parts
    common_len = 0
    for left, right in zip(from_parts, to_parts, strict=False):
        if left != right:
            break
        common_len += 1
    relative = "../" * max(0, len(from_parts) - 1 - common_len) + "/".join(to_parts[common_len:])
    return relative[2:] if relative.startswith("./") else relative


def overview_to_section_link(section_slug: str) -> str:
    """Build correct relative path from overview to section page.

    From: docs/00-overview.md (or other overview at depth 0)
    To:   docs/sections/<slug>/index.md
    Path: sections/<slug>/index.md
    """
    return build_relative_link(
        "docs/00-overview.md",
        f"docs/sections/{section_slug}/index.md",
        DocType.OVERVIEW,
        DocType.SECTION,
    )


# =============================================================================
# NARRATIVE VALIDATION (Phase 10 - Task 10.1)
# =============================================================================
# These validations detect overly generic or boilerplate output patterns
# that indicate the narrative is template-based rather than repository-derived.

# Generic phrase patterns that indicate template content
GENERIC_NARRATIVE_PATTERNS: tuple[str, ...] = (
    "这是一个基于",  # "This is a project based on..."
    "传统文档维护面临的主要挑战包括",  # Template problem statement
    "通过自动化手段降低文档维护成本",  # Generic positioning
    "提供自动化的代码扫描、文档生成和知识图谱构建能力",  # Generic capability
    "系统采用三层架构设计",  # Generic architecture description
    "本系统采用三层架构模型",  # Another generic architecture intro
    "三层架构设计，将运行时存储层、结构化事实层和文档中心层分离",  # Template layer description
)

# Minimum unique content ratio (non-duplicate prose ratio)
NARRATIVE_MIN_UNIQUE_RATIO = 0.6  # At least 60% of content should be unique


def validate_narrative_not_generic(content: str) -> tuple[bool, str]:
    """Validate that narrative content is repository-specific, not generic template.

    This rejects outputs that contain generic boilerplate phrases that indicate
    the content was generated from fixed templates rather than derived from
    repository-specific signals.

    Returns (is_valid, reason) tuple.
    """
    if not content or len(content.strip()) == 0:
        return False, "Narrative content is empty"

    # Check for generic patterns
    found_patterns = []
    for pattern in GENERIC_NARRATIVE_PATTERNS:
        if pattern in content:
            found_patterns.append(pattern)

    if found_patterns:
        # Allow up to 2 generic patterns (some boilerplate may be unavoidable)
        if len(found_patterns) > 2:
            return (
                False,
                f"Narrative contains {len(found_patterns)} generic patterns: {'; '.join(found_patterns[:3])}...",
            )

    # Check for repeated sentences (indicator of template generation)
    sentences = [s.strip() for s in content.split("。") if s.strip()]
    if len(sentences) > 5:
        # Count sentence frequency
        from collections import Counter

        sentence_counts = Counter(sentences)
        # Find sentences that appear more than once (length > 6 to catch template duplicates)
        duplicates = {s: c for s, c in sentence_counts.items() if c > 1 and len(s) > 6}
        if len(duplicates) >= 2:
            return (
                False,
                f"Narrative has {len(duplicates)} repeated sentences, suggesting template generation",
            )

    return True, "Narrative passes generic pattern check"


def validate_architecture_rationale_exists(content: str) -> tuple[bool, str]:
    """Validate that architecture content explains WHY the three-layer model exists,
    not just what the layers are named.

    This rejects outputs that only describe layer names without explaining
    the design rationale for why this architecture was chosen.

    Returns (is_valid, reason) tuple.
    """
    if not content or len(content.strip()) == 0:
        return False, "Architecture content is empty"

    # Check for rationale indicators - reasons WHY the architecture exists
    rationale_indicators = [
        "因为",  # because
        "为了解决",  # in order to solve
        "因此",  # therefore/consequently
        "设计目标",  # design goals
        "决策",  # decisions
        "原因",  # reasons
        " rationale",  # English: design rationale
        "exist because",  # English: why it exists
        "chosen because",  # English: why chosen
        "enables the system to",  # English: capability enablement
        "separating",  # English: separation rationale
    ]

    # Count rationale phrases (need at least 2 for proper explanation)
    found_rationale = []
    content_lower = content.lower()
    for indicator in rationale_indicators:
        if indicator.lower() in content_lower:
            found_rationale.append(indicator)

    # Also check that the content is longer than just layer names (at least 500 chars)
    # This indicates substantive explanation rather than bullet list
    prose_chars = len(content.replace(" ", "").replace("\n", ""))

    if len(found_rationale) < 1 and prose_chars < 800:
        return (
            False,
            "Architecture explains WHAT but not WHY - missing design rationale explanation",
        )

    # Check that content explains problems being solved, not just architecture description
    problem_indicators = [
        "问题",
        "challenge",
        "problem",
        "解决",
        "solve",
        "address",
        "同步",
        "sync",
        "不同步",
        "out of sync",
        "发现",
        "discover",
    ]

    found_problems = [p for p in problem_indicators if p.lower() in content_lower]
    if len(found_problems) < 1:
        return False, "Architecture missing problem statements that the design addresses"

    return True, "Architecture passes rationale validation"


def validate_overview_has_repository_specifics(content: str, repo_name: str) -> tuple[bool, str]:
    """Validate that overview content references repository-specific information.

    This rejects outputs that could apply to any project, not just the target repo.

    Returns (is_valid, reason) tuple.
    """
    if not content or len(content.strip()) == 0:
        return False, "Overview content is empty"

    # Content should reference the actual repository name or project-specific terms
    has_repo_reference = repo_name.lower() in content.lower()

    if not has_repo_reference:
        # Check if any module names from the project appear
        # This is a softer check - the repo name is the primary identifier
        return (
            False,
            f"Overview does not reference repository name '{repo_name}' - content may be generic",
        )

    return True, f"Overview references repository-specific information ({repo_name})"
