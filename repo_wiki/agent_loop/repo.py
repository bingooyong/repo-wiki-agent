"""Sandboxed, cached, read-only view of the repository the agent loop documents."""

from __future__ import annotations

import fnmatch
import hashlib
import os
from collections.abc import Sequence
from pathlib import Path

SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".repo-agent-eval",
        ".repo-wiki",
        "node_modules",
        "vendor",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        ".idea",
        ".vscode",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "coverage",
        ".tox",
    }
)
MAX_FILE_BYTES = 800_000


def norm_rel(rel: object) -> str:
    """Repo-relative path as the model wrote it -> canonical form (no ./ prefix, posix)."""
    s = str(rel or "").strip().strip("`'\"").replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    return s.lstrip("/")


class RepoView:
    """Read-only access to ``root``.

    Every path is resolved inside the root (no escapes through ``..`` or symlinks), vendored /
    build / VCS directories are invisible, and files matching the security deny globs (secrets,
    databases, binaries) can never be listed, read or grepped.
    """

    def __init__(
        self,
        root: Path,
        deny_globs: Sequence[str] = (),
        deny_dirs: Sequence[str] = (),
        max_file_bytes: int = MAX_FILE_BYTES,
        allow_globs: Sequence[str] = (),
    ) -> None:
        self.root = Path(root).resolve()
        self.deny_globs = tuple(deny_globs)
        self.allow_globs = tuple(allow_globs)
        self.skip_dirs = frozenset(SKIP_DIRS | set(deny_dirs))
        self.max_file_bytes = max_file_bytes
        self._files: list[str] | None = None
        self._lines: dict[str, list[str] | None] = {}

    # ------------------------------------------------------------------ paths
    def is_denied(self, rel: str) -> bool:
        """Security deny globs win unless the file is explicitly allow-listed (opt-in, e.g. a
        committed ``.env.example`` template); nothing is allow-listed by default."""
        name = rel.rsplit("/", 1)[-1]

        def hit(globs: tuple[str, ...]) -> bool:
            return any(fnmatch.fnmatch(name, g) or fnmatch.fnmatch(rel, g) for g in globs)

        return hit(self.deny_globs) and not hit(self.allow_globs)

    def safe(self, rel: str | None) -> Path | None:
        """Absolute path for a repo-relative path, or None when it escapes / is hidden."""
        raw = norm_rel(rel) or "."
        try:
            p = (self.root / raw).resolve()
        except (OSError, RuntimeError):
            return None
        if p != self.root and self.root not in p.parents:
            return None
        rel_parts = p.relative_to(self.root).parts
        if any(part in self.skip_dirs for part in rel_parts):
            return None
        if rel_parts and p.is_file() and self.is_denied("/".join(rel_parts)):
            return None
        return p

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    # ------------------------------------------------------------------ listing / reading
    def files(self) -> list[str]:
        if self._files is None:
            out: list[str] = []
            for dirpath, dirnames, filenames in os.walk(self.root):
                dirnames[:] = sorted(
                    d
                    for d in dirnames
                    if d not in self.skip_dirs and (not d.startswith(".") or d == ".github")
                )
                for name in sorted(filenames):
                    rel = (Path(dirpath) / name).relative_to(self.root).as_posix()
                    if not self.is_denied(rel):
                        out.append(rel)
            self._files = out
        return list(self._files)

    def lines(self, rel: str | None) -> list[str] | None:
        key = norm_rel(rel)
        if key in self._lines:
            return self._lines[key]
        p = self.safe(key) if key else None
        result: list[str] | None = None
        if p is not None and p.is_file():
            try:
                if p.stat().st_size <= self.max_file_bytes:
                    result = p.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                result = None
        self._lines[key] = result
        return result

    def window(self, rel: str | None, line: object, radius: int) -> str | None:
        ls = self.lines(rel)
        if not ls or not isinstance(line, int) or isinstance(line, bool):
            return None
        if line < 1 or line > len(ls):
            return None
        return "\n".join(ls[max(0, line - 1 - radius) : line + radius])

    def exists(self, rel: str) -> bool:
        p = self.safe(rel.rstrip("/") or ".")
        return p is not None and p.exists()

    def fingerprint(self) -> str:
        """Content hash of every visible file: tool results are a function of this snapshot."""
        h = hashlib.sha256()
        for rel in self.files():
            p = self.root / rel
            h.update(rel.encode("utf-8", "ignore") + b"\0")
            try:
                if p.stat().st_size <= self.max_file_bytes:
                    h.update(hashlib.sha1(p.read_bytes()).digest())
            except OSError:
                h.update(b"?")
        return h.hexdigest()[:16]
