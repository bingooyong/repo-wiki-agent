"""Read-only registry for external Qoder reference baselines (e.g. ai-testing).

Unlike ``qoder_baseline_registry``, which guards the canonical in-repo
``.qoder/repowiki/zh`` baseline, this module describes baselines that live in
*other* repositories and are consumed only for gap analysis. Nothing here writes
to a baseline, and no baseline content is fed to the planner or composer.
"""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from typing import Any

import yaml

from repo_wiki.verifier.qoder_baseline_registry import compute_baseline_fingerprint

REGISTRY_SCHEMA_VERSION = 1
HASH_ALGORITHM = "sha256(relpath_posix + NUL + file_bytes + NUL), files sorted by relpath"

MODULE_CARD_TYPES = (
    "overview",
    "architecture_design",
    "tech_stack",
    "coding_conventions",
    "unique_setup_and_commands",
)
REPO_CARD_TYPES = (
    "build_system",
    "configuration_system",
    "dependency_management",
    "error_handling",
    "logging_system",
)
CARD_FILENAMES = {
    "overview": "概述.md",
    "architecture_design": "架构设计.md",
    "tech_stack": "技术栈.md",
    "coding_conventions": "编码规范.md",
    "unique_setup_and_commands": "特殊配置与命令.md",
    **{name: f"{name}.md" for name in REPO_CARD_TYPES},
}

FILE_REF_RE = re.compile(r"[A-Za-z0-9_./\-]+\.(?:py|md|yaml|yml|toml|json|java|xml|sh|ts|js)")
LINE_ANCHOR_RE = re.compile(r"#L\d+")


def load_registry(path: Path) -> dict[str, Any]:
    registry = json.loads(path.read_text(encoding="utf-8"))
    if registry.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise ValueError(f"Unsupported registry schema_version: {registry.get('schema_version')}")
    entries = registry.get("baselines")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Registry must contain a non-empty 'baselines' list")
    return registry


def resolve_entry_root(entry: dict[str, Any], overrides: dict[str, Path] | None = None) -> Path:
    overrides = overrides or {}
    if entry["id"] in overrides:
        return overrides[entry["id"]].resolve()
    return (Path(entry["source_repo_root"]) / entry["source_path"]).resolve()


