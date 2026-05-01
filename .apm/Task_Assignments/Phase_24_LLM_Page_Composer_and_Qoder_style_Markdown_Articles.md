# Phase 24 - LLM Page Composer and Qoder-style Markdown Articles

## Task 24.1

```markdown
---
task_ref: "Task 24.1 - Page prompt contract and prompt fragments"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles/Task_24_1_Page_prompt_contract_and_prompt_fragments.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Page prompt contract and prompt fragments

## Task Reference
Implementation Plan: **Task 24.1 - Page prompt contract and prompt fragments** assigned to **Agent_DocGen**

## Context from Dependencies
Read `docs/phases/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles.md`, Phase 21 provider logs, and Phase 23 citation logs.

## Objective
Define prompt contracts and reusable fragments for Qoder-like pages.

## Detailed Instructions
- Add prompt fragments for overview, service, API, data, entity, ops, and development pages.
- Include evidence, citation, heading, style, and anti-hallucination requirements.
- Add snapshot tests and secret-redaction tests.

## Expected Output
- Deliverables: prompt templates/fragments and snapshot tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_page_prompts.py tests/test_llm_config.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles/Task_24_1_Page_prompt_contract_and_prompt_fragments.md`
```

## Task 24.2

```markdown
---
task_ref: "Task 24.2 - Qoder-style article skeleton"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles/Task_24_2_Qoder_style_article_skeleton.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Qoder-style article skeleton

## Task Reference
Implementation Plan: **Task 24.2 - Qoder-style article skeleton** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 24.1. Reuse prompt headings and style constraints.

## Objective
Define stable Qoder-style article structure with TOC and rich headings.

## Detailed Instructions
- Support 目录、简介、项目结构、核心组件、架构总览、详细分析、依赖、性能、排障、结论、附录 where relevant.
- Do not force irrelevant sections on every page type.
- Add heading and TOC snapshot tests.

## Expected Output
- Deliverables: article skeleton builder, heading contract, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_article_skeleton.py tests/test_page_prompts.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles/Task_24_2_Qoder_style_article_skeleton.md`
```

## Task 24.3

```markdown
---
task_ref: "Task 24.3 - LLM page composer pipeline"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles/Task_24_3_LLM_page_composer_pipeline.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: LLM page composer pipeline

## Task Reference
Implementation Plan: **Task 24.3 - LLM page composer pipeline** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 24.2, Task 23.4, and Task 21.2 by Agent_PlatformCore. Integrate page plan, evidence, prompt, and mock provider.

## Objective
Compose Markdown from page plan, evidence, retrieval context, and LLM output.

## Detailed Instructions
- Use mock LLM in CI and optional real-provider smoke only when env exists.
- Preserve citations through normalization.
- Reject pages that lose required evidence or headings.

## Expected Output
- Deliverables: composer pipeline, mock LLM tests, optional smoke hook.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_llm_page_composer.py tests/test_citation_renderer.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles/Task_24_3_LLM_page_composer_pipeline.md`
```

## Task 24.4

```markdown
---
task_ref: "Task 24.4 - Mermaid diagram planner and renderer"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles/Task_24_4_Mermaid_diagram_planner_and_renderer.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Mermaid diagram planner and renderer

## Task Reference
Implementation Plan: **Task 24.4 - Mermaid diagram planner and renderer** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 24.3 and Task 23.4. Use composed page context and citation evidence.

## Objective
Plan and render Mermaid diagrams for suitable Wiki pages.

## Detailed Instructions
- Choose graph, sequence, ER, and flow diagrams based on page topic and evidence.
- Validate Mermaid syntax before writing pages.
- Link diagrams to source evidence.

## Expected Output
- Deliverables: diagram planner, renderer, syntax tests, source mapping.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_mermaid_planner.py tests/test_llm_page_composer.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles/Task_24_4_Mermaid_diagram_planner_and_renderer.md`
```

## Task 24.5

```markdown
---
task_ref: "Task 24.5 - Quality guardrails for hallucination and generic prose"
agent_assignment: "Agent_AdapterGovernance"
memory_log_path: ".apm/Memory/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles/Task_24_5_Quality_guardrails_for_hallucination_and_generic_prose.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Quality guardrails for hallucination and generic prose

## Task Reference
Implementation Plan: **Task 24.5 - Quality guardrails for hallucination and generic prose** assigned to **Agent_AdapterGovernance**

## Context from Dependencies
Depends on Task 24.4 by Agent_DocGen. Read composer output contracts before adding guardrails.

## Objective
Reject ungrounded, generic, or low-quality generated pages.

## Detailed Instructions
- Detect unsupported claims, missing citation density, repeated filler, low prose density, and list dumps.
- Add good and bad sample tests.
- Integrate with qoder-like profile verification.

## Expected Output
- Deliverables: quality guardrails, reason codes, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_quality_guardrails.py tests/test_verifier.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles/Task_24_5_Quality_guardrails_for_hallucination_and_generic_prose.md`
```

## Task 24.6

```markdown
---
task_ref: "Task 24.6 - Page composer incremental cache"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles/Task_24_6_Page_composer_incremental_cache.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Page composer incremental cache

## Task Reference
Implementation Plan: **Task 24.6 - Page composer incremental cache** assigned to **Agent_IndexGraph**

## Context from Dependencies
Depends on Task 24.5 and Phase 12 SQLite invalidation. Use composer inputs and quality outcomes as cache inputs.

## Objective
Cache page composition by input hash and record LLM cost.

## Detailed Instructions
- Compute input hashes from plan, evidence, prompt, model config, and source digests.
- Avoid repeated LLM calls for unchanged pages.
- Persist token/cost and output hashes per page.

## Expected Output
- Deliverables: cache schema/API, cost records, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_page_composer_cache.py tests/test_runtime_store.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles/Task_24_6_Page_composer_incremental_cache.md`
```

