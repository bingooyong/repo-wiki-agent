"""Stable read-only JSON contracts over `.repo-agent-eval/repowiki/zh`.

This module intentionally avoids repo-wiki runtime bootstrapping, config loading,
indexing, embedding, network, and any writes. It only reads the fixed published
READY manifest plus release content/meta sidecars.
"""

from __future__ import annotations

import json
import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SEARCH_SCHEMA_VERSION = "repo_agent.search/1.0"
GRAPH_SCHEMA_VERSION = "repo_agent.graph/1.0"
_RELEASE_MANIFEST_REL = Path(".repo-agent-eval") / "repowiki" / "zh" / "manifest.json"
_CITE_RE = re.compile(r"<cite>\s*([^<]+?)\s*</cite>")
_CITE_TARGET_RE = re.compile(r"^(?P<path>.*?):(?P<start>\d+)(?:-(?P<end>\d+))?(?P<label>.*)$")
_SCHEMA_RE = re.compile(r"^repo_agent\.(?P<artifact>[a-z_]+)/(?P<major>\d+)\.(?P<minor>\d+)$")
_GIT_COMMIT_RE = re.compile(r"[0-9a-f]{7,40}")
_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w:])/(?:[^\s'\"<>:]+/)*[^\s'\"<>:]+")
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^\s'\"]+"),
    re.compile(r"\b[A-Za-z0-9_-]{32,}\b"),
]


@dataclass(frozen=True)
class ReadyRelease:
    root: Path
    release_root: Path
    manifest_path: Path
    manifest: dict[str, Any]
    content_root: Path
    meta_root: Path
    release_meta: dict[str, Any] | None = None


def build_search_contract(
    repo_root: Path,
    *,
    query: str,
    module: str | None = None,
    top_k: int = 10,
) -> tuple[dict[str, Any], int]:
    release, error = _load_ready_release(repo_root, SEARCH_SCHEMA_VERSION)
    if error:
        error.update(
            {"query": query, "top_k": top_k, "results": [], "diagnostics": _diagnostics(None)}
        )
        return error, 1

    assert release is not None
    pages, page_error = _load_pages(release)
    if page_error:
        page_error.update(
            {"query": query, "top_k": top_k, "results": [], "diagnostics": _diagnostics(release)}
        )
        return page_error, 1

    query_terms = _terms(query)
    module_terms = _terms(module or "")
    ranked: list[dict[str, Any]] = []
    for page in pages:
        haystack = " ".join(
            str(page.get(key, "")) for key in ("path", "title", "content", "source_text")
        ).lower()
        if module_terms and not all(term in haystack for term in module_terms):
            continue
        score, reasons = _score_page(haystack, query_terms)
        if score <= 0 and query_terms:
            continue
        result = _page_search_result(page, score=score, reasons=reasons)
        if result is not None:
            ranked.append(result)

    ranked.sort(
        key=lambda item: (-float(item["score"]), str(item["page_path"]), str(item["source"]))
    )
    results = ranked[: max(0, int(top_k))]
    payload = _base_payload(SEARCH_SCHEMA_VERSION, release)
    payload.update(
        {
            "status": "ok",
            "error": None,
            "query": query,
            "top_k": top_k,
            "results": results,
            "diagnostics": _diagnostics(
                release,
                searched_pages=len(pages),
                candidate_count=len(ranked),
                retrieval_order=["ready_manifest", "ready_page_registry", "ready_evidence_index"],
            ),
        }
    )
    return payload, 0


