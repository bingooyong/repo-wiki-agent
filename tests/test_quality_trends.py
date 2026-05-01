"""Tests for quality trend analysis and persistence."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from scripts.qoder_governance_dashboard import (
    GovernanceDB,
    GovernanceMetric,
    TrendAnalyzer,
    TrendData,
    SQLITE_AVAILABLE,
)


class TestQualityTrendPersistence:
    """Tests for quality trend table persistence."""

    @pytest.fixture
    def db_with_trends(self, tmp_path):
        """Set up database with multiple time-series data points."""
        db_path = tmp_path / "trends.db"
        db = GovernanceDB(db_path)
        db.connect()
        db.init_schema()

        # Insert metrics over 7 days
        base_date = datetime.now(timezone.utc)
        scores = [0.50, 0.52, 0.55, 0.54, 0.58, 0.60, 0.62]

        for i, score in enumerate(scores):
            metric = GovernanceMetric(
                repository_name="quality-test-repo",
                repository_path="/path/to/quality",
                language="python",
                size_category="medium",
                complexity="medium",
                overall_score=score,
                structural_score=score - 0.05,
                quality_score=score + 0.05,
                acceptance_blocked=False,
                total_gaps=10 - i,
                critical_gaps=max(0, 3 - i),
                major_gaps=max(0, 4 - i),
                benchmark_date=(base_date - timedelta(days=6-i)).isoformat(),
                fixture_hash=f"hash_{i}",
            )
            db.insert_metric(metric)

        db.close()
        return db_path

    def test_trend_data_persists(self, db_with_trends):
        """Test that trend data is stored correctly."""
        db = GovernanceDB(db_with_trends)
        db.connect()

        cursor = db._conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM governance_metrics")
        count = cursor.fetchone()["cnt"]
        db.close()

        assert count == 7

    def test_query_trends_for_quality_improvement(self, db_with_trends):
        """Test querying quality trends shows improvement."""
        from scripts.qoder_governance_dashboard import GovernanceDashboard

        dashboard = GovernanceDashboard(db_with_trends)
        trends = dashboard.query_trends(repository_name="quality-test-repo")
        dashboard.close()

        assert len(trends) > 0

        # Find the overall_score trend
        overall_trend = None
        for key, trend in trends.items():
            if "overall_score" in key:
                overall_trend = trend
                break

        assert overall_trend is not None
        assert overall_trend.slope > 0  # Should be improving
        assert overall_trend.change_pct > 0

    def test_trend_stability_detection(self, tmp_path):
        """Test detecting stable quality metrics."""
        db_path = tmp_path / "stable.db"
        db = GovernanceDB(db_path)
        db.connect()
        db.init_schema()

        # Insert stable metrics
        base_date = datetime.now(timezone.utc)
        for i in range(5):
            metric = GovernanceMetric(
                repository_name="stable-repo",
                repository_path="/path/to/stable",
                language="python",
                size_category="medium",
                complexity="medium",
                overall_score=0.70,
                structural_score=0.70,
                quality_score=0.70,
                acceptance_blocked=False,
                total_gaps=5,
                critical_gaps=0,
                major_gaps=1,
                benchmark_date=(base_date - timedelta(days=4-i)).isoformat(),
                fixture_hash=f"hash_{i}",
            )
            db.insert_metric(metric)

        db.close()

        from scripts.qoder_governance_dashboard import GovernanceDashboard

        dashboard = GovernanceDashboard(db_path)
        trends = dashboard.query_trends(repository_name="stable-repo")
        dashboard.close()

        # Find overall_score trend
        overall_trend = None
        for key, trend in trends.items():
            if "overall_score" in key:
                overall_trend = trend
                break

        assert overall_trend is not None
        assert abs(overall_trend.slope) < 0.01  # Should be stable


class TestTrendCalculation:
    """Tests for trend calculation algorithms."""

    def test_slope_calculation_improving(self):
        """Test slope positive for improving trend."""
        values = [0.40, 0.45, 0.50, 0.55, 0.60]
        slope = TrendAnalyzer.calculate_slope(values)
        assert slope > 0

    def test_slope_calculation_declining(self):
        """Test slope negative for declining trend."""
        values = [0.60, 0.55, 0.50, 0.45, 0.40]
        slope = TrendAnalyzer.calculate_slope(values)
        assert slope < 0

    def test_slope_calculation_stable(self):
        """Test slope near zero for stable trend."""
        values = [0.50, 0.50, 0.50, 0.50, 0.50]
        slope = TrendAnalyzer.calculate_slope(values)
        assert abs(slope) < 0.001

    def test_volatility_calculation(self):
        """Test volatility calculation."""
        # High volatility
        values = [0.30, 0.70, 0.30, 0.70, 0.30]
        volatility = TrendAnalyzer.calculate_volatility(values)
        assert volatility > 0.1

        # Low volatility
        values = [0.50, 0.51, 0.49, 0.50, 0.50]
        volatility = TrendAnalyzer.calculate_volatility(values)
        assert volatility < 0.05

    def test_change_percentage_calculation(self):
        """Test change percentage calculation."""
        data_points = [
            {"metric_name": "quality_score", "quality_score": 0.50},
            {"metric_name": "quality_score", "quality_score": 0.60},
        ]
        trend = TrendAnalyzer.analyze_trend(data_points, "quality_score")
        assert trend.change_pct == pytest.approx(20.0, rel=0.1)


class TestMultiRepoTrends:
    """Tests for multi-repository trend analysis."""

    @pytest.fixture
    def multi_repo_db(self, tmp_path):
        """Set up database with multiple repositories."""
        db_path = tmp_path / "multi_repo.db"
        db = GovernanceDB(db_path)
        db.connect()
        db.init_schema()

        base_date = datetime.now(timezone.utc)

        # Repository 1 - improving
        for i in range(5):
            metric = GovernanceMetric(
                repository_name="repo-alpha",
                repository_path="/path/to/alpha",
                language="python",
                size_category="medium",
                complexity="medium",
                overall_score=0.50 + i * 0.02,
                structural_score=0.50 + i * 0.02,
                quality_score=0.50 + i * 0.02,
                acceptance_blocked=False,
                total_gaps=5 - i,
                critical_gaps=1,
                major_gaps=2,
                benchmark_date=(base_date - timedelta(days=4-i)).isoformat(),
                fixture_hash=f"alpha_{i}",
            )
            db.insert_metric(metric)

        # Repository 2 - declining
        for i in range(5):
            metric = GovernanceMetric(
                repository_name="repo-beta",
                repository_path="/path/to/beta",
                language="javascript",
                size_category="small",
                complexity="high",
                overall_score=0.70 - i * 0.03,
                structural_score=0.70 - i * 0.03,
                quality_score=0.70 - i * 0.03,
                acceptance_blocked=False,
                total_gaps=2 + i,
                critical_gaps=0,
                major_gaps=1,
                benchmark_date=(base_date - timedelta(days=4-i)).isoformat(),
                fixture_hash=f"beta_{i}",
            )
            db.insert_metric(metric)

        db.close()
        return db_path

    def test_multi_repo_trend_calculation(self, multi_repo_db):
        """Test trend calculation for multiple repositories."""
        from scripts.qoder_governance_dashboard import GovernanceDashboard

        dashboard = GovernanceDashboard(multi_repo_db)

        # Query trends for each repo separately since keys differ based on filter
        alpha_trends = dashboard.query_trends(repository_name="repo-alpha")
        beta_trends = dashboard.query_trends(repository_name="repo-beta")
        dashboard.close()

        assert len(alpha_trends) > 0
        assert len(beta_trends) > 0

        # Check alpha is improving - key format is "{repo_name}_{metric}"
        alpha_overall = alpha_trends.get("repo-alpha_overall_score")
        assert alpha_overall is not None
        assert alpha_overall.slope > 0

        # Check beta is declining
        beta_overall = beta_trends.get("repo-beta_overall_score")
        assert beta_overall is not None
        assert beta_overall.slope < 0


class TestTrendPersistenceEdgeCases:
    """Edge case tests for trend persistence."""

    def test_empty_database(self, tmp_path):
        """Test querying empty database."""
        db_path = tmp_path / "empty.db"
        db = GovernanceDB(db_path)
        db.connect()
        db.init_schema()
        db.close()

        from scripts.qoder_governance_dashboard import GovernanceDashboard

        dashboard = GovernanceDashboard(db_path)
        trends = dashboard.query_trends()
        dashboard.close()

        assert len(trends) == 0

    def test_single_data_point(self, tmp_path):
        """Test trend with single data point."""
        db_path = tmp_path / "single.db"
        db = GovernanceDB(db_path)
        db.connect()
        db.init_schema()

        metric = GovernanceMetric(
            repository_name="single-repo",
            repository_path="/path/to/single",
            language="python",
            size_category="medium",
            complexity="medium",
            overall_score=0.75,
            structural_score=0.70,
            quality_score=0.80,
            acceptance_blocked=False,
            total_gaps=3,
            critical_gaps=0,
            major_gaps=1,
            benchmark_date=datetime.now(timezone.utc).isoformat(),
            fixture_hash="single_hash",
        )
        db.insert_metric(metric)
        db.close()

        from scripts.qoder_governance_dashboard import GovernanceDashboard

        dashboard = GovernanceDashboard(db_path)
        trends = dashboard.query_trends(repository_name="single-repo")
        dashboard.close()

        # Single point should have zero slope
        overall_trend = None
        for key, trend in trends.items():
            if "overall_score" in key:
                overall_trend = trend
                break

        if overall_trend:
            assert overall_trend.slope == 0.0

    def test_trend_with_missing_dates(self, tmp_path):
        """Test trend calculation with non-consecutive dates."""
        db_path = tmp_path / "sparse.db"
        db = GovernanceDB(db_path)
        db.connect()
        db.init_schema()

        dates = [
            "2026-04-01T00:00:00Z",
            "2026-04-05T00:00:00Z",
            "2026-04-10T00:00:00Z",
        ]
        scores = [0.50, 0.60, 0.70]

        for date, score in zip(dates, scores):
            metric = GovernanceMetric(
                repository_name="sparse-repo",
                repository_path="/path/to/sparse",
                language="python",
                size_category="medium",
                complexity="medium",
                overall_score=score,
                structural_score=score,
                quality_score=score,
                acceptance_blocked=False,
                total_gaps=5,
                critical_gaps=0,
                major_gaps=2,
                benchmark_date=date,
                fixture_hash="sparse_hash",
            )
            db.insert_metric(metric)

        db.close()

        from scripts.qoder_governance_dashboard import GovernanceDashboard

        dashboard = GovernanceDashboard(db_path)
        trends = dashboard.query_trends(repository_name="sparse-repo")
        dashboard.close()

        overall_trend = None
        for key, trend in trends.items():
            if "overall_score" in key:
                overall_trend = trend
                break

        assert overall_trend is not None
        assert overall_trend.slope > 0