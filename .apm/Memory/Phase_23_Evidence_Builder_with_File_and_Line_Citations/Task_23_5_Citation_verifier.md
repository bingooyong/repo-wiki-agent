---
task_ref: "Task 23.5 - Citation verifier"
status: "completed"
important_findings: false
compatibility_issue: false
compatibility_issues: false
---

# Task 23.5 - Citation verifier

## Status
Completed

## Implementation Summary

### Deliverables Created

1. **Citation Quality Checks** (`repo_wiki/verifier/service.py`)
   - `_check_citation_coverage()` - Checks that key documentation pages have at least one citation
   - `_check_citation_validity()` - Validates all citations reference valid file paths and line ranges
   - `_check_citation_source_empty()` - Ensures !!! cite blocks are not empty

2. **New Reason Codes Added** (`repo_wiki/verifier/service.py`)
   - `CITATION_MISSING` (5001) - Page has no citations at all
   - `CITATION_BROKEN_PATH` (5002) - Citation file path does not exist
   - `CITATION_BAD_LINES` (5003) - Citation line range is invalid
   - `CITATION_SOURCE_EMPTY` (5004) - Source block is empty

3. **Gate Classification**
   - HARD gate: `CITATION_SOURCE_EMPTY` (empty source blocks are structural failures)
   - SOFT gate: `CITATION_MISSING`, `CITATION_BROKEN_PATH`, `CITATION_BAD_LINES`

4. **Citation Validation Features**
   - Supports negative line numbers detection
   - Validates line ranges (start <= end)
   - Checks if line numbers exceed file length
   - Distinguishes between broken paths and bad line ranges

5. **Tests** (`tests/test_citation_verifier.py`)
   - `test_citation_coverage_pass_with_citations` - PASS case for coverage
   - `test_citation_coverage_fail_on_no_citations` - FAIL case for missing citations
   - `test_citation_coverage_soft_gate_for_missing_citations` - SOFT gate classification
   - `test_citation_validity_fail_on_broken_path` - Broken path detection
   - `test_citation_validity_fail_on_invalid_line_range` - Invalid line range detection
   - `test_citation_validity_fail_on_reversed_line_range` - Reversed range detection
   - `test_citation_validity_fail_on_negative_line` - Negative line detection
   - `test_citation_source_empty_fail` - Empty source block detection
   - `test_citation_source_empty_pass_with_citations` - Non-empty source block PASS
   - `test_valid_citation_single_line` - Valid single-line citation
   - `test_valid_citation_multi_line` - Valid multi-line citation
   - `test_valid_citation_with_symbol` - Valid citation with symbol
   - `test_multiple_citations_mixed_validity` - Mixed valid/invalid detection
   - `test_architecture_citation_validity` - Architecture page validation
   - `test_section_source_block_empty_is_hard_gate` - HARD gate for empty blocks
   - `test_citation_missing_can_be_hard_gate` - Configurable HARD gate
   - `test_reason_codes_include_citation_failures` - Reason code inclusion

### Key Design Decisions

- **Profile-based severity**: WARN vs FAIL distinguished by gate type
- **Lenient coverage check**: Pages with <50 chars of content are skipped (likely placeholders)
- **Validation order**: Negative lines and reversed ranges checked before file existence
- **Duplicate prevention**: Uses set() for glob patterns to avoid duplicate file processing

### Compile Command
`uv run repo-wiki --help` - PASSED

### Self-Test Command
`uv run pytest tests/test_citation_verifier.py tests/test_verifier.py` - PASSED (52 tests)

### Dependencies Used
- Task 23.4: `repo_wiki/evidence/citation_renderer.py` (CiteBlock, validation functions)

### Exports Added to `verifier/__init__.py`
- None (all exports from service.py via VerifierService)