def build_graph_contract(repo_root: Path, *, module: str) -> tuple[dict[str, Any], int]:
    release, error = _load_ready_release(repo_root, GRAPH_SCHEMA_VERSION)
    if error:
        error.update(
            {"module": module, "found": False, "suggestions": [], "node": None, "edges": []}
        )
        return error, 1

    assert release is not None
    nodes, edges, graph_diagnostics = _load_graph_data(release)
    if graph_diagnostics.get("graph_metadata_invalid"):
        payload = _base_payload(GRAPH_SCHEMA_VERSION, release)
        payload.update(
            {
                "status": "error",
                "error": {
                    "code": "graph_metadata_invalid",
                    "message": "Graph metadata sidecar is incompatible or malformed",
                },
                "module": module,
                "found": False,
                "suggestions": [],
                "node": None,
                "edges": [],
                "diagnostics": _diagnostics(release, **graph_diagnostics),
            }
        )
        return payload, 1

    if not nodes:
        payload = _base_payload(GRAPH_SCHEMA_VERSION, release)
        payload.update(
            {
                "status": "error",
                "error": {
                    "code": "graph_metadata_unavailable",
                    "message": "No usable graph metadata found in meta/service-registry.json or meta/repowiki-metadata.json",
                },
                "module": module,
                "found": False,
                "suggestions": [],
                "node": None,
                "edges": [],
                "diagnostics": _diagnostics(release, **graph_diagnostics),
            }
        )
        return payload, 1

    canonical = _find_node_key(nodes, module)
    payload = _base_payload(GRAPH_SCHEMA_VERSION, release)
    if canonical is None:
        suggestions = sorted(nodes.keys())[:20]
        payload.update(
            {
                "status": "ok",
                "error": None,
                "module": module,
                "found": False,
                "suggestions": suggestions,
                "node": None,
                "edges": [],
                "diagnostics": _diagnostics(
                    release, node_count=len(nodes), edge_count=len(edges), **graph_diagnostics
                ),
            }
        )
        return payload, 0

    connected = [
        edge for edge in edges if edge.get("from") == canonical or edge.get("to") == canonical
    ]
    connected.sort(
        key=lambda item: (
            str(item.get("from", "")),
            str(item.get("to", "")),
            str(item.get("type", "")),
        )
    )
    payload.update(
        {
            "status": "ok",
            "error": None,
            "module": module,
            "found": True,
            "suggestions": [],
            "node": nodes[canonical],
            "edges": connected,
            "diagnostics": _diagnostics(
                release, node_count=len(nodes), edge_count=len(edges), **graph_diagnostics
            ),
        }
    )
    return payload, 0


def _load_ready_release(
    repo_root: Path, schema_version: str
) -> tuple[ReadyRelease | None, dict[str, Any] | None]:
    root = repo_root.resolve()
    manifest_path = (root / _RELEASE_MANIFEST_REL).resolve()
    try:
        manifest_path.relative_to(root)
    except ValueError:
        return None, _error_payload(
            schema_version, root, "unsafe_path", "release manifest path escapes repository root"
        )
    if not manifest_path.is_file():
        return None, _error_payload(
            schema_version,
            root,
            "release_missing",
            f"READY release manifest not found: {_RELEASE_MANIFEST_REL.as_posix()}",
        )

    loaded, load_error = _read_json_with_error(manifest_path)
    if load_error:
        return None, _error_payload(
            schema_version,
            root,
            "manifest_malformed",
            f"READY release manifest is invalid JSON: {load_error}",
        )
    if not isinstance(loaded, dict):
        return None, _error_payload(
            schema_version,
            root,
            "manifest_malformed",
            "READY release manifest root must be an object",
        )
    readiness = str(
        loaded.get("release_status")
        or loaded.get("readiness")
        or loaded.get("readiness_state")
        or ""
    ).upper()
    if readiness != "READY":
        return None, _error_payload(
            schema_version,
            root,
            "release_not_ready",
            "READY release is required (release_status/readiness/readiness_state must be READY)",
        )

    release_root = manifest_path.parent
    content_root, content_error = _validated_manifest_child_dir(
        loaded, release_root, "content_root", "content"
    )
    if content_error:
        return None, _error_payload(schema_version, root, "release_path_invalid", content_error)
    meta_root, meta_error = _validated_manifest_child_dir(loaded, release_root, "meta_root", "meta")
    if meta_error:
        return None, _error_payload(schema_version, root, "release_path_invalid", meta_error)
    assert content_root is not None
    assert meta_root is not None

    release_meta_path = meta_root / "release.json"
    release_meta: dict[str, Any] | None = None
    if release_meta_path.exists():
        release_loaded, release_error = _read_json_with_error(release_meta_path)
        if release_error:
            return None, _error_payload(
                schema_version,
                root,
                "release_meta_malformed",
                f"meta/release.json is invalid JSON: {release_error}",
            )
        release_errors = _validate_release_meta(release_loaded, loaded)
        if release_errors:
            return None, _error_payload(
                schema_version, root, "release_meta_invalid", "; ".join(release_errors)
            )
        assert isinstance(release_loaded, dict)
        release_meta = release_loaded

    return ReadyRelease(
        root=root,
        release_root=release_root,
        manifest_path=manifest_path,
        manifest=loaded,
        content_root=content_root,
        meta_root=meta_root,
        release_meta=release_meta,
    ), None


