# Phase 08 – Quality Gates and Qoder Baseline Regression

## Task 8.1

```markdown
---
task_ref: "Task 8.1 - Content-quality verify and CI gate upgrade"
agent_assignment: "Agent_AdapterGovernance"
memory_log_path: ".apm/Memory/Phase_08_Quality_Gates_and_Qoder_Baseline_Regression/Task_8_1_Content_quality_verify_and_CI_gate_upgrade.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Content-quality verify and CI gate upgrade

## Task Reference
Implementation Plan: **Task 8.1 - Content-quality verify and CI gate upgrade** assigned to **Agent_AdapterGovernance**

## Context from Dependencies
This task depends on Task 6.1 and Task 7.1, Task 7.2, Task 7.3, Task 7.4 implemented by Agent_DocGen.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_08_Quality_Gates_and_Qoder_Baseline_Regression.md` to understand the stage goal and the expected quality-gate scope.
2. Read `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_1_Document_output_contract_refactor_and_document_center_layer.md` to identify the new section/phase contract structure.
3. Read `.apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_1_Domain_centered_module_map_generation.md`, `.apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_2_Aggregated_API_contracts_generation.md`, `.apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_3_Domain_aggregated_data_model_generation.md`, and `.apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_4_Section_page_generation_and_navigation_stitching.md`.
4. Review the implementation files referenced by those logs before extending verify logic. Reuse the final contracts rather than inferring quality rules from generated output alone.

**Producer Output Summary:**
- Task 6.1 defines the new document-center layers and the required section/phase contract structure.
- Task 7.1-7.4 define the expected module-map, API, data-model, and section-page outputs that quality gates must enforce.

**Integration Requirements:**
- Keep the command surface unchanged: `verify --ci`.
- Extend governance from file existence to section count, prose presence, aggregation quality, and navigation integrity.
- Provide precise WARN/FAIL reasons so CI output is actionable.

**User Clarification Protocol:**
If the section contract or aggregated output shape is still moving, stop and ask whether the upstream DocGen tasks should be stabilized before verify is upgraded.

## Objective
Upgrade `verify --ci` from existence checks to content-quality governance checks for the new document-center model.

## Detailed Instructions
- Complete all items in one response.
- Add checks for minimum section count and minimum prose paragraphs in overview and architecture docs.
- Add checks that `docs/sections/**` exists and contains the required section pages.
- Add checks that API and data-model overviews are aggregated rather than raw dumps.
- Add checks that section pages and overview docs are stitched together with valid navigation links.
- Extend `--ci` output to include precise reason codes for content-quality WARN and FAIL outcomes.
- Add fixture-based tests that cover empty templates, list-only docs, broken navigation, and missing section layers.

## Expected Output
- Deliverables: extended verify rules, CI output reasons, quality fixtures, and regression coverage.
- Success criteria: `verify --ci` can now fail or warn on poor document quality, not just missing files.
- File locations: `repo_wiki/verifier/**`, CLI integration points, and tests covering new quality rules.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_08_Quality_Gates_and_Qoder_Baseline_Regression/Task_8_1_Content_quality_verify_and_CI_gate_upgrade.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 8.2

