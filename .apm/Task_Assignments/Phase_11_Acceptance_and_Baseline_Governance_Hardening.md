# Phase 11 – Acceptance and Baseline Governance Hardening

## Task 11.1

```markdown
---
task_ref: "Task 11.1 - Hard-gate vs soft-gate verify redesign"
agent_assignment: "Agent_AdapterGovernance"
memory_log_path: ".apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_1_Hard_gate_vs_soft_gate_verify_redesign.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Hard-gate vs soft-gate verify redesign

## Task Reference
Implementation Plan: **Task 11.1 - Hard-gate vs soft-gate verify redesign** assigned to **Agent_AdapterGovernance**

## Context from Dependencies
This task depends on Task 9.4 implemented by Agent_AdapterGovernance and Task 10.4 implemented by Agent_DocGen.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_11_Acceptance_and_Baseline_Governance_Hardening.md` to understand the governance-hardening goals.
2. Read `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_4_Path_aware_verify_navigation_checks.md`.
3. Read `.apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_4_Section_page_builder_rewrite_for_document_center_behavior.md`.
4. Review the implementation files referenced in those logs before redesigning verify grading.

**Producer Output Summary:**
- Task 9.4 should provide structurally accurate navigation validation.
- Task 10.4 should establish the new expected behavior for section pages and therefore change the quality bar verify must enforce.

**Integration Requirements:**
- Preserve `verify --ci` command surface.
- Separate hard structural failures from softer quality deviations.
- Keep reason codes actionable and stable enough for downstream reporting.

**User Clarification Protocol:**
If upstream section-page expectations are still moving, stop and ask whether verify grading should wait for content contracts to stabilize.

## Objective
Split `verify --ci` into structural hard failures and content-quality soft failures with explicit reason families.

## Detailed Instructions
- Complete all items in one response.
- Separate non-negotiable structural failures from softer readability or quality deviations.
- Reclassify existing reason codes into stable families and document grading semantics.
- Ensure CI output explains why a result is FAIL versus WARN.
- Add regression tests covering mixed hard/soft outcomes and multi-check reporting.
- Keep backwards-compatible top-level grade fields while enriching reason detail.

## Expected Output
- Deliverables: verify grading redesign, reason taxonomy, updated CI output schema, and regression tests.
- Success criteria: verify results become decision-grade and distinguish structural blockers from quality drift.
- File locations: `repo_wiki/verifier/**`, CLI integration points, and tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_1_Hard_gate_vs_soft_gate_verify_redesign.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 11.2

```markdown
---
task_ref: "Task 11.2 - Baseline comparator redesign and score integrity recovery"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_2_Baseline_comparator_redesign_and_score_integrity_recovery.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Baseline comparator redesign and score integrity recovery

## Task Reference
Implementation Plan: **Task 11.2 - Baseline comparator redesign and score integrity recovery** assigned to **Agent_QualityRelease**

## Context from Dependencies
This task depends on Task 11.1 implemented by Agent_AdapterGovernance and Task 8.2 implemented by Agent_QualityRelease.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_11_Acceptance_and_Baseline_Governance_Hardening.md`.
2. Read `docs/repo-wiki-phase-06-08-review.md`, `docs/AI_API_Atlas_repo_wiki_gap_analysis.md`, and `docs/operations/AI_API_Atlas_Readiness_Report.md`.
3. Read `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_1_Hard_gate_vs_soft_gate_verify_redesign.md`.
4. Read `.apm/Memory/Phase_08_Quality_Gates_and_Qoder_Baseline_Regression/Task_8_2_Qoder_baseline_regression_harness_and_gap_report.md`.
5. Review the implementation files referenced in those logs before redesigning the comparator.

**Producer Output Summary:**
- Task 11.1 should define the updated verify grading semantics and reason families.
- Task 8.2 provides the current comparator baseline and known weak points that must now be corrected.

**Integration Requirements:**
- Replace weak directory scoring and heading coverage heuristics.
- Distinguish canonical sections from repository-specific overlays.
- Keep outputs both machine-readable and human-readable.

**User Clarification Protocol:**
If a true qoder baseline artifact set is still unavailable for comparison, stop and ask whether a repository-backed golden baseline should be introduced before scoring is finalized.

## Objective
Rebuild the qoder comparison harness so structure and quality scores reflect real deltas rather than heuristic artifacts.

## Detailed Instructions
- Complete all items in one response.
- Replace weak directory-structure scoring with real hierarchy comparison.
- Separate canonical section detection from repository-specific overlays such as Q01/S01.
- Fix heading coverage and baseline-input handling so scores compare the intended artifacts.
- Distinguish hard structural mismatches from reference-quality gaps in the final report.
- Document how to interpret scores and where heuristic limits still remain.

