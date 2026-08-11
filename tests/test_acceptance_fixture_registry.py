from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from repo_wiki.verifier.acceptance_fixture_registry import (
    REQUIRED_REPO_CLASSES,
    AcceptanceFixtureRegistryError,
    validate_acceptance_fixture_registry,
)

REPO_CLASSES = tuple(sorted(REQUIRED_REPO_CLASSES))


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_artifacts(root: Path) -> dict[str, str]:
    paths: dict[str, str] = {}
    for index, repo_class in enumerate(REPO_CLASSES):
        path = f"qoder-baselines/{repo_class}/manifest.json"
        artifact = root / path
        artifact.parent.mkdir(parents=True, exist_ok=True)
        content = f'{{"repo_class":"{repo_class}","index":{index}}}\n'
        artifact.write_text(content, encoding="utf-8")
        paths[repo_class] = path
    return paths


def valid_entries(root: Path) -> list[dict[str, str]]:
    paths = write_artifacts(root)
    entries: list[dict[str, str]] = []
    for index, repo_class in enumerate(REPO_CLASSES):
        artifact_path = paths[repo_class]
        entries.append(
            {
                "fixture_id": f"fixture-{repo_class}",
                "repo_class": repo_class,
                "fixture_hash": sha(f"fixture:{repo_class}"),
                "revision": f"{index:040x}",
                "baseline_artifact_path": artifact_path,
                "baseline_artifact_hash": hashlib.sha256(
                    (root / artifact_path).read_bytes()
                ).hexdigest(),
                "generated_at": f"2026-07-15T08:3{index}:00Z",
                "qoder_version": "qoder-2026.07",
                "generator_identity": "qoder-repowiki-generator@sha256:abc123",
                "rubric_version": "qoder-rubric-v1",
            }
        )
    return entries


def test_valid_registry_reports_deterministic_fingerprint(tmp_path: Path) -> None:
    entries = valid_entries(tmp_path)

    report = validate_acceptance_fixture_registry(
        list(reversed(entries)), artifact_root=tmp_path, validate_filesystem=True
    )
    same_report = validate_acceptance_fixture_registry(
        entries, artifact_root=tmp_path, validate_filesystem=True
    )

    assert report.fingerprint == same_report.fingerprint
    assert report.entry_count == 5
    assert set(report.registered_repo_classes) == REQUIRED_REPO_CLASSES
    assert report.to_dict()["fingerprint"] == report.fingerprint
    assert "fixture-java_kotlin_service" in report.to_json()


@pytest.mark.parametrize("missing_class", REPO_CLASSES)
def test_rejects_missing_required_repo_class(tmp_path: Path, missing_class: str) -> None:
    entries = [entry for entry in valid_entries(tmp_path) if entry["repo_class"] != missing_class]

    with pytest.raises(AcceptanceFixtureRegistryError, match="missing required repository classes"):
        validate_acceptance_fixture_registry(entries)


def test_rejects_duplicate_fixture_hash(tmp_path: Path) -> None:
    entries = valid_entries(tmp_path)
    entries[1]["fixture_hash"] = entries[0]["fixture_hash"]

    with pytest.raises(AcceptanceFixtureRegistryError, match="Duplicate fixture hash"):
        validate_acceptance_fixture_registry(entries)


def test_rejects_duplicate_repo_class(tmp_path: Path) -> None:
    entries = valid_entries(tmp_path)
    entries[1]["repo_class"] = entries[0]["repo_class"]

    with pytest.raises(AcceptanceFixtureRegistryError, match="Duplicate repository class"):
        validate_acceptance_fixture_registry(entries)


@pytest.mark.parametrize(
    "field",
    [
        "revision",
        "generated_at",
        "qoder_version",
        "generator_identity",
        "rubric_version",
    ],
)
def test_rejects_missing_provenance(tmp_path: Path, field: str) -> None:
    entries = valid_entries(tmp_path)
    entries[0][field] = ""

    with pytest.raises(AcceptanceFixtureRegistryError, match="Missing provenance field"):
        validate_acceptance_fixture_registry(entries)


def test_rejects_missing_provenance_key(tmp_path: Path) -> None:
    entries = valid_entries(tmp_path)
    del entries[0]["qoder_version"]

    with pytest.raises(AcceptanceFixtureRegistryError, match="missing required provenance fields"):
        validate_acceptance_fixture_registry(entries)


@pytest.mark.parametrize(
    "artifact_path",
    [
        "../outside.json",
        "qoder-baselines/../../outside.json",
        "/absolute/manifest.json",
        "./qoder-baselines/manifest.json",
        "qoder-baselines\\manifest.json",
        "qoder-baselines//manifest.json",
    ],
)
def test_rejects_noncanonical_or_escaping_artifact_paths(
    tmp_path: Path, artifact_path: str
) -> None:
    entries = valid_entries(tmp_path)
    entries[0]["baseline_artifact_path"] = artifact_path

    with pytest.raises(AcceptanceFixtureRegistryError, match="artifact path"):
        validate_acceptance_fixture_registry(entries)


def test_rejects_baseline_hash_drift_against_filesystem(tmp_path: Path) -> None:
    entries = valid_entries(tmp_path)
    drift_path = entries[0]["baseline_artifact_path"]
    (tmp_path / drift_path).write_text("mutated baseline\n", encoding="utf-8")

    with pytest.raises(AcceptanceFixtureRegistryError, match="hash drift"):
        validate_acceptance_fixture_registry(
            entries, artifact_root=tmp_path, validate_filesystem=True
        )
