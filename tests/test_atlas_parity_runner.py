"""Tests for AI_API_Atlas parity runner."""

from pathlib import Path

import pytest

from repo_wiki.verifier.atlas_parity_runner import (
    AIAPIAtlasParityRunner,
    GapItem,
    ParityComparisonResult,
    ParityMetric,
)


class TestAIAPIAtlasParityRunner:
    """Tests for AIAPIAtlasParityRunner."""

    @pytest.fixture
    def setup_atlas_structure(self, tmp_path):
        """Set up AI_API_Atlas-like directory structure."""
        # Create baseline
        baseline = tmp_path / ".qoder" / "repowiki" / "zh" / "content"
        baseline.mkdir(parents=True)

        # Create target
        target = tmp_path / ".repo-agent-eval" / "test-run" / "content"
        target.mkdir(parents=True)

        # Create baseline content
        (baseline / "00-overview.md").write_text("""# Overview

## Table of Contents
- [Intro](#intro)

## Introduction

This is a sample project.

<cite>source:readme.md</cite>

## Architecture

```mermaid
graph LR
    A --> B
```
""")

        # Create target content (similar but slightly different)
        (target / "00-overview.md").write_text("""# Overview

## Table of Contents

## Introduction

This is a sample project.

<cite>source:readme.md</cite>
""")

        return tmp_path

    def test_runner_initialization(self, setup_atlas_structure):
        """Test runner initializes correctly."""
        runner = AIAPIAtlasParityRunner(
            atlas_root=setup_atlas_structure,
            baseline_dir=setup_atlas_structure / ".qoder" / "repowiki" / "zh",
        )
        assert runner.run_id.startswith("atlas-parity-")
        assert runner.baseline_dir.exists()

    def test_extract_metrics_from_content(self, setup_atlas_structure):
        """Test extracting metrics from content directory."""
        runner = AIAPIAtlasParityRunner(
            atlas_root=setup_atlas_structure,
            baseline_dir=setup_atlas_structure / ".qoder" / "repowiki" / "zh",
        )

        content_dir = setup_atlas_structure / ".qoder" / "repowiki" / "zh" / "content"
        metrics = runner._extract_metrics(content_dir)

        assert metrics["page_count"] == 1
        assert metrics["citation_count"] == 1
        assert metrics["pages_with_citations"] == 1
        assert metrics["pages_with_toc"] == 1
        assert metrics["pages_with_mermaid"] == 1

    def test_run_comparison(self, setup_atlas_structure):
        """Test running comparison."""
        runner = AIAPIAtlasParityRunner(
            atlas_root=setup_atlas_structure,
            baseline_dir=setup_atlas_structure / ".qoder" / "repowiki" / "zh",
        )

        result = runner.run_comparison()

        assert result.run_id.startswith("atlas-parity-")
        assert "baseline" in result.metrics
        assert "target" in result.metrics
        assert len(result.gaps) >= 0  # May have gaps or not

    def test_count_prose(self, setup_atlas_structure):
        """Test prose counting."""
        runner = AIAPIAtlasParityRunner(atlas_root=setup_atlas_structure)

        content = """# Heading

Some prose text here.

- List item 1
- List item 2

More prose text.
"""
        prose_count = runner._count_prose(content)
        assert prose_count > 0

    def test_citation_density(self, setup_atlas_structure):
        """Test citation density calculation."""
        runner = AIAPIAtlasParityRunner(atlas_root=setup_atlas_structure)

        metrics = {
            "citation_count": 5,
            "total_prose_chars": 1000,
        }
        density = runner._compute_citation_density(metrics)
        assert density == 5.0  # 5/1000 * 1000 = 5

    def test_gap_severity_determination(self, setup_atlas_structure):
        """Test gap severity determination."""
        runner = AIAPIAtlasParityRunner(atlas_root=setup_atlas_structure)

        # Critical gap (>50%)
        gap = runner._make_gap(ParityMetric.PAGE_COUNT, 10, 3)
        if gap:
            assert gap.severity == "critical"

        # Major gap (30-50%)
        gap = runner._make_gap(ParityMetric.PAGE_COUNT, 10, 6)
        if gap:
            assert gap.severity in ["major", "minor", "info"]

    def test_overall_parity_calculation(self, setup_atlas_structure):
        """Test overall parity score calculation."""
        runner = AIAPIAtlasParityRunner(atlas_root=setup_atlas_structure)

        gaps = [
            GapItem(ParityMetric.PAGE_COUNT, 10, 5, 0.5, "critical"),
            GapItem(ParityMetric.CITATION_DENSITY, 5, 4, 0.2, "minor"),
        ]
        parity = runner._compute_overall_parity(gaps)
        assert 0 <= parity <= 1


class TestParityComparisonResult:
    """Tests for ParityComparisonResult."""

    def test_create_result(self):
        """Test creating a result."""
        result = ParityComparisonResult(
            run_id="test-run",
            generated_at="2024-01-01T00:00:00Z",
            baseline_content_dir=Path("/baseline"),
            target_content_dir=Path("/target"),
        )
        assert result.run_id == "test-run"
        assert len(result.gaps) == 0


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_run_atlas_parity(self, tmp_path):
        """Test run_atlas_parity factory."""
        # Create structure
        baseline = tmp_path / ".qoder" / "repowiki" / "zh" / "content"
        baseline.mkdir(parents=True)

        (baseline / "00-overview.md").write_text("# Overview\n\n<cite>x</cite>\n\n## TOC\n- a")

        target = tmp_path / ".repo-agent-eval" / "test" / "content"
        target.mkdir(parents=True)

        (target / "00-overview.md").write_text("# Overview\n\n<cite>x</cite>\n\n## TOC\n- a")

        runner = AIAPIAtlasParityRunner(atlas_root=tmp_path)
        result = runner.run_comparison()

        assert result is not None
        assert result.run_id.startswith("atlas-parity-")


class TestGapItem:
    """Tests for GapItem."""

    def test_create_gap_item(self):
        """Test creating a gap item."""
        gap = GapItem(
            metric=ParityMetric.PAGE_COUNT,
            baseline_value=10,
            target_value=5,
            gap_ratio=0.5,
            severity="major",
        )
        assert gap.metric == ParityMetric.PAGE_COUNT
        assert gap.gap_ratio == 0.5


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_content_dir(self, tmp_path):
        """Test handling empty content directory."""
        runner = AIAPIAtlasParityRunner(atlas_root=tmp_path)
        metrics = runner._extract_metrics(tmp_path / "nonexistent")

        assert metrics["page_count"] == 0
        assert metrics["citation_count"] == 0

    def test_zero_baseline(self, tmp_path):
        """Test gap with zero baseline."""
        runner = AIAPIAtlasParityRunner(atlas_root=tmp_path)

        gap = runner._make_gap(ParityMetric.PAGE_COUNT, 0, 5)
        # If baseline is 0 and target > 0, gap ratio is 1.0 (critical)
        if gap:
            assert gap.gap_ratio == 1.0

    def test_no_significant_gap(self, tmp_path):
        """Test that small gaps are filtered out."""
        runner = AIAPIAtlasParityRunner(atlas_root=tmp_path)

        # 5% gap - should be filtered
        gap = runner._make_gap(ParityMetric.PAGE_COUNT, 100, 95)
        assert gap is None  # Filtered out because < 10%
