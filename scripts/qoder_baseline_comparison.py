#!/usr/bin/env python3
"""
Qoder Baseline Comparison Tool (Phase 11 Redesign)

Compares generated repo-wiki outputs against qoder-style baseline repository.
This tool provides machine-readable and human-readable gap reports for governance reviews.

Phase 11 improvements:
- Distinguishes structural deltas from quality deltas
- Provides calibrated score bands with clear acceptance criteria
- Produces reproducible and explainable scores
- Generates machine-readable evidence alongside scores

Usage:
    python scripts/qoder_baseline_comparison.py \
        --target /path/to/generated/output \
        --baseline /path/to/qoder/baseline \
        --output /path/to/gap-report.json \
        --format json|markdown|both

Comparison Dimensions:
    1. Directory Hierarchy - Compare docs/ structure (STRUCTURAL)
    2. Section Coverage - Compare section pages present (STRUCTURAL)
    3. Heading Coverage - Compare heading patterns in overview docs (QUALITY)
    4. Prose Density - Compare prose vs list/table ratio (QUALITY)
    5. Navigation Completeness - Compare cross-links between docs (STRUCTURAL)
    6. Aggregation Quality - Compare API/data-model aggregation level (QUALITY)
"""

from __future__ import annotations

import argparse
import json
import sys
import typing
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class DeltaType(Enum):
    """Classification of comparison deltas.

    STRUCTURAL deltas are hard failures that block acceptance.
    QUALITY deltas are soft failures that indicate needed improvement.
    """

    STRUCTURAL = "STRUCTURAL"  # Hard failures - must fix
    QUALITY = "QUALITY"  # Soft failures - should fix


class GapSeverity(Enum):
    CRITICAL = "CRITICAL"  # Missing core structure (always blocks)
    MAJOR = "MAJOR"  # Missing important content
    MINOR = "MINOR"  # Quality improvements needed
    INFO = "INFO"  # Informational only


class ScoreBand(Enum):
    """Calibrated score bands for acceptance decisions.

    Each band has a clear meaning for teams:
    - EXCELLENT (90-100%): Exceeds baseline expectations
    - GOOD (70-89%): Meets baseline with minor gaps
    - ACCEPTABLE (50-69%): Meets minimum, needs improvement
    - POOR (<50%): Significant gaps, requires major work
    """

    EXCELLENT = "EXCELLENT"  # 90-100%: Exceeds baseline
    GOOD = "GOOD"  # 70-89%: Meets baseline with minor gaps
    ACCEPTABLE = "ACCEPTABLE"  # 50-69%: Meets minimum
    POOR = "POOR"  # <50%: Significant gaps


class ComparisonDimension(Enum):
    DIRECTORY_HIERARCHY = "directory_hierarchy"
    SECTION_COVERAGE = "section_coverage"
    HEADING_COVERAGE = "heading_coverage"
    PROSE_DENSITY = "prose_density"
    NAVIGATION_COMPLETENESS = "navigation_completeness"
    AGGREGATION_QUALITY = "aggregation_quality"

    def get_delta_type(self) -> DeltaType:
        """Determine if this dimension measures structural or quality deltas."""
        structural_dims = {
            ComparisonDimension.DIRECTORY_HIERARCHY,
            ComparisonDimension.SECTION_COVERAGE,
            ComparisonDimension.NAVIGATION_COMPLETENESS,
        }
        return DeltaType.STRUCTURAL if self in structural_dims else DeltaType.QUALITY


