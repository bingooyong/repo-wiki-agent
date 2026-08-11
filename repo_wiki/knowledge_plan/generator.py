"""Knowledge-plan generation from Knowledge Model v3 and IA taxonomy profiles."""

from __future__ import annotations

import re
from typing import Any

from repo_wiki.ia.taxonomy_compiler import TaxonomyProfile, TaxonomyProfileCompiler

from .schema import SCHEMA_VERSION, attach_fingerprint, stable_hash, utc_now_iso

_DIRECTORY_TEMPLATE_RULES: tuple[tuple[str, tuple[dict[str, Any], ...]], ...] = (
    (
        "项目概述/",
        ({"id": "overview.summary", "title": "项目概述", "contracts": ["repository_summary"]},),
    ),
    (
        "架构设计/",
        (
            {
                "id": "architecture.system",
                "title": "系统架构",
                "contracts": ["services", "operation_assets"],
            },
        ),
    ),
    ("服务与模块/", ({"id": "service.module", "title": "服务与模块", "contracts": ["services"]},)),
    ("核心服务/", ({"id": "service.core", "title": "核心服务", "contracts": ["services"]},)),
    ("Python服务/", ({"id": "service.python", "title": "Python 服务", "contracts": ["services"]},)),
    ("API参考/", ({"id": "api.reference", "title": "API 参考", "contracts": ["api_surfaces"]},)),
    ("数据模型/", ({"id": "data.model", "title": "数据模型", "contracts": ["data_models"]},)),
    (
        "前端应用/",
        ({"id": "frontend.app", "title": "前端应用", "contracts": ["frontend_consumers"]},),
    ),
    (
        "开发指南/",
        (
            {
                "id": "guide.development",
                "title": "开发指南",
                "contracts": ["repository", "doc_artifacts"],
            },
        ),
    ),
    (
        "运行与部署/",
        ({"id": "ops.deployment", "title": "运行与部署", "contracts": ["operation_assets"]},),
    ),
    (
        "安全与合规/",
        ({"id": "security.compliance", "title": "安全与合规", "contracts": ["operation_assets"]},),
    ),
    (
        "测试与质量/",
        (
            {
                "id": "quality.testing",
                "title": "测试与质量",
                "contracts": ["operation_assets", "doc_artifacts"],
            },
        ),
    ),
    (
        "故障排除与维护/",
        (
            {
                "id": "maintenance.troubleshooting",
                "title": "故障排除与维护",
                "contracts": ["conflicts", "operation_assets"],
            },
        ),
    ),
)
_TEMPLATE_BY_DIRECTORY = dict(_DIRECTORY_TEMPLATE_RULES)
_RUNTIME_DIRECTORIES = {
    "python": "Python服务/",
    "python-fastapi": "Python服务/",
    "python-flask": "Python服务/",
    "java-spring": "核心服务/",
    "go_main": "核心服务/",
}


def generate_plan(
    knowledge_model: dict[str, Any],
    taxonomy_profile: TaxonomyProfile | None = None,
) -> dict[str, Any]:
    """Generate a first-class knowledge plan from Knowledge Model v3."""

    profile = taxonomy_profile or TaxonomyProfileCompiler().compile(knowledge_model)
    records = knowledge_model.get("records", {}) if isinstance(knowledge_model, dict) else {}
    records = records if isinstance(records, dict) else {}
    directories, page_templates = _directories_and_templates(profile)
    plan = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "model": _model_block(knowledge_model),
        "include": [directory["path"] for directory in directories],
        "exclude": [],
        "docs": {"allowlist": _docs_allowlist(records)},
        "directories": directories,
        "page_templates": page_templates,
        "business_domains": _business_domains(records, directories),
        "manual_sections": [],
        "overwrite_policy": {
            "mode": "protect_manual_edits",
            "managed_fingerprint_required": True,
            "force_overwrite": False,
        },
    }
    return attach_fingerprint(plan)


def _model_block(knowledge_model: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": knowledge_model.get("schema_version"),
        "input_fingerprints": dict(knowledge_model.get("input_fingerprints") or {}),
        "summary": dict(knowledge_model.get("summary") or {}),
        "fingerprint": stable_hash(
            {
                "schema_version": knowledge_model.get("schema_version"),
                "input_fingerprints": knowledge_model.get("input_fingerprints"),
                "summary": knowledge_model.get("summary"),
                "records": knowledge_model.get("records"),
            }
        ),
    }


def _directories_and_templates(
    profile: TaxonomyProfile,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    directories: list[dict[str, Any]] = []
    templates: dict[str, dict[str, Any]] = {}
    for spec in profile.directories:
        refs = [
            dict(item)
            for item in _TEMPLATE_BY_DIRECTORY.get(spec.path, (_fallback_template(spec.path),))
        ]
        for ref in refs:
            templates.setdefault(ref["id"], dict(ref))
        directories.append(
            {
                "path": spec.path,
                "label": spec.label,
                "enabled": bool(spec.enabled),
                "record_families": list(spec.record_families),
                "evidence_threshold": dict(spec.evidence_threshold),
                "templates": [
                    {"id": ref["id"], "contracts": list(ref.get("contracts", []))} for ref in refs
                ],
            }
        )
    return directories, list(templates.values())


def _fallback_template(directory_path: str) -> dict[str, Any]:
    slug = _slug(directory_path.rstrip("/") or "directory")
    return {
        "id": f"directory.{slug}",
        "title": directory_path.rstrip("/"),
        "contracts": ["repository"],
    }


def _docs_allowlist(records: dict[str, Any]) -> list[dict[str, Any]]:
    docs = records.get("doc_artifacts", [])
    if not isinstance(docs, list):
        return []
    allowlist: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in docs:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if not isinstance(path, str) or not path or path in seen:
            continue
        seen.add(path)
        allowlist.append(
            {
                "path": path,
                "doc_id": item.get("doc_id"),
                "doc_type": item.get("doc_type"),
                "authority": item.get("authority"),
                "content_sha256": item.get("content_sha256"),
            }
        )
    return allowlist


def _business_domains(
    records: dict[str, Any], directories: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    services = records.get("services", [])
    if not isinstance(services, list):
        return []
    enabled_paths = {directory["path"] for directory in directories}
    grouped: dict[str, dict[str, Any]] = {}
    for service in services:
        if not isinstance(service, dict):
            continue
        runtime = str(service.get("runtime") or "unknown").strip().lower() or "unknown"
        domain_id = _slug(runtime)
        domain = grouped.setdefault(
            domain_id,
            {
                "id": domain_id,
                "label": f"{runtime} services",
                "runtimes": [],
                "services": [],
                "evidence_paths": [],
                "directories": [],
            },
        )
        _append_unique(domain["runtimes"], runtime)
        service_id = service.get("service_id")
        if isinstance(service_id, str) and service_id:
            _append_unique(domain["services"], service_id)
        evidence_path = service.get("evidence_path")
        if isinstance(evidence_path, str) and evidence_path:
            _append_unique(domain["evidence_paths"], evidence_path)
        directory = _RUNTIME_DIRECTORIES.get(runtime, "服务与模块/")
        if directory in enabled_paths:
            _append_unique(domain["directories"], directory)
    return sorted(grouped.values(), key=lambda item: item["id"])


def _append_unique(items: list[Any], value: Any) -> None:
    if value not in items:
        items.append(value)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"
