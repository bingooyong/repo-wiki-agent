"""Compile and validate G005 production quality-gate bundles.

The G005 bundle is intentionally a derived artifact: every PASS/READY decision is
recomputed from concrete evidence files and public validators. Release publishing
must treat this bundle as an index of evidence paths and fingerprints, not as an
authoritative status flag.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "repo_agent.g005_quality_gates/1.0"
REQUIRED_ARTIFACTS = (
    "strict_verify",
    "qoder_comparison",
    "blind_review_v3",
    "blind_review_attestation",
    "acceptance_fixture_registry",
    "citation_hard_gate_evidence",
    "critical_false_fact_evidence",
    "quality_hard_gate_evidence",
    "conflict_hard_gate_evidence",
)
STRICT_CHECK_GROUPS = {
    "citation_hard_gate_evidence": {"qoder-citation-targets"},
    "critical_false_fact_evidence": {"qoder-critical-false-facts"},
    "quality_hard_gate_evidence": {"qoder-quality-artifacts"},
    "conflict_hard_gate_evidence": {"qoder-unresolved-fact-conflicts"},
}
QODER_REQUIRED_METRICS = frozenset(
    {
        "page_count",
        "chinese_directory_depth",
        "toc_coverage",
        "citation_coverage",
        "file_line_reference_coverage",
        "mermaid_coverage",
        "prose_list_ratio",
        "api_aggregation_quality",
        "data_model_aggregation_quality",
        "broken_links",
        "stale_git_commit",
        "llm_generation_coverage",
    }
)
QODER_REQUIRED_READINESS_THRESHOLDS = frozenset(
    {
        "page_count_ratio_vs_baseline",
        "chinese_directory_depth_ratio_vs_baseline",
        "llm_generation_coverage",
        "baseline_read_only_verified",
    }
)


class G005QualityGateError(ValueError):
    """Raised when a G005 gate cannot be compiled or validated."""


@dataclass(frozen=True)
class G005Inputs:
    run_dir: Path
    qoder_comparison: Path
    blind_review_v3: Path
    acceptance_fixture_registry: Path
    strict_verify: Path | None = None
    citation_hard_gate_evidence: Path | None = None
    critical_false_fact_evidence: Path | None = None
    quality_hard_gate_evidence: Path | None = None
    conflict_hard_gate_evidence: Path | None = None
    acceptance_artifact_root: Path | None = None
    blind_review_attestation: Path | None = None
    review_allowed_signers: Path | None = None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8"))
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def hash_run_tree(run_dir: Path) -> str:
    """Hash the selected run, excluding the self-referential G005 report file."""
    digest = hashlib.sha256()
    excluded = {"reports/g005-quality-gates.json"}
    if not run_dir.exists():
        return digest.hexdigest()
    for path in sorted(run_dir.rglob("*")):
        rel = path.relative_to(run_dir).as_posix()
        if rel in excluded:
            continue
        digest.update(rel.encode("utf-8"))
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def stable_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive guard
        raise G005QualityGateError(f"Invalid JSON artifact: {path}") from exc
    if not isinstance(data, dict):
        raise G005QualityGateError(f"JSON artifact must be an object: {path}")
    return data


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f".{path.name}-",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
            json.dump(payload, tmp, ensure_ascii=False, indent=2)
            tmp.write("\n")
        tmp_path.replace(path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()


def _resolve_inside_run(run_dir: Path, raw: Path | str, description: str) -> Path:
    run_root = run_dir.resolve()
    path = Path(raw)
    resolved = (path if path.is_absolute() else run_root / path).resolve()
    try:
        resolved.relative_to(run_root)
    except ValueError as exc:
        raise G005QualityGateError(
            f"{description} must be inside selected run: {resolved}"
        ) from exc
    if not resolved.is_file():
        raise G005QualityGateError(f"{description} missing: {resolved}")
    return resolved


def _rel(run_dir: Path, path: Path) -> str:
    return path.resolve().relative_to(run_dir.resolve()).as_posix()


def _resolve_inside_root(root: Path, raw: Path | str, description: str) -> Path:
    root_resolved = root.resolve()
    path = Path(raw)
    resolved = (path if path.is_absolute() else root_resolved / path).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise G005QualityGateError(f"{description} escapes artifact root: {resolved}") from exc
    if not resolved.is_file():
        raise G005QualityGateError(f"{description} missing: {resolved}")
    return resolved


def _resolve_acceptance_artifact_root(run_dir: Path, root: Path | str | None) -> Path:
    if root is None:
        root_path = run_dir / "reports" / "acceptance-artifacts"
    else:
        root_path = Path(root)
        if not root_path.is_absolute():
            root_path = run_dir / root_path
    resolved = root_path.resolve()
    try:
        resolved.relative_to(run_dir.resolve())
    except ValueError as exc:
        raise G005QualityGateError(
            f"acceptance artifact root must be inside selected run: {resolved}"
        ) from exc
    if not resolved.is_dir():
        raise G005QualityGateError(f"acceptance artifact root missing: {resolved}")
    return resolved


def _load_manifest(run_dir: Path) -> dict[str, Any]:
    manifest = run_dir / "manifest.json"
    if not manifest.is_file():
        raise G005QualityGateError(f"Run manifest missing: {manifest}")
    return read_json_object(manifest)


def _content_meta_roots(run_dir: Path, manifest: dict[str, Any]) -> tuple[Path, Path]:
    def resolve_root(raw: Any, fallback: Path, label: str) -> Path:
        path = Path(raw) if isinstance(raw, str) and raw else fallback
        resolved = (path if path.is_absolute() else run_dir / path).resolve()
        try:
            resolved.relative_to(run_dir.resolve())
        except ValueError as exc:
            raise G005QualityGateError(f"{label} escapes selected run: {resolved}") from exc
        if not resolved.is_dir():
            raise G005QualityGateError(f"{label} missing: {resolved}")
        return resolved

    canonical = run_dir / "repowiki" / "zh"
    return (
        resolve_root(manifest.get("candidate_content_root"), canonical / "content", "content root"),
        resolve_root(manifest.get("candidate_meta_root"), canonical / "meta", "meta root"),
    )


def _strict_result_clean(strict_result: dict[str, Any]) -> bool:
    summary = strict_result.get("summary") if isinstance(strict_result, dict) else None
    gate_summary = strict_result.get("gate_summary") if isinstance(strict_result, dict) else None
    return (
        isinstance(strict_result, dict)
        and strict_result.get("grade") == "PASS"
        and strict_result.get("exit_code") in (0, None)
        and (not isinstance(summary, dict) or summary.get("hard_gate_failures") in (0, None))
        and (
            not isinstance(gate_summary, dict) or gate_summary.get("hard_gate_blocking") is not True
        )
        and not strict_result.get("hard_gate_codes")
    )


def _checks_by_name(strict_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks = strict_result.get("checks")
    if not isinstance(checks, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for check in checks:
        if isinstance(check, dict) and isinstance(check.get("name"), str):
            result[check["name"]] = check
    return result


def validate_strict_result_for_gate(
    strict_result: dict[str, Any], gate_name: str
) -> dict[str, Any]:
    if not _strict_result_clean(strict_result):
        raise G005QualityGateError("Authoritative qoder-like strict verification is not clean")
    expected_names = STRICT_CHECK_GROUPS.get(gate_name)
    if not expected_names:
        return {"status": "PASS"}
    checks = _checks_by_name(strict_result)
    selected = [checks[name] for name in sorted(expected_names) if name in checks]
    if not selected:
        raise G005QualityGateError(f"Strict verifier did not emit required checks for {gate_name}")
    failing = [check for check in selected if check.get("status") not in {"PASS", "SKIP"}]
    if failing:
        raise G005QualityGateError(f"Strict verifier check failed for {gate_name}")
    return {"status": "PASS", "checks": selected}


def validate_strict_report_artifact(data: dict[str, Any]) -> dict[str, Any]:
    if not _strict_result_clean(data):
        raise G005QualityGateError("Persisted strict verify report is not clean")
    return {"status": "PASS"}


def _require_non_empty_string(data: dict[str, Any], key: str, description: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise G005QualityGateError(f"Qoder comparison missing {description}")
    return value


def validate_qoder_comparison(data: dict[str, Any]) -> dict[str, Any]:
    """Validate authoritative comparator output, not self-attested status flags.

    The accepted schema is the JSON emitted by ``repo-wiki compare``: top-level
    READY must be backed by baseline immutability, readiness thresholds, metrics,
    path/parity evidence, embedded strict verify, manual-review evidence, and
    replacement-readiness-v2 GO.  Minimal ``{"status":"READY"}``-style JSON is
    intentionally rejected.
    """
    status = str(data.get("status") or "").upper()
    if status != "READY":
        raise G005QualityGateError("Qoder comparison is not READY")
    _require_non_empty_string(data, "target", "target provenance")
    _require_non_empty_string(data, "baseline", "baseline provenance")
    if data.get("baseline_read_only_verified") is not True:
        raise G005QualityGateError("Qoder comparison baseline read-only verification missing")

    path_comparison = data.get("path_comparison")
    if not isinstance(path_comparison, dict) or not path_comparison:
        raise G005QualityGateError("Qoder comparison missing path_comparison evidence")
    parity_summary = data.get("parity_summary")
    if not isinstance(parity_summary, dict):
        raise G005QualityGateError("Qoder comparison missing parity_summary evidence")
    if data.get("parity_blocked") is not False:
        raise G005QualityGateError("Qoder comparison parity is blocked")

    metrics = data.get("metrics")
    if not isinstance(metrics, dict):
        raise G005QualityGateError("Qoder comparison missing metrics evidence")
    missing_metrics = sorted(QODER_REQUIRED_METRICS.difference(metrics))
    if missing_metrics:
        raise G005QualityGateError(
            "Qoder comparison missing required metrics: " + ", ".join(missing_metrics)
        )

    gates = data.get("readiness_gates")
    if not isinstance(gates, dict):
        raise G005QualityGateError("Qoder comparison missing readiness_gates")
    if str(gates.get("status") or "").upper() != "PASS":
        raise G005QualityGateError("Qoder comparison readiness gates are not PASS")
    failures = gates.get("failures")
    if not isinstance(failures, list) or failures:
        raise G005QualityGateError("Qoder comparison readiness gates have failures")
    thresholds = gates.get("thresholds")
    if not isinstance(thresholds, dict):
        raise G005QualityGateError("Qoder comparison missing readiness gate thresholds")
    missing_thresholds = sorted(QODER_REQUIRED_READINESS_THRESHOLDS.difference(thresholds))
    if missing_thresholds:
        raise G005QualityGateError(
            "Qoder comparison missing required readiness thresholds: "
            + ", ".join(missing_thresholds)
        )
    if thresholds.get("baseline_read_only_verified") is not True:
        raise G005QualityGateError("Qoder comparison baseline immutability threshold missing")

    strict = data.get("strict_verify")
    if not isinstance(strict, dict):
        raise G005QualityGateError("Qoder comparison missing embedded strict verification")
    if not _strict_result_clean(strict):
        raise G005QualityGateError("Qoder comparison embedded strict verification is not clean")

    manual_review = data.get("manual_review")
    if not isinstance(manual_review, dict):
        raise G005QualityGateError("Qoder comparison missing manual review evidence")
    manual_summary = manual_review.get("summary")
    if (
        not isinstance(manual_summary, dict)
        or str(manual_summary.get("status") or "").upper() != "PASS"
    ):
        raise G005QualityGateError("Qoder comparison manual review is not PASS")

    replacement = data.get("replacement_readiness")
    if not isinstance(replacement, dict):
        raise G005QualityGateError("Qoder comparison missing replacement_readiness")
    readiness_state = str(replacement.get("readiness_state") or "").upper()
    if readiness_state != "READY" or replacement.get("replacement_go") is not True:
        raise G005QualityGateError("Qoder comparison replacement readiness is not READY")
    checks = replacement.get("checks")
    if not isinstance(checks, dict) or not all(
        checks.get(name) is True
        for name in ("strict_verify_pass", "qoder_comparison_ready", "manual_review_pass")
    ):
        raise G005QualityGateError("Qoder comparison replacement readiness checks are incomplete")
    reasons = replacement.get("readiness_reasons")
    if not isinstance(reasons, list) or reasons:
        raise G005QualityGateError("Qoder comparison replacement readiness has blocking reasons")
    top_reasons = data.get("readiness_reasons")
    if not isinstance(top_reasons, list) or top_reasons:
        raise G005QualityGateError("Qoder comparison has blocking readiness reasons")

    return {
        "status": "READY",
        "readiness_state": "READY",
        "baseline_read_only_verified": True,
        "replacement_go": True,
        "metric_count": len(metrics),
    }


def _resolve_qoder_compare_paths(run_dir: Path, data: dict[str, Any]) -> tuple[Path, Path]:
    target_raw = _require_non_empty_string(data, "target", "target provenance")
    baseline_raw = _require_non_empty_string(data, "baseline", "baseline provenance")
    run_root = run_dir.resolve()
    target = Path(target_raw)
    target = (target if target.is_absolute() else run_root / target).resolve()
    try:
        target.relative_to(run_root)
    except ValueError as exc:
        raise G005QualityGateError(
            f"Qoder comparison target must be inside selected run: {target}"
        ) from exc
    if not target.is_dir():
        raise G005QualityGateError(f"Qoder comparison target missing: {target}")

    baseline = Path(baseline_raw)
    baseline = (baseline if baseline.is_absolute() else run_root / baseline).resolve()
    if not baseline.is_dir():
        raise G005QualityGateError(f"Qoder comparison baseline missing: {baseline}")
    return target, baseline


def _recompute_qoder_comparison_report(
    target: Path, baseline: Path, output_dir: Path
) -> dict[str, Any]:
    from repo_wiki.cli import (
        _broken_links,
        _compare_readiness_failures,
        _compute_chinese_directory_depth,
        _compute_file_line_citation_coverage,
        _compute_llm_generation_coverage,
        _compute_stale_git,
        _count_markdown_pages,
        _load_manual_review_result,
        _metric_score,
    )
    from repo_wiki.orchestration.readiness_schema import evaluate_replacement_readiness_v2
    from repo_wiki.verifier.qoder_baseline_registry import (
        baseline_unchanged,
        register_single_qoder_baseline,
    )
    from repo_wiki.verifier.qoder_comparator_paths import create_repaired_comparator
    from repo_wiki.verifier.qoder_parity_metrics import create_parity_report
    from repo_wiki.verifier.qoder_strict_verifier import verify_qoder_like

    try:
        baseline_entry = register_single_qoder_baseline(target_root=target, baseline_root=baseline)
    except ValueError as exc:
        raise G005QualityGateError(f"Qoder baseline registry validation failed: {exc}") from exc
    baseline = baseline_entry.root

    path_result = create_repaired_comparator(target, baseline).compare()
    parity_dict = create_parity_report(target, baseline_root=baseline).to_dict()
    metrics_by_name = {m["metric_name"]: m for m in parity_dict.get("metrics", [])}
    strict_result = verify_qoder_like(target, ci=True, strict=True)
    pages_target = _count_markdown_pages(target)
    pages_baseline = _count_markdown_pages(baseline)

    report_json: dict[str, Any] = {
        "target": str(target),
        "baseline": str(baseline),
        "baseline_registry": {
            "source": baseline_entry.source,
            "root": str(baseline_entry.root),
            "fingerprint": baseline_entry.fingerprint,
            "file_count": baseline_entry.file_count,
            "immutable": baseline_entry.immutable,
        },
        "status": "READY",
        "strict_verify": strict_result,
        "path_comparison": path_result,
        "metrics": {
            "page_count": {
                "target": pages_target,
                "baseline": pages_baseline,
                "delta": pages_target - pages_baseline,
                "ratio_vs_baseline": round((pages_target / pages_baseline), 4)
                if pages_baseline
                else None,
            },
            "chinese_directory_depth": _compute_chinese_directory_depth(target, baseline),
            "toc_coverage": _metric_score(metrics_by_name.get("toc_presence")),
            "citation_coverage": _metric_score(metrics_by_name.get("citation_coverage")),
            "file_line_reference_coverage": _compute_file_line_citation_coverage(target),
            "mermaid_coverage": _metric_score(metrics_by_name.get("mermaid_presence")),
            "prose_list_ratio": _metric_score(metrics_by_name.get("prose_list_ratio")),
            "api_aggregation_quality": _metric_score(metrics_by_name.get("api_aggregation")),
            "data_model_aggregation_quality": _metric_score(
                metrics_by_name.get("data_model_aggregation")
            ),
            "broken_links": _broken_links(metrics_by_name.get("file_reference_integrity")),
            "stale_git_commit": _compute_stale_git(target, baseline),
            "llm_generation_coverage": _compute_llm_generation_coverage(target),
        },
        "parity_summary": parity_dict.get("summary", {}),
        "parity_blocked": parity_dict.get("blocked", False),
    }
    baseline_untouched = baseline_unchanged(baseline_entry)
    report_json["baseline_read_only_verified"] = baseline_untouched
    readiness_failures = _compare_readiness_failures(report_json)
    manual_review_result = _load_manual_review_result(target=target, output_dir=output_dir)
    comparison_status = "READY"
    if parity_dict.get("blocked") or readiness_failures:
        comparison_status = "NOT_READY"
    report_json["readiness_gates"] = {
        "status": "PASS" if comparison_status == "READY" else "FAIL",
        "failures": readiness_failures,
        "thresholds": {
            "page_count_ratio_vs_baseline": 0.80,
            "chinese_directory_depth_ratio_vs_baseline": 0.70,
            "llm_generation_coverage": 0.80,
            "baseline_read_only_verified": True,
        },
    }
    report_json["manual_review"] = manual_review_result
    replacement_readiness = evaluate_replacement_readiness_v2(
        strict_verify=strict_result,
        comparison_result={
            "status": comparison_status,
            "readiness_gates": report_json["readiness_gates"],
        },
        manual_review_result=manual_review_result,
    )
    report_json["replacement_readiness"] = replacement_readiness
    report_json["status"] = replacement_readiness["readiness_state"]
    report_json["readiness_reasons"] = replacement_readiness["readiness_reasons"]
    return report_json


def _assert_compare_report_matches_recomputed(
    submitted: dict[str, Any], recomputed: dict[str, Any]
) -> None:
    if submitted != recomputed:
        submitted_hash = hashlib.sha256(stable_json_bytes(submitted)).hexdigest()
        recomputed_hash = hashlib.sha256(stable_json_bytes(recomputed)).hexdigest()
        raise G005QualityGateError(
            "Qoder comparison report does not match recomputed comparator output "
            f"(submitted={submitted_hash} recomputed={recomputed_hash})"
        )


def validate_qoder_comparison_against_filesystem(
    run_dir: Path, data: dict[str, Any], artifact_path: Path
) -> dict[str, Any]:
    target, baseline = _resolve_qoder_compare_paths(run_dir, data)
    recomputed = _recompute_qoder_comparison_report(target, baseline, artifact_path.parent)
    _assert_compare_report_matches_recomputed(data, recomputed)
    registry = data.get("baseline_registry")
    if not isinstance(registry, dict):
        raise G005QualityGateError("Qoder comparison missing canonical baseline registry evidence")
    if (
        registry.get("source") != "canonical_qoder_baseline"
        or registry.get("immutable") is not True
    ):
        raise G005QualityGateError(
            "Qoder comparison baseline registry is not canonical immutable Qoder"
        )
    if not isinstance(registry.get("fingerprint"), str) or not registry["fingerprint"]:
        raise G005QualityGateError("Qoder comparison missing baseline registry fingerprint")
    return validate_qoder_comparison(data)


def validate_blind_review(data: dict[str, Any]) -> dict[str, Any]:
    from repo_wiki.verifier.blind_review_matrix import (
        evaluate_blind_review_matrix,
        load_blind_review_matrix,
    )

    evaluation = evaluate_blind_review_matrix(load_blind_review_matrix(data)).to_dict()
    if evaluation.get("status") != "PASS":
        raise G005QualityGateError("blind_review_v3 is not PASS")
    return evaluation


def _registry_entries(data: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("entries", "fixtures", "registry"):
        value = data.get(key)
        if isinstance(value, list) and all(isinstance(item, dict) for item in value):
            return value
    if all(k in data for k in ("fixture_id", "repo_class", "fixture_hash")):
        return [data]
    raise G005QualityGateError("Acceptance fixture registry missing entries")


def validate_acceptance_registry(
    data: dict[str, Any], *, artifact_root: Path | None = None
) -> dict[str, Any]:
    from repo_wiki.verifier.acceptance_fixture_registry import validate_acceptance_fixture_registry

    try:
        report = validate_acceptance_fixture_registry(
            _registry_entries(data),
            artifact_root=artifact_root,
            validate_filesystem=artifact_root is not None,
        ).to_dict()
    except Exception as exc:
        raise G005QualityGateError(f"acceptance_fixture_registry is not valid: {exc}") from exc
    return {"status": "PASS", **report}


def _acceptance_artifact_refs(
    run_dir: Path, registry_data: dict[str, Any], artifact_root: Path
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[str] = set()
    root = artifact_root.resolve()
    for entry in _registry_entries(registry_data):
        raw_path = entry.get("baseline_artifact_path")
        fixture_id = entry.get("fixture_id")
        if not isinstance(raw_path, str) or not raw_path:
            raise G005QualityGateError("Acceptance registry entry missing baseline_artifact_path")
        if raw_path in seen:
            raise G005QualityGateError(f"Duplicate acceptance baseline artifact path: {raw_path}")
        seen.add(raw_path)
        artifact = _resolve_inside_root(root, raw_path, "acceptance baseline artifact")
        refs.append(
            {
                "fixture_id": str(fixture_id or ""),
                "path": artifact.relative_to(root).as_posix(),
                "run_path": _rel(run_dir, artifact),
                "sha256": sha256_file(artifact),
            }
        )
    return refs


def _validate_acceptance_artifact_refs(
    run_dir: Path,
    registry_data: dict[str, Any],
    artifact_root: Path,
    refs: Any,
) -> None:
    if not isinstance(refs, list):
        raise G005QualityGateError("G005 quality-gate report missing acceptance_artifacts")
    expected = {
        (ref["fixture_id"], ref["path"]): ref["sha256"]
        for ref in _acceptance_artifact_refs(run_dir, registry_data, artifact_root)
    }
    actual: dict[tuple[str, str], str] = {}
    for ref in refs:
        if not isinstance(ref, dict):
            raise G005QualityGateError("G005 acceptance artifact reference invalid")
        fixture_id = ref.get("fixture_id")
        rel_path = ref.get("path")
        expected_sha = ref.get("sha256")
        if (
            not isinstance(fixture_id, str)
            or not fixture_id
            or not isinstance(rel_path, str)
            or not rel_path
            or not isinstance(expected_sha, str)
            or not expected_sha
        ):
            raise G005QualityGateError("G005 acceptance artifact reference invalid")
        artifact = _resolve_inside_root(artifact_root, rel_path, "G005 acceptance artifact")
        if sha256_file(artifact) != expected_sha:
            raise G005QualityGateError(f"G005 acceptance artifact hash mismatch: {rel_path}")
        actual[(fixture_id, rel_path)] = expected_sha
    if actual != expected:
        raise G005QualityGateError(
            "G005 acceptance_fixture_registry artifact references do not match registry"
        )


def validate_hard_gate_evidence_artifact(
    data: dict[str, Any], *, strict_result: dict[str, Any], gate_name: str
) -> dict[str, Any]:
    """Load a concrete hard-gate artifact and bind it to the public strict validator.

    Citation, false-fact, quality, and conflict checks are emitted by
    qoder_strict_verifier.  The external evidence JSON is still required to exist
    and be parseable so the production report is a concrete evidence index, not a
    status-only bundle.
    """
    validation = validate_strict_result_for_gate(strict_result, gate_name)
    return {
        **validation,
        "evidence_schema_version": data.get("schema_version"),
        "evidence_keys": sorted(str(key) for key in data.keys()),
    }


def _artifact_ref(run_dir: Path, path: Path, *, validator: str) -> dict[str, Any]:
    return {
        "path": _rel(run_dir, path),
        "sha256": sha256_file(path),
        "validator": validator,
    }


def rerun_strict_validator(run_dir: Path) -> dict[str, Any]:
    from repo_wiki.verifier.qoder_strict_verifier import verify_qoder_like

    return verify_qoder_like(run_dir, ci=True, strict=True)


def _resolve_review_allowed_signers(run_dir: Path, raw: Path | str | None) -> Path:
    candidate = raw or os.environ.get("REPO_WIKI_G005_REVIEW_ALLOWED_SIGNERS")
    if candidate is None or not str(candidate).strip():
        raise G005QualityGateError(
            "review allowed-signers path required outside the run "
            "(--review-allowed-signers or REPO_WIKI_G005_REVIEW_ALLOWED_SIGNERS)"
        )

    run_root = run_dir.resolve()
    path = Path(candidate).expanduser().resolve()
    try:
        path.relative_to(run_root)
    except ValueError:
        pass
    else:
        raise G005QualityGateError(
            f"review allowed-signers file must be outside selected run: {path}"
        )
    if not path.is_file():
        raise G005QualityGateError(f"review allowed-signers file missing: {path}")
    return path


def validate_blind_review_attestation(
    *,
    run_dir: Path,
    review_payload: dict[str, Any],
    qoder_comparison_payload: dict[str, Any],
    attestation_payload: dict[str, Any],
    allowed_signers_path: Path,
) -> dict[str, Any]:
    from repo_wiki.verifier.review_attestation import (
        ReviewAttestationError,
        verify_review_attestation,
    )

    try:
        return verify_review_attestation(
            run_dir=run_dir,
            review_payload=review_payload,
            qoder_comparison_payload=qoder_comparison_payload,
            attestation_payload=attestation_payload,
            allowed_signers_path=allowed_signers_path,
        )
    except ReviewAttestationError as exc:
        raise G005QualityGateError(str(exc)) from exc


def compile_g005_quality_gate(inputs: G005Inputs) -> dict[str, Any]:
    run_dir = inputs.run_dir.resolve()
    manifest = _load_manifest(run_dir)
    run_id = str(manifest.get("run_id") or run_dir.name)
    content_root, meta_root = _content_meta_roots(run_dir, manifest)

    strict_path = _resolve_inside_run(
        run_dir,
        inputs.strict_verify or Path("reports/strict-verify-output.json"),
        "strict verify report",
    )
    artifact_paths = {
        "strict_verify": strict_path,
        "qoder_comparison": _resolve_inside_run(
            run_dir, inputs.qoder_comparison, "Qoder comparison report"
        ),
        "blind_review_v3": _resolve_inside_run(
            run_dir, inputs.blind_review_v3, "blind review v3 artifact"
        ),
        "blind_review_attestation": _resolve_inside_run(
            run_dir,
            inputs.blind_review_attestation or Path("reports/blind-review-v3.attestation.json"),
            "blind review attestation artifact",
        ),
        "acceptance_fixture_registry": _resolve_inside_run(
            run_dir, inputs.acceptance_fixture_registry, "acceptance fixture registry artifact"
        ),
        "citation_hard_gate_evidence": _resolve_inside_run(
            run_dir, inputs.citation_hard_gate_evidence or strict_path, "citation evidence artifact"
        ),
        "critical_false_fact_evidence": _resolve_inside_run(
            run_dir,
            inputs.critical_false_fact_evidence or strict_path,
            "critical false fact evidence artifact",
        ),
        "quality_hard_gate_evidence": _resolve_inside_run(
            run_dir, inputs.quality_hard_gate_evidence or strict_path, "quality evidence artifact"
        ),
        "conflict_hard_gate_evidence": _resolve_inside_run(
            run_dir, inputs.conflict_hard_gate_evidence or strict_path, "conflict evidence artifact"
        ),
    }

    strict_result = rerun_strict_validator(run_dir)
    if not _strict_result_clean(strict_result):
        raise G005QualityGateError("Authoritative qoder-like strict verification is not clean")

    loaded_artifacts = {name: read_json_object(path) for name, path in artifact_paths.items()}
    allowed_signers_path = _resolve_review_allowed_signers(run_dir, inputs.review_allowed_signers)
    acceptance_artifact_root = _resolve_acceptance_artifact_root(
        run_dir, inputs.acceptance_artifact_root
    )
    strict_artifact_validation = validate_strict_report_artifact(loaded_artifacts["strict_verify"])
    gates = {
        "strict_verify": strict_artifact_validation,
        "qoder_comparison": validate_qoder_comparison_against_filesystem(
            run_dir, loaded_artifacts["qoder_comparison"], artifact_paths["qoder_comparison"]
        ),
        "blind_review_v3": validate_blind_review(loaded_artifacts["blind_review_v3"]),
        "blind_review_attestation": validate_blind_review_attestation(
            run_dir=run_dir,
            review_payload=loaded_artifacts["blind_review_v3"],
            qoder_comparison_payload=loaded_artifacts["qoder_comparison"],
            attestation_payload=loaded_artifacts["blind_review_attestation"],
            allowed_signers_path=allowed_signers_path,
        ),
        "acceptance_fixture_registry": validate_acceptance_registry(
            loaded_artifacts["acceptance_fixture_registry"],
            artifact_root=acceptance_artifact_root,
        ),
    }
    for gate_name in STRICT_CHECK_GROUPS:
        gates[gate_name] = validate_hard_gate_evidence_artifact(
            loaded_artifacts[gate_name],
            strict_result=strict_result,
            gate_name=gate_name,
        )

    artifact_references = {
        name: _artifact_ref(run_dir, path, validator=_validator_name(name))
        for name, path in artifact_paths.items()
    }
    content_sha256 = hash_tree(content_root)
    meta_sha256 = hash_tree(meta_root)
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "content_sha256": content_sha256,
        "meta_sha256": meta_sha256,
        "run_fingerprints": {
            "manifest_sha256": sha256_file(run_dir / "manifest.json"),
            "run_sha256": hash_run_tree(run_dir),
            "content_sha256": content_sha256,
            "meta_sha256": meta_sha256,
            "strict_report_sha256": sha256_file(strict_path),
            "strict_result_sha256": hashlib.sha256(stable_json_bytes(strict_result)).hexdigest(),
        },
        "artifact_references": artifact_references,
        "review_allowed_signers_sha256": sha256_file(allowed_signers_path),
        "acceptance_artifact_root": acceptance_artifact_root.relative_to(run_dir).as_posix(),
        "acceptance_artifacts": _acceptance_artifact_refs(
            run_dir, loaded_artifacts["acceptance_fixture_registry"], acceptance_artifact_root
        ),
        "gates": gates,
        "status": "PASS",
    }
    return bundle


def _validator_name(name: str) -> str:
    if name == "qoder_comparison":
        return "repo_wiki.cli.compare/readiness_v2"
    if name == "blind_review_v3":
        return "repo_wiki.verifier.blind_review_matrix.evaluate_blind_review_matrix"
    if name == "blind_review_attestation":
        return "repo_wiki.verifier.review_attestation.verify_review_attestation"
    if name == "acceptance_fixture_registry":
        return "repo_wiki.verifier.acceptance_fixture_registry.validate_acceptance_fixture_registry"
    return "repo_wiki.verifier.qoder_strict_verifier.verify_qoder_like"


def validate_g005_bundle(
    run_dir: Path, bundle: dict[str, Any], *, review_allowed_signers: Path | None = None
) -> dict[str, Any]:
    """Re-load/hash/rerun every referenced G005 validator for release-publish."""
    if bundle.get("schema_version") != SCHEMA_VERSION:
        raise G005QualityGateError("G005 quality-gate report has unsupported schema_version")
    manifest = _load_manifest(run_dir)
    expected_run_id = str(manifest.get("run_id") or run_dir.name)
    if str(bundle.get("run_id") or "") != expected_run_id:
        raise G005QualityGateError("G005 quality-gate report run_id mismatch")
    content_root, meta_root = _content_meta_roots(run_dir, manifest)
    if bundle.get("content_sha256") != hash_tree(content_root):
        raise G005QualityGateError("G005 quality-gate report content fingerprint mismatch")
    if bundle.get("meta_sha256") != hash_tree(meta_root):
        raise G005QualityGateError("G005 quality-gate report meta fingerprint mismatch")
    fingerprints = bundle.get("run_fingerprints")
    if not isinstance(fingerprints, dict):
        raise G005QualityGateError("G005 quality-gate report missing run_fingerprints")
    expected_fingerprints = {
        "manifest_sha256": sha256_file(run_dir / "manifest.json"),
        "content_sha256": hash_tree(content_root),
        "meta_sha256": hash_tree(meta_root),
    }
    for name, expected in expected_fingerprints.items():
        if fingerprints.get(name) != expected:
            raise G005QualityGateError(f"G005 quality-gate report {name} mismatch")

    refs = bundle.get("artifact_references")
    if not isinstance(refs, dict):
        raise G005QualityGateError("G005 quality-gate report missing artifact_references")
    missing = [name for name in REQUIRED_ARTIFACTS if name not in refs]
    if missing:
        if len(missing) == 1:
            raise G005QualityGateError(f"G005 quality-gate report missing {missing[0]}")
        raise G005QualityGateError(
            "G005 quality-gate report missing required artifacts: " + ", ".join(missing)
        )

    resolved: dict[str, Path] = {}
    for name in REQUIRED_ARTIFACTS:
        ref = refs.get(name)
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
            raise G005QualityGateError(f"G005 artifact reference invalid: {name}")
        path = _resolve_inside_run(run_dir, ref["path"], f"G005 artifact {name}")
        expected_sha = ref.get("sha256")
        if not isinstance(expected_sha, str) or sha256_file(path) != expected_sha:
            raise G005QualityGateError(f"G005 artifact hash mismatch: {name}")
        resolved[name] = path

    strict_result = rerun_strict_validator(run_dir)
    if not _strict_result_clean(strict_result):
        raise G005QualityGateError("Authoritative qoder-like strict verification is not clean")
    strict_result_sha = hashlib.sha256(stable_json_bytes(strict_result)).hexdigest()
    if fingerprints.get("strict_result_sha256") != strict_result_sha:
        raise G005QualityGateError("G005 quality-gate report strict_result_sha256 mismatch")
    strict_report_sha = sha256_file(resolved["strict_verify"])
    if fingerprints.get("strict_report_sha256") != strict_report_sha:
        raise G005QualityGateError("G005 quality-gate report strict_report_sha256 mismatch")

    loaded_artifacts = {name: read_json_object(path) for name, path in resolved.items()}
    allowed_signers_path = _resolve_review_allowed_signers(run_dir, review_allowed_signers)
    declared_allowed_sha = bundle.get("review_allowed_signers_sha256")
    if declared_allowed_sha != sha256_file(allowed_signers_path):
        raise G005QualityGateError("G005 review allowed-signers fingerprint mismatch")
    raw_acceptance_root = bundle.get("acceptance_artifact_root")
    if not isinstance(raw_acceptance_root, str) or not raw_acceptance_root.strip():
        raise G005QualityGateError("G005 quality-gate report missing acceptance_artifact_root")
    acceptance_artifact_root = _resolve_acceptance_artifact_root(run_dir, raw_acceptance_root)
    _validate_acceptance_artifact_refs(
        run_dir,
        loaded_artifacts["acceptance_fixture_registry"],
        acceptance_artifact_root,
        bundle.get("acceptance_artifacts"),
    )
    validated = {
        "strict_verify": validate_strict_report_artifact(loaded_artifacts["strict_verify"]),
        "qoder_comparison": validate_qoder_comparison_against_filesystem(
            run_dir, loaded_artifacts["qoder_comparison"], resolved["qoder_comparison"]
        ),
        "blind_review_v3": validate_blind_review(loaded_artifacts["blind_review_v3"]),
        "blind_review_attestation": validate_blind_review_attestation(
            run_dir=run_dir,
            review_payload=loaded_artifacts["blind_review_v3"],
            qoder_comparison_payload=loaded_artifacts["qoder_comparison"],
            attestation_payload=loaded_artifacts["blind_review_attestation"],
            allowed_signers_path=allowed_signers_path,
        ),
        "acceptance_fixture_registry": validate_acceptance_registry(
            loaded_artifacts["acceptance_fixture_registry"],
            artifact_root=acceptance_artifact_root,
        ),
    }
    for gate_name in STRICT_CHECK_GROUPS:
        validated[gate_name] = validate_hard_gate_evidence_artifact(
            loaded_artifacts[gate_name],
            strict_result=strict_result,
            gate_name=gate_name,
        )
    if fingerprints.get("run_sha256") != hash_run_tree(run_dir):
        raise G005QualityGateError("G005 quality-gate report run_sha256 mismatch")
    return validated
