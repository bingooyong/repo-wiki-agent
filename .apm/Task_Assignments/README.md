# APM Manager Workflow Artifacts

本目录存放按 Phase 组织的 APM Manager Task Assignment 文件，直接服务于当前仓库的 `.apm/Implementation_Plan.md`。

## 使用顺序

1. 先阅读 `.claude/commands/apm-2-initiate-manager.md`
2. 再阅读以下 guides：
   - `.apm/guides/Memory_System_Guide.md`
   - `.apm/guides/Memory_Log_Guide.md`
   - `.apm/guides/Task_Assignment_Guide.md`
3. 按 Phase 顺序使用本目录中的 Task Assignment 文件
4. 对每个 task：
   - 把对应 code block 发给正确的 Implementation Agent
   - 等待该 agent 完成任务并写回指定 memory log
   - 由 Manager 审阅 log 后再推进下一个 task

## Phase 文件

- `Phase_01_Foundation_Security_and_Scanner_Contracts.md`
- `Phase_02_Local_Knowledge_Substrate_and_Retrieval_Pipeline.md`
- `Phase_03_Documentation_Generation_and_Command_Orchestration.md`
- `Phase_04_Adapter_Output_and_Verification.md`
- `Phase_05_Pilot_Acceptance_CI_Packaging_and_Release_Gate.md`
- `Phase_06_Information_Architecture_and_Document_Contract_Recovery.md`
- `Phase_07_Domain_Centered_Content_Generation.md`
- `Phase_08_Quality_Gates_and_Qoder_Baseline_Regression.md`
- `Phase_09_Output_Contract_and_Navigation_Hardening.md`
- `Phase_10_Narrative_and_Aggregation_Intelligence.md`
- `Phase_11_Acceptance_and_Baseline_Governance_Hardening.md`
- `Phase_12_SQLite_First_Local_Knowledge_Runtime.md`
- `Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance.md`
- `Phase_14_External_Baseline_Calibration_and_Benchmark_Governance.md`
- `Phase_15_Visual_Knowledge_Experience_and_IDE_Integration.md`
- `Phase_16_Qoder_Replacement_Cutover_and_Release_Gate.md`
- `Phase_17_Evidence_Integrity_and_CI_Gate_Repair.md`
- `Phase_18_Transitional_Quality_Uplift.md`
- `Phase_19_Viewer_and_IDE_Hardening.md`
- `Phase_20_Transitional_Release_Candidate_and_Strict_Gap_Plan.md`
- `Phase_21_LLM_Provider_Abstraction_and_Secure_Configuration.md`
- `Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture.md`
- `Phase_23_Evidence_Builder_with_File_and_Line_Citations.md`
- `Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles.md`
- `Phase_25_API_Reference_Specialization.md`
- `Phase_26_Data_Model_and_Database_Architecture_Specialization.md`
- `Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime.md`
- `Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update.md`
- `Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark.md`
- `Phase_30_Replacement_Candidate_Release_and_Documentation.md`
- `Phase_31_Strict_Gate_Closure_and_Freshness_Reliability.md`
- `Phase_32_Qoder_style_Information_Architecture_Deepening.md`
- `Phase_33_Evidence_Ranking_and_Hallucination_Control.md`
- `Phase_34_LLM_Composer_Quality_Loop.md`
- `Phase_35_Replacement_Candidate_Acceptance.md`
- `Phase_36_Eval_Run_Selection_and_Qoder_Baseline_Canonicalization.md`
- `Phase_37_Inventory_Service_API_Coverage_and_Ownership_Repair.md`
- `Phase_38_Mermaid_Backed_API_Article_Quality_Uplift.md`
- `Phase_39_Qoder_Comparison_and_Manual_Review_Hardening.md`
- `Phase_40_Final_Replacement_Readiness_Rerun_and_Dossier.md`
- `Phase_41_Qoder_compatible_Release_Interface_and_Meta_Contract.md`
- `Phase_42_Source_and_Documentation_Discovery_Compiler.md`
- `Phase_43_Knowledge_model_driven_IA_and_Page_Contract_Factory.md`
- `Phase_44_Evidence_backed_Composition_and_Diagram_Generation.md`
- `Phase_45_Product_Release_QA_and_Multi_repository_Acceptance.md`

## Reader-Facing 阶段文档

为避免 Manager 执行材料与人类阅读材料混在一起，新增 reader-facing 阶段文档：

