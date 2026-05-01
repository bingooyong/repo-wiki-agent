# Phase 29 - Quality Governance and Qoder Parity Benchmark

## Task 29.1

```markdown
---
task_ref: "Task 29.1 - Qoder parity metric schema"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark/Task_29_1_Qoder_parity_metric_schema.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Qoder parity metric schema

## Task Reference
Implementation Plan: **Task 29.1 - Qoder parity metric schema** assigned to **Agent_QualityRelease**

## Context from Dependencies
Read `docs/phases/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark.md` and Phase 28 generation logs.

## Objective
Define structural and content parity metrics for qoder-like replacement.

## Detailed Instructions
- Include page coverage, directory depth, cite coverage, file refs, TOC, Mermaid, prose/list ratio, API aggregation, and data-model aggregation.
- Define thresholds, severity, and serialization schema.
- Keep metrics based on observable outputs, not Qoder internals.

## Expected Output
- Deliverables: parity metric schema, serialization, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_qoder_parity_metrics.py tests/test_readiness_schema.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark/Task_29_1_Qoder_parity_metric_schema.md`
```

## Task 29.2

```markdown
---
task_ref: "Task 29.2 - Comparator path-model repair"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark/Task_29_2_Comparator_path_model_repair.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Comparator path-model repair

## Task Reference
Implementation Plan: **Task 29.2 - Comparator path-model repair** assigned to **Agent_QualityRelease**

## Context from Dependencies
Depends on Task 29.1. Use the metric schema and prior qoder comparison findings.

## Objective
Compare Qoder `content/**` with repo-agent `content/**` without docs-specific false positives.

## Detailed Instructions
- Support `.qoder/repowiki/zh` and `.repo-agent-eval/<run>/content` path models.
- Remove assumptions tied to `docs/sections`.
- Add AI_API_Atlas regression so `docs/docs` gaps are not emitted.

## Expected Output
- Deliverables: comparator path model repair, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_qoder_comparator_paths.py tests/test_qoder_parity_metrics.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark/Task_29_2_Comparator_path_model_repair.md`
```

## Task 29.3

```markdown
---
task_ref: "Task 29.3 - Strict verifier for qoder-like profile"
agent_assignment: "Agent_AdapterGovernance"
memory_log_path: ".apm/Memory/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark/Task_29_3_Strict_verifier_for_qoder_like_profile.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Strict verifier for qoder-like profile

## Task Reference
Implementation Plan: **Task 29.3 - Strict verifier for qoder-like profile** assigned to **Agent_AdapterGovernance**

## Context from Dependencies
Depends on Task 29.2 by Agent_QualityRelease and Task 24.5. Use comparator paths and quality guardrails.

## Objective
Add `verify --profile qoder-like --ci` strict gate.

## Detailed Instructions
- Fail missing citations, missing TOC, dump pages, and broken file references.
- Keep strict and pilot thresholds explicit.
- Add regression tests for each hard failure.

## Expected Output
- Deliverables: strict verifier mode, reason codes, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_qoder_like_verifier.py tests/test_quality_guardrails.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark/Task_29_3_Strict_verifier_for_qoder_like_profile.md`
```

## Task 29.4

```markdown
---
task_ref: "Task 29.4 - Golden fixture suite"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark/Task_29_4_Golden_fixture_suite.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Golden fixture suite

## Task Reference
Implementation Plan: **Task 29.4 - Golden fixture suite** assigned to **Agent_QualityRelease**

## Context from Dependencies
Depends on Task 29.3. Use strict verifier and comparator contracts to build stable fixtures.

## Objective
Create stable CI fixtures for qoder-like generation and validation.

## Detailed Instructions
- Include small Java, Python, TypeScript, and SQL fixtures.
- Provide expected Wiki tree and mock LLM outputs.
- Cover planner, evidence, composer, verifier, and comparator paths.

## Expected Output
- Deliverables: golden fixtures, expected outputs, CI tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_golden_qoder_like_fixture.py tests/test_qoder_like_verifier.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark/Task_29_4_Golden_fixture_suite.md`
```

## Task 29.5

```markdown
---
task_ref: "Task 29.5 - AI_API_Atlas qoder parity rerun"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark/Task_29_5_AI_API_Atlas_qoder_parity_rerun.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: AI_API_Atlas qoder parity rerun

## Task Reference
Implementation Plan: **Task 29.5 - AI_API_Atlas qoder parity rerun** assigned to **Agent_QualityRelease**

## Context from Dependencies
Depends on Task 29.4. Use golden fixture confidence before running the real AI_API_Atlas evaluation.

## Objective
Run an isolated AI_API_Atlas qoder parity evaluation.

## Detailed Instructions
- Generate only under `/Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas/.repo-agent-eval/<run>`.
- Compare against `/Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas/.qoder/repowiki/zh` as read-only.
- Report page count, citations, TOC, Mermaid, prose density, API quality, and data-model quality gaps.

## Expected Output
- Deliverables: isolated run, comparison report, gap matrix.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_golden_qoder_like_fixture.py tests/test_qoder_comparator_paths.py`
- Completion rule: do not mark complete unless compile and self-test pass and no Qoder baseline directory is modified.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark/Task_29_5_AI_API_Atlas_qoder_parity_rerun.md`
```

## Task 29.6

```markdown
---
task_ref: "Task 29.6 - Regression dashboard and trend persistence"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark/Task_29_6_Regression_dashboard_and_trend_persistence.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Regression dashboard and trend persistence

## Task Reference
Implementation Plan: **Task 29.6 - Regression dashboard and trend persistence** assigned to **Agent_IndexGraph**

## Context from Dependencies
Depends on Task 29.5 by Agent_QualityRelease and Phase 12 compare persistence. Store parity metrics over time.

## Objective
Persist quality metrics and export trend dashboard.

## Detailed Instructions
- Store multiple run metrics and deltas in SQLite.
- Export dashboard artifacts for Manager review.
- Add trend query and dashboard export tests.

## Expected Output
- Deliverables: metric trend tables, dashboard export, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_quality_trends.py tests/test_dashboard_export.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark/Task_29_6_Regression_dashboard_and_trend_persistence.md`
```

