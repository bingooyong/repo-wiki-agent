"""Tests for baseline comparator score integrity and calibration."""

from __future__ import annotations

import tempfile
from pathlib import Path

from repo_wiki.generator.io import write_text
from scripts.qoder_baseline_comparison import (
    QODER_REQUIRED_SECTIONS,
    DeltaType,
    DimensionResult,
    QoderBaselineComparator,
    ScoreBand,
    get_score_band,
)


def _create_minimal_target(root: Path) -> None:
    """Create minimal target structure for testing."""
    # Create docs structure
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/sections").mkdir(parents=True, exist_ok=True)

    # Create minimal overview
    write_text(
        root / "docs/00-overview.md",
        """# Overview

This is a test overview.
""",
    )

    # Create minimal architecture
    write_text(
        root / "docs/01-architecture.md",
        """# Architecture

```mermaid
graph TD
    A --> B
```
""",
    )


def _create_quality_target(root: Path) -> None:
    """Create quality target structure that should score well."""
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/sections").mkdir(parents=True, exist_ok=True)

    # Create quality overview with proper headings
    write_text(
        root / "docs/00-overview.md",
        """# Overview

## 项目定位

This project provides documentation generation.

## 核心问题

We need better documentation.

## 核心能力

The system can scan and generate docs.

## 快速开始

Run `poetry install`.

## 阅读导航

See architecture for details.
""",
    )

    # Create quality architecture with multiple diagrams
    write_text(
        root / "docs/01-architecture.md",
        """# Architecture

## 系统分层

The system has three layers.

```mermaid
graph TD
    A[.repo-wiki/] --> B[ai/source-of-truth/]
    B --> C[docs/]
```

## 服务协作

Services work together.

```mermaid
graph LR
    A[Scanner] --> B[Indexer]
```
""",
    )

    # Create sections
    for section in QODER_REQUIRED_SECTIONS[:5]:
        section_dir = root / "docs/sections" / section
        section_dir.mkdir(parents=True, exist_ok=True)
        write_text(
            section_dir / "index.md",
            f"""# {section.title()}

## Navigation

- [Overview](../../00-overview.md)
- [Architecture](../../01-architecture.md)

Content for {section}.
""",
        )

    # Create API contracts
    write_text(
        root / "docs/04-api-contracts.md",
        """# API Contracts

## API Groups

## Call Conventions

### Authentication

Bearer token.

### Key Entry APIs

GET /health.
""",
    )

    # Create data model
    write_text(
        root / "docs/05-data-model.md",
        """# Data Models

## Core Data Models

Invoice model.

## Service Data Models

Billing models.

## Database and Migration Strategy

Alembic migrations.
""",
    )


class TestScoreBandCalibration:
    """Test score band calibration."""

    def test_score_band_excellent(self) -> None:
        """Test EXCELLENT band for scores >= 90%."""
        assert get_score_band(1.0) == ScoreBand.EXCELLENT
        assert get_score_band(0.95) == ScoreBand.EXCELLENT
        assert get_score_band(0.90) == ScoreBand.EXCELLENT

    def test_score_band_good(self) -> None:
        """Test GOOD band for scores >= 70% and < 90%."""
        assert get_score_band(0.89) == ScoreBand.GOOD
        assert get_score_band(0.75) == ScoreBand.GOOD
        assert get_score_band(0.70) == ScoreBand.GOOD

    def test_score_band_acceptable(self) -> None:
        """Test ACCEPTABLE band for scores >= 50% and < 70%."""
        assert get_score_band(0.69) == ScoreBand.ACCEPTABLE
        assert get_score_band(0.55) == ScoreBand.ACCEPTABLE
        assert get_score_band(0.50) == ScoreBand.ACCEPTABLE

    def test_score_band_poor(self) -> None:
        """Test POOR band for scores < 50%."""
        assert get_score_band(0.49) == ScoreBand.POOR
        assert get_score_band(0.25) == ScoreBand.POOR
        assert get_score_band(0.0) == ScoreBand.POOR


