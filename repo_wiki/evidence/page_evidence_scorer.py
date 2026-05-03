"""Page evidence scoring model for evidence ranking.

This module provides:
- PageEvidenceScorer: Scores and ranks evidence for wiki pages
- Integration with service ownership resolver (Task 33.1)
- Top-N evidence selection with rejection reasons
- Service-local evidence preference

Scoring dimensions:
1. Title match: Page title vs symbol/file_path similarity
2. Service slug match: Module name vs evidence ownership
3. Domain match: Business domain alignment
4. Runtime role: Function/class purpose matching
5. API relation: Endpoint path matching
6. Data-model relation: Model name matching
"""

from __future__ import annotations

from dataclasses import dataclass, field

from repo_wiki.evidence.service_ownership import (
    OwnershipConfidence,
    OwnershipDecision,
    ServiceOwnershipResolver,
)
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory

# =============================================================================
# Scoring Model Constants
# =============================================================================

# Score weights for multi-dimensional evidence scoring
WEIGHT_TITLE = 2.0
WEIGHT_SERVICE_SLUG = 2.5
WEIGHT_DOMAIN = 1.8
WEIGHT_RUNTIME_ROLE = 1.5
WEIGHT_API_RELATION = 1.8
WEIGHT_DATA_MODEL = 1.8

# Thresholds
REJECTION_THRESHOLD = 0.3  # Confidence below this is rejected
MIN_OWNERSHIP_SCORE = 0.5  # Minimum ownership confidence to accept

# Top-N candidates to retain
TOP_N_CANDIDATES = 5


@dataclass
class EvidenceRejectionReason:
    """Reason why an evidence candidate was rejected."""

    reason_code: str  # e.g., 'INFRASTRUCTURE_CONFLICT', 'DOMAIN_MISMATCH'
    reason: str  # Human-readable explanation
    evidence_id: int | None = None
    span_symbol: str | None = None
    span_file_path: str | None = None


@dataclass
class ScoredEvidenceCandidate:
    """An evidence candidate with multi-dimensional scoring."""

    evidence_id: int
    span: EvidenceSpanRecord
    score: float
    title_score: float = 0.0
    service_slug_score: float = 0.0
    domain_score: float = 0.0
    runtime_role_score: float = 0.0
    api_score: float = 0.0
    data_model_score: float = 0.0
    ownership_score: float = 0.0
    match_signals: list[str] = field(default_factory=list)
    citation_order: int = 0
    is_rejected: bool = False
    rejection_reasons: list[EvidenceRejectionReason] = field(default_factory=list)


@dataclass
class PageEvidenceScoreResult:
    """Result of scoring evidence for a single page."""

    page_id: str
    candidates: list[ScoredEvidenceCandidate]
    rejected: list[ScoredEvidenceCandidate]
    total_spans_evaluated: int = 0
    insufficient_evidence: bool = False


# =============================================================================
# Text Similarity Utilities
# =============================================================================


def _normalize_text(text: str) -> str:
    """Normalize text for matching (lowercase, strip separators)."""
    return (
        text.lower()
        .replace("-", " ")
        .replace("_", " ")
        .replace("/", " ")
        .replace("\\", " ")
        .strip()
    )


def _split_camel_case(text: str) -> list[str]:
    """Split camelCase or PascalCase into words."""
    chars = []
    for i, c in enumerate(text):
        if c.isupper() and i > 0:
            chars.append(" ")
        chars.append(c)
    return " ".join("".join(chars).split()).lower().split()


def _tokenize(text: str) -> set[str]:
    """Tokenize text into searchable keywords."""
    normalized = _normalize_text(text)
    # Split on separators and also handle camelCase
    parts = normalized.split()
    tokens = set()
    for part in parts:
        tokens.update(part.split("-"))
        tokens.update(part.split("_"))
        tokens.update(_split_camel_case(part))
    tokens.discard("")
    return tokens


def _text_similarity(a: str, b: str) -> float:
    """Calculate text similarity (0.0 to 1.0)."""
    if not a or not b:
        return 0.0
    a_tokens = _tokenize(a)
    b_tokens = _tokenize(b)
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    if union == 0:
        return 0.0
    # Exact match
    if a_tokens == b_tokens:
        return 1.0
    # Containment
    if a_tokens <= b_tokens or b_tokens <= a_tokens:
        return 0.8
    # Jaccard-like score
    return overlap / union


