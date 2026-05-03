"""Shared IO helpers for generation, adapter, verifier, and orchestration."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )


def read_yamlish(path: Path, default: Any) -> Any:
    """
    Read YAML-like content with robust fallback:
    1) PyYAML (if available)
    2) JSON-as-YAML (always supported)
    """
    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return default
    try:
        import yaml  # type: ignore

        parsed = yaml.safe_load(raw)
        return default if parsed is None else parsed
    except Exception:
        pass
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def write_yamlish(path: Path, payload: Any) -> None:
    """
    Write deterministic YAML-like output.
    JSON is valid YAML 1.2 and keeps deterministic ordering.
    """
    write_json(path, payload)


def stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def list_repo_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [
            d for d in dirs if d not in {".git", ".repo-wiki", ".pytest_cache", "__pycache__"}
        ]
        for name in files:
            path = Path(base) / name
            if path.suffix in {".pyc"}:
                continue
            out.append(path)
    return sorted(out)


def relpath(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)
