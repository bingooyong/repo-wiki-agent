# Phase 25 - API Reference Specialization

## Task 25.1: API inventory enrichment

**Status**: COMPLETED
**Agent**: Agent_Scanner
**Date**: 2026/04/26

## Summary

Successfully enriched the API inventory with metadata for service, handler, auth, request, and response attributes.

## Changes Made

### 1. Enhanced Endpoint dataclass (`repo_wiki/core/contracts.py`)
Added the following fields to the `Endpoint` model:
- `service_family`: Service family (e.g., 'python-backend', 'typescript-frontend')
- `domain`: Business domain (e.g., 'core-platform', 'ai-services')
- `runtime_role`: Runtime role (e.g., 'api-server', 'worker')
- `auth_type`: Authentication type ('bearer', 'none', 'api-key', 'oauth')
- `auth_required`: Boolean flag
- `request_body`: Boolean flag for POST/PUT/PATCH methods
- `response_type`: Response content type (default 'json')
- `error_codes`: List of common error codes [400, 401, 403, 404, 500]
- `line_number`: Handler line citation (1-based)
- `line_end`: Handler end line for span citation

### 2. Enhanced RepositoryScanner (`repo_wiki/scanner/repository_scanner.py`)
Added `_enrich_endpoints()` method that:
- Attaches module-level metadata (service_family, domain, runtime_role) to endpoints
- Detects auth type based on path patterns, module names, and runtime role
- Sets request_body flag for POST/PUT/PATCH methods
- Sets common error codes
- Extracts handler line numbers for citations

Added Flask route extraction patterns:
- `@app.route("/path", methods=["GET", "POST"])` - multiple methods
- `@app.route("/path")` - default GET

Added helper methods:
- `_is_webhook_path()`: Detects webhook paths
- `_detect_endpoint_auth_type()`: Determines auth requirements
- `_find_handler_line()`: Locates handler function definitions

### 3. Updated artifacts writer (`repo_wiki/scanner/artifacts.py`)
Updated `api-index.yaml` generation to include enriched endpoint metadata.

### 4. Created test suite (`tests/test_api_inventory.py`)
Tests cover:
- Endpoint enrichment with module metadata
- Auth type detection (bearer, none)
- Request body detection
- Line number citations
- Webhook path detection (auth_type=none)
- Health endpoint detection (auth_type=none)
- Error codes assignment
- Flask route extraction with and without methods

## Verification

**Compilation**: `uv run repo-wiki --help` - PASSED

**Self-test**: `uv run pytest tests/test_api_inventory.py tests/test_scanner_artifacts.py tests/test_scanner_normalization.py` - 13 passed

## Deliverables

1. **Enriched API scanner**: RepositoryScanner now extracts and enriches endpoint metadata
2. **Updated contracts**: Endpoint dataclass has additional metadata fields
3. **Fixtures**: Test fixtures for Python FastAPI/Flask endpoints
4. **Tests**: test_api_inventory.py with 10 test cases

## Notes

- Java/TypeScript endpoint extraction patterns are documented but not fully implemented in current scanner
- Scanner currently focuses on Python FastAPI/Flask patterns which are common in repo-agent
- Auth detection uses path patterns (health, status, webhook) and runtime role
- Line number citation uses regex pattern matching on file content