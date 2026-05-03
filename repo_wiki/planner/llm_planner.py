"""LLM-assisted page planner extension.

Extends the rule-first page plan with LLM assistance to expand and improve coverage.
Keeps page IDs deterministic and paths stable.

The LLM is used to:
- Suggest additional pages based on context
- Identify missing documentation opportunities
- Recommend cross-references between pages
- Expand page content suggestions
"""

from __future__ import annotations

from typing import Any, Protocol

from repo_wiki.planner.schema import (
    GenerationMode,
    NavNode,
    RepositoryIdentity,
    SourceRequirement,
    WikiPagePlan,
    WikiPlanManifest,
    WikiTaxonomyCategory,
)


class LLMProvider(Protocol):
    """Protocol for LLM providers used by the planner."""

    def complete(self, prompt: str, **kwargs: Any) -> str:
        """Generate completion from prompt."""
        ...


class MockLLMProvider:
    """Mock LLM provider for testing/CI environments."""

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self._responses = responses or {}

    def complete(self, prompt: str, **kwargs: Any) -> str:
        """Return mock completion based on prompt content."""
        if "api" in prompt.lower():
            return "Consider adding API changelog and migration guide pages."
        if "module" in prompt.lower():
            return "Consider adding module dependency visualization and API compatibility matrix."
        if "security" in prompt.lower():
            return "Consider adding security audit checklist and incident response guide."
        if "deployment" in prompt.lower():
            return "Consider adding rollback procedures and disaster recovery guide."
        return "Consider adding related best practices and troubleshooting FAQ."


