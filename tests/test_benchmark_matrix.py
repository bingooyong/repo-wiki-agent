"""Tests for qoder benchmark matrix and threshold profiles."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from repo_wiki.generator.io import write_text
from scripts.qoder_benchmark_matrix import (
    BENCHMARK_CONTRACT_VERSION,
    BENCHMARK_MATRIX_SCHEMA_VERSION,
    DEFAULT_THRESHOLDS,
    MIN_GATING_SAMPLE_COUNT,
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


def _create_test_fixture(
    root: Path,
    name: str = "test-repo",
    with_provenance: bool = True,
    content_marker: str | None = None,
) -> None:
    """Create a test fixture with required structure."""
    content_marker = content_marker or name
    # Create fixture metadata
    metadata = {
        "schema_version": "1.0",
        "contract_version": "qoder.fixture_provenance/1.1",
        "repository_name": name,
        "repository_type": "python",
        "generated_at": "2026-04-18T00:00:00Z",
        "generator_version": "1.0.0",
    }
    if with_provenance:
        metadata["source"] = name
        metadata["generator"] = "1.0.0"
    (root / "fixture_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Create minimal docs structure
    (root / "docs").mkdir(parents=True, exist_ok=True)

    write_text(
        root / "docs/00-overview.md",
        f"""# Overview

## 项目定位

