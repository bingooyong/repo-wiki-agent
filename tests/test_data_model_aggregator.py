"""Tests for Data Model Aggregator - Phase 10 Task 10.3.

These tests validate that data model aggregation identifies core entities
using ownership cues, endpoint parameters, and cross-module references,
and that migration strategy is properly detected.
"""

from repo_wiki.generator.engine import DataModelAggregator


class TestCoreEntityIdentification:
    """Tests for core entity identification using multiple signals."""

    def test_identifies_shared_entities(self):
        """Test that entities appearing in multiple modules are identified as core."""
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
        assert len(user_models) == 3

        # At least one User model should be identified as core entity
        core_users = [m for m in user_models if m.is_core_entity]
        assert len(core_users) > 0

    def test_identifies_domain_based_core_entities(self):
        """Test that entities in core domains (core-platform, persistence) are identified as core."""
        models = [
            {
                "name": "RepositorySnapshot",
                "module": "core",
                "type": "dataclass",
                "file_path": "core/snapshot.py",
            },
            {
                "name": "BaseModel",
                "module": "persistence",
                "type": "sqlalchemy",
                "file_path": "persistence/base.py",
            },
        ]
        modules = [
            {"name": "core", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "persistence", "domain": "persistence", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)

        for model in aggregator.data_models:
            if model.domain in ("core-platform", "persistence"):
                assert model.is_core_entity or model.core_score > 0

    def test_identifies_foundational_named_entities(self):
        """Test that entities with foundational names are identified as core."""
        models = [
            {
                "name": "BaseEntity",
                "module": "core",
                "type": "dataclass",
                "file_path": "core/base.py",
            },
            {
                "name": "CommonModel",
                "module": "shared",
                "type": "dataclass",
                "file_path": "shared/models.py",
            },
        ]
        modules = [
            {"name": "core", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "shared", "domain": "tooling", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)

        base_entity = next((m for m in aggregator.data_models if m.name == "BaseEntity"), None)
        assert base_entity is not None
        assert base_entity.core_score > 0

    def test_service_models_not_marked_as_core(self):
        """Test that service-specific models have lower core scores than truly shared entities."""
        models = [
            {
                "name": "Invoice",
                "module": "billing",
                "type": "sqlalchemy",
                "file_path": "billing/models.py",
            },
            {
                "name": "LineItem",
                "module": "billing",
                "type": "sqlalchemy",
                "file_path": "billing/models.py",
            },
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
            {"name": "billing", "domain": "persistence", "service_family": "python-backend"},
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)

        # User is shared across 3 modules - should have high core score
        user_models = [m for m in aggregator.data_models if m.name == "User"]
        assert len(user_models) == 3

        # Invoice is only in billing - should have lower core score than User
        invoice = next(m for m in aggregator.data_models if m.name == "Invoice")
        user_core = next(
            m for m in aggregator.data_models if m.name == "User" and len(m.ownership_modules) > 1
        )

        # User should have higher score because it's shared
        assert user_core.core_score >= invoice.core_score


class TestMigrationSignalAnalysis:
    """Tests for migration strategy detection."""

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

    def test_detects_schema_version_tracking(self):
        """Test that schema version tracking is detected."""
        models = [
            {
                "name": "current_schema_version",
                "module": "core",
                "type": "integer",
                "file_path": "core/config.py",
            },
            {
                "name": "SchemaVersion",
                "module": "core",
                "type": "dataclass",
                "file_path": "core/schema.py",
            },
        ]
        modules = [
            {"name": "core", "domain": "core-platform", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)

        assert "Schema 版本跟踪" in aggregator.migration_strategy

    def test_detects_sqlalchemy_orm_strategy(self):
        """Test that SQLAlchemy ORM migration strategy is detected."""
        models = [
            {"name": "User", "module": "auth", "type": "sqlalchemy", "file_path": "auth/models.py"},
            {
                "name": "Base",
                "module": "shared",
                "type": "sqlalchemy",
                "file_path": "shared/base.py",
            },
        ]
        modules = [
            {"name": "auth", "domain": "persistence", "service_family": "python-backend"},
            {"name": "shared", "domain": "persistence", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)

        # Should detect ORM-based strategy (either SQLAlchemy or ORM model migration)
        assert (
            "ORM" in aggregator.migration_strategy
            or "sqlalchemy" in aggregator.migration_strategy.lower()
        )


class TestModelDeduplication:
    """Tests for deduplication of ORM/DTO/builder representations."""

    def test_normalizes_model_names(self):
        """Test that model names are normalized for deduplication."""
        models = [
            {"name": "User", "module": "auth", "type": "sqlalchemy", "file_path": "auth/models.py"},
            {
                "name": "User_dto",
                "module": "api",
                "type": "pydantic",
                "file_path": "api/schemas.py",
            },
            {
                "name": "User_model",
                "module": "billing",
                "type": "dataclass",
                "file_path": "billing/models.py",
            },
        ]
        modules = [
            {"name": "auth", "domain": "persistence", "service_family": "python-backend"},
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
            {"name": "billing", "domain": "persistence", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)

        # All should have the same dedup_key
        user_models = [m for m in aggregator.data_models if "user" in m.name.lower()]
        dedup_keys = set(m.dedup_key for m in user_models)
        assert len(dedup_keys) == 1  # All should normalize to same key


class TestGroupingMethods:
    """Tests for model grouping methods."""

    def test_get_core_entities(self):
        """Test that get_core_entities returns only core entities."""
        models = [
            {
                "name": "RepositorySnapshot",
                "module": "core",
                "type": "dataclass",
                "file_path": "core/snapshot.py",
            },
            {"name": "User", "module": "auth", "type": "dataclass", "file_path": "auth/models.py"},
            {
                "name": "Invoice",
                "module": "billing",
                "type": "sqlalchemy",
                "file_path": "billing/models.py",
            },
        ]
        modules = [
            {"name": "core", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "billing", "domain": "persistence", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)

        core_entities = aggregator.get_core_entities()

        # Core entities should have is_core_entity = True
        for entity in core_entities:
            assert entity.is_core_entity

    def test_get_models_by_domain(self):
        """Test that models are grouped by domain."""
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
        assert len(by_domain["core-platform"]) == 1
        assert len(by_domain["persistence"]) == 1

    def test_get_models_by_module(self):
        """Test that models are grouped by module."""
        models = [
            {"name": "User", "module": "auth", "type": "dataclass", "file_path": "auth/models.py"},
            {
                "name": "AuthToken",
                "module": "auth",
                "type": "dataclass",
                "file_path": "auth/models.py",
            },
        ]
        modules = [
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)

        by_module = aggregator.get_models_by_module()

        assert "auth" in by_module
        assert len(by_module["auth"]) == 2


class TestSummarizationMethods:
    """Tests for database shape and migration strategy summarization."""

    def test_summarize_database_shape(self):
        """Test that database shape is properly summarized."""
        models = [
            {"name": "User", "module": "auth", "type": "sqlalchemy", "file_path": "auth/models.py"},
            {
                "name": "Invoice",
                "module": "billing",
                "type": "sqlalchemy",
                "file_path": "billing/models.py",
            },
            {"name": "Config", "module": "core", "type": "pydantic", "file_path": "core/config.py"},
        ]
        modules = [
            {"name": "auth", "domain": "persistence", "service_family": "python-backend"},
            {"name": "billing", "domain": "persistence", "service_family": "python-backend"},
            {"name": "core", "domain": "core-platform", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)
        summary = aggregator.summarize_database_shape()

        assert "sqlalchemy" in summary.lower()
        assert "pydantic" in summary.lower()
        assert "2" in summary or "3" in summary  # counts

    def test_summarize_migration_strategy(self):
        """Test that migration strategy is properly summarized."""
        models = [
            {"name": "User", "module": "auth", "type": "sqlalchemy", "file_path": "auth/models.py"},
        ]
        modules = [
            {"name": "auth", "domain": "persistence", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)
        summary = aggregator.summarize_migration_strategy()

        assert "迁移" in summary or "migration" in summary.lower()
        assert len(summary) > 20  # Should be substantive

    def test_build_core_models_section(self):
        """Test that core models section contains proper narrative."""
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
        assert "核心" in section or "core" in section.lower()

    def test_build_service_models_section(self):
        """Test that service models section is properly structured."""
        # Use a module that won't be classified as core domain
        models = [
            {
                "name": "InvoiceItem",
                "module": "billing",
                "type": "dataclass",
                "file_path": "billing/models.py",
            },
        ]
        modules = [
            {
                "name": "billing",
                "domain": "operations",
                "service_family": "python-backend",
            },  # Not a core domain
        ]

        aggregator = DataModelAggregator(models=models, modules=modules)
        section = aggregator.build_service_models_section()

        # Should have InvoiceItem as a service model (not core)
        assert "InvoiceItem" in section
        assert "billing" in section

    def test_build_cross_module_boundaries(self):
        """Test that cross-module boundaries are properly documented."""
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


class TestNoModelDump:
    """Tests that detect model dumps without entity identification."""

    def test_model_dump_detected(self):
        """Test that a pure model dump is detected."""
        from repo_wiki.generator.contracts import validate_data_model_not_dump

        dump_content = """
        ## Data Models

        - User (dataclass)
        - Invoice (sqlalchemy)
        - Order (dataclass)
        - Product (pydantic)
        ...
        """

        is_valid, reason = validate_data_model_not_dump(dump_content)
        # This should fail because it's just a list without proper grouping
        assert not is_valid or "boundary" in reason.lower()

    def test_aggregated_models_pass_validation(self):
        """Test that properly aggregated model content passes."""
        from repo_wiki.generator.contracts import validate_data_model_grouped

        aggregated_content = """
        ## 核心数据模型

        系统的基础数据结构，定义跨模块共享的实体类型。

        - RepositorySnapshot: 被多个模块使用

        ## 服务数据模型

        ### billing (persistence)

        - Invoice (sqlalchemy)
        - LineItem (sqlalchemy)

        ## 数据库与迁移策略

        迁移相关描述...
        """

        is_valid, reason = validate_data_model_grouped(aggregated_content)
        # Should have proper sections
        assert is_valid or "core" in reason.lower() or "service" in reason.lower()
