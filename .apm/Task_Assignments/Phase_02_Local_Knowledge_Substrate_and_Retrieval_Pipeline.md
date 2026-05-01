# Phase 02 – Local Knowledge Substrate and Retrieval Pipeline

## Task 2.1

```markdown
---
task_ref: "Task 2.1 - SQLite state and FTS foundation"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_1_SQLite_state_and_FTS_foundation.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: SQLite state and FTS foundation

## Task Reference
Implementation Plan: **Task 2.1 - SQLite state and FTS foundation** assigned to **Agent_IndexGraph**

## Context from Dependencies
This task depends on Task 1.5 implemented by Agent_Scanner.

**Integration Steps (complete in one response):**
1. Read `.apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_5_Source_of_truth_artifact_writer_and_schema_validation.md` to identify the exact artifact schemas and writer outputs produced in Phase 1.
2. Review the files referenced in that log, especially the source-of-truth writers and any snapshot persistence helpers, before designing SQLite tables.
3. Make SQLite the operational state layer without replacing the external YAML/TXT artifacts required by the scanner output contract.

**Producer Output Summary:**
- Task 1.5 provides the schema-valid external artifacts that indexing must consume and remain compatible with.
- The scanner phase defines the canonical module, endpoint, data-model, and doc-path structure expected downstream.

**Integration Requirements:**
- SQLite must support the artifact schemas already defined by Phase 1.
- Exported `symbols.json`, `file-hash.json`, and `meta.json` must remain compatible with later retrieval and verification tasks.
- Use deterministic migrations and avoid creating a second source of truth for repository structure.

**User Clarification Protocol:**
If Phase 1 did not define stable artifact paths or the schema is still moving, stop and ask whether the plan should be updated before implementing SQLite.

## Objective
Introduce SQLite as the local operational store for metadata, hashes, retrieval bookkeeping, and text search.

## Detailed Instructions
- Complete all items in one response.
- Design a SQLite schema under `.repo-wiki/` for files, chunks, symbols, cache metadata, verify runs, and schema versioning.
- Add FTS5 support for chunk text retrieval.
- Enable WAL mode and deterministic migrations.
- Keep JSON exports compatible with the implementation plan.
- Add rebuild and recovery tests so repeated index runs remain safe.

## Expected Output
- Deliverables: SQLite schema, migration/versioning support, FTS5 index support, JSON export writers, tests.
- Success criteria: SQLite can act as the canonical operational state for indexing and lexical retrieval without breaking the external artifact contract.
- File locations: `indexer/`, `.repo-wiki/` management helpers, and relevant tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_1_SQLite_state_and_FTS_foundation.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 2.2

```markdown
---
task_ref: "Task 2.2 - Chunking and semantic vector index"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_2_Chunking_and_semantic_vector_index.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Chunking and semantic vector index

## Task Reference
Implementation Plan: **Task 2.2 - Chunking and semantic vector index** assigned to **Agent_IndexGraph**

## Context from Dependencies
Build directly on your Task 2.1 SQLite and FTS foundation.

- Read `.apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_1_SQLite_state_and_FTS_foundation.md` and reuse the canonical table layout, migration logic, and JSON export expectations already implemented.
- Keep SQLite as the metadata and lexical layer, and add ChromaDB as the semantic layer rather than replacing the previous work.
- Reuse the shared security filter APIs when persisting chunk text.

## Objective
Build the semantic retrieval layer on top of schema-valid scan outputs and security-filtered source text.

## Detailed Instructions
- Complete all items in one response.
- Implement chunking in the frozen order `function -> class -> module`.
- Generate chunk metadata exactly as required by the plan.
- Route all persisted chunk text through the security redaction pipeline.
- Integrate local embeddings using `sentence-transformers` with `BAAI/bge-m3`.
- Persist vectors to `.repo-wiki/index/chroma/` with upsert and delete lifecycle support.
- Implement file hash tracking with `xxhash`.
- Add tests for unchanged, changed, deleted, and renamed files.

## Expected Output
- Deliverables: chunker, embedding integration, ChromaDB persistence, file hash registry, tests.
- Success criteria: semantic indexing works on top of the SQLite metadata layer, security redaction is enforced before persistence, and change handling remains correct.
- File locations: `indexer/`, `.repo-wiki/index/` handling code, and related tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_2_Chunking_and_semantic_vector_index.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 2.3

