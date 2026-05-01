# Phase 20 - Transitional Release Candidate and Strict Gap Plan

## Task 20.1

```markdown
---
task_ref: "Task 20.1 - External fixture provenance and benchmark refresh policy"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_20_Transitional_Release_Candidate_and_Strict_Gap_Plan/Task_20_1_External_fixture_provenance_and_benchmark_refresh_policy.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: External fixture provenance and benchmark refresh policy

## Task Reference
Implementation Plan: **Task 20.1 - External fixture provenance and benchmark refresh policy** assigned to **Agent_QualityRelease**

## Context from Dependencies
Depends on Task 14.1 and Task 18.4. Read `docs/phases/Phase_20_Transitional_Release_Candidate_and_Strict_Gap_Plan.md` and prior evidence docs.

## Objective
Define provenance, freshness, and confidence rules for external qoder snapshot fixtures.

## Detailed Instructions
- Define accepted fixture sources and required capture metadata.
- Add freshness and confidence scoring to release-candidate compare inputs.
- Reject stale or incomplete fixtures for release gates.
- Document fixture refresh workflow and maintainer checklist.

## Expected Output
- Deliverables: fixture provenance policy, refresh workflow, confidence scoring, tests/docs.
- Success criteria: release-candidate comparisons cannot use untrusted or stale fixtures silently.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_20_Transitional_Release_Candidate_and_Strict_Gap_Plan/Task_20_1_External_fixture_provenance_and_benchmark_refresh_policy.md`
```

## Task 20.2

```markdown
---
task_ref: "Task 20.2 - Release-candidate pilot across benchmark repositories"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_20_Transitional_Release_Candidate_and_Strict_Gap_Plan/Task_20_2_Release_candidate_pilot_across_benchmark_repositories.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Release-candidate pilot across benchmark repositories

## Task Reference
Implementation Plan: **Task 20.2 - Release-candidate pilot across benchmark repositories** assigned to **Agent_QualityRelease**

## Context from Dependencies
Depends on Task 19.4 and Task 20.1. Read their logs and use repaired CI/evidence flow from Phase 17.

## Objective
Run a release-candidate pilot using repaired gates, improved content, and hardened viewer evidence.

## Detailed Instructions
- Run generation, verify, compare, visual acceptance, and policy decision per benchmark repo.
- Require transitional profile to pass for candidate repositories.
- Store all evidence under canonical eval layout.
- Separate strict-profile gaps from transitional release status.

## Expected Output
- Deliverables: cross-repo RC evidence bundle, policy outcome matrix, residual risk register.
- Success criteria: Manager can judge transitional replacement readiness from reproducible evidence.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_20_Transitional_Release_Candidate_and_Strict_Gap_Plan/Task_20_2_Release_candidate_pilot_across_benchmark_repositories.md`
```

## Task 20.3

```markdown
---
task_ref: "Task 20.3 - Strict threshold gap backlog and ownership plan"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_20_Transitional_Release_Candidate_and_Strict_Gap_Plan/Task_20_3_Strict_threshold_gap_backlog_and_ownership_plan.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Strict threshold gap backlog and ownership plan

## Task Reference
Implementation Plan: **Task 20.3 - Strict threshold gap backlog and ownership plan** assigned to **Agent_QualityRelease**

## Context from Dependencies
Depends on Task 20.2. Read release-candidate outcomes and score deficits before creating backlog.

## Objective
Translate remaining strict-profile gaps into owned, prioritized, measurable backlog items.

## Detailed Instructions
- Break score deficits into generator, verifier, viewer, and governance work items.
- Assign owner role and acceptance metric to each item.
- Separate strict blockers from polish improvements.
- Identify product-decision gaps separately from implementation gaps.

## Expected Output
- Deliverables: strict gap backlog, owner map, acceptance criteria, sequencing recommendation.
- Success criteria: strict 85% path is explicit and executable.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_20_Transitional_Release_Candidate_and_Strict_Gap_Plan/Task_20_3_Strict_threshold_gap_backlog_and_ownership_plan.md`
```

## Task 20.4

```markdown
---
task_ref: "Task 20.4 - Transitional go/no-go dossier and manager handover"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_20_Transitional_Release_Candidate_and_Strict_Gap_Plan/Task_20_4_Transitional_go_no_go_dossier_and_manager_handover.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Transitional go/no-go dossier and manager handover

## Task Reference
Implementation Plan: **Task 20.4 - Transitional go/no-go dossier and manager handover** assigned to **Agent_QualityRelease**

## Context from Dependencies
Depends on Task 20.2 and Task 20.3. Read all Phase 20 evidence before writing final judgment.

## Objective
Produce a transitional go/no-go dossier and Manager handover package.

## Detailed Instructions
- State whether repo-agent can replace qoder for transitional/pilot environments.
- Keep strict production replacement separate unless strict criteria are met.
- Link every claim to evidence files.
- Update Memory Root with final phase judgment.
- Prepare handover for the next execution cycle.

## Expected Output
- Deliverables: transitional decision dossier, evidence index, handover checklist, next-phase recommendation.
- Success criteria: the next Manager can continue without reconciling contradictory evidence.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_20_Transitional_Release_Candidate_and_Strict_Gap_Plan/Task_20_4_Transitional_go_no_go_dossier_and_manager_handover.md`
```
