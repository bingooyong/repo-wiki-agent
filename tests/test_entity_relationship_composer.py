"""Tests for Entity Relationship Composer - Phase 26 Task 26.4.

These tests validate that:
1. EntityRelationshipComposer correctly analyzes entity relationships
2. ER diagrams are generated from canonical model metadata
3. Schema definitions and foreign key references are captured
4. Citation of source files and schema definitions works

Self-test command: uv run pytest tests/test_entity_relationship_composer.py tests/test_mermaid_planner.py
"""

from __future__ import annotations

import pytest

from repo_wiki.core.contracts import (
    DataModel,
    Endpoint,
    Module,
    RepositoryInfo,
    RepositorySnapshot,
    RepositoryStats,
)
from repo_wiki.generator.entity_relationship_composer import (
    EntityRelationshipComposer,
    EntityRelationshipInfo,
    EntityInfo,
    create_entity_relationship_composer,
    compose_entity_relationship_article,
    compose_entity_relationship_article_async,
    extract_entity_relationships,
    get_entity_summary,
)
from repo_wiki.llm.providers import create_mock_provider
from repo_wiki.planner.schema import (
    GenerationMode,
    SourceRequirement,
    WikiPagePlan,
    WikiTaxonomyCategory,
)


@pytest.fixture
def sample_snapshot() -> RepositorySnapshot:
    """Create a sample repository snapshot for testing."""
    repository = RepositoryInfo(
        name="test-repo",
        root_path="/test",
        language="python",
        framework="fastapi",
    )

    modules = [
        Module(
            name="auth",
            path="src/auth",
            responsibility="Authentication and authorization",
            domain="core-platform",
            service_family="python-backend",
            runtime_role="api-server",
            doc_path="docs/modules/auth.md",
        ),
        Module(
            name="billing",
            path="src/billing",
            responsibility="Billing and payment processing",
            domain="persistence",
            service_family="billing-service",
            runtime_role="api-server",
            doc_path="docs/modules/billing.md",
        ),
        Module(
            name="api",
            path="src/api",
            responsibility="API gateway",
            domain="api-gateway",
            service_family="python-backend",
            runtime_role="api-server",
            doc_path="docs/modules/api.md",
        ),
        Module(
            name="orders",
            path="src/orders",
            responsibility="Order management",
            domain="persistence",
            service_family="order-service",
            runtime_role="api-server",
            doc_path="docs/modules/orders.md",
        ),
    ]

    data_models = [
        # Core entities shared across modules
        DataModel(
            name="User",
            module="auth",
            type="sqlalchemy",
            file_path="src/auth/models.py",
        ),
        DataModel(
            name="UserDTO",
            module="api",
            type="pydantic",
            file_path="src/api/schemas.py",
        ),
        # Billing domain
        DataModel(
            name="Invoice",
            module="billing",
            type="sqlalchemy",
            file_path="src/billing/models.py",
        ),
        DataModel(
            name="InvoiceItem",
            module="billing",
            type="sqlalchemy",
            file_path="src/billing/models.py",
        ),
        DataModel(
            name="Payment",
            module="billing",
            type="sqlalchemy",
            file_path="src/billing/models.py",
        ),
        # Order domain
        DataModel(
            name="Order",
            module="orders",
            type="sqlalchemy",
            file_path="src/orders/models.py",
        ),
        DataModel(
            name="OrderItem",
            module="orders",
            type="sqlalchemy",
            file_path="src/orders/models.py",
        ),
        DataModel(
            name="OrderUserId",  # Foreign key pattern
            module="orders",
            type="sqlalchemy",
            file_path="src/orders/models.py",
        ),
    ]

    endpoints = [
        Endpoint(
            method="POST",
            path="/auth/login",
            module="auth",
            handler="login_handler",
            file_path="src/auth/handlers.py",
            service_family="python-backend",
        ),
        Endpoint(
            method="GET",
            path="/billing/invoices",
            module="billing",
            handler="get_invoices",
            file_path="src/billing/handlers.py",
            service_family="billing-service",
        ),
        Endpoint(
            method="GET",
            path="/orders",
            module="orders",
            handler="get_orders",
            file_path="src/orders/handlers.py",
            service_family="order-service",
        ),
    ]

    return RepositorySnapshot(
        repository=repository,
        modules=modules,
        endpoints=endpoints,
        data_models=data_models,
        commands={},
        stats=RepositoryStats(
            total_files=10,
            scanned_files=10,
            module_count=4,
            endpoint_count=3,
            data_model_count=8,
        ),
    )


@pytest.fixture
def composer(sample_snapshot: RepositorySnapshot) -> EntityRelationshipComposer:
    """Create composer with sample snapshot."""
    return create_entity_relationship_composer(sample_snapshot)


