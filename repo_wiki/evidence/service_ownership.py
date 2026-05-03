"""Service ownership resolver for evidence binding.

Resolves which service owns which evidence spans to prevent hallucinated
bindings between unrelated services (e.g., GitLab/Jenkins/MCP pages should
not bind ai-service evidence).

This module provides:
- ServiceOwnershipResolver: Determines evidence ownership from module metadata
- OwnershipConfidence: Confidence scoring with rejection reasons
- Cross-service isolation: Prevents wrong-service evidence binding
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from repo_wiki.planner.schema import WikiPagePlan


class OwnershipDecision(str, Enum):
    """Decision outcome for service ownership check."""

    HIGH_CONFIDENCE = "high_confidence"  # Strong match, evidence clearly belongs
    MEDIUM_CONFIDENCE = "medium_confidence"  # Probable match
    LOW_CONFIDENCE = "low_confidence"  # Weak match, may not belong
    REJECTED = "rejected"  # Evidence does not belong to this service


@dataclass
class OwnershipSignal:
    """A single signal contributing to ownership decision."""

    signal_type: str  # e.g., 'domain_match', 'module_path', 'symbol_pattern'
    weight: float  # Contribution weight (0.0-1.0)
    score: float  # Signal score (0.0-1.0)
    reason: str  # Human-readable explanation


@dataclass
class OwnershipConfidence:
    """Confidence assessment for service ownership of evidence."""

    decision: OwnershipDecision
    confidence: float  # Overall confidence 0.0-1.0
    signals: list[OwnershipSignal] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    matched_service: str | None = None
    matched_domain: str | None = None

    @property
    def is_owned(self) -> bool:
        """Return True if evidence is considered owned by the service."""
        return self.decision in (
            OwnershipDecision.HIGH_CONFIDENCE,
            OwnershipDecision.MEDIUM_CONFIDENCE,
        )

    @property
    def is_rejected(self) -> bool:
        """Return True if evidence is explicitly rejected."""
        return self.decision == OwnershipDecision.REJECTED

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "decision": self.decision.value,
            "confidence": self.confidence,
            "signals": [
                {"type": s.signal_type, "weight": s.weight, "score": s.score, "reason": s.reason}
                for s in self.signals
            ],
            "rejection_reasons": self.rejection_reasons,
            "matched_service": self.matched_service,
            "matched_domain": self.matched_domain,
        }


# Known infrastructure/tooling services that should NOT be confused with ai-service
INFRASTRUCTURE_SERVICE_PATTERNS = {
    "gitlab": ["gitlab", "git-lfs", "gitlab-ci", ".gitlab"],
    "jenkins": ["jenkins", "jenkinsfile", "jenkins-pipeline"],
    "mcp": ["mcp", "model-context-protocol", "mcp-server", "mcp-client", "model context protocol"],
    "argocd": ["argocd", "argo-cd", "argoWorkflow"],
    "prometheus": ["prometheus", "prom-operator"],
    "grafana": ["grafana", "grafana-dashboard"],
    "kubernetes": ["kubernetes", "k8s", "kube-"],
    "docker": ["docker", "dockerfile", "docker-compose"],
    "terraform": ["terraform", "tf-", ".terraform"],
}

# ai-service related patterns that indicate ai/ML ownership
AI_SERVICE_PATTERNS = {
    "ai-service": [
        "ai-service",
        "ai_service",
        "aiservice",
        "embedding",
        "vector",
        "indexer",
        "retrieval",
        "model",
        "ml-",
        "machine-learning",
        "langchain",
        "llm",
        "openai",
        "anthropic",
        "chromadb",
        "faiss",
        "qdrant",
        "neural",
        "transformer",
        "attention",
    ],
    "indexer": ["indexer", "indexing", "search-index"],
    "retrieval": ["retrieval", "retriever", "rag"],
    "embedding": ["embedding", "embedder", "vectorize"],
}

# Module path to domain mapping for common layouts
DOMAIN_FROM_PATH = {
    "ai": "ai-services",
    "ml": "ai-services",
    "model": "ai-services",
    "embedding": "ai-services",
    "vector": "ai-services",
    "indexer": "ai-services",
    "retrieval": "ai-services",
    "rag": "ai-services",
    "langchain": "ai-services",
    "llm": "ai-services",
    "core-platform": "core-platform",
    "platform": "core-platform",
    "backend": "core-platform",
    "frontend": "frontend",
    "web": "frontend",
    "ui": "frontend",
    "docs": "documentation",
    "scripts": "tooling",
    "ci": "tooling",
    "scripts": "tooling",
    "templates": "tooling",
    "extensions": "extensions",
}


def _compute_text_similarity(a: str, b: str) -> float:
    """Compute simple text similarity (0.0 to 1.0)."""
    if not a or not b:
        return 0.0
    a_lower = a.lower()
    b_lower = b.lower()
    if a_lower == b_lower:
        return 1.0
    if a_lower in b_lower or b_lower in a_lower:
        return 0.8
    # Character overlap
    a_chars = set(a_lower.split())
    b_chars = set(b_lower.split())
    if not a_chars or not b_chars:
        return 0.0
    overlap = len(a_chars & b_chars)
    return overlap / max(len(a_chars), len(b_chars))


def _check_infrastructure_conflict(
    symbol: str | None, file_path: str | None, span_text: str | None
) -> tuple[bool, str]:
    """Check if evidence appears to belong to infrastructure tooling (GitLab, Jenkins, MCP).

    Returns (is_infrastructure, conflict_service)
    """
    text_to_check = " ".join(
        filter(
            None,
            [
                symbol or "",
                file_path or "",
                span_text or "",
            ],
        )
    ).lower()

    for service_name, patterns in INFRASTRUCTURE_SERVICE_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in text_to_check:
                return True, service_name
    return False, ""


def _extract_domain_from_path(file_path: str | None) -> str | None:
    """Extract domain hint from file path."""
    if not file_path:
        return None

    path_lower = file_path.lower().replace("-", "_").replace("/", "_")
    for domain_hint, domain in DOMAIN_FROM_PATH.items():
        if f"_{domain_hint}_" in path_lower or path_lower.startswith(domain_hint):
            return domain
    return None


class ServiceOwnershipResolver:
    """Resolves service ownership for evidence spans.

    Uses module metadata, file paths, symbol names, and domain classification
    to determine whether evidence belongs to a specific service.
    """

    def __init__(
        self,
        service_name: str,
        domain: str | None = None,
        service_family: str | None = None,
        module_paths: list[str] | None = None,
    ) -> None:
        """Initialize resolver for a specific service.

        Args:
            service_name: Name of the service (e.g., 'ai-service', 'gitlab-runner')
            domain: Business domain (e.g., 'ai-services', 'core-platform')
            service_family: Service family (e.g., 'python-backend')
            module_paths: List of module paths that belong to this service
        """
        self.service_name = service_name.lower()
        self.domain = domain
        self.service_family = service_family
        self.module_paths = [p.lower() for p in (module_paths or [])]

    def resolve_ownership(
        self,
        symbol: str | None,
        file_path: str | None,
        span_text: str | None,
        evidence_domain: str | None = None,
    ) -> OwnershipConfidence:
        """Resolve ownership of a single evidence span.

        Args:
            symbol: Symbol name from evidence span
            file_path: File path from evidence span
            span_text: Span text content
            evidence_domain: Domain from the evidence's module (if known)

        Returns:
            OwnershipConfidence with decision and signals
        """
        signals: list[OwnershipSignal] = []
        rejection_reasons: list[str] = []

        # Check for infrastructure conflicts first (GitLab, Jenkins, MCP)
        is_infra, conflict_service = _check_infrastructure_conflict(symbol, file_path, span_text)
        if is_infra:
            rejection_reasons.append(
                f"Evidence belongs to infrastructure service '{conflict_service}', not '{self.service_name}'"
            )
            signals.append(
                OwnershipSignal(
                    signal_type="infrastructure_conflict",
                    weight=1.0,
                    score=0.0,
                    reason=f"Found {conflict_service} pattern in evidence",
                )
            )
            return OwnershipConfidence(
                decision=OwnershipDecision.REJECTED,
                confidence=1.0,
                signals=signals,
                rejection_reasons=rejection_reasons,
            )

        # Score based on domain match
        domain_score = 0.0
        if evidence_domain and self.domain:
            if evidence_domain == self.domain:
                domain_score = 1.0
                signals.append(
                    OwnershipSignal(
                        signal_type="domain_match",
                        weight=0.4,
                        score=1.0,
                        reason=f"Domain '{evidence_domain}' matches service domain",
                    )
                )
            elif _compute_text_similarity(evidence_domain, self.domain) > 0.6:
                domain_score = 0.6
                signals.append(
                    OwnershipSignal(
                        signal_type="domain_similarity",
                        weight=0.4,
                        score=0.6,
                        reason=f"Domain '{evidence_domain}' similar to '{self.domain}'",
                    )
                )
            else:
                rejection_reasons.append(
                    f"Domain mismatch: evidence has '{evidence_domain}', expected '{self.domain}'"
                )
                signals.append(
                    OwnershipSignal(
                        signal_type="domain_mismatch",
                        weight=0.4,
                        score=0.0,
                        reason=f"Domain '{evidence_domain}' does not match '{self.domain}'",
                    )
                )

        # Score based on service name in symbol
        symbol_score = 0.0
        if symbol:
            symbol_lower = symbol.lower()
            service_name_parts = (
                self.service_name.lower().replace("-", " ").replace("_", " ").split()
            )

            # Exact service name match
            if self.service_name in symbol_lower:
                symbol_score = 1.0
                signals.append(
                    OwnershipSignal(
                        signal_type="service_name_in_symbol",
                        weight=0.3,
                        score=1.0,
                        reason=f"Service name '{self.service_name}' found in symbol",
                    )
                )
            # Partial match
            elif any(part in symbol_lower for part in service_name_parts if len(part) > 3):
                symbol_score = 0.7
                signals.append(
                    OwnershipSignal(
                        signal_type="service_name_partial",
                        weight=0.3,
                        score=0.7,
                        reason="Partial service name match in symbol",
                    )
                )
            # AI service patterns
            elif self.service_name in AI_SERVICE_PATTERNS:
                for ai_pattern in AI_SERVICE_PATTERNS.get(self.service_name, []):
                    if ai_pattern.lower() in symbol_lower:
                        symbol_score = 0.8
                        signals.append(
                            OwnershipSignal(
                                signal_type="ai_pattern_match",
                                weight=0.3,
                                score=0.8,
                                reason=f"AI service pattern '{ai_pattern}' found",
                            )
                        )
                        break

        # Score based on file path
        path_score = 0.0
        path_domain = None
        if file_path:
            path_domain = _extract_domain_from_path(file_path)
            if path_domain:
                if path_domain == self.domain:
                    path_score = 1.0
                    signals.append(
                        OwnershipSignal(
                            signal_type="path_domain_match",
                            weight=0.3,
                            score=1.0,
                            reason=f"Path domain '{path_domain}' matches",
                        )
                    )
                elif evidence_domain and path_domain == evidence_domain:
                    path_score = 0.8
                    signals.append(
                        OwnershipSignal(
                            signal_type="path_domain_agrees",
                            weight=0.3,
                            score=0.8,
                            reason=f"Path domain '{path_domain}' agrees with evidence domain",
                        )
                    )
                else:
                    path_score = 0.3
                    signals.append(
                        OwnershipSignal(
                            signal_type="path_domain_hint",
                            weight=0.3,
                            score=0.3,
                            reason=f"Path domain '{path_domain}' is a weak hint",
                        )
                    )

        # Calculate weighted confidence
        total_weight = sum(s.weight for s in signals) if signals else 1.0
        if signals:
            confidence = sum(s.weight * s.score for s in signals) / total_weight
        else:
            confidence = 0.0

        # Determine decision
        if rejection_reasons:
            decision = OwnershipDecision.REJECTED
        elif confidence >= 0.8:
            decision = OwnershipDecision.HIGH_CONFIDENCE
        elif confidence >= 0.5:
            decision = OwnershipDecision.MEDIUM_CONFIDENCE
        else:
            decision = OwnershipDecision.LOW_CONFIDENCE

        return OwnershipConfidence(
            decision=decision,
            confidence=confidence,
            signals=signals,
            rejection_reasons=rejection_reasons,
            matched_domain=evidence_domain or path_domain,
        )


def filter_evidence_by_ownership(
    page: WikiPagePlan,
    evidence_spans: list[dict],
    resolver: ServiceOwnershipResolver,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Filter evidence spans by service ownership.

    Separates spans into owned, uncertain, and rejected categories.

    Args:
        page: The wiki page plan
        evidence_spans: List of evidence span records
        resolver: Service ownership resolver

    Returns:
        Tuple of (owned_spans, uncertain_spans, rejected_spans)
    """
    owned: list[dict] = []
    uncertain: list[dict] = []
    rejected: list[dict] = []

    for span in evidence_spans:
        confidence = resolver.resolve_ownership(
            symbol=span.get("symbol"),
            file_path=span.get("file_path"),
            span_text=span.get("span_text"),
            evidence_domain=span.get("domain"),
        )

        span_with_ownership = {**span, "_ownership": confidence.to_dict()}

        if confidence.is_rejected:
            rejected.append(span_with_ownership)
        elif confidence.is_owned:
            owned.append(span_with_ownership)
        else:
            uncertain.append(span_with_ownership)

    return owned, uncertain, rejected


