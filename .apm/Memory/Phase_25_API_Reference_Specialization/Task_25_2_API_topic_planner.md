# Phase 25 - API Reference Specialization

## Task 25.2: API topic planner

**Status**: COMPLETED
**Agent**: Agent_DocGen
**Date**: 2026/04/26

## Summary

Successfully created the API topic planner that groups API endpoints by service family and topic rather than raw endpoint count. Generates at least 15 AI_API_Atlas API planned pages.

## Changes Made

### 1. Created API Topic Planner (`repo_wiki/planner/api_topic_planner.py`)
New module that provides `APITopicPlanner` class with:
- Groups endpoints by service family (`python-backend`, `api-server`, etc.)
- Creates topic-based API pages (auth, health, core service, etc.)
- Generates authentication/authorization convention pages
- Generates error handling convention pages
- Creates individual endpoint pages grouped by topic
- `plan_api_topics()` convenience function

Key features:
- Groups by service family, not raw endpoint count
- Creates at least 15 API planned pages
- All pages use RULE_FIRST generation mode
- Valid parent-child page relationships
- Navigation tree with API category node

### 2. Created Test Suite (`tests/test_api_topic_planner.py`)
Tests cover:
- `test_generate_api_topics`: Basic generation test
- `test_at_least_fifteen_api_pages`: Verifies 15+ API pages
- `test_api_pages_grouped_by_service_family`: Service family grouping
- `test_auth_api_pages_exist`: Auth/authz pages validation
- `test_error_handling_pages_exist`: Error handling pages validation
- `test_health_api_pages_exist`: Health check API pages validation
- `test_all_pages_use_rule_first_mode`: Generation mode validation
- `test_page_ids_are_unique`: ID uniqueness validation
- `test_navigation_tree_exists`: Navigation tree validation
- `test_parent_child_relationships`: Parent-child relationship validation
- `test_output_paths_valid`: Output path validation
- `test_source_requirements_populated`: Source requirements validation
- Edge cases: empty endpoints, all health endpoints, mixed auth types

### 3. Updated Planner Module Exports (`repo_wiki/planner/__init__.py`)
Added exports for:
- `APITopicPlanner`
- `plan_api_topics`

## Verification

**Compilation**: `uv run repo-wiki --help` - PASSED

**Self-test**: `uv run pytest tests/test_api_topic_planner.py tests/test_rule_first_planner.py` - 29 PASSED

## Deliverables

1. **API topic planner**: `repo_wiki/planner/api_topic_planner.py`
2. **Tests**: `tests/test_api_topic_planner.py` with 16 test cases
3. **Updated exports**: `repo_wiki/planner/__init__.py`

## API Page Structure

The planner generates API pages organized as:
```
API参考 (API Reference)
├── api-reference (API参考概览)
│   ├── api-authentication (认证授权API)
│   │   └── api-auth-endpoints (认证端点)
│   ├── api-authorization (权限管理API)
│   ├── api-error-codes (错误处理API)
│   │   └── api-error-conventions (错误码参考)
│   ├── api-python-backend (python-backend API)
│   ├── api-api-server (api-server API)
│   ├── api-health-api (健康检查API)
│   │   └── GET /health, GET /ready
│   ├── api-authentication (认证相关API)
│   │   └── POST /api/auth/login, etc.
│   └── api-core-service-api (核心服务API)
│       └── Individual endpoint pages
```

## Notes

- Depends on enriched Endpoint metadata from Task 25.1 (service_family, domain, runtime_role, auth_type, etc.)
- Uses RuleFirstPlanner patterns for consistency
- API pages output to `docs/pages/api/` directory
- All page IDs are unique and stable across runs