# Journal - bingooyong (Part 1)

> AI development session journal
> Started: 2026-11-22

---



## Session 1: Freeze ai-testing Qoder baselines and publish gap report
<!-- trellis-session: v=2 fp=7be1c35e4cd0e9f9 -->

**Date**: 2026-11-22
**Task**: Freeze ai-testing Qoder baselines and publish gap report
**Branch**: `task/11-22-baseline-ai-testing-wiki`

### Summary

Task 11-22-baseline-ai-testing-wiki: added read-only external baseline registry (knowledge cards 88 files + long-form wiki 71 files) with reproducible sha256 fingerprints, verification script, knowledge-card field contract, and a 14-item gap report. Measurement overturned two planning premises: the ai-testing long-form wiki is complete on disk (70 pages, 13 top-level IA entries, mermaid 100%, line anchors 98.57%), and ai/source-of-truth is already clean (41 models, 0 pollution) — pseudo-entities survive only in generated docs/01/03/05, so task 2 shifts to regeneration plus anti-recurrence contract tests. Recorded compare limits honestly: cross-repo baseline not consumable, knowledge-card dimension unsupported. 8 new tests plus 126 regression tests pass; ai-testing untouched.

### Git Commits

| Hash | Message |
|------|---------|
| `76993ca` | feat: freeze ai-testing Qoder baselines for reproducible gap analysis |

### Status

[OK] **Completed**


## Session 2: Purge stale facts from generated docs and protect curated content
<!-- trellis-session: v=2 fp=86721c07e4a2d9df -->

**Date**: 2026-11-23
**Task**: Purge stale facts from generated docs and protect curated content
**Branch**: `task/11-22-source-truth-purity`

### Summary

Task 11-22-source-truth-purity: fixed live generation defects rather than re-cleaning an already-clean fact layer. Template rendering now raises on unresolved placeholders and enforces required_keys; cache key includes template bytes so template fixes take effect; core-entity scoring uses word-boundary matching, dedupes reasons and excludes dependency/test sources; language/framework detection prefers package config. Closed two clobbering paths found in review: the task-catalog contract wrote a curated fact file, and generate replaced the human-authored docs/00-overview.md with an init stub. Added HARD unresolved-placeholders gate and 27 contract tests; 438 targeted regressions pass; default verify --ci has zero hard failures. Regenerated docs now show Python/typer-cli with no node_modules pseudo-entities. qoder-like full-chain acceptance transferred to task 6 because no READY release exists (reproduces on base 665408a). Four full-suite failures are pre-existing/environmental. Spec captured in .trellis/spec/backend/docs-generation-purity.md.

### Git Commits

| Hash | Message |
|------|---------|
| `a5abb35` | fix: keep generated docs factual and protect curated content |

### Status

[OK] **Completed**