## Expected Output
- Deliverables: comparator redesign, score rubric, improved section recognition, corrected baseline handling, and regression documentation.
- Success criteria: comparator output is trustworthy enough to support Manager decisions instead of serving only as a rough hint.
- File locations: `scripts/**`, `docs/operations/**`, and any related tests or fixtures.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_2_Baseline_comparator_redesign_and_score_integrity_recovery.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 11.3

```markdown
---
task_ref: "Task 11.3 - Unified readiness-report schema and evidence bundle"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_3_Unified_readiness_report_schema_and_evidence_bundle.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Unified readiness-report schema and evidence bundle

## Task Reference
Implementation Plan: **Task 11.3 - Unified readiness-report schema and evidence bundle** assigned to **Agent_QualityRelease**

## Context from Dependencies
This task depends on Task 11.1 and Task 11.2.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_11_Acceptance_and_Baseline_Governance_Hardening.md`.
2. Read `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_1_Hard_gate_vs_soft_gate_verify_redesign.md`.
3. Read `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_2_Baseline_comparator_redesign_and_score_integrity_recovery.md`.
4. Review the implementation files referenced in those logs before defining the unified readiness-report contract.

**Producer Output Summary:**
- Task 11.1 provides refined verify grading and reasons.
- Task 11.2 provides improved comparator outputs and score semantics.

**Integration Requirements:**
- Stop forcing Manager to manually reconcile multiple governance reports.
- Standardize evidence references and next-step recommendation format.
- Clearly separate product gaps, tooling gaps, and compatibility overlays.

**User Clarification Protocol:**
If verify and comparator outputs still use incompatible top-level shapes after reviewing upstream logs, stop and ask whether upstream schemas should be normalized before report unification proceeds.

## Objective
Merge verify and compare outputs into a single readiness-report contract with reproducible evidence references.

## Detailed Instructions
- Complete all items in one response.
- Define a unified readiness-report schema that includes verify grade, comparator results, blocking gaps, and next-step recommendation.
- Standardize evidence references to generated docs, gap reports, and command outputs.
- Ensure the report explicitly separates product gaps, tooling gaps, and compatibility overlays.
- Update governance documentation so future acceptance runs follow one reporting contract.
- Add tests or fixtures proving report generation remains stable as reason codes evolve.

## Expected Output
- Deliverables: readiness schema, evidence bundle structure, report generator, documentation updates, and tests or fixtures.
- Success criteria: acceptance output becomes a single, reproducible governance artifact instead of a manual synthesis exercise.
- File locations: `docs/operations/**`, `scripts/**`, and any related tests or fixtures.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_3_Unified_readiness_report_schema_and_evidence_bundle.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 11.4

```markdown
---
task_ref: "Task 11.4 - Multi-repository regression acceptance"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_4_Multi_repository_regression_acceptance.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Multi-repository regression acceptance

## Task Reference
Implementation Plan: **Task 11.4 - Multi-repository regression acceptance** assigned to **Agent_QualityRelease**

## Context from Dependencies
This task depends on Task 11.3 implemented by Agent_QualityRelease.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_11_Acceptance_and_Baseline_Governance_Hardening.md`.
2. Read `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_3_Unified_readiness_report_schema_and_evidence_bundle.md`.
3. Review the implementation files referenced in that log before planning or executing multi-repo acceptance.

**Producer Output Summary:**
- Task 11.3 should define the unified readiness-report contract and evidence bundle shape that multi-repo acceptance must reuse.

**Integration Requirements:**
- `AI_API_Atlas` remains mandatory.
- Acceptance must cover at least one additional representative repository.
- Final recommendation must distinguish recurring system gaps from repository-specific quirks.

**User Clarification Protocol:**
If no second representative repository can be selected from current local context, stop and ask which repository should serve as the additional acceptance sample.

## Objective
Expand acceptance beyond `AI_API_Atlas` so replacement-readiness is judged across multiple repository shapes.

## Detailed Instructions
- Complete all items in one response.
- Run the unified acceptance flow on `AI_API_Atlas` and at least one additional representative repository.
- Compare structural and quality outcomes across repositories to identify recurring versus repository-specific gaps.
- Update readiness conclusions using the new evidence bundle and report schema.
- Record blockers that still prevent repo-agent from being positioned as a qoder replacement.
- Provide a clear Manager recommendation for whether to proceed to runtime hardening or return to generation fixes.

## Expected Output
- Deliverables: multi-repo acceptance matrix, comparative gap reports, updated readiness conclusions, and manager-ready recommendation.
- Success criteria: replacement-readiness is no longer inferred from a single target repository.
- File locations: `docs/operations/**`, `scripts/**`, and any related evidence outputs.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_4_Multi_repository_regression_acceptance.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```
