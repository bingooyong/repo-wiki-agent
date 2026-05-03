"""Page prompt system for LLM page composition.

Exports:
- PagePromptContract and related dataclasses
- Prompt fragment templates for all page types
- Article skeleton builder and heading contracts
- Contract registry and utilities

Phase 24 - Task 24.1 (contracts, fragments) and Task 24.2 (skeleton)
"""

from repo_wiki.prompts.contracts import (
    PAGE_PROMPT_CONTRACTS,
    AntiHallucinationRequirement,
    CitationStyle,
    EvidenceRequirement,
    HeadingRequirement,
    PagePromptContract,
    PagePromptType,
    StyleRequirement,
    get_contract_for_doc_type,
    get_contract_for_page_type,
)
from repo_wiki.prompts.fragments import (
    API_PROMPT_FRAGMENT,
    DATA_PROMPT_FRAGMENT,
    DEVELOPMENT_PROMPT_FRAGMENT,
    ENTITY_PROMPT_FRAGMENT,
    OPS_PROMPT_FRAGMENT,
    OVERVIEW_PROMPT_FRAGMENT,
    SERVICE_PROMPT_FRAGMENT,
    SYSTEM_PROMPT_FRAGMENT,
    get_prompt_fragment,
    render_prompt_fragment,
)
from repo_wiki.prompts.skeleton import (
    API_HEADING_CONTRACT,
    DATA_HEADING_CONTRACT,
    DEVELOPMENT_HEADING_CONTRACT,
    ENTITY_HEADING_CONTRACT,
    HEADING_CONTRACTS,
    OPS_HEADING_CONTRACT,
    # Pre-defined contracts
    OVERVIEW_HEADING_CONTRACT,
    # Section keys
    SECTION_KEYS,
    SERVICE_HEADING_CONTRACT,
    # Article skeleton
    ArticleSkeleton,
    HeadingContract,
    # Heading section and contract
    HeadingSection,
    SkeletonBuilder,
    build_skeleton,
    # TOC utilities
    extract_toc_from_markdown,
    # Snapshot utilities
    generate_heading_snapshot,
    get_heading_contract,
    headings_match_snapshot,
    validate_heading_hierarchy,
    validate_toc_completeness,
)

__all__ = [
    # Contracts
    "PagePromptContract",
    "PagePromptType",
    "CitationStyle",
    "HeadingRequirement",
    "EvidenceRequirement",
    "StyleRequirement",
    "AntiHallucinationRequirement",
    "PAGE_PROMPT_CONTRACTS",
    "get_contract_for_page_type",
    "get_contract_for_doc_type",
    # Fragments
    "OVERVIEW_PROMPT_FRAGMENT",
    "SERVICE_PROMPT_FRAGMENT",
    "API_PROMPT_FRAGMENT",
    "DATA_PROMPT_FRAGMENT",
    "ENTITY_PROMPT_FRAGMENT",
    "OPS_PROMPT_FRAGMENT",
    "DEVELOPMENT_PROMPT_FRAGMENT",
    "SYSTEM_PROMPT_FRAGMENT",
    "get_prompt_fragment",
    "render_prompt_fragment",
    # Skeleton (Task 24.2)
    "SECTION_KEYS",
    "HeadingSection",
    "HeadingContract",
    "OVERVIEW_HEADING_CONTRACT",
    "SERVICE_HEADING_CONTRACT",
    "API_HEADING_CONTRACT",
    "DATA_HEADING_CONTRACT",
    "ENTITY_HEADING_CONTRACT",
    "OPS_HEADING_CONTRACT",
    "DEVELOPMENT_HEADING_CONTRACT",
    "HEADING_CONTRACTS",
    "get_heading_contract",
    "ArticleSkeleton",
    "SkeletonBuilder",
    "build_skeleton",
    "extract_toc_from_markdown",
    "validate_toc_completeness",
    "validate_heading_hierarchy",
    "generate_heading_snapshot",
    "headings_match_snapshot",
]
