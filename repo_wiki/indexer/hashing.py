"""Hash helpers with optional xxhash acceleration."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, Mapping


def _xxhash_available() -> bool:
    try:
        import xxhash  # noqa: F401

        return True
    except ImportError:
        return False


def compute_bytes_hash(payload: bytes) -> str:
    """Return an xxh64 hash when available, otherwise sha256."""
    if _xxhash_available():
        import xxhash

        return xxhash.xxh64_hexdigest(payload)
    return hashlib.sha256(payload).hexdigest()


def compute_text_hash(text: str) -> str:
    return compute_bytes_hash(text.encode("utf-8"))


def compute_file_hash(path: str | Path) -> str:
    data = Path(path).read_bytes()
    return compute_bytes_hash(data)


def diff_hash_maps(
    previous: Mapping[str, str],
    current: Mapping[str, str],
) -> Dict[str, Dict[str, str]]:
    """Diff two path->hash maps and detect simple renames by hash."""
    prev = dict(previous)
    curr = dict(current)
    prev_keys = set(prev)
    curr_keys = set(curr)

    added = {k: curr[k] for k in sorted(curr_keys - prev_keys)}
    deleted = {k: prev[k] for k in sorted(prev_keys - curr_keys)}
    modified = {
        k: curr[k]
        for k in sorted(prev_keys & curr_keys)
        if prev[k] != curr[k]
    }
    unchanged = {
        k: curr[k]
        for k in sorted(prev_keys & curr_keys)
        if prev[k] == curr[k]
    }

    # Pair newly-added and deleted files that share a hash as renames.
    deleted_by_hash = {}
    for path, file_hash in deleted.items():
        deleted_by_hash.setdefault(file_hash, []).append(path)

    renames = {}
    for new_path, file_hash in list(added.items()):
        old_paths = deleted_by_hash.get(file_hash, [])
        if not old_paths:
            continue
        old_path = sorted(old_paths)[0]
        renames[old_path] = new_path
        del added[new_path]
        del deleted[old_path]
        deleted_by_hash[file_hash].remove(old_path)
        if not deleted_by_hash[file_hash]:
            del deleted_by_hash[file_hash]

    return {
        "added": added,
        "modified": modified,
        "deleted": deleted,
        "unchanged": unchanged,
        "renamed": renames,
    }
