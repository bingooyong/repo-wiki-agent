"""Page prompt contracts and reusable fragments for LLM page composition.

This module defines the prompt contracts used to generate Qoder-style wiki pages.
Each page type (overview, service, API, data, entity, ops, development) has a
prompt contract that specifies:
- Required evidence and citation requirements
- Heading structure and style requirements
- Anti-hallucination guardrails
- Snapshot test expectations

Phase 24 - Task 24.1: Page prompt contract and prompt fragments
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PagePromptType(Enum):
    """Page type taxonomy for prompt contracts."""
    OVERVIEW = "overview"
    SERVICE = "service"
    API = "api"
    DATA = "data"
    ENTITY = "entity"
    OPS = "ops"
    DEVELOPMENT = "development"


class CitationStyle(Enum):
    """Citation block style for evidence rendering."""
    CITE_BLOCK = "cite_block"  # <cite>file:line</cite>
    MARKDOWN_LINK = "markdown_link"  # [file:line](file://...)
    SOURCE_FOOTER = "source_footer"  # ## Sources section with links


@dataclass(frozen=True)
class HeadingRequirement:
    """Required heading structure for a page type."""
    level: int  # 1-6 (## to ######)
    text: str  # Heading text pattern (can be template)
    required: bool = True
    min_prose_chars: int = 0  # Minimum prose content after heading


@dataclass(frozen=True)
class EvidenceRequirement:
    """Evidence and citation requirements for a page type."""
    min_candidates: int = 5  # Minimum evidence candidates needed
    citation_style: CitationStyle = CitationStyle.CITE_BLOCK
    require_symbol_refs: bool = True  # Must reference specific symbols
    require_file_line_refs: bool = True  # Must reference file:line
    max_hallucination_ratio: float = 0.15  # Max 15% hallucinated content


@dataclass(frozen=True)
class StyleRequirement:
    """Style requirements for generated content."""
    prose_density_min: float = 0.4  # At least 40% prose vs lists/tables
    max_list_ratio: float = 0.5  # Max 50% list/table content
    min_sentence_length_avg: int = 10  # Min avg sentence length (words)
    forbid_generic_phrases: tuple[str, ...] = ()
    require_repository_specifics: bool = True


@dataclass(frozen=True)
class AntiHallucinationRequirement:
    """Anti-hallucination guardrails for page generation."""
    cite_all_symbols: bool = True  # All symbols must have citation
    cite_all_claims: bool = True  # All factual claims must have citation
    forbid_out_of_scope: bool = True  # No mentioning modules not in scope
    require_version_lock: bool = True  # Version info must be locked
    validate_file_paths: bool = True  # All file paths must exist
    validate_line_ranges: bool = True  # All line ranges must be valid


@dataclass
class PagePromptContract:
    """Complete prompt contract for a page type.

    This defines everything needed to generate a Qoder-style page:
    - Evidence requirements
    - Heading structure
    - Style requirements
    - Anti-hallucination guardrails
    - Snapshot test expectations
    """
    page_type: PagePromptType
    description: str
    heading_structure: tuple[HeadingRequirement, ...]
    evidence: EvidenceRequirement
    style: StyleRequirement
    anti_hallucination: AntiHallucinationRequirement
    snapshot_test_pattern: str | None = None  # Regex pattern for snapshot tests
    secret_redaction_required: bool = True  # Whether to redact secrets in output


# =============================================================================
# Page Prompt Contract Instances
# =============================================================================

OVERVIEW_PAGE_CONTRACT = PagePromptContract(
    page_type=PagePromptType.OVERVIEW,
    description="Project overview page with positioning, problem, capabilities",
    heading_structure=(
        HeadingRequirement(1, "# {repository_name} - 项目概览"),
        HeadingRequirement(2, "## 项目定位"),
        HeadingRequirement(2, "## 核心问题"),
        HeadingRequirement(2, "## 核心能力"),
        HeadingRequirement(2, "## 快速开始"),
        HeadingRequirement(3, "### 环境要求"),
        HeadingRequirement(3, "### 启动命令"),
        HeadingRequirement(2, "## 阅读导航"),
    ),
    evidence=EvidenceRequirement(
        min_candidates=8,
        citation_style=CitationStyle.CITE_BLOCK,
        require_symbol_refs=True,
        require_file_line_refs=True,
        max_hallucination_ratio=0.1,
    ),
    style=StyleRequirement(
        prose_density_min=0.5,
        max_list_ratio=0.4,
        min_sentence_length_avg=12,
        forbid_generic_phrases=(
            "这是一个基于",
            "传统文档维护面临的主要挑战包括",
            "通过自动化手段降低文档维护成本",
        ),
        require_repository_specifics=True,
    ),
    anti_hallucination=AntiHallucinationRequirement(
        cite_all_symbols=True,
        cite_all_claims=True,
        forbid_out_of_scope=True,
        require_version_lock=True,
        validate_file_paths=True,
        validate_line_ranges=True,
    ),
    snapshot_test_pattern=r"docs/00-overview\.md",
    secret_redaction_required=True,
)

SERVICE_PAGE_CONTRACT = PagePromptContract(
    page_type=PagePromptType.SERVICE,
    description="Service page covering business logic, modules, commands",
    heading_structure=(
        HeadingRequirement(1, "# {section_title}"),
        HeadingRequirement(2, "## 服务概述"),
        HeadingRequirement(2, "## 核心模块"),
        HeadingRequirement(3, "### {module_name}"),
        HeadingRequirement(2, "## API 端点"),
        HeadingRequirement(2, "## 数据模型"),
        HeadingRequirement(2, "## 相关命令"),
        HeadingRequirement(2, "## 导航"),
    ),
    evidence=EvidenceRequirement(
        min_candidates=5,
        citation_style=CitationStyle.CITE_BLOCK,
        require_symbol_refs=True,
        require_file_line_refs=True,
        max_hallucination_ratio=0.15,
    ),
    style=StyleRequirement(
        prose_density_min=0.4,
        max_list_ratio=0.5,
        min_sentence_length_avg=10,
        forbid_generic_phrases=(
            "本服务采用",
            "系统使用",
        ),
        require_repository_specifics=True,
    ),
    anti_hallucination=AntiHallucinationRequirement(
        cite_all_symbols=True,
        cite_all_claims=True,
        forbid_out_of_scope=True,
        require_version_lock=False,
        validate_file_paths=True,
        validate_line_ranges=True,
    ),
    snapshot_test_pattern=r"docs/sections/[^/]+/index\.md",
    secret_redaction_required=True,
)

API_PAGE_CONTRACT = PagePromptContract(
    page_type=PagePromptType.API,
    description="API reference page with endpoints, auth patterns, error handling",
    heading_structure=(
        HeadingRequirement(1, "# API 参考"),
        HeadingRequirement(2, "## API 分组"),
        HeadingRequirement(2, "## 调用约定"),
        HeadingRequirement(3, "### 认证"),
        HeadingRequirement(3, "### 错误处理"),
        HeadingRequirement(2, "## 关键入口 API"),
        HeadingRequirement(2, "## 端点详情"),
    ),
    evidence=EvidenceRequirement(
        min_candidates=10,
        citation_style=CitationStyle.MARKDOWN_LINK,
        require_symbol_refs=False,
        require_file_line_refs=True,
        max_hallucination_ratio=0.1,
    ),
    style=StyleRequirement(
        prose_density_min=0.3,
        max_list_ratio=0.6,
        min_sentence_length_avg=8,
        forbid_generic_phrases=(),
        require_repository_specifics=True,
    ),
    anti_hallucination=AntiHallucinationRequirement(
        cite_all_symbols=False,
        cite_all_claims=True,
        forbid_out_of_scope=True,
        require_version_lock=True,
        validate_file_paths=True,
        validate_line_ranges=True,
    ),
    snapshot_test_pattern=r"docs/04-api-contracts\.md",
    secret_redaction_required=True,
)

DATA_PAGE_CONTRACT = PagePromptContract(
    page_type=PagePromptType.DATA,
    description="Data model page with core models, service models, migrations",
    heading_structure=(
        HeadingRequirement(1, "# 数据模型"),
        HeadingRequirement(2, "## 核心数据模型"),
        HeadingRequirement(2, "## 服务数据模型"),
        HeadingRequirement(2, "## 数据库与迁移策略"),
        HeadingRequirement(2, "## 模型索引"),
    ),
    evidence=EvidenceRequirement(
        min_candidates=8,
        citation_style=CitationStyle.CITE_BLOCK,
        require_symbol_refs=True,
        require_file_line_refs=True,
        max_hallucination_ratio=0.12,
    ),
    style=StyleRequirement(
        prose_density_min=0.35,
        max_list_ratio=0.55,
        min_sentence_length_avg=9,
        forbid_generic_phrases=(),
        require_repository_specifics=True,
    ),
    anti_hallucination=AntiHallucinationRequirement(
        cite_all_symbols=True,
        cite_all_claims=True,
        forbid_out_of_scope=True,
        require_version_lock=False,
        validate_file_paths=True,
        validate_line_ranges=True,
    ),
    snapshot_test_pattern=r"docs/05-data-model\.md",
    secret_redaction_required=True,
)

ENTITY_PAGE_CONTRACT = PagePromptContract(
    page_type=PagePromptType.ENTITY,
    description="Entity page for individual data entities with relationships",
    heading_structure=(
        HeadingRequirement(1, "# {entity_name}"),
        HeadingRequirement(2, "## 实体描述"),
        HeadingRequirement(2, "## 字段定义"),
        HeadingRequirement(2, "## 关系映射"),
        HeadingRequirement(2, "## 迁移历史"),
    ),
    evidence=EvidenceRequirement(
        min_candidates=3,
        citation_style=CitationStyle.SOURCE_FOOTER,
        require_symbol_refs=True,
        require_file_line_refs=True,
        max_hallucination_ratio=0.15,
    ),
    style=StyleRequirement(
        prose_density_min=0.4,
        max_list_ratio=0.4,
        min_sentence_length_avg=10,
        forbid_generic_phrases=(),
        require_repository_specifics=True,
    ),
    anti_hallucination=AntiHallucinationRequirement(
        cite_all_symbols=True,
        cite_all_claims=True,
        forbid_out_of_scope=False,
        require_version_lock=False,
        validate_file_paths=True,
        validate_line_ranges=True,
    ),
    snapshot_test_pattern=r"docs/modules/[^/]+\.md",
    secret_redaction_required=True,
)

OPS_PAGE_CONTRACT = PagePromptContract(
    page_type=PagePromptType.OPS,
    description="Operations page covering deployment, configuration, monitoring",
    heading_structure=(
        HeadingRequirement(1, "# 部署运维"),
        HeadingRequirement(2, "## 环境配置"),
        HeadingRequirement(2, "## 部署流程"),
        HeadingRequirement(2, "## 监控告警"),
        HeadingRequirement(2, "## 故障恢复"),
    ),
    evidence=EvidenceRequirement(
        min_candidates=5,
        citation_style=CitationStyle.MARKDOWN_LINK,
        require_symbol_refs=False,
        require_file_line_refs=True,
        max_hallucination_ratio=0.18,
    ),
    style=StyleRequirement(
        prose_density_min=0.35,
        max_list_ratio=0.55,
        min_sentence_length_avg=9,
        forbid_generic_phrases=(
            "生产环境",
            "建议使用",
        ),
        require_repository_specifics=True,
    ),
    anti_hallucination=AntiHallucinationRequirement(
        cite_all_symbols=False,
        cite_all_claims=True,
        forbid_out_of_scope=False,
        require_version_lock=True,
        validate_file_paths=True,
        validate_line_ranges=True,
    ),
    snapshot_test_pattern=r"docs/sections/operations/index\.md",
    secret_redaction_required=True,
)

DEVELOPMENT_PAGE_CONTRACT = PagePromptContract(
    page_type=PagePromptType.DEVELOPMENT,
    description="Development guide page with setup, testing, contribution",
    heading_structure=(
        HeadingRequirement(1, "# 开发指南"),
        HeadingRequirement(2, "## 环境搭建"),
        HeadingRequirement(2, "## 开发规范"),
        HeadingRequirement(2, "## 测试策略"),
        HeadingRequirement(2, "## 贡献流程"),
    ),
    evidence=EvidenceRequirement(
        min_candidates=4,
        citation_style=CitationStyle.MARKDOWN_LINK,
        require_symbol_refs=False,
        require_file_line_refs=True,
        max_hallucination_ratio=0.2,
    ),
    style=StyleRequirement(
        prose_density_min=0.3,
        max_list_ratio=0.6,
        min_sentence_length_avg=8,
        forbid_generic_phrases=(),
        require_repository_specifics=True,
    ),
    anti_hallucination=AntiHallucinationRequirement(
        cite_all_symbols=False,
        cite_all_claims=True,
        forbid_out_of_scope=False,
        require_version_lock=False,
        validate_file_paths=True,
        validate_line_ranges=True,
    ),
    snapshot_test_pattern=r"docs/sections/development/index\.md",
    secret_redaction_required=True,
)


# =============================================================================
# Contract Registry
# =============================================================================

PAGE_PROMPT_CONTRACTS: dict[PagePromptType, PagePromptContract] = {
    PagePromptType.OVERVIEW: OVERVIEW_PAGE_CONTRACT,
    PagePromptType.SERVICE: SERVICE_PAGE_CONTRACT,
    PagePromptType.API: API_PAGE_CONTRACT,
    PagePromptType.DATA: DATA_PAGE_CONTRACT,
    PagePromptType.ENTITY: ENTITY_PAGE_CONTRACT,
    PagePromptType.OPS: OPS_PAGE_CONTRACT,
    PagePromptType.DEVELOPMENT: DEVELOPMENT_PAGE_CONTRACT,
}


def get_contract_for_page_type(page_type: PagePromptType) -> PagePromptContract:
    """Get the prompt contract for a given page type.

    Args:
        page_type: The page type to get contract for

    Returns:
        PagePromptContract for the given type

    Raises:
        ValueError: If page_type is not recognized
    """
    if page_type not in PAGE_PROMPT_CONTRACTS:
        raise ValueError(f"Unknown page type: {page_type}")
    return PAGE_PROMPT_CONTRACTS[page_type]


def get_contract_for_doc_type(doc_type: str) -> PagePromptContract:
    """Get the prompt contract for a document type string.

    Args:
        doc_type: Document type string (e.g., 'overview', 'section', 'module')

    Returns:
        PagePromptContract for the given doc type

    Raises:
        ValueError: If doc_type is not recognized
    """
    mapping = {
        "overview": PagePromptType.OVERVIEW,
        "section": PagePromptType.SERVICE,
        "module": PagePromptType.SERVICE,
        "api": PagePromptType.API,
        "data-model": PagePromptType.DATA,
        "data": PagePromptType.DATA,
        "entity": PagePromptType.ENTITY,
        "ops": PagePromptType.OPS,
        "operations": PagePromptType.OPS,
        "development": PagePromptType.DEVELOPMENT,
    }

    if doc_type not in mapping:
        raise ValueError(f"Unknown doc type: {doc_type}")

    return PAGE_PROMPT_CONTRACTS[mapping[doc_type]]