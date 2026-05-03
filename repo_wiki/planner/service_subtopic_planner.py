"""Service subtopic planner for Python services.

Generates subtopic pages for services instead of a single page per service.
Based on Qoder baseline patterns discovered in Task 32.1:
- 服务概述 (Service Overview)
- 架构设计 (Architecture Design)
- API接口文档 (API Documentation)
- 部署配置 (Deployment Configuration)
- 核心组件 (Core Components)

This planner expands Python services into meaningful subtopics, following
the Qoder Chinese wiki convention of multi-page service documentation.
"""

from __future__ import annotations

from repo_wiki.core.contracts import Module, RepositorySnapshot
from repo_wiki.planner.schema import (
    GenerationMode,
    NavNode,
    RepositoryIdentity,
    SourceRequirement,
    WikiPagePlan,
    WikiPlanManifest,
    WikiTaxonomyCategory,
)


# Service subtopic categories
class ServiceSubtopicCategory:
    """Service subtopic categories for multi-page service documentation."""

    OVERVIEW = "overview"  # 服务概述
    ARCHITECTURE = "architecture"  # 架构设计
    API_DOCS = "api-docs"  # API接口文档
    DEPLOYMENT = "deployment"  # 部署配置
    CORE_COMPONENTS = "core-components"  # 核心组件


# Subtopic page templates
_SERVICE_SUBTOPIC_TEMPLATES = {
    ServiceSubtopicCategory.OVERVIEW: {
        "title_suffix": "概述",
        "description": "Service overview and key capabilities",
        "tags": ["service", "overview"],
    },
    ServiceSubtopicCategory.ARCHITECTURE: {
        "title_suffix": "架构设计",
        "description": "Service architecture and component interactions",
        "tags": ["service", "architecture", "design"],
    },
    ServiceSubtopicCategory.API_DOCS: {
        "title_suffix": "API接口文档",
        "description": "Service API endpoints and contracts",
        "tags": ["service", "api", "reference"],
    },
    ServiceSubtopicCategory.DEPLOYMENT: {
        "title_suffix": "部署配置",
        "description": "Service deployment and configuration",
        "tags": ["service", "deployment", "config"],
    },
    ServiceSubtopicCategory.CORE_COMPONENTS: {
        "title_suffix": "核心组件",
        "description": "Core components and engines",
        "tags": ["service", "components", "engines"],
    },
}


