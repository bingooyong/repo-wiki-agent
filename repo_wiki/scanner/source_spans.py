from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Literal

# Supported languages and their file extensions
LANGUAGE_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "java": (".java",),
    "python": (".py",),
    "typescript": (".ts", ".tsx", ".js", ".jsx"),
    "sql": (".sql",),
    "yaml": (".yaml", ".yml"),
    "markdown": (".md",),
}

# Reverse lookup: extension -> language
EXT_TO_LANG: dict[str, str] = {
    ext: lang for lang, exts in LANGUAGE_EXTENSIONS.items() for ext in exts
}


@dataclass
class SourceSpan:
    """Represents a source code span with file, symbol, and line range information.

    Used for evidence building with file and line citations.
    """

    file: str  # Workspace-relative path
    symbol: str  # Symbol name (function, class, table, etc.)
    line_start: int  # 1-based line number
    line_end: int  # 1-based line number
    language: str  # Programming/markup language
    summary: str = ""  # Human-readable summary
    digest: str = ""  # SHA256 digest for invalidation

    def __post_init__(self) -> None:
        if not self.digest:
            self.digest = self._compute_digest()

    def _compute_digest(self) -> str:
        """Compute SHA256 digest for change detection."""
        content = f"{self.file}:{self.symbol}:{self.line_start}-{self.line_end}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def citation(self) -> str:
        """Return a citation string like 'file.py:10-20'."""
        return f"{self.file}:{self.line_start}-{self.line_end}"

    def is_valid(self) -> bool:
        """Check if the span has valid line numbers."""
        return 1 <= self.line_start <= self.line_end


@dataclass
class SourceSpanExtractor:
    """Extracts source spans from code files for evidence building."""

    def extract_from_file(self, file_path: Path, content: str) -> list[SourceSpan]:
        """Extract all source spans from a file."""
        lang = self._detect_language(file_path)
        if lang == "unknown":
            return []

        extractor = _EXTRACTORS.get(lang)
        if extractor is None:
            return []

        return extractor(file_path, content)

    def extract_from_files(
        self, files: list[tuple[Path, str]]
    ) -> list[SourceSpan]:
        """Extract spans from multiple files.

        Args:
            files: List of (relative_path, content) tuples
        """
        spans = []
        for path, content in files:
            spans.extend(self.extract_from_file(path, content))
        return spans

    @staticmethod
    def _detect_language(file_path: Path) -> str:
        """Detect language from file extension."""
        suffix = file_path.suffix.lower()
        return EXT_TO_LANG.get(suffix, "unknown")


# ---------------------------------------------------------------------------
# Language-specific extractors
# ---------------------------------------------------------------------------


def _extract_python(file_path: Path, content: str) -> list[SourceSpan]:
    """Extract spans from Python source."""
    spans: list[SourceSpan] = []
    lines = content.splitlines()

    # Match class definitions
    for match in _regex_finditer(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)", content, re.MULTILINE):
        name = match.group(1)
        start_line = content[: match.start()].count("\n") + 1
        end_line = _find_block_end(lines, start_line - 1, "class", "def")
        spans.append(
            SourceSpan(
                file=file_path.as_posix(),
                symbol=name,
                line_start=start_line,
                line_end=end_line,
                language="python",
                summary=f"Python class '{name}'",
            )
        )

    # Match function definitions (including async)
    for match in _regex_finditer(
        r"^(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)", content, re.MULTILINE
    ):
        name = match.group(1)
        start_line = content[: match.start()].count("\n") + 1
        end_line = _find_block_end(lines, start_line - 1, "def", None)
        spans.append(
            SourceSpan(
                file=file_path.as_posix(),
                symbol=name,
                line_start=start_line,
                line_end=end_line,
                language="python",
                summary=f"Python function '{name}()'",
            )
        )

    return spans


