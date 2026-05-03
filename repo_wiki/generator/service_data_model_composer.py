"""Service data model composer for generating service-level data model articles.

This composer generates articles that explain:
- Service data ownership and database access patterns
- Service-specific schema variations
- Migration and storage evidence

Phase 26 - Task 26.5: Service data-model composer

Integration with existing pipeline:
- Uses LLMPageComposer for actual LLM-based content generation
- Adds service-specific context about data ownership
- Handles entity grouping by service family
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
from repo_wiki.generator.engine import DataModel, DataModelAggregator, ModelCategory
from repo_wiki.llm.providers import MockLLMProvider
from repo_wiki.planner.schema import WikiPagePlan

# =============================================================================
# SERVICE DATA MODEL COMPOSER
# =============================================================================


@dataclass
class ServiceDataModelInfo:
    """Information about a service's data models."""

    service_name: str
    domain: str
    models: list[DataModel] = field(default_factory=list)
    core_entities: list[DataModel] = field(default_factory=list)
    dtos: list[DataModel] = field(default_factory=list)
    persistence_artifacts: list[DataModel] = field(default_factory=list)
    infrastructure_models: list[DataModel] = field(default_factory=list)
    ownership_modules: list[str] = field(default_factory=list)
    related_services: list[str] = field(default_factory=list)


