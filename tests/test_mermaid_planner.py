"""Tests for Mermaid diagram planner and renderer.

Tests the mermaid_planner module which provides:
- MermaidDiagramType: Enum of supported diagram types
- DiagramPlan: Plan for a diagram with evidence backing
- MermaidPlanner: Decides which diagram type to use based on page type
- MermaidRenderer: Renders valid Mermaid syntax
- validate_mermaid_syntax: Validates Mermaid syntax before writing
- plan_and_render_diagram: Convenience function combining plan and render

Phase 24 - Task 24.4: Mermaid diagram planner and renderer
"""

from __future__ import annotations

import pytest

from repo_wiki.generator.mermaid_planner import (
    MermaidDiagramType,
    DiagramNode,
    DiagramEdge,
    DiagramPlan,
    MermaidPlanner,
    MermaidRenderer,
    validate_mermaid_syntax,
    create_planner,
    create_renderer,
    plan_and_render_diagram,
    link_diagram_to_evidence,
)
from repo_wiki.evidence.ranking import EvidenceCandidate, PageEvidenceBinding
from repo_wiki.orchestration.runtime_store import EvidenceSpanRecord


class TestMermaidDiagramType:
    """Tests for MermaidDiagramType enum."""

    def test_diagram_types_exist(self):
        """Test all expected diagram types are defined."""
        assert MermaidDiagramType.FLOWCHART is not None
        assert MermaidDiagramType.SEQUENCE_DIAGRAM is not None
        assert MermaidDiagramType.ER_DIAGRAM is not None
        assert MermaidDiagramType.CLASS_DIAGRAM is not None
        assert MermaidDiagramType.STATE_DIAGRAM is not None

    def test_diagram_type_values(self):
        """Test diagram type string values."""
        assert MermaidDiagramType.FLOWCHART.value == "flowchart"
        assert MermaidDiagramType.SEQUENCE_DIAGRAM.value == "sequenceDiagram"
        assert MermaidDiagramType.ER_DIAGRAM.value == "erDiagram"


class TestDiagramNode:
    """Tests for DiagramNode."""

    def test_create_node(self):
        """Test creating a diagram node."""
        node = DiagramNode(id="A", label="Node A")
        assert node.id == "A"
        assert node.label == "Node A"
        assert node.shape is None

    def test_create_node_with_shape(self):
        """Test creating a node with shape."""
        node = DiagramNode(id="B", label="Node B", shape="rectangle")
        assert node.id == "B"
        assert node.shape == "rectangle"


class TestDiagramEdge:
    """Tests for DiagramEdge."""

    def test_create_edge(self):
        """Test creating an edge."""
        edge = DiagramEdge(from_node="A", to_node="B")
        assert edge.from_node == "A"
        assert edge.to_node == "B"
        assert edge.label is None

    def test_create_edge_with_label(self):
        """Test creating an edge with label."""
        edge = DiagramEdge(from_node="A", to_node="B", label="uses")
        assert edge.label == "uses"


class TestDiagramPlan:
    """Tests for DiagramPlan."""

    def test_create_flowchart_plan(self):
        """Test creating a flowchart plan."""
        plan = DiagramPlan(
            diagram_id="test-flow",
            diagram_type=MermaidDiagramType.FLOWCHART,
            title="Test Flow",
        )
        assert plan.diagram_id == "test-flow"
        assert plan.diagram_type == MermaidDiagramType.FLOWCHART
        assert len(plan.nodes) == 0
        assert len(plan.edges) == 0

    def test_create_sequence_plan(self):
        """Test creating a sequence diagram plan."""
        plan = DiagramPlan(
            diagram_id="test-seq",
            diagram_type=MermaidDiagramType.SEQUENCE_DIAGRAM,
            title="Test Sequence",
            sequence_participants=["client", "server"],
            sequence_messages=[("client", "server", "GET /api")],
        )
        assert plan.diagram_type == MermaidDiagramType.SEQUENCE_DIAGRAM
        assert len(plan.sequence_participants) == 2
        assert len(plan.sequence_messages) == 1


