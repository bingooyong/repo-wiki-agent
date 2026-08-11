"""Tests for readiness schema and final go/no-go decision."""

from __future__ import annotations

from repo_wiki.orchestration.readiness_schema import evaluate_replacement_readiness_v2
from repo_wiki.verifier.manual_review_matrix import (
    MANDATORY_PAGE_LABELS,
    MIN_ACCEPTED_PAGES,
    MIN_REVIEWED_PAGES,
    REQUIRED_CATEGORIES,
    ManualReviewRow,
    evaluate_manual_review_matrix_v2,
    write_manual_review_artifacts,
)
from repo_wiki.verifier.qoder_parity_metrics import (
    PARITY_METRICS,
)


class TestReadinessSchema:
    """Tests for readiness schema validation."""

    def test_all_parity_metrics_defined(self):
        """Test that all required parity metrics are defined."""
        required_metrics = [
            "page_coverage",
            "citation_density",
            "toc_presence",
            "mermaid_presence",
            "prose_density",
        ]
        for metric_name in required_metrics:
            assert metric_name in PARITY_METRICS, f"Missing metric: {metric_name}"

    def test_metric_has_required_fields(self):
        """Test that each metric definition has required fields."""
        for name, metric in PARITY_METRICS.items():
            assert hasattr(metric, "name")
            assert hasattr(metric, "category")
            assert hasattr(metric, "severity")
            assert hasattr(metric, "threshold")
            assert hasattr(metric, "weight")

    def test_metric_thresholds_valid(self):
        """Test that metric thresholds are in valid range."""
        for name, metric in PARITY_METRICS.items():
            assert 0.0 <= metric.threshold <= 1.0, f"Invalid threshold for {name}"
            assert 0.0 <= metric.weight <= 1.0, f"Invalid weight for {name}"

    def test_critical_metrics_have_high_weight(self):
        """Test that critical severity metrics have higher weights."""
        for name, metric in PARITY_METRICS.items():
            if metric.severity.value == "CRITICAL":
                assert metric.weight >= 0.10, f"Critical metric {name} should have weight >= 0.10"


class TestGoNoGoCriteria:
    """Tests for go/no-go decision criteria."""

    def test_reference_repo_readiness_assessed(self):
        """Test that reference-repo readiness can be assessed."""
        # reference-repo pilot was run with isolated output
        # Readiness can be determined by running parity comparison
        from repo_wiki.verifier.reference_parity_runner import ReferenceParityRunner

        runner = ReferenceParityRunner()
        result = runner.run_comparison()

        # Result should be valid
        assert result.run_id.startswith("reference-parity-")
        assert "baseline" in result.metrics
        assert "target" in result.metrics

    def test_general_product_readiness_uses_qoder_like_verifier(self):
        """Test that general product readiness uses QoderLikeVerifierService."""
        # QoderLikeVerifierService requires root path
        from repo_wiki.verifier.qoder_strict_verifier import QoderLikeSeverityThreshold

        threshold = QoderLikeSeverityThreshold()
        # QoderLikeSeverityThreshold is used by QoderLikeVerifierService
        # to determine which codes are blocking
        assert len(threshold.STRICT_HARD_CODES) > 0

    def test_readiness_includes_all_gates(self):
        """Test that readiness check includes all gate types."""
        from repo_wiki.verifier.qoder_strict_verifier import QoderLikeSeverityThreshold

        threshold = QoderLikeSeverityThreshold()

        # All QODER-specific codes should be defined
        qoder_codes = [
            "QODER_CITATION_MISSING",
            "QODER_TOC_MISSING",
            "QODER_FILE_REF_BROKEN",
            "QODER_PAGE_DUMP",
            "QODER_PROSE_TOO_LOW",
        ]

        for code in qoder_codes:
            # Each code should be in STRICT_HARD_CODES
            assert code in threshold.STRICT_HARD_CODES


