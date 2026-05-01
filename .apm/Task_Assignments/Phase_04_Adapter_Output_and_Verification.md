# Phase 04 – Adapter Output and Verification

## Task 4.1

```markdown
---
task_ref: "Task 4.1 - Multi-tool adapter generation and sync command"
agent_assignment: "Agent_AdapterGovernance"
memory_log_path: ".apm/Memory/Phase_04_Adapter_Output_and_Verification/Task_4_1_Multi_tool_adapter_generation_and_sync_command.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Multi-tool adapter generation and sync command

## Task Reference
Implementation Plan: **Task 4.1 - Multi-tool adapter generation and sync command** assigned to **Agent_AdapterGovernance**

## Context from Dependencies
This task depends on Task 3.2 implemented by Agent_DocGen.

**Integration Steps (complete in one response):**
1. Read `.apm/Memory/Phase_03_Documentation_Generation_and_Command_Orchestration/Task_3_2_Generation_engine_cache_and_token_budgeted_context_builder.md` to identify the actual doc generation outputs and prompt fragment paths available to the adapter layer.
2. Review the files referenced in that log before implementing adapter rendering.
3. Keep adapter files minimal and navigational. Do not duplicate project knowledge already produced in docs and source-of-truth outputs.

**Producer Output Summary:**
- Task 3.2 provides the generated docs, prompt fragments, and output contracts that adapters must point to.

**Integration Requirements:**
- Generate `.claude/`, `AGENTS.md`, `.opencode/`, and `.codex/` outputs against real generated file paths.
- Keep adapter content stable and path-valid.
- Implement `sync` as standalone adapter regeneration.

**User Clarification Protocol:**
If generated docs or source-of-truth paths are incomplete or unstable, stop and ask whether upstream generation should be corrected first.

## Objective
Generate AI-tool adapter artifacts that point to the knowledge base without duplicating it.

## Detailed Instructions
- Complete all items in one response.
- Generate `.claude/CLAUDE.md`, `.claude/settings.json`, and fixed template skills under `.claude/skills/`.
- Generate `AGENTS.md`, `.opencode/opencode.json`, and mirrored fixed template skills under `.agents/skills/`.
- Generate `.codex/config.toml` and `.codex/hooks.json`.
- Validate that all adapter references resolve to real generated paths.
- Implement `sync` behavior for standalone adapter regeneration.
- Add validation coverage for readability, path integrity, and minimalism.

## Expected Output
- Deliverables: adapter renderers, sync behavior, path validation, tests.
- Success criteria: all supported AI tool entry files exist, reference the correct knowledge files, and avoid duplicating large knowledge blocks.
- File locations: `adapter/`, adapter output paths under repo root, and related tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_04_Adapter_Output_and_Verification/Task_4_1_Multi_tool_adapter_generation_and_sync_command.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 4.2

```markdown
---
task_ref: "Task 4.2 - Verify command and CI-mode governance checks"
agent_assignment: "Agent_AdapterGovernance"
memory_log_path: ".apm/Memory/Phase_04_Adapter_Output_and_Verification/Task_4_2_Verify_command_and_CI_mode_governance_checks.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Verify command and CI-mode governance checks

## Task Reference
Implementation Plan: **Task 4.2 - Verify command and CI-mode governance checks** assigned to **Agent_AdapterGovernance**

## Context from Dependencies
This task depends on Task 4.1 and Task 1.5.

**Integration Steps (complete in one response):**
1. Read `.apm/Memory/Phase_04_Adapter_Output_and_Verification/Task_4_1_Multi_tool_adapter_generation_and_sync_command.md` to identify the actual adapter outputs and path validation logic created in Task 4.1.
2. Read `.apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_5_Source_of_truth_artifact_writer_and_schema_validation.md` to identify the exact source-of-truth artifact set and schema guarantees produced in Phase 1.
3. Review the files referenced in both logs before implementing verify checks.
4. Keep verify scope limited to the six frozen checks in the implementation plan.

**Producer Output Summary:**
- Task 4.1 provides adapter outputs and path references.
- Task 1.5 provides the source-of-truth artifact set and schema contract that verify must enforce.

**Integration Requirements:**
- Verify must check required files, module doc coverage, cross references, dangling model references, stale docs, and adapter path validity.
- `--ci` output must be machine-readable and return non-zero on FAIL.

**User Clarification Protocol:**
If the artifact set or adapter outputs do not match the frozen contract, stop and ask whether the plan should be updated or the upstream task refined.

## Objective
Implement the frozen MVP verification contract with PASS, WARN, and FAIL grading.

## Detailed Instructions
- Complete all items in one response.
- Implement the six verify checks from the plan exactly.
- Add stale-doc detection based on timestamps and git-aware change detection.
- Implement `--ci` JSON output and non-zero exit behavior on FAIL.
- Add fixture-based tests that exercise PASS, WARN, and FAIL outcomes.

## Expected Output
- Deliverables: verify command implementation, CI output mode, fixture-based governance tests.
- Success criteria: verify covers only the frozen MVP checks, produces stable machine-readable output, and catches missing or stale knowledge artifacts correctly.
- File locations: `verifier/`, CLI integration points, and tests for verify behavior.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_04_Adapter_Output_and_Verification/Task_4_2_Verify_command_and_CI_mode_governance_checks.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```
