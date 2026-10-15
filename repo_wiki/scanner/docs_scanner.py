"""Documentation scanner with authority/freshness/conflict classification.

Phase 42.2:
- discovers markdown/rst/asciidoc/txt docs
- classifies doc types
- scores authority/specificity/freshness
- cross-checks claims against source-inventory signals
- emits docs-inventory.json compatible with release_meta_schema.validate_docs_inventory
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import Any

from repo_wiki.orchestration.release_meta_schema import SCHEMA_VERSION_DOCS_INVENTORY

_DEFAULT_KNOWLEDGE_PLAN_PATH = Path(".repo-wiki/knowledge-plan.yaml")

_DOC_SUFFIXES = {".md", ".markdown", ".rst", ".adoc", ".asciidoc", ".txt"}
_CACHE_DIR = ".repo-wiki/cache"
_CACHE_FILE = "docs_scanner_state.json"


def _normalize_rel_path(value: str | Path) -> str:
    normalized = str(value).replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _has_glob_magic(pattern: str) -> bool:
    return any(ch in pattern for ch in "*?[")


def _glob_matches(pattern: str, rel: str) -> bool:
    pattern = _normalize_rel_path(pattern)
    rel = _normalize_rel_path(rel)
    if not pattern:
        return False
    if pattern.endswith("/"):
        return rel.startswith(pattern)
    return rel == pattern or fnmatch.fnmatch(rel, pattern) or Path(rel).match(pattern)


@dataclass(frozen=True)
class DocsAllowlistEntry:
    """Plan-derived documentation allowlist entry."""

    pattern: str
    doc_type: str | None = None
    authority_level: str | None = None
    authority_score: float | None = None

    @classmethod
    def from_raw(cls, raw: Any) -> DocsAllowlistEntry | None:
        if isinstance(raw, str):
            pattern = _normalize_rel_path(raw)
            return cls(pattern=pattern) if pattern else None
        if not isinstance(raw, dict):
            return None

        patterns = raw.get("paths") or raw.get("path_globs") or raw.get("globs")
        if isinstance(patterns, list) and patterns:
            # Multi-path entries are expanded by DocsScanFilter.from_plan; keep the first here
            # for direct construction fallback.
            path_value: Any = patterns[0]
        else:
            path_value = (
                raw.get("path")
                or raw.get("glob")
                or raw.get("pattern")
                or raw.get("include")
                or raw.get("file")
            )
        if not isinstance(path_value, str):
            return None

        score_raw = raw.get("authority_score")
        try:
            authority_score = float(score_raw) if score_raw is not None else None
        except (TypeError, ValueError):
            authority_score = None

        pattern = _normalize_rel_path(path_value)
        if not pattern:
            return None
        return cls(
            pattern=pattern,
            doc_type=raw.get("doc_type") or raw.get("type"),
            authority_level=raw.get("authority_level") or raw.get("authority"),
            authority_score=authority_score,
        )

    def matches(self, rel: str) -> bool:
        return _glob_matches(self.pattern, rel)


@dataclass(frozen=True)
class DocsScanFilter:
    """Include/exclude filter for documentation scanning.

    The adapter intentionally accepts loose knowledge-plan shapes without importing the
    knowledge-plan package: root- or docs-level ``include``/``exclude`` glob lists plus
    allowlist entries expressed as strings or dictionaries with ``path``/``glob`` and
    optional ``doc_type``/``authority`` metadata.
    """

    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    allowlist: tuple[DocsAllowlistEntry, ...] = ()

    @classmethod
    def from_plan(cls, raw: Any) -> DocsScanFilter | None:
        if raw is None:
            return None
        if isinstance(raw, DocsScanFilter):
            return raw
        if not isinstance(raw, dict):
            return None

        include: list[str] = []
        exclude: list[str] = []
        allowlist: list[DocsAllowlistEntry] = []

        sections: list[dict[str, Any]] = [raw]
        for key in ("docs", "documentation", "docs_filter"):
            value = raw.get(key)
            if isinstance(value, dict):
                sections.append(value)

        for section in sections:
            include.extend(_coerce_str_list(section.get("include") or section.get("includes")))
            include.extend(
                _coerce_str_list(section.get("include_globs") or section.get("path_globs"))
            )
            exclude.extend(_coerce_str_list(section.get("exclude") or section.get("excludes")))
            exclude.extend(_coerce_str_list(section.get("exclude_globs")))

            for key in ("docs_allowlist", "allowlist", "documentation_allowlist", "documents"):
                entries = section.get(key)
                if isinstance(entries, dict):
                    entries = entries.get("entries") or entries.get("items") or entries.get("paths")
                if not isinstance(entries, list):
                    continue
                for item in entries:
                    if isinstance(item, dict):
                        multi_paths = (
                            item.get("paths") or item.get("path_globs") or item.get("globs")
                        )
                        if isinstance(multi_paths, list):
                            for path_value in multi_paths:
                                if isinstance(path_value, str):
                                    expanded = dict(item)
                                    expanded["path"] = path_value
                                    entry = DocsAllowlistEntry.from_raw(expanded)
                                    if entry is not None:
                                        allowlist.append(entry)
                            continue
                    entry = DocsAllowlistEntry.from_raw(item)
                    if entry is not None:
                        allowlist.append(entry)

        normalized = cls(
            include=tuple(dict.fromkeys(_normalize_rel_path(p) for p in include if p)),
            exclude=tuple(dict.fromkeys(_normalize_rel_path(p) for p in exclude if p)),
            allowlist=tuple(allowlist),
        )
        if not normalized.include and not normalized.exclude and not normalized.allowlist:
            return None
        return normalized

    @property
    def has_positive_scope(self) -> bool:
        return bool(self.include or self.allowlist)

    def allows(self, rel: str) -> bool:
        if any(_glob_matches(pattern, rel) for pattern in self.exclude):
            return False
        if not self.has_positive_scope:
            return True
        return any(_glob_matches(pattern, rel) for pattern in self.include) or any(
            entry.matches(rel) for entry in self.allowlist
        )

    def overrides_for(self, rel: str) -> DocsAllowlistEntry | None:
        for entry in self.allowlist:
            if entry.matches(rel):
                return entry
        return None

    def fingerprint(self) -> str:
        payload = {
            "include": list(self.include),
            "exclude": list(self.exclude),
            "allowlist": [entry.__dict__ for entry in self.allowlist],
        }
        return _sha256_text(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def _coerce_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _flatten_source_tokens(source_inventory: dict[str, Any]) -> tuple[set[str], set[str]]:
    names: set[str] = set()
    paths: set[str] = set()
    for key in (
        "services",
        "api_surfaces",
        "data_models",
        "frontend_callers",
        "deployment_assets",
        "tests",
    ):
        bucket = source_inventory.get(key, [])
        if not isinstance(bucket, list):
            continue
        for item in bucket:
            if not isinstance(item, dict):
                continue
            for field in ("name", "service", "service_id", "handler", "path", "evidence_path"):
                val = item.get(field)
                if isinstance(val, str) and val.strip():
                    token = val.strip()
                    if "/" in token or "." in token:
                        paths.add(token.lower())
                    for piece in re.findall(r"[A-Za-z_][A-Za-z0-9_-]{2,}", token):
                        names.add(piece.lower())
    return names, paths


def _classify_doc_type(rel: str, text: str) -> str:
    r = rel.lower()
    if Path(rel).name.lower().startswith("readme"):
        return "readme"
    if "changelog" in r or "release-notes" in r:
        return "changelog"
    if any(k in r for k in ("architecture", "adr", "架构")):
        return "architecture"
    if any(k in r for k in ("api", "openapi", "swagger", "接口")):
        return "api"
    if any(k in r for k in ("runbook", "ops", "operations", "deploy", "运维", "部署")):
        return "operations"
    if any(k in r for k in ("roadmap", "plan", "phase", "planning", "task_")):
        return "planning"
    if any(k in r for k in ("governance", "audit", "apm", "dossier", "review")):
        return "governance"
    if any(k in r for k in ("guide", "tutorial", "user", "manual", "usage")):
        return "user_guide"
    if re.search(r"^#\s*api\b", text, flags=re.I | re.M):
        return "api"
    return "overview"


def _authority_for_type(doc_type: str) -> tuple[str, float]:
    if doc_type in {"api", "architecture", "operations", "readme"}:
        return "source_backed", 0.9
    if doc_type in {"governance", "user_guide", "overview"}:
        return "design_doc", 0.65
    if doc_type in {"planning", "changelog"}:
        return "historical", 0.35
    return "design_doc", 0.5


def _specificity(text: str) -> float:
    score = 0.2
    if re.search(r"`[^`]+`", text):
        score += 0.2
    if re.search(r"/[a-zA-Z0-9/_-]+", text):
        score += 0.2
    if re.search(r"\b(class|function|endpoint|service|model|schema)\b", text, re.I):
        score += 0.2
    if re.search(r"\b([A-Z][A-Za-z0-9_]{2,})\b", text):
        score += 0.2
    return min(score, 1.0)


_PLAUSIBLE_REL_PATH = re.compile(r"^[A-Za-z0-9_./\\-]+$")
_HTTP_URL = re.compile(r"https?://[^\s<>\]`'\"|]+", re.IGNORECASE)
# Do not treat `example-app/blob/...` GitHub URL tails as repo path `app/blob/...`.
_REPO_REL_PATH_PREFIX = re.compile(
    r"(?<![A-Za-z0-9_-])(?:src|app|repo_wiki|docs|tests)/[A-Za-z0-9_./-]+"
)


def _is_plausible_rel_path(value: str) -> bool:
    """Return True when value looks like a relative filesystem path, not prose."""
    if not value or len(value) > 255:
        return False
    if "\0" in value or "\n" in value or "\r" in value:
        return False
    if not _PLAUSIBLE_REL_PATH.fullmatch(value):
        return False
    return "/" in value or "\\" in value or "." in value


def _repo_path_exists(repo_root: Path, rel: str) -> bool:
    """exists() for a claim path; OSError (ENAMETOOLONG, EINVAL) is not a file."""
    if not _is_plausible_rel_path(rel):
        return False
    try:
        return (repo_root / rel).exists()
    except OSError:
        return False


def _extract_claims(text: str) -> tuple[set[str], set[str]]:
    service_like: set[str] = set()
    path_like: set[str] = set()
    text_without_urls = _HTTP_URL.sub(" ", text)
    for m in re.findall(r"`([^`]+)`", text_without_urls):
        if _is_plausible_rel_path(m):
            path_like.add(m.lower())
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_-]{2,}", m):
            service_like.add(token.lower())
    for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_-]{2,}\b", text_without_urls):
        if token.lower().endswith(("service", "api", "model", "router")):
            service_like.add(token.lower())
    for p in _REPO_REL_PATH_PREFIX.findall(text_without_urls):
        if _is_plausible_rel_path(p):
            path_like.add(p.lower())
    return service_like, path_like


INIT_STUB_MARKER = "repo-wiki-init-stub"
_INIT_STUB_PHRASES = (
    "知识管理和文档生成平台",
    "知识管理平台",
    "RESTful API 接口（",
)
_INIT_STUB_EXACT_PATHS = frozenset(
    {
        "docs/00-overview.md",
        "docs/01-architecture.md",
        "docs/03-module-map.md",
        "docs/04-api-contracts.md",
        "docs/05-data-model.md",
    }
)


def is_init_generated_doc(rel: str, text: str) -> bool:
    """Return True for repo-wiki init placeholders, not the user's real docs."""
    rel_n = _normalize_rel_path(rel)
    if INIT_STUB_MARKER in text:
        return True
    if rel_n in _INIT_STUB_EXACT_PATHS or rel_n.startswith("docs/sections/"):
        return any(phrase in text for phrase in _INIT_STUB_PHRASES)
    return False


