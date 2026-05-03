"""Tests for Qoder parity metrics."""

import json

import pytest

from repo_wiki.verifier.qoder_parity_metrics import (
    PARITY_METRIC_SCHEMA_VERSION,
    PARITY_METRICS,
    MetricCategory,
    MetricResult,
    MetricSeverity,
    MetricStatus,
    ParityMetricExtractor,
    ParityReport,
    create_parity_report,
    export_metric_schema,
    load_parity_report,
    metric_schema_to_json,
)


class TestMetricDefinitions:
    """Tests for metric definitions."""

    def test_all_metrics_defined(self):
        """Test all expected metrics are defined."""
        expected = [
            "page_coverage",
            "directory_depth",
            "file_reference_integrity",
            "citation_coverage",
            "citation_density",
            "toc_presence",
            "mermaid_presence",
            "prose_density",
            "prose_list_ratio",
            "api_aggregation",
            "data_model_aggregation",
        ]
        for name in expected:
            assert name in PARITY_METRICS, f"Missing metric: {name}"

    def test_metric_weights_sum_to_one(self):
        """Test metric weights sum to approximately 1.0."""
        total = sum(m.weight for m in PARITY_METRICS.values())
        assert 0.99 <= total <= 1.01, f"Weights sum to {total}, expected ~1.0"

    def test_metric_thresholds_in_range(self):
        """Test all thresholds are in valid range."""
        for metric in PARITY_METRICS.values():
            assert 0 <= metric.threshold <= 1.0, f"{metric.name} threshold out of range"

    def test_definitions_have_unit_and_threshold_compare(self):
        """Registry entries must document units and threshold semantics."""
        for metric in PARITY_METRICS.values():
            assert metric.unit.value
            assert metric.threshold_compare in ("score", "measured_value")


class TestMetricSchemaSerialization:
    """Tests for exported metric schema (Task 29.1)."""

    def test_export_metric_schema_shape(self):
        schema = export_metric_schema()
        assert schema["schema_version"] == PARITY_METRIC_SCHEMA_VERSION
        assert schema["schema_kind"] == "qoder_parity_metrics"
        assert schema["metric_count"] == len(PARITY_METRICS)
        assert len(schema["metrics"]) == len(PARITY_METRICS)
        names = {m["name"] for m in schema["metrics"]}
        assert names == set(PARITY_METRICS.keys())

    def test_metric_schema_json_roundtrip(self):
        raw = metric_schema_to_json(indent=2)
        data = json.loads(raw)
        assert data["schema_version"] == PARITY_METRIC_SCHEMA_VERSION
        first = data["metrics"][0]
        assert "unit" in first
        assert "threshold_compare" in first
        assert "severity" in first


class TestMetricResult:
    """Tests for MetricResult."""

    def test_create_metric_result(self):
        """Test creating a metric result."""
        result = MetricResult(
            metric_name="page_coverage",
            status=MetricStatus.PASS,
            score=0.85,
            measured_value=0.85,
            threshold=0.80,
            severity=MetricSeverity.CRITICAL,
            category=MetricCategory.STRUCTURAL,
        )
        assert result.metric_name == "page_coverage"
        assert result.status == MetricStatus.PASS
        assert result.score == 0.85

    def test_is_blocking_critical_fail(self):
        """Test critical failure is blocking."""
        result = MetricResult(
            metric_name="page_coverage",
            status=MetricStatus.FAIL,
            score=0.5,
            measured_value=0.5,
            threshold=0.80,
            severity=MetricSeverity.CRITICAL,
            category=MetricCategory.STRUCTURAL,
        )
        assert result.is_blocking is True

    def test_is_not_blocking_major_fail(self):
        """Test major failure is not blocking."""
        result = MetricResult(
            metric_name="citation_coverage",
            status=MetricStatus.FAIL,
            score=0.5,
            measured_value=0.5,
            threshold=0.70,
            severity=MetricSeverity.MAJOR,
            category=MetricCategory.CONTENT,
        )
        assert result.is_blocking is False

    def test_to_dict(self):
        """Test serialization to dict."""
        result = MetricResult(
            metric_name="page_coverage",
            status=MetricStatus.PASS,
            score=0.85,
            measured_value=0.85,
            threshold=0.80,
            severity=MetricSeverity.CRITICAL,
            category=MetricCategory.STRUCTURAL,
            gaps=["Minor gap"],
        )
        d = result.to_dict()
        assert d["metric_name"] == "page_coverage"
        assert d["status"] == "pass"
        assert d["score"] == 0.85
        assert d["gaps"] == ["Minor gap"]


