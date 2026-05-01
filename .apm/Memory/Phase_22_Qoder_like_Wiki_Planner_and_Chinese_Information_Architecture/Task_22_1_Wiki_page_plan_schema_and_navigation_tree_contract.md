# Task 22.1 - Wiki page-plan schema and navigation tree contract

## Status: COMPLETED

## Objective
Define `wiki-plan.json` and manifest navigation tree contracts.

## Deliverables
- **Page-plan schema** (`repo_wiki/planner/schema.py`)
  - `WikiPagePlan`: page id, title, category, parent, output path, source requirements, generation mode
  - `WikiPlanManifest`: top-level manifest with pages and navigation tree
  - `NavNode`: navigation tree node for IDE/static viewer consumption
  - `RepositoryIdentity`: repository metadata
  - `SourceRequirement`: source requirements for page generation
  - `GenerationMode` enum: RULE_FIRST, LLM_ASSISTED

- **Schema validation tests** (`tests/test_wiki_plan_schema.py`)
  - 16 tests covering all schema components

- **Navigation tree tests** (`tests/test_manifest_navigation.py`)
  - 14 tests covering nav tree building and IDE consumption

## Compile Check
```
uv run repo-wiki --help  # PASSED
```

## Self-Test Results
```
uv run pytest tests/test_wiki_plan_schema.py tests/test_manifest_navigation.py  # PASSED (30 tests)
```

## Key Implementation Details
- `WikiPagePlan.page_id`: kebab-case slug format
- `WikiPagePlan.category`: WikiTaxonomyCategory enum
- `WikiPlanManifest.navigation_tree`: list of NavNode with hierarchical children
- NavNode supports: category, page, separator node types
- Schema version: 1.0.0
