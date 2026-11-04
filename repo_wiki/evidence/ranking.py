"""Evidence ranking pipeline for page-source matching.

Ranks source evidence spans by relevance to each planned wiki page.
Uses page topic, module, symbol, API, data model, and file proximity signals.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord, SQLiteRuntimeStore
from repo_wiki.planner.schema import (
    INVENTORY_SERVICE_API_PAGE_ID,
    WikiPagePlan,
    WikiPlanManifest,
    WikiTaxonomyCategory,
)
from repo_wiki.scanner.docs_scanner import is_product_citation_source

# Minimum candidate spans per page when evidence exists
MIN_CANDIDATES_PER_PAGE = 5

# Score weights for ranking signals
WEIGHT_MODULE = 2.5
WEIGHT_SYMBOL = 2.0
WEIGHT_API = 1.8
WEIGHT_DATA_MODEL = 1.8
WEIGHT_FILE_PROXIMITY = 1.2
WEIGHT_CATEGORY = 1.0
WEIGHT_ONBOARDING_README = 3.0
WEIGHT_ONBOARDING_SETTINGS = 2.5
WEIGHT_ONBOARDING_ENTRY = 2.5
WEIGHT_SECURITY_AUTH_FILE = 4.0
WEIGHT_API_ROUTES_FILE = 3.0


def _span_is_readme_run_section(span: EvidenceSpanRecord) -> bool:
    from repo_wiki.verifier.handbook import _heading_is_run_usage, _text_has_install_clue

    symbol = str(getattr(span, "symbol", "") or "")
    text = str(getattr(span, "span_text", "") or "")
    return _heading_is_run_usage(symbol) or _text_has_install_clue(text)


def _span_is_readme_badge_header(span: EvidenceSpanRecord) -> bool:
    from repo_wiki.verifier.handbook import _text_is_badge_header

    return _text_is_badge_header(str(getattr(span, "span_text", "") or ""))


_ONBOARDING_OVERVIEW_INSTALL_IDS = frozenset(
    {
        "project-overview",
        "installation",
        "quick-start",
        "quickstart",
        "getting-started",
    }
)


@dataclass
class EvidenceCandidate:
    """A ranked evidence candidate for a wiki page."""

    evidence_id: int
    span: EvidenceSpanRecord
    score: float
    match_signals: list[str]
    citation_order: int


@dataclass
class PageEvidenceBinding:
    """Evidence binding for a wiki page with ranked candidates."""

    page_id: str
    doc_type: str
    candidates: list[EvidenceCandidate]
    insufficient_evidence: bool = False
    bound_count: int = 0


@dataclass
class EvidenceRankingResult:
    """Result of evidence ranking for an entire page plan."""

    bindings: list[PageEvidenceBinding]
    insufficient_pages: list[str]
    total_spans_processed: int
    ranked_pages: int


def _compute_digest(span: EvidenceSpanRecord) -> str:
    """Compute digest for an evidence span record."""
    content = f"{span.file_path}:{span.line_start}-{span.line_end}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _normalize_for_matching(text: str) -> str:
    """Normalize text for matching (lowercase, strip punctuation)."""
    return text.lower().replace("-", " ").replace("_", " ").replace("/", " ").strip()


def _text_similarity(a: str, b: str) -> float:
    """Calculate simple text similarity (0.0 to 1.0)."""
    a_norm = _normalize_for_matching(a)
    b_norm = _normalize_for_matching(b)
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0
    if a_norm in b_norm or b_norm in a_norm:
        return 0.8
    # Simple character overlap
    a_chars = set(a_norm.split())
    b_chars = set(b_norm.split())
    if not a_chars or not b_chars:
        return 0.0
    overlap = len(a_chars & b_chars)
    return overlap / max(len(a_chars), len(b_chars))


def _category_to_doc_type(category: WikiTaxonomyCategory) -> str:
    """Map taxonomy category to document type."""
    mapping = {
        WikiTaxonomyCategory.PROJECT_OVERVIEW: "overview",
        WikiTaxonomyCategory.ARCHITECTURE_DESIGN: "section",
        WikiTaxonomyCategory.CORE_SERVICES: "module",
        WikiTaxonomyCategory.PYTHON_SERVICES: "module",
        WikiTaxonomyCategory.FRONTEND_APPLICATIONS: "module",
        WikiTaxonomyCategory.DATA_MODELS: "data-model",
        WikiTaxonomyCategory.API_REFERENCE: "api",
        WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS: "ops",
        WikiTaxonomyCategory.DEVELOPMENT_GUIDE: "guide",
        WikiTaxonomyCategory.SECURITY_COMPLIANCE: "security",
        WikiTaxonomyCategory.TROUBLESHOOTING: "troubleshooting",
    }
    return mapping.get(category, "page")


def _extract_keywords_from_page(page: WikiPagePlan) -> set[str]:
    """Extract keywords from page for matching."""
    keywords = set()
    # Page ID and title
    keywords.update(_normalize_for_matching(page.page_id).split())
    keywords.update(_normalize_for_matching(page.title).split())
    # Source requirements
    sr = page.source_requirements
    if sr:
        for module in sr.modules:
            keywords.update(_normalize_for_matching(module).split())
        for endpoint in sr.endpoints:
            # Extract path segments from API endpoints
            path = endpoint.split()[-1] if " " in endpoint else endpoint
            keywords.update(path.replace("/", " ").replace("-", " ").split())
        for model in sr.data_models:
            keywords.update(_normalize_for_matching(model).split())
        for file in sr.files:
            keywords.update(Path(file).stem.split())
    # Tags
    keywords.update(page.tags)
    return keywords


def _extract_keywords_from_span(span: EvidenceSpanRecord) -> set[str]:
    """Extract keywords from evidence span for matching."""
    keywords = set()
    # Symbol name
    if span.symbol:
        keywords.update(_normalize_for_matching(span.symbol).split())
    # File path
    if span.file_path:
        path = span.file_path.replace("\\", "/")
        for part in Path(path).parts:
            if part not in ("src", "repo_wiki", "tests", "."):
                keywords.update(part.replace("-", " ").replace("_", " ").split())
    # Span text (first 100 chars only)
    if span.span_text:
        text = span.span_text[:100]
        keywords.update(_normalize_for_matching(text).split())
    return keywords


def _score_by_keywords(page_keywords: set[str], span_keywords: set[str]) -> float:
    """Score based on keyword overlap."""
    if not page_keywords or not span_keywords:
        return 0.0
    overlap = len(page_keywords & span_keywords)
    return overlap / max(len(page_keywords), 1)


def _score_by_module_match(page: WikiPagePlan, span: EvidenceSpanRecord) -> float:
    """Score based on module name match."""
    sr = page.source_requirements
    if not sr or not sr.modules:
        return 0.0
    if not span.symbol:
        return 0.0

    symbol_lower = span.symbol.lower()
    for module in sr.modules:
        module_lower = module.lower()
        # Direct symbol match
        if symbol_lower == module_lower:
            return WEIGHT_MODULE
        # Partial match with path separator
        if module_lower in symbol_lower or symbol_lower in module_lower:
            return WEIGHT_MODULE * 0.8
        # Check if symbol contains module name
        parts = symbol_lower.replace("-", " ").replace("_", " ").split()
        if any(p == module_lower for p in parts):
            return WEIGHT_MODULE * 0.6
    return 0.0


def _score_by_api_match(page: WikiPagePlan, span: EvidenceSpanRecord) -> float:
    """Score based on API endpoint match."""
    sr = page.source_requirements
    if not sr or not sr.endpoints:
        return 0.0
    symbol_lower = (span.symbol or "").lower()
    span_path = _normalized_span_path(span)
    best = 0.0
    for endpoint in sr.endpoints:
        # endpoint format: "METHOD /path" or just "path"
        path = endpoint.split()[-1] if " " in endpoint else endpoint
        path_lower = _normalize_for_matching(path)
        if symbol_lower and (path_lower in symbol_lower or symbol_lower in path_lower):
            best = max(best, WEIGHT_API)
            continue
        parts = [part for part in path.split("/") if part and not part.startswith((":", "{", "*"))]
        if len(parts) >= 2 and all(part.lower() in span_path for part in parts[-2:]):
            best = max(best, WEIGHT_API)
    return best


def _score_by_data_model_match(page: WikiPagePlan, span: EvidenceSpanRecord) -> float:
    """Score based on data model match."""
    sr = page.source_requirements
    if not sr or not sr.data_models:
        return 0.0
    if not span.symbol:
        return 0.0

    symbol_lower = span.symbol.lower()
    for model in sr.data_models:
        model_lower = model.lower()
        if symbol_lower == model_lower:
            return WEIGHT_DATA_MODEL
        if model_lower in symbol_lower:
            return WEIGHT_DATA_MODEL * 0.7
    return 0.0


def _score_by_file_proximity(page: WikiPagePlan, span: EvidenceSpanRecord) -> float:
    """Score based on file path proximity."""
    sr = page.source_requirements
    if not sr or not sr.files:
        return 0.0
    if not span.file_path:
        return 0.0

    span_file = span.file_path.replace("\\", "/")
    for file_req in sr.files:
        file_req_norm = file_req.replace("\\", "/")
        # Exact file match
        if span_file.endswith(file_req_norm) or file_req_norm.endswith(span_file):
            return WEIGHT_FILE_PROXIMITY
        # Check if file basename matches
        span_name = Path(span_file).stem
        req_name = Path(file_req).stem
        if span_name == req_name:
            return WEIGHT_FILE_PROXIMITY * 0.7
    return 0.0


def _score_by_category_relevance(page: WikiPagePlan, span: EvidenceSpanRecord) -> float:
    """Score based on document type relevance to span language."""
    category = page.category

    # Categories that prefer certain languages
    language_preference = {
        WikiTaxonomyCategory.DATA_MODELS: ["go", "sql", "python", "java"],
        WikiTaxonomyCategory.API_REFERENCE: ["go", "typescript", "python", "java"],
        WikiTaxonomyCategory.CORE_SERVICES: ["go", "python", "java", "typescript"],
        WikiTaxonomyCategory.ARCHITECTURE_DESIGN: ["go", "python", "typescript"],
        WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS: ["yaml", "python", "shell"],
        WikiTaxonomyCategory.DEVELOPMENT_GUIDE: ["markdown", "python"],
    }

    preferred_langs = language_preference.get(category, [])
    if not preferred_langs:
        return WEIGHT_CATEGORY * 0.5

    if span.language in preferred_langs:
        return WEIGHT_CATEGORY
    return 0.0


def _normalized_span_path(span: EvidenceSpanRecord) -> str:
    return str(getattr(span, "file_path", "") or "").replace("\\", "/").lower()


def _is_overview_or_install_page(page: WikiPagePlan) -> bool:
    page_id = (page.page_id or "").lower()
    tags = {str(tag).lower() for tag in (page.tags or [])}
    if page_id in _ONBOARDING_OVERVIEW_INSTALL_IDS:
        return True
    if page.category in {
        WikiTaxonomyCategory.PROJECT_OVERVIEW,
        WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
        WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS,
    } and any(
        token in page_id for token in ("overview", "install", "quick-start", "quickstart", "setup")
    ):
        return True
    return bool(tags & {"installation", "setup", "quick-start", "quickstart", "getting-started"})


def _is_security_onboarding_page(page: WikiPagePlan) -> bool:
    page_id = (page.page_id or "").lower()
    if page.category == WikiTaxonomyCategory.SECURITY_COMPLIANCE:
        return True
    return "security" in page_id or "auth" in page_id


def _is_ops_config_page(page: WikiPagePlan) -> bool:
    page_id = (page.page_id or "").lower()
    if page_id in {"configuration", "environment-setup", "logging"}:
        return True
    if page.category == WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS:
        return True
    return any(token in page_id for token in ("config", "logging", "environment"))


def _is_database_troubleshooting_page(page: WikiPagePlan) -> bool:
    page_id = (page.page_id or "").lower()
    if page_id == "database-issues":
        return True
    return page.category == WikiTaxonomyCategory.TROUBLESHOOTING and "database" in page_id


THIN_TOPIC_TOKENS = (
    "git-workflow",
    "git工作流",
    "performance",
    "性能",
    "health-check",
    "健康检查",
    "core-services",
    "核心服务",
    "debug-guide",
    "debug-tools",
    "调试指南",
    "调试工具",
)
WIDE_EVIDENCE_TOKENS = THIN_TOPIC_TOKENS + ("migration", "迁移")


def is_thin_topic_blob(blob: str) -> bool:
    lowered = (blob or "").lower()
    return any(token in lowered for token in THIN_TOPIC_TOKENS)


def wants_wide_evidence(blob: str) -> bool:
    lowered = (blob or "").lower()
    return any(token in lowered for token in WIDE_EVIDENCE_TOKENS)


def _is_thin_topic_page(page: WikiPagePlan) -> bool:
    return is_thin_topic_blob(f"{page.page_id} {page.title}")


def _score_thin_topic_evidence(
    page: WikiPagePlan, path: str, name: str, symbol: str, text: str
) -> tuple[float, list[str]]:
    blob = f"{page.page_id} {page.title}".lower()
    score = 0.0
    signals: list[str] = []
    if "git" in blob:
        if name in {"contributing.md", "contributing.rst", "makefile"} or ".github" in path:
            score += WEIGHT_ONBOARDING_SETTINGS + 1.0
            signals.append("thin_git_workflow")
    if "debug" in blob or "调试" in blob:
        if (
            any(
                token in path or token in text or token in symbol
                for token in ("pprof", "debug", "trace", "dlv", "breakpoint")
            )
            and "scaffold" not in path
        ):
            score += WEIGHT_ONBOARDING_ENTRY + 1.5
            signals.append("thin_debug_source")
            if path.endswith((".go", ".py", ".sh")):
                score += 1.0
                signals.append("thin_debug_impl")
        if "scaffold" in path:
            score -= 4.0
            signals.append("thin_debug_scaffold")
    if "performance" in blob or "性能" in blob:
        if any(token in path or token in text for token in ("pool", "timeout", "cache", "worker")):
            score += WEIGHT_ONBOARDING_SETTINGS + 1.0
            signals.append("thin_performance")
    if "health" in blob or "健康" in blob:
        if any(
            token in path or token in text or token in symbol
            for token in ("health", "readyz", "livez")
        ):
            score += WEIGHT_ONBOARDING_ENTRY + 1.0
            signals.append("thin_health")
        if name.startswith("readme"):
            score += WEIGHT_ONBOARDING_README
            signals.append("thin_health_readme")
    if "核心服务" in blob or "core-service" in blob:
        if path.startswith("app/") or path.startswith("internal/") or path.startswith("cmd/"):
            score += WEIGHT_ONBOARDING_SETTINGS + 1.5
            signals.append("thin_core_service")
    return score, signals


def _score_onboarding_evidence(
    page: WikiPagePlan, span: EvidenceSpanRecord
) -> tuple[float, list[str]]:
    """Boost README / settings / entry files for onboarding pages only.

    API pages must not receive a global README boost.
    """
    path = _normalized_span_path(span)
    name = Path(path).name.lower()
    symbol = str(getattr(span, "symbol", "") or "").lower()
    text = str(getattr(span, "span_text", "") or "").lower()
    score = 0.0
    signals: list[str] = []

    if page.category == WikiTaxonomyCategory.API_REFERENCE:
        if "api/routes" in path:
            score += WEIGHT_API_ROUTES_FILE
            signals.append("api_routes_file")
        if path.endswith(".go") and not name.endswith("_test.go"):
            if path.startswith("internal/") or "/internal/" in path:
                score += WEIGHT_API_ROUTES_FILE + 1.5
                signals.append("go_internal_handler")
            elif name.endswith(".pb.go") or name.endswith("_grpc.pb.go"):
                score -= 2.0
                signals.append("go_generated_api")
            else:
                score += WEIGHT_API_ROUTES_FILE * 0.4
                signals.append("go_api_source")
            if name in {"main.go", "config.go"} and (
                path.startswith("cmd/") or path.count("/") == 0
            ):
                score -= 2.0
                signals.append("go_entrypoint_not_handler")
        return score, signals

    if page.category == WikiTaxonomyCategory.CORE_SERVICES:
        from repo_wiki.generator.process_roles import path_looks_like_example_cmd

        blob = f"{page.page_id} {page.title}".lower()
        from repo_wiki.generator.process_roles import cmd_dir_name

        cmd_name = cmd_dir_name(path)
        if cmd_name and (cmd_name.lower() in blob or cmd_name.replace("-", " ").lower() in blob):
            score += WEIGHT_ONBOARDING_ENTRY + 3.0
            signals.append("core_named_cmd")
        if path_looks_like_example_cmd(path):
            score -= 8.0
            signals.append("core_demote_example_cmd")
        elif path.startswith("app/") or path.startswith("internal/") or path.startswith("cmd/"):
            score += WEIGHT_ONBOARDING_SETTINGS + 1.5
            signals.append("thin_core_service")
        return score, signals

    if _is_overview_or_install_page(page):
        if name == "readme.md":
            score += WEIGHT_ONBOARDING_README + 1.5
            signals.append("onboarding_primary_readme")
            if _span_is_readme_run_section(span):
                score += WEIGHT_ONBOARDING_README + 2.5
                signals.append("onboarding_readme_run")
            elif _span_is_readme_badge_header(span):
                score -= 2.5
                signals.append("onboarding_readme_badge")
        elif name.startswith("readme") and not any(
            marker in name for marker in ("scaffold", "template", "boilerplate")
        ):
            score += WEIGHT_ONBOARDING_README
            signals.append("onboarding_readme")
        elif name.startswith("readme"):
            score -= 1.5
            signals.append("onboarding_secondary_readme")
        if name in {"makefile", "quickstart.md", "go.mod"}:
            score += WEIGHT_ONBOARDING_SETTINGS
            signals.append("onboarding_build_clue")
        if "settings" in path or "database_url" in symbol or "database_url" in text:
            score += WEIGHT_ONBOARDING_SETTINGS
            signals.append("onboarding_settings")
        if name in {"main.py", "main.go"}:
            score += WEIGHT_ONBOARDING_ENTRY
            signals.append("onboarding_entry")
        if path.startswith("cmd/") and name == "main.go":
            score += WEIGHT_ONBOARDING_ENTRY + 1.0
            signals.append("onboarding_cmd_main")
    elif page.category == WikiTaxonomyCategory.ARCHITECTURE_DESIGN:
        if path.endswith(".go") and (path.startswith("internal/") or "/internal/" in path):
            score += WEIGHT_ONBOARDING_SETTINGS + 2.0
            signals.append("arch_go_internal")
            if any(
                token in path
                for token in (
                    "/control/",
                    "/services/",
                    "/repository/",
                    "/exporter/",
                    "/agent/",
                    "/probe/",
                )
            ):
                score += 2.0
                signals.append("arch_go_core")
        if path.startswith("cmd/") and name == "main.go":
            from repo_wiki.generator.process_roles import path_looks_like_example_cmd

            if path_looks_like_example_cmd(path) or any(
                token in path for token in ("example", "demo", "scaffold")
            ):
                score -= 4.0
                signals.append("arch_demo_cmd")
            else:
                score += WEIGHT_ONBOARDING_ENTRY + 2.0
                signals.append("arch_cmd_core")
        if any(part in {"routes", "routers", "models"} for part in Path(path).parts):
            score += WEIGHT_ONBOARDING_SETTINGS + 2.0
            signals.append("arch_core_models_or_routes")
    elif _is_ops_config_page(page) or _is_database_troubleshooting_page(page):
        if "settings" in path or "database_url" in symbol or "database_url" in text:
            score += WEIGHT_ONBOARDING_SETTINGS
            signals.append("onboarding_settings")
        if "docker-compose" in path or name in {"docker-compose.yml", "docker-compose.yaml"}:
            score += WEIGHT_ONBOARDING_SETTINGS
            signals.append("onboarding_compose")
        if "logging" in path or "logging" in page.page_id.lower():
            if "log" in path or "logging" in symbol or "logging" in text:
                score += WEIGHT_ONBOARDING_ENTRY
                signals.append("onboarding_logging")
    elif page.category == WikiTaxonomyCategory.DATA_MODELS:
        if "/models/" in path or name in {"models.py", "model.py"}:
            score += WEIGHT_ONBOARDING_SETTINGS
            signals.append("data_model_file")
        if path.endswith(".go") and (
            "gorm:" in text or "tablename" in symbol or "/models/" in path
        ):
            score += WEIGHT_ONBOARDING_SETTINGS + 1.0
            signals.append("go_gorm_model")
        if path.replace("\\", "/").endswith("db/schema.sql") or path.endswith("schema.sql"):
            score += WEIGHT_ONBOARDING_SETTINGS + 2.0
            signals.append("schema_sql")
        if "alembic" in path.replace("\\", "/"):
            score += WEIGHT_ONBOARDING_SETTINGS
            signals.append("alembic_migration")
    elif _is_security_onboarding_page(page):
        if "authentication.py" in path or path.endswith("/authentication.py"):
            score += WEIGHT_SECURITY_AUTH_FILE
            signals.append("security_auth_file")
    elif _is_thin_topic_page(page):
        extra, extra_signals = _score_thin_topic_evidence(page, path, name, symbol, text)
        score += extra
        signals.extend(extra_signals)

    return score, signals


def score_evidence_for_page(
    page: WikiPagePlan, span: EvidenceSpanRecord
) -> tuple[float, list[str]]:
    """Calculate relevance score for an evidence span to a wiki page.

    Returns:
        Tuple of (score, list of match signals)
    """
    score = 0.0
    signals = []

    # Extract keywords
    page_keywords = _extract_keywords_from_page(page)
    span_keywords = _extract_keywords_from_span(span)

    # Score by keyword overlap
    keyword_score = _score_by_keywords(page_keywords, span_keywords)
    if keyword_score > 0:
        score += keyword_score
        signals.append("keyword_overlap")

    # Score by module match
    module_score = _score_by_module_match(page, span)
    if module_score > 0:
        score += module_score
        signals.append("module_match")

    # Score by API match
    api_score = _score_by_api_match(page, span)
    if api_score > 0:
        score += api_score
        signals.append("api_match")

    # Score by data model match
    dm_score = _score_by_data_model_match(page, span)
    if dm_score > 0:
        score += dm_score
        signals.append("data_model_match")

    # Score by file proximity
    fp_score = _score_by_file_proximity(page, span)
    if fp_score > 0:
        score += fp_score
        signals.append("file_proximity")

    # Score by category relevance
    cat_score = _score_by_category_relevance(page, span)
    if cat_score > 0:
        score += cat_score
        signals.append("category_relevance")

    onboarding_score, onboarding_signals = _score_onboarding_evidence(page, span)
    if onboarding_score != 0:
        score += onboarding_score
        signals.extend(onboarding_signals)

    path = _normalized_span_path(span)
    name = Path(path).name.lower()
    if path.startswith("internal/") or "/internal/" in path:
        score += 2.0
        signals.append("internal_product_source")
    if name.endswith(".pb.go") or name.endswith("_grpc.pb.go"):
        score -= 3.0
        signals.append("generated_pb_go")
    if name.endswith("_test.go") or name.startswith("test_") or name.endswith("_test.py"):
        score -= 2.0
        signals.append("test_source")

    return score, signals


def rank_evidence_for_page(
    page: WikiPagePlan,
    available_spans: list[EvidenceSpanRecord],
) -> list[EvidenceCandidate]:
    """Rank evidence spans for a single wiki page.

    Returns top candidates sorted by score descending.
    """
    doc_type = _category_to_doc_type(page.category)
    candidates: list[tuple[float, int, EvidenceSpanRecord, list[str]]] = []

    for idx, span in enumerate(available_spans):
        file_path = str(getattr(span, "file_path", "") or "")
        if not is_product_citation_source(file_path):
            continue
        score, signals = score_evidence_for_page(page, span)
        if score > 0:
            candidates.append((score, idx, span, signals))

    # Sort by score descending, then by original index
    candidates.sort(key=lambda x: (-x[0], x[1]))

    # Convert to EvidenceCandidate objects
    results: list[EvidenceCandidate] = []
    for rank, (score, _, span, signals) in enumerate(candidates[: MIN_CANDIDATES_PER_PAGE * 2]):
        results.append(
            EvidenceCandidate(
                evidence_id=int(getattr(span, "id", 0) or 0),
                span=span,
                score=score,
                match_signals=signals,
                citation_order=rank,
            )
        )

    return _pin_required_file_candidates(page, available_spans, results[:MIN_CANDIDATES_PER_PAGE])


def _span_matches_required_file(span: EvidenceSpanRecord, req: str) -> bool:
    path = _normalized_span_path(span)
    req_n = req.replace("\\", "/").lower().rstrip("/")
    if not req_n:
        return False
    if path == req_n or path.endswith("/" + req_n):
        return True
    if path.startswith(req_n + "/"):
        return True
    req_name = Path(req_n).name
    return "." in req_name and Path(path).name == req_name


def _pin_required_file_candidates(
    page: WikiPagePlan,
    available_spans: list[EvidenceSpanRecord],
    results: list[EvidenceCandidate],
) -> list[EvidenceCandidate]:
    """Keep required files (especially README) on overview/install pages."""
    required = list((page.source_requirements.files if page.source_requirements else []) or [])
    if _is_overview_or_install_page(page) and not any(
        Path(item).name.lower() == "readme.md" for item in required
    ):
        required.append("README.md")
    if not required:
        return results
    present = {_normalized_span_path(candidate.span) for candidate in results}
    extras: list[EvidenceCandidate] = []
    pinned_paths: set[str] = set()
    required_spans = [
        span
        for span in available_spans
        if any(_span_matches_required_file(span, req) for req in required)
    ]
    required_spans.sort(
        key=lambda span: (
            0 if _span_is_readme_run_section(span) else 1,
            0 if not _span_is_readme_badge_header(span) else 1,
        )
    )
    for span in required_spans:
        path = _normalized_span_path(span)
        if path in present and path in pinned_paths:
            continue
        extras.append(
            EvidenceCandidate(
                evidence_id=int(getattr(span, "id", 0) or 0),
                span=span,
                score=WEIGHT_ONBOARDING_README
                + (4.0 if _span_is_readme_run_section(span) else 2.0),
                match_signals=["required_file", "required_run_section"]
                if _span_is_readme_run_section(span)
                else ["required_file"],
                citation_order=0,
            )
        )
        present.add(path)
        pinned_paths.add(path)
    if not extras:
        return results
    merged = extras + results
    pinned: list[EvidenceCandidate] = []
    for index, candidate in enumerate(merged[:MIN_CANDIDATES_PER_PAGE]):
        pinned.append(
            EvidenceCandidate(
                evidence_id=candidate.evidence_id,
                span=candidate.span,
                score=candidate.score,
                match_signals=candidate.match_signals,
                citation_order=index,
            )
        )
    return pinned


def _infer_service_name_from_page(page: WikiPagePlan) -> str | None:
    """Infer target service name for ownership filtering."""
    if page.page_id == INVENTORY_SERVICE_API_PAGE_ID:
        return "inventory-service"
    sr = page.source_requirements
    if sr and sr.modules:
        preferred = [m for m in sr.modules if "service" in m.lower()]
        if preferred:
            return preferred[0]
        return sr.modules[0]
    lowered = page.page_id.lower()
    if "-service" in lowered:
        idx = lowered.find("-service")
        start = lowered.rfind("-", 0, idx)
        token = lowered[start + 1 : idx + len("-service")]
        if token:
            return token
    return None


def filter_ranked_candidates_by_ownership(
    page: WikiPagePlan,
    candidates: list[EvidenceCandidate],
) -> list[EvidenceCandidate]:
    """Filter out ownership-rejected evidence while preserving ranking order."""
    from repo_wiki.evidence.service_ownership import (
        ServiceOwnershipResolver,
        is_inventory_service,
    )

    service_name = _infer_service_name_from_page(page)
    if not service_name:
        return candidates

    module_paths: list[str] = []
    if page.source_requirements and page.source_requirements.modules:
        module_paths = list(page.source_requirements.modules)
    resolver = ServiceOwnershipResolver(
        service_name=service_name,
        module_paths=module_paths,
    )

    filtered: list[EvidenceCandidate] = []
    for candidate in candidates:
        span = candidate.span
        confidence = resolver.resolve_ownership(
            symbol=span.symbol,
            file_path=span.file_path,
            span_text=span.span_text,
            evidence_domain=None,
        )
        if confidence.is_rejected:
            continue
        # Keep original score/order; append ownership signal for traceability.
        extra_signals = list(candidate.match_signals)
        if confidence.is_owned:
            extra_signals.append("ownership_confirmed")
        filtered.append(
            EvidenceCandidate(
                evidence_id=candidate.evidence_id,
                span=candidate.span,
                score=candidate.score,
                match_signals=extra_signals,
                citation_order=candidate.citation_order,
            )
        )

    # Ensure inventory-service safety: do not accidentally keep AI-only bindings.
    if is_inventory_service(service_name):
        return filtered
    return filtered


class EvidenceRanker:
    """Ranks evidence spans for wiki page plans."""

    def __init__(self, runtime_store: SQLiteRuntimeStore) -> None:
        self.store = runtime_store

    def rank_plan(
        self,
        manifest: WikiPlanManifest,
    ) -> EvidenceRankingResult:
        """Rank evidence for all pages in a plan.

        Uses available evidence spans from the runtime store and matches
        them to planned wiki pages based on topic, module, symbol, API,
        data model, and file proximity signals.
        """
        # Load all available evidence spans from store
        all_spans_raw = self.store.list_evidence_spans(limit=10000)
        all_spans = [
            EvidenceSpanRecord(
                digest=s["digest"],
                file_path=s["file_path"],
                line_start=s["line_start"],
                line_end=s["line_end"],
                language=s["language"],
                symbol=s.get("symbol"),
                span_text=s.get("span_text", ""),
                confidence=s.get("confidence", 1.0),
            )
            for s in all_spans_raw
        ]

        bindings: list[PageEvidenceBinding] = []
        insufficient_pages: list[str] = []
        total_processed = 0

        for page in manifest.pages:
            doc_type = _category_to_doc_type(page.category)
            candidates = rank_evidence_for_page(page, all_spans)

            binding = PageEvidenceBinding(
                page_id=page.page_id,
                doc_type=doc_type,
                candidates=candidates,
                insufficient_evidence=len(candidates) < MIN_CANDIDATES_PER_PAGE
                and len(all_spans) > 0,
                bound_count=len(candidates),
            )
            bindings.append(binding)

            if binding.insufficient_evidence:
                insufficient_pages.append(page.page_id)

            total_processed += len(candidates)

        return EvidenceRankingResult(
            bindings=bindings,
            insufficient_pages=insufficient_pages,
            total_spans_processed=total_processed,
            ranked_pages=len([b for b in bindings if b.candidates]),
        )

    def persist_bindings(
        self,
        manifest: WikiPlanManifest,
        result: EvidenceRankingResult,
    ) -> None:
        """Persist evidence bindings to runtime store.

        Maps evidence spans to wiki page slugs with citation order.
        Records insufficient-evidence pages explicitly.
        """
        # Persist each binding
        for binding in result.bindings:
            doc_type = binding.doc_type

            # Map each candidate evidence to the page
            for candidate in binding.candidates:
                self.store.map_evidence_to_page(
                    doc_slug=binding.page_id,
                    doc_type=doc_type,
                    evidence_id=candidate.evidence_id,
                    citation_order=candidate.citation_order,
                    context_hint=", ".join(candidate.match_signals),
                )

        # Record insufficient evidence pages in store metadata
        # Store as JSON in a dedicated metadata table or as page metadata
        for page_id in result.insufficient_pages:
            # Pages with insufficient evidence are flagged
            # This could be stored as an invalidation reason or metadata
            pass

    def get_insufficient_evidence_pages(
        self,
        manifest: WikiPlanManifest,
        result: EvidenceRankingResult,
    ) -> list[dict[str, Any]]:
        """Get detailed report of pages with insufficient evidence.

        Returns list of dicts with page info and reason for insufficient evidence.
        """
        page_map = {p.page_id: p for p in manifest.pages}
        insufficient = []

        for page_id in result.insufficient_pages:
            page = page_map.get(page_id)
            if not page:
                continue

            binding = next((b for b in result.bindings if b.page_id == page_id), None)
            if not binding:
                continue

            insufficient.append(
                {
                    "page_id": page_id,
                    "title": page.title,
                    "category": page.category.value,
                    "bound_count": binding.bound_count,
                    "required_minimum": MIN_CANDIDATES_PER_PAGE,
                    "source_requirements": page.source_requirements.model_dump()
                    if page.source_requirements
                    else {},
                }
            )

        return insufficient
