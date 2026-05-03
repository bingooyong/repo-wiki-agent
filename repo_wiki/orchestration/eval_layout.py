"""Isolated evaluation output layout policy and manifest schema for target repos.

This module provides:
- EvalOutputProfile: Configuration profiles for eval output destinations
- EvalManifest: Manifest schema describing generated eval artifacts
- Path safety validation: Ensures eval outputs don't pollute baseline directories
- Manifest generator: Creates machine-readable manifests for tool consumption

The `.repo-agent-eval` directory is the isolated output root for evaluation results.
It MUST NOT overlap with baseline directories like `.repo-wiki`, `docs/`, or `ai/`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from repo_wiki.core.errors import ErrorCategory, RepoWikiError

# =============================================================================
# EVAL OUTPUT PROFILES (Configuration)
# =============================================================================

PROTECTED_DIRS: frozenset[str] = frozenset(
    [
        "docs/",
        ".repo-wiki/",
        "ai/",
        ".apm/",
        ".claude/",
        ".codex/",
        ".opencode/",
        "scripts/",
        "templates/",
        ".github/",
        ".vscode/",
        "node_modules/",
        "dist/",
        "build/",
        "coverage/",
        ".venv/",
        "venv/",
        ".qoder/",
    ]
)


class EvalOutputProfile(BaseModel):
    """Configuration profile for eval output destination.

    Attributes:
        name: Profile name (e.g., 'default', 'ci', 'local', 'qoder-like')
        root: Root directory for eval outputs (relative to project root or absolute)
        create_subdirs: Whether to create timestamped run subdirectories
        content_subdir: Subdirectory for content outputs (e.g., 'content' for qoder-like)
        max_manifest_size_kb: Maximum manifest file size in KB
    """

    name: str = "default"
    root: str = ".repo-agent-eval"
    create_subdirs: bool = True
    content_subdir: str | None = None
    max_manifest_size_kb: int = 512

    @field_validator("root")
    @classmethod
    def validate_root_not_protected(cls, v: str) -> str:
        """Reject output roots that overlap with protected directories."""
        normalized = v.rstrip("/")
        for protected in PROTECTED_DIRS:
            protected_stripped = protected.rstrip("/")
            if normalized == protected_stripped:
                raise ValueError(
                    f"Eval output root '{v}' overlaps with protected directory '{protected}'. "
                    f"Eval outputs must be isolated from baseline directories."
                )
            if normalized.startswith(protected_stripped + "/"):
                raise ValueError(
                    f"Eval output root '{v}' is inside protected directory '{protected}'. "
                    f"Eval outputs must be isolated from baseline directories."
                )
        return v

    def get_run_dir(self, run_id: str | None = None) -> Path:
        """Get the run directory for this profile.

        If create_subdirs is True and run_id is provided, creates:
            .repo-agent-eval/<run_id>/
        Otherwise returns the root directory.
        """
        if self.create_subdirs and run_id:
            return Path(self.root) / run_id
        return Path(self.root)

    def get_content_dir(self, run_id: str | None = None) -> Path:
        """Get the content directory for this profile.

        For qoder-like profile with content_subdir, returns:
            .repo-agent-eval/<run_id>/content/
        """
        base = self.get_run_dir(run_id)
        if self.content_subdir:
            return base / self.content_subdir
        return base

    def resolve_root(self, repo_root: Path | str) -> EvalOutputProfile:
        """Return a profile whose relative root is resolved against repo_root."""
        root_path = Path(self.root)
        if root_path.is_absolute():
            return self
        return self.model_copy(update={"root": str(Path(repo_root).resolve() / root_path)})

    def validate_path_safety(self, output_path: str) -> tuple[bool, str]:
        """Validate that an output path is safe (doesn't escape eval root).

        Args:
            output_path: The intended output path relative to eval root

        Returns:
            (is_safe, reason) tuple
        """
        # Disallow absolute paths that point outside eval root
        if output_path.startswith("/"):
            return False, f"Absolute path '{output_path}' not allowed in eval output"

        # Disallow path traversal attempts - resolve the full target path
        eval_root = Path(self.root).resolve()
        # Build target path by joining output_path to eval root
        target_path = (eval_root / output_path).resolve()

        try:
            target_path.relative_to(eval_root)
        except ValueError:
            return False, f"Path '{output_path}' escapes eval root boundary"

        return True, "Path is safe"


# =============================================================================
# EVAL OUTPUT PROFILES REGISTRY
# =============================================================================

EVAL_PROFILES: dict[str, EvalOutputProfile] = {
    "default": EvalOutputProfile(name="default", root=".repo-agent-eval", create_subdirs=True),
    "ci": EvalOutputProfile(name="ci", root=".repo-agent-eval-ci", create_subdirs=False),
    "local": EvalOutputProfile(name="local", root="eval-output", create_subdirs=True),
    "qoder-like": EvalOutputProfile(
        name="qoder-like", root=".repo-agent-eval", create_subdirs=True, content_subdir="content"
    ),
}


def get_eval_profile(name: str) -> EvalOutputProfile:
    """Get an eval profile by name, or return default if not found."""
    return EVAL_PROFILES.get(name, EVAL_PROFILES["default"])


def register_eval_profile(profile: EvalOutputProfile) -> None:
    """Register or update an eval profile."""
    EVAL_PROFILES[profile.name] = profile


# =============================================================================
# EVAL MANIFEST SCHEMA
# =============================================================================


class EvalManifestFile(BaseModel):
    """A file entry in the eval manifest."""

    path: str = Field(description="Relative path from eval root")
    size_bytes: int = Field(description="File size in bytes")
    content_type: str = Field(default="text/markdown", description="MIME type hint")
    hash_sha256: str = Field(description="SHA256 hash of file content")


class EvalManifestEvidence(BaseModel):
    """Evidence file entry in the eval manifest."""

    path: str = Field(description="Relative path to evidence file")
    evidence_type: str = Field(description="Type: 'verify-result', 'diff', 'report'")
    description: str = Field(description="Human-readable description")
    created_at: str = Field(description="ISO timestamp")


class EvalManifest(BaseModel):
    """Manifest schema for isolated eval outputs.

    This manifest is written to `.repo-agent-eval/<run_id>/manifest.json` and
    describes all generated artifacts for human and tool consumption.
    """

    version: str = Field(default="1.0", description="Manifest schema version")
    run_id: str = Field(description="Unique run identifier")
    generated_at: str = Field(description="ISO timestamp of manifest creation")
    profile: str = Field(description="Eval profile name used")
    target_repo: str = Field(description="Target repository path")
    eval_root: str = Field(description="Root directory for this eval run")

    # Git commit information
    target_git_commit: str | None = Field(
        default=None, description="Git commit hash of target repository at generation time"
    )
    wiki_git_commit: str | None = Field(
        default=None, description="Git commit hash where wiki content was generated from"
    )
    target_head_before: str | None = Field(
        default=None, description="Full target repository HEAD before generation"
    )
    target_head_after: str | None = Field(
        default=None, description="Full target repository HEAD after generation"
    )
    target_dirty: bool = Field(
        default=False,
        description="Whether target repository had uncommitted changes during generation",
    )
    target_revision_source: str = Field(
        default="git", description="How target_git_commit was resolved: git or hash-fallback"
    )
    wiki_revision_source: str = Field(
        default="git", description="How wiki_git_commit was resolved: git or hash-fallback"
    )
    stale_detection: dict[str, Any] = Field(
        default_factory=dict,
        description="Stale detection metadata derived from revision comparison",
    )

    # Directory structure
    content_root: str | None = Field(
        default=None, description="Root directory for generated content files"
    )
    runtime_root: str | None = Field(
        default=None, description="Root directory for runtime files (cache, index, etc.)"
    )

    # Navigation
    navigation_tree: list[dict[str, Any]] = Field(
        default_factory=list, description="Hierarchical navigation tree structure"
    )

    # Page registry
    page_registry: list[dict[str, Any]] = Field(
        default_factory=list, description="Registry of all generated pages with metadata"
    )

    files: list[EvalManifestFile] = Field(
        default_factory=list, description="All generated output files"
    )
    evidence: list[EvalManifestEvidence] = Field(
        default_factory=list, description="Evidence files (verify results, diffs, reports)"
    )

    stats: dict[str, Any] = Field(default_factory=dict, description="Statistics about the eval run")

    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


# =============================================================================
# MANIFEST GENERATOR
# =============================================================================

import hashlib


def compute_file_hash(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    if not path.exists():
        return ""
    content = path.read_bytes()
    return hashlib.sha256(content).hexdigest()


def guess_content_type(path: Path) -> str:
    """Guess content type based on file extension."""
    suffix = path.suffix.lower()
    type_map: dict[str, str] = {
        ".md": "text/markdown",
        ".json": "application/json",
        ".yaml": "text/yaml",
        ".yml": "text/yaml",
        ".html": "text/html",
        ".txt": "text/plain",
        ".sqlite": "application/x-sqlite3",
        ".db": "application/x-sqlite3",
    }
    return type_map.get(suffix, "application/octet-stream")


def generate_manifest(
    run_id: str,
    profile: EvalOutputProfile,
    target_repo: str,
    output_dir: Path,
    evidence_files: list[dict[str, str]] | None = None,
    stats: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    navigation_tree: list[dict[str, Any]] | None = None,
    page_registry: list[dict[str, Any]] | None = None,
    target_git_commit: str | None = None,
    wiki_git_commit: str | None = None,
    target_head_before: str | None = None,
    target_head_after: str | None = None,
    target_dirty: bool = False,
    target_revision_source: str = "git",
    wiki_revision_source: str = "git",
    content_root: str | None = None,
    runtime_root: str | None = None,
) -> EvalManifest:
    """Generate an eval manifest by scanning the output directory.

    Args:
        run_id: Unique run identifier
        profile: Eval profile used
        target_repo: Target repository path
        output_dir: Directory to scan for outputs
        evidence_files: Optional list of evidence file descriptors
        stats: Optional statistics dictionary
        metadata: Optional metadata dictionary
        navigation_tree: Optional hierarchical navigation tree
        page_registry: Optional registry of generated pages
        target_git_commit: Optional git commit hash of target repo
        wiki_git_commit: Optional git commit hash of wiki content
        content_root: Optional content root directory path
        runtime_root: Optional runtime root directory path

    Returns:
        Populated EvalManifest instance
    """
    files: list[EvalManifestFile] = []
    evidence: list[EvalManifestEvidence] = []

    # Scan output directory for files
    if output_dir.exists():
        for path in sorted(output_dir.rglob("*")):
            if path.is_file():
                rel_path = str(path.relative_to(output_dir))
                files.append(
                    EvalManifestFile(
                        path=rel_path,
                        size_bytes=path.stat().st_size,
                        content_type=guess_content_type(path),
                        hash_sha256=compute_file_hash(path),
                    )
                )

    # Add evidence files
    if evidence_files:
        for ev in evidence_files:
            evidence.append(
                EvalManifestEvidence(
                    path=ev.get("path", ""),
                    evidence_type=ev.get("type", "unknown"),
                    description=ev.get("description", ""),
                    created_at=ev.get("created_at", ""),
                )
            )

    # Resolve content_root from profile if not provided
    if content_root is None:
        content_root = str(profile.get_content_dir(run_id))

    # Resolve runtime_root if not provided
    if runtime_root is None:
        runtime_root = str(Path(target_repo) / ".repo-wiki")

    stale_detection = {
        "strategy": "git-or-hash",
        "target_revision_source": target_revision_source,
        "wiki_revision_source": wiki_revision_source,
        "is_stale": bool(
            target_git_commit and wiki_git_commit and target_git_commit != wiki_git_commit
        ),
    }

    return EvalManifest(
        version="1.0",
        run_id=run_id,
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        profile=profile.name,
        target_repo=target_repo,
        eval_root=str(output_dir),
        target_git_commit=target_git_commit,
        wiki_git_commit=wiki_git_commit,
        target_head_before=target_head_before,
        target_head_after=target_head_after,
        target_dirty=target_dirty,
        target_revision_source=target_revision_source,
        wiki_revision_source=wiki_revision_source,
        stale_detection=stale_detection,
        content_root=content_root,
        runtime_root=runtime_root,
        navigation_tree=navigation_tree or [],
        page_registry=page_registry or [],
        files=files,
        evidence=evidence,
        stats=stats or {},
        metadata=metadata or {},
    )


def write_manifest(manifest: EvalManifest, output_dir: Path) -> Path:
    """Write manifest to JSON file.

    Args:
        manifest: The manifest to write
        output_dir: Directory to write manifest into

    Returns:
        Path to the written manifest file
    """
    import repo_wiki.generator.io as io

    manifest_path = output_dir / "manifest.json"
    io.write_json(manifest_path, json.loads(manifest.model_dump_json()))
    return manifest_path


# =============================================================================
# GIT COMMIT DETECTION
# =============================================================================

import subprocess


def get_git_commit(repo_path: Path | str) -> str | None:
    """Get the current git commit hash for a repository.

    Args:
        repo_path: Path to the repository

    Returns:
        Git commit hash (first 12 characters) or None if not a git repo
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            commit = result.stdout.strip()
            return commit[:12] if commit else None
    except Exception:
        pass
    return None


def get_git_commit_full(repo_path: Path | str) -> str | None:
    """Get the full git commit hash for a repository.

    Args:
        repo_path: Path to the repository

    Returns:
        Full git commit hash or None if not a git repo
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def compute_revision_fallback(path: Path | str) -> str:
    """Compute deterministic hash fallback when git metadata is unavailable."""
    candidate = Path(path)
    hasher = hashlib.sha256()
    if candidate.is_file():
        hasher.update(candidate.read_bytes())
        return hasher.hexdigest()

    if not candidate.exists():
        hasher.update(str(candidate).encode("utf-8"))
        return hasher.hexdigest()

    ignored_roots = {
        ".git",
        ".repo-agent-eval",
        ".qoder",
        ".repo-wiki",
        ".venv",
        "node_modules",
        "dist",
        "build",
    }

    for item in sorted(candidate.rglob("*")):
        try:
            rel = item.relative_to(candidate).as_posix()
        except ValueError:
            rel = str(item)
        if not rel:
            continue
        root_part = rel.split("/", 1)[0]
        if root_part in ignored_roots:
            continue
        hasher.update(rel.encode("utf-8"))
        if item.is_file():
            try:
                hasher.update(item.read_bytes())
            except OSError:
                hasher.update(str(item.stat().st_size).encode("utf-8"))
    return hasher.hexdigest()


def resolve_revision_with_fallback(path: Path | str) -> tuple[str, str]:
    """Resolve revision from git, falling back to deterministic hash."""
    commit = get_git_commit_full(path) or get_git_commit(path)
    if commit:
        return commit, "git"
    return compute_revision_fallback(path), "hash-fallback"


def is_git_dirty(repo_path: Path | str) -> bool:
    """Return True when the repository has uncommitted changes or untracked files."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return bool(result.stdout.strip())
    except Exception:
        pass
    return False


def get_git_branch(repo_path: Path | str) -> str | None:
    """Get the current git branch name.

    Args:
        repo_path: Path to the repository

    Returns:
        Branch name or None if not a git repo or detached HEAD
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            return branch if branch != "HEAD" else None
    except Exception:
        pass
    return None


def is_git_repository(repo_path: Path | str) -> bool:
    """Check if a path is a git repository.

    Args:
        repo_path: Path to check

    Returns:
        True if path is inside a git repository
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except Exception:
        return False


# =============================================================================
# PATH SAFETY VALIDATION
# =============================================================================


def validate_eval_root_safety(root: Path | str) -> tuple[bool, str, list[str]]:
    """Validate that an eval root is safe (doesn't overlap with protected dirs).

    Args:
        root: The eval root path to validate

    Returns:
        (is_safe, reason, list of warnings)
    """
    warnings: list[str] = []
    root_str = str(root).rstrip("/")
    root_path = Path(root).resolve()

    # Check for direct overlap with protected directories
    for protected in sorted(PROTECTED_DIRS):
        protected_path = Path(protected).resolve()
        try:
            root_path.relative_to(protected_path)
            return False, f"Eval root '{root}' is inside protected directory '{protected}'", []
        except ValueError:
            pass

    # Check if protected dir is inside eval root
    for protected in sorted(PROTECTED_DIRS):
        protected_path = Path(protected).resolve()
        try:
            protected_path.relative_to(root_path)
            warnings.append(f"Protected directory '{protected}' is inside eval root '{root}'")
        except ValueError:
            pass

    return True, "Eval root is safe", warnings


def reject_unsafe_output_root(root: Path | str) -> None:
    """Reject unsafe eval output roots with clear error messages.

    Raises:
        RepoWikiError: If the root overlaps with protected directories
    """
    is_safe, reason, _ = validate_eval_root_safety(root)
    if not is_safe:
        raise RepoWikiError(
            f"Unsafe eval output root: {reason}",
            ErrorCategory.CONFIG,
            {"root": str(root), "protected_dirs": sorted(PROTECTED_DIRS)},
        )


# =============================================================================
# OUTPUT LAYOUT CONTRACT
# =============================================================================

EVAL_OUTPUT_LAYOUT_CONTRACT: dict[str, Any] = {
    "version": "1.0",
    "description": "Isolated eval output layout for repo-agent evaluation runs",
    "root": ".repo-agent-eval",
    "structure": {
        "<run_id>/": {
            "description": "Timestamped run directory (when create_subdirs=true)",
            "files": {
                "manifest.json": "Machine-readable manifest of all outputs",
                "verify-result.json": "Verification results if verify was run",
                "*.md": "Generated documentation outputs",
                "*.sqlite": "Runtime database snapshot",
            },
        },
        "latest/": {
            "description": "Symlink or copy of most recent run (optional)",
        },
    },
    "protected_directories": sorted(PROTECTED_DIRS),
    "boundary_rules": [
        ".repo-agent-eval/ must NOT be inside .repo-wiki/, docs/, ai/, or any protected dir",
        "Baseline outputs (.repo-wiki/, docs/, ai/) must NOT be inside .repo-agent-eval/",
        "Eval outputs should be completely isolated from governance outputs",
    ],
}


def get_eval_output_layout_contract() -> dict[str, Any]:
    """Return the eval output layout contract as a dictionary."""
    return EVAL_OUTPUT_LAYOUT_CONTRACT
