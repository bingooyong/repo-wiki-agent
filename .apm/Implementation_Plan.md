# repo-wiki MVP – APM Implementation Plan
**Memory Strategy:** Layered Local Knowledge (`source-of-truth` + SQLite/FTS5 + ChromaDB + module graph)
**Last Modification:** Phase 28-35 execution complete. Phase 28-31 Completed, Phase 32 Completed, Phase 33 Completed, Phase 34 Completed, Phase 35 Completed (GO). All phases closed. Last update: 2026-05-03.
**Project Overview:** Build an MVP implementation plan for `repo-wiki` that delivers repository scanning, deterministic `source-of-truth` outputs, local semantic indexing, module-level knowledge graph, documentation generation, AI adapter outputs, Git-diff-based incremental update, and verify governance without drifting beyond the frozen MVP scope.

## Implementation Principles

1. Freeze to MVP first. Anything not required by `docs/mvp.md` is treated as a post-MVP extension unless explicitly pulled forward.
2. Keep the pipeline executable end to end. Intermediate artifacts must remain schema-valid; later phases may enrich them, but must not repair invalid earlier outputs.
3. Prefer deterministic extraction before LLM enrichment. Static analysis produces the base facts; LLM generation reorganizes and summarizes.
4. Split local knowledge into layers. SQLite stores operational state and text search indexes; ChromaDB stores semantic vectors; the graph stores dependency and impact structure.
5. Search in stages. Apply hard filters first, then FTS5/BM25, then vector recall, then graph expansion, then prompt assembly.
6. Treat security as a foundation capability. Content filtering and redaction must exist before indexing or LLM generation writes any derived artifact.
7. Keep incremental update at file-detection and module-regeneration granularity. Do not implement symbol-level patching or section patch updates.

## Scope Guardrails

The following items remain out of MVP implementation scope even if they appear in V2 as possible extensions:

- GraphML export
- Qdrant / FAISS / Lance backends
- `repo-wiki serve`
- `ownership.yaml`
- per-module prompt fragment files such as `module-<name>.txt`
- extra docs beyond `00-overview.md`, `01-architecture.md`, `03-module-map.md`, `04-api-contracts.md`, `05-data-model.md`, and `docs/modules/<name>.md`
- function-level global call graphs
- dynamic skill synthesis beyond fixed templates

## Phase 1: Foundation, Security, and Scanner Contracts

### Task 1.1 – CLI skeleton, config foundation, and core contracts - Agent_PlatformCore
**Objective:** Establish executable CLI, typed configuration, common error handling, and schema contracts for the entire MVP pipeline.
**Output:** Command registry, config loader, shared Pydantic models, bootstrap checks, smoke validation baseline.
**Guidance:** Keep the command surface aligned to MVP only: `init`, `index`, `update`, `verify`, `sync`, `search`, `graph`, `cost-estimate`.
1. Create the CLI entry structure and command placeholders for all MVP commands.
2. Define the config model with the six MVP sections: `project`, `scan`, `index`, `llm`, `output`, `security`.
3. Implement config validation, default values, and override precedence for config file plus CLI flags.
4. Define the `RepositorySnapshot` model hierarchy aligned to MVP §§8.3 and 17.1.
5. Define shared contracts for `Module`, `Endpoint`, `DataModel`, `RepositoryStats`, `VerifyResult`, and `ImpactSet`.
6. Implement bootstrap checks for workspace readiness, output directories, and dependency availability.
7. Add stage-level progress logging with Rich and standardized error categories.
8. Run command-level smoke checks and capture baseline pass criteria.

### Task 1.2 – Security filtering and redaction foundation - Agent_PlatformCore
**Objective:** Deliver file-level and content-level security filtering before scan, index, or generation pipelines persist derived data.
**Output:** Security filter module, redaction engine, allow/deny policy, security test fixtures.
**Guidance:** This task must complete before any indexing or generation work. It supplies shared gates consumed by later phases.
1. Implement file exclusion rules from MVP §15.2: `.env*`, `node_modules/`, `dist/`, `build/`, `coverage/`, binaries, generated artifacts, oversized files, and large logs.
2. Implement content-level sensitive pattern detection for API keys, access tokens, private keys, database connection strings, and production domain/IP patterns.
3. Implement redaction rules that replace detected sensitive values with `[REDACTED]` before content is indexed or sent to an LLM.
4. Expose shared APIs for `should_scan(path)`, `sanitize_text(text)`, and `security_warnings`.
5. Add reporting that records detections without exposing raw secret values.
6. Validate behavior on synthetic security fixtures and safe-content control cases.

### Task 1.3 – Repository traversal, language detection, and module discovery - Agent_Scanner
**Objective:** Build the traversal and repository-baseline pipeline that produces the first valid `RepositorySnapshot`.
**Output:** Traverser, language/framework detector, module discovery, command extraction, repository stats.
**Guidance:** **Depends on: Task 1.1 and Task 1.2.** Apply `.gitignore` filtering with `pathspec` and route all text through the security filter before downstream use.
1. Implement repository traversal with `.gitignore`, explicit excludes, and security-deny rules.
2. Detect language, framework, and package manager from `package.json`, `go.mod`, `pyproject.toml`, `Dockerfile`, and `Makefile`.
3. Extract common project commands: `start`, `build`, `test`, and `lint`.
4. Implement module discovery heuristics for TS/JS, Python, and Go as defined in MVP §8.4.
5. Populate the repository-level and module-level sections of `RepositorySnapshot`.
6. Calculate repository stats and consistency checks.
7. Validate traversal and module discovery on representative backend repositories.

### Task 1.4 – Ownership, dependency, API, and data-model extraction - Agent_Scanner
**Objective:** Complete the MVP extraction set and guarantee that required module fields have a defined source.
**Output:** Dependency edges, REST endpoints, data models, ownership mapping, first-pass module responsibilities.
**Guidance:** **Depends on: Task 1.3.** Keep granularity at module level. Do not implement a function-level global call graph.
1. Implement module dependency extraction for `depends_on` and `depended_by` using import, require, and package analysis.
2. Implement REST extraction for NestJS, Express, Fastify, FastAPI, Flask, Gin, Fiber, and simple `net/http` handlers. Treat Django URL mapping as optional, not required for MVP acceptance.
3. Implement data-model extraction for ORM models, DTO/schema definitions, and migration-derived table summaries required by MVP §8.6.
4. Implement ownership extraction from `CODEOWNERS` when present, with deterministic fallback to `unknown` when no owner can be resolved.
5. Implement first-pass responsibility summarization from extracted signals such as module path, exports, endpoints, models, and README cues. This summary must satisfy schema validity even before later LLM enrichment.
6. Normalize all extracted entities into `RepositorySnapshot`.
7. Add fixture-based extraction tests and fallback logging for uncertain patterns.

### Task 1.5 – Source-of-truth artifact writer and schema validation - Agent_Scanner
**Objective:** Write schema-valid MVP artifacts immediately after scan, without relying on later phases to repair required fields.
**Output:** `repo-map.yaml`, `module-index.yaml`, `api-index.yaml`, `data-models.yaml`, `task-catalog.yaml` scaffold, `prompt-fragments/` scaffold.
**Guidance:** **Depends on: Task 1.4.** All written artifacts must be deterministic, sorted, and valid against MVP §17 field requirements.
1. Implement YAML serializers for `repo-map.yaml`, `module-index.yaml`, `api-index.yaml`, and `data-models.yaml`.
2. Ensure `module-index.yaml` entries include all required MVP fields: `name`, `path`, `responsibility`, `exports`, `depends_on`, `depended_by`, `interfaces`, `data_models`, `owner`, and `doc_path`.
3. Generate `task-catalog.yaml` as a structural scaffold that is schema-valid even before LLM enrichment.
4. Create `prompt-fragments/overview.txt` and `prompt-fragments/architecture.txt` placeholders with deterministic fallback text.
5. Add schema validation and fail-fast behavior for invalid artifacts.
6. Add deterministic ordering and formatting to minimize noisy diffs.
7. Validate the full scan-to-artifact pipeline end to end.

## Phase 2: Local Knowledge Substrate and Retrieval Pipeline

### Task 2.1 – SQLite state and FTS foundation - Agent_IndexGraph
**Objective:** Introduce SQLite as the local operational store for metadata, hashes, retrieval bookkeeping, and text search.
**Output:** SQLite schema, migration/versioning support, FTS5 indexes, JSON export writers.
**Guidance:** **Depends on: Task 1.5.** SQLite is the local state and lexical retrieval layer. It does not replace the external JSON/YAML artifacts required by MVP.
1. Design a local SQLite database under `.repo-wiki/` for operational state and search metadata.
2. Create core tables for files, chunks, symbols, generation cache metadata, verify runs, and schema versioning.
3. Create an FTS5 virtual table for chunk text and textual retrieval across code and generated summaries.
4. Enable WAL mode and deterministic migrations for concurrent readers and a single writer.
5. Keep `symbols.json`, `file-hash.json`, and `meta.json` as exported artifacts derived from the canonical SQLite state where practical.
6. Validate migration, rebuild, and recovery behavior on repeated index runs.

### Task 2.2 – Chunking and semantic vector index - Agent_IndexGraph
**Objective:** Build the semantic retrieval layer on top of schema-valid scan outputs and security-filtered source text.
**Output:** Chunker pipeline, embedding integration, ChromaDB persistence, file hash registry.
**Guidance:** **Depends on: Task 2.1.** ChromaDB remains the only MVP vector backend. SQLite handles metadata and lexical recall; ChromaDB handles semantic recall.
1. Implement chunking with the frozen MVP order: `function -> class -> module`.
2. Generate chunk metadata including `chunk_id`, `file_path`, `module_name`, `language`, `chunk_type`, `symbol_name`, `line_start`, `line_end`, and `dependencies`.
3. Route all chunk text through the security redaction pipeline before persistence.
4. Integrate local embeddings with `sentence-transformers` using `BAAI/bge-m3`.
5. Persist vectors to `.repo-wiki/index/chroma/` with upsert and delete lifecycle support.
6. Implement file hash generation and change tracking with `xxhash`.
7. Validate unchanged, changed, deleted, and renamed file behavior.

### Task 2.3 – Module-level knowledge graph and impact cache - Agent_IndexGraph
**Objective:** Construct the module-level graph required for impact analysis and context expansion.
**Output:** `knowledge_graph.json`, `dep_matrix.csv`, `impact_cache.json`.
**Guidance:** **Depends on: Task 1.4.** Keep graph scope strictly within MVP §10.3 and §10.4. Do not implement GraphML export in MVP.
1. Build graph nodes for `Module`, `Interface`, and `DataModel`.
2. Build graph edges for `DEPENDS_ON`, `EXPOSES`, `USES`, and `BELONGS_TO`.
3. Generate `dep_matrix.csv` for human inspection and troubleshooting.
4. Compute `impact_cache.json` with upstream, downstream, depth-2 impact sets, interface lists, and model lists.
5. Output `knowledge_graph.json` in a machine-readable structure suitable for context assembly.
6. Add consistency checks for orphan nodes, broken references, and self-dependencies.
7. Validate graph outputs against fixture repositories and expected module chains.

### Task 2.4 – Retrieval pipeline and incremental impact analyzer - Agent_IndexGraph
**Objective:** Build the retrieval and change-analysis path used by `search`, `update`, and generation context assembly.
**Output:** Search pipeline, incremental analyzer, retrieval diagnostics.
**Guidance:** **Depends on: Task 2.2 and Task 2.3.** Retrieval must follow a layered strategy rather than sending broad raw code to the LLM.
1. Implement changed-file detection via `git diff`, with hash-compare fallback for non-git scenarios.
2. Map changed files to owning modules with deterministic fallback rules.
3. Build the retrieval pipeline in this order:
   - hard filters by module, path, language, and artifact type
   - SQLite FTS5/BM25 lexical recall
   - ChromaDB semantic Top-K recall
   - graph-based neighbor expansion for direct upstream and downstream context
   - final prompt-candidate assembly capped by token budget
4. Expose incremental outputs: `changed_modules`, `impacted_modules`, `global_doc_regeneration_triggers`.
5. Add regression tests for add, modify, delete, and rename scenarios.
6. Add search relevance diagnostics so pilot evaluation can explain why a result ranked highly.

## Phase 3: Documentation Generation and Command Orchestration

### Task 3.1 – Template system and document contracts - Agent_DocGen
**Objective:** Define stable templates and section contracts for all MVP documents and structured support files.
**Output:** Jinja2 templates, document contracts, validation hooks.
**Guidance:** **Depends on: Task 1.5.** Templates must match the frozen MVP document set and avoid V2-only extras.
1. Define contracts for `docs/00-overview.md`, `docs/01-architecture.md`, `docs/03-module-map.md`, `docs/04-api-contracts.md`, `docs/05-data-model.md`, and `docs/modules/<name>.md`.
2. Define the standard module document structure from MVP §11.4.
3. Define contracts for `prompt-fragments/overview.txt`, `prompt-fragments/architecture.txt`, and `task-catalog.yaml`.
4. Implement deterministic template rendering primitives with stable heading order and section order.
5. Add validation hooks for generated structured snippets.
6. Validate template coverage across all required MVP outputs.

### Task 3.2 – Generation engine, cache, and token-budgeted context builder - Agent_DocGen
**Objective:** Implement LLM-backed generation that builds on the layered retrieval pipeline rather than bypassing it.
**Output:** Generation engine, cache, context builder, full and incremental generation flows.
**Guidance:** **Depends on: Task 3.1 and Task 2.4.** Generation may enrich existing schema-valid artifacts, but must not be responsible for making them valid for the first time.
1. Implement the A/B/C context strategy from MVP §11.5:
   - Strategy A: small modules, direct source summary
   - Strategy B: module metadata plus interfaces, models, and Top-K retrieval
   - Strategy C: module summary, graph neighbors, Top-K chunks, and key config or interface summaries
2. Implement generation cache with SQLite plus `diskcache`, keyed by normalized input hash.
3. Implement model selection from config: `model_init`, `model_update`, `model_verify`.
4. Generate project overview and architecture prompt fragments from repository metadata and graph context.
5. Generate `task-catalog.yaml` content from extracted commands, module references, and common workflows.
6. Optionally refine module `responsibility` text when the LLM can improve clarity, but do not rely on this step for schema completeness.
7. Implement full-generation and impacted-module-only regeneration flows.
8. Validate readability, deterministic regeneration behavior, and coverage across the frozen MVP document set.