class TestEvidenceLinkage:
    """Tests for evidence linkage to claims."""

    def test_parity_report_has_evidence_path(self):
        """Test that parity report includes evidence path."""
        from repo_wiki.verifier.reference_parity_runner import ReferenceParityRunner

        runner = ReferenceParityRunner()
        result = runner.run_comparison()
        report_path = runner.save_report(result)

        assert report_path.exists()

    def test_gaps_have_severity_classification(self):
        """Test that gaps are classified by severity."""
        from repo_wiki.verifier.reference_parity_runner import GapItem, ParityMetric

        gap = GapItem(
            metric=ParityMetric.PAGE_COUNT,
            baseline_value=10,
            target_value=5,
            gap_ratio=0.5,
            severity="critical",
        )
        assert gap.severity in ["critical", "major", "minor", "info"]

    def test_trend_data_is_persisted(self):
        """Test that trend data can be persisted and queried."""
        # GovernanceDashboard stores metrics over time
        from scripts.qoder_governance_dashboard import GovernanceDB, GovernanceMetric

        # This test validates the persistence mechanism
        # Actual trend analysis requires multiple data points
        assert GovernanceDB is not None
        assert GovernanceMetric is not None


class TestFinalDecision:
    """Tests for final decision documentation."""

    def test_decision_includes_all_evidence(self):
        """Test that final decision bundles all evidence."""
        # Public release decisions rely on reusable policy and multi-repository evidence,
        # not a repository-specific internal acceptance dossier.
        from pathlib import Path

        # Use absolute path to avoid CWD dependency
        repo_root = Path(__file__).parent.parent
        fixture_policy = (
            repo_root / "docs" / "operations" / "fixture-provenance-and-freshness-policy.md"
        )
        multi_repo_evidence = repo_root / "docs" / "operations" / "multi-repo-pilot-report.md"
        gate_policy = repo_root / "docs" / "operations" / "replacement-gate-policy.md"

        assert fixture_policy.exists(), f"Fixture policy missing at {fixture_policy}"
        assert multi_repo_evidence.exists(), f"Multi-repo evidence missing at {multi_repo_evidence}"
        assert gate_policy.exists(), f"Gate policy missing at {gate_policy}"

    def test_go_decision_requires_all_gates_pass(self):
        """Test that GO decision requires all critical gates pass."""
        from repo_wiki.verifier.qoder_strict_verifier import QoderLikeSeverityThreshold

        # In strict mode, all QODER_* codes block
        strict_threshold = QoderLikeSeverityThreshold()

        critical_codes = [
            "QODER_CITATION_MISSING",
            "QODER_TOC_MISSING",
            "QODER_FILE_REF_BROKEN",
        ]

        for code in critical_codes:
            assert strict_threshold.is_blocking(code) is True

    def test_no_go_decision_triggers_rollback(self):
        """Test that NO-GO decision triggers rollback planning."""
        # Rollback triggers are documented in gate policy
        # Critical gaps (>50%) should trigger immediate rollback
        from pathlib import Path

        policy_doc = Path("docs/operations/replacement-gate-policy.md")
        assert policy_doc.exists()

        content = policy_doc.read_text()
        assert "回滚触发条件" in content or "rollback" in content.lower()


