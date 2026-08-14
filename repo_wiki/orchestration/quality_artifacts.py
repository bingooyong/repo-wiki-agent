"""Generation quality sidecars for isolated qoder-like runs."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any

from repo_wiki.evidence.citation_renderer import normalize_citation_ref
from repo_wiki.orchestration.release_meta_schema import (
    SCHEMA_VERSION_DOCS_INVENTORY,
    SCHEMA_VERSION_EVIDENCE_INDEX,
    SCHEMA_VERSION_PAGE_REGISTRY,
    SCHEMA_VERSION_QUALITY_REPORT,
    SCHEMA_VERSION_SOURCE_INVENTORY,
)

_CITE_PATTERN = re.compile(r"<cite>[^<]+</cite>")
_CITE_VALUE_PATTERN = re.compile(r"<cite>\s*([^<]+?)\s*</cite>")
_CITE_TARGET_PATTERN = re.compile(
    r"(?P<path>.+?):(?P<start>[1-9]\d*)(?:-(?P<end>[1-9]\d*))?(?:\s+.*)?"
)
_URI_SCHEME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_READY_STATES = {"READY", "PASS"}


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_write(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _enum_value(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw) if raw is not None else ""


def _page_type(category: str) -> str:
    return (
        category.lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("项目概述", "project_overview")
        .replace("架构设计", "architecture")
        .replace("核心服务", "core_services")
        .replace("python服务", "python_services")
        .replace("前端应用", "frontend")
        .replace("数据模型", "data_models")
        .replace("api参考", "api_reference")
        .replace("部署运维", "deployment")
        .replace("开发指南", "development")
        .replace("安全合规", "security")
        .replace("故障排除", "troubleshooting")
    )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _quality_state_for(meta: dict[str, Any], llm_summary: dict[str, Any]) -> tuple[str, list[str]]:
    reasons = [str(v) for v in meta.get("reasons", []) if str(v)]
    mode = str(meta.get("generation_mode") or "").lower()
    if mode == "fallback":
        return "DEGRADED", reasons or ["fallback_generation"]
    if mode == "rule":
        if llm_summary.get("mock_reason") == "missing_api_key":
            return "DEGRADED", reasons + ["mock_llm_missing_api_key"]
        return "PASS", reasons or ["rule_or_mock_generated"]
    if mode == "llm":
        if meta.get("quality_warning"):
            return "PASS", reasons + ["composer_quality_warning"]
        return "READY", reasons
    return "UNIDENTIFIED", reasons + ["unknown_generation_mode"]


def build_generation_quality_documents(
    *,
    run_id: str,
    profile_name: str,
    content_dir: Path,
    plan_pages: list[Any],
    written_files: list[str],
    content_stats: dict[str, Any],
    composition_page_metadata: list[dict[str, Any]],
    failed_pages: list[dict[str, Any]],
    quality_warnings: list[dict[str, Any]],
    llm_summary: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build canonical page-registry and quality-report documents.

    The documents intentionally derive per-page state from composer/page-plan evidence:
    output path mappings from the content writer, fallback failures from composer results,
    citations from the rendered file, and evidence counts from evidence bindings.
    """
    generated_at = _now_iso()
    by_source = {
        str(item.get("source_path")): item
        for item in content_stats.get("path_mappings", [])
        if isinstance(item, dict)
    }
    meta_by_source = {str(item.get("source_path")): item for item in composition_page_metadata}
    warnings_by_page = {
        str(item.get("page_id")) for item in quality_warnings if isinstance(item, dict)
    }
    failures_by_page = {
        str(item.get("page_id")): item for item in failed_pages if isinstance(item, dict)
    }

    pages: list[dict[str, Any]] = []
    quality_pages: list[dict[str, Any]] = []
    for page in plan_pages:
        source_path = str(getattr(page, "output_path", ""))
        mapping = by_source.get(source_path)
        if mapping is None:
            continue
        relative_path = str(mapping.get("relative_path") or "")
        rendered = _read_text(content_dir / relative_path)
        page_id = str(getattr(page, "page_id", Path(relative_path).stem))
        category = _enum_value(getattr(page, "category", ""))
        comp_meta = dict(meta_by_source.get(source_path, {}))
        if page_id in warnings_by_page:
            comp_meta["quality_warning"] = True
            comp_meta.setdefault("reasons", []).append("composer_quality_warning")
        if page_id in failures_by_page:
            comp_meta["generation_mode"] = "fallback"
            comp_meta.setdefault("reasons", []).append(
                str(failures_by_page[page_id].get("reason") or "fallback")
            )
        generation_mode = str(comp_meta.get("generation_mode") or "UNIDENTIFIED").lower()
        quality_state, reasons = _quality_state_for(comp_meta, llm_summary)
        citation_count = len(_CITE_PATTERN.findall(rendered))
        evidence_count = int(comp_meta.get("evidence_count") or 0)
        entry = {
            "page_id": page_id,
            "stable_page_id": page_id,
            "relative_path": relative_path,
            "path": relative_path,
            "category": category,
            "page_type": _page_type(category),
            "title": str(getattr(page, "title", Path(relative_path).stem)),
            "generation_mode": generation_mode,
            "quality_state": quality_state,
            "evidence_count": evidence_count,
            "citation_count": citation_count,
            "reasons": reasons,
        }
        pages.append(entry)
        quality_pages.append(
            {
                "page_id": page_id,
                "relative_path": relative_path,
                "path": relative_path,
                "generation_mode": generation_mode,
                "quality_state": quality_state,
                "evidence_count": evidence_count,
                "citation_count": citation_count,
                "reasons": reasons,
            }
        )

    counts = Counter(str(p["quality_state"]) for p in quality_pages)
    fallback_or_degraded = counts.get("FALLBACK", 0) + counts.get("DEGRADED", 0)
    unidentified = counts.get("UNIDENTIFIED", 0)
    all_ready = bool(quality_pages) and all(
        p["quality_state"] in _READY_STATES for p in quality_pages
    )
    grade = (
        "PASS"
        if all_ready
        else "FALLBACK"
        if fallback_or_degraded
        else "UNIDENTIFIED"
        if unidentified
        else "PASS"
    )

    page_registry = {
        "schema_version": SCHEMA_VERSION_PAGE_REGISTRY,
        "generated_at": generated_at,
        "run_id": run_id,
        "pages": pages,
        "summary": {
            "page_count": len(pages),
            "written_file_count": len(written_files),
            "quality_states": dict(counts),
        },
    }
    quality_report = {
        "schema_version": SCHEMA_VERSION_QUALITY_REPORT,
        "generated_at": generated_at,
        "run_id": run_id,
        "summary": {
            "profile": profile_name,
            "grade": grade,
            "strict_mode": True,
            "total_pages": len(quality_pages),
            "ready_count": counts.get("READY", 0),
            "pass_count": counts.get("PASS", 0),
            "fallback_count": counts.get("FALLBACK", 0),
            "degraded_count": counts.get("DEGRADED", 0),
            "unidentified_count": counts.get("UNIDENTIFIED", 0),
            "llm_mode": llm_summary.get("mode"),
            "fallback_page_count": llm_summary.get("fallback_page_count", 0),
        },
        "metrics": {
            "checks_total": len(quality_pages),
            "checks_pass": sum(1 for p in quality_pages if p["quality_state"] in _READY_STATES),
            "evidence_total": sum(int(p["evidence_count"]) for p in quality_pages),
            "citation_total": sum(int(p["citation_count"]) for p in quality_pages),
        },
        "aggregate_summary": {"quality_states": dict(counts)},
        "page_quality": quality_pages,
        "pages": quality_pages,
    }
    return page_registry, quality_report