class LLMAssistedPlanner:
    """LLM-assisted page planner that extends rule-first plans.

    This planner takes a rule-first plan and uses an LLM to:
    1. Identify gaps in coverage
    2. Suggest additional valuable pages
    3. Recommend cross-references
    4. Suggest content outlines

    Page IDs remain stable and deterministic - the LLM only suggests additions.
    """

    def __init__(
        self,
        base_plan: WikiPlanManifest,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self.base_plan = base_plan
        self.llm_provider = llm_provider
        self._added_page_ids: set[str] = {p.page_id for p in base_plan.pages}

    def expand_plan(self) -> WikiPlanManifest:
        """Expand the base plan with LLM suggestions.

        Returns:
            WikiPlanManifest with additional pages from LLM analysis
        """
        if self.llm_provider is None:
            return self.base_plan

        suggestions = self._collect_llm_suggestions()

        # Apply suggestions to create new pages
        new_pages = self._apply_suggestions(suggestions)

        # Merge with base plan
        all_pages = list(self.base_plan.pages) + new_pages

        # Rebuild navigation tree
        planner = _RebuildPlanner(self.base_plan.repository_identity, all_pages)
        nav_tree = planner._build_navigation_tree()

        return WikiPlanManifest(
            version=self.base_plan.version,
            profile=self.base_plan.profile + "-llm-enhanced",
            repository_identity=self.base_plan.repository_identity,
            pages=all_pages,
            navigation_tree=nav_tree,
        )

    def _collect_llm_suggestions(self) -> dict[WikiTaxonomyCategory, list[str]]:
        """Collect LLM suggestions per category."""
        suggestions: dict[WikiTaxonomyCategory, list[str]] = {
            cat: [] for cat in WikiTaxonomyCategory
        }

        # Get summary of each category's current pages
        for category in WikiTaxonomyCategory:
            pages = self.base_plan.pages_by_category(category)
            if not pages:
                continue

            context = self._build_category_context(category, pages)
            prompt = self._build_suggestion_prompt(category, context)
            response = self.llm_provider.complete(prompt)

            # Parse suggestions from response
            category_suggestions = self._parse_suggestions(response)
            suggestions[category] = category_suggestions

        return suggestions

    def _build_category_context(
        self, category: WikiTaxonomyCategory, pages: list[WikiPagePlan]
    ) -> str:
        """Build context string for a category's current pages."""
        page_titles = ", ".join(p.title for p in pages[:10])
        return (
            f"Category: {category.value}\nExisting pages: {page_titles}\nTotal pages: {len(pages)}"
        )

    def _build_suggestion_prompt(self, category: WikiTaxonomyCategory, context: str) -> str:
        """Build LLM prompt for page suggestions."""
        return f"""Based on the following wiki category context, suggest additional valuable pages:

{context}

Suggest up to 5 additional pages that would provide value to users of this documentation.
For each suggestion, provide:
1. Page title (in Chinese)
2. Brief purpose description
3. Target audience

Format: Title | Purpose | Audience
"""

    def _parse_suggestions(self, response: str) -> list[str]:
        """Parse LLM response into page suggestions."""
        suggestions = []
        for line in response.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                parts = line.split("|")
                if parts:
                    suggestions.append(parts[0].strip())
            elif len(line) > 3:
                suggestions.append(line[:50])
        return suggestions[:5]

    def _apply_suggestions(
        self, suggestions: dict[WikiTaxonomyCategory, list[str]]
    ) -> list[WikiPagePlan]:
        """Apply suggestions to create new pages."""
        new_pages: list[WikiPagePlan] = []
        sort_order = 1000  # Start after rule-first pages

        for category, category_suggestions in suggestions.items():
            for suggestion in category_suggestions:
                page_id = self._make_unique_page_id(suggestion)
                page = WikiPagePlan(
                    page_id=page_id,
                    title=suggestion,
                    category=category,
                    parent=self._find_parent_for_category(category),
                    output_path=self._make_output_path(page_id, category),
                    source_requirements=SourceRequirement(),
                    generation_mode=GenerationMode.LLM_ASSISTED,
                    sort_order=sort_order,
                    tags=["llm-suggested"],
                )
                new_pages.append(page)
                sort_order += 1

        return new_pages

    def _make_unique_page_id(self, title: str) -> str:
        """Make a unique page ID from title."""
        import re

        base = title.lower().replace(" ", "-").replace("_", "-")
        base = re.sub(r"[^a-z0-9-]", "", base)
        base = re.sub(r"-+", "-", base).strip("-")

        original = base
        counter = 1
        while base in self._added_page_ids:
            base = f"{original}-{counter}"
            counter += 1

        self._added_page_ids.add(base)
        return base

    def _find_parent_for_category(self, category: WikiTaxonomyCategory) -> str | None:
        """Find the parent page for a category's index."""
        parent_map = {
            WikiTaxonomyCategory.PROJECT_OVERVIEW: "project-overview",
            WikiTaxonomyCategory.ARCHITECTURE_DESIGN: "architecture-overview",
            WikiTaxonomyCategory.CORE_SERVICES: "core-services-index",
            WikiTaxonomyCategory.API_REFERENCE: "api-overview",
            WikiTaxonomyCategory.DATA_MODELS: "data-models-overview",
            WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS: "deployment-overview",
            WikiTaxonomyCategory.DEVELOPMENT_GUIDE: "development-guide",
            WikiTaxonomyCategory.SECURITY_COMPLIANCE: "security-overview",
            WikiTaxonomyCategory.TROUBLESHOOTING: "troubleshooting-overview",
        }
        return parent_map.get(category)

    def _make_output_path(self, page_id: str, category: WikiTaxonomyCategory) -> str:
        """Create output path based on category."""
        category_paths = {
            WikiTaxonomyCategory.PROJECT_OVERVIEW: "docs/pages/overview",
            WikiTaxonomyCategory.ARCHITECTURE_DESIGN: "docs/pages/architecture",
            WikiTaxonomyCategory.CORE_SERVICES: "docs/pages/services",
            WikiTaxonomyCategory.PYTHON_SERVICES: "docs/pages/python-services",
            WikiTaxonomyCategory.FRONTEND_APPLICATIONS: "docs/pages/frontend",
            WikiTaxonomyCategory.DATA_MODELS: "docs/pages/data-models",
            WikiTaxonomyCategory.API_REFERENCE: "docs/pages/api",
            WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS: "docs/pages/deployment",
            WikiTaxonomyCategory.DEVELOPMENT_GUIDE: "docs/pages/development",
            WikiTaxonomyCategory.SECURITY_COMPLIANCE: "docs/pages/security",
            WikiTaxonomyCategory.TROUBLESHOOTING: "docs/pages/troubleshooting",
        }
        base = category_paths.get(category, "docs/pages")
        return f"{base}/{page_id}.md"


class _RebuildPlanner:
    """Helper planner that rebuilds navigation from existing pages."""

    def __init__(
        self,
        identity: RepositoryIdentity,
        pages: list[WikiPagePlan],
    ) -> None:
        self.identity = identity
        self.pages = pages

    def _build_navigation_tree(self) -> list[NavNode]:
        """Build navigation tree from existing pages."""
        from repo_wiki.planner.schema import DEFAULT_CHINESE_TAXONOMY

        _CATEGORY_ORDER = {
            WikiTaxonomyCategory.PROJECT_OVERVIEW: 0,
            WikiTaxonomyCategory.ARCHITECTURE_DESIGN: 1,
            WikiTaxonomyCategory.CORE_SERVICES: 2,
            WikiTaxonomyCategory.PYTHON_SERVICES: 3,
            WikiTaxonomyCategory.FRONTEND_APPLICATIONS: 4,
            WikiTaxonomyCategory.DATA_MODELS: 5,
            WikiTaxonomyCategory.API_REFERENCE: 6,
            WikiTaxonomyCategory.DEPLOYMENT_OPERATIONS: 7,
            WikiTaxonomyCategory.DEVELOPMENT_GUIDE: 8,
            WikiTaxonomyCategory.SECURITY_COMPLIANCE: 9,
            WikiTaxonomyCategory.TROUBLESHOOTING: 10,
        }

        category_nodes: dict[WikiTaxonomyCategory, NavNode] = {}
        for category in DEFAULT_CHINESE_TAXONOMY:
            node = NavNode(
                node_id=f"cat-{category.value}",
                label=category.value,
                node_type="category",
                sort_order=_CATEGORY_ORDER.get(category, 999),
            )
            category_nodes[category] = node

        for page in self.pages:
            cat_node = category_nodes.get(page.category)
            if not cat_node:
                continue

            page_node = NavNode(
                node_id=f"page-{page.page_id}",
                label=page.title,
                node_type="page",
                path=page.output_path,
                sort_order=page.sort_order,
            )

            if page.parent:
                parent_node = self._find_nav_node(cat_node, f"page-{page.parent}")
                if parent_node:
                    parent_node.children.append(page_node)
                else:
                    cat_node.children.append(page_node)
            else:
                cat_node.children.append(page_node)

        def sort_children(node: NavNode) -> None:
            node.children.sort(key=lambda c: (c.sort_order, c.label))
            for child in node.children:
                sort_children(child)

        for node in category_nodes.values():
            sort_children(node)

        return sorted(category_nodes.values(), key=lambda n: n.sort_order)

    def _find_nav_node(self, parent: NavNode, node_id: str) -> NavNode | None:
        """Find a navigation node by ID within parent subtree."""
        for child in parent.children:
            if child.node_id == node_id:
                return child
            found = self._find_nav_node(child, node_id)
            if found:
                return found
        return None


def enhance_plan_with_llm(
    base_plan: WikiPlanManifest,
    llm_provider: LLMProvider | None = None,
) -> WikiPlanManifest:
    """Enhance a base plan with LLM suggestions.

    Args:
        base_plan: The rule-first plan to enhance
        llm_provider: Optional LLM provider (uses MockLLMProvider if None)

    Returns:
        Enhanced WikiPlanManifest with additional pages
    """
    planner = LLMAssistedPlanner(base_plan, llm_provider)
    return planner.expand_plan()
