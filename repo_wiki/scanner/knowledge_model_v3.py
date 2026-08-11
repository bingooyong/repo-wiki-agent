"""Repository Knowledge Model v3 persistence and diff utilities.

Unifies source-inventory (Task 42.1), docs-inventory (Task 42.2), and
source-doc conflict report (Task 42.3) into one persisted model for downstream
IA/evidence/diagram/release workflows.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from repo_wiki.orchestration.release_meta_schema import SCHEMA_VERSION_QUALITY_REPORT

MODEL_SCHEMA_VERSION = "repo_agent.knowledge_model_v3/1.0"
MODEL_CACHE_PATH = Path(".repo-wiki/cache/knowledge_model_v3.json")


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _record_id(prefix: str, payload: dict[str, Any], key_hint: str | None = None) -> str:
    if key_hint:
        parts = [str(payload.get(k, "")) for k in key_hint.split("+")]
        if all(p for p in parts):
            return f"{prefix}:{':'.join(parts)}"
    return f"{prefix}:{_stable_hash(payload)[:16]}"


def _normalize_source_records(source_inventory: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    source_root = str(source_inventory.get("repository_root", ""))
    files = source_inventory.get("files", [])
    return {
        "services": [
            {
                "service_id": _record_id("service", item, "service_id"),
                "runtime": item.get("runtime", item.get("kind", "unknown")),
                "entrypoints": [item.get("handler")] if item.get("handler") else [],
                "ports": item.get("ports", []),
                "dependencies": item.get("dependencies", []),
                "evidence_path": item.get("evidence_path"),
                "raw": item,
            }
            for item in source_inventory.get("services", [])
            if isinstance(item, dict)
        ],
        "api_surfaces": [
            {
                "api_id": _record_id("api", item, "method+path"),
                "service_id": item.get("service_id"),
                "method": item.get("method"),
                "path": item.get("path"),
                "parameters": item.get("parameters", []),
                "response_types": item.get("response_types", []),
                "handler": item.get("handler"),
                "evidence_path": item.get("evidence_path"),
                "raw": item,
            }
            for item in source_inventory.get("api_surfaces", [])
            if isinstance(item, dict)
        ],
        "data_models": [
            {
                "model_id": _record_id("model", item, "name"),
                "name": item.get("name"),
                "fields": item.get("fields", []),
                "relationships": item.get("relationships", []),
                "kind": item.get("kind"),
                "service_id": item.get("service_id"),
                "evidence_path": item.get("evidence_path"),
                "raw": item,
            }
            for item in source_inventory.get("data_models", [])
            if isinstance(item, dict)
        ],
        "frontend_consumers": [
            {
                "consumer_id": _record_id("frontend", item, "target"),
                "call_site": item.get("target"),
                "service_id": item.get("service_id"),
                "evidence_path": item.get("evidence_path"),
                "raw": item,
            }
            for item in source_inventory.get("frontend_callers", [])
            if isinstance(item, dict)
        ],
        "operation_assets": [
            {
                "asset_id": _record_id("ops", item, "evidence_path"),
                "asset_type": item.get("kind"),
                "path": item.get("evidence_path"),
                "raw": item,
            }
            for item in source_inventory.get("deployment_assets", [])
            if isinstance(item, dict)
        ],
        "repository": [
            {
                "repository_id": _stable_hash(source_root)[:16] if source_root else "unknown",
                "repository_root": source_root,
                "shape_summary": {
                    "files_count": len(files) if isinstance(files, list) else 0,
                    "services_count": len(source_inventory.get("services", []))
                    if isinstance(source_inventory.get("services", []), list)
                    else 0,
                    "api_surfaces_count": len(source_inventory.get("api_surfaces", []))
                    if isinstance(source_inventory.get("api_surfaces", []), list)
                    else 0,
                    "data_models_count": len(source_inventory.get("data_models", []))
                    if isinstance(source_inventory.get("data_models", []), list)
                    else 0,
                },
            }
        ],
    }


def _normalize_docs_records(docs_inventory: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in docs_inventory.get("documents", []):
        if not isinstance(d, dict):
            continue
        out.append(
            {
                "doc_id": _record_id("doc", d, "path"),
                "path": d.get("path"),
                "doc_type": d.get("doc_type"),
                "authority": d.get("authority_level"),
                "authority_score": d.get("authority_score"),
                "freshness_score": d.get("freshness_score"),
                "conflict_level": d.get("conflict_level"),
                "stale_references": d.get("stale_references", []),
                "conflicting_claims": d.get("conflicting_claims", []),
                "content_sha256": d.get("content_sha256"),
            }
        )
    return out


def _normalize_conflicts(conflict_report: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in ("resolved_items", "deferred_items", "flagged_items"):
        status = key.replace("_items", "")
        for item in conflict_report.get(key, []):
            if not isinstance(item, dict):
                continue
            out.append(
                {
                    "conflict_id": _record_id("conflict", item),
                    "doc_path": item.get("doc_path"),
                    "reason_code": item.get("reason_code"),
                    "resolution_status": status,
                    "message": item.get("message"),
                    "evidence": item.get("evidence", []),
                }
            )
    return out


def _evidence_from_inputs(
    source_inventory: dict[str, Any], docs_inventory: dict[str, Any]
) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for d in docs_inventory.get("documents", []):
        if not isinstance(d, dict):
            continue
        page = d.get("path")
        for p in d.get("stale_references", []):
            if isinstance(p, str):
                spans.append(
                    {
                        "span_id": _record_id("evidence", {"page": page, "source": p}),
                        "source_path": p,
                        "wiki_page_path": page,
                        "source": "docs_stale_reference",
                    }
                )
    for a in source_inventory.get("api_surfaces", []):
        if not isinstance(a, dict):
            continue
        ep = a.get("evidence_path")
        if isinstance(ep, str):
            spans.append(
                {
                    "span_id": _record_id("evidence", {"source": ep, "api": a.get("path")}),
                    "source_path": ep,
                    "wiki_page_path": None,
                    "source": "source_inventory",
                }
            )
    return spans


def build_knowledge_model_v3(
    source_inventory: dict[str, Any],
    docs_inventory: dict[str, Any],
    conflict_report: dict[str, Any],
    *,
    previous_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build unified model dict with all nine record families."""
    src_norm = _normalize_source_records(source_inventory)
    docs_norm = _normalize_docs_records(docs_inventory)
    conflicts = _normalize_conflicts(conflict_report)
    evidence = _evidence_from_inputs(source_inventory, docs_inventory)

    model: dict[str, Any] = {
        "schema_version": MODEL_SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "input_fingerprints": {
            "source_inventory": _stable_hash(source_inventory),
            "docs_inventory": _stable_hash(docs_inventory),
            "conflict_report": _stable_hash(conflict_report),
        },
        "records": {
            "repository": src_norm["repository"],
            "services": src_norm["services"],
            "api_surfaces": src_norm["api_surfaces"],
            "data_models": src_norm["data_models"],
            "frontend_consumers": src_norm["frontend_consumers"],
            "operation_assets": src_norm["operation_assets"],
            "doc_artifacts": docs_norm,
            "evidence_spans": evidence,
            "conflicts": conflicts,
        },
        "summary": {
            "repository_count": len(src_norm["repository"]),
            "service_count": len(src_norm["services"]),
            "api_surface_count": len(src_norm["api_surfaces"]),
            "data_model_count": len(src_norm["data_models"]),
            "frontend_consumer_count": len(src_norm["frontend_consumers"]),
            "operation_asset_count": len(src_norm["operation_assets"]),
            "doc_artifact_count": len(docs_norm),
            "evidence_span_count": len(evidence),
            "conflict_count": len(conflicts),
        },
    }

    if previous_model and isinstance(previous_model, dict):
        model["previous_generated_at"] = previous_model.get("generated_at")
    return model


