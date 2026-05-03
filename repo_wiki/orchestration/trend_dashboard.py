"""Parity regression dashboard and SQLite trend persistence (Phase 29).

Persists `ParityReport` snapshots over time, computes run-to-run deltas, and
exports JSON dashboard payloads for governance review.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from repo_wiki.verifier.qoder_parity_metrics import (
    MetricCategory,
    MetricResult,
    MetricSeverity,
    MetricStatus,
    ParityReport,
    load_parity_report,
)

SCHEMA_VERSION = "parity_trends_v1"


def default_parity_trends_db(repo_root: Path) -> Path:
    """Default SQLite path under `.repo-wiki/index`."""
    root = repo_root.resolve()
    idx = root / ".repo-wiki" / "index"
    idx.mkdir(parents=True, exist_ok=True)
    return idx / "parity_trends.sqlite3"


def _norm_target(path_str: str) -> str:
    return Path(path_str).expanduser().resolve().as_posix()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def parity_report_from_dict(data: dict[str, Any]) -> ParityReport:
    """Build :class:`ParityReport` from a mapping (same shape as saved JSON)."""
    report = ParityReport(
        target_root=Path(data["target_root"]),
        baseline_root=Path(data["baseline_root"]) if data.get("baseline_root") else None,
        run_id=data["run_id"],
        generated_at=data["generated_at"],
        blocked=data.get("blocked", False),
        blocking_reasons=data.get("blocking_reasons", []),
    )
    for m in data.get("metrics", []):
        report.add_metric(
            MetricResult(
                metric_name=m["metric_name"],
                status=MetricStatus(m["status"]),
                score=m["score"],
                measured_value=m["measured_value"],
                threshold=m["threshold"],
                severity=MetricSeverity(m["severity"]),
                category=MetricCategory(m["category"]),
                gaps=m.get("gaps", []),
                details=m.get("details", {}),
            )
        )
    report.summary = data.get("summary", {})
    return report


@dataclass
class RecordRunResult:
    """Outcome of recording one parity run."""

    run_row_id: int
    run_id: str
    target_root: str
    delta: dict[str, Any] | None


class ParityTrendStore:
    """SQLite store for parity runs, per-metric snapshots, and run deltas."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_schema(self, conn: sqlite3.Connection | None = None) -> None:
        """Create tables if missing."""
        own = conn is None
        if own:
            conn = self.connect()
        assert conn is not None
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS parity_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL UNIQUE,
                    target_root TEXT NOT NULL,
                    baseline_root TEXT,
                    generated_at TEXT NOT NULL,
                    inserted_at TEXT NOT NULL,
                    overall_score REAL,
                    structural_score REAL,
                    quality_score REAL,
                    content_score REAL,
                    pass_rate REAL,
                    passed INTEGER,
                    failed INTEGER,
                    partial INTEGER,
                    total_metrics INTEGER,
                    blocked INTEGER NOT NULL,
                    full_report_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_parity_runs_target
                    ON parity_runs(target_root, generated_at DESC);

                CREATE TABLE IF NOT EXISTS parity_metric_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_row_id INTEGER NOT NULL REFERENCES parity_runs(id) ON DELETE CASCADE,
                    metric_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL,
                    score REAL NOT NULL,
                    measured_value REAL NOT NULL,
                    UNIQUE(run_row_id, metric_name)
                );

                CREATE INDEX IF NOT EXISTS idx_parity_metrics_name
                    ON parity_metric_snapshots(metric_name, run_row_id);

                CREATE TABLE IF NOT EXISTS parity_run_deltas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_root TEXT NOT NULL,
                    from_run_row_id INTEGER NOT NULL REFERENCES parity_runs(id) ON DELETE CASCADE,
                    to_run_row_id INTEGER NOT NULL REFERENCES parity_runs(id) ON DELETE CASCADE,
                    computed_at TEXT NOT NULL,
                    delta_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_parity_deltas_target
                    ON parity_run_deltas(target_root, computed_at DESC);
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
                ("schema_version", SCHEMA_VERSION),
            )
            conn.commit()
        finally:
            if own:
                conn.close()

    def _ensure_summary(self, report: ParityReport) -> dict[str, Any]:
        if not report.summary:
            report.compute_summary()
        return report.summary

    def _fetch_previous_run(self, conn: sqlite3.Connection, target_root: str) -> sqlite3.Row | None:
        row = conn.execute(
            """
            SELECT * FROM parity_runs
            WHERE target_root = ?
            ORDER BY generated_at DESC, inserted_at DESC
            LIMIT 1
            """,
            (target_root,),
        ).fetchone()
        return row

    def _metrics_for_run(
        self, conn: sqlite3.Connection, run_row_id: int
    ) -> dict[str, dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT metric_name, category, status, score, measured_value
            FROM parity_metric_snapshots
            WHERE run_row_id = ?
            """,
            (run_row_id,),
        ).fetchall()
        return {r["metric_name"]: dict(r) for r in rows}

    def _compute_delta(
        self,
        prev_summary: dict[str, Any],
        new_summary: dict[str, Any],
        prev_metrics: dict[str, dict[str, Any]],
        new_metrics: dict[str, dict[str, Any]],
        *,
        from_run_id: str,
        to_run_id: str,
    ) -> dict[str, Any]:
        keys = (
            "overall_score",
            "structural_score",
            "quality_score",
            "content_score",
            "pass_rate",
        )
        summary_delta: dict[str, float] = {}
        for k in keys:
            a = prev_summary.get(k)
            b = new_summary.get(k)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                summary_delta[k] = round(float(b) - float(a), 6)

        metric_delta: dict[str, dict[str, float]] = {}
        names = sorted(set(prev_metrics) | set(new_metrics))
        for name in names:
            pa = prev_metrics.get(name, {}).get("score")
            pb = new_metrics.get(name, {}).get("score")
            if isinstance(pa, (int, float)) and isinstance(pb, (int, float)):
                metric_delta[name] = {
                    "score_delta": round(float(pb) - float(pa), 6),
                    "prev_score": round(float(pa), 6),
                    "new_score": round(float(pb), 6),
                }

        return {
            "from_run_id": from_run_id,
            "to_run_id": to_run_id,
            "summary_delta": summary_delta,
            "metrics_delta": metric_delta,
        }

    def record_run(self, report: ParityReport) -> RecordRunResult:
        """Insert one parity run; compute delta vs previous run for same target."""
        if not report.summary:
            report.compute_summary()
        summary = report.summary
        target = _norm_target(str(report.target_root))
        baseline = _norm_target(str(report.baseline_root)) if report.baseline_root else None
        full_json = json.dumps(report.to_dict(), ensure_ascii=False)

        conn = self.connect()
        try:
            prev = self._fetch_previous_run(conn, target)

            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO parity_runs (
                    run_id, target_root, baseline_root, generated_at, inserted_at,
                    overall_score, structural_score, quality_score, content_score,
                    pass_rate, passed, failed, partial, total_metrics, blocked,
                    full_report_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.run_id,
                    target,
                    baseline,
                    report.generated_at,
                    _now_iso(),
                    summary.get("overall_score"),
                    summary.get("structural_score"),
                    summary.get("quality_score"),
                    summary.get("content_score"),
                    summary.get("pass_rate"),
                    summary.get("passed"),
                    summary.get("failed"),
                    summary.get("partial"),
                    summary.get("total_metrics"),
                    1 if report.blocked else 0,
                    full_json,
                ),
            )
            run_row_id = int(cur.lastrowid)

            for m in report.metrics:
                cur.execute(
                    """
                    INSERT INTO parity_metric_snapshots (
                        run_row_id, metric_name, category, status, score, measured_value
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_row_id,
                        m.metric_name,
                        m.category.value,
                        m.status.value,
                        m.score,
                        m.measured_value,
                    ),
                )

            delta: dict[str, Any] | None = None
            if prev is not None:
                prev_summary = json.loads(prev["full_report_json"])["summary"]
                new_metrics = self._metrics_for_run(conn, run_row_id)
                prev_metrics = self._metrics_for_run(conn, int(prev["id"]))
                delta = self._compute_delta(
                    prev_summary,
                    summary,
                    prev_metrics,
                    new_metrics,
                    from_run_id=str(prev["run_id"]),
                    to_run_id=report.run_id,
                )
                cur.execute(
                    """
                    INSERT INTO parity_run_deltas (
                        target_root, from_run_row_id, to_run_row_id, computed_at, delta_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        target,
                        int(prev["id"]),
                        run_row_id,
                        _now_iso(),
                        json.dumps(delta, ensure_ascii=False),
                    ),
                )

            conn.commit()
            return RecordRunResult(
                run_row_id=run_row_id,
                run_id=report.run_id,
                target_root=target,
                delta=delta,
            )
        finally:
            conn.close()

    def list_runs(self, target_root: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """List stored runs (newest first)."""
        conn = self.connect()
        try:
            if target_root:
                tr = _norm_target(target_root)
                rows = conn.execute(
                    """
                    SELECT id, run_id, target_root, generated_at, inserted_at,
                           overall_score, structural_score, quality_score, content_score,
                           pass_rate, blocked, total_metrics
                    FROM parity_runs
                    WHERE target_root = ?
                    ORDER BY generated_at DESC, inserted_at DESC
                    LIMIT ?
                    """,
                    (tr, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, run_id, target_root, generated_at, inserted_at,
                           overall_score, structural_score, quality_score, content_score,
                           pass_rate, blocked, total_metrics
                    FROM parity_runs
                    ORDER BY generated_at DESC, inserted_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def dimension_trend(
        self,
        target_root: str,
        metric_name: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Time series for one metric on one target (oldest → newest)."""
        tr = _norm_target(target_root)
        conn = self.connect()
        try:
            rows = conn.execute(
                """
                SELECT r.run_id, r.generated_at, m.score, m.measured_value, m.status
                FROM parity_metric_snapshots m
                JOIN parity_runs r ON r.id = m.run_row_id
                WHERE r.target_root = ? AND m.metric_name = ?
                ORDER BY r.generated_at ASC, r.inserted_at ASC
                LIMIT ?
                """,
                (tr, metric_name, limit),
            ).fetchall()
            return [dict(x) for x in rows]
        finally:
            conn.close()

    def latest_delta(self, target_root: str) -> dict[str, Any] | None:
        """Most recent delta row for a target."""
        tr = _norm_target(target_root)
        conn = self.connect()
        try:
            row = conn.execute(
                """
                SELECT delta_json, computed_at, from_run_row_id, to_run_row_id
                FROM parity_run_deltas
                WHERE target_root = ?
                ORDER BY computed_at DESC
                LIMIT 1
                """,
                (tr,),
            ).fetchone()
            if not row:
                return None
            out = json.loads(row["delta_json"])
            out["computed_at"] = row["computed_at"]
            out["from_run_row_id"] = row["from_run_row_id"]
            out["to_run_row_id"] = row["to_run_row_id"]
            return out
        finally:
            conn.close()

    def list_deltas(self, target_root: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Recent deltas for a target."""
        tr = _norm_target(target_root)
        conn = self.connect()
        try:
            rows = conn.execute(
                """
                SELECT delta_json, computed_at
                FROM parity_run_deltas
                WHERE target_root = ?
                ORDER BY computed_at DESC
                LIMIT ?
                """,
                (tr, limit),
            ).fetchall()
            out: list[dict[str, Any]] = []
            for r in rows:
                d = json.loads(r["delta_json"])
                d["computed_at"] = r["computed_at"]
                out.append(d)
            return out
        finally:
            conn.close()


def build_dashboard_payload(
    store: ParityTrendStore,
    *,
    target_root: str | None = None,
    dimension_sample_limit: int = 50,
) -> dict[str, Any]:
    """Aggregate runs, per-dimension trends, and deltas for export / review."""
    runs = store.list_runs(target_root=target_root, limit=200)
    metric_names: set[str] = set()
    conn = store.connect()
    try:
        if target_root:
            tr = _norm_target(target_root)
            mrows = conn.execute(
                """
                SELECT DISTINCT metric_name FROM parity_metric_snapshots m
                JOIN parity_runs r ON r.id = m.run_row_id
                WHERE r.target_root = ?
                """,
                (tr,),
            ).fetchall()
        else:
            mrows = conn.execute(
                "SELECT DISTINCT metric_name FROM parity_metric_snapshots"
            ).fetchall()
        metric_names = {r[0] for r in mrows}
    finally:
        conn.close()

    dimension_trends: dict[str, list[dict[str, Any]]] = {}
    tr_for_series = target_root or (runs[0]["target_root"] if runs else None)
    if tr_for_series:
        for name in sorted(metric_names):
            dimension_trends[name] = store.dimension_trend(
                tr_for_series,
                name,
                limit=dimension_sample_limit,
            )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": _now_iso(),
        "target_root_filter": _norm_target(target_root) if target_root else None,
        "runs": runs,
        "dimension_trends": dimension_trends,
    }
    if tr_for_series:
        payload["latest_delta"] = store.latest_delta(tr_for_series)
        payload["recent_deltas"] = store.list_deltas(tr_for_series, limit=30)
    else:
        payload["latest_delta"] = None
        payload["recent_deltas"] = []
    return payload


def export_dashboard_json(
    store: ParityTrendStore,
    output_path: Path,
    *,
    target_root: str | None = None,
) -> None:
    """Write dashboard JSON for Manager review."""
    payload = build_dashboard_payload(store, target_root=target_root)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def ingest_parity_report(
    source: ParityReport | Path | str | dict[str, Any],
    *,
    db_path: Path | None = None,
    repo_root: Path | None = None,
) -> RecordRunResult:
    """Record a parity report from object, file path, or dict."""
    if isinstance(source, ParityReport):
        report = source
    elif isinstance(source, (Path, str)):
        report = load_parity_report(Path(source))
    else:
        report = parity_report_from_dict(dict(source))

    if not report.summary:
        report.compute_summary()

    path = db_path or (default_parity_trends_db(repo_root) if repo_root else None)
    if path is None:
        raise ValueError("Provide db_path or repo_root for SQLite location")

    store = ParityTrendStore(path)
    store.init_schema()
    return store.record_run(report)