_AGENT_INSTRUCTION_NAMES = frozenset({"AGENTS.md", "CLAUDE.md", "GEMINI.md"})
_EVAL_REPORT_NAME_RE = re.compile(r"^round\d+-report\.md$", re.IGNORECASE)


def is_eval_or_agent_instruction_doc(rel: str) -> bool:
    """Return True for agent instruction files and eval reports, not product docs."""
    rel_n = _normalize_rel_path(rel)
    if not rel_n:
        return False
    parts = Path(rel_n).parts
    if any(part == ".repo-agent-eval" for part in parts):
        return True
    name = Path(rel_n).name
    if name in _AGENT_INSTRUCTION_NAMES:
        return True
    return _EVAL_REPORT_NAME_RE.fullmatch(name) is not None


def is_product_citation_source(rel: str, text: str = "") -> bool:
    """Return whether a doc may be used as product identity or citation evidence."""
    if is_eval_or_agent_instruction_doc(rel):
        return False
    if text and is_init_generated_doc(rel, text):
        return False
    return True


@dataclass
class _DocScanRecord:
    path: str
    doc_type: str
    authority_level: str
    authority_score: float
    freshness_score: float
    specificity_score: float
    conflict_level: str
    stale_references: list[str]
    conflicting_claims: list[str]
    content_sha256: str
    line_count: int
    last_modified: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "doc_type": self.doc_type,
            "authority_level": self.authority_level,
            "authority_score": round(self.authority_score, 3),
            "freshness_score": round(self.freshness_score, 3),
            "specificity_score": round(self.specificity_score, 3),
            "conflict_level": self.conflict_level,
            "stale_references": self.stale_references,
            "conflicting_claims": self.conflicting_claims,
            "content_sha256": self.content_sha256,
            "line_count": self.line_count,
            "last_modified": self.last_modified,
        }


