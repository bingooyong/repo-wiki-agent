"""Wiki page-plan schema and navigation tree contracts.

This module defines the schema for wiki-plan.json and the navigation tree
contracts used across the Qoder-like wiki planning system.

Schema definition:
- page id: unique identifier (slug format: kebab-case)
- title: human-readable title (Chinese/English)
- category: taxonomy category (from WikiTaxonomy)
- parent: parent page id for hierarchy
- output_path: relative path for generated wiki page
- source_requirements: what data is needed to generate
- generation_mode: 'rule-first' | 'llm-assisted'
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class GenerationMode(str, Enum):
    RULE_FIRST = "rule-first"
    LLM_ASSISTED = "llm-assisted"


class WikiTaxonomyCategory(str, Enum):
    """Chinese taxonomy baseline for Qoder-like output."""
    PROJECT_OVERVIEW = "项目概述"
    ARCHITECTURE_DESIGN = "架构设计"
    CORE_SERVICES = "核心服务"
    PYTHON_SERVICES = "Python服务"
    FRONTEND_APPLICATIONS = "前端应用"
    DATA_MODELS = "数据模型"
    API_REFERENCE = "API参考"
    DEPLOYMENT_OPERATIONS = "部署运维"
    DEVELOPMENT_GUIDE = "开发指南"
    SECURITY_COMPLIANCE = "安全合规"
    TROUBLESHOOTING = "故障排除"


# Default Chinese taxonomy for Qoder-like output
DEFAULT_CHINESE_TAXONOMY = [
    WikiTaxonomyCategory.PROJECT_OVERVIEW,
    WikiTaxonomyCategory.ARCHITECTURE_DESIGN,
    WikiTaxonomyCategory.CORE_SERVICES,
    WikiTaxonomyCategory.PYTHON_SERVICES,
    WikiTaxonomyCategory.FRONTEND_APPLICATIONS,
    WikiTaxonomyCategory.DATA_MODELS,
    WikiTaxonomyCategory.API_REFERENCE,
    WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS,
    WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
    WikiTaxonomyCategory.SECURITY_COMPLIANCE,
    WikiTaxonomyCategory.TROUBLESHOOTING,
]


class SourceRequirement(BaseModel):
    """Source requirements for a wiki page."""
    modules: list[str] = Field(default_factory=list)
    endpoints: list[str] = Field(default_factory=list)
    data_models: list[str] = Field(default_factory=list)
    commands: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)


class WikiPagePlan(BaseModel):
    """A single wiki page in the plan.

    Attributes:
        page_id: Unique identifier (slug format: kebab-case)
        title: Human-readable title
        category: Taxonomy category
        parent: Parent page id for hierarchy (None for root pages)
        output_path: Relative path for generated wiki page
        source_requirements: What data is needed to generate this page
        generation_mode: How this page should be generated
        sort_order: Ordering within siblings (lower = earlier)
    """
    page_id: str = Field(..., description="Unique identifier in kebab-case slug format")
    title: str = Field(..., description="Human-readable page title")
    category: WikiTaxonomyCategory = Field(..., description="Taxonomy category")
    parent: str | None = Field(None, description="Parent page ID for hierarchy")
    output_path: str = Field(..., description="Relative output path for wiki page")
    source_requirements: SourceRequirement = Field(
        default_factory=SourceRequirement,
        description="What data is needed to generate this page"
    )
    generation_mode: GenerationMode = Field(
        default=GenerationMode.RULE_FIRST,
        description="How this page should be generated"
    )
    sort_order: int = Field(default=0, description="Ordering within siblings")
    estimated_tokens: int = Field(default=0, description="Estimated token cost for generation")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")


class WikiPlanManifest(BaseModel):
    """Manifest containing the complete wiki page plan.

    This is the top-level schema for wiki-plan.json files.
    """
    version: str = Field(default="1.0.0", description="Schema version")
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp of generation"
    )
    profile: str = Field(default="qoder-chinese", description="Taxonomy profile used")
    repository_identity: RepositoryIdentity | None = None
    pages: list[WikiPagePlan] = Field(default_factory=list, description="All planned pages")
    navigation_tree: list[NavNode] = Field(default_factory=list, description="Navigation hierarchy")

    def page_count(self) -> int:
        """Return the total number of pages in the plan."""
        return len(self.pages)

    def pages_by_category(self, category: WikiTaxonomyCategory) -> list[WikiPagePlan]:
        """Get all pages in a specific category."""
        return [p for p in self.pages if p.category == category]

    def page_by_id(self, page_id: str) -> WikiPagePlan | None:
        """Find a page by its ID."""
        for page in self.pages:
            if page.page_id == page_id:
                return page
        return None

    def children_of(self, parent_id: str | None) -> list[WikiPagePlan]:
        """Get all direct children of a parent (None = root level)."""
        return [p for p in self.pages if p.parent == parent_id]


class NavNode(BaseModel):
    """A navigation tree node for IDE/static viewer consumption.

    This represents a node in the navigation hierarchy that can be
    rendered by documentation viewers or IDE plugins.
    """
    node_id: str = Field(..., description="Unique node identifier")
    label: str = Field(..., description="Display label")
    node_type: Literal["category", "page", "separator"] = Field(
        default="page",
        description="Type of node"
    )
    path: str | None = Field(None, description="Path to the page (for page nodes)")
    icon: str | None = Field(None, description="Icon identifier for UI")
    children: list[NavNode] = Field(default_factory=list, description="Child nodes")
    sort_order: int = Field(default=0, description="Ordering within siblings")
    metadata: dict[str, str] = Field(default_factory=dict, description="Additional metadata")


class RepositoryIdentity(BaseModel):
    """Repository identity resolved from metadata.

    Resolved from: git root, README, pom.xml, package.json, pyproject.toml
    """
    name: str = Field(..., description="Repository name")
    display_name: str = Field(..., description="Human-readable display name")
    root_path: str = Field(..., description="Absolute root path")
    language: str = Field(default="unknown", description="Primary language")
    framework: str = Field(default="unknown", description="Primary framework")
    package_manager: str = Field(default="unknown", description="Primary package manager")
    version: str | None = Field(None, description="Project version")
    description: str | None = Field(None, description="Project description from README")
    entry_points: list[str] = Field(default_factory=list, description="Entry point commands")
    source_digest: str | None = Field(None, description="Hash of source state for change detection")


def current_schema_version() -> str:
    """Return the current wiki-plan schema version."""
    return "1.0.0"