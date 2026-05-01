# Phase 09 – Output Contract and Navigation Hardening

## Task 9.1

```markdown
---
task_ref: "Task 9.1 - Target-output boundary and governance-layer separation"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_1_Target_output_boundary_and_governance_layer_separation.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Target-output boundary and governance-layer separation

## Task Reference
Implementation Plan: **Task 9.1 - Target-output boundary and governance-layer separation** assigned to **Agent_DocGen**

## Context from Dependencies
This task depends on Task 6.1 implemented by Agent_DocGen and Task 8.3 implemented by Agent_QualityRelease.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_09_Output_Contract_and_Navigation_Hardening.md` to understand the phase goal and boundary-fix scope.
2. Read `docs/repo-wiki-phase-06-08-review.md` and `docs/repo-wiki-phase-09-12-roadmap.md` to ground this task in the verified review conclusions.
3. Read `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_1_Document_output_contract_refactor_and_document_center_layer.md` to identify the current document-layer contract model.
4. Read `.apm/Memory/Phase_08_Quality_Gates_and_Qoder_Baseline_Regression/Task_8_3_AI_API_Atlas_regeneration_acceptance_and_readiness_report.md` and `docs/operations/AI_API_Atlas_Readiness_Report.md` to understand how current outputs behave on the fixed target repository.
5. Review the implementation files referenced in those logs before changing output-layer ownership.

**Producer Output Summary:**
- Task 6.1 introduced overview/section/module/phase layering, but review found that governance-layer material and target-repository output are still mixed.
- Task 8.3 confirmed the current acceptance target still exposes unresolved output-boundary ambiguity.

**Integration Requirements:**
- Separate repo-agent internal governance docs from generated target-repository knowledge outputs.
- Make output-layer ownership deterministic and explicit for future generation tasks.
- Preserve historical Phase 06-08 artifacts; do not delete or rewrite prior manager materials.

**User Clarification Protocol:**
If existing consumers depend on phase-layer docs being generated into target repositories and that dependency cannot be inferred from current artifacts, stop and ask whether Phase 09 should preserve an optional compatibility mode.

## Objective
Separate repo-agent's internal governance docs from target repository knowledge outputs and make document-layer ownership explicit.

## Detailed Instructions
- Complete all items in one response.
- Define which document layers belong to repo-agent governance and which belong to generated target-repository outputs.
- Introduce a deterministic output-layer manifest or equivalent contract boundary for generation.
- Ensure `docs/phases/**` remains valid as repo-agent governance material while clarifying whether it is included in target output.
- Keep overview, section, and module outputs additive and stable.
- Add validation coverage that rejects mixed governance-vs-target output paths.

## Expected Output
- Deliverables: output-layer manifest, target-only generation policy, phase-doc boundary rules, contract updates, and tests.
- Success criteria: generation ownership is explicit, and future tasks no longer have to infer whether governance docs belong in target repositories.
- File locations: `repo_wiki/generator/**`, contract registries, validation helpers, and related tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_1_Target_output_boundary_and_governance_layer_separation.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 9.2

```markdown
---
task_ref: "Task 9.2 - Unified link builder and path-contract recovery"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_2_Unified_link_builder_and_path_contract_recovery.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Unified link builder and path-contract recovery

## Task Reference
Implementation Plan: **Task 9.2 - Unified link builder and path-contract recovery** assigned to **Agent_DocGen**

## Context from Dependencies
This task depends on Task 9.1 implemented by Agent_DocGen.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_09_Output_Contract_and_Navigation_Hardening.md` and `docs/repo-wiki-phase-06-08-review.md` to understand the verified path-contract failures.
2. Read `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_1_Target_output_boundary_and_governance_layer_separation.md` to understand the final target-output boundary decisions.
3. Review the implementation files referenced in that log before changing template or generator path logic.

**Producer Output Summary:**
- Task 9.1 should define which outputs are target-facing and therefore need stable navigation contracts.

**Integration Requirements:**
- Replace brittle relative path assembly with a deterministic shared link-building strategy.
- Correct overview/section/module/API/data-model navigation without reintroducing duplicated `docs/` path segments.
- Keep links compatible with the final boundary rules from Task 9.1.

**User Clarification Protocol:**
If Task 9.1 leaves target-vs-governance output ownership unresolved, stop and ask whether boundary rules should be finalized before link recovery proceeds.

## Objective
Replace brittle relative-link assembly with a deterministic path contract across overview, section, module, API, and data-model docs.

## Detailed Instructions
- Complete all items in one response.
- Define canonical relative path rules for overview-to-section, section-to-overview, section-to-module, and core-doc navigation.
- Implement a shared link builder or equivalent helper used by generation and templates.
- Update affected templates and generator helpers to consume the new path contract.
- Add fixtures proving that previously broken path patterns no longer render.
- Keep the command surface unchanged; this task only repairs navigation contract behavior.

