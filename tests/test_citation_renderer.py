"""Tests for citation block renderer."""

import tempfile
from pathlib import Path

import pytest

from repo_wiki.evidence.citation_renderer import (
    BadLineError,
    BrokenPathError,
    CitationRenderer,
    CiteBlock,
    DiagramSource,
    FileLineLink,
    SectionSource,
    validate_citation,
    validate_citation_path,
    validate_line_range,
)
from repo_wiki.evidence.ranking import EvidenceCandidate, PageEvidenceBinding
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord


class TestCiteBlock:
    """Tests for CiteBlock rendering."""

    def test_render_basic_cite(self):
        """Test basic <cite> block rendering."""
        cite = CiteBlock(
            file_path="src/auth/service.py",
            line_start=10,
            line_end=20,
        )
        result = cite.render()
        assert "<cite>src/auth/service.py:10-20</cite>" in result

    def test_render_cite_with_symbol(self):
        """Test <cite> block with symbol name."""
        cite = CiteBlock(
            file_path="src/auth/service.py",
            line_start=10,
            line_end=20,
            symbol="AuthService",
        )
        result = cite.render()
        assert "<cite>src/auth/service.py:10" in result
        assert "(AuthService)" in result

    def test_render_cite_with_label(self):
        """Test <cite> block with label."""
        cite = CiteBlock(
            file_path="src/auth/service.py",
            line_start=10,
            line_end=20,
            label="authentication",
        )
        result = cite.render()
        assert "authentication" in result

    def test_render_cite_single_line(self):
        """Test <cite> block for single line."""
        cite = CiteBlock(
            file_path="src/auth/service.py",
            line_start=10,
            line_end=10,
        )
        result = cite.render()
        assert "<cite>src/auth/service.py:10</cite>" in result

    def test_render_link(self):
        """Test rendering as IDE-resolvable link."""
        cite = CiteBlock(
            file_path="src/auth/service.py",
            line_start=10,
            line_end=20,
        )
        result = cite.render_link()
        # Relative paths use ./ prefix for IDE resolution
        assert "src/auth/service.py" in result


class TestSectionSource:
    """Tests for SectionSource rendering."""

    def test_render_empty_section(self):
        """Test rendering section with no citations."""
        section = SectionSource(
            section_id="architecture",
            page_id="arch",
            doc_type="section",
            citations=[],
        )
        result = section.render()
        assert result == ""

    def test_render_section_with_citations(self):
        """Test rendering section with citations."""
        citations = [
            CiteBlock(file_path="src/a.py", line_start=1, line_end=10),
            CiteBlock(file_path="src/b.py", line_start=5, line_end=15),
        ]
        section = SectionSource(
            section_id="architecture",
            page_id="arch",
            doc_type="section",
            citations=citations,
        )
        result = section.render()
        assert "!!! cite" in result
        assert "architecture" in result
        assert "src/a.py" in result
        assert "src/b.py" in result


class TestDiagramSource:
    """Tests for DiagramSource rendering."""

    def test_render_diagram_basic(self):
        """Test basic diagram source rendering."""
        diagram = DiagramSource(
            diagram_id="arch-flow",
            diagram_type="mermaid",
        )
        result = diagram.render()
        assert "!!! diagram" in result
        assert "arch-flow" in result
        assert "mermaid" in result

    def test_render_diagram_with_source(self):
        """Test diagram with source file and lines."""
        diagram = DiagramSource(
            diagram_id="arch-flow",
            diagram_type="mermaid",
            source_file="docs/architecture.md",
            source_lines=(10, 50),
        )
        result = diagram.render()
        assert "source: docs/architecture.md" in result
        assert "lines: 10-50" in result

    def test_render_diagram_with_evidence(self):
        """Test diagram with evidence spans."""
        citations = [
            CiteBlock(file_path="src/a.py", line_start=1, line_end=10),
        ]
        diagram = DiagramSource(
            diagram_id="arch-flow",
            diagram_type="mermaid",
            evidence_spans=citations,
        )
        result = diagram.render()
        assert "evidence:" in result
        assert "src/a.py" in result


