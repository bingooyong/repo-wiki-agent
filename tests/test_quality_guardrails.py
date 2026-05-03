"""Tests for quality guardrails module.

Tests the quality_guardrails module (repo_wiki/verifier/quality_guardrails.py)
which provides:
- QualityGuardrailsChecker: Core quality checks
- QoderProfileVerifier: Qoder-style profile verification
- QualityGateResult: Results container
- QualityReasonCode: Reason codes for CI

Phase 24 - Task 24.5: Quality guardrails for hallucination and generic prose
"""

from __future__ import annotations

from pathlib import Path

import pytest

from repo_wiki.generator.io import write_text
from repo_wiki.verifier.quality_guardrails import (
    QoderProfileMetrics,
    QoderProfileVerifier,
    QualityGateResult,
    QualityGuardrailsChecker,
    QualityIssue,
    QualityReasonCode,
    check_document_quality,
    create_quality_checker,
)


class TestQualityReasonCode:
    """Tests for QualityReasonCode enum."""

    def test_unsupported_claim_code(self):
        assert QualityReasonCode.UNSUPPORTED_CLAIM.value == "UNSUPPORTED_CLAIM"

    def test_low_citation_density_code(self):
        assert QualityReasonCode.LOW_CITATION_DENSITY.value == "LOW_CITATION_DENSITY"

    def test_repeated_filler_code(self):
        assert QualityReasonCode.REPEATED_FILLER.value == "REPEATED_FILLER"

    def test_generic_prose_code(self):
        assert QualityReasonCode.GENERIC_PROSE.value == "GENERIC_PROSE"

    def test_list_dump_code(self):
        assert QualityReasonCode.LIST_DUMP.value == "LIST_DUMP"

    def test_hallucinated_terminology_code(self):
        assert QualityReasonCode.HALLUCINATED_TERMINOLOGY.value == "HALLUCINATED_TERMINOLOGY"


class TestQualityIssue:
    """Tests for QualityIssue dataclass."""

    def test_create_quality_issue(self):
        issue = QualityIssue(
            reason_code=QualityReasonCode.LOW_CITATION_DENSITY,
            message="Citation density too low",
            location="docs/test.md",
            severity="WARNING",
        )
        assert issue.reason_code == QualityReasonCode.LOW_CITATION_DENSITY
        assert issue.severity == "WARNING"


class TestQualityGateResult:
    """Tests for QualityGateResult dataclass."""

    def test_passed_result(self):
        result = QualityGateResult(
            document_path=Path("docs/test.md"),
            passed=True,
            issues=[],
            metrics={"prose_chars": 500},
        )
        assert result.passed is True
        assert len(result.issues) == 0

    def test_failed_result(self):
        issue = QualityIssue(
            reason_code=QualityReasonCode.LIST_DUMP,
            message="List dump detected",
            severity="ERROR",
        )
        result = QualityGateResult(
            document_path=Path("docs/test.md"),
            passed=False,
            issues=[issue],
            metrics={"prose_chars": 100},
        )
        assert result.passed is False
        assert len(result.issues) == 1
        assert result.issues[0].reason_code == QualityReasonCode.LIST_DUMP

    def test_to_dict(self):
        issue = QualityIssue(
            reason_code=QualityReasonCode.GENERIC_PROSE,
            message="Generic prose detected",
            location="test.md",
            severity="WARNING",
            details={"filler_ratio": 20.0},
        )
        result = QualityGateResult(
            document_path=Path("test.md"),
            passed=False,
            issues=[issue],
            metrics={"prose_chars": 300},
        )
        d = result.to_dict()
        assert d["passed"] is False
        assert d["issue_count"] == 1
        assert d["issues"][0]["reason_code"] == "GENERIC_PROSE"


