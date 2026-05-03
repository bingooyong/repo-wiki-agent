"""Service-family API composer for generating prose-first API articles.

This composer generates API reference articles organized by service family,
focusing on service purpose, core flows, representative endpoints, auth patterns,
and error handling conventions.

Phase 25 - Task 25.3: Service-family API composer

Key features:
- Explains service purpose and core flows
- Bounded endpoint tables (secondary to prose)
- Auth and error pattern documentation
- Citations for handlers, schemas, and call sites
- Integration with existing LLM page composer pipeline
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from repo_wiki.core.contracts import (
    Endpoint,
    RepositorySnapshot,
    extract_service_family_from_page_id,
)
from repo_wiki.evidence.ranking import PageEvidenceBinding
from repo_wiki.generator.composer import (
    ComposerContext,
    ComposerOutput,
    build_composer_input,
    create_composer,
)
from repo_wiki.llm.providers import MockLLMProvider
from repo_wiki.planner.schema import WikiPagePlan

# =============================================================================
# SERVICE FAMILY API COMPOSER
# =============================================================================


class ServiceFamilyAPIComposer:
    """Composer for service-family based API reference articles.

    This composer takes API page plans organized by service family and
    generates prose-first Markdown articles that:
    - Explain service purpose and core business flows
    - Document representative endpoints (bounded table)
    - Detail authentication and authorization patterns
    - Cover error handling conventions
    - Include citations for handlers, schemas, and call sites

    Integration with existing pipeline:
    - Uses LLMPageComposer for actual LLM-based content generation
    - Adds service-family specific context and formatting
    - Handles endpoint grouping and presentation
    """

    def __init__(
        self,
        snapshot: RepositorySnapshot,
        llm_provider: MockLLMProvider | None = None,
        workspace_root: str | Path | None = None,
    ) -> None:
        """Initialize the service family API composer.

        Args:
            snapshot: Repository snapshot with enriched endpoints
            llm_provider: Optional LLM provider (uses mock if not provided)
            workspace_root: Optional workspace root for path resolution
        """
        self.snapshot = snapshot
        self.workspace_root = Path(workspace_root) if workspace_root else None
        self._llm_composer = create_composer(
            provider=llm_provider,
            workspace_root=workspace_root,
        )

    def compose_api_page(
        self,
        page_plan: WikiPagePlan,
        evidence_binding: PageEvidenceBinding | None = None,
    ) -> ComposerOutput:
        """Compose a single API page for a service family.

        Args:
            page_plan: WikiPagePlan for the API page (e.g., api-python-backend)
            evidence_binding: Optional evidence binding for this page

        Returns:
            ComposerOutput with generated Markdown
        """
        # Extract service family from page ID
        service_family = self._extract_service_family(page_plan.page_id)

        # Get endpoints for this service family
        endpoints = self._get_endpoints_for_service_family(service_family, page_plan)

        # Build service context for composition
        context = self._build_service_context(page_plan, service_family, endpoints)

        # Use the LLM composer to generate the actual content
        return self._compose_with_llm(page_plan, evidence_binding, context, endpoints)

    def _extract_service_family(self, page_id: str) -> str | None:
        """Extract service family name from page ID.

        Args:
            page_id: Page ID like 'api-python-backend' or 'api-authentication'

        Returns:
            Service family name or None
        """
        return extract_service_family_from_page_id(page_id)

    def _get_endpoints_for_service_family(
        self,
        service_family: str | None,
        page_plan: WikiPagePlan,
    ) -> list[Endpoint]:
        """Get endpoints relevant to this API page.

        Args:
            service_family: Service family to filter by
            page_plan: The page plan with source requirements

        Returns:
            List of relevant endpoints
        """
        endpoints: list[Endpoint] = []

        # If page has specific endpoints in source requirements, use those
        if page_plan.source_requirements and page_plan.source_requirements.endpoints:
            endpoint_set = set(page_plan.source_requirements.endpoints)
            for ep in self.snapshot.endpoints:
                ep_key = f"{ep.method} {ep.path}"
                if ep_key in endpoint_set:
                    endpoints.append(ep)
            return endpoints

        # Otherwise filter by service family
        if service_family:
            return [ep for ep in self.snapshot.endpoints if ep.service_family == service_family]

        # Check for special pages like authentication, health, etc.
        page_id = page_plan.page_id.lower()
        if "auth" in page_id:
            return [
                ep
                for ep in self.snapshot.endpoints
                if ep.auth_required or ep.auth_type in ("bearer", "oauth", "api-key")
            ]
        if "health" in page_id:
            return [
                ep
                for ep in self.snapshot.endpoints
                if "health" in ep.path.lower() or "ready" in ep.path.lower()
            ]

        return endpoints

    def _build_service_context(
        self,
        page_plan: WikiPagePlan,
        service_family: str | None,
        endpoints: list[Endpoint],
    ) -> dict[str, Any]:
        """Build service context for composition.

        Args:
            page_plan: The page plan
            service_family: Service family name
            endpoints: List of relevant endpoints

        Returns:
            Context dict for LLM composition
        """
        context: dict[str, Any] = {
            "page_id": page_plan.page_id,
            "title": page_plan.title,
            "service_family": service_family or "unknown",
            "endpoint_count": len(endpoints),
            "has_auth": any(ep.auth_required for ep in endpoints),
            "has_request_body": any(ep.request_body for ep in endpoints),
        }

        # Categorize endpoints
        auth_endpoints = [ep for ep in endpoints if ep.auth_required]
        health_endpoints = [
            ep for ep in endpoints if "health" in ep.path.lower() or "ready" in ep.path.lower()
        ]
        mutation_endpoints = [
            ep for ep in endpoints if ep.method in ("POST", "PUT", "PATCH", "DELETE")
        ]

        context["auth_endpoint_count"] = len(auth_endpoints)
        context["health_endpoint_count"] = len(health_endpoints)
        context["mutation_endpoint_count"] = len(mutation_endpoints)

        # Get unique error codes
        error_codes: set[int] = set()
        for ep in endpoints:
            error_codes.update(ep.error_codes)
        context["error_codes"] = sorted(error_codes)

        # Get modules involved (filter out None/empty values)
        modules = list(set(ep.module for ep in endpoints if ep.module))
        context["modules"] = modules

        return context

    async def compose_api_page_async(
        self,
        page_plan: WikiPagePlan,
        evidence_binding: PageEvidenceBinding | None = None,
    ) -> ComposerOutput:
        """Async version of compose_api_page.

        Args:
            page_plan: WikiPagePlan for the API page
            evidence_binding: Optional evidence binding

        Returns:
            ComposerOutput with generated Markdown
        """
        service_family = self._extract_service_family(page_plan.page_id)
        endpoints = self._get_endpoints_for_service_family(service_family, page_plan)
        context = self._build_service_context(page_plan, service_family, endpoints)

        # Build composer context for LLM
        composer_context = self._create_composer_context(page_plan, context, endpoints)

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
        endpoints: list[Endpoint],
    ) -> ComposerContext:
        """Create ComposerContext for LLM composition.

        Args:
            page_plan: The page plan
            service_context: Service-specific context
            endpoints: List of endpoints

        Returns:
            ComposerContext ready for LLM composition
        """
        # Build endpoints summary
        endpoint_summaries = [
            {
                "path": ep.path,
                "method": ep.method,
                "auth_required": ep.auth_required,
                "auth_type": ep.auth_type,
                "request_body": ep.request_body,
            }
            for ep in endpoints
        ]

        return ComposerContext(
            repository_name=service_context.get("service_family", "unknown"),
            primary_language="python",
            framework="fastapi",
            repository_root=str(self.workspace_root) if self.workspace_root else ".",
            endpoints=endpoint_summaries,
        )

    def _compose_with_llm(
        self,
        page_plan: WikiPagePlan,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
        endpoints: list[Endpoint],
    ) -> ComposerOutput:
        """Generate content using LLM composer.

        This is a synchronous wrapper that uses the underlying async method.
        """
        import asyncio

        return asyncio.run(self.compose_api_page_async(page_plan, evidence_binding))

    def format_endpoint_table(self, endpoints: list[Endpoint]) -> str:
        """Format endpoints as a bounded markdown table.

        Args:
            endpoints: List of endpoints to format

        Returns:
            Markdown table string (limited to representative endpoints)
        """
        if not endpoints:
            return ""

        # Limit to 10 representative endpoints
        representative = endpoints[:10]

        lines = ["| Method | Path | Auth | Description |", "|--------|------|------|-------------|"]

        for ep in representative:
            auth_str = ep.auth_type if ep.auth_required else "none"
            # Short description based on handler
            desc = ep.handler or f"{ep.method} {ep.path}"
            lines.append(f"| {ep.method} | `{ep.path}` | {auth_str} | {desc} |")

        if len(endpoints) > 10:
            lines.append(f"\n*... and {len(endpoints) - 10} more endpoints*")

        return "\n".join(lines)

    def format_service_purpose(self, service_family: str | None, endpoints: list[Endpoint]) -> str:
        """Format service purpose description.

        Args:
            service_family: Service family name
            endpoints: Endpoints in this service

        Returns:
            Prose describing service purpose
        """
        if not service_family:
            return "This API group provides various endpoints for the repository."

        # Generate purpose based on endpoints
        auth_count = sum(1 for ep in endpoints if ep.auth_required)
        mutation_count = sum(
            1 for ep in endpoints if ep.method in ("POST", "PUT", "PATCH", "DELETE")
        )
        query_count = sum(1 for ep in endpoints if ep.method == "GET")

        purpose_parts = [f"The **{service_family}** service family"]

        if mutation_count > query_count:
            purpose_parts.append("provides mutation-focused operations")
        elif query_count > mutation_count:
            purpose_parts.append("provides query-focused operations")
        else:
            purpose_parts.append("provides both query and mutation operations")

        if auth_count > 0:
            purpose_parts.append(f"with {auth_count} authenticated endpoints")

        purpose_parts.append(f"spanning {len(endpoints)} total endpoints.")

        return " ".join(purpose_parts)


# =============================================================================
# COMPOSER FACTORY
# =============================================================================


def create_service_family_composer(
    snapshot: RepositorySnapshot,
    llm_provider: MockLLMProvider | None = None,
    workspace_root: str | Path | None = None,
) -> ServiceFamilyAPIComposer:
    """Create a service family API composer.

    Args:
        snapshot: Repository snapshot with enriched endpoints
        llm_provider: Optional LLM provider
        workspace_root: Optional workspace root

    Returns:
        ServiceFamilyAPComposer instance
    """
    return ServiceFamilyAPIComposer(
        snapshot=snapshot,
        llm_provider=llm_provider,
        workspace_root=workspace_root,
    )


# =============================================================================
# STANDALONE COMPOSITION HELPERS
# =============================================================================


def compose_service_family_article(
    page_plan: WikiPagePlan,
    snapshot: RepositorySnapshot,
    evidence_binding: PageEvidenceBinding | None = None,
    llm_provider: MockLLMProvider | None = None,
    workspace_root: str | Path | None = None,
) -> ComposerOutput:
    """Convenience function to compose a service family API article.

    Args:
        page_plan: WikiPagePlan for the API page
        snapshot: Repository snapshot with endpoints
        evidence_binding: Optional evidence binding
        llm_provider: Optional LLM provider
        workspace_root: Optional workspace root

    Returns:
        ComposerOutput with generated content
    """
    composer = create_service_family_composer(
        snapshot=snapshot,
        llm_provider=llm_provider,
        workspace_root=workspace_root,
    )
    return composer.compose_api_page(page_plan, evidence_binding)


async def compose_service_family_article_async(
    page_plan: WikiPagePlan,
    snapshot: RepositorySnapshot,
    evidence_binding: PageEvidenceBinding | None = None,
    llm_provider: MockLLMProvider | None = None,
    workspace_root: str | Path | None = None,
) -> ComposerOutput:
    """Async convenience function to compose a service family API article.

    Args:
        page_plan: WikiPagePlan for the API page
        snapshot: Repository snapshot with endpoints
        evidence_binding: Optional evidence binding
        llm_provider: Optional LLM provider
        workspace_root: Optional workspace root

    Returns:
        ComposerOutput with generated content
    """
    composer = create_service_family_composer(
        snapshot=snapshot,
        llm_provider=llm_provider,
        workspace_root=workspace_root,
    )
    return await composer.compose_api_page_async(page_plan, evidence_binding)
