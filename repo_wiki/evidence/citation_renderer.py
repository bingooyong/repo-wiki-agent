"""Citation block renderer for generated Markdown with file/line citations.

This module renders source citations into generated Markdown:
- <cite> blocks for inline citations
- Section sources with file/line references
- Diagram sources with provenance tracking
- File/line links resolvable by verifier and IDE

Paths are kept workspace-relative for maximum portability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from repo_wiki.evidence.ranking import EvidenceCandidate, PageEvidenceBinding
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord

# Writers/LLMs sometimes emit scheme prefixes. Verifier looks up the literal
# path, so file:README.rst is treated as a missing file even when README.rst exists.
_DROP_CITATION_SCHEMES = ("file:", "path:", "relpath:")
_PLACEHOLDER_CITE_BODY = "start-end"
_CITE_BLOCK_RE = re.compile(r"(<cite>\s*)([^<]+?)(\s*</cite>)")
_BRACKET_CITE_RE = re.compile(r"(\[cite:\s*)([^\]]+?)(\])")
_CITE_PATH_SUFFIX_RE = re.compile(r"^(.+?)(:\d+(?:-\d+)?(?:\s*\([^)]+\))?)$")
_CITE_PAREN_RE = re.compile(r"（[^）]*）|\([^)]*\)")
_CITE_SPLIT_RE = re.compile(r"\s*[,，、]\s*")
_VALID_CITE_BODY_RE = re.compile(
    r"^(?P<path>.+?):(?P<start>\d+)(?:-(?P<end>\d+))?$",
)
_ROOT_README_MD = "README.md"
_ROOT_README_FALLBACKS = ("README.rst", "README.txt", "README")
_ROOT_README_NAMES = (_ROOT_README_MD, *_ROOT_README_FALLBACKS)
_ROOT_README_ALIASES = frozenset({"README", "README.md"})


def unique_root_readme_name(workspace_root: str | Path | None) -> str | None:
    """Return the only root README filename, or None if missing or ambiguous."""
    if workspace_root is None:
        return None
    root = Path(workspace_root)
    found = [name for name in _ROOT_README_NAMES if (root / name).is_file()]
    if len(found) == 1:
        return found[0]
    return None


def _remap_missing_readme_md(value: str, workspace_root: str | Path | None) -> str:
    """Map a missing root README.md / README cite to the one real root readme, if unique."""
    if workspace_root is None:
        return value
    root = Path(workspace_root)
    prefix = ""
    body = value
    if body.lower().startswith("source:"):
        prefix = "source:"
        body = body[len("source:") :].lstrip()
    match = _CITE_PATH_SUFFIX_RE.fullmatch(body)
    if match:
        path_text, suffix = match.group(1), match.group(2)
    else:
        path_text, suffix = body, ""
    path_key = path_text.replace("\\", "/")
    if path_key not in _ROOT_README_ALIASES:
        return value
    if (root / path_key).is_file():
        return value
    found = [name for name in _ROOT_README_NAMES if (root / name).is_file()]
    if len(found) != 1:
        return value
    return f"{prefix}{found[0]}{suffix}"


def normalize_citation_ref(raw: str, workspace_root: str | Path | None = None) -> str:
    """Return a citation target the verifier can resolve.

    Drops ``file:`` / ``path:`` / ``relpath:`` prefixes. Keeps ``source:`` and
    bare repo-relative paths, which already pass. Does not rewrite ``file://`` URIs.
    When ``README.md`` is missing and exactly one of ``README.rst`` / ``README.txt``
    / ``README`` exists at the repo root, remaps the cite to that file.
    """
    value = raw.strip()
    lowered = value.lower()
    if lowered.startswith("file://"):
        return value
    for scheme in _DROP_CITATION_SCHEMES:
        if lowered.startswith(scheme):
            value = value[len(scheme) :].lstrip()
            break
    return _remap_missing_readme_md(value, workspace_root)


def _coerce_path_line_cite(value: str, workspace_root: str | Path | None = None) -> str | None:
    """Return ``path:start`` / ``path:start-end`` or None when lines are not integers."""
    raw = normalize_citation_ref(value, workspace_root).strip()
    prefix = ""
    body = raw
    if body.lower().startswith("source:"):
        prefix = "source:"
        body = body[len("source:") :].lstrip()
    match = _VALID_CITE_BODY_RE.fullmatch(body)
    if not match:
        return None
    path_text = match.group("path").strip()
    start = match.group("start")
    end = match.group("end")
    if not path_text:
        return None
    if end:
        return f"{prefix}{path_text}:{start}-{end}"
    return f"{prefix}{path_text}:{start}"


def sanitize_citation_payloads(raw: str, workspace_root: str | Path | None = None) -> list[str]:
    """Keep only ``path:digits[-digits]`` cites; split joined payloads; drop the rest."""
    stripped = _CITE_PAREN_RE.sub("", raw).strip()
    if not stripped:
        return []
    parts = [part.strip() for part in _CITE_SPLIT_RE.split(stripped) if part.strip()]
    valid: list[str] = []
    for part in parts:
        coerced = _coerce_path_line_cite(part, workspace_root)
        if coerced:
            valid.append(coerced)
    return valid


def is_placeholder_citation_ref(raw: str) -> bool:
    """True for prompt-template leftovers such as ``relpath:start-end``."""
    value = normalize_citation_ref(raw).strip()
    if value.lower().startswith("source:"):
        value = value[len("source:") :].lstrip()
    return value.lower() == _PLACEHOLDER_CITE_BODY


def normalize_citation_markup(text: str, workspace_root: str | Path | None = None) -> str:
    """Rewrite cite blocks so verify sees only ``path:start-end`` targets.

    Strips parentheticals, splits comma-joined payloads, remaps README aliases
    onto the real root readme when unique, and drops unrepaired cite bodies.
    """

    def _rewrite_blocks(match: re.Match[str]) -> str:
        payloads = sanitize_citation_payloads(match.group(2), workspace_root)
        return "".join(f"<cite>{item}</cite>" for item in payloads)

    def _rewrite_brackets(match: re.Match[str]) -> str:
        payloads = sanitize_citation_payloads(match.group(2), workspace_root)
        return "".join(f"[cite: {item}]" for item in payloads)

    rewritten = _CITE_BLOCK_RE.sub(_rewrite_blocks, text)
    return _BRACKET_CITE_RE.sub(_rewrite_brackets, rewritten)


# ============================================================================
# Citation Block Types
# ============================================================================


@dataclass
class CiteBlock:
    """A <cite> block for inline source citation."""

    file_path: str  # Workspace-relative path
    line_start: int
    line_end: int
    symbol: str | None = None
    language: str | None = None
    label: str | None = None  # Human-readable label

    def render(self) -> str:
        """Render as Markdown-compatible <cite> block."""
        location = f"{self.file_path}:{self.line_start}"
        if self.line_end != self.line_start:
            location += f"-{self.line_end}"

        label_part = f" {self.label}" if self.label else ""
        symbol_part = f" ({self.symbol})" if self.symbol else ""

        return f"<cite>{location}{symbol_part}{label_part}</cite>"

    def render_link(self, base_path: str | None = None) -> str:
        """Render as IDE/verifier-resolvable link.

        Args:
            base_path: Optional base path for relative resolution

        Returns:
            Markdown link with file:// URI or relative path
        """
        if base_path:
            # Resolve relative to workspace
            full_path = Path(base_path) / self.file_path
        else:
            full_path = Path(self.file_path)

        location = f"{self.file_path}:{self.line_start}"
        if self.line_end != self.line_start:
            location += f"-{self.line_end}"

        symbol_part = f" ({self.symbol})" if self.symbol else ""
        display = f"{self.file_path}:{self.line_start}{symbol_part}"

        # Use file:// URI for IDE resolution when path is absolute
        if full_path.is_absolute():
            file_uri = full_path.as_uri()
        else:
            # For relative paths, use the path as-is with ./ prefix
            # This is resolvable by most IDEs and verifiers
            file_uri = f"./{self.file_path}"
        return f"[{display}]({file_uri})"


@dataclass
class SectionSource:
    """A section-level source citation."""

    section_id: str  # e.g., "architecture", "installation"
    page_id: str  # Wiki page this section belongs to
    doc_type: str  # e.g., "section", "module"
    citations: list[CiteBlock]  # Evidence spans backing this section

    def render(self) -> str:
        """Render as Markdown section source block."""
        if not self.citations:
            return ""

        lines = [f'!!! cite "{self.section_id}"']
        for cite in self.citations:
            lines.append(f"    {cite.render()}")
        lines.append("")  # Empty line after block
        return "\n".join(lines)


@dataclass
class DiagramSource:
    """A diagram with provenance/source tracking."""

    diagram_id: str
    diagram_type: str  # e.g., "mermaid", "plantuml", "graphviz"
    source_file: str | None = None  # File where diagram is defined
    source_lines: tuple[int, int] | None = None  # Line range in source
    evidence_spans: list[CiteBlock] | None = None  # Evidence backing the diagram
    description: str | None = None

    def render(self) -> str:
        """Render as Markdown diagram source block."""
        parts = [f'!!! diagram "{self.diagram_id}" ({self.diagram_type})']

        if self.source_file:
            parts.append(f"    source: {self.source_file}")
            if self.source_lines:
                parts.append(f"    lines: {self.source_lines[0]}-{self.source_lines[1]}")

        if self.description:
            parts.append(f"    desc: {self.description}")

        if self.evidence_spans:
            parts.append("    evidence:")
            for span in self.evidence_spans:
                parts.append(f"      - {span.render()}")

        parts.append("")
        return "\n".join(parts)


@dataclass
class FileLineLink:
    """A file:line reference link."""

    file_path: str
    line: int
    end_line: int | None = None
    symbol: str | None = None
    label: str | None = None

    def render(self) -> str:
        """Render as Markdown link."""
        location = f"{self.file_path}:{self.line}"
        if self.end_line and self.end_line != self.line:
            location += f"-{self.end_line}"

        label = self.label or (self.symbol if self.symbol else location)

        # Use file:// URI when path is absolute, otherwise use relative path
        path = Path(self.file_path)
        if path.is_absolute():
            file_uri = path.as_uri()
        else:
            file_uri = f"./{self.file_path}"
        return f"[{label}]({file_uri}#{self.line})"

    def render_simple(self) -> str:
        """Render as simple text reference without link."""
        location = f"{self.file_path}:{self.line}"
        if self.end_line and self.end_line != self.line:
            location += f"-{self.end_line}"

        if self.symbol:
            return f"{location} ({self.symbol})"
        return location


# ============================================================================
# Citation Renderer
# ============================================================================


class CitationRenderer:
    """Renders source citations into generated Markdown.

    This renderer takes evidence bindings and page sources and renders them
    into various citation formats for generated wiki pages.

    Paths are kept workspace-relative for maximum portability and IDE resolution.
    """

    def __init__(self, workspace_root: str | Path | None = None) -> None:
        """Initialize citation renderer.

        Args:
            workspace_root: Optional workspace root for absolute path resolution
        """
        self.workspace_root = Path(workspace_root) if workspace_root else None

    def render_cite_block(
        self,
        file_path: str,
        line_start: int,
        line_end: int,
        symbol: str | None = None,
        language: str | None = None,
        label: str | None = None,
    ) -> str:
        """Render a single <cite> block.

        Args:
            file_path: Workspace-relative file path
            line_start: Starting line number (1-based)
            line_end: Ending line number (1-based)
            symbol: Optional symbol name (function, class, etc.)
            language: Optional language for syntax highlighting
            label: Optional human-readable label

        Returns:
            Rendered <cite> block as Markdown string
        """
        cite = CiteBlock(
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            symbol=symbol,
            language=language,
            label=label,
        )
        return cite.render()

    def render_cite_block_from_span(
        self,
        span: EvidenceSpanRecord,
        label: str | None = None,
    ) -> str:
        """Render a <cite> block from an evidence span record.

        Args:
            span: Evidence span record
            label: Optional label override

        Returns:
            Rendered <cite> block as Markdown string
        """
        return self.render_cite_block(
            file_path=span.file_path,
            line_start=span.line_start,
            line_end=span.line_end,
            symbol=span.symbol,
            language=span.language,
            label=label,
        )

    def render_cite_block_from_candidate(
        self,
        candidate: EvidenceCandidate,
        label: str | None = None,
    ) -> str:
        """Render a <cite> block from an evidence candidate.

        Args:
            candidate: Evidence candidate with span
            label: Optional label override

        Returns:
            Rendered <cite> block as Markdown string
        """
        return self.render_cite_block_from_span(candidate.span, label=label)

    def render_section_sources(
        self,
        binding: PageEvidenceBinding,
        section_id: str | None = None,
    ) -> str:
        """Render section sources for a page binding.

        Args:
            binding: Page evidence binding with candidates
            section_id: Optional section identifier override

        Returns:
            Rendered section source block as Markdown string
        """
        section = section_id or binding.page_id

        citations = []
        for candidate in binding.candidates:
            cite = CiteBlock(
                file_path=candidate.span.file_path,
                line_start=candidate.span.line_start,
                line_end=candidate.span.line_end,
                symbol=candidate.span.symbol,
                language=candidate.span.language,
            )
            citations.append(cite)

        section_source = SectionSource(
            section_id=section,
            page_id=binding.page_id,
            doc_type=binding.doc_type,
            citations=citations,
        )
        return section_source.render()

    def render_page_citations(
        self,
        binding: PageEvidenceBinding,
    ) -> list[str]:
        """Render all citations for a page as a list of strings.

        Args:
            binding: Page evidence binding with candidates

        Returns:
            List of rendered <cite> block strings
        """
        return [
            self.render_cite_block_from_candidate(candidate) for candidate in binding.candidates
        ]

    def render_diagram_source(
        self,
        diagram_id: str,
        diagram_type: str,
        evidence_spans: list[EvidenceSpanRecord] | None = None,
        source_file: str | None = None,
        source_lines: tuple[int, int] | None = None,
        description: str | None = None,
    ) -> str:
        """Render a diagram source block with evidence tracking.

        Args:
            diagram_id: Unique diagram identifier
            diagram_type: Type of diagram (mermaid, plantuml, etc.)
            evidence_spans: Evidence spans backing this diagram
            source_file: Source file where diagram is defined
            source_lines: Line range in source file
            description: Human-readable description

        Returns:
            Rendered diagram source block as Markdown string
        """
        citations = None
        if evidence_spans:
            citations = [
                CiteBlock(
                    file_path=span.file_path,
                    line_start=span.line_start,
                    line_end=span.line_end,
                    symbol=span.symbol,
                    language=span.language,
                )
                for span in evidence_spans
            ]

        diagram = DiagramSource(
            diagram_id=diagram_id,
            diagram_type=diagram_type,
            source_file=source_file,
            source_lines=source_lines,
            evidence_spans=citations,
            description=description,
        )
        return diagram.render()

    def render_file_line_link(
        self,
        file_path: str,
        line: int,
        end_line: int | None = None,
        symbol: str | None = None,
        label: str | None = None,
    ) -> str:
        """Render a file:line link for IDE/verifier resolution.

        Args:
            file_path: Workspace-relative file path
            line: Line number (1-based)
            end_line: Optional end line for ranges
            symbol: Optional symbol name
            label: Optional display label

        Returns:
            Rendered Markdown link
        """
        link = FileLineLink(
            file_path=file_path,
            line=line,
            end_line=end_line,
            symbol=symbol,
            label=label,
        )
        return link.render()

    def render_sources_footer(
        self,
        binding: PageEvidenceBinding,
    ) -> str:
        """Render a sources footer for a wiki page.

        Args:
            binding: Page evidence binding with candidates

        Returns:
            Rendered sources section as Markdown string
        """
        if not binding.candidates:
            return ""

        lines = ["## Sources\n"]
        for i, candidate in enumerate(binding.candidates, 1):
            cite = self.render_cite_block_from_candidate(candidate, label=f"[{i}]")
            lines.append(f"- {cite}")

        return "\n".join(lines) + "\n"


# ============================================================================
# Error Detection for Citations
# ============================================================================


class CitationValidationError(Exception):
    """Raised when citation validation fails."""

    pass


class BrokenPathError(CitationValidationError):
    """Raised when a citation file path is broken/non-existent."""

    pass


class BadLineError(CitationValidationError):
    """Raised when a citation line range is invalid."""

    pass


def validate_citation_path(file_path: str, workspace_root: str | Path | None = None) -> Path:
    """Validate that a citation file path exists.

    Args:
        file_path: File path to validate
        workspace_root: Optional workspace root for relative path resolution

    Returns:
        Resolved Path object

    Raises:
        BrokenPathError: If file does not exist
    """
    path = Path(file_path)

    # If path is relative and workspace_root provided, resolve it
    if not path.is_absolute() and workspace_root:
        path = Path(workspace_root) / path

    if not path.exists():
        raise BrokenPathError(f"Citation file does not exist: {file_path}")

    if not path.is_file():
        raise BrokenPathError(f"Citation path is not a file: {file_path}")

    return path


def validate_line_range(
    line_start: int,
    line_end: int,
    file_path: str,
    workspace_root: str | Path | None = None,
) -> None:
    """Validate that a citation line range is valid.

    Args:
        line_start: Starting line (1-based)
        line_end: Ending line (1-based)
        file_path: File path for error messages
        workspace_root: Optional workspace root for file reading

    Raises:
        BadLineError: If line range is invalid
    """
    if line_start < 1:
        raise BadLineError(f"Line start must be >= 1, got {line_start} in {file_path}")

    if line_end < line_start:
        raise BadLineError(
            f"Line end ({line_end}) must be >= line start ({line_start}) in {file_path}"
        )

    # Check if lines exist in file
    try:
        path = validate_citation_path(file_path, workspace_root)
        with open(path, encoding="utf-8") as f:
            line_count = sum(1 for _ in f)

        if line_end > line_count:
            raise BadLineError(
                f"Line end ({line_end}) exceeds file length ({line_count}) in {file_path}"
            )
    except BrokenPathError:
        # Don't fail validation if file doesn't exist - that's a separate error
        pass


def validate_citation(
    file_path: str,
    line_start: int,
    line_end: int,
    workspace_root: str | Path | None = None,
) -> None:
    """Validate a complete citation.

    Args:
        file_path: File path to validate
        line_start: Starting line (1-based)
        line_end: Ending line (1-based)
        workspace_root: Optional workspace root for resolution

    Raises:
        BrokenPathError: If file path is broken
        BadLineError: If line range is invalid
    """
    validate_citation_path(file_path, workspace_root)
    validate_line_range(line_start, line_end, file_path, workspace_root)