class TestQoderProfileVerifier:
    """Tests for QoderProfileVerifier."""

    def test_verify_nonexistent_document(self, tmp_path: Path):
        verifier = QoderProfileVerifier(tmp_path)
        result = verifier.verify_profile(tmp_path / "nonexistent.md")
        assert result.profile_found is False
        assert len(result.issues) > 0

    def test_verify_empty_document(self, tmp_path: Path):
        doc_path = tmp_path / "test.md"
        write_text(doc_path, "")
        verifier = QoderProfileVerifier(tmp_path)
        result = verifier.verify_profile(doc_path)
        assert result.profile_found is True
        assert result.profile_complete is False
        assert "too short" in result.issues[0].lower()

    def test_verify_document_with_citations(self, tmp_path: Path):
        doc_path = tmp_path / "test.md"
        write_text(
            doc_path,
            """# Test

This is a test document with substantial prose content.

See <cite>src/test.py:1</cite> for details.

## Section 1

More prose content here.

## Section 2

Even more content.
""",
        )
        verifier = QoderProfileVerifier(tmp_path)
        result = verifier.verify_profile(doc_path)
        assert result.profile_found is True
        assert result.citations_count >= 1
        assert result.sections_documented >= 2

    def test_verify_profile_completeness(self, tmp_path: Path):
        doc_path = tmp_path / "test.md"
        # Write content with 3+ sections, 200+ prose chars, and citations
        content = """# Test Document

This is the first paragraph with substantial prose content that exceeds
the minimum character threshold for meaningful profile verification.

## Section One

Here is more content for the first section that continues to build up
the overall prose character count.

## Section Two

Additional content in the second section to ensure we have enough
material for proper quality assessment.

## Section Three

The final section with more descriptive text that rounds out our
document and provides adequate coverage.
"""
        write_text(doc_path, content)
        # Add a citation
        content_with_cite = content.replace(
            "The final section",
            "See <cite>src/test.py:10</cite> for more info.\n\nThe final section",
        )
        write_text(doc_path, content_with_cite)

        verifier = QoderProfileVerifier(tmp_path)
        result = verifier.verify_profile(doc_path)
        assert result.profile_found is True
        assert result.estimated_prose_chars >= 200


class TestQualityGuardrailsChecker:
    """Tests for QualityGuardrailsChecker."""

    @pytest.fixture
    def checker(self, tmp_path: Path) -> QualityGuardrailsChecker:
        return QualityGuardrailsChecker(tmp_path)

    def test_check_nonexistent_document(self, checker: QualityGuardrailsChecker):
        result = checker.check_document(Path("nonexistent.md"))
        assert result.passed is False
        assert any("not found" in issue.message.lower() for issue in result.issues)

    def test_check_document_with_good_content(
        self, checker: QualityGuardrailsChecker, tmp_path: Path
    ):
        doc_path = tmp_path / "good.md"
        write_text(
            doc_path,
            """# Good Document

This is a well-written document with substantial prose content
that explains things in detail and provides proper context.

## Architecture

See <cite>src/architecture.py:1-10</cite> for implementation.

The system uses a three-layer architecture with clear separation
of concerns between the presentation, business logic, and data layers.

## Services

Each service is independently deployable and communicates through
well-defined API contracts as shown in <cite>src/api.py:50-60</cite>.

## Data Model

Data models are defined in <cite>src/models.py:1-20</cite> and follow
a consistent pattern for serialization.
""",
        )
        result = checker.check_document(doc_path)
        # Good content should pass or have only warnings
        assert len(result.issues) == 0 or all(i.severity != "ERROR" for i in result.issues)

    def test_detects_list_dump(self, checker: QualityGuardrailsChecker, tmp_path: Path):
        doc_path = tmp_path / "list_dump.md"
        # Create a document with 15 consecutive list items
        content = "# List Dump\n\n## Items\n\n" + "\n".join([f"- item{i}" for i in range(15)])
        write_text(doc_path, content)
        result = checker.check_document(doc_path)
        assert any(issue.reason_code == QualityReasonCode.LIST_DUMP for issue in result.issues)

    def test_detects_low_prose_ratio(self, checker: QualityGuardrailsChecker, tmp_path: Path):
        doc_path = tmp_path / "low_prose.md"
        # Create a document with mostly lists
        content = "# Overview\n\n" + "\n".join([f"- item{i}" for i in range(20)])
        write_text(doc_path, content)
        result = checker.check_document(doc_path)
        assert any(
            issue.reason_code == QualityReasonCode.LOW_PROSE_RATIO for issue in result.issues
        )

    def test_detects_low_citation_density(self, checker: QualityGuardrailsChecker, tmp_path: Path):
        doc_path = tmp_path / "low_cite.md"
        # Create long content with no citations
        content = (
            """# Long Document

"""
            + "This is some prose content. " * 100
        )
        write_text(doc_path, content)
        result = checker.check_document(doc_path)
        assert any(
            issue.reason_code == QualityReasonCode.LOW_CITATION_DENSITY for issue in result.issues
        )

    def test_detects_repeated_filler(self, checker: QualityGuardrailsChecker, tmp_path: Path):
        doc_path = tmp_path / "filler.md"
        # Create content with repeated filler words
        content = """# Test

It is important to note that this system is designed to utilize
the utilization of resources. Furthermore, it should be noted that
additionally, the system utilizes best practices.
"""
        write_text(doc_path, content)
        result = checker.check_document(doc_path)
        # Should detect repeated filler
        filler_issues = [
            i
            for i in result.issues
            if i.reason_code in (QualityReasonCode.REPEATED_FILLER, QualityReasonCode.GENERIC_PROSE)
        ]
        assert len(filler_issues) > 0

    def test_detects_unsupported_claims(self, checker: QualityGuardrailsChecker, tmp_path: Path):
        doc_path = tmp_path / "claims.md"
        # Create content with claims but no citations (need 6+ claims to trigger detection)
        content = """# Claims

The system always performs faster than alternative solutions.
It never fails under normal operating conditions.
This must be the most scalable architecture ever built.
The system implements the best practices and utilizes cutting-edge technology.
It provides the ability to handle massive workloads and enables rapid deployment.
"""
        write_text(doc_path, content)
        result = checker.check_document(doc_path)
        # Should detect unsupported claims
        claim_issues = [
            i for i in result.issues if i.reason_code == QualityReasonCode.UNSUPPORTED_CLAIM
        ]
        assert len(claim_issues) > 0

    def test_detects_hallucinated_terminology(
        self, checker: QualityGuardrailsChecker, tmp_path: Path
    ):
        doc_path = tmp_path / "hallucinated.md"
        # Create content with hallucinated patterns
        content = """# Hallucinated

This is an XML-based, REST-ful, cloud-native microservices-ready
architecture using Framework X version 1.2.3.4.
"""
        write_text(doc_path, content)
        result = checker.check_document(doc_path)
        assert any(
            issue.reason_code == QualityReasonCode.HALLUCINATED_TERMINOLOGY
            for issue in result.issues
        )

    def test_check_batch(self, checker: QualityGuardrailsChecker, tmp_path: Path):
        doc1 = tmp_path / "doc1.md"
        doc2 = tmp_path / "doc2.md"
        write_text(doc1, "# Good\n\nProse content with citations <cite>src/a.py:1</cite>.")
        write_text(doc2, "# Bad\n\n" + "\n".join([f"- item{i}" for i in range(15)]))
        results = checker.check_batch([doc1, doc2])
        assert len(results) == 2
        assert results[doc1].passed or all(i.severity != "ERROR" for i in results[doc1].issues)
        assert results[doc2].passed is False


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_quality_checker(self, tmp_path: Path):
        checker = create_quality_checker(tmp_path)
        assert checker is not None
        assert isinstance(checker, QualityGuardrailsChecker)

    def test_check_document_quality(self, tmp_path: Path):
        doc_path = tmp_path / "test.md"
        write_text(doc_path, "# Test\n\nProse content here.")
        result = check_document_quality(doc_path, tmp_path)
        assert isinstance(result, QualityGateResult)


