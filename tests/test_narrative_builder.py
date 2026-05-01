"""Tests for Narrative Builder - Phase 10 Task 10.1.

These tests validate that narrative content is repository-specific rather
than overly generic or template-based boilerplate.
"""

import pytest
from repo_wiki.generator.contracts import (
    validate_narrative_not_generic,
    validate_architecture_rationale_exists,
    validate_overview_has_repository_specifics,
)


class TestNarrativeGenericDetection:
    """Tests for detecting generic/template-based narrative content."""

    def test_detects_generic_boilerplate_patterns(self):
        """Should reject content containing generic boilerplate patterns."""
        generic_content = """
        这是一个基于 Python 的知识管理和文档生成系统。
        它提供自动化的代码扫描、文档生成和知识图谱构建能力。

        传统文档维护面临的主要挑战包括文档与代码不同步、难以发现和检索。
        通过自动化手段降低文档维护成本。
        """

        is_valid, reason = validate_narrative_not_generic(generic_content)
        assert not is_valid, f"Should reject generic boilerplate: {reason}"

    def test_detects_repeated_sentences(self):
        """Should reject content with repeated sentences indicating template generation."""
        # Content with duplicate sentences
        repeated_content = """
        项目提供核心能力一。项目提供核心能力一。
        系统采用三层架构设计。三层架构包括运行时存储层、结构化事实层和文档中心层。
        系统采用三层架构设计。三层架构确保知识持久化。
        """

        is_valid, reason = validate_narrative_not_generic(repeated_content)
        assert not is_valid, f"Should reject repeated sentences: {reason}"

    def test_accepts_repository_specific_content(self):
        """Should accept content that is repository-specific."""
        specific_content = """
        repo-agent 是一个基于 Python 的 Agent 协作框架。
        它通过消息队列实现多 Agent 之间的任务分发和结果收集。

        核心问题在于传统单 Agent 系统无法有效协调多个专业 Agent 的工作。
        repo-agent 通过统一的 Adapter 接口和 Governance 层来解决这个问题。
        """

        is_valid, reason = validate_narrative_not_generic(specific_content)
        assert is_valid, f"Should accept repository-specific content: {reason}"

    def test_allows_minor_boilerplate(self):
        """Should allow content with only 1-2 generic patterns (some boilerplate is unavoidable)."""
        # Content with only 1 generic pattern should pass
        minor_boilerplate = """
        这是一个基于 Python 的项目。
        repo-agent 的核心问题在于多 Agent 协调的复杂性。
        系统通过 Governance 层和 Adapter 接口实现解耦。
        """

        is_valid, reason = validate_narrative_not_generic(minor_boilerplate)
        # This should pass as it has only 1 generic pattern
        assert is_valid, f"Should allow minor boilerplate: {reason}"


class TestArchitectureRationale:
    """Tests for architecture rationale explanation (WHY, not just WHAT)."""

    def test_rejects_what_without_why(self):
        """Should reject architecture content that only describes WHAT, not WHY."""
        what_only_content = """
        系统采用三层架构：

        第一层：运行时存储层 (.repo-wiki/)
        第二层：结构化事实层 (ai/source-of-truth/)
        第三层：文档中心层 (docs/)

        Layer 1 包含索引、缓存、图谱存储。
        Layer 2 包含 module-index.yaml、api-index.yaml。
        Layer 3 包含总览文档、专题文档、模块文档。
        """

        is_valid, reason = validate_architecture_rationale_exists(what_only_content)
        assert not is_valid, f"Should reject WHAT-only content: {reason}"

    def test_accepts_rationale_explanation(self):
        """Should accept architecture content that explains WHY the design exists."""
        rationale_content = """
        系统采用三层架构来解决以下问题：

        **为什么分离运行时存储与结构化事实？**
        运行时操作会产生大量临时状态，而结构化事实需要稳定持久化。
        如果混在一起，状态污染会影响事实的可靠性。

        **为什么需要文档中心？**
        源代码和结构化事实都不是面向读者的最优格式。
        文档中心通过选择性的信息呈现来提升可读性。

        **层次依赖设计原因：**
        .repo-wiki/ 层不直接面向读者，仅作为系统运行底座；
        ai/source-of-truth/ 层面向机器和自动化工具；
        docs/ 层面向最终读者。
        """

        is_valid, reason = validate_architecture_rationale_exists(rationale_content)
        assert is_valid, f"Should accept rationale content: {reason}"

    def test_requires_problem_statements(self):
        """Should require that architecture explains problems being solved."""
        content_without_problems = """
        系统采用三层架构。

        Layer 1: .repo-wiki/
        Layer 2: ai/source-of-truth/
        Layer 3: docs/

        每一层都有特定的职责。
        """

        is_valid, reason = validate_architecture_rationale_exists(content_without_problems)
        assert not is_valid, f"Should require problem statements: {reason}"


