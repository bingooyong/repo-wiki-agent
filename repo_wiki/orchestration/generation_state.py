"""Generation run state machine and page-level state tracking.

This module implements:
- GenerationRunState: State machine for generation runs (pending/running/completed/failed/retryable)
- PageState: Per-page generation state with resume support
- SQLite persistence for run and page states

Phase 28 - Task 28.1: Generation run state machine

Key features:
- Run-level state transitions
- Page-level state tracking within runs
- Resume without regenerating completed pages
- Failure isolation and retry support
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class RunState(str, Enum):
    """Generation run states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYABLE = "retryable"
    CANCELLED = "cancelled"


class PageState(str, Enum):
    """Page-level generation states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYABLE = "retryable"


@dataclass
class GenerationRun:
    """Represents a generation run with state tracking."""
    run_id: str
    state: RunState
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    total_pages: int = 0
    completed_pages: int = 0
    failed_pages: int = 0
    skipped_pages: int = 0
    error_message: str | None = None
    profile: str = "default"
    run_type: str = "full"  # "full" or "incremental"
    target_git_commit: str | None = None


@dataclass
class PageGenerationState:
    """Represents the state of a single page generation."""
    run_id: str
    doc_slug: str
    doc_type: str
    doc_path: str
    state: PageState
    attempts: int = 0
    max_attempts: int = 3
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    retry_after: str | None = None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _now_epoch() -> float:
    return time.time()


SCHEMA_VERSION = 1

# Migration 1: Generation run state tables
MIGRATION_1 = """
-- Generation runs table: tracks overall run state
CREATE TABLE IF NOT EXISTS generation_runs (
    run_id TEXT PRIMARY KEY,
    state TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    total_pages INTEGER DEFAULT 0,
    completed_pages INTEGER DEFAULT 0,
    failed_pages INTEGER DEFAULT 0,
    skipped_pages INTEGER DEFAULT 0,
    error_message TEXT,
    profile TEXT DEFAULT 'default',
    run_type TEXT DEFAULT 'full',
    target_git_commit TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_state ON generation_runs(state);
CREATE INDEX IF NOT EXISTS idx_runs_created ON generation_runs(created_at);

-- Page generation states table: per-page state tracking
CREATE TABLE IF NOT EXISTS page_generation_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    doc_slug TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    doc_path TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT,
    input_hash TEXT,
    output_hash TEXT,
    retry_after TEXT,
    FOREIGN KEY (run_id) REFERENCES generation_runs(run_id) ON DELETE CASCADE,
    UNIQUE(run_id, doc_slug)
);

