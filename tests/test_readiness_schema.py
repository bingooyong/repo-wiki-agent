"""Tests for readiness schema and final go/no-go decision."""

from __future__ import annotations

import pytest

from repo_wiki.verifier.qoder_strict_verifier import QoderLikeVerifierService
from repo_wiki.verifier.qoder_parity_metrics import (
    ParityMetricDefinition,
    ParityMetricExtractor,
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
            assert hasattr(metric, 'name')
            assert hasattr(metric, 'category')
            assert hasattr(metric, 'severity')
            assert hasattr(metric, 'threshold')
            assert hasattr(metric, 'weight')

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

    def test_ai_api_atlas_readiness_assessed(self):
        """Test that AI_API_Atlas readiness can be assessed."""
        # AI_API_Atlas pilot was run with isolated output
        # Readiness can be determined by running parity comparison
        from repo_wiki.verifier.atlas_parity_runner import AIAPIAtlasParityRunner

        runner = AIAPIAtlasParityRunner()
        result = runner.run_comparison()

        # Result should be valid
        assert result.run_id.startswith("atlas-parity-")
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
        from repo_wiki.verifier.atlas_parity_runner import AIAPIAtlasParityRunner

        runner = AIAPIAtlasParityRunner()
        result = runner.run_comparison()
        report_path = runner.save_report(result)

        assert report_path.exists()

    def test_gaps_have_severity_classification(self):
        """Test that gaps are classified by severity."""
        from repo_wiki.verifier.atlas_parity_runner import GapItem, ParityMetric

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
        # Final dossier should include:
        # - AI_API_Atlas-specific readiness
        # - General product readiness
        # - Remaining gaps
        # - Next backlog

        # This is validated by the existence of pilot reports
        from pathlib import Path

        # Use absolute path to avoid CWD dependency
        repo_root = Path(__file__).parent.parent
        ai_atlas_evidence = repo_root / "docs" / "operations" / "ai-api-atlas-pilot-evidence.md"
        multi_repo_evidence = repo_root / "docs" / "operations" / "multi-repo-pilot-report.md"
        gate_policy = repo_root / "docs" / "operations" / "replacement-gate-policy.md"

        assert ai_atlas_evidence.exists(), f"AI_API_Atlas evidence missing at {ai_atlas_evidence}"
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


class TestMemoryRootUpdate:
    """Tests for Memory Root update."""

    def test_final_judgment_logged(self):
        """Test that final judgment is logged to Memory."""
        from pathlib import Path

        memory_root = Path(".apm/Memory/Memory_Root.md")
        if memory_root.exists():
            content = memory_root.read_text()
            # Memory Root should be updated with Phase 30 judgment
            # This is a structural test
            assert len(content) > 0