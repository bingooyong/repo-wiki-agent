---
task_ref: "Task 25.4 - Auth and error convention generator"
status: "completed"
agent: "Agent_DocGen"
date: "2026/04/26"
summary: "Created AuthErrorConventionGenerator for generating auth and error convention API articles"
---

# Phase 25 - API Reference Specialization

## Task 25.4: Auth and error convention generator

**Status**: COMPLETED
**Agent**: Agent_DocGen
**Date**: 2026/04/26

## Summary

Successfully created the AuthErrorConventionGenerator that generates authentication, authorization, error code, and status code topic pages based on enriched API metadata. Documents missing-evidence behavior instead of inventing conventions.

## Changes Made

### 1. Created AuthErrorConventionGenerator (`repo_wiki/generator/auth_error_convention_generator.py`)

New module providing:

- `AuthErrorConventionGenerator` class:
  - `analyze_auth_patterns()`: Analyzes authentication patterns across endpoints (auth_types, modules, files)
  - `analyze_error_codes()`: Analyzes error codes with categorization (client_error, server_error, auth_error, validation_error, not_found)
  - `get_auth_endpoints()` / `get_unauth_endpoints()`: Filters endpoints by auth requirement
  - `document_auth_conventions()`: Generates markdown documenting auth conventions
  - `document_error_handling_conventions()`: Generates markdown documenting error handling
  - `document_status_code_conventions()`: Generates markdown documenting status code conventions
  - `compose_auth_page()` / `compose_error_codes_page()`: Composes LLM-powered pages
  - `generate_*_static()`: Static content generation without LLM

- Factory function `create_auth_error_convention_generator()`
- Convenience functions `compose_auth_convention_article()` and `compose_error_convention_article()`

### 2. Created Test Suite (`tests/test_auth_error_generator.py`)

36 test cases covering:
- Auth pattern analysis (with auth, without auth, empty snapshots)
- Error code analysis (categorization, endpoints by code, most common)
- Status code documentation (with/without evidence, categories)
- Auth convention documentation (auth types, modules, files with citations)
- Error handling documentation (missing evidence behavior)
- Static content generation
- Page composition
- Factory and convenience functions
- Edge cases

### 3. Key Design Decisions

- **Document missing-evidence behavior**: Pages note when evidence is missing rather than inventing conventions
- **Error code categorization**: Groups error codes by category (auth_error, validation_error, not_found, client_error, server_error)
- **Most common errors**: Identifies errors appearing in 3+ endpoints
- **Auth type patterns**: Documents actual auth types found (bearer, api-key, oauth, none)
- **Citations**: Auth files are cited using `<cite>file:line</cite>` format

## Verification

**Compilation**: `uv run repo-wiki --help` - PASSED

**Self-test**: `uv run pytest tests/test_auth_error_generator.py tests/test_service_family_api_composer.py` - 75 PASSED

## Deliverables

1. **Auth/error convention generator**: `repo_wiki/generator/auth_error_convention_generator.py`
2. **Tests**: `tests/test_auth_error_generator.py` with 36 test cases
3. **Integration**: Works with existing LLMPageComposer and ComposerContext

## Dependencies

- Depends on Task 25.3: ServiceFamilyAPIComposer for endpoint data structure
- Uses existing LLMPageComposer for LLM-based content generation
- Reuses build_composer_input and ComposerContext from composer module

## Notes

- Key principle: Document existing behavior, don't invent conventions
- If evidence is missing, the page notes this rather than guessing
- Auth patterns extracted from actual endpoint metadata (auth_type, auth_required)
- Error codes based on actual endpoint error_codes field
- Missing evidence behavior is explicitly documented in generated pages