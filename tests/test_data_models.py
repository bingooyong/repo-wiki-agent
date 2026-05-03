"""Tests for Data Models - Phase 26 Task 26.1.

These tests validate that:
1. DataModel class has proper metadata fields for canonical resolution
2. DataModelAggregator properly initializes and processes models
3. Model category constants are properly defined
"""

from repo_wiki.generator.engine import (
    DataModel,
    DataModelAggregator,
    ModelCategory,
)


class TestDataModelFields:
    """Tests for DataModel class fields."""

    def test_data_model_has_all_required_fields(self):
        """Test that DataModel has all required fields for Phase 26."""
        model = DataModel(
            name="User",
            module="auth",
            type="sqlalchemy",
            file_path="auth/models.py",
        )

        # Required fields
        assert model.name == "User"
        assert model.module == "auth"
        assert model.type == "sqlalchemy"
        assert model.file_path == "auth/models.py"

        # Default fields
        assert model.domain == "unknown"
        assert model.service_family == "unknown"
        assert model.is_core_entity == False
        assert model.core_score == 0.0
        assert model.core_reason == ""
        assert model.dedup_key == ""
        assert model.migration_related == False
        assert model.ownership_modules == []

        # Phase 26 fields
        assert model.model_category == "unknown"
        assert model.canonical_name == ""
        assert model.is_canonical == False
        assert model.projections == []

    def test_data_model_with_phase26_fields(self):
        """Test DataModel with Phase 26 metadata fields."""
        model = DataModel(
            name="User",
            module="auth",
            type="sqlalchemy",
            file_path="auth/models.py",
            domain="core-platform",
            service_family="python-backend",
            is_core_entity=True,
            core_score=5.0,
            core_reason="Shared across 3 modules",
            dedup_key="user",
            migration_related=True,
            ownership_modules=["auth", "api", "billing"],
            model_category="core_entity",
            canonical_name="User",
            is_canonical=True,
            projections=["UserDTO", "UserEntity"],
        )

        assert model.model_category == "core_entity"
        assert model.canonical_name == "User"
        assert model.is_canonical == True
        assert model.projections == ["UserDTO", "UserEntity"]


class TestModelCategory:
    """Tests for ModelCategory constants."""

    def test_model_category_constants_defined(self):
        """Test that all ModelCategory constants are defined."""
        assert ModelCategory.CORE_ENTITY == "core_entity"
        assert ModelCategory.DTO == "dto"
        assert ModelCategory.REQUEST_RESPONSE == "request_response"
        assert ModelCategory.DUPLICATED_PROJECTION == "duplicated_projection"
        assert ModelCategory.INFRASTRUCTURE == "infrastructure"


