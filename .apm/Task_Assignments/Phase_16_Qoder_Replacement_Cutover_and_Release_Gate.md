# Phase 16 – Qoder-Replacement Cutover and Release Gate

## Task 16.1

```markdown
---
task_ref: "Task 16.1 - Replacement gate policy and rollback playbook"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate/Task_16_1_Replacement_gate_policy_and_rollback_playbook.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Replacement gate policy and rollback playbook

## Task Reference
Implementation Plan: **Task 16.1 - Replacement gate policy and rollback playbook** assigned to **Agent_QualityRelease**

## Context from Dependencies
This task depends on Task 14.4 implemented by Agent_IndexGraph and Task 15.4 implemented by Agent_AdapterGovernance.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate.md`.
2. Read `.apm/Memory/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance/Task_14_4_SQLite_backed_governance_dashboard_export_and_trends.md`.
3. Read `.apm/Memory/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration/Task_15_4_Qoder_style_navigation_metadata_adapter_and_import_bridge.md`.
4. Review existing readiness reports and acceptance evidence schema.
5. Review prior manager go/no-go criteria in roadmap and audit docs.

**Producer Output Summary:**
- Task 14.4 provides trend evidence support.
- Task 15.4 provides compatibility import signals for visual parity evaluation.

**Integration Requirements:**
- Define mandatory replacement gates and optional transitional gates.
- Include rollback criteria and recovery workflow.
- Bind every gate item to measurable evidence sources.

**User Clarification Protocol:**
If policy strictness conflicts with current business rollout expectations, stop and ask whether to publish strict and transitional profiles separately.

## Objective
Create a formal replacement policy and rollback playbook for qoder repo-wiki substitution decisions.

## Detailed Instructions
- Complete all items in one response.
- Define hard gate, soft gate, and transitional criteria.
- Link criteria to verify/compare/runtime/visual evidence.
- Define rollback triggers, actions, and decision authority.
- Add policy validation checks and templates.
- Document usage for Manager sign-off.

## Expected Output
- Deliverables: replacement policy, rollback playbook, validation checks, documentation.
- Success criteria: Manager can execute repeatable go/no-go decisions with clear rollback safety.
- File locations: `docs/operations/**`, governance scripts/configs, tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate/Task_16_1_Replacement_gate_policy_and_rollback_playbook.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 16.2

```markdown
---
task_ref: "Task 16.2 - CI cutover template pack and policy profiles"
agent_assignment: "Agent_AdapterGovernance"
memory_log_path: ".apm/Memory/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate/Task_16_2_CI_cutover_template_pack_and_policy_profiles.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: CI cutover template pack and policy profiles

## Task Reference
Implementation Plan: **Task 16.2 - CI cutover template pack and policy profiles** assigned to **Agent_AdapterGovernance**

## Context from Dependencies
This task depends on Task 16.1 implemented by Agent_QualityRelease and Task 11.1 implemented by Agent_AdapterGovernance.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate.md`.
2. Read `.apm/Memory/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate/Task_16_1_Replacement_gate_policy_and_rollback_playbook.md`.
3. Read `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_1_Hard_gate_vs_soft_gate_verify_redesign.md`.
4. Review current CI integration patterns and verify/compare machine outputs.
5. Review profile threshold definitions from Phase 14 artifacts.

**Producer Output Summary:**
- Task 16.1 defines replacement policy criteria.
- Task 11.1 provides hard/soft gate semantics for CI enforcement.

**Integration Requirements:**
- Encode strict, transitional, and pilot profiles in reusable CI templates.
- Preserve machine-readable outputs for automated policy checks.
- Ensure failed checks include clear remediation evidence references.

**User Clarification Protocol:**
If policy enforcement would break existing pipelines lacking compare artifacts, stop and ask whether to support staged CI adoption.

## Objective
Package replacement governance policies into reusable CI templates and profile-based enforcement configs.

## Detailed Instructions
- Complete all items in one response.
- Build CI templates for strict/transitional/pilot profiles.
- Integrate verify and compare checks with policy evaluation logic.
- Provide failure messages tied to evidence bundle paths.
- Add tests or simulation fixtures for profile behavior.
- Document migration steps from legacy CI checks.

## Expected Output
- Deliverables: CI templates, policy profile configs, enforcement scripts, docs, tests.
- Success criteria: repositories can adopt replacement governance with minimal manual glue code.
- File locations: CI/workflow templates, governance scripts, docs, tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate/Task_16_2_CI_cutover_template_pack_and_policy_profiles.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 16.3