class OwnershipVerifier:
    """Verifies that evidence bindings respect service ownership.

    Used to prevent hallucinated bindings where evidence from one service
    (e.g., GitLab, Jenkins, MCP) is incorrectly bound to another (e.g., ai-service).
    """

    # Maximum fraction of uncertain evidence allowed before flagging
    MAX_UNCERTAIN_RATIO = 0.3

    def __init__(self, default_resolver: ServiceOwnershipResolver | None = None) -> None:
        self.default_resolver = default_resolver

    def verify_binding(
        self,
        page: WikiPagePlan,
        evidence_spans: list[dict],
        resolver: ServiceOwnershipResolver | None = None,
    ) -> dict[str, Any]:
        """Verify that evidence bindings are valid for a page.

        Returns a verification report with:
        - is_valid: Whether bindings pass the ownership check
        - owned_count, uncertain_count, rejected_count: Evidence counts
        - warnings: List of warning messages
        - errors: List of error messages (binding violations)
        """
        resolver = resolver or self.default_resolver
        if not resolver:
            return {
                "is_valid": True,
                "owned_count": len(evidence_spans),
                "uncertain_count": 0,
                "rejected_count": 0,
                "warnings": ["No resolver configured, skipping ownership check"],
                "errors": [],
            }

        owned, uncertain, rejected = filter_evidence_by_ownership(page, evidence_spans, resolver)

        total = len(evidence_spans)
        uncertain_ratio = len(uncertain) / total if total > 0 else 0.0

        warnings: list[str] = []
        errors: list[str] = []

        # Check for rejected evidence
        if rejected:
            errors.append(f"{len(rejected)} evidence spans rejected due to ownership mismatch")
            for span in rejected[:3]:  # Show first 3
                ownership = span.get("_ownership", {})
                reasons = ownership.get("rejection_reasons", [])
                if reasons:
                    errors.append(f"  - {span.get('symbol', span.get('file_path'))}: {reasons[0]}")

        # Warn about uncertain evidence
        if uncertain_ratio > self.MAX_UNCERTAIN_RATIO:
            warnings.append(
                f"Uncertain evidence ratio ({uncertain_ratio:.1%}) exceeds threshold ({self.MAX_UNCERTAIN_RATIO:.1%})"
            )

        # Determine validity
        is_valid = len(rejected) == 0 and uncertain_ratio <= self.MAX_UNCERTAIN_RATIO

        return {
            "is_valid": is_valid,
            "owned_count": len(owned),
            "uncertain_count": len(uncertain),
            "rejected_count": len(rejected),
            "uncertain_ratio": uncertain_ratio,
            "warnings": warnings,
            "errors": errors,
        }
