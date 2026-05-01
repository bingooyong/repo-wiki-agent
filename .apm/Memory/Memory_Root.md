# repo-wiki – APM Memory Root
**Memory Strategy:** Dynamic-MD
**Project Overview:** Build the repo-wiki MVP as a local-first CLI that scans backend repositories, writes source-of-truth artifacts, maintains SQLite plus FTS5 state, ChromaDB vectors, and a module graph, then generates docs and AI adapter files with incremental update and verify support.

## Phase 01 – Foundation, Security, and Scanner Contracts Summary
- Outcome summary: Established the CLI/config/contracts baseline, moved security filtering ahead of all derived artifacts, and completed deterministic scanner extraction plus schema-valid `source-of-truth` writing.
- Involved Agents: `Agent_PlatformCore`, `Agent_Scanner`
- Logs: `.apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_1_CLI_skeleton_config_foundation_and_core_contracts.md`, `.apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_2_Security_filtering_and_redaction_foundation.md`, `.apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_3_Repository_traversal_language_detection_and_module_discovery.md`, `.apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_4_Ownership_dependency_API_and_data_model_extraction.md`, `.apm/Memory/Phase_01_Foundation_Security_and_Scanner_Contracts/Task_1_5_Source_of_truth_artifact_writer_and_schema_validation.md`

## Phase 02 – Local Knowledge Substrate and Retrieval Pipeline Summary
- Outcome summary: Added SQLite/FTS state, semantic chunking and vector persistence, module graph artifacts, and the layered retrieval plus incremental impact path required by `search` and `update`.
- Involved Agents: `Agent_IndexGraph`
- Logs: `.apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_1_SQLite_state_and_FTS_foundation.md`, `.apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_2_Chunking_and_semantic_vector_index.md`, `.apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_3_Module_level_knowledge_graph_and_impact_cache.md`, `.apm/Memory/Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline/Task_2_4_Retrieval_pipeline_and_incremental_impact_analyzer.md`

## Phase 03 – Documentation Generation and Command Orchestration Summary
- Outcome summary: Delivered the frozen MVP document contracts, context-aware generation engine, cache strategy, and end-to-end command orchestration for `init`, `update`, `index`, `search`, `graph`, and `cost-estimate`.
- Involved Agents: `Agent_DocGen`, `Agent_PlatformCore`
- Logs: `.apm/Memory/Phase_03_Documentation_Generation_and_Command_Orchestration/Task_3_1_Template_system_and_document_contracts.md`, `.apm/Memory/Phase_03_Documentation_Generation_and_Command_Orchestration/Task_3_2_Generation_engine_cache_and_token_budgeted_context_builder.md`, `.apm/Memory/Phase_03_Documentation_Generation_and_Command_Orchestration/Task_3_3_Core_command_orchestration_for_init_update_index_search_graph_and_cost_estimate.md`

## Phase 04 – Adapter Output and Verification Summary
- Outcome summary: Generated minimal multi-tool adapter outputs and implemented the frozen MVP `verify --ci` contract, including path integrity and stale-doc governance checks.
- Involved Agents: `Agent_AdapterGovernance`
- Logs: `.apm/Memory/Phase_04_Adapter_Output_and_Verification/Task_4_1_Multi_tool_adapter_generation_and_sync_command.md`, `.apm/Memory/Phase_04_Adapter_Output_and_Verification/Task_4_2_Verify_command_and_CI_mode_governance_checks.md`

## Phase 05 – Pilot Acceptance, CI Packaging, and Release Gate Summary
- Outcome summary: Added pilot acceptance workflows, CI/governance packaging, and the initial readiness gate report, leaving the product functionally complete but with clear quality/readability gaps versus qoder-style output.
- Involved Agents: `Agent_QualityRelease`
- Logs: `.apm/Memory/Phase_05_Pilot_Acceptance_CI_Packaging_and_Release_Gate/Task_5_1_Pilot_acceptance_protocol_and_metric_instrumentation.md`, `.apm/Memory/Phase_05_Pilot_Acceptance_CI_Packaging_and_Release_Gate/Task_5_2_CI_automation_and_governance_packaging.md`, `.apm/Memory/Phase_05_Pilot_Acceptance_CI_Packaging_and_Release_Gate/Task_5_3_Final_readiness_review_and_release_gate_report.md`

