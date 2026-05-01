# Phase 14 – External Baseline Calibration and Benchmark Governance

## Task 14.1

```markdown
---
task_ref: "Task 14.1 - External qoder snapshot fixture contract and ingestion"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance/Task_14_1_External_qoder_snapshot_fixture_contract_and_ingestion.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: External qoder snapshot fixture contract and ingestion

## Task Reference
Implementation Plan: **Task 14.1 - External qoder snapshot fixture contract and ingestion** assigned to **Agent_QualityRelease**

## Context from Dependencies
This task depends on Task 11.2 implemented by Agent_QualityRelease and Task 13.4 implemented by Agent_QualityRelease.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance.md`.
2. Read `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_2_Baseline_comparator_redesign_and_score_integrity_recovery.md`.
3. Read `.apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_4_Atlas_hard_gate_clearance_and_blocker_burndown_report.md`.
4. Read `docs/qoder-repo-wiki-design-analysis.md` and `docs/operations/Qoder_Baseline_Comparison_Harness.md`.
5. Review existing compare fixture handling and baseline input assumptions.

**Producer Output Summary:**
- Task 11.2 stabilized comparator internals.
- Task 13.4 defines current Atlas acceptance gap and baseline needs.

**Integration Requirements:**
- Introduce external baseline fixture metadata and integrity checks.
- Keep deterministic ingest behavior and reproducible fixture normalization.
- Preserve explicit self-baseline mode as fallback, not default.

**User Clarification Protocol:**
If external fixture provenance cannot be validated from available metadata, stop and ask whether to mark fixture as non-gating reference only.

## Objective
Define and implement an external qoder-style snapshot fixture contract and ingestion pipeline for compare governance.

## Detailed Instructions
- Complete all items in one response.
- Design fixture schema with required metadata and integrity fields.
- Implement ingestion normalization for stable path and naming behavior.
- Reject incomplete or inconsistent fixture inputs with explicit diagnostics.
- Add tests for valid fixtures, partial fixtures, and malformed fixtures.
- Document fixture lifecycle and refresh policy.

## Expected Output
- Deliverables: fixture schema, ingestion utilities, validation logic, test coverage, documentation.
- Success criteria: compare can consume external fixture baselines deterministically and audibly.
- File locations: `scripts/**`, `repo_wiki/verifier/**`, `docs/operations/**`, tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance/Task_14_1_External_qoder_snapshot_fixture_contract_and_ingestion.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 14.2

```markdown
---
task_ref: "Task 14.2 - Comparator calibration with external baseline and weighted rubric"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance/Task_14_2_Comparator_calibration_with_external_baseline_and_weighted_rubric.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Comparator calibration with external baseline and weighted rubric

## Task Reference
Implementation Plan: **Task 14.2 - Comparator calibration with external baseline and weighted rubric** assigned to **Agent_QualityRelease**

## Context from Dependencies
This task depends on Task 14.1 implemented by Agent_QualityRelease.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance.md`.
2. Read `.apm/Memory/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance/Task_14_1_External_qoder_snapshot_fixture_contract_and_ingestion.md`.
3. Read `docs/qoder-repo-wiki-design-analysis.md` and `docs/qoder-repo-wiki-sqlite-analysis.md` as comparison references.
4. Review current compare dimension scoring implementation and report schema.
5. Review historical gap reports for score drift patterns.

**Producer Output Summary:**
- Task 14.1 provides external fixture input guarantees required for calibration.

**Integration Requirements:**
- Calibrate structural, narrative, and navigation dimensions with explicit weights.
- Prevent alias/overlay handling from inflating final scores.
- Keep explanation text and reason codes aligned with score computation.

**User Clarification Protocol:**
If weight tuning choices materially change historical pass/fail status, stop and ask whether to apply immediate threshold migration or dual-report transition mode.

## Objective
Recalibrate comparator scoring against external baselines and publish a weighted rubric suitable for replacement gating.

## Detailed Instructions
- Complete all items in one response.
- Define weighted dimensions with rationale and fallback behavior.
- Update comparator logic to consume external fixtures and weight profiles.
- Emit confidence metadata when extraction signals are weak.
- Recompute sample reports for regression comparison.
- Add tests proving score stability and anti-inflation behavior.

## Expected Output
- Deliverables: calibrated scoring model, weight profile definitions, updated reports, regression tests.
- Success criteria: comparator scores reflect meaningful external deltas and support policy-grade interpretation.
- File locations: compare scripts/services, schema definitions, docs, tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance/Task_14_2_Comparator_calibration_with_external_baseline_and_weighted_rubric.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 14.3

