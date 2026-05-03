---
task_ref: "Task 32.3 - Data-model entity topic planner"
status: "completed"
date: "2026-05-03"
agent: "Agent_DocGen"
---

# Task 32.3: Data-model Entity Topic Planner Report

## Objective
Split data-model documentation into entity and persistence topics while eliminating duplicate pages.

## Deliverables

### 1. Extended DataModelTopicPlanner (`repo_wiki/planner/data_model_topic_planner.py`)

**New Topic Categories Added (Task 32.3)**:
- `ENTITY`: Entity drill-down pages
- `MIGRATION`: Data migration details
- `TABLE_STRUCTURE`: Table structure documentation
- `INDEX_PERFORMANCE`: Index and performance pages
- `AUDIT`: Audit trail pages
- `SECURITY`: Security model pages

**New Page Generation Methods**:
- `_generate_entity_drilldown_pages()`: Generates entity-detail, entity-matrix
- `_generate_table_structure_pages()`: Generates table-structure-overview, table-relationships
- `_generate_index_performance_pages()`: Generates index-strategy, performance-tuning
- `_generate_audit_pages()`: Generates audit-overview, audit-events
- `_generate_security_pages()`: Generates security-models, security-config

### 2. Duplicate Page Detection

**New Features**:
- `_title_set`: Tracks titles to detect duplicates
- `_check_duplicate_title()`: Prevents "xxx 数据模型-2" style duplicates
- Deduplication via page ID counter already present in `_make_page_id()`

**Key Behavior**:
- Prevents pages with same title or titles differing only by numeric suffix (-2, -3)
- Page IDs use counter suffix when collisions occur, but titles remain unique

### 3. Entity Drill-down Link Structure

Entity pages linked to service-level pages via parent relationships:
- `entity-detail` -> parent: `entity-relationships`
- `entity-matrix` -> parent: `entity-relationships`
- `table-structure-overview` -> parent: `database-architecture`

### 4. New Test Class: `TestDataModelTopicPlannerDuplicateDetection`

**8 new tests added**:
- `test_no_duplicate_page_titles`: Verifies no numeric suffix duplicates
- `test_duplicate_detection_prevents_same_title_pages`: Tests _check_duplicate_title
- `test_entity_drilldown_pages_exist`: Verifies entity-detail, entity-matrix
- `test_table_structure_pages_exist`: Verifies table-structure-overview, table-relationships
- `test_index_performance_pages_exist`: Verifies index-strategy, performance-tuning
- `test_audit_pages_exist`: Verifies audit-overview, audit-events
- `test_security_pages_exist`: Verifies security-models, security-config
- `test_service_level_links_preserved`: Verifies parent-child relationships

## Self-Test Verification

**Command**: `uv run repo-wiki --help`
**Result**: PASS - repo-wiki commands available

**Command**: `uv run pytest tests/test_data_model_topic_planner.py tests/test_qoder_like_verifier.py -v`
**Result**: PASS - 44 tests passed (18 existing + 8 new + 18 qoder_like_verifier)

## Page Count

Total data model pages now generated: 26+ (including Task 32.3 additions)

## Completion Criteria

- [x] Entity, migration, table-structure, index-performance, audit, security topics generated
- [x] Duplicate page detection implemented (prevents "xxx 数据模型-2")
- [x] Entity drill-down links connected to service-level pages
- [x] Duplicate-topic regression tests added
- [x] All tests pass

---
**Status**: COMPLETED
**Agent**: Agent_DocGen
**Completed**: 2026-05-03
**Next Task**: Task 32.4 - Project overview module hierarchy