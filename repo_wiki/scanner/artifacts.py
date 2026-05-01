from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from repo_wiki.core.contracts import RepositorySnapshot
from repo_wiki.generator.io import ensure_dir, write_yamlish


def write_source_of_truth(root: Path, snapshot: RepositorySnapshot) -> dict[str, Path]:
    _validate_snapshot(snapshot)
    ai_dir = root / "ai" / "source-of-truth"
    ensure_dir(ai_dir / "prompt-fragments")

    repo_map = {
        "repository": {
            "name": snapshot.repository.name,
            "root_path": snapshot.repository.root_path,
            "primary_language": snapshot.repository.language,
            "framework": snapshot.repository.framework,
            "package_manager": snapshot.repository.package_manager,
            "entry_points": snapshot.repository.entry_points,
            "key_directories": snapshot.repository.key_directories,
            "last_scanned": datetime.now(UTC).isoformat(),
        },
        "commands": snapshot.commands,
        "stats": snapshot.stats.model_dump(),
    }

    module_index = {
        "modules": [
            {
                "name": module.name,
                "path": module.path,
                "responsibility": module.responsibility,
                "exports": module.exports,
                "depends_on": module.depends_on,
                "depended_by": module.depended_by,
                "interfaces": module.interfaces,
                "data_models": module.data_models,
                "owner": module.owner,
                "doc_path": module.doc_path,
                # Business domain classification metadata (Phase 06)
                "domain": module.domain,
                "service_family": module.service_family,
                "runtime_role": module.runtime_role,
                "domain_confidence": module.domain_confidence,
                "domain_classification_reason": module.domain_classification_reason,
            }
            for module in snapshot.modules
        ]
    }

    api_index = {
        "endpoints": [
            {
                "method": endpoint.method,
                "path": endpoint.path,
                "module": endpoint.module,
                "handler": endpoint.handler,
                "file_path": endpoint.file_path,
                # Enriched metadata (Phase 25)
                "service_family": endpoint.service_family,
                "domain": endpoint.domain,
                "runtime_role": endpoint.runtime_role,
                "auth_type": endpoint.auth_type,
                "auth_required": endpoint.auth_required,
                "request_body": endpoint.request_body,
                "response_type": endpoint.response_type,
                "error_codes": endpoint.error_codes,
                "line_number": endpoint.line_number,
                "line_end": endpoint.line_end,
            }
            for endpoint in snapshot.endpoints
        ]
    }

    data_models = {
        "models": [
            {
                "name": model.name,
                "type": model.type,
                "module": model.module,
                "file_path": model.file_path,
            }
            for model in snapshot.data_models
        ]
    }

    task_catalog = {
        "tasks": [
            {
                "name": "init",
                "steps": ["scan", "index", "graph", "generate", "sync"],
                "verify": ["repo-wiki verify"],
            },
            {
                "name": "update",
                "steps": ["detect-changes", "resolve-impact", "regenerate", "sync"],
                "verify": ["repo-wiki verify"],
            },
        ]
    }

    outputs: dict[str, Any] = {
        "repo-map.yaml": repo_map,
        "module-index.yaml": module_index,
        "api-index.yaml": api_index,
        "data-models.yaml": data_models,
        "task-catalog.yaml": task_catalog,
    }

    paths: dict[str, Path] = {}
    for name, payload in outputs.items():
        path = ai_dir / name
        write_yamlish(path, payload)
        paths[name] = path

    overview_path = ai_dir / "prompt-fragments" / "overview.txt"
    architecture_path = ai_dir / "prompt-fragments" / "architecture.txt"
    overview_path.write_text(
        f"{snapshot.repository.name} is a {snapshot.repository.language} repository with {len(snapshot.modules)} modules.",
        encoding="utf-8",
    )
    architecture_path.write_text(
        "Architecture summary is generated from module boundaries, dependencies, APIs, and data models.",
        encoding="utf-8",
    )
    paths["prompt-overview"] = overview_path
    paths["prompt-architecture"] = architecture_path

    # Generate classification diagnostics
    diagnostics_path = write_diagnostics_report(root, snapshot)
    paths["classification-diagnostics"] = diagnostics_path

    return paths