class ServiceSubtopicPlanner:
    """Planner for service subtopic pages.

    This planner takes services (modules with service_family='python-backend')
    and generates multiple subtopic pages for each service instead of a single
    page, following the Qoder Chinese wiki convention.

    Key features:
    - Generates 5 subtopic pages per Python service: overview, architecture,
      API docs, deployment, and core components
    - Creates business subdomain pages for core services
    - Preserves stable slugs and manifest navigation ordering
    - Maintains compatibility with existing WikiPlanManifest structure
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
        """Generate service subtopic plan.

        Returns:
            WikiPlanManifest with service subtopic pages
        """
        self.pages = []
        self._page_id_set = set()

        # Generate Python service subtopic pages
        self._generate_python_service_pages()

        # Generate business subdomain pages for core services
        self._generate_business_subdomain_pages()

        # Sort pages by category order then by sort_order
        self.pages.sort(key=lambda p: (self._category_order(p.category), p.sort_order))

        # Build navigation tree
        nav_tree = self._build_navigation_tree()

        manifest = WikiPlanManifest(
            version="1.0.0",
            profile="service-subtopic",
            repository_identity=self.identity,
            pages=self.pages,
            navigation_tree=nav_tree,
        )

        return manifest

    def _category_order(self, category: WikiTaxonomyCategory) -> int:
        """Return sort order for a category."""
        order_map = {
            WikiTaxonomyCategory.PYTHON_SERVICES: 3,
            WikiTaxonomyCategory.CORE_SERVICES: 2,
            WikiTaxonomyCategory.API_REFERENCE: 6,
        }
        return order_map.get(category, 99)

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

    def _make_output_path(self, page_id: str, category: WikiTaxonomyCategory) -> str:
        """Create output path for service pages."""
        if category == WikiTaxonomyCategory.PYTHON_SERVICES:
            return f"docs/pages/python-services/{page_id}.md"
        elif category == WikiTaxonomyCategory.CORE_SERVICES:
            return f"docs/pages/services/{page_id}.md"
        elif category == WikiTaxonomyCategory.API_REFERENCE:
            return f"docs/pages/api/{page_id}.md"
        return f"docs/pages/{page_id}.md"

    def _add_page(
        self,
        page_id: str,
        title: str,
        category: WikiTaxonomyCategory,
        parent: str | None = None,
        source_requirements: SourceRequirement | None = None,
        sort_order: int = 0,
        tags: list[str] | None = None,
    ) -> WikiPagePlan:
        """Add a page to the plan."""
        tags = tags or []

        page = WikiPagePlan(
            page_id=page_id,
            title=title,
            category=category,
            parent=parent,
            output_path=self._make_output_path(page_id, category),
            source_requirements=source_requirements or SourceRequirement(),
            generation_mode=GenerationMode.RULE_FIRST,
            sort_order=sort_order,
            tags=tags,
        )
        self.pages.append(page)
        return page

    def _is_python_service(self, module: Module) -> bool:
        """Check if a module is a Python service."""
        combined = f"{module.runtime_role} {module.service_family}".lower()
        return "python" in combined or "fastapi" in combined

    def _humanize_service_title(self, name: str) -> str:
        """Convert service name to human-readable Chinese title."""
        known = {
            "tcsl-generator-service": "TCSL生成服务",
            "scenario-orchestrator-service": "场景编排服务",
            "doc-parser-service": "文档解析服务",
            "nl-to-dsl-service": "自然语言转DSL服务",
        }
        if name in known:
            return known[name]
        words = [part for part in name.replace("-", " ").split() if part]
        return " ".join(
            part.upper()
            if part.lower() in {"api", "mcp", "ai", "tcsl", "nlp", "dsl"}
            else part.capitalize()
            for part in words
        )

    def _generate_python_service_pages(self) -> None:
        """Generate subtopic pages for Python services."""
        python_modules = [m for m in self.snapshot.modules if self._is_python_service(m)]

        if not python_modules:
            return

        # Add Python services category index
        index_id = self._make_page_id("python-services-index")
        self._add_page(
            page_id=index_id,
            title="Python服务",
            category=WikiTaxonomyCategory.PYTHON_SERVICES,
            parent=None,
            source_requirements=SourceRequirement(modules=[m.name for m in python_modules]),
            sort_order=0,
            tags=["python", "services", "index"],
        )

        # Group Python services by domain
        by_domain: dict[str, list[Module]] = {}
        for module in python_modules:
            domain = module.domain or "unknown"
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(module)

        service_idx = 10
        for domain, modules in sorted(by_domain.items()):
            # Add domain group page
            domain_id = self._make_page_id(f"python-{domain}")
            self._add_page(
                page_id=domain_id,
                title=f"{domain.title()}服务",
                category=WikiTaxonomyCategory.PYTHON_SERVICES,
                parent=index_id,
                source_requirements=SourceRequirement(modules=[m.name for m in modules]),
                sort_order=service_idx,
                tags=["python", "domain", domain],
            )

            # Generate subtopic pages for each service
            for svc_idx, module in enumerate(sorted(modules, key=lambda m: m.name)):
                self._generate_service_subtopics(module, domain_id, service_idx + svc_idx)

            service_idx += 10

    def _generate_service_subtopics(
        self,
        module: Module,
        parent_id: str,
        base_sort: int,
    ) -> None:
        """Generate subtopic pages for a single service.

        Args:
            module: The service module
            parent_id: Parent page ID for the service group
            base_sort: Base sort order offset
        """
        service_title = self._humanize_service_title(module.name)
        service_slug = module.name.lower()

        # Get endpoints for this service
        service_endpoints = [e for e in self.snapshot.endpoints if e.module == module.name]

        subtopic_offset = 0
        for subtopic, template in _SERVICE_SUBTOPIC_TEMPLATES.items():
            page_id = self._make_page_id(f"{service_slug}-{subtopic}")
            title = f"{service_title}{template['title_suffix']}"

            # Build source requirements based on subtopic
            source_reqs = SourceRequirement(modules=[module.name])
            if subtopic == ServiceSubtopicCategory.API_DOCS and service_endpoints:
                source_reqs.endpoints = [f"{e.method} {e.path}" for e in service_endpoints]

            self._add_page(
                page_id=page_id,
                title=title,
                category=WikiTaxonomyCategory.PYTHON_SERVICES,
                parent=parent_id,
                source_requirements=source_reqs,
                sort_order=base_sort + subtopic_offset,
                tags=template["tags"] + [module.name],
            )
            subtopic_offset += 1

    def _generate_business_subdomain_pages(self) -> None:
        """Generate business subdomain pages for core services."""
        # Identify core services that should have subdomain pages
        core_modules = [
            m for m in self.snapshot.modules if m.domain in ("core-platform", "ai-services")
        ]

        if not core_modules:
            return

        # Add core services index
        index_id = self._make_page_id("core-services-index")
        self._add_page(
            page_id=index_id,
            title="核心服务",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            parent=None,
            source_requirements=SourceRequirement(modules=[m.name for m in core_modules]),
            sort_order=0,
            tags=["core", "services", "index"],
        )

        # Group by service family
        by_family: dict[str, list[Module]] = {}
        for module in core_modules:
            family = module.service_family or "unknown"
            if family not in by_family:
                by_family[family] = []
            by_family[family].append(module)

        subdomain_idx = 10
        for family, modules in sorted(by_family.items()):
            # Add service family subdomain page
            family_id = self._make_page_id(f"core-{family}")
            self._add_page(
                page_id=family_id,
                title=f"{family.title()}服务",
                category=WikiTaxonomyCategory.CORE_SERVICES,
                parent=index_id,
                source_requirements=SourceRequirement(modules=[m.name for m in modules]),
                sort_order=subdomain_idx,
                tags=["core", "service-family", family],
            )

            # Add individual service pages
            for svc_idx, module in enumerate(sorted(modules, key=lambda m: m.name)):
                svc_id = self._make_page_id(module.name)
                self._add_page(
                    page_id=svc_id,
                    title=self._humanize_service_title(module.name),
                    category=WikiTaxonomyCategory.CORE_SERVICES,
                    parent=family_id,
                    source_requirements=SourceRequirement(
                        modules=[module.name],
                        files=[module.doc_path] if module.doc_path else [],
                    ),
                    sort_order=subdomain_idx + svc_idx + 1,
                    tags=["core", "service", module.name],
                )

            subdomain_idx += 10

    def _build_navigation_tree(self) -> list[NavNode]:
        """Build navigation tree for service subtopic pages."""
        category_nodes: dict[WikiTaxonomyCategory, NavNode] = {}

        for category in [WikiTaxonomyCategory.PYTHON_SERVICES, WikiTaxonomyCategory.CORE_SERVICES]:
            category_nodes[category] = NavNode(
                node_id=f"cat-{category.value}",
                label=category.value,
                node_type="category",
                sort_order=self._category_order(category),
            )

        for page in self.pages:
            category = page.category
            if category not in category_nodes:
                continue

            parent_node = None
            if page.parent:
                # Find parent in existing nodes
                for node in self._iter_nodes(list(category_nodes.values())):
                    if node.node_id == f"page-{page.parent}":
                        parent_node = node
                        break

            page_node = NavNode(
                node_id=f"page-{page.page_id}",
                label=page.title,
                node_type="page",
                path=page.output_path,
                sort_order=page.sort_order,
            )

            if parent_node:
                parent_node.children.append(page_node)
            else:
                category_nodes[category].children.append(page_node)

        # Sort children within each category
        for category, node in category_nodes.items():
            node.children.sort(key=lambda n: (n.sort_order, n.label))

        return list(category_nodes.values())

    def _iter_nodes(self, nodes: list[NavNode]):
        """Iterate over nodes recursively."""
        for node in nodes:
            yield node
            yield from self._iter_nodes(node.children)


def plan_service_subtopics(
    identity: RepositoryIdentity,
    snapshot: RepositorySnapshot,
) -> WikiPlanManifest:
    """Generate service subtopic plan from repository snapshot.

    Args:
        identity: Repository identity
        snapshot: Repository scan snapshot with enriched modules

    Returns:
        WikiPlanManifest with service subtopic pages
    """
    planner = ServiceSubtopicPlanner(identity, snapshot)
    return planner.generate()
