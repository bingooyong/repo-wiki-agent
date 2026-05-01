# Phase 28 - Generation Orchestration, Cost Control, and Incremental Update

## Task 28.1

```markdown
---
task_ref: "Task 28.1 - Generation run state machine"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update/Task_28_1_Generation_run_state_machine.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Generation run state machine

## Task Reference
Implementation Plan: **Task 28.1 - Generation run state machine** assigned to **Agent_IndexGraph**

## Context from Dependencies
Read `docs/phases/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update.md` and Phase 27 manifest/output logs.

## Objective
Persist generation run and page state.

## Detailed Instructions
- Add pending/running/completed/failed/retryable states for runs and pages.
- Persist state transitions in SQLite.
- Support resume without regenerating completed pages.

## Expected Output
- Deliverables: run state machine, SQLite persistence, resume tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_generation_state_machine.py tests/test_runtime_store.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update/Task_28_1_Generation_run_state_machine.md`
```

## Task 28.2

```markdown
---
task_ref: "Task 28.2 - LLM cost estimator and budget gate"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update/Task_28_2_LLM_cost_estimator_and_budget_gate.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: LLM cost estimator and budget gate

## Task Reference
Implementation Plan: **Task 28.2 - LLM cost estimator and budget gate** assigned to **Agent_PlatformCore**

## Context from Dependencies
Depends on Task 28.1 by Agent_IndexGraph and Task 21.4. Use run state and token budget policy.

## Objective
Estimate generation cost and block over-budget runs.

## Detailed Instructions
- Estimate token/cost from page plan, prompts, provider model, and configured pricing.
- Stop over-budget generation unless explicit override is provided.
- Add reason codes and tests for budget failures.

## Expected Output
- Deliverables: cost estimator, budget gate, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_cost_estimator.py tests/test_generation_state_machine.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update/Task_28_2_LLM_cost_estimator_and_budget_gate.md`
```

## Task 28.3

```markdown
---
task_ref: "Task 28.3 - Concurrent generation scheduler"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update/Task_28_3_Concurrent_generation_scheduler.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Concurrent generation scheduler

## Task Reference
Implementation Plan: **Task 28.3 - Concurrent generation scheduler** assigned to **Agent_PlatformCore**

## Context from Dependencies
Depends on Task 28.2. Use budget gate, provider retry policy, and run state model.

## Objective
Add configurable concurrency, rate limiting, and recoverable scheduling.

## Detailed Instructions
- Respect provider rate limits and max concurrency.
- Keep SQLite run state consistent under concurrent page generation.
- Add cancellation, retry, and rate-limit tests.

## Expected Output
- Deliverables: scheduler, rate limiter, concurrency tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_generation_scheduler.py tests/test_cost_estimator.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update/Task_28_3_Concurrent_generation_scheduler.md`
```

## Task 28.4

```markdown
---
task_ref: "Task 28.4 - Page-level invalidation from git diff and hash fallback"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update/Task_28_4_Page_level_invalidation_from_git_diff_and_hash_fallback.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Page-level invalidation from git diff and hash fallback

## Task Reference
Implementation Plan: **Task 28.4 - Page-level invalidation from git diff and hash fallback** assigned to **Agent_IndexGraph**

## Context from Dependencies
Depends on Task 28.3 and Phase 12 page invalidation. Integrate scheduler state with file-to-page impact mapping.

## Objective
Regenerate only impacted pages using git diff or hash fallback.

## Detailed Instructions
- Map changed files to evidence spans, page source maps, and planned pages.
- Use hash comparison when git is unavailable.
- Add fixture proving one service change invalidates only related pages.

## Expected Output
- Deliverables: page invalidation engine, git/hash fallback tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_page_invalidation.py tests/test_generation_scheduler.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update/Task_28_4_Page_level_invalidation_from_git_diff_and_hash_fallback.md`
```

## Task 28.5

```markdown
---
task_ref: "Task 28.5 - Failure recovery and partial evidence bundle"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update/Task_28_5_Failure_recovery_and_partial_evidence_bundle.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Failure recovery and partial evidence bundle

## Task Reference
Implementation Plan: **Task 28.5 - Failure recovery and partial evidence bundle** assigned to **Agent_QualityRelease**

## Context from Dependencies
Depends on Task 28.4. Use run/page states and invalidation outputs to produce recoverable evidence.

## Objective
Make partial generation runs diagnosable and recoverable.

## Detailed Instructions
- Record failed pages, failure reasons, provider errors, and retry commands.
- Keep successful pages usable when some pages fail.
- Write partial run manifest and evidence bundle.

## Expected Output
- Deliverables: failure evidence bundle, partial manifest, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_partial_generation_evidence.py tests/test_page_invalidation.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update/Task_28_5_Failure_recovery_and_partial_evidence_bundle.md`
```

## Task 28.6

```markdown
---
task_ref: "Task 28.6 - update integration for qoder-like profile"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update/Task_28_6_update_integration_for_qoder_like_profile.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: update integration for qoder-like profile

## Task Reference
Implementation Plan: **Task 28.6 - update integration for qoder-like profile** assigned to **Agent_PlatformCore**

## Context from Dependencies
Depends on Task 28.5 by Agent_QualityRelease. Integrate recovery, invalidation, scheduler, and manifest update paths.

## Objective
Wire incremental update into `repo-wiki update --profile qoder-like`.

## Detailed Instructions
- Reuse planner, invalidation, scheduler, and manifest writing.
- Keep output isolated under `.repo-agent-eval`.
- Add CLI smoke and targeted update tests.

## Expected Output
- Deliverables: qoder-like update command integration and tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_qoder_like_update.py tests/test_cli_update.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update/Task_28_6_update_integration_for_qoder_like_profile.md`
```