class DocumentationScanner:
    """Scans docs and emits docs-inventory + conflict diagnostics."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.cache_path = self.repo_root / _CACHE_DIR / _CACHE_FILE

    def _load_cache(self) -> dict[str, Any]:
        if not self.cache_path.exists():
            return {}
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _save_cache(self, data: dict[str, Any]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    _SKIP_DIRS = frozenset({".git", ".repo-agent-eval", ".repo-wiki", "node_modules", ".venv"})

    def _is_skipped_path(self, path: Path) -> bool:
        try:
            rel_parts = path.relative_to(self.repo_root).parts
        except ValueError:
            rel_parts = path.parts
        return any(part in self._SKIP_DIRS for part in rel_parts)

    def _discover_docs(self, docs_filter: DocsScanFilter | None = None) -> list[Path]:
        out: dict[str, Path] = {}
        for suf in _DOC_SUFFIXES:
            for p in self.repo_root.rglob(f"*{suf}"):
                if self._is_skipped_path(p):
                    continue
                rel = str(p.relative_to(self.repo_root)).replace("\\", "/")
                if is_eval_or_agent_instruction_doc(rel):
                    continue
                if docs_filter is None or docs_filter.allows(rel):
                    out[rel] = p
        for p in self.repo_root.rglob("README*"):
            if self._is_skipped_path(p) or not p.is_file():
                continue
            rel = str(p.relative_to(self.repo_root)).replace("\\", "/")
            if is_eval_or_agent_instruction_doc(rel):
                continue
            if docs_filter is None or docs_filter.allows(rel):
                out[rel] = p

        if docs_filter is not None and docs_filter.has_positive_scope:
            for pattern in [
                *docs_filter.include,
                *(entry.pattern for entry in docs_filter.allowlist),
            ]:
                for p in self._expand_filter_pattern(pattern):
                    if self._is_skipped_path(p) or not p.is_file():
                        continue
                    if p.suffix.lower() not in _DOC_SUFFIXES and not p.name.lower().startswith(
                        "readme"
                    ):
                        continue
                    rel = str(p.relative_to(self.repo_root)).replace("\\", "/")
                    if is_eval_or_agent_instruction_doc(rel):
                        continue
                    if docs_filter.allows(rel):
                        out[rel] = p
        return [out[key] for key in sorted(out)]

    def _expand_filter_pattern(self, pattern: str) -> list[Path]:
        pattern = _normalize_rel_path(pattern)
        if not pattern or _is_unsafe_filter_pattern(pattern):
            return []
        if _has_glob_magic(pattern):
            return [
                p for p in self.repo_root.glob(pattern) if p.is_file() and self._is_under_repo(p)
            ]
        path = self.repo_root / pattern
        return [path] if path.is_file() and self._is_under_repo(path) else []

    def _is_under_repo(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.repo_root)
            return True
        except ValueError:
            return False

    def scan(
        self,
        source_inventory: dict[str, Any],
        *,
        incremental: bool = True,
        docs_filter: DocsScanFilter | dict[str, Any] | None = None,
        persist_cache: bool = True,
    ) -> dict[str, Any]:
        names, paths = _flatten_source_tokens(source_inventory)
        active_filter = DocsScanFilter.from_plan(docs_filter)
        filter_fingerprint = active_filter.fingerprint() if active_filter is not None else ""
        previous = self._load_cache() if incremental else {}
        next_cache: dict[str, Any] = {}
        docs: list[dict[str, Any]] = []
        rescanned = 0
        cached = 0

        for doc in self._discover_docs(active_filter):
            rel = str(doc.relative_to(self.repo_root)).replace("\\", "/")
            text = _safe_read(doc)
            digest = _sha256_text(text)
            prev_item = previous.get(rel)
            prev_filter_fingerprint = "" if isinstance(prev_item, dict) else None
            if isinstance(prev_item, dict):
                prev_filter_fingerprint = str(prev_item.get("_scan_filter_fingerprint", ""))
            if (
                incremental
                and isinstance(prev_item, dict)
                and prev_item.get("content_sha256") == digest
                and prev_filter_fingerprint == filter_fingerprint
            ):
                public_item = {k: v for k, v in prev_item.items() if not k.startswith("_")}
                docs.append(public_item)
                next_cache[rel] = dict(prev_item)
                cached += 1
                continue

            override = active_filter.overrides_for(rel) if active_filter is not None else None
            doc_type = (
                override.doc_type
                if override is not None and override.doc_type
                else _classify_doc_type(rel, text)
            )
            authority_level, authority_base = _authority_for_type(doc_type)
            authority_score_overridden = False
            if override is not None and override.authority_level:
                authority_level = override.authority_level
            if override is not None and override.authority_score is not None:
                authority_base = override.authority_score
                authority_score_overridden = True
            spec_score = _specificity(text)
            if is_init_generated_doc(rel, text):
                claim_names: set[str] = set()
                claim_paths: set[str] = set()
                authority_level = "historical"
                authority_base = 0.1
                authority_score_overridden = True
            else:
                claim_names, claim_paths = _extract_claims(text)

            stale_refs = sorted(
                [
                    p
                    for p in claim_paths
                    if p not in paths and not _repo_path_exists(self.repo_root, p)
                ]
            )
            conflicting_claims = sorted(
                [
                    n
                    for n in claim_names
                    if n not in names and n.endswith(("service", "api", "model"))
                ]
            )
            freshness = max(0.0, 1.0 - (0.2 * len(stale_refs) + 0.15 * len(conflicting_claims)))

            if stale_refs or conflicting_claims:
                conflict = "conflicting"
            elif freshness < 0.75:
                conflict = "stale"
            else:
                conflict = "aligned"

            record = _DocScanRecord(
                path=rel,
                doc_type=doc_type,
                authority_level=authority_level,
                authority_score=max(
                    0.0,
                    min(
                        1.0,
                        authority_base
                        if authority_score_overridden
                        else authority_base + (0.1 if freshness > 0.85 else 0.0),
                    ),
                ),
                freshness_score=freshness,
                specificity_score=spec_score,
                conflict_level=conflict,
                stale_references=stale_refs,
                conflicting_claims=conflicting_claims,
                content_sha256=digest,
                line_count=text.count("\n") + (1 if text else 0),
                last_modified=datetime.fromtimestamp(doc.stat().st_mtime, tz=UTC).isoformat(),
            ).to_dict()
            docs.append(record)
            cached_record = dict(record)
            cached_record["_scan_filter_fingerprint"] = filter_fingerprint
            next_cache[rel] = cached_record
            rescanned += 1

        if persist_cache:
            self._save_cache(next_cache)
        return {
            "schema_version": SCHEMA_VERSION_DOCS_INVENTORY,
            "generated_at": _now_iso(),
            "documents": docs,
            "scanner": {
                "version": "docs_scanner_v1",
                "stats": {
                    "files_total": len(docs),
                    "files_rescanned": rescanned,
                    "files_cached": cached,
                },
                "docs_filter_active": active_filter is not None,
            },
        }


def scan_repository_docs_inventory(
    repo_root: Path,
    source_inventory: dict[str, Any],
    *,
    incremental: bool = True,
    docs_filter: DocsScanFilter | dict[str, Any] | None = None,
    persist_cache: bool = True,
) -> dict[str, Any]:
    """Convenience function for docs-inventory scanning."""
    active_filter = (
        docs_filter
        if docs_filter is not None
        else _load_default_knowledge_plan_filter(Path(repo_root))
    )
    return DocumentationScanner(repo_root).scan(
        source_inventory,
        incremental=incremental,
        docs_filter=active_filter,
        persist_cache=persist_cache,
    )


def write_docs_inventory_json(
    repo_root: Path,
    source_inventory: dict[str, Any],
    output_path: Path | None = None,
    *,
    incremental: bool = True,
    docs_filter: DocsScanFilter | dict[str, Any] | None = None,
) -> Path:
    """Write docs-inventory JSON under `.repo-agent-eval/repowiki/zh/meta` by default."""
    inv = scan_repository_docs_inventory(
        repo_root, source_inventory, incremental=incremental, docs_filter=docs_filter
    )
    out = output_path or (
        Path(repo_root) / ".repo-agent-eval" / "repowiki" / "zh" / "meta" / "docs-inventory.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _is_unsafe_filter_pattern(pattern: str) -> bool:
    normalized = pattern.replace("\\", "/").strip()
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    return (
        not normalized
        or "\x00" in normalized
        or normalized.startswith("~")
        or Path(normalized).is_absolute()
        or PureWindowsPath(normalized).is_absolute()
        or any(part == ".." for part in parts)
        or "$" in normalized
        or "%" in normalized
    )


def _load_default_knowledge_plan_filter(repo_root: Path) -> dict[str, Any] | None:
    plan_path = Path(repo_root) / _DEFAULT_KNOWLEDGE_PLAN_PATH
    if not plan_path.exists():
        return None
    try:
        from repo_wiki.knowledge_plan import load_plan, validate_plan

        plan = load_plan(plan_path)
        issues = [issue for issue in validate_plan(plan) if issue.severity == "error"]
        if issues:
            summary = "; ".join(f"{issue.path}: {issue.message}" for issue in issues[:3])
            raise ValueError(f"Default knowledge plan is invalid: {plan_path}: {summary}")
        return plan
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Default knowledge plan could not be loaded: {plan_path}: {exc}") from exc
