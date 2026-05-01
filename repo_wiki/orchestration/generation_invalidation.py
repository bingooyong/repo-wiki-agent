"""Generation-aware page invalidation with git diff and hash fallback.

This module integrates:
- Git diff analysis for changed files
- Hash-based change detection when git unavailable
- Page-level invalidation based on generation state
- Scheduler integration for targeted regeneration

Phase 28 - Task 28.4: Page-level invalidation from git diff and hash fallback

Key features:
- Git diff parsing and file-to-page mapping
- Hash fallback for non-git repos
- Integration with generation state machine
- Impact analysis for selective regeneration
"""

from __future__ import annotations

import hashlib
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from repo_wiki.orchestration.generation_state import (
    GenerationStateMachine,
    PageGenerationState,
    PageState,
)


# =============================================================================
# GIT DIFF ANALYSIS
# =============================================================================

@dataclass
class GitDiffResult:
    """Result of git diff analysis."""
    changed_files: list[str]
    deleted_files: list[str]
    renamed_files: dict[str, str]  # old_path -> new_path
    commit_range: tuple[str, str] | None
    is_clean: bool = True


def get_git_diff(
    root: Path,
    ref: str | None = None,
    file_filter: list[str] | None = None,
) -> GitDiffResult:
    """Get git diff for a repository.

    Args:
        root: Repository root
        ref: Git ref to diff against (default: HEAD)
        file_filter: Only include files matching these prefixes

    Returns:
        GitDiffResult with changed, deleted, and renamed files
    """
    try:
        # Get diff against ref or HEAD
        base_ref = ref or "HEAD"

        # Get list of changed files
        result = subprocess.run(
            ["git", "diff", "--name-status", base_ref],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return GitDiffResult(
                changed_files=[],
                deleted_files=[],
                renamed_files={},
                commit_range=None,
                is_clean=True,
            )

        changed_files = []
        deleted_files = []
        renamed_files = {}

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue

            status = parts[0]
            path = parts[1]

            # Apply filter
            if file_filter and not any(path.startswith(f) for f in file_filter):
                continue

            if status == "D":
                deleted_files.append(path)
            elif status == "R":
                # Renamed: parts[1]=old, parts[2]=new
                if len(parts) >= 3:
                    renamed_files[parts[1]] = parts[2]
            elif status.startswith("M") or status == "A":
                changed_files.append(path)

        return GitDiffResult(
            changed_files=changed_files,
            deleted_files=deleted_files,
            renamed_files=renamed_files,
            commit_range=(base_ref, "working tree"),
            is_clean=bool(changed_files or deleted_files or renamed_files),
        )

    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return GitDiffResult(
            changed_files=[],
            deleted_files=[],
            renamed_files={},
            commit_range=None,
            is_clean=True,
        )


def get_file_hash(file_path: Path) -> str | None:
    """Get MD5 hash of a file.

    Args:
        file_path: Path to file

    Returns:
        Hex digest of file hash, or None if file doesn't exist
    """
    if not file_path.exists():
        return None

    try:
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return None


def get_directory_hashes(
    root: Path,
    relative_to: Path | str,
    patterns: list[str] | None = None,
) -> dict[str, str]:
    """Get hashes of all files in a directory tree.

    Args:
        root: Repository root
        relative_to: Base directory for relative paths (relative to root, or absolute)
        patterns: File patterns to include (e.g., ["*.py", "*.md"])

    Returns:
        Dictionary mapping relative paths to hashes
    """
    hashes = {}
    # Handle both absolute paths and relative paths
    if Path(relative_to).is_absolute():
        base = Path(relative_to)
    else:
        base = root / relative_to

    if not base.exists():
        return hashes

    for file_path in base.rglob("*"):
        if not file_path.is_file():
            continue

        rel_path = str(file_path.relative_to(base))

        # Apply pattern filter
        if patterns:
            if not any(file_path.match(p) for p in patterns):
                continue

        file_hash = get_file_hash(file_path)
        if file_hash:
            hashes[rel_path] = file_hash

    return hashes


# =============================================================================
# HASH-BASED CHANGE DETECTION
# =============================================================================

@dataclass
class HashChangeResult:
    """Result of hash-based change detection."""
    changed_files: list[str]
    deleted_files: list[str]
    new_files: list[str]
    is_clean: bool


class HashBasedChangeDetector:
    """Detects file changes using content hashes when git is unavailable."""

    def __init__(
        self,
        root: Path,
        baseline_hashes: dict[str, str] | None = None,
    ) -> None:
        """Initialize change detector.

        Args:
            root: Repository root
            baseline_hashes: Previous file hashes for comparison
        """
        self.root = root
        self.baseline_hashes = baseline_hashes or {}

    def compute_current_hashes(
        self,
        patterns: list[str] | None = None,
    ) -> dict[str, str]:
        """Compute current file hashes.

        Args:
            patterns: File patterns to include

        Returns:
            Dictionary of relative paths to hashes
        """
        return get_directory_hashes(self.root, self.root, patterns)

    def detect_changes(
        self,
        current_hashes: dict[str, str] | None = None,
    ) -> HashChangeResult:
        """Detect changes compared to baseline.

        Args:
            current_hashes: Current hashes (computed if None)

        Returns:
            HashChangeResult with changed files
        """
        if current_hashes is None:
            current_hashes = self.compute_current_hashes()

        baseline = self.baseline_hashes
        current = current_hashes

        changed = []
        deleted = []
        new = []

        # Find changed and new files
        for path, hash_val in current.items():
            if path not in baseline:
                new.append(path)
            elif baseline[path] != hash_val:
                changed.append(path)

        # Find deleted files
        for path in baseline:
            if path not in current:
                deleted.append(path)

        return HashChangeResult(
            changed_files=sorted(changed),
            deleted_files=sorted(deleted),
            new_files=sorted(new),
            is_clean=not (changed or deleted or new),
        )


# =============================================================================
# PAGE INVALIDATION INTEGRATION
# =============================================================================

class GenerationAwareInvalidator:
    """Invalidates pages in generation state machine based on file changes."""

    def __init__(
        self,
        state_machine: GenerationStateMachine,
        root: Path,
    ) -> None:
        """Initialize invalidator.

        Args:
            state_machine: Generation state machine
            root: Repository root
        """
        self.state_machine = state_machine
        self.root = root

    def invalidate_from_git_diff(
        self,
        run_id: str,
        ref: str | None = None,
        file_filter: list[str] | None = None,
    ) -> tuple[list[str], list[str]]:
        """Invalidate pages based on git diff.

        Args:
            run_id: Generation run ID
            ref: Git ref to diff against
            file_filter: Only invalidate pages affected by files with these prefixes

        Returns:
            Tuple of (invalidated_slugs, skipped_slugs)
        """
        diff = get_git_diff(self.root, ref, file_filter)

        if diff.is_clean:
            return [], []

        # Map files to doc_slugs
        all_affected = set()

        for changed_file in diff.changed_files:
            affected = self._map_file_to_pages(changed_file)
            all_affected.update(affected)

        for deleted_file in diff.deleted_files:
            affected = self._map_file_to_pages(deleted_file)
            all_affected.update(affected)

        # Mark affected pages for regeneration
        invalidated = []
        skipped = []

        for doc_slug in all_affected:
            # Only invalidate pages that are in PENDING or COMPLETED state
            # (not already running or failed)
            page_state = self.state_machine.get_page_state(run_id, doc_slug)
            if page_state and page_state.state in (PageState.PENDING, PageState.COMPLETED):
                self.state_machine.skip_page(run_id, doc_slug, "Regenerated due to file change")
                invalidated.append(doc_slug)
            else:
                skipped.append(doc_slug)

        return invalidated, skipped

    def invalidate_from_hash_comparison(
        self,
        run_id: str,
        baseline_hashes: dict[str, str],
        current_hashes: dict[str, str] | None = None,
    ) -> tuple[list[str], list[str]]:
        """Invalidate pages based on hash comparison.

        Args:
            run_id: Generation run ID
            baseline_hashes: Baseline file hashes
            current_hashes: Current hashes (computed if None)

        Returns:
            Tuple of (invalidated_slugs, skipped_slugs)
        """
        detector = HashBasedChangeDetector(self.root, baseline_hashes)
        changes = detector.detect_changes(current_hashes)

        if changes.is_clean:
            return [], []

        all_affected = set()

        for changed_file in changes.changed_files:
            affected = self._map_file_to_pages(changed_file)
            all_affected.update(affected)

        for deleted_file in changes.deleted_files:
            affected = self._map_file_to_pages(deleted_file)
            all_affected.update(affected)

        invalidated = []
        skipped = []

        for doc_slug in all_affected:
            page_state = self.state_machine.get_page_state(run_id, doc_slug)
            if page_state and page_state.state in (PageState.PENDING, PageState.COMPLETED):
                self.state_machine.skip_page(run_id, doc_slug, "Regenerated due to content change")
                invalidated.append(doc_slug)
            else:
                skipped.append(doc_slug)

        return invalidated, skipped

    def _map_file_to_pages(self, file_path: str) -> list[str]:
        """Map a file path to affected doc_slugs.

        Args:
            file_path: Changed file path

        Returns:
            List of affected doc_slug values
        """
        # Simple mapping: derive doc_slug from file path
        # docs/00-overview.md -> 00-overview
        # docs/architecture.md -> 01-architecture
        # modules/my-service/index.md -> my-service

        affected = []
        path_str = str(file_path)

        # Map docs/*.md files to their slug
        if path_str.startswith("docs/"):
            if path_str.endswith(".md"):
                # docs/00-overview.md -> 00-overview
                stem = Path(path_str).stem
                affected.append(stem)

        # Map modules/* to module slugs
        if "modules/" in path_str or "services/" in path_str:
            parts = Path(path_str).parts
            if len(parts) >= 2:
                module_name = parts[1]  # modules/<name>/...
                affected.append(module_name)

        return affected

    def get_page_impact_summary(
        self,
        run_id: str,
    ) -> dict[str, Any]:
        """Get a summary of page impact for a run.

        Args:
            run_id: Generation run ID

        Returns:
            Dictionary with impact statistics
        """
        pages = self.state_machine.get_pages_for_run(run_id)

        by_state: dict[str, int] = {}
        for page in pages:
            state = page.state.value
            by_state[state] = by_state.get(state, 0) + 1

        return {
            "run_id": run_id,
            "total_pages": len(pages),
            "by_state": by_state,
            "pending_count": by_state.get("pending", 0),
            "completed_count": by_state.get("completed", 0),
            "running_count": by_state.get("running", 0),
            "failed_count": by_state.get("failed", 0),
            "skipped_count": by_state.get("skipped", 0),
        }


def create_generation_invalidator(
    state_machine: GenerationStateMachine,
    root: Path,
) -> GenerationAwareInvalidator:
    """Create a generation-aware invalidator.

    Args:
        state_machine: Generation state machine
        root: Repository root

    Returns:
        GenerationAwareInvalidator instance
    """
    return GenerationAwareInvalidator(state_machine, root)
