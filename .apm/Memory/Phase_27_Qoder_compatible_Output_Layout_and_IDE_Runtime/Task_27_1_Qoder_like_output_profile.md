---
agent: Agent_PlatformCore
task_ref: "Task 27.1 - Qoder-like output profile"
status: "completed"
ad_hoc_delegation: false
important_findings: true
compatibility_issue: false
compatibility_issues: false
---

# Task 27.1 - Qoder-like output profile

## Implementation Summary

Implemented the qoder-like generation path as an isolated eval-output flow. `repo-wiki generate --profile qoder-like --output .repo-agent-eval --run-id <run>` now writes generated wiki pages directly to `<target>/.repo-agent-eval/<run>/content/**` and writes the run manifest under the same run directory.

The isolated path avoids target repository bootstrap side effects. It scans the target repository, writes source-of-truth artifacts into a temporary staging directory, generates markdown from staging, then materializes only content files into the eval run directory.

## Files Changed

- `repo_wiki/orchestration/service.py`
- `repo_wiki/orchestration/content_layout_writer.py`
- `repo_wiki/orchestration/eval_layout.py`
- `repo_wiki/cli.py`
- `tests/test_qoder_like_profile.py`
- `tests/test_content_layout_writer.py`
- `tests/test_eval_manifest.py`

## Important Findings

- The service-level qoder-like path still needed CLI protection: `repo-wiki generate` previously called `verify()` after generation even when `--ci` was not passed, which could create or update target `.repo-wiki/**`. The CLI now runs verification only when `--ci` is explicitly requested.
- Relative `--output .repo-agent-eval` must be resolved against the target repository root, not the current working directory. `EvalOutputProfile.resolve_root()` now enforces that behavior.
- Target repositories such as `AI_API_Atlas` do not necessarily contain repo-agent templates. The isolated qoder-like generator now falls back to repo-agent's bundled `templates/` directory while keeping target output isolated.

## Validation

- `uv run repo-wiki --help` passed.
- `uv run python -m pytest tests/test_qoder_like_profile.py tests/test_content_layout_writer.py tests/test_eval_manifest.py -q` passed with `26 passed`.
- CLI isolation smoke test on a temporary target repository passed: generated content under `.repo-agent-eval/test-run/**`, did not create `docs/` or `.repo-wiki/`, and did not modify `.qoder/**`.
- AI_API_Atlas acceptance run passed:
  - Run id: `fix-qoder-like-20260430-113703`
  - Output: `/Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas/.repo-agent-eval/fix-qoder-like-20260430-113703/content`
  - Markdown pages: `47`
  - `docs/` unchanged: yes
  - `.qoder/` unchanged: yes
  - `.repo-wiki/` unchanged: yes
  - `manifest.json` page registry count: `47`

## Final Status

Task completed. No compatibility issues are currently known for the implemented qoder-like isolated output path.
