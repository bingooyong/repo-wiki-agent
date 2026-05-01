"""API topic planner for service-family-based API documentation.

Groups API endpoints by service family and topic to create coherent
API reference pages that are grouped logically rather than by raw endpoint count.

This planner extends the RuleFirstPlanner to provide API-specific planning
with service family awareness, generating at least 15 planned API pages.
"""
from __future__ import annotations

from typing import Any

from repo_wiki.core.contracts import Endpoint, RepositorySnapshot
from repo_wiki.planner.schema import (
    GenerationMode,
    NavNode,
    RepositoryIdentity,
    SourceRequirement,
    WikiPagePlan,
    WikiPlanManifest,
    WikiTaxonomyCategory,
)


# API topic categories for grouping
class APITopicCategory:
    """API topic categories for service-family-based grouping."""

    # Core API topics
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    ERROR_HANDLING = "error-handling"
    CORE_SERVICE_API = "core-service-api"
    PYTHON_SERVICE_API = "python-service-api"
    DATA_MODEL_API = "data-model-api"
    ADMIN_API = "admin-api"
    HEALTH_API = "health-api"


# Service family to API topic mapping
_SERVICE_FAMILY_TOPICS: dict[str, list[str]] = {
    "python-backend": [
        APITopicCategory.AUTHENTICATION,
        APITopicCategory.CORE_SERVICE_API,
        APITopicCategory.PYTHON_SERVICE_API,
    ],
    "typescript-frontend": [
        APITopicCategory.DATA_MODEL_API,
    ],
    "api-server": [
        APITopicCategory.CORE_SERVICE_API,
        APITopicCategory.HEALTH_API,
        APITopicCategory.AUTHENTICATION,
    ],
    "worker": [
        APITopicCategory.CORE_SERVICE_API,
    ],
    "data-pipeline": [
        APITopicCategory.CORE_SERVICE_API,
        APITopicCategory.DATA_MODEL_API,
    ],
    "tooling": [
        APITopicCategory.CORE_SERVICE_API,
        APITopicCategory.ADMIN_API,
    ],
    "unknown": [
        APITopicCategory.CORE_SERVICE_API,
        APITopicCategory.AUTHENTICATION,
        APITopicCategory.AUTHORIZATION,
        APITopicCategory.ERROR_HANDLING,
    ],
}


