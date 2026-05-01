# Phase 12 – SQLite-First Local Knowledge Runtime

## Task 12.1

```markdown
---
task_ref: "Task 12.1 - Dual-database runtime architecture for state and evidence"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_12_SQLite_First_Local_Knowledge_Runtime/Task_12_1_Dual_database_runtime_architecture_for_state_and_evidence.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Dual-database runtime architecture for state and evidence

## Task Reference
Implementation Plan: **Task 12.1 - Dual-database runtime architecture for state and evidence** assigned to **Agent_IndexGraph**

## Context from Dependencies
This task depends on Task 11.4 implemented by Agent_QualityRelease and Task 2.1 implemented by Agent_IndexGraph.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_12_SQLite_First_Local_Knowledge_Runtime.md` and `docs/qoder-repo-wiki-sqlite-analysis.md`.
2. Read `docs/repo-wiki-phase-09-12-roadmap.md` to understand the intended runtime role of SQLite.
3. Read `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_4_Multi_repository_regression_acceptance.md`.
4. Read `.apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_1_SQLite_state_and_FTS_foundation.md`.
5. Review the implementation files referenced in those logs before designing the dual-database runtime model.

**Producer Output Summary:**
- Task 2.1 established the current SQLite state and FTS foundation.
- Task 11.4 should provide the acceptance-driven evidence of what runtime data must now be queryable and persistent.

**Integration Requirements:**
- Preserve compatibility with the existing SQLite state foundation.
- Define a clean boundary between operational state and generation/evidence persistence.
- Keep the design local-first and deterministic.

**User Clarification Protocol:**
If existing runtime consumers depend on a single SQLite file and the migration path cannot be inferred from current artifacts, stop and ask whether Phase 12 should initially support both single-DB and dual-DB modes.

## Objective
Define and implement separate responsibilities for operational state and generation/evidence persistence.

## Detailed Instructions
- Complete all items in one response.
- Define the responsibilities of the primary state DB versus a generation/evidence DB.
- Keep compatibility with existing SQLite state while introducing a clean expansion path.
- Document how verify, compare, generation cache, and navigation evidence map onto the new boundary.
- Add migrations or schema versioning support for the expanded runtime model.
- Validate repeated upgrade and rebuild behavior.

## Expected Output
- Deliverables: dual-database architecture, schema plan, migration path, runtime boundary rules, and validation coverage.
- Success criteria: SQLite runtime responsibilities are explicit and ready for hierarchy/evidence expansion.
- File locations: `repo_wiki/indexer/**`, migration helpers, runtime docs, and related tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_12_SQLite_First_Local_Knowledge_Runtime/Task_12_1_Dual_database_runtime_architecture_for_state_and_evidence.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 12.2

```markdown
---
task_ref: "Task 12.2 - SQLite schema for hierarchy, sections, navigation, and evidence"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_12_SQLite_First_Local_Knowledge_Runtime/Task_12_2_SQLite_schema_for_hierarchy_sections_navigation_and_evidence.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: SQLite schema for hierarchy, sections, navigation, and evidence

## Task Reference
Implementation Plan: **Task 12.2 - SQLite schema for hierarchy, sections, navigation, and evidence** assigned to **Agent_IndexGraph**

## Context from Dependencies
This task depends on Task 12.1 implemented by Agent_IndexGraph and Task 9.3 implemented by Agent_DocGen.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_12_SQLite_First_Local_Knowledge_Runtime.md`.
2. Read `.apm/Memory/Phase_12_SQLite_First_Local_Knowledge_Runtime/Task_12_1_Dual_database_runtime_architecture_for_state_and_evidence.md`.
3. Read `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_3_Phase_and_section_registry_completion_with_alias_support.md`.
4. Review the implementation files referenced in those logs before designing schema changes.

**Producer Output Summary:**
- Task 12.1 defines state-vs-evidence DB responsibilities.
- Task 9.3 defines the canonical section and alias registry model that runtime schema must persist.

**Integration Requirements:**
- Store document hierarchy, canonical sections, aliases, and navigation links in structured SQLite form.
- Keep markdown and source-of-truth artifacts as outputs; SQLite becomes the operational metadata backbone.
- Add integrity checks for orphan docs and broken section mappings.

**User Clarification Protocol:**
If registry semantics from Task 9.3 are still changing, stop and ask whether schema design should wait for registry stabilization.

## Objective
Persist document-center structure and quality evidence in SQLite so navigation and readiness become queryable runtime facts.

## Detailed Instructions
- Complete all items in one response.
- Store document hierarchy, canonical sections, aliases, and cross-links in structured SQLite tables.
- Store verify and compare evidence references in queryable form.
- Keep external markdown and source-of-truth artifacts as outputs while SQLite becomes the operational metadata backbone.
- Add integrity checks for orphan docs, broken section mappings, and stale evidence records.
- Validate schema behavior on rebuild and partial-update scenarios.

## Expected Output
- Deliverables: SQLite tables for docs hierarchy, section registry, nav graph, readiness evidence, and related tests.
- Success criteria: document-center structure and evidence are queryable runtime facts instead of ad hoc derived state.
- File locations: `repo_wiki/indexer/**`, schema/migration helpers, and tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_12_SQLite_First_Local_Knowledge_Runtime/Task_12_2_SQLite_schema_for_hierarchy_sections_navigation_and_evidence.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 12.3

