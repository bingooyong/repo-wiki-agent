# Task 33.3 - Citation Relevance Verifier

**Date**: 2026-05-02
**Status**: COMPLETED
**Agent**: AdapterGovernance
**Phase**: Phase 33 - Evidence Ranking and Hallucination Control

## Objective
Add strict verification for page-title to citation relevance in qoder-like profile.

## Implementation Summary

### 1. Added Citation Relevance Check to QoderLikeVerifierService

**File**: `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/verifier/qoder_strict_verifier.py`

- Added `QODER_CITATION_RELEVANCE_MISMATCH` to `STRICT_HARD_CODES`
- Added `_check_qoder_citation_relevance()` method to verify citations match page service/topic
- Added new check to `verify()` method's check list

### 2. Citation Relevance Logic

The `_check_qoder_citation_relevance()` method:
- Compares page title/filename against citation file paths
- Detects high-confidence mismatches (billing page citing auth implementation)
- Uses WARN status for ambiguous shared infrastructure citations (shared/, common/, lib/, utils/)
- Fails with HARD gate for wrong-service evidence binding

**Page Service Mapping**:
- `auth`: auth, login, session, token, oauth, sso keywords
- `billing`: billing, invoice, payment, subscription, price keywords
- `api`: api, endpoint, route, handler, controller, rest keywords
- `data-model`: model, schema, entity, dto, migration keywords
- `database`: db, database, repo, query, sql keywords

**Shared Infrastructure Patterns** (produce WARN, not FAIL):
- shared/, common/, lib/, utils/, base/, core/, vendor/, deps/, external/, third_party/

### 3. Test Coverage

**File**: `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/tests/test_qoder_like_verifier.py`

Added `TestCitationRelevance` class with tests:
- `test_citation_relevance_detects_wrong_service_binding` - FAIL on wrong service
- `test_citation_relevance_allows_shared_infrastructure` - WARN for shared infra
- `test_citation_relevance_passes_for_matching_service` - PASS for correct service
- `test_citation_relevance_api_page_with_api_citations` - API page with API citations passes
- `test_citation_relevance_data_model_page_with_model_citations` - Data model page passes
- `test_citation_relevance_wrong_service_multiple_mismatches` - Multiple mismatches detected

Also added:
- `test_citation_relevance_mismatch_hard_code_is_defined` - Hard code verification

## Verification Results

### Compile Command
```
uv run repo-wiki --help
```
**Status**: PASS - Command executes successfully

### Self-Test Command
```
uv run pytest tests/test_citation_verifier.py tests/test_qoder_like_verifier.py
```
**Status**: 42 passed in 0.66s

## Deliverables
- Citation relevance verifier: Implemented in `_check_qoder_citation_relevance()`
- WARN/FAIL gates: WARN for shared infrastructure, FAIL for wrong-service binding
- Reason codes: `QODER_CITATION_RELEVANCE_MISMATCH`
- Tests: 8 new tests in `TestCitationRelevance` class

## Completion Criteria
- [x] Citation relevance is part of strict qoder-like verification
- [x] Added to `verify()` method check list
- [x] High-confidence mismatches produce HARD failures
- [x] Ambiguous shared-infrastructure citations produce WARN
- [x] Regression cases for wrong-service evidence binding included
