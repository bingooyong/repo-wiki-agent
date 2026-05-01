# Phase 05 – Pilot Acceptance, CI Packaging, and Release Gate

## Task 5.1

```markdown
---
task_ref: "Task 5.1 - Pilot acceptance protocol and metric instrumentation"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_05_Pilot_Acceptance_CI_Packaging_and_Release_Gate/Task_5_1_Pilot_acceptance_protocol_and_metric_instrumentation.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Pilot acceptance protocol and metric instrumentation

## Task Reference
Implementation Plan: **Task 5.1 - Pilot acceptance protocol and metric instrumentation** assigned to **Agent_QualityRelease**

## Context from Dependencies
This task depends on Task 3.3 and Task 4.2.

**Integration Steps (complete in one response):**
1. Read `.apm/Memory/Phase_03_Documentation_Generation_and_Command_Orchestration/Task_3_3_Core_command_orchestration_for_init_update_index_search_graph_and_cost_estimate.md` to identify the actual command surfaces and orchestration behavior available for pilot execution.
2. Read `.apm/Memory/Phase_04_Adapter_Output_and_Verification/Task_4_2_Verify_command_and_CI_mode_governance_checks.md` to identify the verify contract, CI behavior, and governance checks available to pilot validation.
3. Review the referenced implementation files before defining acceptance scripts and metrics.

**Producer Output Summary:**
- Task 3.3 provides the executable command pipeline.
- Task 4.2 provides the governance and verification contract.

**Integration Requirements:**
- Pilot validation must use the frozen MVP acceptance criteria from the implementation plan.
- Metric capture must cover the defined functional and engineering targets without inventing new gates.

**User Clarification Protocol:**
If the command pipeline or verify contract is not stable enough to execute a pilot, stop and ask whether upstream tasks need refinement before running acceptance design.

## Objective
Validate that the full MVP works on a real medium-sized backend repository using the frozen acceptance criteria.

## Detailed Instructions
- Complete all items in one response.
- Define pilot repository qualification rules based on the plan.
- Define the acceptance scenarios for `init`, `search`, `graph`, `update`, and `verify`.
- Instrument the frozen acceptance metrics from the plan.
- Prepare scripts, checklists, or evidence capture conventions that make pilot execution reproducible.
- Produce a pass/fail summary template against the MVP engineering targets.

## Expected Output
- Deliverables: pilot playbook, metric capture scripts or checklists, evidence pack structure, acceptance summary template.
- Success criteria: the pilot protocol can validate the exact MVP targets with reproducible evidence and no extra acceptance scope.
- File locations: quality or release documentation/scripts and any helper assets needed for acceptance runs.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_05_Pilot_Acceptance_CI_Packaging_and_Release_Gate/Task_5_1_Pilot_acceptance_protocol_and_metric_instrumentation.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 5.2

```markdown
---
task_ref: "Task 5.2 - CI automation and governance packaging"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_05_Pilot_Acceptance_CI_Packaging_and_Release_Gate/Task_5_2_CI_automation_and_governance_packaging.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: CI automation and governance packaging

## Task Reference
Implementation Plan: **Task 5.2 - CI automation and governance packaging** assigned to **Agent_QualityRelease**

## Context from Dependencies
This task depends on Task 4.2 implemented by Agent_AdapterGovernance.

**Integration Steps (complete in one response):**
1. Read `.apm/Memory/Phase_04_Adapter_Output_and_Verification/Task_4_2_Verify_command_and_CI_mode_governance_checks.md` to identify the actual `verify --ci` behavior and governance outputs available.
2. Review the referenced implementation files before packaging automation around them.
3. Keep CI and local workflow packaging centered on the existing verify contract instead of creating a separate policy surface.

**Producer Output Summary:**
- Task 4.2 provides the machine-readable verify contract and fail behavior that CI packaging must consume.

**Integration Requirements:**
- `Makefile` targets must map to the frozen MVP command set.
- CI workflows must use `verify --ci` as the enforcement anchor.
- Hook guidance must remain safe and non-destructive.

**User Clarification Protocol:**
If the verify command is not yet stable or lacks CI-grade output, stop and ask whether Task 4.2 should be refined before automation packaging proceeds.

## Objective
Deliver repeatable local and CI workflows after the product path is already working.

## Detailed Instructions
- Complete all items in one response.
- Implement `Makefile` targets for `ai-init`, `ai-update`, `ai-verify`, `ai-sync`, and `ai-cost`.
- Implement CI workflow templates centered on `repo-wiki verify --ci`.
- Add safe hook guidance for post-commit reminders.
- Add onboarding and troubleshooting documentation for local and CI usage.
- Validate the automation package in local and CI-like environments.

## Expected Output
- Deliverables: `Makefile` AI targets, CI workflow templates, hook guidance, operational docs, validation notes.
- Success criteria: local and CI packaging directly reuse the frozen command and verify surfaces and remain deterministic.
- File locations: repo root workflow files, CI config paths, and operational documentation.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_05_Pilot_Acceptance_CI_Packaging_and_Release_Gate/Task_5_2_CI_automation_and_governance_packaging.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 5.3

```markdown
---
task_ref: "Task 5.3 - Final readiness review and release gate report"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_05_Pilot_Acceptance_CI_Packaging_and_Release_Gate/Task_5_3_Final_readiness_review_and_release_gate_report.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Final readiness review and release gate report

## Task Reference
Implementation Plan: **Task 5.3 - Final readiness review and release gate report** assigned to **Agent_QualityRelease**

## Context from Dependencies
Build directly on your Task 5.1 and Task 5.2 work.

- Read `.apm/Memory/Phase_05_Pilot_Acceptance_CI_Packaging_and_Release_Gate/Task_5_1_Pilot_acceptance_protocol_and_metric_instrumentation.md` and `.apm/Memory/Phase_05_Pilot_Acceptance_CI_Packaging_and_Release_Gate/Task_5_2_CI_automation_and_governance_packaging.md`.
- Reuse the evidence pack, acceptance criteria, workflow packaging outputs, and validation notes already created.
- Consolidate the release decision; do not reopen upstream implementation unless a real blocker forces that conclusion.

## Objective
Consolidate validation evidence into a final go or no-go recommendation.

## Detailed Instructions
- Complete all items in one response.
- Aggregate outputs and validation evidence from all phases.
- Evaluate compliance with MVP success criteria and identify remaining risks.
- Define rollback or fallback actions for high-risk operational scenarios.
- Produce the release recommendation and required follow-up actions.
- Include the explicit user checkpoint before implementation handoff.

## Expected Output
- Deliverables: readiness report, unresolved risk register, rollback guidance, launch recommendation.
- Success criteria: the final gate clearly states whether the MVP is ready, what evidence supports the decision, and what must happen next if it is not ready.
- File locations: release or quality reporting outputs and any supporting summary assets.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_05_Pilot_Acceptance_CI_Packaging_and_Release_Gate/Task_5_3_Final_readiness_review_and_release_gate_report.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```
