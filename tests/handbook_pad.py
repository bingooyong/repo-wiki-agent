"""Shared padding so mock handbook pages clear the 800-character body floor."""

from __future__ import annotations

HANDBOOK_SUCCESS_PAD = (
    "The page continues with enough reader-facing detail about module boundaries, "
    "call chains, persistence, and how operators verify the service after a change. "
    "页面继续用足够长的中文段落说明模块边界、调用关系以及控制面与采集端如何协作。"
)


def pad_handbook_markdown(markdown: str, minimum: int = 860) -> str:
    """Append prose until the raw text is safely above the handbook body floor."""
    body = (markdown or "").rstrip()
    while len(body) < minimum:
        body += HANDBOOK_SUCCESS_PAD
    return body + "\n"
