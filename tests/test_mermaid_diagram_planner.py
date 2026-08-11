"""Compatibility test entry for Mermaid diagram planner suite.

Task 38.2 expects pytest target `tests/test_mermaid_diagram_planner.py`.
Keep this file as a focused smoke/contract suite.
"""

from __future__ import annotations

from repo_wiki.generator.mermaid_planner import MermaidDiagramType, create_planner, create_renderer


def test_api_diagram_contract_produces_sequence_and_flowchart() -> None:
    planner = create_planner()
    diagrams = planner.plan_diagram_for_page(
        page_id="inventory-service-api-reference",
        page_type="api",
        evidence_binding=None,
        context={
            "endpoints": [
                {"path": "/endpoints", "method": "GET", "service": "inventory-service"},
                {"path": "/endpoints/count", "method": "GET", "service": "inventory-service"},
            ]
        },
    )
    kinds = {d.diagram_type for d in diagrams}
    assert MermaidDiagramType.SEQUENCE_DIAGRAM in kinds
    assert MermaidDiagramType.FLOWCHART in kinds


def test_api_contract_diagrams_are_mermaid_renderable() -> None:
    planner = create_planner()
    renderer = create_renderer()
    diagrams = planner.plan_diagram_for_page(
        page_id="inventory-service-api-reference",
        page_type="api",
        evidence_binding=None,
        context={
            "endpoints": [
                {"path": "/endpoints/{id}", "method": "GET", "service": "inventory-service"}
            ]
        },
    )
    rendered = [renderer.render_diagram_with_validation(plan) for plan in diagrams]
    assert rendered
    assert any(ok for _, ok, _ in rendered)
