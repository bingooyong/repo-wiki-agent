# Phase 15 – Visual Knowledge Experience and IDE Integration

## Task 15.1

```markdown
---
task_ref: "Task 15.1 - Isolated eval output layout and manifest for target repos"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration/Task_15_1_Isolated_eval_output_layout_and_manifest_for_target_repos.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Isolated eval output layout and manifest for target repos

## Task Reference
Implementation Plan: **Task 15.1 - Isolated eval output layout and manifest for target repos** assigned to **Agent_PlatformCore**

## Context from Dependencies
This task depends on Task 13.4 implemented by Agent_QualityRelease and Task 9.1 implemented by Agent_DocGen.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration.md`.
2. Read `.apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_4_Atlas_hard_gate_clearance_and_blocker_burndown_report.md`.
3. Read `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_1_Target_output_boundary_and_governance_layer_separation.md`.
4. Review current output directory policy and manual acceptance flow artifacts.
5. Review path safety constraints for generated outputs.

**Producer Output Summary:**
- Task 9.1 defined target-vs-governance output boundaries.
- Task 13.4 captured Atlas acceptance evidence workflow needs.

**Integration Requirements:**
- Add isolated output contract rooted at `.repo-agent-eval`.
- Prevent accidental overwrite of baseline `.repo-wiki` or checked-in `docs/` outputs.
- Provide explicit manifest describing generated artifacts and evidence files.

**User Clarification Protocol:**
If introducing isolated output mode conflicts with existing default output expectations, stop and ask whether to switch default or keep isolated mode opt-in.

## Objective
Define a safe and deterministic isolated evaluation output layout with manifest support for human and tool consumption.

## Detailed Instructions
- Complete all items in one response.
- Implement `.repo-agent-eval` output layout policy and manifest schema.
- Add configuration switches for output destination profiles.
- Validate path boundaries and reject unsafe output roots.
- Add tests for manifest completeness and path safety.
- Document manual acceptance workflow using isolated output.

## Expected Output
- Deliverables: output layout contract, manifest generator, configuration integration, tests, docs.
- Success criteria: evaluation runs are isolated and reproducible without modifying protected baseline folders.
- File locations: orchestration/config modules, output helpers, docs, tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration/Task_15_1_Isolated_eval_output_layout_and_manifest_for_target_repos.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 15.2

```markdown
---
task_ref: "Task 15.2 - Static repo-wiki viewer with tree navigation and Mermaid rendering"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration/Task_15_2_Static_repo_wiki_viewer_with_tree_navigation_and_mermaid_rendering.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Static repo-wiki viewer with tree navigation and Mermaid rendering

## Task Reference
Implementation Plan: **Task 15.2 - Static repo-wiki viewer with tree navigation and Mermaid rendering** assigned to **Agent_PlatformCore**

## Context from Dependencies
This task depends on Task 15.1 implemented by Agent_PlatformCore and Task 9.4 implemented by Agent_AdapterGovernance.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration.md`.
2. Read `.apm/Memory/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration/Task_15_1_Isolated_eval_output_layout_and_manifest_for_target_repos.md`.
3. Read `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_4_Path_aware_verify_navigation_checks.md`.
4. Review manifest format and navigation contract from prior tasks.
5. Review repository toolchain constraints for local viewer delivery.

**Producer Output Summary:**
- Task 15.1 defines isolated output and manifest boundaries.
- Task 9.4 ensures navigation links are path-valid and can drive viewer behavior.

**Integration Requirements:**
- Build viewer against manifest/navigation contract, not ad hoc folder scanning.
- Support rendered markdown, heading anchors, and Mermaid diagrams.
- Keep viewer usable on static local files without external service dependency.

**User Clarification Protocol:**
If viewer implementation requires adding a server runtime not currently accepted in this project, stop and ask whether static-only mode should remain mandatory.

## Objective
Deliver a local static viewer that provides tree navigation and rich rendering for generated repo-agent wiki content.

## Detailed Instructions
- Complete all items in one response.
- Render left-side tree navigation from manifest and section/module hierarchy.
- Support table-of-contents and in-page heading jumps.
- Render Mermaid blocks safely and consistently.
- Add fixtures that validate navigation and rendering quality.
- Document usage for manual quality acceptance.

## Expected Output
- Deliverables: static viewer implementation, manifest integration, rendering support, tests, docs.
- Success criteria: users can inspect generated wiki quality through a coherent visual interface.
- File locations: viewer modules, static assets, docs, tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration/Task_15_2_Static_repo_wiki_viewer_with_tree_navigation_and_mermaid_rendering.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 15.3