def _validate_snapshot(snapshot: RepositorySnapshot) -> None:
    required = ("name", "path", "responsibility", "owner", "doc_path")
    for module in snapshot.modules:
        payload = module.model_dump()
        missing = [field for field in required if not str(payload.get(field, "")).strip()]
        if missing:
            raise ValueError(f"Invalid module '{module.name}': missing required fields {missing}")


REQUIRED_SOURCE_OF_TRUTH_FILES = [
    "repo-map.yaml",
    "module-index.yaml",
    "api-index.yaml",
    "data-models.yaml",
    "task-catalog.yaml",
    "prompt-fragments/overview.txt",
    "prompt-fragments/architecture.txt",
]


# Diagnostic thresholds
_LOW_CONFIDENCE_THRESHOLD = 0.3
_FALLBACK_DIAGNOSTIC_TYPES = ("unknown", "core-platform")


def emit_classification_diagnostics(snapshot: RepositorySnapshot) -> dict[str, Any]:
    """Emit diagnostics for low-confidence or fallback classifications.

    Returns a dictionary with diagnostic information about modules that have
    low confidence scores or are using fallback classifications.
    """
    diagnostics: dict[str, Any] = {
        "total_modules": len(snapshot.modules),
        "low_confidence_modules": [],
        "fallback_classifications": [],
        "service_family_coverage": {},
        "runtime_role_coverage": {},
        "summary": {
            "high_confidence_count": 0,
            "low_confidence_count": 0,
            "fallback_count": 0,
        },
    }

    for module in snapshot.modules:
        # Track low confidence modules
        if module.domain_confidence < _LOW_CONFIDENCE_THRESHOLD:
            diagnostics["low_confidence_modules"].append({
                "module": module.name,
                "path": module.path,
                "domain": module.domain,
                "confidence": module.domain_confidence,
                "reason": module.domain_classification_reason,
            })
            diagnostics["summary"]["low_confidence_count"] += 1

        # Track fallback classifications
        if module.domain in _FALLBACK_DIAGNOSTIC_TYPES and module.domain_confidence < 0.5:
            diagnostics["fallback_classifications"].append({
                "module": module.name,
                "path": module.path,
                "domain": module.domain,
                "confidence": module.domain_confidence,
                "reason": module.domain_classification_reason,
                "suggestion": _get_fallback_suggestion(module),
            })
            diagnostics["summary"]["fallback_count"] += 1

        # Track coverage
        diagnostics["service_family_coverage"][module.service_family] = \
            diagnostics["service_family_coverage"].get(module.service_family, 0) + 1
        diagnostics["runtime_role_coverage"][module.runtime_role] = \
            diagnostics["runtime_role_coverage"].get(module.runtime_role, 0) + 1

    # Count high confidence
    diagnostics["summary"]["high_confidence_count"] = (
        len(snapshot.modules) - diagnostics["summary"]["low_confidence_count"]
    )

    return diagnostics


def _get_fallback_suggestion(module: Any) -> str:
    """Generate suggestions for modules with fallback classifications."""
    suggestions = []

    if not module.exports:
        suggestions.append("add-exports")
    if not module.interfaces:
        suggestions.append("add-api-endpoints")
    if not module.data_models:
        suggestions.append("add-data-models")

    path_hints = {
        "ai": "consider-ai-services-domain",
        "indexer": "consider-ai-services-domain",
        "embedding": "consider-ai-services-domain",
        "api": "consider-api-gateway-domain",
        "router": "consider-api-gateway-domain",
        "db": "consider-persistence-domain",
        "storage": "consider-persistence-domain",
    }

    path_lower = module.path.lower()
    for hint, suggestion in path_hints.items():
        if hint in path_lower and suggestion not in suggestions:
            suggestions.append(suggestion)

    return "|".join(suggestions) if suggestions else "no-obvious-signals"


def write_diagnostics_report(root: Path, snapshot: RepositorySnapshot) -> Path:
    """Write a diagnostics report for classification analysis.

    Returns the path to the written diagnostics file.
    """
    diagnostics = emit_classification_diagnostics(snapshot)
    ai_dir = root / "ai" / "source-of-truth"
    ensure_dir(ai_dir)

    import json
    diagnostics_path = ai_dir / "classification-diagnostics.json"
    diagnostics_path.write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return diagnostics_path
