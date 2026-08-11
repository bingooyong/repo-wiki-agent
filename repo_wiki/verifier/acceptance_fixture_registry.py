"""Representative acceptance fixture registry contract for Qoder baselines.

This module is intentionally read-only and self-contained so later release wiring can
validate a reproducible set of representative fixtures without mutating existing
Qoder verifier or baseline registry code.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar

REQUIRED_REPO_CLASSES: frozenset[str] = frozenset(
    {
        "multi_runtime_monorepo",
        "java_kotlin_service",
        "typescript_frontend_node",
        "python_service",
        "go_rust_service",
    }
)

_HASH_ALGORITHMS: frozenset[str] = frozenset({"sha256"})


class AcceptanceFixtureRegistryError(ValueError):
    """Raised when an acceptance fixture registry violates the contract."""


@dataclass(frozen=True)
class AcceptanceFixtureEntry:
    """Immutable representative fixture binding to a Qoder baseline artifact."""

    fixture_id: str
    repo_class: str
    fixture_hash: str
    revision: str
    baseline_artifact_path: str
    baseline_artifact_hash: str
    generated_at: str
    qoder_version: str
    generator_identity: str
    rubric_version: str

    REQUIRED_FIELDS: ClassVar[tuple[str, ...]] = (
        "fixture_id",
        "repo_class",
        "fixture_hash",
        "revision",
        "baseline_artifact_path",
        "baseline_artifact_hash",
        "generated_at",
        "qoder_version",
        "generator_identity",
        "rubric_version",
    )

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> AcceptanceFixtureEntry:
        """Create an entry from plain registry data, rejecting missing fields early."""
        missing = [field for field in cls.REQUIRED_FIELDS if field not in value]
        if missing:
            raise AcceptanceFixtureRegistryError(
                f"Registry entry is missing required provenance fields: {', '.join(missing)}"
            )
        return cls(**{field: str(value[field]) for field in cls.REQUIRED_FIELDS})

    def canonical_dict(self) -> dict[str, str]:
        """Return the stable, serializable representation used for reports/fingerprints."""
        return {field: getattr(self, field) for field in self.REQUIRED_FIELDS}


@dataclass(frozen=True)
class AcceptanceFixtureRegistryReport:
    """Deterministic validation report for release wiring."""

    fingerprint: str
    entry_count: int
    required_repo_classes: tuple[str, ...]
    registered_repo_classes: tuple[str, ...]
    entries: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready deterministic report."""
        return {
            "fingerprint": self.fingerprint,
            "entry_count": self.entry_count,
            "required_repo_classes": list(self.required_repo_classes),
            "registered_repo_classes": list(self.registered_repo_classes),
            "entries": [dict(entry) for entry in self.entries],
        }

    def to_json(self) -> str:
        """Return stable JSON for audit artifacts."""
        return _stable_json(self.to_dict()).decode("utf-8")


@dataclass(frozen=True)
class AcceptanceFixtureRegistry:
    """Validated representative Qoder baseline fixture registry."""

    entries: tuple[AcceptanceFixtureEntry, ...]
    artifact_root: Path | None = None

    @classmethod
    def from_entries(
        cls,
        entries: Sequence[AcceptanceFixtureEntry | dict[str, Any]],
        *,
        artifact_root: Path | None = None,
        validate_filesystem: bool = False,
    ) -> AcceptanceFixtureRegistry:
        parsed = tuple(
            entry
            if isinstance(entry, AcceptanceFixtureEntry)
            else AcceptanceFixtureEntry.from_mapping(entry)
            for entry in entries
        )
        registry = cls(entries=parsed, artifact_root=artifact_root)
        registry.validate(validate_filesystem=validate_filesystem)
        return registry

    def validate(self, *, validate_filesystem: bool = False) -> None:
        """Validate coverage, provenance, uniqueness, canonical paths, and optional hashes."""
        if len(self.entries) == 0:
            raise AcceptanceFixtureRegistryError("Registry must contain representative fixtures")

        seen_classes: set[str] = set()
        seen_fixture_hashes: set[str] = set()
        seen_fixture_ids: set[str] = set()
        for entry in self.entries:
            _validate_entry(entry)
            if entry.fixture_id in seen_fixture_ids:
                raise AcceptanceFixtureRegistryError(
                    f"Duplicate fixture identifier: {entry.fixture_id}"
                )
            seen_fixture_ids.add(entry.fixture_id)
            if entry.repo_class in seen_classes:
                raise AcceptanceFixtureRegistryError(
                    f"Duplicate repository class: {entry.repo_class}"
                )
            seen_classes.add(entry.repo_class)
            normalized_fixture_hash = _normalize_hash(entry.fixture_hash, field="fixture_hash")
            if normalized_fixture_hash in seen_fixture_hashes:
                raise AcceptanceFixtureRegistryError(
                    f"Duplicate fixture hash: {normalized_fixture_hash}"
                )
            seen_fixture_hashes.add(normalized_fixture_hash)

        missing_classes = REQUIRED_REPO_CLASSES.difference(seen_classes)
        if missing_classes:
            raise AcceptanceFixtureRegistryError(
                "Registry missing required repository classes: "
                + ", ".join(sorted(missing_classes))
            )

        if validate_filesystem:
            if self.artifact_root is None:
                raise AcceptanceFixtureRegistryError(
                    "artifact_root is required when validating baseline artifacts against filesystem"
                )
            for entry in self.entries:
                _validate_baseline_artifact_hash(self.artifact_root, entry)

    def fingerprint(self) -> str:
        """Return a stable sha256 over the canonical registry payload."""
        return hashlib.sha256(_stable_json(self._canonical_payload())).hexdigest()

    def report(self) -> AcceptanceFixtureRegistryReport:
        """Return a deterministic report suitable for later release wiring."""
        ordered_entries = _ordered_entries(self.entries)
        return AcceptanceFixtureRegistryReport(
            fingerprint=self.fingerprint(),
            entry_count=len(self.entries),
            required_repo_classes=tuple(sorted(REQUIRED_REPO_CLASSES)),
            registered_repo_classes=tuple(entry.repo_class for entry in ordered_entries),
            entries=tuple(entry.canonical_dict() for entry in ordered_entries),
        )

    def _canonical_payload(self) -> dict[str, Any]:
        return {
            "contract": "repo-wiki.acceptance-fixture-registry.v1",
            "required_repo_classes": sorted(REQUIRED_REPO_CLASSES),
            "entries": [entry.canonical_dict() for entry in _ordered_entries(self.entries)],
        }


