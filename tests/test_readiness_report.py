"""Tests for unified readiness report schema and evidence bundle."""

from __future__ import annotations

from pathlib import Path

from scripts.readiness_report import (
    SCHEMA_VERSION,
    generate_readiness_report,
)


class TestReadinessReportSchema:
    """Test readiness report schema."""

    def test_schema_version_present(self) -> None:
        """Test that schema version is set correctly."""
        verify_result = {"grade": "PASS", "summary": {"hard_gate_failures": 0}}
        baseline_result = {
            "summary": {
                "overall_score": 0.9,
                "overall_band": "EXCELLENT",
                "acceptance_blocked": False,
            }
        }

        report = generate_readiness_report(
            Path("/tmp"),
            verify_result,
            baseline_result,
        )

        assert report.schema_version == SCHEMA_VERSION
        assert report.generated_at is not None

    def test_acceptance_criteria_all_met(self) -> None:
        """Test report when all acceptance criteria are met."""
        verify_result = {
            "grade": "PASS",
            "exit_code": 0,
            "summary": {"hard_gate_failures": 0, "soft_gate_failures": 0},
            "gate_summary": {"hard_gate_blocking": False, "soft_gate_warnings": False},
        }
        baseline_result = {
            "summary": {
                "overall_score": 0.9,
                "overall_band": "EXCELLENT",
                "acceptance_blocked": False,
            }
        }

        report = generate_readiness_report(
            Path("/tmp"),
            verify_result,
            baseline_result,
        )

        assert report.is_accepted() is True
        assert all(c.met for c in report.acceptance_criteria)

    def test_acceptance_criteria_not_met(self) -> None:
        """Test report when acceptance criteria are not met."""
        verify_result = {
            "grade": "FAIL",
            "exit_code": 1,
            "summary": {"hard_gate_failures": 1},
            "gate_summary": {"hard_gate_blocking": True},
        }
        baseline_result = {
            "summary": {
                "overall_score": 0.3,
                "overall_band": "POOR",
                "acceptance_blocked": True,
            }
        }

        report = generate_readiness_report(
            Path("/tmp"),
            verify_result,
            baseline_result,
        )

        assert report.is_accepted() is False
        assert any(not c.met for c in report.acceptance_criteria)

    def test_validate_required_evidence(self) -> None:
        """Test validation of required evidence."""
        verify_result = {"grade": "FAIL", "summary": {"hard_gate_failures": 1}}
        baseline_result = {
            "summary": {
                "overall_score": 0.3,
                "acceptance_blocked": True,
            }
        }

        report = generate_readiness_report(
            Path("/tmp"),
            verify_result,
            baseline_result,
        )

        missing = report.validate_required_evidence()
        assert len(missing) > 0
        assert "verify-grade" in missing


class TestReadinessReportOutput:
    """Test report output formats."""

    def test_to_dict(self) -> None:
        """Test dictionary output."""
        verify_result = {"grade": "PASS", "summary": {"hard_gate_failures": 0}}
        baseline_result = {
            "summary": {
                "overall_score": 0.9,
                "acceptance_blocked": False,
            }
        }

        report = generate_readiness_report(
            Path("/tmp/test"),
            verify_result,
            baseline_result,
        )

        result = report.to_dict()

        assert result["schema_version"] == SCHEMA_VERSION
        assert result["target_path"] == "/tmp/test"
        assert "acceptance_evidence" in result
        assert "acceptance_criteria" in result
        assert "human_readable_summary" in result

    def test_to_markdown(self) -> None:
        """Test markdown output."""
        verify_result = {
            "grade": "PASS",
            "exit_code": 0,
            "summary": {"pass": 10, "fail": 0, "warn": 2, "hard_gate_failures": 0},
            "gate_summary": {"hard_gate_blocking": False, "soft_gate_warnings": True},
        }
        baseline_result = {
            "summary": {
                "overall_score": 0.85,
                "overall_band": "GOOD",
                "structural_score": 0.9,
                "quality_score": 0.8,
                "acceptance_blocked": False,
            },
            "dimensions": [
                {
                    "dimension": "directory_hierarchy",
                    "status": "PASS",
                    "score": 1.0,
                    "score_band": "EXCELLENT",
                    "delta_type": "STRUCTURAL",
                },
                {
                    "dimension": "section_coverage",
                    "status": "PASS",
                    "score": 0.9,
                    "score_band": "GOOD",
                    "delta_type": "STRUCTURAL",
                },
                {
                    "dimension": "heading_coverage",
                    "status": "PASS",
                    "score": 0.8,
                    "score_band": "GOOD",
                    "delta_type": "QUALITY",
                },
            ],
        }

        report = generate_readiness_report(
            Path("/tmp/test"),
            verify_result,
            baseline_result,
        )

        md = report.to_markdown()

        assert "# Readiness Report" in md
        assert "/tmp/test" in md
        assert "READY" in md
        assert "EXCELLENT" in md or "GOOD" in md
        assert "Verify Results" in md
        assert "Baseline Comparison" in md


class TestAcceptanceEvidenceBundle:
    """Test evidence bundling."""

    def test_verify_and_baseline_bundled(self) -> None:
        """Test that verify and baseline results are bundled."""
        verify_result = {"grade": "PASS"}
        baseline_result = {"summary": {"overall_score": 0.9}}

        report = generate_readiness_report(
            Path("/tmp"),
            verify_result,
            baseline_result,
        )

        assert report.acceptance_evidence.verify_result == verify_result
        assert report.acceptance_evidence.baseline_result == baseline_result

    def test_criteria_references_evidence(self) -> None:
        """Test that criteria reference their evidence sources."""
        verify_result = {"grade": "PASS", "summary": {"hard_gate_failures": 0}}
        baseline_result = {
            "summary": {
                "overall_score": 0.9,
                "acceptance_blocked": False,
            }
        }

        report = generate_readiness_report(
            Path("/tmp"),
            verify_result,
            baseline_result,
        )

        for criteria in report.acceptance_criteria:
            assert criteria.evidence_ref.startswith("acceptance_evidence.")
