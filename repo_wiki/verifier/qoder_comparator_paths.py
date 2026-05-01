"""Comparator path model repair for qoder-like and repo-agent outputs.

This module fixes path model assumptions in the baseline comparator:
- Supports `.qoder/repowiki/zh` path model
- Supports `.repo-agent-eval/<run>/content` path model
- Removes `docs/sections` assumptions
- Prevents false positives from `docs/docs` paths

Phase 29 - Task 29.2: Comparator path-model repair
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


# =============================================================================
# PATH MODEL TYPES
# =============================================================================

class PathModel(Enum):
    """Path model types for different output formats."""
    QODER_LIKE = "qoder_like"      # .qoder/repowiki/zh structure
    REPO_AGENT_EVAL = "repo_agent_eval"  # .repo-agent-eval/<run>/content
    LEGACY_DOCS = "legacy_docs"    # docs/sections structure (deprecated)
    GENERIC = "generic"            # Generic content directory


@dataclass
class PathModelConfig:
    """Configuration for path model detection and comparison."""
    content_subdir: str | None = None  # e.g., "content" for qoder-like
    expected_categories: list[str] = field(default_factory=list)
    skip_patterns: list[str] = field(default_factory=list)  # Patterns to skip in comparison
    preserve_qoder_baseline: bool = True  # Don't modify .qoder baseline paths


# Standard qoder-like taxonomy categories
QODER_TAXONOMY_CATEGORIES = [
    "项目概述",
    "架构设计",
    "核心服务",
    "Python服务",
    "数据模型",
    "API参考",
    "部署运维",
    "开发指南",
    "安全合规",
    "故障排除与维护",
]


# Skip patterns for comparison (common noise patterns)
DEFAULT_SKIP_PATTERNS = [
    r"^docs/docs/",  # AI_API_Atlas has docs/docs which is not a section
    r"^docs/sections/",  # Legacy section paths
    r"^\.git/",
    r"^node_modules/",
    r"^__pycache__/",
]


class PathModelRepair:
    """Repairs path model assumptions in comparison logic."""

    def __init__(self, config: PathModelConfig | None = None) -> None:
        """Initialize path model repair.

        Args:
            config: Optional path model configuration
        """
        self.config = config or PathModelConfig()
        self._skip_regexes = [
            re.compile(p) for p in self.config.skip_patterns or DEFAULT_SKIP_PATTERNS
        ]

    def detect_path_model(self, root: Path) -> PathModel:
        """Detect the path model of a given root.

        Args:
            root: Root directory to check

        Returns:
            Detected PathModel
        """
        root_str = str(root)

        # Check for qoder-like structure
        if ".qoder/repowiki/zh" in root_str:
            return PathModel.QODER_LIKE
        if ".qoder" in root_str and "content" in root_str:
            return PathModel.QODER_LIKE

        # Check for repo-agent eval structure
        if ".repo-agent-eval" in root_str:
            return PathModel.REPO_AGENT_EVAL
        if "content" in root_str and "eval" in root_str:
            return PathModel.REPO_AGENT_EVAL

        # Check for legacy docs structure
        docs_path = root / "docs"
        if docs_path.exists() and (docs_path / "sections").exists():
            return PathModel.LEGACY_DOCS

        # Default to generic
        return PathModel.GENERIC

    def normalize_path(self, path: Path, model: PathModel) -> str:
        """Normalize a path for comparison.

        Args:
            path: Path to normalize
            model: Path model context

        Returns:
            Normalized relative path
        """
        # Convert to string and handle various separators
        path_str = str(path)

        # Remove leading content/ prefix for qoder-like
        if model == PathModel.QODER_LIKE:
            path_str = path_str.replace(".qoder/repowiki/zh/", "")
            path_str = path_str.replace("content/", "")

        # Remove leading .repo-agent-eval/<run>/content/ for repo-agent eval
        elif model == PathModel.REPO_AGENT_EVAL:
            path_str = re.sub(r"\.repo-agent-eval/[^/]+/content/", "", path_str)

        # Remove docs/ prefix for legacy
        elif model == PathModel.LEGACY_DOCS:
            path_str = path_str.replace("docs/sections/", "")
            path_str = path_str.replace("docs/", "")

        # Normalize to forward slashes
        path_str = path_str.replace("\\", "/")

        return path_str.strip("/")

    def should_skip_path(self, path: str) -> bool:
        """Check if a path should be skipped in comparison.

        Args:
            path: Path to check

        Returns:
            True if path should be skipped
        """
        for regex in self._skip_regexes:
            if regex.search(path):
                return True
        return False

    def extract_category(self, path: str) -> str | None:
        """Extract taxonomy category from a path.

        Args:
            path: Normalized path

        Returns:
            Category name or None
        """
        parts = Path(path).parts
        if not parts:
            return None

        # For qoder-like: category is first directory
        for cat in QODER_TAXONOMY_CATEGORIES:
            if cat in parts:
                return cat

        # For generic: use first directory as category
        return parts[0] if len(parts) > 1 else None

    def extract_page_slug(self, path: str) -> str | None:
        """Extract page slug from a path.

        Args:
            path: Normalized path

        Returns:
            Page slug or None
        """
        # Remove extension
        stem = Path(path).stem

        # Remove numeric prefixes (00-, 01-, etc.)
        stem = re.sub(r"^\d+-", "", stem)

        return stem

    def build_comparison_pairs(
        self,
        target_root: Path,
        baseline_root: Path | None,
    ) -> list[tuple[str, str | None, str | None]]:
        """Build pairs of paths for comparison.

        Args:
            target_root: Target directory
            baseline_root: Baseline directory (optional)

        Returns:
            List of (normalized_path, target_exists, baseline_exists)
        """
        target_model = self.detect_path_model(target_root)

        pairs = []

        # Get all markdown files from target
        target_files = self._collect_markdown_files(target_root, target_model)

        if baseline_root:
            baseline_model = self.detect_path_model(baseline_root)
            baseline_files = self._collect_markdown_files(baseline_root, baseline_model)

            # Build pairs
            all_paths = set(target_files.keys()) | set(baseline_files.keys())

            for path in sorted(all_paths):
                if self.should_skip_path(path):
                    continue

                target_exists = path in target_files
                baseline_exists = path in baseline_files

                pairs.append((path, target_exists, baseline_exists))
        else:
            # Target only
            for path, _ in target_files.items():
                if self.should_skip_path(path):
                    continue
                pairs.append((path, True, False))

        return pairs

    def _collect_markdown_files(
        self,
        root: Path,
        model: PathModel,
    ) -> dict[str, Path]:
        """Collect all markdown files from a root.

        Args:
            root: Root directory
            model: Path model

        Returns:
            Dictionary mapping normalized paths to actual paths
        """
        files = {}

        # Find content directory
        content_dirs = self._find_content_dirs(root, model)

        for content_dir in content_dirs:
            if not content_dir.exists():
                continue

            for md_file in content_dir.rglob("*.md"):
                # Compute normalized path
                try:
                    rel_path = md_file.relative_to(content_dir)
                    normalized = self.normalize_path(str(rel_path), model)

                    if normalized and not self.should_skip_path(normalized):
                        files[normalized] = md_file
                except ValueError:
                    # File is not relative to content_dir, skip
                    continue

        return files

    def _find_content_dirs(self, root: Path, model: PathModel) -> list[Path]:
        """Find content directories based on path model.

        Args:
            root: Root directory
            model: Path model

        Returns:
            List of content directories
        """
        candidates = []

        if model == PathModel.QODER_LIKE:
            # .qoder/repowiki/zh/content or .qoder/repowiki/zh
            for qoder_dir in root.rglob("content"):
                if ".qoder" in str(qoder_dir):
                    candidates.append(qoder_dir)
            if not candidates:
                # Maybe directly in .qoder/repowiki/zh
                zh_dir = root / ".qoder" / "repowiki" / "zh"
                if zh_dir.exists():
                    candidates.append(zh_dir)

        elif model == PathModel.REPO_AGENT_EVAL:
            # .repo-agent-eval/<run>/content
            for eval_dir in root.rglob("content"):
                if ".repo-agent-eval" in str(eval_dir):
                    candidates.append(eval_dir)

        elif model == PathModel.LEGACY_DOCS:
            # docs/sections
            sections_dir = root / "docs" / "sections"
            if sections_dir.exists():
                candidates.append(sections_dir)

        else:
            # Generic: look for any directory containing markdown files
            for md_file in root.rglob("*.md"):
                dir_path = md_file.parent
                if dir_path not in candidates:
                    candidates.append(dir_path)

        return candidates if candidates else [root]


# =============================================================================
# REPAIRD COMPARATOR INTEGRATION
# =============================================================================

class RepairedBaselineComparator:
    """Baseline comparator with repaired path model assumptions."""

    def __init__(
        self,
        target_root: Path,
        baseline_root: Path | None = None,
        config: PathModelConfig | None = None,
    ) -> None:
        """Initialize repaired comparator.

        Args:
            target_root: Target directory
            baseline_root: Baseline directory (optional)
            config: Path model configuration
        """
        self.target_root = Path(target_root)
        self.baseline_root = Path(baseline_root) if baseline_root else None
        self.path_repair = PathModelRepair(config)

    def compare(self) -> dict[str, Any]:
        """Perform comparison with repaired path model.

        Returns:
            Comparison results dictionary
        """
        target_model = self.path_repair.detect_path_model(self.target_root)

        # Build comparison pairs
        pairs = self.path_repair.build_comparison_pairs(
            self.target_root,
            self.baseline_root,
        )

        # Classify results
        in_both = []
        target_only = []
        baseline_only = []

        for path, target_exists, baseline_exists in pairs:
            if target_exists and baseline_exists:
                in_both.append(path)
            elif target_exists:
                target_only.append(path)
            elif baseline_exists:
                baseline_only.append(path)

        return {
            "target_root": str(self.target_root),
            "baseline_root": str(self.baseline_root) if self.baseline_root else None,
            "target_model": target_model.value,
            "total_files": len(pairs),
            "in_both": in_both,
            "target_only": target_only,
            "baseline_only": baseline_only,
            "symmetric_diff": len(target_only) + len(baseline_only),
        }


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_repaired_comparator(
    target_root: Path,
    baseline_root: Path | None = None,
) -> RepairedBaselineComparator:
    """Create a repaired baseline comparator.

    Args:
        target_root: Target directory
        baseline_root: Baseline directory (optional)

    Returns:
        RepairedBaselineComparator instance
    """
    return RepairedBaselineComparator(target_root, baseline_root)


def detect_and_normalize_path(
    path: Path,
    skip_patterns: list[str] | None = None,
) -> tuple[str, PathModel]:
    """Detect path model and normalize path.

    Args:
        path: Path to analyze
        skip_patterns: Optional skip patterns

    Returns:
        Tuple of (normalized_path, detected_model)
    """
    config = PathModelConfig(skip_patterns=skip_patterns or DEFAULT_SKIP_PATTERNS)
    repair = PathModelRepair(config)
    model = repair.detect_path_model(path)
    normalized = repair.normalize_path(path, model)
    return normalized, model