### Task 3.3 – Core command orchestration for init, update, index, search, graph, and cost-estimate - Agent_PlatformCore
**Objective:** Wire the full pipeline into transparent user-facing command flows.
**Output:** Orchestrated commands, progress reporting, failure handling, integration tests.
**Guidance:** **Depends on: Task 2.4 and Task 3.2.**
1. Implement `init` as: scan -> write source-of-truth -> build SQLite/FTS state -> build vectors -> build graph -> generate docs -> sync adapters.
2. Implement `update` as: detect changed files -> resolve impacted modules -> refresh state -> regenerate impacted docs -> sync adapters when required.
3. Implement `index` as a standalone rebuild of SQLite/FTS, vectors, and graph.
4. Implement `search` using the layered retrieval pipeline with explainable result metadata.
5. Implement `graph` to display upstream and downstream module relationships.
6. Implement `cost-estimate` using repository size, document count, and generation heuristics.
7. Add stage timings, structured failure reports, and end-to-end integration tests.

## Phase 4: Adapter Output and Verification

### Task 4.1 – Multi-tool adapter generation and sync command - Agent_AdapterGovernance
**Objective:** Generate AI-tool adapter artifacts that point to the knowledge base without duplicating it.
**Output:** Claude Code, OpenCode, and baseline Codex adapter files plus `sync` command behavior.
**Guidance:** **Depends on: Task 3.2.** Keep adapter scope within MVP and keep files minimal.
1. Generate `.claude/CLAUDE.md`, `.claude/settings.json`, and fixed template skills under `.claude/skills/`.
2. Generate `AGENTS.md`, `.opencode/opencode.json`, and mirrored fixed template skills under `.agents/skills/`.
3. Generate baseline Codex files: `.codex/config.toml` and `.codex/hooks.json`.
4. Validate that adapter files reference only real generated docs and source-of-truth paths.
5. Implement `sync` for standalone adapter regeneration.
6. Validate readability, path integrity, and minimalism of all adapter files.

### Task 4.2 – Verify command and CI-mode governance checks - Agent_AdapterGovernance
**Objective:** Implement the frozen MVP verification contract with PASS, WARN, and FAIL grading.
**Output:** `verify` command, `--ci` output mode, fixture-based governance tests.
**Guidance:** **Depends on: Task 4.1 and Task 1.5.** Verify scope must match MVP §14.2 exactly.
1. Check that required files exist.
2. Check that every module has a corresponding module document.
3. Check that `api-index.yaml` and `module-index.yaml` cross-reference correctly.
4. Check that `data-models.yaml` has no dangling references.
5. Check for stale docs after code changes using file timestamps and git-aware change detection.
6. Check that adapter files reference correct paths.
7. Implement `--ci` JSON output and non-zero exit code on FAIL.
8. Add fixture-based tests that cover PASS, WARN, and FAIL outcomes.

## Phase 5: Pilot Acceptance, CI Packaging, and Release Gate

### Task 5.1 – Pilot acceptance protocol and metric instrumentation - Agent_QualityRelease
**Objective:** Validate that the full MVP works on a real medium-sized backend repository using the frozen acceptance criteria.
**Output:** Pilot playbook, metric capture scripts, evidence pack, acceptance summary.
**Guidance:** **Depends on: Task 3.3 and Task 4.2.**
1. Define pilot repository qualification based on MVP §18.1.
2. Run the acceptance scenarios: `init`, `search`, `graph`, `update`, and `verify`.
3. Instrument the frozen MVP metrics from §19.1: module identification accuracy, REST extraction accuracy, module doc coverage, Top-3 search hit rate, impact-chain reasonableness, and init success rate.
4. Record reproducible evidence for each scenario.
5. Produce a pass/fail summary against the engineering targets in MVP §19.2.

### Task 5.2 – CI automation and governance packaging - Agent_QualityRelease
**Objective:** Deliver repeatable local and CI workflows after the product path is already working.
**Output:** `Makefile` AI targets, CI workflow templates, hook guidance, operational documentation.
**Guidance:** **Depends on: Task 4.2.** This task owns workflow packaging; do not duplicate this responsibility in adapter generation.
1. Implement `Makefile` targets for `ai-init`, `ai-update`, `ai-verify`, `ai-sync`, and `ai-cost`.
2. Implement CI workflow templates centered on `repo-wiki verify --ci`.
3. Add safe hook guidance for post-commit reminders without destructive behavior.
4. Add onboarding and troubleshooting documentation for local and CI usage.
5. Validate the automation package in local and CI-like environments.

### Task 5.3 – Final readiness review and release gate report - Agent_QualityRelease
**Objective:** Consolidate validation evidence into a final go or no-go recommendation.
**Output:** Readiness report, unresolved-risk register, rollback guidance, launch recommendation.
**Guidance:** **Depends on: Task 5.1 and Task 5.2.**
1. Aggregate outputs and validation evidence from all phases.
2. Evaluate compliance with MVP success criteria and identify remaining risks.
3. Define rollback or fallback actions for high-risk operational scenarios.
4. Produce the release recommendation and required follow-up actions.
5. Trigger the explicit user checkpoint before implementation handoff.

## Post-MVP Qoder Alignment and Document-Center Upgrade

The following phases preserve the implemented MVP baseline and add a dedicated recovery track for qoder-style information architecture, prose-first documentation, and content-quality governance. These tasks do not replace Phase 1-5 deliverables; they upgrade the output model on top of them.

## Phase 6: Information Architecture and Document Contract Recovery

**Manager Status:** `Conditional Pass`
**Exit Judgment:** Direction is correct, but contract boundaries remain incomplete. Phase doc generation is still mixed into target-repository output, and phase/section registry coverage does not yet fully match the implementation plan.

### Task 6.1 – Document output contract refactor and document-center layer - Agent_DocGen
**Objective:** Refactor the document output contract so repo-wiki produces a document center rather than only a flat export set.
**Output:** Updated document contracts, `docs/sections/**` and `docs/phases/**` output definitions, validation hooks, and write-domain rules.
**Guidance:** **Depends on: Task 3.1.** Use `docs/qoder-repo-wiki-design-analysis.md` and `docs/repo-wiki-qoder-gap-task-plan.md` as the recovery baseline. Keep the CLI command surface unchanged while expanding the document output contract.
1. Extend the current document contract model to distinguish overview docs, section docs, module docs, and phase docs.
2. Introduce `docs/sections/` as the section layer between overview docs and module docs.
3. Introduce `docs/phases/` as the reader-facing stage-governance layer for implementation phases.
4. Define path stability, naming rules, and write-domain boundaries so future tasks do not create parallel structures.
5. Add validation hooks that verify required section/phase contracts exist before generation runs.
6. Update any supporting templates or contract registries needed to support the expanded structure.
7. Validate that the contract refactor is additive and does not break existing MVP outputs.

### Task 6.2 – Business-domain classifier and module mapping contracts - Agent_Scanner
**Objective:** Add semantic grouping metadata so modules can be organized by business domain instead of only by physical directory.
**Output:** Domain classifier, module-to-domain mapping outputs, fallback rules, and `module-index` contract extensions.
**Guidance:** **Depends on: Task 6.1 Output by Agent_DocGen.** This task is the normalization bridge between scanner output and the new domain-centered document layer.
1. Define a deterministic business-domain classification strategy using module path, commands, frameworks, interfaces, data models, and ownership cues.
2. Extend normalized module outputs with at least `domain`, `service_family`, and `runtime_role` metadata.
3. Implement fallback behavior for ambiguous modules so every module still maps to a stable higher-level grouping.
4. Update `module-index.yaml` writing logic and schema validation to include the new metadata without breaking existing consumers.
5. Add fixture coverage for mixed backend repositories with multiple service families and support modules.
6. Emit diagnostics that explain why a module was classified into a given domain when signals are weak.

### Task 6.3 – Prose-first overview contract and generation upgrade - Agent_DocGen
**Objective:** Recover `docs/00-overview.md` from a flat summary into a true introduction page for humans and agents.
**Output:** New overview contract, updated generation logic, prose-first overview template, and coverage tests.
**Guidance:** **Depends on: Task 6.1 and Task 6.2.** The overview page must become the entry point of the document center and must not degrade into a stats dump.
1. Redefine the `00-overview.md` contract to require the fixed sections `项目定位`, `核心问题`, `核心能力`, `快速开始`, and `阅读导航`.
2. Generate paragraph-first content using repository metadata, domain groupings, commands, and section navigation links.
3. Add minimum prose and section-count validation so overview generation fails fast on empty or list-only outputs.
4. Ensure overview content points readers toward `docs/sections/` and key module documents rather than repeating raw inventories.
5. Update tests or contract validation so missing prose is treated as a document-quality defect.

### Task 6.4 – Architecture contract recovery and three-layer Mermaid design - Agent_DocGen
**Objective:** Rewrite `docs/01-architecture.md` as a real system-design document that explains the repo-wiki storage and reading model.
**Output:** New architecture contract, Mermaid-backed architecture template, generation logic, and coverage tests.
**Guidance:** **Depends on: Task 6.1, Task 6.2, and Task 6.3.** The architecture page must explicitly explain the relationship between `.repo-wiki`, `ai/source-of-truth`, and `docs`.
1. Redefine the `01-architecture.md` contract to require `系统分层`, `服务协作关系`, `核心数据流`, `存储与检索设计`, and `增量更新与治理闭环`.
2. Add Mermaid generation rules for the three-layer architecture and document-center flow.
3. Use retrieval, graph, and artifact-layer signals to explain how runtime storage, fact contracts, and human-readable docs interact.
4. Add validation that rejects architecture outputs missing Mermaid or the three-layer explanation.
5. Keep the page focused on design reasoning rather than module/API enumeration.

## Phase 7: Domain-Centered Content Generation

**Manager Status:** `Fail to Exit`
**Exit Judgment:** Domain grouping exists, but API, data-model, and section outputs still behave too much like reorganized inventories instead of prose-first aggregated document-center pages.

### Task 7.1 – Domain-centered module map generation - Agent_DocGen
**Objective:** Replace the flat module list with a domain map that reflects how readers should understand the repository.
**Output:** Updated `03-module-map.md` contract, domain-grouped generation logic, navigation links, and tests.
**Guidance:** **Depends on: Task 6.2 Output by Agent_Scanner and Task 6.4.** Use the new domain metadata as the primary grouping layer and keep physical directory names secondary.
1. Redefine `03-module-map.md` to organize modules by business domain, service family, and runtime role.
2. Show module responsibilities, upstream/downstream relationships, and entry docs within each domain group.
3. Require at least three top-level domain groups when the repository contains enough modules to support them.
4. Link domain groups to the relevant section docs and module docs.
5. Add validation that rejects a directory-flat output when domain metadata is available.

### Task 7.2 – Aggregated API contracts generation - Agent_DocGen
**Objective:** Rebuild `04-api-contracts.md` around service and usage groups instead of a raw endpoint dump.
**Output:** API grouping rules, updated API contracts template, call-convention summary, and tests.
**Guidance:** **Depends on: Task 6.2 Output by Agent_Scanner and Task 6.4.** The API overview must aggregate by service/theme/auth model and surface calling conventions for readers.
1. Group APIs by service family, domain theme, and authentication or gateway pattern.
2. Add fixed sections for `服务/API 分组` and `调用约定`.
3. Summarize authentication, error/status behavior, and key entry APIs instead of rendering every endpoint verbatim.
4. Preserve links to lower-level source-of-truth or module docs when readers need deeper detail.
5. Add validation that rejects unbounded raw endpoint lists as overview content.

### Task 7.3 – Domain-aggregated data model generation - Agent_DocGen
**Objective:** Rebuild `05-data-model.md` so it highlights core domain entities and storage strategy instead of dumping every model symbol.
**Output:** Data-model grouping rules, deduplication logic, updated template, and tests.
**Guidance:** **Depends on: Task 6.2 Output by Agent_Scanner and Task 6.4.** This task must reduce noise from repetitive ORM or builder types while preserving structural coverage.
1. Group models into `核心数据模型`, `服务数据模型`, and `数据库/迁移策略`.
2. Deduplicate low-signal repeated types and surface the core entities that define repository behavior.
3. Summarize database shape, migration strategy, and notable cross-module data boundaries.
4. Link aggregated sections back to source-of-truth artifacts and detailed module docs where needed.
5. Add validation that flags model-dump outputs with no aggregation or migration summary.

### Task 7.4 – Section page generation and navigation stitching - Agent_DocGen
**Objective:** Generate the section-layer pages that make the repo-wiki output behave like a document center.
**Output:** Section templates, section generation logic, navigation stitching, and coverage tests.
**Guidance:** **Depends on: Task 7.1, Task 7.2, and Task 7.3.** Keep the phase strictly serial because these tasks share templates, overview docs, and navigation contracts.
1. Generate at minimum the section pages for `project`, `architecture`, `services`, `data-model`, `api`, `operations`, `development`, and `security`.
2. Ensure section pages link to overview docs, related section pages, and relevant module docs.
3. Provide stable directory naming and index-style navigation so adapter files can point readers into the document center.
4. Add validation that section pages exist and cross-link correctly when the repository meets the minimum data threshold.
5. Keep content aggregated and reader-oriented rather than duplicating lower-level docs verbatim.

## Phase 8: Quality Gates and Qoder Baseline Regression

**Manager Status:** `Fail to Exit`
**Exit Judgment:** Verify governance improved, but the baseline comparison harness still contains scoring and structure-recognition weaknesses, so readiness results are informative but not yet decision-grade.

### Task 8.1 – Content-quality verify and CI gate upgrade - Agent_AdapterGovernance
**Objective:** Upgrade `verify --ci` from existence checks to content-quality governance checks for the new document-center model.
**Output:** Extended verify rules, CI output reasons, quality fixtures, and regression coverage.
**Guidance:** **Depends on: Task 6.1 Output by Agent_DocGen and Task 7.1, Task 7.2, Task 7.3, Task 7.4 Output by Agent_DocGen.** Keep the command surface unchanged while expanding the governance criteria.
1. Add checks for minimum section count and minimum prose paragraphs in overview and architecture docs.
2. Add checks that `docs/sections/` exists and contains the required section pages.
3. Add checks that API and data-model overviews are aggregated rather than raw dumps.
4. Add checks that section pages and overview docs are stitched together with valid navigation links.
5. Extend `--ci` output to include precise reason codes for content-quality WARN and FAIL outcomes.
6. Add fixture-based tests that cover empty templates, list-only docs, broken navigation, and missing section layers.