```markdown
---
task_ref: "Task 14.3 - Cross-repository benchmark matrix and threshold profiles"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance/Task_14_3_Cross_repository_benchmark_matrix_and_threshold_profiles.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Cross-repository benchmark matrix and threshold profiles

## Task Reference
Implementation Plan: **Task 14.3 - Cross-repository benchmark matrix and threshold profiles** assigned to **Agent_QualityRelease**

## Context from Dependencies
This task depends on Task 14.2 implemented by Agent_QualityRelease and Task 11.4 implemented by Agent_QualityRelease.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance.md`.
2. Read `.apm/Memory/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance/Task_14_2_Comparator_calibration_with_external_baseline_and_weighted_rubric.md`.
3. Read `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_4_Multi_repository_regression_acceptance.md`.
4. Review benchmark repository candidates and acceptance profiles.
5. Review output schema for comparative matrix reporting.

**Producer Output Summary:**
- Task 14.2 supplies calibrated scoring.
- Task 11.4 provides existing multi-repo acceptance baseline.

**Integration Requirements:**
- Build benchmark matrix on at least three repository shapes.
- Define profile thresholds for strict replacement, transitional adoption, and pilot mode.
- Preserve evidence traceability for each repository-profile result.

**User Clarification Protocol:**
If benchmark repository availability is insufficient for target sample size, stop and ask whether to proceed with provisional thresholds and explicit sample-risk flags.

## Objective
Create a cross-repository benchmark matrix and threshold profiles that can be reused by release gate policies.

## Detailed Instructions
- Complete all items in one response.
- Execute calibrated compare across selected benchmark repositories.
- Produce matrix output with dimension-level and overall scores.
- Define threshold profiles and expected actions per profile outcome.
- Record recurring gaps and repository-specific outliers separately.
- Add regression fixtures for profile evaluation logic.

## Expected Output
- Deliverables: benchmark matrix, threshold profiles, comparative reports, tests/docs.
- Success criteria: Manager can choose release profile with quantified cross-repository evidence.
- File locations: `docs/operations/**`, compare outputs, profile configs, tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance/Task_14_3_Cross_repository_benchmark_matrix_and_threshold_profiles.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 14.4

```markdown
---
task_ref: "Task 14.4 - SQLite-backed governance dashboard export and trends"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance/Task_14_4_SQLite_backed_governance_dashboard_export_and_trends.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: SQLite-backed governance dashboard export and trends

## Task Reference
Implementation Plan: **Task 14.4 - SQLite-backed governance dashboard export and trends** assigned to **Agent_IndexGraph**

## Context from Dependencies
This task depends on Task 12.3 implemented by Agent_IndexGraph and Task 14.3 implemented by Agent_QualityRelease.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance.md`.
2. Read `.apm/Memory/Phase_12_SQLite_First_Local_Knowledge_Runtime/Task_12_3_Verify_and_compare_persistence_with_trend_analysis.md`.
3. Read `.apm/Memory/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance/Task_14_3_Cross_repository_benchmark_matrix_and_threshold_profiles.md`.
4. Review current runtime evidence schema and report export utilities.
5. Review readiness and compare consumers that will read trend outputs.

**Producer Output Summary:**
- Task 12.3 stores run history and trend-ready data.
- Task 14.3 defines benchmark profiles and comparison contexts.

**Integration Requirements:**
- Export trend data by repository, profile, and reason family.
- Keep exports stable for CI and Manager reporting consumers.
- Preserve source evidence references for each reported metric.

**User Clarification Protocol:**
If export schema updates would break existing report consumers, stop and ask whether to introduce versioned export endpoints.

## Objective
Build SQLite-backed trend exports and governance dashboards that make multi-run quality evolution auditable.

## Detailed Instructions
- Complete all items in one response.
- Implement reproducible trend queries and machine-readable exports.
- Provide per-repo and cross-repo views for scores and gates.
- Link trend points to evidence bundle identifiers.
- Add regression tests for schema evolution and export stability.
- Document integration patterns for CI and Manager workflows.

## Expected Output
- Deliverables: trend query/export tools, dashboard artifacts, compatibility docs, tests.
- Success criteria: governance reporting can compare quality movement over time without manual aggregation.
- File locations: `repo_wiki/orchestration/**`, export scripts, docs, tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance/Task_14_4_SQLite_backed_governance_dashboard_export_and_trends.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```
