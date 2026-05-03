"""Quality guardrails for hallucination and generic prose detection.

This module provides quality checks to detect:
- Unsupported claims (assertions without citation backing)
- Missing citation density (too few citations for content length)
- Repeated filler words (generic prose patterns)
- Low prose density (list/table dumps)
- List dumps (excessive bullet points without narrative)

Phase 24 - Task 24.5: Quality guardrails for hallucination and generic prose

Integration:
- Uses qoder-like profile verification via QoderProfileVerifier
- Integrates with VerifierService via QualityGateResult
- Reason codes for CI output
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from repo_wiki.generator.io import read_text

# =============================================================================
# QUALITY GATE REASON CODES (6xxx)
# =============================================================================


class QualityReasonCode(Enum):
    """Reason codes for quality gate failures."""

    # Unsupported claims (60xx)
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"  # 6001: Claim without citation backing
    UNVERIFIABLE_STATEMENT = "UNVERIFIABLE_STATEMENT"  # 6002: Statement that cannot be verified

    # Citation density (61xx)
    LOW_CITATION_DENSITY = "LOW_CITATION_DENSITY"  # 6101: Too few citations for content
    CITATION_AGE_STALE = "CITATION_AGE_STALE"  # 6102: Citation references stale content

    # Generic prose / filler (62xx)
    REPEATED_FILLER = "REPEATED_FILLER"  # 6201: Repeated filler words/phrases
    GENERIC_PROSE = "GENERIC_PROSE"  # 6202: Generic template prose
    HALLUCINATED_TERMINOLOGY = "HALLUCINATED_TERMINOLOGY"  # 6203: Made-up technical terms

    # Prose density (63xx)
    LIST_DUMP = "LIST_DUMP"  # 6301: Excessive list items without prose
    TABLE_DUMP = "TABLE_DUMP"  # 6302: Table without narrative explanation
    LOW_PROSE_RATIO = "LOW_PROSE_RATIO"  # 6303: Less than minimum prose ratio

    # Qoder profile (64xx)
    QODER_PROFILE_MISSING = "QODER_PROFILE_MISSING"  # 6401: No qoder profile found
    QODER_PROFILE_INCOMPLETE = "QODER_PROFILE_INCOMPLETE"  # 6402: Qoder profile incomplete


# =============================================================================
# GENERIC PROSE AND FILLER PATTERNS
# =============================================================================

# Filler words and phrases commonly found in generic AI-generated prose
FILLER_PATTERNS: list[tuple[str, str]] = [
    # Weak qualifiers
    (
        r"\b(v?:?ery|extremely|incredibly|highly|deeply|truly|really|quite|somewhat)\s+",
        "weak_qualifier",
    ),
    # Generic transitions
    (
        r"\b(It is important to note that|It should be noted that|Note that|As previously mentioned|In summary|To summarize|In conclusion|Additionally|Furthermore|Moreover|Likewise|Similarly)\b",
        "generic_transition",
    ),
    # Vague references
    (
        r"\b(this system|this application|this software|the system|the application|the software)\b",
        "vague_reference",
    ),
    # Template phrases
    (
        r"\b(is designed to|is built to|serves as a|acts as a|provides the ability to|enables the user to)\b",
        "template_phrase",
    ),
    # Common filler
    (
        r"\b(of course|obviously|clearly|certainly|undoubtedly|basically|essentially|fundamentally|literally|virtually)\b",
        "common_filler",
    ),
    # Nominalization patterns
    (
        r"\b(utilization|implementation|utilization|optimization|maximization|minimization)\b",
        "nominalization",
    ),
]

# Compiled filler regex for performance
COMPILED_FILLER_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern, re.IGNORECASE), name) for pattern, name in FILLER_PATTERNS
]

# Hallucinated/invented technical terms patterns
HALLUCINATION_PATTERNS: list[tuple[str, str]] = [
    # Common hallucinated patterns
    (
        r"\b(XML-based|XML-driven|JSON-enabled|REST-ful|cloud-native|microservices-ready)\b",
        "buzzword_combo",
    ),
    # Invented frameworks
    (r"\b(Framework\s+X|Architecture\s+Y|Module\s+Z|System\s+ABC)\b", "placeholder_names"),
    # Fake version numbers
    (r"\bv\d+\.\d+\.\d+(?:\.\d+)?\b", "version_bloat"),
]

COMPILED_HALLUCINATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern, re.IGNORECASE), name) for pattern, name in HALLUCINATION_PATTERNS
]


# =============================================================================
# QODER PROFILE VERIFIER
# =============================================================================


@dataclass
class QoderProfileMetrics:
    """Metrics from qoder-style profile verification."""

    profile_found: bool = False
    profile_complete: bool = False
    sections_documented: int = 0
    sections_total: int = 0
    citations_count: int = 0
    estimated_prose_chars: int = 0
    issues: list[str] = field(default_factory=list)


class QoderProfileVerifier:
    """Verifies content against qoder-like profile expectations.

    Qoder profiles define expected section structure and content quality.
    This verifier checks if generated content meets those expectations.
    """

    # Expected section coverage for a complete profile
    EXPECTED_SECTIONS: frozenset[str] = frozenset(
        [
            "project",
            "architecture",
            "services",
            "data-model",
            "api",
            "operations",
            "development",
            "security",
            "troubleshooting",
        ]
    )

    # Minimum citation density: citations per 1000 prose chars
    MIN_CITATION_DENSITY = 0.5

    # Maximum filler ratio: filler words per 1000 prose chars
    MAX_FILLER_RATIO = 15.0

    # Minimum prose ratio: prose chars / total chars
    MIN_PROSE_RATIO = 0.3

    def __init__(self, workspace_root: Path | str | None = None) -> None:
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()

    def verify_profile(self, doc_path: Path) -> QoderProfileMetrics:
        """Verify a document against qoder profile expectations.

        Args:
            doc_path: Path to documentation file to verify

        Returns:
            QoderProfileMetrics with verification results
        """
        metrics = QoderProfileMetrics()

        if not doc_path.exists():
            metrics.issues.append(f"Document does not exist: {doc_path}")
            return metrics

        content = read_text(doc_path)

        # Basic content analysis
        metrics.estimated_prose_chars = self._count_prose_chars(content)

        # Check section coverage
        section_headers = self._extract_section_headers(content)
        metrics.sections_documented = len(section_headers)
        metrics.sections_total = len(self.EXPECTED_SECTIONS)

        # Count citations
        metrics.citations_count = self._count_citations(content)

        # Check profile completeness
        metrics.profile_found = True
        metrics.profile_complete = (
            metrics.sections_documented >= 3
            and metrics.estimated_prose_chars >= 200
            and metrics.citations_count >= 1
        )

        # Report issues
        if metrics.estimated_prose_chars < 200:
            metrics.issues.append("Content too short for meaningful profile")

        if metrics.citations_count == 0:
            metrics.issues.append("No citations found")

        if metrics.sections_documented < 3:
            metrics.issues.append("Too few sections for profile verification")

        return metrics

    def _extract_section_headers(self, content: str) -> list[str]:
        """Extract section headers from content."""
        header_pattern = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
        return [m.group(1).strip() for m in header_pattern.finditer(content)]

    def _count_citations(self, content: str) -> int:
        """Count citations in content."""
        cite_pattern = re.compile(r"<cite>[^<]+</cite>")
        return len(cite_pattern.findall(content))

    def _count_prose_chars(self, content: str) -> int:
        """Count prose characters (excluding markdown syntax).

        Strips headers, list items, code blocks, and tables.
        """
        lines = content.split("\n")
        prose_lines = []
        in_code_block = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            if stripped.startswith("#"):
                continue
            if stripped.startswith("-") or stripped.startswith("*"):
                continue
            if stripped.startswith("|"):
                continue
            if stripped.startswith("!"):
                continue
            prose_lines.append(stripped)

        return len(" ".join(prose_lines))


# =============================================================================
# QUALITY GUARDRAILS CHECKER
# =============================================================================


@dataclass
class QualityIssue:
    """A single quality issue detected."""

    reason_code: QualityReasonCode
    message: str
    location: str = ""  # File or section where issue found
    severity: str = "ERROR"  # ERROR, WARNING, INFO
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityGateResult:
    """Result of quality gate check on a document."""

    document_path: Path
    passed: bool
    issues: list[QualityIssue]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_path": str(self.document_path),
            "passed": self.passed,
            "issue_count": len(self.issues),
            "issues": [
                {
                    "reason_code": issue.reason_code.value,
                    "message": issue.message,
                    "location": issue.location,
                    "severity": issue.severity,
                    "details": issue.details,
                }
                for issue in self.issues
            ],
            "metrics": self.metrics,
        }


class QualityGuardrailsChecker:
    """Checks generated content against quality guardrails.

    This checker detects:
    1. Unsupported claims - assertions without citation backing
    2. Low citation density - too few citations relative to content
    3. Repeated filler - generic filler words and phrases
    4. Low prose density - list dumps and table dumps
    5. Generic prose - template-based AI-generated content

    Phase 24 - Task 24.5
    """

    # Thresholds
    MIN_CITATIONS_PER_1000_CHARS = 0.5  # At least 1 citation per 2000 chars
    MAX_FILLER_WORDS_PER_1000_CHARS = 15.0
    MIN_PROSE_RATIO = 0.25  # At least 25% prose
    MAX_LIST_ITEMS_BEFORE_WARNING = 10  # Warn after 10 list items in a row
    MAX_REPEATED_FILLER_INSTANCES = 3  # Flag if same filler appears 3+ times

    # Patterns for claim detection
    CLAIM_PATTERNS: list[re.Pattern[str]] = [
        # Absolute claims
        re.compile(r"\b(always|never|must|will|shall|guarantee|ensure)\b", re.IGNORECASE),
        # Performance claims
        re.compile(r"\b(faster|slower|better|worse|optimized|scalable)\b", re.IGNORECASE),
        # Technical claims
        re.compile(r"\b(uses?|implements?|provides?|supports?|enables?|allows?)\b", re.IGNORECASE),
    ]

    def __init__(self, workspace_root: Path | str | None = None) -> None:
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.profile_verifier = QoderProfileVerifier(self.workspace_root)

    def check_document(self, doc_path: Path) -> QualityGateResult:
        """Check a document against all quality guardrails.

        Args:
            doc_path: Path to document to check

        Returns:
            QualityGateResult with all issues found
        """
        issues: list[QualityIssue] = []
        metrics: dict[str, Any] = {}

        if not doc_path.exists():
            return QualityGateResult(
                document_path=doc_path,
                passed=False,
                issues=[
                    QualityIssue(
                        reason_code=QualityReasonCode.UNVERIFIABLE_STATEMENT,
                        message=f"Document not found: {doc_path}",
                        severity="ERROR",
                    )
                ],
                metrics={},
            )

        content = read_text(doc_path)

        # Run all checks
        issues.extend(self._check_unsupported_claims(content, doc_path))
        issues.extend(self._check_citation_density(content, doc_path))
        issues.extend(self._check_filler_words(content, doc_path))
        issues.extend(self._check_prose_density(content, doc_path))
        issues.extend(self._check_list_dumps(content, doc_path))
        issues.extend(self._check_generic_prose(content, doc_path))

        # Collect metrics
        metrics = self._collect_metrics(content)

        passed = not any(issue.severity == "ERROR" for issue in issues)

        return QualityGateResult(
            document_path=doc_path,
            passed=passed,
            issues=issues,
            metrics=metrics,
        )

    def check_batch(self, doc_paths: list[Path]) -> dict[Path, QualityGateResult]:
        """Check multiple documents.

        Args:
            doc_paths: List of document paths to check

        Returns:
            Dict mapping each path to its QualityGateResult
        """
        return {doc_path: self.check_document(doc_path) for doc_path in doc_paths}

    def _check_unsupported_claims(self, content: str, doc_path: Path) -> list[QualityIssue]:
        """Check for claims without citation backing.

        Detects absolute claims, performance claims, and technical claims
        that lack citation references.
        """
        issues: list[QualityIssue] = []

        # Find all claims
        claim_lines: list[tuple[int, str]] = []
        for i, line in enumerate(content.split("\n"), 1):
            for pattern in self.CLAIM_PATTERNS:
                if pattern.search(line):
                    claim_lines.append((i, line.strip()))
                    break

        if not claim_lines:
            return issues

        # Count citations in content
        cite_count = len(re.findall(r"<cite>[^<]+</cite>", content))

        # If content has many claims but few citations, flag potential unsupported claims
        if len(claim_lines) > 3 and cite_count == 0:
            issues.append(
                QualityIssue(
                    reason_code=QualityReasonCode.UNSUPPORTED_CLAIM,
                    message=f"Found {len(claim_lines)} claims but no citations - claims may be unsupported",
                    location=f"{doc_path.name}:1-{content.count(chr(10))}",
                    severity="WARNING",
                    details={
                        "claim_count": len(claim_lines),
                        "citation_count": cite_count,
                    },
                )
            )

        return issues

    def _check_citation_density(self, content: str, doc_path: Path) -> list[QualityIssue]:
        """Check citation density against prose length."""
        issues: list[QualityIssue] = []

        prose_chars = self._count_prose_chars(content)
        cite_count = len(re.findall(r"<cite>[^<]+</cite>", content))

        if prose_chars == 0:
            return issues

        # Calculate citation density (citations per 1000 prose chars)
        density = (cite_count / prose_chars) * 1000

        if density < self.MIN_CITATIONS_PER_1000_CHARS:
            issues.append(
                QualityIssue(
                    reason_code=QualityReasonCode.LOW_CITATION_DENSITY,
                    message=f"Citation density too low: {density:.2f}/1000 chars (min: {self.MIN_CITATIONS_PER_1000_CHARS})",
                    location=doc_path.name,
                    severity="WARNING",
                    details={
                        "citation_density": round(density, 3),
                        "prose_chars": prose_chars,
                        "citation_count": cite_count,
                    },
                )
            )

        return issues

    def _check_filler_words(self, content: str, doc_path: Path) -> list[QualityIssue]:
        """Check for repeated filler words and generic phrases."""
        issues: list[QualityIssue] = []
        filler_counts: dict[str, int] = {}

        prose_chars = self._count_prose_chars(content)
        if prose_chars == 0:
            return issues

        # Count each type of filler
        for pattern, name in COMPILED_FILLER_PATTERNS:
            matches = pattern.findall(content)
            if matches:
                filler_counts[name] = len(matches)

        # Check for repeated instances of same filler
        for filler_name, count in filler_counts.items():
            if count >= self.MAX_REPEATED_FILLER_INSTANCES:
                issues.append(
                    QualityIssue(
                        reason_code=QualityReasonCode.REPEATED_FILLER,
                        message=f"Repeated filler '{filler_name}' found {count} times",
                        location=doc_path.name,
                        severity="WARNING",
                        details={"filler_type": filler_name, "count": count},
                    )
                )

        # Calculate total filler ratio
        total_filler = sum(filler_counts.values())
        filler_ratio = (total_filler / prose_chars) * 1000

        if filler_ratio > self.MAX_FILLER_WORDS_PER_1000_CHARS:
            issues.append(
                QualityIssue(
                    reason_code=QualityReasonCode.GENERIC_PROSE,
                    message=f"Filler ratio too high: {filler_ratio:.1f}/1000 chars (max: {self.MAX_FILLER_WORDS_PER_1000_CHARS})",
                    location=doc_path.name,
                    severity="WARNING",
                    details={
                        "filler_ratio": round(filler_ratio, 1),
                        "total_filler": total_filler,
                    },
                )
            )

        return issues

    def _check_prose_density(self, content: str, doc_path: Path) -> list[QualityIssue]:
        """Check prose vs list/table ratio."""
        issues: list[QualityIssue] = []

        lines = content.split("\n")
        prose_lines: list[str] = []
        list_lines: list[str] = []
        table_lines: list[str] = []

        in_code_block = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            if stripped.startswith("#"):
                continue
            if stripped.startswith("-") or stripped.startswith("*"):
                list_lines.append(stripped)
                continue
            if stripped.startswith("|"):
                table_lines.append(stripped)
                continue
            if stripped.startswith("!"):
                continue
            prose_lines.append(stripped)

        total_content_lines = len(prose_lines) + len(list_lines) + len(table_lines)
        if total_content_lines == 0:
            return issues

        prose_ratio = len(prose_lines) / total_content_lines

        if prose_ratio < self.MIN_PROSE_RATIO:
            issues.append(
                QualityIssue(
                    reason_code=QualityReasonCode.LOW_PROSE_RATIO,
                    message=f"Prose ratio too low: {prose_ratio*100:.0f}% (min: {self.MIN_PROSE_RATIO*100:.0f}%)",
                    location=doc_path.name,
                    severity="ERROR",
                    details={
                        "prose_ratio": round(prose_ratio, 2),
                        "prose_lines": len(prose_lines),
                        "list_lines": len(list_lines),
                        "table_lines": len(table_lines),
                    },
                )
            )

        return issues

    def _check_list_dumps(self, content: str, doc_path: Path) -> list[QualityIssue]:
        """Check for excessive list items without narrative."""
        issues: list[QualityIssue] = []

        lines = content.split("\n")
        consecutive_lists: list[int] = []  # Tracks line numbers with list items
        in_code_block = False

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            if stripped.startswith("-") or stripped.startswith("*"):
                consecutive_lists.append(i)

        # Check for list dumps (10+ consecutive list items)
        if len(consecutive_lists) >= self.MAX_LIST_ITEMS_BEFORE_WARNING:
            # Find the longest consecutive run
            max_run = 1
            current_run = 1
            for i in range(1, len(consecutive_lists)):
                if consecutive_lists[i] - consecutive_lists[i - 1] == 1:
                    current_run += 1
                    max_run = max(max_run, current_run)
                else:
                    current_run = 1

            if max_run >= self.MAX_LIST_ITEMS_BEFORE_WARNING:
                issues.append(
                    QualityIssue(
                        reason_code=QualityReasonCode.LIST_DUMP,
                        message=f"List dump detected: {max_run} consecutive list items without narrative",
                        location=doc_path.name,
                        severity="ERROR",
                        details={"consecutive_list_items": max_run},
                    )
                )

        return issues

    def _check_generic_prose(self, content: str, doc_path: Path) -> list[QualityIssue]:
        """Check for generic AI-generated prose patterns."""
        issues: list[QualityIssue] = []

        # Check for hallucination patterns
        hallucination_counts: dict[str, int] = {}
        for pattern, name in COMPILED_HALLUCINATION_PATTERNS:
            matches = pattern.findall(content)
            if matches:
                hallucination_counts[name] = len(matches)

        for hallucination_type, count in hallucination_counts.items():
            if count >= 2:
                issues.append(
                    QualityIssue(
                        reason_code=QualityReasonCode.HALLUCINATED_TERMINOLOGY,
                        message=f"Possible hallucinated content: {hallucination_type} found {count} times",
                        location=doc_path.name,
                        severity="ERROR",
                        details={"type": hallucination_type, "count": count},
                    )
                )

        return issues

    def _count_prose_chars(self, content: str) -> int:
        """Count prose characters (excluding markdown syntax)."""
        lines = content.split("\n")
        prose_lines = []
        in_code_block = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            if stripped.startswith("#"):
                continue
            if stripped.startswith("-") or stripped.startswith("*"):
                continue
            if stripped.startswith("|"):
                continue
            if stripped.startswith("!"):
                continue
            prose_lines.append(stripped)

        return len(" ".join(prose_lines))

    def _collect_metrics(self, content: str) -> dict[str, Any]:
        """Collect quality metrics for a document."""
        prose_chars = self._count_prose_chars(content)
        cite_count = len(re.findall(r"<cite>[^<]+</cite>", content))
        prose_lines = len(
            [
                l
                for l in content.split("\n")
                if l.strip() and not l.strip().startswith(("#", "-", "*", "|", "!", "```"))
            ]
        )
        list_items = len([l for l in content.split("\n") if l.strip().startswith(("-", "*"))])

        filler_counts: dict[str, int] = {}
        for pattern, name in COMPILED_FILLER_PATTERNS:
            filler_counts[name] = len(pattern.findall(content))

        return {
            "prose_chars": prose_chars,
            "prose_lines": prose_lines,
            "citation_count": cite_count,
            "list_item_count": list_items,
            "filler_counts": filler_counts,
            "total_filler": sum(filler_counts.values()),
        }


# =============================================================================
# FACTORY AND INTEGRATION HELPERS
# =============================================================================


def create_quality_checker(
    workspace_root: Path | str | None = None,
) -> QualityGuardrailsChecker:
    """Create a quality guardrails checker.

    Args:
        workspace_root: Optional workspace root for path resolution

    Returns:
        QualityGuardrailsChecker instance
    """
    return QualityGuardrailsChecker(workspace_root)


def check_document_quality(
    doc_path: Path,
    workspace_root: Path | str | None = None,
) -> QualityGateResult:
    """Convenience function to check a single document.

    Args:
        doc_path: Path to document to check
        workspace_root: Optional workspace root

    Returns:
        QualityGateResult with check results
    """
    checker = create_quality_checker(workspace_root)
    return checker.check_document(doc_path)
