"""Deterministic citation/fact coverage helpers for strict qoder-like verification."""

from __future__ import annotations

import re
from dataclasses import dataclass

CITATION_PATTERN = re.compile(r"<cite>\s*([^<]+?)\s*</cite>|\[cite:\s*([^\]]+?)\]")
CODE_FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")
SOURCE_LOOKING_URL_PATTERN = re.compile(
    r"(?:#L\d+|[?&]L\d+=|/blob/|/tree/|raw\.githubusercontent\.com|"
    r"\.(?:py|ts|tsx|js|jsx|java|go|rs|rb|php|cs|cpp|c|h|hpp|yaml|yml|json|toml|md)(?:[#?:/]|$))",
    re.IGNORECASE,
)
FACT_SIGNAL_PATTERN = re.compile(
    r"\b(?:is|are|uses|provides|implements|contains|handles|supports|depends|calls|writes|"
    r"reads|stores|loads|validates|authenticates|authorizes|maps|routes|generates|publishes|"
    r"exposes|returns|creates|updates|deletes|requires|owns|backs|connects|orchestrates)\b|"
    r"\b(?:GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+/|`[^`]+`|\b[A-Z][A-Za-z0-9_]*(?:Service|Model|API|Handler|Manager|Controller)\b",
    re.IGNORECASE,
)
UNRESOLVED_HEADING_PATTERN = re.compile(
    r"^#{1,6}\s+.*\b(?:unresolved|unknown|todo|open question|待确认|未确认|未识别|不明确)\b",
    re.IGNORECASE,
)
TOC_HEADING_PATTERN = re.compile(
    r"^#{1,6}\s+(?:table of contents|contents|toc|目录)\s*$", re.IGNORECASE
)


@dataclass(frozen=True)
class ClaimUnit:
    """A deterministic evidence-required factual unit extracted from markdown."""

    page: str
    line: int
    text: str


@dataclass(frozen=True)
class CitationRef:
    """A citation reference extracted from markdown."""

    raw: str
    line: int


def extract_citation_refs_with_lines(markdown: str) -> list[CitationRef]:
    """Return citation refs with 1-based line numbers."""

    refs: list[CitationRef] = []
    for line_no, line in enumerate(markdown.splitlines(), start=1):
        for match in CITATION_PATTERN.finditer(line):
            raw = match.group(1) or match.group(2) or ""
            raw = raw.strip()
            if raw:
                refs.append(CitationRef(raw=raw, line=line_no))
    return refs


def extract_claim_units(markdown: str, *, page: str = "") -> list[ClaimUnit]:
    """Extract deterministic evidence-required claim units from markdown.

    Units are prose/list sentences or blocks outside headings, code fences, tables, citation-only
    lines, TOC sections, and explicit unresolved/unknown sections. A unit requires evidence when
    it contains stable factual signals such as service/API/model identifiers, endpoint forms, or
    factual implementation verbs. No LLM or probabilistic NLP is used.
    """

    units: list[ClaimUnit] = []
    in_code = False
    in_unresolved = False
    in_toc = False
    paragraph: list[str] = []
    paragraph_start = 0

    def flush() -> None:
        nonlocal paragraph, paragraph_start
        if not paragraph:
            return
        text = " ".join(part.strip() for part in paragraph if part.strip()).strip()
        text = _strip_citations(text)
        for sentence in _split_sentences(text):
            if _is_evidence_required(sentence):
                units.append(ClaimUnit(page=page, line=paragraph_start, text=sentence))
        paragraph = []
        paragraph_start = 0

    for line_no, line in enumerate(markdown.splitlines(), start=1):
        stripped = line.strip()
        if CODE_FENCE_PATTERN.match(stripped):
            flush()
            in_code = not in_code
            continue
        if in_code:
            continue
        if stripped.startswith("#"):
            flush()
            in_unresolved = bool(UNRESOLVED_HEADING_PATTERN.match(stripped))
            in_toc = bool(TOC_HEADING_PATTERN.match(stripped))
            continue
        if in_unresolved:
            continue
        if in_toc:
            if stripped and not stripped.startswith(("-", "*", "+")):
                in_toc = False
            else:
                continue
        if not stripped:
            flush()
            continue
        if stripped.startswith("|"):
            flush()
            continue
        if _is_citation_only(stripped):
            flush()
            continue
        if stripped.startswith(("- ", "* ", "+ ")):
            flush()
            item = stripped[2:].strip()
            item = _strip_citations(item)
            if _is_evidence_required(item):
                units.append(ClaimUnit(page=page, line=line_no, text=item))
            continue
        if re.match(r"^\d+[.)]\s+", stripped):
            flush()
            item = re.sub(r"^\d+[.)]\s+", "", stripped)
            item = _strip_citations(item)
            if _is_evidence_required(item):
                units.append(ClaimUnit(page=page, line=line_no, text=item))
            continue
        if not paragraph:
            paragraph_start = line_no
        paragraph.append(stripped)
    flush()
    return units


def build_claim_coverage(
    markdown: str, *, page: str, valid_repo_citation_lines: set[int]
) -> dict[str, object]:
    """Compute deterministic claim coverage for a page.

    A claim unit is covered when a valid repository citation appears on the same line, the previous
    line, or the next line. The adjacency rule supports the generator's common pattern of placing a
    citation immediately after the factual paragraph while keeping coverage auditable.
    """

    claims = extract_claim_units(markdown, page=page)
    covered = 0
    uncovered: list[dict[str, object]] = []
    for claim in claims:
        citation_window = {claim.line - 1, claim.line, claim.line + 1}
        if citation_window & valid_repo_citation_lines:
            covered += 1
        else:
            uncovered.append({"page": claim.page, "line": claim.line, "text": claim.text[:180]})
    total = len(claims)
    ratio = 1.0 if total == 0 else covered / total
    return {"total": total, "covered": covered, "ratio": ratio, "uncovered": uncovered}


def is_source_looking_url(value: str) -> bool:
    """Return True for URL citations that look like source/line citations."""

    raw = value.strip()
    if raw.startswith("source:"):
        raw = raw[len("source:") :].strip()
    return raw.startswith(("http://", "https://")) and bool(SOURCE_LOOKING_URL_PATTERN.search(raw))


def is_external_url(value: str) -> bool:
    raw = value.strip()
    if raw.startswith("source:"):
        raw = raw[len("source:") :].strip()
    return raw.startswith(("http://", "https://"))


def _strip_citations(text: str) -> str:
    return CITATION_PATTERN.sub("", text).strip()


def _is_citation_only(text: str) -> bool:
    return not _strip_citations(text)


def _is_evidence_required(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 20:
        return False
    if stripped.startswith(("[", "![]")):
        return False
    return bool(FACT_SIGNAL_PATTERN.search(stripped))


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。.!?])\s+", text)
    return [part.strip() for part in parts if part.strip()]