def build_evidence_index(
    *,
    run_id: str,
    content_dir: Path,
    page_registry: dict[str, Any],
) -> dict[str, Any]:
    """Build citation spans from final rendered pages in registry order."""
    spans: list[dict[str, Any]] = []
    for page in page_registry.get("pages", []):
        if not isinstance(page, dict):
            continue
        page_relative_path = str(page.get("relative_path") or "")
        if not _safe_relative_path(page_relative_path, markdown_only=True):
            continue
        rendered = _read_text(content_dir / page_relative_path)
        seen: set[tuple[str, int, int]] = set()
        for raw in _CITE_VALUE_PATTERN.findall(rendered):
            citation = _parse_repository_citation(raw)
            if citation is None or citation in seen:
                continue
            seen.add(citation)
            source_path, start_line, end_line = citation
            identity = f"{page_relative_path}\0{source_path}\0{start_line}\0{end_line}"
            spans.append(
                {
                    "span_id": f"cite-{sha256(identity.encode('utf-8')).hexdigest()[:24]}",
                    "page_relative_path": page_relative_path,
                    "source_path": source_path,
                    "start_line": start_line,
                    "end_line": end_line,
                }
            )
    return {
        "schema_version": SCHEMA_VERSION_EVIDENCE_INDEX,
        "generated_at": str(page_registry.get("generated_at") or _now_iso()),
        "run_id": run_id,
        "spans": spans,
        "summary": {
            "page_count": len(page_registry.get("pages", [])),
            "span_count": len(spans),
        },
    }


