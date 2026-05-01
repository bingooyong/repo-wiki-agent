# Phase 30 - Replacement Candidate Release and Documentation

## Task 30.1

```markdown
---
task_ref: "Task 30.1 - End-user configuration documentation"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_30_Replacement_Candidate_Release_and_Documentation/Task_30_1_End_user_configuration_documentation.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: End-user configuration documentation

## Task Reference
Implementation Plan: **Task 30.1 - End-user configuration documentation** assigned to **Agent_QualityRelease**

## Context from Dependencies
Read `docs/phases/Phase_30_Replacement_Candidate_Release_and_Documentation.md`, Task 29.6, and Phase 21 provider docs/logs.

## Objective
Document LLM provider setup for end users.

## Detailed Instructions
- Document Minimax, OpenAI-compatible, Anthropic-compatible, and local provider configuration.
- Show env/yaml examples without real secrets.
- Include troubleshooting for common config failures.

## Expected Output
- Deliverables: configuration documentation, validated examples.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_cli_config_doctor.py tests/test_docs_examples.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_30_Replacement_Candidate_Release_and_Documentation/Task_30_1_End_user_configuration_documentation.md`
```

## Task 30.2

```markdown
---
task_ref: "Task 30.2 - Installation and VS Code extension workflow"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_30_Replacement_Candidate_Release_and_Documentation/Task_30_2_Installation_and_VS_Code_extension_workflow.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Installation and VS Code extension workflow

## Task Reference
Implementation Plan: **Task 30.2 - Installation and VS Code extension workflow** assigned to **Agent_PlatformCore**

## Context from Dependencies
Depends on Task 30.1 and Task 27.5. Validate CLI and extension workflows against documented behavior.

## Objective
Document and validate CLI install, VSIX install, generate, view, update, and verify workflows.

## Detailed Instructions
- Include extension rebuild/reinstall instructions.
- Validate workflow commands from a clean environment where practical.
- Record packaging smoke evidence.

## Expected Output
- Deliverables: installation workflow docs, VSIX evidence, tests.
- Compile command: `npm --prefix extensions/repo-wiki-browser run compile`
- Self-test command: `npx --yes @vscode/vsce package --out repo-wiki-browser-0.1.0.vsix`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_30_Replacement_Candidate_Release_and_Documentation/Task_30_2_Installation_and_VS_Code_extension_workflow.md`
```

## Task 30.3

```markdown
---
task_ref: "Task 30.3 - AI_API_Atlas full replacement pilot"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_30_Replacement_Candidate_Release_and_Documentation/Task_30_3_AI_API_Atlas_full_replacement_pilot.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: AI_API_Atlas full replacement pilot

## Task Reference
Implementation Plan: **Task 30.3 - AI_API_Atlas full replacement pilot** assigned to **Agent_QualityRelease**

## Context from Dependencies
Depends on Task 30.2 and Task 29.5. Use qoder-like profile and isolate all outputs.

## Objective
Run a full AI_API_Atlas replacement pilot in isolated output.

## Detailed Instructions
- Generate under `.repo-agent-eval/<run>` only.
- Do not modify `.qoder`, `.repo-wiki`, or target `docs`.
- Produce manual acceptance instructions and evidence index.

## Expected Output
- Deliverables: isolated AI_API_Atlas run, manual acceptance pack, evidence index.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_golden_qoder_like_fixture.py tests/test_qoder_like_verifier.py`
- Completion rule: do not mark complete unless compile/self-test pass and baseline directories remain unmodified.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_30_Replacement_Candidate_Release_and_Documentation/Task_30_3_AI_API_Atlas_full_replacement_pilot.md`
```

## Task 30.4

```markdown
---
task_ref: "Task 30.4 - Multi-repository replacement pilot"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_30_Replacement_Candidate_Release_and_Documentation/Task_30_4_Multi_repository_replacement_pilot.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Multi-repository replacement pilot

## Task Reference
Implementation Plan: **Task 30.4 - Multi-repository replacement pilot** assigned to **Agent_QualityRelease**

## Context from Dependencies
Depends on Task 30.3. Use the AI_API_Atlas pilot process as the first benchmark.

## Objective
Validate replacement behavior across at least three repository classes.

## Detailed Instructions
- Cover different language and size profiles.
- Record generation cost, runtime, quality scores, and failures.
- Identify unsupported repository classes explicitly.

## Expected Output
- Deliverables: multi-repo pilot reports, evidence bundle, risk register.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_golden_qoder_like_fixture.py tests/test_qoder_parity_metrics.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_30_Replacement_Candidate_Release_and_Documentation/Task_30_4_Multi_repository_replacement_pilot.md`
```

## Task 30.5

```markdown
---
task_ref: "Task 30.5 - Release gate and rollback plan"
agent_assignment: "Agent_AdapterGovernance"
memory_log_path: ".apm/Memory/Phase_30_Replacement_Candidate_Release_and_Documentation/Task_30_5_Release_gate_and_rollback_plan.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Release gate and rollback plan

## Task Reference
Implementation Plan: **Task 30.5 - Release gate and rollback plan** assigned to **Agent_AdapterGovernance**

## Context from Dependencies
Depends on Task 30.4. Use multi-repo evidence to define production replacement gates.

## Objective
Define production replacement gate, rollback behavior, and failure handling.

## Detailed Instructions
- Block production replacement claims unless strict gates pass.
- Define rollback when docs are stale, low quality, partially generated, or extension display fails.
- Include CI and operator failure modes.

## Expected Output
- Deliverables: release gate policy, rollback plan, failure handling docs/tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_release_gate_policy.py tests/test_qoder_like_verifier.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_30_Replacement_Candidate_Release_and_Documentation/Task_30_5_Release_gate_and_rollback_plan.md`
```

## Task 30.6

```markdown
---
task_ref: "Task 30.6 - Final go/no-go dossier"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_30_Replacement_Candidate_Release_and_Documentation/Task_30_6_Final_go_no_go_dossier.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Final go/no-go dossier

## Task Reference
Implementation Plan: **Task 30.6 - Final go/no-go dossier** assigned to **Agent_QualityRelease**

## Context from Dependencies
Depends on Task 30.5. Read all Phase 30 evidence and release gate policy before writing the final decision.

## Objective
Produce the final replacement decision package.

## Detailed Instructions
- State whether repo-agent can replace Qoder Repo Wiki for target usage.
- Separate AI_API_Atlas-specific readiness from general product readiness.
- Link every claim to evidence and update Memory Root with the final Phase 30 judgment.

## Expected Output
- Deliverables: final decision report, evidence index, remaining gaps, next backlog.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_release_gate_policy.py tests/test_readiness_schema.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_30_Replacement_Candidate_Release_and_Documentation/Task_30_6_Final_go_no_go_dossier.md`
```

