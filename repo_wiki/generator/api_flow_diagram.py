"""API flow diagram generator for service family sequence diagrams.

This module generates sequence diagrams for core API service families using
the existing MermaidPlanner and MermaidRenderer from Task 24.4.

Phase 25 - Task 25.5: API flow diagram generation

Key features:
- Generate sequence diagrams per core API service family
- Cite handlers and downstream calls used in diagrams
- Validate Mermaid syntax before writing output
- Integration with existing diagram planner pipeline
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from repo_wiki.core.contracts import Endpoint, RepositorySnapshot, extract_service_family_from_page_id
from repo_wiki.evidence.ranking import EvidenceCandidate, PageEvidenceBinding
from repo_wiki.generator.mermaid_planner import (
    DiagramPlan,
    MermaidDiagramType,
    MermaidPlanner,
    MermaidRenderer,
    create_planner,
    create_renderer,
    validate_mermaid_syntax,
)
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord
from repo_wiki.planner.schema import WikiPagePlan


# =============================================================================
# API FLOW DIAGRAM GENERATOR
# =============================================================================


@dataclass
class APIFlowEvidence:
    """Evidence backing an API flow diagram."""
    handler_file: str
    handler_line: int
    handler_symbol: str
    downstream_calls: list[tuple[str, str, str]] = field(default_factory=list)  # (service, path, handler)


@dataclass
class APIFlowDiagram:
    """An API flow diagram with evidence backing."""
    diagram_id: str
    service_family: str
    title: str
    diagram_plan: DiagramPlan
    evidence: list[APIFlowEvidence] = field(default_factory=list)


class APIFlowDiagramGenerator:
    """Generates sequence diagrams for API service families.

    This generator creates API flow diagrams that show:
    - Client to API endpoint interactions
    - Handler citations (file and line)
    - Downstream service calls

    Uses the existing MermaidPlanner and MermaidRenderer from Task 24.4.
    """

    def __init__(
        self,
        snapshot: RepositorySnapshot,
        workspace_root: str | None = None,
    ) -> None:
        """Initialize the API flow diagram generator.

        Args:
            snapshot: Repository snapshot with enriched endpoints
            workspace_root: Optional workspace root for path resolution
        """
        self.snapshot = snapshot
        self.workspace_root = workspace_root
        self._planner = create_planner(workspace_root)
        self._renderer = create_renderer()

    def generate_flow_diagram(
        self,
        page_plan: WikiPagePlan,
        evidence_binding: PageEvidenceBinding | None = None,
    ) -> APIFlowDiagram | None:
        """Generate a flow diagram for an API page.

        Args:
            page_plan: WikiPagePlan for the API page
            evidence_binding: Optional evidence binding for this page

        Returns:
            APIFlowDiagram with rendered mermaid code, or None if no endpoints found
        """
        service_family = self._extract_service_family(page_plan.page_id)
        endpoints = self._get_endpoints_for_page(page_plan)

        if not endpoints:
            return None

        # Build context for diagram planning
        context = self._build_flow_context(page_plan, service_family, endpoints)

        # Plan the diagram
        diagrams = self._planner.plan_diagram_for_page(
            page_id=page_plan.page_id,
            page_type="api",
            evidence_binding=evidence_binding,
            context=context,
        )

        if not diagrams:
            return None

        diagram_plan = diagrams[0]

        # Collect evidence from endpoints
        flow_evidence = self._collect_flow_evidence(endpoints)

        # Create API flow diagram
        flow_diagram = APIFlowDiagram(
            diagram_id=diagram_plan.diagram_id,
            service_family=service_family or "unknown",
            title=diagram_plan.title,
            diagram_plan=diagram_plan,
            evidence=flow_evidence,
        )

        # Render the diagram
        rendered = self._renderer.render_diagram(diagram_plan)

        # Validate syntax
        is_valid, error_msg = validate_mermaid_syntax(rendered, diagram_plan.diagram_type)

        if is_valid:
            diagram_plan.rendered_diagram = rendered
        else:
            diagram_plan.rendered_diagram = None

        return flow_diagram

    def generate_flow_diagrams_for_service_families(
        self,
        page_plans: list[WikiPagePlan],
        evidence_bindings: dict[str, PageEvidenceBinding] | None = None,
    ) -> list[APIFlowDiagram]:
        """Generate flow diagrams for multiple API pages.

        Args:
            page_plans: List of WikiPagePlans to generate diagrams for
            evidence_bindings: Optional dict mapping page_id to evidence binding

        Returns:
            List of APIFlowDiagrams (one per page with endpoints)
        """
        diagrams: list[APIFlowDiagram] = []
        evidence_bindings = evidence_bindings or {}

        for page_plan in page_plans:
            evidence = evidence_bindings.get(page_plan.page_id)
            flow_diagram = self.generate_flow_diagram(page_plan, evidence)
            if flow_diagram:
                diagrams.append(flow_diagram)

        return diagrams

    def _extract_service_family(self, page_id: str) -> str | None:
        """Extract service family name from page ID.

        Args:
            page_id: Page ID like 'api-python-backend' or 'api-authentication'

        Returns:
            Service family name or None
        """
        return extract_service_family_from_page_id(page_id)

    def _get_endpoints_for_page(self, page_plan: WikiPagePlan) -> list[Endpoint]:
        """Get endpoints relevant to this API page.

        Args:
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
        service_family = self._extract_service_family(page_plan.page_id)
        if service_family:
            return [
                ep for ep in self.snapshot.endpoints
                if ep.service_family == service_family
            ]

        # Check for special pages like authentication, health, etc.
        page_id = page_plan.page_id.lower()
        if "auth" in page_id:
            return [
                ep for ep in self.snapshot.endpoints
                if ep.auth_required or ep.auth_type in ("bearer", "oauth", "api-key")
            ]
        if "health" in page_id:
            return [
                ep for ep in self.snapshot.endpoints
                if "health" in ep.path.lower() or "ready" in ep.path.lower()
            ]

        return endpoints

    def _build_flow_context(
        self,
        page_plan: WikiPagePlan,
        service_family: str | None,
        endpoints: list[Endpoint],
    ) -> dict[str, Any]:
        """Build context for flow diagram planning.

        Args:
            page_plan: The page plan
            service_family: Service family name
            endpoints: List of relevant endpoints

        Returns:
            Context dict for diagram planning
        """
        # Build endpoint info for context
        endpoint_contexts: list[dict[str, Any]] = []
        for ep in endpoints[:10]:  # Limit to 10
            endpoint_contexts.append({
                "path": ep.path,
                "method": ep.method,
                "service": ep.service_family,
                "handler": ep.handler,
                "file_path": ep.file_path,
            })

        return {
            "page_id": page_plan.page_id,
            "title": page_plan.title,
            "service_family": service_family or "unknown",
            "endpoints": endpoint_contexts,
        }

    def _collect_flow_evidence(self, endpoints: list[Endpoint]) -> list[APIFlowEvidence]:
        """Collect evidence from endpoints for diagram citation.

        Args:
            endpoints: List of endpoints to extract evidence from

        Returns:
            List of APIFlowEvidence with handler citations
        """
        evidence: list[APIFlowEvidence] = []

        for ep in endpoints:
            # TODO: downstream_calls is empty because Endpoint lacks downstream call info.
            # When endpoint metadata is enriched with call-graph data, populate this field.
            downstream_calls: list[tuple[str, str, str]] = []  # (service, path, handler)
            flow_evidence = APIFlowEvidence(
                handler_file=ep.file_path,
                handler_line=ep.line_number,
                handler_symbol=ep.handler,
                downstream_calls=downstream_calls,
            )
            evidence.append(flow_evidence)

        return evidence


