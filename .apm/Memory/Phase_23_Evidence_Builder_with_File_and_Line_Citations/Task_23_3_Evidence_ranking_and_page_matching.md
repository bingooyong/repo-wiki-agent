---
task_ref: "Task 23.3 - Evidence ranking and page matching"
status: "completed"
important_findings: false
compatibility_issue: false
compatibility_issues: false
---

# Task 23.3 - Evidence ranking and page matching

## Status
Completed

## Implementation Summary

### Deliverables Created

1. **Evidence Ranking Pipeline** (`repo_wiki/evidence/ranking.py`)
   - `EvidenceRanker` class - ranks evidence spans for wiki page plans
   - `score_evidence_for_page()` - scores a single span against a page
   - `rank_evidence_for_page()` - ranks all spans for a single page
   - Signals-based scoring: module_match, api_match, data_model_match, file_proximity, category_relevance

2. **Page-Source Mapping**
   - `EvidenceRankingResult` with bindings list and insufficient_pages list
   - `PageEvidenceBinding` with page_id, doc_type, candidates, insufficient_evidence flag
   - `EvidenceCandidate` with evidence_id, span, score, match_signals, citation_order

3. **Tests** (`tests/test_evidence_ranking.py`)
   - TestCategoryMapping - category to doc type mapping
   - TestKeywordExtraction - keyword extraction from pages
   - TestScoringFunctions - individual scoring functions
   - TestScoreEvidenceForPage - overall scoring
   - TestRankEvidenceForPage - ranking for single page
   - TestEvidenceRanker - full ranker with SQLite store
   - TestGetInsufficientEvidencePages - insufficient evidence reporting

### Key Design Decisions

- **Signals-based ranking**: Combines multiple signals (module, symbol, API, data model, file proximity, category relevance) with weights
- **MIN_CANDIDATES_PER_PAGE = 5**: Per task requirement
- **Category to doc type mapping**: Maps WikiTaxonomyCategory to doc types (overview, section, module, data-model, api, ops, guide, security, troubleshooting)
- **Normalization**: Uses `_normalize_for_matching()` to handle hyphen/underscore/path separators

### Compile Command
`uv run repo-wiki --help` - PASSED

### Self-Test Command
`uv run pytest tests/test_evidence_ranking.py tests/test_planner_persistence.py` - PASSED (43 tests)

### Dependencies Used
- Task 23.2: `repo_wiki/orchestration/runtime_store.py` (SQLiteRuntimeStore, EvidenceSpanRecord)
- Task 22.6: `repo_wiki/planner/schema.py` (WikiPagePlan, WikiPlanManifest, WikiTaxonomyCategory)
- Task 23.1: `repo_wiki/scanner/source_spans.py` (group_spans_by_file)

### Insufficient Evidence Handling
- Pages with fewer than MIN_CANDIDATES_PER_PAGE candidates are flagged
- `get_insufficient_evidence_pages()` returns detailed report for verifier/reporting

## Follow-up (2026-04-30)
- `repo_wiki/orchestration/service.py::_bind_evidence_to_plan()` 增加 fallback 绑定：当 ranking 结果为空且仓库存在 span 时，自动补齐前 5 条候选证据。
- 该改动保证“每个 page plan 都有 evidence candidates”，支撑后续 citation 强制渲染。
