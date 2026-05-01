"""Tests for Section Narrative Builder and Reading Path Generator - Phase 10 Task 10.4.

These tests validate that section pages use repository-derived narrative instead
of template-based aggregation, and that reading paths explain WHY documents
are recommended in sequence.
"""

import pytest
from repo_wiki.generator.engine import SectionNarrativeBuilder, ReadingPathGenerator, ReadingPath


class TestSectionNarrativeBuilder:
    """Tests for SectionNarrativeBuilder - repository-specific narrative generation."""

    def test_builder_initializes_with_section_metadata(self):
        """Test that builder initializes with section slug and title."""
        modules = [{"name": "auth", "domain": "core-platform", "responsibility": "Authentication"}]
        endpoints = [{"method": "GET", "path": "/health", "module": "api", "handler": "health"}]
        commands = {"start": "python -m repo_wiki"}
        core_context = {}

        builder = SectionNarrativeBuilder(
            section_slug="services",
            section_title="Core Services",
            modules=modules,
            endpoints=endpoints,
            commands=commands,
            core_context=core_context,
        )

        assert builder.section_slug == "services"
        assert builder.section_title == "Core Services"
        assert len(builder.modules) == 1
        assert len(builder.endpoints) == 1

    def test_build_section_description_returns_string(self):
        """Test that section description is generated."""
        modules = [
            {"name": "auth", "domain": "core-platform", "responsibility": "Authentication"}
        ]
        endpoints = []
        commands = {}
        core_context = {}

        builder = SectionNarrativeBuilder(
            section_slug="services",
            section_title="Core Services",
            modules=modules,
            endpoints=endpoints,
            commands=commands,
            core_context=core_context,
        )

        desc = builder.build_section_description()
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_build_section_description_uses_domain_content(self):
        """Test that description reflects actual module domains."""
        modules = [
            {"name": "api", "domain": "api-gateway", "responsibility": "API Gateway"}
        ]
        endpoints = []
        commands = {}
        core_context = {}

        builder = SectionNarrativeBuilder(
            section_slug="api",
            section_title="API Reference",
            modules=modules,
            endpoints=endpoints,
            commands=commands,
            core_context=core_context,
        )

        desc = builder.build_section_description()
        assert "api-gateway" in desc.lower() or "api" in desc.lower()

    def test_build_section_content_returns_string(self):
        """Test that section content is generated."""
        modules = [
            {"name": "auth", "domain": "core-platform", "responsibility": "Auth module", "runtime_role": "api-server"}
        ]
        endpoints = []
        commands = {}
        core_context = {}

        builder = SectionNarrativeBuilder(
            section_slug="services",
            section_title="Core Services",
            modules=modules,
            endpoints=endpoints,
            commands=commands,
            core_context=core_context,
        )

        content = builder.build_section_content()
        assert isinstance(content, str)
        assert len(content) > 0

    def test_build_section_modules_returns_markdown_list(self):
        """Test that section modules are formatted as markdown list."""
        modules = [
            {"name": "auth", "domain": "core-platform", "path": "auth/", "responsibility": "Auth module"},
            {"name": "users", "domain": "core-platform", "path": "users/", "responsibility": "User module"},
        ]
        endpoints = []
        commands = {}
        core_context = {}

        builder = SectionNarrativeBuilder(
            section_slug="services",
            section_title="Core Services",
            modules=modules,
            endpoints=endpoints,
            commands=commands,
            core_context=core_context,
        )

        modules_output = builder.build_section_modules()
        assert isinstance(modules_output, str)
        assert "auth" in modules_output
        assert "users" in modules_output

    def test_build_section_apis_returns_markdown_list(self):
        """Test that section APIs are formatted as markdown list."""
        modules = []
        endpoints = [
            {"method": "GET", "path": "/users", "module": "api", "handler": "list_users"},
            {"method": "POST", "path": "/users", "module": "api", "handler": "create_user"},
        ]
        commands = {}
        core_context = {}

        builder = SectionNarrativeBuilder(
            section_slug="api",
            section_title="API Reference",
            modules=modules,
            endpoints=endpoints,
            commands=commands,
            core_context=core_context,
        )

        apis_output = builder.build_section_apis()
        assert isinstance(apis_output, str)
        assert "GET" in apis_output
        assert "POST" in apis_output
        assert "/users" in apis_output

    def test_build_section_commands_returns_markdown_list(self):
        """Test that section commands are formatted as markdown list."""
        modules = []
        endpoints = []
        commands = {"start": "python -m repo_wiki", "scan": "python -m repo_wiki scan"}
        core_context = {}

        builder = SectionNarrativeBuilder(
            section_slug="development",
            section_title="Development Guide",
            modules=modules,
            endpoints=endpoints,
            commands=commands,
            core_context=core_context,
        )

        commands_output = builder.build_section_commands()
        assert isinstance(commands_output, str)
        assert "start" in commands_output
        assert "scan" in commands_output

    def test_section_slug_affects_content_generation(self):
        """Test that different section slugs produce different content."""
        modules = [
            {"name": "auth", "domain": "core-platform", "responsibility": "Auth", "runtime_role": "api-server"}
        ]
        endpoints = []
        commands = {}
        core_context = {}

        builder_services = SectionNarrativeBuilder(
            section_slug="services",
            section_title="Services",
            modules=modules,
            endpoints=endpoints,
            commands=commands,
            core_context=core_context,
        )

        builder_api = SectionNarrativeBuilder(
            section_slug="api",
            section_title="API",
            modules=modules,
            endpoints=endpoints,
            commands=commands,
            core_context=core_context,
        )

        content_services = builder_services.build_section_content()
        content_api = builder_api.build_section_content()

        # Different slugs should lead to different content patterns
        assert content_services != content_api

    def test_get_relevant_modules_by_slug(self):
        """Test that relevant modules are filtered by slug-domain mapping."""
        modules = [
            {"name": "auth", "domain": "core-platform", "responsibility": "Auth"},
            {"name": "data", "domain": "data-pipeline", "responsibility": "Data pipeline"},
        ]
        endpoints = []
        commands = {}
        core_context = {}

        builder = SectionNarrativeBuilder(
            section_slug="services",  # Maps to core-platform AND data-pipeline domains
            section_title="Services",
            modules=modules,
            endpoints=endpoints,
            commands=commands,
            core_context=core_context,
        )

        relevant = builder._get_relevant_modules()
        # services slug maps to both core-platform and data-pipeline domains
        # so both modules should be returned
        assert len(relevant) == 2
        relevant_domains = {m["domain"] for m in relevant}
        assert relevant_domains == {"core-platform", "data-pipeline"}