def compute_file_sha256(path: Path) -> str:
    """Compute sha256 hex digest for one baseline artifact file."""
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_acceptance_fixture_registry(
    entries: Sequence[AcceptanceFixtureEntry | dict[str, Any]],
    *,
    artifact_root: Path | None = None,
    validate_filesystem: bool = False,
) -> AcceptanceFixtureRegistryReport:
    """Validate entries and return the deterministic registry report."""
    return AcceptanceFixtureRegistry.from_entries(
        entries,
        artifact_root=artifact_root,
        validate_filesystem=validate_filesystem,
    ).report()


def _validate_entry(entry: AcceptanceFixtureEntry) -> None:
    for field in AcceptanceFixtureEntry.REQUIRED_FIELDS:
        value = getattr(entry, field)
        if value.strip() == "":
            raise AcceptanceFixtureRegistryError(f"Missing provenance field: {field}")
    if entry.repo_class not in REQUIRED_REPO_CLASSES:
        raise AcceptanceFixtureRegistryError(f"Unsupported repository class: {entry.repo_class}")
    _normalize_hash(entry.fixture_hash, field="fixture_hash")
    _normalize_hash(entry.baseline_artifact_hash, field="baseline_artifact_hash")
    _validate_generated_at(entry.generated_at)
    _validate_artifact_path(entry.baseline_artifact_path)


def _validate_generated_at(value: str) -> None:
    normalized = value.removesuffix("Z") + ("+00:00" if value.endswith("Z") else "")
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        raise AcceptanceFixtureRegistryError(f"generated_at must be ISO-8601: {value}")


def _normalize_hash(value: str, *, field: str) -> str:
    if ":" in value:
        algorithm, digest = value.split(":", 1)
        if algorithm not in _HASH_ALGORITHMS:
            raise AcceptanceFixtureRegistryError(f"Unsupported {field} algorithm: {algorithm}")
    else:
        digest = value
    digest = digest.lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise AcceptanceFixtureRegistryError(f"{field} must be a sha256 hex digest")
    return digest


def _validate_artifact_path(value: str) -> PurePosixPath:
    if value != value.strip():
        raise AcceptanceFixtureRegistryError(f"Baseline artifact path is not canonical: {value!r}")
    if "\\" in value or value.startswith("/") or value.startswith("./") or "//" in value:
        raise AcceptanceFixtureRegistryError(f"Baseline artifact path is not canonical: {value}")
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) in {"", "."}:
        raise AcceptanceFixtureRegistryError(f"Baseline artifact path is not canonical: {value}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise AcceptanceFixtureRegistryError(
            f"Baseline artifact path escapes artifact root: {value}"
        )
    if path.as_posix() != value:
        raise AcceptanceFixtureRegistryError(f"Baseline artifact path is not canonical: {value}")
    return path


def _validate_baseline_artifact_hash(artifact_root: Path, entry: AcceptanceFixtureEntry) -> None:
    rel_path = _validate_artifact_path(entry.baseline_artifact_path)
    root = artifact_root.resolve()
    artifact = (root / Path(rel_path.as_posix())).resolve()
    if not artifact.is_relative_to(root):
        raise AcceptanceFixtureRegistryError(
            f"Baseline artifact path escapes artifact root: {entry.baseline_artifact_path}"
        )
    if not artifact.is_file():
        raise AcceptanceFixtureRegistryError(
            f"Baseline artifact missing: {entry.baseline_artifact_path}"
        )
    expected = _normalize_hash(entry.baseline_artifact_hash, field="baseline_artifact_hash")
    actual = compute_file_sha256(artifact)
    if actual != expected:
        raise AcceptanceFixtureRegistryError(
            f"Baseline artifact hash drift for {entry.baseline_artifact_path}: "
            f"expected={expected} actual={actual}"
        )


def _ordered_entries(
    entries: tuple[AcceptanceFixtureEntry, ...],
) -> tuple[AcceptanceFixtureEntry, ...]:
    return tuple(sorted(entries, key=lambda entry: (entry.repo_class, entry.fixture_id)))


def _stable_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
