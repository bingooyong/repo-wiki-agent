# Phase 03 – Documentation Generation and Command Orchestration

## Task 3.1

```markdown
---
task_ref: "Task 3.1 - Template system and document contracts"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_03_Documentation_Generation_and_Command_Orchestration/Task_3_1_Template_system_and_document_contracts.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Template system and document contracts

## Task Reference
Implementation Plan: **Task 3.1 - Template system and document contracts** assigned to **Agent_DocGen**

## Context from Dependencies
This task depends on Task 1.5 implemented by Agent_Scanner.

**Integration Steps (complete in one response):**
1. Read `.apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_5_Source_of_truth_artifact_writer_and_schema_validation.md` to identify the exact source-of-truth files and schema constraints available to the generation layer.
2. Review the artifact writer outputs referenced by that log before defining template contracts.
3. Keep the document set limited to the frozen MVP outputs. Do not introduce V2-only extra docs.

**Producer Output Summary:**
- Task 1.5 defines the schema-valid external artifacts and prompt fragment paths that generation will consume.

**Integration Requirements:**
- Template contracts must align to the scanner-produced artifacts.
- Module docs must follow the fixed MVP section structure.
- Template naming and output paths must remain stable for later adapter and verify work.

**User Clarification Protocol:**
If the Phase 1 artifact names or schema are still unstable, stop and ask whether the generation contract should wait for plan correction.

## Objective
Define stable templates and section contracts for all MVP documents and structured support files.

## Detailed Instructions
- Complete all items in one response.
- Define contracts for `docs/00-overview.md`, `docs/01-architecture.md`, `docs/03-module-map.md`, `docs/04-api-contracts.md`, `docs/05-data-model.md`, and `docs/modules/<name>.md`.
- Define the fixed module document structure from the implementation plan.
- Define contracts for `prompt-fragments/overview.txt`, `prompt-fragments/architecture.txt`, and `task-catalog.yaml`.
- Implement deterministic template rendering primitives and validation hooks.
- Add validation coverage proving all required outputs have a template contract.

## Expected Output
- Deliverables: Jinja2 templates, document contracts, validation hooks, coverage tests.
- Success criteria: the full MVP document set has explicit and stable templates that downstream generation can use without inventing structure dynamically.
- File locations: `templates/`, `generator/` contract helpers, and related tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_03_Documentation_Generation_and_Command_Orchestration/Task_3_1_Template_system_and_document_contracts.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 3.2

```markdown
---
task_ref: "Task 3.2 - Generation engine, cache, and token-budgeted context builder"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_03_Documentation_Generation_and_Command_Orchestration/Task_3_2_Generation_engine_cache_and_token_budgeted_context_builder.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Generation engine, cache, and token-budgeted context builder

## Task Reference
Implementation Plan: **Task 3.2 - Generation engine, cache, and token-budgeted context builder** assigned to **Agent_DocGen**

## Context from Dependencies
This task depends on Task 3.1 and Task 2.4.

**Integration Steps (complete in one response):**
1. Read `.apm/Memory/Phase_03_Documentation_Generation_and_Command_Orchestration/Task_3_1_Template_system_and_document_contracts.md` to confirm the exact document/template contracts you must generate against.
2. Read `.apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_4_Retrieval_pipeline_and_incremental_impact_analyzer.md` to identify the actual retrieval interfaces, diagnostics, and incremental inputs available from the indexing layer.
3. Review the files referenced by both logs before implementing the generation engine.
4. Preserve the rule that generation may enrich artifacts but must not be responsible for making them schema-valid for the first time.

**Producer Output Summary:**
- Task 3.1 provides stable template targets and validation hooks.
- Task 2.4 provides layered retrieval, change analysis, and search candidate assembly needed for context building.

**Integration Requirements:**
- Context building must consume the layered retrieval pipeline instead of bypassing it.
- Caching must use SQLite plus `diskcache`.
- Responsibility text can be refined but not invented as a missing required field.

**User Clarification Protocol:**
If the retrieval layer or template contracts are incomplete, stop and ask whether the missing upstream task should be refined before generation proceeds.

