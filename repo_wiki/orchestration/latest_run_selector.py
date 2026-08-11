"""Select qoder-like run candidates without mtime heuristics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def discover_runs(eval_root: Path) -> list[tuple[str, Path, dict[str, Any]]]:
    runs: list[tuple[str, Path, dict[str, Any]]] = []
    if not eval_root.exists():
        return runs
    runs_bucket = eval_root / "runs"
    if runs_bucket.is_dir():
        for entry in sorted(runs_bucket.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            manifest_path = entry / "manifest.json"
            if not manifest_path.exists():
                continue
            payload = _read_manifest(manifest_path)
            if payload is None:
                continue
            run_id = str(payload.get("run_id") or entry.name)
            runs.append((run_id, entry, payload))

    for entry in sorted(eval_root.iterdir()):
        if not entry.is_dir() or entry.name.startswith(".") or entry.name in {"repowiki", "runs"}:
            continue
        manifest_path = entry / "manifest.json"
        if not manifest_path.exists():
            continue
        payload = _read_manifest(manifest_path)
        if payload is None:
            continue
        run_id = str(payload.get("run_id") or entry.name)
        runs.append((run_id, entry, payload))
    return runs


def select_run(eval_root: Path, run_id: str | None = None) -> Path:
    """Select run by explicit id or lexicographically greatest run id."""
    runs = discover_runs(eval_root)
    if not runs:
        raise ValueError(f"No runs with manifest.json under: {eval_root}")

    if run_id:
        for rid, run_path, _ in runs:
            if rid == run_id or run_path.name == run_id:
                return run_path
        raise ValueError(f"Run not found: {run_id}")

    runs.sort(key=lambda item: item[0])
    return runs[-1][1]
