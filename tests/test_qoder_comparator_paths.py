"""Tests for Qoder comparator path model repair."""

from pathlib import Path

import pytest

from repo_wiki.verifier.qoder_baseline_registry import (
    baseline_unchanged,
    register_single_qoder_baseline,
)
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

    def test_inventory_service_api_missing_counterpart_is_hard_failure(self, tmp_path):
        """Missing API台账服务 API counterpart must be reported as required failure."""
        baseline_dir = tmp_path / ".qoder" / "repowiki" / "zh" / "content"
        baseline_dir.mkdir(parents=True)
        # Baseline has inventory-service API topic.
        (baseline_dir / "API参考" / "核心服务API").mkdir(parents=True, exist_ok=True)
        (baseline_dir / "API参考" / "核心服务API" / "API台账服务 API.md").write_text(
            "# API台账服务 API", encoding="utf-8"
        )

        target_dir = tmp_path / ".repo-agent-eval" / "run-001" / "content"
        target_dir.mkdir(parents=True)
        # Target intentionally misses inventory-service counterpart.
        (target_dir / "API参考" / "核心服务API").mkdir(parents=True, exist_ok=True)
        (target_dir / "API参考" / "核心服务API" / "其他服务 API.md").write_text(
            "# 其他服务 API", encoding="utf-8"
        )

        comparator = create_repaired_comparator(target_dir, baseline_dir)
        result = comparator.compare()

        assert result["required_counterpart_ok"] is False
        failures = result["required_counterpart_failures"]
        assert failures
        assert failures[0]["rule_id"] == "inventory_service_api_topic"

    @pytest.mark.parametrize(
        ("rule_id", "baseline_name"),
        [
            ("gitlab_mcp_api_topic", "GitLab MCP服务 API.md"),
            ("jenkins_mcp_api_topic", "Jenkins MCP服务 API.md"),
            ("knowledge_graph_api_topic", "知识图谱服务 API.md"),
            ("security_audit_api_topic", "安全审计服务 API.md"),
            ("script_generation_api_topic", "脚本生成服务 API.md"),
        ],
    )
    def test_core_service_api_missing_counterpart_is_hard_failure(
        self, tmp_path, rule_id: str, baseline_name: str
    ):
        baseline_dir = tmp_path / ".qoder" / "repowiki" / "zh" / "content"
        baseline_dir.mkdir(parents=True)
        (baseline_dir / "API参考" / "核心服务API").mkdir(parents=True, exist_ok=True)
        (baseline_dir / "API参考" / "核心服务API" / baseline_name).write_text(
            f"# {baseline_name}", encoding="utf-8"
        )

        target_dir = tmp_path / ".repo-agent-eval" / "run-002" / "content"
        target_dir.mkdir(parents=True)
        (target_dir / "API参考" / "核心服务API").mkdir(parents=True, exist_ok=True)
        (target_dir / "API参考" / "核心服务API" / "无关服务 API.md").write_text(
            "# 无关服务 API", encoding="utf-8"
        )

        comparator = create_repaired_comparator(target_dir, baseline_dir)
        result = comparator.compare()

        failures = result["required_counterpart_failures"]
        matched = [f for f in failures if f["rule_id"] == rule_id]
        assert matched
        assert matched[0]["failure_type"] == "missing"

    def test_required_counterpart_quality_low_when_wrong_service_citations(self, tmp_path):
        baseline_dir = tmp_path / ".qoder" / "repowiki" / "zh" / "content"
        baseline_dir.mkdir(parents=True)
        (baseline_dir / "API参考" / "核心服务API").mkdir(parents=True, exist_ok=True)
        (baseline_dir / "API参考" / "核心服务API" / "GitLab MCP服务 API.md").write_text(
            "# GitLab MCP服务 API", encoding="utf-8"
        )

        target_dir = tmp_path / ".repo-agent-eval" / "run-003" / "content"
        target_page = (
            target_dir / "API参考" / "核心服务API" / "GitLab MCP服务" / "GitLab MCP服务API.md"
        )
        target_page.parent.mkdir(parents=True, exist_ok=True)
        target_page.write_text(
            (
                "# GitLab MCP服务API\n"
                "<cite>ai-service/src/main/java/com/ai/api/reference/AiServiceApplication.java:12</cite>\n"
                "<cite>ai-service/src/main/java/com/ai/api/reference/AiServiceApplication.java:36</cite>\n"
            ),
            encoding="utf-8",
        )

        comparator = create_repaired_comparator(target_dir, baseline_dir)
        result = comparator.compare()

        failures = result["required_counterpart_failures"]
        gitlab_failures = [f for f in failures if f["rule_id"] == "gitlab_mcp_api_topic"]
        assert gitlab_failures
        assert gitlab_failures[0]["failure_type"] == "quality_low"
        assert gitlab_failures[0]["pair_score"]["forbidden_hits"] > 0


class TestQoderBaselineRegistry:
    """Tests for single canonical qoder baseline enforcement."""

    def test_registry_requires_existing_canonical_baseline(self, tmp_path: Path):
        target = tmp_path / "repo" / ".repo-agent-eval" / "run-1" / "content"
        target.mkdir(parents=True)
        (tmp_path / "repo" / ".git").mkdir(parents=True)

        with pytest.raises(ValueError, match="Canonical baseline missing"):
            register_single_qoder_baseline(target_root=target)

    def test_registry_rejects_eval_run_as_baseline(self, tmp_path: Path):
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        canonical = repo / ".qoder" / "repowiki" / "zh"
        canonical.mkdir(parents=True)
        (canonical / "content").mkdir()
        (canonical / "content" / "00-overview.md").write_text("# Baseline", encoding="utf-8")
        bad_baseline = repo / ".repo-agent-eval" / "run-1" / "content"
        bad_baseline.mkdir(parents=True)
        target = repo / ".repo-agent-eval" / "run-2" / "content"
        target.mkdir(parents=True)

        with pytest.raises(ValueError, match=r"\.repo-agent-eval"):
            register_single_qoder_baseline(target_root=target, baseline_root=bad_baseline)

    def test_registry_detects_baseline_mutation(self, tmp_path: Path):
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        baseline = repo / ".qoder" / "repowiki" / "zh"
        (baseline / "content").mkdir(parents=True)
        page = baseline / "content" / "00-overview.md"
        page.write_text("# A", encoding="utf-8")
        target = repo / ".repo-agent-eval" / "run-1" / "content"
        target.mkdir(parents=True)

        entry = register_single_qoder_baseline(target_root=target)
        assert baseline_unchanged(entry) is True

        page.write_text("# B", encoding="utf-8")
        assert baseline_unchanged(entry) is False
