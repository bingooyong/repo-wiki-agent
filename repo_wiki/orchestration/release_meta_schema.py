"""Repo-agent release meta documents under `.repo-agent-eval/repowiki/zh/meta/`.

Compatible with Qoder's `content/` + `meta/repowiki-metadata.json` layout while
defining additional machine-readable sidecars (Phase 41.2).

Versioning rules
----------------
* Every **repo-agent-authored** sidecar JSON file MUST include top-level
  ``schema_version`` matching ``^repo_agent\\.<name>/[0-9]+\\.[0-9]+$``.
* **Patch** increments (1.0 → 1.1) add optional fields only; **minor** may add
  required fields for *new* publishers but MUST keep readers tolerant of older
  docs; **major** breaks compatibility and requires explicit migration.
* ``repowiki-metadata.json`` follows Qoder: it does **not** require
  ``schema_version``; validators check required Qoder keys from Task 41.1
  invariants and allow additional unknown keys.

This module provides lightweight ``validate_*`` functions that return a list of
human-readable errors (empty list means the document is structurally valid).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

# ---------------------------------------------------------------------------
# Schema version tokens (repo-agent sidecars only)
# ---------------------------------------------------------------------------

SCHEMA_VERSION_NAVIGATION: Final = "repo_agent.navigation/1.0"
SCHEMA_VERSION_PAGE_REGISTRY: Final = "repo_agent.page_registry/1.0"
SCHEMA_VERSION_SOURCE_INVENTORY: Final = "repo_agent.source_inventory/1.0"
SCHEMA_VERSION_DOCS_INVENTORY: Final = "repo_agent.docs_inventory/1.0"
SCHEMA_VERSION_SERVICE_REGISTRY: Final = "repo_agent.service_registry/1.0"
SCHEMA_VERSION_API_INVENTORY: Final = "repo_agent.api_inventory/1.0"
SCHEMA_VERSION_DATA_MODEL_INVENTORY: Final = "repo_agent.data_model_inventory/1.0"
SCHEMA_VERSION_EVIDENCE_INDEX: Final = "repo_agent.evidence_index/1.0"
SCHEMA_VERSION_DIAGRAM_INDEX: Final = "repo_agent.diagram_index/1.0"
SCHEMA_VERSION_QUALITY_REPORT: Final = "repo_agent.quality_report/1.0"
SCHEMA_VERSION_META_RELEASE: Final = "repo_agent.meta_release/1.0"

_SIDE_CAR_SCHEMA_RE = re.compile(r"^repo_agent\.[a-z_]+/[0-9]+\.[0-9]+$")


def is_valid_repo_agent_schema_version(value: Any) -> bool:
    """Return True if *value* is a compliant repo-agent sidecar schema string."""
    return isinstance(value, str) and bool(_SIDE_CAR_SCHEMA_RE.fullmatch(value))


# Qoder-required top-level keys (Task 41.1 / fixtures)
QODER_REPOWIKI_METADATA_REQUIRED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "code_snippets",
        "knowledge_relations",
        "source_files",
        "wiki_catalogs",
        "wiki_items",
        "wiki_overview",
        "wiki_readme",
        "wiki_repo",
    }
)

META_FILE_REPOWIKI: Final = "repowiki-metadata.json"
META_FILE_NAVIGATION: Final = "navigation.json"
META_FILE_PAGE_REGISTRY: Final = "page-registry.json"
META_FILE_SOURCE_INVENTORY: Final = "source-inventory.json"
META_FILE_DOCS_INVENTORY: Final = "docs-inventory.json"
META_FILE_SERVICE_REGISTRY: Final = "service-registry.json"
META_FILE_API_INVENTORY: Final = "api-inventory.json"
META_FILE_DATA_MODEL_INVENTORY: Final = "data-model-inventory.json"
META_FILE_EVIDENCE_INDEX: Final = "evidence-index.json"
META_FILE_DIAGRAM_INDEX: Final = "diagram-index.json"
META_FILE_QUALITY_REPORT: Final = "quality-report.json"
META_FILE_RELEASE: Final = "release.json"


# ---------------------------------------------------------------------------
# Optional dataclass views (documentation / tooling); validation uses dicts
# ---------------------------------------------------------------------------


@dataclass
class RepoAgentNavigationDocument:
    """``navigation.json`` — tree for viewers (manifest-compatible shapes)."""

    schema_version: str = SCHEMA_VERSION_NAVIGATION
    generated_at: str = ""
    navigation_tree: list[dict[str, Any]] = field(default_factory=list)
    taxonomy_version: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class RepoAgentPageRegistryDocument:
    """``page-registry.json`` — curated page inventory."""

    schema_version: str = SCHEMA_VERSION_PAGE_REGISTRY
    generated_at: str = ""
    pages: list[dict[str, Any]] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class RepoAgentMetaReleaseDocument:
    """``meta/release.json`` — release record (publisher output)."""

    schema_version: str = SCHEMA_VERSION_META_RELEASE
    release_status: str = ""
    release_id: str = ""
    source_run_id: str = ""
    target_git_commit: str | None = None
    published_at: str = ""
    manifest_path: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _err(msg: str) -> list[str]:
    return [msg]


def _require_str(obj: dict[str, Any], key: str, errors: list[str]) -> None:
    v = obj.get(key)
    if not isinstance(v, str) or not v.strip():
        errors.append(f"missing or invalid string field: {key!r}")


def _require_list(obj: dict[str, Any], key: str, errors: list[str]) -> None:
    if not isinstance(obj.get(key), list):
        errors.append(f"missing or invalid list field: {key!r}")


def _require_dict(obj: dict[str, Any], key: str, errors: list[str]) -> None:
    if not isinstance(obj.get(key), dict):
        errors.append(f"missing or invalid object field: {key!r}")


def validate_repowiki_metadata(data: Any) -> list[str]:
    """Validate ``repowiki-metadata.json`` (Qoder-compatible)."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return _err("repowiki-metadata root must be a JSON object")

    missing = sorted(QODER_REPOWIKI_METADATA_REQUIRED_KEYS - set(data.keys()))
    if missing:
        errors.append("repowiki-metadata missing required keys: " + ", ".join(missing))

    for key in sorted(QODER_REPOWIKI_METADATA_REQUIRED_KEYS):
        if key not in data:
            continue
        val = data[key]
        if val is None:
            errors.append(f"repowiki-metadata key {key!r} must not be null")

    # Shape hints from Phase 41.1
    for k in ("wiki_overview", "wiki_readme", "wiki_repo"):
        if k in data and data[k] is not None and not isinstance(data[k], dict):
            errors.append(f"repowiki-metadata.{k} must be an object")

    collection_keys = (
        "wiki_catalogs",
        "wiki_items",
        "code_snippets",
        "source_files",
        "knowledge_relations",
    )
    for ck in collection_keys:
        if ck not in data or data[ck] is None:
            continue
        val = data[ck]
        if not isinstance(val, (list, dict)):
            errors.append(f"repowiki-metadata.{ck} must be a list or object")

    if "schema_version" in data and data["schema_version"] is not None:
        if not isinstance(data["schema_version"], str):
            errors.append("repowiki-metadata.schema_version must be a string if present")

    return errors