```markdown
---
task_ref: "Task 8.2 - Qoder baseline regression harness and gap report"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_08_Quality_Gates_and_Qoder_Baseline_Regression/Task_8_2_Qoder_baseline_regression_harness_and_gap_report.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Qoder baseline regression harness and gap report

## Task Reference
Implementation Plan: **Task 8.2 - Qoder baseline regression harness and gap report** assigned to **Agent_QualityRelease**

## Context from Dependencies
This task depends on Task 8.1 implemented by Agent_AdapterGovernance.

**Integration Steps (complete in one response):**
1. Read `docs/qoder-repo-wiki-design-analysis.md` to understand the qoder-style baseline dimensions that must be turned into a regression harness.
2. Read `docs/repo-wiki-qoder-gap-task-plan.md` to align the comparison harness with the previously identified quality gaps.
3. Read `.apm/Memory/Phase_08_Quality_Gates_and_Qoder_Baseline_Regression/Task_8_1_Content_quality_verify_and_CI_gate_upgrade.md` to identify the exact quality rules and machine-readable reasons now available from verify.
4. Review the files referenced in that log before implementing the comparison harness, so the harness reuses the new governance surface instead of inventing a second unrelated rubric.

**Producer Output Summary:**
- Task 8.1 provides the upgraded content-quality governance rules and CI output reasons.
- The qoder analysis documents provide the target directory, navigation, and readability model the harness must compare against.

**Integration Requirements:**
- Compare directory hierarchy, section coverage, heading coverage, prose density, navigation completeness, and aggregation quality.
- Produce both machine-readable and human-readable gap reports.
- Explain what is missing, not just that a mismatch exists.

**User Clarification Protocol:**
If verify reason codes or qoder baseline dimensions are still ambiguous after reviewing the sources, stop and ask whether the governance rules should be refined before building the comparison harness.

## Objective
Build a repeatable comparison harness that measures repo-wiki output against the qoder-style baseline.

## Detailed Instructions
- Complete all items in one response.
- Define comparison dimensions for directory hierarchy, section coverage, heading coverage, prose density, navigation completeness, and aggregation quality.
- Implement a script or checklist that compares generated outputs against the chosen qoder baseline repository.
- Produce a machine-readable and human-readable gap report format for future regressions.
- Document how the comparison harness is run locally and how its results should be interpreted in governance reviews.
- Ensure the harness can explain what is missing and where the output still diverges from qoder-style organization.

## Expected Output
- Deliverables: baseline comparison script, structure/content checklist, diff report format, and regression documentation.
- Success criteria: the project can now answer "what is still missing versus qoder" with a repeatable report instead of ad hoc review.
- File locations: `scripts/**`, `docs/operations/**`, or other quality/release support paths, plus any tests or fixtures needed.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_08_Quality_Gates_and_Qoder_Baseline_Regression/Task_8_2_Qoder_baseline_regression_harness_and_gap_report.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 8.3

```markdown
---
task_ref: "Task 8.3 - AI_API_Atlas regeneration acceptance and readiness report"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_08_Quality_Gates_and_Qoder_Baseline_Regression/Task_8_3_AI_API_Atlas_regeneration_acceptance_and_readiness_report.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: AI_API_Atlas regeneration acceptance and readiness report

## Task Reference
Implementation Plan: **Task 8.3 - AI_API_Atlas regeneration acceptance and readiness report** assigned to **Agent_QualityRelease**

## Context from Dependencies
This task depends on Task 8.1 and Task 8.2.

**Integration Steps (complete in one response):**
1. Read `.apm/Memory/Phase_08_Quality_Gates_and_Qoder_Baseline_Regression/Task_8_1_Content_quality_verify_and_CI_gate_upgrade.md` to understand the final governance rules and CI reason codes.
2. Read `.apm/Memory/Phase_08_Quality_Gates_and_Qoder_Baseline_Regression/Task_8_2_Qoder_baseline_regression_harness_and_gap_report.md` to understand the final comparison harness, evidence format, and report outputs.
3. Review `docs/phases/Phase_08_Quality_Gates_and_Qoder_Baseline_Regression.md` before running acceptance so the report aligns with the defined stage gates.
4. Use `/Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas` as the fixed acceptance target and reuse the upgraded command and verification surfaces instead of inventing a one-off review process.

**Producer Output Summary:**
- Task 8.1 provides the upgraded content-quality verify gate.
- Task 8.2 provides the qoder baseline comparison harness and gap report model.

**Integration Requirements:**
- Regenerate outputs for `AI_API_Atlas` using the upgraded contracts and generation flow.
- Run the upgraded `verify --ci` and the qoder comparison harness on the same repository.
- Produce a readiness report with explicit remaining gaps, rollout blockers, and next-step recommendation.

**User Clarification Protocol:**
If the comparison harness or upgraded verify flow is not stable enough to run end-to-end on `AI_API_Atlas`, stop and ask whether Task 8.1 or 8.2 should be refined first.

## Objective
Re-run the target repository acceptance flow and determine whether the qoder-aligned output is ready for broader rollout.

## Detailed Instructions
- Complete all items in one response.
- Regenerate knowledge outputs for `/Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas` using the upgraded contracts and generation flow.
- Run the upgraded `verify --ci` and the qoder comparison harness on the target repository.
- Capture evidence for overview quality, architecture readability, section navigation, and aggregated API/data-model docs.
- Produce a readiness report that states remaining quality gaps, rollout blockers, and whether another template/model iteration is required.
- Record the explicit next-step recommendation for Manager follow-up.

## Expected Output
- Deliverables: `AI_API_Atlas` acceptance evidence, regenerated knowledge-base assessment, and a Qoder-alignment readiness report.
- Success criteria: the project has a concrete target-repo verdict on whether qoder alignment is good enough to proceed or still requires another iteration.
- File locations: release/quality documentation paths in this repository plus regenerated outputs under `/Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas`.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_08_Quality_Gates_and_Qoder_Baseline_Regression/Task_8_3_AI_API_Atlas_regeneration_acceptance_and_readiness_report.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```