## Phase 06 – Information Architecture and Document Contract Recovery Summary
- Outcome summary: Refactored document output contracts to introduce four-layer document center architecture (overview/section/module/phase), added business-domain classification metadata (domain/service_family/runtime_role), upgraded overview to prose-first introduction page with fixed sections, and restored architecture as Mermaid-backed three-layer design document.
- Involved Agents: `Agent_DocGen`
- Logs: `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_1_Document_output_contract_refactor_and_document_center_layer.md`, `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_2_Business_domain_classifier_and_module_mapping_contracts.md`, `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_3_Prose_first_overview_contract_and_generation_upgrade.md`, `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_4_Architecture_contract_recovery_and_three_layer_Mermaid_design.md`
- Manager judgment: `Conditional Pass`. Follow-up required in Phase 09 to separate governance-vs-target outputs and complete registry/path contracts.

## Phase 07 – Domain-Centered Content Generation Summary
- Outcome summary: Replaced flat module/API/data-model docs with domain-organized outputs (domain groups, API service groupings, aggregated data models), generated section pages for project/architecture/services/data-model/api/operations/development/security with cross-links, and added validation ensuring content is aggregated rather than raw dumps.
- Involved Agents: `Agent_DocGen`
- Logs: `.apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_1_Domain_centered_module_map_generation.md`, `.apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_2_Aggregated_API_contracts_generation.md`, `.apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_3_Domain_aggregated_data_model_generation.md`, `.apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_4_Section_page_generation_and_navigation_stitching.md`
- Manager judgment: `Fail to Exit`. Follow-up required in Phase 10 because API, data-model, and section outputs still lean too heavily on enumerative export patterns.

## Phase 08 – Quality Gates and Qoder Baseline Regression Summary
- Outcome summary: Upgraded verify --ci from existence checks to content-quality governance with reason codes, built qoder baseline comparison harness for 6-dimension gap analysis, and ran acceptance on AI_API_Atlas producing a readiness report with remaining quality gaps.
- Involved Agents: `Agent_AdapterGovernance`, `Agent_QualityRelease`
- Logs: `.apm/Memory/Phase_08_Quality_Gates_and_Qoder_Baseline_Regression/Task_8_1_Content_quality_verify_and_CI_gate_upgrade.md`, `.apm/Memory/Phase_08_Quality_Gates_and_Qoder_Baseline_Regression/Task_8_2_Qoder_baseline_regression_harness_and_gap_report.md`, `.apm/Memory/Phase_08_Quality_Gates_and_Qoder_Baseline_Regression/Task_8_3_AI_API_Atlas_regeneration_acceptance_and_readiness_report.md`
- Manager judgment: `Fail to Exit`. Follow-up required in Phase 11 because verify and compare are informative but not yet trustworthy enough for replacement-readiness decisions.

## Phase 09 – Output Contract and Navigation Hardening Summary
- Outcome summary: Separated repo-agent governance docs from target repository outputs with OutputLayerPolicy, implemented unified link builder replacing brittle relative-link assembly, completed phase/section registry with alias support for non-canonical formats (Q01/S01), and upgraded verify --ci to path-resolved navigation checks with precise reason codes.
- Involved Agents: `Agent_DocGen`, `Agent_AdapterGovernance`
- Logs: `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_1_Target_output_boundary_and_governance_layer_separation.md`, `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_2_Unified_link_builder_and_path_contract_recovery.md`, `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_3_Phase_and_section_registry_completion_with_alias_support.md`, `.apm/Memory/Phase_09_Output_Contract_and_Navigation_Hardening/Task_9_4_Path_aware_verify_navigation_checks.md`

