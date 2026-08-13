"""Multi-runtime source scanner v3 — structured inventory for Phase 42.

Produces ``source-inventory.json`` compatible with
``release_meta_schema.validate_source_inventory`` while adding separate top-level
sections for services, API surfaces, data models, frontend callers, deployment
assets, and tests. Supports incremental rescans via a content-hash cache under
``.repo-wiki/cache/``.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.orchestration.release_meta_schema import SCHEMA_VERSION_SOURCE_INVENTORY
from repo_wiki.scanner.artifacts import is_product_source_path
from repo_wiki.scanner.fastapi_routes import FastAPIEndpoint, extract_fastapi_endpoints
from repo_wiki.scanner.repository_scanner import RepositoryScanner

# ---------------------------------------------------------------------------
# Cache layout
# ---------------------------------------------------------------------------

CACHE_DIRNAME = ".repo-wiki"
CACHE_SUBDIR = "cache"
STATE_FILENAME = "scanner_v3_state.json"


@dataclass
class FileScanRecord:
    """Per-file structured signals (subset merged into inventory)."""

    path: str
    language: str
    content_sha256: str
    services: list[dict[str, Any]] = field(default_factory=list)
    api_surfaces: list[dict[str, Any]] = field(default_factory=list)
    data_models: list[dict[str, Any]] = field(default_factory=list)
    frontend_callers: list[dict[str, Any]] = field(default_factory=list)
    deployment: list[dict[str, Any]] = field(default_factory=list)
    tests: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "language": self.language,
            "content_sha256": self.content_sha256,
            "services": self.services,
            "api_surfaces": self.api_surfaces,
            "data_models": self.data_models,
            "frontend_callers": self.frontend_callers,
            "deployment": self.deployment,
            "tests": self.tests,
        }


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_json(data: Any) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _scanner_config_payload(config: RepoWikiConfig) -> dict[str, Any]:
    return {
        "project_exclude": sorted(config.project.exclude),
        "scan_exclude_dirs": sorted(config.scan.exclude_dirs),
        "security_deny_dirs": sorted(config.security.deny_dirs),
        "security_deny_globs": sorted(config.security.deny_globs),
        "max_file_size_kb": config.security.max_file_size_kb,
        "max_file_count": config.scan.max_file_count,
        "follow_symlinks": config.scan.follow_symlinks,
        "include_hidden": config.scan.include_hidden,
        "skip_binary_files": config.security.skip_binary_files,
    }


def _scanner_config_fingerprint(config: RepoWikiConfig) -> str:
    return _sha256_json(_scanner_config_payload(config))


def _source_fingerprint(path_hashes: dict[str, str]) -> str:
    return _sha256_json({"files": sorted(path_hashes.items())})


def _lang_from_suffix(path: Path) -> str:
    m = {
        ".py": "python",
        ".java": "java",
        ".kt": "kotlin",
        ".go": "go",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".js": "javascript",
        ".jsx": "jsx",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".sql": "sql",
        ".prisma": "prisma",
        ".dockerfile": "dockerfile",
    }
    suf = path.suffix.lower()
    if suf == ".dockerfile" or path.name.lower() == "dockerfile":
        return "dockerfile"
    return m.get(suf, "unknown")


def _scan_java_like(text: str, rel: str, record: FileScanRecord) -> None:
    if re.search(r"@(?:RestController|Controller|Service|Component)\b", text):
        record.services.append(
            {
                "kind": "spring_component",
                "evidence_path": rel,
            }
        )
    method_map = {
        "GetMapping": "GET",
        "PostMapping": "POST",
        "PutMapping": "PUT",
        "PatchMapping": "PATCH",
        "DeleteMapping": "DELETE",
        "RequestMapping": "GET",
    }
    for ann, route in re.findall(
        r"@((?:Get|Post|Put|Patch|Delete|Request)Mapping)\(\s*(?:value\s*=\s*)?[\"']([^\"']+)[\"']",
        text,
    ):
        record.api_surfaces.append(
            {
                "runtime": "java-spring",
                "method": method_map.get(ann, "GET"),
                "path": route,
                "handler_hint": rel,
                "evidence_path": rel,
            }
        )
    for ent in re.findall(
        r"@Entity\b[\s\S]{0,200}?\bclass\s+([A-Za-z_][A-Za-z0-9_]*)",
        text,
    ):
        record.data_models.append(
            {
                "kind": "jpa_entity",
                "name": ent,
                "evidence_path": rel,
            }
        )


def _scan_python(text: str, rel: str, record: FileScanRecord) -> None:
    if re.search(r"\bFastAPI\s*\(", text) or re.search(r"\bAPIRouter\s*\(", text):
        record.services.append({"kind": "python_fastapi_app", "evidence_path": rel})
    if re.search(r"\bFlask\s*\(", text):
        record.services.append({"kind": "python_flask_app", "evidence_path": rel})
    fastapi_endpoints = extract_fastapi_endpoints([(rel, text)])
    if fastapi_endpoints:
        for endpoint in fastapi_endpoints:
            record.api_surfaces.append(
                {
                    "runtime": "python",
                    "method": endpoint.method,
                    "path": endpoint.path,
                    "handler": endpoint.handler,
                    "evidence_path": rel,
                }
            )
    else:
        for meth, path_lit, handler in re.findall(
            r"@(?:router|app|bp)\.(get|post|put|patch|delete)\(\s*[\"']([^\"']*)[\"'][^)]*\)\s*(?:async\s+)?def\s+(\w+)",
            text,
            re.IGNORECASE,
        ):
            record.api_surfaces.append(
                {
                    "runtime": "python",
                    "method": meth.upper(),
                    "path": path_lit,
                    "handler": handler,
                    "evidence_path": rel,
                }
            )
    for base in re.findall(
        r"class\s+(\w+)\s*\(\s*(?:BaseModel|SQLModel|DeclarativeBase|db\.Model)",
        text,
    ):
        record.data_models.append(
            {
                "kind": "python_model",
                "name": base,
                "evidence_path": rel,
            }
        )


def _record_has_fastapi_service(record: dict[str, Any]) -> bool:
    return any(item.get("kind") == "python_fastapi_app" for item in record.get("services", []))


def _fastapi_surface(endpoint: FastAPIEndpoint) -> dict[str, Any]:
    return {
        "runtime": "python",
        "method": endpoint.method,
        "path": endpoint.path,
        "handler": endpoint.handler,
        "evidence_path": endpoint.file_path,
    }


def _with_full_repo_fastapi_surfaces(
    cached_records: dict[str, dict[str, Any]],
    python_files: list[tuple[str, str]],
) -> dict[str, dict[str, Any]]:
    """Replace per-file FastAPI routes with one full-repo extract (joined prefixes)."""
    endpoints = extract_fastapi_endpoints(python_files)
    by_file: dict[str, list[FastAPIEndpoint]] = {}
    for endpoint in endpoints:
        by_file.setdefault(endpoint.file_path, []).append(endpoint)

    overlayed: dict[str, dict[str, Any]] = {}
    for path, record in cached_records.items():
        if path not in by_file and not _record_has_fastapi_service(record):
            overlayed[path] = record
            continue
        copied = dict(record)
        copied["api_surfaces"] = [
            item for item in record.get("api_surfaces", []) if item.get("runtime") != "python"
        ]
        copied["api_surfaces"].extend(
            _fastapi_surface(endpoint) for endpoint in by_file.get(path, [])
        )
        overlayed[path] = copied
    return overlayed


def _scan_js_ts(text: str, rel: str, record: FileScanRecord) -> None:
    if re.search(r"\bexpress\s*\(\s*\)", text, re.I) or re.search(
        r"require\s*\(\s*['\"]express['\"]\s*\)", text
    ):
        record.services.append({"kind": "nodejs_express", "evidence_path": rel})
    seen_routes: set[tuple[str, str]] = set()
    for m in re.finditer(
        r"(?:app|router)\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)[\"']",
        text,
        re.I,
    ):
        meth = m.group(1).upper()
        path_lit = m.group(2)
        route_key = (meth, path_lit)
        if route_key in seen_routes:
            continue
        seen_routes.add(route_key)
        handler = "anonymous"
        rest = text[m.end() :]
        hm = re.match(r"\s*,\s*(\w+)", rest)
        if hm:
            handler = hm.group(1)
        record.api_surfaces.append(
            {
                "runtime": "nodejs",
                "method": meth,
                "path": path_lit,
                "handler": handler,
                "evidence_path": rel,
            }
        )
    # Frontend callers
    for m in re.finditer(
        r"(axios\.(?:get|post|put|patch|delete)|fetch\s*\()\s*\(\s*[`\"']([^`\"']+)[`\"']",
        text,
    ):
        record.frontend_callers.append(
            {
                "kind": "http_client",
                "pattern": m.group(1),
                "target": m.group(2),
                "evidence_path": rel,
            }
        )


def _scan_go(text: str, rel: str, record: FileScanRecord) -> None:
    if re.search(r"\bfunc\s+main\s*\(", text):
        record.services.append({"kind": "go_main", "evidence_path": rel})
    for path_lit, handler in re.findall(
        r"http\.HandleFunc\s*\(\s*[\"']([^\"']+)[\"']\s*,\s*(\w+)", text
    ):
        record.api_surfaces.append(
            {
                "runtime": "go",
                "method": "GET",
                "path": path_lit,
                "handler": handler,
                "evidence_path": rel,
            }
        )
    for name, body in re.findall(r"type\s+(\w+)\s+struct\s*\{([^}]*)\}", text, re.DOTALL):
        if re.search(r"`[^`]*db:", body):
            record.data_models.append(
                {
                    "kind": "go_struct_db",
                    "name": name,
                    "evidence_path": rel,
                }
            )


def _scan_openapi_yaml(text: str, rel: str, record: FileScanRecord) -> None:
    # Lightweight path extraction (full YAML parse optional)
    for path_lit in re.findall(r"^\s+(/[^{\n]+):\s*$", text, re.MULTILINE):
        p = path_lit.strip().strip("'\"")
        if p.startswith("/"):
            record.api_surfaces.append(
                {
                    "kind": "openapi_path",
                    "path": p,
                    "evidence_path": rel,
                }
            )


def _scan_prisma(text: str, rel: str, record: FileScanRecord) -> None:
    for m in re.findall(r"^\s*model\s+(\w+)\s*\{", text, re.MULTILINE):
        record.data_models.append({"kind": "prisma_model", "name": m, "evidence_path": rel})


def _scan_dockerfile(text: str, rel: str, record: FileScanRecord) -> None:
    base = None
    for line in text.splitlines():
        if line.strip().upper().startswith("FROM "):
            base = line.strip().split(None, 1)[-1]
            break
    record.deployment.append(
        {
            "kind": "dockerfile",
            "base_image_hint": base or "unknown",
            "evidence_path": rel,
        }
    )


def _scan_compose(text: str, rel: str, record: FileScanRecord) -> None:
    for svc in re.findall(r"^\s{2}(\w+):\s*$", text, re.MULTILINE):
        if svc not in ("version", "services", "networks", "volumes"):
            record.deployment.append(
                {"kind": "compose_service", "service": svc, "evidence_path": rel}
            )
            record.services.append(
                {
                    "kind": "docker_compose_service",
                    "name": svc,
                    "evidence_path": rel,
                }
            )


def _scan_ci(text: str, rel: str, record: FileScanRecord) -> None:
    if "jobs:" in text or "steps:" in text:
        record.deployment.append({"kind": "ci_workflow", "evidence_path": rel})


def _scan_tests(path: Path, text: str, rel: str, record: FileScanRecord) -> None:
    lower = rel.lower()
    if "test" not in lower and "/__tests__/" not in lower:
        return
    framework = "unknown"
    if "pytest" in text or "import pytest" in text:
        framework = "pytest"
    elif "jest" in text or "@jest" in text:
        framework = "jest"
    elif "mocha" in text:
        framework = "mocha"
    elif "unittest" in text:
        framework = "unittest"
    elif "testing" in text and "go test" in text:
        framework = "go_test"
    record.tests.append(
        {
            "framework_guess": framework,
            "evidence_path": rel,
        }
    )


def scan_single_file(rel: Path, text: str) -> FileScanRecord:
    """Parse one file's text into a FileScanRecord."""
    rel_s = rel.as_posix()
    h = _sha256_text(text)
    lang = _lang_from_suffix(rel)
    record = FileScanRecord(path=rel_s, language=lang, content_sha256=h)

    if lang in {"java", "kotlin"}:
        _scan_java_like(text, rel_s, record)
    if lang == "python":
        _scan_python(text, rel_s, record)
        _scan_tests(rel, text, rel_s, record)
    if lang in {"typescript", "tsx", "javascript", "jsx"}:
        _scan_js_ts(text, rel_s, record)
        _scan_tests(rel, text, rel_s, record)
    if lang == "go":
        _scan_go(text, rel_s, record)
        _scan_tests(rel, text, rel_s, record)
    if lang == "yaml":
        if "openapi" in text.lower() or "swagger" in text.lower():
            _scan_openapi_yaml(text, rel_s, record)
        if rel.name.lower() in (
            "docker-compose.yml",
            "docker-compose.yaml",
            "compose.yml",
            "compose.yaml",
        ) or ("docker-compose" in text.lower() and "services:" in text):
            _scan_compose(text, rel_s, record)
        if ".github/workflows" in rel_s.replace("\\", "/"):
            _scan_ci(text, rel_s, record)
    if lang == "json" and "openapi" in text.lower():
        # Minimal JSON openapi paths
        if "/paths" in text or '"paths"' in text:
            try:
                data = json.loads(text)
                paths = data.get("paths") or {}
                for p in paths:
                    record.api_surfaces.append(
                        {
                            "kind": "openapi_json_path",
                            "path": p,
                            "evidence_path": rel_s,
                        }
                    )
            except json.JSONDecodeError:
                pass
    if lang == "prisma":
        _scan_prisma(text, rel_s, record)
    if lang == "dockerfile" or rel.name.lower() == "dockerfile":
        _scan_dockerfile(text, rel_s, record)

    # Health / probe hints in any code
    if re.search(r"(health|readiness|liveness)", text, re.I):
        record.deployment.append({"kind": "health_probe_hint", "evidence_path": rel_s})

    if not is_product_source_path(rel_s):
        if record.api_surfaces or record.services:
            record.tests.append({"kind": "non_product_runtime", "evidence_path": rel_s})
        record.api_surfaces = []
        record.services = []

    return record