### Task 8.2 – Qoder baseline regression harness and gap report - Agent_QualityRelease
**Objective:** Build a repeatable comparison harness that measures repo-wiki output against the qoder-style baseline.
**Output:** Baseline comparison script, structure/content checklist, diff report format, and regression documentation.
**Guidance:** **Depends on: Task 8.1 Output by Agent_AdapterGovernance.** Use `docs/qoder-repo-wiki-design-analysis.md` as the comparison source of truth and keep the harness focused on directory, navigation, and readability deltas.
1. Define comparison dimensions for directory hierarchy, section coverage, heading coverage, prose density, navigation completeness, and aggregation quality.
2. Implement a script or checklist that compares generated outputs against the chosen qoder baseline repository.
3. Produce a machine-readable and human-readable gap report format for future regressions.
4. Document how the comparison harness is run locally and how it should be interpreted in governance reviews.
5. Ensure the harness can explain what is missing, not just that a mismatch exists.

### Task 8.3 – AI_API_Atlas regeneration acceptance and readiness report - Agent_QualityRelease
**Objective:** Re-run the target repository acceptance flow and determine whether the qoder-aligned output is ready for broader rollout.
**Output:** `AI_API_Atlas` acceptance evidence, regenerated knowledge-base assessment, and a Qoder-alignment readiness report.
**Guidance:** **Depends on: Task 8.1 and Task 8.2.** Use `/Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas` as the fixed acceptance target and evaluate the upgraded document-center outputs end to end.
1. Regenerate knowledge outputs for `AI_API_Atlas` using the upgraded contracts and generation flow.
2. Run the upgraded `verify --ci` and the qoder comparison harness on the target repository.
3. Capture evidence for overview quality, architecture readability, section navigation, and aggregated API/data-model docs.
4. Produce a readiness report that states remaining quality gaps, rollout blockers, and whether another template/model iteration is required.
5. Record the explicit next-step recommendation for Manager follow-up.

## Key Design Decisions Captured in This Revision

1. Security moved left. Redaction and content filtering now land before index and generation work.
2. `module-index.yaml` is schema-valid as soon as scan finishes. Responsibility and owner fields now have defined extraction or fallback paths.
3. Ownership is part of the base extraction pipeline. It is not deferred to an unspecified later phase.
4. SQLite is now an explicit MVP implementation layer. It handles operational state, migrations, FTS5 lexical retrieval, and cache metadata.
5. ChromaDB remains the only MVP semantic vector backend. SQLite does not replace it.
6. Retrieval is explicitly layered: hard filters -> FTS5 -> semantic vectors -> graph expansion -> prompt assembly.
7. V2-only extras are kept out of the MVP execution path unless later approved as a scoped extension.
8. Phase 1-5 remain the implemented MVP baseline; qoder alignment is tracked as an additive post-MVP upgrade path.
9. Reader-facing stage documents live under `docs/phases/`, while execution-facing task prompts remain under `.apm/Task_Assignments/`.
10. Content quality is now a first-class governance concern alongside file existence and path integrity.
11. Phase 06-08 execution history is preserved; corrective work is appended rather than rewritten to maintain APM traceability.
12. Reader-facing governance material owned by repo-agent must be separated from target repository knowledge outputs before replacement readiness can be claimed.
13. Baseline comparison must distinguish hard structural failures from soft quality deltas; coarse heuristic scores are not sufficient for release decisions.
14. SQLite should evolve from a hidden implementation detail into a first-class local knowledge runtime that stores document hierarchy, navigation evidence, and regression results.

## Corrective Recovery and Replacement-Readiness Track

The following phases do not replace the MVP baseline or erase Phase 06-08 history. They explicitly close the verified gaps found during review and readiness assessment so repo-agent can move from "knowledge-base generator" toward a trustworthy local-first replacement for qoder-style repo-wiki.

## Phase 9: Output Contract and Navigation Hardening

**Manager Status:** `Planned`
**Objective:** Repair output-layer boundaries, path contracts, and registry completeness so document-center outputs become structurally reliable.

### Task 9.1 – Target-output boundary and governance-layer separation - Agent_DocGen
**Objective:** Separate repo-agent's internal governance docs from target repository knowledge outputs and make document-layer ownership explicit.
**Output:** Output-layer manifest, target-only generation policy, phase-doc boundary rules, contract updates.
**Guidance:** **Depends on: Task 6.1 Output by Agent_DocGen and Task 8.3 Output by Agent_QualityRelease.** Use `docs/repo-wiki-phase-06-08-review.md`, `docs/repo-wiki-phase-09-12-roadmap.md`, and `docs/operations/AI_API_Atlas_Readiness_Report.md` as the governing review inputs.
1. Define which document layers belong to repo-agent governance and which belong to generated target-repository outputs.
2. Stop treating repo-agent reader-facing phase governance docs as unconditional target-repository generated artifacts.
3. Introduce a deterministic manifest or contract boundary that future generation tasks can consult before writing outputs.
4. Keep existing overview, section, and module outputs additive, but ensure phase-layer generation follows the corrected ownership rules.
5. Add validation that rejects mixed governance-vs-target output paths.

### Task 9.2 – Unified link builder and path-contract recovery - Agent_DocGen
**Objective:** Replace brittle relative-link assembly with a deterministic path contract across overview, section, module, API, and data-model docs.
**Output:** Unified link builder, corrected relative path policy, path-aware rendering helpers, regression fixtures.
**Guidance:** **Depends on: Task 9.1.** Use the verified navigation findings from `docs/repo-wiki-phase-06-08-review.md` as the failure baseline.
1. Define canonical relative path rules for overview-to-section, section-to-overview, section-to-module, and overview-to-core-doc navigation.
2. Implement a shared link-building primitive so templates do not hardcode inconsistent `../` or duplicated `docs/` segments.
3. Update affected templates and generator helpers to consume the new link builder.
4. Add fixture coverage for nested section paths, module links, and source-of-truth cross-links.
5. Prove that previously identified broken path patterns no longer render.

### Task 9.3 – Phase and section registry completion with alias support - Agent_DocGen
**Objective:** Complete the phase/section contract registry and add explicit alias or overlay handling for non-canonical section structures.
**Output:** Completed registry, alias-capable section definitions, schema tests, compatibility rules.
**Guidance:** **Depends on: Task 9.1 and Task 9.2.** This task closes the registry incompleteness identified in review and prepares the system to reason about canonical sections versus legacy overlays such as Q01/S01.
1. Extend the phase registry so it fully covers the current implementation-plan phase set rather than stopping at Phase 06.
2. Add explicit alias or overlay metadata to section definitions so canonical sections can coexist with repository-specific topical layers.
3. Ensure generation and validation consume the same registry source rather than diverging definitions.
4. Keep canonical section naming stable while making compatibility handling explicit and deterministic.
5. Add contract coverage tests for registry completeness and alias resolution.

### Task 9.4 – Path-aware verify navigation checks - Agent_AdapterGovernance
**Objective:** Upgrade navigation verification from string heuristics to real path resolution and cross-link validation.
**Output:** Path-aware navigation verifier, resolved-link checks, reason-code updates, regression tests.
**Guidance:** **Depends on: Task 9.2 Output by Agent_DocGen and Task 9.3 Output by Agent_DocGen.** Keep `verify --ci` command surface unchanged while replacing weak string checks.
1. Resolve markdown links to actual target files and fail when referenced docs do not exist.
2. Check overview, section, API, data-model, and module-page navigation contracts using the corrected registry and link builder.
3. Replace permissive `../`-string heuristics with path-resolved checks.
4. Add precise reason codes for broken navigation, bad path depth, and invalid section routing.
5. Add fixtures that reproduce the previously accepted-but-broken path cases.

## Phase 10: Narrative and Aggregation Intelligence

**Manager Status:** `Planned`
**Objective:** Convert the main reading surfaces from template-heavy exports into repository-specific narrative and aggregation pages.

### Task 10.1 – Narrative builder for overview and architecture - Agent_DocGen
**Objective:** Rebuild overview and architecture generation around repository-derived narrative instead of static generic prose.
**Output:** Narrative builder, repository summary synthesis rules, architecture explanation generator, upgraded templates and tests.
**Guidance:** **Depends on: Task 9.1, Task 9.2, and Task 9.3.** Use `docs/repo-wiki-phase-06-08-review.md` as the fact baseline for why current prose is insufficient.
1. Derive project positioning, core problem, core capabilities, and architecture rationale from repository signals instead of fixed generic sentences.
2. Keep `00-overview.md` and `01-architecture.md` prose-first, but make the prose repository-specific and stable.
3. Generate architecture narrative that explains why the three-layer model exists for the current repository, not only what the layers are named.
4. Preserve Mermaid requirements while improving surrounding explanatory prose quality.
5. Add tests that detect overly generic or repeated boilerplate output patterns.

### Task 10.2 – True API aggregation and entry-point summarization - Agent_DocGen
**Objective:** Replace endpoint re-enumeration with real API grouping, convention extraction, and key entry-point selection.
**Output:** API aggregation engine, auth/error convention extractor, entry-API selector, upgraded template and tests.
**Guidance:** **Depends on: Task 10.1 and Task 6.2 Output by Agent_Scanner.** This task must stop treating "key entry APIs" as a second dump of the full endpoint list.
1. Group APIs by service family, domain, and exposure pattern using extracted metadata.
2. Summarize authentication, gateway, and error behavior from repository facts where possible, with explicit fallback when signals are weak.
3. Select a bounded set of entry APIs based on centrality or usage signals instead of listing every endpoint.
4. Keep a lower-level index available, but ensure the overview layer remains aggregated.
5. Add validation and fixtures proving the overview page stays below raw-dump thresholds.

### Task 10.3 – Core-entity and migration-aware data model aggregation - Agent_DocGen
**Objective:** Rebuild data-model generation around core entities, service boundaries, and real migration/storage summaries.
**Output:** Entity deduper, model aggregator, migration summarizer, upgraded template and tests.
**Guidance:** **Depends on: Task 10.1 and Task 6.2 Output by Agent_Scanner.** Do not rely on a fixed hardcoded list of "core model names" as the primary classification strategy.
1. Identify core entities from cross-module reuse, structural centrality, and storage role instead of static name matching alone.
2. Group remaining models by service boundary and reduce low-signal repetition.
3. Derive database shape and migration strategy from repository signals such as migrations, ORM metadata, and schema definitions.
4. Keep links into source-of-truth and module docs, but make the overview layer explanatory rather than enumerative.
5. Add fixtures for repositories with high model counts to prove deduplication and aggregation quality.

### Task 10.4 – Section page builder rewrite for document-center behavior - Agent_DocGen
**Objective:** Turn section pages from index-style stubs into reader-oriented topical documents with guided drilldown.
**Output:** Section-specific builders, richer section templates, reading-path stitching, section-content tests.
**Guidance:** **Depends on: Task 10.1, Task 10.2, and Task 10.3.** Section pages should become real thematic hubs, not shallow indexes.
1. Replace the generic "Section Content / 模块列表 / API 端点" layout with topic-specific section structures.
2. Keep section pages prose-first and explicitly connect them to overview docs, peer sections, and relevant module docs.
3. Use domain, service-family, API, and data-model summaries to build reader journeys through the repository.
4. Ensure canonical sections remain stable while allowing repository-specific emphasis within each section.
5. Add validation that section pages are topical documents, not just navigational stubs.

## Phase 11: Acceptance and Baseline Governance Hardening

**Manager Status:** `Planned`
**Objective:** Make verify plus baseline comparison trustworthy enough for Manager go/no-go decisions.

### Task 11.1 – Hard-gate vs soft-gate verify redesign - Agent_AdapterGovernance
**Objective:** Split `verify --ci` into structural hard failures and content-quality soft failures with explicit reason families.
**Output:** Verify grading redesign, reason taxonomy, updated CI output schema, regression tests.
**Guidance:** **Depends on: Task 9.4 Output by Agent_AdapterGovernance and Task 10.4 Output by Agent_DocGen.** Preserve the command surface while making the governance semantics decision-grade.
1. Separate non-negotiable structural failures from softer readability or quality deviations.
2. Reclassify existing reason codes into stable families and document grading behavior.
3. Ensure CI output explains why a result is FAIL versus WARN, not just what check triggered.
4. Add regression tests that cover mixed hard/soft outcomes and multi-check reporting.
5. Keep backwards-compatible top-level grade fields while enriching reason detail.

### Task 11.2 – Baseline comparator redesign and score integrity recovery - Agent_QualityRelease
**Objective:** Rebuild the qoder comparison harness so structure and quality scores reflect real deltas rather than heuristic artifacts.
**Output:** Comparator redesign, score rubric, improved section recognition, corrected baseline handling, regression documentation.
**Guidance:** **Depends on: Task 11.1 Output by Agent_AdapterGovernance and Task 8.2 Output by Agent_QualityRelease.** Use `docs/repo-wiki-phase-06-08-review.md`, `docs/AI_API_Atlas_repo_wiki_gap_analysis.md`, and `docs/operations/AI_API_Atlas_Readiness_Report.md` to ground the redesign.
1. Replace weak directory-structure scoring with real hierarchy comparison.
2. Separate canonical section detection from repository-specific overlays such as Q01/S01.
3. Fix heading coverage and baseline-input handling so scores compare the intended artifacts.
4. Distinguish hard structural mismatches from reference-quality gaps in the final report.
5. Document how to interpret scores and where heuristic limits still remain.

