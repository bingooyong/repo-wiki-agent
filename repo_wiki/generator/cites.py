"""Pick a real source file citation for init document templates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_SOURCE_SUFFIXES = {".py", ".ts", ".js", ".go", ".rs", ".java"}


def select_primary_cite(root: Path, snapshot: dict[str, Any]) -> str:
    root = Path(root)
    for candidate in _candidate_paths(snapshot):
        cite = _cite_for_candidate(root, candidate)
        if cite:
            return cite
    return ""


def _candidate_paths(snapshot: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    repository = _repository(snapshot)
    for item in repository.get("entry_points") or []:
        text = str(item).strip()
        if text:
            paths.append(text)
    for module in _modules(snapshot):
        if isinstance(module, dict):
            text = str(module.get("path") or "").strip()
        else:
            text = str(module).strip()
        if text:
            paths.append(text)
    return paths


def _repository(snapshot: dict[str, Any]) -> dict[str, Any]:
    repo = snapshot.get("repository")
    if isinstance(repo, dict):
        return repo
    repo_map = snapshot.get("repo_map")
    if isinstance(repo_map, dict):
        nested = repo_map.get("repository")
        if isinstance(nested, dict):
            return nested
    return {}


def _modules(snapshot: dict[str, Any]) -> list[Any]:
    modules = snapshot.get("modules")
    if isinstance(modules, list):
        return modules
    module_index = snapshot.get("module_index")
    if isinstance(module_index, dict):
        nested = module_index.get("modules")
        if isinstance(nested, list):
            return nested
    return []


def _cite_for_candidate(root: Path, candidate: str) -> str:
    path = Path(candidate)
    if not path.is_absolute():
        path = root / path
    if not _is_inside_root(root, path):
        return ""
    if not path.exists():
        return ""
    if path.is_file():
        return _format_cite(root, path)
    if path.is_dir():
        nested = _first_nested_source(root, path)
        if nested is not None:
            return _format_cite(root, nested)
    return ""


def _first_nested_source(root: Path, directory: Path) -> Path | None:
    matches: list[Path] = []
    for child in directory.rglob("*"):
        if not child.is_file():
            continue
        if child.suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        if not _is_inside_root(root, child):
            continue
        matches.append(child)
    if not matches:
        return None
    matches.sort(key=lambda item: (len(item.relative_to(directory).parts), item.as_posix()))
    return matches[0]


def _format_cite(root: Path, path: Path) -> str:
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    return f"<cite>{relative}:1</cite>"


def _is_inside_root(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True
