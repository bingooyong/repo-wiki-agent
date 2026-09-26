"""Require code-repo handbooks to cite product source, not only README/docs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from repo_wiki.evidence.citation_renderer import normalize_citation_ref

PRODUCT_SOURCE_EXTS = frozenset({".py", ".go", ".java", ".kt", ".ts", ".tsx", ".js", ".jsx", ".rs"})
_SKIP_DIR_PARTS = frozenset(
    {
        ".git",
        ".repo-agent-eval",
        ".repo-wiki",
        "node_modules",
        "vendor",
        ".venv",
        "venv",
        "__pycache__",
        "dist",
        "build",
        "testdata",
        ".trellis",
        ".trae",
        ".cursor",
        ".claude",
        ".codex",
    }
)
MIN_PRODUCT_SOURCE_FILES = 8
MIN_HANDBOOK_CITATIONS = 20
MIN_SOURCE_CITATION_RATIO = 0.08
_CITE_RE = re.compile(r"<cite>\s*([^<]+?)\s*</cite>|\[cite:\s*([^\]]+?)\]", re.IGNORECASE)


@dataclass(frozen=True)
class SourceCitationStats:
    total_citations: int
    source_citations: int
    product_source_files: int

    @property
    def source_ratio(self) -> float:
        if self.total_citations == 0:
            return 1.0
        return self.source_citations / self.total_citations


def _is_skipped(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    return any(part in _SKIP_DIR_PARTS for part in parts)


def count_product_source_files(repo_root: Path) -> int:
    if not repo_root.exists():
        return 0
    count = 0
    for path in repo_root.rglob("*"):
        if not path.is_file() or _is_skipped(path, repo_root):
            continue
        if path.suffix.lower() in PRODUCT_SOURCE_EXTS:
            name = path.name.lower()
            if _is_generated_or_test_source(path.as_posix()):
                continue
            count += 1
    return count


def source_evidence_should_apply(repo_root: Path) -> bool:
    return count_product_source_files(repo_root) >= MIN_PRODUCT_SOURCE_FILES


def _citation_path(raw: str, repo_root: Path) -> str:
    value = normalize_citation_ref(raw, repo_root)
    if value.lower().startswith("source:"):
        value = value[len("source:") :].lstrip()
    return value.split(":")[0].replace("\\", "/").strip()


def handbook_source_citation_stats(content_dir: Path, repo_root: Path) -> SourceCitationStats:
    total = 0
    source = 0
    for page in content_dir.rglob("*.md"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        for match in _CITE_RE.finditer(text):
            raw = match.group(1) or match.group(2) or ""
            path_text = _citation_path(raw, repo_root)
            if not path_text:
                continue
            total += 1
            if _is_product_source_citation(path_text):
                source += 1
    return SourceCitationStats(
        total_citations=total,
        source_citations=source,
        product_source_files=count_product_source_files(repo_root),
    )


def _is_generated_or_test_source(path_text: str) -> bool:
    name = Path(path_text).name.lower()
    if name.endswith(".pb.go") or name.endswith("_grpc.pb.go"):
        return True
    if name.endswith("_test.go") or name.startswith("test_") or name.endswith("_test.py"):
        return True
    parts = [part.lower() for part in Path(path_text.replace("\\", "/")).parts]
    return "testdata" in parts


def _is_product_source_citation(path_text: str) -> bool:
    suffix = Path(path_text).suffix.lower()
    if suffix not in PRODUCT_SOURCE_EXTS:
        return False
    return not _is_generated_or_test_source(path_text)


def source_evidence_is_sufficient(stats: SourceCitationStats) -> bool:
    if stats.product_source_files < MIN_PRODUCT_SOURCE_FILES:
        return True
    if stats.total_citations < MIN_HANDBOOK_CITATIONS:
        return True
    return stats.source_ratio >= MIN_SOURCE_CITATION_RATIO