def _merge_lists(dst: list[dict[str, Any]], src: list[dict[str, Any]]) -> None:
    seen = {json.dumps(x, sort_keys=True) for x in dst}
    for item in src:
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            seen.add(key)
            dst.append(item)


class MultiRuntimeSourceScannerV3:
    """Incremental multi-runtime scanner."""

    def __init__(self, config: RepoWikiConfig) -> None:
        self.config = config
        self.root = Path(config.project.root).resolve()
        self._legacy = RepositoryScanner(config)

    def _state_path(self) -> Path:
        return self.root / CACHE_DIRNAME / CACHE_SUBDIR / STATE_FILENAME

    def _load_state(self) -> dict[str, Any]:
        p = self._state_path()
        if not p.exists():
            return {"version": 1, "file_hashes": {}, "records": {}}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"version": 1, "file_hashes": {}, "records": {}}

    def _save_state(self, state: dict[str, Any]) -> None:
        p = self._state_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    def scan(
        self,
        *,
        incremental: bool = True,
        batch_size: int = 250,
        persist_state: bool = True,
    ) -> dict[str, Any]:
        """Run scanner and return inventory dict (also suitable for JSON export)."""
        started_at = datetime.now(UTC).replace(microsecond=0)
        start_monotonic = time.perf_counter()
        state = self._load_state() if incremental else {"file_hashes": {}, "records": {}}
        hashes: dict[str, str] = dict(state.get("file_hashes", {}))
        cached_records: dict[str, dict[str, Any]] = dict(state.get("records", {}))

        files_out: list[dict[str, Any]] = []
        rescanned = 0
        reused = 0
        files_seen = 0
        batches_processed = 0

        current_paths: set[str] = set()
        current_hashes: dict[str, str] = {}
        python_files: list[tuple[str, str]] = []

        for batch in self._legacy.iter_file_batches(batch_size=batch_size):
            batches_processed += 1
            for sf in batch:
                rel = sf.path
                rel_s = rel.as_posix()
                current_paths.add(rel_s)
                files_seen += 1
                text = sf.text
                digest = _sha256_text(text)
                current_hashes[rel_s] = digest
                if rel.suffix.lower() == ".py" and is_product_source_path(rel_s):
                    python_files.append((rel_s, text))

                if incremental and hashes.get(rel_s) == digest and rel_s in cached_records:
                    record_dict = cached_records[rel_s]
                    reused += 1
                else:
                    fr = scan_single_file(rel, text)
                    record_dict = fr.to_dict()
                    hashes[rel_s] = digest
                    cached_records[rel_s] = record_dict
                    rescanned += 1

                files_out.append(
                    {
                        "path": record_dict["path"],
                        "language": record_dict["language"],
                        "content_sha256": record_dict["content_sha256"],
                    }
                )

        # Drop stale paths from cache
        stale = set(hashes.keys()) - current_paths
        deleted = len(stale)
        for s in stale:
            hashes.pop(s, None)
            cached_records.pop(s, None)

        scanner_config_fingerprint = _scanner_config_fingerprint(self.config)
        inventory_fingerprint = _source_fingerprint(current_hashes)
        completed_at = datetime.now(UTC).replace(microsecond=0)
        elapsed_seconds = round(time.perf_counter() - start_monotonic, 6)
        checkpoint = {
            "batch_size": batch_size,
            "batches_processed": batches_processed,
            "files_seen": files_seen,
            "files_rescanned": rescanned,
            "files_reused": reused,
            "files_deleted": deleted,
            "rescanned": rescanned,
            "reused": reused,
            "deleted": deleted,
            "scanner_config_fingerprint": scanner_config_fingerprint,
            "inventory_fingerprint": inventory_fingerprint,
            "source_fingerprint": inventory_fingerprint,
            "started_at": started_at.isoformat().replace("+00:00", "Z"),
            "completed_at": completed_at.isoformat().replace("+00:00", "Z"),
            "elapsed_seconds": elapsed_seconds,
        }

        # Aggregate top-level sections (separate signal families)
        services: list[dict[str, Any]] = []
        api_surfaces: list[dict[str, Any]] = []
        data_models: list[dict[str, Any]] = []
        frontend_callers: list[dict[str, Any]] = []
        deployment_assets: list[dict[str, Any]] = []
        tests: list[dict[str, Any]] = []
        inventory_records = _with_full_repo_fastapi_surfaces(cached_records, python_files)

        for _path, rec in sorted(inventory_records.items()):
            _merge_lists(services, rec.get("services", []))
            _merge_lists(api_surfaces, rec.get("api_surfaces", []))
            _merge_lists(data_models, rec.get("data_models", []))
            _merge_lists(frontend_callers, rec.get("frontend_callers", []))
            _merge_lists(deployment_assets, rec.get("deployment", []))
            _merge_lists(tests, rec.get("tests", []))

        new_state = {
            "version": 1,
            "file_hashes": hashes,
            "records": cached_records,
            "checkpoint": checkpoint,
        }
        if persist_state:
            self._save_state(new_state)

        inventory = {
            "schema_version": SCHEMA_VERSION_SOURCE_INVENTORY,
            "generated_at": datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "repository_root": str(self.root),
            "scanner": {
                "name": "multi_runtime_source_scanner_v3",
                "incremental": incremental,
                "stats": {
                    "files_scanned": files_seen,
                    "files_rescanned": rescanned,
                    "files_cached": reused,
                    "files_deleted": deleted,
                    "batches_processed": batches_processed,
                },
                "checkpoint": checkpoint,
            },
            "services": services,
            "api_surfaces": api_surfaces,
            "data_models": data_models,
            "frontend_callers": frontend_callers,
            "deployment_assets": deployment_assets,
            "tests": tests,
            "files": files_out,
        }
        return inventory


def write_source_inventory_json(
    config: RepoWikiConfig,
    output_path: Path | None = None,
    *,
    incremental: bool = True,
) -> Path:
    """Write ``source-inventory.json`` under repo meta path by default."""
    scanner = MultiRuntimeSourceScannerV3(config)
    data = scanner.scan(incremental=incremental)
    if output_path is None:
        root = Path(config.project.root).resolve()
        output_path = (
            root / ".repo-agent-eval" / "repowiki" / "zh" / "meta" / "source-inventory.json"
        )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path


def scan_repository_source_inventory_v3(
    repository_root: Path | str,
    *,
    incremental: bool = True,
) -> dict[str, Any]:
    """Convenience: scan a filesystem path with default RepoWikiConfig."""
    root = Path(repository_root).resolve()
    cfg = RepoWikiConfig.model_validate({"project": {"root": str(root)}})
    return MultiRuntimeSourceScannerV3(cfg).scan(incremental=incremental)
