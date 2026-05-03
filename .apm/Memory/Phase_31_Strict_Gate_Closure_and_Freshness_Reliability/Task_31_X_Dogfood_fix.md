---
agent: Agent_PlatformCore
task_ref: Task 1 - Fix QODER_CONTENT_EMPTY dogfood failure
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: true
---

# Task Log: Dogfood fix — QODER_CONTENT_EMPTY

## Summary
Fixed zero-output qoder-like writes when dogfooding repo-agent: runtime `doc_hierarchy` stores absolute paths while composed pages use repo-relative `docs/pages/...` keys, and partial overlap with legacy on-disk docs would filter out the entire plan. Added path normalization and safe fallback to the full plan set for isolated eval.

## Details
- **Root cause:** `ContentLayoutWriter.load_selected_paths_from_sqlite()` returned absolute paths from SQLite; `write_markdown_pages()` filters `(source_path in selected_source_paths)` using planner-relative paths → no matches → zero files. Separately, runtime docs (`docs/00-overview.md`, `docs/modules/*.md`) rarely intersect qoder plan paths (`docs/pages/**`), so `selected_paths` was non-empty but disjoint from `plan_md_paths`, and the old `if not selected_paths` fallback never ran.
- **Fix:**
  - `_normalize_doc_path_for_filter()` + `load_selected_paths_from_sqlite(..., project_root=)` to map stored paths to POSIX repo-relative strings.
  - In `_generate_isolated_eval`, compute `plan_md_paths`, intersect with normalized sqlite paths; use full `plan_md_paths` when intersection is empty or strictly smaller than the plan (avoids legacy sqlite starving qoder-like output).

## Output
- Modified: `repo_wiki/orchestration/content_layout_writer.py`, `repo_wiki/orchestration/service.py`
- Tests: `tests/test_content_layout_writer.py` (`test_load_selected_paths_from_sqlite_normalizes_absolute_paths`)

## Verification
- `uv run pytest tests/test_content_layout_writer.py` — pass
- Smoke: `REPO_WIKI_LLM_PAGE_LIMIT=8 REPO_WIKI_LLM_REAL_MAX_CALLS=0 uv run repo-wiki generate --profile qoder-like --run-id dogfood-fix-smoke` produced **8** `content/**/*.md` files; strict verifier **`qoder-content-presence` PASS** (previously empty-content failure mode addressed).
- Full `verify --profile qoder-like --ci` on that partial run still **`grade: FAIL`** due to unrelated aggregation gates on an intentionally tiny page set — not a regression from this fix.

## Important Findings
- Isolated qoder-like writes must not rely on raw SQLite path equality against planner paths without normalization and plan-aware fallback.

## Issues
None

## Next Steps
None