```markdown
---
task_ref: "Task 2.3 - Module-level knowledge graph and impact cache"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_3_Module_level_knowledge_graph_and_impact_cache.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Module-level knowledge graph and impact cache

## Task Reference
Implementation Plan: **Task 2.3 - Module-level knowledge graph and impact cache** assigned to **Agent_IndexGraph**

## Context from Dependencies
This task depends on Task 1.4 implemented by Agent_Scanner.

**Integration Steps (complete in one response):**
1. Read `.apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_4_Ownership_dependency_API_and_data_model_extraction.md` to identify the normalized module, endpoint, and data model structures available from the scanner phase.
2. Review the implementation files referenced there before modeling graph nodes and edges.
3. Keep graph scope strictly at `Module`, `Interface`, and `DataModel` level. Do not backslide into function-level global call graph work.

**Producer Output Summary:**
- Task 1.4 provides dependency edges, endpoint extraction, data-model extraction, ownership data, and normalized structures that graph construction must consume.

**Integration Requirements:**
- Graph inputs must map cleanly from the scanner outputs.
- Edge types must remain limited to the frozen MVP set.
- Graph artifacts must be machine-readable and usable by later retrieval and generation tasks.

**User Clarification Protocol:**
If the scanner outputs do not clearly identify modules, interfaces, or models, stop and ask whether the normalization contract should be corrected before graph implementation proceeds.

## Objective
Construct the module-level graph required for impact analysis and context expansion.

## Detailed Instructions
- Complete all items in one response.
- Build graph nodes for `Module`, `Interface`, and `DataModel`.
- Build edges for `DEPENDS_ON`, `EXPOSES`, `USES`, and `BELONGS_TO`.
- Generate `dep_matrix.csv`.
- Compute `impact_cache.json` with upstream, downstream, depth-2 impacts, interfaces, and models.
- Output `knowledge_graph.json` in a machine-readable form suitable for context assembly.
- Add consistency checks for orphan nodes, broken references, and self-dependencies.
- Add fixture-based validation for expected module chains.

## Expected Output
- Deliverables: graph builder, machine-readable graph export, dependency matrix, impact cache, consistency checks, tests.
- Success criteria: graph outputs are limited to MVP scope and can support both impact analysis and generation context expansion.
- File locations: `graph/`, `.repo-wiki/graph/`, and corresponding tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_3_Module_level_knowledge_graph_and_impact_cache.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 2.4

```markdown
---
task_ref: "Task 2.4 - Retrieval pipeline and incremental impact analyzer"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_4_Retrieval_pipeline_and_incremental_impact_analyzer.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Retrieval pipeline and incremental impact analyzer

## Task Reference
Implementation Plan: **Task 2.4 - Retrieval pipeline and incremental impact analyzer** assigned to **Agent_IndexGraph**

## Context from Dependencies
Build directly on your Task 2.2 and Task 2.3 work.

- Read `.apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_2_Chunking_and_semantic_vector_index.md` and `.apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_3_Module_level_knowledge_graph_and_impact_cache.md`.
- Reuse the SQLite/FTS layer, ChromaDB vector layer, and graph outputs you already created.
- Keep the retrieval order fixed as hard filters -> FTS5/BM25 -> semantic Top-K -> graph neighbor expansion -> prompt candidate assembly.

## Objective
Build the retrieval and change-analysis path used by `search`, `update`, and generation context assembly.

## Detailed Instructions
- Complete all items in one response.
- Implement changed-file detection via `git diff`, with hash-compare fallback for non-git scenarios.
- Map changed files to owning modules using deterministic fallback rules.
- Implement the layered retrieval pipeline in the exact order defined by the plan.
- Expose `changed_modules`, `impacted_modules`, and `global_doc_regeneration_triggers`.
- Add regression tests for add, modify, delete, and rename scenarios.
- Add search relevance diagnostics that explain why results were ranked.

## Expected Output
- Deliverables: retrieval pipeline, incremental analyzer, change-mapping logic, search diagnostics, regression tests.
- Success criteria: retrieval no longer relies on broad raw-code injection, and incremental update inputs are explicit and test-covered.
- File locations: `indexer/` and related retrieval utilities, plus tests covering retrieval and change analysis.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_4_Retrieval_pipeline_and_incremental_impact_analyzer.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```
