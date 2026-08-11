"""Manual review matrix v2 for replacement readiness decisions.

Phase 39 - Task 39.2:
- Require at least 30 reviewed pages across key categories
- Require at least 24 accepted pages
- Require zero P0 failures on mandatory rows
- Include API台账服务 API as a mandatory row
- Support storing review artifacts under run reports or operations evidence
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MANDATORY_PAGE_LABELS = ("API台账服务 API",)
REQUIRED_CATEGORIES = (
    "overview",
    "architecture",
    "services",
    "api",
    "data-models",
    "operations",
    "security",
    "troubleshooting",
)
MIN_REVIEWED_PAGES = 30
MIN_ACCEPTED_PAGES = 24


@dataclass(frozen=True)
class ManualReviewRow:
    """A single manual review row."""

    page_label: str
    category: str
    accepted: bool
    severity: str = "P2"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_label": self.page_label,
            "category": self.category,
            "accepted": self.accepted,
            "severity": self.severity.upper(),
            "notes": self.notes,
        }


def evaluate_manual_review_matrix_v2(rows: list[ManualReviewRow]) -> dict[str, Any]:
    """Evaluate manual review matrix v2 readiness gate."""
    category_set = {row.category for row in rows}
    accepted_count = sum(1 for row in rows if row.accepted)
    missing_mandatory = [
        label for label in MANDATORY_PAGE_LABELS if not any(row.page_label == label for row in rows)
    ]
    mandatory_rows = [row for row in rows if row.page_label in MANDATORY_PAGE_LABELS]
    mandatory_p0_failures = [
        row.page_label
        for row in mandatory_rows
        if (not row.accepted and row.severity.upper() == "P0")
    ]
    missing_categories = [c for c in REQUIRED_CATEGORIES if c not in category_set]

    failures: list[dict[str, Any]] = []
    if len(rows) < MIN_REVIEWED_PAGES:
        failures.append(
            {
                "code": "MANUAL_REVIEW_REVIEWED_PAGES_LOW",
                "message": "Reviewed pages are below required minimum",
                "actual": len(rows),
                "threshold": MIN_REVIEWED_PAGES,
            }
        )
    if accepted_count < MIN_ACCEPTED_PAGES:
        failures.append(
            {
                "code": "MANUAL_REVIEW_ACCEPTED_PAGES_LOW",
                "message": "Accepted pages are below required minimum",
                "actual": accepted_count,
                "threshold": MIN_ACCEPTED_PAGES,
            }
        )
    if missing_mandatory:
        failures.append(
            {
                "code": "MANUAL_REVIEW_MANDATORY_ROW_MISSING",
                "message": "Mandatory review rows are missing",
                "actual": missing_mandatory,
                "threshold": list(MANDATORY_PAGE_LABELS),
            }
        )
    if mandatory_p0_failures:
        failures.append(
            {
                "code": "MANUAL_REVIEW_MANDATORY_P0_FAILURE",
                "message": "Mandatory rows contain P0 failures",
                "actual": mandatory_p0_failures,
                "threshold": 0,
            }
        )
    if missing_categories:
        failures.append(
            {
                "code": "MANUAL_REVIEW_CATEGORY_COVERAGE_LOW",
                "message": "Manual review categories are incomplete",
                "actual": sorted(category_set),
                "threshold": list(REQUIRED_CATEGORIES),
                "missing": missing_categories,
            }
        )

    return {
        "schema_version": "manual-review-matrix-v2",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "thresholds": {
            "min_reviewed_pages": MIN_REVIEWED_PAGES,
            "min_accepted_pages": MIN_ACCEPTED_PAGES,
            "mandatory_page_labels": list(MANDATORY_PAGE_LABELS),
            "required_categories": list(REQUIRED_CATEGORIES),
            "mandatory_rows_zero_p0_failures": True,
        },
        "summary": {
            "reviewed_pages": len(rows),
            "accepted_pages": accepted_count,
            "mandatory_rows_present": len(missing_mandatory) == 0,
            "mandatory_p0_failures": mandatory_p0_failures,
            "categories_covered": sorted(category_set),
            "missing_categories": missing_categories,
            "hard_failures": len(failures),
            "status": "PASS" if not failures else "FAIL",
        },
        "failures": failures,
        "rows": [row.to_dict() for row in rows],
    }


def write_manual_review_artifacts(
    evaluation: dict[str, Any],
    *,
    run_reports_dir: Path | None = None,
    operations_evidence_dir: Path | None = None,
) -> dict[str, str]:
    """Write manual review artifacts to run reports and/or operations evidence.

    Note: writing to multiple targets is not atomic — if one target fails after
    another succeeds, artifacts will be partially written. Callers that require
    atomicity should write to a single target or handle cleanup on failure.
    """
    targets = [p for p in (run_reports_dir, operations_evidence_dir) if p is not None]
    if not targets:
        raise ValueError("At least one artifact destination must be provided")

    written: dict[str, str] = {}
    for target in targets:
        target.mkdir(parents=True, exist_ok=True)
        json_path = target / "manual-review-matrix-v2.json"
        md_path = target / "manual-review-matrix-v2.md"
        json_path.write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(_to_markdown(evaluation), encoding="utf-8")
        written[str(target)] = str(json_path)
    return written


def _to_markdown(evaluation: dict[str, Any]) -> str:
    summary = evaluation.get("summary", {})
    thresholds = evaluation.get("thresholds", {})
    lines = [
        "# Manual Review Matrix v2",
        "",
        f"- Status: **{summary.get('status', 'UNKNOWN')}**",
        f"- Reviewed pages: `{summary.get('reviewed_pages', 0)}` (threshold `{thresholds.get('min_reviewed_pages', MIN_REVIEWED_PAGES)}`)",
        f"- Accepted pages: `{summary.get('accepted_pages', 0)}` (threshold `{thresholds.get('min_accepted_pages', MIN_ACCEPTED_PAGES)}`)",
        f"- Mandatory labels: `{', '.join(thresholds.get('mandatory_page_labels', []))}`",
        "",
    ]
    failures = evaluation.get("failures", [])
    if failures:
        lines.append("## Failures")
        for item in failures:
            lines.append(f"- `{item.get('code', 'UNKNOWN')}`: {item.get('message', '')}")
    else:
        lines.append("## Failures")
        lines.append("- None")
    lines.append("")
    lines.append("## Mandatory Row Check")
    for label in thresholds.get("mandatory_page_labels", MANDATORY_PAGE_LABELS):
        lines.append(f"- `{label}` represented: `{summary.get('mandatory_rows_present', False)}`")
    lines.append("")
    return "\n".join(lines) + "\n"
