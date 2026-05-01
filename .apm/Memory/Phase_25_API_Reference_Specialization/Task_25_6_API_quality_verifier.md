---
task_ref: "Task 25.6 - API quality verifier"
status: "completed"
important_findings: false
compatibility_issue: false
compatibility_issues: false
---

# Task 25.6 - API quality verifier

## Task Reference
Phase 25 - Task 25.6: API quality verifier assigned to Agent_AdapterGovernance

## Context Dependencies
- Task 25.5: API flow diagram generation by Agent_DocGen

## Objective
Enforce API aggregation quality for qoder-like output by detecting:
- endpoint-dump pages
- missing service-family grouping
- missing auth/error coverage
- missing citations

## Deliverables

### 1. API Quality Verifier Tests (tests/test_api_quality_verifier.py)

**Test Coverage:**

**Endpoint Dump Detection:**
- `test_endpoint_dump_detection_raw_endpoints_only`: Detects API docs with only raw endpoints without grouping
- `test_endpoint_dump_detection_missing_grouping`: Detects missing service/API grouping section
- `test_endpoint_dump_detection_missing_conventions`: Detects missing call conventions section
- `test_endpoint_dump_detection_missing_key_apis`: Detects missing key entry APIs summary
- `test_endpoint_dump_detection_too_many_endpoints`: Detects >50 raw endpoints in endpoint dump

**Service-Family Grouping:**
- `test_service_family_grouping_detected`: Validates proper service-family grouping is detected
- `test_service_family_grouping_with_bearer_auth`: Validates Bearer auth documentation

**Auth/Error Coverage:**
- `test_auth_coverage_missing_auth_section`: Detects missing authentication section
- `test_auth_coverage_bearer_token_documented`: Validates Bearer token auth is documented
- `test_error_coverage_missing_error_section`: Detects missing error/status codes section
- `test_error_coverage_proper_status_codes`: Validates proper error codes are documented

**Citation Validation:**
- `test_citation_missing_in_api_doc`: Detects API docs without citations
- `test_citation_present_in_api_doc`: Validates API docs with citations pass

**Strict Profile:**
- `test_strict_profile_endpoint_dump_fails`: Validates endpoint dump fails in strict profile
- `test_strict_profile_missing_auth_fails`: Validates missing auth fails in strict profile
- `test_strict_profile_quality_artifacts_pass`: Validates quality artifacts pass in strict mode

**Reason Codes:**
- `test_reason_code_endpoint_dump`: Validates AGG_API_ENDPOINT_DUMP reason code
- `test_reason_code_api_not_grouped`: Validates AGG_API_NOT_GROUPED reason code

**Integration Tests:**
- `test_api_quality_gates_all_pass_with_quality_content`: Full quality gate pass
- `test_api_quality_gates_ci_output_includes_reason_codes`: CI output validation
- `test_gate_summary_shows_api_quality_status`: Gate summary accuracy
- `test_gate_summary_shows_blocking_on_endpoint_dump`: Blocking behavior validation

## Validation Results

**Compilation:** uv run repo-wiki --help - PASSED

**Self-Test:** uv run pytest tests/test_api_quality_verifier.py tests/test_verifier.py
- 57 tests passed
- All API quality verifier tests passed
- All existing verifier tests passed

## Implementation Notes

1. **Reason Codes Used:**
   - `AGG_API_NOT_GROUPED` (3001): API doc is raw endpoint dump
   - `AGG_API_ENDPOINT_DUMP` (3002): Too many raw endpoints (>50)

2. **Quality Gates:**
   - API aggregation check validates: service/API grouping, call conventions, key entry APIs
   - Citation coverage check ensures API docs have proper citations
   - Strict profile can make soft gates (AGG_API_ENDPOINT_DUMP) blocking

3. **Test Strategy:**
   - Uses existing VerifierService with SeverityThreshold for strict mode testing
   - Creates minimal but complete artifacts to avoid unrelated failures
   - Tests focus on API-specific quality checks

## Memory Log
Logged: 2026/04/26