class TestParityReport:
    """Tests for ParityReport."""

    def test_create_parity_report(self, tmp_path):
        """Test creating a parity report."""
        report = ParityReport(
            target_root=tmp_path,
            baseline_root=None,
            run_id="test-run",
            generated_at="2024-01-01T00:00:00Z",
        )
        assert report.target_root == tmp_path
        assert len(report.metrics) == 0

    def test_add_metric(self, tmp_path):
        """Test adding metrics to report."""
        report = ParityReport(
            target_root=tmp_path,
            baseline_root=None,
            run_id="test-run",
            generated_at="2024-01-01T00:00:00Z",
        )
        result = MetricResult(
            metric_name="page_coverage",
            status=MetricStatus.PASS,
            score=0.85,
            measured_value=0.85,
            threshold=0.80,
            severity=MetricSeverity.CRITICAL,
            category=MetricCategory.STRUCTURAL,
        )
        report.add_metric(result)
        assert len(report.metrics) == 1
        assert report.blocked is False

    def test_add_blocking_metric(self, tmp_path):
        """Test adding a blocking metric."""
        report = ParityReport(
            target_root=tmp_path,
            baseline_root=None,
            run_id="test-run",
            generated_at="2024-01-01T00:00:00Z",
        )
        result = MetricResult(
            metric_name="page_coverage",
            status=MetricStatus.FAIL,
            score=0.5,
            measured_value=0.5,
            threshold=0.80,
            severity=MetricSeverity.CRITICAL,
            category=MetricCategory.STRUCTURAL,
            gaps=["Missing 50% of pages"],
        )
        report.add_metric(result)
        assert report.blocked is True
        assert len(report.blocking_reasons) == 1

    def test_compute_summary(self, tmp_path):
        """Test computing summary statistics."""
        report = ParityReport(
            target_root=tmp_path,
            baseline_root=None,
            run_id="test-run",
            generated_at="2024-01-01T00:00:00Z",
        )
        # Add some metrics
        for name, metric in list(PARITY_METRICS.items())[:3]:
            result = MetricResult(
                metric_name=name,
                status=MetricStatus.PASS,
                score=0.85,
                measured_value=0.85,
                threshold=metric.threshold,
                severity=metric.severity,
                category=metric.category,
            )
            report.add_metric(result)

        summary = report.compute_summary()
        assert "total_metrics" in summary
        assert "overall_score" in summary
        assert summary["passed"] == 3

    def test_to_dict(self, tmp_path):
        """Test serialization to dict."""
        report = ParityReport(
            target_root=tmp_path,
            baseline_root=None,
            run_id="test-run",
            generated_at="2024-01-01T00:00:00Z",
        )
        result = MetricResult(
            metric_name="page_coverage",
            status=MetricStatus.PASS,
            score=0.85,
            measured_value=0.85,
            threshold=0.80,
            severity=MetricSeverity.CRITICAL,
            category=MetricCategory.STRUCTURAL,
        )
        report.add_metric(result)

        d = report.to_dict()
        assert d["run_id"] == "test-run"
        assert len(d["metrics"]) == 1
        assert d["blocked"] is False


class TestParityMetricExtractor:
    """Tests for ParityMetricExtractor."""

    @pytest.fixture
    def setup_content(self, tmp_path):
        """Set up content directory structure."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create overview page
        (content_dir / "00-overview.md").write_text("""# Project Overview

