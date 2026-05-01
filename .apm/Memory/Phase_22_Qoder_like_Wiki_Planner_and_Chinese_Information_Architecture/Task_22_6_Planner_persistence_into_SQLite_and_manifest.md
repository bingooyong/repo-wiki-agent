# Task 22.6 - Planner persistence into SQLite and manifest

## Status: COMPLETED

## Objective
Persist page plan and navigation tree into SQLite and manifest output.

## Deliverables
- **Persistence module** (`repo_wiki/planner/persistence.py`)
  - `persist_plan(root, plan, run_id) -> dict`: writes to SQLite and manifest.json
  - `load_plan_from_sqlite(root) -> WikiPlanManifest | None`: loads from SQLite
  - Writes `.repo-agent-eval/<run_id>/manifest.json` with plugin-readable nav tree

- **Persistence tests** (`tests/test_planner_persistence.py`)
  - 16 tests covering SQLite persistence, manifest format, plugin compatibility

## Self-Test Results
```
uv run pytest tests/test_planner_persistence.py tests/test_manifest_navigation.py  # PASSED (16 tests)
```

## Key Implementation Details
- Uses existing SQLiteRuntimeStore from Phase 12
- Stores pages as DocHierarchyRecord with category->doc_type mapping
- Nav nodes stored via upsert_nav_node() with JSON serialized links
- Manifest.json contains: version, run_id, page_count, navigation_tree, pages array
- Plugin-readable navigation tree with node_id, label, node_type, path, children

## Manifest Schema
```json
{
  "version": "1.0.0",
  "run_id": "plan-1234567890",
  "page_count": 80,
  "navigation_tree": [...],
  "pages": [
    {
      "page_id": "overview",
      "title": "Overview",
      "category": "项目概述",
      "parent": null,
      "output_path": "docs/pages/overview.md",
      "generation_mode": "rule-first"
    }
  ]
}
```