### Task 11.3 – Unified readiness-report schema and evidence bundle - Agent_QualityRelease
**Objective:** Merge verify and compare outputs into a single readiness-report contract with reproducible evidence references.
**Output:** Readiness schema, evidence bundle structure, report generator, documentation updates.
**Guidance:** **Depends on: Task 11.1 and Task 11.2.** The goal is to stop producing parallel governance narratives that force Manager to reconcile them manually.
1. Define a unified readiness-report schema that includes verify grade, comparator results, blocking gaps, and next-step recommendation.
2. Standardize evidence references to generated docs, gap reports, and command outputs.
3. Ensure the report explicitly separates product gaps, tooling gaps, and compatibility overlays.
4. Update governance documentation so future acceptance runs follow one reporting contract.
5. Add tests or fixtures proving report generation remains stable as reason codes evolve.

### Task 11.4 – Multi-repository regression acceptance - Agent_QualityRelease
**Objective:** Expand acceptance beyond `AI_API_Atlas` so replacement-readiness is judged across multiple repository shapes.
**Output:** Multi-repo acceptance matrix, comparative gap reports, updated readiness conclusions.
**Guidance:** **Depends on: Task 11.3.** `AI_API_Atlas` remains mandatory, but it must no longer be the sole basis for replacement-readiness claims.
1. Run the unified acceptance flow on `AI_API_Atlas` and at least one additional representative repository.
2. Compare structural and quality outcomes across repositories to identify recurring versus repository-specific gaps.
3. Update readiness conclusions using the new evidence bundle and report schema.
4. Record blockers that still prevent repo-agent from being positioned as a qoder replacement.
5. Provide a clear Manager recommendation for whether to proceed to runtime hardening or return to generation fixes.

## Phase 12: SQLite-First Local Knowledge Runtime

**Manager Status:** `Planned`
**Objective:** Elevate SQLite from operational support store to first-class local knowledge runtime for document hierarchy, evidence, and incremental regeneration.

### Task 12.1 – Dual-database runtime architecture for state and evidence - Agent_IndexGraph
**Objective:** Define and implement separate responsibilities for operational state and generation/evidence persistence.
**Output:** Dual-database architecture, schema plan, migration path, runtime boundary rules.
**Guidance:** **Depends on: Task 11.4 Output by Agent_QualityRelease and Task 2.1 Output by Agent_IndexGraph.** Use `docs/qoder-repo-wiki-sqlite-analysis.md` and `docs/repo-wiki-phase-09-12-roadmap.md` as the planning baseline.
1. Define the responsibilities of the primary state DB versus a generation/evidence DB.
2. Keep compatibility with existing SQLite state while introducing a clean expansion path.
3. Document how verify, compare, generation cache, and navigation evidence map onto the new boundary.
4. Add migrations or schema versioning support for the expanded runtime model.
5. Validate repeated upgrade and rebuild behavior.

### Task 12.2 – SQLite schema for hierarchy, sections, navigation, and evidence - Agent_IndexGraph
**Objective:** Persist document-center structure and quality evidence in SQLite so navigation and readiness become queryable runtime facts.
**Output:** SQLite tables for docs hierarchy, section registry, nav graph, readiness evidence, and related tests.
**Guidance:** **Depends on: Task 12.1 and Task 9.3 Output by Agent_DocGen.**
1. Store document hierarchy, canonical sections, aliases, and cross-links in structured SQLite tables.
2. Store verify and compare evidence references in queryable form.
3. Keep external markdown and source-of-truth artifacts as outputs while SQLite becomes the operational metadata backbone.
4. Add integrity checks for orphan docs, broken section mappings, and stale evidence records.
5. Validate schema behavior on rebuild and partial-update scenarios.

### Task 12.3 – Verify and compare persistence with trend analysis - Agent_IndexGraph
**Objective:** Persist repeated governance runs so repo-agent can analyze quality trends rather than only emit one-off reports.
**Output:** Verify-run storage, compare-run storage, trend queries, diagnostic exports.
**Guidance:** **Depends on: Task 12.2, Task 11.1 Output by Agent_AdapterGovernance, and Task 11.2 Output by Agent_QualityRelease.**
1. Persist verify and compare runs with timestamps, repo target, grades, reason families, and evidence links.
2. Add queries or exports that show recurring failures, regressions, and improvements over time.
3. Keep report generation compatible with single-run workflows while enabling historical analysis.
4. Ensure storage remains local-first and deterministic.
5. Add tests for repeated-run persistence and summary queries.

### Task 12.4 – SQLite-driven page invalidation and incremental regeneration - Agent_IndexGraph
**Objective:** Use SQLite runtime knowledge to drive page-level invalidation and regeneration instead of broad full-template rerenders.
**Output:** Page invalidation model, regeneration planner, cache-invalidation rules, regression tests.
**Guidance:** **Depends on: Task 12.3 and Task 2.4 Output by Agent_IndexGraph.** This task is the runtime payoff of the SQLite-first model.
1. Map changed files and impacted modules to affected overview, section, module, API, and data-model pages using stored hierarchy and navigation facts.
2. Invalidate generation cache entries at page granularity based on evidence-aware dependency rules.
3. Keep full rebuild available, but make incremental regeneration the preferred path when scope is bounded.
4. Validate add, modify, delete, rename, and section-registry-change scenarios.
5. Document how this runtime model supports replacement-readiness for local-first repo-wiki operation.

## Forward Replacement and Productization Track

The following phases are appended as future planning tasks after the Phase 09-12 corrective baseline. They focus on closing Atlas hard gates, aligning against external qoder-style baselines, providing usable visual consumption, and defining a formal replacement release gate.

## Phase 13: Atlas Cutover and Hard-Gate Clearance

**Manager Status:** `Planned`
**Objective:** Clear hard blockers on `AI_API_Atlas` and ensure runtime, compatibility, and core-document quality are integrated in one acceptance loop.

### Task 13.1 – Runtime-store orchestration integration across core commands - Agent_IndexGraph
**Objective:** Wire `runtime.sqlite3` and evidence persistence into `init`, `index`, `update`, and `verify` execution paths.
**Output:** Runtime orchestration integration, command-surface hooks, migration/rebuild handling, acceptance tests.
**Guidance:** **Depends on: Task 12.4 Output by Agent_IndexGraph and Task 3.3 Output by Agent_PlatformCore.** Use `docs/repo-wiki-phase-09-12-audit-atlas-comparison-and-phase-13-plan.md` as the direct acceptance-gap baseline.
1. Integrate runtime store lifecycle into command orchestration without changing CLI command names.
2. Ensure runtime tables required by verify/compare/readiness are created on first run and upgraded safely on subsequent runs.
3. Keep fallback behavior deterministic when runtime DB is missing or corrupted.
4. Add integration tests covering `init -> index -> verify` and incremental `update -> verify`.
5. Emit machine-readable diagnostics proving runtime evidence was persisted.

### Task 13.2 – Section compatibility bridge for Q*/S* formats - Agent_DocGen
**Objective:** Implement canonical-section compatibility mapping for repositories using Q01/S01-style section naming.
**Output:** Alias/overlay bridge rules, section-resolution updates, compatibility tests, migration notes.
**Guidance:** **Depends on: Task 9.3 Output by Agent_DocGen and Task 13.1 Output by Agent_IndexGraph.** Use `docs/operations/AI_API_Atlas_Readiness_Report.md` and `docs/AI_API_Atlas_repo_wiki_gap_analysis.md` to target the verified incompatibility.
1. Keep canonical section slugs stable while allowing explicit alias overlays for legacy Q*/S* sections.
2. Update generation and verify so section coverage can pass through compatibility mappings instead of forced renaming.
3. Record alias resolution in runtime evidence for traceability.
4. Add tests for mixed canonical plus legacy section sets.
5. Document precedence rules when canonical and alias pages both exist.

### Task 13.3 – Atlas core-document narrative and aggregation remediation - Agent_DocGen
**Objective:** Lift `00/01/03/04/05` generation quality on `AI_API_Atlas` to pass prose-first and aggregation gates.
**Output:** Atlas-oriented generation refinements, core-doc quality fixtures, gated test coverage.
**Guidance:** **Depends on: Task 10.4 Output by Agent_DocGen and Task 13.2 Output by Agent_DocGen.** This task closes the unresolved FAIL reasons (`CONTENT_TOO_SHORT`, `ARCH_MERMAID_MISSING`, `AGG_API_NOT_GROUPED`, `AGG_DM_NOT_GROUPED`).
1. Increase prose density with repository-fact-backed narrative, not generic filler.
2. Guarantee architecture output includes valid Mermaid plus explanatory prose.
3. Ensure API and data-model pages meet grouped aggregation contracts.
4. Keep module-map output domain-centered with stable navigation.
5. Add Atlas fixtures proving all five core docs satisfy quality thresholds.

### Task 13.4 – Atlas hard-gate clearance and blocker burn-down report - Agent_QualityRelease
**Objective:** Run full Atlas acceptance and produce a blocker-focused burn-down report for Manager decisioning.
**Output:** Acceptance run logs, verify/compare outputs, blocker matrix, remediation recommendation.
**Guidance:** **Depends on: Task 13.1, Task 13.2, and Task 13.3.** Reuse unified readiness schema from Task 11.3 so results are directly comparable with historical reports.
1. Execute `init`, `index`, `update`, `verify --ci`, and baseline compare on `AI_API_Atlas`.
2. Classify outcomes into hard blockers, soft quality deltas, and compatibility overlays.
3. Produce a burn-down matrix linking each remaining blocker to owning phase/task.
4. Confirm runtime evidence and trend records are written for this acceptance cycle.
5. Provide a clear recommendation to proceed to external baseline calibration or return to generation fixes.

## Phase 14: External Baseline Calibration and Benchmark Governance

**Manager Status:** `Planned`
**Objective:** Replace self-baseline heuristics with external qoder-style snapshots and establish benchmark-grade scoring governance.

### Task 14.1 – External qoder snapshot fixture contract and ingestion - Agent_QualityRelease
**Objective:** Define and implement a reproducible fixture format for external qoder-style repo-wiki snapshots.
**Output:** Snapshot fixture contract, ingestion toolchain, fixture validation tests, documentation.
**Guidance:** **Depends on: Task 11.2 Output by Agent_QualityRelease and Task 13.4 Output by Agent_QualityRelease.**
1. Define required fixture metadata (source commit, capture date, locale, section taxonomy, generation mode).
2. Build ingestion that normalizes snapshot directories for deterministic comparison.
3. Validate fixture completeness and reject partial baselines.
4. Keep support for self-baseline mode as explicit fallback only.
5. Document fixture lifecycle and update policy.

### Task 14.2 – Comparator calibration with external baseline and weighted rubric - Agent_QualityRelease
**Objective:** Calibrate comparison scoring against external fixtures and align weights to replacement-readiness priorities.
**Output:** Calibrated comparator rubric, scoring weights, upgraded reports, regression tests.
**Guidance:** **Depends on: Task 14.1.** Use `docs/qoder-repo-wiki-design-analysis.md` and `docs/qoder-repo-wiki-sqlite-analysis.md` as capability references.
1. Separate structural compatibility, narrative quality, and navigation integrity into explicit weighted dimensions.
2. Ensure section alias/overlay handling does not inflate scores.
3. Add confidence tagging for dimensions with weak extraction signals.
4. Recompute historical sample reports using the new rubric for back-comparison.
5. Publish interpretation rules for score bands and gating thresholds.

### Task 14.3 – Cross-repository benchmark matrix and threshold profiles - Agent_QualityRelease
**Objective:** Build a stable benchmark matrix across multiple repositories with profile-based pass thresholds.
**Output:** Benchmark repository matrix, threshold profiles, comparative acceptance reports.
**Guidance:** **Depends on: Task 14.2 and Task 11.4 Output by Agent_QualityRelease.**
1. Run calibrated compare flow across `AI_API_Atlas` and at least two additional representative repositories.
2. Produce per-profile thresholds (strict replacement, transitional adoption, internal pilot).
3. Identify recurring gaps versus repository-specific outliers.
4. Store benchmark outputs in a reproducible evidence bundle structure.
5. Recommend default threshold profile for replacement announcements.

### Task 14.4 – SQLite-backed governance dashboard export and trends - Agent_IndexGraph
**Objective:** Expose verify/compare trends from SQLite evidence for Manager and release governance consumption.
**Output:** Query/export utilities, trend dashboard artifacts, governance docs, tests.
**Guidance:** **Depends on: Task 12.3 Output by Agent_IndexGraph and Task 14.3 Output by Agent_QualityRelease.**
1. Build reproducible exports for score trend, reason-family trend, and hard/soft gate trend.
2. Link each trend entry to evidence bundle references.
3. Support per-repository and cross-repository views.
4. Keep outputs local-first and scriptable for CI usage.
5. Add regression checks ensuring schema evolution does not break exports.

## Phase 15: Visual Knowledge Experience and IDE Integration

**Manager Status:** `Planned`
**Objective:** Deliver a readable and inspectable local visual experience that makes repo-agent output comparable to qoder repo-wiki consumption patterns.

### Task 15.1 – Isolated eval output layout and manifest for target repos - Agent_PlatformCore
**Objective:** Standardize isolated evaluation outputs under `.repo-agent-eval` without polluting protected baseline directories.
**Output:** Eval output layout contract, manifest schema, path policy, validation tests.
**Guidance:** **Depends on: Task 13.4 Output by Agent_QualityRelease and Task 9.1 Output by Agent_DocGen.**
1. Define directory contract for generated docs, evidence, and compare artifacts in `.repo-agent-eval`.
2. Keep existing `.repo-wiki` and `docs/` baselines untouched by default.
3. Provide explicit configuration toggles for output targets.
4. Validate manifest integrity and path safety.
5. Document manual review workflow for human acceptance.

### Task 15.2 – Static repo-wiki viewer with tree navigation and Mermaid rendering - Agent_PlatformCore
**Objective:** Build a local static viewer for generated wiki docs with left-tree navigation and rich markdown rendering.
**Output:** Static viewer app, nav-tree loader, Mermaid rendering support, viewer tests.
**Guidance:** **Depends on: Task 15.1 and Task 9.4 Output by Agent_AdapterGovernance.**
1. Render canonical overview/section/module hierarchy with collapsible tree navigation.
2. Support headings anchor navigation and table-of-contents for long pages.
3. Render Mermaid diagrams safely in local mode.
4. Keep viewer decoupled from generation so it can open historical snapshots.
5. Add fixtures using Atlas outputs to validate readability and navigation.