class ServiceDataModelComposer:
    """Composer for service-level data model articles.

    This composer takes data-model page plans organized by service family and
    generates prose-first Markdown articles that:
    - Explain service data ownership and database access patterns
    - Document service-specific schema variations
    - Include migration and storage evidence
    - Cite entity files, migrations, and service references

    Integration with existing pipeline:
    - Uses LLMPageComposer for actual LLM-based content generation
    - Adds service-specific context and formatting
    - Handles model grouping by service ownership
    """

    def __init__(
        self,
        snapshot: RepositorySnapshot,
        llm_provider: MockLLMProvider | None = None,
        workspace_root: str | Path | None = None,
    ) -> None:
        """Initialize the service data model composer.

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
        self._build_service_model_info()

    def _build_service_model_info(self) -> None:
        """Build service model information from snapshot data models."""
        # Build module lookup for service_family and domain
        module_lookup: dict[str, dict[str, str]] = {}
        for m in self.snapshot.modules:
            module_lookup[m.name] = {
                "service_family": getattr(m, "service_family", None) or "unknown",
                "domain": getattr(m, "domain", None) or "unknown",
            }

        # Use DataModelAggregator to analyze models
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
                "domain": m.domain,
                "service_family": m.service_family,
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

        # Build service-level grouping
        self._service_models: dict[str, ServiceDataModelInfo] = {}

        # Use original snapshot models for classification (they have correct model_category)
        for model in self.snapshot.data_models:
            # Get service_family and domain from model or fall back to module lookup
            service_key = getattr(model, "service_family", None)
            domain = getattr(model, "domain", None)

            # Fall back to module lookup if not present on model
            if not service_key:
                module_info = module_lookup.get(model.module, {})
                service_key = module_info.get("service_family", "unknown")
            if not domain:
                module_info = module_lookup.get(model.module, {})
                domain = module_info.get("domain", "unknown")

            if service_key is None:
                service_key = "unknown"

            is_core = getattr(model, "is_core_entity", False)
            model_cat = getattr(model, "model_category", None) or "unknown"
            migration_related = getattr(model, "migration_related", False)

            if service_key not in self._service_models:
                self._service_models[service_key] = ServiceDataModelInfo(
                    service_name=service_key,
                    domain=domain or "unknown",
                )

            info = self._service_models[service_key]
            info.models.append(model)
            info.ownership_modules = list(set(info.ownership_modules + [model.module]))

            # Categorize by model type - check both model_category and is_core_entity
            if model_cat == ModelCategory.CORE_ENTITY or is_core:
                if model not in info.core_entities:
                    info.core_entities.append(model)
            elif model_cat == ModelCategory.DTO:
                if model not in info.dtos:
                    info.dtos.append(model)
            elif model_cat == ModelCategory.INFRASTRUCTURE or migration_related:
                if model not in info.infrastructure_models:
                    info.infrastructure_models.append(model)
            else:
                # Check type for persistence artifacts
                if model.type in ("sqlalchemy", "orm", "table"):
                    if model not in info.persistence_artifacts:
                        info.persistence_artifacts.append(model)
                # Also check if type is pydantic for DTOs
                elif model.type == "pydantic" and model not in info.dtos:
                    info.dtos.append(model)

        # Find related services (services that share model names)
        self._find_related_services()

    def _find_related_services(self) -> None:
        """Find services that share data model names."""
        # Build model name -> services map
        model_to_services: dict[str, set[str]] = {}
        for service_name, info in self._service_models.items():
            for model in info.models:
                # Use dedup_key if available, otherwise use lowercase name
                dedup_key = getattr(model, "dedup_key", None) or ""
                key = f"{dedup_key or model.name.lower()}"
                if key not in model_to_services:
                    model_to_services[key] = set()
                model_to_services[key].add(service_name)

        # Update related services
        for service_name, info in self._service_models.items():
            for model in info.models:
                dedup_key = getattr(model, "dedup_key", None) or ""
                key = f"{dedup_key or model.name.lower()}"
                related = model_to_services.get(key, set()) - {service_name}
                info.related_services = list(set(info.related_services + list(related)))

    def compose_data_model_page(
        self,
        page_plan: WikiPagePlan,
        evidence_binding: PageEvidenceBinding | None = None,
    ) -> ComposerOutput:
        """Compose a single data model page for a service.

        Args:
            page_plan: WikiPagePlan for the data model page (e.g., data-model-billing)
            evidence_binding: Optional evidence binding for this page

        Returns:
            ComposerOutput with generated Markdown
        """
        # Extract service family from page ID
        service_family = self._extract_service_family(page_plan.page_id)

        # Get service model info
        service_info = self._get_service_info(service_family, page_plan)

        # Build service context for composition
        context = self._build_service_context(page_plan, service_info)

        # Use the LLM composer to generate the actual content
        return self._compose_with_llm(page_plan, evidence_binding, context, service_info)

    def _extract_service_family(self, page_id: str) -> str | None:
        """Extract service family name from page ID.

        Args:
            page_id: Page ID like 'data-model-billing' or 'data-model-python-backend'

        Returns:
            Service family name or None
        """
        if not page_id.startswith("data-model-"):
            return None

        parts = page_id.split("-")[2:]  # Skip "data-model" prefix
        if parts:
            return "-".join(parts)
        return None

    def _get_service_info(
        self,
        service_family: str | None,
        page_plan: WikiPagePlan | None,
    ) -> ServiceDataModelInfo:
        """Get service model information.

        Args:
            service_family: Service family to filter by
            page_plan: The page plan with source requirements

        Returns:
            ServiceDataModelInfo for the service
        """
        # If page has specific models in source requirements, use those
        if (
            page_plan
            and page_plan.source_requirements
            and page_plan.source_requirements.data_models
        ):
            model_names = set(page_plan.source_requirements.data_models)
            all_models: list[DataModel] = []
            for info in self._service_models.values():
                for model in info.models:
                    if model.name in model_names:
                        all_models.append(model)
            if all_models:
                # Safely get domain attribute
                domain = getattr(all_models[0], "domain", None) or "unknown"
                service_info = ServiceDataModelInfo(
                    service_name=service_family or "unknown",
                    domain=domain,
                    models=all_models,
                )
                return service_info

        # Otherwise use service family
        if service_family and service_family in self._service_models:
            return self._service_models[service_family]

        # Return empty info for unknown services
        return ServiceDataModelInfo(
            service_name=service_family or "unknown",
            domain="unknown",
        )

    def _build_service_context(
        self,
        page_plan: WikiPagePlan,
        service_info: ServiceDataModelInfo,
    ) -> dict[str, Any]:
        """Build service context for composition.

        Args:
            page_plan: The page plan
            service_info: Service model information

        Returns:
            Context dict for LLM composition
        """
        context: dict[str, Any] = {
            "page_id": page_plan.page_id,
            "title": page_plan.title,
            "service_name": service_info.service_name,
            "domain": service_info.domain,
            "model_count": len(service_info.models),
            "core_entity_count": len(service_info.core_entities),
            "dto_count": len(service_info.dtos),
            "persistence_count": len(service_info.persistence_artifacts),
            "infrastructure_count": len(service_info.infrastructure_models),
        }

        # Get ownership modules
        context["ownership_modules"] = service_info.ownership_modules

        # Get related services
        context["related_services"] = service_info.related_services

        # Build model summary
        model_types: dict[str, int] = {}
        for model in service_info.models:
            model_types[model.type] = model_types.get(model.type, 0) + 1
        context["model_types"] = model_types

        # Check for migration evidence
        has_migrations = any(
            getattr(model, "migration_related", False) for model in service_info.models
        )
        context["has_migration_evidence"] = has_migrations

        # Check for persistence artifacts
        context["has_persistence_artifacts"] = len(service_info.persistence_artifacts) > 0

        return context

    async def compose_data_model_page_async(
        self,
        page_plan: WikiPagePlan,
        evidence_binding: PageEvidenceBinding | None = None,
    ) -> ComposerOutput:
        """Async version of compose_data_model_page.

        Args:
            page_plan: WikiPagePlan for the data model page
            evidence_binding: Optional evidence binding

        Returns:
            ComposerOutput with generated Markdown
        """
        service_family = self._extract_service_family(page_plan.page_id)
        service_info = self._get_service_info(service_family, page_plan)
        context = self._build_service_context(page_plan, service_info)

        # Build composer context for LLM
        composer_context = self._create_composer_context(page_plan, context, service_info)

        # Build composer input
        composer_input = build_composer_input(
            page_plan=page_plan,
            evidence_binding=evidence_binding,
            context=composer_context,
        )

        # Delegate to LLM composer
        return await self._llm_composer.compose_page(composer_input)

    def _create_composer_context(
        self,
        page_plan: WikiPagePlan,
        service_context: dict[str, Any],
        service_info: ServiceDataModelInfo,
    ) -> ComposerContext:
        """Create ComposerContext for LLM composition.

        Args:
            page_plan: The page plan
            service_context: Service-specific context
            service_info: Service model information

        Returns:
            ComposerContext ready for LLM composition
        """
        # Build models summary
        models_summary = [
            {
                "name": model.name,
                "type": model.type,
                "module": model.module,
                "file_path": model.file_path,
                "is_core_entity": getattr(model, "is_core_entity", False),
                "migration_related": getattr(model, "migration_related", False),
            }
            for model in service_info.models[:20]  # Limit to 20 models
        ]

        return ComposerContext(
            repository_name=service_context.get("service_name", "unknown"),
            primary_language="python",
            framework="fastapi",
            repository_root=str(self.workspace_root) if self.workspace_root else ".",
            models=models_summary,
        )

    def _compose_with_llm(
        self,
        page_plan: WikiPagePlan,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
        service_info: ServiceDataModelInfo,
    ) -> ComposerOutput:
        """Generate content using LLM composer.

        This is a synchronous wrapper that uses the underlying async method.
        """
        import asyncio

        return asyncio.run(self.compose_data_model_page_async(page_plan, evidence_binding))

    def format_service_data_ownership(self, service_info: ServiceDataModelInfo) -> str:
        """Format service data ownership narrative.

        Args:
            service_info: Service model information

        Returns:
            Prose describing data ownership patterns
        """
        if not service_info.models:
            return f"服务 **{service_info.service_name}** 没有关联的数据模型。"

        parts = ["### 数据所有权\n"]
        parts.append(f"服务 **{service_info.service_name}** 拥有以下数据模型：\n")

        # Core entities
        if service_info.core_entities:
            entity_names = [m.name for m in service_info.core_entities]
            parts.append(f"- **核心实体** ({len(entity_names)}): {', '.join(entity_names)}")

        # DTOs
        if service_info.dtos:
            dto_names = [m.name for m in service_info.dtos]
            parts.append(f"- **数据传输对象** ({len(dto_names)}): {', '.join(dto_names)}")

        # Persistence artifacts
        if service_info.persistence_artifacts:
            persist_names = [m.name for m in service_info.persistence_artifacts]
            parts.append(f"- **持久化产物** ({len(persist_names)}): {', '.join(persist_names)}")

        # Infrastructure
        if service_info.infrastructure_models:
            infra_names = [m.name for m in service_info.infrastructure_models]
            parts.append(f"- **基础设施模型** ({len(infra_names)}): {', '.join(infra_names)}")

        parts.append(f"\n涉及模块: {', '.join(service_info.ownership_modules)}")

        return "\n".join(parts)

    def format_database_access_pattern(self, service_info: ServiceDataModelInfo) -> str:
        """Format database access pattern narrative.

        Args:
            service_info: Service model information

        Returns:
            Prose describing database access patterns
        """
        if not service_info.persistence_artifacts:
            return "### 数据库访问模式\n\n该服务没有持久化数据模型。"

        parts = ["### 数据库访问模式\n"]

        # Analyze persistence types
        persist_types: set[str] = set()
        for model in service_info.persistence_artifacts:
            persist_types.add(model.type)

        type_descriptions = {
            "sqlalchemy": "SQLAlchemy ORM",
            "orm": "ORM 模型",
            "pydantic": "Pydantic 配置/验证",
            "dataclass": "Python dataclass",
        }

        type_list = [type_descriptions.get(t, t) for t in persist_types]
        parts.append(f"使用: {', '.join(type_list)}")

        # Check for migration evidence
        if service_info.infrastructure_models:
            migration_models = [
                m for m in service_info.infrastructure_models if m.migration_related
            ]
            if migration_models:
                parts.append(f"\n**迁移相关模型**: {', '.join([m.name for m in migration_models])}")

        return "\n".join(parts)

    def format_schema_variations(self, service_info: ServiceDataModelInfo) -> str:
        """Format schema variations narrative.

        Args:
            service_info: Service model information

        Returns:
            Prose describing schema variations
        """
        if not service_info.models:
            return "### Schema 变化\n\n该服务没有数据模型。"

        parts = ["### Schema 变化\n"]

        # Group by module
        by_module: dict[str, list[DataModel]] = {}
        for model in service_info.models:
            if model.module not in by_module:
                by_module[model.module] = []
            by_module[model.module].append(model)

        for module, models in sorted(by_module.items()):
            parts.append(f"\n**{module}** 模块 ({len(models)} 个模型):")
            for model in models[:5]:  # Limit per module
                parts.append(f"- `{model.name}` ({model.type}) <cite>{model.file_path}</cite>")
            if len(models) > 5:
                parts.append(f"- ... 还有 {len(models) - 5} 个模型")

        return "\n".join(parts)

    def format_migration_evidence(self, service_info: ServiceDataModelInfo) -> str:
        """Format migration evidence narrative.

        Args:
            service_info: Service model information

        Returns:
            Prose describing migration evidence
        """
        migration_models = [
            m for m in service_info.models if getattr(m, "migration_related", False)
        ]

        if not migration_models:
            return "### 迁移证据\n\n该服务没有迁移相关的模型。"

        parts = ["### 迁移证据\n"]
        parts.append(f"发现 {len(migration_models)} 个迁移相关模型：\n")

        for model in migration_models:
            parts.append(f"- `{model.name}`: {model.type} <cite>{model.file_path}</cite>")

        return "\n".join(parts)


# =============================================================================
# COMPOSER FACTORY
# =============================================================================


def create_service_data_model_composer(
    snapshot: RepositorySnapshot,
    llm_provider: MockLLMProvider | None = None,
    workspace_root: str | Path | None = None,
) -> ServiceDataModelComposer:
    """Create a service data model composer.

    Args:
        snapshot: Repository snapshot with data models
        llm_provider: Optional LLM provider
        workspace_root: Optional workspace root

    Returns:
        ServiceDataModelComposer instance
    """
    return ServiceDataModelComposer(
        snapshot=snapshot,
        llm_provider=llm_provider,
        workspace_root=workspace_root,
    )


# =============================================================================
# STANDALONE COMPOSITION HELPERS
# =============================================================================


def compose_service_data_model_article(
    page_plan: WikiPagePlan,
    snapshot: RepositorySnapshot,
    evidence_binding: PageEvidenceBinding | None = None,
    llm_provider: MockLLMProvider | None = None,
    workspace_root: str | Path | None = None,
) -> ComposerOutput:
    """Convenience function to compose a service data model article.

    Args:
        page_plan: WikiPagePlan for the data model page
        snapshot: Repository snapshot with data models
        evidence_binding: Optional evidence binding
        llm_provider: Optional LLM provider
        workspace_root: Optional workspace root

    Returns:
        ComposerOutput with generated content
    """
    composer = create_service_data_model_composer(
        snapshot=snapshot,
        llm_provider=llm_provider,
        workspace_root=workspace_root,
    )
    return composer.compose_data_model_page(page_plan, evidence_binding)


async def compose_service_data_model_article_async(
    page_plan: WikiPagePlan,
    snapshot: RepositorySnapshot,
    evidence_binding: PageEvidenceBinding | None = None,
    llm_provider: MockLLMProvider | None = None,
    workspace_root: str | Path | None = None,
) -> ComposerOutput:
    """Async convenience function to compose a service data model article.

    Args:
        page_plan: WikiPagePlan for the data model page
        snapshot: Repository snapshot with data models
        evidence_binding: Optional evidence binding
        llm_provider: Optional LLM provider
        workspace_root: Optional workspace root

    Returns:
        ComposerOutput with generated content
    """
    composer = create_service_data_model_composer(
        snapshot=snapshot,
        llm_provider=llm_provider,
        workspace_root=workspace_root,
    )
    return await composer.compose_data_model_page_async(page_plan, evidence_binding)


# =============================================================================
# SERVICE DATA MODEL INFO EXTRACTION
# =============================================================================


def extract_service_data_models(
    snapshot: RepositorySnapshot,
) -> dict[str, ServiceDataModelInfo]:
    """Extract service data model information from repository snapshot.

    Args:
        snapshot: Repository snapshot with data models

    Returns:
        Dictionary mapping service family to ServiceDataModelInfo
    """
    composer = ServiceDataModelComposer(snapshot=snapshot)
    return composer._service_models


def get_service_model_summary(
    service_name: str,
    snapshot: RepositorySnapshot,
) -> ServiceDataModelInfo | None:
    """Get summary of models for a specific service.

    Args:
        service_name: Service family name
        snapshot: Repository snapshot with data models

    Returns:
        ServiceDataModelInfo or None if service not found
    """
    service_models = extract_service_data_models(snapshot)
    return service_models.get(service_name)