def _validate_sidecar_header(
    data: dict[str, Any],
    *,
    expected: str,
    label: str,
    require_generated_at: bool = True,
) -> list[str]:
    errors: list[str] = []
    sv = data.get("schema_version")
    if sv != expected:
        errors.append(f"{label}: schema_version must be {expected!r} (got {sv!r})")
    elif not is_valid_repo_agent_schema_version(sv):
        errors.append(f"{label}: schema_version has invalid format")
    if require_generated_at:
        _require_str(data, "generated_at", errors)
    return errors


def validate_navigation(data: Any) -> list[str]:
    """Validate ``navigation.json``."""
    if not isinstance(data, dict):
        return _err("navigation root must be a JSON object")
    errors = _validate_sidecar_header(data, expected=SCHEMA_VERSION_NAVIGATION, label="navigation")
    _require_list(data, "navigation_tree", errors)
    return errors


def validate_page_registry(data: Any) -> list[str]:
    """Validate ``page-registry.json``."""
    if not isinstance(data, dict):
        return _err("page-registry root must be a JSON object")
    errors = _validate_sidecar_header(
        data, expected=SCHEMA_VERSION_PAGE_REGISTRY, label="page-registry"
    )
    _require_list(data, "pages", errors)
    pages = data.get("pages")
    if isinstance(pages, list):
        for i, p in enumerate(pages):
            if not isinstance(p, dict):
                errors.append(f"pages[{i}] must be an object")
                continue
            for req in ("page_id", "relative_path", "category", "page_type"):
                _require_str(p, req, errors)
    return errors


