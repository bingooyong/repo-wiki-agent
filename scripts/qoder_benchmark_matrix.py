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

BENCHMARK_MATRIX_SCHEMA_VERSION = "qoder.benchmark_matrix/1.1"
BENCHMARK_CONTRACT_VERSION = "qoder.benchmark_contract/1.1"
MIN_GATING_SAMPLE_COUNT = 2


def profile_id(
    language: str | Language, size: RepositorySize, complexity: RepositoryComplexity
) -> str:
    """Stable identifier for a threshold profile."""
    language_value = language.value if isinstance(language, Language) else language
    return f"{language_value}:{size.value}:{complexity.value}"


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
    threshold_profile_id: str = ""
    threshold_profile_sample_count: int = 0
    threshold_profile_observed_sample_count: int = 0
    gating_status: str = "gating"
    non_gating_reasons: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    drift_evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": BENCHMARK_CONTRACT_VERSION,
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
            "threshold_profile": {
                "id": self.threshold_profile_id,
                "sample_count": self.threshold_profile_sample_count,
                "observed_sample_count": self.threshold_profile_observed_sample_count,
                "min_gating_sample_count": MIN_GATING_SAMPLE_COUNT,
            },
            "gating_status": self.gating_status,
            "non_gating_reasons": self.non_gating_reasons,
            "provenance": self.provenance,
            "drift_evidence": self.drift_evidence,
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
    observed_sample_count: int = 0
    calibration_data: dict[str, Any] = field(default_factory=dict)
    gating_status: str = "non_gating"
    non_gating_reasons: list[str] = field(default_factory=list)
    drift_evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": profile_id(self.language, self.size, self.complexity),
            "schema_version": BENCHMARK_CONTRACT_VERSION,
            "language": self.language,
            "size": self.size.value,
            "complexity": self.complexity.value,
            "overall_threshold": self.overall_threshold,
            "structural_threshold": self.structural_threshold,
            "quality_threshold": self.quality_threshold,
            "description": self.description,
            "sample_count": self.sample_count,
            "observed_sample_count": self.observed_sample_count,
            "min_gating_sample_count": MIN_GATING_SAMPLE_COUNT,
            "gating_status": self.gating_status,
            "non_gating_reasons": self.non_gating_reasons,
            "drift_evidence": self.drift_evidence,
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
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_type": self.pattern_type,
            "drift_magnitude": round(self.drift_magnitude, 3),
            "affected_dimensions": self.affected_dimensions,
            "normalization_suggested": self.normalization_suggested,
            "normalization_factor": round(self.normalization_factor, 3),
            "evidence": self.evidence,
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
                evidence={
                    "sample_count": len(results),
                    "reason": "fewer than two benchmark samples",
                    "overall_scores": [round(r.overall_score, 3) for r in results],
                },
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
            evidence={
                "sample_count": len(results),
                "overall_scores": [round(score, 3) for score in overall_scores],
                "first_half_average": round(first_half_avg, 3),
                "second_half_average": round(second_half_avg, 3),
                "drift_threshold": 0.1,
                "stability_threshold": 0.05,
            },
        )


