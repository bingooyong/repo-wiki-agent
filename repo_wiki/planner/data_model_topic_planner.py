"""Data model topic planner for entity relationship and database architecture.

Groups data models by topic (entity relationships, database architecture,
migration strategy) to create coherent data model reference pages.

This planner extends the RuleFirstPlanner to provide data-model-specific planning
with entity deduplication and ER relationship awareness, generating at least
10 AI_API_Atlas data model planned pages.
"""
from __future__ import annotations

from typing import Any

from repo_wiki.core.contracts import DataModel, Module, RepositorySnapshot
from repo_wiki.planner.schema import (
    GenerationMode,
    NavNode,
    RepositoryIdentity,
    SourceRequirement,
    WikiPagePlan,
    WikiPlanManifest,
    WikiTaxonomyCategory,
)


# Data model topic categories for grouping
class DataModelTopicCategory:
    """Data model topic categories for grouping."""

    # Core entity topics
    CORE_ENTITIES = "core-entities"
    CONFIGURATION_MODELS = "configuration-models"
    REPOSITORY_INFO_MODELS = "repository-info-models"
    ANALYSIS_RESULT_MODELS = "analysis-result-models"
    SERVICE_STATE_MODELS = "service-state-models"

    # Database architecture topics
    DATABASE_ARCHITECTURE = "database-architecture"
    SCHEMA_DESIGN = "schema-design"
    MIGRATION_STRATEGY = "migration-strategy"

    # Entity relationship topics
    ENTITY_RELATIONSHIPS = "entity-relationships"
    ER_DIAGRAMS = "er-diagrams"


# Topic to page title mapping
_TOPIC_TITLES: dict[str, str] = {
    DataModelTopicCategory.CORE_ENTITIES: "核心实体",
    DataModelTopicCategory.CONFIGURATION_MODELS: "配置模型",
    DataModelTopicCategory.REPOSITORY_INFO_MODELS: "仓储信息模型",
    DataModelTopicCategory.ANALYSIS_RESULT_MODELS: "分析结果模型",
    DataModelTopicCategory.SERVICE_STATE_MODELS: "服务状态模型",
    DataModelTopicCategory.DATABASE_ARCHITECTURE: "数据库架构",
    DataModelTopicCategory.SCHEMA_DESIGN: "Schema设计",
    DataModelTopicCategory.MIGRATION_STRATEGY: "迁移策略",
    DataModelTopicCategory.ENTITY_RELATIONSHIPS: "实体关系",
    DataModelTopicCategory.ER_DIAGRAMS: "ER图",
}


