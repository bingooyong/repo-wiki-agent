---
agent: "Agent_QualityRelease"
task_ref: "Task 28.5 - Failure recovery and partial evidence bundle"
status: "Completed"
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 28.5 - Failure recovery and partial evidence bundle

## Summary
Implemented failure recovery orchestration that preserves successful pages for partial runs, records structured failed page evidence (reason/provider/retry command), and builds a partial evidence bundle for diagnosable retries.

## Details
- Reviewed `repo_wiki/orchestration/generation_invalidation.py` and aligned behavior with page reset/requeue semantics (`pending`/`completed`/`retryable` safe reset model).
- Integrated with `GenerationStateMachine` run/page states by introducing `FailureRecoveryManager` in `repo_wiki/orchestration/failure_recovery.py`.
- Added failed-page recording flow that validates failed/retryable page state before writing evidence and auto-generates retry commands when absent.
- Added partial evidence bundle assembly that:
  - keeps only completed page outputs as usable artifacts,
  - includes structured failure records for failed/retryable pages,
  - enriches manifest with `retryable_pages`, `failed_or_retryable_pages`, `usable_pages`, and `is_partial`.
- Updated `PartialManifestBuilder` in `repo_wiki/orchestration/partial_evidence.py` to treat `retryable` pages as recoverable failures and to mark run resumability when retryable pages exist.
- Added acceptance-focused tests for partial generation behavior, including retry command presence and successful-page usability.

## Output
- Modified: `repo_wiki/orchestration/partial_evidence.py`
- Added: `repo_wiki/orchestration/failure_recovery.py`
- Modified: `tests/test_partial_generation_evidence.py`
- Validation: `pytest -q tests/test_partial_generation_evidence.py tests/test_generation_state_machine.py` passed.

## Issues
None

## Next Steps
None
