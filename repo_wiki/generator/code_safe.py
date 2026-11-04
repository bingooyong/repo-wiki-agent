"""Protect inline code and fenced blocks from prose rewrites.

Post-processors may only edit bytes outside ``...`` and ```...```.
They must not insert <cite> inside those units or merge neighbouring spans.
"""

from __future__ import annotations

import re
from collections.abc import Callable

_FENCE_RE = re.compile(r"```.*?```", re.S)
_INLINE_RE = re.compile(r"`[^`\n]*`")
_EMPTY_INLINE_RE = re.compile(r"(?<!`)``(?!`)")


def protect_code_units(text: str) -> tuple[str, dict[str, str]]:
    """Replace fences then inline spans with opaque placeholders."""
    held: dict[str, str] = {}

    def _hold(match: re.Match[str]) -> str:
        key = f"\x00CODE{len(held)}\x00"
        held[key] = match.group(0)
        return key

    protected = _FENCE_RE.sub(_hold, text or "")
    protected = _INLINE_RE.sub(_hold, protected)
    return protected, held


def restore_code_units(text: str, held: dict[str, str]) -> str:
    restored = text or ""
    for key, value in held.items():
        restored = restored.replace(key, value)
    return restored


def map_outside_code(text: str, rewriter: Callable[[str], str]) -> str:
    """Apply ``rewriter`` only to prose; fences and inline spans stay byte-identical."""
    protected, held = protect_code_units(text)
    rewritten = rewriter(protected)
    if rewritten is None:
        rewritten = protected
    return restore_code_units(rewritten, held)


def empty_inline_spans(markdown: str) -> list[str]:
    """Return a marker for each empty inline span (``)."""
    stripped = _FENCE_RE.sub("", markdown or "")
    return ["``" for _ in _EMPTY_INLINE_RE.finditer(stripped)]


def fence_language(header: str) -> str:
    token = (header or "").strip().split()[0].lower() if header else ""
    return token


def iter_integrity_code_units(markdown: str) -> list[tuple[str, str]]:
    """Yield (kind, body) for integrity: all fences except mermaid, all inline spans.

    Matches acc-25s/code_integrity.py: bash fences, A.B forms, and spans with
    spaces are included. Empty bodies are yielded as kind=empty.
    """
    units: list[tuple[str, str]] = []
    for match in re.finditer(r"```([^\n]*)\n(.*?)```", markdown or "", flags=re.S):
        lang = fence_language(match.group(1))
        if lang in {"mermaid", "plantuml", "graphviz"}:
            continue
        body = match.group(2)
        units.append(("fence", body))
    stripped = re.sub(r"```.*?```", "", markdown or "", flags=re.S)
    stripped = re.sub(r"<cite>.*?</cite>", "", stripped, flags=re.I)
    for match in re.finditer(r"`([^`\n]*)`", stripped):
        body = match.group(1)
        if body == "":
            units.append(("empty", ""))
        else:
            units.append(("inline", body))
    return units


def iter_delimited_code_units(markdown: str) -> list[str]:
    """Return exact `` ```...``` `` and `` `...` `` strings, mermaid included."""
    units: list[str] = []
    for match in _FENCE_RE.finditer(markdown or ""):
        units.append(match.group(0))
    stripped = _FENCE_RE.sub("", markdown or "")
    for match in _INLINE_RE.finditer(stripped):
        units.append(match.group(0))
    return units


def is_mermaid_fence(unit: str) -> bool:
    return bool(re.match(r"```(?:mermaid|plantuml|graphviz)\b", unit or "", flags=re.I))


def sacred_code_offenders(final: str, raw: str) -> list[str]:
    """Final code units that are not byte-identical to a raw-reply unit.

    Mermaid/plantuml fences are generator-owned diagrams and are ignored here;
    the integrity gate still requires their bodies to exist in source when they
    are not in the raw reply.
    """
    raw_units = set(iter_delimited_code_units(raw))
    offenders: list[str] = []
    for unit in iter_delimited_code_units(final):
        if unit in raw_units or is_mermaid_fence(unit):
            continue
        offenders.append(unit[:160])
    return offenders