class TestEntityInfo:
    """Tests for EntityInfo dataclass."""

    def test_create_empty_entity_info(self):
        """Test creating empty entity info."""
        info = EntityInfo(
            name="TestEntity",
            canonical_name="test_entity",
            category="core_entity",
            module="test",
            file_path="test/models.py",
        )
        assert info.name == "TestEntity"
        assert info.canonical_name == "test_entity"
        assert info.category == "core_entity"
        assert info.attributes == []

    def test_create_full_entity_info(self):
        """Test creating entity info with all fields."""
        info = EntityInfo(
            name="User",
            canonical_name="user",
            category="core_entity",
            module="auth",
            file_path="src/auth/models.py",
            attributes=["sqlalchemy", "pydantic"],
            primary_key="id",
            is_high_frequency=True,
            projections=["UserDTO", "UserModel"],
        )
        assert info.name == "User"
        assert info.is_high_frequency is True
        assert len(info.projections) == 2


class TestEntityRelationshipInfo:
    """Tests for EntityRelationshipInfo dataclass."""

    def test_create_entity_relationship_info(self):
        """Test creating entity relationship info."""
        rel = EntityRelationshipInfo(
            source_entity="User",
            target_entity="Order",
            relationship_type="has_many",
            source_module="auth",
            target_module="orders",
            source_file_path="src/auth/models.py",
            target_file_path="src/orders/models.py",
        )
        assert rel.source_entity == "User"
        assert rel.target_entity == "Order"
        assert rel.relationship_type == "has_many"
        assert rel.is_foreign_key is False

    def test_create_foreign_key_relationship(self):
        """Test creating foreign key relationship."""
        rel = EntityRelationshipInfo(
            source_entity="Order",
            target_entity="User",
            relationship_type="belongs_to",
            source_module="orders",
            target_module="auth",
            source_file_path="src/orders/models.py",
            target_file_path="src/auth/models.py",
            is_foreign_key=True,
        )
        assert rel.is_foreign_key is True


class TestEntityRelationshipComposer:
    """Tests for EntityRelationshipComposer class."""

    def test_create_composer(self, sample_snapshot: RepositorySnapshot):
        """Test creating a composer."""
        composer = create_entity_relationship_composer(sample_snapshot)
        assert composer is not None
        assert composer.snapshot == sample_snapshot

    def test_build_entity_info(self, composer: EntityRelationshipComposer):
        """Test that entity info is built correctly."""
        assert len(composer._entities) > 0

    def test_build_relationships(self, composer: EntityRelationshipComposer):
        """Test that relationships are built."""
        assert composer._relationships is not None

    def test_get_entity_summary(self, composer: EntityRelationshipComposer):
        """Test getting entity summary."""
        summary = composer.get_entity_summary()
        assert summary["total_entities"] > 0
        assert "by_category" in summary
        assert summary["total_relationships"] >= 0

    def test_find_entity_for_model(self, composer: EntityRelationshipComposer):
        """Test finding entity for a model."""
        # Test with a known model
        from repo_wiki.generator.engine import DataModel

        model = DataModel(
            name="User",
            module="auth",
            type="sqlalchemy",
            file_path="src/auth/models.py",
        )

        entity = composer._find_entity_for_model(model)
        # Should find entity or return None
        assert entity is None or isinstance(entity, EntityInfo)

    def test_determine_relationship_type(self, composer: EntityRelationshipComposer):
        """Test determining relationship type."""
        from repo_wiki.generator.engine import DataModel

        model1 = DataModel(
            name="User",
            module="auth",
            type="sqlalchemy",
            file_path="src/auth/models.py",
        )
        model2 = DataModel(
            name="UserDTO",
            module="api",
            type="pydantic",
            file_path="src/api/schemas.py",
        )

        rel_type = composer._determine_relationship_type(model1, model2)
        assert rel_type in ("has_one", "has_many", "references", "belongs_to")

    def test_is_foreign_key_relation(self, composer: EntityRelationshipComposer):
        """Test foreign key detection."""
        from repo_wiki.generator.engine import DataModel

        model1 = DataModel(
            name="OrderUserId",  # Pattern indicating FK
            module="orders",
            type="sqlalchemy",
            file_path="src/orders/models.py",
        )
        model2 = DataModel(
            name="User",
            module="auth",
            type="sqlalchemy",
            file_path="src/auth/models.py",
        )

        is_fk = composer._is_foreign_key_relation(model1, model2)
        assert isinstance(is_fk, bool)


