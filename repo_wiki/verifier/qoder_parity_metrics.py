"""Qoder parity metric schema for structural and content quality measurement.

This module defines:
- Parity metrics for comparing **observable rendered wiki outputs** (markdown trees)
  against an expected structural/content baseline — **no proprietary tool internals**.
- Severity levels and thresholds for each metric
- Serialization for CI and governance dashboards

Phase 29 - Task 29.1: Qoder parity metric schema

Metrics covered (aligned with `QoderLikeVerifierService` checks where applicable):
- Page coverage (taxonomy / expected section presence)
- Structural depth (directory tree depth sanity)
- Citation coverage and citation density
- File reference integrity (relative markdown links)
- TOC presence
- Mermaid coverage (pages with diagrams)
- Prose density and prose vs list ratio
- API and data-model aggregation quality
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

# Public schema version for serialized metric registry (bump when definitions change).
PARITY_METRIC_SCHEMA_VERSION = "1.0.0"


# =============================================================================
# METRIC CATEGORIES AND ENUMS
# =============================================================================


class MetricCategory(Enum):
    """Categories of parity metrics."""

    STRUCTURAL = "structural"  # Hard requirements
    QUALITY = "quality"  # Soft requirements
    CONTENT = "content"  # Content-specific metrics


class MetricSeverity(Enum):
    """Severity levels for metric failures."""

    CRITICAL = "critical"  # Blocks acceptance
    MAJOR = "major"  # Should fix
    MINOR = "minor"  # Can defer
    INFO = "info"  # Informational


class MetricStatus(Enum):
    """Status of a metric check."""

    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    SKIPPED = "skipped"


class MetricUnit(str, Enum):
    """Unit of `MetricResult.measured_value` / primary statistic (vendor-neutral)."""

    FRACTION = "fraction"  # 0..1 portion (pages, groups, or pages meeting a predicate)
    NORMALIZED_SCORE = "normalized_score"  # 0..1 composite score (may combine signals)
    CITATIONS_PER_1K_PROSE_CHARS = "citations_per_1k_prose_chars"
    TREE_DEPTH_LEVELS = "tree_depth_levels"  # integer depth of deepest file under content root
    UNBOUNDED_RATIO = (
        "unbounded_ratio"  # ratio that may exceed 1.0 (e.g. prose lines per list item)
    )


ThresholdCompareTarget = Literal["score", "measured_value"]


# =============================================================================
# PARITY METRIC DEFINITIONS
# =============================================================================


@dataclass
class ParityMetricDefinition:
    """Definition of a single parity metric."""

    name: str
    category: MetricCategory
    severity: MetricSeverity
    description: str
    unit: MetricUnit
    threshold: float  # Minimum acceptable value (see threshold_compare)
    threshold_compare: (
        ThresholdCompareTarget  # Whether threshold applies to score or raw measured_value
    )
    weight: float  # Contribution to overall score
    measurable: bool = True  # Can be measured from outputs

    def to_schema_dict(self) -> dict[str, Any]:
        """Serialize definition for registry export (no runtime paths or vendor data)."""
        return {
            "name": self.name,
            "category": self.category.value,
            "severity": self.severity.value,
            "description": self.description,
            "unit": self.unit.value,
            "threshold": self.threshold,
            "threshold_compare": self.threshold_compare,
            "weight": self.weight,
            "measurable": self.measurable,
        }


# Default parity metrics
PARITY_METRICS: dict[str, ParityMetricDefinition] = {
    # Structural metrics (must have)
    "page_coverage": ParityMetricDefinition(
        name="page_coverage",
        category=MetricCategory.STRUCTURAL,
        severity=MetricSeverity.CRITICAL,
        description=(
            "Fraction of expected topical groups present (slug/path heuristics over markdown tree)"
        ),
        unit=MetricUnit.FRACTION,
        threshold=0.80,
        threshold_compare="measured_value",
        weight=0.15,
    ),
    "directory_depth": ParityMetricDefinition(
        name="directory_depth",
        category=MetricCategory.STRUCTURAL,
        severity=MetricSeverity.MAJOR,
        description=(
            "Directory depth sanity: normalized score from max tree depth; "
            "measured_value is deepest path depth in levels"
        ),
        unit=MetricUnit.TREE_DEPTH_LEVELS,
        threshold=0.70,
        threshold_compare="score",
        weight=0.10,
    ),
    "file_reference_integrity": ParityMetricDefinition(
        name="file_reference_integrity",
        category=MetricCategory.STRUCTURAL,
        severity=MetricSeverity.CRITICAL,
        description="Fraction of relative markdown links that resolve to existing paths",
        unit=MetricUnit.FRACTION,
        threshold=1.0,
        threshold_compare="measured_value",
        weight=0.15,
    ),
    # Content quality metrics
    "citation_coverage": ParityMetricDefinition(
        name="citation_coverage",
        category=MetricCategory.CONTENT,
        severity=MetricSeverity.MAJOR,
        description="Fraction of markdown pages containing at least one citation marker",
        unit=MetricUnit.FRACTION,
        threshold=0.70,
        threshold_compare="measured_value",
        weight=0.10,
    ),
    "citation_density": ParityMetricDefinition(
        name="citation_density",
        category=MetricCategory.CONTENT,
        severity=MetricSeverity.MAJOR,
        description="Citation tags per 1000 prose characters (repository-wide aggregate)",
        unit=MetricUnit.CITATIONS_PER_1K_PROSE_CHARS,
        threshold=0.5,
        threshold_compare="measured_value",
        weight=0.08,
    ),
    "toc_presence": ParityMetricDefinition(
        name="toc_presence",
        category=MetricCategory.CONTENT,
        severity=MetricSeverity.MAJOR,
        description="Fraction of pages with an explicit TOC heading or TOC marker",
        unit=MetricUnit.FRACTION,
        threshold=0.80,
        threshold_compare="measured_value",
        weight=0.08,
    ),
    "mermaid_presence": ParityMetricDefinition(
        name="mermaid_presence",
        category=MetricCategory.CONTENT,
        severity=MetricSeverity.MINOR,
        description="Fraction of pages containing a fenced Mermaid block",
        unit=MetricUnit.FRACTION,
        threshold=0.30,
        threshold_compare="measured_value",
        weight=0.05,
    ),
    # Prose and aggregation metrics
    "prose_density": ParityMetricDefinition(
        name="prose_density",
        category=MetricCategory.QUALITY,
        severity=MetricSeverity.MAJOR,
        description="Prose character count divided by raw file length (noise-resistant heuristic)",
        unit=MetricUnit.FRACTION,
        threshold=0.30,
        threshold_compare="measured_value",
        weight=0.10,
    ),
    "prose_list_ratio": ParityMetricDefinition(
        name="prose_list_ratio",
        category=MetricCategory.QUALITY,
        severity=MetricSeverity.MINOR,
        description="Non-list lines vs markdown list items (structure balanced against bullet dumps)",
        unit=MetricUnit.UNBOUNDED_RATIO,
        threshold=0.40,
        threshold_compare="measured_value",
        weight=0.05,
    ),
    "api_aggregation": ParityMetricDefinition(
        name="api_aggregation",
        category=MetricCategory.QUALITY,
        severity=MetricSeverity.MAJOR,
        description="Fraction of API-tagged pages that show multi-endpoint aggregation signals",
        unit=MetricUnit.FRACTION,
        threshold=0.60,
        threshold_compare="measured_value",
        weight=0.07,
    ),
    "data_model_aggregation": ParityMetricDefinition(
        name="data_model_aggregation",
        category=MetricCategory.QUALITY,
        severity=MetricSeverity.MAJOR,
        description="Fraction of data-model pages that combine schema/relationship/diagram signals",
        unit=MetricUnit.FRACTION,
        threshold=0.60,
        threshold_compare="measured_value",
        weight=0.07,
    ),
}


def export_metric_schema(
    *,
    schema_version: str = PARITY_METRIC_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Export the full metric registry as a JSON-serializable document.

    Suitable for CI artifacts and benchmarks; contains only field definitions and thresholds,
    not computed results or repository paths.
    """
    metrics_sorted = sorted(PARITY_METRICS.values(), key=lambda m: m.name)
    return {
        "schema_version": schema_version,
        "schema_kind": "qoder_parity_metrics",
        "metric_count": len(metrics_sorted),
        "severity_levels": [
            {
                "value": MetricSeverity.CRITICAL.value,
                "meaning": "Fails acceptance when metric status is fail",
            },
            {
                "value": MetricSeverity.MAJOR.value,
                "meaning": "Should fix; does not block via MetricResult.is_blocking",
            },
            {
                "value": MetricSeverity.MINOR.value,
                "meaning": "Deferrable; some metrics may map to PARTIAL instead of FAIL",
            },
            {"value": MetricSeverity.INFO.value, "meaning": "Informational only"},
        ],
        "categories": [c.value for c in MetricCategory],
        "units": [u.value for u in MetricUnit],
        "metrics": [m.to_schema_dict() for m in metrics_sorted],
    }