def _module_documents(root: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    documents: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted(root.rglob("_module.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        module_path = doc.get("module_path")
        if isinstance(module_path, str):
            documents[module_path] = (path, doc)
    return documents


def _relation_reason_coverage(modules: dict[str, Any]) -> tuple[dict[str, int], float | None]:
    counts = {"depends_on": 0, "related_to": 0, "version_of": 0}
    with_reason = 0
    reason_total = 0
    for module in modules.values():
        counts["depends_on"] += len(module.get("depends_on") or [])
        for key in ("related_to", "version_of"):
            relations = module.get(key) or []
            counts[key] += len(relations)
            reason_total += len(relations)
            with_reason += sum(1 for r in relations if str(r.get("reason") or "").strip())
    coverage = round(with_reason / reason_total, 4) if reason_total else None
    return counts, coverage


def collect_knowledge_stats(root: Path) -> dict[str, Any]:
    index = yaml.safe_load((root / "_index.yaml").read_text(encoding="utf-8")) or {}
    modules = index.get("modules") or {}
    documents = _module_documents(root)

    card_type_counts: dict[str, int] = {}
    module_card_counts: dict[str, int] = {}
    repo_card_counts: dict[str, int] = {}
    missing_modules: list[str] = []
    missing_card_files: list[str] = []

    for module_id in modules:
        found = documents.get(module_id)
        if found is None:
            missing_modules.append(module_id)
            continue
        module_dir, doc = found[0].parent, found[1]
        for card_type in (doc.get("kk_cards") or {}):
            card_type_counts[card_type] = card_type_counts.get(card_type, 0) + 1
            bucket = repo_card_counts if card_type in REPO_CARD_TYPES else module_card_counts
            bucket[card_type] = bucket.get(card_type, 0) + 1
            filename = CARD_FILENAMES.get(card_type)
            if filename and not (module_dir / filename).exists():
                missing_card_files.append(f"{module_id}/{filename}")

    markdown_files = sorted(root.rglob("*.md"))
    total_chars = 0
    file_ref_count = 0
    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        total_chars += len(text)
        file_ref_count += len(FILE_REF_RE.findall(text))

    relation_counts, reason_coverage = _relation_reason_coverage(modules)
    return {
        "schema_version": index.get("schema_version"),
        "locale": index.get("locale"),
        "commit": index.get("commit"),
        "branch": index.get("branch"),
        "exported_at": index.get("exported_at"),
        "module_count": len(modules),
        "module_yaml_count": len(documents),
        "markdown_file_count": len(markdown_files),
        "card_type_counts": dict(sorted(card_type_counts.items())),
        "module_card_counts": dict(sorted(module_card_counts.items())),
        "repo_card_counts": dict(sorted(repo_card_counts.items())),
        "relation_counts": relation_counts,
        "relation_reason_coverage": reason_coverage,
        "evidence": {
            "file_ref_count": file_ref_count,
            "total_chars": total_chars,
            "refs_per_1k_chars": round(file_ref_count / total_chars * 1000, 4)
            if total_chars
            else None,
        },
        "missing_module_yaml": sorted(missing_modules),
        "missing_card_files": sorted(missing_card_files),
    }


def collect_longform_stats(root: Path) -> dict[str, Any]:
    content = root / "content"
    pages = sorted(content.rglob("*.md")) if content.is_dir() else []
    lengths = [len(p.read_text(encoding="utf-8")) for p in pages]
    mermaid = cite = anchors = 0
    for path in pages:
        text = path.read_text(encoding="utf-8")
        mermaid += "```mermaid" in text
        cite += "<cite>" in text
        anchors += bool(LINE_ANCHOR_RE.search(text))

    meta_path = root / "meta" / "repowiki-metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    catalogs = meta.get("wiki_catalogs") or []
    page_count = len(pages)
    return {
        "page_count": page_count,
        "catalog_count": len(catalogs),
        "root_catalog_count": sum(1 for c in catalogs if not c.get("parent_id")),
        "wiki_item_count": len(meta.get("wiki_items") or []),
        "knowledge_relation_count": len(meta.get("knowledge_relations") or []),
        "progress_status": (meta.get("wiki_repo") or {}).get("progress_status"),
        "present_status": (meta.get("wiki_repo") or {}).get("wiki_present_status"),
        "commit": (meta.get("wiki_repo") or {}).get("last_commit_id"),
        "top_level_entries": sorted(p.name for p in content.iterdir()) if content.is_dir() else [],
        "mermaid_coverage": round(mermaid / page_count, 4) if page_count else None,
        "cite_block_coverage": round(cite / page_count, 4) if page_count else None,
        "line_anchor_coverage": round(anchors / page_count, 4) if page_count else None,
        "page_chars": {
            "min": min(lengths) if lengths else None,
            "median": int(statistics.median(lengths)) if lengths else None,
            "max": max(lengths) if lengths else None,
            "total": sum(lengths),
        },
    }


def collect_stats(kind: str, root: Path) -> dict[str, Any]:
    if kind == "knowledge_cards":
        return collect_knowledge_stats(root)
    if kind == "long_form_wiki":
        return collect_longform_stats(root)
    raise ValueError(f"Unknown baseline kind: {kind}")


def refresh_entry(entry: dict[str, Any], root: Path) -> dict[str, Any]:
    fingerprint, file_count = compute_baseline_fingerprint(root)
    refreshed = dict(entry)
    refreshed["content_hash"] = fingerprint
    refreshed["file_count"] = file_count
    refreshed["stats"] = collect_stats(entry["kind"], root)
    return refreshed


def verify_entry(entry: dict[str, Any], root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": entry["id"],
        "kind": entry["kind"],
        "root": str(root),
        "status": "PASS",
        "mismatches": [],
    }
    if not root.is_dir():
        result["status"] = "FAIL"
        result["mismatches"].append(f"baseline root missing: {root}")
        return result

    first, file_count = compute_baseline_fingerprint(root)
    second, _ = compute_baseline_fingerprint(root)
    result["content_hash"] = first
    result["file_count"] = file_count
    result["hash_reproducible"] = first == second
    if not result["hash_reproducible"]:
        result["mismatches"].append("fingerprint not reproducible across two reads")
    if first != entry.get("content_hash"):
        result["mismatches"].append(
            f"content_hash mismatch: registry={entry.get('content_hash')} actual={first}"
        )
    if file_count != entry.get("file_count"):
        result["mismatches"].append(
            f"file_count mismatch: registry={entry.get('file_count')} actual={file_count}"
        )

    stats = collect_stats(entry["kind"], root)
    result["stats"] = stats
    if stats != entry.get("stats"):
        result["mismatches"].append("stats mismatch against registry")
    if result["mismatches"]:
        result["status"] = "FAIL"
    return result


def verify_registry(
    registry_path: Path, overrides: dict[str, Path] | None = None
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    entries = [
        verify_entry(entry, resolve_entry_root(entry, overrides)) for entry in registry["baselines"]
    ]
    failed = [e["id"] for e in entries if e["status"] != "PASS"]
    return {
        "registry": str(registry_path),
        "schema_version": registry["schema_version"],
        "hash_algorithm": HASH_ALGORITHM,
        "status": "FAIL" if failed else "PASS",
        "failed_entries": failed,
        "entries": entries,
    }