# =============================================================================
# GOOD AND BAD SAMPLE TESTS
# =============================================================================


class TestGoodSamples:
    """Tests with good quality content samples."""

    def test_good_architecture_doc(self, tmp_path: Path):
        """Architecture doc with proper citations and prose."""
        doc_path = tmp_path / "01-architecture.md"
        write_text(
            doc_path,
            """# Architecture

See <cite>src/architecture.py:1-50</cite> for the core architecture implementation.

## System Layers

The system is organized into three distinct layers that provide
clear separation of concerns and enable independent scaling of each tier.

```mermaid
graph TD
    A[Presentation] --> B[Business Logic]
    B --> C[Data Layer]
```

## Service Collaboration

Services communicate through REST APIs defined in <cite>src/api/routes.py:10-30</cite>.
Each service maintains its own database and exposes well-defined interfaces.

## Three-Layer Architecture

1. .repo-wiki/ - Runtime storage and configuration
2. ai/source-of-truth/ - Structured facts and contracts
3. docs/ - Human-readable documentation output

## Storage Design

Data persistence uses SQLite as documented in <cite>src/db.py:1-20</cite>.
""",
        )
        checker = QualityGuardrailsChecker(tmp_path)
        result = checker.check_document(doc_path)
        # Should pass with no errors
        assert all(issue.severity != "ERROR" for issue in result.issues)

    def test_good_overview_doc(self, tmp_path: Path):
        """Overview doc with substantial prose."""
        doc_path = tmp_path / "00-overview.md"
        write_text(
            doc_path,
            """# Project Overview

See <cite>src/main.py:1-10</cite> for the entry point.

## Project Description

This is a comprehensive repository documentation system that provides
automated generation of wiki content from source code analysis.

## Core Problem

We needed a better way to document repositories that maintains accuracy
and traceability to the actual source code.

## Core Capabilities

The system provides automated scanning, indexing, and documentation generation
based on the patterns and structure discovered in the codebase.

## Environment Requirements

- Python 3.10 or higher
- SQLite 3.x for data storage
- Access to source code repository

## Startup Commands

Run `poetry install` to set up dependencies.
""",
        )
        checker = QualityGuardrailsChecker(tmp_path)
        result = checker.check_document(doc_path)
        assert all(issue.severity != "ERROR" for issue in result.issues)