def metric_schema_to_json(
    *,
    schema_version: str = PARITY_METRIC_SCHEMA_VERSION,
    indent: int | None = 2,
) -> str:
    """Serialize metric schema to JSON text."""
    return json.dumps(
        export_metric_schema(schema_version=schema_version),
        ensure_ascii=False,
        indent=indent,
    )


# =============================================================================
# METRIC RESULT
# =============================================================================


@dataclass
class MetricResult:
    """Result of a single metric measurement."""

    metric_name: str
    status: MetricStatus
    score: float  # 0.0 - 1.0
    measured_value: float
    threshold: float
    severity: MetricSeverity
    category: MetricCategory
    details: dict[str, Any] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)  # Descriptions of failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "status": self.status.value,
            "score": round(self.score, 3),
            "measured_value": round(self.measured_value, 3),
            "threshold": round(self.threshold, 3),
            "severity": self.severity.value,
            "category": self.category.value,
            "gaps": self.gaps,
            "details": self.details,
        }

    @property
    def is_blocking(self) -> bool:
        """Check if this metric failure blocks acceptance."""
        return self.status == MetricStatus.FAIL and self.severity == MetricSeverity.CRITICAL


# =============================================================================
# PARITY REPORT
# =============================================================================


@dataclass
class ParityReport:
    """Complete parity assessment report."""

    target_root: Path
    baseline_root: Path | None
    run_id: str
    generated_at: str
    metrics: list[MetricResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    blocked: bool = False
    blocking_reasons: list[str] = field(default_factory=list)

    def add_metric(self, result: MetricResult) -> None:
        """Add a metric result."""
        self.metrics.append(result)
        if result.is_blocking:
            self.blocked = True
            self.blocking_reasons.append(f"{result.metric_name}: {', '.join(result.gaps)}")

    def compute_summary(self) -> dict[str, Any]:
        """Compute summary statistics."""
        if not self.metrics:
            return {"error": "No metrics computed"}

        total = len(self.metrics)
        passed = sum(1 for m in self.metrics if m.status == MetricStatus.PASS)
        failed = sum(1 for m in self.metrics if m.status == MetricStatus.FAIL)
        partial = sum(1 for m in self.metrics if m.status == MetricStatus.PARTIAL)

        # Calculate weighted scores
        structural_metrics = [m for m in self.metrics if m.category == MetricCategory.STRUCTURAL]
        quality_metrics = [m for m in self.metrics if m.category == MetricCategory.QUALITY]
        content_metrics = [m for m in self.metrics if m.category == MetricCategory.CONTENT]

        def weighted_avg(metrics: list[MetricResult]) -> float:
            if not metrics:
                return 0.0
            total_weight = sum(PARITY_METRICS[m.metric_name].weight for m in metrics)
            if total_weight == 0:
                return 0.0
            weighted_sum = sum(m.score * PARITY_METRICS[m.metric_name].weight for m in metrics)
            return weighted_sum / total_weight

        structural_score = weighted_avg(structural_metrics)
        quality_score = weighted_avg(quality_metrics)
        content_score = weighted_avg(content_metrics)
        overall_score = weighted_avg(self.metrics)

        self.summary = {
            "total_metrics": total,
            "passed": passed,
            "failed": failed,
            "partial": partial,
            "overall_score": round(overall_score, 3),
            "structural_score": round(structural_score, 3),
            "quality_score": round(quality_score, 3),
            "content_score": round(content_score, 3),
            "blocked": self.blocked,
            "blocking_reasons": self.blocking_reasons,
            "pass_rate": round(passed / total, 3) if total > 0 else 0,
        }

        return self.summary

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_root": str(self.target_root),
            "baseline_root": str(self.baseline_root) if self.baseline_root else None,
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "metrics": [m.to_dict() for m in self.metrics],
            "summary": self.summary,
            "blocked": self.blocked,
            "blocking_reasons": self.blocking_reasons,
        }

    def to_json(self, path: Path | None = None) -> str:
        """Serialize to JSON."""
        data = self.to_dict()
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        if path:
            path.write_text(json_str)
        return json_str


