#!/usr/bin/env python3
"""
Qoder Benchmark Matrix Tool (Phase 14)

Runs compare on multiple repositories and builds threshold profiles for
different repository types (language, size, complexity).

Key Features:
- Batch comparison across multiple repositories
- Repository type classification
- Threshold profile generation
- Score drift detection and normalization

Usage:
    python scripts/qoder_benchmark_matrix.py \
        --repos /path/to/repo1 /path/to/repo2 \
        --baseline /path/to/qoder/baseline \
        --output /path/to/benchmark_matrix.json

    python scripts/qoder_benchmark_matrix.py \
        --from-csv repos.csv \
        --baseline /path/to/qoder/baseline \
        --output /path/to/benchmark_matrix.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class RepositorySize(Enum):
    SMALL = "small"  # < 10 files
    MEDIUM = "medium"  # 10-100 files
    LARGE = "large"  # 100-1000 files
    XLARGE = "xlarge"  # > 1000 files


class RepositoryComplexity(Enum):
    LOW = "low"  # Simple structure
    MEDIUM = "medium"  # Moderate nesting
    HIGH = "high"  # Deep nesting, multiple services


class Language(Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    UNKNOWN = "unknown"


# Threshold profiles for different repository types
THRESHOLD_PROFILES = {
    # Python repositories
    ("python", RepositorySize.SMALL, RepositoryComplexity.LOW): {
        "overall": 0.50,
        "structural": 0.40,
        "quality": 0.50,
        "description": "Python small/simple projects have relaxed thresholds",
    },
    ("python", RepositorySize.MEDIUM, RepositoryComplexity.MEDIUM): {
        "overall": 0.60,
        "structural": 0.55,
        "quality": 0.60,
        "description": "Python medium projects require balanced coverage",
    },
    ("python", RepositorySize.LARGE, RepositoryComplexity.HIGH): {
        "overall": 0.70,
        "structural": 0.65,
        "quality": 0.70,
        "description": "Python large/complex projects need strong structure",
    },
    # JavaScript/TypeScript repositories
    ("javascript", RepositorySize.SMALL, RepositoryComplexity.LOW): {
        "overall": 0.45,
        "structural": 0.35,
        "quality": 0.50,
        "description": "JS/TS small projects",
    },
    ("javascript", RepositorySize.MEDIUM, RepositoryComplexity.MEDIUM): {
        "overall": 0.55,
        "structural": 0.50,
        "quality": 0.55,
        "description": "JS/TS medium projects",
    },
    ("javascript", RepositorySize.LARGE, RepositoryComplexity.HIGH): {
        "overall": 0.65,
        "structural": 0.60,
        "quality": 0.65,
        "description": "JS/TS large projects",
    },
    # Java repositories
    ("java", RepositorySize.MEDIUM, RepositoryComplexity.MEDIUM): {
        "overall": 0.65,
        "structural": 0.60,
        "quality": 0.65,
        "description": "Java medium projects",
    },
    ("java", RepositorySize.LARGE, RepositoryComplexity.HIGH): {
        "overall": 0.75,
        "structural": 0.70,
        "quality": 0.75,
        "description": "Java large/complex projects require high standards",
    },
    # Go repositories
    ("go", RepositorySize.MEDIUM, RepositoryComplexity.MEDIUM): {
        "overall": 0.60,
        "structural": 0.55,
        "quality": 0.60,
        "description": "Go medium projects",
    },
    ("go", RepositorySize.LARGE, RepositoryComplexity.HIGH): {
        "overall": 0.70,
        "structural": 0.65,
        "quality": 0.70,
        "description": "Go large/complex projects",
    },
    # Unknown/default
    ("unknown", RepositorySize.MEDIUM, RepositoryComplexity.MEDIUM): {
        "overall": 0.50,
        "structural": 0.45,
        "quality": 0.50,
        "description": "Default thresholds for unknown types",
    },
}

# Default threshold for profiles not explicitly defined
DEFAULT_THRESHOLDS = {
    "overall": 0.50,
    "structural": 0.45,
    "quality": 0.50,
    "description": "Default thresholds (fallback)",
}


@dataclass
class RepositoryMetadata:
    """Metadata about a repository being benchmarked."""

    path: Path
    name: str
    language: Language
    size: RepositorySize
    complexity: RepositoryComplexity
    file_count: int = 0
    section_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "name": self.name,
            "language": self.language.value,
            "size": self.size.value,
            "complexity": self.complexity.value,
            "file_count": self.file_count,
            "section_count": self.section_count,
        }


@dataclass
class BenchmarkResult:
    """Result of benchmarking a single repository."""

    repository: RepositoryMetadata
    overall_score: float
    structural_score: float
    quality_score: float
    dimension_scores: dict[str, float]
    gaps: list[dict[str, Any]]
    acceptance_blocked: bool
    thresholds: dict[str, float]
    passed_thresholds: bool
    drift_from_baseline: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "repository": self.repository.to_dict(),
            "overall_score": round(self.overall_score, 3),
            "structural_score": round(self.structural_score, 3),
            "quality_score": round(self.quality_score, 3),
            "dimension_scores": {k: round(v, 3) for k, v in self.dimension_scores.items()},
            "gaps": self.gaps,
            "acceptance_blocked": self.acceptance_blocked,
            "thresholds": self.thresholds,
            "passed_thresholds": self.passed_thresholds,
            "drift_from_baseline": round(self.drift_from_baseline, 3),
        }


@dataclass
class ThresholdProfile:
    """A threshold profile for a repository type."""

    language: str
    size: RepositorySize
    complexity: RepositoryComplexity
    overall_threshold: float
    structural_threshold: float
    quality_threshold: float
    description: str
    sample_count: int = 0
    calibration_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "size": self.size.value,
            "complexity": self.complexity.value,
            "overall_threshold": self.overall_threshold,
            "structural_threshold": self.structural_threshold,
            "quality_threshold": self.quality_threshold,
            "description": self.description,
            "sample_count": self.sample_count,
            "calibration_data": self.calibration_data,
        }


@dataclass
class ScoreDriftAnalysis:
    """Analysis of score drift patterns."""

    pattern_type: str  # "improving", "declining", "stable", "volatile"
    drift_magnitude: float
    affected_dimensions: list[str]
    normalization_suggested: bool
    normalization_factor: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_type": self.pattern_type,
            "drift_magnitude": round(self.drift_magnitude, 3),
            "affected_dimensions": self.affected_dimensions,
            "normalization_suggested": self.normalization_suggested,
            "normalization_factor": round(self.normalization_factor, 3),
        }


class RepositoryClassifier:
    """Classifies repositories by type, size, and complexity."""

    @staticmethod
    def classify_by_language(repo_path: Path) -> Language:
        """Infer repository language from file structure."""
        # Check for common language markers
        if (repo_path / "package.json").exists():
            content = (repo_path / "package.json").read_text(encoding="utf-8")
            if "typescript" in content.lower():
                return Language.TYPESCRIPT
            return Language.JAVASCRIPT
        if (repo_path / "requirements.txt").exists() or (repo_path / "pyproject.toml").exists():
            return Language.PYTHON
        if (repo_path / "pom.xml").exists() or (repo_path / "build.gradle").exists():
            return Language.JAVA
        if (repo_path / "go.mod").exists():
            return Language.GO
        if (repo_path / "Cargo.toml").exists():
            return Language.RUST
        return Language.UNKNOWN

    @staticmethod
    def classify_by_size(repo_path: Path) -> RepositorySize:
        """Classify repository by file count."""
        try:
            md_files = list(repo_path.rglob("*.md"))
            file_count = len(md_files)
            if file_count < 10:
                return RepositorySize.SMALL
            elif file_count < 100:
                return RepositorySize.MEDIUM
            elif file_count < 1000:
                return RepositorySize.LARGE
            else:
                return RepositorySize.XLARGE
        except (PermissionError, OSError):
            return RepositorySize.MEDIUM

    @staticmethod
    def classify_by_complexity(repo_path: Path) -> RepositoryComplexity:
        """Classify repository by structural complexity."""
        try:
            max_depth = 0
            for path in repo_path.rglob("*"):
                if path.is_dir():
                    try:
                        depth = len(path.relative_to(repo_path).parts)
                        max_depth = max(max_depth, depth)
                    except ValueError:
                        pass

            section_dirs = repo_path / "docs" / "sections"
            section_count = 0
            if section_dirs.exists():
                section_count = len(list(section_dirs.iterdir()))

            # Complexity based on depth and sections
            if max_depth <= 2 and section_count < 5:
                return RepositoryComplexity.LOW
            elif max_depth <= 4 and section_count < 9:
                return RepositoryComplexity.MEDIUM
            else:
                return RepositoryComplexity.HIGH
        except (PermissionError, OSError):
            return RepositoryComplexity.MEDIUM

    @classmethod
    def classify(cls, repo_path: Path, name: str = "") -> RepositoryMetadata:
        """Classify a repository by all dimensions."""
        return RepositoryMetadata(
            path=repo_path,
            name=name or repo_path.name,
            language=cls.classify_by_language(repo_path),
            size=cls.classify_by_size(repo_path),
            complexity=cls.classify_by_complexity(repo_path),
        )


class ThresholdProfileGenerator:
    """Generates and manages threshold profiles."""

    @staticmethod
    def get_profile(
        language: Language, size: RepositorySize, complexity: RepositoryComplexity
    ) -> ThresholdProfile:
        """Get threshold profile for a repository type."""
        key = (language.value, size, complexity)
        thresholds = THRESHOLD_PROFILES.get(key, DEFAULT_THRESHOLDS)

        return ThresholdProfile(
            language=language.value,
            size=size,
            complexity=complexity,
            overall_threshold=thresholds["overall"],
            structural_threshold=thresholds["structural"],
            quality_threshold=thresholds["quality"],
            description=thresholds["description"],
        )

    @staticmethod
    def suggest_normalization(results: list[BenchmarkResult]) -> float:
        """Suggest normalization factor based on score drift patterns."""
        if len(results) < 2:
            return 1.0

        scores = [r.overall_score for r in results]
        variance = sum((s - sum(scores) / len(scores)) ** 2 for s in scores) / len(scores)
        std_dev = variance**0.5

        # If variance is high, suggest normalization
        if std_dev > 0.15:
            # Find the median score
            sorted_scores = sorted(scores)
            median = sorted_scores[len(sorted_scores) // 2]

            # Normalization factor to bring median to 0.65
            if median > 0:
                return min(0.65 / median, 1.5)
            return 1.0

        return 1.0


class ScoreDriftDetector:
    """Detects score drift patterns across benchmark runs."""

    @staticmethod
    def analyze(results: list[BenchmarkResult]) -> ScoreDriftAnalysis:
        """Analyze score drift patterns."""
        if len(results) < 2:
            return ScoreDriftAnalysis(
                pattern_type="stable",
                drift_magnitude=0.0,
                affected_dimensions=[],
                normalization_suggested=False,
            )

        # Calculate overall score trend
        overall_scores = [r.overall_score for r in results]
        first_half_avg = sum(overall_scores[: len(overall_scores) // 2]) / (
            len(overall_scores) // 2
        )
        second_half_avg = sum(overall_scores[len(overall_scores) // 2 :]) / (
            len(overall_scores) - len(overall_scores) // 2
        )

        drift = second_half_avg - first_half_avg

        # Identify affected dimensions
        affected = []
        for dim in ["structural_score", "quality_score"]:
            dim_values = [getattr(r, dim) for r in results]
            dim_first = sum(dim_values[: len(dim_values) // 2]) / (len(dim_values) // 2)
            dim_second = sum(dim_values[len(dim_values) // 2 :]) / (
                len(dim_values) - len(dim_values) // 2
            )
            if abs(dim_second - dim_first) > 0.1:
                affected.append(dim)

        # Classify pattern
        if abs(drift) < 0.05:
            pattern = "stable"
        elif drift > 0.1:
            pattern = "improving"
        elif drift < -0.1:
            pattern = "declining"
        else:
            pattern = "volatile"

        # Determine if normalization suggested
        variance = sum(
            (s - sum(overall_scores) / len(overall_scores)) ** 2 for s in overall_scores
        ) / len(overall_scores)
        normalization_suggested = variance**0.5 > 0.15

        return ScoreDriftAnalysis(
            pattern_type=pattern,
            drift_magnitude=drift,
            affected_dimensions=affected,
            normalization_suggested=normalization_suggested,
            normalization_factor=ThresholdProfileGenerator.suggest_normalization(results)
            if normalization_suggested
            else 1.0,
        )


class BenchmarkMatrix:
    """Main class for building and managing benchmark matrices."""

    def __init__(self, baseline_path: Path) -> None:
        self.baseline_path = baseline_path
        self.results: list[BenchmarkResult] = []
        self.generated_at = datetime.now(UTC).isoformat()

    def add_repository(self, repo_path: Path, name: str = "") -> BenchmarkResult:
        """Benchmark a single repository and add to matrix."""
        # Import here to avoid circular dependency
        from scripts.qoder_baseline_comparison import QoderBaselineComparator

        # Classify repository
        metadata = RepositoryClassifier.classify(repo_path, name)

        # Count files and sections
        try:
            metadata.file_count = len(list(repo_path.rglob("*.md")))
            sections_dir = repo_path / "docs" / "sections"
            if sections_dir.exists():
                metadata.section_count = len(list(sections_dir.iterdir()))
        except (PermissionError, OSError):
            pass

        # Run comparison
        comparator = QoderBaselineComparator(repo_path, self.baseline_path)
        report = comparator.compare_all()

        # Get thresholds for this repository type
        profile = ThresholdProfileGenerator.get_profile(
            metadata.language, metadata.size, metadata.complexity
        )

        # Extract dimension scores
        dimension_scores = {}
        for dim in report.dimensions:
            dimension_scores[dim.dimension] = dim.score

        # Create result
        result = BenchmarkResult(
            repository=metadata,
            overall_score=report.summary["overall_score"],
            structural_score=report.summary["structural_score"],
            quality_score=report.summary["quality_score"],
            dimension_scores=dimension_scores,
            gaps=[g.to_dict() for g in report.dimensions for g in g.gaps],
            acceptance_blocked=report.summary["acceptance_blocked"],
            thresholds={
                "overall": profile.overall_threshold,
                "structural": profile.structural_threshold,
                "quality": profile.quality_threshold,
            },
            passed_thresholds=(
                report.summary["overall_score"] >= profile.overall_threshold
                and report.summary["structural_score"] >= profile.structural_threshold
                and report.summary["quality_score"] >= profile.quality_threshold
            ),
        )

        self.results.append(result)
        return result

    def analyze_drift(self) -> ScoreDriftAnalysis:
        """Analyze score drift across all results."""
        return ScoreDriftDetector.analyze(self.results)

    def to_dict(self) -> dict[str, Any]:
        """Convert matrix to dictionary for JSON export."""
        drift_analysis = self.analyze_drift()

        return {
            "generated_at": self.generated_at,
            "baseline": str(self.baseline_path),
            "repository_count": len(self.results),
            "results": [r.to_dict() for r in self.results],
            "drift_analysis": drift_analysis.to_dict(),
            "threshold_profiles": self._get_unique_profiles(),
        }

    def _get_unique_profiles(self) -> list[dict[str, Any]]:
        """Get unique threshold profiles used in this matrix."""
        profiles_seen = set()
        profiles = []

        for result in self.results:
            key = (result.repository.language, result.repository.size, result.repository.complexity)
            if key not in profiles_seen:
                profiles_seen.add(key)
                profile = ThresholdProfileGenerator.get_profile(
                    result.repository.language,
                    result.repository.size,
                    result.repository.complexity,
                )
                profiles.append(profile.to_dict())

        return profiles

    def to_markdown(self) -> str:
        """Generate markdown report of the benchmark matrix."""
        drift_analysis = self.analyze_drift()

        lines = [
            "# Qoder Benchmark Matrix Report",
            "",
            f"**Generated:** {self.generated_at}",
            f"**Baseline:** `{self.baseline_path}`",
            f"**Repositories:** {len(self.results)}",
            "",
            "---",
            "",
            "## Threshold Profiles",
            "",
        ]

        # Group by language
        by_language: dict[str, list[BenchmarkResult]] = {}
        for result in self.results:
            lang = result.repository.language.value
            if lang not in by_language:
                by_language[lang] = []
            by_language[lang].append(result)

        for lang, results in sorted(by_language.items()):
            lines.append(f"### {lang.title()} Repositories")
            lines.append("")
            for result in results:
                profile = result.thresholds
                status = "PASS" if result.passed_thresholds else "FAIL"
                lines.append(
                    f"- **{result.repository.name}**: "
                    f"Overall {result.overall_score:.1%} (threshold: {profile['overall']:.1%}) "
                    f"[{status}]"
                )
            lines.append("")

        lines.extend(
            [
                "---",
                "",
                "## Score Drift Analysis",
                "",
                f"- **Pattern:** {drift_analysis.pattern_type}",
                f"- **Drift Magnitude:** {drift_analysis.drift_magnitude:+.1%}",
                f"- **Normalization Suggested:** {'Yes' if drift_analysis.normalization_suggested else 'No'}",
            ]
        )

        if drift_analysis.normalization_suggested and drift_analysis.normalization_factor != 1.0:
            lines.append(f"- **Normalization Factor:** {drift_analysis.normalization_factor:.2f}")

        lines.append("")

        return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Qoder benchmark matrix tool")
    parser.add_argument("--repos", nargs="+", type=Path, help="Paths to repository directories")
    parser.add_argument("--from-csv", type=Path, help="CSV file with repository paths")
    parser.add_argument(
        "--baseline", type=Path, required=True, help="Path to qoder baseline fixture"
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="Output path for benchmark matrix"
    )

    args = parser.parse_args()

    if not args.baseline.exists():
        print(f"Error: Baseline path does not exist: {args.baseline}", file=sys.stderr)
        return 1

    # Collect repository paths
    repo_paths = []
    if args.repos:
        repo_paths = args.repos
    elif args.from_csv:
        import csv

        with open(args.from_csv, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                repo_paths.append(Path(row["path"]))
    else:
        print("Error: Must specify --repos or --from-csv", file=sys.stderr)
        return 1

    # Build matrix
    matrix = BenchmarkMatrix(args.baseline)

    for repo_path in repo_paths:
        if not repo_path.exists():
            print(f"Warning: Repository path does not exist: {repo_path}", file=sys.stderr)
            continue
        print(f"Benchmarking: {repo_path}")
        result = matrix.add_repository(repo_path)
        print(
            f"  Overall: {result.overall_score:.1%}, Structural: {result.structural_score:.1%}, Quality: {result.quality_score:.1%}"
        )

    # Export
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(matrix.to_dict(), f, ensure_ascii=False, indent=2)
    print(f"\nBenchmark matrix written to: {args.output}")

    # Also write markdown report
    md_path = args.output.parent / f"{args.output.stem}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(matrix.to_markdown())
    print(f"Markdown report written to: {md_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
