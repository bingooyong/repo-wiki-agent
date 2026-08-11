"""Incremental impact analysis for knowledge plans and Knowledge Model v3."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any


def analyze_impact(
    old_plan: dict[str, Any] | None = None,
    new_plan: dict[str, Any] | None = None,
    old_model: dict[str, Any] | None = None,
    new_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic impacted directories/pages/templates/domains/docs."""

    reasons: list[dict[str, str]] = []
    directories = _changed_directory_paths(old_plan, new_plan, reasons)
    templates = _changed_template_ids(old_plan, new_plan, reasons)
    domains = _changed_domain_ids(old_plan, new_plan, reasons)
    docs = _changed_doc_paths(old_plan, new_plan, reasons)

    scope_directories, scope_docs = _changed_scope(old_plan, new_plan, reasons)
    directories.update(scope_directories)
    docs.update(scope_docs)
    directories.update(_model_impacted_directories(old_model, new_model, new_plan, reasons))
    templates.update(_templates_for_directories(old_plan, directories))
    templates.update(_templates_for_directories(new_plan, directories))
    pages = sorted(
        _pages_for_directories(old_plan, directories)
        | _pages_for_directories(new_plan, directories)
        | templates
    )
    return {
        "directories": sorted(directories),
        "pages": pages,
        "templates": sorted(templates),
        "domains": sorted(domains),
        "docs": sorted(docs),
        "reasons": reasons,
    }


def _changed_scope(
    old_plan: dict[str, Any] | None,
    new_plan: dict[str, Any] | None,
    reasons: list[dict[str, str]],
) -> tuple[set[str], set[str]]:
    directories: set[str] = set()
    docs: set[str] = set()
    all_directories = _directory_paths(old_plan) | _directory_paths(new_plan)
    all_docs = _doc_paths(old_plan) | _doc_paths(new_plan)
    for key in ("include", "exclude"):
        old = {str(item) for item in _raw_list(old_plan, key) if isinstance(item, str)}
        new = {str(item) for item in _raw_list(new_plan, key) if isinstance(item, str)}
        for pattern in sorted(old ^ new):
            reasons.append(
                {
                    "kind": key,
                    "id": pattern,
                    "reason": f"{key} path scope added, removed, or changed",
                }
            )
            matched_directories = {
                path for path in all_directories if _scope_matches(pattern, path)
            }
            matched_docs = {path for path in all_docs if _scope_matches(pattern, path)}
            if matched_directories:
                directories.update(matched_directories)
            elif pattern.endswith("/") or not Path(pattern).suffix:
                directories.add(pattern)
            if matched_docs:
                docs.update(matched_docs)
            elif Path(pattern).suffix:
                docs.add(pattern)
    return directories, docs


def _scope_matches(pattern: str, rel: str) -> bool:
    normalized_pattern = str(pattern).replace("\\", "/")
    normalized_rel = str(rel).replace("\\", "/")
    if normalized_pattern.endswith("/"):
        return normalized_rel == normalized_pattern or normalized_rel.startswith(normalized_pattern)
    return (
        normalized_rel == normalized_pattern
        or fnmatch.fnmatch(normalized_rel, normalized_pattern)
        or Path(normalized_rel).match(normalized_pattern)
    )


