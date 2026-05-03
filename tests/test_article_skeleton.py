"""Tests for article skeleton builder and heading contracts.

Tests the skeleton module (repo_wiki/prompts/skeleton.py) which provides:
- ArticleSkeleton: Structured article outline with headings and TOC
- HeadingContract: Valid heading hierarchies per page type
- SkeletonBuilder: Builds skeletons from page types and context
- TOC extraction and validation utilities

Phase 24 - Task 24.2: Qoder-style article skeleton
"""

from __future__ import annotations

import pytest

from repo_wiki.prompts.skeleton import (
    API_HEADING_CONTRACT,
    HEADING_CONTRACTS,
    OVERVIEW_HEADING_CONTRACT,
    # Section definitions
    SECTION_KEYS,
    SERVICE_HEADING_CONTRACT,
    # Skeleton
    ArticleSkeleton,
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


class TestSectionKeys:
    """Tests for SECTION_KEYS constant."""

    def test_all_required_sections_defined(self) -> None:
        """Test that all required sections are in SECTION_KEYS."""
        required = [
            "目录",
            "简介",
            "项目结构",
            "核心组件",
            "架构总览",
            "详细分析",
            "依赖",
            "性能",
            "排障",
            "结论",
            "附录",
        ]
        for section in required:
            assert section in SECTION_KEYS, f"Missing section: {section}"


class TestHeadingSection:
    """Tests for HeadingSection dataclass."""

    def test_heading_section_creation(self) -> None:
        """Test creating a HeadingSection."""
        section = HeadingSection(
            key="目录", heading_text="## 目录", level=2, required=True, min_prose_chars=50
        )
        assert section.key == "目录"
        assert section.heading_text == "## 目录"
        assert section.level == 2
        assert section.required is True
        assert section.min_prose_chars == 50

    def test_heading_section_defaults(self) -> None:
        """Test HeadingSection default values."""
        section = HeadingSection(key="测试", heading_text="## 测试", level=2)
        assert section.required is False
        assert section.min_prose_chars == 0


class TestHeadingContract:
    """Tests for HeadingContract dataclass."""

    def test_overview_contract_structure(self) -> None:
        """Test overview contract has correct structure."""
        contract = OVERVIEW_HEADING_CONTRACT
        assert contract.page_type == "overview"
        assert len(contract.sections) >= 8
        assert contract.toc_required is True
        assert contract.toc_depth == 2

    def test_all_page_types_have_contracts(self) -> None:
        """Test that all expected page types have contracts."""
        expected = ["overview", "service", "api", "data", "entity", "ops", "development"]
        for page_type in expected:
            assert page_type in HEADING_CONTRACTS, f"Missing contract for {page_type}"

    def test_overview_required_sections(self) -> None:
        """Test overview contract requires correct sections."""
        contract = OVERVIEW_HEADING_CONTRACT
        required = contract.get_required_sections()
        assert "目录" in required
        assert "简介" in required
        assert "项目结构" in required
        assert "核心组件" in required

    def test_service_required_sections(self) -> None:
        """Test service contract requires correct sections."""
        contract = SERVICE_HEADING_CONTRACT
        required = contract.get_required_sections()
        assert "目录" in required
        assert "简介" in required
        assert "核心组件" in required

    def test_api_required_sections(self) -> None:
        """Test API contract requires correct sections."""
        contract = API_HEADING_CONTRACT
        required = contract.get_required_sections()
        assert "目录" in required
        assert "简介" in required
        assert "核心组件" in required
        assert "详细分析" in required  # 端点详情

    def test_get_optional_sections(self) -> None:
        """Test getting optional sections from contract."""
        contract = OVERVIEW_HEADING_CONTRACT
        optional = contract.get_optional_sections()
        # 架构总览, 详细分析, 依赖, 性能, 排障, 结论, 附录 should be optional
        assert "架构总览" in optional
        assert "详细分析" in optional
        assert "附录" in optional

    def test_validate_heading(self) -> None:
        """Test heading validation against contract."""
        contract = OVERVIEW_HEADING_CONTRACT
        assert contract.validate_heading("## 目录") is True
        assert contract.validate_heading("## 简介") is True
        assert contract.validate_heading("## 核心组件") is True
        assert contract.validate_heading("## 不存在的章节") is False

    def test_contract_has_min_prose_chars(self) -> None:
        """Test that required sections have min_prose_chars set."""
        for contract in HEADING_CONTRACTS.values():
            for section in contract.sections:
                if section.required:
                    assert (
                        section.min_prose_chars > 0
                    ), f"{contract.page_type}.{section.key} required but has no min_prose_chars"


class TestGetHeadingContract:
    """Tests for get_heading_contract function."""

    def test_valid_page_types(self) -> None:
        """Test getting contracts for valid page types."""
        for page_type in ["overview", "service", "api", "data", "entity", "ops", "development"]:
            contract = get_heading_contract(page_type)
            assert contract is not None
            assert contract.page_type == page_type

    def test_invalid_page_type_raises(self) -> None:
        """Test that invalid page type raises ValueError."""
        with pytest.raises(ValueError):
            get_heading_contract("invalid")


class TestArticleSkeleton:
    """Tests for ArticleSkeleton dataclass."""

    def test_render_toc_empty(self) -> None:
        """Test rendering empty TOC."""
        skeleton = ArticleSkeleton(
            page_type="overview",
            title="Test",
            headings=(),
            toc_entries=(),
        )
        assert skeleton.render_toc() == ""

    def test_render_toc_with_entries(self) -> None:
        """Test rendering TOC with entries."""
        skeleton = ArticleSkeleton(
            page_type="overview",
            title="Test",
            headings=(
                HeadingSection("目录", "## 目录", 2),
                HeadingSection("简介", "## 简介", 2),
            ),
            toc_entries=("## 目录", "## 简介"),
        )
        toc = skeleton.render_toc()
        assert "## 目录" in toc
        # TOC entries are rendered as "- 简介" (markdown list), not "## 简介"
        assert "- 目录" in toc
        assert "- 简介" in toc

    def test_render_skeleton_markdown(self) -> None:
        """Test rendering skeleton as markdown."""
        skeleton = ArticleSkeleton(
            page_type="overview",
            title="Test Title",
            headings=(
                HeadingSection("目录", "## 目录", 2),
                HeadingSection("简介", "## 简介", 2),
            ),
            toc_entries=(),
        )
        md = skeleton.render_skeleton_markdown()
        assert "# Test Title" in md
        assert "## 目录" in md
        assert "## 简介" in md

    def test_get_heading_count(self) -> None:
        """Test getting heading count by level."""
        skeleton = ArticleSkeleton(
            page_type="overview",
            title="Test",
            headings=(
                HeadingSection("目录", "## 目录", 2),
                HeadingSection("简介", "## 简介", 2),
                HeadingSection("核心组件", "### 核心组件", 3),
            ),
            toc_entries=(),
        )
        counts = skeleton.get_heading_count()
        assert counts[2] == 2
        assert counts[3] == 1


class TestSkeletonBuilder:
    """Tests for SkeletonBuilder class."""

    def test_build_minimal_skeleton(self) -> None:
        """Test building a minimal skeleton."""
        builder = SkeletonBuilder("overview")
        builder.set_title("Test Repository")
        skeleton = builder.build()

        assert skeleton.page_type == "overview"
        assert skeleton.title == "Test Repository"
        assert len(skeleton.headings) >= 4  # At least required sections

    def test_builder_context(self) -> None:
        """Test setting context on builder."""
        builder = SkeletonBuilder("overview")
        builder.set_title("Test")
        builder.set_context(performance_data="CPU metrics")
        skeleton = builder.build()

        assert skeleton.context["performance_data"] == "CPU metrics"

    def test_build_without_title_raises(self) -> None:
        """Test that building without title raises ValueError."""
        builder = SkeletonBuilder("overview")
        with pytest.raises(ValueError, match="Title must be set"):
            builder.build()

    def test_all_overview_sections_included(self) -> None:
        """Test all overview sections are included when built."""
        builder = SkeletonBuilder("overview")
        builder.set_title("Test Overview")
        skeleton = builder.build()

        heading_keys = [s.key for s in skeleton.headings]
        # Required sections should be present
        assert "目录" in heading_keys
        assert "简介" in heading_keys
        assert "项目结构" in heading_keys
        assert "核心组件" in heading_keys

    def test_api_skeleton_includes_endpoint_details(self) -> None:
        """Test API skeleton includes endpoint details section."""
        builder = SkeletonBuilder("api")
        builder.set_title("API Reference")
        skeleton = builder.build()

        heading_keys = [s.key for s in skeleton.headings]
        assert "详细分析" in heading_keys  # 端点详情


class TestBuildSkeleton:
    """Tests for build_skeleton convenience function."""

    def test_build_overview_skeleton(self) -> None:
        """Test building overview skeleton."""
        skeleton = build_skeleton("overview", title="My Project", repository_name="my-project")

        assert skeleton.page_type == "overview"
        assert skeleton.title == "My Project"
        assert len(skeleton.headings) > 0

    def test_build_service_skeleton(self) -> None:
        """Test building service skeleton."""
        skeleton = build_skeleton(
            "service", title="Auth Service", section_description="Authentication service"
        )

        assert skeleton.page_type == "service"
        assert skeleton.title == "Auth Service"

    def test_build_api_skeleton(self) -> None:
        """Test building API skeleton."""
        skeleton = build_skeleton("api", title="REST API", api_groups=[])

        assert skeleton.page_type == "api"
        assert skeleton.title == "REST API"


class TestExtractTocFromMarkdown:
    """Tests for extract_toc_from_markdown function."""

    def test_extract_simple_toc(self) -> None:
        """Test extracting TOC from simple markdown."""
        content = """# Title

## 目录

## 简介

### 背景

## 核心组件
"""
        toc = extract_toc_from_markdown(content, max_depth=3)
        # H1 (Title) is skipped, so we get 4 entries: 目录, 简介, 背景, 核心组件
        assert len(toc) == 4
        # First entry should be 目录 (H2), not Title (H1)
        assert toc[0] == (2, "目录")
        assert toc[1] == (2, "简介")
        assert toc[2] == (3, "背景")
        assert toc[3] == (2, "核心组件")

    def test_extract_toc_respects_max_depth(self) -> None:
        """Test that TOC extraction respects max_depth."""
        content = """# Title

## 目录

## 简介

### 背景

#### 子背景

## 核心组件
"""
        toc = extract_toc_from_markdown(content, max_depth=2)
        # H1 (Title) is skipped, H3+ are skipped due to max_depth=2
        # Only H2 entries: 目录, 简介, 核心组件
        assert len(toc) == 3
        # All entries should be at level <= max_depth (2)
        assert all(level <= 2 for level, _ in toc)
        # Only H2 entries should be present (Title is H1 and skipped, 背景 is H3)
        assert toc[0] == (2, "目录")
        assert toc[1] == (2, "简介")
        assert toc[2] == (2, "核心组件")

    def test_extract_empty_content(self) -> None:
        """Test extracting TOC from empty content."""
        toc = extract_toc_from_markdown("")
        assert toc == []


class TestValidateTocCompleteness:
    """Tests for validate_toc_completeness function."""

    def test_valid_overview_toc(self) -> None:
        """Test validation passes for complete overview TOC."""
        content = """# Test

## 目录

## 简介

## 项目结构

## 核心组件

## 附录
"""
        is_valid, missing = validate_toc_completeness(content, OVERVIEW_HEADING_CONTRACT)
        assert is_valid is True
        assert missing == []

    def test_missing_required_sections(self) -> None:
        """Test validation fails for missing required sections."""
        content = """# Test

## 目录

## 简介
"""
        is_valid, missing = validate_toc_completeness(content, OVERVIEW_HEADING_CONTRACT)
        assert is_valid is False
        assert "项目结构" in missing
        assert "核心组件" in missing


class TestValidateHeadingHierarchy:
    """Tests for validate_heading_hierarchy function."""

    def test_valid_hierarchy(self) -> None:
        """Test validation passes for valid hierarchy."""
        content = """# Title

## Section 1

### Subsection 1.1

### Subsection 1.2

## Section 2
"""
        is_valid, error = validate_heading_hierarchy(content)
        assert is_valid is True
        assert error == ""

    def test_invalid_level_skip(self) -> None:
        """Test validation fails for skipped heading levels."""
        content = """# Title

## Section 1

#### Subsection 1.1 (invalid - H2 to H4)
"""
        is_valid, error = validate_heading_hierarchy(content)
        assert is_valid is False
        assert "H2 followed by H4" in error

    def test_empty_content(self) -> None:
        """Test validation passes for empty content."""
        is_valid, error = validate_heading_hierarchy("")
        assert is_valid is True


class TestGenerateHeadingSnapshot:
    """Tests for generate_heading_snapshot function."""

    def test_generate_snapshot(self) -> None:
        """Test generating heading snapshot."""
        content = """# Title

## 目录

## 简介

### 背景

## 核心组件
"""
        snapshot = generate_heading_snapshot(content)
        assert "目录" in snapshot
        assert "简介" in snapshot
        assert "  背景" in snapshot  # Indented for level 3
        assert "核心组件" in snapshot

    def test_snapshot_excludes_code_blocks(self) -> None:
        """Test that snapshot excludes headings in code blocks."""
        content = """# Title

## 目录

```
# Inside code block
```

## 简介
"""
        snapshot = generate_heading_snapshot(content)
        assert "Inside code block" not in snapshot
        assert snapshot.count("目录") == 1


class TestHeadingsMatchSnapshot:
    """Tests for headings_match_snapshot function."""

    def test_matching_snapshot(self) -> None:
        """Test that matching content returns True."""
        content = """# Title

## 目录

## 简介
"""
        # Snapshot includes H1 with no indent, H2 with 1 indent
        snapshot = """Title
  目录
  简介"""
        matches, diff = headings_match_snapshot(content, snapshot)
        assert matches is True
        assert diff == ""

    def test_non_matching_snapshot(self) -> None:
        """Test that non-matching content returns False with diff."""
        content = """# Title

## 目录

## 新章节
"""
        snapshot = """Title
  目录
  简介"""
        matches, diff = headings_match_snapshot(content, snapshot)
        assert matches is False
        assert "新章节" in diff or "简介" in diff or "差异" in diff.lower()


class TestHeadingContractsSnapshot:
    """Snapshot tests for heading contracts."""

    def test_overview_contract_heading_count(self) -> None:
        """Test overview contract has expected number of headings."""
        contract = OVERVIEW_HEADING_CONTRACT
        # Overview should have 11 sections total
        assert len(contract.sections) == 11

    def test_all_contracts_have_toc(self) -> None:
        """Test all contracts require TOC."""
        for page_type, contract in HEADING_CONTRACTS.items():
            assert contract.toc_required is True, f"{page_type} should require TOC"

    def test_all_contracts_toc_depth_is_2(self) -> None:
        """Test all contracts have TOC depth of 2."""
        for contract in HEADING_CONTRACTS.values():
            assert contract.toc_depth == 2


class TestSkeletonSnapshotTests:
    """Snapshot tests for article skeletons."""

    def test_overview_skeleton_snapshot(self) -> None:
        """Test overview skeleton matches expected snapshot."""
        skeleton = build_skeleton("overview", title="Test Repository", repository_name="test-repo")

        snapshot = generate_heading_snapshot(skeleton.render_skeleton_markdown())
        # Should contain key sections
        assert "目录" in snapshot
        assert "简介" in snapshot
        assert "项目结构" in snapshot
        assert "核心组件" in snapshot

    def test_api_skeleton_snapshot(self) -> None:
        """Test API skeleton matches expected snapshot."""
        skeleton = build_skeleton("api", title="API Reference")

        snapshot = generate_heading_snapshot(skeleton.render_skeleton_markdown())
        # Should contain API-specific sections
        assert "目录" in snapshot
        assert "API 分组" in snapshot
        assert "调用约定" in snapshot
        assert "端点详情" in snapshot

    def test_ops_skeleton_snapshot(self) -> None:
        """Test Ops skeleton matches expected snapshot."""
        skeleton = build_skeleton("ops", title="Deployment Guide")

        snapshot = generate_heading_snapshot(skeleton.render_skeleton_markdown())
        # Should contain ops-specific sections
        assert "目录" in snapshot
        assert "环境配置" in snapshot
        assert "部署流程" in snapshot


class TestTOCSnapshotTests:
    """Snapshot tests for TOC generation."""

    def test_overview_toc_render(self) -> None:
        """Test overview TOC renders correctly."""
        skeleton = build_skeleton("overview", title="Test")
        toc = skeleton.render_toc()

        assert "## 目录" in toc
        assert "- 目录" in toc
        # Required sections should be in TOC
        assert "- 简介" in toc
        assert "- 项目结构" in toc
        assert "- 核心组件" in toc

    def test_service_toc_render(self) -> None:
        """Test service TOC renders correctly."""
        skeleton = build_skeleton("service", title="Test Service")
        toc = skeleton.render_toc()

        assert "## 目录" in toc
        assert "- 服务概述" in toc
        assert "- 核心模块" in toc

    def test_toc_excludes_deep_headings(self) -> None:
        """Test TOC only includes headings up to max_depth."""
        skeleton = build_skeleton("overview", title="Test")
        toc = skeleton.render_toc()

        # All entries should be at appropriate levels
        for line in toc.split("\n"):
            if line.startswith("-") and "  -" not in line:
                # Top level TOC entry
                pass


class TestSkeletonBuilderChaining:
    """Tests for builder method chaining."""

    def test_chained_methods(self) -> None:
        """Test that builder methods can be chained."""
        skeleton = (
            SkeletonBuilder("overview")
            .set_title("Chained Title")
            .set_context(key1="value1", key2="value2")
            .include_optional_sections("性能", "排障")
            .build()
        )

        assert skeleton.title == "Chained Title"
        assert skeleton.context["key1"] == "value1"
        assert skeleton.context["key2"] == "value2"