class BenchmarkMatrix:
    """Main class for building and managing benchmark matrices."""

    def __init__(self, baseline_path: Path) -> None:
        self.baseline_path = baseline_path
        self.results: list[BenchmarkResult] = []
        self.generated_at = datetime.now(UTC).isoformat()
        self.baseline_provenance = self._load_fixture_provenance(baseline_path)

    @staticmethod
    def _load_fixture_provenance(fixture_path: Path) -> dict[str, Any]:
        """Load stable provenance for a benchmark fixture/repository sample."""
        from scripts.qoder_fixture_ingestion import (
            FIXTURE_HASH_ALGORITHM,
            FIXTURE_MANIFEST_SCHEMA_VERSION,
            FIXTURE_PROVENANCE_CONTRACT_VERSION,
            FixtureIntegrityChecker,
            get_fixture_provenance_issues,
        )

        metadata_path = fixture_path / "fixture_metadata.json"
        metadata: dict[str, Any] = {}
        metadata_present = metadata_path.exists()
        metadata_error = ""
        if metadata_present:
            try:
                loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    metadata = loaded
                else:
                    metadata_error = "fixture_metadata.json must contain a JSON object"
            except (json.JSONDecodeError, UnicodeDecodeError, OSError):
                metadata_error = "fixture_metadata.json could not be parsed"

        custom_fields = metadata.get("custom_fields", {})
        if not isinstance(custom_fields, dict):
            custom_fields = {}

        def valid_string(value: Any) -> bool:
            return isinstance(value, str) and bool(value.strip())

        def missing_string(value: Any) -> bool:
            return value is None or (
                isinstance(value, str) and value.strip().lower() in {"", "unknown"}
            )

        def select_value(candidates: list[tuple[str, Any]]) -> Any:
            for _, value in candidates:
                if valid_string(value):
                    return value.strip()
            return candidates[0][1] if candidates else None

        source_candidates = [
            (field_name, metadata[field_name])
            for field_name in ("source", "fixture_source")
            if field_name in metadata
        ]
        if "source" in custom_fields:
            source_candidates.append(("custom_fields.source", custom_fields["source"]))
        generator_candidates = [
            (field_name, metadata[field_name])
            for field_name in ("generator", "generator_version")
            if field_name in metadata
        ]

        source_value = select_value(source_candidates)
        generator_value = select_value(generator_candidates)
        schema_version = metadata.get("schema_version")
        contract_version = metadata.get("contract_version")
        generated_at = metadata.get("generated_at")

        invalid = []
        if metadata_error:
            invalid.append(metadata_error)
        for field_name, value in (*source_candidates, *generator_candidates):
            if not valid_string(value):
                invalid.append(f"metadata.{field_name} must be a non-empty string")

        integrity = FixtureIntegrityChecker.compute_integrity(fixture_path)
        metadata_hash_value = metadata.get("fixture_hash")
        metadata_hash = (
            metadata_hash_value.strip().lower() if valid_string(metadata_hash_value) else None
        )
        if "fixture_hash" in metadata and metadata_hash is None:
            invalid.append("metadata.fixture_hash must be a non-empty string")
        elif metadata_hash and (
            len(metadata_hash) != 64
            or any(character not in "0123456789abcdef" for character in metadata_hash)
        ):
            invalid.append("metadata.fixture_hash must be a 64-character SHA-256 hex digest")

        metadata_hash_algorithm_value = metadata.get("hash_algorithm")
        metadata_hash_algorithm = (
            metadata_hash_algorithm_value.strip()
            if valid_string(metadata_hash_algorithm_value)
            else None
        )
        if "hash_algorithm" in metadata and metadata_hash_algorithm is None:
            invalid.append("metadata.hash_algorithm must be a non-empty string")
        elif metadata_hash_algorithm and metadata_hash_algorithm != FIXTURE_HASH_ALGORITHM:
            invalid.append(f"Unsupported fixture hash_algorithm '{metadata_hash_algorithm}'")

        missing = []
        if not metadata_present:
            missing.append("fixture_metadata.json")
        if missing_string(schema_version):
            missing.append("schema_version")
        if missing_string(contract_version):
            missing.append("contract_version")
        if missing_string(source_value):
            missing.append("source")
        if missing_string(generator_value):
            missing.append("generator")
        if missing_string(generated_at):
            missing.append("generated_at")
        if integrity.file_count <= 0:
            missing.append("markdown_samples")

        hash_mismatch = bool(metadata_hash and metadata_hash != integrity.fixture_hash)
        provenance_issues = get_fixture_provenance_issues(
            schema_version=schema_version,
            contract_version=contract_version,
            source=source_value,
            generator=generator_value,
            generated_at=generated_at,
            fixture_hash=integrity.fixture_hash,
            sample_count=integrity.file_count,
        )
        for issue in invalid:
            if issue not in provenance_issues:
                provenance_issues.append(issue)
        invalid = [issue for issue in provenance_issues if not issue.startswith("Missing ")]

        return {
            "schema_version": FIXTURE_MANIFEST_SCHEMA_VERSION,
            "contract_version": FIXTURE_PROVENANCE_CONTRACT_VERSION,
            "path": str(fixture_path),
            "metadata_present": metadata_present,
            "metadata_schema_version": schema_version.strip()
            if valid_string(schema_version)
            else "unknown",
            "metadata_contract_version": contract_version.strip()
            if valid_string(contract_version)
            else "unknown",
            "source": source_value.strip() if valid_string(source_value) else "unknown",
            "generator": generator_value.strip() if valid_string(generator_value) else "unknown",
            "generated_at": generated_at.strip() if valid_string(generated_at) else "unknown",
            "fixture_hash": integrity.fixture_hash,
            "hash_algorithm": FIXTURE_HASH_ALGORITHM,
            "metadata_fixture_hash": metadata_hash,
            "metadata_hash_algorithm": metadata_hash_algorithm,
            "fixture_hash_source": "metadata+computed" if metadata_hash else "computed",
            "hash_mismatch": hash_mismatch,
            "sample_count": integrity.file_count,
            "missing_required_provenance": missing,
            "invalid_required_provenance": invalid,
            "provenance_issues": provenance_issues,
            "gating_eligible": not provenance_issues and not hash_mismatch,
        }

    @staticmethod
    def _profile_key(
        result: BenchmarkResult,
    ) -> tuple[Language, RepositorySize, RepositoryComplexity]:
        return (result.repository.language, result.repository.size, result.repository.complexity)

    @staticmethod
    def _profile_id_for_metadata(metadata: RepositoryMetadata) -> str:
        return profile_id(metadata.language, metadata.size, metadata.complexity)

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
        profile_identifier = self._profile_id_for_metadata(metadata)

        # Extract dimension scores
        dimension_scores = {}
        for dim in report.dimensions:
            dimension_scores[dim.dimension] = dim.score

        sample_provenance = self._load_fixture_provenance(repo_path)
        non_gating_reasons = []
        for scope, provenance in (
            ("baseline", self.baseline_provenance),
            ("sample", sample_provenance),
        ):
            for missing in provenance["missing_required_provenance"]:
                non_gating_reasons.append(f"{scope} missing required provenance: {missing}")
            if provenance["hash_mismatch"]:
                non_gating_reasons.append(f"{scope} fixture_hash does not match computed hash")

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
            threshold_profile_id=profile_identifier,
            provenance={
                "baseline": self.baseline_provenance,
                "sample": sample_provenance,
            },
            non_gating_reasons=non_gating_reasons,
        )

        self.results.append(result)
        self._refresh_contract_statuses()
        return result

    def analyze_drift(self) -> ScoreDriftAnalysis:
        """Analyze score drift across all results."""
        return ScoreDriftDetector.analyze(self.results)

    @staticmethod
    def _deduplicate_reasons(reasons: list[str]) -> list[str]:
        return list(dict.fromkeys(reasons))

    @classmethod
    def _provenance_non_gating_reasons(cls, scope: str, provenance: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        for missing in provenance.get("missing_required_provenance", []):
            reasons.append(f"{scope} missing required provenance: {missing}")
        for issue in provenance.get("provenance_issues", []):
            if not issue.startswith("Missing "):
                reasons.append(f"{scope} invalid provenance: {issue}")
        if provenance.get("hash_mismatch"):
            reasons.append(f"{scope} fixture_hash does not match computed hash")
        return cls._deduplicate_reasons(reasons)

    @staticmethod
    def _build_drift_evidence(
        observed_results: list[BenchmarkResult],
        gating_results: list[BenchmarkResult],
        gating_status: str,
        non_gating_reasons: list[str],
    ) -> dict[str, Any]:
        observed_analysis = ScoreDriftDetector.analyze(observed_results).to_dict()
        gating_analysis = ScoreDriftDetector.analyze(gating_results).to_dict()
        selected = gating_analysis if gating_status == "gating" else observed_analysis
        drift_evidence = dict(selected)
        drift_evidence["evidence"] = {
            **selected.get("evidence", {}),
            "evidence_scope": "gating" if gating_status == "gating" else "observed_diagnostic",
            "observed_sample_count": len(observed_results),
            "gating_sample_count": len(gating_results),
        }
        drift_evidence.update(
            {
                "gating_status": gating_status,
                "non_gating_reasons": non_gating_reasons,
                "diagnostic_only": gating_status != "gating",
                "observed_analysis": observed_analysis,
                "gating_analysis": gating_analysis if gating_status == "gating" else None,
            }
        )
        return drift_evidence

    def _profile_contracts(
        self,
    ) -> dict[tuple[Language, RepositorySize, RepositoryComplexity], dict[str, Any]]:
        grouped_results: dict[
            tuple[Language, RepositorySize, RepositoryComplexity], list[BenchmarkResult]
        ] = {}
        for result in self.results:
            grouped_results.setdefault(self._profile_key(result), []).append(result)

        contracts = {}
        baseline_reasons = self._provenance_non_gating_reasons("baseline", self.baseline_provenance)
        for key, results in grouped_results.items():
            reasons = list(baseline_reasons)
            eligible_results = []
            fixture_hash_counts: dict[str, int] = {}

            for result in results:
                sample = result.provenance.get("sample", {})
                sample_reasons = self._provenance_non_gating_reasons(
                    f"sample {result.repository.name}", sample
                )
                reasons.extend(sample_reasons)
                if not sample_reasons and sample.get("gating_eligible"):
                    eligible_results.append(result)
                    fixture_hash = sample["fixture_hash"]
                    fixture_hash_counts[fixture_hash] = fixture_hash_counts.get(fixture_hash, 0) + 1

            independent_results = []
            seen_hashes = set()
            for result in eligible_results:
                fixture_hash = result.provenance["sample"]["fixture_hash"]
                if fixture_hash not in seen_hashes:
                    independent_results.append(result)
                    seen_hashes.add(fixture_hash)

            duplicate_hashes = sorted(
                fixture_hash for fixture_hash, count in fixture_hash_counts.items() if count > 1
            )
            for fixture_hash in duplicate_hashes:
                reasons.append(
                    "threshold profile duplicate fixture_hash "
                    f"{fixture_hash} observed {fixture_hash_counts[fixture_hash]} times"
                )

            sample_count = len(independent_results)
            if sample_count < MIN_GATING_SAMPLE_COUNT:
                reasons.append(
                    f"threshold profile sample_count {sample_count} below minimum "
                    f"{MIN_GATING_SAMPLE_COUNT}"
                )

            reasons = self._deduplicate_reasons(reasons)
            gating_status = "non_gating" if reasons else "gating"
            contracts[key] = {
                "results": results,
                "observed_sample_count": len(results),
                "provenance_qualified_sample_count": len(eligible_results),
                "sample_count": sample_count,
                "independent_results": independent_results,
                "duplicate_fixture_hashes": duplicate_hashes,
                "duplicate_sample_count": len(eligible_results) - sample_count,
                "gating_status": gating_status,
                "non_gating_reasons": reasons,
                "drift_evidence": self._build_drift_evidence(
                    results,
                    independent_results,
                    gating_status,
                    reasons,
                ),
            }

        return contracts

    def _refresh_contract_statuses(
        self,
    ) -> dict[tuple[Language, RepositorySize, RepositoryComplexity], dict[str, Any]]:
        """Update sample counts, drift evidence, and gating status for all results."""
        contracts = self._profile_contracts()

        for contract in contracts.values():
            for result in contract["results"]:
                result_reasons = []
                for scope in ("baseline", "sample"):
                    result_reasons.extend(
                        self._provenance_non_gating_reasons(scope, result.provenance.get(scope, {}))
                    )
                result_reasons.extend(contract["non_gating_reasons"])

                result.threshold_profile_sample_count = contract["sample_count"]
                result.threshold_profile_observed_sample_count = contract["observed_sample_count"]
                result.drift_evidence = contract["drift_evidence"]
                result.non_gating_reasons = self._deduplicate_reasons(result_reasons)
                result.gating_status = "non_gating" if result.non_gating_reasons else "gating"
                scores_pass = (
                    result.overall_score >= result.thresholds["overall"]
                    and result.structural_score >= result.thresholds["structural"]
                    and result.quality_score >= result.thresholds["quality"]
                )
                result.passed_thresholds = scores_pass and result.gating_status == "gating"

        return contracts

    def _matrix_contract_status(
        self,
        contracts: dict[tuple[Language, RepositorySize, RepositoryComplexity], dict[str, Any]],
    ) -> tuple[str, list[str]]:
        reasons = self._provenance_non_gating_reasons("baseline", self.baseline_provenance)
        if not self.results:
            reasons.append("benchmark matrix has no observed samples")

        baseline_reasons = set(reasons)
        for key, contract in contracts.items():
            profile_identifier = profile_id(*key)
            for reason in contract["non_gating_reasons"]:
                if reason not in baseline_reasons:
                    reasons.append(f"threshold profile {profile_identifier}: {reason}")

        reasons = self._deduplicate_reasons(reasons)
        return ("non_gating" if reasons else "gating", reasons)

    def to_dict(self) -> dict[str, Any]:
        """Convert matrix to dictionary for JSON export."""
        contracts = self._refresh_contract_statuses()
        gating_status, non_gating_reasons = self._matrix_contract_status(contracts)
        gating_results = [
            result for contract in contracts.values() for result in contract["independent_results"]
        ]
        drift_analysis = self._build_drift_evidence(
            self.results,
            gating_results,
            gating_status,
            non_gating_reasons,
        )

        return {
            "schema_version": BENCHMARK_MATRIX_SCHEMA_VERSION,
            "contract_version": BENCHMARK_CONTRACT_VERSION,
            "generated_at": self.generated_at,
            "baseline": str(self.baseline_path),
            "baseline_provenance": self.baseline_provenance,
            "repository_count": len(self.results),
            "gating_status": gating_status,
            "non_gating_reasons": non_gating_reasons,
            "results": [r.to_dict() for r in self.results],
            "drift_analysis": drift_analysis,
            "threshold_profiles": self._get_unique_profiles(contracts),
        }

    def _get_unique_profiles(
        self,
        contracts: dict[tuple[Language, RepositorySize, RepositoryComplexity], dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Get unique threshold profiles used in this matrix."""
        profiles = []

        for key, contract in contracts.items():
            language, size, complexity = key
            profile = ThresholdProfileGenerator.get_profile(language, size, complexity)
            profile.sample_count = contract["sample_count"]
            profile.observed_sample_count = contract["observed_sample_count"]
            profile.gating_status = contract["gating_status"]
            profile.non_gating_reasons = contract["non_gating_reasons"]
            profile.drift_evidence = contract["drift_evidence"]
            profile.calibration_data = {
                "sample_count": contract["sample_count"],
                "observed_sample_count": contract["observed_sample_count"],
                "provenance_qualified_sample_count": contract["provenance_qualified_sample_count"],
                "duplicate_sample_count": contract["duplicate_sample_count"],
                "duplicate_fixture_hashes": contract["duplicate_fixture_hashes"],
                "min_gating_sample_count": MIN_GATING_SAMPLE_COUNT,
                "profile_id": profile_id(language, size, complexity),
            }
            profiles.append(profile.to_dict())

        return profiles

    def to_markdown(self) -> str:
        """Generate markdown report of the benchmark matrix."""
        self._refresh_contract_statuses()
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
                status = (
                    "NON-GATING"
                    if result.gating_status == "non_gating"
                    else ("PASS" if result.passed_thresholds else "FAIL")
                )
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
