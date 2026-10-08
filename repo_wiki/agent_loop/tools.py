"""Read-only repository tools offered to agents (sandboxed to the repo root, capped outputs)."""

from __future__ import annotations

import fnmatch
import re
from typing import Any

from repo_wiki.agent_loop.inventory import file_outline
from repo_wiki.agent_loop.repo import RepoView

READ_CAP = 120
READ_MAX = 250
GREP_MAX_HITS = 80
LIST_MAX = 300


def fn(name: str, desc: str, props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


LIST_DIR = fn(
    "list_dir", "List a directory (repo-relative).", {"path": {"type": "string"}}, ["path"]
)
READ_FILE = fn(
    "read_file",
    f"Read a file with line numbers. Without a range (or with a range over {READ_CAP} lines) the "
    f"output is capped at {READ_CAP} lines; request narrow start/end ranges.",
    {"path": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}},
    ["path"],
)
GREP = fn(
    "grep",
    f"Regex search over repo files (at most {GREP_MAX_HITS} hits); glob filters paths "
    "(e.g. '*.py', 'src/*').",
    {"pattern": {"type": "string"}, "glob": {"type": "string"}},
    ["pattern"],
)
OUTLINE = fn(
    "outline",
    "Compact line-numbered outline of one file: declarations, tags, route-like literals and "
    "router calls. Cheaper than read_file for large files.",
    {"path": {"type": "string"}},
    ["path"],
)
READ_TOOLS = [LIST_DIR, READ_FILE, GREP, OUTLINE]
READ_GREP = [READ_FILE, GREP, OUTLINE]
READ_TOOL_NAMES = frozenset({"list_dir", "read_file", "grep", "outline"})


def _int(value: object, default: int | None) -> int | None:
    try:
        return int(value) if value not in (None, "") else default  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return default


class ToolBox:
    def __init__(self, repo: RepoView) -> None:
        self.repo = repo

    def run(self, name: str, args: dict[str, Any]) -> str:
        if name == "list_dir":
            return self.list_dir(str(args.get("path") or "."))
        if name == "read_file":
            return self.read_file(str(args.get("path") or ""), args.get("start"), args.get("end"))
        if name == "grep":
            return self.grep(str(args.get("pattern") or ""), str(args.get("glob") or "*"))
        if name == "outline":
            return self.outline(str(args.get("path") or ""))
        return f"ERROR: unknown tool {name}"

    def list_dir(self, path: str) -> str:
        p = self.repo.safe(path)
        if p is None or not p.is_dir():
            return f"ERROR: not a directory: {path}"
        visible = set(self.repo.files())
        out = []
        for child in sorted(p.iterdir()):
            rel = self.repo.rel(child)
            if child.is_dir():
                if child.name in self.repo.skip_dirs or not any(
                    f.startswith(rel + "/") for f in visible
                ):
                    continue
                out.append(rel + "/")
            elif rel in visible:
                out.append(f"{rel}  ({child.stat().st_size} B)")
        return "\n".join(out[:LIST_MAX]) or "(empty)"

    def read_file(self, path: str, start: object = None, end: object = None) -> str:
        lines = self.repo.lines(path)
        if lines is None:
            return f"ERROR: cannot read {path}"
        n = len(lines)
        st = max(1, _int(start, 1) or 1)
        en = _int(end, None)
        capped = (en is None or en - st + 1 > READ_CAP) and n > READ_CAP
        if en is None or capped:
            en = st + READ_CAP - 1
        en = min(n, en, st + READ_MAX - 1)
        body = "\n".join(f"{i}: {lines[i - 1]}" for i in range(st, en + 1))
        note = ""
        if en < n:
            note = f"\n... ({n} lines total)"
            if capped:
                note += f"\n[read capped at {READ_CAP} lines; request a narrower range (start/end)]"
        return f"{path} lines {st}-{en}\n{body}{note}"

    def grep(self, pattern: str, glob: str = "*") -> str:
        try:
            rx = re.compile(pattern)
        except re.error as e:
            return f"ERROR: bad regex: {e}"
        hits: list[str] = []
        for rel in self.repo.files():
            if not (fnmatch.fnmatch(rel, glob) or fnmatch.fnmatch(rel.rsplit("/", 1)[-1], glob)):
                continue
            for i, ln in enumerate(self.repo.lines(rel) or [], 1):
                if rx.search(ln):
                    hits.append(f"{rel}:{i}: {ln.strip()[:200]}")
                    if len(hits) >= GREP_MAX_HITS:
                        return "\n".join(hits) + f"\n... (truncated at {GREP_MAX_HITS} hits)"
        return "\n".join(hits) or "(no matches)"

    def outline(self, path: str) -> str:
        if self.repo.lines(path) is None:
            return f"ERROR: cannot read {path}"
        return file_outline(self.repo, path)