# =============================================================================
# Single-Dimension Scoring Functions
# =============================================================================


def _score_by_title_match(page: WikiPagePlan, span: EvidenceSpanRecord) -> float:
    """Score based on title/page_id vs symbol/file_path similarity."""
    title_norm = _normalize_text(page.title)
    page_id_norm = _normalize_text(page.page_id)

    # Check symbol
    symbol_sim = 0.0
    if span.symbol:
        symbol_sim = max(
            _text_similarity(title_norm, span.symbol),
            _text_similarity(page_id_norm, span.symbol),
        )

    # Check file path
    path_sim = 0.0
    if span.file_path:
        file_stem = _normalize_text(span.file_path.split("/")[-1].split("\\")[-1])
        path_sim = max(
            _text_similarity(title_norm, file_stem),
            _text_similarity(page_id_norm, file_stem),
        )

    return max(symbol_sim, path_sim) * WEIGHT_TITLE


def _score_by_service_slug(page: WikiPagePlan, span: EvidenceSpanRecord) -> float:
    """Score based on module/service slug match."""
    sr = page.source_requirements
    if not sr or not sr.modules:
        return 0.0

    span_symbol_lower = span.symbol.lower() if span.symbol else ""
    span_path_lower = span.file_path.lower() if span.file_path else ""

    best_score = 0.0
    for module in sr.modules:
        module_lower = module.lower()

        # Direct symbol match
        if module_lower == span_symbol_lower:
            best_score = max(best_score, WEIGHT_SERVICE_SLUG)
        # Symbol contains module
        elif module_lower in span_symbol_lower:
            best_score = max(best_score, WEIGHT_SERVICE_SLUG * 0.8)
        # Path contains module
        elif module_lower in span_path_lower:
            best_score = max(best_score, WEIGHT_SERVICE_SLUG * 0.7)
        # Partial match in path
        else:
            module_parts = module_lower.replace("-", " ").split()
            matched_parts = sum(1 for p in module_parts if p in span_path_lower)
            if matched_parts > 0:
                best_score = max(
                    best_score, WEIGHT_SERVICE_SLUG * 0.5 * (matched_parts / len(module_parts))
                )

    return best_score


def _score_by_domain_match(
    page: WikiPagePlan, span: EvidenceSpanRecord, ownership_confidence: OwnershipConfidence | None
) -> float:
    """Score based on domain alignment between page and evidence."""
    # If we have ownership info, use it
    if ownership_confidence and ownership_confidence.matched_domain:
        # Domain matches suggest higher relevance
        if ownership_confidence.decision in (
            OwnershipDecision.HIGH_CONFIDENCE,
            OwnershipDecision.MEDIUM_CONFIDENCE,
        ):
            return ownership_confidence.confidence * WEIGHT_DOMAIN
        elif ownership_confidence.decision == OwnershipDecision.REJECTED:
            return 0.0

    # Fallback: check if page category suggests a domain
    domain_hints = {
        WikiTaxonomyCategory.CORE_SERVICES: ["service", "core"],
        WikiTaxonomyCategory.DATA_MODELS: ["data", "model", "schema"],
        WikiTaxonomyCategory.API_REFERENCE: ["api", "endpoint", "rest"],
        WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS: ["deploy", "ops", "infra"],
    }

    category_hint = domain_hints.get(page.category, [])
    if not category_hint:
        return WEIGHT_DOMAIN * 0.3  # Neutral score for unknown category

    span_text_lower = (span.span_text or "").lower()
    symbol_lower = (span.symbol or "").lower()

    # Check if span keywords match category hints
    for hint in category_hint:
        if hint in symbol_lower or hint in span_text_lower:
            return WEIGHT_DOMAIN

    return 0.0