### Task 15.3 – VS Code extension prototype for repo-agent wiki browsing - Agent_PlatformCore
**Objective:** Provide an IDE extension prototype that exposes repo-agent wiki tree and page preview in VS Code-compatible environments.
**Output:** Extension scaffold, tree provider, markdown preview bridge, packaging instructions.
**Guidance:** **Depends on: Task 15.2.** This phase is a capability prototype; it must not change the existing command surface.
1. Implement sidebar tree loading from `.repo-agent-eval` manifest.
2. Open selected nodes in preview with linked navigation support.
3. Expose quick actions for `repo-wiki update` and `repo-wiki verify --ci`.
4. Keep extension behavior explicit about local filesystem scope.
5. Document compatibility assumptions and non-goals versus proprietary qoder integration.

### Task 15.4 – Qoder-style navigation metadata adapter and import bridge - Agent_AdapterGovernance
**Objective:** Add optional metadata adapter so qoder-like navigation structures can be imported for side-by-side evaluation.
**Output:** Metadata adapter, import bridge, compatibility docs, verifier checks.
**Guidance:** **Depends on: Task 15.3 and Task 9.3 Output by Agent_DocGen.**
1. Define adapter contract for ingesting qoder-like tree metadata into repo-agent viewer format.
2. Keep adapter optional and non-invasive to canonical generation contracts.
3. Validate imported metadata links against actual files.
4. Emit compatibility warnings when imported metadata diverges from canonical sections.
5. Add regression fixtures for mixed canonical plus imported navigation trees.

## Phase 16: Qoder-Replacement Cutover and Release Gate

**Manager Status:** `Planned`
**Objective:** Formalize replacement governance, rollout policy, and final go/no-go decisioning for qoder repo-wiki substitution.

### Task 16.1 – Replacement gate policy and rollback playbook - Agent_QualityRelease
**Objective:** Define strict replacement gate policy and rollback procedures for target repositories.
**Output:** Replacement gate contract, rollback playbook, operational checklist.
**Guidance:** **Depends on: Task 14.4 Output by Agent_IndexGraph and Task 15.4 Output by Agent_AdapterGovernance.**
1. Define mandatory gate conditions across verify, compare, runtime evidence, and visual acceptance.
2. Specify transition policies for repositories in transitional profile tiers.
3. Define rollback triggers and recovery workflow.
4. Provide decision templates for Manager sign-off.
5. Add policy validation checks to prevent incomplete gate claims.

### Task 16.2 – CI cutover template pack and policy profiles - Agent_AdapterGovernance
**Objective:** Package replacement gate policies into reusable CI templates and profile presets.
**Output:** CI template pack, profile configs, policy enforcement scripts, documentation.
**Guidance:** **Depends on: Task 16.1 and Task 11.1 Output by Agent_AdapterGovernance.**
1. Encode strict, transitional, and pilot policy profiles for CI usage.
2. Keep `verify --ci` and compare outputs machine-readable for pipeline enforcement.
3. Add failure messaging that points to remediation evidence paths.
4. Provide migration guidance from legacy governance scripts.
5. Add tests for profile-based CI behavior.

### Task 16.3 – Final pilot execution across Atlas and benchmark repositories - Agent_QualityRelease
**Objective:** Execute final replacement pilots across Atlas and benchmark repositories under new gate policies.
**Output:** Pilot execution package, cross-repo gate outcomes, residual-risk register.
**Guidance:** **Depends on: Task 16.2 and Task 14.3 Output by Agent_QualityRelease.**
1. Run full generation, verification, compare, and visual acceptance on pilot repositories.
2. Record pass/fail outcomes per policy profile.
3. Capture residual risks and unresolved compatibility constraints.
4. Validate rollback readiness through at least one drill.
5. Summarize whether replacement criteria are sustainably met.

### Task 16.4 – Go/no-go decision dossier and handover package - Agent_QualityRelease
**Objective:** Produce final decision dossier with evidence links and implementation handover plan.
**Output:** Decision dossier, handover package, next-cycle backlog recommendations.
**Guidance:** **Depends on: Task 16.3.** The dossier must be decision-grade and explicitly state whether repo-agent can replace qoder repo-wiki in scoped environments.
1. Aggregate evidence from all prior phases into one auditable dossier.
2. State go/no-go with explicit blocking reasons if no-go.
3. Provide repository rollout ordering and ownership model.
4. Capture deferred improvements as post-cutover backlog.
5. Publish handover checklist for ongoing operations and governance.

## Evidence Repair and Transitional Release Track

The Phase 14-16 review found useful implementation progress but also evidence contradictions, unenforced CI gates, a packaging blocker, and remaining content-quality gaps. The following phases explicitly repair those issues before any replacement claim is made.

## Phase 17: Evidence Integrity and CI Gate Repair

**Manager Status:** `Planned`
**Objective:** Make governance evidence and CI gates trustworthy before further release work proceeds.

### Task 17.1 – Decision evidence reconciliation and dossier canonicalization - Agent_QualityRelease
**Objective:** Reconcile contradictory Memory, evidence, and decision artifacts into one canonical decision record.
**Output:** Canonical dossier location, corrected evidence summary, Memory status patch, contradiction report.
**Guidance:** **Depends on: Task 16.4 Output by Agent_QualityRelease.** Use `docs/repo-wiki-phase-14-16-review-and-phase-17-20-plan.md` as the review baseline.
1. Compare `.apm/Memory/Memory_Root.md`, Phase 14-16 logs, `.repo-agent-eval/go-no-go-decision/**`, and `docs/operations/**`.
2. Resolve `CONDITIONAL GO` versus `CONDITIONAL NO-GO` wording into a single Manager-approved status.
3. Promote or explicitly classify generated decision artifacts so paths in logs and operations docs match reality.
4. Add an evidence consistency checklist for future handovers.
5. Record unresolved claims as follow-up risks instead of silent PASS statements.

### Task 17.2 – CI decision gate enforcement and workflow correctness - Agent_AdapterGovernance
**Objective:** Fix CI workflows so policy rejections fail jobs and scripts execute through the correct interpreter.
**Output:** Corrected workflows, decision script hardening, profile simulation tests, CI documentation updates.
**Guidance:** **Depends on: Task 16.2 Output by Agent_AdapterGovernance and Task 17.1 Output by Agent_QualityRelease.**
1. Replace `python ci/scripts/decision.sh` with the correct shell execution path.
2. Remove failure-swallowing behavior from strict and transitional decision gates.
3. Define the expected behavior for pilot `allow-continue` explicitly.
4. Remove or replace undeclared dependencies such as `bc`.
5. Add tests that simulate PASS, WARN, and REJECTED profile outcomes.

### Task 17.3 – Python packaging and reproducible test harness repair - Agent_PlatformCore
**Objective:** Fix package discovery and document a reproducible test command for Phase 14-16 governance tests.
**Output:** `pyproject.toml` package discovery fix, reproducible test command, test environment docs.
**Guidance:** **Depends on: Task 17.2 and current `pyproject.toml`.**
1. Restrict package discovery so `uv run pytest` can build the editable project.
2. Keep `repo_wiki` as the intended distributable package.
3. Verify Phase 14-16 targeted tests run under the documented command.
4. Add packaging regression checks where practical.
5. Document local and CI test invocation.

### Task 17.4 – Governance regression tests for known review failures - Agent_QualityRelease
**Objective:** Add focused regression tests for failures found in the Phase 14-16 audit.
**Output:** Tests for comparator config export, CI gate behavior, evidence path existence, and dossier consistency.
**Guidance:** **Depends on: Task 17.1, Task 17.2, and Task 17.3.**
1. Add a test for `BaselineComparatorConfig().to_dict()`.
2. Add tests that fail when workflows call shell scripts through Python.
3. Add tests that fail when strict/transitional gates are made non-blocking.
4. Add evidence path checks for files claimed by Memory logs and operation docs.
5. Include these checks in the standard governance test subset.

## Phase 18: Transitional Quality Uplift

**Manager Status:** `Planned`
**Objective:** Raise repo-agent output from pilot-only quality toward the transitional replacement threshold.

### Task 18.1 – Section coverage completion and navigation contract repair - Agent_DocGen
**Objective:** Bring required section coverage and navigation completeness to transitional target.
**Output:** Missing section generation, navigation links, section coverage tests.
**Guidance:** **Depends on: Task 17.4 and Task 15.4 Output by Agent_AdapterGovernance.**
1. Ensure required sections, including troubleshooting, are generated or mapped deterministically.
2. Repair overview-to-section and section-to-overview links.
3. Keep qoder-style overlays compatible without replacing canonical sections.
4. Add coverage tests for required section set and cross-links.
5. Update verify expectations for transitional profile.

### Task 18.2 – Heading coverage and prose-density generation upgrade - Agent_DocGen
**Objective:** Improve overview, architecture, and section prose so compare quality score can reach transitional thresholds.
**Output:** Heading contract enforcement, prose-first builders, anti-list-dump checks, fixtures.
**Guidance:** **Depends on: Task 18.1 and Task 10.1 Output by Agent_DocGen.**
1. Add required heading coverage for core docs.
2. Increase repository-specific prose density without generic filler.
3. Reduce list/table dominance in top-level reading pages.
4. Add tests for minimum prose, heading coverage, and repeated-boilerplate detection.
5. Keep generated text grounded in source-of-truth facts.

### Task 18.3 – API and data-model aggregation depth refinement - Agent_DocGen
**Objective:** Improve API and data-model aggregation quality beyond partial grouping.
**Output:** Better service-family grouping, core entity summaries, migration/storage summaries, quality tests.
**Guidance:** **Depends on: Task 18.2, Task 10.2, and Task 10.3.**
1. Ensure API docs include grouped service families, auth/error conventions, and selected key entry points.
2. Ensure data-model docs include core entities, service models, and database/migration summaries.
3. Limit raw endpoint/model dumps in overview surfaces.
4. Preserve lower-level drilldown links for detail.
5. Add high-count fixture tests.

### Task 18.4 – Transitional acceptance rerun and quality burn-down - Agent_QualityRelease
**Objective:** Re-run acceptance after quality fixes and determine whether transitional threshold is met.
**Output:** Updated compare report, verify report, burn-down matrix, go/no-go recommendation for Phase 19.
**Guidance:** **Depends on: Task 18.1, Task 18.2, and Task 18.3.**
1. Run verify and compare using repaired CI/test harness.
2. Target overall score >= 0.70 and no hard gate failures.
3. Report remaining gaps by dimension and owning component.
4. Store evidence under the canonical eval output layout.
5. Recommend whether to proceed to visual hardening or recycle content fixes.

## Phase 19: Viewer and IDE Hardening

**Manager Status:** `Planned`
**Objective:** Convert Phase 15 prototypes into reliable manual-acceptance tools.

### Task 19.1 – Static viewer offline asset and safety hardening - Agent_PlatformCore
**Objective:** Remove CDN dependency, harden Mermaid/markdown rendering, and keep viewer local-first.
**Output:** Bundled asset strategy, safer rendering pipeline, offline viewer tests.
**Guidance:** **Depends on: Task 18.4 and Task 15.2 Output by Agent_PlatformCore.**
1. Replace CDN-only Mermaid loading with bundled or configurable local assets.
2. Define markdown/HTML safety boundaries for static rendering.
3. Keep viewer usable directly from eval artifacts.
4. Add tests for Mermaid rendering and asset availability.
5. Document offline review behavior.

### Task 19.2 – VS Code extension runtime path and manifest discovery repair - Agent_PlatformCore
**Objective:** Fix extension runtime behavior so sidebar nodes open correct files from eval runs.
**Output:** Workspace-root path resolution, run-dir manifest discovery, command execution tests, extension docs.
**Guidance:** **Depends on: Task 19.1 and Task 15.3 Output by Agent_PlatformCore.**
1. Resolve node paths against the workspace root before opening files.
2. Discover timestamped `.repo-agent-eval/<run_id>/manifest.json` files, not only root manifest.
3. Expose active-run selection or deterministic latest-run behavior.
4. Validate command invocations for update and verify.
5. Add extension host or smoke tests where practical.

### Task 19.3 – Visual acceptance snapshots and navigation regression suite - Agent_QualityRelease
**Objective:** Add automated evidence for viewer usability and navigation integrity.
**Output:** Snapshot test harness, navigation regression report, visual acceptance evidence.
**Guidance:** **Depends on: Task 19.1 and Task 19.2.**
1. Use generated eval artifacts as viewer fixtures.
2. Capture representative desktop and narrow viewport snapshots.
3. Verify navigation tree, page rendering, Mermaid presence, and broken-link behavior.
4. Store visual evidence in the canonical evidence bundle.
5. Make visual acceptance a non-optional release-candidate check.

### Task 19.4 – Qoder side-by-side navigation comparison hardening - Agent_AdapterGovernance
**Objective:** Make qoder-style navigation import useful for manual comparison without weakening canonical contracts.
**Output:** Side-by-side nav compare report, import schema tests, compatibility warnings.
**Guidance:** **Depends on: Task 19.3 and Task 15.4.**
1. Validate imported qoder navigation against actual files and canonical sections.
2. Report unmatched nodes, alias conflicts, and depth mismatch with reason codes.
3. Provide side-by-side output for manual review.
4. Keep imported metadata read-only.
5. Add fixtures for AI_API_Atlas-style navigation trees.

## Phase 20: Transitional Release Candidate and Strict Gap Plan

**Manager Status:** `Planned`
**Objective:** Produce a trustworthy release-candidate decision and a concrete backlog to reach strict replacement quality.

### Task 20.1 – External fixture provenance and benchmark refresh policy - Agent_QualityRelease
**Objective:** Formalize provenance rules for qoder snapshot fixtures used in release-candidate comparison.
**Output:** Fixture provenance policy, refresh workflow, fixture confidence scoring, docs.
**Guidance:** **Depends on: Task 14.1 and Task 18.4.**
1. Define accepted fixture sources, capture metadata, and retention policy.
2. Record confidence levels for proprietary or manually captured baselines.
3. Make fixture freshness visible in compare reports.
4. Add refresh checklist for benchmark maintainers.
5. Reject release-candidate comparisons with stale or incomplete fixtures.

