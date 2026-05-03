"""Entity relationship composer for generating ER diagram articles.

This composer generates articles that explain:
- Entity relationships between data models
- ER diagram generation from canonical model metadata
- Schema definitions and foreign key references

Phase 26 - Task 26.4: Entity relationship composer

Integration with existing pipeline:
- Uses DataModelAggregator for model analysis
- Uses CanonicalModelResolver for entity deduplication
- Uses MermaidPlanner/MermaidRenderer for ER diagram generation
- Uses LLMPageComposer for prose generation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from repo_wiki.core.contracts import RepositorySnapshot
from repo_wiki.evidence.ranking import PageEvidenceBinding
from repo_wiki.generator.composer import (
    ComposerContext,
    ComposerOutput,
    build_composer_input,
    create_composer,
)
from repo_wiki.generator.engine import (
    CanonicalModel,
    CanonicalModelResolver,
    DataModel,
    DataModelAggregator,
    ModelCategory,
)
from repo_wiki.generator.mermaid_planner import (
    DiagramPlan,
    MermaidDiagramType,
    create_planner,
    create_renderer,
)
from repo_wiki.llm.providers import MockLLMProvider
from repo_wiki.planner.schema import WikiPagePlan

# =============================================================================
# ENTITY RELATIONSHIP COMPOSER
# =============================================================================


@dataclass
class EntityRelationshipInfo:
    """Information about entity relationships."""

    source_entity: str
    target_entity: str
    relationship_type: str  # "has_one", "has_many", "references", "belongs_to"
    source_module: str
    target_module: str
    source_file_path: str
    target_file_path: str
    is_foreign_key: bool = False
    is_core_entity_relation: bool = False


@dataclass
class EntityInfo:
    """Information about an entity for ER diagram."""

    name: str
    canonical_name: str
    category: str
    module: str
    file_path: str
    attributes: list[str] = field(default_factory=list)
    primary_key: str = "id"
    is_high_frequency: bool = False
    projections: list[str] = field(default_factory=list)


class EntityRelationshipComposer:
    """Composer for entity relationship and ER diagram articles.

    This composer takes data model information and generates:
    - Entity relationship overview articles
    - ER diagrams with schema definitions and foreign key references
    - Citation of source files and schema definitions

    Integration with existing pipeline:
    - Uses DataModelAggregator for model analysis
    - Uses CanonicalModelResolver for entity deduplication
    - Uses MermaidPlanner/MermaidRenderer for ER diagram generation
    """

    def __init__(
        self,
        snapshot: RepositorySnapshot,
        llm_provider: MockLLMProvider | None = None,
        workspace_root: str | Path | None = None,
    ) -> None:
        """Initialize the entity relationship composer.

        Args:
            snapshot: Repository snapshot with data models
            llm_provider: Optional LLM provider (uses mock if not provided)
            workspace_root: Optional workspace root for path resolution
        """
        self.snapshot = snapshot
        self.workspace_root = Path(workspace_root) if workspace_root else None
        self._llm_composer = create_composer(
            provider=llm_provider,
            workspace_root=workspace_root,
        )
        self._mermaid_planner = create_planner(workspace_root=workspace_root)
        self._mermaid_renderer = create_renderer()
        self._build_entity_info()

    def _build_entity_info(self) -> None:
        """Build entity information from snapshot data models."""
        # Build model dicts for DataModelAggregator
        models_dicts = [
            {
                "name": m.name,
                "module": m.module,
                "type": m.type,
                "file_path": m.file_path,
            }
            for m in self.snapshot.data_models
        ]

        modules_dicts = [
            {
                "name": m.name,
                "domain": getattr(m, "domain", None) or "unknown",
                "service_family": getattr(m, "service_family", None) or "unknown",
            }
            for m in self.snapshot.modules
        ]

        endpoints_dicts = [
            {
                "name": ep.handler or f"{ep.method} {ep.path}",
                "module": ep.module,
                "method": ep.method,
                "path": ep.path,
            }
            for ep in self.snapshot.endpoints
        ]

        self._aggregator = DataModelAggregator(
            models=models_dicts,
            modules=modules_dicts,
            endpoints=endpoints_dicts,
        )

        # Use CanonicalModelResolver for entity deduplication
        self._resolver = CanonicalModelResolver(self._aggregator.data_models)

        # Build entity info list
        self._entities: list[EntityInfo] = []
        self._entity_by_name: dict[str, EntityInfo] = {}

        for canonical in self._resolver.canonical_models:
            # Get the authoritative model
            auth_model = canonical.models[0] if canonical.models else None

            entity_info = EntityInfo(
                name=auth_model.name if auth_model else canonical.canonical_name,
                canonical_name=canonical.canonical_name,
                category=canonical.category,
                module=auth_model.module if auth_model else "unknown",
                file_path=auth_model.file_path if auth_model else "",
                attributes=self._extract_attributes(canonical),
                primary_key=self._infer_primary_key(canonical),
                is_high_frequency=canonical.is_high_frequency,
                projections=canonical.models[1:] if len(canonical.models) > 1 else [],
            )

            self._entities.append(entity_info)
            self._entity_by_name[canonical.canonical_name.lower()] = entity_info

        # Build relationships
        self._relationships = self._build_relationships()

    def _extract_attributes(self, canonical: CanonicalModel) -> list[str]:
        """Extract attributes from canonical model."""
        attributes = []
        for model in canonical.models:
            # Use model type as attribute indicator
            if model.type not in attributes:
                attributes.append(model.type)
        return attributes

    def _infer_primary_key(self, canonical: CanonicalModel) -> str:
        """Infer primary key from canonical model."""
        # High-frequency models often have 'id' as primary key
        if canonical.is_high_frequency:
            return "id"
        # Check model names for 'id' pattern
        for model in canonical.models:
            if "id" in model.name.lower():
                return "id"
        return "id"  # Default

    def _build_relationships(self) -> list[EntityRelationshipInfo]:
        """Build entity relationships from canonical models."""
        relationships: list[EntityRelationshipInfo] = []

        # Build dedup key lookup
        dedup_key_to_entity: dict[str, EntityInfo] = {}
        for entity in self._entities:
            key = entity.canonical_name.lower()
            dedup_key_to_entity[key] = entity

        # Analyze relationships based on:
        # 1. Shared entities across modules (has_many)
        # 2. Naming patterns (_id -> foreign key reference)
        # 3. Module ownership patterns

        for canonical in self._resolver.canonical_models:
            if len(canonical.models) < 2:
                continue

            # Multiple projections of the same entity indicate close relationship
            for i, model in enumerate(canonical.models):
                for other_model in canonical.models[i + 1 :]:
                    # Determine relationship type based on modules
                    rel_type = self._determine_relationship_type(model, other_model)

                    source_entity = self._find_entity_for_model(model)
                    target_entity = self._find_entity_for_model(other_model)

                    if source_entity and target_entity:
                        rel = EntityRelationshipInfo(
                            source_entity=source_entity.canonical_name,
                            target_entity=target_entity.canonical_name,
                            relationship_type=rel_type,
                            source_module=model.module,
                            target_module=other_model.module,
                            source_file_path=model.file_path,
                            target_file_path=other_model.file_path,
                            is_foreign_key=self._is_foreign_key_relation(model, other_model),
                            is_core_entity_relation=canonical.category == ModelCategory.CORE_ENTITY,
                        )
                        relationships.append(rel)

        return relationships

    def _find_entity_for_model(self, model: DataModel) -> EntityInfo | None:
        """Find entity info for a model."""
        # First try exact match by canonical name
        model_name_lower = model.name.lower()
        if model_name_lower in self._entity_by_name:
            return self._entity_by_name[model_name_lower]

        # Then try matching projections
        for projection in model.projections:
            if isinstance(projection, str):
                proj_lower = projection.lower()
                if proj_lower in self._entity_by_name:
                    return self._entity_by_name[proj_lower]

        return None

    def _determine_relationship_type(self, model1: DataModel, model2: DataModel) -> str:
        """Determine relationship type between two models."""
        # If models are in same module, likely has_one/has_many within service
        if model1.module == model2.module:
            # Same module - could be composition
            if model1.name.lower() + "_item" == model2.name.lower():
                return "has_many"
            if "_item" in model2.name.lower():
                return "belongs_to"
            return "has_one"

        # Different modules - cross-module relationship
        return "references"

    def _is_foreign_key_relation(self, model1: DataModel, model2: DataModel) -> bool:
        """Check if relationship is a foreign key reference."""
        # Pattern: target_entity_id in source model name
        for model in [model1, model2]:
            if model.name.lower().endswith("_id"):
                return True
            if "_id" in model.name.lower():
                return True
        return False

    def compose_er_diagram_page(
        self,
        page_plan: WikiPagePlan,
        evidence_binding: PageEvidenceBinding | None = None,
    ) -> ComposerOutput:
        """Compose an ER diagram page.

        Args:
            page_plan: WikiPagePlan for the ER diagram page
            evidence_binding: Optional evidence binding

        Returns:
            ComposerOutput with generated Markdown
        """
        # Get entities and relationships for this page
        entities = self._get_entities_for_page(page_plan)
        relationships = self._get_relationships_for_page(page_plan)

        # Build context
        context = self._build_er_context(page_plan, entities, relationships)

        # Generate ER diagram
        er_diagram = self._generate_er_diagram(entities, relationships)

        # Compose with LLM
        return self._compose_er_article(
            page_plan=page_plan,
            evidence_binding=evidence_binding,
            context=context,
            er_diagram=er_diagram,
            entities=entities,
            relationships=relationships,
        )

    async def compose_er_diagram_page_async(
        self,
        page_plan: WikiPagePlan,
        evidence_binding: PageEvidenceBinding | None = None,
    ) -> ComposerOutput:
        """Async compose an ER diagram page.

        Args:
            page_plan: WikiPagePlan for the ER diagram page
            evidence_binding: Optional evidence binding

        Returns:
            ComposerOutput with generated Markdown
        """
        # Get entities and relationships for this page
        entities = self._get_entities_for_page(page_plan)
        relationships = self._get_relationships_for_page(page_plan)

        # Build context
        context = self._build_er_context(page_plan, entities, relationships)

        # Generate ER diagram
        er_diagram = self._generate_er_diagram(entities, relationships)

        # Compose with LLM (async)
        return await self._compose_er_article_async(
            page_plan=page_plan,
            evidence_binding=evidence_binding,
            context=context,
            er_diagram=er_diagram,
            entities=entities,
            relationships=relationships,
        )

    def _get_entities_for_page(self, page_plan: WikiPagePlan) -> list[EntityInfo]:
        """Get entities relevant to a page."""
        if page_plan.source_requirements and page_plan.source_requirements.data_models:
            # Filter by source requirements
            model_names = set(name.lower() for name in page_plan.source_requirements.data_models)
            return [
                e
                for e in self._entities
                if e.canonical_name.lower() in model_names or e.name.lower() in model_names
            ]

        # Return all entities (for overview page)
        return self._entities[:20]  # Limit to 20 for performance

    def _get_relationships_for_page(
        self,
        page_plan: WikiPagePlan,
    ) -> list[EntityRelationshipInfo]:
        """Get relationships relevant to a page."""
        # Get entities for this page
        entity_names = {e.canonical_name for e in self._get_entities_for_page(page_plan)}

        # Filter relationships
        return [
            r
            for r in self._relationships
            if r.source_entity in entity_names or r.target_entity in entity_names
        ]

    def _build_er_context(
        self,
        page_plan: WikiPagePlan,
        entities: list[EntityInfo],
        relationships: list[EntityRelationshipInfo],
    ) -> dict[str, Any]:
        """Build context for ER composition."""
        context: dict[str, Any] = {
            "page_id": page_plan.page_id,
            "title": page_plan.title,
            "entity_count": len(entities),
            "relationship_count": len(relationships),
        }

        # Group by category
        by_category: dict[str, list[str]] = {}
        for entity in entities:
            if entity.category not in by_category:
                by_category[entity.category] = []
            by_category[entity.category].append(entity.canonical_name)
        context["entities_by_category"] = by_category

        # High-frequency entities
        high_freq = [e for e in entities if e.is_high_frequency]
        context["high_frequency_entities"] = [e.canonical_name for e in high_freq]

        # Core entity relationships
        core_rels = [r for r in relationships if r.is_core_entity_relation]
        context["core_entity_relationships"] = len(core_rels)

        return context

    def _generate_er_diagram(
        self,
        entities: list[EntityInfo],
        relationships: list[EntityRelationshipInfo],
    ) -> str:
        """Generate ER diagram using Mermaid syntax."""
        # Build diagram plan
        er_entities = []
        for entity in entities:
            er_entities.append(
                {
                    "entity": entity.canonical_name,
                    "attributes": entity.attributes,
                    "primary_key": entity.primary_key,
                }
            )

        plan = DiagramPlan(
            diagram_id="entity-relationship",
            diagram_type=MermaidDiagramType.ER_DIAGRAM,
            title="Entity Relationship Diagram",
            er_entities=er_entities,
        )

        return self._mermaid_renderer.render_diagram(plan)

    def _compose_er_article(
        self,
        page_plan: WikiPagePlan,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
        er_diagram: str,
        entities: list[EntityInfo],
        relationships: list[EntityRelationshipInfo],
    ) -> ComposerOutput:
        """Compose ER article using LLM."""
        import asyncio

        return asyncio.run(
            self._compose_er_article_async(
                page_plan, evidence_binding, context, er_diagram, entities, relationships
            )
        )

    async def _compose_er_article_async(
        self,
        page_plan: WikiPagePlan,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
        er_diagram: str,
        entities: list[EntityInfo],
        relationships: list[EntityRelationshipInfo],
    ) -> ComposerOutput:
        """Async compose ER article."""
        # Build composer context
        composer_context = ComposerContext(
            repository_name=getattr(self.snapshot.repository, "name", "unknown"),
            primary_language=getattr(self.snapshot.repository, "language", "python"),
            framework=getattr(self.snapshot.repository, "framework", "unknown"),
            repository_root=str(self.workspace_root) if self.workspace_root else ".",
            models=[
                {
                    "name": e.canonical_name,
                    "type": e.category,
                    "module": e.module,
                    "file_path": e.file_path,
                }
                for e in entities[:20]
            ],
        )

        # Build composer input
        composer_input = build_composer_input(
            page_plan=page_plan,
            evidence_binding=evidence_binding,
            context=composer_context,
        )

        # Delegate to LLM composer
        return await self._llm_composer.compose_page(composer_input)

    def format_entity_relationship_narrative(
        self,
        entities: list[EntityInfo],
        relationships: list[EntityRelationshipInfo],
    ) -> str:
        """Format entity relationship narrative.

        Args:
            entities: List of entities
            relationships: List of relationships

        Returns:
            Prose describing entity relationships
        """
        if not entities:
            return "No entity relationship information available."

        parts = ["### 实体关系概览\n"]

        # Entity summary by category
        by_category: dict[str, list[EntityInfo]] = {}
        for entity in entities:
            if entity.category not in by_category:
                by_category[entity.category] = []
            by_category[entity.category].append(entity)

        parts.append(f"**Entity categories**: {len(entities)} entities total\n")
        for category, cats_entities in sorted(by_category.items()):
            entity_names = [e.canonical_name for e in cats_entities]
            parts.append(f"- **{category}** ({len(cats_entities)}): {', '.join(entity_names[:5])}")
            if len(entity_names) > 5:
                parts.append(f"  - ... and {len(entity_names) - 5} more")

        parts.append("")

        # Relationship summary
        if relationships:
            parts.append(f"**Relationship summary**: {len(relationships)} relationships total\n")

            rel_by_type: dict[str, int] = {}
            for rel in relationships:
                rel_by_type[rel.relationship_type] = rel_by_type.get(rel.relationship_type, 0) + 1

            for rel_type, count in sorted(rel_by_type.items()):
                parts.append(f"- {rel_type}: {count}")

            parts.append("")

            # Core entity relationships
            core_rels = [r for r in relationships if r.is_core_entity_relation]
            if core_rels:
                parts.append("**Core entity relationships**:\n")
                for rel in core_rels[:5]:
                    parts.append(
                        f"- {rel.source_entity} --[{rel.relationship_type}]--> {rel.target_entity}"
                    )
                    parts.append(f"  - 源: <cite>{rel.source_file_path}</cite>")
                    parts.append(f"  - 目标: <cite>{rel.target_file_path}</cite>")

        return "\n".join(parts)

    def format_er_diagram_markdown(self, er_diagram: str) -> str:
        """Format ER diagram as markdown code block.

        Args:
            er_diagram: Mermaid ER diagram code

        Returns:
            Markdown code block
        """
        return f"```mermaid\n{er_diagram}\n```"

    def format_schema_references(
        self,
        entities: list[EntityInfo],
    ) -> str:
        """Format schema references section.

        Args:
            entities: List of entities

        Returns:
            Prose describing schema references
        """
        if not entities:
            return "### Schema References\n\nNo schema reference information available."

        parts = ["### Schema 引用\n"]

        # Group by module
        by_module: dict[str, list[EntityInfo]] = {}
        for entity in entities:
            if entity.module not in by_module:
                by_module[entity.module] = []
            by_module[entity.module].append(entity)

        parts.append(f"**By module** ({len(by_module)} modules total):\n")

        for module_name in sorted(by_module.keys()):
            module_entities = by_module[module_name]
            parts.append(f"\n**{module_name}** 模块：\n")

            for entity in sorted(module_entities, key=lambda e: e.canonical_name):
                parts.append(
                    f"- `{entity.canonical_name}` ({entity.category}) "
                    f"<cite>{entity.file_path}</cite>"
                )
                if entity.is_high_frequency:
                    parts.append("  - High-frequency entity")

        return "\n".join(parts)

    def format_foreign_key_references(
        self,
        relationships: list[EntityRelationshipInfo],
    ) -> str:
        """Format foreign key references section.

        Args:
            relationships: List of relationships

        Returns:
            Prose describing foreign key references
        """
        fk_rels = [r for r in relationships if r.is_foreign_key]

        if not fk_rels:
            return "### Foreign Key References\n\nNo foreign key references detected."

        parts = ["### 外键引用\n"]
        parts.append(f"**Detected {len(fk_rels)} foreign key references**:\n")

        for rel in fk_rels[:10]:
            parts.append(f"- {rel.source_entity}.{rel.target_entity}_id -> {rel.target_entity}.id")
            parts.append(f"  - 源实体: {rel.source_entity} <cite>{rel.source_file_path}</cite>")
            parts.append(f"  - 目标实体: {rel.target_entity} <cite>{rel.target_file_path}</cite>")

        return "\n".join(parts)

    def get_entity_summary(self) -> dict[str, Any]:
        """Get entity summary statistics.

        Returns:
            Dictionary with entity summary
        """
        return {
            "total_entities": len(self._entities),
            "by_category": {
                cat: len([e for e in self._entities if e.category == cat])
                for cat in set(e.category for e in self._entities)
            },
            "high_frequency_count": len([e for e in self._entities if e.is_high_frequency]),
            "core_entity_count": len(
                [e for e in self._entities if e.category == ModelCategory.CORE_ENTITY]
            ),
            "total_relationships": len(self._relationships),
            "fk_relationships": len([r for r in self._relationships if r.is_foreign_key]),
        }


# =============================================================================
# COMPOSER FACTORY
# =============================================================================


def create_entity_relationship_composer(
    snapshot: RepositorySnapshot,
    llm_provider: MockLLMProvider | None = None,
    workspace_root: str | Path | None = None,
) -> EntityRelationshipComposer:
    """Create an entity relationship composer.

    Args:
        snapshot: Repository snapshot with data models
        llm_provider: Optional LLM provider
        workspace_root: Optional workspace root

    Returns:
        EntityRelationshipComposer instance
    """
    return EntityRelationshipComposer(
        snapshot=snapshot,
        llm_provider=llm_provider,
        workspace_root=workspace_root,
    )


# =============================================================================
# STANDALONE COMPOSITION HELPERS
# =============================================================================


def compose_entity_relationship_article(
    page_plan: WikiPagePlan,
    snapshot: RepositorySnapshot,
    evidence_binding: PageEvidenceBinding | None = None,
    llm_provider: MockLLMProvider | None = None,
    workspace_root: str | Path | None = None,
) -> ComposerOutput:
    """Convenience function to compose an entity relationship article.

    Args:
        page_plan: WikiPagePlan for the ER page
        snapshot: Repository snapshot with data models
        evidence_binding: Optional evidence binding
        llm_provider: Optional LLM provider
        workspace_root: Optional workspace root

    Returns:
        ComposerOutput with generated content
    """
    composer = create_entity_relationship_composer(
        snapshot=snapshot,
        llm_provider=llm_provider,
        workspace_root=workspace_root,
    )
    return composer.compose_er_diagram_page(page_plan, evidence_binding)


async def compose_entity_relationship_article_async(
    page_plan: WikiPagePlan,
    snapshot: RepositorySnapshot,
    evidence_binding: PageEvidenceBinding | None = None,
    llm_provider: MockLLMProvider | None = None,
    workspace_root: str | Path | None = None,
) -> ComposerOutput:
    """Async convenience function to compose an entity relationship article.

    Args:
        page_plan: WikiPagePlan for the ER page
        snapshot: Repository snapshot with data models
        evidence_binding: Optional evidence binding
        llm_provider: Optional LLM provider
        workspace_root: Optional workspace root

    Returns:
        ComposerOutput with generated content
    """
    composer = create_entity_relationship_composer(
        snapshot=snapshot,
        llm_provider=llm_provider,
        workspace_root=workspace_root,
    )
    return await composer.compose_er_diagram_page_async(page_plan, evidence_binding)


# =============================================================================
# ENTITY RELATIONSHIP INFO EXTRACTION
# =============================================================================


def extract_entity_relationships(
    snapshot: RepositorySnapshot,
) -> tuple[list[EntityInfo], list[EntityRelationshipInfo]]:
    """Extract entity relationships from repository snapshot.

    Args:
        snapshot: Repository snapshot with data models

    Returns:
        Tuple of (entities, relationships)
    """
    composer = EntityRelationshipComposer(snapshot=snapshot)
    return composer._entities, composer._relationships


def get_entity_summary(
    snapshot: RepositorySnapshot,
) -> dict[str, Any]:
    """Get summary of entities and relationships.

    Args:
        snapshot: Repository snapshot with data models

    Returns:
        Entity summary dictionary
    """
    composer = EntityRelationshipComposer(snapshot=snapshot)
    return composer.get_entity_summary()