## Phase 10 – Narrative and Aggregation Intelligence Summary
- Outcome summary: Replaced template-based overview/architecture/API/data-model content with repository-specific narrative builders, implemented core entity identification and migration-aware aggregation, rewrote section page builder with SectionNarrativeBuilder and ReadingPathGenerator for true document-center behavior, and added 21 new tests.
- Involved Agents: `Agent_DocGen`
- Logs: `.apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_1_Narrative_builder_for_overview_and_architecture.md`, `.apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_2_True_API_aggregation_and_entry_point_summarization.md`, `.apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_3_Core_entity_and_migration_aware_data_model_aggregation.md`, `.apm/Memory/Phase_10_Narrative_and_Aggregation_Intelligence/Task_10_4_Section_page_builder_rewrite_for_document_center_behavior.md`

## Phase 11 – Acceptance and Baseline Governance Hardening Summary
- Outcome summary: Redesigned verify with hard/soft gate distinction and configurable severity thresholds, rebuilt baseline comparator with DeltaType/ScoreBand enums distinguishing structural vs quality deltas, created unified readiness report schema with evidence bundling, ran multi-repository acceptance on repo-agent and AI_API_Atlas with 46 tests passing.
- Involved Agents: `Agent_AdapterGovernance`, `Agent_QualityRelease`
- Logs: `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_1_Hard_gate_vs_soft_gate_verify_redesign.md`, `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_2_Baseline_comparator_redesign_and_score_integrity_recovery.md`, `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_3_Unified_readiness_report_schema_and_evidence_bundle.md`, `.apm/Memory/Phase_11_Acceptance_and_Baseline_Governance_Hardening/Task_11_4_Multi_repository_regression_acceptance.md`

## Phase 12 – SQLite-First Local Knowledge Runtime Summary
- Outcome summary: Implemented dual-database architecture (state.sqlite3 vs runtime.sqlite3), extended SQLite schema for doc hierarchy, section registry, nav graph, and evidence persistence, added verify/compare run persistence with trend analysis queries, and built PageInvalidationEngine with Kahn's algorithm for incremental regeneration driven by SQLite state.
- Involved Agents: `Agent_IndexGraph`
- Logs: `.apm/Memory/Phase_12_SQLite_First_Local_Knowledge_Runtime/Task_12_1_Dual_database_runtime_architecture_for_state_and_evidence.md`, `.apm/Memory/Phase_12_SQLite_First_Local_Knowledge_Runtime/Task_12_2_SQLite_schema_for_hierarchy_sections_navigation_and_evidence.md`, `.apm/Memory/Phase_12_SQLite_First_Local_Knowledge_Runtime/Task_12_3_Verify_and_compare_persistence_with_trend_analysis.md`, `.apm/Memory/Phase_12_SQLite_First_Local_Knowledge_Runtime/Task_12_4_SQLite_driven_page_invalidation_and_incremental_regeneration.md`

## Phase 13 – Atlas Cutover and Hard-Gate Clearance Summary
- Outcome summary: Integrated runtime SQLite orchestration into core commands, implemented Q*/S* section compatibility bridge with alias resolution, remediated Atlas core docs (prose 135→3470 chars, 4 Mermaid diagrams), and achieved 0 hard gate failures with WARN grade.
- Involved Agents: `Agent_IndexGraph`, `Agent_DocGen`, `Agent_QualityRelease`
- Logs: `.apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_1_Runtime_store_orchestration_integration_across_core_commands.md`, `.apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_2_Section_compatibility_bridge_for_Q_and_S_formats.md`, `.apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_3_Atlas_core_document_narrative_and_aggregation_remediation.md`, `.apm/Memory/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance/Task_13_4_Atlas_hard_gate_clearance_and_blocker_burndown_report.md`

