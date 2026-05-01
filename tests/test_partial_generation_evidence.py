"""Tests for partial generation evidence bundle."""

import tempfile
from pathlib import Path

import pytest

from repo_wiki.orchestration.generation_state import (
    GenerationStateMachine,
    PageState,
)
from repo_wiki.orchestration.partial_evidence import (
    EvidenceBundleCreator,
    FailureEvidenceRecorder,
    FailureReason,
    PageFailureEvidence,
    PartialManifestBuilder,
    PartialRunManifest,
    create_failure_recorder,
    create_partial_manifest,
)


class TestFailureReason:
    """Tests for FailureReason enum."""

    def test_failure_reason_values(self):
        """Test failure reason enum values."""
        assert FailureReason.PROVIDER_ERROR.value == "provider_error"
        assert FailureReason.RATE_LIMIT_EXCEEDED.value == "rate_limit_exceeded"
        assert FailureReason.BUDGET_EXCEEDED.value == "budget_exceeded"


class TestPageFailureEvidence:
    """Tests for PageFailureEvidence dataclass."""

    def test_create_failure_evidence(self):
        """Test creating failure evidence."""
        evidence = PageFailureEvidence(
            run_id="gen-test",
            doc_slug="00-overview",
            doc_type="overview",
            doc_path="docs/00-overview.md",
            attempts=3,
            last_error="Connection timeout",
            reason_code=FailureReason.TIMEOUT,
            provider="openai",
            model="gpt-4o-mini",
            timestamp="2024-01-01T00:00:00Z",
        )
        assert evidence.run_id == "gen-test"
        assert evidence.doc_slug == "00-overview"
        assert evidence.attempts == 3
        assert evidence.reason_code == FailureReason.TIMEOUT


class TestPartialRunManifest:
    """Tests for PartialRunManifest dataclass."""

    def test_create_manifest(self):
        """Test creating partial manifest."""
        manifest = PartialRunManifest(
            run_id="gen-test",
            profile="default",
            total_pages=5,
            completed_pages=["00-overview", "01-architecture"],
            failed_pages=["02-services"],
            skipped_pages=["03-other"],
            pending_pages=["04-pending"],
            success_rate=0.4,
            failure_reasons={"02-services": "timeout"},
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:01:00Z",
            can_resume=True,
            is_retry=False,
        )
        assert manifest.run_id == "gen-test"
        assert manifest.total_pages == 5
        assert len(manifest.completed_pages) == 2
        assert manifest.can_resume is True