# Qoder baseline expected structure
QODER_REQUIRED_SECTIONS = [
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

QODER_REQUIRED_OVERVIEW_HEADINGS = [
    "项目定位",
    "核心问题",
    "核心能力",
    "快速开始",
    "阅读导航",
    "系统分层",
    "服务协作",
    "核心链路",
    "存储与索引设计",
]

QODER_MIN_PROSE_CHARS = 500
QODER_MAX_LIST_RATIO = 0.6
QODER_MIN_SECTION_NAV_LINKS = 3

# Score calibration thresholds
SCORE_BAND_THRESHOLDS = {
    ScoreBand.EXCELLENT: 0.90,
    ScoreBand.GOOD: 0.70,
    ScoreBand.ACCEPTABLE: 0.50,
}


# Phase 14: Explicit dimension weights for calibrated scoring
# Weights are designed to:
# 1. Prioritize structural dimensions (must have) over quality dimensions (should have)
# 2. Prevent alias/overlay inflation where one dimension's score incorrectly dominates
# 3. Ensure deterministic, documented rubric choices

DIMENSION_WEIGHTS = {
    # Structural dimensions (weight: 0.20 each, total: 0.60)
    # These are hard requirements - missing them blocks acceptance
    ComparisonDimension.DIRECTORY_HIERARCHY: 0.20,
    ComparisonDimension.SECTION_COVERAGE: 0.20,
    ComparisonDimension.NAVIGATION_COMPLETENESS: 0.20,
    # Quality dimensions (weight: ~0.13 each, total: 0.40)
    # These are soft requirements - they affect score but don't block
    ComparisonDimension.HEADING_COVERAGE: 0.133,
    ComparisonDimension.PROSE_DENSITY: 0.133,
    ComparisonDimension.AGGREGATION_QUALITY: 0.134,
}

# Rubric documentation: How scores translate to gap counts
RUBRIC_SCORE_TO_GAPS = {
    1.0: 0,  # Perfect: no gaps
    0.9: 1,  # Excellent: 1 minor gap
    0.7: 3,  # Good: up to 3 minor gaps or 1 major
    0.5: 5,  # Acceptable: up to 5 gaps of any type
    0.0: 999,  # Poor: critical gaps
}


@dataclass
class BaselineComparatorConfig:
    """Configuration for QoderBaselineComparator with YAML support.

    Attributes:
        structural_weight: Total weight for structural dimensions (default 0.60)
        quality_weight: Total weight for quality dimensions (default 0.40)
        dimension_weights: Optional override for individual dimension weights
        structural_dims: Dimensions classified as structural
        quality_dims: Dimensions classified as quality
    """

    structural_weight: float = 0.60
    quality_weight: float = 0.40
    dimension_weights: dict[str, float] | None = None
    structural_dims: list[str] | None = None
    quality_dims: list[str] | None = None

    # Default dimension lists (as class variables to avoid dataclass issues)
    _DEFAULT_STRUCTURAL: typing.ClassVar[list[str]] = [
        "directory_hierarchy",
        "section_coverage",
        "navigation_completeness",
    ]
    _DEFAULT_QUALITY: typing.ClassVar[list[str]] = [
        "heading_coverage",
        "prose_density",
        "aggregation_quality",
    ]

    @classmethod
    def from_yaml(cls, config: dict[str, Any]) -> BaselineComparatorConfig:
        """Create BaselineComparatorConfig from YAML configuration.

        Args:
            config: Dictionary with optional keys:
                - structural_weight: Total weight for structural dimensions
                - quality_weight: Total weight for quality dimensions
                - dimension_weights: Dict mapping dimension names to weights
                - structural_dims: List of dimension names classified as structural
                - quality_dims: List of dimension names classified as quality

        Example YAML:
            compare:
              structural_weight: 0.60
              quality_weight: 0.40
              dimension_weights:
                directory_hierarchy: 0.20
                section_coverage: 0.20
                navigation_completeness: 0.20
                heading_coverage: 0.133
                prose_density: 0.133
                aggregation_quality: 0.134
        """
        return cls(
            structural_weight=config.get("structural_weight", 0.60),
            quality_weight=config.get("quality_weight", 0.40),
            dimension_weights=config.get("dimension_weights"),
            structural_dims=config.get("structural_dims"),
            quality_dims=config.get("quality_dims"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            "structural_weight": self.structural_weight,
            "quality_weight": self.quality_weight,
            "dimension_weights": self.dimension_weights,
            "structural_dims": self.structural_dims or BaselineComparatorConfig._DEFAULT_STRUCTURAL,
            "quality_dims": self.quality_dims or BaselineComparatorConfig._DEFAULT_QUALITY,
        }

    def get_structural_dims(self) -> list[str]:
        """Get list of structural dimension names."""
        return self.structural_dims or self._DEFAULT_STRUCTURAL

    def get_quality_dims(self) -> list[str]:
        """Get list of quality dimension names."""
        return self.quality_dims or self._DEFAULT_QUALITY


def get_default_dimension_weights() -> dict[ComparisonDimension, float]:
    """Get the default dimension weights."""
    return dict(DIMENSION_WEIGHTS)


@dataclass
class WeightedScore:
    """A weighted score with breakdown for transparency."""

    raw_score: float
    weighted_score: float
    weight: float
    dimension: str
    delta_type: DeltaType

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_score": round(self.raw_score, 3),
            "weighted_score": round(self.weighted_score, 3),
            "weight": self.weight,
            "dimension": self.dimension,
            "delta_type": self.delta_type.value,
        }


def get_score_band(score: float) -> ScoreBand:
    """Get the score band for a given score."""
    if score >= SCORE_BAND_THRESHOLDS[ScoreBand.EXCELLENT]:
        return ScoreBand.EXCELLENT
    elif score >= SCORE_BAND_THRESHOLDS[ScoreBand.GOOD]:
        return ScoreBand.GOOD
    elif score >= SCORE_BAND_THRESHOLDS[ScoreBand.ACCEPTABLE]:
        return ScoreBand.ACCEPTABLE
    else:
        return ScoreBand.POOR


@dataclass
class GapItem:
    dimension: str
    severity: str
    description: str
    target_path: str
    baseline_path: str | None = None
    recommendation: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "severity": self.severity,
            "description": self.description,
            "target_path": self.target_path,
            "baseline_path": self.baseline_path,
            "recommendation": self.recommendation,
            "details": self.details,
        }


@dataclass
class DimensionResult:
    dimension: str
    status: str  # PASS, FAIL, PARTIAL
    score: float  # 0.0 - 1.0
    gaps: list[GapItem] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    delta_type: DeltaType = DeltaType.QUALITY  # STRUCTURAL or QUALITY
    score_band: ScoreBand = ScoreBand.POOR  # EXCELLENT, GOOD, ACCEPTABLE, POOR

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "status": self.status,
            "score": round(self.score, 3),
            "delta_type": self.delta_type.value,
            "score_band": self.score_band.value,
            "gaps": [g.to_dict() for g in self.gaps],
            "metrics": self.metrics,
        }


