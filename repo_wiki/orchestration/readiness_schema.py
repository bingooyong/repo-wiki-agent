"""Replacement readiness schema v2.

Decouples strict verification PASS from final replacement GO decisions.
Replacement GO requires:
- strict verify PASS
- qoder comparison READY
- manual review matrix v2 PASS
"""

from __future__ import annotations

from typing import Any


def _is_strict_pass(strict_verify: dict[str, Any] | None) -> bool:
    if not isinstance(strict_verify, dict):
        return False
    return str(strict_verify.get("grade", "")).upper() == "PASS"


def _is_comparison_ready(comparison_result: dict[str, Any] | None) -> bool:
    if not isinstance(comparison_result, dict):
        return False
    return str(comparison_result.get("status", "")).upper() == "READY"


def _is_manual_review_pass(manual_review_result: dict[str, Any] | None) -> bool:
    if not isinstance(manual_review_result, dict):
        return False
    summary = manual_review_result.get("summary")
    if not isinstance(summary, dict):
        return False
    return str(summary.get("status", "")).upper() == "PASS"


def evaluate_replacement_readiness_v2(
    *,
    strict_verify: dict[str, Any] | None,
    comparison_result: dict[str, Any] | None,
    manual_review_result: dict[str, Any] | None,
) -> dict[str, Any]:
    """Evaluate replacement readiness using schema v2."""
    strict_pass = _is_strict_pass(strict_verify)
    comparison_ready = _is_comparison_ready(comparison_result)
    manual_review_pass = _is_manual_review_pass(manual_review_result)

    reasons: list[str] = []
    if not strict_pass:
        reasons.append("STRICT_VERIFY_NOT_PASS")
    if comparison_result is None:
        reasons.append("QODER_COMPARISON_REQUIRED")
    elif not comparison_ready:
        reasons.append("QODER_COMPARISON_NOT_READY")
    if manual_review_result is None:
        reasons.append("MANUAL_REVIEW_REQUIRED")
    elif not manual_review_pass:
        reasons.append("MANUAL_REVIEW_NOT_PASS")
        failures = manual_review_result.get("failures", [])
        if isinstance(failures, list):
            for item in failures:
                if isinstance(item, dict):
                    code = item.get("code")
                    if isinstance(code, str) and code:
                        reasons.append(code)

    replacement_go = strict_pass and comparison_ready and manual_review_pass
    readiness_state = "READY" if replacement_go else "NOT_READY"

    return {
        "schema_version": "readiness-schema-v2",
        "replacement_go": replacement_go,
        "readiness_state": readiness_state,
        "readiness_reasons": reasons,
        "checks": {
            "strict_verify_pass": strict_pass,
            "qoder_comparison_ready": comparison_ready,
            "manual_review_pass": manual_review_pass,
        },
    }