class TestDataModelAggregator:
    """Tests for DataModelAggregator initialization and processing."""

    def test_aggregator_initializes_with_models(self):
        """Test that aggregator initializes properly with model dicts."""
        models = [
            {"name": "User", "module": "auth", "type": "sqlalchemy", "file_path": "auth/models.py"},
        ]
        modules = [
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)

        assert len(aggregator.data_models) == 1
        assert aggregator.data_models[0].name == "User"

    def test_aggregator_builds_model_objects(self):
        """Test that aggregator converts dicts to DataModel objects."""
        models = [
            {"name": "User", "module": "auth", "type": "sqlalchemy", "file_path": "auth/models.py"},
        ]
        modules = [
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)

        assert isinstance(aggregator.data_models[0], DataModel)

    def test_aggregator_identifies_core_entities(self):
        """Test that aggregator identifies core entities."""
        models = [
            {"name": "User", "module": "auth", "type": "sqlalchemy", "file_path": "auth/models.py"},
            {"name": "User", "module": "api", "type": "pydantic", "file_path": "api/schemas.py"},
            {
                "name": "User",
                "module": "billing",
                "type": "dataclass",
                "file_path": "billing/models.py",
            },
        ]
        modules = [
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
            {"name": "billing", "domain": "persistence", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)

        core_entities = aggregator.get_core_entities()
        assert len(core_entities) > 0

    def test_aggregator_deduplicates_models(self):
        """Test that aggregator deduplicates models."""
        models = [
            {"name": "User", "module": "auth", "type": "sqlalchemy", "file_path": "auth/models.py"},
            {"name": "User", "module": "api", "type": "pydantic", "file_path": "api/schemas.py"},
        ]
        modules = [
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)

        # Both should have the same dedup_key
        assert aggregator.data_models[0].dedup_key == aggregator.data_models[1].dedup_key


class TestCoreEntityScoring:
    """Tests for core entity scoring mechanism."""

    def test_shared_entity_gets_higher_score(self):
        """Test that entities shared across modules get higher scores."""
        models = [
            {"name": "User", "module": "auth", "type": "dataclass", "file_path": "auth/models.py"},
            {"name": "User", "module": "api", "type": "pydantic", "file_path": "api/schemas.py"},
            {
                "name": "User",
                "module": "billing",
                "type": "sqlalchemy",
                "file_path": "billing/models.py",
            },
        ]
        modules = [
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
            {"name": "billing", "domain": "persistence", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)

        user_models = [m for m in aggregator.data_models if m.name == "User"]
        for user in user_models:
            assert user.core_score > 0

    def test_domain_affects_core_score(self):
        """Test that being in core domain affects core score."""
        models = [
            {
                "name": "RepositorySnapshot",
                "module": "core",
                "type": "dataclass",
                "file_path": "core/snapshot.py",
            },
            {
                "name": "Invoice",
                "module": "billing",
                "type": "sqlalchemy",
                "file_path": "billing/models.py",
            },
        ]
        modules = [
            {"name": "core", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "billing", "domain": "persistence", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)

        snapshot = next(m for m in aggregator.data_models if m.name == "RepositorySnapshot")
        invoice = next(m for m in aggregator.data_models if m.name == "Invoice")

        # Core domain entities should have higher or equal scores
        assert snapshot.core_score >= invoice.core_score


class TestModelGrouping:
    """Tests for model grouping methods."""

    def test_group_by_module(self):
        """Test models are grouped by module."""
        models = [
            {"name": "User", "module": "auth", "type": "dataclass", "file_path": "auth/models.py"},
            {
                "name": "AuthToken",
                "module": "auth",
                "type": "dataclass",
                "file_path": "auth/models.py",
            },
            {
                "name": "Invoice",
                "module": "billing",
                "type": "sqlalchemy",
                "file_path": "billing/models.py",
            },
        ]
        modules = [
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "billing", "domain": "persistence", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)

        by_module = aggregator.get_models_by_module()
        assert "auth" in by_module
        assert "billing" in by_module
        assert len(by_module["auth"]) == 2
        assert len(by_module["billing"]) == 1

    def test_group_by_domain(self):
        """Test models are grouped by domain."""
        models = [
            {"name": "User", "module": "auth", "type": "dataclass", "file_path": "auth/models.py"},
            {
                "name": "Invoice",
                "module": "billing",
                "type": "sqlalchemy",
                "file_path": "billing/models.py",
            },
        ]
        modules = [
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "billing", "domain": "persistence", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)

        by_domain = aggregator.get_models_by_domain()
        assert "core-platform" in by_domain
        assert "persistence" in by_domain


class TestMigrationSignals:
    """Tests for migration signal analysis."""

    def test_detects_migration_related_models(self):
        """Test that migration-related models are identified."""
        models = [
            {
                "name": "current_schema_version",
                "module": "core",
                "type": "integer",
                "file_path": "core/config.py",
            },
            {"name": "User", "module": "auth", "type": "sqlalchemy", "file_path": "auth/models.py"},
        ]
        modules = [
            {"name": "core", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)

        version_model = next(
            m for m in aggregator.data_models if "schema_version" in m.name.lower()
        )
        assert version_model.migration_related

    def test_detects_alembic_migration(self):
        """Test that Alembic migration strategy is detected."""
        models = [
            {
                "name": "User",
                "module": "auth",
                "type": "sqlalchemy",
                "file_path": "alembic/versions/user_model.py",
            },
        ]
        modules = [
            {"name": "auth", "domain": "persistence", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)

        assert "Alembic" in aggregator.migration_strategy


class TestSummarizationMethods:
    """Tests for model summarization methods."""

    def test_summarize_database_shape(self):
        """Test database shape summarization."""
        models = [
            {"name": "User", "module": "auth", "type": "sqlalchemy", "file_path": "auth/models.py"},
            {"name": "UserDTO", "module": "api", "type": "pydantic", "file_path": "api/schemas.py"},
        ]
        modules = [
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)
        summary = aggregator.summarize_database_shape()

        assert "数据库形状概述" in summary
        assert "sqlalchemy" in summary
        assert "pydantic" in summary

    def test_summarize_migration_strategy(self):
        """Test migration strategy summarization."""
        models = [
            {"name": "User", "module": "auth", "type": "sqlalchemy", "file_path": "auth/models.py"},
        ]
        modules = [
            {"name": "auth", "domain": "persistence", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)
        summary = aggregator.summarize_migration_strategy()

        assert "迁移" in summary or "migration" in summary.lower()

    def test_build_core_models_section(self):
        """Test core models section building."""
        models = [
            {
                "name": "RepositorySnapshot",
                "module": "core",
                "type": "dataclass",
                "file_path": "core/snapshot.py",
            },
        ]
        modules = [
            {"name": "core", "domain": "core-platform", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)
        section = aggregator.build_core_models_section()

        assert "RepositorySnapshot" in section

    def test_build_service_models_section(self):
        """Test service models section building."""
        models = [
            {
                "name": "InvoiceItem",
                "module": "billing",
                "type": "dataclass",
                "file_path": "billing/models.py",
            },
        ]
        modules = [
            {"name": "billing", "domain": "operations", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)
        section = aggregator.build_service_models_section()

        assert "InvoiceItem" in section


class TestCrossModuleBoundaries:
    """Tests for cross-module boundary documentation."""

    def test_build_cross_module_boundaries(self):
        """Test cross-module boundaries documentation."""
        models = [
            {"name": "User", "module": "auth", "type": "dataclass", "file_path": "auth/models.py"},
            {"name": "User", "module": "api", "type": "pydantic", "file_path": "api/schemas.py"},
        ]
        modules = [
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)
        boundaries = aggregator.build_cross_module_boundaries()

        assert "User" in boundaries
        assert "模块" in boundaries or "module" in boundaries.lower()
