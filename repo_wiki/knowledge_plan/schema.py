"""Versioned schema and validation for repository knowledge plans."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import Any

SCHEMA_VERSION = "repo_agent.knowledge_plan/1.0"
DEFAULT_PLAN_PATH = Path(".repo-wiki/knowledge-plan.yaml")
MANAGED_KEYS: tuple[str, ...] = (
    "schema_version",
    "generated_at",
    "model",
    "include",
    "exclude",
    "docs",
    "directories",
    "page_templates",
    "business_domains",
    "overwrite_policy",
)
_TEMPLATE_ID_RE = re.compile(r"^[a-z][a-z0-9_\-]*(\.[a-z][a-z0-9_\-]*)*$")
_DOMAIN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]*$")


@dataclass(frozen=True)
class ValidationIssue:
    """Structured knowledge-plan validation issue."""

    severity: str
    path: str
    message: str
    code: str

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
            "code": self.code,
        }


class ManualEditConflictError(RuntimeError):
    """Raised when a write would silently replace manual edits."""


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_hash(payload: Any) -> str:
    """Return a deterministic SHA-256 hash for YAML/JSON-compatible data."""

    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def managed_portion(plan: dict[str, Any]) -> dict[str, Any]:
    """Return the generated portion protected by the plan fingerprint."""

    return {key: plan.get(key) for key in MANAGED_KEYS if key in plan}


def compute_managed_fingerprint(plan: dict[str, Any]) -> str:
    return stable_hash(managed_portion(plan))


def attach_fingerprint(plan: dict[str, Any]) -> dict[str, Any]:
    """Attach/refresh generated metadata without mutating the input plan."""

    out = dict(plan)
    generated = dict(out.get("generated") or {})
    generated["managed_keys"] = list(MANAGED_KEYS)
    out["generated"] = generated
    out["generated"]["fingerprint"] = compute_managed_fingerprint(out)
    return out


def stored_fingerprint(plan: dict[str, Any]) -> str | None:
    generated = plan.get("generated")
    if not isinstance(generated, dict):
        return None
    value = generated.get("fingerprint")
    return value if isinstance(value, str) and value else None


def has_manual_managed_edits(plan: dict[str, Any]) -> bool:
    """True when the managed portion no longer matches the stored fingerprint."""

    stored = stored_fingerprint(plan)
    return stored is not None and compute_managed_fingerprint(plan) != stored


def validate_plan(plan: dict[str, Any]) -> list[ValidationIssue]:
    """Validate a knowledge plan and return structured issues."""

    issues: list[ValidationIssue] = []
    if not isinstance(plan, dict):
        return [
            ValidationIssue(
                "error",
                "$",
                "Knowledge plan must be a mapping.",
                "plan.not_mapping",
            )
        ]

    _check_schema_version(plan, issues)
    _check_path_list(plan, "include", issues)
    _check_path_list(plan, "exclude", issues)
    _check_directories(plan, issues)
    _check_docs_allowlist(plan, issues)
    _check_templates(plan, issues)
    _check_domains(plan, issues)
    _check_overwrite_policy(plan, issues)
    _check_generated_metadata(plan, issues)
    return issues


def _check_schema_version(plan: dict[str, Any], issues: list[ValidationIssue]) -> None:
    if plan.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            ValidationIssue(
                "error",
                "schema_version",
                f"schema_version must be {SCHEMA_VERSION}.",
                "schema_version.unsupported",
            )
        )


def _check_path_list(plan: dict[str, Any], key: str, issues: list[ValidationIssue]) -> None:
    value = plan.get(key, [])
    if not isinstance(value, list):
        issues.append(ValidationIssue("error", key, f"{key} must be a list.", f"{key}.not_list"))
        return
    for index, item in enumerate(value):
        path = f"{key}[{index}]"
        if not isinstance(item, str) or not item.strip():
            issues.append(
                ValidationIssue(
                    "error",
                    path,
                    f"{key} entries must be non-empty strings.",
                    f"{key}.invalid_path",
                )
            )
            continue
        _check_safe_relative_path(item, path, f"{key}.unsafe_path", issues)


def _check_directories(plan: dict[str, Any], issues: list[ValidationIssue]) -> None:
    directories = plan.get("directories", [])
    if not isinstance(directories, list):
        issues.append(
            ValidationIssue(
                "error", "directories", "directories must be a list.", "directories.not_list"
            )
        )
        return
    seen: dict[str, int] = {}
    for index, directory in enumerate(directories):
        base = f"directories[{index}]"
        if not isinstance(directory, dict):
            issues.append(
                ValidationIssue(
                    "error", base, "Directory entries must be mappings.", "directory.not_mapping"
                )
            )
            continue
        path = directory.get("path")
        if not isinstance(path, str) or not path.strip():
            issues.append(
                ValidationIssue(
                    "error",
                    f"{base}.path",
                    "Directory path is required.",
                    "directory.path_required",
                )
            )
            continue
        _check_safe_relative_path(path, f"{base}.path", "directory.unsafe_path", issues)
        if path in seen:
            issues.append(
                ValidationIssue(
                    "error",
                    f"{base}.path",
                    f"Duplicate directory path also appears at directories[{seen[path]}].",
                    "directory.duplicate_path",
                )
            )
        seen[path] = index


def _check_docs_allowlist(plan: dict[str, Any], issues: list[ValidationIssue]) -> None:
    docs = plan.get("docs", {})
    if not isinstance(docs, dict):
        issues.append(
            ValidationIssue("error", "docs", "docs must be a mapping.", "docs.not_mapping")
        )
        return
    allowlist = docs.get("allowlist", [])
    if not isinstance(allowlist, list):
        issues.append(
            ValidationIssue(
                "error",
                "docs.allowlist",
                "docs.allowlist must be a list.",
                "docs.allowlist.not_list",
            )
        )
        return
    for index, item in enumerate(allowlist):
        base = f"docs.allowlist[{index}]"
        if not isinstance(item, dict):
            issues.append(
                ValidationIssue(
                    "error",
                    base,
                    "Docs allowlist entries must be mappings.",
                    "docs.allowlist.not_mapping",
                )
            )
            continue
        path = item.get("path")
        if not isinstance(path, str) or not path.strip():
            issues.append(
                ValidationIssue(
                    "error",
                    f"{base}.path",
                    "Docs allowlist entry path is required.",
                    "docs.allowlist.path_required",
                )
            )
        else:
            _check_safe_relative_path(path, f"{base}.path", "docs.allowlist.unsafe_path", issues)


def _check_templates(plan: dict[str, Any], issues: list[ValidationIssue]) -> None:
    templates = plan.get("page_templates", [])
    if not isinstance(templates, list):
        issues.append(
            ValidationIssue(
                "error", "page_templates", "page_templates must be a list.", "templates.not_list"
            )
        )
        return
    known_ids: set[str] = set()
    for index, template in enumerate(templates):
        base = f"page_templates[{index}]"
        if not isinstance(template, dict):
            issues.append(
                ValidationIssue(
                    "error", base, "Template entries must be mappings.", "template.not_mapping"
                )
            )
            continue
        template_id = template.get("id")
        if not isinstance(template_id, str) or not _TEMPLATE_ID_RE.match(template_id):
            issues.append(
                ValidationIssue(
                    "error",
                    f"{base}.id",
                    "Template id has an invalid shape.",
                    "template.invalid_id",
                )
            )
            continue
        known_ids.add(template_id)
    _check_directory_template_refs(plan, known_ids, issues)


def _check_directory_template_refs(
    plan: dict[str, Any], known_ids: set[str], issues: list[ValidationIssue]
) -> None:
    directories = plan.get("directories", [])
    if not isinstance(directories, list):
        return
    for index, directory in enumerate(directories):
        if not isinstance(directory, dict):
            continue
        refs = directory.get("templates", [])
        if not isinstance(refs, list):
            issues.append(
                ValidationIssue(
                    "error",
                    f"directories[{index}].templates",
                    "Directory templates must be a list.",
                    "directory.templates.not_list",
                )
            )
            continue
        for ref_index, ref in enumerate(refs):
            template_id = ref.get("id") if isinstance(ref, dict) else ref
            if not isinstance(template_id, str) or template_id not in known_ids:
                issues.append(
                    ValidationIssue(
                        "error",
                        f"directories[{index}].templates[{ref_index}]",
                        "Directory references an unknown template id.",
                        "directory.template_unknown",
                    )
                )


def _check_domains(plan: dict[str, Any], issues: list[ValidationIssue]) -> None:
    domains = plan.get("business_domains", [])
    if not isinstance(domains, list):
        issues.append(
            ValidationIssue(
                "error", "business_domains", "business_domains must be a list.", "domains.not_list"
            )
        )
        return
    directory_paths = {
        item.get("path") for item in plan.get("directories", []) if isinstance(item, dict)
    }
    for index, domain in enumerate(domains):
        base = f"business_domains[{index}]"
        if not isinstance(domain, dict):
            issues.append(
                ValidationIssue(
                    "error", base, "Domain entries must be mappings.", "domain.not_mapping"
                )
            )
            continue
        domain_id = domain.get("id")
        if not isinstance(domain_id, str) or not _DOMAIN_ID_RE.match(domain_id):
            issues.append(
                ValidationIssue(
                    "error", f"{base}.id", "Domain id has an invalid shape.", "domain.invalid_id"
                )
            )
        directories = domain.get("directories", [])
        if not isinstance(directories, list):
            issues.append(
                ValidationIssue(
                    "error",
                    f"{base}.directories",
                    "Domain directories must be a list.",
                    "domain.directories.not_list",
                )
            )
            continue
        for dir_index, directory in enumerate(directories):
            path = f"{base}.directories[{dir_index}]"
            if not isinstance(directory, str) or not directory.strip():
                issues.append(
                    ValidationIssue(
                        "error",
                        path,
                        "Domain directory path must be a non-empty string.",
                        "domain.directory_invalid",
                    )
                )
                continue
            _check_safe_relative_path(directory, path, "domain.directory_unsafe_path", issues)
            if directory not in directory_paths:
                issues.append(
                    ValidationIssue(
                        "error",
                        path,
                        "Domain maps to an unknown directory path.",
                        "domain.directory_unknown",
                    )
                )


def _check_safe_relative_path(
    value: str, path: str, code: str, issues: list[ValidationIssue]
) -> None:
    normalized = value.replace("\\", "/").strip()
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    has_env = "$" in normalized or "%" in normalized or os.path.expandvars(normalized) != normalized
    if (
        not normalized
        or "\x00" in normalized
        or normalized.startswith("~")
        or Path(normalized).is_absolute()
        or PureWindowsPath(normalized).is_absolute()
        or any(part == ".." for part in parts)
        or has_env
    ):
        issues.append(
            ValidationIssue(
                "error",
                path,
                "Path-like entries must be explicit repository-relative paths without absolute, parent, env, home, or NUL expansion.",
                code,
            )
        )


def _check_generated_metadata(plan: dict[str, Any], issues: list[ValidationIssue]) -> None:
    requires_fingerprint = plan.get("schema_version") == SCHEMA_VERSION or "generated" in plan
    if not requires_fingerprint:
        return

    generated = plan.get("generated")
    if not isinstance(generated, dict):
        issues.append(
            ValidationIssue(
                "error",
                "generated",
                "Generated metadata is required for current schema plans.",
                "generated.required",
            )
        )
        return

    managed_keys = generated.get("managed_keys")
    if not isinstance(managed_keys, list) or not all(
        isinstance(item, str) for item in managed_keys
    ):
        issues.append(
            ValidationIssue(
                "error",
                "generated.managed_keys",
                "generated.managed_keys must be a list of strings.",
                "generated.managed_keys.invalid",
            )
        )
    elif managed_keys != list(MANAGED_KEYS):
        issues.append(
            ValidationIssue(
                "error",
                "generated.managed_keys",
                "generated.managed_keys does not match the managed schema keys.",
                "generated.managed_keys.mismatch",
            )
        )

    fingerprint = generated.get("fingerprint")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        issues.append(
            ValidationIssue(
                "error",
                "generated.fingerprint",
                "generated.fingerprint must be a SHA-256 hex digest.",
                "generated.fingerprint.invalid",
            )
        )
        return
    if compute_managed_fingerprint(plan) != fingerprint:
        issues.append(
            ValidationIssue(
                "error",
                "generated.fingerprint",
                "generated.fingerprint does not match managed content.",
                "generated.fingerprint.mismatch",
            )
        )


def _check_overwrite_policy(plan: dict[str, Any], issues: list[ValidationIssue]) -> None:
    if "overwrite_policy" not in plan:
        return

    policy = plan.get("overwrite_policy")
    if not isinstance(policy, dict):
        issues.append(
            ValidationIssue(
                "error",
                "overwrite_policy",
                "overwrite_policy must be a mapping.",
                "overwrite_policy.not_mapping",
            )
        )
        return

    mode = policy.get("mode")
    if not isinstance(mode, str) or not mode.strip():
        issues.append(
            ValidationIssue(
                "error",
                "overwrite_policy.mode",
                "overwrite_policy.mode is required.",
                "overwrite_policy.mode_required",
            )
        )
    elif mode not in {"protect_manual_edits", "overwrite"}:
        issues.append(
            ValidationIssue(
                "error",
                "overwrite_policy.mode",
                "overwrite_policy.mode is not supported.",
                "overwrite_policy.mode_unsupported",
            )
        )

    for key in ("managed_fingerprint_required", "force_overwrite"):
        if key in policy and not isinstance(policy.get(key), bool):
            issues.append(
                ValidationIssue(
                    "error",
                    f"overwrite_policy.{key}",
                    f"overwrite_policy.{key} must be a boolean.",
                    f"overwrite_policy.{key}.not_bool",
                )
            )
