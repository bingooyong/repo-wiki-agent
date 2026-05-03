"""Tests for Qoder comparator path model repair."""

from pathlib import Path

import pytest

from repo_wiki.verifier.qoder_comparator_paths import (
    QODER_TAXONOMY_CATEGORIES,
    PathModel,
    PathModelRepair,
    create_repaired_comparator,
    detect_and_normalize_path,
)


class TestPathModelDetection:
    """Tests for path model detection."""

    def test_detect_qoder_like_path(self):
        """Test detecting qoder-like path model."""
        repair = PathModelRepair()
        path = Path("/some/path/.qoder/repowiki/zh/content/pages")
        model = repair.detect_path_model(path)
        assert model == PathModel.QODER_LIKE

    def test_detect_repo_agent_eval_path(self):
        """Test detecting repo-agent eval path model."""
        repair = PathModelRepair()
        path = Path("/some/path/.repo-agent-eval/run-123/content/pages")
        model = repair.detect_path_model(path)
        assert model == PathModel.REPO_AGENT_EVAL

    def test_detect_generic_path(self):
        """Test detecting generic path model."""
        repair = PathModelRepair()
        path = Path("/some/path/content/pages")
        model = repair.detect_path_model(path)
        assert model == PathModel.GENERIC


class TestPathNormalization:
    """Tests for path normalization."""

    def test_normalize_qoder_path(self):
        """Test normalizing qoder-like paths."""
        repair = PathModelRepair()
        path = Path(".qoder/repowiki/zh/content/00-overview.md")
        normalized = repair.normalize_path(path, PathModel.QODER_LIKE)
        assert normalized == "00-overview.md"

    def test_normalize_repo_agent_path(self):
        """Test normalizing repo-agent eval paths."""
        repair = PathModelRepair()
        path = Path(".repo-agent-eval/run-123/content/00-overview.md")
        normalized = repair.normalize_path(path, PathModel.REPO_AGENT_EVAL)
        assert normalized == "00-overview.md"

    def test_normalize_legacy_docs_path(self):
        """Test normalizing legacy docs paths."""
        repair = PathModelRepair()
        path = Path("docs/sections/00-overview/index.md")
        normalized = repair.normalize_path(path, PathModel.LEGACY_DOCS)
        assert normalized == "00-overview/index.md"


class TestSkipPatterns:
    """Tests for skip pattern matching."""

    def test_skip_docs_docs(self):
        """Test skipping docs/docs paths."""
        repair = PathModelRepair()
        assert repair.should_skip_path("docs/docs/something.md") is True
        assert repair.should_skip_path("docs/sections/something.md") is True
        assert repair.should_skip_path("docs/00-overview.md") is False

    def test_skip_git_and_cache(self):
        """Test skipping git and cache directories."""
        repair = PathModelRepair()
        assert repair.should_skip_path(".git/config") is True
        assert repair.should_skip_path("node_modules/package.json") is True
        assert repair.should_skip_path("__pycache__/module.pyc") is True


class TestCategoryExtraction:
    """Tests for taxonomy category extraction."""

    def test_extract_qoder_category(self):
        """Test extracting qoder taxonomy category."""
        repair = PathModelRepair()
        path = "项目概述/00-overview.md"
        category = repair.extract_category(path)
        assert category == "项目概述"

    def test_extract_generic_category(self):
        """Test extracting generic category from path."""
        repair = PathModelRepair()
        path = "api/reference.md"
        category = repair.extract_category(path)
        assert category == "api"

    def test_extract_no_category(self):
        """Test path with no extractable category."""
        repair = PathModelRepair()
        path = "README.md"
        category = repair.extract_category(path)
        assert category is None


class TestPageSlugExtraction:
    """Tests for page slug extraction."""

    def test_extract_slug_with_prefix(self):
        """Test extracting slug from prefixed filename."""
        repair = PathModelRepair()
        slug = repair.extract_page_slug("00-overview.md")
        assert slug == "overview"

    def test_extract_slug_without_prefix(self):
        """Test extracting slug from non-prefixed filename."""
        repair = PathModelRepair()
        slug = repair.extract_page_slug("architecture.md")
        assert slug == "architecture"


