#!/usr/bin/env python3
"""
Qoder Governance Dashboard Tool (Phase 14)

Provides SQLite-backed trend analysis and dashboard export for governance metrics.

Key Features:
- Export governance metrics to SQLite for trend analysis
- Dashboard query layer for verify/compare trends
- Export to human-readable and machine-readable formats
- Validate trend queries against historical run data

Usage:
    python scripts/qoder_governance_dashboard.py \
        --init \
        --db-path /path/to/governance.db

    python scripts/qoder_governance_dashboard.py \
        --import /path/to/benchmark_matrix.json \
        --db-path /path/to/governance.db

    python scripts/qoder_governance_dashboard.py \
        --query trends \
        --db-path /path/to/governance.db \
        --output /path/to/trends.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Try to import sqlite3, but provide fallback for environments where it's not available
try:
    import sqlite3
    SQLITE_AVAILABLE = True
except ImportError:
    SQLITE_AVAILABLE = False


# Schema version for database migrations
SCHEMA_VERSION = "1.0"


@dataclass
class GovernanceMetric:
    """A governance metric for tracking over time."""
    id: int | None = None
    repository_name: str = ""
    repository_path: str = ""
    language: str = ""
    size_category: str = ""
    complexity: str = ""
    overall_score: float = 0.0
    structural_score: float = 0.0
    quality_score: float = 0.0
    acceptance_blocked: bool = False
    total_gaps: int = 0
    critical_gaps: int = 0
    major_gaps: int = 0
    benchmark_date: str = ""
    fixture_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "repository_name": self.repository_name,
            "repository_path": self.repository_path,
            "language": self.language,
            "size_category": self.size_category,
            "complexity": self.complexity,
            "overall_score": self.overall_score,
            "structural_score": self.structural_score,
            "quality_score": self.quality_score,
            "acceptance_blocked": self.acceptance_blocked,
            "total_gaps": self.total_gaps,
            "critical_gaps": self.critical_gaps,
            "major_gaps": self.major_gaps,
            "benchmark_date": self.benchmark_date,
            "fixture_hash": self.fixture_hash,
        }


@dataclass
class TrendData:
    """Trend data for a specific metric."""
    metric_name: str
    data_points: list[dict[str, Any]]
    slope: float  # positive = improving, negative = declining
    volatility: float  # standard deviation
    latest_value: float
    oldest_value: float
    change_pct: float  # percentage change

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "data_points": self.data_points,
            "slope": round(self.slope, 4),
            "volatility": round(self.volatility, 4),
            "latest_value": round(self.latest_value, 3),
            "oldest_value": round(self.oldest_value, 3),
            "change_pct": round(self.change_pct, 1),
        }


class GovernanceDB:
    """SQLite-backed governance database."""

    def __init__(self, db_path: Path) -> None:
        if not SQLITE_AVAILABLE:
            raise ImportError("sqlite3 module is not available. Please install Python with SQLite support.")

        self.db_path = db_path
        self._conn = None

    def connect(self) -> None:
        """Connect to the database and create schema if needed."""
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def init_schema(self) -> None:
        """Initialize database schema."""
        if not self._conn:
            self.connect()

        cursor = self._conn.cursor()

        # Governance metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS governance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repository_name TEXT NOT NULL,
                repository_path TEXT NOT NULL,
                language TEXT,
                size_category TEXT,
                complexity TEXT,
                overall_score REAL NOT NULL,
                structural_score REAL NOT NULL,
                quality_score REAL NOT NULL,
                acceptance_blocked INTEGER NOT NULL,
                total_gaps INTEGER DEFAULT 0,
                critical_gaps INTEGER DEFAULT 0,
                major_gaps INTEGER DEFAULT 0,
                benchmark_date TEXT NOT NULL,
                fixture_hash TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_repository_name
            ON governance_metrics(repository_name)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_benchmark_date
            ON governance_metrics(benchmark_date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_language
            ON governance_metrics(language)
        """)

        # Schema version table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version TEXT PRIMARY KEY,
                applied_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Record schema version
        cursor.execute("""
            INSERT OR IGNORE INTO schema_version (version) VALUES (?)
        """, (SCHEMA_VERSION,))

        self._conn.commit()

    def insert_metric(self, metric: GovernanceMetric) -> int:
        """Insert a governance metric and return its ID."""
        if not self._conn:
            self.connect()

        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO governance_metrics (
                repository_name, repository_path, language, size_category,
                complexity, overall_score, structural_score, quality_score,
                acceptance_blocked, total_gaps, critical_gaps, major_gaps,
                benchmark_date, fixture_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metric.repository_name,
            metric.repository_path,
            metric.language,
            metric.size_category,
            metric.complexity,
            metric.overall_score,
            metric.structural_score,
            metric.quality_score,
            1 if metric.acceptance_blocked else 0,
            metric.total_gaps,
            metric.critical_gaps,
            metric.major_gaps,
            metric.benchmark_date,
            metric.fixture_hash,
        ))

        self._conn.commit()
        return cursor.lastrowid

    def import_from_benchmark_matrix(self, matrix_data: dict[str, Any]) -> int:
        """Import data from a benchmark matrix JSON."""
        if not self._conn:
            self.connect()

        count = 0
        for result in matrix_data.get("results", []):
            repo = result.get("repository", {})
            metric = GovernanceMetric(
                repository_name=repo.get("name", "unknown"),
                repository_path=repo.get("path", ""),
                language=repo.get("language", "unknown"),
                size_category=repo.get("size", "medium"),
                complexity=repo.get("complexity", "medium"),
                overall_score=result.get("overall_score", 0.0),
                structural_score=result.get("structural_score", 0.0),
                quality_score=result.get("quality_score", 0.0),
                acceptance_blocked=result.get("acceptance_blocked", False),
                total_gaps=len(result.get("gaps", [])),
                critical_gaps=sum(1 for g in result.get("gaps", []) if g.get("severity") == "CRITICAL"),
                major_gaps=sum(1 for g in result.get("gaps", []) if g.get("severity") == "MAJOR"),
                benchmark_date=matrix_data.get("generated_at", datetime.now(timezone.utc).isoformat()),
                fixture_hash="",
            )
            self.insert_metric(metric)
            count += 1

        return count