# =============================================================================
# SPECIALIZED API FLOW DIAGRAMS
# =============================================================================


class SpecializedAPIFlowGenerator:
    """Generates specialized flow diagrams for auth, error, and health APIs."""

    def __init__(
        self,
        snapshot: RepositorySnapshot,
        workspace_root: str | None = None,
    ) -> None:
        """Initialize the specialized API flow generator.

        Args:
            snapshot: Repository snapshot with enriched endpoints
            workspace_root: Optional workspace root
        """
        self.snapshot = snapshot
        self.workspace_root = workspace_root
        self._base_generator = APIFlowDiagramGenerator(snapshot, workspace_root)
        self._renderer = create_renderer()

    def generate_auth_flow_diagram(
        self,
        page_plan: WikiPagePlan,
        evidence_binding: PageEvidenceBinding | None = None,
    ) -> APIFlowDiagram | None:
        """Generate authentication/authorization flow diagram.

        Args:
            page_plan: WikiPagePlan for auth API page
            evidence_binding: Optional evidence binding

        Returns:
            APIFlowDiagram showing auth flow or None
        """
        # Get auth endpoints
        auth_endpoints = [
            ep for ep in self.snapshot.endpoints
            if ep.auth_required or ep.auth_type in ("bearer", "oauth", "api-key")
        ]

        if not auth_endpoints:
            return None

        # Build auth-specific context
        context = {
            "endpoints": [
                {
                    "path": ep.path,
                    "method": ep.method,
                    "service": ep.service_family,
                    "auth_type": ep.auth_type,
                }
                for ep in auth_endpoints[:10]
            ]
        }

        # Plan diagram
        planner = create_planner(self.workspace_root)
        diagrams = planner.plan_diagram_for_page(
            page_id=page_plan.page_id,
            page_type="api",
            evidence_binding=evidence_binding,
            context=context,
        )

        if not diagrams:
            return None

        diagram_plan = diagrams[0]

        # Collect auth-specific evidence
        evidence = [
            APIFlowEvidence(
                handler_file=ep.file_path,
                handler_line=ep.line_number,
                handler_symbol=ep.handler,
                downstream_calls=[("auth", ep.path, ep.handler)],
            )
            for ep in auth_endpoints
        ]

        return APIFlowDiagram(
            diagram_id=diagram_plan.diagram_id,
            service_family="authentication",
            title=f"Auth Flow: {page_plan.title}",
            diagram_plan=diagram_plan,
            evidence=evidence,
        )

    def generate_health_check_flow_diagram(
        self,
        page_plan: WikiPagePlan,
        evidence_binding: PageEvidenceBinding | None = None,
    ) -> APIFlowDiagram | None:
        """Generate health check flow diagram.

        Args:
            page_plan: WikiPagePlan for health API page
            evidence_binding: Optional evidence binding

        Returns:
            APIFlowDiagram showing health check flow or None
        """
        health_endpoints = [
            ep for ep in self.snapshot.endpoints
            if "health" in ep.path.lower() or "ready" in ep.path.lower()
        ]

        if not health_endpoints:
            return None

        # Build health-specific context
        context = {
            "endpoints": [
                {
                    "path": ep.path,
                    "method": ep.method,
                    "service": ep.service_family,
                }
                for ep in health_endpoints
            ]
        }

        # Plan diagram
        planner = create_planner(self.workspace_root)
        diagrams = planner.plan_diagram_for_page(
            page_id=page_plan.page_id,
            page_type="api",
            evidence_binding=evidence_binding,
            context=context,
        )

        if not diagrams:
            return None

        diagram_plan = diagrams[0]

        # Collect health-specific evidence
        evidence = [
            APIFlowEvidence(
                handler_file=ep.file_path,
                handler_line=ep.line_number,
                handler_symbol=ep.handler,
            )
            for ep in health_endpoints
        ]

        return APIFlowDiagram(
            diagram_id=diagram_plan.diagram_id,
            service_family="health",
            title=f"Health Check Flow: {page_plan.title}",
            diagram_plan=diagram_plan,
            evidence=evidence,
        )


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_api_flow_diagram_generator(
    snapshot: RepositorySnapshot,
    workspace_root: str | None = None,
) -> APIFlowDiagramGenerator:
    """Create an API flow diagram generator.

    Args:
        snapshot: Repository snapshot with enriched endpoints
        workspace_root: Optional workspace root

    Returns:
        APIFlowDiagramGenerator instance
    """
    return APIFlowDiagramGenerator(snapshot=snapshot, workspace_root=workspace_root)