def validate_source_inventory(data: Any) -> list[str]:
    """Validate ``source-inventory.json``."""
    if not isinstance(data, dict):
        return _err("source-inventory root must be a JSON object")
    errors = _validate_sidecar_header(
        data, expected=SCHEMA_VERSION_SOURCE_INVENTORY, label="source-inventory"
    )
    _require_str(data, "repository_root", errors)
    _require_list(data, "files", errors)
    files = data.get("files")
    if isinstance(files, list):
        for i, f in enumerate(files):
            if not isinstance(f, dict):
                errors.append(f"files[{i}] must be an object")
                continue
            _require_str(f, "path", errors)
    return errors


def validate_docs_inventory(data: Any) -> list[str]:
    """Validate ``docs-inventory.json``."""
    if not isinstance(data, dict):
        return _err("docs-inventory root must be a JSON object")
    errors = _validate_sidecar_header(
        data, expected=SCHEMA_VERSION_DOCS_INVENTORY, label="docs-inventory"
    )
    _require_list(data, "documents", errors)
    docs = data.get("documents")
    if isinstance(docs, list):
        for i, d in enumerate(docs):
            if not isinstance(d, dict):
                errors.append(f"documents[{i}] must be an object")
                continue
            _require_str(d, "path", errors)
    return errors


def validate_service_registry(data: Any) -> list[str]:
    """Validate ``service-registry.json``."""
    if not isinstance(data, dict):
        return _err("service-registry root must be a JSON object")
    errors = _validate_sidecar_header(
        data, expected=SCHEMA_VERSION_SERVICE_REGISTRY, label="service-registry"
    )
    _require_list(data, "services", errors)
    services = data.get("services")
    if isinstance(services, list):
        for i, s in enumerate(services):
            if not isinstance(s, dict):
                errors.append(f"services[{i}] must be an object")
                continue
            _require_str(s, "service_id", errors)
            _require_str(s, "display_name", errors)
            _require_str(s, "runtime_family", errors)
    return errors


def validate_api_inventory(data: Any) -> list[str]:
    """Validate ``api-inventory.json``."""
    if not isinstance(data, dict):
        return _err("api-inventory root must be a JSON object")
    errors = _validate_sidecar_header(
        data, expected=SCHEMA_VERSION_API_INVENTORY, label="api-inventory"
    )
    _require_list(data, "endpoints", errors)
    eps = data.get("endpoints")
    if isinstance(eps, list):
        for i, e in enumerate(eps):
            if not isinstance(e, dict):
                errors.append(f"endpoints[{i}] must be an object")
                continue
            _require_str(e, "service_id", errors)
            _require_str(e, "method", errors)
            _require_str(e, "path", errors)
    return errors


def validate_data_model_inventory(data: Any) -> list[str]:
    """Validate ``data-model-inventory.json``."""
    if not isinstance(data, dict):
        return _err("data-model-inventory root must be a JSON object")
    errors = _validate_sidecar_header(
        data, expected=SCHEMA_VERSION_DATA_MODEL_INVENTORY, label="data-model-inventory"
    )
    _require_list(data, "models", errors)
    models = data.get("models")
    if isinstance(models, list):
        for i, m in enumerate(models):
            if not isinstance(m, dict):
                errors.append(f"models[{i}] must be an object")
                continue
            _require_str(m, "model_id", errors)
            _require_str(m, "kind", errors)
            _require_str(m, "service_id", errors)
    return errors


def validate_evidence_index(data: Any) -> list[str]:
    """Validate ``evidence-index.json``."""
    if not isinstance(data, dict):
        return _err("evidence-index root must be a JSON object")
    errors = _validate_sidecar_header(
        data, expected=SCHEMA_VERSION_EVIDENCE_INDEX, label="evidence-index"
    )
    _require_list(data, "spans", errors)
    spans = data.get("spans")
    if isinstance(spans, list):
        for i, sp in enumerate(spans):
            if not isinstance(sp, dict):
                errors.append(f"spans[{i}] must be an object")
                continue
            _require_str(sp, "span_id", errors)
            _require_str(sp, "page_relative_path", errors)
            _require_str(sp, "source_path", errors)
            if "start_line" in sp or "end_line" in sp:
                for lk in ("start_line", "end_line"):
                    v = sp.get(lk)
                    if v is not None and type(v) is not int:
                        errors.append(f"spans[{i}].{lk} must be an integer")
    return errors