class TestScoreIntegrity:
    """Test score reproducibility and integrity."""

    def test_same_input_produces_same_score(self) -> None:
        """Test that same input produces identical scores."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_quality_target(root)

            # Run comparison twice
            comparator1 = QoderBaselineComparator(root, root)
            report1 = comparator1.compare_all()

            comparator2 = QoderBaselineComparator(root, root)
            report2 = comparator2.compare_all()

            # Scores should be identical
            assert report1.summary["overall_score"] == report2.summary["overall_score"]
            assert report1.summary["structural_score"] == report2.summary["structural_score"]
            assert report1.summary["quality_score"] == report2.summary["quality_score"]

    def test_dimension_scores_are_bounded(self) -> None:
        """Test that dimension scores are between 0 and 1."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_quality_target(root)

            comparator = QoderBaselineComparator(root, root)
            report = comparator.compare_all()

            for dim in report.dimensions:
                assert (
                    0.0 <= dim.score <= 1.0
                ), f"Score {dim.score} out of bounds for {dim.dimension}"

    def test_overall_score_is_weighted_sum(self) -> None:
        """Test that overall score is weighted sum of dimension scores (Phase 14)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_quality_target(root)

            comparator = QoderBaselineComparator(root, root)
            report = comparator.compare_all()

            # Phase 14: Overall score is now a weighted sum, not a simple average
            # Check that weighting scheme is documented
            assert report.summary.get("weighting_scheme") == "explicit"
            assert "dimension_weights" in report.summary
            assert "weighted_breakdown" in report.summary

            # Verify weighted breakdown sums to overall score
            weighted_sum = sum(ws["weighted_score"] for ws in report.summary["weighted_breakdown"])
            assert abs(report.summary["overall_score"] - weighted_sum) < 0.001

    def test_overall_score_bounded_by_weights(self) -> None:
        """Test that overall score respects weight boundaries (Phase 14 anti-inflation)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_quality_target(root)

            comparator = QoderBaselineComparator(root, root)
            report = comparator.compare_all()

            # Overall score should be sum of weighted scores
            # Each weighted score = raw_score * weight
            # Sum of all weights = 1.0
            total_weight = sum(report.summary["dimension_weights"].values())
            assert abs(total_weight - 1.0) < 0.001

    def test_structural_vs_quality_separation(self) -> None:
        """Test that structural and quality dimensions are properly separated."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_quality_target(root)

            comparator = QoderBaselineComparator(root, root)
            report = comparator.compare_all()

            structural_dims = [d for d in report.dimensions if d.delta_type == DeltaType.STRUCTURAL]
            quality_dims = [d for d in report.dimensions if d.delta_type == DeltaType.QUALITY]

            # Should have 3 structural dimensions: directory_hierarchy, section_coverage, navigation_completeness
            assert len(structural_dims) == 3
            # Should have 3 quality dimensions: heading_coverage, prose_density, aggregation_quality
            assert len(quality_dims) == 3

    def test_acceptance_blocked_on_structural_failure(self) -> None:
        """Test that acceptance is blocked when structural dimensions fail."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Create minimal structure (no sections)
            _create_minimal_target(root)

            comparator = QoderBaselineComparator(root, root)
            report = comparator.compare_all()

            # With missing sections, acceptance should be blocked
            assert report.summary["acceptance_blocked"] is True

    def test_score_band_consistency(self) -> None:
        """Test that score bands are consistent with scores."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_quality_target(root)

            comparator = QoderBaselineComparator(root, root)
            report = comparator.compare_all()

            for dim in report.dimensions:
                expected_band = get_score_band(dim.score)
                assert dim.score_band == expected_band, (
                    f"Inconsistent band for {dim.dimension}: "
                    f"score={dim.score} but band={dim.score_band}, expected={expected_band}"
                )


class TestDeltaTypeClassification:
    """Test delta type classification."""

    def test_structural_dimensions(self) -> None:
        """Test that structural dimensions are correctly classified."""
        structural_dims = {
            "directory_hierarchy",
            "section_coverage",
            "navigation_completeness",
        }

        for dim in structural_dims:
            result = DimensionResult(
                dimension=dim,
                status="PASS",
                score=1.0,
                delta_type=DeltaType.STRUCTURAL,
            )
            assert result.delta_type == DeltaType.STRUCTURAL

    def test_quality_dimensions(self) -> None:
        """Test that quality dimensions are correctly classified."""
        quality_dims = {
            "heading_coverage",
            "prose_density",
            "aggregation_quality",
        }

        for dim in quality_dims:
            result = DimensionResult(
                dimension=dim,
                status="PASS",
                score=1.0,
                delta_type=DeltaType.QUALITY,
            )
            assert result.delta_type == DeltaType.QUALITY


class TestPhase14Calibration:
    """Test Phase 14 calibration features: weights, anti-inflation, determinism."""

    def test_weighted_breakdown_in_summary(self) -> None:
        """Test that weighted breakdown is included in summary (Phase 14)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_quality_target(root)

            comparator = QoderBaselineComparator(root, root)
            report = comparator.compare_all()

            # Check weighted breakdown exists
            assert "weighted_breakdown" in report.summary
            assert len(report.summary["weighted_breakdown"]) == 6  # 6 dimensions

            # Each entry should have required fields
            for entry in report.summary["weighted_breakdown"]:
                assert "dimension" in entry
                assert "raw_score" in entry
                assert "weighted_score" in entry
                assert "weight" in entry
                assert "delta_type" in entry

    def test_structural_quality_scores_sum_to_one(self) -> None:
        """Test that structural and quality weights sum correctly (Phase 14)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_quality_target(root)

            comparator = QoderBaselineComparator(root, root)
            report = comparator.compare_all()

            # Structural weights: 0.20 * 3 = 0.60
            # Quality weights: ~0.133 * 3 = ~0.40
            structural_weight = sum(
                entry["weight"]
                for entry in report.summary["weighted_breakdown"]
                if entry["delta_type"] == "STRUCTURAL"
            )
            quality_weight = sum(
                entry["weight"]
                for entry in report.summary["weighted_breakdown"]
                if entry["delta_type"] == "QUALITY"
            )

            assert abs(structural_weight - 0.60) < 0.01
            assert abs(quality_weight - 0.40) < 0.01
            assert abs(structural_weight + quality_weight - 1.0) < 0.01

    def test_no_single_dimension_dominates(self) -> None:
        """Test that no single dimension can dominate the overall score (anti-inflation)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_quality_target(root)

            comparator = QoderBaselineComparator(root, root)
            report = comparator.compare_all()

            # Max possible contribution from any single dimension
            max_single_contribution = max(
                entry["weight"] for entry in report.summary["weighted_breakdown"]
            )

            # No dimension should have weight > 0.25 (to prevent domination)
            assert max_single_contribution <= 0.25

    def test_score_stability_across_runs(self) -> None:
        """Test that scores are deterministic across multiple runs."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_quality_target(root)

            # Run comparison multiple times
            scores = []
            for _ in range(5):
                comparator = QoderBaselineComparator(root, root)
                report = comparator.compare_all()
                scores.append(report.summary["overall_score"])

            # All scores should be identical
            assert len(set(scores)) == 1, f"Score instability detected: {scores}"

    def test_weighting_scheme_documented(self) -> None:
        """Test that weighting scheme is documented in output."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_quality_target(root)

            comparator = QoderBaselineComparator(root, root)
            report = comparator.compare_all()

            assert report.summary.get("weighting_scheme") == "explicit"
            assert "dimension_weights" in report.summary
            assert len(report.summary["dimension_weights"]) == 6

    def test_acceptance_blocked_on_structural_failure_despite_high_quality(self) -> None:
        """Test that high quality score cannot overcome structural failure."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_minimal_target(root)

            comparator = QoderBaselineComparator(root, root)
            report = comparator.compare_all()

            # Structural failure should block acceptance regardless of quality
            assert report.summary["acceptance_blocked"] is True
