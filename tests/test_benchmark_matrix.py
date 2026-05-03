"""Tests for qoder benchmark matrix and threshold profiles."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from repo_wiki.generator.io import write_text
from scripts.qoder_benchmark_matrix import (
    DEFAULT_THRESHOLDS,
    THRESHOLD_PROFILES,
    BenchmarkMatrix,
    BenchmarkResult,
    Language,
    RepositoryClassifier,
    RepositoryComplexity,
    RepositorySize,
    ScoreDriftDetector,
    ThresholdProfileGenerator,
)


def _create_test_fixture(root: Path, name: str = "test-repo") -> None:
    """Create a test fixture with required structure."""
    # Create fixture metadata
    metadata = {
        "schema_version": "1.0",
        "repository_name": name,
        "repository_type": "python",
        "generated_at": "2026-04-18T00:00:00Z",
        "generator_version": "1.0.0",
    }
    (root / "fixture_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Create minimal docs structure
    (root / "docs").mkdir(parents=True, exist_ok=True)

    write_text(
        root / "docs/00-overview.md",
        """# Overview

## 项目定位

This is a test project.

## 核心问题

We need better docs.

## 核心能力

The system can generate docs.
""",
    )

    write_text(
        root / "docs/01-architecture.md",
        """# Architecture

## 系统分层

Three layers.

## 服务协作

Services work together.
""",
    )

    # Create sections
    (root / "docs/sections").mkdir(parents=True, exist_ok=True)
    for section in ["project", "architecture", "services"]:
        section_dir = root / "docs/sections" / section
        section_dir.mkdir(parents=True, exist_ok=True)
        write_text(section_dir / "index.md", f"# {section.title()}\n")


class TestRepositoryClassifier:
    """Test repository classification."""

    def test_classify_python_repo(self) -> None:
        """Test classification of Python repository."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("[project]\nname = 'test'", encoding="utf-8")

            classifier = RepositoryClassifier()
            result = classifier.classify(root)

            assert result.language == Language.PYTHON

    def test_classify_javascript_repo(self) -> None:
        """Test classification of JavaScript repository."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text('{"name": "test"}', encoding="utf-8")

            classifier = RepositoryClassifier()
            result = classifier.classify(root)

            assert result.language == Language.JAVASCRIPT

    def test_classify_by_size(self) -> None:
        """Test repository size classification."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # Create small repo (no md files)
            classifier = RepositoryClassifier()
            result = classifier.classify(root)
            assert result.size == RepositorySize.SMALL

            # Create medium repo (10-100 md files)
            for i in range(50):
                write_text(root / f"docs/file_{i}.md", f"# File {i}\n")

            result = classifier.classify(root)
            assert result.size == RepositorySize.MEDIUM

    def test_classify_by_complexity(self) -> None:
        """Test repository complexity classification."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir(parents=True, exist_ok=True)
            (root / "docs/sections").mkdir(parents=True, exist_ok=True)

            # Create simple structure
            classifier = RepositoryClassifier()
            result = classifier.classify(root)
            assert result.complexity in [RepositoryComplexity.LOW, RepositoryComplexity.MEDIUM]


class TestThresholdProfileGenerator:
    """Test threshold profile generation."""

    def test_get_python_small_low_profile(self) -> None:
        """Test getting profile for Python small/low complexity repo."""
        profile = ThresholdProfileGenerator.get_profile(
            Language.PYTHON,
            RepositorySize.SMALL,
            RepositoryComplexity.LOW,
        )

        assert (
            profile.overall_threshold
            == THRESHOLD_PROFILES[("python", RepositorySize.SMALL, RepositoryComplexity.LOW)][
                "overall"
            ]
        )
        assert profile.description is not None

    def test_get_unknown_profile_returns_default(self) -> None:
        """Test that unknown types return default thresholds."""
        profile = ThresholdProfileGenerator.get_profile(
            Language.UNKNOWN,
            RepositorySize.MEDIUM,
            RepositoryComplexity.MEDIUM,
        )

        assert profile.overall_threshold == DEFAULT_THRESHOLDS["overall"]
        assert profile.structural_threshold == DEFAULT_THRESHOLDS["structural"]
        assert profile.quality_threshold == DEFAULT_THRESHOLDS["quality"]

    def test_suggest_normalization_high_variance(self) -> None:
        """Test normalization suggestion for high variance scores."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_test_fixture(root)

            # Create mock results with high variance
            from unittest.mock import MagicMock

            mock_results = []
            for score in [0.3, 0.4, 0.5, 0.8, 0.9]:
                result = MagicMock()
                result.overall_score = score
                mock_results.append(result)

            norm_factor = ThresholdProfileGenerator.suggest_normalization(mock_results)

            # High variance should suggest normalization
            assert norm_factor != 1.0