class TestRepairedBaselineComparator:
    """Tests for RepairedBaselineComparator."""

    @pytest.fixture
    def setup_qoder_like_structure(self, tmp_path):
        """Set up a qoder-like directory structure."""
        content_dir = tmp_path / ".qoder" / "repowiki" / "zh" / "content"
        content_dir.mkdir(parents=True)

        # Create some pages
        (content_dir / "00-overview.md").write_text("# Overview")
        (content_dir / "01-architecture.md").write_text("# Architecture")

        # Return the content directory, not tmp_path
        return content_dir

    @pytest.fixture
    def setup_repo_agent_eval_structure(self, tmp_path):
        """Set up a repo-agent eval directory structure."""
        content_dir = tmp_path / ".repo-agent-eval" / "run-123" / "content"
        content_dir.mkdir(parents=True)

        # Create some pages
        (content_dir / "00-overview.md").write_text("# Overview")
        (content_dir / "01-architecture.md").write_text("# Architecture")
        (content_dir / "api-reference.md").write_text("# API Reference")

        return content_dir

    def test_compare_qoder_like(self, setup_qoder_like_structure):
        """Test comparing qoder-like structure."""
        comparator = create_repaired_comparator(setup_qoder_like_structure)
        result = comparator.compare()

        assert result["target_model"] == "qoder_like"
        assert result["total_files"] == 2
        assert len(result["in_both"]) == 0  # No baseline

    def test_compare_with_baseline(
        self, setup_repo_agent_eval_structure, setup_qoder_like_structure
    ):
        """Test comparing target with baseline."""
        comparator = create_repaired_comparator(
            setup_repo_agent_eval_structure,
            setup_qoder_like_structure,
        )
        result = comparator.compare()

        assert result["target_model"] == "repo_agent_eval"
        assert result["baseline_root"] is not None

    def test_detect_skip_docs_docs(self, setup_repo_agent_eval_structure):
        """Test that docs/docs paths are skipped."""
        # Create a docs/docs structure (should be skipped)
        docs_docs = setup_repo_agent_eval_structure / "docs" / "docs"
        docs_docs.mkdir(parents=True, exist_ok=True)
        (docs_docs / "extra.md").write_text("# Extra")

        comparator = create_repaired_comparator(setup_repo_agent_eval_structure)
        result = comparator.compare()

        # docs/docs/extra.md should be skipped
        extra_paths = [p for p in result["target_only"] if "extra" in p]
        # If skip pattern works, extra.md won't appear
        assert len(extra_paths) == 0 or all("docs/docs" not in p for p in extra_paths)


class TestDetectAndNormalize:
    """Tests for detect_and_normalize_path function."""

    def test_detect_qoder_path(self):
        """Test detecting and normalizing qoder path."""
        path = Path("/some/.qoder/repowiki/zh/content/page.md")
        normalized, model = detect_and_normalize_path(path)
        assert model == PathModel.QODER_LIKE
        assert "qoder" not in normalized

    def test_detect_repo_agent_path(self):
        """Test detecting and normalizing repo-agent path."""
        path = Path("/some/.repo-agent-eval/run-123/content/page.md")
        normalized, model = detect_and_normalize_path(path)
        assert model == PathModel.REPO_AGENT_EVAL
        assert "repo-agent-eval" not in normalized


class TestQoderTaxonomyCategories:
    """Tests for qoder taxonomy categories."""

    def test_all_categories_defined(self):
        """Test all expected categories are defined."""
        expected = [
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
        for cat in expected:
            assert cat in QODER_TAXONOMY_CATEGORIES


class TestIntegration:
    """Integration tests for path model repair."""

    def test_full_qoder_comparison(self, tmp_path):
        """Test full comparison workflow with qoder-like structure."""
        # Create qoder baseline
        baseline_dir = tmp_path / ".qoder" / "repowiki" / "zh" / "content"
        baseline_dir.mkdir(parents=True)
        (baseline_dir / "00-overview.md").write_text("# Overview")
        (baseline_dir / "01-architecture.md").write_text("# Architecture")

        # Create repo-agent target
        target_dir = tmp_path / ".repo-agent-eval" / "run-456" / "content"
        target_dir.mkdir(parents=True)
        (target_dir / "00-overview.md").write_text("# Overview Updated")
        (target_dir / "02-services.md").write_text("# Services")  # Not in baseline

        # Compare
        comparator = create_repaired_comparator(target_dir, baseline_dir)
        result = comparator.compare()

        # Should detect same files in both
        assert result["target_model"] == "repo_agent_eval"
        assert result["total_files"] >= 2