class TestReadingPathGenerator:
    """Tests for ReadingPathGenerator - document-center reading path generation."""

    def test_generator_initializes(self):
        """Test that generator initializes with section metadata."""
        modules = [{"name": "auth", "domain": "core-platform"}]
        endpoints = [{"method": "GET", "path": "/health", "module": "api"}]
        core_context = {}

        gen = ReadingPathGenerator(
            section_slug="services",
            section_title="Core Services",
            modules=modules,
            endpoints=endpoints,
            core_context=core_context,
        )

        assert gen.section_slug == "services"
        assert gen.section_title == "Core Services"

    def test_generate_reading_paths_returns_list_of_reading_paths(self):
        """Test that reading paths are generated as typed dicts."""
        modules = []
        endpoints = []
        core_context = {}

        gen = ReadingPathGenerator(
            section_slug="services",
            section_title="Core Services",
            modules=modules,
            endpoints=endpoints,
            core_context=core_context,
        )

        paths = gen.generate_reading_paths()
        assert isinstance(paths, list)
        assert len(paths) > 0

        # Check structure of each path
        for path in paths:
            assert isinstance(path, dict)
            assert "doc_path" in path
            assert "doc_title" in path
            assert "reason" in path
            assert "order" in path

    def test_reading_paths_have_sequential_order(self):
        """Test that reading paths have sequential ordering."""
        modules = []
        endpoints = []
        core_context = {}

        gen = ReadingPathGenerator(
            section_slug="architecture",
            section_title="Architecture",
            modules=modules,
            endpoints=endpoints,
            core_context=core_context,
        )

        paths = gen.generate_reading_paths()
        orders = [p["order"] for p in paths]
        assert orders == sorted(orders)

    def test_reading_paths_explain_why(self):
        """Test that reading paths include explanatory reasons."""
        modules = []
        endpoints = []
        core_context = {}

        gen = ReadingPathGenerator(
            section_slug="services",
            section_title="Core Services",
            modules=modules,
            endpoints=endpoints,
            core_context=core_context,
        )

        paths = gen.generate_reading_paths()
        # All paths should have non-empty reasons explaining WHY to read
        for path in paths:
            assert len(path["reason"]) > 5, f"Reason too short: {path['reason']}"

    def test_format_reading_paths_returns_markdown(self):
        """Test that reading paths are formatted as markdown."""
        modules = []
        endpoints = []
        core_context = {}

        gen = ReadingPathGenerator(
            section_slug="project",
            section_title="Project Overview",
            modules=modules,
            endpoints=endpoints,
            core_context=core_context,
        )

        formatted = gen.format_reading_paths()
        assert isinstance(formatted, str)
        assert "推荐阅读路径" in formatted or "reading" in formatted.lower()
        assert "[" in formatted  # Markdown link syntax
        assert "(" in formatted  # Markdown link URL

    def test_format_related_sections_returns_markdown(self):
        """Test that related sections are formatted as markdown."""
        modules = []
        endpoints = []
        core_context = {}

        gen = ReadingPathGenerator(
            section_slug="api",
            section_title="API Reference",
            modules=modules,
            endpoints=endpoints,
            core_context=core_context,
        )

        formatted = gen.format_related_sections()
        assert isinstance(formatted, str)
        assert "相关专题" in formatted or "related" in formatted.lower()
        assert "[" in formatted  # Markdown link syntax

    def test_different_sections_have_different_paths(self):
        """Test that different sections get different reading paths."""
        modules = []
        endpoints = []
        core_context = {}

        gen_project = ReadingPathGenerator(
            section_slug="project",
            section_title="Project",
            modules=modules,
            endpoints=endpoints,
            core_context=core_context,
        )

        gen_api = ReadingPathGenerator(
            section_slug="api",
            section_title="API",
            modules=modules,
            endpoints=endpoints,
            core_context=core_context,
        )

        paths_project = gen_project.generate_reading_paths()
        paths_api = gen_api.generate_reading_paths()

        # Different sections should have different path combinations
        project_titles = {p["doc_title"] for p in paths_project}
        api_titles = {p["doc_title"] for p in paths_api}
        assert project_titles != api_titles

    def test_reading_paths_always_include_overview_first(self):
        """Test that overview is always recommended first."""
        modules = []
        endpoints = []
        core_context = {}

        gen = ReadingPathGenerator(
            section_slug="troubleshooting",
            section_title="Troubleshooting",
            modules=modules,
            endpoints=endpoints,
            core_context=core_context,
        )

        paths = gen.generate_reading_paths()
        # The overview path should have order -1 (special order indicating first)
        overview_paths = [p for p in paths if "overview" in p["doc_path"].lower()]
        assert len(overview_paths) >= 1
        # Overview should have order == -1
        overview_path = overview_paths[0]
        assert overview_path["order"] == -1


