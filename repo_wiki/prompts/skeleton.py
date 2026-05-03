"""Qoder-style article skeleton builder and heading contracts.

This module provides:
- ArticleSkeleton: A structured article outline with headings and TOC
- HeadingContract: Defines valid heading hierarchies per page type
- SkeletonBuilder: Builds article skeletons from page types and context
- TOC generation utilities

Phase 24 - Task 24.2: Qoder-style article skeleton

Sections supported (not all apply to every page type):
- 目录 (Table of Contents)
- 简介 (Introduction)
- 项目结构 (Project Structure)
- 核心组件 (Core Components)
- 架构总览 (Architecture Overview)
- 详细分析 (Detailed Analysis)
- 依赖 (Dependencies)
- 性能 (Performance)
- 排障 (Troubleshooting)
- 结论 (Conclusion)
- 附录 (Appendix)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# =============================================================================
# HEADING SECTION DEFINITIONS
# =============================================================================
# Standard section keys used in Qoder-style articles

SECTION_KEYS = (
    "目录",  # Table of Contents
    "简介",  # Introduction
    "项目结构",  # Project Structure
    "核心组件",  # Core Components
    "架构总览",  # Architecture Overview
    "详细分析",  # Detailed Analysis
    "依赖",  # Dependencies
    "性能",  # Performance
    "排障",  # Troubleshooting
    "结论",  # Conclusion
    "附录",  # Appendix
)


@dataclass(frozen=True)
class HeadingSection:
    """A heading section in an article skeleton."""

    key: str  # Section key (e.g., "目录", "简介")
    heading_text: str  # Full heading text (e.g., "## 目录")
    level: int  # Heading level (1-6)
    required: bool = False  # Whether this section is required
    min_prose_chars: int = 0  # Minimum prose characters


@dataclass
class HeadingContract:
    """Contract defining valid heading structure for a page type.

    This defines which sections are required/optional and their ordering
    for a specific page type (e.g., overview, service, API, etc.).
    """

    page_type: str
    sections: tuple[HeadingSection, ...]
    toc_required: bool = True
    toc_depth: int = 2  # How deep to render TOC

    def get_required_sections(self) -> list[str]:
        """Get list of required section keys."""
        return [s.key for s in self.sections if s.required]

    def get_optional_sections(self) -> list[str]:
        """Get list of optional section keys."""
        return [s.key for s in self.sections if not s.required]

    def validate_heading(self, heading_text: str) -> bool:
        """Check if a heading matches this contract."""
        normalized = heading_text.strip()
        for section in self.sections:
            if normalized == section.heading_text:
                return True
        return False


# =============================================================================
# HEADING CONTRACTS PER PAGE TYPE
# =============================================================================

# Overview page heading contract
OVERVIEW_HEADING_CONTRACT = HeadingContract(
    page_type="overview",
    sections=(
        HeadingSection("目录", "## 目录", 2, required=True, min_prose_chars=50),
        HeadingSection("简介", "## 简介", 2, required=True, min_prose_chars=100),
        HeadingSection("项目结构", "## 项目结构", 2, required=True, min_prose_chars=80),
        HeadingSection("核心组件", "## 核心组件", 2, required=True, min_prose_chars=100),
        HeadingSection("架构总览", "## 架构总览", 2, required=False, min_prose_chars=100),
        HeadingSection("详细分析", "## 详细分析", 2, required=False, min_prose_chars=150),
        HeadingSection("依赖", "## 依赖", 2, required=False, min_prose_chars=50),
        HeadingSection("性能", "## 性能", 2, required=False, min_prose_chars=50),
        HeadingSection("排障", "## 排障", 2, required=False, min_prose_chars=50),
        HeadingSection("结论", "## 结论", 2, required=False, min_prose_chars=50),
        HeadingSection("附录", "## 附录", 2, required=False, min_prose_chars=0),
    ),
    toc_required=True,
    toc_depth=2,
)

# Service/Section page heading contract
SERVICE_HEADING_CONTRACT = HeadingContract(
    page_type="service",
    sections=(
        HeadingSection("目录", "## 目录", 2, required=True, min_prose_chars=30),
        HeadingSection("简介", "## 服务概述", 2, required=True, min_prose_chars=80),
        HeadingSection("核心组件", "## 核心模块", 2, required=True, min_prose_chars=100),
        HeadingSection("项目结构", "## 项目结构", 2, required=False, min_prose_chars=50),
        HeadingSection("详细分析", "## 详细分析", 2, required=False, min_prose_chars=100),
        HeadingSection("依赖", "## 相关命令", 2, required=False, min_prose_chars=30),
        HeadingSection("性能", "## 性能", 2, required=False, min_prose_chars=50),
        HeadingSection("排障", "## 排障", 2, required=False, min_prose_chars=50),
        HeadingSection("结论", "## 结论", 2, required=False, min_prose_chars=50),
        HeadingSection("附录", "## 附录", 2, required=False, min_prose_chars=0),
    ),
    toc_required=True,
    toc_depth=2,
)

# API page heading contract
API_HEADING_CONTRACT = HeadingContract(
    page_type="api",
    sections=(
        HeadingSection("目录", "## 目录", 2, required=True, min_prose_chars=30),
        HeadingSection("简介", "## API 分组", 2, required=True, min_prose_chars=50),
        HeadingSection("核心组件", "## 调用约定", 2, required=True, min_prose_chars=80),
        HeadingSection("详细分析", "## 端点详情", 2, required=True, min_prose_chars=100),
        HeadingSection("依赖", "## 认证", 2, required=False, min_prose_chars=50),
        HeadingSection("性能", "## 错误处理", 2, required=False, min_prose_chars=50),
        HeadingSection("排障", "## 排障", 2, required=False, min_prose_chars=30),
        HeadingSection("附录", "## 附录", 2, required=False, min_prose_chars=0),
    ),
    toc_required=True,
    toc_depth=2,
)

# Data model page heading contract
DATA_HEADING_CONTRACT = HeadingContract(
    page_type="data",
    sections=(
        HeadingSection("目录", "## 目录", 2, required=True, min_prose_chars=30),
        HeadingSection("简介", "## 核心数据模型", 2, required=True, min_prose_chars=80),
        HeadingSection("核心组件", "## 服务数据模型", 2, required=True, min_prose_chars=80),
        HeadingSection("详细分析", "## 数据库与迁移策略", 2, required=True, min_prose_chars=100),
        HeadingSection("依赖", "## 模型索引", 2, required=False, min_prose_chars=50),
        HeadingSection("附录", "## 附录", 2, required=False, min_prose_chars=0),
    ),
    toc_required=True,
    toc_depth=2,
)

# Entity page heading contract
ENTITY_HEADING_CONTRACT = HeadingContract(
    page_type="entity",
    sections=(
        HeadingSection("目录", "## 目录", 2, required=True, min_prose_chars=20),
        HeadingSection("简介", "## 实体描述", 2, required=True, min_prose_chars=50),
        HeadingSection("核心组件", "## 字段定义", 2, required=True, min_prose_chars=80),
        HeadingSection("详细分析", "## 关系映射", 2, required=False, min_prose_chars=50),
        HeadingSection("依赖", "## 迁移历史", 2, required=False, min_prose_chars=30),
        HeadingSection("附录", "## 附录", 2, required=False, min_prose_chars=0),
    ),
    toc_required=True,
    toc_depth=2,
)

# Ops page heading contract
OPS_HEADING_CONTRACT = HeadingContract(
    page_type="ops",
    sections=(
        HeadingSection("目录", "## 目录", 2, required=True, min_prose_chars=30),
        HeadingSection("简介", "## 环境配置", 2, required=True, min_prose_chars=80),
        HeadingSection("核心组件", "## 部署流程", 2, required=True, min_prose_chars=100),
        HeadingSection("详细分析", "## 监控告警", 2, required=False, min_prose_chars=80),
        HeadingSection("性能", "## 故障恢复", 2, required=False, min_prose_chars=80),
        HeadingSection("排障", "## 排障", 2, required=False, min_prose_chars=50),
        HeadingSection("附录", "## 附录", 2, required=False, min_prose_chars=0),
    ),
    toc_required=True,
    toc_depth=2,
)

# Development page heading contract
DEVELOPMENT_HEADING_CONTRACT = HeadingContract(
    page_type="development",
    sections=(
        HeadingSection("目录", "## 目录", 2, required=True, min_prose_chars=30),
        HeadingSection("简介", "## 环境搭建", 2, required=True, min_prose_chars=80),
        HeadingSection("核心组件", "## 开发规范", 2, required=True, min_prose_chars=80),
        HeadingSection("详细分析", "## 测试策略", 2, required=False, min_prose_chars=80),
        HeadingSection("依赖", "## 贡献流程", 2, required=False, min_prose_chars=50),
        HeadingSection("附录", "## 附录", 2, required=False, min_prose_chars=0),
    ),
    toc_required=True,
    toc_depth=2,
)


# Registry of heading contracts
HEADING_CONTRACTS: dict[str, HeadingContract] = {
    "overview": OVERVIEW_HEADING_CONTRACT,
    "service": SERVICE_HEADING_CONTRACT,
    "api": API_HEADING_CONTRACT,
    "data": DATA_HEADING_CONTRACT,
    "entity": ENTITY_HEADING_CONTRACT,
    "ops": OPS_HEADING_CONTRACT,
    "development": DEVELOPMENT_HEADING_CONTRACT,
}


def get_heading_contract(page_type: str) -> HeadingContract:
    """Get heading contract for a page type.

    Args:
        page_type: Page type string (overview, service, api, data, entity, ops, development)

    Returns:
        HeadingContract for the page type

    Raises:
        ValueError: If page_type is not recognized
    """
    if page_type not in HEADING_CONTRACTS:
        raise ValueError(
            f"Unknown page type: {page_type}. " f"Available: {list(HEADING_CONTRACTS.keys())}"
        )
    return HEADING_CONTRACTS[page_type]


# =============================================================================
# ARTICLE SKELETON
# =============================================================================


@dataclass
class ArticleSkeleton:
    """A structured article skeleton with headings and TOC.

    This represents the skeletal structure of a Qoder-style article,
    including all headings, their levels, and an optional table of contents.
    """

    page_type: str
    title: str  # Article title (H1)
    headings: tuple[HeadingSection, ...]  # All headings in order
    toc_entries: tuple[str, ...]  # TOC entries (heading texts)
    context: dict[str, Any] = field(default_factory=dict)  # Template context

    def render_toc(self) -> str:
        """Render the table of contents as markdown."""
        if not self.toc_entries:
            return ""

        lines = ["## 目录", ""]
        for entry in self.toc_entries:
            # Convert heading to TOC entry (remove leading ## )
            toc_line = entry.strip()
            if toc_line.startswith("##"):
                toc_line = toc_line[2:].strip()
            # Indent based on level (simple approach)
            indent = "  " if "###" in entry else ""
            lines.append(f"{indent}- {toc_line}")
        return "\n".join(lines)

    def render_skeleton_markdown(self) -> str:
        """Render the skeleton as markdown headings."""
        lines = [f"# {self.title}", ""]

        for heading in self.headings:
            lines.append(heading.heading_text)
            lines.append("")  # Empty line after heading

        return "\n".join(lines)

    def get_heading_count(self) -> dict[int, int]:
        """Get count of headings by level."""
        counts: dict[int, int] = {}
        for heading in self.headings:
            counts[heading.level] = counts.get(heading.level, 0) + 1
        return counts


# =============================================================================
# SKELETON BUILDER
# =============================================================================


class SkeletonBuilder:
    """Builder for ArticleSkeleton instances.

    This builder creates Qoder-style article skeletons based on page type
    and provided context. It respects the heading contracts and can
    optionally include/exclude sections based on context.
    """

    def __init__(self, page_type: str) -> None:
        """Initialize builder for a page type.

        Args:
            page_type: The page type (overview, service, api, data, entity, ops, development)
        """
        self.page_type = page_type
        self._contract = get_heading_contract(page_type)
        self._context: dict[str, Any] = {}
        self._title = ""

    def set_title(self, title: str) -> SkeletonBuilder:
        """Set the article title.

        Args:
            title: The article title (H1)

        Returns:
            Self for chaining
        """
        self._title = title
        return self

    def set_context(self, **kwargs: Any) -> SkeletonBuilder:
        """Set template context.

        Returns:
            Self for chaining
        """
        self._context.update(kwargs)
        return self

    def include_optional_sections(self, *section_keys: str) -> SkeletonBuilder:
        """Explicitly include optional sections by their keys.

        Args:
            section_keys: Section keys to include (e.g., "性能", "排障")

        Returns:
            Self for chaining
        """
        # Mark sections as included
        for section in self._contract.sections:
            if section.key in section_keys and not section.required:
                # This is a no-op at build time, but signals intent
                pass
        return self

    def build(self) -> ArticleSkeleton:
        """Build the article skeleton.

        Returns:
            ArticleSkeleton with all headings and TOC

        Raises:
            ValueError: If title is not set
        """
        if not self._title:
            raise ValueError("Title must be set before building skeleton")

        # Collect headings based on contract
        headings: list[HeadingSection] = []
        toc_entries: list[str] = []

        for section in self._contract.sections:
            # Skip optional sections that aren't relevant based on context
            if not section.required and not self._is_section_relevant(section.key):
                continue

            headings.append(section)
            toc_entries.append(section.heading_text)

        return ArticleSkeleton(
            page_type=self.page_type,
            title=self._title,
            headings=tuple(headings),
            toc_entries=tuple(toc_entries),
            context=self._context.copy(),
        )

    def _is_section_relevant(self, section_key: str) -> bool:
        """Check if an optional section is relevant based on context.

        Args:
            section_key: Section key to check

        Returns:
            True if section should be included
        """
        # Check if context provides content for the section
        context_key = section_key.lower()
        for key in self._context:
            if context_key in key.lower():
                return True

        # Performance and troubleshooting sections are relevant if
        # there are performance-sensitive or error-prone components
        if section_key in ("性能", "排障"):
            return True

        return False


def build_skeleton(
    page_type: str,
    title: str,
    **context: Any,
) -> ArticleSkeleton:
    """Convenience function to build an article skeleton.

    Args:
        page_type: Page type (overview, service, api, data, entity, ops, development)
        title: Article title
        **context: Template context

    Returns:
        ArticleSkeleton instance
    """
    builder = SkeletonBuilder(page_type)
    builder.set_title(title)
    if context:
        builder.set_context(**context)
    return builder.build()


# =============================================================================
# TOC EXTRACTION AND VALIDATION
# =============================================================================


def extract_toc_from_markdown(content: str, max_depth: int = 2) -> list[tuple[int, str]]:
    """Extract table of contents from markdown content.

    Args:
        content: Markdown content
        max_depth: Maximum heading level to include (default 2, which means H1-H2)

    Returns:
        List of (level, heading_text) tuples
    """
    toc: list[tuple[int, str]] = []
    pattern = re.compile(r"^(#{1,6})\s+(.+)$")
    in_code_block = False

    for line in content.split("\n"):
        # Track code blocks
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        match = pattern.match(line.strip())
        if match:
            level = len(match.group(1))
            # Skip H1 (level 1) as it's typically the title
            # Only include H2+ up to max_depth
            if level > 1 and level <= max_depth:
                toc.append((level, match.group(2).strip()))

    return toc


def validate_toc_completeness(
    content: str,
    contract: HeadingContract,
) -> tuple[bool, list[str]]:
    """Validate that a markdown document has all required sections.

    Args:
        content: Markdown content to validate
        contract: Heading contract to validate against

    Returns:
        (is_valid, missing_sections) tuple
    """
    toc = extract_toc_from_markdown(content, max_depth=contract.toc_depth)

    # Extract section keys from TOC
    present_sections: set[str] = set()
    for level, heading_text in toc:
        for section in contract.sections:
            if heading_text in section.heading_text or section.heading_text in heading_text:
                present_sections.add(section.key)

    # Check required sections
    required = set(contract.get_required_sections())
    missing = list(required - present_sections)

    return len(missing) == 0, missing


def validate_heading_hierarchy(content: str) -> tuple[bool, str]:
    """Validate that heading levels are properly nested.

    Heading hierarchy rules:
    - H1 can be followed by H2 or stay at H1
    - H2 can be followed by H2 or H3
    - H3 can be followed by H3 or H4
    - Cannot skip levels (e.g., H2 directly followed by H4)

    Args:
        content: Markdown content to validate

    Returns:
        (is_valid, error_message) tuple
    """
    pattern = re.compile(r"^(#{1,6})\s+(.+)$")
    headings: list[int] = []

    for line in content.split("\n"):
        match = pattern.match(line.strip())
        if match:
            level = len(match.group(1))
            headings.append(level)

    # Validate hierarchy
    for i in range(1, len(headings)):
        prev_level = headings[i - 1]
        curr_level = headings[i]

        # Cannot skip levels
        if curr_level > prev_level + 1:
            return False, f"Heading level skip: H{prev_level} followed by H{curr_level}"

    return True, ""


# =============================================================================
# SNAPSHOT TEST UTILITIES
# =============================================================================


def generate_heading_snapshot(content: str) -> str:
    """Generate a heading snapshot from markdown content.

    This produces a compact representation of headings suitable for
    snapshot testing. Headings inside code blocks are excluded.

    Args:
        content: Markdown content

    Returns:
        Snapshot string showing heading structure
    """
    lines: list[str] = []
    pattern = re.compile(r"^(#{1,6})\s+(.+)$")
    in_code_block = False

    for line in content.split("\n"):
        # Track code blocks
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        match = pattern.match(line.strip())
        if match:
            level = len(match.group(1))
            heading = match.group(2).strip()
            indent = "  " * (level - 1)
            lines.append(f"{indent}{heading}")

    return "\n".join(lines)


def headings_match_snapshot(
    content: str,
    expected_snapshot: str,
) -> tuple[bool, str]:
    """Check if content headings match expected snapshot.

    Args:
        content: Markdown content
        expected_snapshot: Expected heading snapshot

    Returns:
        (matches, diff) tuple
    """
    actual = generate_heading_snapshot(content)
    if actual == expected_snapshot:
        return True, ""

    # Generate diff
    actual_lines = actual.split("\n")
    expected_lines = expected_snapshot.split("\n")

    diff_lines = ["Differences:"]

    for i, (actual_line, expected_line) in enumerate(zip(actual_lines, expected_lines, strict=False)):
        if actual_line != expected_line:
            diff_lines.append(f"Line {i}: got '{actual_line}', expected '{expected_line}'")

    if len(actual_lines) != len(expected_lines):
        diff_lines.append(f"Line count: got {len(actual_lines)}, expected {len(expected_lines)}")

    return False, "\n".join(diff_lines)