## Phase 14 – External Baseline Calibration and Benchmark Governance Summary
- Outcome summary: Implemented external qoder fixture schema with VALID/PARTIAL/INVALID states, calibrated comparator with structural (0.60) vs quality (0.40) weighting, built cross-repository threshold profiles by language/size/complexity, and delivered SQLite-backed governance dashboard with trend analysis.
- Involved Agents: `Agent_QualityRelease`, `Agent_IndexGraph`
- Logs: `.apm/Memory/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance/Task_14_1_External_qoder_snapshot_fixture_contract_and_ingestion.md`, `.apm/Memory/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance/Task_14_2_Comparator_calibration_with_external_baseline_and_weighted_rubric.md`, `.apm/Memory/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance/Task_14_3_Cross_repository_benchmark_matrix_and_threshold_profiles.md`, `.apm/Memory/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance/Task_14_4_SQLite_backed_governance_dashboard_export_and_trends.md`

## Phase 15 – Visual Knowledge Experience and IDE Integration Summary
- Outcome summary: Delivered isolated eval output layout (`.repo-agent-eval`) with manifest support, static HTML viewer with tree navigation and Mermaid rendering, VS Code extension prototype for wiki browsing, and qoder-style navigation metadata import bridge.
- Involved Agents: `Agent_PlatformCore`, `Agent_AdapterGovernance`
- Logs: `.apm/Memory/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration/Task_15_1_Isolated_eval_output_layout_and_manifest_for_target_repos.md`, `.apm/Memory/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration/Task_15_2_Static_repo_wiki_viewer_with_tree_navigation_and_mermaid_rendering.md`, `.apm/Memory/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration/Task_15_3_VS_Code_extension_prototype_for_repo_agent_wiki_browsing.md`, `.apm/Memory/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration/Task_15_4_Qoder_style_navigation_metadata_adapter_and_import_bridge.md`

## Phase 16 – Qoder-Replacement Cutover and Release Gate Summary
- Outcome summary: Executed final pilot across Atlas and benchmark repos (score: 50.2% ACCEPTABLE, not meeting transitional 70% or strict 85%), produced go/no-go dossier with CONDITIONAL NO-GO decision, documented improvement roadmap for prose density, section coverage, and heading coverage gaps.
- Involved Agents: `Agent_QualityRelease`, `Agent_AdapterGovernance`
- Logs: `.apm/Memory/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate/Task_16_1_Replacement_gate_policy_and_rollback_playbook.md`, `.apm/Memory/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate/Task_16_2_CI_cutover_template_pack_and_policy_profiles.md`, `.apm/Memory/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate/Task_16_3_Final_pilot_execution_across_Atlas_and_benchmark_repositories.md`, `.apm/Memory/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate/Task_16_4_Go_no_go_decision_dossier_and_handover_package.md`

## Phase 17 – Evidence Integrity and CI Gate Repair Summary
- Outcome summary: Completed CI gate enforcement (removed `|| true` from strict/transitional workflows), fixed Python packaging (explicit pyproject.toml package discovery), added governance regression tests (12 tests in test_governance_regression.py), and fixed BaselineComparatorConfig.to_dict() NameError.
- Involved Agents: `Agent_QualityRelease`, `Agent_AdapterGovernance`, `Agent_PlatformCore`
- Logs: `.apm/Memory/Phase_17_Evidence_Integrity_and_CI_Gate_Repair/Task_17_1_Decision_evidence_reconciliation_and_dossier_canonicalization.md`, `.apm/Memory/Phase_17_Evidence_Integrity_and_CI_Gate_Repair/Task_17_2_CI_decision_gate_enforcement_and_workflow_correctness.md`, `.apm/Memory/Phase_17_Evidence_Integrity_and_CI_Gate_Repair/Task_17_3_Python_packaging_and_reproducible_test_harness_repair.md`, `.apm/Memory/Phase_17_Evidence_Integrity_and_CI_Gate_Repair/Task_17_4_Governance_regression_tests_for_known_review_failures.md`
- Manager judgment: `Completed`. CI gates now enforce policy outcomes correctly.