def create_specialized_flow_generator(
    snapshot: RepositorySnapshot,
    workspace_root: str | None = None,
) -> SpecializedAPIFlowGenerator:
    """Create a specialized API flow generator.

    Args:
        snapshot: Repository snapshot with enriched endpoints
        workspace_root: Optional workspace root

    Returns:
        SpecializedAPIFlowGenerator instance
    """
    return SpecializedAPIFlowGenerator(snapshot=snapshot, workspace_root=workspace_root)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def generate_api_flow_diagram(
    page_plan: WikiPagePlan,
    snapshot: RepositorySnapshot,
    evidence_binding: PageEvidenceBinding | None = None,
    workspace_root: str | None = None,
) -> APIFlowDiagram | None:
    """Convenience function to generate a single API flow diagram.

    Args:
        page_plan: WikiPagePlan for the API page
        snapshot: Repository snapshot with enriched endpoints
        evidence_binding: Optional evidence binding
        workspace_root: Optional workspace root

    Returns:
        APIFlowDiagram with rendered mermaid code, or None if no endpoints
    """
    generator = create_api_flow_diagram_generator(snapshot, workspace_root)
    return generator.generate_flow_diagram(page_plan, evidence_binding)


def render_flow_diagram_to_markdown(
    flow_diagram: APIFlowDiagram,
) -> str:
    """Render an API flow diagram to Markdown with mermaid block.

    Args:
        flow_diagram: The API flow diagram to render

    Returns:
        Markdown string with ```mermaid block
    """
    if not flow_diagram.diagram_plan.rendered_diagram:
        return ""

    return f"""## {flow_diagram.title}

Service Family: **{flow_diagram.service_family}**

```mermaid
{flow_diagram.diagram_plan.rendered_diagram}
```

### Handler Citations
"""