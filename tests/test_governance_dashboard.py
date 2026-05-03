"""Tests for qoder governance dashboard and SQLite export."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.qoder_governance_dashboard import (
    SQLITE_AVAILABLE,
    GovernanceDB,
    GovernanceMetric,
    TrendAnalyzer,
    TrendData,
)


class TestGovernanceMetric:
    """Test GovernanceMetric dataclass."""

    def test_to_dict(self) -> None:
        """Test metric to dict conversion."""
        metric = GovernanceMetric(
            id=1,
            repository_name="test-repo",
            repository_path="/path/to/repo",
            language="python",
            size_category="medium",
            complexity="medium",
            overall_score=0.75,
            structural_score=0.70,
            quality_score=0.80,
            acceptance_blocked=False,
            total_gaps=5,
            critical_gaps=0,
            major_gaps=2,
            benchmark_date="2026-04-18T00:00:00Z",
            fixture_hash="abc123",
        )

        result = metric.to_dict()

        assert result["id"] == 1
        assert result["repository_name"] == "test-repo"
        assert result["overall_score"] == 0.75
        assert result["acceptance_blocked"] is False


class TestTrendAnalyzer:
    """Test trend analysis functionality."""

    def test_calculate_slope_improving(self) -> None:
        """Test slope calculation for improving trend."""
        values = [0.5, 0.55, 0.6, 0.65, 0.7]
        slope = TrendAnalyzer.calculate_slope(values)

        assert slope > 0  # Positive slope indicates improvement

    def test_calculate_slope_declining(self) -> None:
        """Test slope calculation for declining trend."""
        values = [0.7, 0.65, 0.6, 0.55, 0.5]
        slope = TrendAnalyzer.calculate_slope(values)

        assert slope < 0  # Negative slope indicates decline

    def test_calculate_slope_stable(self) -> None:
        """Test slope calculation for stable trend."""
        values = [0.5, 0.5, 0.5, 0.5, 0.5]
        slope = TrendAnalyzer.calculate_slope(values)

        assert abs(slope) < 0.01  # Near-zero slope indicates stability

    def test_calculate_slope_single_value(self) -> None:
        """Test slope calculation with single value."""
        values = [0.5]
        slope = TrendAnalyzer.calculate_slope(values)

        assert slope == 0.0

    def test_calculate_volatility(self) -> None:
        """Test volatility calculation."""
        # High variance values
        values = [0.3, 0.7, 0.3, 0.7, 0.3]
        volatility = TrendAnalyzer.calculate_volatility(values)

        assert volatility > 0  # Should have non-zero volatility

    def test_calculate_volatility_stable(self) -> None:
        """Test volatility calculation with stable values."""
        values = [0.5, 0.5, 0.5, 0.5, 0.5]
        volatility = TrendAnalyzer.calculate_volatility(values)

        assert volatility == 0.0  # No variance

    def test_analyze_trend(self) -> None:
        """Test complete trend analysis."""
        data_points = [
            {"metric_name": "overall_score", "overall_score": 0.5},
            {"metric_name": "overall_score", "overall_score": 0.55},
            {"metric_name": "overall_score", "overall_score": 0.6},
        ]

        trend = TrendAnalyzer.analyze_trend(data_points, "overall_score")

        assert isinstance(trend, TrendData)
        assert trend.metric_name == "overall_score"
        assert len(trend.data_points) == 3
        assert trend.slope > 0  # Improving
        assert trend.latest_value == 0.6
        assert trend.oldest_value == 0.5
        assert trend.change_pct > 0  # Positive change


class TestGovernanceDB:
    """Test GovernanceDB functionality (requires SQLite)."""

    @pytest.mark.skipif(not SQLITE_AVAILABLE, reason="SQLite not available")
    def test_init_schema(self) -> None:
        """Test database schema initialization."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            db = GovernanceDB(db_path)
            db.connect()
            db.init_schema()
            db.close()

            # Verify tables exist
            conn = db_path
            import sqlite3

            c = sqlite3.connect(str(conn))
            cursor = c.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            c.close()

            assert "governance_metrics" in tables
            assert "schema_version" in tables
        finally:
            db_path.unlink(missing_ok=True)

    @pytest.mark.skipif(not SQLITE_AVAILABLE, reason="SQLite not available")
    def test_insert_and_retrieve_metric(self) -> None:
        """Test inserting and retrieving a metric."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            db = GovernanceDB(db_path)
            db.connect()
            db.init_schema()

            metric = GovernanceMetric(
                repository_name="test-repo",
                repository_path="/path/to/test",
                language="python",
                size_category="medium",
                complexity="medium",
                overall_score=0.75,
                structural_score=0.70,
                quality_score=0.80,
                acceptance_blocked=False,
                total_gaps=5,
                critical_gaps=0,
                major_gaps=2,
                benchmark_date=datetime.now(UTC).isoformat(),
                fixture_hash="abc123",
            )

            metric_id = db.insert_metric(metric)
            assert metric_id > 0

            # Query the metric
            cursor = db._conn.cursor()
            cursor.execute("SELECT * FROM governance_metrics WHERE id = ?", (metric_id,))
            row = cursor.fetchone()
            db.close()

            assert row is not None
            assert row["repository_name"] == "test-repo"
            assert row["overall_score"] == 0.75
        finally:
            db_path.unlink(missing_ok=True)

    @pytest.mark.skipif(not SQLITE_AVAILABLE, reason="SQLite not available")
    def test_import_from_benchmark_matrix(self) -> None:
        """Test importing data from benchmark matrix JSON."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            matrix_data = {
                "generated_at": "2026-04-18T00:00:00Z",
                "results": [
                    {
                        "repository": {
                            "name": "repo1",
                            "path": "/path/to/repo1",
                            "language": "python",
                            "size": "medium",
                            "complexity": "medium",
                        },
                        "overall_score": 0.75,
                        "structural_score": 0.70,
                        "quality_score": 0.80,
                        "acceptance_blocked": False,
                        "gaps": [
                            {"severity": "MAJOR"},
                            {"severity": "MINOR"},
                        ],
                    },
                    {
                        "repository": {
                            "name": "repo2",
                            "path": "/path/to/repo2",
                            "language": "javascript",
                            "size": "small",
                            "complexity": "low",
                        },
                        "overall_score": 0.60,
                        "structural_score": 0.55,
                        "quality_score": 0.65,
                        "acceptance_blocked": True,
                        "gaps": [
                            {"severity": "CRITICAL"},
                            {"severity": "MAJOR"},
                            {"severity": "MAJOR"},
                        ],
                    },
                ],
            }

            db = GovernanceDB(db_path)
            db.connect()
            db.init_schema()
            count = db.import_from_benchmark_matrix(matrix_data)
            db.close()

            assert count == 2  # Two repositories imported
        finally:
            db_path.unlink(missing_ok=True)


class TestSQLiteAvailability:
    """Test SQLite availability check."""

    def test_sqlite_available_flag(self) -> None:
        """Test that SQLITE_AVAILABLE is correctly set."""
        # This test just verifies the flag exists
        assert isinstance(SQLITE_AVAILABLE, bool)