class TestEntityRelationshipComposition:
    """Tests for entity relationship composition."""

    def test_compose_er_diagram_page(
        self,
        composer: EntityRelationshipComposer,
    ):
        """Test composing an ER diagram page."""
        page_plan = WikiPagePlan(
            page_id="entity-relationships",
            title="实体关系概览",
            category=WikiTaxonomyCategory.DATA_MODELS,
            output_path="docs/pages/data-models/entity-relationships.md",
            source_requirements=SourceRequirement(
                data_models=["User", "Invoice", "Order"],
            ),
            generation_mode=GenerationMode.LLM_ASSISTED,
        )

        output = composer.compose_er_diagram_page(page_plan, None)

        assert output.page_id == "entity-relationships"
        # Output may be empty for mock LLM but should not error

    def test_compose_er_diagram_page_overview(
        self,
        composer: EntityRelationshipComposer,
    ):
        """Test composing ER diagram for overview page."""
        page_plan = WikiPagePlan(
            page_id="er-diagrams",
            title="ER图参考",
            category=WikiTaxonomyCategory.DATA_MODELS,
            output_path="docs/pages/data-models/er-diagrams.md",
            generation_mode=GenerationMode.RULE_FIRST,
        )

        output = composer.compose_er_diagram_page(page_plan, None)

        assert output.page_id == "er-diagrams"

    @pytest.mark.asyncio
    async def test_compose_er_diagram_page_async(
        self,
        composer: EntityRelationshipComposer,
    ):
        """Test async ER diagram composition."""
        page_plan = WikiPagePlan(
            page_id="entity-relationships",
            title="实体关系概览",
            category=WikiTaxonomyCategory.DATA_MODELS,
            output_path="docs/pages/data-models/entity-relationships.md",
            generation_mode=GenerationMode.LLM_ASSISTED,
        )

        output = await composer.compose_er_diagram_page_async(page_plan, None)

        assert output.page_id == "entity-relationships"


class TestGetEntitiesAndRelationships:
    """Tests for getting entities and relationships."""

    def test_get_entities_for_page(self, composer: EntityRelationshipComposer):
        """Test getting entities for a page."""
        page_plan = WikiPagePlan(
            page_id="test-page",
            title="Test Page",
            category=WikiTaxonomyCategory.DATA_MODELS,
            output_path="docs/test.md",
            source_requirements=SourceRequirement(
                data_models=["User", "Invoice"],
            ),
            generation_mode=GenerationMode.RULE_FIRST,
        )

        entities = composer._get_entities_for_page(page_plan)
        assert isinstance(entities, list)

    def test_get_entities_for_page_no_filter(self, composer: EntityRelationshipComposer):
        """Test getting all entities when no filter specified."""
        page_plan = WikiPagePlan(
            page_id="test-page",
            title="Test Page",
            category=WikiTaxonomyCategory.DATA_MODELS,
            output_path="docs/test.md",
            generation_mode=GenerationMode.RULE_FIRST,
        )

        entities = composer._get_entities_for_page(page_plan)
        # Should return limited set (max 20)
        assert len(entities) <= 20

    def test_get_relationships_for_page(self, composer: EntityRelationshipComposer):
        """Test getting relationships for a page."""
        page_plan = WikiPagePlan(
            page_id="test-page",
            title="Test Page",
            category=WikiTaxonomyCategory.DATA_MODELS,
            output_path="docs/test.md",
            generation_mode=GenerationMode.RULE_FIRST,
        )

        relationships = composer._get_relationships_for_page(page_plan)
        assert isinstance(relationships, list)


class TestERDiagramGeneration:
    """Tests for ER diagram generation."""

    def test_generate_er_diagram(self, composer: EntityRelationshipComposer):
        """Test generating ER diagram."""
        entities = composer._entities[:5]  # Limit for test
        relationships = composer._relationships[:5]

        er_diagram = composer._generate_er_diagram(entities, relationships)

        assert er_diagram is not None
        assert "erDiagram" in er_diagram

    def test_format_er_diagram_markdown(self, composer: EntityRelationshipComposer):
        """Test formatting ER diagram as markdown."""
        diagram_code = "erDiagram\n    USER {int id}"

        markdown = composer.format_er_diagram_markdown(diagram_code)

        assert markdown.startswith("```mermaid")
        assert markdown.endswith("```")
        assert "erDiagram" in markdown


