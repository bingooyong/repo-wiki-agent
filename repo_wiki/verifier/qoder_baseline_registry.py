"""Canonical Qoder baseline registry and read-only guards.

Phase 36 - Task 36.3:
- Treat `.qoder/repowiki/zh` as the single canonical baseline.
- Reject compare flows that try to use `.repo-agent-eval/*` as baseline.
- Provide immutable metadata/fingerprint for read-only enforcement.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BaselineRegistryEntry:
    """Registered canonical baseline metadata."""

    root: Path
    repository_root: Path
    fingerprint: str
    file_count: int
    immutable: bool = True
    source: str = "canonical_qoder_baseline"


def _find_repository_root(start: Path) -> Path | None:
    current = start if start.is_dir() else start.parent
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _default_canonical_baseline(repo_root: Path) -> Path:
    return repo_root / ".qoder" / "repowiki" / "zh"


def compute_baseline_fingerprint(root: Path) -> tuple[str, int]:
    """Create deterministic baseline fingerprint from relative paths + bytes."""
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Baseline root does not exist: {root}")

    h = hashlib.sha256()
    file_count = 0
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix().encode("utf-8")
        h.update(rel)
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
        file_count += 1
    return h.hexdigest(), file_count


def register_single_qoder_baseline(
    target_root: Path, baseline_root: Path | None = None
) -> BaselineRegistryEntry:
    """Register and validate a single canonical `.qoder/repowiki/zh` baseline."""
    repo_root = _find_repository_root(target_root)
    if repo_root is None:
        raise ValueError(f"Cannot locate repository root from: {target_root}")

    canonical = _default_canonical_baseline(repo_root).resolve()
    if not canonical.exists() or not canonical.is_dir():
        raise ValueError(f"Canonical baseline missing: {canonical}")

    if baseline_root is not None:
        provided = baseline_root.resolve()
        provided_str = str(provided).replace("\\", "/")
        if "/.repo-agent-eval/" in provided_str:
            raise ValueError(
                "Invalid baseline root: baseline must be .qoder/repowiki/zh, "
                "not a .repo-agent-eval run directory"
            )
        if provided != canonical:
            raise ValueError(
                f"Baseline must be canonical .qoder/repowiki/zh. "
                f"provided={provided} canonical={canonical}"
            )

    fingerprint, file_count = compute_baseline_fingerprint(canonical)
    return BaselineRegistryEntry(
        root=canonical,
        repository_root=repo_root.resolve(),
        fingerprint=fingerprint,
        file_count=file_count,
    )


def baseline_unchanged(entry: BaselineRegistryEntry) -> bool:
    """Check whether baseline content is unchanged since registration."""
    current, _ = compute_baseline_fingerprint(entry.root)
    return current == entry.fingerprint
