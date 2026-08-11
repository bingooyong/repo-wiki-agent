"""CLI tests for qoder-like release publishing contract."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

import repo_wiki.orchestration.g005_quality_gate as g005_quality_gate
import repo_wiki.orchestration.release_publisher as release_publisher
from repo_wiki.cli import _compare_readiness_failures, _load_manual_review_result, app
from repo_wiki.orchestration.g005_quality_gate import hash_run_tree, stable_json_bytes
from repo_wiki.orchestration.release_publisher import (
    ReleasePublishError,
    _hash_tree,
    publish_ready_run,
    resolve_publish_run_dir,
)

runner = CliRunner()


@pytest.fixture(autouse=True)
def _release_publish_strict_rerun_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    def clean(_run_dir: Path) -> dict:
        return _strict_pass_report()

    monkeypatch.setattr(release_publisher, "_rerun_authoritative_strict_verification", clean)
    monkeypatch.setattr(
        g005_quality_gate, "rerun_strict_validator", lambda _run_dir: clean(_run_dir)
    )
    monkeypatch.setattr(
        g005_quality_gate,
        "validate_qoder_comparison_against_filesystem",
        lambda _run_dir, data, _artifact_path: g005_quality_gate.validate_qoder_comparison(data),
    )
    monkeypatch.setattr(
        g005_quality_gate,
        "validate_blind_review_attestation",
        lambda **_kwargs: {"status": "PASS", "test_stub": True},
    )


def _valid_navigation_meta() -> dict:
    return {
        "schema_version": "repo_agent.navigation/1.0",
        "generated_at": "2024-01-01T00:00:00Z",
        "navigation_tree": [],
    }


def _valid_page_registry_meta() -> dict:
    return {
        "schema_version": "repo_agent.page_registry/1.0",
        "generated_at": "2024-01-01T00:00:00Z",
        "pages": [
            {
                "page_id": "overview",
                "relative_path": "00-overview.md",
                "category": "root",
                "page_type": "overview",
            }
        ],
    }


def _valid_evidence_index_meta() -> dict:
    return {
        "schema_version": "repo_agent.evidence_index/1.0",
        "generated_at": "2024-01-01T00:00:00Z",
        "spans": [],
    }


def _sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_text(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode()).hexdigest()


def _stable_hash(value: dict) -> str:
    import hashlib

    return hashlib.sha256(stable_json_bytes(value)).hexdigest()


def _strict_pass_report() -> dict:
    return {
        "grade": "PASS",
        "exit_code": 0,
        "summary": {"hard_gate_failures": 0, "soft_gate_failures": 0},
        "gate_summary": {"hard_gate_blocking": False},
        "hard_gate_codes": [],
        "checks": [
            {"name": "qoder-citation-targets", "status": "PASS"},
            {"name": "qoder-critical-false-facts", "status": "PASS"},
            {"name": "qoder-quality-artifacts", "status": "PASS"},
            {"name": "qoder-unresolved-fact-conflicts", "status": "PASS"},
        ],
    }


def _blind_review_payload() -> dict:
    classes = [
        "multi_runtime_monorepo",
        "java_kotlin_service",
        "typescript_frontend_node",
        "python_service",
        "go_rust_service",
    ]
    candidates = [
        {
            "candidate_id": "a1",
            "system": "repo-agent",
            "artifact_hash": _hash_text("a1"),
            "provenance_hash": _hash_text("pa1"),
        },
        {
            "candidate_id": "b1",
            "system": "qoder",
            "artifact_hash": _hash_text("b1"),
            "provenance_hash": _hash_text("pb1"),
        },
    ]
    records = []
    for cls in classes:
        records.append(
            {
                "repo_class": cls,
                "candidate_id": "a1",
                "scores": {
                    "accuracy": 5,
                    "coverage": 5,
                    "navigation": 5,
                    "readability": 5,
                    "actionability": 5,
                },
                "critical_false_facts": 0,
            }
        )
        records.append(
            {
                "repo_class": cls,
                "candidate_id": "b1",
                "scores": {
                    "accuracy": 4,
                    "coverage": 4,
                    "navigation": 4,
                    "readability": 4,
                    "actionability": 4,
                },
                "critical_false_facts": 0,
            }
        )
    return {
        "schema_version": "blind-review-matrix-v3",
        "reviewer_identity_hash": _hash_text("reviewer"),
        "candidates": candidates,
        "records": records,
    }


def _full_qoder_comparison_report() -> dict:
    return {
        "target": "/tmp/repo/.repo-agent-eval/run/repowiki/zh",
        "baseline": "/tmp/repo/.qoder/repowiki/zh",
        "status": "READY",
        "strict_verify": _strict_pass_report(),
        "path_comparison": {"status": "PASS", "matched_paths": []},
        "metrics": {
            "page_count": {"target": 1, "baseline": 1, "delta": 0, "ratio_vs_baseline": 1.0},
            "chinese_directory_depth": {"target": 1, "baseline": 1, "ratio_vs_baseline": 1.0},
            "toc_coverage": 1.0,
            "citation_coverage": 1.0,
            "file_line_reference_coverage": 1.0,
            "mermaid_coverage": 1.0,
            "prose_list_ratio": 1.0,
            "api_aggregation_quality": 1.0,
            "data_model_aggregation_quality": 1.0,
            "broken_links": [],
            "stale_git_commit": False,
            "llm_generation_coverage": 1.0,
        },
        "parity_summary": {"overall_score": 1.0},
        "parity_blocked": False,
        "baseline_read_only_verified": True,
        "readiness_gates": {
            "status": "PASS",
            "failures": [],
            "thresholds": {
                "page_count_ratio_vs_baseline": 0.80,
                "chinese_directory_depth_ratio_vs_baseline": 0.70,
                "llm_generation_coverage": 0.80,
                "baseline_read_only_verified": True,
            },
        },
        "manual_review": {"summary": {"status": "PASS"}, "failures": []},
        "replacement_readiness": {
            "schema_version": "readiness-schema-v2",
            "replacement_go": True,
            "readiness_state": "READY",
            "readiness_reasons": [],
            "checks": {
                "strict_verify_pass": True,
                "qoder_comparison_ready": True,
                "manual_review_pass": True,
            },
        },
        "readiness_reasons": [],
    }


def _acceptance_registry_payload() -> dict:
    classes = [
        "multi_runtime_monorepo",
        "java_kotlin_service",
        "typescript_frontend_node",
        "python_service",
        "go_rust_service",
    ]
    return {
        "entries": [
            {
                "fixture_id": f"fx-{i}",
                "repo_class": cls,
                "fixture_hash": _hash_text(f"fixture-{cls}"),
                "revision": "abc123",
                "baseline_artifact_path": f"{cls}/baseline.json",
                "baseline_artifact_hash": _hash_text(f"baseline-{cls}"),
                "generated_at": "2024-01-01T00:00:00Z",
                "qoder_version": "qoder-test",
                "generator_identity": "test",
                "rubric_version": "v1",
            }
            for i, cls in enumerate(classes)
        ]
    }


def _write_g005_production_artifacts(run_dir: Path, run_id: str, content: Path, meta: Path) -> None:
    reports = run_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    strict = reports / "strict-verify-output.json"
    strict.write_text(json.dumps(_strict_pass_report()), encoding="utf-8")
    (reports / "qoder-comparison-report.json").write_text(
        json.dumps(_full_qoder_comparison_report()), encoding="utf-8"
    )
    (reports / "blind-review-v3.json").write_text(
        json.dumps(_blind_review_payload()), encoding="utf-8"
    )
    (reports / "blind-review-v3.attestation.json").write_text(
        json.dumps({"test": "stub"}), encoding="utf-8"
    )
    allowed_signers = run_dir.parent / "allowed-signers"
    allowed_signers.write_text(
        "reviewer@example.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestOnly\n", encoding="utf-8"
    )
    import os

    os.environ["REPO_WIKI_G005_REVIEW_ALLOWED_SIGNERS"] = str(allowed_signers)
    acceptance_root = reports / "acceptance-artifacts"
    for cls in [
        "multi_runtime_monorepo",
        "java_kotlin_service",
        "typescript_frontend_node",
        "python_service",
        "go_rust_service",
    ]:
        artifact = acceptance_root / cls / "baseline.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(f"baseline-{cls}", encoding="utf-8")
    (reports / "acceptance-fixture-registry.json").write_text(
        json.dumps(_acceptance_registry_payload()), encoding="utf-8"
    )
    paths = {
        "strict_verify": strict,
        "qoder_comparison": reports / "qoder-comparison-report.json",
        "blind_review_v3": reports / "blind-review-v3.json",
        "blind_review_attestation": reports / "blind-review-v3.attestation.json",
        "acceptance_fixture_registry": reports / "acceptance-fixture-registry.json",
        "citation_hard_gate_evidence": strict,
        "critical_false_fact_evidence": strict,
        "quality_hard_gate_evidence": strict,
        "conflict_hard_gate_evidence": strict,
    }
    refs = {
        name: {
            "path": path.relative_to(run_dir).as_posix(),
            "sha256": _sha256_file(path),
            "validator": "test",
        }
        for name, path in paths.items()
    }
    registry = json.loads((reports / "acceptance-fixture-registry.json").read_text())
    acceptance_refs = []
    for entry in registry["entries"]:
        artifact = acceptance_root / entry["baseline_artifact_path"]
        acceptance_refs.append(
            {
                "fixture_id": entry["fixture_id"],
                "path": entry["baseline_artifact_path"],
                "run_path": artifact.relative_to(run_dir).as_posix(),
                "sha256": _sha256_file(artifact),
            }
        )
    (reports / "g005-quality-gates.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.g005_quality_gates/1.0",
                "run_id": run_id,
                "content_sha256": _hash_tree(content),
                "meta_sha256": _hash_tree(meta),
                "run_fingerprints": {
                    "manifest_sha256": _sha256_file(run_dir / "manifest.json"),
                    "run_sha256": hash_run_tree(run_dir),
                    "content_sha256": _hash_tree(content),
                    "meta_sha256": _hash_tree(meta),
                    "strict_report_sha256": _sha256_file(strict),
                    "strict_result_sha256": _stable_hash(_strict_pass_report()),
                },
                "artifact_references": refs,
                "review_allowed_signers_sha256": _sha256_file(allowed_signers),
                "acceptance_artifact_root": "reports/acceptance-artifacts",
                "acceptance_artifacts": acceptance_refs,
                "gates": {
                    "qoder_comparison": {"status": "READY", "readiness_state": "READY"},
                    "blind_review_v3": {"grade": "PASS", "status": "PASS"},
                    "acceptance_fixture_registry": {"status": "PASS"},
                    "citation_hard_gate_evidence": {"status": "PASS", "hard_gate_failures": 0},
                    "critical_false_fact_evidence": {
                        "status": "PASS",
                        "critical_false_fact_failures": 0,
                    },
                    "quality_hard_gate_evidence": {"status": "PASS", "hard_gate_failures": 0},
                    "conflict_hard_gate_evidence": {"status": "PASS", "unresolved_count": 0},
                },
                "status": "PASS",
            }
        ),
        encoding="utf-8",
    )


def _create_run(
    eval_root: Path,
    run_dir_name: str,
    *,
    run_id: str,
    readiness_state: str = "READY",
    include_candidate_dirs: bool = True,
    include_strict_pass: bool = True,
    extra_meta: dict[str, dict] | None = None,
) -> Path:
    run_dir = eval_root / run_dir_name
    run_dir.mkdir(parents=True, exist_ok=True)

    candidate_root = run_dir / "repowiki" / "zh"
    candidate_content = candidate_root / "content"
    candidate_meta = candidate_root / "meta"
    if include_candidate_dirs:
        candidate_content.mkdir(parents=True, exist_ok=True)
        candidate_meta.mkdir(parents=True, exist_ok=True)
        (candidate_content / "00-overview.md").write_text("# Overview\n", encoding="utf-8")
        (candidate_meta / "navigation.json").write_text(
            json.dumps(_valid_navigation_meta()), encoding="utf-8"
        )
        (candidate_meta / "page-registry.json").write_text(
            json.dumps(_valid_page_registry_meta()), encoding="utf-8"
        )
        (candidate_meta / "evidence-index.json").write_text(
            json.dumps(_valid_evidence_index_meta()), encoding="utf-8"
        )
        if extra_meta:
            for fname, payload in extra_meta.items():
                (candidate_meta / fname).write_text(json.dumps(payload), encoding="utf-8")

    reports_dir = run_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    if include_strict_pass:
        (reports_dir / "strict-verify-output.json").write_text(
            json.dumps(_strict_pass_report()), encoding="utf-8"
        )

    manifest = {
        "run_id": run_id,
        "readiness_state": readiness_state,
        "target_dirty": False,
        "git_fresh": True,
        "navigation_tree": [
            {"type": "page", "label": "Overview", "path": "content/00-overview.md"}
        ],
        "candidate_repowiki_zh_root": str(candidate_root),
        "candidate_content_root": str(candidate_content),
        "candidate_meta_root": str(candidate_meta),
        "report_paths": {
            "strict_verify": "reports/strict-verify-output.json",
            "g005_quality_gates": "reports/g005-quality-gates.json",
        },
        "files": [
            {"path": "reports/strict-verify-output.json"},
            {"path": "reports/g005-quality-gates.json"},
        ],
        "evidence": [],
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if include_candidate_dirs and include_strict_pass:
        _write_g005_production_artifacts(run_dir, run_id, candidate_content, candidate_meta)
    return run_dir


def _snapshot_published_state(eval_root: Path) -> tuple[dict[str, bytes], bytes]:
    release_root = eval_root / "repowiki" / "zh"
    release_files = {
        str(path.relative_to(release_root)): path.read_bytes()
        for path in sorted(release_root.rglob("*"))
        if path.is_file()
    }
    return release_files, (eval_root / "release-history.json").read_bytes()


def test_release_publish_publishes_ready_run_atomically(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_run(eval_root, "run-ready", run_id="run-200")

    result = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-200"])
    assert result.exit_code == 0
    release_root = eval_root / "repowiki" / "zh"
    assert (release_root / "manifest.json").exists()
    assert (release_root / "meta" / "release.json").exists()
    assert (eval_root / "release-history.json").exists()

    published_manifest = json.loads((release_root / "manifest.json").read_text(encoding="utf-8"))
    assert published_manifest["release_status"] == "READY"
    assert published_manifest["source_run_id"] == "run-200"


def test_release_publish_rejects_not_ready_manifest(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_run(eval_root, "run-review", run_id="run-201", readiness_state="REVIEW_ONLY")
    result = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-201"])
    assert result.exit_code != 0
    assert "not READY" in result.output


def test_release_publish_rejects_run_1777730692266_style_manifest(tmp_path: Path) -> None:
    """Legacy run manifest lacks selected-run repowiki/zh candidate dirs and must be rejected."""
    eval_root = tmp_path / ".repo-agent-eval"
    _create_run(
        eval_root,
        "run-legacy",
        run_id="run-1777730692266",
        include_candidate_dirs=False,
        include_strict_pass=True,
    )
    result = runner.invoke(
        app, ["release-publish", "--output", str(eval_root), "--run", "run-1777730692266"]
    )
    assert result.exit_code != 0
    assert (
        "candidate_content_root missing" in result.output
        or "candidate_meta_root missing" in result.output
    )


def test_release_publish_succeeds_with_valid_meta_sidecars(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    page_registry = {
        "schema_version": "repo_agent.page_registry/1.0",
        "generated_at": "2024-01-01T00:00:00Z",
        "pages": [
            {
                "page_id": "overview",
                "relative_path": "00-overview.md",
                "category": "root",
                "page_type": "overview",
            }
        ],
    }
    _create_run(
        eval_root,
        "run-meta",
        run_id="run-210",
        extra_meta={"page-registry.json": page_registry},
    )
    result = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-210"])
    assert result.exit_code == 0
    meta_nav = eval_root / "repowiki" / "zh" / "meta" / "navigation.json"
    meta_reg = eval_root / "repowiki" / "zh" / "meta" / "page-registry.json"
    assert meta_nav.exists()
    assert meta_reg.exists()
    reg = json.loads(meta_reg.read_text(encoding="utf-8"))
    assert reg["pages"][0]["page_id"] == "overview"


def test_release_publish_invalid_meta_preserves_previous_release(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_run(eval_root, "run-ready", run_id="run-200")
    first = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-200"])
    assert first.exit_code == 0
    published_before = json.loads(
        (eval_root / "repowiki" / "zh" / "manifest.json").read_text(encoding="utf-8")
    )
    assert published_before["source_run_id"] == "run-200"

    bad_run = _create_run(eval_root, "run-bad-meta", run_id="run-400")
    bad_nav = bad_run / "repowiki" / "zh" / "meta" / "navigation.json"
    bad_nav.write_text("{}", encoding="utf-8")

    second = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-400"])
    assert second.exit_code != 0
    assert "Meta validation failed" in second.output or "navigation" in second.output

    published_after = json.loads(
        (eval_root / "repowiki" / "zh" / "manifest.json").read_text(encoding="utf-8")
    )
    assert published_after["source_run_id"] == "run-200"


def test_release_publish_failure_after_backup_move_restores_previous_ready(
    tmp_path: Path,
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_run(eval_root, "run-stable", run_id="run-800")
    first = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-800"])
    assert first.exit_code == 0
    published_before = _snapshot_published_state(eval_root)

    _create_run(eval_root, "run-next", run_id="run-801")
    with pytest.raises(ReleasePublishError, match="after_existing_release_moved_to_backup"):
        publish_ready_run(
            eval_root,
            "run-next",
            _failure_injection="after_existing_release_moved_to_backup",
        )

    assert _snapshot_published_state(eval_root) == published_before
    assert not (eval_root / "repowiki" / "zh.__backup__").exists()


def test_release_publish_history_append_failure_restores_previous_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_run(eval_root, "run-stable", run_id="run-810")
    first = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-810"])
    assert first.exit_code == 0
    published_before = _snapshot_published_state(eval_root)

    def fail_history(_eval_root: Path, _release_entry: dict) -> None:
        raise OSError("simulated history write failure")

    _create_run(eval_root, "run-next-history", run_id="run-811")
    monkeypatch.setattr(release_publisher, "_write_release_history", fail_history)

    with pytest.raises(OSError, match="simulated history write failure"):
        publish_ready_run(eval_root, "run-next-history")

    assert _snapshot_published_state(eval_root) == published_before
    assert not (eval_root / "repowiki" / "zh.__backup__").exists()


@pytest.mark.parametrize(
    ("invalid_history", "error_message"),
    [
        (b"{invalid json}\n", "release history is unreadable or invalid JSON"),
        (b'{"unexpected":"object"}\n', "release history must be a JSON array"),
        (b'["not-an-object"]\n', "release history entries must be JSON objects"),
    ],
)
def test_release_publish_invalid_history_restores_ready_without_truncation(
    tmp_path: Path,
    invalid_history: bytes,
    error_message: str,
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_run(eval_root, "run-stable", run_id="run-820")
    first = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-820"])
    assert first.exit_code == 0

    history_path = eval_root / "release-history.json"
    history_path.write_bytes(invalid_history)
    published_before = _snapshot_published_state(eval_root)

    _create_run(eval_root, "run-next-history", run_id="run-821")
    with pytest.raises(ReleasePublishError, match=error_message):
        publish_ready_run(eval_root, "run-next-history")

    assert _snapshot_published_state(eval_root) == published_before
    assert history_path.read_bytes() == invalid_history
    assert not (eval_root / "repowiki" / "zh.__backup__").exists()


def test_release_publish_rejects_dirty_run(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_run(eval_root, "run-dirty", run_id="run-500")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["target_dirty"] = True
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-500"])
    assert result.exit_code != 0
    assert "target_dirty" in result.output


def test_release_publish_rejects_git_not_fresh(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_run(eval_root, "run-stale-git", run_id="run-501")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["git_fresh"] = False
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-501"])
    assert result.exit_code != 0
    assert "git_fresh=false" in result.output


def test_release_publish_rejects_missing_strict_report(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_run(eval_root, "run-missing-strict", run_id="run-502", include_strict_pass=False)
    result = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-502"])
    assert result.exit_code != 0
    assert "Strict verify PASS report missing" in result.output


def test_release_publish_rejects_failed_strict_report(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_run(eval_root, "run-failed-strict", run_id="run-503")
    (run_dir / "reports" / "strict-verify-output.json").write_text(
        json.dumps({"grade": "FAIL"}), encoding="utf-8"
    )
    result = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-503"])
    assert result.exit_code != 0
    assert "Strict verify grade is not PASS" in result.output


def test_release_publish_accepts_relative_candidate_roots_inside_selected_run(
    tmp_path: Path,
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_run(eval_root, "runs/run-relative", run_id="run-504")
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["candidate_repowiki_zh_root"] = "repowiki/zh"
    manifest["candidate_content_root"] = "repowiki/zh/content"
    manifest["candidate_meta_root"] = "repowiki/zh/meta"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _write_g005_production_artifacts(
        run_dir,
        "run-504",
        run_dir / "repowiki" / "zh" / "content",
        run_dir / "repowiki" / "zh" / "meta",
    )

    result = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-504"])
    assert result.exit_code == 0
    published_manifest = json.loads(
        (eval_root / "repowiki" / "zh" / "manifest.json").read_text(encoding="utf-8")
    )
    assert published_manifest["source_run_id"] == "run-504"


def test_publish_functions_reject_absolute_and_traversal_run_refs(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_run(eval_root, "run-safe", run_id="run-safe")
    outside_run = _create_run(tmp_path, "outside-run", run_id="run-outside")

    for run_ref in (str(outside_run), "../outside-run"):
        with pytest.raises(ReleasePublishError, match="run_ref"):
            resolve_publish_run_dir(eval_root, run_ref)
        with pytest.raises(ReleasePublishError, match="run_ref"):
            publish_ready_run(eval_root, run_ref)

        cli_result = runner.invoke(
            app, ["release-publish", "--output", str(eval_root), "--run", run_ref]
        )
        assert cli_result.exit_code != 0

    assert not (eval_root / "repowiki" / "zh").exists()
    assert not (eval_root / "release-history.json").exists()


def test_release_publish_rejects_selected_run_symlink_escape_for_cli_and_direct(
    tmp_path: Path,
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_run(eval_root, "run-stable", run_id="run-700")
    first = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-700"])
    assert first.exit_code == 0
    published_before = _snapshot_published_state(eval_root)

    outside_run = _create_run(tmp_path, "outside-symlink-run", run_id="run-701")
    run_link = eval_root / "run-link"
    try:
        run_link.symlink_to(outside_run, target_is_directory=True)
    except OSError as exc:  # pragma: no cover - platform capability guard
        pytest.skip(f"directory symlink unavailable: {exc}")

    with pytest.raises(ReleasePublishError, match="escapes eval root"):
        resolve_publish_run_dir(eval_root, run_link.name)
    with pytest.raises(ReleasePublishError, match="escapes eval root"):
        publish_ready_run(eval_root, run_link.name)

    cli_result = runner.invoke(
        app, ["release-publish", "--output", str(eval_root), "--run", "run-701"]
    )
    assert cli_result.exit_code != 0
    assert "escapes eval root" in cli_result.output
    assert _snapshot_published_state(eval_root) == published_before


def test_release_publish_rejects_candidate_repowiki_root_from_other_run_and_preserves_release(
    tmp_path: Path,
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_run(eval_root, "run-ready", run_id="run-600")
    first = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-600"])
    assert first.exit_code == 0

    other_run = _create_run(eval_root, "run-other", run_id="run-601")
    bad_run = _create_run(eval_root, "run-bad-root", run_id="run-602")
    manifest_path = bad_run / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["candidate_repowiki_zh_root"] = str(other_run / "repowiki" / "zh")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-602"])
    assert result.exit_code != 0
    assert "candidate_repowiki_zh_root" in result.output

    published_after = json.loads(
        (eval_root / "repowiki" / "zh" / "manifest.json").read_text(encoding="utf-8")
    )
    assert published_after["source_run_id"] == "run-600"


def test_release_publish_rejects_relative_content_root_escape(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_run(eval_root, "run-relative-escape", run_id="run-603")
    outside_content = eval_root / "outside-content"
    outside_content.mkdir(parents=True)
    (outside_content / "00-overview.md").write_text("# Escape\n", encoding="utf-8")
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["candidate_content_root"] = "../outside-content"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-603"])
    assert result.exit_code != 0
    assert "candidate_content_root escapes selected canonical run tree" in result.output


def test_release_publish_rejects_absolute_meta_root_from_different_run(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    other_run = _create_run(eval_root, "run-other-meta", run_id="run-604")
    bad_run = _create_run(eval_root, "run-bad-meta-root", run_id="run-605")
    manifest_path = bad_run / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["candidate_meta_root"] = str(other_run / "repowiki" / "zh" / "meta")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-605"])
    assert result.exit_code != 0
    assert "candidate_meta_root escapes selected canonical run tree" in result.output


def test_release_publish_rejects_symlink_content_root_escape(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_run(eval_root, "run-symlink-escape", run_id="run-606")
    outside_content = eval_root / "outside-symlink-content"
    outside_content.mkdir(parents=True)
    (outside_content / "00-overview.md").write_text("# Escape\n", encoding="utf-8")
    canonical_content = run_dir / "repowiki" / "zh" / "content"
    shutil.rmtree(canonical_content)
    try:
        canonical_content.symlink_to(outside_content, target_is_directory=True)
    except OSError as exc:  # pragma: no cover - platform capability guard
        pytest.skip(f"directory symlink unavailable: {exc}")

    result = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-606"])
    assert result.exit_code != 0
    assert "candidate_content_root escapes selected canonical run tree" in result.output


def test_release_publish_rejects_symlink_canonical_tree_escape(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_run(eval_root, "run-symlink-canonical", run_id="run-607")
    outside_zh = eval_root / "outside-canonical-zh"
    outside_content = outside_zh / "content"
    outside_meta = outside_zh / "meta"
    outside_content.mkdir(parents=True)
    outside_meta.mkdir(parents=True)
    (outside_content / "00-overview.md").write_text("# Escape\n", encoding="utf-8")
    (outside_meta / "navigation.json").write_text(
        json.dumps(_valid_navigation_meta()), encoding="utf-8"
    )

    canonical_zh = run_dir / "repowiki" / "zh"
    shutil.rmtree(canonical_zh)
    try:
        canonical_zh.symlink_to(outside_zh, target_is_directory=True)
    except OSError as exc:  # pragma: no cover - platform capability guard
        pytest.skip(f"directory symlink unavailable: {exc}")

    result = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-607"])
    assert result.exit_code != 0
    assert "Selected run canonical tree escapes selected run" in result.output
    assert not (eval_root / "repowiki" / "zh" / "manifest.json").exists()


def test_release_publish_rejects_descendant_file_symlink_and_preserves_release(
    tmp_path: Path,
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_run(eval_root, "run-stable", run_id="run-710")
    first = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-710"])
    assert first.exit_code == 0
    published_before = _snapshot_published_state(eval_root)

    bad_run = _create_run(eval_root, "run-file-link", run_id="run-711")
    outside_file = tmp_path / "outside-content.md"
    outside_file.write_text("# Must not be copied\n", encoding="utf-8")
    file_link = bad_run / "repowiki" / "zh" / "content" / "outside-content.md"
    try:
        file_link.symlink_to(outside_file)
    except OSError as exc:  # pragma: no cover - platform capability guard
        pytest.skip(f"file symlink unavailable: {exc}")

    result = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-711"])
    assert result.exit_code != 0
    assert "candidate_content_root contains symlink" in result.output
    assert _snapshot_published_state(eval_root) == published_before


def test_release_publish_rejects_descendant_directory_symlink_and_preserves_release(
    tmp_path: Path,
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_run(eval_root, "run-stable", run_id="run-720")
    first = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-720"])
    assert first.exit_code == 0
    published_before = _snapshot_published_state(eval_root)

    bad_run = _create_run(eval_root, "run-directory-link", run_id="run-721")
    outside_dir = tmp_path / "outside-meta"
    outside_dir.mkdir()
    (outside_dir / "private.json").write_text(json.dumps({"private": True}), encoding="utf-8")
    directory_link = bad_run / "repowiki" / "zh" / "meta" / "outside-meta"
    try:
        directory_link.symlink_to(outside_dir, target_is_directory=True)
    except OSError as exc:  # pragma: no cover - platform capability guard
        pytest.skip(f"directory symlink unavailable: {exc}")

    result = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "run-721"])
    assert result.exit_code != 0
    assert "candidate_meta_root contains symlink" in result.output
    assert _snapshot_published_state(eval_root) == published_before


def test_release_publish_inspect_only_does_not_mutate_release(tmp_path: Path) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_run(eval_root, "run-ready", run_id="run-300")
    result = runner.invoke(
        app,
        ["release-publish", "--output", str(eval_root), "--run", "run-300", "--inspect-only"],
    )
    assert result.exit_code == 0
    assert "READY_CANDIDATE" in result.output
    assert not (eval_root / "repowiki" / "zh" / "manifest.json").exists()


def test_compare_readiness_flags_required_counterpart_missing() -> None:
    failures = _compare_readiness_failures(
        {
            "metrics": {
                "page_count": {"ratio_vs_baseline": 1.0},
                "chinese_directory_depth": {"ratio_vs_baseline": 1.0, "baseline_depth": 2},
                "llm_generation_coverage": {"coverage": 1.0},
            },
            "baseline_read_only_verified": True,
            "path_comparison": {
                "required_counterpart_failures": [
                    {
                        "rule_id": "inventory_service_api_topic",
                        "message": "Missing required counterpart page for Inventory Service API",
                        "baseline_matches": ["API参考/核心服务API/API台账服务 API.md"],
                        "required_prefixes": ["API参考/核心服务API/"],
                    }
                ]
            },
        }
    )
    assert any(f["code"] == "QODER_REQUIRED_COUNTERPART_MISSING" for f in failures)


def test_compare_readiness_flags_required_counterpart_quality_low() -> None:
    failures = _compare_readiness_failures(
        {
            "metrics": {
                "page_count": {"ratio_vs_baseline": 1.0},
                "chinese_directory_depth": {"ratio_vs_baseline": 1.0, "baseline_depth": 2},
                "llm_generation_coverage": {"coverage": 1.0},
            },
            "baseline_read_only_verified": True,
            "path_comparison": {
                "required_counterpart_failures": [
                    {
                        "rule_id": "gitlab_mcp_api_topic",
                        "failure_type": "quality_low",
                        "message": "Counterpart exists but ownership/citation score is below threshold.",
                        "baseline_matches": ["API参考/核心服务API/GitLab MCP服务 API.md"],
                        "required_prefixes": ["API参考/核心服务API/"],
                        "pair_score": {"score": 0.1, "forbidden_hits": 2},
                    }
                ]
            },
        }
    )
    assert any(f["code"] == "QODER_REQUIRED_COUNTERPART_QUALITY_LOW" for f in failures)


class TestLoadManualReviewResult:
    """Tests for _load_manual_review_result search path resolution."""

    def test_finds_in_output_dir(self, tmp_path: Path) -> None:
        payload = {"summary": {"status": "PASS"}, "failures": []}
        (tmp_path / "manual-review-matrix-v2.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        result = _load_manual_review_result(target=tmp_path / "target", output_dir=tmp_path)
        assert result is not None
        assert result["summary"]["status"] == "PASS"

    def test_finds_in_target_parent_reports(self, tmp_path: Path) -> None:
        target = tmp_path / "content"
        target.mkdir()
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        payload = {"summary": {"status": "FAIL"}, "failures": [{"code": "X"}]}
        (reports_dir / "manual-review-matrix-v2.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        result = _load_manual_review_result(target=target, output_dir=tmp_path / "output")
        assert result is not None
        assert result["summary"]["status"] == "FAIL"

    def test_finds_in_target_parent(self, tmp_path: Path) -> None:
        target = tmp_path / "content"
        target.mkdir()
        payload = {"summary": {"status": "PASS"}, "failures": []}
        (tmp_path / "manual-review-matrix-v2.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        result = _load_manual_review_result(target=target, output_dir=tmp_path / "output")
        assert result is not None

    def test_returns_none_when_not_found(self, tmp_path: Path) -> None:
        target = tmp_path / "content"
        target.mkdir()
        result = _load_manual_review_result(target=target, output_dir=tmp_path / "output")
        assert result is None

    def test_returns_none_on_invalid_json(self, tmp_path: Path) -> None:
        (tmp_path / "manual-review-matrix-v2.json").write_text("bad{json", encoding="utf-8")
        result = _load_manual_review_result(target=tmp_path / "target", output_dir=tmp_path)
        assert result is None