CREATE INDEX IF NOT EXISTS idx_page_run ON page_generation_states(run_id);
CREATE INDEX IF NOT EXISTS idx_page_state ON page_generation_states(state);
CREATE INDEX IF NOT EXISTS idx_page_doc ON page_generation_states(doc_slug);
"""


class GenerationStateMachine:
    """State machine for managing generation runs and page states.

    Supports:
    - Run-level state transitions
    - Page-level state tracking
    - Resume from interrupted runs
    - Retry for failed pages
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize the state machine.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensure database schema exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript(MIGRATION_1)
            conn.commit()
        finally:
            conn.close()

    def _conn(self) -> sqlite3.Connection:
        """Get a database connection with row factory enabled."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================================
    # RUN STATE OPERATIONS
    # =========================================================================

    def create_run(
        self,
        profile: str = "default",
        run_type: str = "full",
        total_pages: int = 0,
        target_git_commit: str | None = None,
    ) -> GenerationRun:
        """Create a new generation run.

        Args:
            profile: Eval profile name
            run_type: "full" or "incremental"
            total_pages: Total number of pages to generate
            target_git_commit: Git commit hash at run start

        Returns:
            GenerationRun instance
        """
        run_id = f"gen-{uuid.uuid4().hex[:12]}"
        now = _now_iso()

        run = GenerationRun(
            run_id=run_id,
            state=RunState.PENDING,
            created_at=now,
            total_pages=total_pages,
            profile=profile,
            run_type=run_type,
            target_git_commit=target_git_commit,
        )

        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO generation_runs
                (run_id, state, created_at, total_pages, profile, run_type, target_git_commit)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run.run_id, run.state.value, run.created_at, run.total_pages,
                 run.profile, run.run_type, run.target_git_commit),
            )
            conn.commit()
        finally:
            conn.close()

        return run

    def start_run(self, run_id: str) -> GenerationRun | None:
        """Start a pending run.

        Args:
            run_id: The run ID to start

        Returns:
            Updated GenerationRun or None if not found
        """
        now = _now_iso()
        conn = self._conn()
        try:
            cursor = conn.execute(
                """
                UPDATE generation_runs
                SET state = ?, started_at = ?
                WHERE run_id = ? AND state = ?
                """,
                (RunState.RUNNING.value, now, run_id, RunState.PENDING.value),
            )
            conn.commit()

            if cursor.rowcount == 0:
                return None

            return self.get_run(run_id)
        finally:
            conn.close()

    def complete_run(
        self,
        run_id: str,
        error_message: str | None = None,
    ) -> GenerationRun | None:
        """Mark a run as completed or failed.

        Args:
            run_id: The run ID to complete
            error_message: Error message if failed

        Returns:
            Updated GenerationRun or None if not found
        """
        now = _now_iso()
        conn = self._conn()
        try:
            # Determine final state based on page outcomes
            stats = self._get_run_stats(conn, run_id)

            if stats["retryable"] > 0:
                final_state = RunState.RETRYABLE
            elif stats["failed"] > 0 and stats["completed"] == 0:
                final_state = RunState.FAILED
            elif stats["skipped"] == stats["total"] and stats["total"] > 0:
                final_state = RunState.COMPLETED
            elif stats["completed"] == stats["total"]:
                final_state = RunState.COMPLETED
            elif stats["completed"] > 0:
                final_state = RunState.COMPLETED  # Partial success
            else:
                final_state = RunState.FAILED

            conn.execute(
                """
                UPDATE generation_runs
                SET state = ?, completed_at = ?, completed_pages = ?,
                    failed_pages = ?, skipped_pages = ?, error_message = ?
                WHERE run_id = ?
                """,
                (final_state.value, now, stats["completed"], stats["failed"],
                 stats["skipped"], error_message, run_id),
            )
            conn.commit()

            return self.get_run(run_id)
        finally:
            conn.close()

    def resume_run(self, run_id: str) -> GenerationRun | None:
        """Resume an interrupted run without touching completed/skipped pages.

        Any in-flight page (`running`) is converted to `retryable`, while already
        completed pages remain completed and won't be re-generated.
        """
        now = _now_iso()
        conn = self._conn()
        try:
            run_row = conn.execute(
                "SELECT state FROM generation_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if not run_row:
                return None

            run_state = RunState(run_row["state"])
            if run_state not in {RunState.PENDING, RunState.RUNNING, RunState.RETRYABLE, RunState.FAILED}:
                return self.get_run(run_id)

            # Mark interrupted in-flight pages as retryable for safe re-execution.
            conn.execute(
                """
                UPDATE page_generation_states
                SET state = ?, error_message = COALESCE(error_message, ?), completed_at = ?
                WHERE run_id = ? AND state = ?
                """,
                (
                    PageState.RETRYABLE.value,
                    "Interrupted run resumed",
                    now,
                    run_id,
                    PageState.RUNNING.value,
                ),
            )

            conn.execute(
                """
                UPDATE generation_runs
                SET state = ?, started_at = COALESCE(started_at, ?), completed_at = NULL
                WHERE run_id = ?
                """,
                (RunState.RUNNING.value, now, run_id),
            )
            conn.commit()
            return self.get_run(run_id)
        finally:
            conn.close()

    def cancel_run(self, run_id: str) -> GenerationRun | None:
        """Cancel a running or pending run.

        Args:
            run_id: The run ID to cancel

        Returns:
            Updated GenerationRun or None if not found
        """
        now = _now_iso()
        conn = self._conn()
        try:
            conn.execute(
                """
                UPDATE generation_runs
                SET state = ?, completed_at = ?, error_message = ?
                WHERE run_id = ? AND state IN (?, ?)
                """,
                (RunState.CANCELLED.value, now, "Cancelled by user",
                 run_id, RunState.PENDING.value, RunState.RUNNING.value),
            )
            conn.commit()

            # Mark remaining pending pages as skipped
            conn.execute(
                """
                UPDATE page_generation_states
                SET state = ?, completed_at = ?
                WHERE run_id = ? AND state = ?
                """,
                (PageState.SKIPPED.value, now, run_id, PageState.PENDING.value),
            )
            conn.commit()

            return self.get_run(run_id)
        finally:
            conn.close()

    def get_run(self, run_id: str) -> GenerationRun | None:
        """Get a run by ID.

        Args:
            run_id: The run ID

        Returns:
            GenerationRun or None if not found
        """
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM generation_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()

            if not row:
                return None

            return GenerationRun(
                run_id=row["run_id"],
                state=RunState(row["state"]),
                created_at=row["created_at"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
                total_pages=row["total_pages"],
                completed_pages=row["completed_pages"],
                failed_pages=row["failed_pages"],
                skipped_pages=row["skipped_pages"],
                error_message=row["error_message"],
                profile=row["profile"],
                run_type=row["run_type"],
                target_git_commit=row["target_git_commit"],
            )
        finally:
            conn.close()

    def get_run_stats(self, run_id: str) -> dict[str, int]:
        """Get page statistics for a run.

        Args:
            run_id: The run ID

        Returns:
            Dict with total, completed, failed, skipped counts
        """
        conn = self._conn()
        try:
            return self._get_run_stats(conn, run_id)
        finally:
            conn.close()

    def _get_run_stats(self, conn: sqlite3.Connection, run_id: str) -> dict[str, int]:
        """Get page statistics (internal)."""
        stats = conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN state = ? THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN state = ? THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN state = ? THEN 1 ELSE 0 END) as skipped,
                SUM(CASE WHEN state = ? THEN 1 ELSE 0 END) as retryable
            FROM page_generation_states
            WHERE run_id = ?
            """,
            (PageState.COMPLETED.value, PageState.FAILED.value,
             PageState.SKIPPED.value, PageState.RETRYABLE.value, run_id),
        ).fetchone()

        return {
            "total": stats["total"] or 0,
            "completed": stats["completed"] or 0,
            "failed": stats["failed"] or 0,
            "skipped": stats["skipped"] or 0,
            "retryable": stats["retryable"] or 0,
        }

    def list_runs(
        self,
        state: RunState | None = None,
        limit: int = 10,
    ) -> list[GenerationRun]:
        """List recent runs.

        Args:
            state: Optional state filter
            limit: Maximum number of runs to return

        Returns:
            List of GenerationRun instances
        """
        conn = self._conn()
        try:
            if state:
                rows = conn.execute(
                    """
                    SELECT * FROM generation_runs
                    WHERE state = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (state.value, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM generation_runs
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

            return [
                GenerationRun(
                    run_id=row["run_id"],
                    state=RunState(row["state"]),
                    created_at=row["created_at"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    total_pages=row["total_pages"],
                    completed_pages=row["completed_pages"],
                    failed_pages=row["failed_pages"],
                    skipped_pages=row["skipped_pages"],
                    error_message=row["error_message"],
                    profile=row["profile"],
                    run_type=row["run_type"],
                    target_git_commit=row["target_git_commit"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    # =========================================================================
    # PAGE STATE OPERATIONS
    # =========================================================================

    def add_page(
        self,
        run_id: str,
        doc_slug: str,
        doc_type: str,
        doc_path: str,
        input_hash: str | None = None,
    ) -> PageGenerationState:
        """Add a page to track for a run.

        Args:
            run_id: Parent run ID
            doc_slug: Document slug
            doc_type: Document type (overview, section, module)
            doc_path: Document path
            input_hash: Hash of generation inputs

        Returns:
            PageGenerationState instance
        """
        state = PageGenerationState(
            run_id=run_id,
            doc_slug=doc_slug,
            doc_type=doc_type,
            doc_path=doc_path,
            state=PageState.PENDING,
            input_hash=input_hash,
        )

        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO page_generation_states
                (run_id, doc_slug, doc_type, doc_path, state, input_hash)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (state.run_id, state.doc_slug, state.doc_type,
                 state.doc_path, state.state.value, state.input_hash),
            )
            conn.commit()
        finally:
            conn.close()

        return state

    def start_page(self, run_id: str, doc_slug: str) -> PageGenerationState | None:
        """Mark a page as running.

        Args:
            run_id: Parent run ID
            doc_slug: Document slug

        Returns:
            Updated PageGenerationState or None if not found
        """
        now = _now_iso()
        conn = self._conn()
        try:
            cursor = conn.execute(
                """
                UPDATE page_generation_states
                SET state = ?, started_at = ?
                WHERE run_id = ? AND doc_slug = ? AND state IN (?, ?)
                """,
                (PageState.RUNNING.value, now, run_id, doc_slug,
                 PageState.PENDING.value, PageState.RETRYABLE.value),
            )
            conn.commit()

            if cursor.rowcount == 0:
                return None

            return self.get_page_state(run_id, doc_slug)
        finally:
            conn.close()

    def complete_page(
        self,
        run_id: str,
        doc_slug: str,
        output_hash: str | None = None,
    ) -> PageGenerationState | None:
        """Mark a page as completed.

        Args:
            run_id: Parent run ID
            doc_slug: Document slug
            output_hash: Hash of generated output

        Returns:
            Updated PageGenerationState or None if not found
        """
        now = _now_iso()
        conn = self._conn()
        try:
            conn.execute(
                """
                UPDATE page_generation_states
                SET state = ?, completed_at = ?, output_hash = ?
                WHERE run_id = ? AND doc_slug = ?
                """,
                (PageState.COMPLETED.value, now, output_hash, run_id, doc_slug),
            )
            conn.commit()
            return self.get_page_state(run_id, doc_slug)
        finally:
            conn.close()

    def fail_page(
        self,
        run_id: str,
        doc_slug: str,
        error_message: str,
        retryable: bool = True,
    ) -> PageGenerationState | None:
        """Mark a page as failed.

        Args:
            run_id: Parent run ID
            doc_slug: Document slug
            error_message: Error description
            retryable: Whether page can be retried (auto-false if max_attempts reached)

        Returns:
            Updated PageGenerationState or None if not found
        """
        now = _now_iso()
        conn = self._conn()
        try:
            # Get current page state to check attempts
            page = self.get_page_state(run_id, doc_slug)
            if not page:
                return None

            # Increment attempts on each failure
            new_attempts = page.attempts + 1

            # Check if max attempts reached
            if new_attempts >= page.max_attempts:
                retryable = False

            new_state = PageState.RETRYABLE if retryable else PageState.FAILED

            conn.execute(
                """
                UPDATE page_generation_states
                SET state = ?, completed_at = ?, error_message = ?, attempts = ?
                WHERE run_id = ? AND doc_slug = ?
                """,
                (new_state.value, now, error_message, new_attempts, run_id, doc_slug),
            )
            conn.commit()
            return self.get_page_state(run_id, doc_slug)
        finally:
            conn.close()

    def skip_page(
        self,
        run_id: str,
        doc_slug: str,
        reason: str | None = None,
    ) -> PageGenerationState | None:
        """Mark a page as skipped.

        Args:
            run_id: Parent run ID
            doc_slug: Document slug
            reason: Skip reason

        Returns:
            Updated PageGenerationState or None if not found
        """
        now = _now_iso()
        conn = self._conn()
        try:
            conn.execute(
                """
                UPDATE page_generation_states
                SET state = ?, completed_at = ?, error_message = ?
                WHERE run_id = ? AND doc_slug = ?
                """,
                (PageState.SKIPPED.value, now, reason, run_id, doc_slug),
            )
            conn.commit()
            return self.get_page_state(run_id, doc_slug)
        finally:
            conn.close()

    def get_page_state(
        self,
        run_id: str,
        doc_slug: str,
    ) -> PageGenerationState | None:
        """Get state for a specific page.

        Args:
            run_id: Parent run ID
            doc_slug: Document slug

        Returns:
            PageGenerationState or None if not found
        """
        conn = self._conn()
        try:
            row = conn.execute(
                """
                SELECT * FROM page_generation_states
                WHERE run_id = ? AND doc_slug = ?
                """,
                (run_id, doc_slug),
            ).fetchone()

            if not row:
                return None

            return PageGenerationState(
                run_id=row["run_id"],
                doc_slug=row["doc_slug"],
                doc_type=row["doc_type"],
                doc_path=row["doc_path"],
                state=PageState(row["state"]),
                attempts=row["attempts"],
                max_attempts=row["max_attempts"],
                error_message=row["error_message"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
                input_hash=row["input_hash"],
                output_hash=row["output_hash"],
                retry_after=row["retry_after"],
            )
        finally:
            conn.close()

    def get_pages_for_run(
        self,
        run_id: str,
        state: PageState | None = None,
    ) -> list[PageGenerationState]:
        """Get all pages for a run.

        Args:
            run_id: The run ID
            state: Optional state filter

        Returns:
            List of PageGenerationState instances
        """
        conn = self._conn()
        try:
            if state:
                rows = conn.execute(
                    """
                    SELECT * FROM page_generation_states
                    WHERE run_id = ? AND state = ?
                    ORDER BY doc_slug
                    """,
                    (run_id, state.value),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM page_generation_states
                    WHERE run_id = ?
                    ORDER BY doc_slug
                    """,
                    (run_id,),
                ).fetchall()

            return [
                PageGenerationState(
                    run_id=row["run_id"],
                    doc_slug=row["doc_slug"],
                    doc_type=row["doc_type"],
                    doc_path=row["doc_path"],
                    state=PageState(row["state"]),
                    attempts=row["attempts"],
                    max_attempts=row["max_attempts"],
                    error_message=row["error_message"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    input_hash=row["input_hash"],
                    output_hash=row["output_hash"],
                    retry_after=row["retry_after"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_pending_pages(self, run_id: str) -> list[PageGenerationState]:
        """Get pending and retryable pages for a run.

        Args:
            run_id: The run ID

        Returns:
            List of pages that can be processed
        """
        conn = self._conn()
        try:
            rows = conn.execute(
                """
                SELECT * FROM page_generation_states
                WHERE run_id = ? AND state IN (?, ?)
                ORDER BY
                    CASE WHEN state = 'retryable' THEN 0 ELSE 1 END,
                    doc_slug
                """,
                (run_id, PageState.PENDING.value, PageState.RETRYABLE.value),
            ).fetchall()

            return [
                PageGenerationState(
                    run_id=row["run_id"],
                    doc_slug=row["doc_slug"],
                    doc_type=row["doc_type"],
                    doc_path=row["doc_path"],
                    state=PageState(row["state"]),
                    attempts=row["attempts"],
                    max_attempts=row["max_attempts"],
                    error_message=row["error_message"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    input_hash=row["input_hash"],
                    output_hash=row["output_hash"],
                    retry_after=row["retry_after"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def is_run_complete(self, run_id: str) -> bool:
        """Check if a run is complete (all pages processed).

        Args:
            run_id: The run ID

        Returns:
            True if all pages are completed, failed, or skipped
        """
        conn = self._conn()
        try:
            pending = conn.execute(
                """
                SELECT COUNT(*) FROM page_generation_states
                WHERE run_id = ? AND state IN (?, ?)
                """,
                (run_id, PageState.PENDING.value, PageState.RUNNING.value),
            ).fetchone()

            return (pending["COUNT(*)"] or 0) == 0
        finally:
            conn.close()

    # =========================================================================
    # RESUME SUPPORT
    # =========================================================================

    def get_resumable_runs(self) -> list[GenerationRun]:
        """Get runs that can be resumed.

        Returns:
            List of runs in pending/running/retryable state
        """
        return (
            self.list_runs(state=RunState.RUNNING, limit=5)
            + self.list_runs(state=RunState.PENDING, limit=5)
            + self.list_runs(state=RunState.RETRYABLE, limit=5)
        )

    def get_pages_needing_regeneration(
        self,
        run_id: str,
        current_input_hashes: dict[str, str],
    ) -> list[PageGenerationState]:
        """Get pages where input hash changed (needs regeneration).

        Args:
            run_id: The run ID
            current_input_hashes: Dict mapping doc_slug to current input hash

        Returns:
            List of pages that need regeneration
        """
        pages = self.get_pages_for_run(run_id, state=PageState.COMPLETED)
        needs_regen = []

        for page in pages:
            if page.doc_slug in current_input_hashes:
                if page.input_hash != current_input_hashes[page.doc_slug]:
                    needs_regen.append(page)

        return needs_regen


def create_generation_state_machine(root: Path) -> GenerationStateMachine:
    """Create a generation state machine with standard database path.

    Args:
        root: Repository root path

    Returns:
        GenerationStateMachine instance
    """
    db_path = root / ".repo-wiki" / "index" / "generation_state.sqlite3"
    return GenerationStateMachine(db_path)