def _error_payload(schema_version: str, root: Path, code: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "status": "error",
        "error": {"code": code, "message": _redact(message)},
        "repo": _repo_identity(root),
        "release": None,
        "freshness": {"status": "unknown", "head": _git_head(root), "release_commit": None},
    }


def _base_payload(schema_version: str, release: ReadyRelease) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "repo": _repo_identity(release.root, release.manifest),
        "release": _release_provenance(release),
        "freshness": _freshness(release),
    }


def _repo_identity(root: Path, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    identity = {}
    if isinstance(manifest, dict):
        metadata = manifest.get("metadata")
        if isinstance(metadata, dict) and isinstance(metadata.get("repository_identity"), dict):
            identity = dict(metadata["repository_identity"])
    return {
        "root": ".",
        "name": _safe_str(identity.get("name") or root.name),
        "display_name": _safe_str(
            identity.get("display_name") or identity.get("name") or root.name
        ),
    }


def _release_provenance(release: ReadyRelease) -> dict[str, Any]:
    manifest = release.manifest
    meta = release.release_meta or {}
    return {
        "release_id": _safe_str(meta.get("release_id") or manifest.get("release_id")),
        "source_run_id": _safe_str(
            meta.get("source_run_id") or manifest.get("source_run_id") or manifest.get("run_id")
        ),
        "published_at": _safe_str(meta.get("published_at") or manifest.get("published_at")),
        "generated_at": _safe_str(manifest.get("generated_at")),
        "manifest_path": _safe_rel(release.manifest_path, release.root),
        "manifest_relative_path": _safe_rel(release.manifest_path, release.root),
        "content_root": _safe_rel(_content_root(release), release.root),
        "meta_root": _safe_rel(_meta_root(release), release.root),
        "target_git_commit": _raw_str(
            meta.get("target_git_commit")
            or manifest.get("target_git_commit")
            or manifest.get("wiki_git_commit")
        ),
    }


def _freshness(release: ReadyRelease) -> dict[str, Any]:
    head = _git_head(release.root)
    meta = release.release_meta or {}
    release_commit = _raw_str(
        meta.get("target_git_commit")
        or release.manifest.get("target_git_commit")
        or release.manifest.get("wiki_git_commit")
    )
    if not head or not release_commit:
        status = "unknown"
    elif head == release_commit:
        status = "fresh"
    else:
        status = "stale"
    return {"status": status, "head": head, "release_commit": release_commit}


def _git_head(root: Path) -> str | None:
    try:
        top_proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if top_proc.returncode != 0 or Path(top_proc.stdout.strip()).resolve() != root.resolve():
            return None
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value or None


def _load_pages(release: ReadyRelease) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    registry_payload, registry_error = _load_required_search_sidecar(
        release, "page-registry.json", "page_registry"
    )
    if registry_error:
        return [], registry_error
    evidence_payload, evidence_error = _load_required_search_sidecar(
        release, "evidence-index.json", "evidence_index"
    )
    if evidence_error:
        return [], evidence_error

    assert isinstance(registry_payload, dict)
    assert isinstance(evidence_payload, dict)
    evidence_by_page: dict[str, list[dict[str, Any]]] = {}
    for span in evidence_payload.get("spans", []):
        if not isinstance(span, dict):
            continue
        page_rel = _safe_source_path(span.get("page_relative_path") or span.get("page_path"))
        source = _safe_source_path(span.get("source_path"))
        if page_rel is None or source is None:
            continue
        evidence_by_page.setdefault(page_rel, []).append(span)

    pages: list[dict[str, Any]] = []
    content_root = _content_root(release)
    for item in registry_payload.get("pages", []):
        if not isinstance(item, dict):
            continue
        rel = _page_path_from_registry_item(item)
        if not rel:
            continue
        path = _safe_content_page_path(content_root, rel)
        if path is None:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        pages.append(
            {
                "path": rel,
                "title": _safe_str(
                    item.get("title")
                    or item.get("label")
                    or item.get("page_id")
                    or _title_from_markdown(content)
                    or Path(rel).stem
                ),
                "content": content,
                "evidence": evidence_by_page.get(rel, []),
                "aliases": _safe_aliases(item.get("aliases")),
            }
        )
    pages.sort(key=lambda page: str(page.get("path", "")))
    return pages, None


def _load_required_search_sidecar(
    release: ReadyRelease, filename: str, artifact: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    path = _meta_root(release) / filename
    if not path.is_file():
        return None, _error_payload(
            SEARCH_SCHEMA_VERSION,
            release.root,
            "search_sidecar_missing",
            f"Required READY sidecar is missing: meta/{filename}",
        )
    payload, load_error = _read_json_with_error(path)
    if load_error:
        return None, _error_payload(
            SEARCH_SCHEMA_VERSION,
            release.root,
            "search_sidecar_malformed",
            f"Required READY sidecar is invalid JSON: meta/{filename}: {load_error}",
        )
    validation_errors = _validate_search_sidecar(payload, artifact)
    if validation_errors:
        return None, _error_payload(
            SEARCH_SCHEMA_VERSION,
            release.root,
            "search_sidecar_malformed",
            f"Required READY sidecar is malformed: meta/{filename}: {'; '.join(validation_errors)}",
        )
    assert isinstance(payload, dict)
    return payload, None


def _validate_search_sidecar(payload: Any, artifact: str) -> list[str]:
    if not isinstance(payload, dict):
        return ["root must be a JSON object"]
    errors = _validate_repo_agent_header(payload, artifact, require_generated_at=True)
    if artifact == "page_registry":
        pages = payload.get("pages")
        if not isinstance(pages, list):
            errors.append("missing or invalid list field: 'pages'")
        else:
            for index, page in enumerate(pages):
                if not isinstance(page, dict):
                    errors.append(f"pages[{index}] must be an object")
                    continue
                for key in ("page_id", "relative_path", "category", "page_type"):
                    if not isinstance(page.get(key), str) or not page[key].strip():
                        errors.append(f"pages[{index}].{key} must be a non-empty string")
    elif artifact == "evidence_index":
        spans = payload.get("spans")
        if not isinstance(spans, list):
            errors.append("missing or invalid list field: 'spans'")
        else:
            for index, span in enumerate(spans):
                if not isinstance(span, dict):
                    errors.append(f"spans[{index}] must be an object")
                    continue
                for key in ("span_id", "page_relative_path", "source_path"):
                    if not isinstance(span.get(key), str) or not span[key].strip():
                        errors.append(f"spans[{index}].{key} must be a non-empty string")
                for key in ("start_line", "end_line"):
                    if key in span and span[key] is not None and type(span[key]) is not int:
                        errors.append(f"spans[{index}].{key} must be an integer")
    return errors


def _validate_release_meta(payload: Any, manifest: dict[str, Any]) -> list[str]:
    if not isinstance(payload, dict):
        return ["meta/release root must be a JSON object"]
    errors = _validate_repo_agent_header(payload, "meta_release", require_generated_at=False)
    for key in ("release_status", "release_id", "source_run_id", "published_at"):
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            errors.append(f"missing or invalid string field: {key!r}")
    status = payload.get("release_status")
    if isinstance(status, str) and status.upper() != "READY":
        errors.append("meta/release.json release_status must be READY")
    target_commit = payload.get("target_git_commit")
    if target_commit is not None and (
        not isinstance(target_commit, str) or not _GIT_COMMIT_RE.fullmatch(target_commit.strip())
    ):
        errors.append("target_git_commit must be null/absent or a 7-40 hex git commit")

    comparisons = (
        ("release_id", payload.get("release_id"), manifest.get("release_id")),
        (
            "source_run_id",
            payload.get("source_run_id"),
            manifest.get("source_run_id") or manifest.get("run_id"),
        ),
        (
            "target_git_commit",
            payload.get("target_git_commit"),
            manifest.get("target_git_commit") or manifest.get("wiki_git_commit"),
        ),
    )
    for key, release_value, manifest_value in comparisons:
        if release_value in (None, "") or manifest_value in (None, ""):
            continue
        if str(release_value) != str(manifest_value):
            errors.append(f"meta/release.json {key} does not match manifest")
    return errors


def _validate_repo_agent_header(
    payload: dict[str, Any], artifact: str, *, require_generated_at: bool
) -> list[str]:
    errors: list[str] = []
    schema_version = payload.get("schema_version")
    match = _SCHEMA_RE.fullmatch(schema_version) if isinstance(schema_version, str) else None
    if match is None or match.group("artifact") != artifact:
        errors.append(f"schema_version must match 'repo_agent.{artifact}/<major>.<minor>'")
    elif match.group("major") != "1":
        errors.append(f"schema_version major must be 1 for repo_agent.{artifact}")
    if require_generated_at and (
        not isinstance(payload.get("generated_at"), str) or not payload["generated_at"].strip()
    ):
        errors.append("missing or invalid string field: 'generated_at'")
    return errors


def _page_path_from_registry_item(item: dict[str, Any]) -> str | None:
    for key in ("relative_path", "path", "page_relative_path"):
        value = item.get(key)
        if isinstance(value, str) and value.endswith(".md") and _is_safe_relative(value):
            return value
    return None


def _content_root(release: ReadyRelease) -> Path:
    return release.content_root


def _meta_root(release: ReadyRelease) -> Path:
    return release.meta_root


def _validated_manifest_child_dir(
    manifest: dict[str, Any], release_root: Path, key: str, default: str
) -> tuple[Path | None, str | None]:
    raw = str(manifest.get(key) or default)
    if not _is_safe_relative(raw):
        return None, f"READY manifest {key} must be a safe relative path"
    child = release_root / raw
    try:
        child_stat = child.lstat()
    except OSError:
        return None, f"READY manifest {key} directory is missing: {default}"
    if stat.S_ISLNK(child_stat.st_mode):
        return None, f"READY manifest {key} directory must not be a symlink"
    if not stat.S_ISDIR(child_stat.st_mode):
        return None, f"READY manifest {key} must point to an existing directory"
    try:
        real_release_root = release_root.resolve(strict=True)
        real_child = child.resolve(strict=True)
        relative = real_child.relative_to(real_release_root)
    except (ValueError, OSError, RuntimeError):
        return None, f"READY manifest {key} real path must stay inside the release root"
    if real_child == real_release_root or not relative.parts:
        return None, f"READY manifest {key} real path must be inside the release root"
    return real_child, None


def _safe_content_page_path(content_root: Path, rel: str) -> Path | None:
    if not _is_safe_relative(rel) or not rel.endswith(".md"):
        return None
    root = content_root.resolve()
    candidate = content_root / rel
    current = content_root
    try:
        if content_root.is_symlink() or not content_root.is_dir():
            return None
        for part in Path(rel).parts:
            current = current / part
            if current.is_symlink():
                return None
        resolved = candidate.resolve()
        resolved.relative_to(root)
        if not resolved.is_file():
            return None
    except (OSError, RuntimeError, ValueError):
        return None
    return resolved


def _score_page(haystack: str, terms: list[str]) -> tuple[float, list[str]]:
    if not terms:
        return 1.0, ["empty-query-release-order"]
    matches = [term for term in terms if term in haystack]
    if not matches:
        return 0.0, []
    score = len(matches) / len(terms)
    if all(term in haystack for term in terms):
        score += 0.25
    return round(score, 6), ["keyword:" + term for term in sorted(set(matches))]


def _page_search_result(
    page: dict[str, Any], *, score: float, reasons: list[str]
) -> dict[str, Any] | None:
    content = str(page.get("content") or "")
    citations = _citations_from_page(page, content)
    if not citations:
        return None
    first_citation = citations[0]
    source = _safe_str(first_citation.get("source") or first_citation.get("file_path"))
    line_start = first_citation.get("line_start") or 1
    line_end = first_citation.get("line_end") or line_start
    page_path = _safe_str(page.get("path"))
    return {
        "chunk_id": page_path,
        "file_path": source,
        "source": source,
        "path": source,
        "module_name": "",
        "language": "markdown",
        "chunk_type": "ready_page",
        "symbol_name": _safe_str(page.get("title")),
        "score": score,
        "reasons": sorted(set(reasons)),
        "aliases": _safe_aliases(page.get("aliases")),
        "excerpt": _excerpt(content),
        "line_start": line_start,
        "line_end": line_end,
        "start_line": line_start,
        "end_line": line_end,
        "line_range": {"start": line_start, "end": line_end},
        "range": {"start": line_start, "end": line_end},
        "citations": citations,
        "page_path": page_path,
    }


def _citations_from_page(page: dict[str, Any], content: str) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for span in page.get("evidence", []) if isinstance(page.get("evidence"), list) else []:
        source = _safe_source_path(span.get("source_path"))
        if source is None:
            continue
        start = _positive_int(span.get("start_line") or span.get("line_start"), 1)
        end = _positive_int(span.get("end_line") or span.get("line_end"), start)
        citations.append(
            _citation_dict(source, start, max(start, end), _safe_str(span.get("span_id")))
        )
    for raw in _CITE_RE.findall(content):
        parsed = _parse_citation(raw)
        if parsed:
            citations.append(parsed)
    seen: set[tuple[str, int, int]] = set()
    deduped: list[dict[str, Any]] = []
    for citation in citations:
        key = (citation["source"], citation["line_start"], citation["line_end"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(citation)
    return deduped[:20]


def _parse_citation(raw: str) -> dict[str, Any] | None:
    match = _CITE_TARGET_RE.match(raw.strip())
    if not match:
        return None
    source = _safe_source_path(match.group("path"))
    if source is None:
        return None
    start = _positive_int(match.group("start"), 1)
    end = _positive_int(match.group("end"), start)
    return _citation_dict(source, start, max(start, end), match.group("label").strip())


def _citation_dict(source: str, start: int, end: int, label: str = "") -> dict[str, Any]:
    return {
        "source": source,
        "file_path": source,
        "line_start": start,
        "line_end": end,
        "start_line": start,
        "end_line": end,
        "line_range": {"start": start, "end": end},
        "range": {"start": start, "end": end},
        "label": _redact(label),
    }


def _load_graph_data(
    release: ReadyRelease,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {"graph_sources": [], "graph_source_errors": []}

    service_registry, service_error = _load_optional_json(
        _meta_root(release) / "service-registry.json"
    )
    if service_error:
        diagnostics["graph_source_errors"].append(f"service-registry.json:{service_error}")
    elif isinstance(service_registry, dict):
        service_errors = _validate_service_registry_for_graph(service_registry)
        if service_errors:
            diagnostics["graph_source_errors"].append(
                "service-registry.json:" + ";".join(service_errors)
            )
            diagnostics["graph_metadata_invalid"] = True
        else:
            before = len(nodes)
            _merge_service_registry(nodes, edges, service_registry)
            if len(nodes) > before:
                diagnostics["graph_sources"].append("service-registry.json")

    metadata, metadata_error = _load_optional_json(_meta_root(release) / "repowiki-metadata.json")
    if metadata_error:
        diagnostics["graph_source_errors"].append(f"repowiki-metadata.json:{metadata_error}")
    elif isinstance(metadata, dict):
        metadata_errors = _validate_optional_repo_agent_graph_sidecar(metadata, "repowiki_metadata")
        if metadata_errors:
            diagnostics["graph_source_errors"].append(
                "repowiki-metadata.json:" + ";".join(metadata_errors)
            )
            diagnostics["graph_metadata_invalid"] = True
        else:
            before_nodes = len(nodes)
            before_edges = len(edges)
            _merge_repowiki_metadata(nodes, edges, metadata)
            if len(nodes) > before_nodes or len(edges) > before_edges:
                diagnostics["graph_sources"].append("repowiki-metadata.json")

    dedup_edges = {json.dumps(edge, sort_keys=True, ensure_ascii=True): edge for edge in edges}
    return (
        dict(sorted(nodes.items())),
        [dedup_edges[key] for key in sorted(dedup_edges)],
        diagnostics,
    )


def _validate_service_registry_for_graph(payload: dict[str, Any]) -> list[str]:
    errors = _validate_repo_agent_header(payload, "service_registry", require_generated_at=True)
    services = payload.get("services")
    if not isinstance(services, list):
        errors.append("missing or invalid list field: 'services'")
    return errors


def _validate_optional_repo_agent_graph_sidecar(
    payload: dict[str, Any], artifact: str
) -> list[str]:
    schema_version = payload.get("schema_version")
    if schema_version is None:
        return []
    if not isinstance(schema_version, str):
        return ["schema_version must be a string when present"]
    match = _SCHEMA_RE.fullmatch(schema_version)
    if match is None:
        return []
    if match.group("major") != "1":
        return [f"schema_version major must be 1 for repo_agent.{match.group('artifact')}"]
    if match.group("artifact") != artifact:
        return [f"schema_version artifact should be repo_agent.{artifact} when present"]
    return []


def _merge_service_registry(
    nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]], payload: dict[str, Any]
) -> None:
    services = payload.get("services")
    if not isinstance(services, list):
        return
    for service in services:
        if not isinstance(service, dict):
            continue
        key = _node_key(
            service.get("service_id") or service.get("name") or service.get("display_name")
        )
        if not key:
            continue
        nodes[key] = {"id": key, **_scrub_obj(service)}
        for dep_key in ("dependencies", "depends_on", "upstream", "downstream"):
            deps = service.get(dep_key)
            if not isinstance(deps, list):
                continue
            for dep in deps:
                target = _node_key(
                    dep if not isinstance(dep, dict) else dep.get("service_id") or dep.get("target")
                )
                if target:
                    if dep_key in {"dependencies", "depends_on", "upstream"}:
                        edges.append({"from": key, "to": target, "type": dep_key})
                    else:
                        edges.append({"from": target, "to": key, "type": dep_key})


def _merge_repowiki_metadata(
    nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]], metadata: dict[str, Any]
) -> None:
    relations = metadata.get("knowledge_relations")
    if not isinstance(relations, list):
        return
    for rel in relations:
        if not isinstance(rel, dict):
            continue
        src = _node_key(rel.get("from") or rel.get("source") or rel.get("source_id"))
        dst = _node_key(rel.get("to") or rel.get("target") or rel.get("target_id"))
        if not src or not dst:
            continue
        nodes.setdefault(src, {"id": src})
        nodes.setdefault(dst, {"id": dst})
        edges.append(
            {
                "from": src,
                "to": dst,
                "type": _safe_str(rel.get("type") or rel.get("relation") or "related"),
            }
        )


def _find_node_key(nodes: dict[str, dict[str, Any]], module: str) -> str | None:
    wanted = _node_key(module)
    if wanted in nodes:
        return wanted
    wanted_lower = module.lower()
    for key, node in nodes.items():
        aliases = {
            key.lower(),
            _safe_str(node.get("display_name")).lower(),
            _safe_str(node.get("name")).lower(),
        }
        if wanted_lower in aliases:
            return key
    return None


def _node_key(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    if not text or not _is_safe_relative(text):
        return None
    return _redact(text).replace("/", ":")


def _read_json_with_error(path: Path) -> tuple[Any, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except OSError as exc:
        return None, exc.__class__.__name__
    except UnicodeDecodeError:
        return None, "UnicodeDecodeError"
    except json.JSONDecodeError as exc:
        return None, f"JSONDecodeError:{exc.msg}"


def _load_optional_json(path: Path) -> tuple[Any, str | None]:
    if not path.exists():
        return None, None
    payload, error = _read_json_with_error(path)
    if error:
        return None, error
    if not isinstance(payload, dict):
        return None, "root must be a JSON object"
    return payload, None


def _diagnostics(release: ReadyRelease | None, **extra: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "readonly": True,
        "ready_release_required": True,
        "selected_manifest": _RELEASE_MANIFEST_REL.as_posix(),
    }
    if release is not None:
        data["release_root"] = _safe_rel(release.release_root, release.root)
    data.update(_scrub_obj(extra))
    return data


def _terms(value: str) -> list[str]:
    return [term.lower() for term in re.findall(r"[\w\-\.]+", value, flags=re.UNICODE) if term]


def _excerpt(content: str, limit: int = 400) -> str:
    compact = re.sub(r"\s+", " ", content).strip()
    return _redact(compact[:limit])


def _title_from_markdown(content: str) -> str:
    for line in content.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return ""


def _safe_rel(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except (ValueError, OSError, RuntimeError):
        return ""


def _safe_source_path(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    if not text or not _is_safe_relative(text):
        return None
    return _redact(text)


def _safe_aliases(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_safe_str(item) for item in value if isinstance(item, str) and item.strip()]


def _is_safe_relative(value: str) -> bool:
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts and "\x00" not in value


def _safe_str(value: Any) -> str:
    return _redact(str(value)) if value is not None else ""


def _raw_str(value: Any) -> str:
    return str(value) if value is not None else ""


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _redact(value: str) -> str:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return _ABSOLUTE_PATH_RE.sub("[REDACTED_PATH]", redacted)


def _scrub_obj(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(k): _scrub_obj(v)
            for k, v in sorted(value.items())
            if _is_allowed_output_key(str(k))
        }
    if isinstance(value, list):
        return [_scrub_obj(v) for v in value]
    if isinstance(value, str):
        return _redact(value)
    return value


def _is_allowed_output_key(key: str) -> bool:
    lowered = key.lower()
    return not any(
        secret in lowered for secret in ("secret", "token", "password", "api_key", "apikey")
    )
