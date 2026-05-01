"""Chunking pipeline in frozen order: function -> class -> module."""

from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass
from typing import Callable, Iterable, List, Sequence


SanitizeFn = Callable[[str], str]


@dataclass
class Chunk:
    chunk_id: str
    file_path: str
    module_name: str
    language: str
    chunk_type: str
    symbol_name: str
    line_start: int
    line_end: int
    dependencies: List[str]
    text: str

    def to_record(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "file_path": self.file_path,
            "module_name": self.module_name,
            "language": self.language,
            "chunk_type": self.chunk_type,
            "symbol_name": self.symbol_name,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "dependencies": self.dependencies,
            "text": self.text,
        }


def _slice_lines(source: str, start: int, end: int) -> str:
    lines = source.splitlines()
    if not lines:
        return ""
    return "\n".join(lines[max(start - 1, 0) : max(end, 0)])


def _build_chunk_id(
    file_path: str,
    chunk_type: str,
    symbol_name: str,
    line_start: int,
    line_end: int,
) -> str:
    payload = f"{file_path}|{chunk_type}|{symbol_name}|{line_start}|{line_end}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _python_dependencies(tree: ast.AST) -> List[str]:
    deps = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                deps.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            deps.add(node.module)
    return sorted(deps)


def _python_chunks(
    source: str,
    file_path: str,
    module_name: str,
    language: str,
    sanitize_text: SanitizeFn,
) -> List[Chunk]:
    tree = ast.parse(source)
    parent = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node

    deps = _python_dependencies(tree)
    chunks: List[Chunk] = []

    function_nodes = []
    class_nodes = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_nodes.append(node)
        elif isinstance(node, ast.ClassDef):
            class_nodes.append(node)

    for node in sorted(function_nodes, key=lambda n: n.lineno):
        line_end = getattr(node, "end_lineno", node.lineno)
        owner = parent.get(node)
        if isinstance(owner, ast.ClassDef):
            symbol = f"{owner.name}.{node.name}"
        else:
            symbol = node.name
        text = sanitize_text(_slice_lines(source, node.lineno, line_end))
        chunks.append(
            Chunk(
                chunk_id=_build_chunk_id(file_path, "function", symbol, node.lineno, line_end),
                file_path=file_path,
                module_name=module_name,
                language=language,
                chunk_type="function",
                symbol_name=symbol,
                line_start=node.lineno,
                line_end=line_end,
                dependencies=deps,
                text=text,
            )
        )

    for node in sorted(class_nodes, key=lambda n: n.lineno):
        line_end = getattr(node, "end_lineno", node.lineno)
        text = sanitize_text(_slice_lines(source, node.lineno, line_end))
        chunks.append(
            Chunk(
                chunk_id=_build_chunk_id(file_path, "class", node.name, node.lineno, line_end),
                file_path=file_path,
                module_name=module_name,
                language=language,
                chunk_type="class",
                symbol_name=node.name,
                line_start=node.lineno,
                line_end=line_end,
                dependencies=deps,
                text=text,
            )
        )

    total_lines = max(len(source.splitlines()), 1)
    module_text = sanitize_text(source)
    chunks.append(
        Chunk(
            chunk_id=_build_chunk_id(file_path, "module", module_name, 1, total_lines),
            file_path=file_path,
            module_name=module_name,
            language=language,
            chunk_type="module",
            symbol_name=module_name,
            line_start=1,
            line_end=total_lines,
            dependencies=deps,
            text=module_text,
        )
    )
    return chunks


def _heuristic_ranges(source: str, patterns: Sequence[tuple[str, str]]) -> Iterable[tuple[str, str, int, int]]:
    lines = source.splitlines()
    markers = []
    for idx, line in enumerate(lines, start=1):
        for chunk_type, pattern in patterns:
            match = re.match(pattern, line)
            if match:
                name = match.group(1)
                markers.append((chunk_type, name, idx))

    if not markers:
        return []

    markers_sorted = sorted(markers, key=lambda item: item[2])
    ranges = []
    for i, (chunk_type, name, start) in enumerate(markers_sorted):
        if i + 1 < len(markers_sorted):
            end = markers_sorted[i + 1][2] - 1
        else:
            end = len(lines)
        ranges.append((chunk_type, name, start, max(start, end)))
    return ranges


def _generic_chunks(
    source: str,
    file_path: str,
    module_name: str,
    language: str,
    sanitize_text: SanitizeFn,
) -> List[Chunk]:
    patterns = [
        ("function", r"^\s*(?:def|async\s+def|function|func)\s+([A-Za-z_][A-Za-z0-9_]*)"),
        ("class", r"^\s*(?:class|type)\s+([A-Za-z_][A-Za-z0-9_]*)"),
    ]
    chunk_ranges = list(_heuristic_ranges(source, patterns))
    function_ranges = [item for item in chunk_ranges if item[0] == "function"]
    class_ranges = [item for item in chunk_ranges if item[0] == "class"]
    ordered_ranges = function_ranges + class_ranges

    chunks: List[Chunk] = []
    for chunk_type, symbol, start, end in ordered_ranges:
        text = sanitize_text(_slice_lines(source, start, end))
        chunks.append(
            Chunk(
                chunk_id=_build_chunk_id(file_path, chunk_type, symbol, start, end),
                file_path=file_path,
                module_name=module_name,
                language=language,
                chunk_type=chunk_type,
                symbol_name=symbol,
                line_start=start,
                line_end=end,
                dependencies=[],
                text=text,
            )
        )

    total_lines = max(len(source.splitlines()), 1)
    chunks.append(
        Chunk(
            chunk_id=_build_chunk_id(file_path, "module", module_name, 1, total_lines),
            file_path=file_path,
            module_name=module_name,
            language=language,
            chunk_type="module",
            symbol_name=module_name,
            line_start=1,
            line_end=total_lines,
            dependencies=[],
            text=sanitize_text(source),
        )
    )
    return chunks


def chunk_source(
    source: str,
    *,
    file_path: str,
    module_name: str,
    language: str = "python",
    sanitize_text: SanitizeFn | None = None,
) -> List[Chunk]:
    sanitize = sanitize_text or (lambda text: text)
    if language.lower() == "python":
        try:
            return _python_chunks(source, file_path, module_name, language, sanitize)
        except SyntaxError:
            pass
    return _generic_chunks(source, file_path, module_name, language, sanitize)