def _extract_java(file_path: Path, content: str) -> list[SourceSpan]:
    """Extract spans from Java source."""
    spans: list[SourceSpan] = []
    lines = content.splitlines()

    # Match class, interface, enum definitions
    for match in _regex_finditer(
        r"^(?:public|private|protected)?\s*(?:abstract|final)?\s*(class|interface|enum)\s+([A-Za-z_][A-Za-z0-9_]*)",
        content,
        re.MULTILINE,
    ):
        kind = match.group(1)  # 'class', 'interface', or 'enum'
        name = match.group(2)
        start_line = content[: match.start()].count("\n") + 1
        end_line = _find_block_end(lines, start_line - 1, "{", None)
        spans.append(
            SourceSpan(
                file=file_path.as_posix(),
                symbol=name,
                line_start=start_line,
                line_end=end_line,
                language="java",
                summary=f"Java {kind} '{name}'",
            )
        )

    # Match method definitions (allowing leading whitespace for indentation)
    for match in _regex_finditer(
        r"^\s*(?:public|private|protected)?\s*(?:static)?\s*(?:\w+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        content,
        re.MULTILINE,
    ):
        name = match.group(1)
        # Skip constructors and known framework methods
        if name in ("if", "while", "for", "switch", "catch"):
            continue
        start_line = content[: match.start()].count("\n") + 1
        end_line = _find_block_end(lines, start_line - 1, "{", None)
        spans.append(
            SourceSpan(
                file=file_path.as_posix(),
                symbol=name,
                line_start=start_line,
                line_end=end_line,
                language="java",
                summary=f"Java method '{name}()'",
            )
        )

    return spans


def _extract_typescript(file_path: Path, content: str) -> list[SourceSpan]:
    """Extract spans from TypeScript/JavaScript source."""
    spans: list[SourceSpan] = []
    lines = content.splitlines()

    # Match class definitions (including export)
    for match in _regex_finditer(r"^(?:export\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)", content, re.MULTILINE):
        name = match.group(1)
        start_line = content[: match.start()].count("\n") + 1
        end_line = _find_block_end(lines, start_line - 1, "{", None)
        export_prefix = "export " if match.group(0).startswith("export") else ""
        spans.append(
            SourceSpan(
                file=file_path.as_posix(),
                symbol=name,
                line_start=start_line,
                line_end=end_line,
                language="typescript",
                summary=f"TypeScript {export_prefix}class '{name}'",
            )
        )

    # Match function declarations (including async, arrow functions)
    for match in _regex_finditer(
        r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)",
        content,
        re.MULTILINE,
    ):
        name = match.group(1)
        start_line = content[: match.start()].count("\n") + 1
        end_line = _find_block_end(lines, start_line - 1, "{", None)
        spans.append(
            SourceSpan(
                file=file_path.as_posix(),
                symbol=name,
                line_start=start_line,
                line_end=end_line,
                language="typescript",
                summary=f"TypeScript function '{name}()'",
            )
        )

    # Match const/let/var with function (arrow functions)
    for match in _regex_finditer(
        r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=",
        content,
        re.MULTILINE,
    ):
        name = match.group(1)
        start_line = content[: match.start()].count("\n") + 1
        end_line = _find_block_end_arrow(lines, start_line - 1)
        spans.append(
            SourceSpan(
                file=file_path.as_posix(),
                symbol=name,
                line_start=start_line,
                line_end=end_line,
                language="typescript",
                summary=f"TypeScript variable '{name}'",
            )
        )

    # Match interface and type definitions
    for match in _regex_finditer(
        r"^(?:export\s+)?(interface|type)\s+([A-Za-z_][A-Za-z0-9_]*)",
        content,
        re.MULTILINE,
    ):
        kind = match.group(1)  # 'interface' or 'type'
        name = match.group(2)
        start_line = content[: match.start()].count("\n") + 1
        end_line = _find_block_end(lines, start_line - 1, "{", None)
        spans.append(
            SourceSpan(
                file=file_path.as_posix(),
                symbol=name,
                line_start=start_line,
                line_end=end_line,
                language="typescript",
                summary=f"TypeScript {kind} '{name}'",
            )
        )

    return spans


