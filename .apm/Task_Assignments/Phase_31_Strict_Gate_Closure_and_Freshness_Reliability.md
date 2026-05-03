# Phase 31 - Strict Gate Closure and Freshness Reliability

## Task 31.1

```markdown
---
task_ref: "Task 31.1 - Commit freshness preflight"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_31_Strict_Gate_Closure_and_Freshness_Reliability/Task_31_1_Commit_freshness_preflight.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Commit freshness preflight

## Task Reference
Implementation Plan: **Task 31.1 - Commit freshness preflight** assigned to **Agent_IndexGraph**

## Context from Dependencies
Depends on Task 30.6 and Task 27.3. Read the final Phase 30 dossier, manifest navigation/commit metadata implementation, and the latest PLAN0501 findings before changing behavior. Treat `run-1777730692266` as an example of a newest-by-mtime run that must not be selected as READY because its manifest has `target_dirty=true` and no readiness field.

## Objective
Record and verify target repository freshness around qoder-like generation.

## Detailed Instructions
- Record target repository HEAD and dirty state before generation starts.
- Re-check target HEAD after generation completes.
- In strict mode, require a clean target worktree by default and emit `QODER_STALE_GIT_COMMIT` for stale generation metadata.
- If dirty runs are allowed for manual review, mark `target_dirty=true` and force comparison output to `NOT_READY`.
- Add explicit manifest readiness fields and latest-run selection rules so tools prefer latest READY run over newest directory mtime.
- Add stale commit, dirty tree, missing readiness, and latest-run selector regression tests.

## Expected Output
- Deliverables: target HEAD metadata, dirty-state manifest fields, readiness metadata, latest-run selector, stale-run strict gate behavior, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_qoder_like_verifier.py tests/test_manifest_navigation.py`
- Completion rule: do not mark complete unless strict stale/dirty behavior, missing readiness, latest READY selection, and `.qoder/**` read-only behavior are tested.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_31_Strict_Gate_Closure_and_Freshness_Reliability/Task_31_1_Commit_freshness_preflight.md`
```

## Task 31.2

```markdown
---
task_ref: "Task 31.2 - Dump page retry policy"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_31_Strict_Gate_Closure_and_Freshness_Reliability/Task_31_2_Dump_page_retry_policy.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Dump page retry policy

## Task Reference
Implementation Plan: **Task 31.2 - Dump page retry policy** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 31.1 and Task 24.5. Use freshness metadata from Task 31.1 and existing hallucination/generic prose guardrails from Task 24.5.

## Objective
Retry pages that fail dump-page quality gates instead of accepting list-dominant output.

## Detailed Instructions
- Route `QODER_PAGE_DUMP` failures into a second-pass LLM rewrite queue.
- Require service responsibility, flow, risk, and source-evidence prose sections in rewrite prompts.
- Preserve valid citations while replacing list-dominant body content.
- Emit page-level retry status and terminal failure reasons.

## Expected Output
- Deliverables: dump-page repair queue, rewrite prompt policy, page retry status, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_quality_guardrails.py tests/test_llm_page_composer.py`
- Completion rule: do not mark complete unless dump pages are repaired or explicitly failed with reason codes.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_31_Strict_Gate_Closure_and_Freshness_Reliability/Task_31_2_Dump_page_retry_policy.md`
```

## Task 31.3

```markdown
---
task_ref: "Task 31.3 - Prose density repair"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_31_Strict_Gate_Closure_and_Freshness_Reliability/Task_31_3_Prose_density_repair.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Prose density repair

## Task Reference
Implementation Plan: **Task 31.3 - Prose density repair** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 31.2. Reuse the repair queue and page retry status from dump-page repair.

## Objective
Repair pages that fail qoder-like prose density checks.

## Detailed Instructions
- Detect `QODER_PROSE_TOO_LOW` pages after initial composition.
- Add targeted prose repair prompts that convert template/list output into grounded narrative.
- Report failed pages, reasons, and suggested retry commands when repair is exhausted.
- Add tests for low-prose detection and successful repair.

## Expected Output
- Deliverables: prose-density classifier, repair prompts, failure report, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_quality_guardrails.py tests/test_llm_page_composer.py`
- Completion rule: do not mark complete unless low-prose pages are repaired or fail loudly with retry guidance.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_31_Strict_Gate_Closure_and_Freshness_Reliability/Task_31_3_Prose_density_repair.md`
```

## Task 31.4

```markdown
---
task_ref: "Task 31.4 - Strict gate rerun package"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_31_Strict_Gate_Closure_and_Freshness_Reliability/Task_31_4_Strict_gate_rerun_package.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Strict gate rerun package

## Task Reference
Implementation Plan: **Task 31.4 - Strict gate rerun package** assigned to **Agent_QualityRelease**

## Context from Dependencies
Depends on Task 31.3. Use the freshness, dump-repair, and prose-repair outputs to run a fresh AI_API_Atlas strict evaluation.

## Objective
Produce a fresh AI_API_Atlas qoder-like run package that can clear strict verification.

## Detailed Instructions
- Generate under `/Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas/.repo-agent-eval/<run>` only.
- Verify `.qoder/**` remains read-only and unmodified.
- Run `repo-wiki verify --profile qoder-like --ci`.
- Require `QODER_STALE_GIT_COMMIT`, `QODER_PAGE_DUMP`, and `QODER_PROSE_TOO_LOW` reason codes to be zero before declaring readiness.
- Produce a manual review index for remaining human inspection.

## Expected Output
- Deliverables: isolated run, strict report, comparison report, manual review index.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_qoder_like_verifier.py tests/test_golden_qoder_like_fixture.py`
- Completion rule: do not mark complete unless strict report is PASS or the output clearly remains `NOT_READY`.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_31_Strict_Gate_Closure_and_Freshness_Reliability/Task_31_4_Strict_gate_rerun_package.md`
```
