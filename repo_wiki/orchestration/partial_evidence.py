"""Partial generation evidence bundle and failure recovery.

This module provides:
- Failure evidence recording with provider errors and retry info
- Partial run manifest for partially completed runs
- Evidence bundle creation for successful pages
- Recovery commands for failed pages

Phase 28 - Task 28.5: Failure recovery and partial evidence bundle

Key features:
- Structured failure records with error categorization
- Partial manifest preserving successful outputs
- Evidence bundle with content and metadata
- Retry command generation
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from repo_wiki.orchestration.generation_state import (
    GenerationStateMachine,
    PageState,
)

# =============================================================================
# FAILURE REASON CODES
# =============================================================================


class FailureReason(str, Enum):
    """Structured failure reason codes."""

    PROVIDER_ERROR = "provider_error"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    AUTHENTICATION_FAILED = "authentication_failed"
    CONTENT_FILTERED = "content_filtered"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    VALIDATION_FAILED = "validation_failed"
    BUDGET_EXCEEDED = "budget_exceeded"
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    UNKNOWN_ERROR = "unknown_error"


# =============================================================================
# FAILURE EVIDENCE
# =============================================================================


@dataclass
class PageFailureEvidence:
    """Evidence for a failed page generation."""

    run_id: str
    doc_slug: str
    doc_type: str
    doc_path: str
    attempts: int
    last_error: str
    reason_code: FailureReason
    provider: str
    model: str
    timestamp: str
    retry_command: str | None = None
    related_failures: list[str] = field(default_factory=list)


@dataclass
class PartialRunManifest:
    """Manifest for a partially completed generation run."""

    run_id: str
    profile: str
    total_pages: int
    completed_pages: list[str]
    failed_pages: list[str]
    skipped_pages: list[str]
    pending_pages: list[str]
    success_rate: float
    failure_reasons: dict[str, str]  # doc_slug -> reason_code
    created_at: str
    updated_at: str
    can_resume: bool
    is_retry: bool


@dataclass
class EvidenceBundle:
    """Bundle of evidence from a generation run."""

    run_id: str
    manifest: PartialRunManifest
    successful_pages: list[dict[str, Any]]  # Page evidence
    failed_pages: list[PageFailureEvidence]
    total_cost_usd: float
    total_tokens: int
    output_dir: Path | None


# =============================================================================
# FAILURE EVIDENCE RECORDER
# =============================================================================


class FailureEvidenceRecorder:
    """Records failure evidence for failed page generations."""

    def __init__(
        self,
        state_machine: GenerationStateMachine,
        db_path: Path,
    ) -> None:
        """Initialize failure recorder.

        Args:
            state_machine: Generation state machine
            db_path: Path to evidence database
        """
        self.state_machine = state_machine
        self.db_path = Path(db_path)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensure database schema exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS failure_evidence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    doc_slug TEXT NOT NULL,
                    doc_type TEXT,
                    doc_path TEXT,
                    attempts INTEGER DEFAULT 0,
                    last_error TEXT,
                    reason_code TEXT,
                    provider TEXT,
                    model TEXT,
                    timestamp TEXT NOT NULL,
                    retry_command TEXT,
                    related_failures_json TEXT,
                    UNIQUE(run_id, doc_slug)
                );

                CREATE INDEX IF NOT EXISTS idx_failure_run
                    ON failure_evidence(run_id);
                CREATE INDEX IF NOT EXISTS idx_failure_reason
                    ON failure_evidence(reason_code);
            """)
            conn.commit()
        finally:
            conn.close()

    def _conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def record_failure(
        self,
        run_id: str,
        doc_slug: str,
        doc_type: str,
        doc_path: str,
        attempts: int,
        last_error: str,
        reason_code: FailureReason,
        provider: str,
        model: str,
        retry_command: str | None = None,
        related_failures: list[str] | None = None,
    ) -> None:
        """Record a failure for a page.

        Args:
            run_id: Generation run ID
            doc_slug: Document slug
            doc_type: Document type
            doc_path: Document path
            attempts: Number of attempts made
            last_error: Last error message
            reason_code: Structured failure reason
            provider: LLM provider
            model: Model name
            retry_command: Command to retry this page
            related_failures: Other doc_slugs that failed with similar errors
        """
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO failure_evidence
                (run_id, doc_slug, doc_type, doc_path, attempts, last_error,
                 reason_code, provider, model, timestamp, retry_command,
                 related_failures_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, doc_slug) DO UPDATE SET
                    attempts = excluded.attempts,
                    last_error = excluded.last_error,
                    reason_code = excluded.reason_code,
                    provider = excluded.provider,
                    model = excluded.model,
                    timestamp = excluded.timestamp,
                    retry_command = excluded.retry_command,
                    related_failures_json = excluded.related_failures_json
                """,
                (
                    run_id,
                    doc_slug,
                    doc_type,
                    doc_path,
                    attempts,
                    last_error,
                    reason_code.value,
                    provider,
                    model,
                    datetime.now(UTC).isoformat(),
                    retry_command,
                    json.dumps(related_failures or []),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_failures_for_run(self, run_id: str) -> list[PageFailureEvidence]:
        """Get all failures for a run.

        Args:
            run_id: Generation run ID

        Returns:
            List of PageFailureEvidence
        """
        conn = self._conn()
        try:
            rows = conn.execute(
                """
                SELECT * FROM failure_evidence
                WHERE run_id = ?
                ORDER BY timestamp
                """,
                (run_id,),
            ).fetchall()

            failures = []
            for row in rows:
                failures.append(
                    PageFailureEvidence(
                        run_id=row["run_id"],
                        doc_slug=row["doc_slug"],
                        doc_type=row["doc_type"] or "",
                        doc_path=row["doc_path"] or "",
                        attempts=row["attempts"],
                        last_error=row["last_error"],
                        reason_code=FailureReason(row["reason_code"]),
                        provider=row["provider"],
                        model=row["model"],
                        timestamp=row["timestamp"],
                        retry_command=row["retry_command"],
                        related_failures=json.loads(row["related_failures_json"] or "[]"),
                    )
                )
            return failures
        finally:
            conn.close()

    def categorize_failures(
        self,
        failures: list[PageFailureEvidence],
    ) -> dict[FailureReason, list[str]]:
        """Categorize failures by reason code.

        Args:
            failures: List of failures

        Returns:
            Dictionary mapping reason codes to doc_slugs
        """
        categorized: dict[FailureReason, list[str]] = {}
        for failure in failures:
            if failure.reason_code not in categorized:
                categorized[failure.reason_code] = []
            categorized[failure.reason_code].append(failure.doc_slug)
        return categorized


# =============================================================================
# PARTIAL MANIFEST BUILDER
# =============================================================================


class PartialManifestBuilder:
    """Builds partial run manifests for partially completed runs."""

    def __init__(
        self,
        state_machine: GenerationStateMachine,
    ) -> None:
        """Initialize manifest builder.

        Args:
            state_machine: Generation state machine
        """
        self.state_machine = state_machine

    def build_manifest(self, run_id: str) -> PartialRunManifest | None:
        """Build a partial manifest for a run.

        Args:
            run_id: Generation run ID

        Returns:
            PartialRunManifest or None if run not found
        """
        run = self.state_machine.get_run(run_id)
        if not run:
            return None

        pages = self.state_machine.get_pages_for_run(run_id)

        completed = []
        failed = []
        skipped = []
        pending = []
        failure_reasons: dict[str, str] = {}

        for page in pages:
            if page.state == PageState.COMPLETED:
                completed.append(page.doc_slug)
            elif page.state == PageState.FAILED:
                failed.append(page.doc_slug)
                if page.error_message:
                    failure_reasons[page.doc_slug] = page.error_message
            elif page.state == PageState.RETRYABLE:
                failed.append(page.doc_slug)
                if page.error_message:
                    failure_reasons[page.doc_slug] = page.error_message
                else:
                    failure_reasons[page.doc_slug] = FailureReason.UNKNOWN_ERROR.value
            elif page.state == PageState.SKIPPED:
                skipped.append(page.doc_slug)
            elif page.state == PageState.PENDING:
                pending.append(page.doc_slug)

        total = len(pages)
        success_rate = len(completed) / total if total > 0 else 0.0

        # Can resume if there are pending pages and no running pages
        can_resume = (
            len(pending) > 0 or any(p.state == PageState.RETRYABLE for p in pages)
        ) and not any(p.state == PageState.RUNNING for p in pages)

        return PartialRunManifest(
            run_id=run_id,
            profile=run.profile,
            total_pages=total,
            completed_pages=completed,
            failed_pages=failed,
            skipped_pages=skipped,
            pending_pages=pending,
            success_rate=success_rate,
            failure_reasons=failure_reasons,
            created_at=run.created_at,
            updated_at=run.completed_at or run.created_at,
            can_resume=can_resume,
            is_retry=False,
        )

    def to_dict(self, manifest: PartialRunManifest) -> dict[str, Any]:
        """Convert manifest to dictionary.

        Args:
            manifest: Partial run manifest

        Returns:
            Dictionary representation
        """
        return {
            "run_id": manifest.run_id,
            "profile": manifest.profile,
            "total_pages": manifest.total_pages,
            "completed_pages": manifest.completed_pages,
            "failed_pages": manifest.failed_pages,
            "skipped_pages": manifest.skipped_pages,
            "pending_pages": manifest.pending_pages,
            "success_rate": manifest.success_rate,
            "failure_reasons": manifest.failure_reasons,
            "created_at": manifest.created_at,
            "updated_at": manifest.updated_at,
            "can_resume": manifest.can_resume,
            "is_retry": manifest.is_retry,
        }


# =============================================================================
# EVIDENCE BUNDLE CREATOR
# =============================================================================


class EvidenceBundleCreator:
    """Creates evidence bundles for generation runs."""

    def __init__(
        self,
        state_machine: GenerationStateMachine,
        evidence_recorder: FailureEvidenceRecorder,
        output_dir: Path | None = None,
    ) -> None:
        """Initialize evidence bundle creator.

        Args:
            state_machine: Generation state machine
            evidence_recorder: Failure evidence recorder
            output_dir: Output directory for evidence bundles
        """
        self.state_machine = state_machine
        self.evidence_recorder = evidence_recorder
        self.output_dir = output_dir

    def create_bundle(
        self,
        run_id: str,
        successful_page_content: dict[str, str] | None = None,
        total_cost: float = 0.0,
        total_tokens: int = 0,
    ) -> EvidenceBundle | None:
        """Create an evidence bundle for a run.

        Args:
            run_id: Generation run ID
            successful_page_content: Mapping of doc_slug to content
            total_cost: Total cost in USD
            total_tokens: Total tokens used

        Returns:
            EvidenceBundle or None if run not found
        """
        manifest_builder = PartialManifestBuilder(self.state_machine)
        manifest = manifest_builder.build_manifest(run_id)

        if not manifest:
            return None

        failures = self.evidence_recorder.get_failures_for_run(run_id)

        # Build successful pages evidence
        successful_pages = []
        if successful_page_content:
            for doc_slug, content in successful_page_content.items():
                successful_pages.append(
                    {
                        "doc_slug": doc_slug,
                        "content": content,
                        "content_length": len(content),
                    }
                )

        bundle = EvidenceBundle(
            run_id=run_id,
            manifest=manifest,
            successful_pages=successful_pages,
            failed_pages=failures,
            total_cost_usd=total_cost,
            total_tokens=total_tokens,
            output_dir=self.output_dir,
        )

        # Write bundle to file if output_dir provided
        if self.output_dir:
            self._write_bundle(bundle)

        return bundle

    def _write_bundle(self, bundle: EvidenceBundle) -> None:
        """Write evidence bundle to file.

        Args:
            bundle: Evidence bundle to write
        """
        if not self.output_dir:
            return

        bundle_dir = self.output_dir / bundle.run_id
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # Write manifest
        manifest_path = bundle_dir / "manifest.json"
        manifest_builder = PartialManifestBuilder(self.state_machine)
        manifest_dict = manifest_builder.to_dict(bundle.manifest)
        manifest_path.write_text(json.dumps(manifest_dict, indent=2))

        # Write failures
        if bundle.failed_pages:
            failures_path = bundle_dir / "failures.json"
            failures_data = [
                {
                    "doc_slug": f.doc_slug,
                    "reason_code": f.reason_code.value,
                    "last_error": f.last_error,
                    "attempts": f.attempts,
                }
                for f in bundle.failed_pages
            ]
            failures_path.write_text(json.dumps(failures_data, indent=2))

        # Write successful pages metadata
        if bundle.successful_pages:
            pages_path = bundle_dir / "pages.json"
            pages_data = [
                {
                    "doc_slug": p["doc_slug"],
                    "content_length": p["content_length"],
                }
                for p in bundle.successful_pages
            ]
            pages_path.write_text(json.dumps(pages_data, indent=2))

    def generate_retry_command(
        self,
        run_id: str,
        failed_slugs: list[str],
    ) -> str:
        """Generate a retry command for failed pages.

        Args:
            run_id: Generation run ID
            failed_slugs: List of doc_slugs to retry

        Returns:
            Retry command string
        """
        slugs_str = ",".join(failed_slugs)
        return f"repo-wiki generate --run {run_id} --retry {slugs_str}"


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_failure_recorder(
    root: Path,
) -> FailureEvidenceRecorder:
    """Create a failure evidence recorder.

    Args:
        root: Repository root

    Returns:
        FailureEvidenceRecorder instance
    """
    db_path = root / ".repo-wiki" / "index" / "failure_evidence.sqlite3"
    state_machine = GenerationStateMachine(
        root / ".repo-wiki" / "index" / "generation_state.sqlite3"
    )
    return FailureEvidenceRecorder(state_machine, db_path)


def create_partial_manifest(
    state_machine: GenerationStateMachine,
    run_id: str,
) -> PartialRunManifest | None:
    """Create a partial manifest for a run.

    Args:
        state_machine: Generation state machine
        run_id: Generation run ID

    Returns:
        PartialRunManifest or None
    """
    builder = PartialManifestBuilder(state_machine)
    return builder.build_manifest(run_id)