class TestValidateMermaidSyntax:
    """Tests for validate_mermaid_syntax function."""

    def test_valid_flowchart(self):
        """Test validating a valid flowchart."""
        code = """flowchart TD
    A[Start] --> B[End]"""
        is_valid, msg = validate_mermaid_syntax(code, MermaidDiagramType.FLOWCHART)
        assert is_valid is True
        assert msg == "Valid"

    def test_empty_code(self):
        """Test validating empty code."""
        is_valid, msg = validate_mermaid_syntax("", MermaidDiagramType.FLOWCHART)
        assert is_valid is False
        assert "empty" in msg.lower()

    def test_flowchart_missing_direction(self):
        """Test flowchart missing direction indicator."""
        code = """    A[Start]
    A --> B"""
        is_valid, msg = validate_mermaid_syntax(code, MermaidDiagramType.FLOWCHART)
        assert is_valid is False
        assert "direction" in msg.lower()

    def test_valid_sequence_diagram(self):
        """Test validating a valid sequence diagram."""
        code = """sequenceDiagram
    participant C as Client
    participant S as Server
    C->>+S: GET /api
    S-->>-C: response"""
        is_valid, msg = validate_mermaid_syntax(code, MermaidDiagramType.SEQUENCE_DIAGRAM)
        assert is_valid is True
        assert msg == "Valid"

    def test_sequence_missing_header(self):
        """Test sequence diagram missing header."""
        code = """    participant C as Client
    participant S as Server
    C->>S: GET"""
        is_valid, msg = validate_mermaid_syntax(code, MermaidDiagramType.SEQUENCE_DIAGRAM)
        assert is_valid is False
        assert "sequence" in msg.lower()

    def test_valid_er_diagram(self):
        """Test validating a valid ER diagram."""
        code = """erDiagram
    USER {
        int id PK
        string name
        string email
    }
    ORDER {
        int id PK
        int user_id FK
    }"""
        is_valid, msg = validate_mermaid_syntax(code, MermaidDiagramType.ER_DIAGRAM)
        assert is_valid is True
        assert msg == "Valid"

    def test_er_missing_header(self):
        """Test ER diagram missing header."""
        code = """    USER {
        int id PK
    }"""
        is_valid, msg = validate_mermaid_syntax(code, MermaidDiagramType.ER_DIAGRAM)
        assert is_valid is False
        assert "er" in msg.lower()

    def test_valid_class_diagram(self):
        """Test validating a valid class diagram."""
        code = """classDiagram
    class User {
        +int id
        +string name
        +getName()
    }"""
        is_valid, msg = validate_mermaid_syntax(code, MermaidDiagramType.CLASS_DIAGRAM)
        assert is_valid is True
        assert msg == "Valid"

    def test_valid_state_diagram(self):
        """Test validating a valid state diagram."""
        code = """stateDiagram-v2
    [*] --> start
    state start { }
    start --> [*]"""
        is_valid, msg = validate_mermaid_syntax(code, MermaidDiagramType.STATE_DIAGRAM)
        assert is_valid is True


class TestMermaidPlanner:
    """Tests for MermaidPlanner class."""

    def test_create_planner(self):
        """Test creating a planner."""
        planner = create_planner()
        assert planner is not None

    def test_plan_overview_architecture_diagram(self):
        """Test planning an overview/architecture diagram."""
        planner = create_planner()
        context = {
            "modules": [
                {"name": "auth", "path": "src/auth"},
                {"name": "api", "path": "src/api"},
            ]
        }

        diagrams = planner.plan_diagram_for_page(
            page_id="overview",
            page_type="overview",
            evidence_binding=None,
            context=context,
        )

        assert len(diagrams) >= 1
        diagram = diagrams[0]
        assert diagram.diagram_id == "overview-architecture"
        assert diagram.diagram_type == MermaidDiagramType.FLOWCHART

    def test_plan_api_diagram(self):
        """Test planning an API sequence diagram."""
        planner = create_planner()
        context = {
            "endpoints": [
                {"path": "/api/users", "method": "GET", "service": "users"},
                {"path": "/api/orders", "method": "POST", "service": "orders"},
            ]
        }

        diagrams = planner.plan_diagram_for_page(
            page_id="api-ref",
            page_type="api",
            evidence_binding=None,
            context=context,
        )

        assert len(diagrams) >= 1
        diagram = diagrams[0]
        assert diagram.diagram_type == MermaidDiagramType.SEQUENCE_DIAGRAM

    def test_plan_data_model_diagram(self):
        """Test planning a data model ER diagram."""
        planner = create_planner()
        context = {
            "data_models": [
                {"name": "User", "table": "users", "primary_key": "id"},
                {"name": "Order", "table": "orders", "primary_key": "id"},
            ]
        }

        diagrams = planner.plan_diagram_for_page(
            page_id="data-model",
            page_type="data",
            evidence_binding=None,
            context=context,
        )

        assert len(diagrams) >= 1
        diagram = diagrams[0]
        assert diagram.diagram_type == MermaidDiagramType.ER_DIAGRAM

    def test_plan_with_evidence_binding(self):
        """Test planning with evidence binding."""
        planner = create_planner()

        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/auth.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="AuthService",
            span_text="class AuthService:",
        )
        candidate = EvidenceCandidate(
            evidence_id=1,
            span=span,
            score=1.0,
            match_signals=["module_match"],
            citation_order=0,
        )
        binding = PageEvidenceBinding(
            page_id="overview",
            doc_type="overview",
            candidates=[candidate],
        )

        diagrams = planner.plan_diagram_for_page(
            page_id="overview",
            page_type="overview",
            evidence_binding=binding,
            context={},
        )

        assert len(diagrams) >= 1
        diagram = diagrams[0]
        assert len(diagram.evidence_spans) >= 1
        assert diagram.evidence_spans[0].file_path == "src/auth.py"


