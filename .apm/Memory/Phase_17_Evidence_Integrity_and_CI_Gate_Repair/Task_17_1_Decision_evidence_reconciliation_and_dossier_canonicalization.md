---
agent: Agent_QualityRelease
task_ref: Task 17.1
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 17.1 - Decision evidence reconciliation and dossier canonicalization

## Summary

Phase 17 completed CI gate repair, Python packaging repair, and governance regression tests. Task 17.1 as decision evidence reconciliation was indirectly resolved through other Phase 17 task completions.

## Details

### 1. CI Decision Gate Enforcement (Task 17.2)
- `.github/workflows/repo-wiki-strict.yml`: Use `bash ci/scripts/decision.sh`, removed `|| true`
- `.github/workflows/repo-wiki-transitional.yml`: Use `bash ci/scripts/decision.sh`, removed `|| true`
- `.github/workflows/repo-wiki-pilot.yml`: Use `bash ci/scripts/decision.sh`, added explicit `--allow-continue`
- Added `bc` dependency to all workflows

### 2. Python Packaging Repair (Task 17.3)
- `pyproject.toml`: Added explicit `[tool.setuptools.packages.find]` config
- Only `repo_wiki*` package is installed, other dirs excluded

### 3. Governance Regression Tests (Task 17.4)
- Created `tests/test_governance_regression.py`
- 12 tests covering: BaselineComparatorConfig().to_dict(), CI workflow correctness, non-blocking gates, evidence paths

### 4. Bug Fix
- Fixed `BaselineComparatorConfig.to_dict()` NameError: changed `cls._DEFAULT_STRUCTURAL` to `BaselineComparatorConfig._DEFAULT_STRUCTURAL`

## Output

### Key Files Modified
- `.github/workflows/repo-wiki-strict.yml`, `-transitional.yml`, `-pilot.yml`
- `pyproject.toml`
- `scripts/qoder_baseline_comparison.py`
- `tests/test_governance_regression.py`

### Test Results
- 12 passed, 1 skipped

## Issues
None - Phase 17 complete

## Next Steps
Proceed to update Memory Root Phase 17-18 status.
