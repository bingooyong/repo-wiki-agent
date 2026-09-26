"""Tests for content layout writer and Qoder-compatible output."""

import json
import re
import sqlite3
from pathlib import Path

from repo_wiki.orchestration.content_layout_writer import (
    TAXONOMY_ORDER,
    ContentLayoutWriter,
    build_navigation_tree,
    compute_stable_slug,
    get_taxonomy_category,
    organize_content_by_taxonomy,
    write_qoder_like_content,
)
from repo_wiki.orchestration.eval_layout import EvalOutputProfile, get_eval_profile


def _page_labels(nodes: list[dict]) -> list[str]:
    labels: list[str] = []
    for node in nodes:
        if node.get("type") == "page":
            labels.append(str(node.get("label", "")))
        children = node.get("children")
        if isinstance(children, list):
            labels.extend(_page_labels(children))
    return labels


class TestComputeStableSlug:
    """Tests for stable slug computation."""

    def test_simple_title(self):
        assert compute_stable_slug("Hello World") == "hello-world"

    def test_with_underscores(self):
        assert compute_stable_slug("hello_world") == "hello-world"

    def test_with_special_chars(self):
        assert compute_stable_slug("API Reference (v2)!") == "api-reference-v2"

    def test_truncation(self):
        long_title = "a" * 100
        slug = compute_stable_slug(long_title, max_length=50)
        assert len(slug) <= 50


class TestGetTaxonomyCategory:
    """Tests for taxonomy category detection."""

    def test_overview(self):
        assert get_taxonomy_category("docs/00-overview.md") == "项目概述"

    def test_architecture(self):
        assert get_taxonomy_category("docs/01-architecture.md") == "架构设计"

    def test_module_map(self):
        assert get_taxonomy_category("docs/03-module-map.md") == "核心服务"

    def test_data_model(self):
        assert get_taxonomy_category("docs/05-data-model.md") == "数据模型"

    def test_api(self):
        assert get_taxonomy_category("docs/04-api-contracts.md") == "API参考"

    def test_security(self):
        assert get_taxonomy_category("docs/08-security.md") == "安全合规"

    def test_frontend(self):
        assert get_taxonomy_category("docs/pages/frontend/app-shell.md") == "前端应用"


class TestOrganizeContentByTaxonomy:
    """Tests for content organization by taxonomy."""

    def test_empty_list(self):
        result = organize_content_by_taxonomy([], Path("."))
        assert len(result) > 0

    def test_organized_output(self):
        files = [
            "docs/00-overview.md",
            "docs/01-architecture.md",
            "docs/04-api-contracts.md",
        ]
        result = organize_content_by_taxonomy(files, Path("."))
        assert result["项目概述"] == ["docs/00-overview.md"]
        assert result["架构设计"] == ["docs/01-architecture.md"]
        assert result["API参考"] == ["docs/04-api-contracts.md"]


class TestContentLayoutWriter:
    """Tests for ContentLayoutWriter."""

    def test_writer_initialization(self):
        profile = get_eval_profile("qoder-like")
        writer = ContentLayoutWriter(profile, "run-123")
        assert writer.run_id == "run-123"
        expected_dir = Path(".repo-agent-eval/runs/run-123/repowiki/zh/content")
        assert writer.content_dir == expected_dir

    def test_get_output_path_with_content_subdir(self):
        profile = get_eval_profile("qoder-like")
        writer = ContentLayoutWriter(profile, "run-123")
        output = writer.get_output_path("docs/00-overview.md")
        assert output == Path(
            ".repo-agent-eval/runs/run-123/repowiki/zh/content/项目概述/项目概述.md"
        )

    def test_get_output_path_default_profile(self):
        profile = get_eval_profile("default")
        writer = ContentLayoutWriter(profile, "run-123")
        # Default profile preserves docs/ prefix
        output = writer.get_output_path("docs/00-overview.md")
        assert output == Path(".repo-agent-eval/run-123/docs/00-overview.md")

    def test_write_content(self, tmp_path):
        # Create source files
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "docs").mkdir()
        (source_dir / "docs" / "00-overview.md").write_text("# Overview")

        profile = get_eval_profile("qoder-like")
        writer = ContentLayoutWriter(profile, "test-run")

        files = ["docs/00-overview.md"]
        written, stats = writer.write_content(source_dir, files)

        assert len(written) == 1
        assert stats["files_written"] == 1
        assert "项目概述" in stats["by_category"]


