# Phase 19 - Viewer and IDE Hardening

## Task 19.1

```markdown
---
task_ref: "Task 19.1 - Static viewer offline asset and safety hardening"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_19_Viewer_and_IDE_Hardening/Task_19_1_Static_viewer_offline_asset_and_safety_hardening.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Static viewer offline asset and safety hardening

## Task Reference
Implementation Plan: **Task 19.1 - Static viewer offline asset and safety hardening** assigned to **Agent_PlatformCore**

## Context from Dependencies
Depends on Task 18.4 and Task 15.2. Read `docs/phases/Phase_19_Viewer_and_IDE_Hardening.md`, `docs/repo-wiki-phase-14-16-review-and-phase-17-20-plan.md`, and relevant Memory logs.

## Objective
Make the static viewer local-first and safer for manual acceptance.

## Detailed Instructions
- Replace CDN-only Mermaid loading with bundled or configurable local assets.
- Define markdown/HTML rendering safety boundaries.
- Keep viewer driven by manifest and markdown artifacts.
- Add offline viewer tests for Mermaid and static assets.

## Expected Output
- Deliverables: offline viewer asset strategy, safer rendering, tests, docs.
- Success criteria: viewer works from eval artifacts without network dependency.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_19_Viewer_and_IDE_Hardening/Task_19_1_Static_viewer_offline_asset_and_safety_hardening.md`
```

## Task 19.2

```markdown
---
task_ref: "Task 19.2 - VS Code extension runtime path and manifest discovery repair"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_19_Viewer_and_IDE_Hardening/Task_19_2_VS_Code_extension_runtime_path_and_manifest_discovery_repair.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: VS Code extension runtime path and manifest discovery repair

## Task Reference
Implementation Plan: **Task 19.2 - VS Code extension runtime path and manifest discovery repair** assigned to **Agent_PlatformCore**

## Context from Dependencies
Depends on Task 19.1 and Task 15.3. Read completed Task 19.1 log and extension source before editing.

## Objective
Fix VS Code extension runtime file opening and eval run manifest discovery.

## Detailed Instructions
- Resolve wiki node paths against workspace root.
- Discover timestamped `.repo-agent-eval/<run_id>/manifest.json` files.
- Define latest-run or active-run behavior.
- Validate update/verify command invocations.
- Add extension smoke tests where practical.

## Expected Output
- Deliverables: extension runtime fixes, docs, tests.
- Success criteria: sidebar clicks open correct files from selected eval run.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_19_Viewer_and_IDE_Hardening/Task_19_2_VS_Code_extension_runtime_path_and_manifest_discovery_repair.md`
```

## Task 19.3

```markdown
---
task_ref: "Task 19.3 - Visual acceptance snapshots and navigation regression suite"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_19_Viewer_and_IDE_Hardening/Task_19_3_Visual_acceptance_snapshots_and_navigation_regression_suite.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Visual acceptance snapshots and navigation regression suite

## Task Reference
Implementation Plan: **Task 19.3 - Visual acceptance snapshots and navigation regression suite** assigned to **Agent_QualityRelease**

## Context from Dependencies
Depends on Tasks 19.1 and 19.2. Read their logs and use current eval artifacts as viewer fixtures.

## Objective
Add reproducible visual and navigation evidence for manual acceptance tooling.

## Detailed Instructions
- Build snapshot coverage for representative desktop and narrow viewports.
- Verify navigation tree, page rendering, Mermaid presence, and broken-link behavior.
- Store visual evidence in the canonical evidence bundle.
- Make visual acceptance part of release-candidate evidence.

## Expected Output
- Deliverables: snapshot harness, navigation regression report, visual evidence docs.
- Success criteria: viewer usability is verified beyond compile success.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_19_Viewer_and_IDE_Hardening/Task_19_3_Visual_acceptance_snapshots_and_navigation_regression_suite.md`
```

## Task 19.4

```markdown
---
task_ref: "Task 19.4 - Qoder side-by-side navigation comparison hardening"
agent_assignment: "Agent_AdapterGovernance"
memory_log_path: ".apm/Memory/Phase_19_Viewer_and_IDE_Hardening/Task_19_4_Qoder_side_by_side_navigation_comparison_hardening.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Qoder side-by-side navigation comparison hardening

## Task Reference
Implementation Plan: **Task 19.4 - Qoder side-by-side navigation comparison hardening** assigned to **Agent_AdapterGovernance**

## Context from Dependencies
Depends on Task 19.3 and Task 15.4. Read completed logs and current qoder adapter implementation.

## Objective
Make qoder-style navigation import useful for side-by-side review while preserving canonical contracts.

## Detailed Instructions
- Validate imported qoder navigation against actual files and canonical sections.
- Report unmatched nodes, alias conflicts, and depth mismatches.
- Produce side-by-side navigation comparison output for manual review.
- Keep imported metadata read-only.
- Add AI_API_Atlas-style fixture tests.

## Expected Output
- Deliverables: side-by-side nav compare report, adapter hardening, tests, docs.
- Success criteria: qoder navigation can be compared without mutating repo-agent canonical output.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_19_Viewer_and_IDE_Hardening/Task_19_4_Qoder_side_by_side_navigation_comparison_hardening.md`
```