## Phase 18 – Transitional Quality Uplift Summary
- Outcome summary: Achieved overall score 92% EXCELLENT (vs 70% threshold), added troubleshooting section, fixed heading coverage (核心数据流→核心链路), added narrative prose to SectionNarrativeBuilder, improved API/DataModel aggregation.
- Involved Agents: `Agent_DocGen`, `Agent_QualityRelease`
- Logs: `.apm/Memory/Phase_18_Transitional_Quality_Uplift/Task_18_1_Section_coverage_completion_and_navigation_contract_repair.md`, `.apm/Memory/Phase_18_Transitional_Quality_Uplift/Task_18_2_Heading_coverage_and_prose_density_generation_upgrade.md`, `.apm/Memory/Phase_18_Transitional_Quality_Uplift/Task_18_3_API_and_data_model_aggregation_depth_refinement.md`, `.apm/Memory/Phase_18_Transitional_Quality_Uplift/Task_18_4_Transitional_acceptance_rerun_and_quality_burndown.md`
- Manager judgment: `GO for Phase 19`. Transitional threshold met with 92% score.

## Phase 19 – Viewer and IDE Hardening Summary
- Outcome summary: Added offline Mermaid support (get_mermaid_script with local path), fixed VS Code extension path resolution and manifest discovery, added Q01/S01 format support, created 23 visual acceptance tests, added side-by-side qoder comparison.
- Involved Agents: `Agent_PlatformCore`, `Agent_QualityRelease`, `Agent_AdapterGovernance`
- Logs: `.apm/Memory/Phase_19_Viewer_and_IDE_Hardening/Task_19_1_Static_viewer_offline_asset_and_safety_hardening.md`, `.apm/Memory/Phase_19_Viewer_and_IDE_Hardening/Task_19_2_VS_Code_extension_runtime_path_and_manifest_discovery_repair.md`, `.apm/Memory/Phase_19_Viewer_and_IDE_Hardening/Task_19_3_Visual_acceptance_snapshots_and_navigation_regression_suite.md`, `.apm/Memory/Phase_19_Viewer_and_IDE_Hardening/Task_19_4_Qoder_side_by_side_navigation_comparison_hardening.md`
- Manager judgment: `Completed`. Viewer works offline, extension opens correct files, 106 tests pass.

## Phase 20 – Transitional Release Candidate and Strict Gap Plan Summary
- Outcome summary: Formalized external fixture provenance with FreshnessValidator and ConfidenceScorer, executed release-candidate pilot (score: 13.4%), produced strict-gap backlog with 7 generator items and 4 extra items for reaching 85%, and issued transitional NO-GO with strict pending evidence.
- Involved Agents: `Agent_QualityRelease`
- Logs: `.apm/Memory/Phase_20_Transitional_Release_Candidate_and_Strict_Gap_Plan/Task_20_1_External_fixture_provenance_and_benchmark_refresh_policy.md`, `.apm/Memory/Phase_20_Transitional_Release_Candidate_and_Strict_Gap_Plan/Task_20_2_Release_candidate_pilot_across_benchmark_repositories.md`, `.apm/Memory/Phase_20_Transitional_Release_Candidate_and_Strict_Gap_Plan/Task_20_3_Strict_threshold_gap_backlog_and_ownership_plan.md`, `.apm/Memory/Phase_20_Transitional_Release_Candidate_and_Strict_Gap_Plan/Task_20_4_Transitional_go_no_go_dossier_and_manager_handover.md`
- Manager judgment: `Conditional GO - Transitional`. Pilot profile allowed; strict production replacement blocked pending Phase 21-23 execution.

## Phase 21 – LLM Provider Abstraction and Secure Configuration Summary
- Outcome summary: `Completed`. LLM config schema with env resolution and secret redaction, provider interface (LLMClient, ChatRequest, ChatResponse), OpenAI-compatible and Minimax providers, token budgeting/retry/cache policy, CLI diagnostics (`repo-wiki config`).
- Involved Agents: `Agent_PlatformCore`, `Agent_AdapterGovernance`
- Logs: `.apm/Memory/Phase_21_LLM_Provider_Abstraction_and_Secure_Configuration/Task_21_1_LLM_config_schema_and_environment_resolution.md`, `.apm/Memory/Phase_21_LLM_Provider_Abstraction_and_Secure_Configuration/Task_21_2_Provider_interface_and_request_response_contract.md`, `.apm/Memory/Phase_21_LLM_Provider_Abstraction_and_Secure_Configuration/Task_21_3_OpenAI_compatible_and_Minimax_provider_implementation.md`, `.apm/Memory/Phase_21_LLM_Provider_Abstraction_and_Secure_Configuration/Task_21_4_Token_budgeting_retry_and_cache_policy.md`, `.apm/Memory/Phase_21_LLM_Provider_Abstraction_and_Secure_Configuration/Task_21_5_CLI_configuration_validation_and_diagnostics.md`
- Manager judgment: `Completed`. 103 Phase 21 tests pass. Mock provider coverage and secret-safe diagnostics implemented.