@dataclass
class GapReport:
    target_root: Path
    baseline_root: Path
    dimensions: list[DimensionResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_root": str(self.target_root),
            "baseline_root": str(self.baseline_root),
            "dimensions": [d.to_dict() for d in self.dimensions],
            "summary": self.summary,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Qoder Baseline Gap Report",
            "",
            f"**Target:** `{self.target_root}`",
            f"**Baseline:** `{self.baseline_root}`",
            f"**Generated:** {self.summary.get('generated_at', 'N/A')}",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
        ]

        total_gaps = sum(len(d.gaps) for d in self.dimensions)
        critical = sum(
            1 for d in self.dimensions for g in d.gaps if g.severity == GapSeverity.CRITICAL.value
        )
        major = sum(
            1 for d in self.dimensions for g in d.gaps if g.severity == GapSeverity.MAJOR.value
        )

        overall_score = (
            sum(d.score for d in self.dimensions) / len(self.dimensions) if self.dimensions else 0
        )

        lines.append(
            f"- **Overall Score:** {overall_score:.1%} ({self.summary.get('overall_band', 'N/A')})"
        )
        lines.append(f"- **Structural Score:** {self.summary.get('structural_score', 0):.1%}")
        lines.append(f"- **Quality Score:** {self.summary.get('quality_score', 0):.1%}")
        lines.append(f"- **Total Gaps:** {total_gaps}")
        lines.append(f"- **Critical Issues:** {critical}")
        lines.append(f"- **Major Issues:** {major}")
        lines.append(
            f"- **Acceptance:** {'BLOCKED' if self.summary.get('acceptance_blocked') else 'READY'}"
        )
        lines.append("")

        lines.append("### Score Band Guide")
        lines.append("- **EXCELLENT (90-100%):** Exceeds baseline expectations")
        lines.append("- **GOOD (70-89%):** Meets baseline with minor gaps")
        lines.append("- **ACCEPTABLE (50-69%):** Meets minimum, needs improvement")
        lines.append("- **POOR (<50%):** Significant gaps, requires major work")
        lines.append("")

        # Phase 14: Add weighting scheme information
        if "weighting_scheme" in self.summary:
            lines.append("### Scoring Rubric (Phase 14)")
            lines.append(
                f"- **Weighting Scheme:** {self.summary.get('weighting_scheme', 'uniform')}"
            )
            lines.append("")
            lines.append("**Dimension Weights:**")
            for dim, weight in sorted(self.summary.get("dimension_weights", {}).items()):
                lines.append(f"- {dim}: {weight:.1%}")
            lines.append("")

        lines.append("---")
        lines.append("")

        for dim in self.dimensions:
            status_icon = {"PASS": "✓", "FAIL": "✗", "PARTIAL": "◐"}.get(dim.status, "?")
            delta_icon = {"STRUCTURAL": "🔴", "QUALITY": "🟡"}.get(dim.delta_type.value, "?")
            lines.append(
                f"### {status_icon} {delta_icon} {dim.dimension.replace('_', ' ').title()}"
            )
            lines.append(f"- Status: **{dim.status}**")
            lines.append(f"- Score: {dim.score:.1%} ({dim.score_band.value})")
            lines.append(f"- Delta Type: **{dim.delta_type.value}**")
            lines.append("")

            if dim.gaps:
                lines.append("**Gaps:**")
                for gap in dim.gaps:
                    lines.append(f"- [{gap.severity}] {gap.description}")
                    if gap.recommendation:
                        lines.append(f"  - Recommendation: {gap.recommendation}")
                lines.append("")

            if dim.metrics:
                lines.append("**Metrics:**")
                for key, value in dim.metrics.items():
                    lines.append(f"- {key}: {value}")
                lines.append("")

            lines.append("---\n")

        # Add detailed gap listing
        if total_gaps > 0:
            lines.append("## Detailed Gap Listing\n")
            for dim in self.dimensions:
                for gap in dim.gaps:
                    lines.append(f"### {gap.severity}: {gap.description}")
                    lines.append(f"- **Dimension:** {gap.dimension}")
                    lines.append(f"- **Target Path:** `{gap.target_path}`")
                    if gap.baseline_path:
                        lines.append(f"- **Baseline Path:** `{gap.baseline_path}`")
                    if gap.recommendation:
                        lines.append(f"- **Recommendation:** {gap.recommendation}")
                    if gap.details:
                        lines.append(
                            f"- **Details:** `{json.dumps(gap.details, ensure_ascii=False)}`"
                        )
                    lines.append("")

        return "\n".join(lines)


