"""Qoder-like profile update integration.

This module integrates:
- Generation state machine for run tracking
- Cost estimator and budget gate
- Concurrent scheduler with rate limiting
- Page invalidation from git diff and hash
- Partial evidence bundle for failure recovery
- Content layout writer for qoder-like output

Phase 28 - Task 28.6: Update integration for qoder-like profile

Key features:
- Profile-aware update with qoder-like support
- Incremental update with targeted invalidation
- Budget-aware generation scheduling
- Failure recovery with partial evidence
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repo_wiki.orchestration.content_layout_writer import ContentLayoutWriter
from repo_wiki.orchestration.cost_estimator import (
    BudgetGate,
    GenerationCostEstimator,
)
from repo_wiki.orchestration.eval_layout import EvalOutputProfile, get_eval_profile
from repo_wiki.orchestration.generation_invalidation import (
    create_generation_invalidator,
)
from repo_wiki.orchestration.generation_scheduler import (
    GenerationScheduler,
    SchedulerConfig,
)
from repo_wiki.orchestration.generation_state import GenerationStateMachine
from repo_wiki.orchestration.partial_evidence import (
    EvidenceBundleCreator,
    FailureEvidenceRecorder,
    PartialManifestBuilder,
)

# =============================================================================
# INTEGRATION CONFIG
# =============================================================================


@dataclass
class QoderUpdateConfig:
    """Configuration for qoder-like update integration."""

    profile: EvalOutputProfile
    max_concurrency: int = 4
    default_budget_usd: float = 10.0
    allow_budget_override: bool = True
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    incremental: bool = True


# =============================================================================
# QODER UPDATE INTEGRATOR
# =============================================================================


class QoderUpdateIntegrator:
    """Integrates all Phase 28 components for qoder-like profile updates."""

    def __init__(
        self,
        root: Path,
        config: QoderUpdateConfig,
    ) -> None:
        """Initialize integrator.

        Args:
            root: Repository root
            config: Qoder update configuration
        """
        self.root = root
        self.config = config

        # Initialize state machine
        state_db = root / ".repo-wiki" / "index" / "generation_state.sqlite3"
        self.state_machine = GenerationStateMachine(state_db)

        # Initialize cost estimator and budget gate
        self.cost_estimator = GenerationCostEstimator(
            root / ".repo-wiki" / "index" / "generation_costs.sqlite3",
            default_budget_usd=config.default_budget_usd,
        )
        self.budget_gate = BudgetGate(
            self.cost_estimator,
            default_budget_usd=config.default_budget_usd,
            allow_override=config.allow_budget_override,
        )

        # Initialize scheduler
        scheduler_config = SchedulerConfig(
            max_concurrency=config.max_concurrency,
        )
        self.scheduler = GenerationScheduler(
            self.state_machine,
            self.cost_estimator,
            self.budget_gate,
            scheduler_config,
        )

        # Initialize invalidator
        self.invalidator = create_generation_invalidator(
            self.state_machine,
            root,
        )

        # Initialize evidence recorder
        self.evidence_recorder = FailureEvidenceRecorder(
            self.state_machine,
            root / ".repo-wiki" / "index" / "failure_evidence.sqlite3",
        )

        # Initialize evidence bundle creator
        self.evidence_creator = EvidenceBundleCreator(
            self.state_machine,
            self.evidence_recorder,
            output_dir=root / ".repo-wiki" / "evidence",
        )

        # Content layout writer for qoder-like output
        self.content_writer = ContentLayoutWriter(
            profile=config.profile,
            run_id="",  # Will be set per-run
        )

    def create_run(
        self,
        profile: str | None = None,
        total_pages: int = 0,
    ) -> tuple[str, GenerationStateMachine]:
        """Create a new generation run.

        Args:
            profile: Profile name
            total_pages: Total pages to generate

        Returns:
            Tuple of (run_id, state_machine)
        """
        run = self.state_machine.create_run(
            profile=profile or self.config.profile.name,
            total_pages=total_pages,
        )
        return run.run_id, self.state_machine

    def plan_incremental_update(
        self,
        run_id: str,
        baseline_hashes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Plan an incremental update.

        Args:
            run_id: Generation run ID
            baseline_hashes: Baseline file hashes for comparison

        Returns:
            Dictionary with invalidation plan
        """
        if baseline_hashes:
            invalidated, skipped = self.invalidator.invalidate_from_hash_comparison(
                run_id,
                baseline_hashes,
            )
        else:
            invalidated, skipped = self.invalidator.invalidate_from_git_diff(run_id)

        summary = self.invalidator.get_page_impact_summary(run_id)

        return {
            "run_id": run_id,
            "invalidated_pages": invalidated,
            "skipped_pages": skipped,
            "impact_summary": summary,
        }

    def create_partial_manifest(
        self,
        run_id: str,
    ) -> dict[str, Any]:
        """Create a partial manifest for a run.

        Args:
            run_id: Generation run ID

        Returns:
            Dictionary representation of manifest
        """
        builder = PartialManifestBuilder(self.state_machine)
        manifest = builder.build_manifest(run_id)
        if manifest:
            return builder.to_dict(manifest)
        return {}

    def create_evidence_bundle(
        self,
        run_id: str,
        successful_page_content: dict[str, str] | None = None,
        total_cost: float = 0.0,
        total_tokens: int = 0,
    ) -> dict[str, Any]:
        """Create an evidence bundle.

        Args:
            run_id: Generation run ID
            successful_page_content: Mapping of doc_slug to content
            total_cost: Total cost in USD
            total_tokens: Total tokens used

        Returns:
            Bundle metadata dictionary
        """
        bundle = self.evidence_creator.create_bundle(
            run_id,
            successful_page_content,
            total_cost,
            total_tokens,
        )
        if bundle:
            return {
                "run_id": bundle.run_id,
                "total_cost_usd": bundle.total_cost_usd,
                "total_tokens": bundle.total_tokens,
                "completed_pages": len(bundle.successful_pages),
                "failed_pages": len(bundle.failed_pages),
            }
        return {}

    def get_content_output_dir(self, run_id: str) -> Path:
        """Get the content output directory for a run.

        Args:
            run_id: Generation run ID

        Returns:
            Content directory path
        """
        writer = ContentLayoutWriter(
            profile=self.config.profile,
            run_id=run_id,
        )
        return writer.content_dir


# =============================================================================
# UPDATE INTEGRATION HELPERS
# =============================================================================


def create_qoder_integrator(
    root: Path,
    profile: str = "qoder-like",
    **kwargs: Any,
) -> QoderUpdateIntegrator:
    """Create a qoder-like update integrator.

    Args:
        root: Repository root
        profile: Profile name (default: qoder-like)
        **kwargs: Additional config options

    Returns:
        QoderUpdateIntegrator instance
    """
    eval_profile = get_eval_profile(profile)
    config = QoderUpdateConfig(profile=eval_profile, **kwargs)
    return QoderUpdateIntegrator(root, config)


def get_qoder_like_output_dir(
    root: Path,
    run_id: str,
    profile: str = "qoder-like",
) -> Path:
    """Get the qoder-like output directory for a run.

    Args:
        root: Repository root
        run_id: Generation run ID
        profile: Profile name

    Returns:
        Content directory path
    """
    eval_profile = get_eval_profile(profile)
    writer = ContentLayoutWriter(profile=eval_profile, run_id=run_id)
    return writer.content_dir