def _extract_sql(file_path: Path, content: str) -> list[SourceSpan]:
    """Extract spans from SQL source."""
    spans: list[SourceSpan] = []

    # Match CREATE TABLE statements
    for match in _regex_finditer(
        r"(?i)CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)",
        content,
    ):
        name = match.group(1)
        start_line = content[: match.start()].count("\n") + 1
        end_line = _find_sql_block_end(content, match.end())
        spans.append(
            SourceSpan(
                file=file_path.as_posix(),
                symbol=name,
                line_start=start_line,
                line_end=end_line,
                language="sql",
                summary=f"SQL table '{name}'",
            )
        )

    # Match CREATE INDEX statements
    for match in _regex_finditer(
        r"(?i)CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)",
        content,
    ):
        name = match.group(1)
        start_line = content[: match.start()].count("\n") + 1
        end_line = content[: match.end()].count("\n") + 1
        spans.append(
            SourceSpan(
                file=file_path.as_posix(),
                symbol=name,
                line_start=start_line,
                line_end=end_line,
                language="sql",
                summary=f"SQL index '{name}'",
            )
        )

    # Match CREATE VIEW statements
    for match in _regex_finditer(
        r"(?i)CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+([A-Za-z_][A-Za-z0-9_]*)",
        content,
    ):
        name = match.group(1)
        start_line = content[: match.start()].count("\n") + 1
        end_line = _find_sql_block_end(content, match.end())
        spans.append(
            SourceSpan(
                file=file_path.as_posix(),
                symbol=name,
                line_start=start_line,
                line_end=end_line,
                language="sql",
                summary=f"SQL view '{name}'",
            )
        )

    # Match CREATE FUNCTION/PROCEDURE statements
    for match in _regex_finditer(
        r"(?i)CREATE\s+(?:OR\s+REPLACE\s+)?(?:FUNCTION|PROCEDURE)\s+([A-Za-z_][A-Za-z0-9_]*)",
        content,
    ):
        name = match.group(1)
        start_line = content[: match.start()].count("\n") + 1
        end_line = _find_sql_block_end(content, match.end())
        spans.append(
            SourceSpan(
                file=file_path.as_posix(),
                symbol=name,
                line_start=start_line,
                line_end=end_line,
                language="sql",
                summary=f"SQL routine '{name}'",
            )
        )

    return spans


def _extract_yaml(file_path: Path, content: str) -> list[SourceSpan]:
    """Extract spans from YAML source."""
    spans: list[SourceSpan] = []
    lines = content.splitlines()

    # Match top-level keys as "sections"
    current_key = ""
    key_start_line = 1

    for i, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
            # Check for key: pattern
            key_match = re.match(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", line)
            if key_match:
                indent = len(key_match.group(1))
                if indent == 0:
                    # Top-level key
                    if current_key:
                        spans.append(
                            SourceSpan(
                                file=file_path.as_posix(),
                                symbol=current_key,
                                line_start=key_start_line,
                                line_end=i - 1,
                                language="yaml",
                                summary=f"YAML key '{current_key}'",
                            )
                        )
                    current_key = key_match.group(2)
                    key_start_line = i

    # Don't forget the last key
    if current_key:
        spans.append(
            SourceSpan(
                file=file_path.as_posix(),
                symbol=current_key,
                line_start=key_start_line,
                line_end=len(lines),
                language="yaml",
                summary=f"YAML key '{current_key}'",
            )
        )

    return spans


def _extract_markdown(file_path: Path, content: str) -> list[SourceSpan]:
    """Extract spans from Markdown source."""
    spans: list[SourceSpan] = []
    lines = content.splitlines()

    current_heading = ""
    heading_start_line = 1

    for i, line in enumerate(lines, start=1):
        # Match ATX-style headings (# heading)
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            level = len(match.group(1))
            heading_text = match.group(2).strip()

            if current_heading:
                spans.append(
                    SourceSpan(
                        file=file_path.as_posix(),
                        symbol=current_heading,
                        line_start=heading_start_line,
                        line_end=i - 1,
                        language="markdown",
                        summary=f"Markdown section '{current_heading}' (h{level - 1})",
                    )
                )

            current_heading = heading_text
            heading_start_line = i

    # Don't forget the last heading/section
    if current_heading:
        spans.append(
            SourceSpan(
                file=file_path.as_posix(),
                symbol=current_heading,
                line_start=heading_start_line,
                line_end=len(lines),
                language="markdown",
                summary=f"Markdown section '{current_heading}'",
            )
        )

    return spans


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

_EXTRACTORS: dict[str, callable] = {
    "python": _extract_python,
    "java": _extract_java,
    "typescript": _extract_typescript,
    "sql": _extract_sql,
    "yaml": _extract_yaml,
    "markdown": _extract_markdown,
}


def _regex_finditer(pattern: str, text: str, flags: re.RegexFlag = 0) -> Iterator[re.Match]:
    """Safely find regex matches, returning empty iterator on error."""
    try:
        return re.finditer(pattern, text, flags)
    except re.error:
        return iter([])


def _find_block_end(
    lines: list[str], start_idx: int, start_char: str, end_word: str | None
) -> int:
    """Find the line index where a code block ends.

    Args:
        lines: All lines in the file (0-indexed)
        start_idx: 0-based index where the block starts
        start_char: Opening character to match ('{', 'class', 'def', etc.)
        end_word: If not None, also stop at lines that start with this word at same indent

    Returns:
        1-based line number where block ends
    """
    if start_idx < 0 or start_idx >= len(lines):
        return start_idx + 1

    start_line = lines[start_idx]

    # Determine base indent
    base_indent = len(start_line) - len(start_line.lstrip())

    # Handle Python def/class blocks
    if start_char in ("def", "class"):
        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip())
            # Found next item at same or lower indent
            if indent <= base_indent:
                return i  # 1-based
        return len(lines)  # 1-based

    # Handle brace-delimited blocks
    if start_char == "{":
        brace_count = start_line.count("{") - start_line.count("}")
        for i in range(start_idx + 1, len(lines)):
            brace_count += lines[i].count("{") - lines[i].count("}")
            if brace_count <= 0:
                return i + 1  # 1-based
        return len(lines)  # 1-based

    # Default: single line
    return start_idx + 1  # 1-based