class QoderBaselineComparator:
    """Compares generated repo-wiki output against qoder-style baseline."""

    def __init__(
        self,
        target_root: Path,
        baseline_root: Path,
        config: BaselineComparatorConfig | None = None,
    ) -> None:
        self.target_root = target_root
        self.baseline_root = baseline_root
        self.config = config or BaselineComparatorConfig()
        # Build effective dimension weights from config
        self._effective_weights = self._build_dimension_weights()

    def _build_dimension_weights(self) -> dict[ComparisonDimension, float]:
        """Build effective dimension weights from config or defaults."""
        if self.config.dimension_weights:
            # Use config-provided weights
            result = {}
            for dim_name, weight in self.config.dimension_weights.items():
                try:
                    dim_enum = ComparisonDimension(dim_name)
                    result[dim_enum] = weight
                except ValueError:
                    pass
            return result

        # Fall back to default weights
        return get_default_dimension_weights()

    @classmethod
    def from_yaml_config(
        cls,
        target_root: Path,
        baseline_root: Path,
        config: dict[str, Any],
    ) -> QoderBaselineComparator:
        """Create comparator with YAML configuration.

        Args:
            target_root: Path to generated output
            baseline_root: Path to qoder baseline
            config: YAML configuration dict with optional keys:
                - structural_weight: Total weight for structural dimensions
                - quality_weight: Total weight for quality dimensions
                - dimension_weights: Dict mapping dimension names to weights
                - structural_dims: List of structural dimension names
                - quality_dims: List of quality dimension names
        """
        comparator_config = BaselineComparatorConfig.from_yaml(config)
        return cls(target_root, baseline_root, comparator_config)

    def compare_all(self) -> GapReport:
        """Run all comparison dimensions and produce a gap report."""
        report = GapReport(
            target_root=self.target_root,
            baseline_root=self.baseline_root,
            dimensions=[
                self._compare_directory_hierarchy(),
                self._compare_section_coverage(),
                self._compare_heading_coverage(),
                self._compare_prose_density(),
                self._compare_navigation_completeness(),
                self._compare_aggregation_quality(),
            ],
        )

        # Calculate summary with structural vs quality separation
        total_gaps = sum(len(d.gaps) for d in report.dimensions)
        critical = sum(
            1 for d in report.dimensions for g in d.gaps if g.severity == GapSeverity.CRITICAL.value
        )
        major = sum(
            1 for d in report.dimensions for g in d.gaps if g.severity == GapSeverity.MAJOR.value
        )

        # Phase 14: Use explicit weights for deterministic scoring
        # Prevent alias/overlay inflation by capping individual dimension influence
        weighted_scores = self._calculate_weighted_scores(report.dimensions)
        overall_score = sum(ws.weighted_score for ws in weighted_scores)

        # Separate structural and quality dimensions
        structural_dims = [d for d in report.dimensions if d.delta_type == DeltaType.STRUCTURAL]
        quality_dims = [d for d in report.dimensions if d.delta_type == DeltaType.QUALITY]

        # Weighted structural score
        structural_weighted = [
            ws for ws in weighted_scores if ws.delta_type == DeltaType.STRUCTURAL
        ]
        structural_score = sum(ws.weighted_score for ws in structural_weighted)

        # Weighted quality score
        quality_weighted = [ws for ws in weighted_scores if ws.delta_type == DeltaType.QUALITY]
        quality_score = sum(ws.weighted_score for ws in quality_weighted)

        # Determine overall score band
        overall_band = get_score_band(overall_score)

        # Acceptance is blocked if:
        # 1. Any CRITICAL gaps exist, OR
        # 2. Structural score is below ACCEPTABLE threshold
        acceptance_blocked = critical > 0 or any(d.status == "FAIL" for d in structural_dims)

        report.summary = {
            "generated_at": "2026-04-18",
            "total_gaps": total_gaps,
            "critical_gaps": critical,
            "major_gaps": major,
            "overall_score": round(overall_score, 3),
            "overall_band": overall_band.value,
            "structural_score": round(structural_score, 3),
            "quality_score": round(quality_score, 3),
            "dimension_count": len(report.dimensions),
            "structural_dimensions": len(structural_dims),
            "quality_dimensions": len(quality_dims),
            "passed_dimensions": sum(1 for d in report.dimensions if d.status == "PASS"),
            "failed_dimensions": sum(1 for d in report.dimensions if d.status == "FAIL"),
            "partial_dimensions": sum(1 for d in report.dimensions if d.status == "PARTIAL"),
            "acceptance_blocked": acceptance_blocked,
            # Phase 14: Weight information for transparency
            "weighting_scheme": "explicit",
            "dimension_weights": {ws.dimension: round(ws.weight, 3) for ws in weighted_scores},
            "weighted_breakdown": [ws.to_dict() for ws in weighted_scores],
        }

        return report

    def _calculate_weighted_scores(self, dimensions: list[DimensionResult]) -> list[WeightedScore]:
        """Calculate weighted scores using explicit dimension weights.

        This method prevents alias/overlay inflation by:
        1. Using explicit, documented weights instead of implicit averaging
        2. Capping any single dimension's raw score influence
        3. Separating structural and quality dimension contributions
        """
        weighted_scores = []
        for dim in dimensions:
            try:
                dim_enum = ComparisonDimension(dim.dimension)
                weight = self._effective_weights.get(dim_enum, 0.1)
            except ValueError:
                weight = 0.1  # Default weight if dimension not found

            # Prevent alias/overlay inflation: cap raw score influence at 1.0
            # This ensures no single dimension can dominate the overall score
            capped_raw = min(dim.score, 1.0)
            weighted_score = capped_raw * weight

            weighted_scores.append(
                WeightedScore(
                    raw_score=dim.score,
                    weighted_score=weighted_score,
                    weight=weight,
                    dimension=dim.dimension,
                    delta_type=dim.delta_type,
                )
            )

        return weighted_scores

    def _compare_directory_hierarchy(self) -> DimensionResult:
        """Compare docs/ directory structure (STRUCTURAL delta type)."""
        result = DimensionResult(
            dimension=ComparisonDimension.DIRECTORY_HIERARCHY.value,
            status="FAIL",
            score=0.0,
            delta_type=DeltaType.STRUCTURAL,
        )

        target_docs = self.target_root / "docs"
        baseline_docs = self.baseline_root / "docs"

        if not target_docs.exists():
            result.gaps.append(
                GapItem(
                    dimension=result.dimension,
                    severity=GapSeverity.CRITICAL.value,
                    description="docs/ directory does not exist",
                    target_path=str(target_docs),
                    recommendation="Generate docs/ directory with overview and section pages",
                )
            )
            result.score_band = get_score_band(result.score)
            return result

        # Compare key structure
        target_structure = self._get_docs_structure(target_docs)
        baseline_structure = self._get_docs_structure(baseline_docs)

        result.metrics["target_structure"] = target_structure
        result.metrics["baseline_structure"] = baseline_structure

        # Check for sections directory
        if not (target_docs / "sections").exists():
            result.gaps.append(
                GapItem(
                    dimension=result.dimension,
                    severity=GapSeverity.CRITICAL.value,
                    description="docs/sections/ directory missing",
                    target_path=str(target_docs / "sections"),
                    baseline_path=str(baseline_docs / "sections"),
                    recommendation="Create docs/sections/ with topic-based section pages",
                )
            )

        # Calculate score based on structure match
        target_keys = set(target_structure.keys())
        baseline_keys = set(baseline_structure.keys())

        if target_keys >= baseline_keys:
            result.status = "PASS"
            result.score = 1.0
        elif target_keys:
            # Partial match
            match_ratio = len(target_keys & baseline_keys) / len(baseline_keys)
            result.score = match_ratio
            result.status = "PARTIAL" if match_ratio > 0.5 else "FAIL"
        else:
            result.status = "FAIL"
            result.score = 0.0

        result.score_band = get_score_band(result.score)
        return result

    def _get_docs_structure(self, docs_path: Path) -> dict[str, Any]:
        """Get a summary of the docs/ directory structure."""
        if not docs_path.exists():
            return {}

        structure: dict[str, Any] = {
            "exists": True,
            "subdirs": [],
            "overview_files": [],
        }

        try:
            for item in docs_path.iterdir():
                if item.is_dir():
                    if item.name not in (".DS_Store",):
                        structure["subdirs"].append(item.name)
                elif item.is_file() and item.suffix == ".md":
                    structure["overview_files"].append(item.name)
        except PermissionError:
            pass

        return structure

    def _compare_section_coverage(self) -> DimensionResult:
        """Compare section page coverage (STRUCTURAL delta type)."""
        result = DimensionResult(
            dimension=ComparisonDimension.SECTION_COVERAGE.value,
            status="FAIL",
            score=0.0,
            delta_type=DeltaType.STRUCTURAL,
        )

        target_sections = self.target_root / "docs/sections"
        baseline_sections = self.baseline_root / "docs/sections"

        if not target_sections.exists():
            result.gaps.append(
                GapItem(
                    dimension=result.dimension,
                    severity=GapSeverity.CRITICAL.value,
                    description="docs/sections/ directory missing",
                    target_path=str(target_sections),
                    baseline_path=str(baseline_sections),
                    recommendation="Create docs/sections/ with required section pages",
                )
            )
            result.score_band = get_score_band(result.score)
            return result

        # Check each required section
        target_section_files = set()
        baseline_section_files = set()

        try:
            for section_dir in target_sections.iterdir():
                if section_dir.is_dir() and (section_dir / "index.md").exists():
                    target_section_files.add(section_dir.name)
        except PermissionError:
            pass

        try:
            for section_dir in baseline_sections.iterdir():
                if section_dir.is_dir() and (section_dir / "index.md").exists():
                    baseline_section_files.add(section_dir.name)
        except PermissionError:
            pass

        result.metrics["target_sections"] = sorted(target_section_files)
        result.metrics["baseline_sections"] = sorted(baseline_section_files)

        # Compare against required sections
        missing_sections = []
        for required in QODER_REQUIRED_SECTIONS:
            if required not in target_section_files:
                missing_sections.append(required)

        if missing_sections:
            result.gaps.append(
                GapItem(
                    dimension=result.dimension,
                    severity=GapSeverity.MAJOR.value,
                    description=f"Missing required sections: {', '.join(missing_sections)}",
                    target_path=str(target_sections),
                    recommendation=f"Create section pages for: {', '.join(missing_sections)}",
                    details={"missing_sections": missing_sections},
                )
            )

        # Calculate score
        if not baseline_section_files:
            baseline_count = len(QODER_REQUIRED_SECTIONS)
        else:
            baseline_count = len(baseline_section_files)

        target_count = len(target_section_files)
        if baseline_count > 0:
            coverage = len(target_section_files & baseline_section_files) / baseline_count
            result.score = min(coverage, 1.0)
        else:
            result.score = 0.0

        result.status = (
            "PASS" if result.score >= 1.0 else ("PARTIAL" if result.score >= 0.5 else "FAIL")
        )
        result.score_band = get_score_band(result.score)
        return result

    def _compare_heading_coverage(self) -> DimensionResult:
        """Compare heading patterns in overview documents (QUALITY delta type)."""
        result = DimensionResult(
            dimension=ComparisonDimension.HEADING_COVERAGE.value,
            status="FAIL",
            score=0.0,
            delta_type=DeltaType.QUALITY,
        )

        overview_files = ["00-overview.md", "01-architecture.md"]
        all_headings: dict[str, set[str]] = {}
        all_required = set(QODER_REQUIRED_OVERVIEW_HEADINGS)

        for filename in overview_files:
            target_path = self.target_root / "docs" / filename
            baseline_path = self.baseline_root / "docs" / filename

            target_headings = self._extract_headings(target_path)
            baseline_headings = self._extract_headings(baseline_path)

            all_headings[f"target_{filename}"] = target_headings

            # Check for required headings in target
            missing_headings = []
            for required in QODER_REQUIRED_OVERVIEW_HEADINGS:
                if required not in target_headings and required not in baseline_headings:
                    missing_headings.append(required)

            if missing_headings:
                result.gaps.append(
                    GapItem(
                        dimension=result.dimension,
                        severity=GapSeverity.MAJOR.value,
                        description=f"{filename} missing required headings",
                        target_path=str(target_path),
                        recommendation=f"Add headings: {', '.join(missing_headings[:3])}",
                        details={"missing_headings": missing_headings},
                    )
                )

        result.metrics["extracted_headings"] = {k: list(v) for k, v in all_headings.items()}

        # Calculate score based on heading match
        if all_required:
            found = sum(
                1
                for h in all_headings.values()
                for _ in h
                if any(r in str(_) for r in all_required)
            )
            result.score = min(found / len(all_required), 1.0)
        else:
            result.score = 0.5

        result.status = (
            "PASS" if result.score >= 0.8 else ("PARTIAL" if result.score >= 0.4 else "FAIL")
        )
        result.score_band = get_score_band(result.score)
        return result

    def _extract_headings(self, path: Path) -> set[str]:
        """Extract h2 headings from a markdown file."""
        if not path.exists():
            return set()

        headings: set[str] = set()
        try:
            content = path.read_text(encoding="utf-8")
            for line in content.split("\n"):
                stripped = line.strip()
                if stripped.startswith("## "):
                    heading_text = stripped[3:].strip()
                    headings.add(heading_text)
                    # Also add Chinese keywords
                    for keyword in [
                        "项目定位",
                        "核心问题",
                        "核心能力",
                        "快速开始",
                        "阅读导航",
                        "系统分层",
                        "服务协作",
                        "核心链路",
                        "存储",
                        "索引",
                    ]:
                        if keyword in heading_text:
                            headings.add(keyword)
        except (PermissionError, UnicodeDecodeError):
            pass

        return headings

    def _compare_prose_density(self) -> DimensionResult:
        """Compare prose vs list/table ratio (QUALITY delta type)."""
        result = DimensionResult(
            dimension=ComparisonDimension.PROSE_DENSITY.value,
            status="FAIL",
            score=0.0,
            delta_type=DeltaType.QUALITY,
        )

        overview_files = ["00-overview.md", "01-architecture.md"]
        total_prose_chars = 0
        total_list_items = 0
        total_table_rows = 0

        for filename in overview_files:
            path = self.target_root / "docs" / filename
            if path.exists():
                metrics = self._analyze_prose_density(path)
                total_prose_chars += metrics["prose_chars"]
                total_list_items += metrics["list_items"]
                total_table_rows += metrics["table_rows"]

        result.metrics["prose_chars"] = total_prose_chars
        result.metrics["list_items"] = total_list_items
        result.metrics["table_rows"] = total_table_rows

        # Check minimum prose
        if total_prose_chars < QODER_MIN_PROSE_CHARS:
            result.gaps.append(
                GapItem(
                    dimension=result.dimension,
                    severity=GapSeverity.MAJOR.value,
                    description=f"Overview docs have insufficient prose ({total_prose_chars} < {QODER_MIN_PROSE_CHARS} chars)",
                    target_path=str(self.target_root / "docs"),
                    recommendation="Add more narrative content explaining the project",
                    details={
                        "prose_chars": total_prose_chars,
                        "min_required": QODER_MIN_PROSE_CHARS,
                    },
                )
            )

        # Check list ratio
        list_ratio = 0.0
        total_content = total_prose_chars + total_list_items * 50 + total_table_rows * 50
        if total_content > 0:
            list_ratio = (total_list_items + total_table_rows) / (total_content / 50)
            result.metrics["list_ratio"] = round(list_ratio, 3)

            if list_ratio > QODER_MAX_LIST_RATIO:
                result.gaps.append(
                    GapItem(
                        dimension=result.dimension,
                        severity=GapSeverity.MAJOR.value,
                        description=f"Overview docs have too many lists/tables ({list_ratio:.1%} > {QODER_MAX_LIST_RATIO:.1%})",
                        target_path=str(self.target_root / "docs"),
                        recommendation="Replace some lists with prose explanations",
                        details={
                            "list_ratio": round(list_ratio, 3),
                            "max_allowed": QODER_MAX_LIST_RATIO,
                        },
                    )
                )

        # Calculate score
        prose_score = min(total_prose_chars / QODER_MIN_PROSE_CHARS, 1.0)
        ratio_score = (
            1.0 if list_ratio <= QODER_MAX_LIST_RATIO else QODER_MAX_LIST_RATIO / list_ratio
        )
        result.score = (prose_score + ratio_score) / 2
        result.status = (
            "PASS" if result.score >= 0.8 else ("PARTIAL" if result.score >= 0.4 else "FAIL")
        )
        result.score_band = get_score_band(result.score)
        return result

    def _analyze_prose_density(self, path: Path) -> dict[str, int]:
        """Analyze prose density of a markdown file."""
        if not path.exists():
            return {"prose_chars": 0, "list_items": 0, "table_rows": 0}

        try:
            content = path.read_text(encoding="utf-8")
        except (PermissionError, UnicodeDecodeError):
            return {"prose_chars": 0, "list_items": 0, "table_rows": 0}

        lines = content.split("\n")
        prose_chars = 0
        list_items = 0
        table_rows = 0
        in_code_block = False

        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            if stripped.startswith("-"):
                list_items += 1
                continue
            if stripped.startswith("|"):
                table_rows += 1
                continue
            if stripped.startswith("!"):
                continue

            # Count as prose
            prose_chars += len(stripped)

        return {"prose_chars": prose_chars, "list_items": list_items, "table_rows": table_rows}

    def _compare_navigation_completeness(self) -> DimensionResult:
        """Compare navigation links between docs (STRUCTURAL delta type)."""
        result = DimensionResult(
            dimension=ComparisonDimension.NAVIGATION_COMPLETENESS.value,
            status="FAIL",
            score=0.0,
            delta_type=DeltaType.STRUCTURAL,
        )

        sections_dir = self.target_root / "docs/sections"
        if not sections_dir.exists():
            result.gaps.append(
                GapItem(
                    dimension=result.dimension,
                    severity=GapSeverity.CRITICAL.value,
                    description="Cannot check navigation - docs/sections/ missing",
                    target_path=str(sections_dir),
                    recommendation="Create section pages with navigation links",
                )
            )
            result.score_band = get_score_band(result.score)
            return result

        # Check navigation links in section pages
        broken_links: list[str] = []
        sections_without_overview_link: list[str] = []
        low_nav_sections: list[tuple[str, int]] = []

        try:
            for section_dir in sections_dir.iterdir():
                if not section_dir.is_dir():
                    continue
                index_path = section_dir / "index.md"
                if not index_path.exists():
                    continue

                try:
                    content = index_path.read_text(encoding="utf-8")
                except (PermissionError, UnicodeDecodeError):
                    continue

                # Check for overview link
                if "../../00-overview.md" not in content and "../00-overview.md" not in content:
                    sections_without_overview_link.append(section_dir.name)

                # Count internal navigation links
                nav_links = content.count("../")
                if nav_links < QODER_MIN_SECTION_NAV_LINKS:
                    low_nav_sections.append((section_dir.name, nav_links))

        except PermissionError:
            pass

        result.metrics["sections_checked"] = len(sections_without_overview_link) + len(
            low_nav_sections
        )

        if sections_without_overview_link:
            result.gaps.append(
                GapItem(
                    dimension=result.dimension,
                    severity=GapSeverity.MAJOR.value,
                    description=f"{len(sections_without_overview_link)} sections missing overview link",
                    target_path=str(sections_dir),
                    recommendation="Add link to ../../00-overview.md in all section pages",
                    details={"sections": sections_without_overview_link},
                )
            )

        if low_nav_sections:
            result.gaps.append(
                GapItem(
                    dimension=result.dimension,
                    severity=GapSeverity.MINOR.value,
                    description=f"{len(low_nav_sections)} sections have insufficient nav links",
                    target_path=str(sections_dir),
                    recommendation=f"Add more cross-links (minimum {QODER_MIN_SECTION_NAV_LINKS} per section)",
                    details={"low_nav_sections": low_nav_sections},
                )
            )

        # Calculate score
        total_sections = len(sections_without_overview_link) + len(low_nav_sections)
        if total_sections == 0:
            result.score = 1.0
            result.status = "PASS"
        elif sections_without_overview_link:
            result.score = 0.3
            result.status = "FAIL"
        else:
            result.score = 0.6
            result.status = "PARTIAL"

        result.score_band = get_score_band(result.score)
        return result

    def _compare_aggregation_quality(self) -> DimensionResult:
        """Compare API and data model aggregation quality (QUALITY delta type)."""
        result = DimensionResult(
            dimension=ComparisonDimension.AGGREGATION_QUALITY.value,
            status="FAIL",
            score=0.0,
            delta_type=DeltaType.QUALITY,
        )

        # Check API contracts aggregation
        api_path = self.target_root / "docs/04-api-contracts.md"
        api_metrics = self._analyze_api_aggregation(api_path)
        result.metrics["api_aggregation"] = api_metrics

        if not api_path.exists():
            result.gaps.append(
                GapItem(
                    dimension=result.dimension,
                    severity=GapSeverity.CRITICAL.value,
                    description="04-api-contracts.md missing",
                    target_path=str(api_path),
                    recommendation="Generate API contracts document with proper grouping",
                )
            )
        elif api_metrics["raw_endpoint_count"] > 50:
            result.gaps.append(
                GapItem(
                    dimension=result.dimension,
                    severity=GapSeverity.MAJOR.value,
                    description=f"API contracts has {api_metrics['raw_endpoint_count']} raw endpoints (should be aggregated)",
                    target_path=str(api_path),
                    recommendation="Group endpoints by service/auth and provide summary instead of full list",
                    details={"raw_endpoints": api_metrics["raw_endpoint_count"]},
                )
            )
        elif not api_metrics["has_grouping"]:
            result.gaps.append(
                GapItem(
                    dimension=result.dimension,
                    severity=GapSeverity.MAJOR.value,
                    description="API contracts missing service/API grouping section",
                    target_path=str(api_path),
                    recommendation="Add grouping section that organizes APIs by service family or auth pattern",
                )
            )

        # Check data model aggregation
        dm_path = self.target_root / "docs/05-data-model.md"
        dm_metrics = self._analyze_data_model_aggregation(dm_path)
        result.metrics["data_model_aggregation"] = dm_metrics

        if not dm_path.exists():
            result.gaps.append(
                GapItem(
                    dimension=result.dimension,
                    severity=GapSeverity.CRITICAL.value,
                    description="05-data-model.md missing",
                    target_path=str(dm_path),
                    recommendation="Generate data model document with proper categorization",
                )
            )
        elif dm_metrics["raw_model_count"] > 30:
            result.gaps.append(
                GapItem(
                    dimension=result.dimension,
                    severity=GapSeverity.MAJOR.value,
                    description=f"Data model has {dm_metrics['raw_model_count']} raw models (should be aggregated)",
                    target_path=str(dm_path),
                    recommendation="Separate into core models, service models, and database/migration sections",
                    details={"raw_models": dm_metrics["raw_model_count"]},
                )
            )
        elif not dm_metrics["has_three_sections"]:
            result.gaps.append(
                GapItem(
                    dimension=result.dimension,
                    severity=GapSeverity.MAJOR.value,
                    description="Data model missing three-section structure",
                    target_path=str(dm_path),
                    recommendation="Organize into: Core Data Models, Service Data Models, Database & Migration",
                )
            )

        # Calculate score
        api_score = (
            1.0
            if (api_metrics["has_grouping"] and api_metrics["raw_endpoint_count"] <= 50)
            else 0.5
        )
        dm_score = (
            1.0
            if (dm_metrics["has_three_sections"] and dm_metrics["raw_model_count"] <= 30)
            else 0.5
        )
        result.score = (api_score + dm_score) / 2
        result.status = (
            "PASS" if result.score >= 0.8 else ("PARTIAL" if result.score >= 0.4 else "FAIL")
        )
        result.score_band = get_score_band(result.score)
        return result

    def _analyze_api_aggregation(self, path: Path) -> dict[str, Any]:
        """Analyze API contracts aggregation quality."""
        if not path.exists():
            return {"has_grouping": False, "raw_endpoint_count": 0, "has_conventions": False}

        try:
            content = path.read_text(encoding="utf-8")
        except (PermissionError, UnicodeDecodeError):
            return {"has_grouping": False, "raw_endpoint_count": 0, "has_conventions": False}

        # Check for grouping
        has_grouping = "服务/API 分组" in content or "分组" in content

        # Count raw endpoints
        lines = content.split("\n")
        endpoint_patterns = [
            "| GET |",
            "| POST |",
            "| PUT |",
            "| PATCH |",
            "| DELETE |",
        ]
        raw_count = sum(1 for line in lines if any(p in line for p in endpoint_patterns))

        # Check for conventions
        has_conventions = "调用约定" in content or "认证" in content

        return {
            "has_grouping": has_grouping,
            "raw_endpoint_count": raw_count,
            "has_conventions": has_conventions,
        }

    def _analyze_data_model_aggregation(self, path: Path) -> dict[str, Any]:
        """Analyze data model aggregation quality."""
        if not path.exists():
            return {"has_three_sections": False, "raw_model_count": 0}

        try:
            content = path.read_text(encoding="utf-8")
        except (PermissionError, UnicodeDecodeError):
            return {"has_three_sections": False, "raw_model_count": 0}

        # Check for three sections
        has_core = "核心数据模型" in content or "Core Data Models" in content
        has_service = "服务数据模型" in content or "Service Data Models" in content
        has_db = "数据库与迁移" in content or "Database" in content
        has_three_sections = has_core and has_service and has_db

        # Count raw models
        lines = content.split("\n")
        raw_count = sum(
            1 for line in lines if line.strip().startswith("| ") and "model" in line.lower()
        )

        return {
            "has_three_sections": has_three_sections,
            "raw_model_count": raw_count,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Qoder baseline comparison tool")
    parser.add_argument("--target", type=Path, required=True, help="Path to generated output")
    parser.add_argument("--baseline", type=Path, required=True, help="Path to qoder baseline")
    parser.add_argument("--output", type=Path, help="Output path for JSON report")
    parser.add_argument(
        "--format", choices=["json", "markdown", "both"], default="both", help="Output format"
    )
    parser.add_argument(
        "--config", type=Path, help="Path to YAML config file for comparator settings"
    )

    args = parser.parse_args()

    if not args.target.exists():
        print(f"Error: Target path does not exist: {args.target}", file=sys.stderr)
        return 1

    if not args.baseline.exists():
        print(f"Error: Baseline path does not exist: {args.baseline}", file=sys.stderr)
        return 1

    # Load config if provided
    config_dict = None
    if args.config and args.config.exists():
        import yaml

        config_dict = yaml.safe_load(args.config.read_text(encoding="utf-8"))

    # Run comparison with optional config
    if config_dict:
        comparator = QoderBaselineComparator.from_yaml_config(
            args.target, args.baseline, config_dict
        )
    else:
        comparator = QoderBaselineComparator(args.target, args.baseline)
    report = comparator.compare_all()

    # Output
    if args.format in ("json", "both"):
        json_output = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
        if args.output:
            args.output.write_text(json_output, encoding="utf-8")
            print(f"JSON report written to: {args.output}")
        else:
            print(json_output)

    if args.format in ("markdown", "both"):
        md_output = report.to_markdown()
        md_path = args.output.parent / f"{args.output.stem}.md" if args.output else None
        if md_path:
            md_path.write_text(md_output, encoding="utf-8")
            print(f"Markdown report written to: {md_path}")
        else:
            print(md_output)

    # Exit code based on acceptance decision
    # 0 = acceptance ready
    # 1 = acceptance blocked (critical gaps or structural failures)
    # 2 = significant quality gaps (score below acceptable threshold)
    if report.summary.get("acceptance_blocked"):
        return 1  # Acceptance blocked
    elif report.summary.get("overall_score", 0) < 0.5:
        return 2  # Significant gaps but not blocking
    return 0


if __name__ == "__main__":
    sys.exit(main())
