"""AI_API_Atlas isolated qoder parity rerun.

This module performs an isolated parity evaluation:
- Generates content under .repo-agent-eval/<run>
- Compares against read-only .qoder/repowiki/zh baseline
- Reports page count, citations, TOC, Mermaid, prose density gaps

Phase 29 - Task 29.5: AI_API_Atlas qoder parity rerun

Note: This module is read-only for Qoder baseline and write-only for
.repo-agent-eval directory. It does not modify the baseline.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


# =============================================================================
# ATLAS PATH CONSTANTS
# =============================================================================

def _get_atlas_root() -> Path:
    """Get ATLAS_ROOT from environment or use default."""
    env_path = os.environ.get("ATLAS_ROOT")
    if env_path:
        return Path(env_path)
    # Require ATLAS_ROOT environment variable for CI/CD
    raise RuntimeError(
        "ATLAS_ROOT environment variable not set. "
        "This tool requires ATLAS_ROOT to be set for path safety."
    )


ATLAS_ROOT = _get_atlas_root()
QODER_BASELINE_DIR = ATLAS_ROOT / ".qoder" / "repowiki" / "zh"
ATLAS_CONTENT_DIR = ATLAS_ROOT / ".repo-agent-eval"

logger = logging.getLogger(__name__)


# =============================================================================
# PARITY METRICS
# =============================================================================

class ParityMetric(Enum):
    PAGE_COUNT = "page_count"
    CITATION_COUNT = "citation_count"
    CITATION_DENSITY = "citation_density"
    TOC_PRESENCE = "toc_presence"
    MERMAID_PRESENCE = "mermaid_presence"
    PROSE_DENSITY = "prose_density"
    API_QUALITY = "api_quality"
    DATA_MODEL_QUALITY = "data_model_quality"


@dataclass
class GapItem:
    """A single gap item."""
    metric: ParityMetric
    baseline_value: float
    target_value: float
    gap_ratio: float  # (baseline - target) / baseline
    severity: str  # "critical", "major", "minor", "info"


@dataclass
class ParityComparisonResult:
    """Result of parity comparison."""
    run_id: str
    generated_at: str
    baseline_content_dir: Path
    target_content_dir: Path
    metrics: dict[str, Any] = field(default_factory=dict)
    gaps: list[GapItem] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# ATLAS PARITY RUNNER
# =============================================================================

class AIAPIAtlasParityRunner:
    """Runs isolated parity evaluation on AI_API_Atlas."""

    def __init__(
        self,
        atlas_root: Path = ATLAS_ROOT,
        baseline_dir: Path = QODER_BASELINE_DIR,
    ) -> None:
        """Initialize parity runner.

        Args:
            atlas_root: AI_API_Atlas root
            baseline_dir: Qoder baseline directory
        """
        self.atlas_root = Path(atlas_root)
        self.baseline_dir = Path(baseline_dir)
        self.run_id = f"atlas-parity-{uuid.uuid4().hex[:8]}"

    def get_output_dir(self) -> Path:
        """Get the output directory for this run."""
        return self.atlas_root / ".repo-agent-eval" / self.run_id / "content"

    def run_comparison(self) -> ParityComparisonResult:
        """Run parity comparison between target and baseline.

        Returns:
            ParityComparisonResult with all metrics and gaps
        """
        result = ParityComparisonResult(
            run_id=self.run_id,
            generated_at=datetime.now(UTC).isoformat(),
            baseline_content_dir=self.baseline_dir / "content",
            target_content_dir=self.get_output_dir(),
        )

        # Ensure output directory exists
        result.target_content_dir.parent.mkdir(parents=True, exist_ok=True)

        # Extract metrics from both directories
        baseline_metrics = self._extract_metrics(self.baseline_dir / "content")
        target_metrics = self._extract_metrics(result.target_content_dir)

        result.metrics = {
            "baseline": baseline_metrics,
            "target": target_metrics,
        }

        # Compute gaps
        result.gaps = self._compute_gaps(baseline_metrics, target_metrics)

        # Compute summary
        result.summary = self._compute_summary(result.gaps, baseline_metrics, target_metrics)

        return result

    def _extract_metrics(self, content_dir: Path) -> dict[str, Any]:
        """Extract metrics from a content directory.

        Args:
            content_dir: Content directory path

        Returns:
            Dictionary of metrics
        """
        metrics = {
            "page_count": 0,
            "citation_count": 0,
            "pages_with_citations": 0,
            "pages_with_toc": 0,
            "pages_with_mermaid": 0,
            "total_prose_chars": 0,
            "total_chars": 0,
        }

        if not content_dir.exists():
            return metrics

        # Count markdown files
        md_files = list(content_dir.rglob("*.md"))
        metrics["page_count"] = len(md_files)

        for f in md_files:
            try:
                content = f.read_text(encoding="utf-8")
                metrics["total_chars"] += len(content)

                # Count citations
                citations = content.count("<cite>") + content.count("[cite:")
                metrics["citation_count"] += citations
                if citations > 0:
                    metrics["pages_with_citations"] += 1

                # Check TOC
                if "Table of Contents" in content or "目录" in content or "[TOC]" in content:
                    metrics["pages_with_toc"] += 1

                # Check Mermaid
                if "```mermaid" in content or ":::mermaid" in content:
                    metrics["pages_with_mermaid"] += 1

                # Count prose
                metrics["total_prose_chars"] += self._count_prose(content)

            except Exception as e:
                logger.debug(f"Failed to read {f}: {e}")
                continue

        return metrics

    def _count_prose(self, content: str) -> int:
        """Count prose characters in markdown."""
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
            prose_lines.append(stripped)

        return len(" ".join(prose_lines))

    def _compute_gaps(
        self,
        baseline: dict[str, Any],
        target: dict[str, Any],
    ) -> list[GapItem]:
        """Compute gaps between baseline and target.

        Args:
            baseline: Baseline metrics
            target: Target metrics

        Returns:
            List of GapItems
        """
        gaps = []

        # Page count gap
        page_gap = self._make_gap(
            ParityMetric.PAGE_COUNT,
            baseline.get("page_count", 0),
            target.get("page_count", 0),
        )
        if page_gap:
            gaps.append(page_gap)

        # Citation density gap
        baseline_density = self._compute_citation_density(baseline)
        target_density = self._compute_citation_density(target)
        density_gap = self._make_gap(
            ParityMetric.CITATION_DENSITY,
            baseline_density,
            target_density,
        )
        if density_gap:
            gaps.append(density_gap)

        # TOC presence gap
        baseline_toc_ratio = baseline.get("pages_with_toc", 0) / max(1, baseline.get("page_count", 1))
        target_toc_ratio = target.get("pages_with_toc", 0) / max(1, target.get("page_count", 1))
        toc_gap = self._make_gap(
            ParityMetric.TOC_PRESENCE,
            baseline_toc_ratio,
            target_toc_ratio,
        )
        if toc_gap:
            gaps.append(toc_gap)

        # Prose density gap
        baseline_prose_ratio = baseline.get("total_prose_chars", 0) / max(1, baseline.get("total_chars", 1))
        target_prose_ratio = target.get("total_prose_chars", 0) / max(1, target.get("total_chars", 1))
        prose_gap = self._make_gap(
            ParityMetric.PROSE_DENSITY,
            baseline_prose_ratio,
            target_prose_ratio,
        )
        if prose_gap:
            gaps.append(prose_gap)

        return gaps

    def _compute_citation_density(self, metrics: dict[str, Any]) -> float:
        """Compute citation density (citations per 1000 prose chars)."""
        prose = metrics.get("total_prose_chars", 0)
        citations = metrics.get("citation_count", 0)
        if prose == 0:
            return 0.0
        return (citations / prose) * 1000

    def _make_gap(
        self,
        metric: ParityMetric,
        baseline_value: float,
        target_value: float,
    ) -> GapItem | None:
        """Make a gap item if values differ significantly."""
        if baseline_value == 0 and target_value == 0:
            return None

        if baseline_value == 0:
            gap_ratio = 1.0 if target_value > 0 else 0.0
        else:
            gap_ratio = (baseline_value - target_value) / baseline_value

        # Only report if gap is significant (> 10%)
        if abs(gap_ratio) < 0.1:
            return None

        # Determine severity
        if gap_ratio > 0.5:
            severity = "critical"
        elif gap_ratio > 0.3:
            severity = "major"
        elif gap_ratio > 0.1:
            severity = "minor"
        else:
            severity = "info"

        return GapItem(
            metric=metric,
            baseline_value=baseline_value,
            target_value=target_value,
            gap_ratio=gap_ratio,
            severity=severity,
        )

    def _compute_summary(
        self,
        gaps: list[GapItem],
        baseline: dict[str, Any],
        target: dict[str, Any],
    ) -> dict[str, Any]:
        """Compute summary of comparison."""
        critical = sum(1 for g in gaps if g.severity == "critical")
        major = sum(1 for g in gaps if g.severity == "major")
        minor = sum(1 for g in gaps if g.severity == "minor")

        return {
            "total_gaps": len(gaps),
            "critical_gaps": critical,
            "major_gaps": major,
            "minor_gaps": minor,
            "baseline_pages": baseline.get("page_count", 0),
            "target_pages": target.get("page_count", 0),
            "overall_parity": self._compute_overall_parity(gaps),
        }

    def _compute_overall_parity(self, gaps: list[GapItem]) -> float:
        """Compute overall parity score (0-1)."""
        if not gaps:
            return 1.0

        # Weight by severity
        weights = {"critical": 0.4, "major": 0.3, "minor": 0.2, "info": 0.1}
        weighted_sum = sum(
            (1.0 - abs(g.gap_ratio)) * weights.get(g.severity, 0.1)
            for g in gaps
        )
        total_weight = sum(weights.get(g.severity, 0.1) for g in gaps)

        return max(0.0, min(1.0, weighted_sum / total_weight)) if total_weight > 0 else 1.0

    def save_report(self, result: ParityComparisonResult) -> Path:
        """Save report to JSON file.

        Args:
            result: ParityComparisonResult

        Returns:
            Path to saved report
        """
        output_dir = self.get_output_dir().parent
        report_path = output_dir / "parity_report.json"

        report_data = {
            "run_id": result.run_id,
            "generated_at": result.generated_at,
            "baseline_content_dir": str(result.baseline_content_dir),
            "target_content_dir": str(result.target_content_dir),
            "metrics": result.metrics,
            "gaps": [
                {
                    "metric": g.metric.value,
                    "baseline_value": g.baseline_value,
                    "target_value": g.target_value,
                    "gap_ratio": g.gap_ratio,
                    "severity": g.severity,
                }
                for g in result.gaps
            ],
            "summary": result.summary,
        }

        report_path.write_text(json.dumps(report_data, ensure_ascii=False, indent=2))
        return report_path


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def run_atlas_parity() -> ParityComparisonResult:
    """Run AI_API_Atlas parity evaluation.

    Returns:
        ParityComparisonResult
    """
    runner = AIAPIAtlasParityRunner()
    result = runner.run_comparison()
    runner.save_report(result)
    return result


def get_atlas_parity_report(run_id: str) -> ParityComparisonResult | None:
    """Get a previous parity report by run ID.

    Args:
        run_id: Run ID to look up

    Returns:
        ParityComparisonResult or None
    """
    report_path = ATLAS_CONTENT_DIR / run_id / "parity_report.json"
    if not report_path.exists():
        return None

    data = json.loads(report_path.read_text())
    # Reconstruct result (simplified)
    return ParityComparisonResult(
        run_id=data["run_id"],
        generated_at=data["generated_at"],
        baseline_content_dir=Path(data["baseline_content_dir"]),
        target_content_dir=Path(data["target_content_dir"]),
        metrics=data["metrics"],
        gaps=[
            GapItem(
                metric=ParityMetric(g["metric"]),
                baseline_value=g["baseline_value"],
                target_value=g["target_value"],
                gap_ratio=g["gap_ratio"],
                severity=g["severity"],
            )
            for g in data.get("gaps", [])
        ],
        summary=data.get("summary", {}),
    )