"""G005 release-publish hard-gate closure tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

import repo_wiki.verifier.qoder_strict_verifier as strict_verifier
from repo_wiki.cli import app
from repo_wiki.orchestration.g005_quality_gate import (
    _recompute_qoder_comparison_report,
    hash_run_tree,
    stable_json_bytes,
)
from repo_wiki.orchestration.release_publisher import (
    ReleasePublishError,
    _hash_tree,
    publish_ready_run,
)
from repo_wiki.verifier.review_attestation import NAMESPACE, canonical_signed_bytes

runner = CliRunner()


def _valid_navigation_meta() -> dict:
    return {
        "schema_version": "repo_agent.navigation/1.0",
        "generated_at": "2024-01-01T00:00:00Z",
        "navigation_tree": [],
    }


def _base_gates(**overrides: object) -> dict:
    gates = {
        "qoder_comparison": {"status": "READY", "readiness_state": "READY"},
        "blind_review_v3": {"grade": "PASS", "status": "PASS"},
        "acceptance_fixture_registry": {"status": "PASS"},
        "citation_hard_gate_evidence": {"status": "PASS", "hard_gate_failures": 0},
        "critical_false_fact_evidence": {"status": "PASS", "critical_false_fact_failures": 0},
        "quality_hard_gate_evidence": {"status": "PASS", "hard_gate_failures": 0},
        "conflict_hard_gate_evidence": {"status": "PASS", "unresolved_count": 0},
    }
    for key, value in overrides.items():
        if value is None:
            gates.pop(key, None)
        else:
            gates[key] = value
    return gates


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


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode()).hexdigest()


def _stable_hash(value: dict) -> str:
    import hashlib

    return hashlib.sha256(stable_json_bytes(value)).hexdigest()


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
            "artifact_hash": _hash("a1"),
            "provenance_hash": _hash("pa1"),
        },
        {
            "candidate_id": "b1",
            "system": "qoder",
            "artifact_hash": _hash("b1"),
            "provenance_hash": _hash("pb1"),
        },
    ]
    records = []
    for repo_class in classes:
        records.append(
            {
                "repo_class": repo_class,
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
                "repo_class": repo_class,
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
        "reviewer_identity_hash": _hash("reviewer"),
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


def _write_standard_content_pages(content_dir: Path) -> None:
    pages = [
        "00-overview",
        "01-architecture",
        "02-services",
        "03-module-map",
        "04-api",
        "05-data-model",
        "operations",
        "development",
        "security",
        "troubleshooting",
    ]
    content_dir.mkdir(parents=True, exist_ok=True)
    for slug in pages:
        (content_dir / f"{slug}.md").write_text(
            f"# {slug}\n\n## 目录\n\n- [Evidence](#evidence)\n\n## Evidence\n\n"
            "```mermaid\ngraph TD; A-->B;\n```\n\n"
            "<cite>repo_wiki/cli.py:1</cite>\n\n"
            "This page contains enough prose about repo wiki generation, API contracts, data models, operations, development, security, and troubleshooting evidence.\n",
            encoding="utf-8",
        )


def _ensure_test_repo_and_baseline(eval_root: Path) -> Path:
    repo_root = eval_root.parent
    (repo_root / ".git").mkdir(exist_ok=True)
    baseline = repo_root / ".qoder" / "repowiki" / "zh"
    (baseline / "content").mkdir(parents=True, exist_ok=True)
    (baseline / "meta").mkdir(parents=True, exist_ok=True)
    _write_standard_content_pages(baseline / "content")
    (baseline / "meta" / "navigation.json").write_text(
        json.dumps(_valid_navigation_meta()), encoding="utf-8"
    )
    return baseline


def _eval_root_for_run(run_dir: Path) -> Path:
    return run_dir.parents[1] if run_dir.parent.name == "runs" else run_dir.parent


def _write_attestation_artifacts(
    run_dir: Path,
    review_payload: dict,
    qoder_payload: dict,
    allowed_signers: Path,
) -> tuple[Path, Path]:
    reports = run_dir / "reports"
    signed_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    signed = canonical_signed_bytes(
        review_payload=review_payload,
        qoder_comparison_payload=qoder_payload,
        signed_at=signed_at,
    )
    sig = reports / "blind-review-v3.sig"
    sig.write_bytes(b"test-detached-signature")
    attestation = {
        "namespace": NAMESPACE,
        "principal": "reviewer@example.com",
        "signed_at": signed_at,
        "signature_path": sig.relative_to(run_dir).as_posix(),
        "signed_payload_sha256": _hash_bytes(signed),
    }
    att_path = reports / "blind-review-v3.attestation.json"
    att_path.write_text(json.dumps(attestation), encoding="utf-8")
    allowed_signers.write_text(
        "reviewer@example.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestOnly\n", encoding="utf-8"
    )
    return att_path, sig


def _hash_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


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
                "fixture_hash": _hash(f"fixture-{cls}"),
                "revision": "abc123",
                "baseline_artifact_path": f"{cls}/baseline.json",
                "baseline_artifact_hash": _hash(f"baseline-{cls}"),
                "generated_at": "2024-01-01T00:00:00Z",
                "qoder_version": "qoder-test",
                "generator_identity": "test",
                "rubric_version": "v1",
            }
            for i, cls in enumerate(classes)
        ]
    }


def _write_production_artifacts(run_dir: Path, run_id: str, content: Path, meta: Path) -> None:
    reports = run_dir / "reports"
    pages = [
        {
            "page_id": page.stem,
            "stable_page_id": page.stem,
            "relative_path": page.relative_to(content).as_posix(),
            "category": "test",
            "page_type": "test",
            "title": page.stem,
        }
        for page in sorted(content.rglob("*.md"))
    ]
    (meta / "page-registry.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.page_registry/1.0",
                "generated_at": "2026-07-15T00:00:00Z",
                "run_id": run_id,
                "pages": pages,
            }
        ),
        encoding="utf-8",
    )
    (meta / "evidence-index.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.evidence_index/1.0",
                "generated_at": "2026-07-15T00:00:00Z",
                "run_id": run_id,
                "spans": [],
            }
        ),
        encoding="utf-8",
    )
    strict = reports / "strict-verify-output.json"
    strict.write_text(json.dumps(_strict_pass_report()), encoding="utf-8")
    (reports / "manual-review-matrix-v2.json").write_text(
        json.dumps({"summary": {"status": "PASS"}, "failures": []}), encoding="utf-8"
    )
    qoder_payload = _recompute_qoder_comparison_report(
        run_dir / "repowiki" / "zh",
        _ensure_test_repo_and_baseline(_eval_root_for_run(run_dir)),
        reports,
    )
    (reports / "qoder-comparison-report.json").write_text(
        json.dumps(qoder_payload), encoding="utf-8"
    )
    review_payload = _blind_review_payload()
    (reports / "blind-review-v3.json").write_text(json.dumps(review_payload), encoding="utf-8")
    allowed_signers = run_dir.parents[2] / "allowed-signers"
    _write_attestation_artifacts(run_dir, review_payload, qoder_payload, allowed_signers)
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
    refs = {}
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
    for name, path in paths.items():
        refs[name] = {
            "path": path.relative_to(run_dir).as_posix(),
            "sha256": _sha256(path),
            "validator": "test",
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
                "sha256": _sha256(artifact),
            }
        )
    bundle = {
        "schema_version": "repo_agent.g005_quality_gates/1.0",
        "run_id": run_id,
        "content_sha256": _hash_tree(content),
        "meta_sha256": _hash_tree(meta),
        "run_fingerprints": {
            "manifest_sha256": _sha256(run_dir / "manifest.json"),
            "run_sha256": hash_run_tree(run_dir),
            "content_sha256": _hash_tree(content),
            "meta_sha256": _hash_tree(meta),
            "strict_report_sha256": _sha256(strict),
            "strict_result_sha256": _stable_hash(_strict_pass_report()),
        },
        "artifact_references": refs,
        "review_allowed_signers_sha256": _sha256(run_dir.parents[2] / "allowed-signers"),
        "acceptance_artifact_root": "reports/acceptance-artifacts",
        "acceptance_artifacts": acceptance_refs,
        "gates": _base_gates(),
        "status": "PASS",
    }
    (reports / "g005-quality-gates.json").write_text(json.dumps(bundle), encoding="utf-8")


def _refresh_g005_bundle_after_artifact_edit(run_dir: Path) -> None:
    bundle_path = run_dir / "reports" / "g005-quality-gates.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    for ref in bundle.get("artifact_references", {}).values():
        if isinstance(ref, dict) and isinstance(ref.get("path"), str):
            path = run_dir / ref["path"]
            if path.is_file():
                ref["sha256"] = _sha256(path)
    fingerprints = bundle.get("run_fingerprints")
    if isinstance(fingerprints, dict):
        fingerprints["manifest_sha256"] = _sha256(run_dir / "manifest.json")
        fingerprints["run_sha256"] = hash_run_tree(run_dir)
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")


def _create_candidate(
    eval_root: Path,
    run_dir_rel: str,
    *,
    run_id: str,
    readiness_state: str | None = "READY",
    ready: bool | None = None,
    gates: dict | None = None,
    strict_grade: str = "PASS",
) -> Path:
    run_dir = eval_root / run_dir_rel
    content = run_dir / "repowiki" / "zh" / "content"
    meta = run_dir / "repowiki" / "zh" / "meta"
    reports = run_dir / "reports"
    content.mkdir(parents=True, exist_ok=True)
    meta.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    _write_standard_content_pages(content)
    (meta / "navigation.json").write_text(json.dumps(_valid_navigation_meta()), encoding="utf-8")
    (reports / "strict-verify-output.json").write_text(
        json.dumps(_strict_pass_report() if strict_grade == "PASS" else {"grade": strict_grade}),
        encoding="utf-8",
    )
    manifest = {
        "run_id": run_id,
        "target_dirty": False,
        "git_fresh": True,
        "candidate_repowiki_zh_root": str(run_dir / "repowiki" / "zh"),
        "candidate_content_root": str(content),
        "candidate_meta_root": str(meta),
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
    if readiness_state is not None:
        manifest["readiness_state"] = readiness_state
    if ready is not None:
        manifest["ready"] = ready
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _write_production_artifacts(run_dir, run_id, content, meta)
    if gates is not None:
        bundle_path = reports / "g005-quality-gates.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        refs = bundle["artifact_references"]
        if "qoder_comparison" not in gates:
            refs.pop("qoder_comparison", None)
        elif gates.get("qoder_comparison", {}).get("readiness_state") == "NOT_READY":
            (reports / "qoder-comparison-report.json").write_text(
                json.dumps({"status": "NOT_READY", "baseline_read_only_verified": True}),
                encoding="utf-8",
            )
            refs["qoder_comparison"]["sha256"] = _sha256(reports / "qoder-comparison-report.json")
        if "blind_review_v3" not in gates:
            refs.pop("blind_review_v3", None)
        elif gates.get("blind_review_v3", {}).get("grade") == "FAIL":
            bad = _blind_review_payload()
            bad["records"][0]["critical_false_facts"] = 1
            (reports / "blind-review-v3.json").write_text(json.dumps(bad), encoding="utf-8")
            refs["blind_review_v3"]["sha256"] = _sha256(reports / "blind-review-v3.json")
        if gates.get("acceptance_fixture_registry", {}).get("status") == "FAIL":
            (reports / "acceptance-fixture-registry.json").write_text(
                json.dumps({"entries": []}), encoding="utf-8"
            )
            refs["acceptance_fixture_registry"]["sha256"] = _sha256(
                reports / "acceptance-fixture-registry.json"
            )
        for name in (
            "quality_hard_gate_evidence",
            "conflict_hard_gate_evidence",
            "critical_false_fact_evidence",
            "citation_hard_gate_evidence",
        ):
            gate = gates.get(name)
            if isinstance(gate, dict) and (
                gate.get("status") == "FAIL"
                or gate.get("hard_gate_failures")
                or gate.get("unresolved_count")
                or gate.get("critical_false_fact_failures")
            ):
                refs.pop(name, None)
        bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    return run_dir


@pytest.fixture
def strict_pass(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def pass_verify(_root: Path, *, ci: bool = True, strict: bool = True) -> dict:
        return _strict_pass_report()

    monkeypatch.setattr(strict_verifier, "verify_qoder_like", pass_verify)
    import repo_wiki.verifier.review_attestation as review_attestation

    monkeypatch.setattr(review_attestation, "_verify_openssh_signature", lambda **_kwargs: None)


def test_forged_shallow_strict_pass_report_rejected_by_authoritative_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_candidate(eval_root, "runs/run-forged", run_id="run-forged")

    def fail_verify(_root: Path, *, ci: bool = True, strict: bool = True) -> dict:
        return {
            "grade": "FAIL",
            "exit_code": 1,
            "summary": {"hard_gate_failures": 1},
            "gate_summary": {"hard_gate_blocking": True},
            "hard_gate_codes": ["QODER_CONTENT_EMPTY"],
        }

    monkeypatch.setattr(strict_verifier, "verify_qoder_like", fail_verify)
    with pytest.raises(ReleasePublishError, match="Authoritative qoder-like strict verification"):
        publish_ready_run(eval_root, "run-forged")


def test_page_tamper_after_g005_bundle_rejected_and_previous_release_preserved(
    tmp_path: Path, strict_pass: None
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_candidate(eval_root, "runs/run-stable", run_id="run-stable")
    publish_ready_run(eval_root, "run-stable")
    before = (eval_root / "repowiki" / "zh" / "manifest.json").read_bytes()

    tampered = _create_candidate(eval_root, "runs/run-tampered", run_id="run-tampered")
    (tampered / "repowiki" / "zh" / "content" / "00-overview.md").write_text(
        "# Tampered after bundle\n", encoding="utf-8"
    )

    with pytest.raises(ReleasePublishError, match="content fingerprint mismatch"):
        publish_ready_run(eval_root, "run-tampered")
    assert (eval_root / "repowiki" / "zh" / "manifest.json").read_bytes() == before


@pytest.mark.parametrize(
    ("gates", "message"),
    [
        (_base_gates(qoder_comparison=None), "missing qoder_comparison"),
        (
            _base_gates(qoder_comparison={"status": "PASS", "readiness_state": "NOT_READY"}),
            "Qoder comparison missing target provenance",
        ),
        (_base_gates(blind_review_v3=None), "missing blind_review_v3"),
        (_base_gates(blind_review_v3={"grade": "FAIL", "status": "FAIL"}), "blind_review_v3"),
        (
            _base_gates(acceptance_fixture_registry={"status": "FAIL"}),
            "acceptance_fixture_registry",
        ),
        (
            _base_gates(quality_hard_gate_evidence={"status": "PASS", "hard_gate_failures": 1}),
            "quality_hard_gate_evidence",
        ),
        (
            _base_gates(conflict_hard_gate_evidence={"status": "PASS", "unresolved_count": 1}),
            "conflict_hard_gate_evidence",
        ),
        (
            _base_gates(
                critical_false_fact_evidence={"status": "PASS", "critical_false_fact_failures": 1}
            ),
            "critical_false_fact_evidence",
        ),
        (
            _base_gates(citation_hard_gate_evidence={"status": "FAIL"}),
            "citation_hard_gate_evidence",
        ),
    ],
)
def test_g005_bundle_hard_gate_failures_rejected(
    tmp_path: Path, strict_pass: None, gates: dict, message: str
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_candidate(eval_root, "runs/run-gate", run_id="run-gate", gates=gates)
    with pytest.raises(ReleasePublishError, match=message):
        publish_ready_run(eval_root, "run-gate")


def test_ready_true_without_readiness_state_cannot_publish(
    tmp_path: Path, strict_pass: None
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_candidate(
        eval_root,
        "runs/run-ready-bool-only",
        run_id="run-ready-bool-only",
        readiness_state=None,
        ready=True,
    )
    with pytest.raises(ReleasePublishError, match="requires readiness_state=READY"):
        publish_ready_run(eval_root, "run-ready-bool-only")


@pytest.mark.parametrize("filename", ["page-registry.json", "evidence-index.json"])
def test_publish_rejects_missing_required_ide_sidecar(
    tmp_path: Path, strict_pass: None, filename: str
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_candidate(
        eval_root,
        f"runs/run-missing-{filename}",
        run_id=f"run-missing-{filename}",
    )
    (run_dir / "repowiki" / "zh" / "meta" / filename).unlink()

    with pytest.raises(
        ReleasePublishError, match=f"Required READY meta sidecar missing: {filename}"
    ):
        publish_ready_run(eval_root, run_dir.name)


def test_all_valid_g005_bundle_publishes(tmp_path: Path, strict_pass: None) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_candidate(eval_root, "runs/run-valid", run_id="run-valid")
    result = publish_ready_run(eval_root, "run-valid")
    assert result["status"] == "PUBLISHED"
    published = json.loads((eval_root / "repowiki" / "zh" / "manifest.json").read_text())
    assert published["source_run_id"] == "run-valid"


def test_cli_run_path_identity_fixes_flat_nested_same_name_collision(
    tmp_path: Path, strict_pass: None
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    _create_candidate(eval_root, "same", run_id="flat-id")
    _create_candidate(eval_root, "runs/same", run_id="nested-id")

    result = runner.invoke(app, ["release-publish", "--output", str(eval_root), "--run", "flat-id"])
    assert result.exit_code == 0, result.output
    published = json.loads((eval_root / "repowiki" / "zh" / "manifest.json").read_text())
    assert published["source_run_id"] == "flat-id"


def test_quality_gate_cli_compiles_all_valid_production_bundle(
    tmp_path: Path, strict_pass: None
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_candidate(eval_root, "runs/run-compile", run_id="run-compile")
    (run_dir / "reports" / "g005-quality-gates.json").unlink()

    result = runner.invoke(
        app, ["quality-gate", "--output", str(eval_root), "--run", "run-compile"]
    )
    assert result.exit_code == 0, result.output
    bundle = json.loads((run_dir / "reports" / "g005-quality-gates.json").read_text())
    assert bundle["status"] == "PASS"
    assert set(bundle["artifact_references"]) >= {
        "qoder_comparison",
        "blind_review_v3",
        "acceptance_fixture_registry",
        "citation_hard_gate_evidence",
    }
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["report_paths"]["g005_quality_gates"] == "reports/g005-quality-gates.json"


def _copy_allowed_signers_to(path: Path, source: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def test_quality_gate_compile_rejects_run_local_allowed_signers(
    tmp_path: Path, strict_pass: None
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_candidate(
        eval_root, "runs/run-local-signers-compile", run_id="run-local-signers-compile"
    )
    (run_dir / "reports" / "g005-quality-gates.json").unlink()
    run_local = _copy_allowed_signers_to(
        run_dir / "reports" / "allowed-signers",
        run_dir.parents[2] / "allowed-signers",
    )

    result = runner.invoke(
        app,
        [
            "quality-gate",
            "--output",
            str(eval_root),
            "--run",
            "run-local-signers-compile",
            "--review-allowed-signers",
            str(run_local),
        ],
    )

    assert result.exit_code != 0
    assert "allowed-signers file must be outside selected run" in result.output


def test_release_publish_rejects_explicit_run_local_allowed_signers(
    tmp_path: Path, strict_pass: None
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_candidate(
        eval_root, "runs/run-local-signers-publish", run_id="run-local-signers-publish"
    )
    run_local = _copy_allowed_signers_to(
        run_dir / "reports" / "allowed-signers",
        run_dir.parents[2] / "allowed-signers",
    )

    with pytest.raises(
        ReleasePublishError, match="allowed-signers file must be outside selected run"
    ):
        publish_ready_run(eval_root, "run-local-signers-publish", review_allowed_signers=run_local)


def test_release_publish_rejects_env_run_local_allowed_signers(
    tmp_path: Path, strict_pass: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_candidate(
        eval_root, "runs/run-local-signers-env", run_id="run-local-signers-env"
    )
    run_local = _copy_allowed_signers_to(
        run_dir / "reports" / "allowed-signers",
        run_dir.parents[2] / "allowed-signers",
    )
    monkeypatch.setenv("REPO_WIKI_G005_REVIEW_ALLOWED_SIGNERS", str(run_local))

    with pytest.raises(
        ReleasePublishError, match="allowed-signers file must be outside selected run"
    ):
        publish_ready_run(eval_root, "run-local-signers-env")


def test_quality_gate_compile_rejects_missing_and_non_file_allowed_signers(
    tmp_path: Path, strict_pass: None
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_candidate(eval_root, "runs/run-bad-signers", run_id="run-bad-signers")
    (run_dir / "reports" / "g005-quality-gates.json").unlink()

    missing_result = runner.invoke(
        app,
        [
            "quality-gate",
            "--output",
            str(eval_root),
            "--run",
            "run-bad-signers",
            "--review-allowed-signers",
            str(tmp_path / "missing-allowed-signers"),
        ],
    )
    assert missing_result.exit_code != 0
    assert "allowed-signers file missing" in missing_result.output

    directory = tmp_path / "allowed-signers-dir"
    directory.mkdir()
    dir_result = runner.invoke(
        app,
        [
            "quality-gate",
            "--output",
            str(eval_root),
            "--run",
            "run-bad-signers",
            "--review-allowed-signers",
            str(directory),
        ],
    )
    assert dir_result.exit_code != 0
    assert "is a" in dir_result.output and "directory" in dir_result.output


def test_allowed_signers_symlink_resolution_enforces_resolved_trust_root(
    tmp_path: Path, strict_pass: None
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_candidate(eval_root, "runs/run-symlink-signers", run_id="run-symlink-signers")
    external = run_dir.parents[2] / "allowed-signers"

    inside_link_to_external = run_dir / "reports" / "allowed-signers-link"
    inside_link_to_external.symlink_to(external)
    (run_dir / "reports" / "g005-quality-gates.json").unlink()
    pass_result = runner.invoke(
        app,
        [
            "quality-gate",
            "--output",
            str(eval_root),
            "--run",
            "run-symlink-signers",
            "--review-allowed-signers",
            str(inside_link_to_external),
        ],
    )
    assert pass_result.exit_code == 0, pass_result.output

    run_local = _copy_allowed_signers_to(run_dir / "reports" / "allowed-signers", external)
    outside_link_to_inside = tmp_path / "outside-link-to-run-allowed-signers"
    outside_link_to_inside.symlink_to(run_local)
    with pytest.raises(
        ReleasePublishError, match="allowed-signers file must be outside selected run"
    ):
        publish_ready_run(
            eval_root, "run-symlink-signers", review_allowed_signers=outside_link_to_inside
        )


def test_quality_gate_compile_with_explicit_external_allowed_signers_passes(
    tmp_path: Path, strict_pass: None
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_candidate(
        eval_root, "runs/run-external-signers", run_id="run-external-signers"
    )
    external = run_dir.parents[2] / "allowed-signers"
    (run_dir / "reports" / "g005-quality-gates.json").unlink()

    result = runner.invoke(
        app,
        [
            "quality-gate",
            "--output",
            str(eval_root),
            "--run",
            "run-external-signers",
            "--review-allowed-signers",
            str(external),
        ],
    )

    assert result.exit_code == 0, result.output
    bundle = json.loads((run_dir / "reports" / "g005-quality-gates.json").read_text())
    assert bundle["review_allowed_signers_sha256"] == _sha256(external)


def test_release_publish_rejects_g005_artifact_tamper(tmp_path: Path, strict_pass: None) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_candidate(eval_root, "runs/run-artifact-tamper", run_id="run-artifact-tamper")
    (run_dir / "reports" / "qoder-comparison-report.json").write_text(
        json.dumps({"status": "READY", "baseline_read_only_verified": True}), encoding="utf-8"
    )
    with pytest.raises(ReleasePublishError, match="qoder_comparison"):
        publish_ready_run(eval_root, "run-artifact-tamper")


def test_minimal_forged_qoder_comparison_cannot_publish_even_with_matching_hashes(
    tmp_path: Path, strict_pass: None
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_candidate(eval_root, "runs/run-minimal-forged", run_id="run-minimal-forged")
    (run_dir / "reports" / "qoder-comparison-report.json").write_text(
        json.dumps(
            {
                "status": "READY",
                "baseline_read_only_verified": True,
                "readiness_gates": {"status": "PASS"},
                "replacement_readiness": {"readiness_state": "READY", "replacement_go": True},
                "strict_verify": _strict_pass_report(),
            }
        ),
        encoding="utf-8",
    )
    _refresh_g005_bundle_after_artifact_edit(run_dir)

    with pytest.raises(
        ReleasePublishError, match="target provenance|path_comparison|metrics|manual review"
    ):
        publish_ready_run(eval_root, "run-minimal-forged")


def test_unsigned_blind_review_cannot_publish(tmp_path: Path, strict_pass: None) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_candidate(eval_root, "runs/run-unsigned-review", run_id="run-unsigned-review")
    bundle_path = run_dir / "reports" / "g005-quality-gates.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle["artifact_references"].pop("blind_review_attestation", None)
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

    with pytest.raises(ReleasePublishError, match="blind_review_attestation"):
        publish_ready_run(eval_root, "run-unsigned-review")


def test_forged_full_qoder_comparison_with_nonexistent_paths_cannot_publish(
    tmp_path: Path, strict_pass: None
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_candidate(
        eval_root, "runs/run-forged-full-compare", run_id="run-forged-full-compare"
    )
    report_path = run_dir / "reports" / "qoder-comparison-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["target"] = str(run_dir / "missing-target")
    report["baseline"] = str(tmp_path / ".qoder" / "missing-baseline")
    report_path.write_text(json.dumps(report), encoding="utf-8")
    _refresh_g005_bundle_after_artifact_edit(run_dir)

    with pytest.raises(ReleasePublishError, match="target missing|baseline missing"):
        publish_ready_run(eval_root, "run-forged-full-compare")


def test_acceptance_registry_nonexistent_baseline_artifacts_cannot_publish(
    tmp_path: Path, strict_pass: None
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_candidate(
        eval_root, "runs/run-missing-baselines", run_id="run-missing-baselines"
    )
    registry_path = run_dir / "reports" / "acceptance-fixture-registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    for entry in registry["entries"]:
        entry["baseline_artifact_path"] = f"missing/{entry['repo_class']}/baseline.json"
        entry["baseline_artifact_hash"] = _hash(f"fake-{entry['repo_class']}")
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    bundle_path = run_dir / "reports" / "g005-quality-gates.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle["acceptance_artifacts"] = [
        {
            "fixture_id": entry["fixture_id"],
            "path": entry["baseline_artifact_path"],
            "run_path": f"reports/acceptance-artifacts/{entry['baseline_artifact_path']}",
            "sha256": entry["baseline_artifact_hash"],
        }
        for entry in registry["entries"]
    ]
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    _refresh_g005_bundle_after_artifact_edit(run_dir)

    with pytest.raises(
        ReleasePublishError, match="acceptance.*missing|acceptance_fixture_registry"
    ):
        publish_ready_run(eval_root, "run-missing-baselines")


def test_qoder_like_verify_ci_persists_canonical_report_and_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    run_dir = _create_candidate(eval_root, "runs/run-verify", run_id="run-verify")
    monkeypatch.setattr(
        strict_verifier, "verify_qoder_like", lambda *_args, **_kwargs: _strict_pass_report()
    )

    result = runner.invoke(
        app, ["verify", "--profile", "qoder-like", "--output", str(run_dir), "--ci"]
    )
    assert result.exit_code == 0, result.output
    report_path = run_dir / "reports" / "strict-verify-output.json"
    assert report_path.is_file()
    persisted = json.loads(report_path.read_text())
    assert persisted["grade"] == "PASS"
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["report_paths"]["strict_verify"] == "reports/strict-verify-output.json"
    assert {item["path"] for item in manifest["files"] if isinstance(item, dict)} >= {
        "reports/strict-verify-output.json"
    }


def test_cli_g005_end_to_end_valid_and_adversarial_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eval_root = tmp_path / ".repo-agent-eval"
    monkeypatch.setattr(
        strict_verifier, "verify_qoder_like", lambda *_args, **_kwargs: _strict_pass_report()
    )
    import repo_wiki.verifier.review_attestation as review_attestation

    monkeypatch.setattr(review_attestation, "_verify_openssh_signature", lambda **_kwargs: None)

    valid = _create_candidate(eval_root, "runs/run-cli-e2e-valid", run_id="run-cli-e2e-valid")
    (valid / "reports" / "g005-quality-gates.json").unlink()
    verify_result = runner.invoke(
        app, ["verify", "--profile", "qoder-like", "--output", str(valid), "--ci"]
    )
    assert verify_result.exit_code == 0, verify_result.output
    gate_result = runner.invoke(
        app, ["quality-gate", "--output", str(eval_root), "--run", "run-cli-e2e-valid"]
    )
    assert gate_result.exit_code == 0, gate_result.output
    publish_result = runner.invoke(
        app, ["release-publish", "--output", str(eval_root), "--run", "run-cli-e2e-valid"]
    )
    assert publish_result.exit_code == 0, publish_result.output

    tampered = _create_candidate(eval_root, "runs/run-cli-e2e-tamper", run_id="run-cli-e2e-tamper")
    (tampered / "reports" / "g005-quality-gates.json").unlink()
    assert (
        runner.invoke(
            app, ["quality-gate", "--output", str(eval_root), "--run", "run-cli-e2e-tamper"]
        ).exit_code
        == 0
    )
    (tampered / "reports" / "qoder-comparison-report.json").write_text(
        json.dumps({"status": "READY", "baseline_read_only_verified": False}),
        encoding="utf-8",
    )
    tamper_result = runner.invoke(
        app, ["release-publish", "--output", str(eval_root), "--run", "run-cli-e2e-tamper"]
    )
    assert tamper_result.exit_code != 0
    assert "qoder_comparison" in tamper_result.output

    forged = _create_candidate(eval_root, "runs/run-cli-e2e-forged", run_id="run-cli-e2e-forged")
    (forged / "reports" / "g005-quality-gates.json").unlink()
    assert (
        runner.invoke(
            app, ["quality-gate", "--output", str(eval_root), "--run", "run-cli-e2e-forged"]
        ).exit_code
        == 0
    )

    def fail_verify(_root: Path, *, ci: bool = True, strict: bool = True) -> dict:
        return {
            "grade": "FAIL",
            "exit_code": 1,
            "summary": {"hard_gate_failures": 1},
            "gate_summary": {"hard_gate_blocking": True},
            "hard_gate_codes": ["QODER_FORGED"],
        }

    monkeypatch.setattr(strict_verifier, "verify_qoder_like", fail_verify)
    forged_result = runner.invoke(
        app, ["release-publish", "--output", str(eval_root), "--run", "run-cli-e2e-forged"]
    )
    assert forged_result.exit_code != 0
    assert "Authoritative qoder-like strict verification" in forged_result.output