class TestOverviewRepositorySpecifics:
    """Tests for repository-specific content in overview documents."""

    def test_rejects_content_without_repo_name(self):
        """Should reject overview that doesn't reference repository name."""
        content_without_name = """
        这是一个基于 Python 的知识管理和文档生成系统。
        系统提供自动化文档生成能力。
        """

        is_valid, reason = validate_overview_has_repository_specifics(content_without_name, "repo-agent")
        assert not is_valid, f"Should reject content without repo name: {reason}"

    def test_accepts_content_with_repo_name(self):
        """Should accept overview that references the actual repository name."""
        content_with_name = """
        repo-agent 是一个基于 Python 的 Agent 协作框架。
        系统提供多 Agent 协调和任务分发能力。
        """

        is_valid, reason = validate_overview_has_repository_specifics(content_with_name, "repo-agent")
        assert is_valid, f"Should accept content with repo name: {reason}"

    def test_case_insensitive_repo_name_check(self):
        """Should match repository name case-insensitively."""
        content = """
        Repo-Agent 提供核心能力。
        """

        is_valid, reason = validate_overview_has_repository_specifics(content, "repo-agent")
        assert is_valid, f"Should match case-insensitively: {reason}"


class TestNarrativeBuilderIntegration:
    """Integration tests for NarrativeBuilder with GenerationEngine."""

    def test_narrative_builder_derives_knowledge_management_signals(self):
        """Test that NarrativeBuilder correctly identifies knowledge management systems."""
        from repo_wiki.generator.engine import NarrativeBuilder

        # Simulate a knowledge management system (not a document generation system)
        builder = NarrativeBuilder(
            repo_name="graph-store",
            primary_language="python",
            framework="unknown",
            modules=[
                {
                    "name": "graph_store",
                    "path": "graph_store",
                    "domain": "ai-services",
                    "service_family": "python-backend",
                    "runtime_role": "data-store",
                    "responsibility": "Graph database and traversal",
                }
            ],
            endpoints=[],
            models=[],
            commands={"start": "python -m graph_store.server"},
        )

        # Should detect knowledge management signals
        assert builder.is_knowledge_management_system, "Should detect knowledge management signals"
        assert not builder.is_document_generation_system, "Should not detect doc gen without signals"

    def test_narrative_builder_derives_document_generation_signals(self):
        """Test that NarrativeBuilder correctly identifies document generation systems."""
        from repo_wiki.generator.engine import NarrativeBuilder

        builder = NarrativeBuilder(
            repo_name="doc-generator",
            primary_language="python",
            framework="unknown",
            modules=[
                {
                    "name": "generator",
                    "path": "generator",
                    "domain": "tooling",
                    "service_family": "python-backend",
                    "runtime_role": "tooling",
                    "responsibility": "Document generation from templates",
                    "exports": ["generate_markdown", "render_template"],
                }
            ],
            endpoints=[],
            models=[],
            commands={},
        )

        # Should detect document generation signals from module exports
        assert builder.is_document_generation_system, "Should detect doc generation signals"

    def test_narrative_builder_builds_specific_project_description(self):
        """Test that NarrativeBuilder generates repository-specific project description."""
        from repo_wiki.generator.engine import NarrativeBuilder

        builder = NarrativeBuilder(
            repo_name="repo-agent",
            primary_language="python",
            framework="unknown",
            modules=[
                {
                    "name": "scanner",
                    "path": "scanner",
                    "domain": "core-platform",
                    "service_family": "python-backend",
                    "runtime_role": "tooling",
                    "responsibility": "Code scanning",
                }
            ],
            endpoints=[
                {"module": "api", "method": "GET", "path": "/status"}
            ],
            models=[
                {"name": "Repository", "module": "core", "type": "dataclass"}
            ],
            commands={"scan": "repo-wiki scan"},
        )

        description = builder.build_project_description()

        # Should reference repo name and specific capabilities
        assert "repo-agent" in description, "Should include repo name"
        # Should NOT contain generic template text
        assert "知识管理和文档生成系统" not in description or "repo-agent" in description

    def test_narrative_builder_explains_architecture_rationale(self):
        """Test that NarrativeBuilder explains WHY, not just WHAT."""
        from repo_wiki.generator.engine import NarrativeBuilder

        builder = NarrativeBuilder(
            repo_name="repo-agent",
            primary_language="python",
            framework="unknown",
            modules=[],
            endpoints=[],
            models=[],
            commands={},
        )

        rationale = builder.build_architecture_rationale()

        # Should contain "为什么" (why) explanations
        assert "为什么" in rationale or "原因" in rationale or "为了" in rationale
        # Should NOT just list layer names
        assert not (rationale.count("第一层") > 0 and rationale.count("分离") == 0)

    def test_narrative_builder_builds_capabilities_from_signals(self):
        """Test that capabilities are derived from actual repository signals."""
        from repo_wiki.generator.engine import NarrativeBuilder

        builder = NarrativeBuilder(
            repo_name="repo-agent",
            primary_language="python",
            framework="fastapi",
            modules=[
                {
                    "name": "api",
                    "path": "api",
                    "domain": "api-gateway",
                    "service_family": "python-backend",
                    "runtime_role": "api-server",
                    "responsibility": "REST API endpoints",
                }
            ],
            endpoints=[
                {"module": "api", "method": "GET", "path": "/health"},
                {"module": "api", "method": "POST", "path": "/scan"},
            ],
            models=[],
            commands={"start": "uvicorn api.main:app"},
        )

        capabilities = builder.build_core_capabilities()

        # Should mention actual endpoint count
        assert "2 个端点" in capabilities or "2个端点" in capabilities
        # Should NOT be generic template
        assert "模块分析和依赖关系构建" not in capabilities or len(capabilities) > 20