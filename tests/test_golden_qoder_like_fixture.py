"""Tests for golden fixture suite."""

import json

import pytest

from repo_wiki.test.golden_fixtures import (
    GOLDEN_FIXTURES,
    GoldenFixtureBuilder,
    GoldenFixtureValidator,
    create_golden_fixtures,
    get_fixture,
    list_fixtures,
    validate_golden_fixture,
)


class TestGoldenFixtures:
    """Tests for golden fixture definitions."""

    def test_all_fixtures_defined(self):
        """Test all expected fixtures are defined."""
        expected = ["python-microservice", "typescript-react", "java-springboot", "sql-database"]
        for name in expected:
            assert name in GOLDEN_FIXTURES, f"Missing fixture: {name}"

    def test_fixture_properties(self):
        """Test fixture properties are valid."""
        for name, fixture in GOLDEN_FIXTURES.items():
            assert fixture.name == name
            assert fixture.language in ["python", "typescript", "java", "sql"]
            assert 0 <= fixture.complexity_score <= 1.0
            assert fixture.size_category in ["small", "medium", "large"]
            assert len(fixture.expected_wiki_tree) > 0

    def test_fixture_wiki_tree_structure(self):
        """Test fixture wiki tree structure."""
        for name, fixture in GOLDEN_FIXTURES.items():
            assert isinstance(fixture.expected_wiki_tree, dict)
            assert len(fixture.expected_wiki_tree) > 0
            for category, docs in fixture.expected_wiki_tree.items():
                assert isinstance(category, str)
                assert isinstance(docs, list)
                assert len(docs) > 0


class TestGoldenFixtureBuilder:
    """Tests for GoldenFixtureBuilder."""

    @pytest.fixture
    def builder_setup(self, tmp_path):
        """Set up builder with temp directory."""
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        builder = GoldenFixtureBuilder(fixtures_dir)
        return builder, fixtures_dir

    def test_build_python_fixture(self, builder_setup):
        """Test building Python microservice fixture."""
        builder, fixtures_dir = builder_setup
        fixture = get_fixture("python-microservice")
        assert fixture is not None

        root = builder.build_fixture(fixture)
        assert root.exists()
        assert (root / "content").exists()
        assert (root / "fixture_metadata.json").exists()

    def test_build_all_fixtures(self, builder_setup):
        """Test building all fixtures."""
        builder, fixtures_dir = builder_setup
        roots = builder.build_all_fixtures()

        assert len(roots) == len(GOLDEN_FIXTURES)
        for root in roots:
            assert root.exists()
            assert (root / "fixture_metadata.json").exists()

    def test_fixture_content_structure(self, builder_setup):
        """Test fixture creates correct content structure."""
        builder, fixtures_dir = builder_setup
        fixture = get_fixture("python-microservice")
        assert fixture is not None

        root = builder.build_fixture(fixture)
        content_dir = root / "content"

        # Check that categories exist
        for category in fixture.expected_wiki_tree.keys():
            assert (content_dir / category).exists()

        # Check that markdown files exist
        md_files = list(content_dir.rglob("*.md"))
        assert len(md_files) > 0

    def test_metadata_format(self, builder_setup):
        """Test fixture metadata is valid JSON."""
        builder, fixtures_dir = builder_setup
        fixture = get_fixture("python-microservice")
        assert fixture is not None

        root = builder.build_fixture(fixture)
        metadata_path = root / "fixture_metadata.json"

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert metadata["name"] == "python-microservice"
        assert metadata["language"] == "python"
        assert "schema_version" in metadata


class TestGoldenFixtureValidator:
    """Tests for GoldenFixtureValidator."""

    @pytest.fixture
    def validator_setup(self, tmp_path):
        """Set up validator with a built fixture."""
        fixtures_dir = tmp_path / "fixtures"
        fixtures_dir.mkdir()
        builder = GoldenFixtureBuilder(fixtures_dir)
        builder.build_all_fixtures()
        return fixtures_dir

    def test_validate_valid_fixture(self, validator_setup):
        """Test validating a valid fixture."""
        fixture_root = validator_setup / "python-microservice"
        validator = GoldenFixtureValidator(fixture_root)
        is_valid, errors = validator.validate()

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_missing_metadata(self, validator_setup):
        """Test validation fails on missing metadata."""
        fixture_root = validator_setup / "python-microservice"
        (fixture_root / "fixture_metadata.json").unlink()

        validator = GoldenFixtureValidator(fixture_root)
        is_valid, errors = validator.validate()

        assert is_valid is False
        assert "Missing fixture_metadata.json" in errors

    def test_validate_invalid_json(self, validator_setup):
        """Test validation fails on invalid JSON."""
        fixture_root = validator_setup / "python-microservice"
        (fixture_root / "fixture_metadata.json").write_text("not valid json")

        validator = GoldenFixtureValidator(fixture_root)
        is_valid, errors = validator.validate()

        assert is_valid is False
        assert any("Invalid JSON" in e for e in errors)


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_golden_fixtures(self, tmp_path):
        """Test create_golden_fixtures factory."""
        roots = create_golden_fixtures(tmp_path)

        assert len(roots) == len(GOLDEN_FIXTURES)
        for root in roots:
            assert root.exists()

    def test_get_fixture(self):
        """Test get_fixture function."""
        fixture = get_fixture("python-microservice")
        assert fixture is not None
        assert fixture.name == "python-microservice"

        missing = get_fixture("nonexistent")
        assert missing is None

    def test_list_fixtures(self):
        """Test list_fixtures function."""
        names = list_fixtures()
        assert len(names) == len(GOLDEN_FIXTURES)
        assert "python-microservice" in names
        assert "typescript-react" in names


class TestIntegration:
    """Integration tests for golden fixtures."""

    def test_full_fixture_lifecycle(self, tmp_path):
        """Test complete fixture lifecycle: create, validate."""
        # Create fixtures
        roots = create_golden_fixtures(tmp_path)
        assert len(roots) == 4

        # Validate each
        for root in roots:
            is_valid, errors = validate_golden_fixture(root)
            assert is_valid is True, f"Validation failed for {root.name}: {errors}"

    def test_fixture_content_has_citations(self, tmp_path):
        """Test that fixture content includes citations."""
        builder = GoldenFixtureBuilder(tmp_path)
        fixture = get_fixture("python-microservice")
        assert fixture is not None

        root = builder.build_fixture(fixture)
        content_dir = root / "content"

        # Find markdown files and check for citations
        md_files = list(content_dir.rglob("*.md"))
        found_citations = False

        for md_file in md_files:
            content = md_file.read_text(encoding="utf-8")
            if "<cite>" in content or "[cite:" in content:
                found_citations = True
                break

        # At least some files should have citations
        assert found_citations, "No citations found in fixture content"

    def test_fixture_toc_in_overview(self, tmp_path):
        """Test that overview pages have TOC."""
        builder = GoldenFixtureBuilder(tmp_path)
        fixture = get_fixture("python-microservice")
        assert fixture is not None

        root = builder.build_fixture(fixture)
        content_dir = root / "content"

        # Find overview file
        overview_files = list(content_dir.rglob("*overview*.md"))
        if overview_files:
            content = overview_files[0].read_text(encoding="utf-8")
            # Should have TOC heading or marker
            has_toc = "Table of Contents" in content or "目录" in content or "[TOC]" in content
            assert has_toc, "Overview missing TOC"
