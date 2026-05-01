# Phase 34 - LLM Composer Quality Loop

## Task 34.1

```markdown
---
task_ref: "Task 34.1 - Page quality classifier"
agent_assignment: "Agent_AdapterGovernance"
memory_log_path: ".apm/Memory/Phase_34_LLM_Composer_Quality_Loop/Task_34_1_Page_quality_classifier.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Page quality classifier

## Task Reference
Implementation Plan: **Task 34.1 - Page quality classifier** assigned to **Agent_AdapterGovernance**

## Context from Dependencies
Depends on Task 33.4 and Task 24.5. Combine low-confidence fallback behavior with existing quality guardrails.

## Objective
Classify generated pages as `PASS`, `REPAIRABLE`, or `REJECTED`.

## Detailed Instructions
- Classify each page after generation and before final manifest readiness.
- Use dump ratio, prose density, citation relevance, heading completeness, and generic prose signals.
- Persist classification results in the run evidence bundle.
- Add classifier tests for pass, repairable, and rejected pages.

## Expected Output
- Deliverables: page quality classifier, persisted status, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_quality_guardrails.py tests/test_qoder_like_verifier.py`
- Completion rule: do not mark complete unless classification results are visible to verify/compare outputs.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_34_LLM_Composer_Quality_Loop/Task_34_1_Page_quality_classifier.md`
```

## Task 34.2

```markdown
---
task_ref: "Task 34.2 - Targeted repair prompts"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_34_LLM_Composer_Quality_Loop/Task_34_2_Targeted_repair_prompts.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Targeted repair prompts

## Task Reference
Implementation Plan: **Task 34.2 - Targeted repair prompts** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 34.1. Use page quality classification to select page-type-specific repair prompts.

## Objective
Repair failed pages with page-type-specific prompts.

## Detailed Instructions
- Provide repair prompts for API, data-model, architecture, service, and operations pages.
- Rewrite only failed pages and preserve valid citations.
- Track before/after quality scores for each repaired page.
- Add mock-provider tests for targeted repair behavior.

## Expected Output
- Deliverables: targeted repair prompts, repair pipeline integration, before/after scoring, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_llm_page_composer.py tests/test_quality_guardrails.py`
- Completion rule: do not mark complete unless repair preserves citations and rewrites only failed pages.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_34_LLM_Composer_Quality_Loop/Task_34_2_Targeted_repair_prompts.md`
```

## Task 34.3

```markdown
---
task_ref: "Task 34.3 - Cost-aware retry scheduler"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_34_LLM_Composer_Quality_Loop/Task_34_3_Cost_aware_retry_scheduler.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Cost-aware retry scheduler

## Task Reference
Implementation Plan: **Task 34.3 - Cost-aware retry scheduler** assigned to **Agent_PlatformCore**

## Context from Dependencies
Depends on Task 34.2 and Task 28.3. Integrate targeted repair with the existing generation scheduler, concurrency, and provider rate-limit behavior.

## Objective
Schedule repairs with bounded retries, token budgets, and visible progress.

## Detailed Instructions
- Enforce maximum repair attempts and token budget per run.
- Record planned, `llm_done`, repairing, fallback, and failed counts in CLI progress.
- Preserve partial usable output while marking unrepaired failures as not ready.
- Add budget and retry-limit tests.

## Expected Output
- Deliverables: retry scheduler, budget enforcement, CLI progress, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_generation_scheduler.py tests/test_cli_qoder_like.py`
- Completion rule: do not mark complete unless retry exhaustion produces explicit `NOT_READY` state.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_34_LLM_Composer_Quality_Loop/Task_34_3_Cost_aware_retry_scheduler.md`
```

## Task 34.4

```markdown
---
task_ref: "Task 34.4 - Cache validity by quality hash"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_34_LLM_Composer_Quality_Loop/Task_34_4_Cache_validity_by_quality_hash.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Cache validity by quality hash

## Task Reference
Implementation Plan: **Task 34.4 - Cache validity by quality hash** assigned to **Agent_IndexGraph**

## Context from Dependencies
Depends on Task 34.3 and Task 24.6. Extend existing page composition cache behavior with quality-profile invalidation.

## Objective
Prevent stale low-quality cached pages from being reused after quality rules change.

## Detailed Instructions
- Include quality profile hash in page composition cache keys.
- Invalidate old low-quality cache entries when repair or verifier rules change.
- Record repair coverage and cache reuse in manifest summaries.
- Add cache invalidation regression tests.

## Expected Output
- Deliverables: quality-profile cache key, invalidation behavior, manifest repair summary, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_page_composer_cache.py tests/test_manifest_navigation.py`
- Completion rule: do not mark complete unless old low-quality cache entries are invalidated when quality rules change.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_34_LLM_Composer_Quality_Loop/Task_34_4_Cache_validity_by_quality_hash.md`
```