```markdown
---
task_ref: "Task 12.3 - Verify and compare persistence with trend analysis"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_12_SQLite_First_Local_Knowledge_Runtime/Task_12_3_Verify_and_compare_persistence_with_trend_analysis.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Verify and compare persistence with trend analysis

## Task Reference
Implementation Plan: **Task 12.3 - Verify and compare persistence with trend analysis** assigned to **Agent_IndexGraph**

## Context from Dependencies
This task depends on Task 12.2 implemented by Agent_IndexGraph, Task 11.1 implemented by Agent_AdapterGovernance, and Task 11.2 implemented by Agent_QualityRelease.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_12_SQLite_First_Local_Knowledge_Runtime.md`.
2. Read `.apm/Memory/Phase_12_SQLite_First_Local_Knowledge_Runtime/Task_12_2_SQLite_schema_for_hierarchy_sections_navigation_and_evidence.md`.
3. Read `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_1_Hard_gate_vs_soft_gate_verify_redesign.md`.
4. Read `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_2_Baseline_comparator_redesign_and_score_integrity_recovery.md`.
5. Review the implementation files referenced in those logs before adding persistence and trend analysis.

**Producer Output Summary:**
- Task 12.2 should provide the schema slots for hierarchy, navigation, and evidence.
- Task 11.1 and Task 11.2 define the verify and comparator outputs that now need historical persistence.

**Integration Requirements:**
- Persist repeated governance runs locally with deterministic metadata.
- Keep single-run workflows working while enabling trend analysis.
- Preserve clear linkage to evidence bundles and reason families.

**User Clarification Protocol:**
If upstream verify or comparator outputs still lack stable identifiers for runs and reason families, stop and ask whether schemas should be stabilized first.

## Objective
Persist repeated governance runs so repo-agent can analyze quality trends rather than only emit one-off reports.

## Detailed Instructions
- Complete all items in one response.
- Persist verify and compare runs with timestamps, repo target, grades, reason families, and evidence links.
- Add queries or exports that show recurring failures, regressions, and improvements over time.
- Keep report generation compatible with single-run workflows while enabling historical analysis.
- Ensure storage remains local-first and deterministic.
- Add tests for repeated-run persistence and summary queries.

## Expected Output
- Deliverables: verify-run storage, compare-run storage, trend queries, diagnostic exports, and tests.
- Success criteria: governance quality becomes historically observable instead of tied to one-off reports.
- File locations: `repo_wiki/indexer/**`, runtime/reporting helpers, and tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_12_SQLite_First_Local_Knowledge_Runtime/Task_12_3_Verify_and_compare_persistence_with_trend_analysis.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 12.4

```markdown
---
task_ref: "Task 12.4 - SQLite-driven page invalidation and incremental regeneration"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_12_SQLite_First_Local_Knowledge_Runtime/Task_12_4_SQLite_driven_page_invalidation_and_incremental_regeneration.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: SQLite-driven page invalidation and incremental regeneration

## Task Reference
Implementation Plan: **Task 12.4 - SQLite-driven page invalidation and incremental regeneration** assigned to **Agent_IndexGraph**

## Context from Dependencies
This task depends on Task 12.3 implemented by Agent_IndexGraph and Task 2.4 implemented by Agent_IndexGraph.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_12_SQLite_First_Local_Knowledge_Runtime.md`.
2. Read `.apm/Memory/Phase_12_SQLite_First_Local_Knowledge_Runtime/Task_12_3_Verify_and_compare_persistence_with_trend_analysis.md`.
3. Read `.apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_4_Retrieval_pipeline_and_incremental_impact_analyzer.md`.
4. Review the implementation files referenced in those logs before changing incremental regeneration behavior.

**Producer Output Summary:**
- Task 12.3 should persist hierarchy and evidence in a way that can support dependency-aware invalidation.
- Task 2.4 provides the current changed-file and impacted-module logic that this task must extend to page-level regeneration.

**Integration Requirements:**
- Keep full rebuild available.
- Make page-level invalidation the preferred path when impact scope is bounded.
- Cover add, modify, delete, rename, and registry-change scenarios.

**User Clarification Protocol:**
If current generation code cannot map impacted modules to page-level outputs without additional runtime metadata, stop and ask whether extra hierarchy capture should be added before invalidation work proceeds.

## Objective
Use SQLite runtime knowledge to drive page-level invalidation and regeneration instead of broad full-template rerenders.

## Detailed Instructions
- Complete all items in one response.
- Map changed files and impacted modules to affected overview, section, module, API, and data-model pages using stored hierarchy and navigation facts.
- Invalidate generation cache entries at page granularity based on evidence-aware dependency rules.
- Keep full rebuild available, but make incremental regeneration the preferred path when scope is bounded.
- Validate add, modify, delete, rename, and section-registry-change scenarios.
- Document how this runtime model supports replacement-readiness for local-first repo-wiki operation.

## Expected Output
- Deliverables: page invalidation model, regeneration planner, cache-invalidation rules, and regression tests.
- Success criteria: incremental regeneration becomes page-aware and SQLite-driven instead of relying on broad rerender behavior.
- File locations: `repo_wiki/indexer/**`, `repo_wiki/generator/**`, runtime docs, and tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_12_SQLite_First_Local_Knowledge_Runtime/Task_12_4_SQLite_driven_page_invalidation_and_incremental_regeneration.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```
