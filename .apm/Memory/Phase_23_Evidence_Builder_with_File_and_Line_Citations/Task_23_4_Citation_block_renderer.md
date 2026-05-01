---
task_ref: "Task 23.4 - Citation block renderer"
status: "completed"
important_findings: false
compatibility_issue: false
compatibility_issues: false
---

# Task 23.4 - Citation block renderer

## Status
Completed

## Implementation Summary

### Deliverables Created

1. **Citation Renderer Module** (`repo_wiki/evidence/citation_renderer.py`)
   - `CiteBlock` class - renders `<cite>` blocks for inline source citation
   - `SectionSource` class - renders section-level source citations
   - `DiagramSource` class - renders diagram sources with provenance tracking
   - `FileLineLink` class - renders IDE/verifier-resolvable file:line links
   - `CitationRenderer` class - main renderer coordinating all citation types

2. **Key Methods**
   - `render_cite_block()` - renders single `<cite>` block
   - `render_cite_block_from_span()` - renders from EvidenceSpanRecord
   - `render_cite_block_from_candidate()` - renders from EvidenceCandidate
   - `render_section_sources()` - renders section source block
   - `render_page_citations()` - renders all citations for a page
   - `render_diagram_source()` - renders diagram with evidence tracking
   - `render_file_line_link()` - renders file:line IDE link
   - `render_sources_footer()` - renders sources section footer

3. **Validation Functions** (broken-path and bad-line tests)
   - `validate_citation_path()` - validates file path exists
   - `validate_line_range()` - validates line numbers are valid
   - `validate_citation()` - validates complete citation
   - `BrokenPathError` - raised when file path is broken
   - `BadLineError` - raised when line range is invalid

4. **Tests** (`tests/test_citation_renderer.py`)
   - TestCiteBlock - cite block rendering
   - TestSectionSource - section source rendering
   - TestDiagramSource - diagram source rendering
   - TestFileLineLink - file/line link rendering
   - TestCitationRenderer - main renderer tests
   - TestBrokenPathRenderer - broken-path detection tests
   - TestBadLineRenderer - bad-line detection tests
   - TestValidateCitation - combined validation tests
   - TestWorkspaceRelativePaths - path handling tests

### Key Design Decisions

- **Workspace-relative paths**: All paths remain relative for portability
- **IDE resolution**: Relative paths use `./` prefix for IDE resolution
- **Markdown-compatible**: All outputs are valid Markdown
- **Evidence integration**: Uses EvidenceSpanRecord and EvidenceCandidate from Task 23.3

### Compile Command
`uv run repo-wiki --help` - PASSED

### Self-Test Command
`uv run pytest tests/test_citation_renderer.py tests/test_evidence_ranking.py` - PASSED (67 tests)

### Dependencies Used
- Task 23.3: `repo_wiki/evidence/ranking.py` (EvidenceCandidate, PageEvidenceBinding)
- Task 23.2: `repo_wiki/orchestration/runtime_store.py` (EvidenceSpanRecord)

### Exports Added to `evidence/__init__.py`
- CitationRenderer
- CiteBlock
- SectionSource
- DiagramSource
- FileLineLink
- BrokenPathError
- BadLineError
- validate_citation_path
- validate_line_range
- validate_citation
