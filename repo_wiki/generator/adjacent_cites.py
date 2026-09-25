"""Place evidence citations on the same line or next line as factual claims."""

from __future__ import annotations

import re
from pathlib import Path

from repo_wiki.verifier.citation_fact_coverage import (
    extract_citation_refs_with_lines,
    extract_claim_units,
)

_CITE_TAG_RE = re.compile(
    r"<cite>\s*([^:<]+):(\d+)(?:-(\d+))?(?:\s*\([^)]*\))?\s*</cite>",
    re.IGNORECASE,
)
_IDENT_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]{3,})`")
_FILE_SUFFIXES = (".py", ".go", ".md", ".yml", ".yaml", ".rst", ".json", ".sql", ".toml")


def sentence_identifiers(text: str) -> set[str]:
    """Backticked identifiers used by the cite-relevance heuristic."""
    found = {
        item
        for item in _IDENT_RE.findall(text or "")
        if "/" not in item and not item.endswith(_FILE_SUFFIXES)
    }
    return {item.split(".")[-1] for item in found if len(item.split(".")[-1]) >= 4}


def _parse_cite_tag(tag: str) -> tuple[str, int, int] | None:
    match = _CITE_TAG_RE.search(tag)
    if not match:
        return None
    start = int(match.group(2))
    end = int(match.group(3) or start)
    return match.group(1).strip(), start, end


def _cite_window(tag: str, root: Path) -> str:
    parsed = _parse_cite_tag(tag)
    if not parsed:
        return ""
    rel, start, end = parsed
    path = root / rel
    try:
        if not path.is_file():
            return ""
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[max(0, start - 4) : end + 3])


def _first_matching_tag(idents: set[str], tags: list[str], root: Path) -> str | None:
    for tag in tags:
        window = _cite_window(tag, root)
        if window and any(ident in window for ident in idents):
            return tag
    return None


def is_cite_realign_page(page: object | None) -> bool:
    title = str(getattr(page, "title", "") or "")
    stem = Path(str(getattr(page, "output_path", "") or "")).stem
    return title in {"核心服务", "数据库架构"} or stem in {"核心服务", "数据库架构"}


def attach_adjacent_cites(
    markdown: str,
    cite_tags: list[str],
    workspace_root: str | Path | None = None,
) -> str:
    """Insert unused evidence cites on the next line after uncovered claims.

    Coverage uses the existing ±1 line window. Tags must already be concrete
    ``<cite>path:start-end</cite>`` strings from bound evidence; this helper
    does not invent paths. When the sentence names a backticked identifier,
    only attach a tag whose cited range contains that identifier.
    """
    tags = [tag.strip() for tag in cite_tags if str(tag).strip()]
    if not markdown or not tags:
        return markdown

    claims = extract_claim_units(markdown, page="")
    if not claims:
        return markdown

    existing_lines = {ref.line for ref in extract_citation_refs_with_lines(markdown)}
    uncovered = [
        claim
        for claim in claims
        if not {claim.line - 1, claim.line, claim.line + 1} & existing_lines
    ]
    if not uncovered:
        return markdown

    root = Path(workspace_root) if workspace_root is not None else None
    lines = markdown.splitlines()
    tag_index = 0
    for claim in sorted(uncovered, key=lambda item: item.line, reverse=True):
        insert_at = min(max(claim.line, 0), len(lines))
        claim_text = claim.text or (lines[claim.line - 1] if 0 < claim.line <= len(lines) else "")
        idents = sentence_identifiers(claim_text) if root is not None else set()
        if idents and root is not None:
            tag = _first_matching_tag(idents, tags, root)
            if tag is None:
                continue
        else:
            tag = tags[tag_index % len(tags)]
            tag_index += 1
        lines.insert(insert_at, tag)

    rewritten = "\n".join(lines)
    if markdown.endswith("\n") and not rewritten.endswith("\n"):
        rewritten += "\n"
    return rewritten


def realign_irrelevant_cites(
    markdown: str,
    cite_tags: list[str],
    workspace_root: str | Path,
) -> str:
    """Replace or drop cites whose range does not contain a named identifier."""
    root = Path(workspace_root)
    tags = [tag.strip() for tag in cite_tags if str(tag).strip()]
    if not markdown:
        return markdown
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        cites = list(_CITE_TAG_RE.finditer(line))
        if not cites:
            continue
        prose = _CITE_TAG_RE.sub("", line).strip() or (lines[index - 1] if index else "")
        idents = sentence_identifiers(prose)
        if not idents:
            continue
        new_line = line
        for match in reversed(cites):
            tag = match.group(0)
            window = _cite_window(tag, root)
            if window and any(ident in window for ident in idents):
                continue
            replacement = _first_matching_tag(idents, tags, root) or ""
            if not replacement:
                parsed = _parse_cite_tag(tag)
                replacement = f"`{parsed[0]}`" if parsed else ""
            new_line = new_line[: match.start()] + replacement + new_line[match.end() :]
        lines[index] = new_line
    rewritten = "\n".join(lines)
    if markdown.endswith("\n") and not rewritten.endswith("\n"):
        rewritten += "\n"
    return rewritten