def _score_by_runtime_role(page: WikiPagePlan, span: EvidenceSpanRecord) -> float:
    """Score based on runtime role (function, class, config, etc.)."""
    if not span.symbol:
        return 0.0

    symbol_lower = span.symbol.lower()

    # Determine expected role from source requirements
    expected_roles: list[str] = []
    if page.source_requirements:
        for module in page.source_requirements.modules:
            expected_roles.append(module.lower())
        for endpoint in page.source_requirements.endpoints:
            # Extract role from endpoint path
            path_parts = endpoint.lower().split("/")
            expected_roles.extend([p for p in path_parts if p])

    if not expected_roles:
        # Infer from page category
        if page.category == WikiTaxonomyCategory.API_REFERENCE:
            expected_roles = ["handler", "endpoint", "route", "controller"]
        elif page.category == WikiTaxonomyCategory.DATA_MODELS:
            expected_roles = ["model", "entity", "schema", "class"]
        elif page.category == WikiTaxonomyCategory.CORE_SERVICES:
            expected_roles = ["service", "handler", "processor"]

    # Check symbol against expected roles
    role_score = 0.0
    for role in expected_roles:
        if role in symbol_lower:
            role_score = max(role_score, WEIGHT_RUNTIME_ROLE * 0.8)
            # Exact role match
            if symbol_lower == role:
                role_score = max(role_score, WEIGHT_RUNTIME_ROLE)

    return role_score


def _score_by_api_relation(page: WikiPagePlan, span: EvidenceSpanRecord) -> float:
    """Score based on API endpoint relation."""
    sr = page.source_requirements
    if not sr or not sr.endpoints:
        return 0.0

    if not span.symbol:
        return 0.0

    symbol_lower = span.symbol.lower()

    for endpoint in sr.endpoints:
        # endpoint format: "METHOD /path" or just "/path"
        path = endpoint.split()[-1] if " " in endpoint else endpoint
        path_lower = _normalize_text(path)
        path_tokens = set(path_lower.replace("/", " ").split())

        # Check symbol against path tokens
        symbol_tokens = _tokenize(span.symbol)
        overlap = len(path_tokens & symbol_tokens)
        if overlap > 0:
            return WEIGHT_API_RELATION * (overlap / max(len(path_tokens), 1))

    return 0.0


def _score_by_data_model_relation(page: WikiPagePlan, span: EvidenceSpanRecord) -> float:
    """Score based on data model name relation."""
    sr = page.source_requirements
    if not sr or not sr.data_models:
        return 0.0

    if not span.symbol:
        return 0.0

    symbol_lower = span.symbol.lower()

    best_score = 0.0
    for model in sr.data_models:
        model_lower = model.lower()
        model_tokens = _tokenize(model)

        # Exact match
        if symbol_lower == model_lower:
            best_score = max(best_score, WEIGHT_DATA_MODEL)
        # Symbol contains model name
        elif model_lower in symbol_lower:
            best_score = max(best_score, WEIGHT_DATA_MODEL * 0.8)
        # Token overlap
        else:
            symbol_tokens = _tokenize(span.symbol)
            overlap = len(model_tokens & symbol_tokens)
            if overlap > 0:
                best_score = max(
                    best_score, WEIGHT_DATA_MODEL * 0.5 * (overlap / max(len(model_tokens), 1))
                )

    return best_score


def _score_by_ownership(
    ownership_confidence: OwnershipConfidence | None,
) -> float:
    """Convert ownership confidence to a score."""
    if not ownership_confidence:
        return 0.0  # No info means no ownership score

    if ownership_confidence.is_rejected:
        return 0.0
    if ownership_confidence.decision == OwnershipDecision.HIGH_CONFIDENCE:
        return 1.0 * WEIGHT_DOMAIN  # Strong ownership boost
    if ownership_confidence.decision == OwnershipDecision.MEDIUM_CONFIDENCE:
        return 0.7 * WEIGHT_DOMAIN
    if ownership_confidence.decision == OwnershipDecision.LOW_CONFIDENCE:
        return 0.4 * WEIGHT_DOMAIN

    return 0.0


def _create_rejection_reason(
    code: str,
    message: str,
    span: EvidenceSpanRecord | None = None,
    evidence_id: int | None = None,
) -> EvidenceRejectionReason:
    """Create a rejection reason with context."""
    return EvidenceRejectionReason(
        reason_code=code,
        reason=message,
        evidence_id=evidence_id,
        span_symbol=span.symbol if span else None,
        span_file_path=span.file_path if span else None,
    )


# =============================================================================
# Page Evidence Scorer
# =============================================================================