```markdown
---
task_ref: "Task 16.3 - Final pilot execution across Atlas and benchmark repositories"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate/Task_16_3_Final_pilot_execution_across_Atlas_and_benchmark_repositories.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Final pilot execution across Atlas and benchmark repositories

## Task Reference
Implementation Plan: **Task 16.3 - Final pilot execution across Atlas and benchmark repositories** assigned to **Agent_QualityRelease**

## Context from Dependencies
This task depends on Task 16.2 implemented by Agent_AdapterGovernance and Task 14.3 implemented by Agent_QualityRelease.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate.md`.
2. Read `.apm/Memory/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate/Task_16_2_CI_cutover_template_pack_and_policy_profiles.md`.
3. Read `.apm/Memory/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance/Task_14_3_Cross_repository_benchmark_matrix_and_threshold_profiles.md`.
4. Review benchmark repository list and profile thresholds.
5. Review evidence bundle and readiness report schema.

**Producer Output Summary:**
- Task 16.2 enables policy-enforced CI execution.
- Task 14.3 provides benchmark baselines and threshold profiles.

**Integration Requirements:**
- Execute full pilot flow on Atlas plus benchmark repositories.
- Produce per-repository policy outcome and residual risk capture.
- Validate rollback path with at least one drill scenario.

**User Clarification Protocol:**
If one or more benchmark repositories are unavailable for pilot execution, stop and ask whether to proceed with reduced sample and explicit confidence downgrade.

## Objective
Run final cross-repository pilots under cutover policies and produce release-readiness evidence.

## Detailed Instructions
- Complete all items in one response.
- Execute generation, verify, compare, and visual acceptance per policy profile.
- Collect outcomes and residual risk register for each repository.
- Perform rollback drill and record results.
- Update readiness summary with profile-level pass/fail.
- Provide recommendation for final decision dossier.

## Expected Output
- Deliverables: pilot execution reports, residual risk register, rollback drill evidence, recommendation.
- Success criteria: final decision can rely on reproducible multi-repository pilot evidence.
- File locations: `docs/operations/**`, evidence bundles, CI run artifacts.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate/Task_16_3_Final_pilot_execution_across_Atlas_and_benchmark_repositories.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 16.4

```markdown
---
task_ref: "Task 16.4 - Go/no-go decision dossier and handover package"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate/Task_16_4_Go_no_go_decision_dossier_and_handover_package.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Go/no-go decision dossier and handover package

## Task Reference
Implementation Plan: **Task 16.4 - Go/no-go decision dossier and handover package** assigned to **Agent_QualityRelease**

## Context from Dependencies
This task depends on Task 16.3 implemented by Agent_QualityRelease.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate.md`.
2. Read `.apm/Memory/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate/Task_16_3_Final_pilot_execution_across_Atlas_and_benchmark_repositories.md`.
3. Read replacement policy artifacts from Task 16.1 and CI profile artifacts from Task 16.2.
4. Review all linked evidence bundles and trend exports for audit completeness.
5. Validate that decision conclusions map to explicit gate outcomes.

**Producer Output Summary:**
- Task 16.3 provides final pilot outcomes and residual risks required for final decisioning.

**Integration Requirements:**
- Produce one auditable dossier with explicit go/no-go verdict.
- Include rollout ordering, ownership, and fallback path.
- Separate confirmed blockers from deferred improvements.

**User Clarification Protocol:**
If evidence remains incomplete for one or more mandatory gates, stop and ask whether to issue provisional no-go or reopen pilot scope.

## Objective
Deliver final go/no-go decision dossier and operational handover package for qoder replacement.

## Detailed Instructions
- Complete all items in one response.
- Aggregate phase evidence into one decision-grade package.
- State final verdict with blocking reasons or acceptance scope.
- Provide rollout sequence and owner mapping.
- Provide post-cutover backlog for deferred non-blocking improvements.
- Publish handover checklist for ongoing governance operations.

## Expected Output
- Deliverables: final decision dossier, handover package, rollout and backlog plan.
- Success criteria: leadership and implementation teams can execute next steps without ambiguity.
- File locations: `docs/operations/**`, handover docs, governance references.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate/Task_16_4_Go_no_go_decision_dossier_and_handover_package.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```
