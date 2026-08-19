"""Source-docs conflict resolver for repository knowledge compilation.

Policy:
- Prefer source/config/OpenAPI for current implementation facts.
- Use docs for intent, background, terminology, and historical context.
- Mark disagreements as 待确认 or historical instead of inventing current facts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SOURCE_DOC_MISMATCH = "SOURCE_DOC_MISMATCH"
STALE_DOC_REFERENCE = "STALE_DOC_REFERENCE"
UNSUPPORTED_DOC_CLAIM = "UNSUPPORTED_DOC_CLAIM"
MISSING_SOURCE_CONFIRMATION = "MISSING_SOURCE_CONFIRMATION"


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _to_token_set(source_inventory: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for key in (
        "services",
        "api_surfaces",
        "data_models",
        "frontend_callers",
        "deployment_assets",
        "tests",
    ):
        items = source_inventory.get(key, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            for field in (
                "name",
                "service",
                "service_id",
                "handler",
                "path",
                "kind",
                "evidence_path",
            ):
                val = item.get(field)
                if isinstance(val, str) and val.strip():
                    tokens.add(val.strip().lower())
    return tokens


@dataclass(frozen=True)
class ConflictItem:
    doc_path: str
    reason_code: str
    status: str
    classification: str
    message: str
    evidence: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_path": self.doc_path,
            "reason_code": self.reason_code,
            "status": self.status,
            "classification": self.classification,
            "message": self.message,
            "evidence": self.evidence,
        }


def _is_historical_doc(doc: dict[str, Any]) -> bool:
    """Planning/changelog docs and already-historical items do not block READY."""
    doc_type = str(doc.get("doc_type", "")).lower()
    authority = str(doc.get("authority_level", "")).lower()
    classification = str(doc.get("classification", "")).lower()
    return (
        doc_type in {"planning", "changelog"}
        or authority == "historical"
        or classification == "historical"
    )


def _status_for_doc(doc: dict[str, Any], blocking_status: str) -> tuple[str, str]:
    if _is_historical_doc(doc):
        return "resolved", "historical"
    return blocking_status, "待确认"


def resolve_source_docs_conflicts(
    source_inventory: dict[str, Any],
    docs_inventory: dict[str, Any],
) -> dict[str, Any]:
    """Resolve source/docs conflicts into resolved/deferred/flagged buckets."""
    source_tokens = _to_token_set(source_inventory)
    documents = docs_inventory.get("documents", [])
    if not isinstance(documents, list):
        documents = []

    items: list[ConflictItem] = []
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        path = str(doc.get("path", "unknown"))
        conflict_level = str(doc.get("conflict_level", "aligned")).lower()
        stale_refs = [str(v) for v in doc.get("stale_references", []) if isinstance(v, str)]
        conflicting_claims = [
            str(v) for v in doc.get("conflicting_claims", []) if isinstance(v, str)
        ]
        doc_type = str(doc.get("doc_type", "overview")).lower()

        if stale_refs:
            status, classification = _status_for_doc(doc, "flagged")
            items.append(
                ConflictItem(
                    doc_path=path,
                    reason_code=STALE_DOC_REFERENCE,
                    status=status,
                    classification=classification,
                    message="Doc references source artifacts that no longer exist.",
                    evidence=stale_refs,
                )
            )
        if conflicting_claims:
            status, classification = _status_for_doc(doc, "deferred")
            items.append(
                ConflictItem(
                    doc_path=path,
                    reason_code=SOURCE_DOC_MISMATCH,
                    status=status,
                    classification=classification,
                    message="Doc claims conflict with current source inventory facts.",
                    evidence=conflicting_claims,
                )
            )

        # Unsupported / missing confirmation checks for planning/historical docs.
        if doc_type in {"planning", "changelog"} and conflict_level in {"stale", "conflicting"}:
            items.append(
                ConflictItem(
                    doc_path=path,
                    reason_code=UNSUPPORTED_DOC_CLAIM,
                    status="resolved",
                    classification="historical",
                    message="Historical/planning claim is not suitable as current implementation fact.",
                    evidence=conflicting_claims or stale_refs or [path],
                )
            )

        # Feature claim without source confirmation.
        for claim in conflicting_claims:
            if claim.lower() not in source_tokens:
                status, classification = _status_for_doc(doc, "deferred")
                items.append(
                    ConflictItem(
                        doc_path=path,
                        reason_code=MISSING_SOURCE_CONFIRMATION,
                        status=status,
                        classification=classification,
                        message="Doc feature claim has no source confirmation.",
                        evidence=[claim],
                    )
                )

    resolved: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    flagged: list[dict[str, Any]] = []
    for item in items:
        encoded = item.to_dict()
        if item.status == "resolved":
            resolved.append(encoded)
        elif item.status == "deferred":
            deferred.append(encoded)
        else:
            flagged.append(encoded)

    return {
        "schema_version": "source-docs-conflict-resolver-v1",
        "generated_at": _now_iso(),
        "policy": {
            "implementation_facts_preferred_from": ["source", "config", "openapi"],
            "docs_used_for": ["intent", "background", "terminology", "historical_decisions"],
            "conflict_marking": ["待确认", "historical"],
        },
        "reason_codes": [
            SOURCE_DOC_MISMATCH,
            STALE_DOC_REFERENCE,
            UNSUPPORTED_DOC_CLAIM,
            MISSING_SOURCE_CONFIRMATION,
        ],
        "summary": {
            "resolved_count": len(resolved),
            "deferred_count": len(deferred),
            "flagged_count": len(flagged),
            "total_items": len(items),
        },
        "resolved_items": resolved,
        "deferred_items": deferred,
        "flagged_items": flagged,
    }


def write_conflict_report(
    report: dict[str, Any],
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
