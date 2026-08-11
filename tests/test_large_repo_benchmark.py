from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.large_repo_benchmark import (
    SCALE_BENCHMARK_CONTRACT_VERSION,
    SCALE_BENCHMARK_SCHEMA_VERSION,
    run_scale_benchmark,
)
from scripts.large_repo_fixture import generate_scale_fixture, load_and_validate_scale_fixture


def test_scale_benchmark_exports_contract_and_measurement_evidence(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixture"
    generate_scale_fixture(fixture_root, effective_file_count=8, git_file_count=12, seed=9)

    report = run_scale_benchmark(
        fixture_root,
        cache_policy="cold",
        provider="mock/replay",
        model="fixture-model",
        network_condition="offline",
    )

    assert report["schema_version"] == SCALE_BENCHMARK_SCHEMA_VERSION
    assert report["contract_version"] == SCALE_BENCHMARK_CONTRACT_VERSION
    assert report["contract_status"] == "passed"
    assert report["gating_status"] == "gating"
    assert report["non_gating_reasons"] == []
    assert report["measurements"]["elapsed_seconds"] >= 0
    assert report["measurements"]["peak_rss_bytes"] > 0
    assert report["inventory_evidence"]["observed_git_file_count"] == 12
    assert report["inventory_evidence"]["observed_effective_file_count"] == 8
    assert report["threshold_profile"] == {
        "id": "stage0-contract",
        "scope": "contract-only",
        "sample_count": 1,
        "production_scale_gate": "not_evaluated",
    }
    assert report["environment"]["provider"] == "mock/replay"
    assert report["environment"]["model"] == "fixture-model"
    assert "node" in report["environment"]
    assert report["fixture"]["fixture_commit"] == "synthetic-seed:9"


def test_scale_benchmark_marks_warmup_and_drift_non_gating(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixture"
    manifest = generate_scale_fixture(
        fixture_root, effective_file_count=3, git_file_count=5, seed=2
    )
    changed = fixture_root / "repository" / manifest["inventory"]["expected_effective_files"][0]
    changed.write_text("drift\n", encoding="utf-8")

    report = run_scale_benchmark(fixture_root, measured_run=False)

    assert report["contract_status"] == "failed"
    assert report["gating_status"] == "non_gating"
    assert report["threshold_profile"]["sample_count"] == 0
    assert any("warmup" in reason for reason in report["non_gating_reasons"])
    assert any("inventory_hash" in reason for reason in report["non_gating_reasons"])


def test_scale_benchmark_rejects_malformed_fixture_provenance(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixture"
    generate_scale_fixture(fixture_root, effective_file_count=3, git_file_count=5)
    manifest_path = fixture_root / "fixture-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["provenance"]["generated_at"] = "not-a-timestamp"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = run_scale_benchmark(fixture_root)

    assert report["contract_status"] == "failed"
    assert report["gating_status"] == "non_gating"
    assert report["threshold_profile"]["sample_count"] == 0
    assert any("generated_at" in reason for reason in report["non_gating_reasons"])


def test_scale_benchmark_cli_writes_json_report(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixture"
    output = tmp_path / "benchmark.json"
    generate_scale_fixture(fixture_root, effective_file_count=4, git_file_count=7, seed=4)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/large_repo_benchmark.py",
            "--fixture",
            str(fixture_root),
            "--output",
            str(output),
            "--cache-policy",
            "cold",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["contract_status"] == "passed"
    assert report["command"]["argv"]
    assert report["inventory_evidence"]["expected_git_file_count"] == 7


def test_scale_benchmark_source_scan_records_operation_metrics(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixture"
    generate_scale_fixture(fixture_root, effective_file_count=4, git_file_count=6, seed=11)

    report = run_scale_benchmark(
        fixture_root,
        operation="source-scan",
        scanner_incremental=False,
    )

    assert report["contract_status"] == "passed"
    assert report["command"]["operation"] == "source-scan"
    metrics = report["measurements"]["operation_metrics"]["source_scan"]
    assert metrics["scanner_name"] == "multi_runtime_source_scanner_v3"
    assert metrics["incremental"] is False
    assert metrics["files_total"] == 6
    assert metrics["files_scanned"] == 6
    assert metrics["files_rescanned"] == 6
    assert metrics["files_cached"] == 0
    assert len(metrics["input_fingerprint"]) == 64
    assert metrics["checkpoint"]["present"] is True
    assert len(metrics["checkpoint"]["fingerprint"]) == 64


def test_scale_benchmark_knowledge_plan_records_plan_counts(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixture"
    generate_scale_fixture(fixture_root, effective_file_count=5, git_file_count=5, seed=12)

    report = run_scale_benchmark(
        fixture_root,
        operation="knowledge-plan",
        scanner_incremental=False,
    )

    assert report["contract_status"] == "passed"
    metrics = report["measurements"]["operation_metrics"]
    assert metrics["source_scan"]["files_scanned"] == 5
    plan_metrics = metrics["knowledge_plan"]
    assert plan_metrics["plan_directory_count"] > 0
    assert plan_metrics["plan_template_count"] > 0
    assert plan_metrics["plan_domain_count"] >= 0
    assert plan_metrics["plan_doc_count"] == 0
    assert len(plan_metrics["plan_fingerprint"]) == 64
    assert len(plan_metrics["knowledge_model_fingerprint"]) == 64
    assert plan_metrics["knowledge_model_input_fingerprints"]["source_inventory"]
    assert plan_metrics["validation_issue_count"] == 0


def test_scale_benchmark_mutating_operations_do_not_drift_fixture(
    tmp_path: Path,
) -> None:
    fixture_root = tmp_path / "fixture"
    generate_scale_fixture(fixture_root, effective_file_count=5, git_file_count=7, seed=15)
    fixture_repository = fixture_root / "repository"

    source_scan_report = run_scale_benchmark(
        fixture_root,
        operation="source-scan",
        scanner_incremental=False,
    )
    knowledge_plan_report = run_scale_benchmark(
        fixture_root,
        operation="knowledge-plan",
        scanner_incremental=False,
    )
    _, observed, reasons = load_and_validate_scale_fixture(fixture_root)

    assert source_scan_report["contract_status"] == "passed"
    assert knowledge_plan_report["contract_status"] == "passed"
    assert observed["git_file_count"] == 7
    assert reasons == []
    assert not (fixture_repository / ".repo-wiki").exists()

    source_metrics = source_scan_report["measurements"]["operation_metrics"]
    plan_metrics = knowledge_plan_report["measurements"]["operation_metrics"]
    for metrics in (source_metrics, plan_metrics):
        measurement_repository = metrics["measurement_repository"]
        assert measurement_repository["isolated"] is True
        assert measurement_repository["fixture_repository_path"] == str(
            fixture_repository.resolve()
        )
        assert measurement_repository["path"] != str(fixture_repository.resolve())
        checkpoint = metrics["source_scan"]["checkpoint"]
        assert checkpoint["present"] is True
        assert checkpoint["path"].startswith(measurement_repository["path"])


def test_scale_benchmark_tiered_profile_rejects_inventory_only_measurement(
    tmp_path: Path,
) -> None:
    fixture_root = tmp_path / "fixture"
    generate_scale_fixture(fixture_root, effective_file_count=4, git_file_count=7, seed=16)

    report = run_scale_benchmark(
        fixture_root,
        threshold_profile="tiered-10k-100k",
        hard_10k_effective_files=4,
        stress_100k_git_files=7,
        gate_100k_stress=True,
    )

    assert report["contract_status"] == "failed"
    profile = report["threshold_profile"]
    assert profile["production_scale_gate"] == "failed"
    assert profile["hard_10k_effective_files"]["observed"] is None
    assert profile["stress_100k_git_files"]["observed"] is None
    assert any("requires measured source-scan" in reason for reason in profile["reasons"])


def test_scale_benchmark_tiered_profile_uses_measured_source_scan_counts(
    tmp_path: Path,
) -> None:
    fixture_root = tmp_path / "fixture"
    generate_scale_fixture(fixture_root, effective_file_count=2, git_file_count=6, seed=17)

    report = run_scale_benchmark(
        fixture_root,
        operation="source-scan",
        scanner_incremental=False,
        threshold_profile="tiered-10k-100k",
        hard_10k_effective_files=6,
        stress_100k_git_files=6,
        gate_100k_stress=True,
    )

    metrics = report["measurements"]["operation_metrics"]["source_scan"]
    assert metrics["files_scanned"] == 6
    assert metrics["files_total"] == 6
    assert report["inventory_evidence"]["observed_effective_file_count"] == 2
    assert report["threshold_profile"]["production_scale_gate"] == "passed"
    assert report["threshold_profile"]["hard_10k_effective_files"]["observed"] == 6
    assert report["threshold_profile"]["stress_100k_git_files"]["observed"] == 6


def test_scale_benchmark_tiered_profile_supports_overridden_gates(
    tmp_path: Path,
) -> None:
    fixture_root = tmp_path / "fixture"
    generate_scale_fixture(fixture_root, effective_file_count=4, git_file_count=7, seed=13)

    report = run_scale_benchmark(
        fixture_root,
        operation="source-scan",
        scanner_incremental=False,
        threshold_profile="tiered-10k-100k",
        hard_10k_effective_files=4,
        stress_100k_git_files=7,
        gate_100k_stress=True,
    )

    assert report["contract_status"] == "passed"
    assert report["threshold_profile"]["id"] == "tiered-10k-100k"
    assert report["threshold_profile"]["production_scale_gate"] == "passed"
    assert report["threshold_profile"]["hard_10k_effective_files"] == {
        "threshold": 4,
        "observed": 7,
        "passed": True,
        "gating": True,
    }
    assert report["threshold_profile"]["stress_100k_git_files"] == {
        "threshold": 7,
        "observed": 7,
        "passed": True,
        "gating": True,
    }
    assert report["threshold_profile"]["reasons"] == []


def test_scale_benchmark_tiered_profile_reports_failed_gate_reason(
    tmp_path: Path,
) -> None:
    fixture_root = tmp_path / "fixture"
    generate_scale_fixture(fixture_root, effective_file_count=3, git_file_count=5, seed=14)

    report = run_scale_benchmark(
        fixture_root,
        operation="source-scan",
        scanner_incremental=False,
        threshold_profile="tiered-10k-100k",
        hard_10k_effective_files=6,
        stress_100k_git_files=6,
    )

    assert report["contract_status"] == "failed"
    assert report["gating_status"] == "non_gating"
    profile = report["threshold_profile"]
    assert profile["hard_10k_effective_files"]["passed"] is False
    assert profile["stress_100k_git_files"]["passed"] is False
    assert profile["stress_100k_git_files"]["gating"] is False
    assert any("hard_10k_effective_files" in reason for reason in profile["reasons"])
    assert any("hard_10k_effective_files" in reason for reason in report["non_gating_reasons"])