class PageEvidenceScorer:
    """Scores and ranks evidence spans for wiki pages.

    Uses multi-dimensional scoring combining:
    - Title match
    - Service slug match
    - Domain alignment
    - Runtime role
    - API relation
    - Data-model relation
    - Ownership confidence (from Task 33.1)

    Provides:
    - Top-N candidates with full scoring breakdown
    - Rejected candidates with reasons
    - Service-local evidence preference
    """

    def __init__(
        self,
        ownership_resolver: ServiceOwnershipResolver | None = None,
        top_n: int = TOP_N_CANDIDATES,
    ) -> None:
        """Initialize scorer.

        Args:
            ownership_resolver: Optional service ownership resolver for filtering
            top_n: Number of top candidates to retain
        """
        self.ownership_resolver = ownership_resolver
        self.top_n = top_n

    def score_page_evidence(
        self,
        page: WikiPagePlan,
        spans: list[EvidenceSpanRecord],
    ) -> PageEvidenceScoreResult:
        """Score evidence spans for a single wiki page.

        Args:
            page: The wiki page plan
            spans: Available evidence spans

        Returns:
            PageEvidenceScoreResult with candidates, rejected, and metadata
        """
        candidates: list[ScoredEvidenceCandidate] = []
        rejected: list[ScoredEvidenceCandidate] = []

        for span in spans:
            # Get ownership confidence if resolver available
            ownership: OwnershipConfidence | None = None
            if self.ownership_resolver:
                ownership = self.ownership_resolver.resolve_ownership(
                    symbol=span.symbol,
                    file_path=span.file_path,
                    span_text=span.span_text,
                )

            # Calculate individual dimension scores
            title_score = _score_by_title_match(page, span)
            slug_score = _score_by_service_slug(page, span)
            domain_score = _score_by_domain_match(page, span, ownership)
            role_score = _score_by_runtime_role(page, span)
            api_score = _score_by_api_relation(page, span)
            dm_score = _score_by_data_model_relation(page, span)
            ownership_score = _score_by_ownership(ownership)

            # Combine into total score
            total_score = (
                title_score + slug_score + domain_score + role_score + api_score + dm_score
            )
            if ownership_score > 0:
                total_score += ownership_score

            # Build match signals
            signals: list[str] = []
            if title_score > 0:
                signals.append("title_match")
            if slug_score > 0:
                signals.append("service_slug_match")
            if domain_score > 0:
                signals.append("domain_match")
            if role_score > 0:
                signals.append("runtime_role_match")
            if api_score > 0:
                signals.append("api_relation")
            if dm_score > 0:
                signals.append("data_model_relation")
            if ownership_score > 0:
                signals.append("ownership_confirmed")

            # Determine if rejected
            is_rejected = False
            rejection_reasons: list[EvidenceRejectionReason] = []

            if ownership and ownership.is_rejected:
                is_rejected = True
                for reason_text in ownership.rejection_reasons:
                    rejection_reasons.append(
                        _create_rejection_reason(
                            code="OWNERSHIP_REJECTED",
                            message=reason_text,
                            span=span,
                            evidence_id=getattr(span, "id", None),
                        )
                    )

            if total_score < REJECTION_THRESHOLD:
                is_rejected = True
                if not rejection_reasons:
                    rejection_reasons.append(
                        _create_rejection_reason(
                            code="LOW_SCORE",
                            message=f"Total score {total_score:.2f} below threshold {REJECTION_THRESHOLD}",
                            span=span,
                            evidence_id=getattr(span, "id", None),
                        )
                    )

            # Get evidence_id from span
            evidence_id = getattr(span, "id", None) or 0

            scored = ScoredEvidenceCandidate(
                evidence_id=evidence_id,
                span=span,
                score=total_score,
                title_score=title_score,
                service_slug_score=slug_score,
                domain_score=domain_score,
                runtime_role_score=role_score,
                api_score=api_score,
                data_model_score=dm_score,
                ownership_score=ownership_score,
                match_signals=signals,
                is_rejected=is_rejected,
                rejection_reasons=rejection_reasons,
            )

            if is_rejected:
                rejected.append(scored)
            else:
                candidates.append(scored)

        # Sort by score descending
        candidates.sort(key=lambda x: -x.score)
        rejected.sort(key=lambda x: -x.score)

        # Keep only top N candidates
        top_candidates = candidates[: self.top_n]

        # Determine if evidence is insufficient
        insufficient = len(top_candidates) < self.top_n and len(spans) > 0

        return PageEvidenceScoreResult(
            page_id=page.page_id,
            candidates=top_candidates,
            rejected=rejected,
            total_spans_evaluated=len(spans),
            insufficient_evidence=insufficient,
        )

    def score_evidence_with_rejection_persistence(
        self,
        page: WikiPagePlan,
        spans: list[EvidenceSpanRecord],
    ) -> tuple[list[ScoredEvidenceCandidate], list[ScoredEvidenceCandidate]]:
        """Score evidence and return candidates with rejection reasons.

        This method persists rejection reasons in the candidate objects
        for later inspection/audit.

        Args:
            page: The wiki page plan
            spans: Available evidence spans

        Returns:
            Tuple of (top_candidates, rejected_candidates) with reasons
        """
        result = self.score_page_evidence(page, spans)

        # Rejection reasons are already stored in each candidate
        # This allows later inspection via result.rejected[i].rejection_reasons

        return result.candidates, result.rejected