### Task 20.2 – Release-candidate pilot across benchmark repositories - Agent_QualityRelease
**Objective:** Run a full release-candidate pilot using repaired gates, improved content, and hardened visual tools.
**Output:** Cross-repo RC evidence bundle, policy outcome matrix, residual risk register.
**Guidance:** **Depends on: Task 19.4 and Task 20.1.**
1. Run generation, verify, compare, viewer snapshot, and policy decision for each benchmark repository.
2. Require transitional profile to pass for candidate repositories.
3. Record strict-profile gap separately from transitional release status.
4. Store all evidence under canonical output layout.
5. Produce a release-candidate decision summary.

### Task 20.3 – Strict threshold gap backlog and ownership plan - Agent_QualityRelease
**Objective:** Convert remaining strict-profile gaps into owned, prioritized backlog items.
**Output:** Strict gap backlog, owner map, acceptance criteria, sequencing recommendation.
**Guidance:** **Depends on: Task 20.2.**
1. Break remaining score deficits into concrete generator, verifier, viewer, and governance tasks.
2. Assign owner role and acceptance metric to each backlog item.
3. Separate strict blockers from polish improvements.
4. Identify any gaps that need product decision instead of implementation.
5. Recommend Phase 21+ only if strict release remains non-trivial.

### Task 20.4 – Transitional go/no-go dossier and manager handover - Agent_QualityRelease
**Objective:** Produce a final transitional go/no-go dossier and handover package.
**Output:** Transitional decision dossier, evidence index, handover checklist, next-phase recommendation.
**Guidance:** **Depends on: Task 20.2 and Task 20.3.**
1. State whether repo-agent can replace qoder for transitional/pilot environments.
2. Keep strict production replacement separate unless strict criteria are met.
3. Link every claim to evidence files.
4. Update Memory Root with final phase judgment.
5. Prepare Manager handover for the next execution cycle.

## Phase 21: LLM Provider Abstraction and Secure Configuration

**Manager Status:** `Planned`
**Objective:** Establish a secure, pluggable LLM provider layer for Minimax, OpenAI-compatible endpoints, Anthropic-compatible adapters, and local providers.

### Task 21.1 – LLM config schema and environment resolution - Agent_PlatformCore
**Objective:** Add the `llm` configuration schema, environment variable resolution, and secret redaction.
**Output:** Typed schema, env precedence rules, redacted diagnostics, tests.
**Guidance:** **Depends on: Task 20.4.**
1. Define provider/model/base_url/api_key_env/timeout/retry/token fields.
2. Resolve values from config, environment, and CLI overrides without logging secrets.
3. Add validation errors with stable reason codes.
4. Add targeted tests for missing key, redaction, and invalid provider values.

### Task 21.2 – Provider interface and request/response contract - Agent_PlatformCore
**Objective:** Define the unified LLM client contract.
**Output:** `LLMClient`, `ChatRequest`, `ChatResponse`, provider error model, mock provider tests.
**Guidance:** **Depends on: Task 21.1.**
1. Define request/response fields needed by page planning and composition.
2. Normalize provider errors for timeout, rate limit, auth, and missing key cases.
3. Add a mock provider used by CI and snapshot tests.
4. Keep real API usage optional.

### Task 21.3 – OpenAI-compatible and Minimax provider implementation - Agent_PlatformCore
**Objective:** Implement OpenAI-compatible and Minimax provider adapters.
**Output:** Provider adapters, config mapping, mock-backed unit tests, optional smoke hook.
**Guidance:** **Depends on: Task 21.2.**
1. Support base_url/model/api_key_env configuration.
2. Avoid requiring real keys in CI.
3. Add optional smoke command gated by env availability.
4. Ensure provider responses map into the unified response contract.

### Task 21.4 – Token budgeting, retry, and cache policy - Agent_PlatformCore
**Objective:** Add token budget accounting, retry/backoff policy, and safe cache behavior.
**Output:** Budget estimator, retry wrapper, cache key policy, tests.
**Guidance:** **Depends on: Task 21.3.**
1. Track estimated prompt/completion tokens per request.
2. Retry only safe provider failures with bounded backoff.
3. Cache successful deterministic requests and never cache failures.
4. Add duplicate-request cache hit tests.

### Task 21.5 – CLI configuration validation and diagnostics - Agent_AdapterGovernance
**Objective:** Add a user-facing configuration diagnostic command.
**Output:** `repo-wiki config doctor` or equivalent diagnostics with reason codes.
**Guidance:** **Depends on: Task 21.4 Output by Agent_PlatformCore.**
1. Validate provider, model, base URL, API key env, and budget settings.
2. Redact all secrets in terminal and JSON outputs.
3. Return machine-readable reason codes for missing key and invalid provider.
4. Add CLI smoke tests.

## Phase 22: Qoder-like Wiki Planner and Chinese Information Architecture

**Manager Status:** `Planned`
**Objective:** Replace fixed docs output with a planned Chinese Wiki tree that can approach Qoder page coverage before generation starts.

### Task 22.1 – Wiki page-plan schema and navigation tree contract - Agent_DocGen
**Objective:** Define the page plan and navigation manifest contracts.
**Output:** `wiki-plan.json` schema, navigation tree manifest contract, compatibility tests.
**Guidance:** **Depends on: Task 21.5.**
1. Define page id, title, category, parent, output path, source requirements, and generation mode.
2. Define manifest navigation nodes consumed by the IDE and static viewer.
3. Add schema tests and backward compatibility checks.

### Task 22.2 – Chinese taxonomy baseline for Qoder-like output - Agent_DocGen
**Objective:** Add the default Chinese top-level taxonomy for Qoder-like output.
**Output:** Taxonomy rules for 项目概述、架构设计、核心服务、Python服务、前端应用、数据模型、API参考、部署运维、开发指南、安全合规、故障排除.
**Guidance:** **Depends on: Task 22.1.**
1. Encode top-level categories and allowed child category families.
2. Make taxonomy configurable by profile without breaking defaults.
3. Validate AI_API_Atlas can plan Chinese top-level columns.

### Task 22.3 – Repository identity resolver - Agent_Scanner
**Objective:** Identify the repository name, product position, and major runtimes from source evidence.
**Output:** Repository identity resolver using git root, README, build files, package metadata, and directory names.
**Guidance:** **Depends on: Task 22.2 Output by Agent_DocGen.**
1. Prefer explicit repository metadata over generic workspace names.
2. Extract identity hints from README, pom.xml, package.json, pyproject.toml, and directory naming.
3. Add AI_API_Atlas regression so identity is not `workspace`.

### Task 22.4 – Rule-first page planner - Agent_DocGen
**Objective:** Generate a stable page plan without calling an LLM.
**Output:** Deterministic planner that creates a Qoder-like page tree from source-of-truth artifacts.
**Guidance:** **Depends on: Task 22.3 Output by Agent_Scanner.**
1. Use repository identity, modules, APIs, data models, and runtime roles.
2. Produce at least 80 AI_API_Atlas planned pages in rule-only mode.
3. Keep output order stable across runs.

### Task 22.5 – LLM-assisted page planner - Agent_DocGen
**Objective:** Use the LLM provider to expand and improve page titles and structure.
**Output:** LLM planner mode with mock tests and optional real provider smoke.
**Guidance:** **Depends on: Task 22.4 and Task 21.4 Output by Agent_PlatformCore.**
1. Extend the rule plan rather than replacing it blindly.
2. Keep page ids deterministic and paths stable.
3. Target at least 120 AI_API_Atlas planned pages when LLM is enabled.

### Task 22.6 – Planner persistence into SQLite and manifest - Agent_IndexGraph
**Objective:** Persist page plan and navigation tree for downstream generation and plugins.
**Output:** SQLite plan tables and `.repo-agent-eval/<run>/manifest.json` navigation tree.
**Guidance:** **Depends on: Task 22.5 Output by Agent_DocGen and Task 12.2.**
1. Store planned pages, nav nodes, and profile metadata.
2. Write manifest fields consumed by the VS Code extension.
3. Add read/write and manifest tests.

## Phase 23: Evidence Builder with File and Line Citations

**Manager Status:** `Planned`
**Objective:** Build file/line evidence so generated pages can include Qoder-like citations and verifiable source grounding.

### Task 23.1 – Source span extractor for Java Python TypeScript SQL YAML Markdown - Agent_Scanner
**Objective:** Extract file, symbol, line range, and summary spans across core languages.
**Output:** Multi-language span extractor and fixtures.
**Guidance:** **Depends on: Task 22.6.**
1. Support Java, Python, TypeScript, SQL, YAML, and Markdown fixtures.
2. Preserve accurate line ranges for symbols and important blocks.
3. Add tests for line-number accuracy.

### Task 23.2 – Evidence SQLite schema - Agent_IndexGraph
**Objective:** Store evidence spans and page-source relationships.
**Output:** `evidence_span`, `page_source_map`, `symbol_reference` tables and migrations.
**Guidance:** **Depends on: Task 23.1 Output by Agent_Scanner.**
1. Persist source spans with file path, line range, language, symbol, and digest.
2. Persist page-source matching records.
3. Add migration and read/write tests.

### Task 23.3 – Evidence ranking and page matching - Agent_DocGen
**Objective:** Match planned pages to the most relevant evidence candidates.
**Output:** Evidence ranking pipeline and page matching tests.
**Guidance:** **Depends on: Task 23.2 Output by Agent_IndexGraph and Task 22.6.**
1. Rank evidence by page topic, module, symbol, API, and data model relevance.
2. Bind at least five candidates per planned page where source exists.
3. Record insufficient-evidence pages explicitly.

### Task 23.4 – Citation block renderer - Agent_DocGen
**Objective:** Render citations into generated Markdown.
**Output:** `<cite>` blocks, section sources, diagram sources, path-resolvable file links.
**Guidance:** **Depends on: Task 23.3.**
1. Render file paths and line ranges without leaking local secrets.
2. Support citations for prose sections and Mermaid diagrams.
3. Add broken-path fixtures and renderer tests.

### Task 23.5 – Citation verifier - Agent_AdapterGovernance
**Objective:** Add citation coverage and broken citation checks to verify.
**Output:** `verify --ci` citation gates and reason codes.
**Guidance:** **Depends on: Task 23.4 Output by Agent_DocGen.**
1. Detect pages with missing citations, bad paths, or invalid line ranges.
2. Distinguish hard failures from warnings by profile.
3. Add regression tests for broken citation examples.

## Phase 24: LLM Page Composer and Qoder-style Markdown Articles

**Manager Status:** `Planned`
**Objective:** Upgrade page generation from template/index output to readable LLM-composed articles grounded in evidence.

### Task 24.1 – Page prompt contract and prompt fragments - Agent_DocGen
**Objective:** Define page prompt templates by topic type.
**Output:** Prompt fragments for overview, service, API, data, entity, ops, and development pages.
**Guidance:** **Depends on: Task 23.5 and Task 21.4.**
1. Include evidence, citation requirements, heading contract, and style constraints.
2. Add prompt snapshot tests.
3. Ensure prompts redact secrets and avoid local absolute path leakage unless configured.

### Task 24.2 – Qoder-style article skeleton - Agent_DocGen
**Objective:** Define stable article structure with TOC and rich headings.
**Output:** Article skeleton including 目录、简介、项目结构、核心组件、架构总览、详细分析、依赖、性能、排障、结论、附录.
**Guidance:** **Depends on: Task 24.1.**
1. Apply skeletons by page type without forcing irrelevant sections.
2. Ensure each generated page has TOC and stable heading anchors.
3. Add heading snapshot tests.

### Task 24.3 – LLM page composer pipeline - Agent_DocGen
**Objective:** Compose Markdown from page plan, evidence, retrieval context, and LLM response.
**Output:** Page composer pipeline with mock LLM tests.
**Guidance:** **Depends on: Task 24.2, Task 23.4, and Task 21.2 Output by Agent_PlatformCore.**
1. Use mock provider in CI.
2. Preserve citations through LLM output normalization.
3. Support optional real-provider smoke testing.

### Task 24.4 – Mermaid diagram planner and renderer - Agent_DocGen
**Objective:** Generate appropriate diagrams for architecture, flow, sequence, ER, and graph pages.
**Output:** Diagram planner, Mermaid renderer, syntax tests, source mapping.
**Guidance:** **Depends on: Task 24.3 and Task 23.4.**
1. Choose diagram type from page topic and available evidence.
2. Validate Mermaid syntax before writing pages.
3. Link diagrams to source evidence.

### Task 24.5 – Quality guardrails for hallucination and generic prose - Agent_AdapterGovernance
**Objective:** Reject ungrounded, generic, or low-density pages.
**Output:** Guardrails for unsupported claims, generic prose, list-dump ratio, and citation density.
**Guidance:** **Depends on: Task 24.4 Output by Agent_DocGen.**
1. Detect assertions without citations where required.
2. Detect repeated filler and template-like prose.
3. Add bad-sample and good-sample tests.

### Task 24.6 – Page composer incremental cache - Agent_IndexGraph
**Objective:** Cache page composition by inputs and record cost.
**Output:** Page input/output hash, LLM cost records, cache hit behavior.
**Guidance:** **Depends on: Task 24.5 and Task 12.4.**
1. Compute page-level input hashes from plan, evidence, prompt, and provider config.
2. Avoid repeated LLM calls for unchanged pages.
3. Record cost and token estimates per generated page.

## Phase 25: API Reference Specialization

**Manager Status:** `Planned`
**Objective:** Convert API documentation from endpoint dump into service-family, authentication, error convention, and call-flow articles.

### Task 25.1 – API inventory enrichment - Agent_Scanner
**Objective:** Enrich API inventory with service, handler, auth, request, and response metadata.
**Output:** Java/Python/TypeScript API extraction improvements and fixtures.
**Guidance:** **Depends on: Task 24.6.**
1. Extract controller/router/handler locations and service ownership.
2. Infer auth and error handling sources when available.
3. Add multilingual fixture coverage.

### Task 25.2 – API topic planner - Agent_DocGen
**Objective:** Plan API-specific Wiki pages.
**Output:** API reference, core service API, Python service API, auth API, and error handling page plan.
**Guidance:** **Depends on: Task 25.1 Output by Agent_Scanner and Task 22.6.**
1. Generate at least 15 AI_API_Atlas API planned pages.
2. Group by service family and topic instead of dumping all endpoints.
3. Preserve links to detailed endpoint evidence.