## Expected Output
- Deliverables: unified link builder, corrected path policy, rendering helpers, updated templates, and regression tests.
- Success criteria: rendered links are deterministic and path-correct across the document-center layers.
- File locations: `repo_wiki/generator/**`, `templates/docs/**`, and related tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_2_Unified_link_builder_and_path_contract_recovery.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 9.3

```markdown
---
task_ref: "Task 9.3 - Phase and section registry completion with alias support"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_3_Phase_and_section_registry_completion_with_alias_support.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Phase and section registry completion with alias support

## Task Reference
Implementation Plan: **Task 9.3 - Phase and section registry completion with alias support** assigned to **Agent_DocGen**

## Context from Dependencies
This task depends on Task 9.1 and Task 9.2 implemented by Agent_DocGen.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_09_Output_Contract_and_Navigation_Hardening.md`, `docs/repo-wiki-phase-06-08-review.md`, and `docs/AI_API_Atlas_repo_wiki_gap_analysis.md` to understand registry and compatibility gaps.
2. Read `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_1_Target_output_boundary_and_governance_layer_separation.md`.
3. Read `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_2_Unified_link_builder_and_path_contract_recovery.md`.
4. Review the implementation files referenced in those logs before modifying phase/section registry logic.

**Producer Output Summary:**
- Task 9.1 defines output ownership.
- Task 9.2 defines corrected path contracts that registry consumers must follow.

**Integration Requirements:**
- Extend the phase registry beyond its current incomplete coverage.
- Keep canonical section names stable while adding explicit alias/overlay support for compatibility analysis.
- Ensure generation and validation consume one shared registry source.

**User Clarification Protocol:**
If compatibility handling for non-canonical section overlays would force canonical section names to change, stop and ask whether overlay support should remain read-only instead of generation-capable.

## Objective
Complete the phase/section contract registry and add explicit alias or overlay handling for non-canonical section structures.

## Detailed Instructions
- Complete all items in one response.
- Extend phase registry coverage to the current implementation-plan phase set.
- Add alias or overlay metadata to section definitions so canonical sections can coexist with repository-specific topical layers.
- Ensure generation and validation reuse the same registry definitions.
- Keep canonical section naming stable and deterministic.
- Add schema tests for registry completeness and alias resolution.

## Expected Output
- Deliverables: completed registry, alias-capable section definitions, compatibility rules, and tests.
- Success criteria: registry coverage matches the implementation plan and compatibility handling is explicit instead of ad hoc.
- File locations: `repo_wiki/generator/**`, contract registries, validation helpers, and tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_3_Phase_and_section_registry_completion_with_alias_support.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 9.4

```markdown
---
task_ref: "Task 9.4 - Path-aware verify navigation checks"
agent_assignment: "Agent_AdapterGovernance"
memory_log_path: ".apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_4_Path_aware_verify_navigation_checks.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Path-aware verify navigation checks

## Task Reference
Implementation Plan: **Task 9.4 - Path-aware verify navigation checks** assigned to **Agent_AdapterGovernance**

## Context from Dependencies
This task depends on Task 9.2 and Task 9.3 implemented by Agent_DocGen.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_09_Output_Contract_and_Navigation_Hardening.md` to understand the stage goal and exit-gate expectations.
2. Read `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_2_Unified_link_builder_and_path_contract_recovery.md`.
3. Read `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_3_Phase_and_section_registry_completion_with_alias_support.md`.
4. Review the implementation files referenced by those logs before changing verify behavior.

**Producer Output Summary:**
- Task 9.2 defines corrected path rules and shared link-building behavior.
- Task 9.3 defines the final registry model that navigation checks must understand.

**Integration Requirements:**
- Preserve `verify --ci` command surface.
- Replace permissive string heuristics with real path resolution.
- Emit actionable reason codes for broken navigation and bad section routing.

**User Clarification Protocol:**
If upstream tasks leave link resolution rules or registry semantics ambiguous, stop and ask whether navigation checks should wait for contract stabilization.

## Objective
Upgrade navigation verification from string heuristics to real path resolution and cross-link validation.

## Detailed Instructions
- Complete all items in one response.
- Resolve markdown links to actual target files and fail when referenced docs do not exist.
- Check overview, section, API, data-model, and module-page navigation contracts using the corrected registry and link builder.
- Replace permissive `../` string checks with path-resolved validation.
- Add precise reason codes for broken navigation, bad path depth, and invalid section routing.
- Add fixtures for previously accepted-but-broken path cases.

## Expected Output
- Deliverables: path-aware navigation verifier, resolved-link checks, reason-code updates, and regression tests.
- Success criteria: `verify --ci` now fails broken links that earlier heuristic checks would have passed.
- File locations: `repo_wiki/verifier/**`, tests, and any supporting validation helpers.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_4_Path_aware_verify_navigation_checks.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```
