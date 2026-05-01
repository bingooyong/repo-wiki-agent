# Phase 18 - Transitional Quality Uplift

## Task 18.1

```markdown
---
task_ref: "Task 18.1 - Section coverage completion and navigation contract repair"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_18_Transitional_Quality_Uplift/Task_18_1_Section_coverage_completion_and_navigation_contract_repair.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Section coverage completion and navigation contract repair

## Task Reference
Implementation Plan: **Task 18.1 - Section coverage completion and navigation contract repair** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 17.4 and Task 15.4. Read `docs/phases/Phase_18_Transitional_Quality_Uplift.md`, `docs/repo-wiki-phase-14-16-review-and-phase-17-20-plan.md`, and the relevant Memory logs before editing.

## Objective
Complete required section coverage and repair section navigation for transitional acceptance.

## Detailed Instructions
- Generate or map all required sections, including troubleshooting.
- Repair overview-to-section and section-to-overview links through shared link contracts.
- Preserve canonical section slugs while keeping qoder overlays compatible.
- Add tests for required section set and navigation links.

## Expected Output
- Deliverables: section generation/mapping updates, navigation fixes, tests.
- Success criteria: section coverage and navigation completeness improve toward transitional threshold.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_18_Transitional_Quality_Uplift/Task_18_1_Section_coverage_completion_and_navigation_contract_repair.md`
```

## Task 18.2

```markdown
---
task_ref: "Task 18.2 - Heading coverage and prose-density generation upgrade"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_18_Transitional_Quality_Uplift/Task_18_2_Heading_coverage_and_prose_density_generation_upgrade.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Heading coverage and prose-density generation upgrade

## Task Reference
Implementation Plan: **Task 18.2 - Heading coverage and prose-density generation upgrade** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 18.1 and Task 10.1. Read Phase 18 docs, Phase 17 review, and completed Task 18.1 log before editing.

## Objective
Improve required heading coverage and prose density without adding generic filler.

## Detailed Instructions
- Add required heading coverage for core docs.
- Increase repository-specific prose in overview, architecture, and section pages.
- Reduce list/table dominance in top-level reading pages.
- Add tests for prose thresholds, headings, and boilerplate repetition.

## Expected Output
- Deliverables: generator/template updates and prose quality tests.
- Success criteria: quality dimensions move materially toward compare >= 0.70.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_18_Transitional_Quality_Uplift/Task_18_2_Heading_coverage_and_prose_density_generation_upgrade.md`
```

## Task 18.3

```markdown
---
task_ref: "Task 18.3 - API and data-model aggregation depth refinement"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_18_Transitional_Quality_Uplift/Task_18_3_API_and_data_model_aggregation_depth_refinement.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: API and data-model aggregation depth refinement

## Task Reference
Implementation Plan: **Task 18.3 - API and data-model aggregation depth refinement** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 18.2, Task 10.2, and Task 10.3. Read relevant logs and current API/DataModel generators before editing.

## Objective
Improve API and data-model aggregation quality so they read as summaries instead of dumps.

## Detailed Instructions
- Group API by service family, auth/error convention, and key entry points.
- Group data models by core entities, service models, storage, and migrations.
- Preserve drilldown details while keeping overview pages bounded.
- Add high-count fixture tests.

## Expected Output
- Deliverables: aggregation refinements, templates, and tests.
- Success criteria: aggregation quality no longer remains a partial/dump-driven score.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_18_Transitional_Quality_Uplift/Task_18_3_API_and_data_model_aggregation_depth_refinement.md`
```

## Task 18.4

```markdown
---
task_ref: "Task 18.4 - Transitional acceptance rerun and quality burn-down"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_18_Transitional_Quality_Uplift/Task_18_4_Transitional_acceptance_rerun_and_quality_burndown.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Transitional acceptance rerun and quality burn-down

## Task Reference
Implementation Plan: **Task 18.4 - Transitional acceptance rerun and quality burn-down** assigned to **Agent_QualityRelease**

## Context from Dependencies
Depends on Tasks 18.1, 18.2, and 18.3. Read their logs and use the repaired Phase 17 test/CI path.

## Objective
Re-run acceptance and produce a burn-down report against transitional thresholds.

## Detailed Instructions
- Run verify and compare with the repaired governance harness.
- Target overall score >= 0.70 and no hard gate failures.
- Store evidence under canonical eval layout.
- Report remaining gaps by dimension and owner.

## Expected Output
- Deliverables: verify/compare evidence, quality burn-down report, go/no-go recommendation for Phase 19.
- Success criteria: Manager can decide whether quality is high enough to harden visual tooling.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_18_Transitional_Quality_Uplift/Task_18_4_Transitional_acceptance_rerun_and_quality_burndown.md`
```
