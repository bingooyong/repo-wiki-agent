---
task_ref: "Task 25.3 - Service-family API composer"
status: "completed"
agent: "Agent_DocGen"
date: "2026/04/26"
summary: "Created ServiceFamilyAPIComposer for generating prose-first API articles by service family"
---

# Phase 25 - API Reference Specialization

## Task 25.3: Service-family API composer

**Status**: COMPLETED
**Agent**: Agent_DocGen
**Date**: 2026/04/26

## Summary

Successfully created the ServiceFamilyAPIComposer that generates prose-first API reference articles organized by service family. Integrates with the existing LLM page composer pipeline.

## Changes Made

### 1. Created ServiceFamilyAPIComposer (`repo_wiki/generator/service_family_api_composer.py`)

New module providing:

- `ServiceFamilyAPIComposer` class:
  - `_extract_service_family()`: Extracts service family from page ID (e.g., `api-python-backend` → `python-backend`)
  - `_get_endpoints_for_service_family()`: Filters endpoints by service family or source requirements
  - `_build_service_context()`: Builds context with endpoint counts, auth info, error codes
  - `_create_composer_context()`: Creates ComposerContext for LLM composition
  - `format_endpoint_table()`: Formats endpoints as bounded markdown table (max 10 rows)
  - `format_service_purpose()`: Generates prose description of service purpose

- Factory function `create_service_family_composer()`
- Convenience functions `compose_service_family_article()` and `compose_service_family_article_async()`
- Uses existing LLMPageComposer for actual LLM-based content generation

### 2. Created Test Suite (`tests/test_service_family_api_composer.py`)

47 test cases covering:
- Service family extraction from page IDs
- Endpoint filtering by service family and source requirements
- Context building with auth/error info
- Endpoint table formatting (bounded to 10 rows)
- Service purpose formatting
- LLM composition integration
- Async composition support
- Edge cases (empty snapshots, all HTTP methods)

### 3. Key Design Decisions

- Service family extraction skips common prefixes: `auth`, `authentication`, `error`, `health`, `core`, `data`, `admin`
- Endpoint tables limited to 10 representative rows to keep prose primary
- Prose describes service purpose, auth patterns, mutation vs query focus
- Integration with existing composer pipeline via `build_composer_input`

## Verification

**Compilation**: `uv run repo-wiki --help` - PASSED

**Self-test**: `uv run pytest tests/test_service_family_api_composer.py tests/test_llm_page_composer.py` - 69 PASSED

## Deliverables

1. **Service family API composer**: `repo_wiki/generator/service_family_api_composer.py`
2. **Tests**: `tests/test_service_family_api_composer.py` with 47 test cases
3. **Integration**: Works with existing LLMPageComposer and build_composer_input

## Notes

- Depends on enriched Endpoint metadata from Task 25.1 (service_family, domain, runtime_role, auth_type, etc.)
- Uses existing LLM composer pipeline for actual content generation
- Citations for handlers, schemas, and call sites preserved through composer validators