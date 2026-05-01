# Phase 26 - Data Model and Database Architecture Specialization

## Task 26.1

```markdown
---
task_ref: "Task 26.1 - Entity deduplication and canonical model resolver"
agent_assignment: "Agent_Scanner"
memory_log_path: ".apm/Memory/Phase_26_Data_Model_and_Database_Architecture_Specialization/Task_26_1_Entity_deduplication_and_canonical_model_resolver.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Entity deduplication and canonical model resolver

## Task Reference
Implementation Plan: **Task 26.1 - Entity deduplication and canonical model resolver** assigned to **Agent_Scanner**

## Context from Dependencies
Read `docs/phases/Phase_26_Data_Model_and_Database_Architecture_Specialization.md` and Phase 24 composer logs before implementation.

## Objective
Resolve Java entities, DTOs, TypeScript types, and SQL tables into canonical models.

## Detailed Instructions
- Distinguish core entities, DTOs, request/response types, and duplicated projections.
- Add deduplication keys and canonical model metadata.
- Add high-count model fixtures so DTOs do not dominate output.

## Expected Output
- Deliverables: canonical model resolver, model metadata, fixtures, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_model_deduplication.py tests/test_data_models.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_26_Data_Model_and_Database_Architecture_Specialization/Task_26_1_Entity_deduplication_and_canonical_model_resolver.md`
```

## Task 26.2

```markdown
---
task_ref: "Task 26.2 - Database migration and table extractor"
agent_assignment: "Agent_Scanner"
memory_log_path: ".apm/Memory/Phase_26_Data_Model_and_Database_Architecture_Specialization/Task_26_2_Database_migration_and_table_extractor.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Database migration and table extractor

## Task Reference
Implementation Plan: **Task 26.2 - Database migration and table extractor** assigned to **Agent_Scanner**

## Context from Dependencies
Depends on Task 26.1. Reuse canonical model metadata and scanner extraction conventions.

## Objective
Extract database schema and migration facts.

## Detailed Instructions
- Parse SQL migration tables, indexes, foreign keys, JSONB fields, and ordering.
- Link table evidence to canonical models where possible.
- Add PostgreSQL migration fixture tests.

## Expected Output
- Deliverables: migration/table extractor, schema facts, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_database_migrations.py tests/test_model_deduplication.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_26_Data_Model_and_Database_Architecture_Specialization/Task_26_2_Database_migration_and_table_extractor.md`
```

## Task 26.3

```markdown
---
task_ref: "Task 26.3 - Data-model topic planner"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_26_Data_Model_and_Database_Architecture_Specialization/Task_26_3_Data_model_topic_planner.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Data-model topic planner

## Task Reference
Implementation Plan: **Task 26.3 - Data-model topic planner** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 26.2 by Agent_Scanner and Task 22.6. Use canonical model and database facts in page planning.

## Objective
Plan data-model Wiki pages by core entity, service model, database architecture, and migration strategy.

## Detailed Instructions
- Generate at least 30 AI_API_Atlas data-model planned pages.
- Avoid one page per raw DTO/model when it does not add reader value.
- Preserve drill-down links for important entities and storage objects.

## Expected Output
- Deliverables: data-model topic planner, fixtures, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_data_model_topic_planner.py tests/test_rule_first_planner.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_26_Data_Model_and_Database_Architecture_Specialization/Task_26_3_Data_model_topic_planner.md`
```

## Task 26.4

```markdown
---
task_ref: "Task 26.4 - Entity relationship composer"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_26_Data_Model_and_Database_Architecture_Specialization/Task_26_4_Entity_relationship_composer.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Entity relationship composer

## Task Reference
Implementation Plan: **Task 26.4 - Entity relationship composer** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 26.3 and Task 24.4. Use data-model page plan, canonical models, and Mermaid renderer.

## Objective
Generate entity relationship articles with ER diagrams and citations.

## Detailed Instructions
- Explain entity role, storage, relationships, lifecycle, and important fields.
- Render ER diagrams when relationship evidence exists.
- Cite entity files, migrations, and service references.

## Expected Output
- Deliverables: entity relationship composer, ER diagrams, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_entity_relationship_composer.py tests/test_mermaid_planner.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_26_Data_Model_and_Database_Architecture_Specialization/Task_26_4_Entity_relationship_composer.md`
```

## Task 26.5

```markdown
---
task_ref: "Task 26.5 - Service data-model composer"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_26_Data_Model_and_Database_Architecture_Specialization/Task_26_5_Service_data_model_composer.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Service data-model composer

## Task Reference
Implementation Plan: **Task 26.5 - Service data-model composer** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 26.4. Reuse canonical model pages and service ownership metadata.

## Objective
Generate service-level data-model articles.

## Detailed Instructions
- Group entities, DTOs, persistence artifacts, and flows by service ownership.
- Keep raw model lists secondary to explanation.
- Include source citations and related API links.

## Expected Output
- Deliverables: service data-model composer and tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_service_data_model_composer.py tests/test_entity_relationship_composer.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_26_Data_Model_and_Database_Architecture_Specialization/Task_26_5_Service_data_model_composer.md`
```

## Task 26.6

```markdown
---
task_ref: "Task 26.6 - Data-model quality verifier"
agent_assignment: "Agent_AdapterGovernance"
memory_log_path: ".apm/Memory/Phase_26_Data_Model_and_Database_Architecture_Specialization/Task_26_6_Data_model_quality_verifier.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Data-model quality verifier

## Task Reference
Implementation Plan: **Task 26.6 - Data-model quality verifier** assigned to **Agent_AdapterGovernance**

## Context from Dependencies
Depends on Task 26.5 by Agent_DocGen. Read generated data-model page contracts before adding verifier checks.

## Objective
Enforce data-model aggregation quality.

## Detailed Instructions
- Detect raw model dump pages, missing deduplication, missing ER/migration evidence, and broken citations.
- Fail current `05-data-model.md`-style dump examples in strict profile.
- Add regression tests.

## Expected Output
- Deliverables: data-model quality gates, reason codes, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_data_model_quality_verifier.py tests/test_verifier.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_26_Data_Model_and_Database_Architecture_Specialization/Task_26_6_Data_model_quality_verifier.md`
```

