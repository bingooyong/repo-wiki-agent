"""Tests for qoder fixture ingestion and validation."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from repo_wiki.generator.io import write_text
from scripts.qoder_fixture_ingestion import (
    FixtureIngestion,
    FixtureManifest,
    FixtureStatus,
    IngestionError,
    DiagnosticMessage,
    FixtureSchemaValidator,
    FixtureIntegrityChecker,
    PathNormalizer,
    create_fixture_metadata,
    REQUIRED_SECTIONS,
    REQUIRED_FILES,
    REQUIRED_METADATA_FIELDS,
    CURRENT_SCHEMA_VERSION,
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
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Create docs structure
    (root / "docs").mkdir(parents=True, exist_ok=True)

    # Create overview files
    write_text(root / "docs/00-overview.md", """# Overview

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
""")

    write_text(root / "docs/01-architecture.md", """# Architecture

## 系统分层

Three layers.

## 服务协作

Services work together.
""")

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
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Create docs structure (missing some sections)
    (root / "docs").mkdir(parents=True, exist_ok=True)

    write_text(root / "docs/00-overview.md", """# Overview

Some content.
""")

    write_text(root / "docs/01-architecture.md", """# Architecture

Some architecture content.
""")

    # Only create a few sections
    (root / "docs/sections").mkdir(parents=True, exist_ok=True)
    for section in REQUIRED_SECTIONS[:3]:
        section_dir = root / "docs/sections" / section
        section_dir.mkdir(parents=True, exist_ok=True)
        write_text(section_dir / "index.md", f"# {section.title()}\n")


def _create_malformed_fixture(root: Path) -> None:
    """Create a malformed fixture with invalid structure."""
    # Create invalid JSON metadata
    (root / "fixture_metadata.json").write_text(
        "{ invalid json }",
        encoding="utf-8"
    )

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
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            (root / "docs").mkdir(parents=True, exist_ok=True)

            validator = FixtureSchemaValidator(root)
            is_valid, diagnostics = validator.validate()

            assert is_valid is False
            missing_file_diags = [
                d for d in diagnostics
                if d.error == IngestionError.MISSING_REQUIRED_FILE and d.severity == "ERROR"
            ]
            assert len(missing_file_diags) > 0

    def test_missing_required_metadata_field_fails(self) -> None:
        """Test that missing required metadata fields fail validation."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # Metadata missing schema_version
            metadata = {
                "repository_name": "test",
                "repository_type": "python",
                "generated_at": "2026-04-18T00:00:00Z",
                "generator_version": "1.0.0",
            }
            (root / "fixture_metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            (root / "docs").mkdir(parents=True, exist_ok=True)
            (root / "docs/00-overview.md").write_text("# Overview", encoding="utf-8")
            (root / "docs/01-architecture.md").write_text("# Architecture", encoding="utf-8")

            validator = FixtureSchemaValidator(root)
            is_valid, diagnostics = validator.validate()

            assert is_valid is False
            missing_field_diags = [
                d for d in diagnostics
                if d.error == IngestionError.MISSING_REQUIRED_FIELD and "schema_version" in d.field_path
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
            assert manifest.integrity.file_count > 0
            assert manifest.integrity.total_chars > 0

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
