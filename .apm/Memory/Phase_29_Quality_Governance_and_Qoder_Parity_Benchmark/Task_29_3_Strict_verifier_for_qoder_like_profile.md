---
agent: Agent_AdapterGovernance
task_ref: "Task 29.3 - Strict verifier for qoder-like profile"
status: Completed
ad_hoc_delegation: false
compatibility_issues: true
important_findings: true
---

# Task Log: Task 29.3 - Strict verifier for qoder-like profile

## Summary
Refactored qoder-like strict verification to validate isolated `content/**` outputs directly and exposed it through `repo-wiki verify --profile qoder-like --ci --output ...`.

## Details
- Rebuilt `repo_wiki/verifier/qoder_strict_verifier.py`:
- Removed legacy `docs/sections` hard-coupling and switched to qoder-like content gates.
- Added strict checks:
- content presence
- TOC coverage
- citation coverage
- file/line reference coverage
- broken links
- Mermaid coverage
- API aggregation quality
- Data model aggregation quality
- dump-page detection
- prose density
- stale git commit
- Updated commit matching to tolerate short hash prefixes from manifest.
- Fixed content root detection for direct `.../content` targets in:
- `repo_wiki/verifier/qoder_strict_verifier.py`
- `repo_wiki/verifier/qoder_parity_metrics.py`
- Extended `repo_wiki/cli.py verify`:
- new flags `--profile`, `--output`
- `qoder-like` mode returns `NOT_READY` and non-zero exit in `--ci`.

## Output
- Modified:
- `repo_wiki/verifier/qoder_strict_verifier.py`
- `repo_wiki/verifier/qoder_parity_metrics.py`
- `repo_wiki/cli.py`
- `tests/test_qoder_compare_cli.py`
- Verification run (AI_API_Atlas isolated content):
- command: `repo-wiki verify --profile qoder-like --ci --output /Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas/.repo-agent-eval/phase22-24-pipeline-v2`
- result: `FAIL`, hard gate: `QODER_API_AGGREGATION_LOW`

## Issues
- Strict gate still blocks replacement readiness due API aggregation quality below threshold on current generated pages.

## Compatibility Concerns
- The verifier contract for qoder-like profile changed from legacy docs-structure checks to content-centric checks.
- Existing automation consuming old reason-code mix may need to update expectations.

## Important Findings
- Current repo-agent output for AI_API_Atlas now passes structure-level qoder-like checks (TOC/citation/file-line/Mermaid/stale commit) but fails only on API aggregation quality.
- This narrows the remaining replacement gap to generation quality, not validator path/contract mismatch.

## Next Steps
- Improve API page aggregation generation (service-family summary + schema/context synthesis) to clear `QODER_API_AGGREGATION_LOW`.
