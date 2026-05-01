# Phase 17 - Evidence Integrity and CI Gate Repair

## Task 17.1

```markdown
---
task_ref: "Task 17.1 - Decision evidence reconciliation and dossier canonicalization"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_17_Evidence_Integrity_and_CI_Gate_Repair/Task_17_1_Decision_evidence_reconciliation_and_dossier_canonicalization.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Decision evidence reconciliation and dossier canonicalization

## Task Reference
Implementation Plan: **Task 17.1 - Decision evidence reconciliation and dossier canonicalization** assigned to **Agent_QualityRelease**

## Context from Dependencies
This task depends on Task 16.4 implemented by Agent_QualityRelease.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_17_Evidence_Integrity_and_CI_Gate_Repair.md`.
2. Read `docs/repo-wiki-phase-14-16-review-and-phase-17-20-plan.md`.
3. Read `.apm/Memory/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate/Task_16_4_Go_no_go_decision_dossier_and_handover_package.md`.
4. Compare `.apm/Memory/Memory_Root.md`, `.repo-agent-eval/go-no-go-decision/**`, `.repo-agent-eval/Final_Pilot_Execution_Report.md`, and `docs/operations/**`.
5. Do not rely on Memory summaries when actual evidence contradicts them.

## Objective
Reconcile contradictory decision/evidence outputs and define the canonical decision dossier location and status language.

## Detailed Instructions
- Resolve `CONDITIONAL GO` versus `CONDITIONAL NO-GO` into one Manager-approved status.
- Align claimed paths with actual files or explicitly promote generated evidence into `docs/operations`.
- Update or add an evidence consistency report without deleting historical logs.
- Make phase/task status discrepancies explicit.
- Add a handover checklist for future Manager sessions.

## Expected Output
- Deliverables: contradiction report, canonical dossier/evidence path, status reconciliation, updated operations docs.
- Success criteria: Memory, evidence, and operations docs can be read without conflicting go/no-go conclusions.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_17_Evidence_Integrity_and_CI_Gate_Repair/Task_17_1_Decision_evidence_reconciliation_and_dossier_canonicalization.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block using `.claude/commands/apm-3-initiate-implementation.md`.
```

## Task 17.2

```markdown
---
task_ref: "Task 17.2 - CI decision gate enforcement and workflow correctness"
agent_assignment: "Agent_AdapterGovernance"
memory_log_path: ".apm/Memory/Phase_17_Evidence_Integrity_and_CI_Gate_Repair/Task_17_2_CI_decision_gate_enforcement_and_workflow_correctness.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: CI decision gate enforcement and workflow correctness

## Task Reference
Implementation Plan: **Task 17.2 - CI decision gate enforcement and workflow correctness** assigned to **Agent_AdapterGovernance**