- `docs/phases/Phase_06_Information_Architecture_and_Document_Contract_Recovery.md`
- `docs/phases/Phase_07_Domain_Centered_Content_Generation.md`
- `docs/phases/Phase_08_Quality_Gates_and_Qoder_Baseline_Regression.md`
- `docs/phases/Phase_09_Output_Contract_and_Navigation_Hardening.md`
- `docs/phases/Phase_10_Narrative_and_Aggregation_Intelligence.md`
- `docs/phases/Phase_11_Acceptance_and_Baseline_Governance_Hardening.md`
- `docs/phases/Phase_12_SQLite_First_Local_Knowledge_Runtime.md`
- `docs/phases/Phase_13_Atlas_Cutover_and_Hard_Gate_Clearance.md`
- `docs/phases/Phase_14_External_Baseline_Calibration_and_Benchmark_Governance.md`
- `docs/phases/Phase_15_Visual_Knowledge_Experience_and_IDE_Integration.md`
- `docs/phases/Phase_16_Qoder_Replacement_Cutover_and_Release_Gate.md`
- `docs/phases/Phase_17_Evidence_Integrity_and_CI_Gate_Repair.md`
- `docs/phases/Phase_18_Transitional_Quality_Uplift.md`
- `docs/phases/Phase_19_Viewer_and_IDE_Hardening.md`
- `docs/phases/Phase_20_Transitional_Release_Candidate_and_Strict_Gap_Plan.md`
- `docs/phases/Phase_21_LLM_Provider_Abstraction_and_Secure_Configuration.md`
- `docs/phases/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture.md`
- `docs/phases/Phase_23_Evidence_Builder_with_File_and_Line_Citations.md`
- `docs/phases/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles.md`
- `docs/phases/Phase_25_API_Reference_Specialization.md`
- `docs/phases/Phase_26_Data_Model_and_Database_Architecture_Specialization.md`
- `docs/phases/Phase_27_Qoder_compatible_Output_Layout_and_IDE_Runtime.md`
- `docs/phases/Phase_28_Generation_Orchestration_Cost_Control_and_Incremental_Update.md`
- `docs/phases/Phase_29_Quality_Governance_and_Qoder_Parity_Benchmark.md`
- `docs/phases/Phase_30_Replacement_Candidate_Release_and_Documentation.md`
- `docs/phases/Phase_31_Strict_Gate_Closure_and_Freshness_Reliability.md`
- `docs/phases/Phase_32_Qoder_style_Information_Architecture_Deepening.md`
- `docs/phases/Phase_33_Evidence_Ranking_and_Hallucination_Control.md`
- `docs/phases/Phase_34_LLM_Composer_Quality_Loop.md`
- `docs/phases/Phase_35_Replacement_Candidate_Acceptance.md`
- `docs/phases/Phase_36_Eval_Run_Selection_and_Qoder_Baseline_Canonicalization.md`
- `docs/phases/Phase_37_Inventory_Service_API_Coverage_and_Ownership_Repair.md`
- `docs/phases/Phase_38_Mermaid_Backed_API_Article_Quality_Uplift.md`
- `docs/phases/Phase_39_Qoder_Comparison_and_Manual_Review_Hardening.md`
- `docs/phases/Phase_40_Final_Replacement_Readiness_Rerun_and_Dossier.md`
- `docs/phases/Phase_41_Qoder_compatible_Release_Interface_and_Meta_Contract.md`
- `docs/phases/Phase_42_Source_and_Documentation_Discovery_Compiler.md`
- `docs/phases/Phase_43_Knowledge_model_driven_IA_and_Page_Contract_Factory.md`
- `docs/phases/Phase_44_Evidence_backed_Composition_and_Diagram_Generation.md`
- `docs/phases/Phase_45_Product_Release_QA_and_Multi_repository_Acceptance.md`

## Memory 结构

已按 APM Dynamic-MD 结构预置：

- `.apm/Memory/Memory_Root.md`
- `.apm/Memory/Phase_XX_<slug>/Task_Y_Z_<slug>.md`

所有 Phase 的 task log 文件都已预创建为空文件，便于 Manager 直接引用。
Phase 06-45 追加后，Manager 需要继续保持 `.apm/Implementation_Plan.md`、`.apm/Task_Assignments/`、`.apm/Memory/` 的编号与目录一致性，并明确区分“已执行但未退出的历史阶段”“纠偏基线阶段”“替代发布阶段”“证据修复/RC 阶段”“Qoder-like Repo Wiki replacement track”“Qoder replacement quality closure track”“post-acceptance correction track”和“source/docs intelligence productization track”。
