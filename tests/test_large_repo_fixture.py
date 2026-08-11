from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.large_repo_fixture import (
    GENERATOR_ID,
    SCALE_FIXTURE_CONTRACT_VERSION,
    SCALE_FIXTURE_SCHEMA_VERSION,
    generate_scale_fixture,
    load_and_validate_scale_fixture,
)


def test_scale_fixture_is_deterministic_across_roots(tmp_path: Path) -> None:
    generated_at = "2026-07-14T00:00:00+00:00"
    first = generate_scale_fixture(
        tmp_path / "first",
        effective_file_count=9,
        git_file_count=13,
        seed=17,
        generated_at=generated_at,
    )
    second = generate_scale_fixture(
        tmp_path / "nested" / "second",
        effective_file_count=9,
        git_file_count=13,
        seed=17,
        generated_at=generated_at,
    )

    assert first["fixture_hash"] == second["fixture_hash"]
    assert first["inventory"] == second["inventory"]
    assert first["inventory"]["git_file_count"] == 13
    assert first["inventory"]["effective_file_count"] == 9
    assert len(first["inventory"]["expected_effective_files"]) == 9
    assert first["schema_version"] == SCALE_FIXTURE_SCHEMA_VERSION
    assert first["contract_version"] == SCALE_FIXTURE_CONTRACT_VERSION
    assert first["provenance"]["source"] == "synthetic:deterministic-scale"
    assert first["provenance"]["generator"] == GENERATOR_ID
    assert first["provenance"]["fixture_commit"] == "synthetic-seed:17"


def test_scale_fixture_hash_changes_with_seed(tmp_path: Path) -> None:
    first = generate_scale_fixture(
        tmp_path / "first", effective_file_count=3, git_file_count=5, seed=1
    )
    second = generate_scale_fixture(
        tmp_path / "second", effective_file_count=3, git_file_count=5, seed=2
    )

    assert first["fixture_hash"] != second["fixture_hash"]


def test_scale_fixture_validation_detects_content_drift(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixture"
    manifest = generate_scale_fixture(
        fixture_root, effective_file_count=4, git_file_count=6, seed=3
    )
    changed = fixture_root / "repository" / manifest["inventory"]["expected_effective_files"][0]
    changed.write_text("changed\n", encoding="utf-8")

    _, observed, reasons = load_and_validate_scale_fixture(fixture_root)

    assert observed["git_file_count"] == 6
    assert "fixture inventory mismatch: inventory_hash" in reasons
    assert "fixture_hash does not match observed inventory_hash" in reasons


@pytest.mark.parametrize(
    ("field_name", "value", "reason"),
    [
        ("source", ["invalid"], "provenance.source must be a non-empty string"),
        ("generator", None, "provenance.generator must be a non-empty string"),
        (
            "generated_at",
            "2026-07-14T00:00:00",
            "provenance.generated_at must be a timezone-aware ISO timestamp",
        ),
        (
            "fixture_commit",
            123,
            "provenance.fixture_commit must be a non-empty string",
        ),
    ],
)
def test_scale_fixture_validation_rejects_malformed_provenance(
    tmp_path: Path, field_name: str, value: object, reason: str
) -> None:
    fixture_root = tmp_path / field_name
    generate_scale_fixture(fixture_root, effective_file_count=3, git_file_count=5)
    manifest_path = fixture_root / "fixture-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["provenance"][field_name] = value
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    _, _, reasons = load_and_validate_scale_fixture(fixture_root)

    assert reason in reasons


def test_scale_fixture_validation_rejects_invalid_hash_and_parameters(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixture"
    generate_scale_fixture(fixture_root, effective_file_count=3, git_file_count=5)
    manifest_path = fixture_root / "fixture-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["fixture_hash"] = ["invalid"]
    manifest["parameters"]["effective_file_count"] = 4
    manifest["parameters"]["git_file_count"] = 6
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    _, _, reasons = load_and_validate_scale_fixture(fixture_root)

    assert "fixture_hash must be a 64-character SHA-256 hex digest" in reasons
    assert "fixture parameter mismatch: effective_file_count" in reasons
    assert "fixture parameter mismatch: git_file_count" in reasons


def test_scale_fixture_emits_language_specific_source_shapes(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixture"
    manifest = generate_scale_fixture(
        fixture_root,
        effective_file_count=8,
        git_file_count=8,
        seed=7,
    )
    repository_root = fixture_root / "repository"
    content_by_suffix = {
        Path(relative_path).suffix: (repository_root / relative_path).read_text(encoding="utf-8")
        for relative_path in manifest["inventory"]["expected_effective_files"]
    }

    assert content_by_suffix[".py"].startswith("def fixture_7_0()")
    assert content_by_suffix[".ts"].startswith("export const fixture_7_1")
    assert content_by_suffix[".go"].startswith("package fixture\n")
    assert "final class Fixture_7_3" in content_by_suffix[".java"]
    assert content_by_suffix[".kt"].startswith("package fixture\n")
    assert "namespace Fixture" in content_by_suffix[".cs"]
    assert content_by_suffix[".rs"].startswith("pub const FIXTURE_7_6")
    assert content_by_suffix[".md"].startswith("# fixture_7_7")


@pytest.mark.parametrize(
    ("effective_files", "git_files"),
    [(0, 1), (2, 1)],
)
def test_scale_fixture_rejects_invalid_counts(
    tmp_path: Path, effective_files: int, git_files: int
) -> None:
    with pytest.raises(ValueError):
        generate_scale_fixture(
            tmp_path / "invalid",
            effective_file_count=effective_files,
            git_file_count=git_files,
        )


def test_scale_fixture_cli_writes_machine_readable_manifest(tmp_path: Path) -> None:
    output = tmp_path / "cli-fixture"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/large_repo_fixture.py",
            "--output",
            str(output),
            "--effective-files",
            "3",
            "--git-files",
            "5",
            "--generated-at",
            "2026-07-14T00:00:00+00:00",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads((output / "fixture-manifest.json").read_text(encoding="utf-8"))
    assert payload["inventory"]["git_file_count"] == 5
    assert payload["inventory"]["effective_file_count"] == 3