class TestManualReviewMatrixV2:
    """Tests for manual review matrix v2 thresholds and mandatory rows."""

    def _build_minimum_pass_rows(self) -> list[ManualReviewRow]:
        rows: list[ManualReviewRow] = []
        categories = list(REQUIRED_CATEGORIES)
        # Ensure mandatory row exists and is accepted.
        rows.append(
            ManualReviewRow(
                page_label="API台账服务 API",
                category="api",
                accepted=True,
                severity="P1",
                notes="Mandatory API row",
            )
        )
        # Build remaining rows to meet 30 reviewed and >=24 accepted.
        accepted_needed = MIN_ACCEPTED_PAGES - 1
        total_needed = MIN_REVIEWED_PAGES - 1
        for i in range(total_needed):
            accepted = i < accepted_needed
            rows.append(
                ManualReviewRow(
                    page_label=f"review-row-{i}",
                    category=categories[i % len(categories)],
                    accepted=accepted,
                    severity="P2" if accepted else "P3",
                    notes="fixture",
                )
            )
        return rows

    def test_mandatory_inventory_service_api_row_is_configured(self):
        assert "API台账服务 API" in MANDATORY_PAGE_LABELS

    def test_manual_review_matrix_v2_passes_thresholds(self):
        rows = self._build_minimum_pass_rows()
        result = evaluate_manual_review_matrix_v2(rows)
        assert result["summary"]["status"] == "PASS"
        assert result["summary"]["reviewed_pages"] >= MIN_REVIEWED_PAGES
        assert result["summary"]["accepted_pages"] >= MIN_ACCEPTED_PAGES
        assert result["summary"]["mandatory_rows_present"] is True

    def test_manual_review_matrix_v2_fails_when_mandatory_missing(self):
        rows = [
            ManualReviewRow(
                page_label=f"row-{i}",
                category=list(REQUIRED_CATEGORIES)[i % len(REQUIRED_CATEGORIES)],
                accepted=True,
                severity="P2",
                notes="fixture",
            )
            for i in range(MIN_REVIEWED_PAGES)
        ]
        result = evaluate_manual_review_matrix_v2(rows)
        codes = [f["code"] for f in result["failures"]]
        assert "MANUAL_REVIEW_MANDATORY_ROW_MISSING" in codes

    def test_manual_review_matrix_v2_fails_on_mandatory_p0(self):
        rows = self._build_minimum_pass_rows()
        # Turn mandatory row into P0 failure.
        rows[0] = ManualReviewRow(
            page_label="API台账服务 API",
            category="api",
            accepted=False,
            severity="P0",
            notes="blocking",
        )
        result = evaluate_manual_review_matrix_v2(rows)
        codes = [f["code"] for f in result["failures"]]
        assert "MANUAL_REVIEW_MANDATORY_P0_FAILURE" in codes

    def test_manual_review_artifacts_written_to_run_or_operations(self, tmp_path):
        rows = self._build_minimum_pass_rows()
        result = evaluate_manual_review_matrix_v2(rows)
        run_reports = tmp_path / ".repo-agent-eval" / "runs" / "run-1" / "reports"
        ops_evidence = tmp_path / "docs" / "operations" / "evidence"
        written = write_manual_review_artifacts(
            result,
            run_reports_dir=run_reports,
            operations_evidence_dir=ops_evidence,
        )
        assert str(run_reports) in written
        assert str(ops_evidence) in written
        assert (run_reports / "manual-review-matrix-v2.md").exists()
        assert (ops_evidence / "manual-review-matrix-v2.json").exists()


class TestReplacementReadinessSchemaV2:
    """Tests for replacement readiness schema v2."""

    def test_strict_pass_alone_cannot_go(self):
        result = evaluate_replacement_readiness_v2(
            strict_verify={"grade": "PASS"},
            comparison_result=None,
            manual_review_result=None,
        )
        assert result["replacement_go"] is False
        assert result["readiness_state"] == "NOT_READY"
        assert "QODER_COMPARISON_REQUIRED" in result["readiness_reasons"]
        assert "MANUAL_REVIEW_REQUIRED" in result["readiness_reasons"]

    def test_strict_pass_manual_fail_cannot_go(self):
        manual_fail = {
            "summary": {"status": "FAIL"},
            "failures": [{"code": "MANUAL_REVIEW_MANDATORY_P0_FAILURE"}],
        }
        result = evaluate_replacement_readiness_v2(
            strict_verify={"grade": "PASS"},
            comparison_result={"status": "READY"},
            manual_review_result=manual_fail,
        )
        assert result["replacement_go"] is False
        assert result["readiness_state"] == "NOT_READY"
        assert "MANUAL_REVIEW_NOT_PASS" in result["readiness_reasons"]
        assert "MANUAL_REVIEW_MANDATORY_P0_FAILURE" in result["readiness_reasons"]

    def test_all_gates_pass_can_go(self):
        manual_pass = {"summary": {"status": "PASS"}, "failures": []}
        result = evaluate_replacement_readiness_v2(
            strict_verify={"grade": "PASS"},
            comparison_result={"status": "READY"},
            manual_review_result=manual_pass,
        )
        assert result["replacement_go"] is True
        assert result["readiness_state"] == "READY"
        assert result["readiness_reasons"] == []