class ServiceLocalPreference:
    """Applies service-local preference bias to evidence scoring.

    Service-local evidence (from the same module/service) is preferred
    over generic shared modules unless the page topic explicitly requires
    shared infrastructure.
    """

    # Modules that are considered shared/infrastructure
    SHARED_MODULES = {
        "shared",
        "common",
        "util",
        "utils",
        "lib",
        "library",
        "config",
        "constants",
        "types",
        "interfaces",
        "infra",
        "infrastructure",
        "foundation",
    }

    def __init__(self, prefer_local: bool = True) -> None:
        """Initialize preference.

        Args:
            prefer_local: If True, prefer local evidence over shared
        """
        self.prefer_local = prefer_local

    def is_shared_module(self, file_path: str | None) -> bool:
        """Check if file path belongs to a shared module."""
        if not file_path:
            return False
        path_lower = file_path.lower()
        for shared in self.SHARED_MODULES:
            if f"/{shared}/" in path_lower or f"\\{shared}\\" in path_lower:
                return True
        return False

    def apply_preference(
        self,
        candidates: list[ScoredEvidenceCandidate],
    ) -> list[ScoredEvidenceCandidate]:
        """Apply service-local preference to candidates.

        Args:
            candidates: Scored evidence candidates

        Returns:
            Candidates with preference bias applied
        """
        if len(candidates) <= 1:
            return candidates

        if not self.prefer_local:
            # When preference is disabled, just sort by score descending
            return sorted(candidates, key=lambda c: -c.score)

        def locality_key(c: ScoredEvidenceCandidate) -> tuple[bool, float]:
            """Key for sorting: (is_shared, negative_score)."""
            is_shared = self.is_shared_module(c.span.file_path)
            return (is_shared, -c.score)

        return sorted(candidates, key=locality_key)


# =============================================================================
# Convenience Functions
# =============================================================================


def score_page_evidence(
    page: WikiPagePlan,
    spans: list[EvidenceSpanRecord],
    ownership_resolver: ServiceOwnershipResolver | None = None,
    prefer_local: bool = True,
) -> tuple[list[ScoredEvidenceCandidate], list[ScoredEvidenceCandidate]]:
    """Score evidence for a page with service-local preference.

    Args:
        page: The wiki page plan
        spans: Available evidence spans
        ownership_resolver: Optional service ownership resolver
        prefer_local: If True, prefer local evidence over shared

    Returns:
        Tuple of (top_candidates, rejected_candidates)
    """
    scorer = PageEvidenceScorer(ownership_resolver)
    result = scorer.score_page_evidence(page, spans)

    if prefer_local:
        preference = ServiceLocalPreference(prefer_local=True)
        result.candidates = preference.apply_preference(result.candidates)

    return result.candidates, result.rejected


def get_rejection_reasons(
    rejected: list[ScoredEvidenceCandidate],
) -> list[EvidenceRejectionReason]:
    """Extract all rejection reasons from rejected candidates.

    Args:
        rejected: List of rejected candidates

    Returns:
        Flat list of all rejection reasons for inspection
    """
    reasons: list[EvidenceRejectionReason] = []
    for candidate in rejected:
        reasons.extend(candidate.rejection_reasons)
    return reasons
