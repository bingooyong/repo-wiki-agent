# Phase 10 – Narrative and Aggregation Intelligence

## Task 10.1

```markdown
---
task_ref: "Task 10.1 - Narrative builder for overview and architecture"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_1_Narrative_builder_for_overview_and_architecture.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Narrative builder for overview and architecture

## Task Reference
Implementation Plan: **Task 10.1 - Narrative builder for overview and architecture** assigned to **Agent_DocGen**

## Context from Dependencies
This task depends on Task 9.1, Task 9.2, and Task 9.3 implemented by Agent_DocGen.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_10_Narrative_and_Aggregation_Intelligence.md` and `docs/repo-wiki-phase-06-08-review.md` to understand the narrative-quality gap.
2. Read `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_1_Target_output_boundary_and_governance_layer_separation.md`.
3. Read `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_2_Unified_link_builder_and_path_contract_recovery.md`.
4. Read `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_3_Phase_and_section_registry_completion_with_alias_support.md`.
5. Review the implementation files referenced in those logs before changing narrative generation.

**Producer Output Summary:**
- Phase 09 should stabilize output ownership, paths, and registry semantics so prose generation can stop compensating for structural uncertainty.

**Integration Requirements:**
- Make overview and architecture prose repository-derived rather than generic template text.
- Preserve prose-first structure and Mermaid requirements.
- Keep outputs deterministic enough for governance tests.

**User Clarification Protocol:**
If Phase 09 leaves output ownership or canonical navigation unstable, stop and ask whether narrative work should wait for structural stabilization.

## Objective
Rebuild overview and architecture generation around repository-derived narrative instead of static generic prose.

## Detailed Instructions
- Complete all items in one response.
- Derive project positioning, core problem, core capabilities, and architecture rationale from repository signals rather than fixed boilerplate.
- Keep `00-overview.md` and `01-architecture.md` prose-first with stable headings and deterministic structure.
- Preserve Mermaid and three-layer explanations while improving surrounding narrative quality.
- Add tests that detect overly generic or repeated boilerplate output patterns.

## Expected Output
- Deliverables: narrative builder, repository summary synthesis rules, architecture explanation generator, upgraded templates, and tests.
- Success criteria: overview and architecture pages become repository-specific explanation pages rather than generic summaries.
- File locations: `repo_wiki/generator/**`, `templates/docs/00-overview.md.j2`, `templates/docs/01-architecture.md.j2`, and related tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_1_Narrative_builder_for_overview_and_architecture.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 10.2

```markdown
---
task_ref: "Task 10.2 - True API aggregation and entry-point summarization"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_2_True_API_aggregation_and_entry_point_summarization.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: True API aggregation and entry-point summarization

## Task Reference
Implementation Plan: **Task 10.2 - True API aggregation and entry-point summarization** assigned to **Agent_DocGen**

## Context from Dependencies
This task depends on Task 10.1 implemented by Agent_DocGen and Task 6.2 implemented by Agent_Scanner.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_10_Narrative_and_Aggregation_Intelligence.md` to understand the aggregation-quality requirements.
2. Read `.apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_1_Narrative_builder_for_overview_and_architecture.md`.
3. Read `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_2_Business_domain_classifier_and_module_mapping_contracts.md`.
4. Review the implementation files referenced in those logs before changing API aggregation logic.

**Producer Output Summary:**
- Task 10.1 should provide stronger narrative framing for overview layers.
- Task 6.2 provides domain, service-family, and runtime-role metadata required for real API grouping.

**Integration Requirements:**
- Stop treating "key entry APIs" as a second full endpoint list.
- Group APIs by service family, domain, and exposure pattern.
- Preserve lower-level source-of-truth detail while keeping the overview layer aggregated.

**User Clarification Protocol:**
If service-family or domain metadata remains too weak to support bounded aggregation, stop and ask whether classifier enrichment should happen before API summarization continues.

## Objective
Replace endpoint re-enumeration with real API grouping, convention extraction, and key entry-point selection.

## Detailed Instructions
- Complete all items in one response.
- Group APIs by service family, domain, and exposure pattern using extracted metadata.
- Summarize authentication, gateway, and error behavior from repository facts where possible, with explicit fallback when signals are weak.
- Select a bounded set of entry APIs based on centrality or usage signals instead of listing every endpoint.
- Keep a lower-level index available, but ensure the overview layer remains aggregated.
- Add validation and fixtures proving the overview page stays below raw-dump thresholds.

## Expected Output
- Deliverables: API aggregation engine, auth/error convention extractor, entry-API selector, upgraded template, and tests.
- Success criteria: the API overview explains service surfaces and calling conventions without degenerating into an endpoint dump.
- File locations: `repo_wiki/generator/**`, `templates/docs/04-api-contracts.md.j2`, and related tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_2_True_API_aggregation_and_entry_point_summarization.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 10.3