class TestMermaidRenderer:
    """Tests for MermaidRenderer class."""

    def test_create_renderer(self):
        """Test creating a renderer."""
        renderer = create_renderer()
        assert renderer is not None

    def test_render_flowchart(self):
        """Test rendering a flowchart."""
        renderer = create_renderer()
        plan = DiagramPlan(
            diagram_id="test",
            diagram_type=MermaidDiagramType.FLOWCHART,
            title="Test",
            nodes=[
                DiagramNode(id="A", label="Start", shape="round"),
                DiagramNode(id="B", label="End", shape="round"),
            ],
            edges=[
                DiagramEdge(from_node="A", to_node="B"),
            ],
        )

        result = renderer.render_diagram(plan)
        assert "flowchart TD" in result
        assert "A" in result
        assert "B" in result
        assert "-->" in result

    def test_render_sequence_diagram(self):
        """Test rendering a sequence diagram."""
        renderer = create_renderer()
        plan = DiagramPlan(
            diagram_id="test-seq",
            diagram_type=MermaidDiagramType.SEQUENCE_DIAGRAM,
            title="Test Sequence",
            sequence_participants=["client", "server"],
            sequence_messages=[("client", "server", "GET /api")],
        )

        result = renderer.render_diagram(plan)
        assert "sequenceDiagram" in result
        assert "client" in result
        assert "server" in result
        assert "GET /api" in result

    def test_render_er_diagram(self):
        """Test rendering an ER diagram."""
        renderer = create_renderer()
        plan = DiagramPlan(
            diagram_id="test-er",
            diagram_type=MermaidDiagramType.ER_DIAGRAM,
            title="Test ER",
            er_entities=[
                {"entity": "User", "attributes": ["name", "email"], "primary_key": "id"},
            ],
        )

        result = renderer.render_diagram(plan)
        assert "erDiagram" in result
        assert "User" in result
        assert "id" in result

    def test_render_diagram_with_validation(self):
        """Test rendering with validation."""
        renderer = create_renderer()
        plan = DiagramPlan(
            diagram_id="test",
            diagram_type=MermaidDiagramType.FLOWCHART,
            title="Test",
            nodes=[
                DiagramNode(id="A", label="Start", shape="round"),
                DiagramNode(id="B", label="End", shape="round"),
            ],
            edges=[
                DiagramEdge(from_node="A", to_node="B"),
            ],
        )

        rendered, is_valid, msg = renderer.render_diagram_with_validation(plan)
        assert rendered is not None
        assert is_valid is True
        assert msg == "Valid"

    def test_render_diagram_block(self):
        """Test rendering as complete Markdown block."""
        renderer = create_renderer()
        plan = DiagramPlan(
            diagram_id="test",
            diagram_type=MermaidDiagramType.FLOWCHART,
            title="Test",
            nodes=[
                DiagramNode(id="A", label="Start", shape="round"),
            ],
            edges=[],
        )

        result = renderer.render_diagram_block(plan)
        assert result.startswith("```mermaid")
        assert result.endswith("```")
        assert "flowchart TD" in result


class TestPlanAndRenderDiagram:
    """Tests for plan_and_render_diagram convenience function."""

    def test_plan_and_render_overview(self):
        """Test planning and rendering for overview page."""
        rendered, is_valid, msg = plan_and_render_diagram(
            page_id="overview",
            page_type="overview",
            evidence_binding=None,
            context={
                "modules": [{"name": "auth", "path": "src/auth"}]
            },
        )

        assert rendered is not None
        assert is_valid is True
        assert "flowchart TD" in rendered

    def test_plan_and_render_api(self):
        """Test planning and rendering for API page."""
        rendered, is_valid, msg = plan_and_render_diagram(
            page_id="api-ref",
            page_type="api",
            evidence_binding=None,
            context={
                "endpoints": [
                    {"path": "/api/users", "method": "GET", "service": "users"}
                ]
            },
        )

        assert rendered is not None
        assert is_valid is True
        assert "sequenceDiagram" in rendered


class TestLinkDiagramToEvidence:
    """Tests for link_diagram_to_evidence function."""

    def test_link_diagram_to_evidence(self):
        """Test linking diagram to evidence spans."""
        plan = DiagramPlan(
            diagram_id="test",
            diagram_type=MermaidDiagramType.FLOWCHART,
            title="Test",
            nodes=[],
            edges=[],
        )

        span = EvidenceSpanRecord(
            digest="abc123",
            file_path="src/auth.py",
            line_start=10,
            line_end=20,
            language="python",
            symbol="AuthService",
            span_text="class AuthService:",
        )
        candidate = EvidenceCandidate(
            evidence_id=1,
            span=span,
            score=1.0,
            match_signals=["module_match"],
            citation_order=0,
        )
        binding = PageEvidenceBinding(
            page_id="test",
            doc_type="test",
            candidates=[candidate],
        )

        result = link_diagram_to_evidence(plan, binding)
        assert len(result.evidence_spans) == 1
        assert result.evidence_spans[0].file_path == "src/auth.py"

    def test_link_diagram_with_no_evidence(self):
        """Test linking with no evidence binding returns unchanged plan."""
        plan = DiagramPlan(
            diagram_id="test",
            diagram_type=MermaidDiagramType.FLOWCHART,
            title="Test",
            nodes=[],
            edges=[],
        )

        result = link_diagram_to_evidence(plan, None)
        assert result is plan
        assert len(result.evidence_spans) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
