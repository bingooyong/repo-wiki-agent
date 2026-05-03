"""Mermaid diagram planner and renderer for wiki pages.

This module provides:
- MermaidDiagramType: Enum of supported diagram types
- DiagramPlan: Plan for a diagram with evidence backing
- MermaidPlanner: Decides which diagram type to use based on page type and evidence
- MermaidRenderer: Renders valid Mermaid syntax
- validate_mermaid_syntax: Validates Mermaid syntax before writing

Phase 24 - Task 24.4: Mermaid diagram planner and renderer

Diagram types supported:
- flowchart: Process flows, architecture flows (TD/BT/LR/RL)
- sequenceDiagram: API calls, service interactions
- erDiagram: Entity relationships for data models
- classDiagram: Module/class relationships
- stateDiagram: State machine transitions
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from repo_wiki.evidence.ranking import PageEvidenceBinding
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord

# ============================================================================
# DIAGRAM TYPE DEFINITIONS
# ============================================================================


class MermaidDiagramType(str, Enum):
    """Supported Mermaid diagram types."""

    FLOWCHART = "flowchart"
    SEQUENCE_DIAGRAM = "sequenceDiagram"
    ER_DIAGRAM = "erDiagram"
    CLASS_DIAGRAM = "classDiagram"
    STATE_DIAGRAM = "stateDiagram"
    JOURNEY_DIAGRAM = "journey"


# Diagram type to Mermaid code block language
DIAGRAM_TYPE_TO_LANG = {
    MermaidDiagramType.FLOWCHART: "mermaid",
    MermaidDiagramType.SEQUENCE_DIAGRAM: "mermaid",
    MermaidDiagramType.ER_DIAGRAM: "mermaid",
    MermaidDiagramType.CLASS_DIAGRAM: "mermaid",
    MermaidDiagramType.STATE_DIAGRAM: "mermaid",
    MermaidDiagramType.JOURNEY_DIAGRAM: "mermaid",
}


# Page types that benefit from each diagram type
PAGE_TYPE_TO_DIAGRAM_PREFERENCE = {
    # Overview and architecture benefit from flowchart
    "overview": [MermaidDiagramType.FLOWCHART, MermaidDiagramType.STATE_DIAGRAM],
    "architecture": [MermaidDiagramType.FLOWCHART, MermaidDiagramType.CLASS_DIAGRAM],
    "section": [MermaidDiagramType.FLOWCHART, MermaidDiagramType.STATE_DIAGRAM],
    # Service pages benefit from sequence and flow
    "service": [MermaidDiagramType.SEQUENCE_DIAGRAM, MermaidDiagramType.FLOWCHART],
    # API pages benefit from sequence diagrams
    "api": [MermaidDiagramType.SEQUENCE_DIAGRAM, MermaidDiagramType.FLOWCHART],
    # Data model pages benefit from ER diagrams
    "data": [MermaidDiagramType.ER_DIAGRAM, MermaidDiagramType.CLASS_DIAGRAM],
    # Entity pages benefit from ER and class diagrams
    "entity": [MermaidDiagramType.ER_DIAGRAM, MermaidDiagramType.CLASS_DIAGRAM],
    # Ops pages benefit from flowcharts
    "ops": [MermaidDiagramType.FLOWCHART, MermaidDiagramType.STATE_DIAGRAM],
    # Development guides benefit from flowcharts
    "development": [MermaidDiagramType.FLOWCHART, MermaidDiagramType.JOURNEY_DIAGRAM],
}


# ============================================================================
# DIAGRAM PLAN AND EVIDENCE
# ============================================================================


@dataclass
class DiagramNode:
    """A node in a Mermaid diagram."""

    id: str
    label: str
    shape: str | None = None  # e.g., "round", "circle", "diamond"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagramEdge:
    """An edge/arrow in a Mermaid diagram."""

    from_node: str
    to_node: str
    label: str | None = None
    style: str | None = None  # e.g., "==>\" for thick arrow


@dataclass
class DiagramPlan:
    """Plan for generating a Mermaid diagram."""

    diagram_id: str
    diagram_type: MermaidDiagramType
    title: str
    description: str | None = None

    # For flowchart
    nodes: list[DiagramNode] = field(default_factory=list)
    edges: list[DiagramEdge] = field(default_factory=list)

    # For sequence diagram
    sequence_participants: list[str] = field(default_factory=list)
    sequence_messages: list[tuple[str, str, str]] = field(
        default_factory=list
    )  # (from, to, message)

    # For ER diagram
    er_entities: list[dict[str, Any]] = field(
        default_factory=list
    )  # {entity, attributes, primary_key}

    # For class diagram
    class_definitions: list[dict[str, Any]] = field(default_factory=list)

    # Source evidence backing this diagram
    evidence_spans: list[EvidenceSpanRecord] = field(default_factory=list)

    # Rendered mermaid code (populated after rendering)
    rendered_diagram: str | None = None


# ============================================================================
# MERMAID SYNTAX VALIDATOR
# ============================================================================


class MermaidSyntaxError(Exception):
    """Raised when Mermaid syntax is invalid."""

    pass


def validate_mermaid_syntax(
    diagram_code: str, diagram_type: MermaidDiagramType
) -> tuple[bool, str]:
    """Validate Mermaid diagram syntax.

    Args:
        diagram_code: The Mermaid diagram code (without ```mermaid wrapper)
        diagram_type: Type of diagram

    Returns:
        (is_valid, error_message) tuple
    """
    if not diagram_code or not diagram_code.strip():
        return False, "Diagram code is empty"

    errors: list[str] = []

    # Common validation for all diagram types
    lines = diagram_code.strip().split("\n")

    if diagram_type == MermaidDiagramType.FLOWCHART:
        errors.extend(_validate_flowchart_syntax(diagram_code, lines))
    elif diagram_type == MermaidDiagramType.SEQUENCE_DIAGRAM:
        errors.extend(_validate_sequence_syntax(diagram_code, lines))
    elif diagram_type == MermaidDiagramType.ER_DIAGRAM:
        errors.extend(_validate_er_syntax(diagram_code, lines))
    elif diagram_type == MermaidDiagramType.CLASS_DIAGRAM:
        errors.extend(_validate_class_syntax(diagram_code, lines))
    elif diagram_type == MermaidDiagramType.STATE_DIAGRAM:
        errors.extend(_validate_state_syntax(diagram_code, lines))

    if errors:
        return False, "; ".join(errors[:3])  # Limit to first 3 errors

    return True, "Valid"


def _validate_flowchart_syntax(code: str, lines: list[str]) -> list[str]:
    """Validate flowchart syntax."""
    errors = []

    # Check for proper direction indicator
    has_direction = any(
        re.match(r"^\s*(flowchart\s+[BTLR][R]?\s*|graph\s+[BTLR][R]?)", line) for line in lines
    )
    if not has_direction:
        # Also check for simple graph direction
        has_direction = any(re.match(r"^\s*(graph\s+[TDLR]\s*)", line) for line in lines)
    if not has_direction:
        errors.append("Flowchart missing direction (TD/BT/LR/RL)")

    # Check for node definitions (format: A[...] or A([...]) etc.)
    node_pattern = re.compile(r"^\s*([A-Za-z0-9_]+)(\[|\(|\{|\<|[\|])")
    has_nodes = any(node_pattern.match(line) for line in lines)

    # Alternative: edges can also define nodes implicitly
    edge_pattern = re.compile(r"^\s*([A-Za-z0-9_]+)\s*[-.]+[>=]")
    has_edges = any(edge_pattern.match(line) for line in lines)
    has_implicit_nodes = any(edge_pattern.match(line) for line in lines)

    if not has_nodes and not has_implicit_nodes and len(lines) > 1:
        errors.append("Flowchart has no visible node definitions")

    # Check for balanced brackets in node definitions
    for line in lines:
        # Skip direction and comment lines
        if line.strip().startswith("flowchart") or line.strip().startswith("graph"):
            continue
        if line.strip().startswith("%%"):
            continue

        # Count bracket balance
        open_brackets = line.count("[") + line.count("(") + line.count("{")
        close_brackets = line.count("]") + line.count(")") + line.count("}")

        if open_brackets != close_brackets:
            # Only warn if line has both types
            if open_brackets > 0 or close_brackets > 0:
                errors.append(f"Unbalanced brackets in: {line[:50]}")
                break

    return errors


def _validate_sequence_syntax(code: str, lines: list[str]) -> list[str]:
    """Validate sequence diagram syntax."""
    errors = []

    # Check for sequenceDiagram header
    has_header = any(re.match(r"^\s*sequenceDiagram\s*$", line) for line in lines)
    if not has_header:
        errors.append("Sequence diagram missing 'sequenceDiagram' header")

    # Check for participant declarations
    participant_pattern = re.compile(r"^\s*participant\s+")
    has_participants = any(participant_pattern.match(line) for line in lines)
    if not has_participants:
        errors.append("Sequence diagram has no participant declarations")

    # Check for message arrows (format: A->>B or A->B)
    message_pattern = re.compile(r"^\s*([A-Za-z0-9_]+)\s*[-.]+[>x-]", re.IGNORECASE)
    has_messages = any(message_pattern.match(line) for line in lines)
    if not has_messages:
        errors.append("Sequence diagram has no message arrows")

    return errors


def _validate_er_syntax(code: str, lines: list[str]) -> list[str]:
    """Validate ER diagram syntax."""
    errors = []

    # Check for erDiagram header
    has_header = any(re.match(r"^\s*erDiagram\s*$", line) for line in lines)
    if not has_header:
        errors.append("ER diagram missing 'erDiagram' header")

    # Check for entity declarations
    entity_pattern = re.compile(r"^\s*([A-Za-z0-9_]+)\s*\{", re.IGNORECASE)
    has_entities = any(entity_pattern.match(line) for line in lines)
    if not has_entities:
        errors.append("ER diagram has no entity declarations")

    return errors


def _validate_class_syntax(code: str, lines: list[str]) -> list[str]:
    """Validate class diagram syntax."""
    errors = []

    # Check for classDiagram header
    has_header = any(re.match(r"^\s*classDiagram\s*$", line) for line in lines)
    if not has_header:
        errors.append("Class diagram missing 'classDiagram' header")

    # Check for class declarations
    class_pattern = re.compile(r"^\s*class\s+", re.IGNORECASE)
    has_classes = any(class_pattern.match(line) for line in lines)
    if not has_classes:
        errors.append("Class diagram has no class declarations")

    return errors


def _validate_state_syntax(code: str, lines: list[str]) -> list[str]:
    """Validate state diagram syntax."""
    errors = []

    # Check for stateDiagram header (accept variants like stateDiagram-v2)
    has_header = any(
        re.match(r"^\s*stateDiagram[-a-z0-9]*\s*", line, re.IGNORECASE) for line in lines
    )
    if not has_header:
        errors.append("State diagram missing 'stateDiagram' header")

    # Check for state definitions or transitions
    state_pattern = re.compile(r"^\s*state\s+", re.IGNORECASE)
    transition_pattern = re.compile(r"^\s*\[.*\]\s*-->|-->\s*\[", re.IGNORECASE)
    has_states = any(state_pattern.match(line) for line in lines)
    has_transitions = any(transition_pattern.search(line) for line in lines)
    if not has_states and not has_transitions:
        errors.append("State diagram has no state definitions or transitions")

    return errors


# ============================================================================
# MERMAID PLANNER
# ============================================================================


class MermaidPlanner:
    """Plans Mermaid diagrams for wiki pages based on page type and evidence.

    The planner decides:
    1. Which diagram type is most appropriate for the page
    2. What content should go in the diagram
    3. Which evidence spans back the diagram elements
    """

    def __init__(self, workspace_root: str | None = None) -> None:
        self.workspace_root = workspace_root

    def plan_diagram_for_page(
        self,
        page_id: str,
        page_type: str,
        evidence_binding: PageEvidenceBinding | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[DiagramPlan]:
        """Plan diagrams for a wiki page.

        Args:
            page_id: Unique page identifier
            page_type: Page type string (e.g., "overview", "api", "data")
            evidence_binding: Evidence binding with candidates
            context: Additional context (modules, endpoints, etc.)

        Returns:
            List of DiagramPlan objects for this page
        """
        diagrams: list[DiagramPlan] = []
        context = context or {}

        # Get preferred diagram types for this page type
        preferred_types = PAGE_TYPE_TO_DIAGRAM_PREFERENCE.get(
            page_type, [MermaidDiagramType.FLOWCHART]
        )

        # Plan based on page type
        if page_type in ("overview", "architecture"):
            diagram = self._plan_overview_architecture_diagram(page_id, evidence_binding, context)
            if diagram:
                diagrams.append(diagram)

        elif page_type in ("service", "section"):
            diagram = self._plan_service_diagram(page_id, evidence_binding, context)
            if diagram:
                diagrams.append(diagram)

        elif page_type == "api":
            diagram = self._plan_api_diagram(page_id, evidence_binding, context)
            if diagram:
                diagrams.append(diagram)

        elif page_type in ("data", "entity"):
            diagram = self._plan_data_model_diagram(page_id, evidence_binding, context)
            if diagram:
                diagrams.append(diagram)

        elif page_type == "ops":
            diagram = self._plan_ops_diagram(page_id, evidence_binding, context)
            if diagram:
                diagrams.append(diagram)

        return diagrams

    def _plan_overview_architecture_diagram(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        """Plan architecture/overview flowchart."""
        modules = context.get("modules", [])

        # Build nodes from modules
        nodes = []
        edges = []

        # Add repository root node
        nodes.append(DiagramNode(id="repo", label="Repository", shape="round"))

        # Add module nodes
        for i, module in enumerate(modules[:10]):  # Limit to 10 modules
            module_name = module.get("name", f"module_{i}")
            nodes.append(DiagramNode(id=module_name, label=module_name, shape="rectangle"))
            edges.append(DiagramEdge(from_node="repo", to_node=module_name))

        # Add layer nodes for three-layer architecture
        layers = [
            ("docs", "docs/", "rectangle"),
            ("ai", "ai/source-of-truth", "rectangle"),
            ("repo_wiki", ".repo-wiki", "rectangle"),
        ]
        for layer_id, layer_label, shape in layers:
            nodes.append(DiagramNode(id=layer_id, label=layer_label, shape=shape))
            edges.append(DiagramEdge(from_node="repo", to_node=layer_id))

        # Collect evidence spans
        evidence_spans = []
        if evidence_binding:
            for candidate in evidence_binding.candidates:
                evidence_spans.append(candidate.span)

        return DiagramPlan(
            diagram_id=f"{page_id}-architecture",
            diagram_type=MermaidDiagramType.FLOWCHART,
            title="Repository Architecture",
            description="Three-layer architecture overview",
            nodes=nodes,
            edges=edges,
            evidence_spans=evidence_spans,
        )

    def _plan_service_diagram(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        """Plan service/section flow diagram."""
        modules = context.get("modules", [])
        commands = context.get("commands", {})

        nodes = []
        edges = []

        # Add module nodes
        for i, module in enumerate(modules[:8]):
            module_name = module.get("name", f"module_{i}")
            nodes.append(DiagramNode(id=module_name, label=module_name, shape="rectangle"))

        # Add command nodes
        for cmd, cmd_line in list(commands.items())[:5]:
            cmd_id = f"cmd_{cmd}"
            nodes.append(DiagramNode(id=cmd_id, label=cmd, shape="rounded"))
            edges.append(DiagramEdge(from_node=cmd_id, to_node="start", style="==>"))

        evidence_spans = []
        if evidence_binding:
            for candidate in evidence_binding.candidates:
                evidence_spans.append(candidate.span)

        return DiagramPlan(
            diagram_id=f"{page_id}-service-flow",
            diagram_type=MermaidDiagramType.FLOWCHART,
            title="Service Flow",
            description="Module and command relationships",
            nodes=nodes,
            edges=edges,
            evidence_spans=evidence_spans,
        )

    def _plan_api_diagram(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        """Plan API sequence diagram."""
        endpoints = context.get("endpoints", [])

        # Extract participant names from endpoints
        participants: list[str] = []
        messages: list[tuple[str, str, str]] = []

        # Group endpoints by service
        seen_services: set[str] = set()
        for endpoint in endpoints[:10]:  # Limit to 10
            path = endpoint.get("path", "/unknown")
            method = endpoint.get("method", "GET")
            service = endpoint.get("service", "client")

            if service not in seen_services:
                participants.append(service)
                seen_services.add(service)

            # Create message: client -> service
            if service != "client":
                messages.append(("client", service, f"{method} {path}"))

        # If no endpoints, provide a generic client->API flow
        if not participants:
            participants = ["client", "API"]
            messages.append(("client", "API", "request"))

        evidence_spans = []
        if evidence_binding:
            for candidate in evidence_binding.candidates:
                evidence_spans.append(candidate.span)

        return DiagramPlan(
            diagram_id=f"{page_id}-api-sequence",
            diagram_type=MermaidDiagramType.SEQUENCE_DIAGRAM,
            title="API Sequence",
            description="API call flow and interactions",
            sequence_participants=participants,
            sequence_messages=messages,
            evidence_spans=evidence_spans,
        )

    def _plan_data_model_diagram(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        """Plan data model ER diagram."""
        models = context.get("data_models", [])
        modules = context.get("modules", [])

        er_entities = []
        for model in models[:10]:  # Limit to 10 models
            entity_name = model.get("name", model.get("table", "unknown"))
            attributes = model.get("attributes", [])
            primary_key = model.get("primary_key", "id")
            er_entities.append(
                {
                    "entity": entity_name,
                    "attributes": attributes,
                    "primary_key": primary_key,
                }
            )

        # If no explicit models, infer from modules
        if not er_entities:
            for module in modules[:5]:
                module_name = module.get("name", "unknown")
                er_entities.append(
                    {
                        "entity": module_name,
                        "attributes": [],
                        "primary_key": "id",
                    }
                )

        evidence_spans = []
        if evidence_binding:
            for candidate in evidence_binding.candidates:
                evidence_spans.append(candidate.span)

        return DiagramPlan(
            diagram_id=f"{page_id}-er-diagram",
            diagram_type=MermaidDiagramType.ER_DIAGRAM,
            title="Data Model",
            description="Entity relationships",
            er_entities=er_entities,
            evidence_spans=evidence_spans,
        )

    def _plan_ops_diagram(
        self,
        page_id: str,
        evidence_binding: PageEvidenceBinding | None,
        context: dict[str, Any],
    ) -> DiagramPlan | None:
        """Plan ops flowchart."""
        commands = context.get("commands", {})

        nodes = []
        edges = []

        # Add command nodes
        cmd_list = list(commands.items())[:8]
        if cmd_list:
            # Start node
            nodes.append(DiagramNode(id="start", label="Start", shape="circle"))
            prev_node = "start"
            for cmd, _ in cmd_list:
                cmd_id = f"cmd_{cmd}"
                nodes.append(DiagramNode(id=cmd_id, label=cmd, shape="rectangle"))
                edges.append(DiagramEdge(from_node=prev_node, to_node=cmd_id))
                prev_node = cmd_id
            # End node
            nodes.append(DiagramNode(id="end", label="End", shape="circle"))
            edges.append(DiagramEdge(from_node=prev_node, to_node="end"))

        evidence_spans = []
        if evidence_binding:
            for candidate in evidence_binding.candidates:
                evidence_spans.append(candidate.span)

        return DiagramPlan(
            diagram_id=f"{page_id}-ops-flow",
            diagram_type=MermaidDiagramType.FLOWCHART,
            title="Operations Flow",
            description="Command execution flow",
            nodes=nodes,
            edges=edges,
            evidence_spans=evidence_spans,
        )


# ============================================================================
# MERMAID RENDERER
# ============================================================================


class MermaidRenderer:
    """Renders Mermaid diagram plans to valid Mermaid syntax."""

    def __init__(self) -> None:
        pass

    def render_diagram(self, plan: DiagramPlan) -> str:
        """Render a DiagramPlan to Mermaid syntax string.

        Args:
            plan: DiagramPlan to render

        Returns:
            Mermaid code string (without ```mermaid wrapper)
        """
        if plan.diagram_type == MermaidDiagramType.FLOWCHART:
            return self._render_flowchart(plan)
        elif plan.diagram_type == MermaidDiagramType.SEQUENCE_DIAGRAM:
            return self._render_sequence(plan)
        elif plan.diagram_type == MermaidDiagramType.ER_DIAGRAM:
            return self._render_er(plan)
        elif plan.diagram_type == MermaidDiagramType.CLASS_DIAGRAM:
            return self._render_class(plan)
        elif plan.diagram_type == MermaidDiagramType.STATE_DIAGRAM:
            return self._render_state(plan)
        elif plan.diagram_type == MermaidDiagramType.JOURNEY_DIAGRAM:
            return self._render_journey(plan)
        else:
            return self._render_flowchart(plan)  # Default to flowchart

    def _render_flowchart(self, plan: DiagramPlan) -> str:
        """Render flowchart diagram."""
        lines = ["flowchart TD"]

        # Render nodes
        for node in plan.nodes:
            if node.shape == "circle":
                lines.append(f"    {node.id}(({node.label}))")
            elif node.shape == "diamond":
                lines.append(f"    {node.id}{{{node.label}}}")
            elif node.shape == "rounded" or node.shape == "round":
                lines.append(f"    {node.id}(({node.label}))")
            elif node.shape == "rectangle":
                lines.append(f"    {node.id}[{node.label}]")
            else:
                lines.append(f"    {node.id}[{node.label}]")

        # Render edges
        for edge in plan.edges:
            if edge.style:
                lines.append(f"    {edge.from_node} {edge.style} {edge.to_node}")
            elif edge.label:
                lines.append(f"    {edge.from_node} -->|{edge.label}| {edge.to_node}")
            else:
                lines.append(f"    {edge.from_node} --> {edge.to_node}")

        return "\n".join(lines)

    def _render_sequence(self, plan: DiagramPlan) -> str:
        """Render sequence diagram."""
        lines = ["sequenceDiagram"]

        # Render participants
        for participant in plan.sequence_participants:
            lines.append(f"    participant {participant}")

        # Render messages
        for from_p, to_p, message in plan.sequence_messages:
            lines.append(f"    {from_p}->>+{to_p}: {message}")
            lines.append(f"    {to_p}-->>-{from_p}: response")

        return "\n".join(lines)

    def _render_er(self, plan: DiagramPlan) -> str:
        """Render ER diagram."""
        lines = ["erDiagram"]

        for entity in plan.er_entities:
            entity_name = entity.get("entity", "Unknown")
            attributes = entity.get("attributes", [])
            primary_key = entity.get("primary_key", "id")

            # Format attributes string
            attr_str = ""
            if attributes:
                attr_list = [f"{attr}" for attr in attributes]
                attr_str = " {" + ", ".join(attr_list) + "}"

            lines.append(f"    {entity_name} {{{primary_key}{attr_str}}}")

        return "\n".join(lines)

    def _render_class(self, plan: DiagramPlan) -> str:
        """Render class diagram."""
        lines = ["classDiagram"]

        for class_def in plan.class_definitions:
            class_name = class_def.get("name", "Unknown")
            lines.append(f"    class {class_name}")

            # Add methods if present
            methods = class_def.get("methods", [])
            for method in methods:
                lines.append(f"    {class_name} : {method}")

        return "\n".join(lines)

    def _render_state(self, plan: DiagramPlan) -> str:
        """Render state diagram."""
        lines = ["stateDiagram-v2"]
        lines.append("    [*] --> start")

        for node in plan.nodes:
            if node.id not in ("start", "end"):
                lines.append(f"    state {node.id} {{ {node.label} }}")
                lines.append(f"    start --> {node.id}")
                lines.append(f"    {node.id} --> [*]")

        return "\n".join(lines)

    def _render_journey(self, plan: DiagramPlan) -> str:
        """Render journey diagram."""
        lines = ["journey"]
        lines.append("    title TODO")

        for i, node in enumerate(plan.nodes[:5]):
            lines.append(f"    section {node.label}")
            lines.append(f"      {node.id}: {i+1}")

        return "\n".join(lines)

    def render_diagram_with_validation(self, plan: DiagramPlan) -> tuple[str | None, bool, str]:
        """Render a diagram and validate its syntax.

        Returns:
            (rendered_diagram, is_valid, error_message) tuple
        """
        rendered = self.render_diagram(plan)
        is_valid, error_msg = validate_mermaid_syntax(rendered, plan.diagram_type)

        if is_valid:
            return rendered, True, "Valid"
        else:
            return None, False, error_msg

    def render_diagram_block(self, plan: DiagramPlan) -> str:
        """Render a diagram as a complete Markdown code block.

        Args:
            plan: DiagramPlan to render

        Returns:
            Complete Markdown code block with ```mermaid wrapper
        """
        rendered = self.render_diagram(plan)
        return f"```mermaid\n{rendered}\n```"


# ============================================================================
# FACTORY AND HELPERS
# ============================================================================


def create_planner(workspace_root: str | None = None) -> MermaidPlanner:
    """Create a Mermaid planner.

    Args:
        workspace_root: Optional workspace root for path resolution

    Returns:
        MermaidPlanner instance
    """
    return MermaidPlanner(workspace_root=workspace_root)


def create_renderer() -> MermaidRenderer:
    """Create a Mermaid renderer.

    Returns:
        MermaidRenderer instance
    """
    return MermaidRenderer()


def plan_and_render_diagram(
    page_id: str,
    page_type: str,
    evidence_binding: PageEvidenceBinding | None = None,
    context: dict[str, Any] | None = None,
    workspace_root: str | None = None,
) -> tuple[str | None, bool, str]:
    """Plan and render a diagram for a wiki page.

    This is a convenience function that combines planning and rendering
    with syntax validation.

    Args:
        page_id: Unique page identifier
        page_type: Page type string
        evidence_binding: Evidence binding with candidates
        context: Additional context
        workspace_root: Optional workspace root

    Returns:
        (rendered_diagram, is_valid, error_message) tuple
    """
    planner = create_planner(workspace_root)
    renderer = create_renderer()

    diagrams = planner.plan_diagram_for_page(page_id, page_type, evidence_binding, context)

    if not diagrams:
        return None, False, "No diagram could be planned for this page type"

    # Render first diagram
    plan = diagrams[0]
    return renderer.render_diagram_with_validation(plan)


def link_diagram_to_evidence(
    diagram_plan: DiagramPlan,
    evidence_binding: PageEvidenceBinding | None,
) -> DiagramPlan:
    """Link a diagram plan to evidence spans.

    Args:
        diagram_plan: Diagram plan to update
        evidence_binding: Evidence binding with candidates

    Returns:
        Updated diagram plan with evidence links
    """
    if not evidence_binding:
        return diagram_plan

    existing_digests = {span.digest for span in diagram_plan.evidence_spans}
    for candidate in evidence_binding.candidates:
        if candidate.span.digest not in existing_digests:
            diagram_plan.evidence_spans.append(candidate.span)
            existing_digests.add(candidate.span.digest)

    return diagram_plan
