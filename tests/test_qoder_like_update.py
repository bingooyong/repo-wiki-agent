"""Tests for qoder-like update integration."""

import tempfile
from pathlib import Path

import pytest

from repo_wiki.orchestration.eval_layout import EvalOutputProfile
from repo_wiki.orchestration.qoder_update_integration import (
    QoderUpdateConfig,
    QoderUpdateIntegrator,
    create_qoder_integrator,
    get_qoder_like_output_dir,
)


class TestQoderUpdateConfig:
    """Tests for QoderUpdateConfig."""

    def test_create_config(self):
        """Test creating qoder update config."""
        profile = EvalOutputProfile(name="qoder-like")
        config = QoderUpdateConfig(profile=profile)

        assert config.profile.name == "qoder-like"
        assert config.max_concurrency == 4
        assert config.default_budget_usd == 10.0

    def test_custom_config(self):
        """Test custom qoder update config."""
        profile = EvalOutputProfile(name="qoder-like")
        config = QoderUpdateConfig(
            profile=profile,
            max_concurrency=8,
            default_budget_usd=20.0,
            provider="anthropic",
            model="claude-sonnet-4-6",
        )

        assert config.max_concurrency == 8
        assert config.default_budget_usd == 20.0
        assert config.provider == "anthropic"
        assert config.model == "claude-sonnet-4-6"


class TestQoderUpdateIntegrator:
    """Tests for QoderUpdateIntegrator."""

    @pytest.fixture
    def integrator_setup(self, tmp_path):
        """Set up integrator with dependencies."""
        # Create required directories
        (tmp_path / ".repo-wiki" / "index").mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs").mkdir(parents=True, exist_ok=True)

        profile = EvalOutputProfile(name="qoder-like")
        config = QoderUpdateConfig(profile=profile)
        integrator = QoderUpdateIntegrator(tmp_path, config)

        return integrator, tmp_path

    def test_create_integrator(self, integrator_setup):
        """Test creating integrator."""
        integrator, _ = integrator_setup
        assert isinstance(integrator, QoderUpdateIntegrator)

    def test_create_run(self, integrator_setup):
        """Test creating a generation run."""
        integrator, _ = integrator_setup

        run_id, sm = integrator.create_run(profile="test", total_pages=5)

        assert run_id.startswith("gen-")
        assert sm is integrator.state_machine

    def test_plan_incremental_update(self, integrator_setup):
        """Test planning incremental update."""
        integrator, _ = integrator_setup

        # Create a run
        run_id, _ = integrator.create_run(profile="test", total_pages=3)
        integrator.state_machine.add_page(
            run_id, "00-overview", "overview", "docs/00-overview.md"
        )
        integrator.state_machine.add_page(
            run_id, "01-architecture", "overview", "docs/01-architecture.md"
        )
        integrator.state_machine.add_page(
            run_id, "02-services", "module", "docs/02-services.md"
        )

        # Plan update
        plan = integrator.plan_incremental_update(run_id)

        assert plan["run_id"] == run_id
        assert "invalidated_pages" in plan
        assert "skipped_pages" in plan
        assert "impact_summary" in plan

    def test_create_partial_manifest(self, integrator_setup):
        """Test creating partial manifest."""
        integrator, _ = integrator_setup

        # Create and complete a run
        run_id, _ = integrator.create_run(profile="test", total_pages=2)
        integrator.state_machine.add_page(
            run_id, "00-overview", "overview", "docs/00-overview.md"
        )
        integrator.state_machine.add_page(
            run_id, "01-architecture", "overview", "docs/01-architecture.md"
        )

        integrator.state_machine.start_page(run_id, "00-overview")
        integrator.state_machine.complete_page(run_id, "00-overview")

        manifest = integrator.create_partial_manifest(run_id)

        assert manifest["run_id"] == run_id
        assert manifest["total_pages"] == 2
        assert len(manifest["completed_pages"]) == 1
        assert manifest["success_rate"] == 0.5

    def test_create_evidence_bundle(self, integrator_setup):
        """Test creating evidence bundle."""
        integrator, _ = integrator_setup

        # Create run with failures
        run_id, _ = integrator.create_run(profile="test", total_pages=2)
        integrator.state_machine.add_page(
            run_id, "00-overview", "overview", "docs/00-overview.md"
        )
        integrator.state_machine.add_page(
            run_id, "01-architecture", "overview", "docs/01-architecture.md"
        )

        integrator.state_machine.complete_page(run_id, "00-overview")
        integrator.state_machine.start_page(run_id, "01-architecture")
        integrator.state_machine.fail_page(
            run_id, "01-architecture", "timeout", retryable=False
        )

        # Record failure
        from repo_wiki.orchestration.partial_evidence import FailureReason
        integrator.evidence_recorder.record_failure(
            run_id=run_id,
            doc_slug="01-architecture",
            doc_type="overview",
            doc_path="docs/01-architecture.md",
            attempts=3,
            last_error="timeout",
            reason_code=FailureReason.TIMEOUT,
            provider="openai",
            model="gpt-4o-mini",
        )

        # Create evidence bundle
        content = {"00-overview": "# Overview\n\nContent"}
        bundle = integrator.create_evidence_bundle(
            run_id,
            successful_page_content=content,
            total_cost=0.05,
            total_tokens=1500,
        )

        assert bundle["run_id"] == run_id
        assert bundle["completed_pages"] == 1
        assert bundle["failed_pages"] == 1
        assert bundle["total_cost_usd"] == 0.05

    def test_get_content_output_dir(self, integrator_setup):
        """Test getting content output directory."""
        integrator, _ = integrator_setup

        run_id, _ = integrator.create_run(profile="test", total_pages=1)
        output_dir = integrator.get_content_output_dir(run_id)

        # Output dir should contain run_id and be under .repo-agent-eval
        assert run_id in str(output_dir)
        assert ".repo-agent-eval" in str(output_dir)


class TestCreateQoderIntegrator:
    """Tests for create_qoder_integrator factory."""

    def test_create_qoder_integrator(self, tmp_path):
        """Test create_qoder_integrator factory."""
        # Create required directories
        (tmp_path / ".repo-wiki" / "index").mkdir(parents=True, exist_ok=True)

        integrator = create_qoder_integrator(tmp_path)
        assert isinstance(integrator, QoderUpdateIntegrator)

    def test_create_qoder_integrator_custom(self, tmp_path):
        """Test create_qoder_integrator with custom config."""
        # Create required directories
        (tmp_path / ".repo-wiki" / "index").mkdir(parents=True, exist_ok=True)

        integrator = create_qoder_integrator(
            tmp_path,
            max_concurrency=8,
            default_budget_usd=20.0,
        )
        assert integrator.config.max_concurrency == 8
        assert integrator.config.default_budget_usd == 20.0


class TestGetQoderLikeOutputDir:
    """Tests for get_qoder_like_output_dir function."""

    def test_get_output_dir(self, tmp_path):
        """Test getting qoder-like output directory."""
        output_dir = get_qoder_like_output_dir(tmp_path, "gen-test-123")
        assert isinstance(output_dir, Path)