class TestIntegrationWithBuildSectionContext:
    """Tests for integration with _build_section_context method."""

    def test_section_context_uses_narrative_builder(self):
        """Test that _build_section_context produces narrative-based content."""
        from repo_wiki.generator.engine import GenerationEngine
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # Create minimal structure
            (root / "templates").mkdir(parents=True)
            (root / "templates" / "section.md.j2").write_text("{{ content }}")
            (root / "ai" / "source-of-truth").mkdir(parents=True)
            (root / "docs").mkdir(parents=True)
            (root / ".repo-wiki" / "cache").mkdir(parents=True)

            engine = GenerationEngine(root=root)

            modules = [
                {"name": "auth", "domain": "core-platform", "path": "auth/", "responsibility": "Authentication"}
            ]
            endpoints = [
                {"method": "GET", "path": "/users", "module": "api", "handler": "list_users"}
            ]
            commands = {"start": "python -m repo_wiki"}
            core_context = {}

            ctx = engine._build_section_context(
                section_slug="services",
                section_title="Core Services",
                modules=modules,
                endpoints=endpoints,
                commands=commands,
                core_context=core_context,
            )

            # Check that all fields are populated
            assert ctx["section_title"] == "Core Services"
            assert len(ctx["section_description"]) > 0
            assert len(ctx["section_content"]) > 0
            assert len(ctx["section_modules"]) > 0
            assert len(ctx["section_nav"]) > 0
            # Reading paths and related sections come from generator
            assert "reading_paths" in ctx
            assert "related_sections" in ctx

    def test_section_context_reading_paths_explain_sequence(self):
        """Test that reading paths in context explain WHY sequence is recommended."""
        from repo_wiki.generator.engine import GenerationEngine
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "templates").mkdir(parents=True)
            (root / "templates" / "section.md.j2").write_text("{{ content }}")
            (root / "ai" / "source-of-truth").mkdir(parents=True)
            (root / "docs").mkdir(parents=True)
            (root / ".repo-wiki" / "cache").mkdir(parents=True)

            engine = GenerationEngine(root=root)

            ctx = engine._build_section_context(
                section_slug="architecture",
                section_title="Architecture",
                modules=[],
                endpoints=[],
                commands={},
                core_context={},
            )

            # Reading paths should contain explanations
            assert "推荐阅读路径" in ctx["reading_paths"] or "reading" in ctx["reading_paths"].lower()
            # Should have markdown links
            assert "[项目概览]" in ctx["reading_paths"] or "[Overview]" in ctx["reading_paths"]