## Objective
Implement LLM-backed generation that builds on the layered retrieval pipeline rather than bypassing it.

## Detailed Instructions
- Complete all items in one response.
- Implement the A/B/C context strategy from the implementation plan.
- Implement generation caching with SQLite plus `diskcache`.
- Implement model selection from config.
- Generate project overview and architecture prompt fragments from repository metadata and graph context.
- Generate `task-catalog.yaml` content from extracted commands and module references.
- Support full-generation and impacted-module-only regeneration flows.
- Add tests or verification proving deterministic behavior and coverage for the frozen MVP output set.

## Expected Output
- Deliverables: generation engine, context builder, cache layer, model selection, full/incremental generation flow, validation coverage.
- Success criteria: generation reuses the retrieval pipeline, respects the frozen document contracts, and behaves deterministically across unchanged inputs.
- File locations: `generator/`, caching helpers, prompt/template integration points, and related tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_03_Documentation_Generation_and_Command_Orchestration/Task_3_2_Generation_engine_cache_and_token_budgeted_context_builder.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 3.3

```markdown
---
task_ref: "Task 3.3 - Core command orchestration for init, update, index, search, graph, and cost-estimate"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_03_Documentation_Generation_and_Command_Orchestration/Task_3_3_Core_command_orchestration_for_init_update_index_search_graph_and_cost_estimate.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Core command orchestration for init, update, index, search, graph, and cost-estimate

## Task Reference
Implementation Plan: **Task 3.3 - Core command orchestration for init, update, index, search, graph, and cost-estimate** assigned to **Agent_PlatformCore**

## Context from Dependencies
This task depends on Task 2.4 and Task 3.2.

**Integration Steps (complete in one response):**
1. Read `.apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_4_Retrieval_pipeline_and_incremental_impact_analyzer.md` to understand the available retrieval, search, and incremental update primitives.
2. Read `.apm/Memory/Phase_03_Documentation_Generation_and_Command_Orchestration/Task_3_2_Generation_engine_cache_and_token_budgeted_context_builder.md` to understand the generation interfaces and regeneration flows available to command orchestration.
3. Review the implementation files referenced in both logs before wiring command orchestration.
4. Keep command behavior aligned to the plan: `init` must orchestrate the full stack, `update` must use changed-file detection and impacted modules, and `index` must rebuild SQLite/FTS, vectors, and graph.

**Producer Output Summary:**
- Task 2.4 provides the layered retrieval and incremental-analysis path.
- Task 3.2 provides generation interfaces and regeneration behavior.

**Integration Requirements:**
- Reuse the existing command and logging framework from Task 1.1.
- Do not bypass the retrieval or generation layers with duplicated orchestration logic.
- Keep stage timing and failure reporting explicit.

**User Clarification Protocol:**
If Task 2.4 or Task 3.2 does not expose callable APIs needed for orchestration, stop and ask whether the upstream tasks should be adjusted first.

## Objective
Wire the full pipeline into transparent user-facing command flows.

## Detailed Instructions
- Complete all items in one response.
- Implement `init`, `update`, `index`, `search`, `graph`, and `cost-estimate` orchestration using the existing CLI skeleton.
- Ensure `init` follows scan -> source-of-truth -> SQLite/FTS -> vectors -> graph -> docs -> adapters.
- Ensure `update` follows diff detection -> impacted modules -> refresh state -> regenerate docs -> sync adapters.
- Add explainable output for `search` and dependency display for `graph`.
- Add stage timing and structured failure reporting.
- Add end-to-end integration tests for representative command scenarios.

## Expected Output
- Deliverables: command orchestration layer, stage timing, error reporting, end-to-end integration coverage.
- Success criteria: the MVP commands run the correct pipeline in the correct order and expose enough diagnostics for later pilot validation.
- File locations: `cli/`, orchestration services in shared runtime modules, and integration tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_03_Documentation_Generation_and_Command_Orchestration/Task_3_3_Core_command_orchestration_for_init_update_index_search_graph_and_cost_estimate.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```