def model_cache_file(repo_root: Path) -> Path:
    return Path(repo_root).resolve() / MODEL_CACHE_PATH


def load_knowledge_model_v3(repo_root: Path) -> dict[str, Any] | None:
    path = model_cache_file(repo_root)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def is_model_stale(
    model: dict[str, Any] | None,
    source_inventory: dict[str, Any],
    docs_inventory: dict[str, Any],
    conflict_report: dict[str, Any],
) -> bool:
    """True when cached model fingerprints no longer match current inputs."""
    if not model or not isinstance(model, dict):
        return True
    fp = model.get("input_fingerprints")
    if not isinstance(fp, dict):
        return True
    return any(
        fp.get(name) != _stable_hash(payload)
        for name, payload in (
            ("source_inventory", source_inventory),
            ("docs_inventory", docs_inventory),
            ("conflict_report", conflict_report),
        )
    )


def persist_knowledge_model_v3(
    repo_root: Path,
    source_inventory: dict[str, Any],
    docs_inventory: dict[str, Any],
    conflict_report: dict[str, Any],
    *,
    incremental: bool = True,
) -> tuple[dict[str, Any], bool]:
    """Persist model to `.repo-wiki/cache/knowledge_model_v3.json`.

    Returns `(model, reused_cache)` where `reused_cache=True` means stale check
    passed and existing cache was reused unchanged.
    """
    existing = load_knowledge_model_v3(repo_root)
    stale = is_model_stale(existing, source_inventory, docs_inventory, conflict_report)
    if incremental and not stale and existing is not None:
        return existing, True

    model = build_knowledge_model_v3(
        source_inventory,
        docs_inventory,
        conflict_report,
        previous_model=existing if isinstance(existing, dict) else None,
    )
    out = model_cache_file(repo_root)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
    return model, False