## Phase 22 – Qoder-like Wiki Planner and Chinese Information Architecture Summary
- Outcome summary: `Completed`. Wiki page-plan schema (WikiPlanManifest, NavNode, 11 Chinese categories), Chinese taxonomy baseline, repository identity resolver, rule-first planner (81 pages for AI_API_Atlas), LLM-assisted planner (120+ pages), SQLite and manifest persistence.
- Involved Agents: `Agent_DocGen`, `Agent_Scanner`, `Agent_IndexGraph`
- Logs: `.apm/Memory/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture/Task_22_1_Wiki_page_plan_schema_and_navigation_tree_contract.md`, `.apm/Memory/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture/Task_22_2_Chinese_taxonomy_baseline_for_Qoder_like_output.md`, `.apm/Memory/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture/Task_22_3_Repository_identity_resolver.md`, `.apm/Memory/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture/Task_22_4_Rule_first_page_planner.md`, `.apm/Memory/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture/Task_22_5_LLM_assisted_page_planner.md`, `.apm/Memory/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture/Task_22_6_Planner_persistence_into_SQLite_and_manifest.md`
- Manager judgment: `Completed`. 574 tests pass. AI_API_Atlas page planning at Qoder-like scale (81 rule-first, 120+ LLM-assisted) and manifest-backed navigation achieved.

## Phase 23 – Evidence Builder with File and Line Citations Summary
- Outcome summary: `Completed`. Source span extractor (Java/Python/TypeScript/SQL/YAML/Markdown), Evidence SQLite schema (evidence_span, page_source_map, symbol_reference tables), evidence ranking pipeline with page-source bindings, citation block renderer, citation verifier with WARN/FAIL gates.
- Involved Agents: `Agent_Scanner`, `Agent_IndexGraph`, `Agent_DocGen`, `Agent_AdapterGovernance`
- Logs: `.apm/Memory/Phase_23_Evidence_Builder_with_File_and_Line_Citations/Task_23_1_Source_span_extractor_for_Java_Python_TypeScript_SQL_YAML_Markdown.md`, `.apm/Memory/Phase_23_Evidence_Builder_with_File_and_Line_Citations/Task_23_2_Evidence_SQLite_schema.md`, `.apm/Memory/Phase_23_Evidence_Builder_with_File_and_Line_Citations/Task_23_3_Evidence_ranking_and_page_matching.md`, `.apm/Memory/Phase_23_Evidence_Builder_with_File_and_Line_Citations/Task_23_4_Citation_block_renderer.md`, `.apm/Memory/Phase_23_Evidence_Builder_with_File_and_Line_Citations/Task_23_5_Citation_verifier.md`
- Manager judgment: `Completed`. 720 tests pass. Resolvable file/line citations and verify coverage for broken citation cases implemented.

## Phase 24 – LLM Page Composer and Qoder-style Markdown Articles Summary
- Outcome summary: `Completed`. Prompt contracts (7 page types), skeleton builder with TOC, LLM page composer pipeline, Mermaid diagram planner/renderer (6 diagram types), quality guardrails (7 checks), incremental cache with input/output hashing.
- Involved Agents: `Agent_DocGen`, `Agent_AdapterGovernance`, `Agent_IndexGraph`
- Logs: `.apm/Memory/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles/Task_24_1_Page_prompt_contract_and_prompt_fragments.md`, `.apm/Memory/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles/Task_24_2_Qoder_style_article_skeleton.md`, `.apm/Memory/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles/Task_24_3_LLM_page_composer_pipeline.md`, `.apm/Memory/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles/Task_24_4_Mermaid_diagram_planner_and_renderer.md`, `.apm/Memory/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles/Task_24_5_Quality_guardrails_for_hallucination_and_generic_prose.md`, `.apm/Memory/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles/Task_24_6_Page_composer_incremental_cache.md`
- Manager judgment: `Completed`. 948 tests pass. Mock-LLM composer tests and page-level cache behavior implemented.

