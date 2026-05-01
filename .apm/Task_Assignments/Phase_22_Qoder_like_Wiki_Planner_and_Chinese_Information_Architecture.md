# Phase 22 - Qoder-like Wiki Planner and Chinese Information Architecture

## Task 22.1

```markdown
---
task_ref: "Task 22.1 - Wiki page-plan schema and navigation tree contract"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture/Task_22_1_Wiki_page_plan_schema_and_navigation_tree_contract.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Wiki page-plan schema and navigation tree contract

## Task Reference
Implementation Plan: **Task 22.1 - Wiki page-plan schema and navigation tree contract** assigned to **Agent_DocGen**

## Context from Dependencies
Read `docs/phases/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture.md` and Phase 21 completion logs before starting.

## Objective
Define `wiki-plan.json` and manifest navigation tree contracts.

## Detailed Instructions
- Define page id, title, category, parent, output path, source requirements, and generation mode.
- Define manifest navigation nodes for IDE/static viewer consumption.
- Add schema validation and compatibility tests.

## Expected Output
- Deliverables: page-plan schema, navigation tree contract, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_wiki_plan_schema.py tests/test_manifest_navigation.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture/Task_22_1_Wiki_page_plan_schema_and_navigation_tree_contract.md`
```

## Task 22.2

```markdown
---
task_ref: "Task 22.2 - Chinese taxonomy baseline for Qoder-like output"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture/Task_22_2_Chinese_taxonomy_baseline_for_Qoder_like_output.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Chinese taxonomy baseline for Qoder-like output

## Task Reference
Implementation Plan: **Task 22.2 - Chinese taxonomy baseline for Qoder-like output** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 22.1. Reuse the page-plan and navigation contracts.

## Objective
Add the default Chinese taxonomy for Qoder-like output.

## Detailed Instructions
- Add top-level categories: 项目概述、架构设计、核心服务、Python服务、前端应用、数据模型、API参考、部署运维、开发指南、安全合规、故障排除.
- Make taxonomy profile-configurable without breaking qoder-like defaults.
- Add AI_API_Atlas planning fixture assertions.

## Expected Output
- Deliverables: taxonomy rules, tests, documentation notes.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_wiki_taxonomy.py tests/test_wiki_plan_schema.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture/Task_22_2_Chinese_taxonomy_baseline_for_Qoder_like_output.md`
```

## Task 22.3

```markdown
---
task_ref: "Task 22.3 - Repository identity resolver"
agent_assignment: "Agent_Scanner"
memory_log_path: ".apm/Memory/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture/Task_22_3_Repository_identity_resolver.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Repository identity resolver

## Task Reference
Implementation Plan: **Task 22.3 - Repository identity resolver** assigned to **Agent_Scanner**

## Context from Dependencies
Depends on Task 22.2 by Agent_DocGen. Read taxonomy expectations and ensure scanner identity fields support planner inputs.

## Objective
Resolve real repository identity from metadata and source evidence.

## Detailed Instructions
- Read git root, README, pom.xml, package.json, pyproject.toml, and directory names.
- Prefer explicit metadata over generic workspace names.
- Add AI_API_Atlas regression so project name is not `workspace`.

## Expected Output
- Deliverables: identity resolver, scanner contract fields, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_repository_identity.py tests/test_scanner.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture/Task_22_3_Repository_identity_resolver.md`
```

## Task 22.4

```markdown
---
task_ref: "Task 22.4 - Rule-first page planner"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture/Task_22_4_Rule_first_page_planner.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Rule-first page planner

## Task Reference
Implementation Plan: **Task 22.4 - Rule-first page planner** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 22.3 by Agent_Scanner. Read identity resolver output and integrate it into page planning.

## Objective
Generate a stable Qoder-like page plan without calling an LLM.

## Detailed Instructions
- Use repository identity, modules, APIs, data models, and runtime roles.
- Produce stable page ids, paths, parent links, and order.
- Ensure AI_API_Atlas rule-only plan contains at least 80 pages.

## Expected Output
- Deliverables: deterministic page planner, fixtures, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_rule_first_planner.py tests/test_wiki_taxonomy.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture/Task_22_4_Rule_first_page_planner.md`
```

## Task 22.5

```markdown
---
task_ref: "Task 22.5 - LLM-assisted page planner"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture/Task_22_5_LLM_assisted_page_planner.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: LLM-assisted page planner

## Task Reference
Implementation Plan: **Task 22.5 - LLM-assisted page planner** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 22.4 and Phase 21 provider work. Use mock provider in CI.

## Objective
Use LLM assistance to expand and improve the rule-first page plan.

## Detailed Instructions
- Extend the rule plan rather than replacing it blindly.
- Keep page ids deterministic and paths stable.
- With LLM enabled, target at least 120 AI_API_Atlas planned pages.

## Expected Output
- Deliverables: LLM planner mode, mock tests, optional real-provider smoke path.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_llm_assisted_planner.py tests/test_rule_first_planner.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture/Task_22_5_LLM_assisted_page_planner.md`
```

## Task 22.6

```markdown
---
task_ref: "Task 22.6 - Planner persistence into SQLite and manifest"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture/Task_22_6_Planner_persistence_into_SQLite_and_manifest.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Planner persistence into SQLite and manifest

## Task Reference
Implementation Plan: **Task 22.6 - Planner persistence into SQLite and manifest** assigned to **Agent_IndexGraph**

## Context from Dependencies
Depends on Task 22.5 by Agent_DocGen and Phase 12 SQLite runtime. Read planner output and existing runtime schema patterns.

## Objective
Persist page plan and navigation tree into SQLite and manifest output.

## Detailed Instructions
- Store planned pages, nav nodes, profile, source digests, and path registry.
- Write `.repo-agent-eval/<run>/manifest.json` with plugin-readable navigation tree.
- Add read/write and manifest compatibility tests.

## Expected Output
- Deliverables: SQLite plan persistence, manifest writer, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_planner_persistence.py tests/test_manifest_navigation.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_22_Qoder_like_Wiki_Planner_and_Chinese_Information_Architecture/Task_22_6_Planner_persistence_into_SQLite_and_manifest.md`
```