class TrendAnalyzer:
    """Analyzes trends in governance metrics."""

    @staticmethod
    def calculate_slope(values: list[float]) -> float:
        """Calculate slope of linear trend (simple linear regression)."""
        if len(values) < 2:
            return 0.0

        n = len(values)
        x_values = list(range(n))
        x_mean = sum(x_values) / n
        y_mean = sum(values) / n

        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)

        if denominator == 0:
            return 0.0

        return numerator / denominator

    @staticmethod
    def calculate_volatility(values: list[float]) -> float:
        """Calculate volatility (standard deviation)."""
        if len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return variance ** 0.5

    @classmethod
    def analyze_trend(cls, data_points: list[dict[str, Any]], metric_name: str) -> TrendData:
        """Analyze trend for a specific metric."""
        values = [point.get(metric_name, 0.0) for point in data_points]

        if not values:
            return TrendData(
                metric_name=metric_name,
                data_points=[],
                slope=0.0,
                volatility=0.0,
                latest_value=0.0,
                oldest_value=0.0,
                change_pct=0.0,
            )

        slope = cls.calculate_slope(values)
        volatility = cls.calculate_volatility(values)
        oldest_value = values[0]
        latest_value = values[-1]

        change_pct = 0.0
        if oldest_value != 0:
            change_pct = ((latest_value - oldest_value) / oldest_value) * 100

        return TrendData(
            metric_name=metric_name,
            data_points=data_points,
            slope=slope,
            volatility=volatility,
            latest_value=latest_value,
            oldest_value=oldest_value,
            change_pct=change_pct,
        )


