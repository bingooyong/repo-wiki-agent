from __future__ import annotations

import json

from repo_wiki.scanner.conflict_resolver import (
    MISSING_SOURCE_CONFIRMATION,
    SOURCE_DOC_MISMATCH,
    STALE_DOC_REFERENCE,
    UNSUPPORTED_DOC_CLAIM,
    resolve_source_docs_conflicts,
    write_conflict_report,
)
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeSeverityThreshold


def _source_inventory_fixture() -> dict:
    return {
        "services": [{"service_id": "orders-service", "name": "orders-service"}],
        "api_surfaces": [{"path": "/orders", "method": "GET", "service": "orders-service"}],
        "data_models": [{"name": "OrderModel"}],
        "frontend_callers": [],
        "deployment_assets": [],
        "tests": [],
    }


def test_conflict_resolver_handles_all_four_reason_codes(tmp_path):
    docs_inventory = {
        "documents": [
            {
                "path": "docs/api.md",
                "doc_type": "api",
                "conflict_level": "conflicting",
                "stale_references": ["src/legacy/order_api.py"],
                "conflicting_claims": ["payment-service", "OrderV2Model"],
            },
            {
                "path": "docs/phase-plan.md",
                "doc_type": "planning",
                "conflict_level": "stale",
                "stale_references": [],
                "conflicting_claims": ["future-service"],
            },
        ]
    }

    report = resolve_source_docs_conflicts(_source_inventory_fixture(), docs_inventory)
    all_items = report["resolved_items"] + report["deferred_items"] + report["flagged_items"]
    codes = {item["reason_code"] for item in all_items}

    assert SOURCE_DOC_MISMATCH in codes
    assert STALE_DOC_REFERENCE in codes
    assert UNSUPPORTED_DOC_CLAIM in codes
    assert MISSING_SOURCE_CONFIRMATION in codes

    classifications = {item["classification"] for item in all_items}
    assert "待确认" in classifications
    assert "historical" in classifications

    planning_items = [item for item in all_items if item["doc_path"] == "docs/phase-plan.md"]
    assert planning_items
    assert all(item["status"] == "resolved" for item in planning_items)
    assert all(item["classification"] == "historical" for item in planning_items)
    assert any(item["reason_code"] == UNSUPPORTED_DOC_CLAIM for item in planning_items)

    api_items = [item for item in all_items if item["doc_path"] == "docs/api.md"]
    assert api_items
    assert all(item["status"] in {"deferred", "flagged"} for item in api_items)
    assert all(item["classification"] == "待确认" for item in api_items)

    out = write_conflict_report(report, tmp_path / "reports" / "source-docs-conflicts.json")
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["summary"]["total_items"] >= 4
    assert payload["summary"]["resolved_count"] == len(planning_items)
    assert payload["summary"]["deferred_count"] + payload["summary"]["flagged_count"] == len(
        api_items
    )


def test_reason_codes_are_blocking_in_strict_profile():
    threshold = QoderLikeSeverityThreshold()
    for code in (
        SOURCE_DOC_MISMATCH,
        STALE_DOC_REFERENCE,
        UNSUPPORTED_DOC_CLAIM,
        MISSING_SOURCE_CONFIRMATION,
    ):
        assert threshold.is_blocking(code) is True


def test_historical_authority_docs_are_resolved():
    docs_inventory = {
        "documents": [
            {
                "path": "docs/00-overview.md",
                "doc_type": "overview",
                "authority_level": "historical",
                "conflict_level": "stale",
                "stale_references": ["src/legacy/gone.py"],
                "conflicting_claims": ["GhostService"],
            }
        ]
    }
    report = resolve_source_docs_conflicts(_source_inventory_fixture(), docs_inventory)
    assert report["deferred_items"] == []
    assert report["flagged_items"] == []
    assert report["resolved_items"]
    assert all(item["status"] == "resolved" for item in report["resolved_items"])
    assert all(item["classification"] == "historical" for item in report["resolved_items"])