class TestFailureEvidenceRecorder:
    """Tests for FailureEvidenceRecorder."""

    @pytest.fixture
    def recorder_setup(self, tmp_path):
        """Set up recorder with dependencies."""
        state_db = tmp_path / "state.sqlite3"
        evidence_db = tmp_path / "evidence.sqlite3"

        state_machine = GenerationStateMachine(state_db)
        recorder = FailureEvidenceRecorder(state_machine, evidence_db)

        return recorder, state_machine

    def test_record_failure(self, recorder_setup):
        """Test recording a failure."""
        recorder, state_machine = recorder_setup

        recorder.record_failure(
            run_id="gen-test",
            doc_slug="00-overview",
            doc_type="overview",
            doc_path="docs/00-overview.md",
            attempts=3,
            last_error="Connection timeout",
            reason_code=FailureReason.TIMEOUT,
            provider="openai",
            model="gpt-4o-mini",
        )

        failures = recorder.get_failures_for_run("gen-test")
        assert len(failures) == 1
        assert failures[0].doc_slug == "00-overview"
        assert failures[0].attempts == 3
        assert failures[0].reason_code == FailureReason.TIMEOUT

    def test_get_failures_for_run(self, recorder_setup):
        """Test getting failures for a run."""
        recorder, state_machine = recorder_setup

        # Record multiple failures
        recorder.record_failure(
            run_id="gen-test",
            doc_slug="00-overview",
            doc_type="overview",
            doc_path="docs/00-overview.md",
            attempts=1,
            last_error="error1",
            reason_code=FailureReason.PROVIDER_ERROR,
            provider="openai",
            model="gpt-4o-mini",
        )
        recorder.record_failure(
            run_id="gen-test",
            doc_slug="01-architecture",
            doc_type="overview",
            doc_path="docs/01-architecture.md",
            attempts=2,
            last_error="error2",
            reason_code=FailureReason.RATE_LIMIT_EXCEEDED,
            provider="openai",
            model="gpt-4o-mini",
        )

        failures = recorder.get_failures_for_run("gen-test")
        assert len(failures) == 2

    def test_categorize_failures(self, recorder_setup):
        """Test categorizing failures by reason code."""
        recorder, state_machine = recorder_setup

        recorder.record_failure(
            run_id="gen-test",
            doc_slug="00-overview",
            doc_type="overview",
            doc_path="docs/00-overview.md",
            attempts=1,
            last_error="error1",
            reason_code=FailureReason.PROVIDER_ERROR,
            provider="openai",
            model="gpt-4o-mini",
        )
        recorder.record_failure(
            run_id="gen-test",
            doc_slug="01-architecture",
            doc_type="overview",
            doc_path="docs/01-architecture.md",
            attempts=2,
            last_error="error2",
            reason_code=FailureReason.PROVIDER_ERROR,
            provider="openai",
            model="gpt-4o-mini",
        )
        recorder.record_failure(
            run_id="gen-test",
            doc_slug="02-services",
            doc_type="module",
            doc_path="docs/02-services.md",
            attempts=1,
            last_error="rate limit",
            reason_code=FailureReason.RATE_LIMIT_EXCEEDED,
            provider="openai",
            model="gpt-4o-mini",
        )

        failures = recorder.get_failures_for_run("gen-test")
        categorized = recorder.categorize_failures(failures)

        assert FailureReason.PROVIDER_ERROR in categorized
        assert len(categorized[FailureReason.PROVIDER_ERROR]) == 2
        assert FailureReason.RATE_LIMIT_EXCEEDED in categorized
        assert len(categorized[FailureReason.RATE_LIMIT_EXCEEDED]) == 1


class TestPartialManifestBuilder:
    """Tests for PartialManifestBuilder."""

    @pytest.fixture
    def builder_setup(self, tmp_path):
        """Set up builder with dependencies."""
        db_path = tmp_path / "state.sqlite3"
        state_machine = GenerationStateMachine(db_path)
        builder = PartialManifestBuilder(state_machine)

        return builder, state_machine

    def test_build_manifest(self, builder_setup):
        """Test building a manifest."""
        builder, state_machine = builder_setup

        # Create run with pages
        run = state_machine.create_run(profile="test", total_pages=4)
        state_machine.add_page(run.run_id, "00-overview", "overview", "docs/00-overview.md")
        state_machine.add_page(run.run_id, "01-architecture", "overview", "docs/01-architecture.md")
        state_machine.add_page(run.run_id, "02-services", "module", "docs/02-services.md")
        state_machine.add_page(run.run_id, "03-data", "module", "docs/03-data.md")

        # Complete some, fail some (fail_page makes it retryable unless max attempts reached)
        state_machine.start_page(run.run_id, "00-overview")
        state_machine.complete_page(run.run_id, "00-overview")
        state_machine.start_page(run.run_id, "01-architecture")
        state_machine.complete_page(run.run_id, "01-architecture")

        # Exhaust retries to make it FAILED
        state_machine.start_page(run.run_id, "02-services")
        state_machine.fail_page(run.run_id, "02-services", "timeout")
        state_machine.start_page(run.run_id, "02-services")
        state_machine.fail_page(run.run_id, "02-services", "timeout")
        state_machine.start_page(run.run_id, "02-services")
        state_machine.fail_page(run.run_id, "02-services", "timeout", retryable=False)

        # 03-data stays pending

        manifest = builder.build_manifest(run.run_id)

        assert manifest is not None
        assert manifest.run_id == run.run_id
        assert manifest.total_pages == 4
        assert len(manifest.completed_pages) == 2
        assert len(manifest.failed_pages) == 1
        assert len(manifest.pending_pages) == 1
        assert manifest.success_rate == 0.5
        assert "02-services" in manifest.failure_reasons

    def test_build_manifest_not_found(self, builder_setup):
        """Test building manifest for nonexistent run."""
        builder, _ = builder_setup
        manifest = builder.build_manifest("nonexistent")
        assert manifest is None

    def test_to_dict(self, builder_setup):
        """Test converting manifest to dict."""
        builder, state_machine = builder_setup

        # Create minimal run
        run = state_machine.create_run(profile="test", total_pages=1)
        state_machine.add_page(run.run_id, "00-overview", "overview", "docs/00-overview.md")
        state_machine.complete_page(run.run_id, "00-overview")

        manifest = builder.build_manifest(run.run_id)
        assert manifest is not None

        manifest_dict = builder.to_dict(manifest)
        assert manifest_dict["run_id"] == run.run_id
        assert manifest_dict["total_pages"] == 1
        assert len(manifest_dict["completed_pages"]) == 1


