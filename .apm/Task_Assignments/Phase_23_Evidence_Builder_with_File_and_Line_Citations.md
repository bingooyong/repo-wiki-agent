# Phase 23 - Evidence Builder with File and Line Citations

## Task 23.1

```markdown
---
task_ref: "Task 23.1 - Source span extractor for Java Python TypeScript SQL YAML Markdown"
agent_assignment: "Agent_Scanner"
memory_log_path: ".apm/Memory/Phase_23_Evidence_Builder_with_File_and_Line_Citations/Task_23_1_Source_span_extractor_for_Java_Python_TypeScript_SQL_YAML_Markdown.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Source span extractor for Java Python TypeScript SQL YAML Markdown

## Task Reference
Implementation Plan: **Task 23.1 - Source span extractor for Java Python TypeScript SQL YAML Markdown** assigned to **Agent_Scanner**

## Context from Dependencies
Read `docs/phases/Phase_23_Evidence_Builder_with_File_and_Line_Citations.md` and Phase 22 plan persistence logs.

## Objective
Extract file, symbol, line range, language, and summary spans across core source formats.

## Detailed Instructions
- Support Java, Python, TypeScript, SQL, YAML, and Markdown fixtures.
- Preserve accurate line ranges for symbols and important blocks.
- Record span digests for later invalidation.

## Expected Output
- Deliverables: source span extractor, fixtures, line accuracy tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_source_spans.py tests/test_scanner.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_23_Evidence_Builder_with_File_and_Line_Citations/Task_23_1_Source_span_extractor_for_Java_Python_TypeScript_SQL_YAML_Markdown.md`
```

## Task 23.2

```markdown
---
task_ref: "Task 23.2 - Evidence SQLite schema"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_23_Evidence_Builder_with_File_and_Line_Citations/Task_23_2_Evidence_SQLite_schema.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Evidence SQLite schema

## Task Reference
Implementation Plan: **Task 23.2 - Evidence SQLite schema** assigned to **Agent_IndexGraph**

## Context from Dependencies
Depends on Task 23.1 by Agent_Scanner. Read source span output and Phase 12 SQLite schema conventions.

## Objective
Store evidence spans and page-source relationships in SQLite.

## Detailed Instructions
- Add `evidence_span`, `page_source_map`, and `symbol_reference` tables.
- Persist file path, line range, language, symbol, digest, and page relationship fields.
- Add migration and read/write tests.

## Expected Output
- Deliverables: SQLite migration/schema, repository APIs, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_evidence_schema.py tests/test_runtime_store.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_23_Evidence_Builder_with_File_and_Line_Citations/Task_23_2_Evidence_SQLite_schema.md`
```

## Task 23.3

```markdown
---
task_ref: "Task 23.3 - Evidence ranking and page matching"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_23_Evidence_Builder_with_File_and_Line_Citations/Task_23_3_Evidence_ranking_and_page_matching.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Evidence ranking and page matching

## Task Reference
Implementation Plan: **Task 23.3 - Evidence ranking and page matching** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 23.2 by Agent_IndexGraph and Task 22.6. Read evidence schema and page plan persistence before matching.

## Objective
Select the most relevant evidence candidates for each planned page.

## Detailed Instructions
- Rank by page topic, module, symbol, API, data model, and file proximity.
- Bind at least five candidate spans per planned page where source evidence exists.
- Record insufficient-evidence pages explicitly for verifier/reporting.

## Expected Output
- Deliverables: evidence ranking pipeline, page-source mapping, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_evidence_ranking.py tests/test_planner_persistence.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_23_Evidence_Builder_with_File_and_Line_Citations/Task_23_3_Evidence_ranking_and_page_matching.md`
```

## Task 23.4

```markdown
---
task_ref: "Task 23.4 - Citation block renderer"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_23_Evidence_Builder_with_File_and_Line_Citations/Task_23_4_Citation_block_renderer.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Citation block renderer

## Task Reference
Implementation Plan: **Task 23.4 - Citation block renderer** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 23.3. Use ranked evidence and page-source mappings.

## Objective
Render source citations into generated Markdown.

## Detailed Instructions
- Render `<cite>` blocks, section sources, diagram sources, and file/line links.
- Keep paths workspace-relative and resolvable by verifier and IDE.
- Add broken-path and bad-line renderer tests.

## Expected Output
- Deliverables: citation renderer, source block formats, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_citation_renderer.py tests/test_evidence_ranking.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_23_Evidence_Builder_with_File_and_Line_Citations/Task_23_4_Citation_block_renderer.md`
```

## Task 23.5

```markdown
---
task_ref: "Task 23.5 - Citation verifier"
agent_assignment: "Agent_AdapterGovernance"
memory_log_path: ".apm/Memory/Phase_23_Evidence_Builder_with_File_and_Line_Citations/Task_23_5_Citation_verifier.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Citation verifier

## Task Reference
Implementation Plan: **Task 23.5 - Citation verifier** assigned to **Agent_AdapterGovernance**

## Context from Dependencies
Depends on Task 23.4 by Agent_DocGen. Read citation block formats before adding verify checks.

## Objective
Add citation coverage and broken citation checks to verify.

## Detailed Instructions
- Detect missing citations, bad paths, invalid line ranges, and empty source blocks.
- Distinguish WARN and FAIL by profile.
- Add regression tests for no-citation and broken-citation pages.

## Expected Output
- Deliverables: verify citation gates, reason codes, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_citation_verifier.py tests/test_verifier.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_23_Evidence_Builder_with_File_and_Line_Citations/Task_23_5_Citation_verifier.md`
```