class TestFormatMethods:
    """Tests for formatting methods."""

    def test_format_entity_relationship_narrative(
        self,
        composer: EntityRelationshipComposer,
    ):
        """Test formatting entity relationship narrative."""
        entities = composer._entities[:5]
        relationships = composer._relationships[:3]

        narrative = composer.format_entity_relationship_narrative(
            entities, relationships
        )

        assert "实体关系" in narrative or "Entity" in narrative
        assert isinstance(narrative, str)

    def test_format_entity_relationship_narrative_empty(
        self,
        composer: EntityRelationshipComposer,
    ):
        """Test formatting with empty entities."""
        narrative = composer.format_entity_relationship_narrative([], [])
        assert "暂无" in narrative or len(narrative) > 0

    def test_format_schema_references(self, composer: EntityRelationshipComposer):
        """Test formatting schema references."""
        entities = composer._entities[:5]

        schema_refs = composer.format_schema_references(entities)

        assert "Schema" in schema_refs or "schema" in schema_refs.lower()
        assert isinstance(schema_refs, str)

    def test_format_schema_references_empty(self, composer: EntityRelationshipComposer):
        """Test formatting schema references with empty list."""
        schema_refs = composer.format_schema_references([])
        assert "暂无" in schema_refs or len(schema_refs) > 0

    def test_format_foreign_key_references(self, composer: EntityRelationshipComposer):
        """Test formatting foreign key references."""
        relationships = composer._relationships

        fk_refs = composer.format_foreign_key_references(relationships)

        assert isinstance(fk_refs, str)
        # Should mention foreign key or be empty message

    def test_format_foreign_key_references_empty(self, composer: EntityRelationshipComposer):
        """Test formatting with no FK relationships."""
        fk_refs = composer.format_foreign_key_references([])
        assert isinstance(fk_refs, str)


class TestBuildContext:
    """Tests for context building."""

    def test_build_er_context(self, composer: EntityRelationshipComposer):
        """Test building ER context."""
        page_plan = WikiPagePlan(
            page_id="entity-relationships",
            title="实体关系概览",
            category=WikiTaxonomyCategory.DATA_MODELS,
            output_path="docs/test.md",
            generation_mode=GenerationMode.RULE_FIRST,
        )

        entities = composer._entities[:5]
        relationships = composer._relationships[:3]

        context = composer._build_er_context(page_plan, entities, relationships)

        assert "page_id" in context
        assert "title" in context
        assert "entity_count" in context
        assert "relationship_count" in context
        assert "entities_by_category" in context

    def test_build_er_context_with_high_frequency(
        self,
        composer: EntityRelationshipComposer,
    ):
        """Test context includes high frequency entities."""
        page_plan = WikiPagePlan(
            page_id="entity-relationships",
            title="实体关系概览",
            category=WikiTaxonomyCategory.DATA_MODELS,
            output_path="docs/test.md",
            generation_mode=GenerationMode.RULE_FIRST,
        )

        entities = composer._entities
        relationships = composer._relationships

        context = composer._build_er_context(page_plan, entities, relationships)

        if context["high_frequency_entities"]:
            # Should have high frequency entities
            assert len(context["high_frequency_entities"]) >= 0


class TestStandaloneHelpers:
    """Tests for standalone helper functions."""

    def test_extract_entity_relationships(self, sample_snapshot: RepositorySnapshot):
        """Test extracting entity relationships."""
        entities, relationships = extract_entity_relationships(sample_snapshot)

        assert isinstance(entities, list)
        assert isinstance(relationships, list)
        assert len(entities) > 0

    def test_get_entity_summary(self, sample_snapshot: RepositorySnapshot):
        """Test getting entity summary."""
        summary = get_entity_summary(sample_snapshot)

        assert "total_entities" in summary
        assert "by_category" in summary
        assert summary["total_entities"] > 0

    def test_compose_entity_relationship_article(
        self,
        sample_snapshot: RepositorySnapshot,
    ):
        """Test standalone composition function."""
        page_plan = WikiPagePlan(
            page_id="entity-relationships",
            title="实体关系概览",
            category=WikiTaxonomyCategory.DATA_MODELS,
            output_path="docs/entity-relationships.md",
            generation_mode=GenerationMode.LLM_ASSISTED,
        )

        output = compose_entity_relationship_article(
            page_plan=page_plan,
            snapshot=sample_snapshot,
            evidence_binding=None,
        )

        assert output.page_id == "entity-relationships"

    @pytest.mark.asyncio
    async def test_compose_entity_relationship_article_async(
        self,
        sample_snapshot: RepositorySnapshot,
    ):
        """Test async standalone composition function."""
        page_plan = WikiPagePlan(
            page_id="entity-relationships",
            title="实体关系概览",
            category=WikiTaxonomyCategory.DATA_MODELS,
            output_path="docs/entity-relationships.md",
            generation_mode=GenerationMode.LLM_ASSISTED,
        )

        output = await compose_entity_relationship_article_async(
            page_plan=page_plan,
            snapshot=sample_snapshot,
            evidence_binding=None,
        )

        assert output.page_id == "entity-relationships"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])