def _changed_directory_paths(
    old_plan: dict[str, Any] | None,
    new_plan: dict[str, Any] | None,
    reasons: list[dict[str, str]],
) -> set[str]:
    old = _by_key(_list(old_plan, "directories"), "path")
    new = _by_key(_list(new_plan, "directories"), "path")
    changed = {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
    for key in sorted(changed):
        reasons.append(
            {"kind": "directory", "id": key, "reason": "directory added, removed, or changed"}
        )
    return changed


def _changed_template_ids(
    old_plan: dict[str, Any] | None,
    new_plan: dict[str, Any] | None,
    reasons: list[dict[str, str]],
) -> set[str]:
    old = _by_key(_list(old_plan, "page_templates"), "id")
    new = _by_key(_list(new_plan, "page_templates"), "id")
    changed = {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
    for key in sorted(changed):
        reasons.append(
            {"kind": "template", "id": key, "reason": "template added, removed, or changed"}
        )
    return changed


def _changed_domain_ids(
    old_plan: dict[str, Any] | None,
    new_plan: dict[str, Any] | None,
    reasons: list[dict[str, str]],
) -> set[str]:
    old = _by_key(_list(old_plan, "business_domains"), "id")
    new = _by_key(_list(new_plan, "business_domains"), "id")
    changed = {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
    for key in sorted(changed):
        reasons.append({"kind": "domain", "id": key, "reason": "domain added, removed, or changed"})
    return changed


def _changed_doc_paths(
    old_plan: dict[str, Any] | None,
    new_plan: dict[str, Any] | None,
    reasons: list[dict[str, str]],
) -> set[str]:
    old = _by_key(_docs(old_plan), "path")
    new = _by_key(_docs(new_plan), "path")
    changed = {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
    for key in sorted(changed):
        reasons.append(
            {"kind": "doc", "id": key, "reason": "doc allowlist entry added, removed, or changed"}
        )
    return changed


def _model_impacted_directories(
    old_model: dict[str, Any] | None,
    new_model: dict[str, Any] | None,
    new_plan: dict[str, Any] | None,
    reasons: list[dict[str, str]],
) -> set[str]:
    if old_model is None or new_model is None or old_model == new_model:
        return set()
    changed_families = _changed_record_families(old_model, new_model)
    directories: set[str] = set()
    for directory in _list(new_plan, "directories"):
        families = directory.get("record_families", []) if isinstance(directory, dict) else []
        if not isinstance(families, list):
            continue
        if changed_families.intersection(str(item) for item in families):
            path = directory.get("path")
            if isinstance(path, str):
                directories.add(path)
    for family in sorted(changed_families):
        reasons.append(
            {"kind": "model", "id": family, "reason": "knowledge model record family changed"}
        )
    return directories


def _changed_record_families(old_model: dict[str, Any], new_model: dict[str, Any]) -> set[str]:
    old_records = old_model.get("records", {}) if isinstance(old_model, dict) else {}
    new_records = new_model.get("records", {}) if isinstance(new_model, dict) else {}
    old_records = old_records if isinstance(old_records, dict) else {}
    new_records = new_records if isinstance(new_records, dict) else {}
    return {
        key
        for key in old_records.keys() | new_records.keys()
        if old_records.get(key) != new_records.get(key)
    }


def _pages_for_directories(plan: dict[str, Any] | None, directories: set[str]) -> set[str]:
    pages: set[str] = set()
    for directory in _list(plan, "directories"):
        if not isinstance(directory, dict) or directory.get("path") not in directories:
            continue
        directory_path = str(directory["path"])
        for template in directory.get("templates", []):
            template_id = template.get("id") if isinstance(template, dict) else template
            if isinstance(template_id, str):
                pages.add(f"{directory_path}{template_id}.md")
    return pages


def _templates_for_directories(plan: dict[str, Any] | None, directories: set[str]) -> set[str]:
    templates: set[str] = set()
    for directory in _list(plan, "directories"):
        if not isinstance(directory, dict) or directory.get("path") not in directories:
            continue
        for template in directory.get("templates", []):
            template_id = template.get("id") if isinstance(template, dict) else template
            if isinstance(template_id, str):
                templates.add(template_id)
    return templates


def _directory_paths(plan: dict[str, Any] | None) -> set[str]:
    return {
        str(item["path"])
        for item in _list(plan, "directories")
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }


def _doc_paths(plan: dict[str, Any] | None) -> set[str]:
    return {
        str(item["path"])
        for item in _docs(plan)
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }


def _raw_list(plan: dict[str, Any] | None, key: str) -> list[Any]:
    value = plan.get(key, []) if isinstance(plan, dict) else []
    return value if isinstance(value, list) else []


def _docs(plan: dict[str, Any] | None) -> list[dict[str, Any]]:
    docs = plan.get("docs", {}) if isinstance(plan, dict) else {}
    if not isinstance(docs, dict):
        return []
    allowlist = docs.get("allowlist", [])
    return allowlist if isinstance(allowlist, list) else []


def _list(plan: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    value = plan.get(key, []) if isinstance(plan, dict) else []
    return value if isinstance(value, list) else []


def _by_key(items: list[Any], key: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get(key)
        if isinstance(value, str):
            out[value] = item
    return out
