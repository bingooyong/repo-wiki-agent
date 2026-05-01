# Phase 13 – Atlas Cutover and Hard-Gate Clearance

## Task 13.1

```markdown
---
task_ref: "Task 13.1 - Runtime-store orchestration integration across core commands"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_1_Runtime_store_orchestration_integration_across_core_commands.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Runtime-store orchestration integration across core commands

## Task Reference
Implementation Plan: **Task 13.1 - Runtime-store orchestration integration across core commands** assigned to **Agent_IndexGraph**

## Context from Dependencies
This task depends on Task 12.4 implemented by Agent_IndexGraph and Task 3.3 implemented by Agent_PlatformCore.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance.md`.
2. Read `docs/repo-wiki-phase-09-12-audit-atlas-comparison-and-phase-13-plan.md` to capture runtime落地缺口。
3. Read `.apm/Memory/Phase_12_SQLite_First_Local_Knowledge_Runtime/Task_12_4_SQLite_driven_page_invalidation_and_incremental_regeneration.md`.
4. Read `.apm/Memory/Phase_03_Documentation_Generation_and_Command_Orchestration/Task_3_3_Core_command_orchestration_for_init_update_index_search_graph_and_cost_estimate.md`.
5. Review current command orchestration and runtime store integration points before making changes.

**Producer Output Summary:**
- Task 12.4 provides page-level invalidation runtime logic.
- Task 3.3 defines command orchestration surfaces that now need runtime evidence hooks.

**Integration Requirements:**
- Keep command surface unchanged (`init/index/update/verify/sync/search/graph/cost-estimate`).
- Make runtime DB lifecycle deterministic in first-run, upgrade, and recovery paths.
- Persist verify/compare-related evidence prerequisites for downstream acceptance.

**User Clarification Protocol:**
If runtime integration requires command contract changes that cannot remain backward-compatible, stop and ask whether compatibility-breaking changes are allowed in Phase 13.

## Objective
Integrate runtime SQLite orchestration into core command flows so evidence tables are created and maintained automatically.

## Detailed Instructions
- Complete all items in one response.
- Integrate runtime store initialization into command entrypoints for `init`, `index`, `update`, and `verify`.
- Ensure schema bootstrap and migration are safe across repeated runs.
- Add fallback behavior for missing/corrupt runtime DB with clear diagnostics.
- Add integration tests that validate runtime evidence persistence during typical workflows.
- Keep all changes local-first and deterministic.

## Expected Output
- Deliverables: runtime orchestration integration, schema lifecycle handling, diagnostics, integration tests.
- Success criteria: Atlas acceptance runs can rely on runtime evidence tables without manual DB preparation.
- File locations: `repo_wiki/orchestration/**`, command orchestration modules, and tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_1_Runtime_store_orchestration_integration_across_core_commands.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 13.2

```markdown
---
task_ref: "Task 13.2 - Section compatibility bridge for Q*/S* formats"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_2_Section_compatibility_bridge_for_Q_and_S_formats.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Section compatibility bridge for Q*/S* formats

## Task Reference
Implementation Plan: **Task 13.2 - Section compatibility bridge for Q*/S* formats** assigned to **Agent_DocGen**

## Context from Dependencies
This task depends on Task 9.3 implemented by Agent_DocGen and Task 13.1 implemented by Agent_IndexGraph.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance.md`.
2. Read `docs/operations/AI_API_Atlas_Readiness_Report.md` and `docs/AI_API_Atlas_repo_wiki_gap_analysis.md`.
3. Read `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_3_Phase_and_section_registry_completion_with_alias_support.md`.
4. Read `.apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_1_Runtime_store_orchestration_integration_across_core_commands.md`.
5. Review section registry, alias handling, and verifier section checks before implementing.

**Producer Output Summary:**
- Task 9.3 introduced alias-capable registry.
- Task 13.1 ensures runtime tables can persist compatibility evidence.

**Integration Requirements:**
- Preserve canonical section slugs as primary contract.
- Support explicit alias overlays for Q*/S* patterns without weakening canonical checks.
- Ensure verify and generation share the same compatibility mapping.

**User Clarification Protocol:**
If compatibility requires replacing canonical section naming as the generation default, stop and ask whether this repository accepts canonical-contract changes.

## Objective
Implement deterministic section compatibility mapping so legacy Q*/S* structures can pass compatibility checks via explicit alias/overlay rules.

## Detailed Instructions
- Complete all items in one response.
- Extend section registry mapping for Q*/S* style aliases and overlay semantics.
- Ensure section existence checks resolve through canonical plus alias bridge.
- Persist alias resolution evidence for diagnostics and readiness reports.
- Add tests for canonical-only, alias-only, and mixed-mode repositories.
- Document precedence rules and conflict handling.

