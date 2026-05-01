---
task_ref: "Task 23.1 - Source span extractor for Java Python TypeScript SQL YAML Markdown"
status: "COMPLETED"
important_findings: false
compatibility_issue: false
compatibility_issues: false
---

# Task 23.1 - Source span extractor for Java Python TypeScript SQL YAML Markdown

## Status: COMPLETED

## Objective
Extract file, symbol, line range, language, and summary spans across core source formats for evidence building with file and line citations.

## Deliverables

### 1. Source Span Extractor Module
**File:** `repo_wiki/scanner/source_spans.py`

- `SourceSpan` dataclass with fields:
  - `file`: Workspace-relative path
  - `symbol`: Symbol name (function, class, table, etc.)
  - `line_start`: 1-based line number
  - `line_end`: 1-based line number
  - `language`: Programming/markup language
  - `summary`: Human-readable summary
  - `digest`: SHA256 digest (first 16 chars) for invalidation

- `SourceSpanExtractor` class with methods:
  - `extract_from_file(file_path, content) -> list[SourceSpan]`
  - `extract_from_files(files) -> list[SourceSpan]`

- Language-specific extractors:
  - `_extract_python()`: Classes, functions (including async)
  - `_extract_java()`: Classes, interfaces, enums, methods
  - `_extract_typescript()`: Classes, interfaces, types, arrow functions
  - `_extract_sql()`: Tables, indexes, views, functions/procedures
  - `_extract_yaml()`: Top-level keys as sections
  - `_extract_markdown()`: Headings as sections

- Utility functions:
  - `compute_span_digest()`: Compute digest for a span
  - `group_spans_by_file()`: Group spans by file path
  - `filter_spans_by_language()`: Filter by language list
  - `spans_to_citations()`: Convert spans to citation strings

### 2. Test Suite
**File:** `tests/test_source_spans.py`

- 44 tests covering:
  - Python extractor: functions, classes, async functions, line accuracy
  - Java extractor: classes, interfaces, methods, line accuracy
  - TypeScript extractor: classes, interfaces, types, arrow functions
  - SQL extractor: tables, indexes, views, functions
  - YAML extractor: keys as sections
  - Markdown extractor: headings as sections
  - SourceSpan data class: citation format, validation, digest
  - Integration tests: multi-file extraction, grouping, filtering
  - Line accuracy tests: verify line numbers are accurate

### 3. Supported Languages and Extensions
| Language | Extensions |
|----------|-----------|
| Java | .java |
| Python | .py |
| TypeScript | .ts, .tsx, .js, .jsx |
| SQL | .sql |
| YAML | .yaml, .yml |
| Markdown | .md |

## Self-Test Results
```
uv run pytest tests/test_source_spans.py tests/test_scanner_normalization.py tests/test_scanner_artifacts.py
# 48 passed in 0.11s
```

## Compilation Verification
```
uv run repo-wiki --help
# Works correctly
```

## Key Implementation Details

### Line Number Accuracy
- All line numbers are 1-based (human-readable)
- Block detection uses indentation (Python) or brace matching ({})
- SQL statement detection handles nested parentheses and string literals

### Digest for Invalidation
- Format: SHA256 hash truncated to 16 characters
- Based on file:line_start-line_end for fast computation
- Used for later evidence invalidation

### Citation Format
- String format: `file.py:10-15`
- Computed via `span.citation()` method

## Dependencies
- Uses only standard library and project dependencies
- No external parsing libraries required
- Robust regex-based extraction with error handling

## Notes
- Java method extraction handles indented code (4-space indentation)
- TypeScript export classes/interfaces are properly detected
- YAML extraction focuses on top-level keys as evidence sections
- Markdown extraction handles ATX-style headings (# to ######)
