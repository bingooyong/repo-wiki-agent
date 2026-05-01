# Phase 35 - Replacement Candidate Acceptance

## Task 35.1

```markdown
---
task_ref: "Task 35.1 - AI_API_Atlas full pilot rerun"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_35_Replacement_Candidate_Acceptance/Task_35_1_AI_API_Atlas_full_pilot_rerun.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: AI_API_Atlas full pilot rerun

## Task Reference
Implementation Plan: **Task 35.1 - AI_API_Atlas full pilot rerun** assigned to **Agent_QualityRelease**

## Context from Dependencies
Depends on Task 34.4. Use strict, information architecture, evidence relevance, repair loop, and cache validity outputs from Phase 31-34.

## Objective
Run the final full AI_API_Atlas Minimax pilot after strict, IA, evidence, and repair improvements.

## Detailed Instructions
- Generate under `/Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas/.repo-agent-eval/<run>` only.
- Verify `.qoder/**` remains read-only and unmodified.
- Produce strict report, qoder comparison report, and manual review checklist.
- Require fallback pages to be `<= 5%` before READY consideration.

## Expected Output
- Deliverables: full isolated run, strict report, qoder comparison report, review checklist.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_qoder_like_verifier.py tests/test_qoder_comparator_paths.py`
- Completion rule: do not mark complete unless the run is either READY with evidence or explicitly `NOT_READY`.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_35_Replacement_Candidate_Acceptance/Task_35_1_AI_API_Atlas_full_pilot_rerun.md`
```

## Task 35.2

```markdown
---
task_ref: "Task 35.2 - Manual review pack"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_35_Replacement_Candidate_Acceptance/Task_35_2_Manual_review_pack.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Manual review pack

## Task Reference
Implementation Plan: **Task 35.2 - Manual review pack** assigned to **Agent_QualityRelease**

## Context from Dependencies
Depends on Task 35.1. Use final pilot outputs, strict report, and qoder comparison report.

## Objective
Build a 30-page manual review pack comparing repo-agent output to Qoder pages.

## Detailed Instructions
- Select 30 representative pages covering overview, architecture, core services, Python services, data models, API, operations, security, and troubleshooting.
- Record the Qoder page, repo-agent page, gap summary, and acceptability for each pair.
- Require at least 24 of 30 pages to be acceptable for replacement readiness.
- Keep review artifacts inside the isolated evaluation output or operations evidence.

## Expected Output
- Deliverables: 30-page manual review matrix, page-pair references, acceptance summary.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_qoder_parity_metrics.py tests/test_readiness_schema.py`
- Completion rule: do not mark complete unless review count and acceptance threshold are explicit.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_35_Replacement_Candidate_Acceptance/Task_35_2_Manual_review_pack.md`
```

## Task 35.3

```markdown
---
task_ref: "Task 35.3 - Plugin acceptance pass"
agent_assignment: "Agent_PlatformCore"
memory_log_path: ".apm/Memory/Phase_35_Replacement_Candidate_Acceptance/Task_35_3_Plugin_acceptance_pass.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Plugin acceptance pass

## Task Reference
Implementation Plan: **Task 35.3 - Plugin acceptance pass** assigned to **Agent_PlatformCore**

## Context from Dependencies
Depends on Task 35.2 and Task 27.5. Validate the extension against latest READY and NOT_READY run behavior.

## Objective
Verify the VS Code plugin experience against latest READY and NOT_READY runs.

## Detailed Instructions
- Validate left navigation, Markdown preview, stale prompt, and run selection.
- Default the plugin to the latest READY run.
- Clearly label NOT_READY runs and prevent accidental replacement claims.
- Add extension compile/package smoke evidence.

## Expected Output
- Deliverables: plugin acceptance evidence, latest-run behavior, NOT_READY labeling, package smoke result.
- Compile command: `npm --prefix extensions/repo-wiki-browser run compile`
- Self-test command: `npx --yes @vscode/vsce package --out repo-wiki-browser-0.1.0.vsix`
- Completion rule: do not mark complete unless extension navigation and stale/ready behavior are validated.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_35_Replacement_Candidate_Acceptance/Task_35_3_Plugin_acceptance_pass.md`
```

## Task 35.4

```markdown
---
task_ref: "Task 35.4 - Go/no-go dossier"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_35_Replacement_Candidate_Acceptance/Task_35_4_Go_no_go_dossier.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Go/no-go dossier

## Task Reference
Implementation Plan: **Task 35.4 - Go/no-go dossier** assigned to **Agent_QualityRelease**

## Context from Dependencies
Depends on Task 35.3 and Task 30.6. Use final pilot, manual review, plugin evidence, and prior go/no-go reporting conventions.

## Objective
Issue the final replacement decision dossier.

## Detailed Instructions
- State whether AI_API_Atlas can replace Qoder Repo Wiki with repo-agent output.
- Separate AI_API_Atlas-specific replacement readiness from general-purpose readiness.
- Require strict verify PASS, qoder compare READY, `.qoder/**` read-only verification, and at least 24 accepted manual review pages.
- If not ready, return `NOT_READY` with non-zero CLI behavior or explicit failure state.
- Update Memory Root with the final Phase 35 judgment.

## Expected Output
- Deliverables: go/no-go dossier, evidence index, readiness separation, Memory Root update.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_release_gate_policy.py tests/test_readiness_schema.py`
- Completion rule: do not mark complete unless the decision is evidence-linked and distinguishes AI_API_Atlas readiness from general readiness.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_35_Replacement_Candidate_Acceptance/Task_35_4_Go_no_go_dossier.md`
```

