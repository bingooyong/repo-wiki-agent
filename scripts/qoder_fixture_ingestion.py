#!/usr/bin/env python3
"""
Qoder Fixture Ingestion Tool (Phase 14)

Provides fixture contract validation, normalization, and ingestion for
external qoder-style baseline snapshots used in comparison benchmarking.

Key Features:
- Fixture schema validation with required metadata and integrity fields
- Path normalization for stable cross-repository comparisons
- Rejection of incomplete/inconsistent fixtures with diagnostic messages
- Lifecycle management and refresh policy support

Usage:
    python scripts/qoder_fixture_ingestion.py \
        --fixture /path/to/qoder_snapshot \
        --validate-only

    python scripts/qoder_fixture_ingestion.py \
        --fixture /path/to/qoder_snapshot \
        --output /path/to/normalized_fixture.json

Schema Version: 1.0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class FixtureStatus(Enum):
    VALID = "VALID"
    PARTIAL = "PARTIAL"
    INVALID = "INVALID"
    MALFORMED = "MALFORMED"


class IngestionError(Enum):
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FIELD_TYPE = "INVALID_FIELD_TYPE"
    MISSING_REQUIRED_FILE = "MISSING_REQUIRED_FILE"
    INCONSISTENT_STRUCTURE = "INCONSISTENT_STRUCTURE"
    INTEGRITY_HASH_MISMATCH = "INTEGRITY_HASH_MISMATCH"
    SCHEMA_VERSION_MISMATCH = "SCHEMA_VERSION_MISMATCH"
    UNSUPPORTED_SCHEMA_VERSION = "UNSUPPORTED_SCHEMA_VERSION"
    MALFORMED = "MALFORMED"


# Required metadata fields for fixture validity
REQUIRED_METADATA_FIELDS = [
    "schema_version",
    "repository_name",
    "repository_type",
    "generated_at",
    "generator_version",
]

# Required structural elements
REQUIRED_FILES = [
    "docs/00-overview.md",
    "docs/01-architecture.md",
]

# Required sections (at least these must be present)
REQUIRED_SECTIONS = [
    "project", "architecture", "services", "data-model",
    "api", "operations", "development", "security", "troubleshooting"
]

# Supported schema versions
SUPPORTED_SCHEMA_VERSIONS = ["1.0", "1.1"]

# Current schema version
CURRENT_SCHEMA_VERSION = "1.0"

# Freshness thresholds (in days)
FRESSHNESS_THRESHOLDS = {
    "strict": 7,        # 7 days for strict profile
    "transitional": 30, # 30 days for transitional profile
    "pilot": 90,        # 90 days for pilot profile
}

# Confidence score thresholds (0.0 - 1.0)
CONFIDENCE_THRESHOLDS = {
    "high": 0.90,       # >= 90% confidence
    "medium": 0.70,     # >= 70% confidence
    "low": 0.50,        # >= 50% confidence
    "unacceptable": 0.0 # below 50%
}

# Maximum acceptable age for fixtures by profile (days)
MAX_FIXTURE_AGE = {
    "strict": 7,
    "transitional": 30,
    "pilot": 90,
}


@dataclass
class DiagnosticMessage:
    """Represents a diagnostic message for fixture validation."""
    error: IngestionError
    field_path: str
    message: str
    severity: str = "ERROR"  # ERROR, WARNING, INFO
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.error.value,
            "field_path": self.field_path,
            "message": self.message,
            "severity": self.severity,
            "context": self.context,
        }


@dataclass
class FixtureIntegrity:
    """Integrity information for a fixture."""
    content_hash: str
    structure_hash: str
    file_count: int
    total_chars: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_hash": self.content_hash,
            "structure_hash": self.structure_hash,
            "file_count": self.file_count,
            "total_chars": self.total_chars,
        }


@dataclass
class FixtureMetadata:
    """Metadata for a qoder fixture snapshot."""
    schema_version: str
    repository_name: str
    repository_type: str
    generated_at: str
    generator_version: str
    language: str = "unknown"
    complexity_score: float = 0.0
    size_category: str = "medium"  # small, medium, large, xlarge
    custom_fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "repository_name": self.repository_name,
            "repository_type": self.repository_type,
            "generated_at": self.generated_at,
            "generator_version": self.generator_version,
            "language": self.language,
            "complexity_score": self.complexity_score,
            "size_category": self.size_category,
            "custom_fields": self.custom_fields,
        }


@dataclass
class FixtureManifest:
    """Complete fixture manifest with metadata and integrity."""
    metadata: FixtureMetadata
    integrity: FixtureIntegrity
    status: FixtureStatus
    diagnostics: list[DiagnosticMessage] = field(default_factory=list)
    normalized_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "integrity": self.integrity.to_dict(),
            "status": self.status.value,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "normalized_path": self.normalized_path,
        }

    def is_valid(self) -> bool:
        return self.status == FixtureStatus.VALID

    def is_usable(self) -> bool:
        return self.status in (FixtureStatus.VALID, FixtureStatus.PARTIAL)


class FixtureSchemaValidator:
    """Validates fixture against required schema."""

    def __init__(self, fixture_root: Path) -> None:
        self.fixture_root = fixture_root
        self.diagnostics: list[DiagnosticMessage] = []

    def validate(self) -> tuple[bool, list[DiagnosticMessage]]:
        """Run all validation checks. Returns (is_valid, diagnostics)."""
        self.diagnostics = []

        # Check metadata file
        metadata_valid = self._validate_metadata()
        # Check required files
        files_valid = self._validate_required_files()
        # Check section structure
        sections_valid = self._validate_sections()

        is_valid = metadata_valid and files_valid and sections_valid
        return is_valid, self.diagnostics

    def _validate_metadata(self) -> bool:
        """Validate fixture metadata fields."""
        metadata_path = self.fixture_root / "fixture_metadata.json"

        if not metadata_path.exists():
            self.diagnostics.append(DiagnosticMessage(
                error=IngestionError.MISSING_REQUIRED_FILE,
                field_path="fixture_metadata.json",
                message="fixture_metadata.json not found in fixture root",
                severity="ERROR",
            ))
            return False

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except json.JSONDecodeError as e:
            self.diagnostics.append(DiagnosticMessage(
                error=IngestionError.MALFORMED,
                field_path="fixture_metadata.json",
                message=f"Invalid JSON in fixture_metadata.json: {e}",
                severity="ERROR",
            ))
            return False

        # Check required fields
        for field_name in REQUIRED_METADATA_FIELDS:
            if field_name not in metadata:
                self.diagnostics.append(DiagnosticMessage(
                    error=IngestionError.MISSING_REQUIRED_FIELD,
                    field_path=f"metadata.{field_name}",
                    message=f"Required field '{field_name}' is missing from metadata",
                    severity="ERROR",
                ))

        # Check schema version
        if "schema_version" in metadata:
            schema_version = metadata["schema_version"]
            if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
                self.diagnostics.append(DiagnosticMessage(
                    error=IngestionError.UNSUPPORTED_SCHEMA_VERSION,
                    field_path="metadata.schema_version",
                    message=f"Schema version '{schema_version}' is not supported. Supported: {SUPPORTED_SCHEMA_VERSIONS}",
                    severity="ERROR",
                    context={"supported_versions": SUPPORTED_SCHEMA_VERSIONS},
                ))
                return False

        return len([d for d in self.diagnostics if d.severity == "ERROR"]) == 0

    def _validate_required_files(self) -> bool:
        """Validate that required files exist."""
        all_present = True
        for required_file in REQUIRED_FILES:
            file_path = self.fixture_root / required_file
            if not file_path.exists():
                self.diagnostics.append(DiagnosticMessage(
                    error=IngestionError.MISSING_REQUIRED_FILE,
                    field_path=required_file,
                    message=f"Required file '{required_file}' is missing",
                    severity="ERROR",
                ))
                all_present = False

        return all_present

    def _validate_sections(self) -> bool:
        """Validate that required sections exist."""
        sections_dir = self.fixture_root / "docs/sections"

        if not sections_dir.exists():
            self.diagnostics.append(DiagnosticMessage(
                error=IngestionError.MISSING_REQUIRED_FILE,
                field_path="docs/sections",
                message="docs/sections directory is missing",
                severity="ERROR",
            ))
            return False

        # Check for required sections
        present_sections = set()
        try:
            for section_dir in sections_dir.iterdir():
                if section_dir.is_dir() and (section_dir / "index.md").exists():
                    present_sections.add(section_dir.name)
        except PermissionError:
            pass

        missing_sections = [s for s in REQUIRED_SECTIONS if s not in present_sections]
        if missing_sections:
            self.diagnostics.append(DiagnosticMessage(
                error=IngestionError.MISSING_REQUIRED_FILE,
                field_path="docs/sections/*",
                message=f"Missing required sections: {', '.join(missing_sections)}",
                severity="WARNING",
                context={"missing": missing_sections, "present": sorted(present_sections)},
            ))

        return True


class FixtureIntegrityChecker:
    """Computes integrity hashes for fixture content."""

    @staticmethod
    def compute_content_hash(fixture_root: Path) -> str:
        """Compute SHA256 hash of all markdown content."""
        hasher = hashlib.sha256()
        content_files = sorted(fixture_root.rglob("*.md"))

        for file_path in content_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                hasher.update(content.encode("utf-8"))
            except (PermissionError, UnicodeDecodeError, IsADirectoryError):
                continue

        return hasher.hexdigest()

    @staticmethod
    def compute_structure_hash(fixture_root: Path) -> str:
        """Compute hash of directory structure."""
        hasher = hashlib.sha256()
        dirs = sorted(fixture_root.rglob("*"))
        structure = []

        for path in dirs:
            if path.is_file():
                rel_path = path.relative_to(fixture_root)
                structure.append(f"FILE:{rel_path}")

        hasher.update("\n".join(structure).encode("utf-8"))
        return hasher.hexdigest()

    @staticmethod
    def compute_integrity(fixture_root: Path) -> FixtureIntegrity:
        """Compute complete integrity information."""
        content_hash = FixtureIntegrityChecker.compute_content_hash(fixture_root)
        structure_hash = FixtureIntegrityChecker.compute_structure_hash(fixture_root)

        file_count = 0
        total_chars = 0

        for md_file in fixture_root.rglob("*.md"):
            if md_file.is_file():
                file_count += 1
                try:
                    total_chars += len(md_file.read_text(encoding="utf-8"))
                except (PermissionError, UnicodeDecodeError):
                    continue

        return FixtureIntegrity(
            content_hash=content_hash,
            structure_hash=structure_hash,
            file_count=file_count,
            total_chars=total_chars,
        )


class PathNormalizer:
    """Normalizes paths for stable cross-repository comparisons."""

    @staticmethod
    def normalize(fixture_root: Path) -> dict[str, Any]:
        """Normalize fixture paths and return normalized structure."""
        docs_dir = fixture_root / "docs"
        sections_dir = docs_dir / "sections"

        normalized = {
            "root": str(fixture_root.resolve()),
            "docs": str(docs_dir.resolve()) if docs_dir.exists() else None,
            "sections": str(sections_dir.resolve()) if sections_dir.exists() else None,
            "overview_files": [],
            "section_files": {},
            "api_contracts": None,
            "data_model": None,
        }

        # Normalize overview files
        for filename in ["00-overview.md", "01-architecture.md", "03-module-map.md",
                         "04-api-contracts.md", "05-data-model.md"]:
            file_path = docs_dir / filename
            if file_path.exists():
                normalized["overview_files"].append(filename)

        # Normalize section files
        if sections_dir.exists():
            for section_dir in sections_dir.iterdir():
                if section_dir.is_dir():
                    index_path = section_dir / "index.md"
                    if index_path.exists():
                        normalized["section_files"][section_dir.name] = str(index_path.resolve())

        # Check for aggregated API/data model files
        api_path = docs_dir / "04-api-contracts.md"
        dm_path = docs_dir / "05-data-model.md"
        normalized["api_contracts"] = str(api_path.resolve()) if api_path.exists() else None
        normalized["data_model"] = str(dm_path.resolve()) if dm_path.exists() else None

        return normalized


class FreshnessValidator:
    """Validates fixture freshness based on generation timestamp."""

    @staticmethod
    def compute_age_days(generated_at: str) -> int:
        """Compute age of fixture in days from ISO timestamp."""
        try:
            # Parse ISO format timestamp
            if "Z" in generated_at:
                generated_dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            else:
                generated_dt = datetime.fromisoformat(generated_at)
            now = datetime.now(timezone.utc)
            age = (now - generated_dt).days
            return max(0, age)  # Non-negative
        except (ValueError, TypeError):
            return 999  # Unparseable dates treated as stale

    @staticmethod
    def get_freshness_status(generated_at: str, profile: str = "transitional") -> tuple[str, int, bool]:
        """Check if fixture is fresh enough for the given profile.

        Returns:
            tuple of (status, age_days, is_usable)
            status: "fresh", "stale", or "critical"
            age_days: actual age in days
            is_usable: whether fixture passes freshness check
        """
        age_days = FreshnessValidator.compute_age_days(generated_at)
        max_age = MAX_FIXTURE_AGE.get(profile, 30)

        if age_days <= max_age:
            return ("fresh", age_days, True)
        elif age_days <= max_age * 2:
            return ("stale", age_days, True)  # Usable but with warning
        else:
            return ("critical", age_days, False)  # Must be rejected

    @staticmethod
    def get_freshness_score(generated_at: str, profile: str = "transitional") -> float:
        """Compute freshness score from 0.0 to 1.0.

        Score mapping:
        - Age 0 days: 1.0
        - Age at max_age: 0.7
        - Age at 2x max_age: 0.4
        - Age beyond: 0.0
        """
        age_days = FreshnessValidator.compute_age_days(generated_at)
        max_age = MAX_FIXTURE_AGE.get(profile, 30)

        if age_days <= max_age:
            # Linear decay from 1.0 to 0.7 over the acceptable window
            ratio = age_days / max_age
            return 1.0 - (ratio * 0.3)
        elif age_days <= max_age * 2:
            # Linear decay from 0.7 to 0.4 over the next window
            excess = age_days - max_age
            window = max_age
            ratio = excess / window
            return 0.7 - (ratio * 0.3)
        else:
            return 0.0


class ConfidenceScorer:
    """Computes confidence scores for fixture quality and reliability."""

    @staticmethod
    def compute_confidence_score(manifest: FixtureManifest, profile: str = "transitional") -> float:
        """Compute overall confidence score for a fixture.

        Combines multiple factors:
        - Schema validity (0.0 - 0.3)
        - Structural completeness (0.0 - 0.3)
        - Freshness (0.0 - 0.4)
        """
        score = 0.0

        # Schema validity contribution (30%)
        if manifest.status == FixtureStatus.VALID:
            score += 0.30
        elif manifest.status == FixtureStatus.PARTIAL:
            score += 0.15
        else:
            return 0.0  # INVALID fixtures get zero confidence

        # Structural completeness contribution (30%)
        # Based on diagnostics - fewer errors = higher score
        error_count = sum(1 for d in manifest.diagnostics if d.severity == "ERROR")
        warning_count = sum(1 for d in manifest.diagnostics if d.severity == "WARNING")

        if error_count == 0 and warning_count == 0:
            completeness_score = 0.30
        elif error_count == 0:
            completeness_score = 0.30 - (warning_count * 0.05)
        else:
            completeness_score = max(0.0, 0.15 - (error_count * 0.05))
        score += completeness_score

        # Freshness contribution (40%)
        freshness_score = FreshnessValidator.get_freshness_score(
            manifest.metadata.generated_at, profile
        )
        score += freshness_score * 0.4

        return max(0.0, min(1.0, score))  # Clamp to [0.0, 1.0]

    @staticmethod
    def get_confidence_level(score: float) -> str:
        """Map confidence score to level label."""
        if score >= CONFIDENCE_THRESHOLDS["high"]:
            return "high"
        elif score >= CONFIDENCE_THRESHOLDS["medium"]:
            return "medium"
        elif score >= CONFIDENCE_THRESHOLDS["low"]:
            return "low"
        else:
            return "unacceptable"

    @staticmethod
    def get_release_gate_decision(
        manifest: FixtureManifest,
        profile: str = "transitional"
    ) -> dict[str, Any]:
        """Determine release gate decision based on fixture confidence.

        Returns:
            dict with decision, confidence_score, confidence_level,
            freshness_status, is_approved, and rejection_reasons
        """
        confidence_score = ConfidenceScorer.compute_confidence_score(manifest, profile)
        confidence_level = ConfidenceScorer.get_confidence_level(confidence_score)
        freshness_status, age_days, freshness_usable = FreshnessValidator.get_freshness_status(
            manifest.metadata.generated_at, profile
        )

        rejection_reasons = []

        # Check status
        if manifest.status == FixtureStatus.INVALID:
            rejection_reasons.append(f"Fixture status is INVALID")

        # Check freshness
        if not freshness_usable:
            rejection_reasons.append(f"Fixture is critically stale ({age_days} days old)")

        # Check confidence
        if confidence_level == "unacceptable":
            rejection_reasons.append(f"Confidence score {confidence_score:.2f} is unacceptable")

        # Profile-specific minimum confidence thresholds
        min_confidence = {
            "strict": 0.90,
            "transitional": 0.70,
            "pilot": 0.50,
        }.get(profile, 0.70)

        if confidence_score < min_confidence:
            rejection_reasons.append(
                f"Confidence score {confidence_score:.2f} below {profile} threshold {min_confidence}"
            )

        is_approved = len(rejection_reasons) == 0

        return {
            "decision": "APPROVED" if is_approved else "REJECTED",
            "confidence_score": round(confidence_score, 3),
            "confidence_level": confidence_level,
            "freshness_status": freshness_status,
            "age_days": age_days,
            "is_approved": is_approved,
            "rejection_reasons": rejection_reasons,
            "profile": profile,
        }


class FixtureIngestion:
    """Main class for fixture ingestion and validation."""

    def __init__(self, fixture_root: Path) -> None:
        self.fixture_root = fixture_root
        self.validator = FixtureSchemaValidator(fixture_root)

    def ingest(self) -> FixtureManifest:
        """Ingest a fixture and produce a manifest with validation status."""
        # Validate
        is_valid, diagnostics = self.validator.validate()

        # Compute integrity
        integrity = FixtureIntegrityChecker.compute_integrity(self.fixture_root)

        # Load metadata if available
        metadata = self._load_metadata()

        # Normalize paths
        normalized = PathNormalizer.normalize(self.fixture_root)

        # Determine status
        if is_valid and not diagnostics:
            status = FixtureStatus.VALID
        elif is_valid and any(d.severity == "WARNING" for d in diagnostics):
            status = FixtureStatus.PARTIAL
        elif diagnostics and all(d.severity == "WARNING" for d in diagnostics):
            status = FixtureStatus.PARTIAL
        else:
            status = FixtureStatus.INVALID

        manifest = FixtureManifest(
            metadata=metadata,
            integrity=integrity,
            status=status,
            diagnostics=diagnostics,
            normalized_path=normalized["root"],
        )

        return manifest

    def _load_metadata(self) -> FixtureMetadata:
        """Load fixture metadata from fixture_metadata.json."""
        metadata_path = self.fixture_root / "fixture_metadata.json"

        if not metadata_path.exists():
            return FixtureMetadata(
                schema_version="unknown",
                repository_name="unknown",
                repository_type="unknown",
                generated_at="unknown",
                generator_version="unknown",
            )

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            return FixtureMetadata(
                schema_version=data.get("schema_version", "unknown"),
                repository_name=data.get("repository_name", "unknown"),
                repository_type=data.get("repository_type", "unknown"),
                generated_at=data.get("generated_at", "unknown"),
                generator_version=data.get("generator_version", "unknown"),
                language=data.get("language", "unknown"),
                complexity_score=data.get("complexity_score", 0.0),
                size_category=data.get("size_category", "medium"),
                custom_fields=data.get("custom_fields", {}),
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            return FixtureMetadata(
                schema_version="unknown",
                repository_name="unknown",
                repository_type="unknown",
                generated_at="unknown",
                generator_version="unknown",
            )

    def produce_diagnostic_report(self, manifest: FixtureManifest) -> str:
        """Produce a human-readable diagnostic report."""
        lines = [
            "# Fixture Ingestion Report",
            "",
            f"**Fixture Root:** `{self.fixture_root}`",
            f"**Status:** {manifest.status.value}",
            f"**Schema Version:** {manifest.metadata.schema_version}",
            "",
            "---",
            "",
            "## Diagnostics",
            "",
        ]

        if not manifest.diagnostics:
            lines.append("*No diagnostics generated.*")
        else:
            error_count = sum(1 for d in manifest.diagnostics if d.severity == "ERROR")
            warning_count = sum(1 for d in manifest.diagnostics if d.severity == "WARNING")
            lines.append(f"- **Errors:** {error_count}")
            lines.append(f"- **Warnings:** {warning_count}")
            lines.append("")

            for diag in manifest.diagnostics:
                icon = "❌" if diag.severity == "ERROR" else "⚠️"
                lines.append(f"### {icon} {diag.error.value}")
                lines.append(f"- **Field:** `{diag.field_path}`")
                lines.append(f"- **Message:** {diag.message}")
                if diag.context:
                    lines.append(f"- **Context:** `{json.dumps(diag.context, ensure_ascii=False)}`")
                lines.append("")

        lines.extend([
            "---",
            "",
            "## Integrity Information",
            "",
            f"- **Content Hash:** `{manifest.integrity.content_hash}`",
            f"- **Structure Hash:** `{manifest.integrity.structure_hash}`",
            f"- **File Count:** {manifest.integrity.file_count}",
            f"- **Total Chars:** {manifest.integrity.total_chars:,}",
            "",
            "## Normalized Paths",
            "",
            f"- **Root:** `{manifest.normalized_path}`",
        ])

        return "\n".join(lines)


def create_fixture_metadata(
    repository_name: str,
    repository_type: str,
    generator_version: str,
    language: str = "unknown",
    complexity_score: float = 0.0,
    size_category: str = "medium",
) -> dict[str, Any]:
    """Helper to create a fixture_metadata.json file."""
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "repository_name": repository_name,
        "repository_type": repository_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator_version": generator_version,
        "language": language,
        "complexity_score": complexity_score,
        "size_category": size_category,
        "custom_fields": {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Qoder fixture ingestion and validation tool")
    parser.add_argument("--fixture", type=Path, required=True, help="Path to fixture directory")
    parser.add_argument("--validate-only", action="store_true", help="Only validate, don't produce output")
    parser.add_argument("--output", type=Path, help="Output path for normalized fixture manifest")
    parser.add_argument("--create-metadata", action="store_true",
                       help="Create sample fixture_metadata.json in fixture directory")
    parser.add_argument("--repo-name", default="unknown", help="Repository name for metadata")
    parser.add_argument("--repo-type", default="unknown", help="Repository type for metadata")
    parser.add_argument("--generator-version", default="unknown", help="Generator version for metadata")
    parser.add_argument("--profile", choices=["strict", "transitional", "pilot"], default="transitional",
                       help="Profile for freshness validation (strict/transitional/pilot)")
    parser.add_argument("--check-confidence", action="store_true",
                       help="Run release gate confidence check and exit with code based on approval")

    args = parser.parse_args()

    if not args.fixture.exists():
        print(f"Error: Fixture path does not exist: {args.fixture}", file=sys.stderr)
        return 1

    # Create metadata if requested
    if args.create_metadata:
        metadata = create_fixture_metadata(
            repository_name=args.repo_name,
            repository_type=args.repo_type,
            generator_version=args.generator_version,
        )
        metadata_path = args.fixture / "fixture_metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        print(f"Created fixture_metadata.json at: {metadata_path}")

    # Ingest fixture
    ingestion = FixtureIngestion(args.fixture)
    manifest = ingestion.ingest()

    # Confidence check for release gates
    if args.check_confidence:
        decision = ConfidenceScorer.get_release_gate_decision(manifest, args.profile)
        print(f"\n=== Release Gate Decision ===")
        print(f"Profile: {decision['profile']}")
        print(f"Decision: {decision['decision']}")
        print(f"Confidence Score: {decision['confidence_score']:.3f} ({decision['confidence_level']})")
        print(f"Freshness Status: {decision['freshness_status']} ({decision['age_days']} days old)")

        if decision['rejection_reasons']:
            print(f"\nRejection Reasons:")
            for reason in decision['rejection_reasons']:
                print(f"  - {reason}")

        if decision['is_approved']:
            print(f"\nFixture APPROVED for {args.profile} release gate.")
            return 0
        else:
            print(f"\nFixture REJECTED for {args.profile} release gate.")
            return 1

    # Validate
    if not manifest.is_usable():
        print("Fixture validation FAILED:", file=sys.stderr)
        for diag in manifest.diagnostics:
            if diag.severity == "ERROR":
                print(f"  - [{diag.error.value}] {diag.message}", file=sys.stderr)
                print(f"    Field: {diag.field_path}", file=sys.stderr)
        print(file=sys.stderr)
        print("Fixture cannot be used for comparison.", file=sys.stderr)
        return 1

    # Output
    if args.validate_only:
        print(f"Fixture status: {manifest.status.value}")
        if manifest.diagnostics:
            print("\nDiagnostics:")
            for diag in manifest.diagnostics:
                print(f"  [{diag.severity}] {diag.error.value}: {diag.message}")
        return 0

    # Full report
    if args.output:
        # Write JSON manifest
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"Fixture manifest written to: {args.output}")

        # Also write diagnostic report
        md_output = args.output.parent / f"{args.output.stem}_diagnostics.md"
        with open(md_output, "w", encoding="utf-8") as f:
            f.write(ingestion.produce_diagnostic_report(manifest))
        print(f"Diagnostic report written to: {md_output}")
    else:
        # Print diagnostic report to stdout
        print(ingestion.produce_diagnostic_report(manifest))

    return 0


if __name__ == "__main__":
    sys.exit(main())