```markdown
---
task_ref: "Task 15.3 - VS Code extension prototype for repo-agent wiki browsing"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration/Task_15_3_VS_Code_extension_prototype_for_repo_agent_wiki_browsing.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: VS Code extension prototype for repo-agent wiki browsing

## Task Reference
Implementation Plan: **Task 15.3 - VS Code extension prototype for repo-agent wiki browsing** assigned to **Agent_PlatformCore**

## Context from Dependencies
This task depends on Task 15.2 implemented by Agent_PlatformCore.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration.md`.
2. Read `.apm/Memory/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration/Task_15_2_Static_repo_wiki_viewer_with_tree_navigation_and_mermaid_rendering.md`.
3. Review current CLI command triggers and local output manifest contract.
4. Review extension packaging constraints and compatibility notes.
5. Review manual acceptance workflow expectations for Atlas.

**Producer Output Summary:**
- Task 15.2 provides visual rendering and navigation primitives that can be reused in IDE form.

**Integration Requirements:**
- Keep extension prototype additive and optional.
- Load navigation from `.repo-agent-eval` manifest.
- Expose command shortcuts without changing CLI behavior.

**User Clarification Protocol:**
If extension runtime cannot support required rendering features in current scope, stop and ask whether to deliver navigation-only prototype first.

## Objective
Build a VS Code-compatible extension prototype that allows browsing repo-agent wiki outputs with sidebar tree and preview.

## Detailed Instructions
- Complete all items in one response.
- Implement tree provider bound to manifest contract.
- Implement markdown preview integration with link navigation.
- Add quick actions for `repo-wiki update` and `repo-wiki verify --ci`.
- Provide packaging and local install instructions.
- Add basic extension tests or smoke checks.

## Expected Output
- Deliverables: extension prototype, tree/preview integration, quick actions, docs, tests.
- Success criteria: manual reviewers can browse generated wiki content directly inside IDE.
- File locations: extension workspace/package, integration helpers, docs, tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration/Task_15_3_VS_Code_extension_prototype_for_repo_agent_wiki_browsing.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 15.4

```markdown
---
task_ref: "Task 15.4 - Qoder-style navigation metadata adapter and import bridge"
agent_assignment: "Agent_AdapterGovernance"
memory_log_path: ".apm/Memory/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration/Task_15_4_Qoder_style_navigation_metadata_adapter_and_import_bridge.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Qoder-style navigation metadata adapter and import bridge

## Task Reference
Implementation Plan: **Task 15.4 - Qoder-style navigation metadata adapter and import bridge** assigned to **Agent_AdapterGovernance**

## Context from Dependencies
This task depends on Task 15.3 implemented by Agent_PlatformCore and Task 9.3 implemented by Agent_DocGen.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration.md`.
2. Read `.apm/Memory/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration/Task_15_3_VS_Code_extension_prototype_for_repo_agent_wiki_browsing.md`.
3. Read `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_3_Phase_and_section_registry_completion_with_alias_support.md`.
4. Review import targets and metadata format assumptions from existing qoder outputs.
5. Review verifier checks to ensure imported metadata does not bypass canonical validation.

**Producer Output Summary:**
- Task 15.3 provides IDE-side navigation consumer.
- Task 9.3 provides alias-aware registry for compatibility mapping.

**Integration Requirements:**
- Keep adapter optional and isolated from canonical generation output.
- Validate imported metadata against actual file paths and section contracts.
- Emit warnings when imported trees diverge from canonical mapping.

**User Clarification Protocol:**
If imported metadata semantics conflict with canonical contracts in non-resolvable ways, stop and ask whether to keep import as read-only visualization mode.

## Objective
Provide an optional metadata adapter and import bridge to evaluate qoder-like navigation side-by-side with repo-agent canonical structures.

## Detailed Instructions
- Complete all items in one response.
- Define adapter schema and import pipeline for qoder-style navigation metadata.
- Map imported nodes to canonical section/module targets where possible.
- Add validation and warning reason codes for unresolved mappings.
- Integrate adapter output with viewer/extension consumption paths.
- Add regression fixtures for mixed canonical/imported trees.

## Expected Output
- Deliverables: metadata adapter, import bridge, compatibility checks, docs, tests.
- Success criteria: side-by-side navigation evaluation is possible without weakening canonical contracts.
- File locations: adapter/verifier modules, viewer integration points, docs, tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration/Task_15_4_Qoder_style_navigation_metadata_adapter_and_import_bridge.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```
