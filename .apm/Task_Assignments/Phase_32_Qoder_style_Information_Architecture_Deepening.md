# Phase 32 - Qoder-style Information Architecture Deepening

## Task 32.1

```markdown
---
task_ref: "Task 32.1 - Qoder baseline topic mining"
agent_assignment: "Agent_QualityRelease"
memory_log_path: ".apm/Memory/Phase_32_Qoder_style_Information_Architecture_Deepening/Task_32_1_Qoder_baseline_topic_mining.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Qoder baseline topic mining

## Task Reference
Implementation Plan: **Task 32.1 - Qoder baseline topic mining** assigned to **Agent_QualityRelease**

## Context from Dependencies
Depends on Task 31.4 and Task 29.2. Use the latest strict rerun package and comparator path model.

## Objective
Mine Qoder baseline directory patterns without copying Qoder content.

## Detailed Instructions
- Read `/Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas/.qoder/repowiki/zh/content` as a read-only baseline.
- Extract reusable topic, depth, and directory-shape patterns.
- Avoid copying Qoder page prose or proprietary implementation detail.
- Report target common-path improvements and gaps.

## Expected Output
- Deliverables: generalized topic taxonomy, path-pattern report, comparison gap notes.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_qoder_comparator_paths.py tests/test_qoder_parity_metrics.py`
- Completion rule: do not mark complete unless Qoder baseline remains unmodified.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_32_Qoder_style_Information_Architecture_Deepening/Task_32_1_Qoder_baseline_topic_mining.md`
```

## Task 32.2

```markdown
---
task_ref: "Task 32.2 - Service subtopic planner"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_32_Qoder_style_Information_Architecture_Deepening/Task_32_2_Service_subtopic_planner.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Service subtopic planner

## Task Reference
Implementation Plan: **Task 32.2 - Service subtopic planner** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 32.1 and Task 22.6. Use the mined taxonomy and existing page-plan persistence contract. Preserve Qoder's dedicated API台账服务 API topic as a required comparison target.

## Objective
Generate service subtopic plans instead of one page per service.

## Detailed Instructions
- Plan `服务概述`, `架构设计`, `API接口文档`, `部署配置`, and `核心组件` pages for Python services.
- Generate business subdomain pages for core services when evidence supports them.
- Generate a dedicated `API参考/核心服务API/API台账服务/API台账服务API.md` or equivalent stable page for `inventory-service`.
- Preserve stable slugs and manifest navigation ordering.
- Add planner tests for service subtopic expansion and API台账服务 API page coverage.

## Expected Output
- Deliverables: service subtopic planner, inventory-service API page plan, navigation updates, planner tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_qoder_like_planner.py tests/test_manifest_navigation.py`
- Completion rule: do not mark complete unless service plans expand into meaningful subtopics and API台账服务 has a dedicated API page.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_32_Qoder_style_Information_Architecture_Deepening/Task_32_2_Service_subtopic_planner.md`
```

## Task 32.3

```markdown
---
task_ref: "Task 32.3 - Data-model entity topic planner"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_32_Qoder_style_Information_Architecture_Deepening/Task_32_3_Data_model_entity_topic_planner.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Data-model entity topic planner

## Task Reference
Implementation Plan: **Task 32.3 - Data-model entity topic planner** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 32.2 and Task 26.3. Reuse service subtopic hierarchy and data-model topic planner contracts.

## Objective
Split data-model documentation into entity and persistence topics while eliminating duplicate pages.

## Detailed Instructions
- Generate entity, migration, table-structure, index-performance, audit, and security data-model topics.
- Eliminate duplicate pages such as `xxx 数据模型` and `xxx 数据模型-2`.
- Keep entity drill-down links connected to service-level pages.
- Add duplicate-topic regression tests.

## Expected Output
- Deliverables: data-model entity topic planner, duplicate-topic guard, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_data_model_topic_planner.py tests/test_qoder_like_planner.py`
- Completion rule: do not mark complete if duplicate data-model page plans remain.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_32_Qoder_style_Information_Architecture_Deepening/Task_32_3_Data_model_entity_topic_planner.md`
```

## Task 32.4

```markdown
---
task_ref: "Task 32.4 - Project overview module hierarchy"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_32_Qoder_style_Information_Architecture_Deepening/Task_32_4_Project_overview_module_hierarchy.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Project overview module hierarchy

## Task Reference
Implementation Plan: **Task 32.4 - Project overview module hierarchy** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 32.3. Use service and data-model topic plans to build the project overview module hierarchy.

## Objective
Generate a Qoder-depth project overview and module organization hierarchy.

## Detailed Instructions
- Target directory depth of `4` with non-empty topic pages.
- Increase Qoder path common count from the current baseline toward at least `80`.
- Keep repo-agent page count within `90%-120%` of Qoder page count.
- Treat missing Qoder baseline counterparts such as `API参考/核心服务API/API台账服务API.md` as explicit comparison gaps.
- Add hierarchy fixture tests and AI_API_Atlas path comparison evidence.

## Expected Output
- Deliverables: module hierarchy planner, navigation metadata, path comparison evidence.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_qoder_like_planner.py tests/test_qoder_comparator_paths.py`
- Completion rule: do not mark complete unless hierarchy depth and duplicate-page assertions are tested.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_32_Qoder_style_Information_Architecture_Deepening/Task_32_4_Project_overview_module_hierarchy.md`
```
