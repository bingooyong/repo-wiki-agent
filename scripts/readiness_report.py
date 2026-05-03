#!/usr/bin/env python3
"""
Unified Readiness Report Generator

Combines verify --ci results, baseline comparison, and acceptance criteria
into a single evidence package for governance reviews.

Phase 11: Task 11.3 - Unified readiness report schema and evidence bundle

Usage:
    python scripts/readiness_report.py \
        --target /path/to/target \
        --output /path/to/report.json \
        --format json|markdown|both

Output Schema:
    - report_metadata: Version, generated timestamp, tool versions
    - acceptance_evidence: Bundled verify and baseline results
    - acceptance_criteria: Required evidence fields and validation status
    - human_readable_summary: Executive summary for stakeholders
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Schema version for future compatibility
SCHEMA_VERSION = "1.0.0"


@dataclass
class AcceptanceEvidence:
    """Bundled evidence from verify and baseline comparison."""

    verify_result: dict[str, Any]
    baseline_result: dict[str, Any]


@dataclass
class EvidenceField:
    """A required evidence field with validation status."""

    name: str
    description: str
    present: bool
    validated: bool = False
    details: str = ""


@dataclass
class ReadinessCriteria:
    """Acceptance criteria with validation status."""

    field_name: str
    description: str
    met: bool
    evidence_ref: str = ""


@dataclass
class ReadinessReport:
    """Unified readiness report schema."""

    schema_version: str
    generated_at: str
    target_path: str
    acceptance_evidence: AcceptanceEvidence
    acceptance_criteria: list[ReadinessCriteria]
    human_readable_summary: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "target_path": self.target_path,
            "acceptance_evidence": asdict(self.acceptance_evidence),
            "acceptance_criteria": [asdict(c) for c in self.acceptance_criteria],
            "human_readable_summary": self.human_readable_summary,
            "metadata": self.metadata,
        }

    def to_markdown(self) -> str:
        """Generate human-readable markdown summary."""
        lines = [
            "# Readiness Report",
            "",
            f"**Target:** `{self.target_path}`",
            f"**Generated:** {self.generated_at}",
            f"**Schema Version:** {self.schema_version}",
            "",
            "---",
            "",
            "## Acceptance Summary",
            "",
        ]

        # Overall status
        overall_status = "READY" if self.is_accepted() else "NOT READY"
        status_icon = "✓" if self.is_accepted() else "✗"
        lines.append(f"{status_icon} **Overall Status:** {overall_status}")
        lines.append("")

        # Summary metrics
        summary = self.human_readable_summary
        if "overall_score" in summary:
            lines.append(f"- **Overall Score:** {summary['overall_score']:.1%}")
        if "grade" in summary:
            lines.append(f"- **Verify Grade:** {summary['grade']}")
        if "exit_code" in summary:
            lines.append(f"- **Exit Code:** {summary['exit_code']}")
        if "acceptance_blocked" in summary:
            blocked = "YES" if summary["acceptance_blocked"] else "NO"
            lines.append(f"- **Acceptance Blocked:** {blocked}")
        lines.append("")

        # Gate summary
        if "gate_summary" in summary:
            gate = summary["gate_summary"]
            lines.append("### Gate Status")
            lines.append(
                f"- Hard Gate Blocking: {'YES' if gate.get('hard_gate_blocking') else 'NO'}"
            )
            lines.append(
                f"- Soft Gate Warnings: {'YES' if gate.get('soft_gate_warnings') else 'NO'}"
            )
            lines.append("")

        # Criteria status
        lines.append("### Acceptance Criteria")
        for criteria in self.acceptance_criteria:
            icon = "✓" if criteria.met else "✗"
            lines.append(f"- [{icon}] {criteria.field_name}: {criteria.description}")
        lines.append("")

        # Detailed evidence references
        lines.append("---")
        lines.append("")
        lines.append("## Evidence Details")
        lines.append("")
        lines.append("### Verify Results")
        verify = self.acceptance_evidence.verify_result
        lines.append(f"- Grade: **{verify.get('grade', 'N/A')}**")
        if "summary" in verify:
            s = verify["summary"]
            lines.append(
                f"- Checks: {s.get('pass', 0)} passed, {s.get('fail', 0)} failed, {s.get('warn', 0)} warnings"
            )
        lines.append("")

        lines.append("### Baseline Comparison")
        baseline = self.acceptance_evidence.baseline_result
        if "summary" in baseline:
            s = baseline["summary"]
            lines.append(f"- Overall Score: **{s.get('overall_score', 0):.1%}**")
            lines.append(f"- Score Band: {s.get('overall_band', 'N/A')}")
            lines.append(f"- Structural Score: {s.get('structural_score', 0):.1%}")
            lines.append(f"- Quality Score: {s.get('quality_score', 0):.1%}")
            lines.append("")

        # Dimension breakdown
        if "dimensions" in baseline:
            lines.append("### Dimension Details")
            for dim in baseline["dimensions"]:
                status_icon = {"PASS": "✓", "FAIL": "✗", "PARTIAL": "◐"}.get(
                    dim.get("status", ""), "?"
                )
                lines.append(
                    f"- {status_icon} {dim.get('dimension')}: {dim.get('score', 0):.1%} ({dim.get('score_band', 'N/A')}) [{dim.get('delta_type', 'N/A')}]"
                )
            lines.append("")

        # Required evidence fields
        lines.append("---")
        lines.append("")
        lines.append("## Required Evidence Checklist")
        for criteria in self.acceptance_criteria:
            icon = "✓" if criteria.met else "✗"
            lines.append(f"- [{icon}] **{criteria.field_name}**: {criteria.description}")

        return "\n".join(lines)

    def is_accepted(self) -> bool:
        """Check if all acceptance criteria are met."""
        return all(c.met for c in self.acceptance_criteria)

    def validate_required_evidence(self) -> list[str]:
        """Validate that all required evidence is present. Returns list of missing evidence."""
        missing = []
        for criteria in self.acceptance_criteria:
            if not criteria.met:
                missing.append(criteria.field_name)
        return missing


def generate_readiness_report(
    target_path: Path,
    verify_result: dict[str, Any],
    baseline_result: dict[str, Any],
) -> ReadinessReport:
    """Generate a unified readiness report from verify and baseline results."""

    # Build acceptance criteria based on verify and baseline results
    criteria = []

    # Verify grade criterion
    verify_grade = verify_result.get("grade", "FAIL")
    criteria.append(
        ReadinessCriteria(
            field_name="verify-grade",
            description=f"Verify grade is PASS (got: {verify_grade})",
            met=verify_grade == "PASS",
            evidence_ref="acceptance_evidence.verify_result.grade",
        )
    )

    # No hard gate failures
    hard_failures = verify_result.get("summary", {}).get("hard_gate_failures", 0)
    criteria.append(
        ReadinessCriteria(
            field_name="no-hard-gate-failures",
            description=f"No hard gate failures (got: {hard_failures})",
            met=hard_failures == 0,
            evidence_ref="acceptance_evidence.verify_result.summary.hard_gate_failures",
        )
    )

    # Acceptance not blocked
    acceptance_blocked = baseline_result.get("summary", {}).get("acceptance_blocked", True)
    criteria.append(
        ReadinessCriteria(
            field_name="baseline-acceptance",
            description=f"Baseline acceptance not blocked (blocked: {acceptance_blocked})",
            met=not acceptance_blocked,
            evidence_ref="acceptance_evidence.baseline_result.summary.acceptance_blocked",
        )
    )

    # Overall score above threshold
    overall_score = baseline_result.get("summary", {}).get("overall_score", 0)
    criteria.append(
        ReadinessCriteria(
            field_name="baseline-score",
            description=f"Overall baseline score >= 0.5 (got: {overall_score:.2f})",
            met=overall_score >= 0.5,
            evidence_ref="acceptance_evidence.baseline_result.summary.overall_score",
        )
    )

    # Generate human-readable summary
    summary = {
        "grade": verify_grade,
        "exit_code": verify_result.get("exit_code", 0),
        "overall_score": overall_score,
        "overall_band": baseline_result.get("summary", {}).get("overall_band", "N/A"),
        "acceptance_blocked": acceptance_blocked,
        "gate_summary": verify_result.get("gate_summary", {}),
        "verify_summary": verify_result.get("summary", {}),
        "baseline_summary": baseline_result.get("summary", {}),
    }

    report = ReadinessReport(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        target_path=str(target_path),
        acceptance_evidence=AcceptanceEvidence(
            verify_result=verify_result,
            baseline_result=baseline_result,
        ),
        acceptance_criteria=criteria,
        human_readable_summary=summary,
        metadata={
            "schema_version": SCHEMA_VERSION,
            "generator": "readiness_report.py",
        },
    )

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified readiness report generator")
    parser.add_argument("--target", type=Path, required=True, help="Path to target repository")
    parser.add_argument(
        "--verify", type=Path, help="Path to verify JSON output (if not using default)"
    )
    parser.add_argument("--baseline", type=Path, help="Path to baseline comparison JSON output")
    parser.add_argument(
        "--baseline-target",
        type=Path,
        help="Baseline comparison target (default: same as --target)",
    )
    parser.add_argument("--baseline-baseline", type=Path, help="Baseline comparison baseline")
    parser.add_argument("--output", type=Path, required=True, help="Output path for report")
    parser.add_argument(
        "--format", choices=["json", "markdown", "both"], default="both", help="Output format"
    )

    args = parser.parse_args()

    if not args.target.exists():
        print(f"Error: Target path does not exist: {args.target}", file=sys.stderr)
        return 1

    # Get verify result
    if args.verify:
        verify_result = json.loads(args.verify.read_text())
    else:
        # Run verify inline
        from repo_wiki.verifier.service import VerifierService

        verifier = VerifierService(args.target)
        verify_result = verifier.verify(ci=True)

    # Get baseline result
    if args.baseline:
        baseline_result = json.loads(args.baseline.read_text())
    elif args.baseline_target and args.baseline_baseline:
        # Run baseline comparison
        from scripts.qoder_baseline_comparison import QoderBaselineComparator

        comparator = QoderBaselineComparator(args.baseline_target, args.baseline_baseline)
        baseline_result = comparator.compare_all().to_dict()
    else:
        # Use target as baseline (self-comparison for minimal report)
        from scripts.qoder_baseline_comparison import QoderBaselineComparator

        comparator = QoderBaselineComparator(args.target, args.target)
        baseline_result = comparator.compare_all().to_dict()

    # Generate unified report
    report = generate_readiness_report(args.target, verify_result, baseline_result)

    # Output
    if args.format in ("json", "both"):
        json_output = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
        json_path = args.output.with_suffix(".json")
        json_path.write_text(json_output)
        print(f"JSON report written to: {json_path}")

    if args.format in ("markdown", "both"):
        md_output = report.to_markdown()
        md_path = args.output.with_suffix(".md")
        md_path.write_text(md_output)
        print(f"Markdown report written to: {md_path}")

    # Validation
    missing = report.validate_required_evidence()
    if missing:
        print(f"\nWarning: Missing required evidence: {', '.join(missing)}")
        return 1

    # Exit code based on acceptance
    return 0 if report.is_accepted() else 1


if __name__ == "__main__":
    sys.exit(main())
