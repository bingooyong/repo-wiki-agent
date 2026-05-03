"""Evidence builder module for file and line citations.

This module provides:
- Source span extraction (Task 23.1)
- Evidence SQLite schema (Task 23.2)
- Evidence ranking and page matching (Task 23.3)
- Citation block rendering (Task 23.4)
- Citation verification (Task 23.5)
- Page evidence scoring (Task 33.2)
- Service ownership resolver (Task 33.1)
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
from repo_wiki.evidence.page_evidence_scorer import (
    PageEvidenceScorer,
    ServiceLocalPreference,
    EvidenceRejectionReason,
    ScoredEvidenceCandidate,
    PageEvidenceScoreResult,
    score_page_evidence,
    get_rejection_reasons,
)
from repo_wiki.evidence.service_ownership import (
    ServiceOwnershipResolver,
    OwnershipVerifier,
    OwnershipConfidence,
    OwnershipDecision,
    filter_evidence_by_ownership,
)

__all__ = [
    # Ranking
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
    # Page evidence scorer (Task 33.2)
    "PageEvidenceScorer",
    "ServiceLocalPreference",
    "EvidenceRejectionReason",
    "ScoredEvidenceCandidate",
    "PageEvidenceScoreResult",
    "score_page_evidence",
    "get_rejection_reasons",
    # Service ownership (Task 33.1)
    "ServiceOwnershipResolver",
    "OwnershipVerifier",
    "OwnershipConfidence",
    "OwnershipDecision",
    "filter_evidence_by_ownership",
]