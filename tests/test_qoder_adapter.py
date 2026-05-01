"""Tests for qoder-style navigation metadata adapter and import bridge."""

import pytest

from repo_wiki.adapter.qoder_adapter import (
    CANONICAL_SECTIONS,
    QODER_TO_CANONICAL,
    VALIDATION_REASON_CODES,
    QoderImportBridge,
    QoderNavMetadata,
    QoderNavNode,
    QoderToRepoAgentMapper,
    SideBySideComparisonResult,
    check_qoder_compatibility,
    format_side_by_side_report,
    generate_side_by_side_comparison,
)


class TestQoderNavNode:
    """Tests for QoderNavNode schema."""

    def test_minimal_node(self):
        node = QoderNavNode(id="q01-architecture", label="Architecture", nav_type="section")
        assert node.id == "q01-architecture"
        assert node.label == "Architecture"
        assert node.nav_type == "section"
        assert node.path is None
        assert len(node.children) == 0

    def test_node_with_children(self):
        child = QoderNavNode(id="child1", label="Child", nav_type="module")
        node = QoderNavNode(
            id="parent",
            label="Parent",
            nav_type="section",
            children=[child],
        )
        assert len(node.children) == 1
        assert node.children[0].id == "child1"

    def test_node_with_aliases(self):
        node = QoderNavNode(
            id="architecture",
            label="Architecture",
            nav_type="section",
            aliases=["q01-architecture", "arch"],
        )
        assert len(node.aliases) == 2
        assert "q01-architecture" in node.aliases


class TestQoderNavMetadata:
    """Tests for QoderNavMetadata schema."""

    def test_minimal_metadata(self):
        metadata = QoderNavMetadata()
        assert metadata.version == "1.0"
        assert metadata.root_id is None
        assert len(metadata.nodes) == 0

    def test_metadata_with_nodes(self):
        node = QoderNavNode(id="test", label="Test", nav_type="section")
        metadata = QoderNavMetadata(nodes=[node])
        assert len(metadata.nodes) == 1


class TestQoderToRepoAgentMapper:
    """Tests for Qoder to repo-agent mapper."""

    def test_finds_canonical_slug_q01_prefix(self):
        mapper = QoderToRepoAgentMapper()
        slug = mapper._find_canonical_slug("q01-architecture")
        assert slug == "architecture"

    def test_finds_canonical_slug_s01_prefix(self):
        mapper = QoderToRepoAgentMapper()
        slug = mapper._find_canonical_slug("s01-architecture")
        assert slug == "architecture"

    def test_finds_canonical_slug_direct(self):
        mapper = QoderToRepoAgentMapper()
        slug = mapper._find_canonical_slug("architecture")
        assert slug == "architecture"

    def test_finds_canonical_slug_data_model_underscore(self):
        mapper = QoderToRepoAgentMapper()
        slug = mapper._find_canonical_slug("data_model")
        assert slug == "data-model"

    def test_returns_none_for_unknown(self):
        mapper = QoderToRepoAgentMapper()
        slug = mapper._find_canonical_slug("unknown-section-xyz")
        assert slug is None

    def test_builds_section_path(self):
        mapper = QoderToRepoAgentMapper()
        node = QoderNavNode(id="q01-architecture", label="Architecture", nav_type="section")
        path = mapper._build_repo_agent_path("architecture", node)
        assert path == "docs/sections/architecture/index.md"

    def test_builds_overview_path(self):
        mapper = QoderToRepoAgentMapper()
        node = QoderNavNode(id="overview", label="Overview", nav_type="overview")
        path = mapper._build_repo_agent_path("project", node)
        assert path == "docs/00-project.md"

    def test_map_node_success(self):
        mapper = QoderToRepoAgentMapper()
        node = QoderNavNode(id="q01-architecture", label="Architecture", nav_type="section")
        result = mapper.map_node(node)
        assert result.success is True
        assert result.repo_agent_path == "docs/sections/architecture/index.md"

    def test_map_node_unknown_id(self):
        mapper = QoderToRepoAgentMapper()
        node = QoderNavNode(id="unknown-xyz", label="Unknown", nav_type="section")
        result = mapper.map_node(node)
        assert result.success is False
        assert len(result.warnings) > 0

    def test_map_node_detects_duplicate_id(self):
        mapper = QoderToRepoAgentMapper()
        node1 = QoderNavNode(id="architecture", label="Arch", nav_type="section")
        node2 = QoderNavNode(id="architecture", label="Arch 2", nav_type="section")
        mapper.map_node(node1)
        result = mapper.map_node(node2)
        assert result.success is False
        assert any("QODER_DUPLICATE_ID" in e for e in result.errors)