## Phase 25 – API Reference Specialization Summary
- Outcome summary: `Completed`. API inventory enrichment (service_family, auth, request/response metadata), API topic planner (15+ pages grouped by service family), service-family API composer (prose-first articles), auth/error convention generator, API flow diagram generator (sequence diagrams), API quality verifier (endpoint-dump detection, reason codes AGG_API_NOT_GROUPED/AGG_API_ENDPOINT_DUMP).
- Involved Agents: `Agent_Scanner`, `Agent_DocGen`, `Agent_AdapterGovernance`
- Logs: `.apm/Memory/Phase_25_API_Reference_Specialization/Task_25_1_API_inventory_enrichment.md`, `.apm/Memory/Phase_25_API_Reference_Specialization/Task_25_2_API_topic_planner.md`, `.apm/Memory/Phase_25_API_Reference_Specialization/Task_25_3_Service_family_API_composer.md`, `.apm/Memory/Phase_25_API_Reference_Specialization/Task_25_4_Auth_and_error_convention_generator.md`, `.apm/Memory/Phase_25_API_Reference_Specialization/Task_25_5_API_flow_diagram_generation.md`, `.apm/Memory/Phase_25_API_Reference_Specialization/Task_25_6_API_quality_verifier.md`
- Manager judgment: `Completed`. 1102 tests pass. Prose-first API articles and strict verifier reject endpoint dump regressions.

## Phase 26 – Data Model and Database Architecture Specialization Summary
- Outcome summary: `Completed`. Canonical model resolver (core entity/DTO/RequestResponse distinction), database migration extractor (SQL/Alembic), data model topic planner (10+ pages), entity relationship composer with ER diagrams, service data model composer, data model quality verifier (AGG_DM_MODEL_DUMP/AGG_DM_NOT_GROUPED).
- Involved Agents: `Agent_Scanner`, `Agent_DocGen`, `Agent_AdapterGovernance`
- Logs: `.apm/Memory/Phase_26_Data_Model_and_Database_Architecture_Specialization/Task_26_1_Entity_deduplication_and_canonical_model_resolver.md`, `.apm/Memory/Phase_26_Data_Model_and_Database_Architecture_Specialization/Task_26_2_Database_migration_and_table_extractor.md`, `.apm/Memory/Phase_26_Data_Model_and_Database_Architecture_Specialization/Task_26_3_Data_model_topic_planner.md`, `.apm/Memory/Phase_26_Data_Model_and_Database_Architecture_Specialization/Task_26_4_Entity_relationship_composer.md`, `.apm/Memory/Phase_26_Data_Model_and_Database_Architecture_Specialization/Task_26_5_Service_data_model_composer.md`, `.apm/Memory/Phase_26_Data_Model_and_Database_Architecture_Specialization/Task_26_6_Data_model_quality_verifier.md`
- Manager judgment: `Completed`. 1252 tests pass. Data-model pages avoid raw dumps with relationship/storage evidence.

## Phase 27 – Qoder-compatible Output Layout and IDE Runtime Summary
- Outcome summary: `Planned`. This phase aligns isolated output layout, manifest navigation, VS Code extension behavior, Markdown preview, stale prompts, and static viewer parity.
- Involved Agents: `Agent_PlatformCore`, `Agent_DocGen`, `Agent_IndexGraph`
- Logs: `.apm/Memory/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime/Task_27_1_Qoder_like_output_profile.md`, `.apm/Memory/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime/Task_27_2_Content_layout_writer.md`, `.apm/Memory/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime/Task_27_3_Manifest_navigation_tree_and_commit_metadata.md`, `.apm/Memory/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime/Task_27_4_VS_Code_extension_nav_tree_integration.md`, `.apm/Memory/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime/Task_27_5_Markdown_preview_and_stale_wiki_UX.md`, `.apm/Memory/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime/Task_27_6_Static_viewer_parity_pass.md`
- Manager judgment: `Planned`. Exit requires qoder-like output profile, manifest-driven IDE tree, Markdown preview, and stale update UX.

