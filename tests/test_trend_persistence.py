"""Tests for parity trend SQLite persistence and dashboard export."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from repo_wiki.orchestration.trend_dashboard import (
    ParityTrendStore,
    RecordRunResult,
    build_dashboard_payload,
    default_parity_trends_db,
    export_dashboard_json,
    ingest_parity_report,
    parity_report_from_dict,
)
from repo_wiki.verifier.qoder_parity_metrics import (
    MetricCategory,
    MetricResult,
    MetricSeverity,
    MetricStatus,
    ParityReport,
)


def _minimal_report(
    *,
    run_id: str,
    target: Path,
    overall: float = 0.7,
    metric_scores: dict[str, float] | None = None,
    generated_at: str = "2026-05-01T12:00:00Z",
) -> ParityReport:
    metric_scores = metric_scores or {"page_coverage": 0.8, "citation_density": 0.6}
    r = ParityReport(
        target_root=target,
        baseline_root=None,
        run_id=run_id,
        generated_at=generated_at,
    )
    for name, sc in metric_scores.items():
        r.add_metric(
            MetricResult(
                metric_name=name,
                status=MetricStatus.PASS if sc >= 0.5 else MetricStatus.FAIL,
                score=sc,
                measured_value=sc,
                threshold=0.5,
                severity=MetricSeverity.INFO,
                category=MetricCategory.CONTENT,
                gaps=[],
                details={},
            )
        )
    r.compute_summary()
    return r


@pytest.fixture()
def tmp_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
        p = Path(f.name)
    yield p
    p.unlink(missing_ok=True)


class TestParityReportFromDict:
    def test_roundtrip_fields(self, tmp_path: Path) -> None:
        report = _minimal_report(run_id="r1", target=tmp_path / "docs")
        data = report.to_dict()
        restored = parity_report_from_dict(data)
        assert restored.run_id == report.run_id
        assert restored.metrics[0].metric_name == report.metrics[0].metric_name


class TestParityTrendStore:
    def test_init_schema(self, tmp_db: Path) -> None:
        store = ParityTrendStore(tmp_db)
        store.init_schema()
        conn = store.connect()
        try:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert "parity_runs" in tables
            assert "parity_metric_snapshots" in tables
            assert "parity_run_deltas" in tables
        finally:
            conn.close()

    def test_record_and_list_runs(self, tmp_path: Path, tmp_db: Path) -> None:
        store = ParityTrendStore(tmp_db)
        store.init_schema()
        r = _minimal_report(run_id="run-a", target=tmp_path)
        out = store.record_run(r)
        assert isinstance(out, RecordRunResult)
        assert out.delta is None
        runs = store.list_runs(target_root=str(tmp_path))
        assert len(runs) == 1
        assert runs[0]["run_id"] == "run-a"
        assert runs[0]["overall_score"] is not None

    def test_delta_between_two_runs(self, tmp_path: Path, tmp_db: Path) -> None:
        store = ParityTrendStore(tmp_db)
        store.init_schema()
        t = tmp_path.resolve()
        store.record_run(
            _minimal_report(
                run_id="run-1",
                target=t,
                metric_scores={"page_coverage": 0.5, "citation_density": 0.5},
            )
        )
        result = store.record_run(
            _minimal_report(
                run_id="run-2",
                target=t,
                generated_at="2026-05-02T12:00:00Z",
                metric_scores={"page_coverage": 0.7, "citation_density": 0.6},
            )
        )
        assert result.delta is not None
        assert result.delta["from_run_id"] == "run-1"
        assert result.delta["to_run_id"] == "run-2"
        md = result.delta["metrics_delta"]["page_coverage"]
        assert md["score_delta"] == pytest.approx(0.2)
        latest = store.latest_delta(str(t))
        assert latest is not None
        assert latest["summary_delta"]["overall_score"] != 0 or latest["metrics_delta"]

    def test_dimension_trend_order(self, tmp_path: Path, tmp_db: Path) -> None:
        store = ParityTrendStore(tmp_db)
        store.init_schema()
        t = tmp_path.resolve()
        store.record_run(
            _minimal_report(
                run_id="t1",
                target=t,
                metric_scores={"toc_presence": 0.4},
            )
        )
        store.record_run(
            _minimal_report(
                run_id="t2",
                target=t,
                generated_at="2026-05-03T12:00:00Z",
                metric_scores={"toc_presence": 0.9},
            )
        )
        series = store.dimension_trend(str(t), "toc_presence")
        assert len(series) == 2
        assert series[0]["score"] == pytest.approx(0.4)
        assert series[1]["score"] == pytest.approx(0.9)


class TestDashboardExport:
    def test_build_payload_has_keys(self, tmp_path: Path, tmp_db: Path) -> None:
        store = ParityTrendStore(tmp_db)
        store.init_schema()
        t = tmp_path.resolve()
        store.record_run(_minimal_report(run_id="d1", target=t))
        payload = build_dashboard_payload(store, target_root=str(t))
        assert payload["schema_version"]
        assert "exported_at" in payload
        assert len(payload["runs"]) >= 1
        assert "dimension_trends" in payload
        assert "page_coverage" in payload["dimension_trends"]

    def test_export_dashboard_json_writes_file(self, tmp_path: Path, tmp_db: Path) -> None:
        store = ParityTrendStore(tmp_db)
        store.init_schema()
        t = tmp_path.resolve()
        store.record_run(_minimal_report(run_id="e1", target=t))
        out = tmp_path / "dash.json"
        export_dashboard_json(store, out, target_root=str(t))
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["runs"]


class TestIngestParityReport:
    def test_ingest_from_dict(self, tmp_path: Path, tmp_db: Path) -> None:
        report = _minimal_report(run_id="ing1", target=tmp_path)
        rec = ingest_parity_report(report.to_dict(), db_path=tmp_db)
        assert rec.run_id == "ing1"


class TestDefaultDbPath:
    def test_creates_under_repo_wiki_index(self, tmp_path: Path) -> None:
        p = default_parity_trends_db(tmp_path)
        assert ".repo-wiki" in p.parts
        assert p.name == "parity_trends.sqlite3"