class TestBuildNavigationTree:
    """Tests for navigation tree building."""

    def test_empty_files(self):
        tree = build_navigation_tree([], Path("."))
        assert len(tree) > 0
        labels = {node["label"] for node in tree}
        assert "项目概述" in labels
        assert "前端应用" in labels

    def test_navigation_tree_structure(self, tmp_path):
        # Create test files
        content_dir = tmp_path / "content"
        content_dir.mkdir(parents=True)
        (content_dir / "项目概述").mkdir()
        (content_dir / "项目概述" / "项目概述.md").write_text("# 项目概述")

        files = ["项目概述/项目概述.md"]
        tree = build_navigation_tree(files, content_dir)

        assert len(tree) >= 1
        # Find 项目概述 category
        overview_cat = next((c for c in tree if c["label"] == "项目概述"), None)
        assert overview_cat is not None
        assert len(overview_cat["children"]) >= 1
        assert overview_cat["children"][0]["label"] == "项目概述"


class TestWriteQoderLikeContent:
    """Tests for write_qoder_like_content convenience function."""

    def test_write_with_qoder_profile(self, tmp_path):
        # Create source directory and file
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "docs").mkdir()
        (source_dir / "docs" / "00-overview.md").write_text("# Test")

        profile = get_eval_profile("qoder-like")
        files = ["docs/00-overview.md"]

        written, stats = write_qoder_like_content(
            source_dir=source_dir,
            profile=profile,
            run_id="test-run",
            files=files,
        )

        assert len(written) == 1
        assert stats["files_written"] == 1
        assert written[0] == "项目概述/项目概述.md"

    def test_write_skips_non_docs_files_for_qoder_profile(self, tmp_path):
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "docs").mkdir()
        (source_dir / "docs" / "00-overview.md").write_text("# Test")
        (source_dir / "ai").mkdir()
        (source_dir / "ai" / "task-catalog.yaml").write_text("tasks: []")

        profile = EvalOutputProfile(
            name="qoder-like",
            root=str(tmp_path / ".repo-agent-eval"),
            create_subdirs=True,
            content_subdir="content",
        )
        writer = ContentLayoutWriter(profile, "test-run")

        written, stats = writer.write_content(
            source_dir=source_dir,
            files=["docs/00-overview.md", "ai/task-catalog.yaml"],
        )

        assert written == ["项目概述/项目概述.md"]
        assert stats["files_written"] == 1
        assert (tmp_path / ".repo-agent-eval/test-run/content/项目概述/项目概述.md").exists()
        assert not (tmp_path / ".repo-agent-eval/test-run/content/ai/task-catalog.yaml").exists()

    def test_manifest_content_points_to_real_files(self, tmp_path):
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "docs").mkdir()
        (source_dir / "docs" / "00-overview.md").write_text("# Project Overview")

        profile = EvalOutputProfile(
            name="qoder-like",
            root=str(tmp_path / ".repo-agent-eval"),
            create_subdirs=True,
            content_subdir="content",
        )
        writer = ContentLayoutWriter(profile, "test-run")
        written, _ = writer.write_content(source_dir, ["docs/00-overview.md"])
        manifest_content = writer.build_manifest_content(written)

        assert manifest_content["content_root"] == str(writer.content_dir.resolve())
        assert manifest_content["page_registry"][0]["path"] == "项目概述/项目概述.md"
        assert Path(manifest_content["page_registry"][0]["absolutePath"]).exists()

    def test_write_markdown_pages_uses_qoder_like_chinese_layout(self, tmp_path):
        profile = EvalOutputProfile(
            name="qoder-like",
            root=str(tmp_path / ".repo-agent-eval"),
            create_subdirs=True,
            content_subdir="content",
        )
        writer = ContentLayoutWriter(profile, "test-run")

        written, _ = writer.write_markdown_pages(
            [
                ("docs/pages/api/api-overview.md", "# API参考\n"),
                ("docs/pages/api/doc-parser-service-api-reference.md", "# 文档解析服务API\n"),
                ("docs/pages/data-models/core-data-models.md", "# 核心数据模型\n"),
                ("docs/pages/services/doc-parser-service.md", "# 文档解析服务\n"),
            ]
        )

        assert "API参考/API参考.md" in written
        assert "API参考/Python服务API/文档解析服务/文档解析服务API.md" in written
        assert "数据模型/核心数据模型/核心数据模型.md" in written
        assert "Python服务/文档解析服务/文档解析服务.md" in written

    def test_write_markdown_pages_filters_by_manifest_plan(self, tmp_path):
        profile = EvalOutputProfile(
            name="qoder-like",
            root=str(tmp_path / ".repo-agent-eval"),
            create_subdirs=True,
            content_subdir="content",
        )
        writer = ContentLayoutWriter(profile, "test-run")
        manifest_path = writer.run_dir / "manifest.json"
        writer.run_dir.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "pages": [
                        {"output_path": "docs/pages/api/api-overview.md"},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        selected = writer.load_selected_paths_from_manifest(manifest_path)
        written, stats = writer.write_markdown_pages(
            [
                ("docs/pages/api/api-overview.md", "# API参考\n"),
                ("docs/pages/services/api-gateway.md", "# API网关\n"),
            ],
            selected_source_paths=selected,
        )

        assert selected == {"docs/pages/api/api-overview.md"}
        assert written == ["API参考/API参考.md"]
        assert stats["files_written"] == 1

    def test_load_selected_paths_from_sqlite_normalizes_absolute_paths(self, tmp_path):
        """doc_hierarchy often stores absolute paths; plan uses repo-relative keys."""
        profile = EvalOutputProfile(
            name="qoder-like",
            root=str(tmp_path / ".repo-agent-eval"),
            create_subdirs=True,
            content_subdir="content",
        )
        writer = ContentLayoutWriter(profile, "test-run")
        repo = tmp_path / "target-repo"
        api_dir = repo / "docs" / "pages" / "api"
        api_dir.mkdir(parents=True)
        md_file = api_dir / "api-overview.md"
        md_file.write_text("# API参考\n")
        sqlite_path = tmp_path / ".repo-wiki" / "index" / "runtime.sqlite3"
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path = str(md_file.resolve())
        with sqlite3.connect(sqlite_path) as conn:
            conn.execute("CREATE TABLE doc_hierarchy (doc_path TEXT NOT NULL)")
            conn.execute("INSERT INTO doc_hierarchy(doc_path) VALUES (?)", (abs_path,))
            conn.commit()

        raw_only = writer.load_selected_paths_from_sqlite(sqlite_path)
        assert raw_only != {"docs/pages/api/api-overview.md"}

        normalized = writer.load_selected_paths_from_sqlite(sqlite_path, project_root=repo)
        assert normalized == {"docs/pages/api/api-overview.md"}

    def test_write_markdown_pages_filters_by_sqlite_plan(self, tmp_path):
        profile = EvalOutputProfile(
            name="qoder-like",
            root=str(tmp_path / ".repo-agent-eval"),
            create_subdirs=True,
            content_subdir="content",
        )
        writer = ContentLayoutWriter(profile, "test-run")
        sqlite_path = tmp_path / ".repo-wiki" / "index" / "runtime.sqlite3"
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(sqlite_path) as conn:
            conn.execute("CREATE TABLE doc_hierarchy (doc_path TEXT NOT NULL)")
            conn.execute(
                "INSERT INTO doc_hierarchy(doc_path) VALUES (?)",
                ("docs/pages/services/doc-parser-service.md",),
            )
            conn.execute(
                "INSERT INTO doc_hierarchy(doc_path) VALUES (?)",
                ("docs/pages/data-models/core-data-models.md",),
            )
            conn.commit()

        selected = writer.load_selected_paths_from_sqlite(sqlite_path)
        written, stats = writer.write_markdown_pages(
            [
                ("docs/pages/services/doc-parser-service.md", "# 文档解析服务\n"),
                ("docs/pages/data-models/core-data-models.md", "# 核心数据模型\n"),
                ("docs/pages/api/api-overview.md", "# API参考\n"),
            ],
            selected_source_paths=selected,
        )

        assert selected == {
            "docs/pages/services/doc-parser-service.md",
            "docs/pages/data-models/core-data-models.md",
        }
        assert "Python服务/文档解析服务/文档解析服务.md" in written
        assert "数据模型/核心数据模型/核心数据模型.md" in written
        assert "API参考/API参考.md" not in written
        assert stats["files_written"] == 2

    def test_qoder_like_layout_preserves_taxonomy_hierarchy(self, tmp_path):
        profile = EvalOutputProfile(
            name="qoder-like",
            root=str(tmp_path / ".repo-agent-eval"),
            create_subdirs=True,
            content_subdir="content",
        )
        writer = ContentLayoutWriter(profile, "test-run")

        pages = [
            ("docs/00-overview.md", "# 项目概述\n"),
            ("docs/01-architecture.md", "# 架构设计\n"),
            ("docs/pages/services/api-gateway.md", "# API网关\n"),
            ("docs/pages/python-services/python-services-index.md", "# Python服务\n"),
            ("docs/pages/frontend/app-shell.md", "# 前端应用\n"),
            ("docs/pages/data-models/core-data-models.md", "# 核心数据模型\n"),
            ("docs/pages/api/api-overview.md", "# API参考\n"),
            ("docs/pages/deployment/deployment-overview.md", "# 部署运维\n"),
            ("docs/pages/development/development-guide.md", "# 开发指南\n"),
            ("docs/pages/security/security-overview.md", "# 安全合规\n"),
            ("docs/pages/troubleshooting/troubleshooting-overview.md", "# 故障排除\n"),
        ]
        writer.write_markdown_pages(pages)

        for category in TAXONOMY_ORDER:
            category_dir = writer.content_dir / category
            category_file = writer.content_dir / f"{category}.md"
            assert category_dir.exists() or category_file.exists()

    def test_catalog_leaves_use_chinese_product_titles_when_body_starts_at_h2(self, tmp_path):
        """Sidebar and filenames must be planner Chinese titles, not English slugs."""
        profile = EvalOutputProfile(
            name="qoder-like",
            root=str(tmp_path / ".repo-agent-eval"),
            create_subdirs=True,
            content_subdir="content",
        )
        writer = ContentLayoutWriter(profile, "test-run")
        pages = [
            ("docs/pages/deployment/logging.md", "## 请求日志\n\n应用记录每个请求的状态码。\n"),
            ("docs/pages/deployment/cicd-pipeline.md", "## 流水线阶段\n\n合并后构建并发布镜像。\n"),
            (
                "docs/pages/development/testing-guide.md",
                "## 单测与集成\n\npytest 覆盖路由与仓储。\n",
            ),
            (
                "docs/pages/development/performance-optimization.md",
                "## 热点路径\n\n缓存重复查询结果。\n",
            ),
            (
                "docs/pages/security/security-best-practices.md",
                "## 密钥管理\n\n密钥只放环境变量。\n",
            ),
            ("docs/pages/troubleshooting/build-failures.md", "## 依赖冲突\n\n锁定传递依赖版本。\n"),
            (
                "docs/pages/troubleshooting/debug-tools.md",
                "## 日志定位\n\n用 access log 追请求。\n",
            ),
        ]
        written, _ = writer.write_markdown_pages(pages)
        expected = {
            "部署运维/日志管理.md",
            "部署运维/CI／CD流水线.md",
            "开发指南/测试指南.md",
            "开发指南/性能优化.md",
            "安全合规/安全最佳实践.md",
            "故障排除/构建失败.md",
            "故障排除/调试工具.md",
        }
        assert expected <= set(written)
        english_stems = {
            "logging.md",
            "cicd pipeline.md",
            "cicd-pipeline.md",
            "testing guide.md",
            "testing-guide.md",
            "performance optimization.md",
            "performance-optimization.md",
            "security best practices.md",
            "security-best-practices.md",
            "build failures.md",
            "build-failures.md",
            "debug tools.md",
            "debug-tools.md",
        }
        assert not any(Path(path).name.lower() in english_stems for path in written)

        tree = build_navigation_tree(written, writer.content_dir)
        labels = _page_labels(tree)
        for title in (
            "日志管理",
            "CI/CD流水线",
            "测试指南",
            "性能优化",
            "安全最佳实践",
            "构建失败",
            "调试工具",
        ):
            assert title in labels, labels
        assert not any(label.lower() in english_stems for label in labels)
        assert "cicd pipeline" not in {label.lower() for label in labels}
        assert "logging" not in labels

    def test_duplicate_troubleshooting_overviews_write_one_page(self, tmp_path):
        profile = EvalOutputProfile(
            name="qoder-like",
            root=str(tmp_path / ".repo-agent-eval"),
            create_subdirs=True,
            content_subdir="content",
        )
        writer = ContentLayoutWriter(profile, "test-run")
        written, _ = writer.write_markdown_pages(
            [
                (
                    "docs/pages/troubleshooting/troubleshooting-overview.md",
                    "# 故障排除\n\n常见故障与回滚路径。\n",
                ),
                (
                    "docs/pages/troubleshooting/troubleshooting-maintenance-overview.md",
                    "# 故障排除与维护\n\n维护窗口与健康检查。\n",
                ),
            ]
        )

        assert written == ["故障排除.md"]
        leftover = [
            path
            for path in written
            if re.search(r"故障排除-.*-2\.md$", path) or "troubleshooting" in path
        ]
        assert leftover == []
        assert not (writer.content_dir / "故障排除-troubleshooting-maintena-2.md").exists()

        tree = build_navigation_tree(written, writer.content_dir)
        root_paths = [node.get("path") for node in tree if node.get("type") == "page"]
        assert "故障排除.md" in root_paths
        assert not any(
            isinstance(path, str) and ("-2.md" in path or "troubleshooting" in path)
            for path in root_paths
        )


class TestEvalProfileContentDir:
    """Tests for eval profile content directory handling."""

    def test_qoder_like_profile_content_dir(self):
        profile = get_eval_profile("qoder-like")
        content_dir = profile.get_content_dir("run-456")
        assert content_dir == Path(".repo-agent-eval/runs/run-456/repowiki/zh/content")

    def test_default_profile_content_dir(self):
        profile = get_eval_profile("default")
        content_dir = profile.get_content_dir("run-456")
        assert content_dir == Path(".repo-agent-eval/run-456")

    def test_ci_profile_content_dir(self):
        profile = get_eval_profile("ci")
        content_dir = profile.get_content_dir("run-456")
        assert content_dir == Path(".repo-agent-eval-ci")