class TestBadSamples:
    """Tests with bad quality content samples."""

    def test_pure_list_dump(self, tmp_path: Path):
        """Pure list without narrative."""
        doc_path = tmp_path / "bad.md"
        write_text(
            doc_path,
            """# Module List

## Items

- item1
- item2
- item3
- item4
- item5
- item6
- item7
- item8
- item9
- item10
- item11
""",
        )
        checker = QualityGuardrailsChecker(tmp_path)
        result = checker.check_document(doc_path)
        list_dump_issues = [
            i for i in result.issues if i.reason_code == QualityReasonCode.LIST_DUMP
        ]
        assert len(list_dump_issues) > 0

    def test_generic_template_prose(self, tmp_path: Path):
        """Generic AI-generated template prose."""
        doc_path = tmp_path / "generic.md"
        write_text(
            doc_path,
            """# System Documentation

It should be noted that this system is designed to utilize the latest
technologies. Furthermore, it is important to note that the system
provides the ability to handle various workloads. Additionally,
the system serves as a comprehensive solution.

## Features

- Feature A
- Feature B
- Feature C
""",
        )
        checker = QualityGuardrailsChecker(tmp_path)
        result = checker.check_document(doc_path)
        assert len(result.issues) > 0

    def test_claim_without_citation(self, tmp_path: Path):
        """Technical claims without citation backing."""
        doc_path = tmp_path / "claims.md"
        # Need 6+ claims to trigger unsupported claim detection
        write_text(
            doc_path,
            """# Performance Claims

This system always outperforms all alternatives. It never has downtime.
The architecture must be the most scalable solution available.
The system provides the ability to handle massive scale and utilizes best practices.
It implements cutting-edge technology that ensures optimal performance.
""",
        )
        checker = QualityGuardrailsChecker(tmp_path)
        result = checker.check_document(doc_path)
        unsupported_issues = [
            i for i in result.issues if i.reason_code == QualityReasonCode.UNSUPPORTED_CLAIM
        ]
        assert len(unsupported_issues) > 0


# =============================================================================
# INTEGRATION WITH QODER PROFILE
# =============================================================================


class TestQoderProfileIntegration:
    """Tests for qoder profile verification integration."""

    def test_qoder_profile_verifier_interface(self, tmp_path: Path):
        """Test that QoderProfileVerifier provides expected interface."""
        verifier = QoderProfileVerifier(tmp_path)
        assert hasattr(verifier, "verify_profile")
        assert hasattr(verifier, "EXPECTED_SECTIONS")

    def test_profile_metrics_structure(self):
        """Test QoderProfileMetrics has expected structure."""
        metrics = QoderProfileMetrics(
            profile_found=True,
            profile_complete=True,
            sections_documented=5,
            sections_total=9,
            citations_count=3,
            estimated_prose_chars=500,
        )
        assert metrics.profile_found is True
        assert metrics.profile_complete is True
        assert metrics.sections_documented == 5

    def test_full_pipeline_with_qoder_profile(self, tmp_path: Path):
        """Test full quality check pipeline with qoder profile verification."""
        # Create a complete qoder-style document
        doc_path = tmp_path / "docs/sections/architecture/index.md"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        write_text(
            doc_path,
            """# Architecture

See <cite>src/arch.py:1-30</cite> for implementation.

## System Design

The architecture follows a microservices pattern with clear boundaries.

## Three Layers

1. Layer 1
2. Layer 2
3. Layer 3
""",
        )
        # Run qoder profile verification
        verifier = QoderProfileVerifier(tmp_path)
        metrics = verifier.verify_profile(doc_path)
        assert metrics.profile_found is True

        # Run full quality check
        checker = QualityGuardrailsChecker(tmp_path)
        result = checker.check_document(doc_path)
        assert isinstance(result, QualityGateResult)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