def diff_knowledge_models(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Compute simple per-record-family added/removed counts and IDs."""
    out: dict[str, Any] = {"record_diffs": {}, "summary_delta": {}}
    old_records = old.get("records", {}) if isinstance(old, dict) else {}
    new_records = new.get("records", {}) if isinstance(new, dict) else {}
    for family in (
        "repository",
        "services",
        "api_surfaces",
        "data_models",
        "frontend_consumers",
        "operation_assets",
        "doc_artifacts",
        "evidence_spans",
        "conflicts",
    ):
        old_items = old_records.get(family, []) if isinstance(old_records, dict) else []
        new_items = new_records.get(family, []) if isinstance(new_records, dict) else []
        _id_fields = (
            "repository_id",
            "service_id",
            "api_id",
            "model_id",
            "consumer_id",
            "asset_id",
            "doc_id",
            "span_id",
            "conflict_id",
        )
        old_ids = {
            _id
            for item in old_items
            if isinstance(item, dict)
            for _id in [next((item[k] for k in _id_fields if item.get(k)), None)]
            if isinstance(_id, str)
        }
        new_ids = {
            _id
            for item in new_items
            if isinstance(item, dict)
            for _id in [next((item[k] for k in _id_fields if item.get(k)), None)]
            if isinstance(_id, str)
        }
        out["record_diffs"][family] = {
            "added": sorted(new_ids - old_ids),
            "removed": sorted(old_ids - new_ids),
            "added_count": len(new_ids - old_ids),
            "removed_count": len(old_ids - new_ids),
        }

    old_summary = old.get("summary", {}) if isinstance(old, dict) else {}
    new_summary = new.get("summary", {}) if isinstance(new, dict) else {}
    for key, nv in new_summary.items():
        ov = old_summary.get(key)
        if isinstance(nv, int) and isinstance(ov, int):
            out["summary_delta"][key] = nv - ov
    return out


def export_model_summary_for_release_meta(model: dict[str, Any]) -> dict[str, Any]:
    """Export quality-report-compatible summary payload for release meta sidecars."""
    summary = model.get("summary", {}) if isinstance(model, dict) else {}
    conflicts = summary.get("conflict_count", 0)
    grade = "PASS" if isinstance(conflicts, int) and conflicts == 0 else "WARN"
    return {
        "schema_version": SCHEMA_VERSION_QUALITY_REPORT,
        "summary": {
            "profile": "knowledge-model-v3",
            "grade": grade,
            "strict_mode": True,
        },
        "metrics": {
            "knowledge_model_v3": summary,
        },
    }
