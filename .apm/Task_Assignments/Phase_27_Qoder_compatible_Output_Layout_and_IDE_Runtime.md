# Phase 27 - Qoder-compatible Output Layout and IDE Runtime

## Task 27.1

```markdown
---
task_ref: "Task 27.1 - Qoder-like output profile"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime/Task_27_1_Qoder_like_output_profile.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Qoder-like output profile

## Task Reference
Implementation Plan: **Task 27.1 - Qoder-like output profile** assigned to **Agent_PlatformCore**

## Context from Dependencies
Read `docs/phases/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime.md`, Task 24.6, Task 25.6, and Task 26.6 logs.

## Objective
Add isolated qoder-like generation profile and output path controls.

## Detailed Instructions
- Implement `repo-wiki generate --profile qoder-like --output .repo-agent-eval`.
- Default qoder-like output to `.repo-agent-eval/<run>`.
- Add guardrails so `.qoder`, `.repo-wiki`, and target docs are not modified by default.

## Expected Output
- Deliverables: qoder-like profile, CLI command integration, safety tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_qoder_like_profile.py tests/test_cli_generate.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime/Task_27_1_Qoder_like_output_profile.md`
```

## Task 27.2

```markdown
---
task_ref: "Task 27.2 - Content layout writer"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime/Task_27_2_Content_layout_writer.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Content layout writer

## Task Reference
Implementation Plan: **Task 27.2 - Content layout writer** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 27.1 by Agent_PlatformCore and Task 22.6 by Agent_IndexGraph. Use profile and manifest plan.

## Objective
Write generated pages into `.repo-agent-eval/<run>/content/**` using the planner tree.

## Detailed Instructions
- Preserve Chinese taxonomy hierarchy and stable slugs.
- Write only planned pages selected by manifest.
- Add layout fixture tests and safety checks.

## Expected Output
- Deliverables: content layout writer, fixtures, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_content_layout_writer.py tests/test_qoder_like_profile.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime/Task_27_2_Content_layout_writer.md`
```

## Task 27.3

```markdown
---
task_ref: "Task 27.3 - Manifest navigation tree and commit metadata"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime/Task_27_3_Manifest_navigation_tree_and_commit_metadata.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Manifest navigation tree and commit metadata

## Task Reference
Implementation Plan: **Task 27.3 - Manifest navigation tree and commit metadata** assigned to **Agent_IndexGraph**

## Context from Dependencies
Depends on Task 27.2 and Phase 12 runtime store. Persist manifest fields consumed by IDE and static viewer.

## Objective
Write manifest navigation and git freshness metadata.

## Detailed Instructions
- Populate `navigation_tree`, `wiki_git_commit`, `target_git_commit`, `content_root`, `runtime_root`, and `page_registry`.
- Support git commit detection and hash fallback.
- Add stale-detection and manifest compatibility tests.

## Expected Output
- Deliverables: manifest writer, commit metadata, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_eval_manifest.py tests/test_commit_freshness.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime/Task_27_3_Manifest_navigation_tree_and_commit_metadata.md`
```

## Task 27.4

```markdown
---
task_ref: "Task 27.4 - VS Code extension nav-tree integration"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime/Task_27_4_VS_Code_extension_nav_tree_integration.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: VS Code extension nav-tree integration

## Task Reference
Implementation Plan: **Task 27.4 - VS Code extension nav-tree integration** assigned to **Agent_PlatformCore**

## Context from Dependencies
Depends on Task 27.3 by Agent_IndexGraph and Task 19.2. Use manifest navigation instead of path guessing.

## Objective
Make the VS Code extension render the manifest navigation tree.

## Detailed Instructions
- Discover latest or selected `.repo-agent-eval/<run>/manifest.json`.
- Render Chinese Qoder-like tree in the left Repo Wiki activity view.
- Add extension compile and command smoke tests where practical.

## Expected Output
- Deliverables: extension nav-tree integration and tests.
- Compile command: `npm --prefix extensions/repo-wiki-browser run compile`
- Self-test command: `uv run pytest tests/test_eval_manifest.py tests/test_extension_manifest_contract.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime/Task_27_4_VS_Code_extension_nav_tree_integration.md`
```

## Task 27.5

```markdown
---
task_ref: "Task 27.5 - Markdown preview and stale wiki UX"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime/Task_27_5_Markdown_preview_and_stale_wiki_UX.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Markdown preview and stale wiki UX

## Task Reference
Implementation Plan: **Task 27.5 - Markdown preview and stale wiki UX** assigned to **Agent_PlatformCore**

## Context from Dependencies
Depends on Task 27.4. Continue within the VS Code extension write domain.

## Objective
Open selected Wiki pages in Markdown preview and show stale Wiki prompts.

## Detailed Instructions
- Click tree nodes to open Markdown Preview.
- Compare current git id with manifest git id and show update/sync actions when stale.
- Ensure VSIX packaging succeeds.

## Expected Output
- Deliverables: preview command, stale prompt UX, VSIX packaging evidence.
- Compile command: `npm --prefix extensions/repo-wiki-browser run compile`
- Self-test command: `npx --yes @vscode/vsce package --out repo-wiki-browser-0.1.0.vsix`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime/Task_27_5_Markdown_preview_and_stale_wiki_UX.md`
```

## Task 27.6

```markdown
---
task_ref: "Task 27.6 - Static viewer parity pass"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime/Task_27_6_Static_viewer_parity_pass.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Static viewer parity pass

## Task Reference
Implementation Plan: **Task 27.6 - Static viewer parity pass** assigned to **Agent_PlatformCore**

## Context from Dependencies
Depends on Task 27.5 and Task 19.1. Use the same manifest navigation contract for extension and viewer.

## Objective
Make the static viewer consume the same manifest tree as the extension.

## Detailed Instructions
- Remove divergent navigation construction in viewer code.
- Validate extension and viewer render the same hierarchy.
- Add parity regression tests.

## Expected Output
- Deliverables: viewer manifest integration, parity tests.
- Compile command: `npm --prefix extensions/repo-wiki-browser run compile`
- Self-test command: `uv run pytest tests/test_static_viewer.py tests/test_viewer_extension_nav_parity.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime/Task_27_6_Static_viewer_parity_pass.md`
```