### Task 25.3 – Service-family API composer - Agent_DocGen
**Objective:** Generate service-family API articles.
**Output:** API articles with prose-first explanation and bounded endpoint tables.
**Guidance:** **Depends on: Task 25.2 and Task 24.3.**
1. Explain service purpose, core flows, and representative endpoints.
2. Limit raw endpoint table dominance.
3. Include citations for handlers and schemas.

### Task 25.4 – Auth and error convention generator - Agent_DocGen
**Objective:** Generate authentication, authorization, error code, and status code pages.
**Output:** Auth/error convention articles grounded in config and frontend/backend call sites.
**Guidance:** **Depends on: Task 25.3.**
1. Cite configuration, middleware, controller, and client files.
2. Explain common request patterns and failure modes.
3. Add tests for missing-auth and missing-error evidence behavior.

### Task 25.5 – API flow diagram generation - Agent_DocGen
**Objective:** Generate sequence diagrams for core API flows.
**Output:** Mermaid sequence diagrams for key service families.
**Guidance:** **Depends on: Task 25.4 and Task 24.4.**
1. Generate at least one sequence diagram per core API service family.
2. Cite handlers and downstream calls used in diagrams.
3. Validate diagrams before writing pages.

### Task 25.6 – API quality verifier - Agent_AdapterGovernance
**Objective:** Enforce API aggregation quality.
**Output:** API quality gate detecting endpoint dumps and missing grouping/citations.
**Guidance:** **Depends on: Task 25.5 Output by Agent_DocGen.**
1. Fail endpoint-dump regressions in qoder-like strict profile.
2. Check service family grouping, auth/error coverage, and citation coverage.
3. Add regression tests.

## Phase 26: Data Model and Database Architecture Specialization

**Manager Status:** `Planned`
**Objective:** Convert data-model documentation from model dumps into core entity, service model, database architecture, and migration strategy articles.

### Task 26.1 – Entity deduplication and canonical model resolver - Agent_Scanner
**Objective:** Resolve Java entities, DTOs, TypeScript types, and SQL tables into canonical models.
**Output:** Deduplication rules and canonical entity resolver.
**Guidance:** **Depends on: Task 24.6.**
1. Distinguish core entities, DTOs, request/response types, and duplicated projections.
2. Prevent duplicated DTOs from dominating data-model pages.
3. Add high-count model fixtures.

### Task 26.2 – Database migration and table extractor - Agent_Scanner
**Objective:** Extract database schema and migration facts.
**Output:** SQL migration table/index/FK/JSONB extractor with fixtures.
**Guidance:** **Depends on: Task 26.1.**
1. Parse table, index, foreign key, and selected column metadata.
2. Detect migration ordering and storage patterns.
3. Add PostgreSQL migration fixture tests.

### Task 26.3 – Data-model topic planner - Agent_DocGen
**Objective:** Plan data-model Wiki pages by entity and service.
**Output:** Core model, service model, database architecture, migration strategy, and entity detail page plan.
**Guidance:** **Depends on: Task 26.2 Output by Agent_Scanner and Task 22.6.**
1. Generate at least 30 AI_API_Atlas data-model planned pages.
2. Avoid page plans that mirror raw model counts.
3. Preserve drill-down links for important entities.

### Task 26.4 – Entity relationship composer - Agent_DocGen
**Objective:** Generate entity relationship articles with ER diagrams.
**Output:** Entity pages with ER diagrams, field explanation, and citations.
**Guidance:** **Depends on: Task 26.3 and Task 24.4.**
1. Explain entity role, storage, relationships, and lifecycle.
2. Render ER diagrams where relationship evidence exists.
3. Cite entity, migration, and service references.

### Task 26.5 – Service data-model composer - Agent_DocGen
**Objective:** Generate service-level data-model articles.
**Output:** Service model pages that summarize key entities, DTOs, persistence, and flows.
**Guidance:** **Depends on: Task 26.4.**
1. Group models by service ownership and runtime role.
2. Keep raw model lists secondary to explanation.
3. Include source citations and related API links.

### Task 26.6 – Data-model quality verifier - Agent_AdapterGovernance
**Objective:** Enforce data-model aggregation quality.
**Output:** Gate checks for deduplication, ER coverage, migration citations, and dump detection.
**Guidance:** **Depends on: Task 26.5 Output by Agent_DocGen.**
1. Detect high-volume raw model dump pages.
2. Require ER/migration/source evidence where applicable.
3. Add regression tests using current `05-data-model.md`-style bad output.

## Phase 27: Qoder-compatible Output Layout and IDE Runtime

**Manager Status:** `Planned`
**Objective:** Align generated artifact layout and IDE behavior with Qoder-like usage while keeping output isolated.

### Task 27.1 – Qoder-like output profile - Agent_PlatformCore
**Objective:** Add isolated qoder-like generation profile.
**Output:** `repo-wiki generate --profile qoder-like --output .repo-agent-eval`.
**Guidance:** **Depends on: Task 24.6, Task 25.6, and Task 26.6.**
1. Default qoder-like output to `.repo-agent-eval/<run>`.
2. Never write target `docs`, `.qoder`, or `.repo-wiki` unless explicitly configured.
3. Add CLI smoke tests.

### Task 27.2 – Content layout writer - Agent_DocGen
**Objective:** Write generated pages into a Chinese `content/**` tree.
**Output:** `.repo-agent-eval/<run>/content/**` writer using the planner tree.
**Guidance:** **Depends on: Task 27.1 and Task 22.6 Output by Agent_IndexGraph.**
1. Preserve taxonomy hierarchy and stable slugs.
2. Write only pages selected by the manifest plan.
3. Add layout fixture tests.

### Task 27.3 – Manifest navigation tree and commit metadata - Agent_IndexGraph
**Objective:** Write manifest navigation and git freshness metadata.
**Output:** Manifest with `navigation_tree`, `wiki_git_commit`, `target_git_commit`, and page registry.
**Guidance:** **Depends on: Task 27.2 and Task 12.2.**
1. Record content root, runtime root, profile, and page registry.
2. Detect current git commit and fallback hashes.
3. Add stale-detection tests.

### Task 27.4 – VS Code extension nav-tree integration - Agent_PlatformCore
**Objective:** Make the extension read manifest navigation instead of guessing paths.
**Output:** Extension nav tree based on manifest nodes.
**Guidance:** **Depends on: Task 27.3 Output by Agent_IndexGraph and Task 19.2.**
1. Read latest or selected eval run manifest.
2. Render Chinese Qoder-like tree in the left sidebar.
3. Add extension compile and command tests where practical.

### Task 27.5 – Markdown preview and stale wiki UX - Agent_PlatformCore
**Objective:** Open selected Wiki pages in Markdown preview and show stale prompts.
**Output:** Preview command and git freshness prompt.
**Guidance:** **Depends on: Task 27.4.**
1. Click tree nodes to open Markdown preview.
2. Compare current git id with manifest git id.
3. Show update/sync actions when stale.
4. Package VSIX successfully.

### Task 27.6 – Static viewer parity pass - Agent_PlatformCore
**Objective:** Make the static viewer consume the same manifest tree.
**Output:** Viewer/extension navigation parity and tests.
**Guidance:** **Depends on: Task 27.5 and Task 19.1.**
1. Use one nav-tree contract for IDE and static viewer.
2. Validate both surfaces show the same content hierarchy.
3. Add parity regression tests.

## Phase 28: Generation Orchestration, Cost Control, and Incremental Update

**Manager Status:** `Planned`
**Objective:** Make full generation resumable, budget-aware, rate-limited, and incremental.

### Task 28.1 – Generation run state machine - Agent_IndexGraph
**Objective:** Persist generation run and page state.
**Output:** Pending/running/completed/failed/retryable state machine.
**Guidance:** **Depends on: Task 27.6.**
1. Store run and page states in SQLite.
2. Resume interrupted runs without regenerating completed pages.
3. Add failure and resume tests.

### Task 28.2 – LLM cost estimator and budget gate - Agent_PlatformCore
**Objective:** Estimate generation cost and enforce budget.
**Output:** Token/cost estimator and budget gate.
**Guidance:** **Depends on: Task 28.1 Output by Agent_IndexGraph and Task 21.4.**
1. Estimate cost from page plan, prompt size, and provider pricing config.
2. Block over-budget runs unless explicitly overridden.
3. Add budget tests.

### Task 28.3 – Concurrent generation scheduler - Agent_PlatformCore
**Objective:** Add configurable concurrency and provider rate limiting.
**Output:** Scheduler with concurrency, rate limit, retry, and cancellation behavior.
**Guidance:** **Depends on: Task 28.2.**
1. Respect provider limits and retry policy.
2. Keep SQLite state consistent under concurrent generation.
3. Add concurrency and rate-limit tests.

### Task 28.4 – Page-level invalidation from git diff and hash fallback - Agent_IndexGraph
**Objective:** Regenerate only impacted pages.
**Output:** Git-diff and hash-fallback page invalidation.
**Guidance:** **Depends on: Task 28.3 and Task 12.4.**
1. Map changed files to evidence spans and pages.
2. Use hash fallback when git is unavailable.
3. Prove changing one service only invalidates related pages.

### Task 28.5 – Failure recovery and partial evidence bundle - Agent_QualityRelease
**Objective:** Make partial runs diagnosable and recoverable.
**Output:** Failed page records, retry commands, partial manifests, evidence bundle.
**Guidance:** **Depends on: Task 28.4.**
1. Keep successful pages usable when some pages fail.
2. Record failure reason, provider error, and retry command.
3. Add tests for partial generation acceptance behavior.

### Task 28.6 – update integration for qoder-like profile - Agent_PlatformCore
**Objective:** Wire incremental update into the qoder-like profile.
**Output:** `repo-wiki update --profile qoder-like`.
**Guidance:** **Depends on: Task 28.5 Output by Agent_QualityRelease.**
1. Reuse planner, invalidation, scheduler, and manifest update paths.
2. Keep output isolated under `.repo-agent-eval`.
3. Add CLI smoke and targeted update tests.

## Phase 29: Quality Governance and Qoder Parity Benchmark

**Manager Status:** `Planned`
**Objective:** Make qoder parity measurable with strict profile gates and trustworthy comparison outputs.

### Task 29.1 – Qoder parity metric schema - Agent_QualityRelease
**Objective:** Define metric schema for structural and content parity.
**Output:** Metrics for page coverage, depth, citations, file refs, TOC, Mermaid, prose/list ratio, API/data-model aggregation.
**Guidance:** **Depends on: Task 28.6.**
1. Define metric units, thresholds, and severity levels.
2. Add schema and serialization tests.
3. Keep metrics independent from proprietary qoder internals.

### Task 29.2 – Comparator path-model repair - Agent_QualityRelease
**Objective:** Compare Qoder `content/**` with repo-agent `content/**`.
**Output:** Path-model repair and comparison tests.
**Guidance:** **Depends on: Task 29.1.**
1. Remove assumptions tied to `docs/sections`.
2. Support `.qoder/repowiki/zh` and `.repo-agent-eval/<run>/content`.
3. Ensure AI_API_Atlas comparisons do not emit false `docs/docs` gaps.

### Task 29.3 – Strict verifier for qoder-like profile - Agent_AdapterGovernance
**Objective:** Add strict qoder-like verification mode.
**Output:** `verify --profile qoder-like --ci` with TOC, cite, dump, and file-link gates.
**Guidance:** **Depends on: Task 29.2 Output by Agent_QualityRelease and Task 24.5.**
1. Fail missing citations, missing TOC, dump pages, and broken file references.
2. Keep strict vs pilot thresholds explicit.
3. Add regression tests.

### Task 29.4 – Golden fixture suite - Agent_QualityRelease
**Objective:** Build stable CI fixtures independent from real LLM keys.
**Output:** Java/Python/TypeScript/SQL fixtures and expected Wiki tree.
**Guidance:** **Depends on: Task 29.3.**
1. Use mock LLM outputs where generation is required.
2. Cover planner, evidence, composer, verifier, and comparator.
3. Make fixtures small enough for CI.

### Task 29.5 – AI_API_Atlas qoder parity rerun - Agent_QualityRelease
**Objective:** Run an isolated AI_API_Atlas parity evaluation.
**Output:** Latest `.repo-agent-eval/<run>` output, comparison report, gap matrix.
**Guidance:** **Depends on: Task 29.4.**
1. Do not modify `.qoder` or `.repo-wiki`.
2. Compare against `/Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas/.qoder/repowiki/zh`.
3. Report page count, citations, TOC, Mermaid, prose density, and specialization scores.

### Task 29.6 – Regression dashboard and trend persistence - Agent_IndexGraph
**Objective:** Persist quality metrics and export trend dashboard.
**Output:** SQLite trend records and dashboard export.
**Guidance:** **Depends on: Task 29.5 Output by Agent_QualityRelease and Task 12.3.**
1. Store multiple run metrics and deltas.
2. Export dashboard artifacts for Manager review.
3. Add trend query tests.

## Phase 30: Replacement Candidate Release and Documentation

**Manager Status:** `Planned`
**Objective:** Package a configurable Qoder replacement candidate and provide evidence-based go/no-go.

### Task 30.1 – End-user configuration documentation - Agent_QualityRelease
**Objective:** Document LLM provider setup for users.
**Output:** Minimax, OpenAI-compatible, Anthropic-compatible, and local provider configuration docs.
**Guidance:** **Depends on: Task 29.6 and Task 21.5.**
1. Show env/yaml examples without real secrets.
2. Explain mock vs real provider behavior.
3. Include troubleshooting for common config failures.

### Task 30.2 – Installation and VS Code extension workflow - Agent_PlatformCore
**Objective:** Document and validate CLI and VSIX workflows.
**Output:** CLI install, VSIX install, generate, view, update, and verify workflow docs.
**Guidance:** **Depends on: Task 30.1 and Task 27.5.**
1. Validate from a clean environment where practical.
2. Include extension rebuild/reinstall instructions.
3. Add packaging smoke evidence.

### Task 30.3 – AI_API_Atlas full replacement pilot - Agent_QualityRelease
**Objective:** Run a full AI_API_Atlas replacement pilot in isolated output.
**Output:** `.repo-agent-eval/<run>` full output and manual acceptance package.
**Guidance:** **Depends on: Task 30.2 and Task 29.5.**
1. Use qoder-like profile and configured provider.
2. Do not modify `.qoder`, `.repo-wiki`, or target `docs`.
3. Produce human-readable acceptance instructions.

