"""Tests for repository identity resolver."""

import json
from pathlib import Path

from repo_wiki.planner.identity import (
    _human_readable_name,
    detect_language_and_framework,
    detect_package_manager,
    resolve_repository_identity,
)


class TestRepositoryIdentityResolver:
    """Tests for repository identity resolution."""

    def test_resolve_from_package_json(self, tmp_path: Path):
        """Test resolving identity from package.json."""
        package_json = tmp_path / "package.json"
        package_json.write_text(
            json.dumps(
                {
                    "name": "my-awesome-project",
                    "version": "2.0.0",
                    "description": "An awesome project",
                }
            ),
            encoding="utf-8",
        )

        identity = resolve_repository_identity(tmp_path)
        assert identity.name == "my-awesome-project"
        assert identity.display_name == "My Awesome Project"
        assert identity.version == "2.0.0"
        assert identity.description == "An awesome project"

    def test_resolve_from_pyproject_toml(self, tmp_path: Path):
        """Test resolving identity from pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "my-python-project"
version = "1.0.0"
description = "A Python project"
""",
            encoding="utf-8",
        )

        identity = resolve_repository_identity(tmp_path)
        assert identity.name == "my-python-project"
        assert identity.version == "1.0.0"

    def test_resolve_from_pom_xml(self, tmp_path: Path):
        """Test resolving identity from pom.xml."""
        pom = tmp_path / "pom.xml"
        pom.write_text(
            """
<project>
    <artifactId>my-java-project</artifactId>
    <version>1.5.0</version>
</project>
""",
            encoding="utf-8",
        )

        identity = resolve_repository_identity(tmp_path)
        assert identity.name == "my-java-project"
        assert identity.version == "1.5.0"

    def test_fallback_to_directory_name(self, tmp_path: Path):
        """Test fallback to directory name when no metadata."""
        identity = resolve_repository_identity(tmp_path)
        assert identity.name == tmp_path.name
        assert identity.display_name == _human_readable_name(tmp_path.name)

    def test_readme_description_extraction(self, tmp_path: Path):
        """Test extracting description from README."""
        readme = tmp_path / "README.md"
        readme.write_text(
            """
# My Project

This is a detailed description of my project.
It does amazing things.

## Getting Started

Quick start guide here.
""",
            encoding="utf-8",
        )

        identity = resolve_repository_identity(tmp_path)
        assert identity.description is not None
        assert (
            "amazing" in identity.description.lower() or "project" in identity.description.lower()
        )

    def test_ai_api_atlas_not_workspace(self, tmp_path: Path):
        """Test that AI_API_Atlas project name is not 'workspace'."""
        # Create a fake AI_API_Atlas project structure
        (tmp_path / "README.md").write_text(
            "# AI API Atlas\n\nAn API documentation atlas.", encoding="utf-8"
        )
        (tmp_path / "repo_wiki").mkdir()
        (tmp_path / "tests").mkdir()

        identity = resolve_repository_identity(tmp_path)
        # The name should NOT be "workspace" - it should come from README/git/etc
        assert identity.name != "workspace", "AI_API_Atlas should not resolve to 'workspace'"


class TestLanguageDetection:
    """Tests for language and framework detection."""

    def test_detect_python(self, tmp_path: Path):
        """Test detecting Python projects."""
        (tmp_path / "setup.py").write_text("# setup", encoding="utf-8")
        (tmp_path / "module.py").write_text("def foo(): pass", encoding="utf-8")

        lang, framework = detect_language_and_framework(tmp_path)
        assert lang == "python"

    def test_detect_typescript(self, tmp_path: Path):
        """Test detecting TypeScript projects."""
        (tmp_path / "package.json").write_text('{"name": "test"}', encoding="utf-8")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "index.ts").write_text("export const x = 1;", encoding="utf-8")

        lang, framework = detect_language_and_framework(tmp_path)
        assert lang == "typescript"

    def test_detect_golang(self, tmp_path: Path):
        """Test detecting Go projects."""
        (tmp_path / "go.mod").write_text("module test", encoding="utf-8")
        (tmp_path / "main.go").write_text("package main", encoding="utf-8")

        lang, framework = detect_language_and_framework(tmp_path)
        assert lang == "golang"

    def test_detect_fastapi_framework(self, tmp_path: Path):
        """Test detecting FastAPI framework."""
        (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn", encoding="utf-8")
        (tmp_path / "main.py").write_text("from fastapi import FastAPI", encoding="utf-8")

        lang, framework = detect_language_and_framework(tmp_path)
        assert framework == "fastapi"

    def test_detect_nestjs_framework(self, tmp_path: Path):
        """Test detecting NestJS framework."""
        package_json = tmp_path / "package.json"
        package_json.write_text(
            json.dumps({"dependencies": {"@nestjs/core": "^10.0.0"}}), encoding="utf-8"
        )

        lang, framework = detect_language_and_framework(tmp_path)
        assert framework == "nestjs"


class TestPackageManagerDetection:
    """Tests for package manager detection."""

    def test_detect_npm(self, tmp_path: Path):
        """Test detecting npm."""
        (tmp_path / "package.json").write_text('{"name": "test"}', encoding="utf-8")
        (tmp_path / "package-lock.json").write_text("{}", encoding="utf-8")

        pm = detect_package_manager(tmp_path)
        assert pm == "npm"

    def test_detect_pnpm(self, tmp_path: Path):
        """Test detecting pnpm."""
        (tmp_path / "pnpm-lock.yaml").write_text("", encoding="utf-8")

        pm = detect_package_manager(tmp_path)
        assert pm == "pnpm"

    def test_detect_yarn(self, tmp_path: Path):
        """Test detecting yarn."""
        (tmp_path / "yarn.lock").write_text("", encoding="utf-8")

        pm = detect_package_manager(tmp_path)
        assert pm == "yarn"

    def test_detect_poetry(self, tmp_path: Path):
        """Test detecting Poetry."""
        (tmp_path / "poetry.lock").write_text("", encoding="utf-8")

        pm = detect_package_manager(tmp_path)
        assert pm == "poetry"

    def test_detect_go_modules(self, tmp_path: Path):
        """Test detecting Go modules."""
        (tmp_path / "go.sum").write_text("", encoding="utf-8")

        pm = detect_package_manager(tmp_path)
        assert pm == "go"

    def test_unknown_package_manager(self, tmp_path: Path):
        """Test unknown package manager."""
        pm = detect_package_manager(tmp_path)
        assert pm == "unknown"


class TestHumanReadableName:
    """Tests for human-readable name conversion."""

    def test_kebab_to_title(self):
        """Test converting kebab-case to title case."""
        assert _human_readable_name("my-project") == "My Project"
        assert _human_readable_name("awesome-tool") == "Awesome Tool"

    def test_snake_to_title(self):
        """Test converting snake_case to title case."""
        assert _human_readable_name("my_project") == "My Project"
        assert _human_readable_name("awesome_tool") == "Awesome Tool"

    def test_ai_api_atlas(self):
        """Test AI_API_Atlas name conversion."""
        result = _human_readable_name("AI_API_Atlas")
        assert result == "AI API Atlas"

    def test_single_word(self):
        """Test single word names."""
        assert _human_readable_name("repo") == "Repo"
        assert _human_readable_name("WIKI") == "WIKI"
