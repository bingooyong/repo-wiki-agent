"""Tests for qoder fixture ingestion and validation."""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from repo_wiki.generator.io import write_text
from scripts.qoder_fixture_ingestion import (
    CURRENT_SCHEMA_VERSION,
    FRESHNESS_THRESHOLDS,
    FRESSHNESS_THRESHOLDS,
    REQUIRED_METADATA_FIELDS,
    REQUIRED_SECTIONS,
    ConfidenceScorer,
    FixtureIngestion,
    FixtureIntegrityChecker,
    FixtureSchemaValidator,
    FixtureStatus,
    IngestionError,
    PathNormalizer,
    create_fixture_metadata,
)


def _create_valid_fixture(root: Path) -> None:
    """Create a valid fixture with all required elements."""
    # Create fixture metadata
    metadata = create_fixture_metadata(
        repository_name="test-repo",
        repository_type="python",
        generator_version="1.0.0",
        language="python",
        complexity_score=0.75,
        size_category="medium",
    )
    (root / "fixture_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Create docs structure
    (root / "docs").mkdir(parents=True, exist_ok=True)

    # Create overview files
    write_text(
        root / "docs/00-overview.md",
        """# Overview

## 项目定位

This is a test project.

## 核心问题

We need better docs.

## 核心能力

The system can generate docs.

## 快速开始

Run poetry install.

## 阅读导航

See architecture.
""",
    )

    write_text(
        root / "docs/01-architecture.md",
        """# Architecture

## 系统分层

Three layers.

## 服务协作

Services work together.
""",
    )

    # Create sections
    (root / "docs/sections").mkdir(parents=True, exist_ok=True)
    for section in REQUIRED_SECTIONS:
        section_dir = root / "docs/sections" / section
        section_dir.mkdir(parents=True, exist_ok=True)
        write_text(
            section_dir / "index.md",
            f"""# {section.title()}

## Navigation

- [Overview](../../00-overview.md)

Content for {section}.
""",
        )


def _write_hash_tree(root: Path, files: dict[str, str]) -> None:
    """Write a small markdown tree used by fixture hash regression tests."""
    for relative_path, content in files.items():
        write_text(root / relative_path, content)


def _create_partial_fixture(root: Path) -> None:
    """Create a partial fixture with missing elements."""
    # Create fixture metadata with missing optional fields
    metadata = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "repository_name": "partial-repo",
        "repository_type": "python",
        "generated_at": "2026-04-18T00:00:00Z",
        "generator_version": "1.0.0",
    }
    (root / "fixture_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Create docs structure (missing some sections)
    (root / "docs").mkdir(parents=True, exist_ok=True)

    write_text(
        root / "docs/00-overview.md",
        """# Overview

Some content.
""",
    )

    write_text(
        root / "docs/01-architecture.md",
        """# Architecture

Some architecture content.
""",
    )

    # Only create a few sections
    (root / "docs/sections").mkdir(parents=True, exist_ok=True)
    for section in REQUIRED_SECTIONS[:3]:
        section_dir = root / "docs/sections" / section
        section_dir.mkdir(parents=True, exist_ok=True)
        write_text(section_dir / "index.md", f"# {section.title()}\n")


def _create_malformed_fixture(root: Path) -> None:
    """Create a malformed fixture with invalid structure."""
    # Create invalid JSON metadata
    (root / "fixture_metadata.json").write_text("{ invalid json }", encoding="utf-8")

    # Create minimal docs
    (root / "docs").mkdir(parents=True, exist_ok=True)
    write_text(root / "docs/00-overview.md", "# Overview\n")


class TestFixtureSchemaValidation:
    """Test fixture schema validation."""

    def test_valid_fixture_passes_validation(self) -> None:
        """Test that a valid fixture passes all validation checks."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_valid_fixture(root)

            validator = FixtureSchemaValidator(root)
            is_valid, diagnostics = validator.validate()

            assert is_valid is True
            error_diags = [d for d in diagnostics if d.severity == "ERROR"]
            assert len(error_diags) == 0

    def test_missing_metadata_file_fails_validation(self) -> None:
        """Test that missing fixture_metadata.json fails validation."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir(parents=True, exist_ok=True)
            (root / "docs/00-overview.md").write_text("# Overview", encoding="utf-8")

            validator = FixtureSchemaValidator(root)
            is_valid, diagnostics = validator.validate()

            assert is_valid is False
            errors = [d for d in diagnostics if d.error == IngestionError.MISSING_REQUIRED_FILE]
            assert any("fixture_metadata.json" in d.field_path for d in errors)

    def test_invalid_json_metadata_fails_validation(self) -> None:
        """Test that invalid JSON in metadata fails validation."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fixture_metadata.json").write_text("{ invalid }", encoding="utf-8")

            validator = FixtureSchemaValidator(root)
            is_valid, diagnostics = validator.validate()

            assert is_valid is False

    def test_missing_required_file_fails_validation(self) -> None:
        """Test that missing required files fail validation."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # Create valid metadata but missing required files
            metadata = create_fixture_metadata(
                repository_name="test",
                repository_type="python",
                generator_version="1.0.0",
            )
            (root / "fixture_metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (root / "docs").mkdir(parents=True, exist_ok=True)

            validator = FixtureSchemaValidator(root)
            is_valid, diagnostics = validator.validate()

            assert is_valid is False
            missing_file_diags = [
                d
                for d in diagnostics
                if d.error == IngestionError.MISSING_REQUIRED_FILE and d.severity == "ERROR"
            ]
            assert len(missing_file_diags) > 0

    def test_missing_required_core_metadata_field_fails(self) -> None:
        """Test that missing non-provenance metadata still fails validation."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # Metadata missing repository_name
            metadata = {
                "schema_version": CURRENT_SCHEMA_VERSION,
                "contract_version": "qoder.fixture_provenance/1.1",
                "repository_type": "python",
                "source": "test",
                "generated_at": "2026-04-18T00:00:00Z",
                "generator_version": "1.0.0",
            }
            (root / "fixture_metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (root / "docs").mkdir(parents=True, exist_ok=True)
            (root / "docs/00-overview.md").write_text("# Overview", encoding="utf-8")
            (root / "docs/01-architecture.md").write_text("# Architecture", encoding="utf-8")

            validator = FixtureSchemaValidator(root)
            is_valid, diagnostics = validator.validate()

            assert is_valid is False
            missing_field_diags = [
                d
                for d in diagnostics
                if d.error == IngestionError.MISSING_REQUIRED_FIELD
                and "repository_name" in d.field_path
            ]
            assert len(missing_field_diags) > 0


class TestFixtureIngestion:
    """Test complete fixture ingestion."""

    def test_valid_fixture_produces_valid_manifest(self) -> None:
        """Test that a valid fixture produces a VALID manifest."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_valid_fixture(root)

            ingestion = FixtureIngestion(root)
            manifest = ingestion.ingest()

            assert manifest.status == FixtureStatus.VALID
            assert manifest.is_valid() is True
            assert manifest.is_usable() is True

    def test_partial_fixture_produces_partial_manifest(self) -> None:
        """Test that a partial fixture produces a PARTIAL manifest."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_partial_fixture(root)

            ingestion = FixtureIngestion(root)
            manifest = ingestion.ingest()

            assert manifest.status == FixtureStatus.PARTIAL
            assert manifest.is_valid() is False
            assert manifest.is_usable() is True

    def test_malformed_fixture_produces_invalid_manifest(self) -> None:
        """Test that a malformed fixture produces an INVALID manifest."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_malformed_fixture(root)

            ingestion = FixtureIngestion(root)
            manifest = ingestion.ingest()

            assert manifest.status == FixtureStatus.INVALID
            assert manifest.is_valid() is False
            assert manifest.is_usable() is False

    def test_manifest_contains_integrity_info(self) -> None:
        """Test that manifest contains integrity information."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_valid_fixture(root)

            ingestion = FixtureIngestion(root)
            manifest = ingestion.ingest()

            assert manifest.integrity.content_hash is not None
            assert manifest.integrity.structure_hash is not None
            assert manifest.integrity.fixture_hash is not None
            assert len(manifest.integrity.fixture_hash) == 64
            assert manifest.integrity.file_count > 0
            assert manifest.integrity.total_chars > 0

    def test_manifest_exposes_explicit_provenance_contract(self) -> None:
        """Test that manifests expose stable provenance and contract metadata."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_valid_fixture(root)

            manifest = FixtureIngestion(root).ingest()
            manifest_dict = manifest.to_dict()

            assert manifest_dict["schema_version"] == "qoder.fixture_manifest/1.1"
            assert manifest_dict["contract_version"] == "qoder.fixture_provenance/1.1"
            assert manifest_dict["provenance"]["source"] == "test-repo"
            assert manifest_dict["provenance"]["generator"] == "1.0.0"
            assert manifest_dict["provenance"]["fixture_hash"] == manifest.integrity.fixture_hash
            assert manifest_dict["provenance"]["hash_algorithm"] == "qoder.fixture_hash/2"
            assert manifest_dict["integrity"]["hash_algorithm"] == "qoder.fixture_hash/2"
            assert manifest_dict["gating"]["eligible"] is True

    def test_legacy_metadata_without_source_ingests_but_gate_rejects(self) -> None:
        """Old metadata remains usable for ingestion but not for gate contexts."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_valid_fixture(root)
            metadata_path = root / "fixture_metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata.pop("source", None)
            metadata.pop("fixture_source", None)
            metadata["generated_at"] = datetime.now(UTC).isoformat()
            metadata_path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            manifest = FixtureIngestion(root).ingest()
            decision = ConfidenceScorer.get_release_gate_decision(manifest, "pilot")

            assert manifest.status == FixtureStatus.PARTIAL
            assert manifest.is_usable() is True
            assert any(d.error == IngestionError.MISSING_PROVENANCE for d in manifest.diagnostics)
            assert decision["decision"] == "REJECTED"
            assert any("source provenance" in reason for reason in decision["rejection_reasons"])

    def test_legacy_metadata_missing_provenance_fields_ingests_partial(self) -> None:
        """Missing legacy provenance fields warn on import and fail the release gate."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_valid_fixture(root)
            metadata_path = root / "fixture_metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            for field_name in (
                "schema_version",
                "contract_version",
                "source",
                "generator",
                "generator_version",
                "generated_at",
            ):
                metadata.pop(field_name, None)
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

            manifest = FixtureIngestion(root).ingest()
            decision = ConfidenceScorer.get_release_gate_decision(manifest, "pilot")

            assert manifest.status == FixtureStatus.PARTIAL
            assert manifest.is_usable() is True
            assert decision["decision"] == "REJECTED"
            reasons = "\n".join(decision["rejection_reasons"])
            assert "schema_version" in reasons
            assert "contract_version" in reasons
            assert "source provenance" in reasons
            assert "generator provenance" in reasons
            assert "generated_at provenance" in reasons

    def test_invalid_provenance_values_are_rejected(self) -> None:
        """Present-but-invalid provenance never satisfies the release gate."""
        cases = (
            ("source", ["not", "a", "string"], "source"),
            ("generated_at", 123, "generated_at"),
            ("generated_at", "not-a-timestamp", "generated_at"),
            ("schema_version", {"invalid": True}, "schema_version"),
            ("schema_version", "99.0", "schema_version"),
            ("contract_version", 123, "contract_version"),
            (
                "contract_version",
                "qoder.fixture_provenance/99.0",
                "contract_version",
            ),
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, (field_name, value, reason_fragment) in enumerate(cases):
                case_root = root / str(index)
                case_root.mkdir()
                _create_valid_fixture(case_root)
                metadata_path = case_root / "fixture_metadata.json"
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                metadata[field_name] = value
                metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

                manifest = FixtureIngestion(case_root).ingest()
                decision = ConfidenceScorer.get_release_gate_decision(manifest, "pilot")

                assert manifest.status == FixtureStatus.INVALID, field_name
                assert decision["decision"] == "REJECTED", field_name
                assert any(reason_fragment in reason for reason in decision["rejection_reasons"]), (
                    field_name
                )

    def test_invalid_generator_does_not_override_generator_version(self) -> None:
        """A malformed generator alias is rejected without replacing a valid fallback."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_valid_fixture(root)
            metadata_path = root / "fixture_metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["generator"] = {"invalid": True}
            metadata["generator_version"] = "generator-v1"
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

            manifest = FixtureIngestion(root).ingest()
            decision = ConfidenceScorer.get_release_gate_decision(manifest, "pilot")

            assert manifest.metadata.generator_version == "generator-v1"
            assert manifest.status == FixtureStatus.INVALID
            assert decision["decision"] == "REJECTED"
            assert manifest.to_dict()["gating"]["eligible"] is False
            assert any(
                "generator" in reason
                for reason in manifest.to_dict()["gating"]["non_gating_reasons"]
            )
            assert any(
                diagnostic.field_path == "metadata.generator"
                and diagnostic.error == IngestionError.INVALID_FIELD_TYPE
                for diagnostic in manifest.diagnostics
            )

    def test_declared_fixture_hash_mismatch_is_rejected(self) -> None:
        """A metadata-declared hash must match the framed computed hash."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_valid_fixture(root)
            metadata_path = root / "fixture_metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["fixture_hash"] = "0" * 64
            metadata["hash_algorithm"] = "qoder.fixture_hash/2"
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

            manifest = FixtureIngestion(root).ingest()
            decision = ConfidenceScorer.get_release_gate_decision(manifest, "pilot")
            manifest_dict = manifest.to_dict()

            assert manifest.status == FixtureStatus.INVALID
            assert manifest_dict["provenance"]["hash_mismatch"] is True
            assert manifest_dict["gating"]["eligible"] is False
            assert decision["decision"] == "REJECTED"
            assert any("fixture_hash" in reason for reason in decision["rejection_reasons"])

    def test_freshness_threshold_typo_alias_is_preserved(self) -> None:
        """The corrected freshness constant keeps the old misspelled alias."""
        assert FRESSHNESS_THRESHOLDS is FRESHNESS_THRESHOLDS

    def test_manifest_contains_diagnostics(self) -> None:
        """Test that manifest contains diagnostic messages."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_partial_fixture(root)

            ingestion = FixtureIngestion(root)
            manifest = ingestion.ingest()

            # Partial fixture should have warnings
            warning_diags = [d for d in manifest.diagnostics if d.severity == "WARNING"]
            assert len(warning_diags) > 0


class TestFixtureIntegrityChecker:
    """Test integrity computation."""

    def test_content_hash_is_deterministic(self) -> None:
        """Test that content hash is deterministic."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_valid_fixture(root)

            hash1 = FixtureIntegrityChecker.compute_content_hash(root)
            hash2 = FixtureIntegrityChecker.compute_content_hash(root)

            assert hash1 == hash2

    def test_different_content_produces_different_hash(self) -> None:
        """Test that different content produces different hash."""
        with tempfile.TemporaryDirectory() as tmp:
            root1 = Path(tmp) / "fixture1"
            root2 = Path(tmp) / "fixture2"
            root1.mkdir(parents=True)
            root2.mkdir(parents=True)

            write_text(root1 / "docs/00-overview.md", "# Content A")
            write_text(root2 / "docs/00-overview.md", "# Content B")

            hash1 = FixtureIntegrityChecker.compute_content_hash(root1)
            hash2 = FixtureIntegrityChecker.compute_content_hash(root2)

            assert hash1 != hash2

    def test_structure_hash_captures_directory_structure(self) -> None:
        """Test that structure hash captures directory layout."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir(parents=True, exist_ok=True)
            (root / "docs/sections").mkdir(parents=True, exist_ok=True)
            (root / "docs/sections/project").mkdir(parents=True, exist_ok=True)
            write_text(root / "docs/00-overview.md", "# Overview")
            write_text(root / "docs/sections/project/index.md", "# Project")

            structure_hash = FixtureIntegrityChecker.compute_structure_hash(root)

            assert structure_hash is not None
            assert len(structure_hash) == 64  # SHA256 hex length

    def test_fixture_hash_is_root_independent(self) -> None:
        """Identical relative trees hash the same under different roots."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first"
            second = root / "nested" / "second"
            files = {
                "docs/a.md": "alpha",
                "docs/README.MD": "uppercase extension",
                "docs/sections/project/index.md": "beta",
            }
            _write_hash_tree(first, files)
            _write_hash_tree(second, files)

            first_hash = FixtureIntegrityChecker.compute_integrity(first).fixture_hash
            second_hash = FixtureIntegrityChecker.compute_integrity(second).fixture_hash

            assert first_hash == second_hash
            assert FixtureIntegrityChecker.compute_integrity(first).file_count == 3

    def test_fixture_hash_changes_with_content_or_relative_path(self) -> None:
        """Fixture hashes bind both bytes and relative POSIX paths."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "original"
            content_changed = root / "content-changed"
            path_changed = root / "path-changed"
            _write_hash_tree(original, {"docs/a.md": "same"})
            _write_hash_tree(content_changed, {"docs/a.md": "different"})
            _write_hash_tree(path_changed, {"docs/renamed.md": "same"})

            original_hash = FixtureIntegrityChecker.compute_integrity(original).fixture_hash

            assert (
                FixtureIntegrityChecker.compute_integrity(content_changed).fixture_hash
                != original_hash
            )
            assert (
                FixtureIntegrityChecker.compute_integrity(path_changed).fixture_hash
                != original_hash
            )

    def test_content_hash_frames_file_boundaries(self) -> None:
        """Different file boundaries cannot collide through raw concatenation."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first"
            second = root / "second"
            _write_hash_tree(first, {"a.md": "ab", "b.md": "c"})
            _write_hash_tree(second, {"a.md": "a", "b.md": "bc"})

            assert "ab" + "c" == "a" + "bc"
            assert FixtureIntegrityChecker.compute_content_hash(
                first
            ) != FixtureIntegrityChecker.compute_content_hash(second)


class TestPathNormalizer:
    """Test path normalization."""

    def test_normalize_produces_consistent_structure(self) -> None:
        """Test that normalization produces expected structure."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_valid_fixture(root)

            normalized = PathNormalizer.normalize(root)

            assert "root" in normalized
            assert "docs" in normalized
            assert "sections" in normalized
            assert "overview_files" in normalized
            assert "section_files" in normalized
            assert "00-overview.md" in normalized["overview_files"]
            assert "01-architecture.md" in normalized["overview_files"]

    def test_normalize_captures_all_sections(self) -> None:
        """Test that normalization captures all section paths."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_valid_fixture(root)

            normalized = PathNormalizer.normalize(root)

            for section in REQUIRED_SECTIONS:
                assert section in normalized["section_files"]


class TestCreateFixtureMetadata:
    """Test fixture metadata creation helper."""

    def test_create_metadata_has_required_fields(self) -> None:
        """Test that created metadata has all required fields."""
        metadata = create_fixture_metadata(
            repository_name="test-repo",
            repository_type="python",
            generator_version="1.0.0",
        )

        for field_name in REQUIRED_METADATA_FIELDS:
            assert field_name in metadata

    def test_create_metadata_has_current_schema_version(self) -> None:
        """Test that created metadata has current schema version."""
        metadata = create_fixture_metadata(
            repository_name="test-repo",
            repository_type="python",
            generator_version="1.0.0",
        )

        assert metadata["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_create_metadata_includes_custom_fields(self) -> None:
        """Test that custom fields can be specified."""
        metadata = create_fixture_metadata(
            repository_name="test-repo",
            repository_type="python",
            generator_version="1.0.0",
        )

        assert "custom_fields" in metadata
        assert isinstance(metadata["custom_fields"], dict)
