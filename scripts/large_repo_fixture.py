#!/usr/bin/env python3
"""Generate deterministic large-repository benchmark fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCALE_FIXTURE_SCHEMA_VERSION = "repo_agent.scale_fixture/1.0"
SCALE_FIXTURE_CONTRACT_VERSION = "repo_agent.scale_fixture_contract/1.0"
SCALE_FIXTURE_HASH_ALGORITHM = "repo_agent.scale_fixture_hash/1"
GENERATOR_ID = "scripts/large_repo_fixture.py@1.0"

LANGUAGE_LAYOUT: tuple[tuple[str, str], ...] = (
    ("python", ".py"),
    ("typescript", ".ts"),
    ("go", ".go"),
    ("java", ".java"),
    ("kotlin", ".kt"),
    ("csharp", ".cs"),
    ("rust", ".rs"),
    ("docs", ".md"),
)


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _parse_generated_at(value: Any) -> datetime | None:
    if not _is_non_empty_string(value):
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def _is_sha256_hex(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )


def _update_frame(hasher: Any, payload: bytes) -> None:
    hasher.update(len(payload).to_bytes(8, byteorder="big", signed=False))
    hasher.update(payload)


def _hash_paths(paths: list[str]) -> str:
    hasher = hashlib.sha256(b"repo_agent.scale_fixture.paths/1")
    for relative_path in sorted(paths):
        _update_frame(hasher, relative_path.encode("utf-8"))
    return hasher.hexdigest()


def _iter_repository_files(repository_root: Path) -> Iterator[tuple[str, Path]]:
    for directory, directory_names, file_names in os.walk(repository_root):
        directory_names[:] = sorted(name for name in directory_names if name != ".git")
        directory_path = Path(directory)
        for file_name in sorted(file_names):
            path = directory_path / file_name
            yield path.relative_to(repository_root).as_posix(), path


def inspect_repository(repository_root: Path) -> dict[str, Any]:
    """Stream a fixture repository and compute deterministic inventory evidence."""
    hasher = hashlib.sha256(b"repo_agent.scale_fixture.inventory/1")
    effective_files: list[str] = []
    all_distribution: Counter[str] = Counter()
    effective_distribution: Counter[str] = Counter()
    git_file_count = 0
    total_bytes = 0

    for relative_path, path in _iter_repository_files(repository_root):
        content = path.read_bytes()
        git_file_count += 1
        total_bytes += len(content)
        suffix = path.suffix.lower() or "<none>"
        all_distribution[suffix] += 1
        if relative_path.startswith("src/"):
            effective_files.append(relative_path)
            effective_distribution[suffix] += 1

        _update_frame(hasher, relative_path.encode("utf-8"))
        _update_frame(hasher, content)

    effective_files.sort()
    return {
        "git_file_count": git_file_count,
        "effective_file_count": len(effective_files),
        "excluded_file_count": git_file_count - len(effective_files),
        "total_bytes": total_bytes,
        "file_type_distribution": dict(sorted(all_distribution.items())),
        "effective_file_type_distribution": dict(sorted(effective_distribution.items())),
        "expected_effective_files": effective_files,
        "expected_effective_files_hash": _hash_paths(effective_files),
        "inventory_hash": hasher.hexdigest(),
    }


def _effective_content(index: int, seed: int, language: str, suffix: str) -> bytes:
    identifier = f"fixture_{seed}_{index}"
    if suffix == ".md":
        text = f"# {identifier}\n\nDeterministic scale fixture document for {language}.\n"
    elif suffix == ".py":
        text = f'def {identifier}() -> str:\n    return "{identifier}"\n'
    elif suffix == ".ts":
        text = f'export const {identifier} = "{identifier}";\n'
    elif suffix == ".go":
        text = f'package fixture\n\nconst {identifier} = "{identifier}"\n'
    elif suffix == ".java":
        text = (
            f"final class {identifier.title()} {{\n"
            f'    static final String VALUE = "{identifier}";\n'
            "}\n"
        )
    elif suffix == ".kt":
        text = f'package fixture\n\nconst val {identifier} = "{identifier}"\n'
    elif suffix == ".cs":
        text = (
            "namespace Fixture\n"
            "{\n"
            f"    internal static class {identifier.title()}\n"
            "    {\n"
            f'        internal const string Value = "{identifier}";\n'
            "    }\n"
            "}\n"
        )
    elif suffix == ".rs":
        text = f'pub const {identifier.upper()}: &str = "{identifier}";\n'
    else:  # pragma: no cover - guarded by the static language layout
        raise ValueError(f"unsupported scale fixture suffix: {suffix}")
    return text.encode("utf-8")


def _excluded_content(index: int, seed: int) -> bytes:
    return f"generated artifact seed={seed} index={index}\n".encode()


def generate_scale_fixture(
    output_root: Path,
    *,
    effective_file_count: int,
    git_file_count: int,
    seed: int = 1,
    source: str = "synthetic:deterministic-scale",
    generated_at: str | None = None,
    fixture_commit: str | None = None,
) -> dict[str, Any]:
    """Create a deterministic workload and its provenance manifest."""
    if isinstance(effective_file_count, bool) or not isinstance(effective_file_count, int):
        raise ValueError("effective_file_count must be an integer")
    if isinstance(git_file_count, bool) or not isinstance(git_file_count, int):
        raise ValueError("git_file_count must be an integer")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if effective_file_count < 1:
        raise ValueError("effective_file_count must be at least 1")
    if git_file_count < effective_file_count:
        raise ValueError("git_file_count must be greater than or equal to effective_file_count")
    if not _is_non_empty_string(source):
        raise ValueError("source must be a non-empty string")

    generated_timestamp = generated_at or datetime.now(UTC).isoformat()
    if _parse_generated_at(generated_timestamp) is None:
        raise ValueError("generated_at must be a timezone-aware ISO timestamp")
    fixture_revision = fixture_commit if fixture_commit is not None else f"synthetic-seed:{seed}"
    if not _is_non_empty_string(fixture_revision):
        raise ValueError("fixture_commit must be a non-empty string")

    repository_root = output_root / "repository"
    manifest_path = output_root / "fixture-manifest.json"
    if repository_root.exists() or manifest_path.exists():
        raise FileExistsError(f"scale fixture output already exists: {output_root}")

    width = max(6, len(str(git_file_count)))
    for index in range(effective_file_count):
        language, suffix = LANGUAGE_LAYOUT[index % len(LANGUAGE_LAYOUT)]
        relative_path = Path(
            "src",
            language,
            f"shard_{index // 1000:04d}",
            f"file_{index:0{width}d}{suffix}",
        )
        path = repository_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_effective_content(index, seed, language, suffix))

    for index in range(git_file_count - effective_file_count):
        relative_path = Path(
            "vendor",
            "generated",
            f"shard_{index // 1000:04d}",
            f"artifact_{index:0{width}d}.txt",
        )
        path = repository_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_excluded_content(index, seed))

    inventory = inspect_repository(repository_root)
    manifest = {
        "schema_version": SCALE_FIXTURE_SCHEMA_VERSION,
        "contract_version": SCALE_FIXTURE_CONTRACT_VERSION,
        "fixture_hash": inventory["inventory_hash"],
        "hash_algorithm": SCALE_FIXTURE_HASH_ALGORITHM,
        "provenance": {
            "source": source,
            "generator": GENERATOR_ID,
            "generated_at": generated_timestamp,
            "fixture_commit": fixture_revision,
            "seed": seed,
        },
        "repository_root": "repository",
        "parameters": {
            "effective_file_count": effective_file_count,
            "git_file_count": git_file_count,
            "seed": seed,
        },
        "filters": {
            "effective_root": "src/",
            "recommended_exclude": ["vendor/generated/**"],
        },
        "inventory": inventory,
        "gating": {
            "eligible": True,
            "scope": "fixture-contract",
            "non_gating_reasons": [],
            "production_scale_gate": "not_evaluated",
        },
    }
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def load_and_validate_scale_fixture(
    output_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Load a scale fixture and return manifest, observed inventory, and issues."""
    manifest_path = output_root / "fixture-manifest.json"
    issues: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        return {}, {}, [f"fixture manifest is unavailable or invalid: {exc}"]

    if not isinstance(manifest, dict):
        return {}, {}, ["fixture manifest must contain a JSON object"]
    if manifest.get("schema_version") != SCALE_FIXTURE_SCHEMA_VERSION:
        issues.append("unsupported fixture schema_version")
    if manifest.get("contract_version") != SCALE_FIXTURE_CONTRACT_VERSION:
        issues.append("unsupported fixture contract_version")
    if manifest.get("hash_algorithm") != SCALE_FIXTURE_HASH_ALGORITHM:
        issues.append("unsupported fixture hash_algorithm")

    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        issues.append("fixture provenance must be an object")
        provenance = {}
    for field_name in ("source", "generator", "fixture_commit"):
        if not _is_non_empty_string(provenance.get(field_name)):
            issues.append(f"provenance.{field_name} must be a non-empty string")
    if _parse_generated_at(provenance.get("generated_at")) is None:
        issues.append("provenance.generated_at must be a timezone-aware ISO timestamp")
    provenance_seed = provenance.get("seed")
    if isinstance(provenance_seed, bool) or not isinstance(provenance_seed, int):
        issues.append("provenance.seed must be an integer")

    fixture_hash = manifest.get("fixture_hash")
    if not _is_sha256_hex(fixture_hash):
        issues.append("fixture_hash must be a 64-character SHA-256 hex digest")

    repository_value = manifest.get("repository_root")
    if not isinstance(repository_value, str) or not repository_value:
        return manifest, {}, [*issues, "repository_root must be a non-empty string"]
    repository_root = output_root / repository_value
    if not repository_root.is_dir():
        return manifest, {}, [*issues, "fixture repository_root does not exist"]

    observed = inspect_repository(repository_root)
    parameters = manifest.get("parameters")
    if not isinstance(parameters, dict):
        issues.append("fixture parameters must be an object")
        parameters = {}
    for field_name in ("effective_file_count", "git_file_count"):
        parameter_value = parameters.get(field_name)
        if isinstance(parameter_value, bool) or not isinstance(parameter_value, int):
            issues.append(f"parameters.{field_name} must be an integer")
        elif parameter_value != observed[field_name]:
            issues.append(f"fixture parameter mismatch: {field_name}")
    parameter_seed = parameters.get("seed")
    if isinstance(parameter_seed, bool) or not isinstance(parameter_seed, int):
        issues.append("parameters.seed must be an integer")
    elif isinstance(provenance_seed, int) and parameter_seed != provenance_seed:
        issues.append("fixture parameter mismatch: seed")

    expected = manifest.get("inventory")
    if not isinstance(expected, dict):
        return manifest, observed, [*issues, "fixture inventory must be an object"]

    compared_fields = (
        "git_file_count",
        "effective_file_count",
        "excluded_file_count",
        "total_bytes",
        "file_type_distribution",
        "effective_file_type_distribution",
        "expected_effective_files",
        "expected_effective_files_hash",
        "inventory_hash",
    )
    for field_name in compared_fields:
        if expected.get(field_name) != observed.get(field_name):
            issues.append(f"fixture inventory mismatch: {field_name}")
    if _is_sha256_hex(fixture_hash) and fixture_hash.lower() != observed["inventory_hash"]:
        issues.append("fixture_hash does not match observed inventory_hash")

    return manifest, observed, list(dict.fromkeys(issues))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--effective-files", required=True, type=int)
    parser.add_argument("--git-files", required=True, type=int)
    parser.add_argument("--seed", default=1, type=int)
    parser.add_argument("--source", default="synthetic:deterministic-scale")
    parser.add_argument("--generated-at")
    parser.add_argument("--fixture-commit")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        manifest = generate_scale_fixture(
            args.output,
            effective_file_count=args.effective_files,
            git_file_count=args.git_files,
            seed=args.seed,
            source=args.source,
            generated_at=args.generated_at,
            fixture_commit=args.fixture_commit,
        )
    except (FileExistsError, OSError, ValueError) as exc:
        print(f"scale-fixture: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(manifest, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