def validate_diagram_index(data: Any) -> list[str]:
    """Validate ``diagram-index.json``."""
    if not isinstance(data, dict):
        return _err("diagram-index root must be a JSON object")
    errors = _validate_sidecar_header(
        data, expected=SCHEMA_VERSION_DIAGRAM_INDEX, label="diagram-index"
    )
    _require_list(data, "diagrams", errors)
    diagrams = data.get("diagrams")
    if isinstance(diagrams, list):
        for i, d in enumerate(diagrams):
            if not isinstance(d, dict):
                errors.append(f"diagrams[{i}] must be an object")
                continue
            _require_str(d, "diagram_id", errors)
            _require_str(d, "page_relative_path", errors)
            _require_str(d, "kind", errors)
    return errors


def validate_quality_report(data: Any) -> list[str]:
    """Validate ``quality-report.json``."""
    if not isinstance(data, dict):
        return _err("quality-report root must be a JSON object")
    errors = _validate_sidecar_header(
        data,
        expected=SCHEMA_VERSION_QUALITY_REPORT,
        label="quality-report",
        require_generated_at=False,
    )
    _require_dict(data, "summary", errors)
    summary = data.get("summary")
    if isinstance(summary, dict):
        _require_str(summary, "profile", errors)
        _require_str(summary, "grade", errors)
        if summary.get("strict_mode") is not None and not isinstance(
            summary.get("strict_mode"), bool
        ):
            errors.append("quality-report.summary.strict_mode must be a boolean")
    metrics = data.get("metrics")
    if metrics is not None and not isinstance(metrics, dict):
        errors.append("quality-report.metrics must be an object if present")
    parity = data.get("parity_summary")
    if parity is not None and not isinstance(parity, dict):
        errors.append("quality-report.parity_summary must be an object if present")
    return errors


def validate_meta_release(data: Any) -> list[str]:
    """Validate ``meta/release.json`` (publisher record)."""
    if not isinstance(data, dict):
        return _err("meta/release root must be a JSON object")
    errors: list[str] = []
    sv = data.get("schema_version")
    if sv != SCHEMA_VERSION_META_RELEASE:
        errors.append(
            "meta/release.json: schema_version must be "
            f"{SCHEMA_VERSION_META_RELEASE!r} (got {sv!r})"
        )
    elif not is_valid_repo_agent_schema_version(sv):
        errors.append("meta/release.json: invalid schema_version format")

    _require_str(data, "release_status", errors)
    _require_str(data, "release_id", errors)
    _require_str(data, "source_run_id", errors)
    _require_str(data, "published_at", errors)

    rs = data.get("release_status")
    if isinstance(rs, str) and rs.upper() not in {"READY", "NOT_READY", "REVOKED"}:
        errors.append("release_status must be READY | NOT_READY | REVOKED")

    tgc = data.get("target_git_commit")
    if tgc is not None:
        if not isinstance(tgc, str) or not tgc.strip():
            errors.append(
                "target_git_commit must be null/absent or a non-empty 7-40 hex git commit"
            )
        elif not re.fullmatch(r"[0-9a-f]{7,40}", tgc.strip()):
            errors.append("target_git_commit must be a 7-40 hex git commit (or null if unknown)")

    mp = data.get("manifest_path")
    if mp is not None and not isinstance(mp, str):
        errors.append("manifest_path must be a string if present")

    return errors


# Filename → validator registry (relative to meta/)
META_VALIDATORS: Final[dict[str, Callable[[Any], list[str]]]] = {
    META_FILE_REPOWIKI: validate_repowiki_metadata,
    META_FILE_NAVIGATION: validate_navigation,
    META_FILE_PAGE_REGISTRY: validate_page_registry,
    META_FILE_SOURCE_INVENTORY: validate_source_inventory,
    META_FILE_DOCS_INVENTORY: validate_docs_inventory,
    META_FILE_SERVICE_REGISTRY: validate_service_registry,
    META_FILE_API_INVENTORY: validate_api_inventory,
    META_FILE_DATA_MODEL_INVENTORY: validate_data_model_inventory,
    META_FILE_EVIDENCE_INDEX: validate_evidence_index,
    META_FILE_DIAGRAM_INDEX: validate_diagram_index,
    META_FILE_QUALITY_REPORT: validate_quality_report,
    META_FILE_RELEASE: validate_meta_release,
}


def meta_basename(filename: str) -> str:
    """Return basename for registry lookup (``meta/navigation.json`` → ``navigation.json``)."""
    return Path(filename).name


def validate_meta_file(filename: str, data: Any) -> list[str]:
    """Validate *data* according to registry entry for Path(*filename*).name."""
    name = meta_basename(filename)
    fn = META_VALIDATORS.get(name)
    if fn is None:
        known = ", ".join(sorted(META_VALIDATORS.keys()))
        return [f"unknown meta filename for validation: {name!r} (known: {known})"]
    return fn(data)