## Expected Output
- Deliverables: section compatibility bridge, alias resolution logic, verifier alignment, tests, and docs.
- Success criteria: repositories with legacy section naming can pass structural checks without rewriting canonical contracts.
- File locations: `repo_wiki/generator/**`, `repo_wiki/verifier/**`, runtime evidence helpers, and tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_2_Section_compatibility_bridge_for_Q_and_S_formats.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 13.3

```markdown
---
task_ref: "Task 13.3 - Atlas core-document narrative and aggregation remediation"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_3_Atlas_core_document_narrative_and_aggregation_remediation.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Atlas core-document narrative and aggregation remediation

## Task Reference
Implementation Plan: **Task 13.3 - Atlas core-document narrative and aggregation remediation** assigned to **Agent_DocGen**

## Context from Dependencies
This task depends on Task 10.4 implemented by Agent_DocGen and Task 13.2 implemented by Agent_DocGen.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance.md`.
2. Read `docs/operations/AI_API_Atlas_Readiness_Report.md` and target FAIL reason codes.
3. Read `.apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_4_Section_page_builder_rewrite_for_document_center_behavior.md`.
4. Read `.apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_2_Section_compatibility_bridge_for_Q_and_S_formats.md`.
5. Review current builders for `00-overview.md`, `01-architecture.md`, `03-module-map.md`, `04-api-contracts.md`, and `05-data-model.md`.

**Producer Output Summary:**
- Task 10.4 provides narrative and topical section generation baseline.
- Task 13.2 provides section compatibility contract needed for Atlas.

**Integration Requirements:**
- Close known Atlas quality failures without hardcoding repository-only hacks.
- Keep prose-first and aggregated contracts aligned with verify checks.
- Preserve navigability and source-of-truth traceability.

**User Clarification Protocol:**
If Atlas-specific remediation requires non-portable hardcoded repository constants, stop and ask whether to proceed with profile-based customization.

## Objective
Remediate Atlas core docs so narrative depth, Mermaid requirements, and aggregation quality pass updated governance thresholds.

## Detailed Instructions
- Complete all items in one response.
- Improve repository-fact-backed narrative in overview and architecture docs.
- Ensure architecture always includes valid Mermaid and explanatory prose.
- Upgrade API/Data Model summaries to grouped and non-dump output.
- Validate module-map and section navigation consistency.
- Add targeted regression tests using Atlas fixtures.

## Expected Output
- Deliverables: improved core-doc builders/templates, Atlas fixture tests, quality-threshold checks.
- Success criteria: Atlas core docs no longer fail due to short prose, missing Mermaid, or non-grouped aggregation.
- File locations: `repo_wiki/generator/**`, templates, fixtures, tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_3_Atlas_core_document_narrative_and_aggregation_remediation.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 13.4

```markdown
---
task_ref: "Task 13.4 - Atlas hard-gate clearance and blocker burn-down report"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_4_Atlas_hard_gate_clearance_and_blocker_burndown_report.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Atlas hard-gate clearance and blocker burn-down report

## Task Reference
Implementation Plan: **Task 13.4 - Atlas hard-gate clearance and blocker burn-down report** assigned to **Agent_QualityRelease**

## Context from Dependencies
This task depends on Task 13.1 implemented by Agent_IndexGraph, Task 13.2 implemented by Agent_DocGen, and Task 13.3 implemented by Agent_DocGen.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance.md`.
2. Read `.apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_1_Runtime_store_orchestration_integration_across_core_commands.md`.
3. Read `.apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_2_Section_compatibility_bridge_for_Q_and_S_formats.md`.
4. Read `.apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_3_Atlas_core_document_narrative_and_aggregation_remediation.md`.
5. Reuse unified readiness schema from `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_3_Unified_readiness_report_schema_and_evidence_bundle.md`.

**Producer Output Summary:**
- Tasks 13.1-13.3 should provide runtime support, section compatibility, and core-doc quality remediation for Atlas.

**Integration Requirements:**
- Run full Atlas acceptance chain with reproducible evidence.
- Separate hard blockers, soft quality issues, and compatibility overlays.
- Produce actionable burn-down table tied to next-phase planning.

**User Clarification Protocol:**
If Atlas environment prerequisites are missing and block full acceptance execution, stop and ask whether to run partial evidence mode or wait for environment completion.

## Objective
Execute end-to-end Atlas acceptance and generate a blocker burn-down report that drives Phase 14 decisions.

## Detailed Instructions
- Complete all items in one response.
- Run generation/update/verify/compare acceptance flow for Atlas.
- Collect evidence bundle and runtime trend outputs.
- Produce blocker matrix with owner, severity, and remediation target task.
- Summarize whether Phase 13 exit gate is met.
- Provide explicit recommendation for moving to Phase 14 or recycling fixes.

## Expected Output
- Deliverables: Atlas acceptance outputs, burn-down report, readiness summary.
- Success criteria: Manager can make a clear transition decision with auditable evidence.
- File locations: `docs/operations/**`, `.repo-agent-eval/**`, evidence exports, and tests if updated.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_4_Atlas_hard_gate_clearance_and_blocker_burndown_report.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```
