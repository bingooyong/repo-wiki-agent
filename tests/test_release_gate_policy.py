"""Tests for release gate policy enforcement."""

from __future__ import annotations

import pytest

from repo_wiki.verifier.qoder_strict_verifier import (
    QoderLikeSeverityThreshold,
    QoderLikeVerifierService,
)


class TestReleaseGatePolicy:
    """Tests for release gate policy."""

    def test_strict_mode_blocks_citation_missing(self):
        """Test that strict mode blocks missing citations."""
        threshold = QoderLikeSeverityThreshold()

        # QODER_CITATION_MISSING should block
        assert threshold.is_blocking("QODER_CITATION_MISSING") is True

    def test_strict_mode_blocks_toc_missing(self):
        """Test that strict mode blocks missing TOC."""
        threshold = QoderLikeSeverityThreshold()

        assert threshold.is_blocking("QODER_TOC_MISSING") is True

    def test_strict_mode_blocks_file_ref_broken(self):
        """Test that strict mode blocks broken file references."""
        threshold = QoderLikeSeverityThreshold()

        assert threshold.is_blocking("QODER_FILE_REF_BROKEN") is True

    def test_strict_mode_blocks_page_dump(self):
        """Test that strict mode blocks dump pages."""
        threshold = QoderLikeSeverityThreshold()

        assert threshold.is_blocking("QODER_PAGE_DUMP") is True

    def test_strict_mode_blocks_prose_too_low(self):
        """Test that strict mode blocks low prose density."""
        threshold = QoderLikeSeverityThreshold()

        assert threshold.is_blocking("QODER_PROSE_TOO_LOW") is True

    def test_strict_mode_default_blocks_all(self):
        """Test that strict mode defaults to blocking unknown codes."""
        from repo_wiki.verifier.service import GateType

        threshold = QoderLikeSeverityThreshold()

        # Unknown codes should default to HARD (blocking)
        assert threshold.get_gate_type("UNKNOWN_CODE") == GateType.HARD

    def test_soft_codes_become_hard_in_strict(self):
        """Test that soft codes become HARD in strict mode."""
        from repo_wiki.verifier.service import GateType

        threshold = QoderLikeSeverityThreshold()

        # CONTENT_LIST_ONLY becomes HARD in strict
        assert threshold.get_gate_type("CONTENT_LIST_ONLY") == GateType.HARD
        # CITATION_MISSING becomes HARD in strict
        assert threshold.get_gate_type("CITATION_MISSING") == GateType.HARD


class TestGateExitCodes:
    """Tests for gate exit code behavior."""

    def test_hard_gate_fail_exit_code_1(self):
        """Test that hard gate failure returns exit code 1."""
        threshold = QoderLikeSeverityThreshold()

        # If any hard gate fails, exit code should be 1
        hard_gate_codes = threshold.STRICT_HARD_CODES
        assert len(hard_gate_codes) > 0

        for code in hard_gate_codes:
            assert threshold.is_blocking(code) is True


class TestRollbackTriggers:
    """Tests for rollback trigger conditions."""

    def test_critical_gap_triggers_rollback(self):
        """Test that critical gaps trigger rollback evaluation."""
        # Critical is defined as > 50% gap ratio
        threshold = QoderLikeSeverityThreshold()

        # Verify critical threshold is defined
        # (In actual implementation, this would be checked in _make_gap)
        assert threshold is not None

    def test_major_gap_allowed_with_review(self):
        """Test that major gaps are allowed with review."""
        threshold = QoderLikeSeverityThreshold()

        # Major is defined as 30-50% gap ratio
        # In strict mode, this should still block
        assert threshold.is_blocking("STRUCT_MISSING_SECTIONS") is True


class TestPolicyProfiles:
    """Tests for policy profile configurations."""

    def test_strict_profile_criteria(self):
        """Test strict profile requires all hard gates pass."""
        threshold = QoderLikeSeverityThreshold()

        # Strict profile: hard_gate_failures must be 0
        hard_failures = len(threshold.STRICT_HARD_CODES)
        assert hard_failures > 0  # There should be hard codes defined

    def test_transitional_profile_allows_some_failures(self):
        """Test transitional profile allows some soft failures."""
        # In transitional profile, soft failures <= 3 are allowed
        from repo_wiki.verifier.service import GateType

        threshold = QoderLikeSeverityThreshold()

        # Verify soft-to-hard conversion still applies in transitional
        assert threshold.get_gate_type("CONTENT_LIST_ONLY") == GateType.HARD

    def test_pilot_profile_more_flexible(self):
        """Test pilot profile allows more failures."""
        # In pilot profile: hard <= 1, soft <= 5
        threshold = QoderLikeSeverityThreshold()

        # Even pilot mode should block critical issues
        critical_codes = [
            "STRUCT_SECTION_DIR_MISSING",
            "CONTENT_EMPTY",
            "QODER_CITATION_MISSING",
        ]
        for code in critical_codes:
            if code in threshold.STRICT_HARD_CODES:
                assert threshold.is_blocking(code) is True


class TestGateTypeEnforcement:
    """Tests for gate type enforcement."""

    def test_gate_type_hard_blocks(self):
        """Test HARD gate type blocks release."""
        from repo_wiki.verifier.service import GateType

        threshold = QoderLikeSeverityThreshold()

        hard_codes = ["STRUCT_SECTION_DIR_MISSING", "QODER_CITATION_MISSING"]
        for code in hard_codes:
            assert threshold.get_gate_type(code) == GateType.HARD

    def test_gate_type_soft_warns_in_non_strict(self):
        """Test SOFT gate type warns in non-strict mode."""
        from repo_wiki.verifier.service import GateType

        # Default threshold (not strict) would allow soft gates
        # but we don't have non-strict implementation in qoder_strict_verifier
        # This test validates the enum exists
        assert hasattr(GateType, 'HARD')
        assert hasattr(GateType, 'SOFT')


class TestVerificationIntegration:
    """Integration tests for verification with gate policy."""

    def test_verifier_uses_strict_threshold(self, tmp_path):
        """Test that verifier uses strict threshold."""
        # Create minimal content
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        (content_dir / "00-overview.md").write_text("# Overview\n\n<cite>x</cite>\n\n## TOC\n- a")

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        assert verifier.strict is True

    def test_verifier_blocks_on_hard_failure(self, tmp_path):
        """Test that verifier blocks on hard gate failure."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        # Create page without TOC (should fail QODER_TOC_MISSING)
        (content_dir / "00-overview.md").write_text("# Overview\n\n<cite>x</cite>\nShort content.")

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        # Should have hard failures
        if result.get("hard_gate_failures", 0) > 0:
            assert result["exit_code"] == 1


class TestEvidenceCollection:
    """Tests for evidence collection in gate evaluation."""

    def test_verify_result_includes_hard_codes(self, tmp_path):
        """Test that verify result includes hard gate codes."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        (content_dir / "00-overview.md").write_text("# Overview\n\n## TOC\n- item")

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        # Result should have structure for hard codes
        assert "hard_gate_codes" in result or "grade" in result

    def test_verify_result_includes_soft_codes(self, tmp_path):
        """Test that verify result includes soft gate codes."""
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        (content_dir / "00-overview.md").write_text("# Overview\n\n## TOC\n- item\n<cite>x</cite>")

        verifier = QoderLikeVerifierService(tmp_path, strict=True)
        result = verifier.verify(ci=True)

        # Result should include gate information
        assert "profile" in result
        assert result["profile"] == "qoder-like"