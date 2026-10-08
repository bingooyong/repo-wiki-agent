"""Deterministic evidence primitives: parsing ``FILE:LINE: quote`` strings and checking them."""

from __future__ import annotations

import re
from typing import Any

from repo_wiki.agent_loop.repo import RepoView, norm_rel

Evidence = dict[str, Any]

EV_RX = re.compile(r"^\s*`?([^\s:`]+):(\d+)`?\s*:?\s*(.*)$", re.S)
_EV_SPACING_RX = re.compile(r"^\s*([^\s:]+?)\s*:\s*(\d+)\s*:\s?")
COMMON_TOKENS = frozenset(
    {
        "HTTP",
        "HTTPS",
        "API",
        "JSON",
        "SQL",
        "ORM",
        "ODM",
        "URL",
        "REST",
        "RESTFUL",
        "CLI",
        "JWT",
        "YAML",
        "YML",
        "TCP",
        "UDP",
        "CRUD",
        "UUID",
        "ID",
        "PK",
        "FK",
        "README",
        "DB",
        "OS",
        "UI",
        "SDK",
        "TLS",
        "DNS",
        "MIT",
        "ICMP",
        "GRPC",
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "PATCH",
    }
)
DOC_RX = re.compile(r"(?i)(^|/)readme[^/]*$|\.(md|rst|txt|adoc)$|(^|/)docs?/")
PARAM_RX = re.compile(r"<(?:[\w]+:)?(\w+)>|\{(\w+)(?::[^}]*)?\}|:(\w+)")


def ws(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def norm(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace('\\"', '"').strip()).lower()


def parse_ev(raw: object) -> Evidence | None:
    """``'FILE:LINE: quote'`` (or a dict with file/line/quote) -> evidence dict."""
    if isinstance(raw, dict):
        line = raw.get("line")
        try:
            line_no = int(line) if line is not None else None
        except (TypeError, ValueError):
            line_no = None
        return {
            "file": norm_rel(raw.get("file", "")),
            "line": line_no,
            "quote": str(raw.get("quote", "")),
        }
    text = _EV_SPACING_RX.sub(r"\1:\2: ", str(raw or ""))
    m = EV_RX.match(text)
    if not m:
        return None
    return {
        "file": norm_rel(m.group(1)),
        "line": int(m.group(2)),
        "quote": m.group(3).strip().strip("`"),
    }


def quote_ok(repo: RepoView, ev: Evidence, radius: int = 2) -> int | None:
    """Return the verified line number for ``ev`` or None.

    The quote must occur (whitespace-normalised) within ``radius`` lines of the cited line. When
    the literal occurs exactly once elsewhere in the same file the evidence is accepted at the
    corrected line (the returned value); quoting the file path itself proves existence.
    """
    rel = norm_rel(ev.get("file", ""))
    lines = repo.lines(rel)
    line = ev.get("line")
    q = ws(str(ev.get("quote", "")).replace('\\"', '"').replace("\\'", "'")).strip("`'\" ")
    if lines is None or len(q) < 3:
        return None
    if q.rstrip("/") == rel.rstrip("/"):
        return line if isinstance(line, int) and 1 <= line <= max(len(lines), 1) else 1
    if isinstance(line, int) and 1 <= line <= len(lines):
        win = ws(" ".join(lines[max(0, line - 1 - radius) : line + radius]))
        if q in win:
            return line
    hits = [i + 1 for i, ln in enumerate(lines) if q in ws(ln)]
    if len(hits) == 1:
        return hits[0]
    return None


def claim_tokens(text: str) -> set[str]:
    """Identifiers / numbers / paths / commands in a claim that must be grounded in evidence."""
    text = re.sub(
        r"(?:[\w\-]+/)*[\w.\-]*\.[A-Za-z]\w*:\d+(-\d+)?|(?<=[、,，])\s*:\d+", " ", text or ""
    )
    toks = set(re.findall(r"`([^`]{2,80})`", text))
    rest = re.sub(r"`[^`]*`", " ", text)
    toks |= {
        t
        for t in re.findall(r"[A-Za-z0-9_][A-Za-z0-9_./:\-]*[A-Za-z0-9_/]", rest)
        if (re.search(r"[_./:]", t) or re.search(r"\d", t) or (t.isupper() and len(t) >= 3))
        and t.upper() not in COMMON_TOKENS
    }
    return {t.strip().rstrip(".,;:)") for t in toks if len(t.strip()) >= 2}


# .txt manifests / build files are code-side sources, not documentation
NOT_DOC_RX = re.compile(r"(?i)(^|/)(requirements[^/]*|constraints[^/]*|CMakeLists|robots)\.txt$")


def is_doc_file(rel: str) -> bool:
    return bool(DOC_RX.search(rel)) and not NOT_DOC_RX.search(rel)


def is_doc_evidence(evidence: list[str]) -> bool:
    files = {e.rpartition(":")[0] for e in evidence}
    return bool(files) and all(is_doc_file(f) for f in files)


def split_ref(ref: str) -> tuple[str, int | None]:
    path, _, line = str(ref).rpartition(":")
    return (path, int(line)) if line.isdigit() else (str(ref), None)


# ------------------------------------------------------------------ URL path helpers (routes)
def norm_path(path: str) -> str:
    p = (path or "").strip().strip("`'\"")
    p = re.sub(r"^https?://[^/]+", "", p)
    p = PARAM_RX.sub(lambda m: ":" + (m.group(1) or m.group(2) or m.group(3)), p)
    return re.sub(r"/+", "/", "/" + p.strip("/"))


def shape(path: str) -> str:
    return re.sub(r":\w+", ":p", norm_path(path))


def join_parts(parts: list[str]) -> str:
    return norm_path("/".join(x.strip("/") for x in parts if x and x.strip("/")))
