# Task 24.5: Quality guardrails for hallucination and generic prose

## Task Status: COMPLETED

## Agent: Agent_AdapterGovernance

## Completion Date: 2026-04-26

## Dependencies
- Task 24.4 by Agent_DocGen (composer output contracts) - Completed

## Deliverables

### 1. Quality Guardrails Module
**File:** `/repo_wiki/verifier/quality_guardrails.py`

Quality guardrails module providing:

- **QualityGuardrailsChecker**: Core checker with methods for:
  - `_check_unsupported_claims()`: Detects claims without citation backing
  - `_check_citation_density()`: Ensures citation density >= 0.5/1000 chars
  - `_check_filler_words()`: Detects repeated filler patterns
  - `_check_prose_density()`: Ensures prose ratio >= 25%
  - `_check_list_dumps()`: Detects 10+ consecutive list items
  - `_check_generic_prose()`: Detects hallucinated terminology

- **QoderProfileVerifier**: Qoder-style profile verification with:
  - Profile completeness checking
  - Section coverage verification
  - Citation density metrics

- **QualityReasonCode Enum**: Reason codes for CI output:
  - `UNSUPPORTED_CLAIM` (6001)
  - `LOW_CITATION_DENSITY` (6101)
  - `REPEATED_FILLER` (6201)
  - `GENERIC_PROSE` (6202)
  - `HALLUCINATED_TERMINOLOGY` (6203)
  - `LIST_DUMP` (6301)
  - `LOW_PROSE_RATIO` (6303)

### 2. Quality Issues Detected

| Issue Type | Threshold | Severity |
|------------|-----------|----------|
| Unsupported Claims | >3 claims with 0 citations | WARNING |
| Low Citation Density | <0.5 citations per 1000 chars | WARNING |
| Repeated Filler | 3+ instances of same filler | WARNING |
| Generic Prose | >15 filler per 1000 chars | WARNING |
| List Dump | 10+ consecutive list items | ERROR |
| Low Prose Ratio | <25% prose content | ERROR |
| Hallucinated Terms | 2+ instances | ERROR |

### 3. Integration with Qoder Profile

The `QoderProfileVerifier` class integrates with qoder-like profile verification:
- Verifies document against expected section structure
- Checks citation density metrics
- Validates prose length thresholds
- Returns `QoderProfileMetrics` for diagnostics

### 4. Test Coverage

**File:** `/tests/test_quality_guardrails.py`

- 33 test cases covering all quality checks
- Good samples: Architecture doc, Overview doc
- Bad samples: Pure list dump, Generic template prose, Claims without citation
- Integration tests for qoder profile verification

## Verification Commands

```bash
# Compile check
uv run repo-wiki --help

# Run tests
uv run pytest tests/test_quality_guardrails.py tests/test_verifier.py
```

## Test Results

- **test_quality_guardrails.py**: 33 passed
- **test_verifier.py**: 35 passed
- **Combined**: 68 passed

## Key Findings

1. Quality guardrails detect hallucination patterns using regex-based filler and hallucination detection
2. Citation density checks ensure proper source traceability
3. Prose density thresholds prevent list/table dumps
4. QoderProfileVerifier integrates with existing verification infrastructure
5. All reason codes follow the 6xxx naming convention for quality gates