```markdown
---
task_ref: "Task 10.3 - Core-entity and migration-aware data model aggregation"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_3_Core_entity_and_migration_aware_data_model_aggregation.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Core-entity and migration-aware data model aggregation

## Task Reference
Implementation Plan: **Task 10.3 - Core-entity and migration-aware data model aggregation** assigned to **Agent_DocGen**

## Context from Dependencies
This task depends on Task 10.1 implemented by Agent_DocGen and Task 6.2 implemented by Agent_Scanner.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_10_Narrative_and_Aggregation_Intelligence.md`.
2. Read `.apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_1_Narrative_builder_for_overview_and_architecture.md`.
3. Read `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_2_Business_domain_classifier_and_module_mapping_contracts.md`.
4. Review the implementation files referenced in those logs before changing data-model aggregation logic.

**Producer Output Summary:**
- Task 10.1 establishes stronger narrative expectations for overview pages.
- Task 6.2 provides the semantic grouping metadata needed to explain service boundaries.

**Integration Requirements:**
- Stop relying primarily on a fixed hardcoded list of "core model names."
- Summarize storage and migration strategy from repository facts where possible.
- Keep links to source-of-truth and module docs without turning the overview layer into a model dump.

**User Clarification Protocol:**
If the current scanner outputs do not expose enough migration or storage signals, stop and ask whether the scanner should be extended before continuing.

## Objective
Rebuild data-model generation around core entities, service boundaries, and real migration/storage summaries.

## Detailed Instructions
- Complete all items in one response.
- Identify core entities from cross-module reuse, structural centrality, and storage role instead of static name matching alone.
- Group remaining models by service boundary and reduce low-signal repetition.
- Derive database shape and migration strategy from repository signals such as migrations, ORM metadata, and schema definitions.
- Keep links into source-of-truth and module docs, but make the overview layer explanatory rather than enumerative.
- Add fixtures for repositories with high model counts to prove deduplication and aggregation quality.

## Expected Output
- Deliverables: entity deduper, model aggregator, migration summarizer, upgraded template, and tests.
- Success criteria: data-model docs surface core entities and storage strategy instead of recycling raw model listings.
- File locations: `repo_wiki/generator/**`, `templates/docs/05-data-model.md.j2`, and related tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_3_Core_entity_and_migration_aware_data_model_aggregation.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 10.4

```markdown
---
task_ref: "Task 10.4 - Section page builder rewrite for document-center behavior"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_4_Section_page_builder_rewrite_for_document_center_behavior.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Section page builder rewrite for document-center behavior

## Task Reference
Implementation Plan: **Task 10.4 - Section page builder rewrite for document-center behavior** assigned to **Agent_DocGen**

## Context from Dependencies
This task depends on Task 10.1, Task 10.2, and Task 10.3 implemented by Agent_DocGen.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_10_Narrative_and_Aggregation_Intelligence.md`.
2. Read `.apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_1_Narrative_builder_for_overview_and_architecture.md`.
3. Read `.apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_2_True_API_aggregation_and_entry_point_summarization.md`.
4. Read `.apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_3_Core_entity_and_migration_aware_data_model_aggregation.md`.
5. Review the implementation files referenced in those logs before rewriting section-page generation.

**Producer Output Summary:**
- Task 10.1 improves narrative structure for top-level pages.
- Task 10.2 and Task 10.3 provide richer aggregated API and data-model material for section pages to reuse.

**Integration Requirements:**
- Replace generic section-page scaffolding with section-specific topical builders.
- Keep canonical section names stable.
- Ensure section pages become reader-oriented thematic hubs instead of shallow index pages.

**User Clarification Protocol:**
If there is pressure to preserve the generic section template as the primary rendered shape, stop and ask whether Phase 10 should allow a compatibility template while the topical builders become the new default.

## Objective
Turn section pages from index-style stubs into reader-oriented topical documents with guided drilldown.

## Detailed Instructions
- Complete all items in one response.
- Replace the generic "Section Content / 模块列表 / API 端点" layout with topic-specific section structures.
- Keep section pages prose-first and explicitly connect them to overview docs, peer sections, and relevant module docs.
- Use domain, service-family, API, and data-model summaries to build reader journeys through the repository.
- Ensure canonical sections remain stable while allowing repository-specific emphasis within each section.
- Add validation that section pages are topical documents, not just navigational stubs.

## Expected Output
- Deliverables: section-specific builders, richer section templates, reading-path stitching, and tests.
- Success criteria: section pages behave like document-center topical hubs rather than generated indexes.
- File locations: `repo_wiki/generator/**`, `templates/docs/**`, and related tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_4_Section_page_builder_rewrite_for_document_center_behavior.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```
