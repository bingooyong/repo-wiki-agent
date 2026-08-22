"""Place evidence citations on the same line or next line as factual claims."""

from __future__ import annotations

from repo_wiki.verifier.citation_fact_coverage import (
    extract_citation_refs_with_lines,
    extract_claim_units,
)


def attach_adjacent_cites(markdown: str, cite_tags: list[str]) -> str:
    """Insert unused evidence cites on the next line after uncovered claims.

    Coverage uses the existing ±1 line window. Tags must already be concrete
    ``<cite>path:start-end</cite>`` strings from bound evidence; this helper
    does not invent paths.
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

    lines = markdown.splitlines()
    tag_index = 0
    for claim in sorted(uncovered, key=lambda item: item.line, reverse=True):
        insert_at = min(max(claim.line, 0), len(lines))
        tag = tags[tag_index % len(tags)]
        tag_index += 1
        lines.insert(insert_at, tag)

    rewritten = "\n".join(lines)
    if markdown.endswith("\n") and not rewritten.endswith("\n"):
        rewritten += "\n"
    return rewritten
