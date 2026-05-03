"""Failure recovery helpers for partial generation runs.

This module keeps successful pages usable when a run is partially failed and
produces structured failure artifacts to make retry actions explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from repo_wiki.orchestration.generation_state import (
    GenerationStateMachine,
    PageState,
    RunState,
)
from repo_wiki.orchestration.partial_evidence import (
    FailureEvidenceRecorder,
    FailureReason,
    PartialManifestBuilder,
)


@dataclass
class FailedPageRecord:
    """Structured failure information for a page in a run."""

    run_id: str
    doc_slug: str
    reason_code: FailureReason
    provider_error: str
    provider: str
    model: str
    retry_command: str
    attempts: int
    page_state: str
    timestamp: str


@dataclass
class PartialEvidenceBundle:
    """Evidence bundle produced even when run is incomplete."""

    run_id: str
    run_state: RunState
    successful_pages: list[dict[str, Any]]
    failed_pages: list[FailedPageRecord]
    partial_manifest: dict[str, Any]
    created_at: str


class FailureRecoveryManager:
    """Handles recovery records and partial evidence generation."""

    def __init__(
        self,
        state_machine: GenerationStateMachine,
        evidence_recorder: FailureEvidenceRecorder,
    ) -> None:
        self.state_machine = state_machine
        self.evidence_recorder = evidence_recorder
        self.manifest_builder = PartialManifestBuilder(state_machine)

    def generate_retry_command(self, run_id: str, doc_slug: str) -> str:
        """Generate a deterministic retry command for a failed page."""
        return f"repo-wiki generate --run {run_id} --retry {doc_slug}"

    def record_failed_page(
        self,
        run_id: str,
        doc_slug: str,
        reason_code: FailureReason,
        provider_error: str,
        provider: str,
        model: str,
        retry_command: str | None = None,
    ) -> FailedPageRecord | None:
        """Record failure evidence for failed/retryable page state."""
        page = self.state_machine.get_page_state(run_id, doc_slug)
        if not page:
            return None
        if page.state not in (PageState.FAILED, PageState.RETRYABLE):
            return None

        retry_cmd = retry_command or self.generate_retry_command(run_id, doc_slug)
        self.evidence_recorder.record_failure(
            run_id=run_id,
            doc_slug=doc_slug,
            doc_type=page.doc_type,
            doc_path=page.doc_path,
            attempts=page.attempts,
            last_error=provider_error,
            reason_code=reason_code,
            provider=provider,
            model=model,
            retry_command=retry_cmd,
        )

        return FailedPageRecord(
            run_id=run_id,
            doc_slug=doc_slug,
            reason_code=reason_code,
            provider_error=provider_error,
            provider=provider,
            model=model,
            retry_command=retry_cmd,
            attempts=page.attempts,
            page_state=page.state.value,
            timestamp=datetime.now(UTC).isoformat(),
        )

    def build_partial_evidence_bundle(
        self,
        run_id: str,
        successful_page_content: dict[str, str] | None = None,
    ) -> PartialEvidenceBundle | None:
        """Build evidence for completed + failed/retryable pages in one bundle."""
        run = self.state_machine.get_run(run_id)
        if not run:
            return None

        manifest = self.manifest_builder.build_manifest(run_id)
        if not manifest:
            return None

        pages = self.state_machine.get_pages_for_run(run_id)
        completed_slugs = {p.doc_slug for p in pages if p.state == PageState.COMPLETED}

        successful_pages: list[dict[str, Any]] = []
        if successful_page_content:
            for slug, content in successful_page_content.items():
                if slug not in completed_slugs:
                    continue
                successful_pages.append(
                    {
                        "doc_slug": slug,
                        "content": content,
                        "content_length": len(content),
                        "usable": True,
                    }
                )

        failed_pages: list[FailedPageRecord] = []
        for evidence in self.evidence_recorder.get_failures_for_run(run_id):
            failed_pages.append(
                FailedPageRecord(
                    run_id=evidence.run_id,
                    doc_slug=evidence.doc_slug,
                    reason_code=evidence.reason_code,
                    provider_error=evidence.last_error,
                    provider=evidence.provider,
                    model=evidence.model,
                    retry_command=evidence.retry_command
                    or self.generate_retry_command(evidence.run_id, evidence.doc_slug),
                    attempts=evidence.attempts,
                    page_state=(
                        self.state_machine.get_page_state(run_id, evidence.doc_slug).state.value
                        if self.state_machine.get_page_state(run_id, evidence.doc_slug)
                        else PageState.FAILED.value
                    ),
                    timestamp=evidence.timestamp,
                )
            )

        failed_from_manifest = set(manifest.failed_pages) | set(manifest.pending_pages)
        for page in pages:
            if page.state != PageState.RETRYABLE:
                continue
            failed_from_manifest.add(page.doc_slug)
            if page.doc_slug in {f.doc_slug for f in failed_pages}:
                continue
            failed_pages.append(
                FailedPageRecord(
                    run_id=run_id,
                    doc_slug=page.doc_slug,
                    reason_code=FailureReason.UNKNOWN_ERROR,
                    provider_error=page.error_message or "Retryable page without recorder entry",
                    provider="unknown",
                    model="unknown",
                    retry_command=self.generate_retry_command(run_id, page.doc_slug),
                    attempts=page.attempts,
                    page_state=PageState.RETRYABLE.value,
                    timestamp=datetime.now(UTC).isoformat(),
                )
            )

        partial_manifest = self.manifest_builder.to_dict(manifest)
        partial_manifest["retryable_pages"] = sorted(
            p.doc_slug for p in pages if p.state == PageState.RETRYABLE
        )
        partial_manifest["failed_or_retryable_pages"] = sorted(failed_from_manifest)
        partial_manifest["usable_pages"] = sorted(completed_slugs)
        partial_manifest["is_partial"] = run.state in (RunState.RETRYABLE, RunState.FAILED)

        return PartialEvidenceBundle(
            run_id=run_id,
            run_state=run.state,
            successful_pages=successful_pages,
            failed_pages=failed_pages,
            partial_manifest=partial_manifest,
            created_at=datetime.now(UTC).isoformat(),
        )


def create_failure_recovery_manager(root: Path) -> FailureRecoveryManager:
    """Create failure recovery manager with default DB locations."""
    state_machine = GenerationStateMachine(
        root / ".repo-wiki" / "index" / "generation_state.sqlite3"
    )
    evidence_recorder = FailureEvidenceRecorder(
        state_machine, root / ".repo-wiki" / "index" / "failure_evidence.sqlite3"
    )
    return FailureRecoveryManager(state_machine, evidence_recorder)
