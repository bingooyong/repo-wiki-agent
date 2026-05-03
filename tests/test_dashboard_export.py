"""Tests for dashboard export functionality."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from scripts.qoder_governance_dashboard import (
    GovernanceDashboard,
    GovernanceDB,
    GovernanceMetric,
)


@pytest.fixture
def dashboard_with_data(tmp_path):
    """Set up dashboard with test data."""
    db_path = tmp_path / "dashboard.db"
    db = GovernanceDB(db_path)
    db.connect()
    db.init_schema()

    base_date = datetime.now(UTC)

    # Add test repositories
    repos = [
        {
            "name": "alpha-service",
            "path": "/path/to/alpha",
            "language": "python",
            "size": "medium",
            "complexity": "medium",
            "scores": (0.72, 0.68, 0.76),
            "blocked": False,
            "gaps": (2, 0, 1),
        },
        {
            "name": "beta-service",
            "path": "/path/to/beta",
            "language": "typescript",
            "size": "small",
            "complexity": "low",
            "scores": (0.45, 0.42, 0.40),
            "blocked": True,
            "gaps": (8, 2, 4),
        },
        {
            "name": "gamma-service",
            "path": "/path/to/gamma",
            "language": "java",
            "size": "large",
            "complexity": "high",
            "scores": (0.80, 0.78, 0.82),
            "blocked": False,
            "gaps": (1, 0, 0),
        },
    ]

    for repo in repos:
        metric = GovernanceMetric(
            repository_name=repo["name"],
            repository_path=repo["path"],
            language=repo["language"],
            size_category=repo["size"],
            complexity=repo["complexity"],
            overall_score=repo["scores"][0],
            structural_score=repo["scores"][1],
            quality_score=repo["scores"][2],
            acceptance_blocked=repo["blocked"],
            total_gaps=repo["gaps"][0],
            critical_gaps=repo["gaps"][1],
            major_gaps=repo["gaps"][2],
            benchmark_date=base_date.isoformat(),
            fixture_hash="test_hash",
        )
        db.insert_metric(metric)

    db.close()
    return db_path


class TestDashboardExport:
    """Tests for dashboard export functionality."""

    def test_export_human_readable(self, dashboard_with_data):
        """Test exporting human-readable markdown report."""
        dashboard = GovernanceDashboard(dashboard_with_data)
        report = dashboard.export_human_readable()
        dashboard.close()

        assert "Governance Dashboard Report" in report
        assert "Latest Metrics" in report
        assert "alpha-service" in report
        assert "beta-service" in report
        assert "gamma-service" in report

    def test_export_machine_readable(self, dashboard_with_data):
        """Test exporting machine-readable JSON."""
        dashboard = GovernanceDashboard(dashboard_with_data)
        data = dashboard.export_machine_readable()
        dashboard.close()

        assert "generated_at" in data
        assert "repository_count" in data
        assert "latest_metrics" in data
        assert "trends" in data

        assert data["repository_count"] == 3
        assert len(data["latest_metrics"]) == 3

    def test_export_json_format(self, dashboard_with_data):
        """Test JSON export format is valid."""
        dashboard = GovernanceDashboard(dashboard_with_data)
        data = dashboard.export_machine_readable()
        dashboard.close()

        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        parsed = json.loads(json_str)

        assert parsed["repository_count"] == 3
        assert len(parsed["latest_metrics"]) == 3

    def test_export_trends_structure(self, dashboard_with_data):
        """Test trends in machine-readable export."""
        dashboard = GovernanceDashboard(dashboard_with_data)
        data = dashboard.export_machine_readable()
        dashboard.close()

        trends = data["trends"]
        assert isinstance(trends, dict)

        for key, trend in trends.items():
            assert "metric_name" in trend
            assert "slope" in trend
            assert "volatility" in trend
            assert "latest_value" in trend
            assert "oldest_value" in trend
            assert "change_pct" in trend

    def test_export_includes_scores(self, dashboard_with_data):
        """Test that export includes quality scores."""
        dashboard = GovernanceDashboard(dashboard_with_data)
        data = dashboard.export_machine_readable()
        dashboard.close()

        latest = data["latest_metrics"]
        for metric in latest:
            assert "overall_score" in metric
            assert "structural_score" in metric
            assert "quality_score" in metric

    def test_export_blocked_status(self, dashboard_with_data):
        """Test that blocked status is exported correctly."""
        dashboard = GovernanceDashboard(dashboard_with_data)
        data = dashboard.export_machine_readable()
        dashboard.close()

        latest = data["latest_metrics"]
        beta = next(m for m in latest if m["repository_name"] == "beta-service")
        gamma = next(m for m in latest if m["repository_name"] == "gamma-service")

        assert beta["acceptance_blocked"] == 1
        assert gamma["acceptance_blocked"] == 0


class TestDashboardQuery:
    """Tests for dashboard query functionality."""

    def test_query_latest_all_repos(self, dashboard_with_data):
        """Test querying latest metrics for all repositories."""
        dashboard = GovernanceDashboard(dashboard_with_data)
        latest = dashboard.query_latest()
        dashboard.close()

        assert len(latest) == 3
        repo_names = {m["repository_name"] for m in latest}
        assert repo_names == {"alpha-service", "beta-service", "gamma-service"}

    def test_query_latest_filtered(self, dashboard_with_data):
        """Test querying latest metrics filtered by repository."""
        dashboard = GovernanceDashboard(dashboard_with_data)
        latest = dashboard.query_latest(repository_name="alpha-service")
        dashboard.close()

        assert len(latest) == 1
        assert latest[0]["repository_name"] == "alpha-service"

    def test_query_trends_all_repos(self, dashboard_with_data):
        """Test querying trends for all repositories."""
        dashboard = GovernanceDashboard(dashboard_with_data)
        trends = dashboard.query_trends()
        dashboard.close()

        assert len(trends) > 0

    def test_query_trends_filtered(self, dashboard_with_data):
        """Test querying trends filtered by repository."""
        dashboard = GovernanceDashboard(dashboard_with_data)
        trends = dashboard.query_trends(repository_name="beta-service")
        dashboard.close()

        # Should have trends for beta-service only
        beta_keys = [k for k in trends.keys() if "beta-service" in k]
        assert len(beta_keys) > 0


class TestDashboardExportEdgeCases:
    """Edge case tests for dashboard export."""

    def test_export_empty_dashboard(self, tmp_path):
        """Test exporting empty dashboard."""
        db_path = tmp_path / "empty.db"
        db = GovernanceDB(db_path)
        db.connect()
        db.init_schema()
        db.close()

        dashboard = GovernanceDashboard(db_path)

        md_report = dashboard.export_human_readable()
        assert "No metrics recorded" in md_report or "Governance Dashboard Report" in md_report

        data = dashboard.export_machine_readable()
        assert data["repository_count"] == 0
        assert len(data["latest_metrics"]) == 0

        dashboard.close()

    def test_export_no_output_path(self, dashboard_with_data):
        """Test that export works without output file path."""
        dashboard = GovernanceDashboard(dashboard_with_data)

        # These should not raise even without output path
        md_report = dashboard.export_human_readable()
        data = dashboard.export_machine_readable()

        assert isinstance(md_report, str)
        assert isinstance(data, dict)

        dashboard.close()


class TestDashboardPersistence:
    """Tests for dashboard data persistence."""

    def test_data_persists_after_reopen(self, tmp_path):
        """Test that data persists after closing and reopening."""
        db_path = tmp_path / "persist.db"
        db = GovernanceDB(db_path)
        db.connect()
        db.init_schema()

        metric = GovernanceMetric(
            repository_name="persist-test",
            repository_path="/path/to/persist",
            language="python",
            size_category="medium",
            complexity="medium",
            overall_score=0.75,
            structural_score=0.70,
            quality_score=0.80,
            acceptance_blocked=False,
            total_gaps=2,
            critical_gaps=0,
            major_gaps=1,
            benchmark_date=datetime.now(UTC).isoformat(),
            fixture_hash="persist_hash",
        )
        db.insert_metric(metric)
        db.close()

        # Reopen dashboard
        dashboard = GovernanceDashboard(db_path)
        latest = dashboard.query_latest(repository_name="persist-test")
        dashboard.close()

        assert len(latest) == 1
        assert latest[0]["repository_name"] == "persist-test"
        assert latest[0]["overall_score"] == 0.75

    def test_multiple_inserts_same_repo(self, tmp_path):
        """Test that multiple metrics for same repo are tracked."""
        db_path = tmp_path / "multi_insert.db"
        db = GovernanceDB(db_path)
        db.connect()
        db.init_schema()

        base_date = datetime.now(UTC)

        # Insert with different dates to simulate time progression
        dates = [
            base_date - timedelta(hours=2),
            base_date - timedelta(hours=1),
            base_date,
        ]
        scores = [0.50, 0.55, 0.60]

        for score, date in zip(scores, dates, strict=False):
            metric = GovernanceMetric(
                repository_name="multi-insert",
                repository_path="/path/to/multi",
                language="python",
                size_category="medium",
                complexity="medium",
                overall_score=score,
                structural_score=score,
                quality_score=score,
                acceptance_blocked=False,
                total_gaps=5,
                critical_gaps=1,
                major_gaps=2,
                benchmark_date=date.isoformat(),
                fixture_hash=f"hash_{score}",
            )
            db.insert_metric(metric)

        db.close()

        # Query latest should return most recent
        dashboard = GovernanceDashboard(db_path)
        latest = dashboard.query_latest(repository_name="multi-insert")
        dashboard.close()

        assert len(latest) == 1
        assert latest[0]["overall_score"] == 0.60  # Most recent

    def test_concurrent_export_consistency(self, dashboard_with_data):
        """Test that multiple exports return consistent data."""
        dashboard = GovernanceDashboard(dashboard_with_data)

        # Export multiple times
        data1 = dashboard.export_machine_readable()
        data2 = dashboard.export_machine_readable()
        md1 = dashboard.export_human_readable()
        md2 = dashboard.export_human_readable()

        dashboard.close()

        assert data1["repository_count"] == data2["repository_count"]
        assert len(data1["latest_metrics"]) == len(data2["latest_metrics"])

        # Compare core content, not timestamps
        md1_lines = md1.split("\n")
        md2_lines = md2.split("\n")
        assert len(md1_lines) == len(md2_lines)

        # Check key sections are present
        assert any("Latest Metrics" in line for line in md1_lines)
        assert any("Trend Analysis" in line for line in md1_lines)