This is the {content_marker} test project.

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
            assert result_dict["schema_version"] == BENCHMARK_MATRIX_SCHEMA_VERSION
            assert result_dict["contract_version"] == BENCHMARK_CONTRACT_VERSION
            assert "baseline_provenance" in result_dict
            assert result_dict["results"][0]["schema_version"] == BENCHMARK_CONTRACT_VERSION
            assert result_dict["gating_status"] == "non_gating"
            assert result_dict["non_gating_reasons"]
            assert result_dict["results"][0]["threshold_profile"]["sample_count"] == 1
            assert result_dict["results"][0]["threshold_profile"]["observed_sample_count"] == 1
            assert result_dict["results"][0]["gating_status"] == "non_gating"
            assert any(
                "sample_count" in reason
                for reason in result_dict["results"][0]["non_gating_reasons"]
            )

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
            assert drift_analysis.to_dict()["evidence"]["sample_count"] == 3

            matrix_dict = matrix.to_dict()
            assert matrix_dict["gating_status"] == "gating"
            assert matrix_dict["drift_analysis"]["evidence"]["observed_sample_count"] == 3
            assert matrix_dict["drift_analysis"]["evidence"]["gating_sample_count"] == 3
            assert matrix_dict["drift_analysis"]["diagnostic_only"] is False

    def test_missing_provenance_marks_result_non_gating(self) -> None:
        """Benchmark samples with legacy provenance are marked non-gating."""
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline"
            baseline.mkdir()
            _create_test_fixture(baseline, "baseline", with_provenance=False)

            repo = Path(tmp) / "repo"
            repo.mkdir()
            _create_test_fixture(repo, "test-repo", with_provenance=False)

            matrix = BenchmarkMatrix(baseline)
            result = matrix.add_repository(repo, "test-repo")
            result_dict = result.to_dict()

            assert result_dict["gating_status"] == "non_gating"
            assert result_dict["passed_thresholds"] is False
            assert any(
                "missing required provenance: source" in reason
                for reason in result_dict["non_gating_reasons"]
            )
            assert result_dict["provenance"]["baseline"]["fixture_hash"]
            assert result_dict["provenance"]["sample"]["fixture_hash"]
            assert result_dict["provenance"]["sample"]["hash_algorithm"] == "qoder.fixture_hash/2"

    def test_threshold_profiles_include_sample_count_and_drift_evidence(self) -> None:
        """Threshold profile exports include sample_count and drift evidence."""
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline"
            baseline.mkdir()
            _create_test_fixture(baseline, "baseline")

            matrix = BenchmarkMatrix(baseline)
            for i in range(MIN_GATING_SAMPLE_COUNT):
                repo = Path(tmp) / f"repo_{i}"
                repo.mkdir()
                _create_test_fixture(repo, f"repo_{i}")
                matrix.add_repository(repo, f"repo_{i}")

            profile = matrix.to_dict()["threshold_profiles"][0]

            assert profile["schema_version"] == BENCHMARK_CONTRACT_VERSION
            assert profile["sample_count"] == MIN_GATING_SAMPLE_COUNT
            assert profile["observed_sample_count"] == MIN_GATING_SAMPLE_COUNT
            assert profile["gating_status"] == "gating"
            assert (
                profile["drift_evidence"]["evidence"]["observed_sample_count"]
                == MIN_GATING_SAMPLE_COUNT
            )
            assert (
                profile["drift_evidence"]["evidence"]["gating_sample_count"]
                == MIN_GATING_SAMPLE_COUNT
            )

    def test_invalid_provenance_values_mark_benchmark_non_gating(self) -> None:
        """Types, timestamps, and unsupported versions are non-gating evidence."""
        cases = (
            ("source", {"invalid": True}, "source"),
            ("generated_at", 123, "generated_at"),
            ("generated_at", "not-a-time", "generated_at"),
            ("schema_version", ["invalid"], "schema_version"),
            ("schema_version", "99.0", "schema_version"),
            ("contract_version", 123, "contract_version"),
            (
                "contract_version",
                "qoder.fixture_provenance/99.0",
                "contract_version",
            ),
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, (field_name, value, reason_fragment) in enumerate(cases):
                case_root = root / str(index)
                baseline = case_root / "baseline"
                sample = case_root / "sample"
                baseline.mkdir(parents=True)
                sample.mkdir()
                _create_test_fixture(baseline, f"baseline-{index}")
                _create_test_fixture(sample, f"sample-{index}")
                metadata_path = sample / "fixture_metadata.json"
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                metadata[field_name] = value
                metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

                matrix = BenchmarkMatrix(baseline)
                result = matrix.add_repository(sample, f"sample-{index}")
                matrix_dict = matrix.to_dict()

                assert result.gating_status == "non_gating", field_name
                assert matrix_dict["gating_status"] == "non_gating", field_name
                assert any(reason_fragment in reason for reason in result.non_gating_reasons), (
                    field_name
                )

    def test_invalid_generator_falls_back_but_remains_non_gating(self) -> None:
        """A bad generator alias cannot replace a valid generator_version."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            sample = root / "sample"
            baseline.mkdir()
            sample.mkdir()
            _create_test_fixture(baseline, "baseline")
            _create_test_fixture(sample, "sample")
            metadata_path = sample / "fixture_metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["generator"] = ["invalid"]
            metadata["generator_version"] = "generator-v1"
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

            result = BenchmarkMatrix(baseline).add_repository(sample, "sample")

            assert result.provenance["sample"]["generator"] == "generator-v1"
            assert result.gating_status == "non_gating"
            assert any("metadata.generator" in reason for reason in result.non_gating_reasons)

    def test_declared_fixture_hash_mismatch_is_non_gating(self) -> None:
        """A benchmark sample cannot gate when its declared hash conflicts."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            sample = root / "sample"
            baseline.mkdir()
            sample.mkdir()
            _create_test_fixture(baseline, "baseline")
            _create_test_fixture(sample, "sample")
            metadata_path = sample / "fixture_metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["fixture_hash"] = "0" * 64
            metadata["hash_algorithm"] = "qoder.fixture_hash/2"
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

            result = BenchmarkMatrix(baseline).add_repository(sample, "sample")

            assert result.provenance["sample"]["hash_mismatch"] is True
            assert result.gating_status == "non_gating"
            assert any("does not match" in reason for reason in result.non_gating_reasons)

    def test_profile_excludes_missing_provenance_samples(self) -> None:
        """Observed samples without provenance do not count as gating samples."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            baseline.mkdir()
            _create_test_fixture(baseline, "baseline")

            matrix = BenchmarkMatrix(baseline)
            for index in range(MIN_GATING_SAMPLE_COUNT):
                sample = root / f"sample-{index}"
                sample.mkdir()
                _create_test_fixture(
                    sample,
                    f"sample-{index}",
                    with_provenance=False,
                )
                matrix.add_repository(sample, f"sample-{index}")

            matrix_dict = matrix.to_dict()
            profile = matrix_dict["threshold_profiles"][0]

            assert profile["observed_sample_count"] == MIN_GATING_SAMPLE_COUNT
            assert profile["sample_count"] == 0
            assert profile["gating_status"] == "non_gating"
            assert any(
                "sample" in reason and "source" in reason
                for reason in profile["non_gating_reasons"]
            )

    def test_profile_deduplicates_fixture_hashes(self) -> None:
        """Repeated fixtures count once and cannot create gating drift evidence."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            baseline.mkdir()
            _create_test_fixture(baseline, "baseline")

            matrix = BenchmarkMatrix(baseline)
            for index in range(MIN_GATING_SAMPLE_COUNT):
                sample = root / f"sample-{index}"
                sample.mkdir()
                _create_test_fixture(
                    sample,
                    f"sample-{index}",
                    content_marker="identical-content",
                )
                matrix.add_repository(sample, f"sample-{index}")

            matrix_dict = matrix.to_dict()
            profile = matrix_dict["threshold_profiles"][0]

            assert profile["observed_sample_count"] == MIN_GATING_SAMPLE_COUNT
            assert profile["sample_count"] == 1
            assert profile["gating_status"] == "non_gating"
            assert any(
                "duplicate fixture_hash" in reason for reason in profile["non_gating_reasons"]
            )
            assert any("below minimum" in reason for reason in profile["non_gating_reasons"])
            assert profile["drift_evidence"]["diagnostic_only"] is True
            assert (
                profile["drift_evidence"]["evidence"]["observed_sample_count"]
                == MIN_GATING_SAMPLE_COUNT
            )
            assert profile["drift_evidence"]["evidence"]["gating_sample_count"] == 1
            assert matrix_dict["gating_status"] == "non_gating"

    def test_invalid_baseline_provenance_blocks_profile_and_matrix(self) -> None:
        """A profile cannot gate against an unsupported baseline contract."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline"
            baseline.mkdir()
            _create_test_fixture(baseline, "baseline")
            metadata_path = baseline / "fixture_metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["contract_version"] = "qoder.fixture_provenance/99.0"
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

            matrix = BenchmarkMatrix(baseline)
            for index in range(MIN_GATING_SAMPLE_COUNT):
                sample = root / f"sample-{index}"
                sample.mkdir()
                _create_test_fixture(sample, f"sample-{index}")
                matrix.add_repository(sample, f"sample-{index}")

            matrix_dict = matrix.to_dict()
            profile = matrix_dict["threshold_profiles"][0]

            assert profile["sample_count"] == MIN_GATING_SAMPLE_COUNT
            assert profile["gating_status"] == "non_gating"
            assert any(
                "baseline" in reason and "contract_version" in reason
                for reason in profile["non_gating_reasons"]
            )
            assert matrix_dict["gating_status"] == "non_gating"

    def test_empty_matrix_is_explicitly_non_gating(self) -> None:
        """A matrix with no observed benchmark samples cannot be gating."""
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline"
            baseline.mkdir()
            _create_test_fixture(baseline, "baseline")

            matrix_dict = BenchmarkMatrix(baseline).to_dict()

            assert matrix_dict["gating_status"] == "non_gating"
            assert any(
                "no observed samples" in reason for reason in matrix_dict["non_gating_reasons"]
            )
            assert matrix_dict["drift_analysis"]["diagnostic_only"] is True
            assert matrix_dict["drift_analysis"]["evidence"]["observed_sample_count"] == 0
            assert matrix_dict["drift_analysis"]["evidence"]["gating_sample_count"] == 0