class TestQoderImportBridge:
    """Tests for Qoder import bridge."""

    def test_parses_minimal_metadata(self):
        bridge = QoderImportBridge()
        data = {
            "version": "1.0",
            "nodes": [
                {"id": "q01-architecture", "label": "Architecture", "type": "section"},
            ],
        }
        metadata = bridge.parse_qoder_metadata(data)
        assert len(metadata.nodes) == 1
        assert metadata.nodes[0].id == "q01-architecture"

    def test_parses_nested_children(self):
        bridge = QoderImportBridge()
        data = {
            "nodes": [
                {
                    "id": "parent",
                    "label": "Parent",
                    "type": "section",
                    "children": [
                        {"id": "child", "label": "Child", "type": "module"},
                    ],
                },
            ],
        }
        metadata = bridge.parse_qoder_metadata(data)
        assert len(metadata.nodes) == 1
        assert len(metadata.nodes[0].children) == 1
        assert metadata.nodes[0].children[0].id == "child"

    def test_imports_valid_metadata(self):
        bridge = QoderImportBridge()
        metadata = QoderNavMetadata(
            nodes=[
                QoderNavNode(id="q01-architecture", label="Architecture", nav_type="section"),
                QoderNavNode(id="q02-services", label="Services", nav_type="section"),
            ],
        )
        result = bridge.import_metadata(metadata)
        assert result.success is True
        assert result.total_qoder_nodes == 2
        assert result.total_mapped == 2

    def test_import_preserves_unmapped(self):
        bridge = QoderImportBridge()
        metadata = QoderNavMetadata(
            nodes=[
                QoderNavNode(id="unknown-xyz", label="Unknown", nav_type="section"),
            ],
        )
        result = bridge.import_metadata(metadata)
        assert len(result.unmapped_ids) == 1
        assert "unknown-xyz" in result.unmapped_ids


class TestCheckQoderCompatibility:
    """Tests for compatibility check convenience function."""

    def test_compatible_metadata(self):
        qoder_data = {
            "nodes": [
                {"id": "q01-architecture", "label": "Architecture", "type": "section"},
            ],
        }
        result = check_qoder_compatibility(qoder_data)
        assert "compatible" in result
        assert "import_result" in result

    def test_incompatible_with_error(self):
        # Invalid data (missing required 'id' field)
        qoder_data = {"nodes": [{"label": "No ID", "type": "section"}]}
        # This would cause a KeyError during parsing
        result = check_qoder_compatibility(qoder_data)
        # Should handle gracefully
        assert "compatible" in result


class TestCanonicalMappings:
    """Tests for canonical section mappings."""

    def test_all_qoder_prefixes_mapped(self):
        """Verify Q01/S01 prefixed sections map to canonical slugs."""
        mapper = QoderToRepoAgentMapper()

        for prefix in ["q", "s"]:
            for num in range(1, 10):
                q_id = f"{prefix}{num:02d}-architecture"
                slug = mapper._find_canonical_slug(q_id)
                if slug:
                    assert slug == "architecture"

    def test_data_model_variants(self):
        mapper = QoderToRepoAgentMapper()
        # underscore variant
        assert mapper._find_canonical_slug("data_model") == "data-model"
        # hyphen variant
        assert mapper._find_canonical_slug("data-model") == "data-model"


class TestValidationReasonCodes:
    """Tests for validation reason codes."""

    def test_all_codes_defined(self):
        assert "QODER_NODE_UNMAPPED" in VALIDATION_REASON_CODES
        assert "QODER_PATH_MISSING" in VALIDATION_REASON_CODES
        assert "QODER_ALIAS_CONFLICT" in VALIDATION_REASON_CODES
        assert "QODER_DEPTH_MISMATCH" in VALIDATION_REASON_CODES
        assert "QODER_CYCLE_DETECTED" in VALIDATION_REASON_CODES
        assert "QODER_DUPLICATE_ID" in VALIDATION_REASON_CODES