class DataModelTopicPlanner:
    """Planner for data model topic pages organized by entity relationships,
    database architecture, and migration strategy.

    This planner takes data models and creates data model reference pages
    grouped by topic rather than by raw model count.

    Key features:
    - Groups models by topic (configuration, repository info, analysis results, etc.)
    - Creates entity relationship overview pages
    - Creates database architecture and migration strategy pages
    - Generates individual model pages with ER citations
    """

    def __init__(
        self,
        identity: RepositoryIdentity,
        snapshot: RepositorySnapshot,
    ) -> None:
        self.identity = identity
        self.snapshot = snapshot
        self.pages: list[WikiPagePlan] = []
        self._page_id_set: set[str] = set()

    def generate(self) -> WikiPlanManifest:
        """Generate data model topic plan.

        Returns:
            WikiPlanManifest with data model reference pages
        """
        self.pages = []
        self._page_id_set = set()

        # Generate data models overview page
        self._generate_data_models_overview()

        # Generate entity relationship pages
        self._generate_entity_relationship_pages()

        # Generate database architecture pages
        self._generate_database_architecture_pages()

        # Generate migration strategy pages
        self._generate_migration_strategy_pages()

        # Generate topic-grouped model pages
        self._generate_topic_grouped_models()

        # Generate individual model pages
        self._generate_individual_model_pages()

        # Build navigation tree
        nav_tree = self._build_navigation_tree()

        manifest = WikiPlanManifest(
            version="1.0.0",
            profile="data-model-topic",
            repository_identity=self.identity,
            pages=self.pages,
            navigation_tree=nav_tree,
        )

        return manifest

    def _make_page_id(self, base: str) -> str:
        """Create a unique page ID."""
        slug = base.lower().replace(" ", "-").replace("_", "-")
        slug = slug.strip("-")

        original = slug
        counter = 1
        while slug in self._page_id_set:
            slug = f"{original}-{counter}"
            counter += 1

        self._page_id_set.add(slug)
        return slug

    def _make_output_path(self, page_id: str) -> str:
        """Create output path for data model pages."""
        return f"docs/pages/data-models/{page_id}.md"

    def _add_page(
        self,
        page_id: str,
        title: str,
        category: WikiTaxonomyCategory = WikiTaxonomyCategory.DATA_MODELS,
        parent: str | None = None,
        source_requirements: SourceRequirement | None = None,
        sort_order: int = 0,
        tags: list[str] | None = None,
    ) -> WikiPagePlan:
        """Add a page to the plan."""
        tags = tags or []
        if "data-model" not in tags:
            tags.append("data-model")

        page = WikiPagePlan(
            page_id=page_id,
            title=title,
            category=category,
            parent=parent,
            output_path=self._make_output_path(page_id),
            source_requirements=source_requirements or SourceRequirement(),
            generation_mode=GenerationMode.RULE_FIRST,
            sort_order=sort_order,
            tags=tags,
        )
        self.pages.append(page)
        return page

    def _classify_model(self, model: DataModel) -> str:
        """Classify a data model into a topic category.

        Args:
            model: Data model to classify

        Returns:
            Topic category string
        """
        name = model.name.lower()

        # Configuration models
        if any(kw in name for kw in ["config", "settings"]):
            return DataModelTopicCategory.CONFIGURATION_MODELS

        # Repository info models
        if any(kw in name for kw in ["repository", "snapshot", "stats", "info"]):
            return DataModelTopicCategory.REPOSITORY_INFO_MODELS

        # Analysis/verification result models
        if any(kw in name for kw in ["result", "verify", "impact"]):
            return DataModelTopicCategory.ANALYSIS_RESULT_MODELS

        # Service state models
        if any(kw in name for kw in ["state", "runtime", "store"]):
            return DataModelTopicCategory.SERVICE_STATE_MODELS

        # Core entities
        if any(kw in name for kw in ["entity", "model", "module", "endpoint"]):
            return DataModelTopicCategory.CORE_ENTITIES

        return DataModelTopicCategory.CORE_ENTITIES

    def _group_models_by_topic(self) -> dict[str, list[DataModel]]:
        """Group data models by topic category.

        Returns:
            Dictionary mapping topic category to list of models
        """
        topics: dict[str, list[DataModel]] = {
            DataModelTopicCategory.CORE_ENTITIES: [],
            DataModelTopicCategory.CONFIGURATION_MODELS: [],
            DataModelTopicCategory.REPOSITORY_INFO_MODELS: [],
            DataModelTopicCategory.ANALYSIS_RESULT_MODELS: [],
            DataModelTopicCategory.SERVICE_STATE_MODELS: [],
        }

        for model in self.snapshot.data_models:
            topic = self._classify_model(model)
            if topic not in topics:
                topics[topic] = []
            topics[topic].append(model)

        return topics

    def _generate_data_models_overview(self) -> None:
        """Generate data models overview page."""
        self._add_page(
            page_id=self._make_page_id("data-models-overview"),
            title="数据模型概览",
            category=WikiTaxonomyCategory.DATA_MODELS,
            parent=None,
            source_requirements=SourceRequirement(
                data_models=[dm.name for dm in self.snapshot.data_models]
            ),
            sort_order=0,
            tags=["data-model", "overview", "index"],
        )

    def _generate_entity_relationship_pages(self) -> None:
        """Generate entity relationship overview and ER diagram pages."""
        # Entity relationships overview
        self._add_page(
            page_id=self._make_page_id("entity-relationships"),
            title="实体关系概览",
            category=WikiTaxonomyCategory.DATA_MODELS,
            parent="data-models-overview",
            source_requirements=SourceRequirement(
                data_models=[dm.name for dm in self.snapshot.data_models],
                modules=[m.name for m in self.snapshot.modules],
            ),
            sort_order=10,
            tags=["data-model", "entity", "relationships"],
        )

        # ER diagrams page
        self._add_page(
            page_id=self._make_page_id("er-diagrams"),
            title="ER图参考",
            category=WikiTaxonomyCategory.DATA_MODELS,
            parent="entity-relationships",
            source_requirements=SourceRequirement(
                data_models=[dm.name for dm in self.snapshot.data_models],
            ),
            sort_order=11,
            tags=["data-model", "er-diagram", "mermaid"],
        )

    def _generate_database_architecture_pages(self) -> None:
        """Generate database architecture and schema design pages."""
        # Database architecture overview
        self._add_page(
            page_id=self._make_page_id("database-architecture"),
            title="数据库架构",
            category=WikiTaxonomyCategory.DATA_MODELS,
            parent="data-models-overview",
            sort_order=20,
            tags=["data-model", "database", "architecture"],
        )

        # Schema design page
        self._add_page(
            page_id=self._make_page_id("schema-design"),
            title="Schema设计原则",
            category=WikiTaxonomyCategory.DATA_MODELS,
            parent="database-architecture",
            sort_order=21,
            tags=["data-model", "schema", "design"],
        )

    def _generate_migration_strategy_pages(self) -> None:
        """Generate migration strategy pages."""
        # Migration overview
        self._add_page(
            page_id=self._make_page_id("migration-strategy"),
            title="迁移策略",
            category=WikiTaxonomyCategory.DATA_MODELS,
            parent="data-models-overview",
            sort_order=30,
            tags=["data-model", "migration", "strategy"],
        )

        # Migration execution page
        self._add_page(
            page_id=self._make_page_id("migration-execution"),
            title="迁移执行指南",
            category=WikiTaxonomyCategory.DATA_MODELS,
            parent="migration-strategy",
            sort_order=31,
            tags=["data-model", "migration", "execution"],
        )

    def _generate_topic_grouped_models(self) -> None:
        """Generate model pages grouped by topic."""
        topics = self._group_models_by_topic()

        sort_order = 100
        for topic, models in sorted(topics.items()):
            if not models:
                continue

            topic_id = self._make_page_id(f"topic-{topic}")
            title = _TOPIC_TITLES.get(topic, topic.replace("-", " ").title())

            self._add_page(
                page_id=topic_id,
                title=title,
                category=WikiTaxonomyCategory.DATA_MODELS,
                parent="data-models-overview",
                source_requirements=SourceRequirement(
                    data_models=[m.name for m in models],
                    modules=list(set(m.module for m in models)),
                ),
                sort_order=sort_order,
                tags=["data-model", "topic", topic],
            )

            sort_order += 1

    def _generate_individual_model_pages(self) -> None:
        """Generate individual data model pages."""
        # Group models by module
        by_module: dict[str, list[DataModel]] = {}
        for model in self.snapshot.data_models:
            if model.module not in by_module:
                by_module[model.module] = []
            by_module[model.module].append(model)

        sort_order = 200
        for module_name, models in sorted(by_module.items()):
            module_topic = self._classify_model(models[0])
            topic_id = f"topic-{module_topic}"

            for model_idx, model in enumerate(sorted(models, key=lambda m: m.name)):
                model_id = self._make_page_id(f"{module_name}-{model.name}")
                self._add_page(
                    page_id=model_id,
                    title=model.name,
                    category=WikiTaxonomyCategory.DATA_MODELS,
                    parent="data-models-overview",
                    source_requirements=SourceRequirement(
                        data_models=[model.name],
                        modules=[model.module],
                        files=[model.file_path],
                    ),
                    sort_order=sort_order + model_idx,
                    tags=["data-model", model.type, module_name],
                )

            sort_order += 10

    def _build_navigation_tree(self) -> list[NavNode]:
        """Build navigation tree for data model pages."""
        # Create data models category node
        data_models_category = NavNode(
            node_id="cat-data-models",
            label="数据模型",
            node_type="category",
            sort_order=5,
        )

        # Add overview as first child
        root_pages = [p for p in self.pages if p.parent is None]
        for page in sorted(root_pages, key=lambda p: p.sort_order):
            page_node = NavNode(
                node_id=f"page-{page.page_id}",
                label=page.title,
                node_type="page",
                path=page.output_path,
                sort_order=page.sort_order,
            )

            # Add children
            children = [p for p in self.pages if p.parent == page.page_id]
            for child in sorted(children, key=lambda p: p.sort_order):
                child_node = NavNode(
                    node_id=f"page-{child.page_id}",
                    label=child.title,
                    node_type="page",
                    path=child.output_path,
                    sort_order=child.sort_order,
                )
                page_node.children.append(child_node)

            data_models_category.children.append(page_node)

        return [data_models_category]


def plan_data_model_topics(
    identity: RepositoryIdentity,
    snapshot: RepositorySnapshot,
) -> WikiPlanManifest:
    """Generate data model topic plan from repository snapshot.

    Args:
        identity: Repository identity
        snapshot: Repository scan snapshot with data models

    Returns:
        WikiPlanManifest with data model reference pages
    """
    planner = DataModelTopicPlanner(identity, snapshot)
    return planner.generate()
