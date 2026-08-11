#!/usr/bin/env python3
"""Measure and validate deterministic large-repository fixture inventories."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from scripts.large_repo_fixture import load_and_validate_scale_fixture
except ModuleNotFoundError:  # Direct `python scripts/large_repo_benchmark.py` execution.
    from large_repo_fixture import load_and_validate_scale_fixture

try:
    import resource
except ImportError:  # pragma: no cover - resource is unavailable on Windows
    resource = None  # type: ignore[assignment]


SCALE_BENCHMARK_SCHEMA_VERSION = "repo_agent.scale_benchmark/1.0"
SCALE_BENCHMARK_CONTRACT_VERSION = "repo_agent.scale_benchmark_contract/1.0"
OPERATIONS = ("inventory", "source-scan", "knowledge-plan")
THRESHOLD_PROFILE_STAGE0 = "stage0-contract"
THRESHOLD_PROFILE_TIERED = "tiered-10k-100k"


def _peak_rss_bytes() -> int | None:
    if resource is None:
        return None
    raw_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(raw_peak)
    return int(raw_peak * 1024)


def _total_memory_bytes() -> int | None:
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        page_count = os.sysconf("SC_PHYS_PAGES")
        return int(page_size * page_count)
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _node_version() -> str | None:
    executable = shutil.which("node")
    if executable is None:
        return None
    try:
        completed = subprocess.run(
            [executable, "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip() or None


@contextmanager
def _isolated_measurement_repository(repository_root: Path) -> Iterator[Path]:
    """Copy a fixture repository before operations that write scanner artifacts."""
    with tempfile.TemporaryDirectory(prefix="repo-wiki-benchmark-") as temp_dir:
        measurement_root = (Path(temp_dir) / "repository").resolve()
        shutil.copytree(repository_root, measurement_root, symlinks=True)
        yield measurement_root


def _fixture_repository_root(fixture_root: Path, manifest: dict[str, Any]) -> Path:
    repository_value = manifest.get("repository_root")
    if isinstance(repository_value, str) and repository_value:
        return fixture_root / repository_value
    return fixture_root / "repository"


def _fingerprint(payload: Any) -> str:
    import hashlib

    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _source_scan_metrics(
    repository_root: Path, *, incremental: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    from repo_wiki.scanner.multi_runtime_scanner_v3 import (
        CACHE_DIRNAME,
        CACHE_SUBDIR,
        STATE_FILENAME,
        scan_repository_source_inventory_v3,
    )

    inventory = scan_repository_source_inventory_v3(repository_root, incremental=incremental)
    scanner = inventory.get("scanner", {}) if isinstance(inventory, dict) else {}
    stats = scanner.get("stats", {}) if isinstance(scanner, dict) else {}
    files = inventory.get("files", []) if isinstance(inventory, dict) else []
    state_path = repository_root / CACHE_DIRNAME / CACHE_SUBDIR / STATE_FILENAME
    checkpoint: dict[str, Any] = {
        "path": str(state_path),
        "present": state_path.exists(),
    }
    if state_path.exists():
        try:
            checkpoint["fingerprint"] = _fingerprint(
                json.loads(state_path.read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError):
            checkpoint["fingerprint"] = None

    files_total = len(files) if isinstance(files, list) else None
    files_scanned = stats.get("files_scanned")
    max_file_count = stats.get("max_file_count")
    if max_file_count is None:
        checkpoint_stats = scanner.get("checkpoint", {}) if isinstance(scanner, dict) else {}
        if isinstance(checkpoint_stats, dict):
            max_file_count = checkpoint_stats.get("max_file_count")
    truncated = (
        isinstance(files_scanned, int)
        and isinstance(max_file_count, int)
        and files_scanned >= max_file_count
        and (files_total is None or files_total >= max_file_count)
    )

    return inventory, {
        "scanner_name": scanner.get("name"),
        "incremental": scanner.get("incremental"),
        "files_total": files_total,
        "files_scanned": files_scanned,
        "files_cached": stats.get("files_cached"),
        "files_rescanned": stats.get("files_rescanned"),
        "batches_processed": stats.get("batches_processed"),
        "max_file_count": max_file_count,
        "truncated_by_max_file_count": truncated,
        "input_fingerprint": _fingerprint(inventory),
        "checkpoint": checkpoint,
    }


def _knowledge_plan_metrics(
    repository_root: Path, source_inventory: dict[str, Any]
) -> dict[str, Any]:
    from repo_wiki.knowledge_plan import generate_plan, validate_plan
    from repo_wiki.scanner.knowledge_model_v3 import build_knowledge_model_v3

    knowledge_model = build_knowledge_model_v3(
        source_inventory,
        {"documents": []},
        {"conflicts": []},
    )
    plan = generate_plan(knowledge_model)
    issues = validate_plan(plan)
    directories = plan.get("directories", []) if isinstance(plan, dict) else []
    templates = plan.get("page_templates", []) if isinstance(plan, dict) else []
    docs = plan.get("docs", {}) if isinstance(plan, dict) else {}
    allowlist = docs.get("allowlist", []) if isinstance(docs, dict) else []
    domains = plan.get("business_domains", []) if isinstance(plan, dict) else []
    return {
        "plan_directory_count": len(directories) if isinstance(directories, list) else 0,
        "plan_template_count": len(templates) if isinstance(templates, list) else 0,
        "plan_domain_count": len(domains) if isinstance(domains, list) else 0,
        "plan_doc_count": len(allowlist) if isinstance(allowlist, list) else 0,
        "plan_fingerprint": (plan.get("generated") or {}).get("fingerprint"),
        "knowledge_model_fingerprint": (plan.get("model") or {}).get("fingerprint"),
        "knowledge_model_input_fingerprints": knowledge_model.get("input_fingerprints", {}),
        "validation_issue_count": len(issues),
        "validation_issues": [issue.as_dict() for issue in issues],
        "output_directory": str(repository_root / ".repo-wiki"),
    }


def _threshold_profile(
    *,
    profile_id: str,
    observed_effective_file_count: int | None,
    observed_git_file_count: int | None,
    contract_passed: bool,
    hard_10k_effective_files: int,
    stress_100k_git_files: int,
    gate_100k_stress: bool,
    measured_operation_metrics: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    if profile_id == THRESHOLD_PROFILE_STAGE0:
        return (
            {
                "id": THRESHOLD_PROFILE_STAGE0,
                "scope": "contract-only",
                "sample_count": 1 if contract_passed else 0,
                "production_scale_gate": "not_evaluated",
            },
            [],
        )

    reasons: list[str] = []
    source_scan = (measured_operation_metrics or {}).get("source_scan")
    if not isinstance(source_scan, dict):
        reasons.append(
            "tiered-10k-100k gate requires measured source-scan or knowledge-plan operation metrics"
        )
        observed_effective_file_count = None
        observed_git_file_count = None
    else:
        files_scanned = source_scan.get("files_scanned")
        files_total = source_scan.get("files_total")
        observed_effective_file_count = files_scanned if isinstance(files_scanned, int) else None
        observed_git_file_count = files_total if isinstance(files_total, int) else None
        if source_scan.get("truncated_by_max_file_count") is True:
            reasons.append(
                "source_scan truncated by max_file_count: "
                f"scanned {observed_effective_file_count}, "
                f"cap {source_scan.get('max_file_count')}"
            )

    hard_passed = (
        observed_effective_file_count is not None
        and observed_effective_file_count >= hard_10k_effective_files
    )
    stress_passed = (
        observed_git_file_count is not None and observed_git_file_count >= stress_100k_git_files
    )
    if not hard_passed:
        reasons.append(
            "hard_10k_effective_files gate failed: "
            f"observed {observed_effective_file_count}, "
            f"required {hard_10k_effective_files}"
        )
    if gate_100k_stress and not stress_passed:
        reasons.append(
            "stress_100k_git_files gate failed: "
            f"observed {observed_git_file_count}, required {stress_100k_git_files}"
        )

    profile = {
        "id": THRESHOLD_PROFILE_TIERED,
        "scope": "tiered-large-repo",
        "sample_count": 1 if contract_passed and not reasons else 0,
        "production_scale_gate": "passed" if contract_passed and not reasons else "failed",
        "hard_10k_effective_files": {
            "threshold": hard_10k_effective_files,
            "observed": observed_effective_file_count,
            "passed": hard_passed,
            "gating": True,
        },
        "stress_100k_git_files": {
            "threshold": stress_100k_git_files,
            "observed": observed_git_file_count,
            "passed": stress_passed,
            "gating": gate_100k_stress,
        },
        "reasons": reasons,
    }
    return profile, reasons


def run_scale_benchmark(
    fixture_root: Path,
    *,
    operation: str = "inventory",
    cache_policy: str = "cold",
    provider: str = "mock/replay",
    model: str = "not-applicable",
    network_condition: str = "offline",
    measured_run: bool = True,
    command_argv: list[str] | None = None,
    scanner_incremental: bool | None = None,
    threshold_profile: str = THRESHOLD_PROFILE_STAGE0,
    hard_10k_effective_files: int = 10_000,
    stress_100k_git_files: int = 100_000,
    gate_100k_stress: bool = False,
) -> dict[str, Any]:
    """Validate one fixture while recording machine-readable measurement evidence."""
    if operation not in OPERATIONS:
        raise ValueError(f"unsupported benchmark operation: {operation}")
    if threshold_profile not in {THRESHOLD_PROFILE_STAGE0, THRESHOLD_PROFILE_TIERED}:
        raise ValueError(f"unsupported threshold profile: {threshold_profile}")

    started = time.perf_counter()
    manifest, observed, reasons = load_and_validate_scale_fixture(fixture_root)
    operation_metrics: dict[str, Any] = {"operation": operation}
    repository_root = _fixture_repository_root(fixture_root, manifest)
    source_inventory: dict[str, Any] | None = None
    if operation in {"source-scan", "knowledge-plan"} and not reasons:
        with _isolated_measurement_repository(repository_root) as measurement_repository_root:
            operation_metrics["measurement_repository"] = {
                "path": str(measurement_repository_root.resolve()),
                "fixture_repository_path": str(repository_root.resolve()),
                "isolated": True,
            }
            incremental = scanner_incremental
            if incremental is None:
                incremental = cache_policy != "cold"
            source_inventory, source_metrics = _source_scan_metrics(
                measurement_repository_root, incremental=incremental
            )
            operation_metrics["source_scan"] = source_metrics
            if operation == "knowledge-plan":
                operation_metrics["knowledge_plan"] = _knowledge_plan_metrics(
                    measurement_repository_root, source_inventory
                )

    elapsed_seconds = time.perf_counter() - started
    peak_rss_bytes = _peak_rss_bytes()

    if not measured_run:
        reasons.append("run is marked as warmup, not a measured run")
    if peak_rss_bytes is None:
        reasons.append("peak RSS measurement is unavailable on this platform")

    reasons = list(dict.fromkeys(reasons))
    provenance = manifest.get("provenance", {}) if isinstance(manifest, dict) else {}
    inventory = manifest.get("inventory", {}) if isinstance(manifest, dict) else {}
    profile, threshold_reasons = _threshold_profile(
        profile_id=threshold_profile,
        observed_effective_file_count=observed.get("effective_file_count"),
        observed_git_file_count=observed.get("git_file_count"),
        contract_passed=not reasons,
        hard_10k_effective_files=hard_10k_effective_files,
        stress_100k_git_files=stress_100k_git_files,
        gate_100k_stress=gate_100k_stress,
        measured_operation_metrics=operation_metrics,
    )
    reasons = list(dict.fromkeys([*reasons, *threshold_reasons]))
    contract_status = "passed" if not reasons else "failed"
    if threshold_profile == THRESHOLD_PROFILE_STAGE0:
        profile["sample_count"] = 1 if contract_status == "passed" else 0
    report = {
        "schema_version": SCALE_BENCHMARK_SCHEMA_VERSION,
        "contract_version": SCALE_BENCHMARK_CONTRACT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "fixture": {
            "path": str(fixture_root.resolve()),
            "fixture_hash": manifest.get("fixture_hash") if manifest else None,
            "source": provenance.get("source"),
            "generator": provenance.get("generator"),
            "fixture_generated_at": provenance.get("generated_at"),
            "fixture_commit": provenance.get("fixture_commit"),
        },
        "environment": {
            "os": platform.system(),
            "os_release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "node": _node_version(),
            "cpu_count": os.cpu_count(),
            "total_memory_bytes": _total_memory_bytes(),
            "provider": provider,
            "model": model,
            "network_condition": network_condition,
        },
        "command": {
            "operation": operation,
            "legacy_operation": "validate-scale-fixture-inventory",
            "argv": command_argv or [],
            "cwd": str(Path.cwd().resolve()),
            "cache_policy": cache_policy,
            "measured_run": measured_run,
            "scanner_incremental": scanner_incremental,
        },
        "measurements": {
            "elapsed_seconds": round(elapsed_seconds, 6),
            "peak_rss_bytes": peak_rss_bytes,
            "exit_code": 0 if not reasons else 1,
            "operation_metrics": operation_metrics,
        },
        "inventory_evidence": {
            "expected_git_file_count": inventory.get("git_file_count"),
            "observed_git_file_count": observed.get("git_file_count"),
            "expected_effective_file_count": inventory.get("effective_file_count"),
            "observed_effective_file_count": observed.get("effective_file_count"),
            "expected_total_bytes": inventory.get("total_bytes"),
            "observed_total_bytes": observed.get("total_bytes"),
            "expected_inventory_hash": inventory.get("inventory_hash"),
            "observed_inventory_hash": observed.get("inventory_hash"),
            "file_type_distribution": observed.get("file_type_distribution", {}),
        },
        "threshold_profile": profile,
        "contract_status": contract_status,
        "gating_status": "gating" if contract_status == "passed" else "non_gating",
        "non_gating_reasons": reasons,
    }
    return report


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--operation", choices=OPERATIONS, default="inventory")
    parser.add_argument("--cache-policy", default="cold")
    parser.add_argument("--provider", default="mock/replay")
    parser.add_argument("--model", default="not-applicable")
    parser.add_argument("--network-condition", default="offline")
    parser.add_argument("--warmup", action="store_true")
    parser.add_argument(
        "--scanner-incremental",
        choices=("auto", "true", "false"),
        default="auto",
        help="Whether source-scan operations reuse scanner cache.",
    )
    parser.add_argument(
        "--threshold-profile",
        choices=(THRESHOLD_PROFILE_STAGE0, THRESHOLD_PROFILE_TIERED),
        default=THRESHOLD_PROFILE_STAGE0,
    )
    parser.add_argument("--hard-10k-effective-files", type=int, default=10_000)
    parser.add_argument("--stress-100k-git-files", type=int, default=100_000)
    parser.add_argument("--gate-100k-stress", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    raw_argv = sys.argv[1:] if argv is None else argv
    args = parse_args(raw_argv)
    scanner_incremental = {
        "auto": None,
        "true": True,
        "false": False,
    }[args.scanner_incremental]
    report = run_scale_benchmark(
        args.fixture,
        operation=args.operation,
        cache_policy=args.cache_policy,
        provider=args.provider,
        model=args.model,
        network_condition=args.network_condition,
        measured_run=not args.warmup,
        command_argv=[sys.executable, str(Path(__file__).resolve()), *raw_argv],
        scanner_incremental=scanner_incremental,
        threshold_profile=args.threshold_profile,
        hard_10k_effective_files=args.hard_10k_effective_files,
        stress_100k_git_files=args.stress_100k_git_files,
        gate_100k_stress=args.gate_100k_stress,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if report["contract_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