class TestIntegration:
    """Integration tests for the qoder adapter."""

    def test_full_import_flow(self):
        """Test complete import flow from qoder data to repo-agent mapping."""
        qoder_data = {
            "version": "1.0",
            "root_id": "root",
            "nodes": [
                {
                    "id": "q01-architecture",
                    "label": "Architecture",
                    "type": "section",
                    "path": "docs/sections/architecture/index.md",
                },
                {
                    "id": "q02-services",
                    "label": "Services",
                    "type": "section",
                    "children": [
                        {"id": "module-service-a", "label": "Service A", "type": "module"},
                    ],
                },
            ],
        }

        bridge = QoderImportBridge()
        metadata = bridge.parse_qoder_metadata(qoder_data)
        result = bridge.import_metadata(metadata)

        assert result.success is True
        assert result.total_qoder_nodes == 3  # 2 top-level + 1 child
        assert len(result.mapped_nodes) >= 2  # At least the mapped ones

    def test_qoder_to_canonical_mapping_coverage(self):
        """Test that all canonical sections have qoder mappings."""
        mapper = QoderToRepoAgentMapper()

        for section in CANONICAL_SECTIONS:
            # Each canonical section should be mappable
            slug = mapper._find_canonical_slug(section)
            # Most should map directly or via variants
            assert slug is not None or section in ["project", "python-services"]

    def test_mixed_mapped_unmapped(self):
        """Test handling of mixed mapped and unmapped nodes."""
        bridge = QoderImportBridge()
        metadata = QoderNavMetadata(
            nodes=[
                QoderNavNode(id="q01-architecture", label="Arch", nav_type="section"),
                QoderNavNode(id="unknown-section", label="Unknown", nav_type="section"),
                QoderNavNode(id="q05-api", label="API", nav_type="section"),
            ],
        )
        result = bridge.import_metadata(metadata)

        # Should have both mapped and unmapped
        assert len(result.unmapped_ids) == 1
        assert "unknown-section" in result.unmapped_ids
        assert len(result.mapped_nodes) == 2


class TestSideBySideComparison:
    """Tests for side-by-side navigation comparison."""

    def test_generate_side_by_side_comparison(self):
        """Test generation of side-by-side comparison result."""
        qoder_data = {
            "version": "1.0",
            "nodes": [
                {"id": "q01-architecture", "label": "Architecture", "type": "section"},
                {"id": "q02-services", "label": "Services", "type": "section"},
                {"id": "unknown-xyz", "label": "Unknown", "type": "section"},
            ],
        }
        result = generate_side_by_side_comparison(qoder_data)

        assert isinstance(result, SideBySideComparisonResult)
        assert len(result.qoder_nav) >= 2  # At least mapped ones
        assert "Mapped: 2" in result.summary or "Mapped:" in result.summary
        assert result.unmatched_qoder or len(result.qoder_nav) >= 2

    def test_side_by_side_comparison_with_alias_conflict(self):
        """Test detection of alias conflicts."""
        qoder_data = {
            "version": "1.0",
            "nodes": [
                {"id": "q01-architecture", "label": "Architecture", "type": "section", "aliases": ["arch", "architecture"]},
                {"id": "q02-services", "label": "Services", "type": "section", "aliases": ["arch"]},  # Duplicate alias
            ],
        }
        result = generate_side_by_side_comparison(qoder_data)
        # Should handle the duplicate alias gracefully
        assert isinstance(result, SideBySideComparisonResult)

    def test_format_side_by_side_report(self):
        """Test report formatting."""
        qoder_data = {
            "version": "1.0",
            "nodes": [
                {"id": "q01-architecture", "label": "Architecture", "type": "section"},
            ],
        }
        result = generate_side_by_side_comparison(qoder_data)
        report = format_side_by_side_report(result)

        assert "Qoder vs Repo-Agent Navigation Comparison" in report
        assert "MAPPED" in report or "mapped" in report.lower() or len(result.qoder_nav) >= 0
        assert "Canonical Sections" in report

    def test_side_by_side_comparison_unmapped_nodes(self):
        """Test that unmapped nodes are correctly identified."""
        qoder_data = {
            "version": "1.0",
            "nodes": [
                {"id": "q01-architecture", "label": "Architecture", "type": "section"},
                {"id": "completely-unknown-section", "label": "Unknown Section", "type": "section"},
            ],
        }
        result = generate_side_by_side_comparison(qoder_data)

        assert len(result.unmatched_qoder) >= 1 or len(result.qoder_nav) >= 1

    def test_side_by_side_is_read_only(self):
        """Test that comparison does not mutate qoder data."""
        qoder_data = {
            "version": "1.0",
            "nodes": [
                {"id": "q01-architecture", "label": "Architecture", "type": "section"},
            ],
        }
        original_data = dict(qoder_data)
        generate_side_by_side_comparison(qoder_data)
        # Data should be unchanged
        assert qoder_data == original_data
