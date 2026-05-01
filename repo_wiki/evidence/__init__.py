"""Evidence builder module for file and line citations.

This module provides:
- Source span extraction (Task 23.1)
- Evidence SQLite schema (Task 23.2)
- Evidence ranking and page matching (Task 23.3)
- Citation block rendering (Task 23.4)
- Citation verification (Task 23.5)
"""
from __future__ import annotations

from repo_wiki.evidence.ranking import (
    EvidenceRanker,
    EvidenceCandidate,
    EvidenceRankingResult,
    PageEvidenceBinding,
    MIN_CANDIDATES_PER_PAGE,
    score_evidence_for_page,
    rank_evidence_for_page,
)
from repo_wiki.evidence.citation_renderer import (
    CitationRenderer,
    CiteBlock,
    SectionSource,
    DiagramSource,
    FileLineLink,
    BrokenPathError,
    BadLineError,
    validate_citation_path,
    validate_line_range,
    validate_citation,
)

__all__ = [
    "EvidenceRanker",
    "EvidenceCandidate",
    "EvidenceRankingResult",
    "PageEvidenceBinding",
    "MIN_CANDIDATES_PER_PAGE",
    "score_evidence_for_page",
    "rank_evidence_for_page",
    # Citation renderer
    "CitationRenderer",
    "CiteBlock",
    "SectionSource",
    "DiagramSource",
    "FileLineLink",
    "BrokenPathError",
    "BadLineError",
    "validate_citation_path",
    "validate_line_range",
    "validate_citation",
]