## Phase 28 – Generation Orchestration, Cost Control, and Incremental Update Summary
- Outcome summary: `Planned`. This phase makes Qoder-like generation resumable, budget-aware, rate-limited, partially recoverable, and incrementally updatable.
- Involved Agents: `Agent_IndexGraph`, `Agent_PlatformCore`, `Agent_QualityRelease`
- Logs: `.apm/Memory/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update/Task_28_1_Generation_run_state_machine.md`, `.apm/Memory/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update/Task_28_2_LLM_cost_estimator_and_budget_gate.md`, `.apm/Memory/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update/Task_28_3_Concurrent_generation_scheduler.md`, `.apm/Memory/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update/Task_28_4_Page_level_invalidation_from_git_diff_and_hash_fallback.md`, `.apm/Memory/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update/Task_28_5_Failure_recovery_and_partial_evidence_bundle.md`, `.apm/Memory/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update/Task_28_6_update_integration_for_qoder_like_profile.md`
- Manager judgment: `Planned`. Exit requires resumable generation and page-level invalidation.

## Phase 29 – Quality Governance and Qoder Parity Benchmark Summary
- Outcome summary: `Planned`. This phase defines Qoder parity metrics, repairs comparator path models, adds strict qoder-like verification, builds golden fixtures, reruns AI_API_Atlas parity, and persists trends.
- Involved Agents: `Agent_QualityRelease`, `Agent_AdapterGovernance`, `Agent_IndexGraph`
- Logs: `.apm/Memory/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark/Task_29_1_Qoder_parity_metric_schema.md`, `.apm/Memory/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark/Task_29_2_Comparator_path_model_repair.md`, `.apm/Memory/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark/Task_29_3_Strict_verifier_for_qoder_like_profile.md`, `.apm/Memory/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark/Task_29_4_Golden_fixture_suite.md`, `.apm/Memory/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark/Task_29_5_AI_API_Atlas_qoder_parity_rerun.md`, `.apm/Memory/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark/Task_29_6_Regression_dashboard_and_trend_persistence.md`
- Manager judgment: `Planned`. Exit requires credible AI_API_Atlas gap matrix and strict verifier coverage.

## Phase 30 – Replacement Candidate Release and Documentation Summary
- Outcome summary: `Planned`. This phase packages configuration docs, install/extension workflow, AI_API_Atlas pilot, multi-repo pilot, release gate, rollback, and final go/no-go dossier.
- Involved Agents: `Agent_QualityRelease`, `Agent_PlatformCore`, `Agent_AdapterGovernance`
- Logs: `.apm/Memory/Phase_30_Replacement_Candidate_Release_and_Documentation/Task_30_1_End_user_configuration_documentation.md`, `.apm/Memory/Phase_30_Replacement_Candidate_Release_and_Documentation/Task_30_2_Installation_and_VS_Code_extension_workflow.md`, `.apm/Memory/Phase_30_Replacement_Candidate_Release_and_Documentation/Task_30_3_AI_API_Atlas_full_replacement_pilot.md`, `.apm/Memory/Phase_30_Replacement_Candidate_Release_and_Documentation/Task_30_4_Multi_repository_replacement_pilot.md`, `.apm/Memory/Phase_30_Replacement_Candidate_Release_and_Documentation/Task_30_5_Release_gate_and_rollback_plan.md`, `.apm/Memory/Phase_30_Replacement_Candidate_Release_and_Documentation/Task_30_6_Final_go_no_go_dossier.md`
- Manager judgment: `Planned`. Exit requires final evidence-backed go/no-go on replacing Qoder Repo Wiki for target usage.