## Table of Contents
- [Introduction](#introduction)
- [Architecture](#architecture)

## Introduction

This is a sample project. It provides functionality X.

## Architecture

```mermaid
graph LR
    A --> B
```

<cite>source:docs/overview.md</cite>
""")

        # Create architecture page
        (content_dir / "01-architecture.md").write_text("""# Architecture

## Core链路

This system uses microservices.

## Storage Design

<cite>source:docs/architecture.md</cite>
""")

        return tmp_path

    def test_extract_page_coverage(self, setup_content):
        """Test extracting page coverage."""
        extractor = ParityMetricExtractor(setup_content)
        result = extractor._measure_page_coverage()

        assert result.metric_name == "page_coverage"
        assert result.status in [MetricStatus.PASS, MetricStatus.FAIL]

    def test_extract_toc_presence(self, setup_content):
        """Test extracting TOC presence."""
        extractor = ParityMetricExtractor(setup_content)
        result = extractor._measure_toc_presence()

        assert result.metric_name == "toc_presence"
        # Only 1/2 pages have TOC, so score is 0.5
        assert result.status == MetricStatus.FAIL  # Below 0.8 threshold
        assert result.score == 0.5

    def test_extract_mermaid_presence(self, setup_content):
        """Test extracting Mermaid presence."""
        extractor = ParityMetricExtractor(setup_content)
        result = extractor._measure_mermaid_presence()

        assert result.metric_name == "mermaid_presence"
        assert result.status == MetricStatus.PASS  # We have Mermaid

    def test_extract_all_metrics(self, setup_content):
        """Test extracting all metrics."""
        extractor = ParityMetricExtractor(setup_content)
        report = extractor.extract_all()

        assert len(report.metrics) >= 10  # At least our defined metrics
        assert report.summary.get("total_metrics", 0) >= 10


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_parity_report(self, tmp_path):
        """Test create_parity_report factory."""
        # Create minimal content
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "00-overview.md").write_text("# Overview\n\nTest content.")

        report = create_parity_report(tmp_path)
        assert isinstance(report, ParityReport)
        assert len(report.metrics) > 0

    def test_load_parity_report(self, tmp_path):
        """Test load_parity_report factory."""
        # Create minimal content
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "00-overview.md").write_text("# Overview\n\nTest content.")

        # Create and save a report
        report = create_parity_report(tmp_path)
        json_path = tmp_path / "report.json"
        report.to_json(json_path)

        # Load it back
        loaded = load_parity_report(json_path)
        assert isinstance(loaded, ParityReport)
        assert loaded.run_id == report.run_id


class TestIntegration:
    """Integration tests for parity metrics."""

    def test_empty_content_dir(self, tmp_path):
        """Test handling of empty content directory."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        extractor = ParityMetricExtractor(tmp_path)
        report = extractor.extract_all()

        # Should have metrics with low scores
        assert len(report.metrics) > 0
        page_metric = next((m for m in report.metrics if m.metric_name == "page_coverage"), None)
        if page_metric:
            assert page_metric.status == MetricStatus.FAIL

    def test_realistic_content(self, tmp_path):
        """Test with more realistic content."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create a realistic page
        (content_dir / "00-overview.md").write_text("""# Project Overview

## Table of Contents
1. [Introduction](#introduction)
2. [Quick Start](#quick-start)

## Introduction

This project provides a comprehensive solution for X.

<cite>source:overview.md</cite>

## Quick Start

1. Install dependencies
2. Configure settings
3. Run the application

### Installation

```bash
pip install package
```

### Configuration

```json
{
  "setting": "value"
}
```
""")

        extractor = ParityMetricExtractor(tmp_path)
        report = extractor.extract_all()

        # Should have good scores
        toc_metric = next((m for m in report.metrics if m.metric_name == "toc_presence"), None)
        if toc_metric:
            assert toc_metric.score >= 0.5

        prose_metric = next((m for m in report.metrics if m.metric_name == "prose_density"), None)
        if prose_metric:
            assert prose_metric.score > 0