class APITopicPlanner:
    """Planner for API topic pages organized by service family and topic.

    This planner takes enriched endpoints (with service_family, domain, runtime_role)
    and creates API reference pages grouped by topic rather than by raw endpoint count.

    Key features:
    - Groups endpoints by service family and topic
    - Creates topic-based overview pages
    - Generates individual endpoint pages
    - Creates auth/authz/error handling convention pages
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
        """Generate API topic plan.

        Returns:
            WikiPlanManifest with API reference pages
        """
        self.pages = []
        self._page_id_set = set()

        # Generate API overview page
        self._generate_api_overview()

        # Generate auth/authz convention pages
        self._generate_auth_convention_pages()

        # Generate error handling convention pages
        self._generate_error_handling_pages()

        # Generate service-family-based API pages
        self._generate_service_family_api_pages()

        # Generate individual endpoint pages grouped by topic
        self._generate_topic_grouped_endpoints()

        # Build navigation tree
        nav_tree = self._build_navigation_tree()

        manifest = WikiPlanManifest(
            version="1.0.0",
            profile="api-topic",
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
        """Create output path for API pages."""
        return f"docs/pages/api/{page_id}.md"

    def _add_page(
        self,
        page_id: str,
        title: str,
        category: WikiTaxonomyCategory = WikiTaxonomyCategory.API_REFERENCE,
        parent: str | None = None,
        source_requirements: SourceRequirement | None = None,
        sort_order: int = 0,
        tags: list[str] | None = None,
    ) -> WikiPagePlan:
        """Add a page to the plan."""
        tags = tags or []
        if "api" not in tags:
            tags.append("api")

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

    def _generate_api_overview(self) -> None:
        """Generate API reference overview page."""
        self._add_page(
            page_id=self._make_page_id("api-reference"),
            title="API参考概览",
            category=WikiTaxonomyCategory.API_REFERENCE,
            parent=None,
            source_requirements=SourceRequirement(
                endpoints=[f"{e.method} {e.path}" for e in self.snapshot.endpoints]
            ),
            sort_order=0,
            tags=["api", "reference", "overview"],
        )

    def _generate_auth_convention_pages(self) -> None:
        """Generate authentication and authorization convention pages."""
        # Authentication API page
        self._add_page(
            page_id=self._make_page_id("api-authentication"),
            title="认证授权API",
            category=WikiTaxonomyCategory.API_REFERENCE,
            parent="api-reference",
            source_requirements=SourceRequirement(
                endpoints=[
                    f"{e.method} {e.path}"
                    for e in self.snapshot.endpoints
                    if e.auth_required or e.auth_type in ("bearer", "oauth", "api-key")
                ]
            ),
            sort_order=10,
            tags=["api", "authentication", "auth"],
        )

        # Auth endpoints index
        auth_endpoints = [
            e for e in self.snapshot.endpoints
            if e.auth_required or e.auth_type in ("bearer", "oauth", "api-key")
        ]
        if auth_endpoints:
            self._add_page(
                page_id=self._make_page_id("api-auth-endpoints"),
                title="认证端点",
                category=WikiTaxonomyCategory.API_REFERENCE,
                parent="api-authentication",
                source_requirements=SourceRequirement(
                    endpoints=[f"{e.method} {e.path}" for e in auth_endpoints]
                ),
                sort_order=11,
                tags=["api", "auth", "endpoints"],
            )

        # Authorization conventions page
        self._add_page(
            page_id=self._make_page_id("api-authorization"),
            title="权限管理API",
            category=WikiTaxonomyCategory.API_REFERENCE,
            parent="api-reference",
            sort_order=12,
            tags=["api", "authorization", "permissions"],
        )

    def _generate_error_handling_pages(self) -> None:
        """Generate error handling convention pages."""
        # Error codes reference
        all_error_codes: set[int] = set()
        for ep in self.snapshot.endpoints:
            all_error_codes.update(ep.error_codes)

        self._add_page(
            page_id=self._make_page_id("api-error-codes"),
            title="错误处理API",
            category=WikiTaxonomyCategory.API_REFERENCE,
            parent="api-reference",
            source_requirements=SourceRequirement(
                endpoints=[f"{e.method} {e.path}" for e in self.snapshot.endpoints]
            ),
            sort_order=20,
            tags=["api", "error-handling", "errors"],
        )

        # Error response conventions
        self._add_page(
            page_id=self._make_page_id("api-error-conventions"),
            title="错误码参考",
            category=WikiTaxonomyCategory.API_REFERENCE,
            parent="api-error-codes",
            sort_order=21,
            tags=["api", "errors", "conventions"],
        )

    def _generate_service_family_api_pages(self) -> None:
        """Generate API pages grouped by service family."""
        # Group endpoints by service_family
        by_family: dict[str, list[Endpoint]] = {}
        for ep in self.snapshot.endpoints:
            sf = ep.service_family or "unknown"
            if sf not in by_family:
                by_family[sf] = []
            by_family[sf].append(ep)

        sort_order = 30
        for family, endpoints in sorted(by_family.items()):
            family_id = self._make_page_id(f"api-{family}")
            self._add_page(
                page_id=family_id,
                title=f"{family} API",
                category=WikiTaxonomyCategory.API_REFERENCE,
                parent="api-reference",
                source_requirements=SourceRequirement(
                    modules=list(set(e.module for e in endpoints)),
                    endpoints=[f"{e.method} {e.path}" for e in endpoints],
                ),
                sort_order=sort_order,
                tags=["api", "service-family", family],
            )
            sort_order += 1

    def _generate_topic_grouped_endpoints(self) -> None:
        """Generate endpoint pages grouped by topic (auth, health, data, etc.)."""
        # Group endpoints by topic
        topics: dict[str, list[Endpoint]] = {
            APITopicCategory.AUTHENTICATION: [],
            APITopicCategory.HEALTH_API: [],
            APITopicCategory.CORE_SERVICE_API: [],
            APITopicCategory.DATA_MODEL_API: [],
        }

        for ep in self.snapshot.endpoints:
            if "health" in ep.path.lower() or "ready" in ep.path.lower():
                topics[APITopicCategory.HEALTH_API].append(ep)
            elif ep.auth_required or ep.auth_type in ("bearer", "oauth", "api-key"):
                topics[APITopicCategory.AUTHENTICATION].append(ep)
            elif ep.request_body:
                topics[APITopicCategory.CORE_SERVICE_API].append(ep)
            else:
                topics[APITopicCategory.CORE_SERVICE_API].append(ep)

        sort_order = 100
        for topic, endpoints in topics.items():
            if not endpoints:
                continue

            topic_id = self._make_page_id(f"api-{topic}")
            self._add_page(
                page_id=topic_id,
                title=self._topic_title(topic),
                category=WikiTaxonomyCategory.API_REFERENCE,
                parent="api-reference",
                source_requirements=SourceRequirement(
                    endpoints=[f"{e.method} {e.path}" for e in endpoints]
                ),
                sort_order=sort_order,
                tags=["api", "topic", topic],
            )

            # Add individual endpoint pages under topic
            for ep_idx, ep in enumerate(sorted(endpoints, key=lambda e: (e.method, e.path))):
                ep_id = self._make_page_id(
                    f"api-{ep.method.lower()}-{ep.path.replace('/', '-')}"
                )
                self._add_page(
                    page_id=ep_id,
                    title=f"{ep.method} {ep.path}",
                    category=WikiTaxonomyCategory.API_REFERENCE,
                    parent=topic_id,
                    source_requirements=SourceRequirement(
                        endpoints=[f"{ep.method} {ep.path}"],
                        files=[ep.file_path],
                    ),
                    sort_order=sort_order + 1 + ep_idx,
                    tags=["api", "endpoint", ep.method.lower()],
                )

            sort_order += 10

    def _topic_title(self, topic: str) -> str:
        """Get human-readable title for topic."""
        titles = {
            APITopicCategory.AUTHENTICATION: "认证相关API",
            APITopicCategory.AUTHORIZATION: "授权相关API",
            APITopicCategory.ERROR_HANDLING: "错误处理API",
            APITopicCategory.CORE_SERVICE_API: "核心服务API",
            APITopicCategory.PYTHON_SERVICE_API: "Python服务API",
            APITopicCategory.DATA_MODEL_API: "数据模型API",
            APITopicCategory.ADMIN_API: "管理API",
            APITopicCategory.HEALTH_API: "健康检查API",
        }
        return titles.get(topic, topic.replace("-", " ").title())

    def _build_navigation_tree(self) -> list[NavNode]:
        """Build navigation tree for API pages."""
        # Create API category node
        api_category = NavNode(
            node_id="cat-api",
            label="API参考",
            node_type="category",
            sort_order=6,
        )

        # Add pages as children
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

            api_category.children.append(page_node)

        return [api_category]


def plan_api_topics(
    identity: RepositoryIdentity,
    snapshot: RepositorySnapshot,
) -> WikiPlanManifest:
    """Generate API topic plan from repository snapshot.

    Args:
        identity: Repository identity
        snapshot: Repository scan snapshot with enriched endpoints

    Returns:
        WikiPlanManifest with API reference pages
    """
    planner = APITopicPlanner(identity, snapshot)
    return planner.generate()