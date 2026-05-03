---
agent: Agent_IndexGraph
task_ref: Task 29.6 - Regression dashboard and trend persistence
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 29.6 - Regression dashboard and trend persistence

## Summary

Implemented SQLite-backed parity run history with per-metric snapshots, automatic run-to-run deltas, and JSON dashboard export for governance review. Integrated with existing `ParityReport` / `load_parity_report` from Task 29.5-style outputs.

## Details

1. Added `repo_wiki/orchestration/trend_dashboard.py`:
   - Schema: `parity_runs`, `parity_metric_snapshots`, `parity_run_deltas`, `schema_meta`.
   - Normalizes `target_root` via resolved path for stable joins across ingest paths.
   - `record_run`: stores full report JSON; on second and later runs for the same target, computes summary and per-metric score deltas vs the immediately previous run and persists one `parity_run_deltas` row.
   - Query API: `list_runs`, `dimension_trend(metric_name)`, `latest_delta`, `list_deltas`.
   - `build_dashboard_payload` / `export_dashboard_json` produce Manager-review artifacts (runs list, `dimension_trends`, latest/recent deltas).
   - `ingest_parity_report` accepts `ParityReport`, JSON file path (`Path` or `str`), or dict; default DB path `default_parity_trends_db(repo_root)` → `.repo-wiki/index/parity_trends.sqlite3`.
2. Added `tests/test_trend_persistence.py`: schema init, multi-run delta correctness, dimension trend ordering, dashboard payload/export, dict ingest.

## Output

- New: `repo_wiki/orchestration/trend_dashboard.py`
- New: `tests/test_trend_persistence.py`
- Deliverable DB location (default): `.repo-wiki/index/parity_trends.sqlite3` (created on first ingest)

Example ingest after a parity JSON export:

```python
from pathlib import Path
from repo_wiki.orchestration.trend_dashboard import ingest_parity_report, export_dashboard_json, ParityTrendStore, default_parity_trends_db

repo = Path("/path/to/repo")
db = default_parity_trends_db(repo)
ingest_parity_report(Path("parity_report.json"), db_path=db)
export_dashboard_json(ParityTrendStore(db), repo / "parity_dashboard.json", target_root=str(repo))
```

## Issues

None.

## Next Steps

None. Optional: wire CLI or CI step to call `ingest_parity_report` after Task 29.5 parity JSON is written.
