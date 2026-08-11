"""JSON shape tests for repo-agent release meta contracts (Phase 41.2)."""

from __future__ import annotations

import json
from pathlib import Path

from repo_wiki.orchestration import release_meta_schema as rms

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "release_meta"


def _load(name: str) -> object:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class TestReleaseMetaFixturesValid:
    def test_all_valid_fixtures_pass(self) -> None:
        cases = [
            ("minimal-repowiki-metadata.json", "repowiki-metadata.json"),
            ("valid-navigation.json", "navigation.json"),
            ("valid-page-registry.json", "page-registry.json"),
            ("valid-source-inventory.json", "source-inventory.json"),
            ("valid-docs-inventory.json", "docs-inventory.json"),
            ("valid-service-registry.json", "service-registry.json"),
            ("valid-api-inventory.json", "api-inventory.json"),
            ("valid-data-model-inventory.json", "data-model-inventory.json"),
            ("valid-evidence-index.json", "evidence-index.json"),
            ("valid-diagram-index.json", "diagram-index.json"),
            ("valid-quality-report.json", "quality-report.json"),
            ("valid-release.json", "release.json"),
        ]
        for file_name, meta_name in cases:
            data = _load(file_name)
            errors = rms.validate_meta_file(meta_name, data)
            assert errors == [], f"{file_name}: {errors}"

    def test_dispatch_by_path_basename(self) -> None:
        data = _load("valid-navigation.json")
        assert rms.validate_meta_file("meta/navigation.json", data) == []

    def test_unknown_file_errors(self) -> None:
        errors = rms.validate_meta_file("unknown.json", {})
        assert errors != []
        assert "unknown meta filename" in errors[0]
        assert "known:" in errors[0]


class TestReleaseMetaInvalid:
    def test_wrong_navigation_schema_version(self) -> None:
        data = _load("invalid-navigation-wrong-schema-version.json")
        errors = rms.validate_meta_file("navigation.json", data)
        assert any("schema_version" in e for e in errors)

    def test_repowiki_metadata_missing_key(self) -> None:
        data = {"wiki_catalogs": []}
        errors = rms.validate_repowiki_metadata(data)
        assert any("missing required keys" in e for e in errors)


class TestSchemaVersionHelper:
    def test_is_valid_repo_agent_schema_version(self) -> None:
        assert rms.is_valid_repo_agent_schema_version("repo_agent.navigation/1.0")
        assert not rms.is_valid_repo_agent_schema_version("not-a-version")


class TestQoderInvariantCrossCheck:
    """Ensure Qoder fixture invariant keys stay aligned with validator."""

    def test_fixture_lists_required_keys_subset(self) -> None:
        inv = json.loads(
            Path("tests/fixtures/qoder_release_interface_invariants.json").read_text(
                encoding="utf-8"
            )
        )
        required = set(inv["meta_repowiki_metadata"]["required_top_level_keys"])
        assert required == rms.QODER_REPOWIKI_METADATA_REQUIRED_KEYS
