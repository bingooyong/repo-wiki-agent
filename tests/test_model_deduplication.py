"""Tests for Model Deduplication - Phase 26 Task 26.1.

These tests validate that:
1. Java entities, DTOs, TypeScript types, and SQL tables are resolved into canonical models
2. Deduplication keys properly normalize entity names
3. Model categories (core_entity, dto, request_response, duplicated_projection) are assigned
4. High-frequency models are identified for fixture generation
"""

import pytest
from repo_wiki.generator.engine import (
    DataModel,
    DataModelAggregator,
    CanonicalModelResolver,
    CanonicalModel,
    ModelCategory,
)


class TestCanonicalModelResolution:
    """Tests for canonical model resolution."""

    def test_resolves_user_entity_across_modules(self):
        """Test that User entity with multiple projections resolves to single canonical model."""
        models = [
            DataModel(name="User", module="auth", type="sqlalchemy", file_path="auth/models.py"),
            DataModel(name="User_dto", module="api", type="pydantic", file_path="api/schemas.py"),
            DataModel(name="UserEntity", module="billing", type="dataclass", file_path="billing/models.py"),
        ]
        modules = [
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
            {"name": "billing", "domain": "persistence", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=[m.__dict__ for m in models], modules=modules)
        resolver = CanonicalModelResolver(aggregator.data_models)

        # Should have one canonical model for User
        user_canonical = [c for c in resolver.canonical_models if "user" in c.dedup_key]
        assert len(user_canonical) == 1

        # All three projections should be grouped
        assert len(user_canonical[0].models) == 3

    def test_normalizes_dto_suffixes(self):
        """Test that _dto, _DTO suffixes are normalized for deduplication."""
        models = [
            DataModel(name="UserDTO", module="api", type="pydantic", file_path="api/schemas.py"),
            DataModel(name="UserDto", module="service", type="pydantic", file_path="service/schemas.py"),
        ]
        modules = [
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
            {"name": "service", "domain": "core-platform", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=[m.__dict__ for m in models], modules=modules)
        resolver = CanonicalModelResolver(aggregator.data_models)

        # Should normalize to same dedup_key
        assert len(resolver.canonical_models) == 1
        assert resolver.canonical_models[0].dedup_key == "user"

    def test_normalizes_request_response_suffixes(self):
        """Test that request/response suffixes are normalized to base entity."""
        models = [
            DataModel(name="CreateUserRequest", module="api", type="pydantic", file_path="api/schemas.py"),
            DataModel(name="CreateUserResponse", module="api", type="pydantic", file_path="api/schemas.py"),
        ]
        modules = [
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=[m.__dict__ for m in models], modules=modules)
        resolver = CanonicalModelResolver(aggregator.data_models)

        # Should normalize to same dedup key (base entity: CreateUser)
        # They share the same base entity but are different projections
        assert len(resolver.canonical_models) == 1
        assert resolver.canonical_models[0].dedup_key == "createuser"

        # Both should be classified as request_response
        assert resolver.canonical_models[0].category == ModelCategory.REQUEST_RESPONSE

        # Should have 2 projections
        assert len(resolver.canonical_models[0].models) == 2

    def test_classifies_sqlalchemy_as_core_entity(self):
        """Test that SQLAlchemy models are classified as core entities."""
        models = [
            DataModel(name="User", module="auth", type="sqlalchemy", file_path="auth/models.py"),
        ]
        modules = [
            {"name": "auth", "domain": "persistence", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=[m.__dict__ for m in models], modules=modules)
        resolver = CanonicalModelResolver(aggregator.data_models)

        assert len(resolver.canonical_models) == 1
        assert resolver.canonical_models[0].category == ModelCategory.CORE_ENTITY

    def test_classifies_pydantic_dto(self):
        """Test that Pydantic models with _dto suffix are classified as DTO."""
        models = [
            DataModel(name="UserDTO", module="api", type="pydantic", file_path="api/schemas.py"),
        ]
        modules = [
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=[m.__dict__ for m in models], modules=modules)
        resolver = CanonicalModelResolver(aggregator.data_models)

        assert len(resolver.canonical_models) == 1
        assert resolver.canonical_models[0].category == ModelCategory.DTO

    def test_classifies_request_response_types(self):
        """Test that request/response types are properly classified."""
        models = [
            DataModel(name="LoginRequest", module="api", type="pydantic", file_path="api/schemas.py"),
            DataModel(name="LoginResponse", module="api", type="pydantic", file_path="api/schemas.py"),
        ]
        modules = [
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=[m.__dict__ for m in models], modules=modules)
        resolver = CanonicalModelResolver(aggregator.data_models)

        categories = [c.category for c in resolver.canonical_models]
        assert ModelCategory.REQUEST_RESPONSE in categories


class TestHighFrequencyModelIdentification:
    """Tests for high-frequency model identification for fixtures."""

    def test_identifies_high_frequency_by_module_count(self):
        """Test that models shared across 3+ modules are marked as high-frequency."""
        models = [
            DataModel(name="User", module="auth", type="sqlalchemy", file_path="auth/models.py"),
            DataModel(name="User", module="api", type="pydantic", file_path="api/schemas.py"),
            DataModel(name="User", module="billing", type="dataclass", file_path="billing/models.py"),
        ]
        modules = [
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
            {"name": "billing", "domain": "persistence", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=[m.__dict__ for m in models], modules=modules)
        resolver = CanonicalModelResolver(aggregator.data_models)

        high_freq = resolver.get_high_frequency_models()
        assert len(high_freq) == 1
        assert "user" in high_freq[0].dedup_key
        assert "跨 3 个模块共享" in high_freq[0].high_frequency_reason

    def test_identifies_high_frequency_by_name_pattern(self):
        """Test that models with high-frequency name patterns are identified."""
        models = [
            DataModel(name="Config", module="core", type="pydantic", file_path="core/config.py"),
        ]
        modules = [
            {"name": "core", "domain": "core-platform", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=[m.__dict__ for m in models], modules=modules)
        resolver = CanonicalModelResolver(aggregator.data_models)

        high_freq = resolver.get_high_frequency_models()
        assert len(high_freq) >= 1

    def test_high_frequency_models_sorted_first(self):
        """Test that high-frequency models appear first in canonical list."""
        models = [
            DataModel(name="Invoice", module="billing", type="sqlalchemy", file_path="billing/models.py"),
            DataModel(name="User", module="auth", type="sqlalchemy", file_path="auth/models.py"),
            DataModel(name="User", module="api", type="pydantic", file_path="api/schemas.py"),
            DataModel(name="User", module="billing", type="dataclass", file_path="billing/models.py"),
        ]
        modules = [
            {"name": "billing", "domain": "persistence", "service_family": "python-backend"},
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=[m.__dict__ for m in models], modules=modules)
        resolver = CanonicalModelResolver(aggregator.data_models)

        # User is high-frequency, should be first
        assert resolver.canonical_models[0].dedup_key == "user"


class TestCategoryFiltering:
    """Tests for filtering models by category."""

    def test_get_core_entities(self):
        """Test filtering for core entities."""
        models = [
            DataModel(name="User", module="auth", type="sqlalchemy", file_path="auth/models.py"),
            DataModel(name="UserDTO", module="api", type="pydantic", file_path="api/schemas.py"),
        ]
        modules = [
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=[m.__dict__ for m in models], modules=modules)
        resolver = CanonicalModelResolver(aggregator.data_models)

        core = resolver.get_core_entities()
        assert len(core) >= 1

    def test_get_dtos(self):
        """Test filtering for DTOs."""
        models = [
            DataModel(name="UserDTO", module="api", type="pydantic", file_path="api/schemas.py"),
            DataModel(name="LoginRequest", module="api", type="pydantic", file_path="api/schemas.py"),
        ]
        modules = [
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=[m.__dict__ for m in models], modules=modules)
        resolver = CanonicalModelResolver(aggregator.data_models)

        dtos = resolver.get_dtos()
        assert len(dtos) >= 1

    def test_get_request_response_types(self):
        """Test filtering for request/response types."""
        models = [
            DataModel(name="LoginRequest", module="api", type="pydantic", file_path="api/schemas.py"),
            DataModel(name="LoginResponse", module="api", type="pydantic", file_path="api/schemas.py"),
        ]
        modules = [
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=[m.__dict__ for m in models], modules=modules)
        resolver = CanonicalModelResolver(aggregator.data_models)

        req_resp = resolver.get_request_response_types()
        assert len(req_resp) >= 1


class TestAuthorityRepresentation:
    """Tests for authoritative representation selection."""

    def test_sqlalchemy_takes_priority_over_pydantic(self):
        """Test that SQLAlchemy models are selected as authoritative over Pydantic."""
        models = [
            DataModel(name="User", module="auth", type="sqlalchemy", file_path="auth/models.py"),
            DataModel(name="User_dto", module="api", type="pydantic", file_path="api/schemas.py"),
        ]
        modules = [
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=[m.__dict__ for m in models], modules=modules)
        resolver = CanonicalModelResolver(aggregator.data_models)

        assert len(resolver.canonical_models) == 1
        assert resolver.canonical_models[0].authority_type == "sqlalchemy"

    def test_authority_path_is_set(self):
        """Test that authority path is set correctly."""
        models = [
            DataModel(name="User", module="auth", type="sqlalchemy", file_path="auth/models.py"),
        ]
        modules = [
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=[m.__dict__ for m in models], modules=modules)
        resolver = CanonicalModelResolver(aggregator.data_models)

        assert resolver.canonical_models[0].authority_path == "auth/models.py"


class TestModelMetadata:
    """Tests for model metadata assignment."""

    def test_model_gets_canonical_name(self):
        """Test that models get canonical_name assigned."""
        models = [
            DataModel(name="User", module="auth", type="sqlalchemy", file_path="auth/models.py"),
            DataModel(name="User_dto", module="api", type="pydantic", file_path="api/schemas.py"),
        ]
        modules = [
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=[m.__dict__ for m in models], modules=modules)
        resolver = CanonicalModelResolver(aggregator.data_models)

        for model in aggregator.data_models:
            assert model.canonical_name != ""
            assert model.model_category != "unknown"

    def test_projections_are_populated(self):
        """Test that projections list is populated for duplicate models."""
        models = [
            DataModel(name="User", module="auth", type="sqlalchemy", file_path="auth/models.py"),
            DataModel(name="User_dto", module="api", type="pydantic", file_path="api/schemas.py"),
        ]
        modules = [
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=[m.__dict__ for m in models], modules=modules)
        resolver = CanonicalModelResolver(aggregator.data_models)

        for model in aggregator.data_models:
            if model.name == "User":
                assert "User_dto" in model.projections


class TestSummarization:
    """Tests for canonical model summarization."""

    def test_summarize_canonical_models(self):
        """Test that summary contains category counts."""
        models = [
            DataModel(name="User", module="auth", type="sqlalchemy", file_path="auth/models.py"),
            DataModel(name="UserDTO", module="api", type="pydantic", file_path="api/schemas.py"),
            DataModel(name="LoginRequest", module="api", type="pydantic", file_path="api/schemas.py"),
        ]
        modules = [
            {"name": "auth", "domain": "core-platform", "service_family": "python-backend"},
            {"name": "api", "domain": "api-gateway", "service_family": "python-backend"},
        ]

        aggregator = DataModelAggregator(models=[m.__dict__ for m in models], modules=modules)
        resolver = CanonicalModelResolver(aggregator.data_models)

        summary = resolver.summarize_canonical_models()
        assert "规范模型解析结果" in summary
        assert "core_entity" in summary or "dto" in summary or "request_response" in summary