## Context from Dependencies
This task depends on Task 16.2 implemented by Agent_AdapterGovernance and Task 17.1 implemented by Agent_QualityRelease.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_17_Evidence_Integrity_and_CI_Gate_Repair.md`.
2. Read `docs/repo-wiki-phase-14-16-review-and-phase-17-20-plan.md`.
3. Read `.apm/Memory/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate/Task_16_2_CI_cutover_template_pack_and_policy_profiles.md`.
4. Read `.apm/Memory/Phase_17_Evidence_Integrity_and_CI_Gate_Repair/Task_17_1_Decision_evidence_reconciliation_and_dossier_canonicalization.md`.
5. Inspect `.github/workflows/repo-wiki-*.yml`, `ci/scripts/decision.sh`, and `ci/profiles/*.yaml`.

## Objective
Make CI decision gates enforce policy outcomes instead of silently continuing after rejected results.

## Detailed Instructions
- Replace Python execution of shell scripts with correct shell execution.
- Remove non-blocking `|| true` from strict and transitional decision gates.
- Define pilot `allow-continue` behavior explicitly.
- Remove or replace undeclared dependencies such as `bc`.
- Add simulation tests for strict, transitional, and pilot outcomes.

## Expected Output
- Deliverables: corrected workflows, hardened decision script, CI docs, profile simulation tests.
- Success criteria: strict/transitional rejected gates fail the job; pilot behavior is explicit and tested.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_17_Evidence_Integrity_and_CI_Gate_Repair/Task_17_2_CI_decision_gate_enforcement_and_workflow_correctness.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block using `.claude/commands/apm-3-initiate-implementation.md`.
```

## Task 17.3

```markdown
---
task_ref: "Task 17.3 - Python packaging and reproducible test harness repair"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_17_Evidence_Integrity_and_CI_Gate_Repair/Task_17_3_Python_packaging_and_reproducible_test_harness_repair.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Python packaging and reproducible test harness repair

## Task Reference
Implementation Plan: **Task 17.3 - Python packaging and reproducible test harness repair** assigned to **Agent_PlatformCore**

## Context from Dependencies
This task depends on Task 17.2 implemented by Agent_AdapterGovernance.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_17_Evidence_Integrity_and_CI_Gate_Repair.md`.
2. Read `docs/repo-wiki-phase-14-16-review-and-phase-17-20-plan.md`.
3. Read `.apm/Memory/Phase_17_Evidence_Integrity_and_CI_Gate_Repair/Task_17_2_CI_decision_gate_enforcement_and_workflow_correctness.md`.
4. Inspect `pyproject.toml` and current package layout.
5. Reproduce and fix the editable build failure under `uv run`.

## Objective
Repair package discovery and provide a reproducible test harness for governance tests.

## Detailed Instructions
- Configure package discovery so only intended Python packages are installed.
- Keep non-package directories such as `ai`, `templates`, and `extensions` out of setuptools auto-discovery.
- Verify `uv run pytest` works for the Phase 14-16/17 target test subset.
- Document the local and CI test commands.
- Add packaging regression coverage where practical.

## Expected Output
- Deliverables: `pyproject.toml` packaging fix, test command docs, passing targeted tests.
- Success criteria: governance tests run from a clean `uv run` environment.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_17_Evidence_Integrity_and_CI_Gate_Repair/Task_17_3_Python_packaging_and_reproducible_test_harness_repair.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block using `.claude/commands/apm-3-initiate-implementation.md`.
```

## Task 17.4

```markdown
---
task_ref: "Task 17.4 - Governance regression tests for known review failures"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_17_Evidence_Integrity_and_CI_Gate_Repair/Task_17_4_Governance_regression_tests_for_known_review_failures.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Governance regression tests for known review failures

## Task Reference
Implementation Plan: **Task 17.4 - Governance regression tests for known review failures** assigned to **Agent_QualityRelease**

## Context from Dependencies
This task depends on Task 17.1, Task 17.2, and Task 17.3.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_17_Evidence_Integrity_and_CI_Gate_Repair.md`.
2. Read `docs/repo-wiki-phase-14-16-review-and-phase-17-20-plan.md`.
3. Read all completed Phase 17 task logs.
4. Inspect updated workflows, decision script, comparator config, and evidence docs.
5. Build tests around the exact review failures.

## Objective
Add regression tests so Phase 14-16 governance failures cannot reappear unnoticed.

## Detailed Instructions
- Add a test for `BaselineComparatorConfig().to_dict()`.
- Add checks that workflows do not run `decision.sh` through Python.
- Add checks that strict/transitional gates are not non-blocking.
- Add evidence path existence checks for claimed dossier/handover outputs.
- Include these tests in the documented governance test subset.

## Expected Output
- Deliverables: governance regression tests and updated test docs.
- Success criteria: all known review failures are covered by tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_17_Evidence_Integrity_and_CI_Gate_Repair/Task_17_4_Governance_regression_tests_for_known_review_failures.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block using `.claude/commands/apm-3-initiate-implementation.md`.
```
