# Phase 01 – Foundation, Security, and Scanner Contracts

## Task 1.1

```markdown
---
task_ref: "Task 1.1 - CLI skeleton, config foundation, and core contracts"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_1_CLI_skeleton_config_foundation_and_core_contracts.md"
execution_type: "single-step"
dependency_context: false
ad_hoc_delegation: false
---

# APM Task Assignment: CLI skeleton, config foundation, and core contracts

## Task Reference
Implementation Plan: **Task 1.1 - CLI skeleton, config foundation, and core contracts** assigned to **Agent_PlatformCore**

## Objective
Establish the executable CLI, shared configuration model, common contracts, and baseline runtime scaffolding for the repo-wiki MVP.

## Detailed Instructions
- Complete all items in one response.
- Create or update the Python package structure for the command layer and shared core layer so later phases can extend it without reorganizing directories.
- Implement command placeholders for `init`, `index`, `update`, `verify`, `sync`, `search`, `graph`, and `cost-estimate`.
- Define typed config models matching the six MVP sections: `project`, `scan`, `index`, `llm`, `output`, and `security`.
- Implement config loading, defaults, and CLI override precedence.
- Define shared contracts for `RepositorySnapshot`, `Module`, `Endpoint`, `DataModel`, `RepositoryStats`, `VerifyResult`, and `ImpactSet`.
- Add bootstrap checks for directory readiness, dependency availability, and standardized error categories.
- Add Rich-based progress and logging primitives that later tasks can reuse.
- Add smoke tests that prove the CLI boots and parses configuration correctly.
- Keep the design aligned to `.apm/Implementation_Plan.md`; do not introduce out-of-scope commands or extra product surfaces.

## Expected Output
- Deliverables: command registry, config loader, shared models, bootstrap checks, logging baseline, smoke tests.
- Success criteria: CLI boots successfully, config schema validates, shared contracts are importable by downstream modules, and tests cover the new baseline.
- File locations: `cli/`, `core/`, `tests/`, and any repo entrypoint files needed to expose the CLI.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_1_CLI_skeleton_config_foundation_and_core_contracts.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 1.2

```markdown
---
task_ref: "Task 1.2 - Security filtering and redaction foundation"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_2_Security_filtering_and_redaction_foundation.md"
execution_type: "single-step"
dependency_context: false
ad_hoc_delegation: false
---

# APM Task Assignment: Security filtering and redaction foundation

## Task Reference
Implementation Plan: **Task 1.2 - Security filtering and redaction foundation** assigned to **Agent_PlatformCore**

## Objective
Deliver the shared security filter and redaction capabilities that all later scan, index, and generation flows must reuse.

## Detailed Instructions
- Complete all items in one response.
- Implement file-level exclusion rules for `.env*`, build artifacts, binaries, oversized files, large logs, and generated output directories.
- Implement content-level sensitive pattern detection for API keys, access tokens, private keys, database connection strings, and production domain or IP patterns.
- Implement text sanitization that replaces detected sensitive values with `[REDACTED]` before any downstream persistence or LLM use.
- Expose reusable APIs such as path filtering, text sanitization, and structured security warnings.
- Make the design importable by scanner, indexer, and generator layers without duplicate logic.
- Add tests for allowed files, denied files, safe content, and redaction cases.
- Keep output reporting free of raw secret values.

## Expected Output
- Deliverables: security filter module, redaction engine, warning/reporting API, security fixtures and tests.
- Success criteria: downstream modules can call the security APIs directly, sensitive content is redacted consistently, and tests cover both detection and pass-through behavior.
- File locations: `core/` security-related modules and `tests/` security fixtures or suites.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_2_Security_filtering_and_redaction_foundation.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 1.3

```markdown
---
task_ref: "Task 1.3 - Repository traversal, language detection, and module discovery"
agent_assignment: "Agent_Scanner"
memory_log_path: ".apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_3_Repository_traversal_language_detection_and_module_discovery.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Repository traversal, language detection, and module discovery

## Task Reference
Implementation Plan: **Task 1.3 - Repository traversal, language detection, and module discovery** assigned to **Agent_Scanner**

## Context from Dependencies
This task depends on Task 1.1 and Task 1.2 implemented by Agent_PlatformCore.

**Integration Steps (complete in one response):**
1. Read `.apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_1_CLI_skeleton_config_foundation_and_core_contracts.md` to identify the actual config, shared model, and logging files created in Task 1.1.
2. Read `.apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_2_Security_filtering_and_redaction_foundation.md` to identify the actual security filter and redaction module paths created in Task 1.2.
3. Review the implementation files referenced by those logs before writing scanner code. Reuse the shared config/contracts and security APIs instead of duplicating them.
4. If the producer tasks used a different package layout than expected, adapt to that layout rather than creating a parallel abstraction.

**Producer Output Summary:**
- Task 1.1 provides the CLI/config/runtime baseline and the shared contracts that scanner outputs must satisfy.
- Task 1.2 provides the file filtering and text sanitization APIs that must guard scanner inputs.

**Integration Requirements:**
- Scanner output must populate the shared `RepositorySnapshot` model from Task 1.1.
- File traversal must apply `.gitignore` logic and the shared security-deny rules from Task 1.2.
- All extracted text inputs must flow through the security layer before downstream use.

**User Clarification Protocol:**
If Task 1.1 or Task 1.2 has not populated its log with actual output paths or leaves missing shared contracts, stop and ask the User whether to wait for completion or revise the plan.

## Objective
Build the traversal and repository-baseline pipeline that produces the first valid `RepositorySnapshot`.

## Detailed Instructions
- Complete all items in one response.
- Implement repository traversal with `.gitignore`, explicit excludes, and security-deny rules.
- Detect repository language, framework, package manager, and common engineering files.
- Extract standard project commands: `start`, `build`, `test`, and `lint`.
- Implement module discovery heuristics for TS/JS, Python, and Go exactly as scoped by the implementation plan.
- Populate repository-level and module-level sections of `RepositorySnapshot`.
- Add repository stats and consistency checks.
- Add representative tests or fixtures for backend repositories and edge cases.

## Expected Output
- Deliverables: traverser, language detector, module discovery logic, command extraction logic, repository stats support, tests.
- Success criteria: scanner can produce a valid baseline snapshot on representative repositories and consumes the shared security/config foundations instead of redefining them.
- File locations: `scanner/`, shared model integration points, and `tests/` fixtures covering traversal and discovery.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_3_Repository_traversal_language_detection_and_module_discovery.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 1.4

```markdown
---
task_ref: "Task 1.4 - Ownership, dependency, API, and data-model extraction"
agent_assignment: "Agent_Scanner"
memory_log_path: ".apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_4_Ownership_dependency_API_and_data_model_extraction.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Ownership, dependency, API, and data-model extraction

