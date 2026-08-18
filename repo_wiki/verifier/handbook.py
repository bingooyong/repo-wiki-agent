"""Handbook wiki helpers: generator-meta detection and page-local quality rejects."""

from __future__ import annotations

HANDBOOK_META_PHRASES = (
    "fallback composer",
    "repo-agent",
    "该页面对应",
    "evidence ranking",
)

GENERATOR_META_REJECTION = "Handbook generator meta content"

_PAGE_LOCAL_QUALITY_REJECTIONS = frozenset(
    {
        "Insufficient prose content",
        GENERATOR_META_REJECTION,
    }
)


def contains_generator_meta(markdown: str) -> bool:
    """Return True when markdown contains generator self-description phrases."""
    if not markdown:
        return False
    lowered = markdown.lower()
    for phrase in HANDBOOK_META_PHRASES:
        needle = phrase.lower()
        if needle in lowered:
            return True
    return False


def is_page_local_quality_rejection(reason: str | None) -> bool:
    """Quality rejects after HTTP 200 are page-local, not provider outages."""
    return reason in _PAGE_LOCAL_QUALITY_REJECTIONS