# =============================================================================
# PARITY METRIC EXTRACTOR
# =============================================================================


class ParityMetricExtractor:
    """Extracts parity metrics from generated content."""

    def __init__(self, root: Path) -> None:
        """Initialize extractor.

        Args:
            root: Root directory of generated content
        """
        self.root = Path(root)

    @staticmethod
    def _status_for_definition(
        definition: ParityMetricDefinition,
        score: float,
        measured_value: float,
        *,
        allow_partial_below_threshold: bool = False,
    ) -> MetricStatus:
        cmp_val = score if definition.threshold_compare == "score" else measured_value
        if cmp_val >= definition.threshold:
            return MetricStatus.PASS
        if allow_partial_below_threshold:
            return MetricStatus.PARTIAL
        return MetricStatus.FAIL

    def extract_all(self, baseline_root: Path | None = None) -> ParityReport:
        """Extract all parity metrics.

        Args:
            baseline_root: Optional baseline for comparison

        Returns:
            ParityReport with all metrics
        """
        report = ParityReport(
            target_root=self.root,
            baseline_root=baseline_root,
            run_id=self._generate_run_id(),
            generated_at=datetime.now(UTC).isoformat(),
        )

        # Page coverage
        report.add_metric(self._measure_page_coverage())

        # Directory depth
        report.add_metric(self._measure_directory_depth())

        # File reference integrity
        report.add_metric(self._measure_file_reference_integrity())

        # Citation coverage
        report.add_metric(self._measure_citation_coverage())

        # Citation density
        report.add_metric(self._measure_citation_density())

        # TOC presence
        report.add_metric(self._measure_toc_presence())

        # Mermaid presence
        report.add_metric(self._measure_mermaid_presence())

        # Prose density
        report.add_metric(self._measure_prose_density())

        # Prose/list ratio
        report.add_metric(self._measure_prose_list_ratio())

        # API aggregation
        report.add_metric(self._measure_api_aggregation())

        # Data model aggregation
        report.add_metric(self._measure_data_model_aggregation())

        report.compute_summary()
        return report

    def _generate_run_id(self) -> str:
        """Generate a run ID."""
        import uuid

        return f"parity-{uuid.uuid4().hex[:8]}"

    def _measure_page_coverage(self) -> MetricResult:
        """Measure page coverage."""
        expected_groups = {
            "overview": ["00-overview", "project-overview", "overview", "readme", "项目概述"],
            "architecture": [
                "01-architecture",
                "architecture-overview",
                "architecture",
                "架构设计",
                "整体架构",
            ],
            "services": ["02-services", "core-services-index", "services", "核心服务"],
            "module-map": ["03-module", "module-relationships", "modules", "模块关系", "模块组织"],
            "api": ["04-api", "api-overview", "api", "API参考"],
            "data-model": ["05-data-model", "data-models-overview", "data-models", "数据模型"],
            "operations": ["operations", "deployment-overview", "deployment", "部署运维"],
            "development": ["development", "development-guide", "开发指南"],
            "security": ["security", "security-overview", "安全合规"],
            "troubleshooting": ["troubleshooting", "troubleshooting-overview", "故障排除", "维护"],
        }

        content_dir = self._find_content_dir()
        if not content_dir:
            return self._fail_result("page_coverage", "No content directory found")

        actual_pages = set()
        for f in content_dir.rglob("*.md"):
            slug = self._slug_from_path(f)
            if slug:
                actual_pages.add(slug)
            actual_pages.update(part for part in f.relative_to(content_dir).parts if part)

        # Check coverage
        covered_groups = []
        missing = []
        for group, aliases in expected_groups.items():
            if any(any(alias in ap for ap in actual_pages) for alias in aliases):
                covered_groups.append(group)
            else:
                missing.append(group)
        score = len(covered_groups) / len(expected_groups) if expected_groups else 0

        gaps = []
        if missing:
            gaps.append(f"Missing pages: {', '.join(missing)}")

        defn = PARITY_METRICS["page_coverage"]
        return MetricResult(
            metric_name="page_coverage",
            status=self._status_for_definition(defn, score, score),
            score=score,
            measured_value=score,
            threshold=defn.threshold,
            severity=defn.severity,
            category=defn.category,
            details={
                "expected_groups": expected_groups,
                "covered_groups": covered_groups,
                "actual": list(actual_pages),
            },
            gaps=gaps,
        )

    def _measure_directory_depth(self) -> MetricResult:
        """Measure directory depth matches baseline."""
        content_dir = self._find_content_dir()
        if not content_dir:
            return self._fail_result("directory_depth", "No content directory found")

        # Measure max depth of content directory
        max_depth = 0
        for f in content_dir.rglob("*"):
            if f.is_file():
                depth = len(f.relative_to(content_dir).parts)
                max_depth = max(max_depth, depth)

        # Expected depth is 2-3 levels (category/subcategory/page)
        score = 1.0 if 2 <= max_depth <= 4 else max(0, 1.0 - abs(max_depth - 3) / 3)

        defn = PARITY_METRICS["directory_depth"]
        return MetricResult(
            metric_name="directory_depth",
            status=self._status_for_definition(defn, score, float(max_depth)),
            score=score,
            measured_value=float(max_depth),
            threshold=defn.threshold,
            severity=defn.severity,
            category=defn.category,
            details={"max_depth": max_depth, "expected_range": [2, 4]},
            gaps=[]
            if 2 <= max_depth <= 4
            else [f"Directory depth {max_depth} outside expected range [2, 4]"],
        )

    def _measure_file_reference_integrity(self) -> MetricResult:
        """Measure all file references point to existing files."""
        content_dir = self._find_content_dir()
        if not content_dir:
            return self._fail_result("file_reference_integrity", "No content directory found")

        broken_refs = []
        md_files = list(content_dir.rglob("*.md"))

        for md_file in md_files:
            try:
                content = md_file.read_text(encoding="utf-8")
                # Find markdown links [text](path)
                links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
                for _, path in links:
                    if path.startswith("#") or path.startswith("http"):
                        continue
                    # Resolve relative to md_file
                    ref_path = (md_file.parent / path).resolve()
                    if not ref_path.exists():
                        broken_refs.append(f"{md_file.name} -> {path}")
            except Exception:
                continue

        score = 1.0 if not broken_refs else max(0, 1.0 - len(broken_refs) / 10)

        defn = PARITY_METRICS["file_reference_integrity"]
        return MetricResult(
            metric_name="file_reference_integrity",
            status=self._status_for_definition(defn, score, score),
            score=score,
            measured_value=score,
            threshold=defn.threshold,
            severity=defn.severity,
            category=defn.category,
            details={"broken_refs": broken_refs, "total_refs": len(md_files)},
            gaps=[f"Broken references: {len(broken_refs)}"] if broken_refs else [],
        )

    def _measure_citation_coverage(self) -> MetricResult:
        """Measure percentage of pages with at least one citation."""
        content_dir = self._find_content_dir()
        if not content_dir:
            return self._fail_result("citation_coverage", "No content directory found")

        md_files = list(content_dir.rglob("*.md"))
        with_citations = 0

        for f in md_files:
            try:
                content = f.read_text(encoding="utf-8")
                if "<cite>" in content or "[cite:" in content:
                    with_citations += 1
            except Exception:
                continue

        score = with_citations / len(md_files) if md_files else 0

        defn = PARITY_METRICS["citation_coverage"]
        return MetricResult(
            metric_name="citation_coverage",
            status=self._status_for_definition(defn, score, score),
            score=score,
            measured_value=score,
            threshold=defn.threshold,
            severity=defn.severity,
            category=defn.category,
            details={"pages_with_citations": with_citations, "total_pages": len(md_files)},
            gaps=[]
            if score >= defn.threshold
            else [f"Only {with_citations}/{len(md_files)} pages have citations"],
        )

    def _measure_citation_density(self) -> MetricResult:
        """Measure citations per 1000 prose characters."""
        content_dir = self._find_content_dir()
        if not content_dir:
            return self._fail_result("citation_density", "No content directory found")

        total_citations = 0
        total_prose_chars = 0

        for f in content_dir.rglob("*.md"):
            try:
                content = f.read_text(encoding="utf-8")
                citations = len(re.findall(r"<cite>[^<]+</cite>", content))
                prose = self._count_prose_chars(content)
                total_citations += citations
                total_prose_chars += prose
            except Exception:
                continue

        density = (total_citations / total_prose_chars * 1000) if total_prose_chars > 0 else 0
        defn = PARITY_METRICS["citation_density"]
        score = min(1.0, density / defn.threshold) if density < defn.threshold else 1.0

        return MetricResult(
            metric_name="citation_density",
            status=self._status_for_definition(defn, score, density),
            score=score,
            measured_value=density,
            threshold=defn.threshold,
            severity=defn.severity,
            category=defn.category,
            details={"total_citations": total_citations, "prose_chars": total_prose_chars},
            gaps=[]
            if density >= defn.threshold
            else [f"Citation density {density:.2f} below threshold {defn.threshold}"],
        )

    def _measure_toc_presence(self) -> MetricResult:
        """Measure pages containing table of contents."""
        content_dir = self._find_content_dir()
        if not content_dir:
            return self._fail_result("toc_presence", "No content directory found")

        md_files = list(content_dir.rglob("*.md"))
        with_toc = 0

        for f in md_files:
            try:
                content = f.read_text(encoding="utf-8")
                # TOC detection: ## Table of Contents or ## 目录
                if re.search(r"^#{1,6}\s+(Table of Contents|目录|Contents)", content, re.MULTILINE) or "[TOC]" in content or "[toc]" in content:
                    with_toc += 1
            except Exception:
                continue

        score = with_toc / len(md_files) if md_files else 0

        defn = PARITY_METRICS["toc_presence"]
        return MetricResult(
            metric_name="toc_presence",
            status=self._status_for_definition(defn, score, score),
            score=score,
            measured_value=score,
            threshold=defn.threshold,
            severity=defn.severity,
            category=defn.category,
            details={"pages_with_toc": with_toc, "total_pages": len(md_files)},
            gaps=[]
            if score >= defn.threshold
            else [f"Only {with_toc}/{len(md_files)} pages have TOC"],
        )

    def _measure_mermaid_presence(self) -> MetricResult:
        """Measure pages containing Mermaid diagrams."""
        content_dir = self._find_content_dir()
        if not content_dir:
            return self._fail_result("mermaid_presence", "No content directory found")

        md_files = list(content_dir.rglob("*.md"))
        with_mermaid = 0

        for f in md_files:
            try:
                content = f.read_text(encoding="utf-8")
                if "```mermaid" in content or ":::mermaid" in content:
                    with_mermaid += 1
            except Exception:
                continue

        score = with_mermaid / len(md_files) if md_files else 0

        defn = PARITY_METRICS["mermaid_presence"]
        status = self._status_for_definition(
            defn,
            score,
            score,
            allow_partial_below_threshold=True,
        )
        return MetricResult(
            metric_name="mermaid_presence",
            status=status,
            score=score,
            measured_value=score,
            threshold=defn.threshold,
            severity=defn.severity,
            category=defn.category,
            details={"pages_with_mermaid": with_mermaid, "total_pages": len(md_files)},
            gaps=[]
            if score >= defn.threshold
            else [f"Only {with_mermaid}/{len(md_files)} pages have Mermaid"],
        )

    def _measure_prose_density(self) -> MetricResult:
        """Measure prose to total content ratio."""
        content_dir = self._find_content_dir()
        if not content_dir:
            return self._fail_result("prose_density", "No content directory found")

        total_prose = 0
        total_chars = 0

        for f in content_dir.rglob("*.md"):
            try:
                content = f.read_text(encoding="utf-8")
                prose = self._count_prose_chars(content)
                total_prose += prose
                total_chars += len(content)
            except Exception:
                continue

        ratio = total_prose / total_chars if total_chars > 0 else 0
        defn = PARITY_METRICS["prose_density"]
        score = ratio / defn.threshold if ratio < defn.threshold else 1.0

        return MetricResult(
            metric_name="prose_density",
            status=self._status_for_definition(defn, score, ratio),
            score=score,
            measured_value=ratio,
            threshold=defn.threshold,
            severity=defn.severity,
            category=defn.category,
            details={"prose_chars": total_prose, "total_chars": total_chars},
            gaps=[]
            if ratio >= defn.threshold
            else [f"Prose density {ratio:.1%} below {defn.threshold:.0%} threshold"],
        )

    def _measure_prose_list_ratio(self) -> MetricResult:
        """Measure ratio of prose paragraphs to list items."""
        content_dir = self._find_content_dir()
        if not content_dir:
            return self._fail_result("prose_list_ratio", "No content directory found")

        total_prose_paras = 0
        total_list_items = 0

        for f in content_dir.rglob("*.md"):
            try:
                content = f.read_text(encoding="utf-8")
                # Count prose paragraphs (non-empty lines that aren't lists)
                lines = content.split("\n")
                prose_paras = sum(
                    1 for l in lines if l.strip() and not l.strip().startswith(("-", "*", "|"))
                )
                # Count list items
                list_items = len(re.findall(r"^[\s]*[-*]\s+", content, re.MULTILINE))
                total_prose_paras += prose_paras
                total_list_items += list_items
            except Exception:
                continue

        ratio = total_prose_paras / total_list_items if total_list_items > 0 else float("inf")
        defn = PARITY_METRICS["prose_list_ratio"]
        effective_ratio = ratio if ratio != float("inf") else 1.0
        score = (
            min(1.0, effective_ratio / defn.threshold) if effective_ratio < defn.threshold else 1.0
        )

        return MetricResult(
            metric_name="prose_list_ratio",
            status=self._status_for_definition(defn, score, effective_ratio),
            score=score,
            measured_value=effective_ratio,
            threshold=defn.threshold,
            severity=defn.severity,
            category=defn.category,
            details={
                "prose_paras": total_prose_paras,
                "list_items": total_list_items,
                "no_list_items": total_list_items == 0,
            },
            gaps=[]
            if (ratio == float("inf") or ratio >= defn.threshold)
            else [f"Prose/list ratio {ratio:.2f} below {defn.threshold} threshold"],
        )

    def _measure_api_aggregation(self) -> MetricResult:
        """Measure API aggregation quality."""
        content_dir = self._find_content_dir()
        if not content_dir:
            return self._fail_result("api_aggregation", "No content directory found")

        # Look for API documentation pages
        api_files = []
        for f in content_dir.rglob("*.md"):
            if "api" in f.stem.lower() or "API" in f.name:
                api_files.append(f)

        if not api_files:
            return self._fail_result("api_aggregation", "No API pages found")

        aggregated_count = 0
        for f in api_files:
            try:
                content = f.read_text(encoding="utf-8")
                # Check for aggregated content (multiple endpoints, schemas, etc.)
                has_endpoints = (
                    len(re.findall(r"(GET|POST|PUT|DELETE|PATCH)\s+", content, re.IGNORECASE)) >= 3
                )
                has_schemas = "schema" in content.lower() or "```json" in content.lower()
                if has_endpoints and has_schemas:
                    aggregated_count += 1
            except Exception:
                continue

        score = aggregated_count / len(api_files) if api_files else 0

        defn = PARITY_METRICS["api_aggregation"]
        return MetricResult(
            metric_name="api_aggregation",
            status=self._status_for_definition(defn, score, score),
            score=score,
            measured_value=score,
            threshold=defn.threshold,
            severity=defn.severity,
            category=defn.category,
            details={"aggregated_apis": aggregated_count, "total_api_pages": len(api_files)},
            gaps=[]
            if score >= defn.threshold
            else [f"Only {aggregated_count}/{len(api_files)} API pages are aggregated"],
        )

    def _measure_data_model_aggregation(self) -> MetricResult:
        """Measure data model aggregation quality."""
        content_dir = self._find_content_dir()
        if not content_dir:
            return self._fail_result("data_model_aggregation", "No data model pages found")

        # Look for data model pages
        dm_files = []
        for f in content_dir.rglob("*.md"):
            relative_text = f.relative_to(content_dir).as_posix()
            lower_text = relative_text.lower()
            if (
                "data" in lower_text
                or "model" in lower_text
                or "schema" in lower_text
                or "数据模型" in relative_text
                or "数据库" in relative_text
                or "迁移" in relative_text
            ):
                dm_files.append(f)

        if not dm_files:
            return self._fail_result("data_model_aggregation", "No data model pages found")

        aggregated_count = 0
        for f in dm_files:
            try:
                content = f.read_text(encoding="utf-8")
                # Check for relational content (links between models, ERDs, etc.)
                lower_content = content.lower()
                has_relationships = (
                    "relationship" in lower_content
                    or "erd" in lower_content
                    or "entity" in lower_content
                    or "关系" in content
                    or "实体" in content
                )
                has_diagrams = "```mermaid" in content or "erDiagram" in content
                has_schema = (
                    "```sql" in content
                    or "schema" in lower_content
                    or "数据库" in content
                    or "表" in content
                    or "字段" in content
                    or "迁移" in content
                )
                if sum([has_relationships, has_diagrams, has_schema]) >= 2:
                    aggregated_count += 1
            except Exception:
                continue

        score = aggregated_count / len(dm_files) if dm_files else 0

        defn = PARITY_METRICS["data_model_aggregation"]
        return MetricResult(
            metric_name="data_model_aggregation",
            status=self._status_for_definition(defn, score, score),
            score=score,
            measured_value=score,
            threshold=defn.threshold,
            severity=defn.severity,
            category=defn.category,
            details={"aggregated_dm": aggregated_count, "total_dm_pages": len(dm_files)},
            gaps=[]
            if score >= defn.threshold
            else [f"Only {aggregated_count}/{len(dm_files)} data model pages are aggregated"],
        )

    def _find_content_dir(self) -> Path | None:
        """Find the content directory in the root."""
        if self.root.exists() and self.root.is_dir() and self.root.name == "content":
            return self.root
        # Check common locations
        candidates = [
            self.root / "content",
            self.root / ".repo-agent-eval" / "content",
        ]
        for c in candidates:
            if c.exists():
                return c
        # Fallback: first directory with .md files
        for f in self.root.rglob("*.md"):
            return f.parent
        return None

    def _slug_from_path(self, path: Path) -> str | None:
        """Extract slug from a markdown file path."""
        name = path.stem
        # Remove common prefixes
        for prefix in ["00-", "01-", "02-", "03-", "04-", "05-"]:
            if name.startswith(prefix):
                return name[len(prefix) :]
        return name

    def _count_prose_chars(self, content: str) -> int:
        """Count prose characters in markdown content."""
        lines = content.split("\n")
        prose_lines = []
        in_code_block = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            if stripped.startswith("#"):
                continue
            if stripped.startswith("-") or stripped.startswith("*"):
                continue
            if stripped.startswith("|"):
                continue
            if stripped.startswith("!"):
                continue
            prose_lines.append(stripped)

        return len(" ".join(prose_lines))

    def _fail_result(self, metric_name: str, message: str) -> MetricResult:
        """Create a failure metric result."""
        return MetricResult(
            metric_name=metric_name,
            status=MetricStatus.FAIL,
            score=0.0,
            measured_value=0.0,
            threshold=PARITY_METRICS[metric_name].threshold,
            severity=PARITY_METRICS[metric_name].severity,
            category=PARITY_METRICS[metric_name].category,
            gaps=[message],
        )


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_parity_report(
    target_root: Path,
    baseline_root: Path | None = None,
) -> ParityReport:
    """Create a parity report for target content.

    Args:
        target_root: Root of content to check
        baseline_root: Optional baseline for comparison

    Returns:
        ParityReport with all metrics
    """
    extractor = ParityMetricExtractor(target_root)
    return extractor.extract_all(baseline_root)


def load_parity_report(path: Path) -> ParityReport:
    """Load a parity report from JSON file.

    Args:
        path: Path to JSON file

    Returns:
        ParityReport instance
    """
    data = json.loads(path.read_text())
    report = ParityReport(
        target_root=Path(data["target_root"]),
        baseline_root=Path(data["baseline_root"]) if data.get("baseline_root") else None,
        run_id=data["run_id"],
        generated_at=data["generated_at"],
        blocked=data.get("blocked", False),
        blocking_reasons=data.get("blocking_reasons", []),
    )
    for m in data.get("metrics", []):
        report.add_metric(
            MetricResult(
                metric_name=m["metric_name"],
                status=MetricStatus(m["status"]),
                score=m["score"],
                measured_value=m["measured_value"],
                threshold=m["threshold"],
                severity=MetricSeverity(m["severity"]),
                category=MetricCategory(m["category"]),
                gaps=m.get("gaps", []),
                details=m.get("details", {}),
            )
        )
    report.summary = data.get("summary", {})
    return report