## Task Reference
Implementation Plan: **Task 1.4 - Ownership, dependency, API, and data-model extraction** assigned to **Agent_Scanner**

## Context from Dependencies
Build directly on your Task 1.3 scanner baseline.

- Read `.apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_3_Repository_traversal_language_detection_and_module_discovery.md` and reuse the snapshot structure, file traversal conventions, and module discovery logic already implemented.
- Extend the same scanner pipeline; do not fork extraction logic into a disconnected subsystem.
- Keep all new extraction outputs normalized into the existing `RepositorySnapshot`.

## Objective
Complete the MVP extraction set and guarantee that required module fields have a defined source.

## Detailed Instructions
- Complete all items in one response.
- Implement module-level dependency extraction for `depends_on` and `depended_by`.
- Implement REST extraction for NestJS, Express, Fastify, FastAPI, Flask, Gin, Fiber, and simple `net/http` handlers. Treat Django URL mapping as optional only.
- Implement data-model extraction for ORM models, DTO/schema definitions, and migration-derived table summaries.
- Implement ownership extraction from `CODEOWNERS` with deterministic `unknown` fallback.
- Implement first-pass module responsibility summarization from module path, exports, endpoints, models, and README cues.
- Normalize all extracted entities into the existing snapshot contracts.
- Add fixture coverage and fallback logging for uncertain patterns.

## Expected Output
- Deliverables: dependency extraction, endpoint extraction, data model extraction, ownership mapping, responsibility summarization, normalization tests.
- Success criteria: required module fields now have a deterministic source and the snapshot can feed source-of-truth generation without schema gaps.
- File locations: `scanner/` extractors, any normalization helpers, and `tests/` fixtures for route/model/ownership patterns.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_4_Ownership_dependency_API_and_data_model_extraction.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 1.5

```markdown
---
task_ref: "Task 1.5 - Source-of-truth artifact writer and schema validation"
agent_assignment: "Agent_Scanner"
memory_log_path: ".apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_5_Source_of_truth_artifact_writer_and_schema_validation.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Source-of-truth artifact writer and schema validation

## Task Reference
Implementation Plan: **Task 1.5 - Source-of-truth artifact writer and schema validation** assigned to **Agent_Scanner**

## Context from Dependencies
Build directly on your Task 1.4 extraction work.

- Read `.apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_4_Ownership_dependency_API_and_data_model_extraction.md` and reuse the normalized snapshot, responsibility fallback rules, ownership handling, and extraction outputs already implemented.
- Keep `module-index.yaml` schema-valid immediately after scan. Do not defer required fields to later LLM work.
- Preserve deterministic ordering and naming so later phases can rely on stable artifact diffs.

## Objective
Write schema-valid MVP artifacts immediately after scan, without relying on later phases to repair required fields.

## Detailed Instructions
- Complete all items in one response.
- Implement serializers for `repo-map.yaml`, `module-index.yaml`, `api-index.yaml`, and `data-models.yaml`.
- Ensure `module-index.yaml` includes all required fields, especially `responsibility`, `owner`, and `doc_path`.
- Generate a schema-valid scaffold for `task-catalog.yaml`.
- Create placeholder content for `prompt-fragments/overview.txt` and `prompt-fragments/architecture.txt`.
- Add schema validation and fail-fast behavior for invalid artifact writes.
- Add deterministic formatting and ordering.
- Add end-to-end tests from scan output to written artifacts.

## Expected Output
- Deliverables: source-of-truth writers, schema validators, deterministic formatting behavior, end-to-end artifact tests.
- Success criteria: scanner output can be persisted as valid MVP artifacts with no missing required fields and stable diffs across identical runs.
- File locations: `scanner/` or shared writer modules, `ai/source-of-truth/` generation paths, and corresponding tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_5_Source_of_truth_artifact_writer_and_schema_validation.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```