class TestScoreDriftDetector:
    """Test score drift detection."""

    def test_stable_pattern(self) -> None:
        """Test detection of stable pattern."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_test_fixture(root)

            from unittest.mock import MagicMock

            # Create stable scores
            mock_results = []
            for _ in range(5):
                result = MagicMock()
                result.overall_score = 0.65
                result.structural_score = 0.60
                result.quality_score = 0.65
                mock_results.append(result)

            analysis = ScoreDriftDetector.analyze(mock_results)

            assert analysis.pattern_type == "stable"
            assert abs(analysis.drift_magnitude) < 0.05
            assert not analysis.normalization_suggested

    def test_improving_pattern(self) -> None:
        """Test detection of improving pattern."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_test_fixture(root)

            from unittest.mock import MagicMock

            # Create improving scores
            mock_results = []
            for score in [0.5, 0.55, 0.6, 0.7, 0.8]:
                result = MagicMock()
                result.overall_score = score
                result.structural_score = score
                result.quality_score = score
                mock_results.append(result)

            analysis = ScoreDriftDetector.analyze(mock_results)

            assert analysis.pattern_type == "improving"
            assert analysis.drift_magnitude > 0.1

    def test_declining_pattern(self) -> None:
        """Test detection of declining pattern."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_test_fixture(root)

            from unittest.mock import MagicMock

            # Create declining scores
            mock_results = []
            for score in [0.8, 0.7, 0.6, 0.5, 0.4]:
                result = MagicMock()
                result.overall_score = score
                result.structural_score = score
                result.quality_score = score
                mock_results.append(result)

            analysis = ScoreDriftDetector.analyze(mock_results)

            assert analysis.pattern_type == "declining"
            assert analysis.drift_magnitude < -0.1

    def test_single_result_returns_stable(self) -> None:
        """Test that single result returns stable pattern."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_test_fixture(root)

            from unittest.mock import MagicMock

            result = MagicMock()
            result.overall_score = 0.65

            analysis = ScoreDriftDetector.analyze([result])

            assert analysis.pattern_type == "stable"
            assert analysis.drift_magnitude == 0.0


class TestBenchmarkMatrix:
    """Test benchmark matrix functionality."""

    def test_add_repository_creates_result(self) -> None:
        """Test adding a repository to the matrix."""
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline"
            baseline.mkdir()
            _create_test_fixture(baseline, "baseline")

            repo = Path(tmp) / "repo"
            repo.mkdir()
            _create_test_fixture(repo, "test-repo")

            matrix = BenchmarkMatrix(baseline)
            result = matrix.add_repository(repo, "test-repo")

            assert isinstance(result, BenchmarkResult)
            assert result.repository.name == "test-repo"
            assert "overall_score" in result.to_dict()
            assert "thresholds" in result.to_dict()

    def test_to_dict_contains_all_fields(self) -> None:
        """Test that to_dict includes all required fields."""
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline"
            baseline.mkdir()
            _create_test_fixture(baseline, "baseline")

            repo = Path(tmp) / "repo"
            repo.mkdir()
            _create_test_fixture(repo, "test-repo")

            matrix = BenchmarkMatrix(baseline)
            matrix.add_repository(repo, "test-repo")

            result_dict = matrix.to_dict()

            assert "generated_at" in result_dict
            assert "baseline" in result_dict
            assert "repository_count" in result_dict
            assert "results" in result_dict
            assert "drift_analysis" in result_dict
            assert "threshold_profiles" in result_dict

    def test_analyze_drift_with_multiple_results(self) -> None:
        """Test drift analysis with multiple results."""
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline"
            baseline.mkdir()
            _create_test_fixture(baseline, "baseline")

            matrix = BenchmarkMatrix(baseline)

            # Add multiple repositories
            for i in range(3):
                repo = Path(tmp) / f"repo_{i}"
                repo.mkdir()
                _create_test_fixture(repo, f"repo_{i}")
                matrix.add_repository(repo, f"repo_{i}")

            drift_analysis = matrix.analyze_drift()

            assert drift_analysis.pattern_type in ["stable", "improving", "declining", "volatile"]
            assert "drift_magnitude" in drift_analysis.to_dict()
