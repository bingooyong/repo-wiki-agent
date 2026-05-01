# Task 25.5 - API flow diagram generation

## Task Reference
Phase 25 - Task 25.5: API flow diagram generation assigned to Agent_DocGen

## Context Dependencies
- Task 25.4: Auth and error convention generator
- Task 24.4: Mermaid diagram planner and renderer

## Objective
Generate sequence diagrams for core API service families with handler citations and downstream calls.

## Deliverables

### 1. API Flow Diagram Generator (repo_wiki/generator/api_flow_diagram.py)

**Key Classes:**
- `APIFlowEvidence`: Dataclass for evidence backing API flow diagrams (handler_file, handler_line, handler_symbol, downstream_calls)
- `APIFlowDiagram`: Dataclass combining diagram plan with evidence backing
- `APIFlowDiagramGenerator`: Main generator class that creates sequence diagrams for API service families
- `SpecializedAPIFlowGenerator`: Generates specialized diagrams for auth and health check flows

**Key Features:**
- Uses existing MermaidPlanner and MermaidRenderer from Task 24.4
- Extracts service family from page IDs (e.g., api-python-backend -> python-backend)
- Filters endpoints by source requirements or service family
- Collects handler citations (file path, line number, symbol name)
- Validates Mermaid syntax before rendering

**Factory Functions:**
- create_api_flow_diagram_generator(): Creates standard API flow diagram generator
- create_specialized_flow_generator(): Creates specialized generator for auth/health flows

### 2. Tests (tests/test_api_flow_diagrams.py)

**Test Coverage:**
- TestAPIFlowEvidence: APIFlowEvidence dataclass creation
- TestServiceFamilyExtraction: Service family extraction from page IDs
- TestEndpointFiltering: Endpoint filtering by source requirements and service family
- TestFlowDiagramGeneration: Flow diagram generation with evidence backing
- TestMultipleDiagramGeneration: Multiple diagram generation for service families
- TestSpecializedFlowGenerator: Auth and health check flow diagram generation
- TestConvenienceFunctions: Convenience function tests
- TestMarkdownRendering: Markdown rendering of flow diagrams
- TestCitationsAndEvidence: Handler citation tests
- TestEdgeCases: Edge case handling

## Validation Results

**Compilation:** uv run repo-wiki --help - PASSED

**Self-Test:** uv run pytest tests/test_api_flow_diagrams.py tests/test_mermaid_planner.py
- 64 tests passed
- All API flow diagram tests passed
- All Mermaid planner tests passed

## Implementation Notes

1. **Diagram Planning Integration**: The generator delegates diagram planning to MermaidPlanner.plan_diagram_for_page() which determines appropriate diagram types based on page type (api -> sequenceDiagram).

2. **Evidence Collection**: Handler evidence is collected from Endpoint objects which contain:
   - file_path: Handler file path
   - line_number: Handler line citation (1-based)
   - handler: Handler symbol name

3. **Service Family Extraction**: Common prefixes like auth, authentication, error, health, core, data, admin, status, convention are skipped when extracting service family from page ID.

4. **Mermaid Validation**: Syntax validation is performed using validate_mermaid_syntax() from the mermaid_planner module before setting rendered_diagram.

## Memory Log
Logged: 2026/04/26