### Task 30.4 – Multi-repository replacement pilot - Agent_QualityRelease
**Objective:** Validate replacement behavior across repository types.
**Output:** At least three repository pilot reports.
**Guidance:** **Depends on: Task 30.3.**
1. Cover different language and size profiles.
2. Record generation cost, runtime, quality scores, and failures.
3. Identify repo classes that remain unsupported.

### Task 30.5 – Release gate and rollback plan - Agent_AdapterGovernance
**Objective:** Define production replacement gate and rollback behavior.
**Output:** Release gate policy, rollback plan, failure handling.
**Guidance:** **Depends on: Task 30.4.**
1. Do not allow production-replacement claims unless strict gates pass.
2. Define rollback when generated docs are stale or low quality.
3. Include CI and operator failure modes.

### Task 30.6 – Final go/no-go dossier - Agent_QualityRelease
**Objective:** Produce the final replacement decision package.
**Output:** Final decision report, evidence index, remaining gaps, and next backlog.
**Guidance:** **Depends on: Task 30.5.**
1. State whether repo-agent can replace Qoder Repo Wiki for target usage.
2. Separate AI_API_Atlas-specific outcome from general product readiness.
3. Link every claim to generated evidence.
4. Update Memory Root with final Phase 30 judgment.

## Phase 31: Strict Gate Closure and Freshness Reliability

**Manager Status:** `Planned`
**Objective:** Make the latest AI_API_Atlas Minimax run pass strict qoder-like verification before expanding replacement scope.

### Task 31.1 – Commit freshness preflight - Agent_IndexGraph
**Objective:** Record and verify target repository freshness around qoder-like generation.
**Output:** Target HEAD and dirty-state metadata in manifest plus stale-run strict gate behavior.
**Guidance:** **Depends on: Task 30.6 and Task 27.3.**
1. Record target repository HEAD and dirty state before generation starts.
2. Re-check target HEAD after generation completes.
3. In strict mode, require a clean target worktree by default and emit `QODER_STALE_GIT_COMMIT` for stale generation metadata.
4. If dirty runs are allowed for manual review, mark `target_dirty=true` and force comparison output to `NOT_READY`.
5. Add stale commit and dirty tree regression tests.

### Task 31.2 – Dump page retry policy - Agent_DocGen
**Objective:** Retry pages that fail dump-page quality gates instead of accepting list-dominant output.
**Output:** Dump-page repair queue and rewrite prompt policy.
**Guidance:** **Depends on: Task 31.1 and Task 24.5.**
1. Route `QODER_PAGE_DUMP` failures into a second-pass LLM rewrite queue.
2. Require service responsibility, flow, risk, and source-evidence prose sections in rewrite prompts.
3. Preserve valid citations while replacing list-dominant body content.
4. Emit page-level retry status and terminal failure reasons.

### Task 31.3 – Prose density repair - Agent_DocGen
**Objective:** Repair pages that fail qoder-like prose density checks.
**Output:** Prose-density repair classifier, retry workflow, and failure reporting.
**Guidance:** **Depends on: Task 31.2.**
1. Detect `QODER_PROSE_TOO_LOW` pages after initial composition.
2. Add targeted prose repair prompts that convert template/list output into grounded narrative.
3. Report failed pages, reasons, and suggested retry commands when repair is exhausted.
4. Add tests for low-prose detection and successful repair.

### Task 31.4 – Strict gate rerun package - Agent_QualityRelease
**Objective:** Produce a fresh AI_API_Atlas qoder-like run package that can clear strict verification.
**Output:** Latest isolated run, strict report, comparison report, and manual review index.
**Guidance:** **Depends on: Task 31.3.**
1. Generate under `/Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas/.repo-agent-eval/<run>` only.
2. Verify `.qoder/**` remains read-only and unmodified.
3. Run `repo-wiki verify --profile qoder-like --ci`.
4. Require `QODER_STALE_GIT_COMMIT`, `QODER_PAGE_DUMP`, and `QODER_PROSE_TOO_LOW` reason codes to be zero before declaring readiness.
5. Produce a manual review index for remaining human inspection.

## Phase 32: Qoder-style Information Architecture Deepening

**Manager Status:** `Planned`
**Objective:** Deepen generated Wiki hierarchy so repo-agent matches Qoder-style topic decomposition instead of service-level aggregation only.

### Task 32.1 – Qoder baseline topic mining - Agent_QualityRelease
**Objective:** Mine Qoder baseline directory patterns without copying Qoder content.
**Output:** Generalized topic taxonomy and path-pattern report.
**Guidance:** **Depends on: Task 31.4 and Task 29.2.**
1. Read `/Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas/.qoder/repowiki/zh/content` as a read-only baseline.
2. Extract reusable topic, depth, and directory-shape patterns.
3. Avoid copying proprietary page prose or implementation detail.
4. Report target common-path improvements and gaps.

### Task 32.2 – Service subtopic planner - Agent_DocGen
**Objective:** Generate service subtopic plans instead of one page per service.
**Output:** Service overview, architecture, API, deployment, and component subtopic plan.
**Guidance:** **Depends on: Task 32.1 and Task 22.6.**
1. Plan `服务概述`, `架构设计`, `API接口文档`, `部署配置`, and `核心组件` pages for Python services.
2. Generate business subdomain pages for core services when evidence supports them.
3. Preserve stable slugs and manifest navigation ordering.
4. Add planner tests for service subtopic expansion.

### Task 32.3 – Data-model entity topic planner - Agent_DocGen
**Objective:** Split data-model documentation into entity and persistence topics while eliminating duplicate pages.
**Output:** Data-model topic plan for core entities, migrations, tables, indexes, audit, and security.
**Guidance:** **Depends on: Task 32.2 and Task 26.3.**
1. Generate entity, migration, table-structure, index-performance, audit, and security data-model topics.
2. Eliminate duplicate pages such as `xxx 数据模型` and `xxx 数据模型-2`.
3. Keep entity drill-down links connected to service-level pages.
4. Add duplicate-topic regression tests.

### Task 32.4 – Project overview module hierarchy - Agent_DocGen
**Objective:** Generate a Qoder-depth project overview and module organization hierarchy.
**Output:** `项目概述/模块组织结构/<服务>/<子组件>/...` hierarchy and navigation metadata.
**Guidance:** **Depends on: Task 32.3.**
1. Target directory depth of `4` with non-empty topic pages.
2. Increase Qoder path common count from the current baseline toward at least `80`.
3. Keep repo-agent page count within `90%-120%` of Qoder page count.
4. Add hierarchy fixture tests and AI_API_Atlas path comparison evidence.

## Phase 33: Evidence Ranking and Hallucination Control

**Manager Status:** `Planned`
**Objective:** Prevent page topics from binding to unrelated source evidence and make low-confidence content explicit.

### Task 33.1 – Service ownership resolver - Agent_Scanner
**Objective:** Resolve service ownership from repository structure, package metadata, runtime signals, and docs.
**Output:** Service ownership resolver with confidence scoring and tests.
**Guidance:** **Depends on: Task 32.4 and Task 23.3.**
1. Use module paths, package names, ports, build files, and README cues to determine service ownership.
2. Prevent GitLab, Jenkins, and MCP pages from binding unrelated `ai-service` evidence.
3. Emit confidence and rejection reasons for ambiguous ownership.
4. Add fixtures covering similarly named services and unrelated evidence.

### Task 33.2 – Page evidence scoring - Agent_IndexGraph
**Objective:** Score evidence by page title, service slug, domain, runtime role, API relation, and data-model relation.
**Output:** Page evidence score model with top-N selections and rejection reasons.
**Guidance:** **Depends on: Task 33.1 Output by Agent_Scanner and Task 23.3.**
1. Combine title, slug, domain, runtime role, API, and data-model features into a relevance score.
2. Store top-N evidence and rejected candidates with reasons.
3. Prefer service-local evidence over generic shared modules unless the page topic requires shared infrastructure.
4. Add tests for positive matches and false-positive rejection.

### Task 33.3 – Citation relevance verifier - Agent_AdapterGovernance
**Objective:** Add strict verification for page-title to citation relevance.
**Output:** Citation relevance WARN/FAIL gates in qoder-like strict verification.
**Guidance:** **Depends on: Task 33.2 Output by Agent_IndexGraph and Task 29.3.**
1. Compare page title, service slug, and topic type against citation file paths and symbols.
2. Fail high-confidence mismatches in strict profile.
3. Warn on ambiguous but explainable shared-infrastructure citations.
4. Add regression cases for wrong-service evidence binding.

### Task 33.4 – Low-confidence fallback - Agent_DocGen
**Objective:** Replace unsupported implementation claims with explicit low-confidence sections.
**Output:** Low-confidence fallback behavior for pages with insufficient evidence.
**Guidance:** **Depends on: Task 33.3 and Task 24.5.**
1. Generate `待确认` sections when evidence is insufficient.
2. Prohibit fabricated implementation details in low-confidence pages.
3. Ensure uncertainty text does not dominate otherwise well-evidenced pages.
4. Add tests for insufficient-evidence composition.

## Phase 34: LLM Composer Quality Loop

**Manager Status:** `Planned`
**Objective:** Convert one-shot page generation into a measurable, retryable, and cache-aware quality loop.

### Task 34.1 – Page quality classifier - Agent_AdapterGovernance
**Objective:** Classify generated pages as `PASS`, `REPAIRABLE`, or `REJECTED`.
**Output:** Page quality classifier using dump ratio, prose density, citation relevance, headings, and generic prose.
**Guidance:** **Depends on: Task 33.4 and Task 24.5.**
1. Classify each page after generation and before final manifest readiness.
2. Use dump ratio, prose density, citation relevance, heading completeness, and generic prose signals.
3. Persist classification results in the run evidence bundle.
4. Add classifier tests for pass, repairable, and rejected pages.

### Task 34.2 – Targeted repair prompts - Agent_DocGen
**Objective:** Repair failed pages with page-type-specific prompts.
**Output:** API, data-model, architecture, service, and operations repair prompts.
**Guidance:** **Depends on: Task 34.1.**
1. Provide repair prompts for API, data-model, architecture, service, and operations pages.
2. Rewrite only failed pages and preserve valid citations.
3. Track before/after quality scores for each repaired page.
4. Add mock-provider tests for targeted repair behavior.

### Task 34.3 – Cost-aware retry scheduler - Agent_PlatformCore
**Objective:** Schedule repairs with bounded retries, token budgets, and visible progress.
**Output:** Retry scheduler with max attempts, budget enforcement, failure policy, and CLI progress.
**Guidance:** **Depends on: Task 34.2 and Task 28.3.**
1. Enforce maximum repair attempts and token budget per run.
2. Record planned, `llm_done`, repairing, fallback, and failed counts in CLI progress.
3. Preserve partial usable output while marking unrepaired failures as not ready.
4. Add budget and retry-limit tests.

### Task 34.4 – Cache validity by quality hash - Agent_IndexGraph
**Objective:** Prevent stale low-quality cached pages from being reused after quality rules change.
**Output:** Cache keys that include input hash and quality profile hash.
**Guidance:** **Depends on: Task 34.3 and Task 24.6.**
1. Include quality profile hash in page composition cache keys.
2. Invalidate old low-quality cache entries when repair or verifier rules change.
3. Record repair coverage and cache reuse in manifest summaries.
4. Add cache invalidation regression tests.

## Phase 35: Replacement Candidate Acceptance

**Manager Status:** `Planned`
**Objective:** Produce the evidence-backed final decision on whether repo-agent can replace Qoder Repo Wiki for AI_API_Atlas.

### Task 35.1 – AI_API_Atlas full pilot rerun - Agent_QualityRelease
**Objective:** Run the final full AI_API_Atlas Minimax pilot after strict, IA, evidence, and repair improvements.
**Output:** Full isolated run, strict report, qoder comparison report, and review checklist.
**Guidance:** **Depends on: Task 34.4.**
1. Generate under `/Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas/.repo-agent-eval/<run>` only.
2. Verify `.qoder/**` remains read-only and unmodified.
3. Produce strict report, qoder comparison report, and manual review checklist.
4. Require fallback pages to be `<= 5%` before READY consideration.

### Task 35.2 – Manual review pack - Agent_QualityRelease
**Objective:** Build a 30-page manual review pack comparing repo-agent output to Qoder pages.
**Output:** Manual review matrix with page pairs, gap notes, and acceptance status.
**Guidance:** **Depends on: Task 35.1.**
1. Select 30 representative pages covering overview, architecture, core services, Python services, data models, API, operations, security, and troubleshooting.
2. Record the Qoder page, repo-agent page, gap summary, and acceptability for each pair.
3. Require at least 24 of 30 pages to be acceptable for replacement readiness.
4. Keep review artifacts inside the isolated evaluation output or operations evidence.

### Task 35.3 – Plugin acceptance pass - Agent_PlatformCore
**Objective:** Verify the VS Code plugin experience against latest READY and NOT_READY runs.
**Output:** Plugin acceptance evidence for navigation, preview, stale prompt, and run selection.
**Guidance:** **Depends on: Task 35.2 and Task 27.5.**
1. Validate left navigation, Markdown preview, stale prompt, and run selection.
2. Default the plugin to the latest READY run.
3. Clearly label NOT_READY runs and prevent accidental replacement claims.
4. Add extension compile/package smoke evidence.

### Task 35.4 – Go/no-go dossier - Agent_QualityRelease
**Objective:** Issue the final replacement decision dossier.
**Output:** Go/no-go dossier separating AI_API_Atlas readiness from general repository readiness.
**Guidance:** **Depends on: Task 35.3 and Task 30.6.**
1. State whether AI_API_Atlas can replace Qoder Repo Wiki with repo-agent output.
2. Separate AI_API_Atlas-specific replacement readiness from general-purpose readiness.
3. Require strict verify PASS, qoder compare READY, `.qoder/**` read-only verification, and at least 24 accepted manual review pages.
4. If not ready, return `NOT_READY` with non-zero CLI behavior or explicit failure state.
5. Update Memory Root with the final Phase 35 judgment.