class GovernanceDashboard:
    """Governance dashboard with trend analysis."""

    def __init__(self, db_path: Path) -> None:
        self.db = GovernanceDB(db_path)
        self.db.connect()

    def close(self) -> None:
        """Close database connection."""
        self.db.close()

    def query_trends(
        self,
        repository_name: str | None = None,
        days: int = 30,
    ) -> dict[str, TrendData]:
        """Query trend data for specified repository or all repositories."""
        cursor = self.db._conn.cursor()

        # Build query
        query = """
            SELECT repository_name, benchmark_date, overall_score,
                   structural_score, quality_score, acceptance_blocked,
                   total_gaps, critical_gaps, major_gaps
            FROM governance_metrics
        """
        params = []

        if repository_name:
            query += " WHERE repository_name = ?"
            params.append(repository_name)

        query += " ORDER BY benchmark_date ASC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Group by repository
        by_repo: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            repo_name = row["repository_name"]
            if repo_name not in by_repo:
                by_repo[repo_name] = []
            by_repo[repo_name].append({
                "repository_name": repo_name,
                "benchmark_date": row["benchmark_date"],
                "overall_score": row["overall_score"],
                "structural_score": row["structural_score"],
                "quality_score": row["quality_score"],
                "acceptance_blocked": bool(row["acceptance_blocked"]),
                "total_gaps": row["total_gaps"],
                "critical_gaps": row["critical_gaps"],
                "major_gaps": row["major_gaps"],
            })

        # Analyze trends for each repository
        trends = {}
        for repo_name, data_points in by_repo.items():
            for metric in ["overall_score", "structural_score", "quality_score", "total_gaps"]:
                key = f"{repo_name}_{metric}" if repository_name else f"{metric}"
                trends[key] = TrendAnalyzer.analyze_trend(data_points, metric)

        return trends

    def query_latest(self, repository_name: str | None = None) -> list[dict[str, Any]]:
        """Query latest metrics for repository or all repositories."""
        cursor = self.db._conn.cursor()

        query = """
            SELECT g1.* FROM governance_metrics g1
            INNER JOIN (
                SELECT repository_name, MAX(benchmark_date) as max_date
                FROM governance_metrics
        """
        params = []

        if repository_name:
            query += " WHERE repository_name = ?"
            params.append(repository_name)

        query += """
                GROUP BY repository_name
            ) g2 ON g1.repository_name = g2.repository_name
                   AND g1.benchmark_date = g2.max_date
            ORDER BY g1.repository_name
        """

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def export_human_readable(self) -> str:
        """Export dashboard data as human-readable markdown."""
        latest = self.query_latest()
        trends = self.query_trends()

        lines = [
            "# Governance Dashboard Report",
            "",
            f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
            f"**Repositories Tracked:** {len(latest)}",
            "",
            "---",
            "",
            "## Latest Metrics",
            "",
        ]

        if not latest:
            lines.append("*No metrics recorded yet.*")
        else:
            lines.append("| Repository | Language | Overall | Structural | Quality | Status |")
            lines.append("|------------|----------|---------|------------|---------|--------|")
            for row in latest:
                status = "BLOCKED" if row["acceptance_blocked"] else "READY"
                lines.append(
                    f"| {row['repository_name']} | {row['language']} | "
                    f"{row['overall_score']:.1%} | {row['structural_score']:.1%} | "
                    f"{row['quality_score']:.1%} | {status} |"
                )

        lines.extend([
            "",
            "---",
            "",
            "## Trend Analysis",
            "",
        ])

        if not trends:
            lines.append("*No trend data available.*")
        else:
            for key, trend in trends.items():
                if trend.slope > 0.01:
                    direction = "improving"
                elif trend.slope < -0.01:
                    direction = "declining"
                else:
                    direction = "stable"

                lines.append(f"### {key}")
                lines.append(f"- **Direction:** {direction}")
                lines.append(f"- **Change:** {trend.change_pct:+.1f}% ({trend.oldest_value:.1%} → {trend.latest_value:.1%})")
                lines.append(f"- **Volatility:** {trend.volatility:.3f}")
                lines.append("")

        return "\n".join(lines)

    def export_machine_readable(self) -> dict[str, Any]:
        """Export dashboard data as machine-readable JSON."""
        latest = self.query_latest()
        trends = self.query_trends()

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repository_count": len(latest),
            "latest_metrics": latest,
            "trends": {k: v.to_dict() for k, v in trends.items()},
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Qoder governance dashboard tool")
    parser.add_argument("--db-path", type=Path, required=True, help="Path to SQLite database")
    parser.add_argument("--init", action="store_true", help="Initialize database schema")
    parser.add_argument("--import", dest="import_file", type=Path, help="Import benchmark matrix JSON")
    parser.add_argument("--query", choices=["trends", "latest", "both"], help="Query type")
    parser.add_argument("--repository", type=str, help="Filter by repository name")
    parser.add_argument("--output", type=Path, help="Output path for results")
    parser.add_argument("--format", choices=["json", "markdown", "both"], default="both", help="Output format")

    args = parser.parse_args()

    if not SQLITE_AVAILABLE:
        print("Error: sqlite3 module is not available.", file=sys.stderr)
        print("Please ensure Python is installed with SQLite support.", file=sys.stderr)
        return 1

    # Initialize database
    if args.init:
        db = GovernanceDB(args.db_path)
        db.init_schema()
        db.close()
        print(f"Database initialized at: {args.db_path}")
        return 0

    # Import data
    if args.import_file:
        if not args.import_file.exists():
            print(f"Error: Import file does not exist: {args.import_file}", file=sys.stderr)
            return 1

        matrix_data = json.loads(args.import_file.read_text(encoding="utf-8"))
        db = GovernanceDB(args.db_path)
        db.connect()
        db.init_schema()
        count = db.import_from_benchmark_matrix(matrix_data)
        db.close()
        print(f"Imported {count} metrics from {args.import_file}")
        return 0

    # Query data
    dashboard = GovernanceDashboard(args.db_path)

    try:
        if args.query in ["trends", "both"]:
            trends = dashboard.query_trends(repository_name=args.repository)
            if args.output:
                output_data = {k: v.to_dict() for k, v in trends.items()}
                args.output.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"Trends written to: {args.output}")

        if args.query in ["latest", "both"]:
            latest = dashboard.query_latest(repository_name=args.repository)
            if args.output:
                output_data = {"latest_metrics": latest}
                args.output.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"Latest metrics written to: {args.output}")

        if args.format in ["markdown", "both"] and args.query:
            md_output = dashboard.export_human_readable()
            md_path = args.output.parent / f"{args.output.stem}_report.md" if args.output else None
            if md_path:
                md_path.write_text(md_output, encoding="utf-8")
                print(f"Markdown report written to: {md_path}")
            else:
                print(md_output)

        if args.format in ["json", "both"] and args.query:
            json_output = dashboard.export_machine_readable()
            json_path = args.output.parent / f"{args.output.stem}_data.json" if args.output else None
            if json_path:
                json_path.write_text(json.dumps(json_output, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"JSON data written to: {json_path}")
            else:
                print(json.dumps(json_output, ensure_ascii=False, indent=2))

    finally:
        dashboard.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