def _find_block_end_arrow(lines: list[str], start_idx: int) -> int:
    """Find end of an arrow function or assignment.

    Handles:
        const foo = () => { ... };
        const foo = async () => { ... };
        let bar = something;
    """
    if start_idx < 0 or start_idx >= len(lines):
        return start_idx + 1

    start_line = lines[start_idx]

    # If line ends with { and ;, find matching }
    if "=>" in start_line or "=" in start_line:
        # Single line case
        if start_line.strip().endswith((";", ",")) and "{" not in start_line:
            return start_idx + 1

        # Multi-line case
        if "{" in start_line:
            brace_count = start_line.count("{") - start_line.count("}")
            for i in range(start_idx + 1, len(lines)):
                brace_count += lines[i].count("{") - lines[i].count("}")
                if brace_count <= 0:
                    return i + 1  # 1-based
                # Check for statement ending with ;
                if brace_count == 0 and ";" in lines[i]:
                    return i + 1  # 1-based

    return start_idx + 1  # 1-based


def _find_sql_block_end(content: str, start_pos: int) -> int:
    """Find end line of a SQL statement/block."""
    lines_before = content[:start_pos].count("\n")
    text_after = content[start_pos:]

    # Find semicolon that ends the statement
    # But ignore semicolons inside string literals or nested blocks
    in_string = False
    string_char = ""
    paren_depth = 0
    bracket_depth = 0

    for i, char in enumerate(text_after):
        if char in ("'", '"', "`") and (i == 0 or text_after[i - 1] != "\\"):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False

        if not in_string:
            if char == "(":
                paren_depth += 1
            elif char == ")":
                paren_depth -= 1
            elif char == "[":
                bracket_depth += 1
            elif char == "]":
                bracket_depth -= 1
            elif char == ";" and paren_depth == 0 and bracket_depth == 0:
                # End of statement
                return lines_before + text_after[:i].count("\n") + 1

    # No semicolon found, return last line
    return content.count("\n") + 1


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def compute_span_digest(file_path: str, line_start: int, line_end: int) -> str:
    """Compute a digest for a span for later invalidation."""
    content = f"{file_path}:{line_start}-{line_end}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def group_spans_by_file(spans: list[SourceSpan]) -> dict[str, list[SourceSpan]]:
    """Group spans by file path."""
    result: dict[str, list[SourceSpan]] = {}
    for span in spans:
        if span.file not in result:
            result[span.file] = []
        result[span.file].append(span)
    return result


def filter_spans_by_language(
    spans: list[SourceSpan], languages: list[str]
) -> list[SourceSpan]:
    """Filter spans to only include specified languages."""
    return [s for s in spans if s.language in languages]


def spans_to_citations(spans: list[SourceSpan]) -> list[str]:
    """Convert spans to citation strings."""
    return [s.citation() for s in spans]