class TestNoTemplateDump:
    """Tests that detect template dumps without narrative generation."""

    def test_content_not_just_listing_modules(self):
        """Test that section content is not just a module listing."""
        modules = [
            {"name": "auth", "domain": "core-platform", "responsibility": "Auth", "runtime_role": "api-server"},
            {"name": "billing", "domain": "persistence", "responsibility": "Billing", "runtime_role": "worker"},
        ]
        endpoints = []
        commands = {}
        core_context = {}

        builder = SectionNarrativeBuilder(
            section_slug="services",
            section_title="Services",
            modules=modules,
            endpoints=endpoints,
            commands=commands,
            core_context=core_context,
        )

        content = builder.build_section_content()

        # Should have narrative structure, not just bullet points
        assert "## " in content  # Has section headers (narrative structure)
        # Content should reference domain/runtimes, not just names
        assert "core-platform" in content or "persistence" in content or "api-server" in content or "runtime" in content.lower()

    def test_reading_paths_not_just_links(self):
        """Test that reading paths have explanatory reasons, not just links."""
        modules = []
        endpoints = []
        core_context = {}

        gen = ReadingPathGenerator(
            section_slug="api",
            section_title="API",
            modules=modules,
            endpoints=endpoints,
            core_context=core_context,
        )

        formatted = gen.format_reading_paths()

        # Should contain explanatory text explaining WHY
        # Reasons use Chinese patterns like "是...的接口", "需要关注", etc.
        assert "是" in formatted and "的" in formatted  # Contains explanatory phrasing