class TestFileLineLink:
    """Tests for FileLineLink rendering."""

    def test_render_simple_link(self):
        """Test simple file:line link."""
        link = FileLineLink(
            file_path="src/auth.py",
            line=10,
        )
        result = link.render()
        # Relative paths use ./ prefix for IDE resolution
        assert "src/auth.py" in result
        assert "./src/auth.py" in result

    def test_render_link_with_range(self):
        """Test file:line-range link."""
        link = FileLineLink(
            file_path="src/auth.py",
            line=10,
            end_line=20,
        )
        result = link.render()
        assert "src/auth.py:10-20" in result

    def test_render_link_with_symbol(self):
        """Test link with symbol name."""
        link = FileLineLink(
            file_path="src/auth.py",
            line=10,
            symbol="AuthService",
        )
        result = link.render()
        # Label should use symbol name
        assert "AuthService" in result

    def test_render_simple_text(self):
        """Test simple text rendering without link."""
        link = FileLineLink(
            file_path="src/auth.py",
            line=10,
        )
        result = link.render_simple()
        assert result == "src/auth.py:10"

    def test_render_simple_text_with_symbol(self):
        """Test simple text with symbol."""
        link = FileLineLink(
            file_path="src/auth.py",
            line=10,
            symbol="AuthService",
        )
        result = link.render_simple()
        assert "AuthService" in result


class TestCitationRenderer:
    """Tests for CitationRenderer class."""

    def test_render_cite_block(self):
        """Test rendering a single <cite> block."""
        renderer = CitationRenderer()
        result = renderer.render_cite_block(
            file_path="src/auth.py",
            line_start=10,
            line_end=20,
            symbol="AuthService",
        )
        assert "<cite>" in result
        assert "src/auth.py:10-20" in result

    def test_render_cite_block_from_span(self):
        """Test rendering from evidence span record."""
        renderer = CitationRenderer()
        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/auth.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="AuthService",
            span_text="class AuthService:",
        )
        result = renderer.render_cite_block_from_span(span)
        assert "<cite>" in result
        assert "src/auth.py" in result
        assert "(AuthService)" in result

    def test_render_cite_block_from_candidate(self):
        """Test rendering from evidence candidate."""
        renderer = CitationRenderer()
        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/auth.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="AuthService",
            span_text="class AuthService:",
        )
        candidate = EvidenceCandidate(
            evidence_id=1,
            span=span,
            score=1.0,
            match_signals=["module_match"],
            citation_order=0,
        )
        result = renderer.render_cite_block_from_candidate(candidate)
        assert "<cite>" in result
        assert "src/auth.py" in result

    def test_render_section_sources(self):
        """Test rendering section sources."""
        renderer = CitationRenderer()
        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/auth.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="AuthService",
            span_text="class AuthService:",
        )
        candidate = EvidenceCandidate(
            evidence_id=1,
            span=span,
            score=1.0,
            match_signals=["module_match"],
            citation_order=0,
        )
        binding = PageEvidenceBinding(
            page_id="auth",
            doc_type="module",
            candidates=[candidate],
        )
        result = renderer.render_section_sources(binding)
        assert "!!! cite" in result
        assert "auth" in result

    def test_render_page_citations(self):
        """Test rendering all page citations."""
        renderer = CitationRenderer()
        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/auth.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="AuthService",
            span_text="class AuthService:",
        )
        candidate = EvidenceCandidate(
            evidence_id=1,
            span=span,
            score=1.0,
            match_signals=["module_match"],
            citation_order=0,
        )
        binding = PageEvidenceBinding(
            page_id="auth",
            doc_type="module",
            candidates=[candidate],
        )
        result = renderer.render_page_citations(binding)
        assert len(result) == 1
        assert "<cite>" in result[0]

    def test_render_diagram_source(self):
        """Test rendering diagram source."""
        renderer = CitationRenderer()
        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="docs/diagrams.md",
            line_start=10,
            line_end=20,
            language="markdown",
            symbol=None,
            span_text="```mermaid",
        )
        result = renderer.render_diagram_source(
            diagram_id="flow",
            diagram_type="mermaid",
            evidence_spans=[span],
            source_file="docs/diagrams.md",
            source_lines=(10, 20),
            description="Architecture flow diagram",
        )
        assert "!!! diagram" in result
        assert "flow" in result
        assert "mermaid" in result

    def test_render_file_line_link(self):
        """Test rendering file:line link."""
        renderer = CitationRenderer()
        result = renderer.render_file_line_link(
            file_path="src/auth.py",
            line=10,
            end_line=20,
            symbol="AuthService",
        )
        # Relative paths use ./ prefix for IDE resolution
        assert "src/auth.py" in result
        assert "AuthService" in result

    def test_render_sources_footer(self):
        """Test rendering sources footer."""
        renderer = CitationRenderer()
        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/auth.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="AuthService",
            span_text="class AuthService:",
        )
        candidate = EvidenceCandidate(
            evidence_id=1,
            span=span,
            score=1.0,
            match_signals=["module_match"],
            citation_order=0,
        )
        binding = PageEvidenceBinding(
            page_id="auth",
            doc_type="module",
            candidates=[candidate],
        )
        result = renderer.render_sources_footer(binding)
        assert "## Sources" in result
        assert "src/auth.py" in result

    def test_render_sources_footer_empty(self):
        """Test rendering empty sources footer."""
        renderer = CitationRenderer()
        binding = PageEvidenceBinding(
            page_id="empty",
            doc_type="module",
            candidates=[],
        )
        result = renderer.render_sources_footer(binding)
        assert result == ""