class TestEvidenceBundleCreator:
    """Tests for EvidenceBundleCreator."""

    @pytest.fixture
    def creator_setup(self, tmp_path):
        """Set up creator with dependencies."""
        state_db = tmp_path / "state.sqlite3"
        evidence_db = tmp_path / "evidence.sqlite3"

        state_machine = GenerationStateMachine(state_db)
        recorder = FailureEvidenceRecorder(state_machine, evidence_db)
        output_dir = tmp_path / "evidence"
        creator = EvidenceBundleCreator(state_machine, recorder, output_dir)

        return creator, recorder, state_machine

    def test_create_bundle(self, creator_setup):
        """Test creating an evidence bundle."""
        creator, recorder, state_machine = creator_setup

        # Create run with some pages
        run = state_machine.create_run(profile="test", total_pages=3)
        state_machine.add_page(run.run_id, "00-overview", "overview", "docs/00-overview.md")
        state_machine.add_page(run.run_id, "01-architecture", "overview", "docs/01-architecture.md")
        state_machine.add_page(run.run_id, "02-services", "module", "docs/02-services.md")

        state_machine.complete_page(run.run_id, "00-overview")
        state_machine.fail_page(run.run_id, "01-architecture", "timeout")

        # Record the failure
        recorder.record_failure(
            run_id=run.run_id,
            doc_slug="01-architecture",
            doc_type="overview",
            doc_path="docs/01-architecture.md",
            attempts=2,
            last_error="timeout",
            reason_code=FailureReason.TIMEOUT,
            provider="openai",
            model="gpt-4o-mini",
        )

        # Create bundle
        content = {"00-overview": "# Overview\n\nContent here."}
        bundle = creator.create_bundle(
            run.run_id,
            successful_page_content=content,
            total_cost=0.05,
            total_tokens=1500,
        )

        assert bundle is not None
        assert bundle.run_id == run.run_id
        assert len(bundle.successful_pages) == 1
        assert len(bundle.failed_pages) == 1
        assert bundle.total_cost_usd == 0.05

    def test_create_bundle_not_found(self, creator_setup):
        """Test creating bundle for nonexistent run."""
        creator, _, _ = creator_setup
        bundle = creator.create_bundle("nonexistent")
        assert bundle is None

    def test_generate_retry_command(self, creator_setup):
        """Test generating retry command."""
        creator, _, _ = creator_setup

        cmd = creator.generate_retry_command(
            "gen-test",
            ["00-overview", "01-architecture"],
        )

        assert "gen-test" in cmd
        assert "00-overview" in cmd
        assert "01-architecture" in cmd


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_failure_recorder(self, tmp_path):
        """Test create_failure_recorder factory."""
        recorder = create_failure_recorder(tmp_path)
        assert isinstance(recorder, FailureEvidenceRecorder)

    def test_create_partial_manifest(self, tmp_path):
        """Test create_partial_manifest factory."""
        db_path = tmp_path / "state.sqlite3"
        state_machine = GenerationStateMachine(db_path)

        run = state_machine.create_run(profile="test", total_pages=1)
        state_machine.add_page(run.run_id, "00-overview", "overview", "docs/00-overview.md")

        manifest = create_partial_manifest(state_machine, run.run_id)
        assert manifest is not None
        assert manifest.run_id == run.run_id