def _parse_repository_citation(raw: str) -> tuple[str, int, int] | None:
    value = normalize_citation_ref(raw)
    if value.startswith("source:"):
        value = value[len("source:") :].strip()
    match = _CITE_TARGET_PATTERN.fullmatch(value)
    if match is None:
        return None
    source_path = match.group("path").strip()
    if not _safe_relative_path(source_path):
        return None
    start_line = int(match.group("start"))
    end_line = int(match.group("end") or start_line)
    if end_line < start_line:
        return None
    return PurePosixPath(source_path).as_posix(), start_line, end_line


def _safe_relative_path(value: str, *, markdown_only: bool = False) -> bool:
    if (
        not value
        or "\\" in value
        or "\x00" in value
        or value.startswith("/")
        or _URI_SCHEME_PATTERN.match(value)
    ):
        return False
    path = PurePosixPath(value)
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        return False
    return not markdown_only or path.suffix.lower() == ".md"


def write_generation_quality_artifacts(
    *,
    meta_dir: Path,
    run_id: str,
    profile_name: str,
    content_dir: Path,
    plan_pages: list[Any],
    written_files: list[str],
    content_stats: dict[str, Any],
    composition_page_metadata: list[dict[str, Any]],
    failed_pages: list[dict[str, Any]],
    quality_warnings: list[dict[str, Any]],
    llm_summary: dict[str, Any],
) -> dict[str, str]:
    page_registry, quality_report = build_generation_quality_documents(
        run_id=run_id,
        profile_name=profile_name,
        content_dir=content_dir,
        plan_pages=plan_pages,
        written_files=written_files,
        content_stats=content_stats,
        composition_page_metadata=composition_page_metadata,
        failed_pages=failed_pages,
        quality_warnings=quality_warnings,
        llm_summary=llm_summary,
    )
    evidence_index = build_evidence_index(
        run_id=run_id,
        content_dir=content_dir,
        page_registry=page_registry,
    )
    return {
        "page_registry": str(_json_write(meta_dir / "page-registry.json", page_registry)),
        "evidence_index": str(_json_write(meta_dir / "evidence-index.json", evidence_index)),
        "quality_report": str(_json_write(meta_dir / "quality-report.json", quality_report)),
    }


def write_generation_conflict_artifacts(
    *,
    config: Any,
    repo_root: Path,
    meta_dir: Path,
    reports_dir: Path,
    persist_scanner_cache: bool = True,
) -> dict[str, str]:
    """Write source/docs inventories and canonical source-doc conflict reports."""
    from repo_wiki.scanner.conflict_resolver import (
        resolve_source_docs_conflicts,
        write_conflict_report,
    )
    from repo_wiki.scanner.docs_scanner import scan_repository_docs_inventory
    from repo_wiki.scanner.multi_runtime_scanner_v3 import MultiRuntimeSourceScannerV3

    source_inventory = MultiRuntimeSourceScannerV3(config).scan(
        incremental=persist_scanner_cache,
        persist_state=persist_scanner_cache,
    )
    docs_inventory = scan_repository_docs_inventory(
        repo_root,
        source_inventory,
        incremental=persist_scanner_cache,
        persist_cache=persist_scanner_cache,
    )

    # Ensure headers remain explicit if upstream scanners add optional version fields later.
    source_inventory.setdefault("schema_version", SCHEMA_VERSION_SOURCE_INVENTORY)
    docs_inventory.setdefault("schema_version", SCHEMA_VERSION_DOCS_INVENTORY)

    conflict_report = resolve_source_docs_conflicts(source_inventory, docs_inventory)
    source_path = _json_write(meta_dir / "source-inventory.json", source_inventory)
    docs_path = _json_write(meta_dir / "docs-inventory.json", docs_inventory)
    meta_conflicts = write_conflict_report(conflict_report, meta_dir / "source-docs-conflicts.json")
    report_conflicts = write_conflict_report(
        conflict_report, reports_dir / "source-docs-conflicts.json"
    )
    return {
        "source_inventory": str(source_path),
        "docs_inventory": str(docs_path),
        "source_docs_conflicts_meta": str(meta_conflicts),
        "source_docs_conflicts_report": str(report_conflicts),
    }