class TestBrokenPathRenderer:
    """Tests for broken-path detection in citation renderer."""

    def test_validate_path_nonexistent_file(self):
        """Test validation fails for non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(BrokenPathError):
                validate_citation_path("nonexistent/file.py", workspace_root=tmpdir)

    def test_validate_path_existing_file(self):
        """Test validation passes for existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("print('hello')")

            result = validate_citation_path("test.py", workspace_root=tmpdir)
            assert result == test_file

    def test_validate_path_absolute(self):
        """Test validation with absolute path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("print('hello')")

            result = validate_citation_path(str(test_file))
            assert result == test_file

    def test_validate_path_is_directory(self):
        """Test validation fails for directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(BrokenPathError):
                validate_citation_path(tmpdir)


class TestBadLineRenderer:
    """Tests for bad-line detection in citation renderer."""

    def test_validate_line_start_zero(self):
        """Test validation fails for line_start = 0."""
        with pytest.raises(BadLineError) as exc_info:
            validate_line_range(0, 10, "test.py")
        assert "must be >= 1" in str(exc_info.value)

    def test_validate_line_start_negative(self):
        """Test validation fails for negative line_start."""
        with pytest.raises(BadLineError) as exc_info:
            validate_line_range(-1, 10, "test.py")
        assert "must be >= 1" in str(exc_info.value)

    def test_validate_line_end_less_than_start(self):
        """Test validation fails when line_end < line_start."""
        with pytest.raises(BadLineError) as exc_info:
            validate_line_range(10, 5, "test.py")
        assert "must be >= line start" in str(exc_info.value)

    def test_validate_line_range_valid(self):
        """Test validation passes for valid range."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("\n".join([f"line {i}" for i in range(20)]))

            # Should not raise
            validate_line_range(1, 10, "test.py", workspace_root=tmpdir)

    def test_validate_line_end_exceeds_file(self):
        """Test validation fails when line_end exceeds file length."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("\n".join([f"line {i}" for i in range(10)]))

            with pytest.raises(BadLineError) as exc_info:
                validate_line_range(1, 100, "test.py", workspace_root=tmpdir)
            assert "exceeds file length" in str(exc_info.value)

    def test_validate_line_end_exactly_file_length(self):
        """Test validation passes when line_end equals file length."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            content = "\n".join([f"line {i}" for i in range(10)])
            test_file.write_text(content)
            line_count = len(content.splitlines())

            # Should not raise
            validate_line_range(1, line_count, "test.py", workspace_root=tmpdir)


class TestValidateCitation:
    """Tests for combined citation validation."""

    def test_validate_citation_valid(self):
        """Test validation passes for valid citation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("\n".join([f"line {i}" for i in range(20)]))

            # Should not raise
            validate_citation("test.py", 1, 10, workspace_root=tmpdir)

    def test_validate_citation_broken_path(self):
        """Test validation fails for broken path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(BrokenPathError):
                validate_citation("nonexistent.py", 1, 10, workspace_root=tmpdir)

    def test_validate_citation_bad_line(self):
        """Test validation fails for bad line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("print('hello')")

            with pytest.raises(BadLineError):
                validate_citation("test.py", 1, 100, workspace_root=tmpdir)


class TestWorkspaceRelativePaths:
    """Tests for workspace-relative path handling."""

    def test_paths_stay_relative(self):
        """Test that paths remain workspace-relative."""
        renderer = CitationRenderer()
        result = renderer.render_cite_block(
            file_path="src/auth/service.py",
            line_start=10,
            line_end=20,
        )
        # Path should be relative (no leading /)
        assert "src/auth/service.py" in result
        assert not result.startswith("/")

    def test_render_link_preserves_path(self):
        """Test that render_link preserves relative path."""
        renderer = CitationRenderer()
        cite = CiteBlock(
            file_path="src/auth/service.py",
            line_start=10,
            line_end=20,
        )
        result = cite.render_link()
        # URI should preserve the relative path
        assert "src/auth/service.py" in result

    def test_workspace_root_affects_resolution(self):
        """Test that workspace_root affects path resolution in links."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("print('hello')")

            renderer = CitationRenderer(workspace_root=tmpdir)
            result = renderer.render_cite_block(
                file_path="test.py",
                line_start=1,
                line_end=5,
            )
            assert "test.py" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
