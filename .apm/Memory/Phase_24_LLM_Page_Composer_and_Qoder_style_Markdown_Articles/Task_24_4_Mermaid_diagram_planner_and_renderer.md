---
task_ref: "Task 24.4 - Mermaid diagram planner and renderer"
status: "completed"
important_findings: false
compatibility_issue: false
compatibility_issues: false
---

# Task 24.4 - Mermaid diagram planner and renderer

## 任务状态
已完成

## 任务参考
- Task Assignment: `.apm/Task_Assignments/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles.md`
- Phase Document: `docs/phases/Phase_24_LLM_Page_Composer_and_Qoder_style_Markdown_Articles.md`

## 上下文依赖
- Task 24.3 (LLM page composer pipeline)
- Task 23.4 (Evidence builder with file and line citations)

## 目标
Plan and render Mermaid diagrams for suitable Wiki pages.

## 交付物

### 1. Diagram Planner (`repo_wiki/generator/mermaid_planner.py`)
- `MermaidDiagramType` enum: FLOWCHART, SEQUENCE_DIAGRAM, ER_DIAGRAM, CLASS_DIAGRAM, STATE_DIAGRAM, JOURNEY_DIAGRAM
- `DiagramPlan` dataclass: Plan for a diagram with evidence backing
- `DiagramNode`, `DiagramEdge` dataclasses: Graph components
- `MermaidPlanner` class: Decides diagram type based on page type and evidence
- `PAGE_TYPE_TO_DIAGRAM_PREFERENCE` mapping: Defines which diagram types suit each page type

### 2. Renderer (`repo_wiki/generator/mermaid_planner.py`)
- `MermaidRenderer` class: Renders DiagramPlan to valid Mermaid syntax
- `render_diagram()`: Renders based on diagram type
- `render_diagram_block()`: Renders complete Markdown code block with ```mermaid wrapper
- `render_diagram_with_validation()`: Render and validate syntax

### 3. Syntax Validator (`repo_wiki/generator/mermaid_planner.py`)
- `validate_mermaid_syntax()`: Validates Mermaid syntax before writing pages
- `MermaidSyntaxError` exception
- Type-specific validators: `_validate_flowchart_syntax()`, `_validate_sequence_syntax()`, `_validate_er_syntax()`, `_validate_class_syntax()`, `_validate_state_syntax()`

### 4. Source Mapping (`repo_wiki/generator/mermaid_planner.py`)
- `DiagramPlan.evidence_spans`: Links diagrams to source evidence
- `link_diagram_to_evidence()`: Associates diagram plans with evidence bindings
- `CitationRenderer.render_diagram_source()`: Already existed for diagram provenance

### 5. Tests (`tests/test_mermaid_planner.py`)
- `TestMermaidDiagramType`: Diagram type enum tests
- `TestDiagramNode`, `TestDiagramEdge`, `TestDiagramPlan`: Data structure tests
- `TestValidateMermaidSyntax`: Syntax validation tests
- `TestMermaidPlanner`: Planner tests for all page types
- `TestMermaidRenderer`: Renderer tests
- `TestPlanAndRenderDiagram`: Integration tests
- `TestLinkDiagramToEvidence`: Evidence linking tests

## 设计与实现

### 架构决策
1. **Diagram Type Selection**: 根据页面类型自动选择最合适的图表类型
   - overview/architecture: flowchart
   - service/section: flowchart 或 sequence
   - api: sequenceDiagram
   - data/entity: erDiagram
   - ops: flowchart

2. **Syntax Validation**: 写入前验证，发现问题降级为文字说明

3. **Evidence Linking**: 图表通过 evidence_spans 追踪来源

### 页面类型到图表类型的映射
```python
PAGE_TYPE_TO_DIAGRAM_PREFERENCE = {
    "overview": [FLOWCHART, STATE_DIAGRAM],
    "architecture": [FLOWCHART, CLASS_DIAGRAM],
    "section": [FLOWCHART, STATE_DIAGRAM],
    "service": [SEQUENCE_DIAGRAM, FLOWCHART],
    "api": [SEQUENCE_DIAGRAM, FLOWCHART],
    "data": [ER_DIAGRAM, CLASS_DIAGRAM],
    "entity": [ER_DIAGRAM, CLASS_DIAGRAM],
    "ops": [FLOWCHART, STATE_DIAGRAM],
    "development": [FLOWCHART, JOURNEY_DIAGRAM],
}
```

## 自测结果
```
62 passed in 0.20s
```

## 编译验证
```
uv run repo-wiki --help
```
成功执行，命令正常可用。

## 关键文件
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/generator/mermaid_planner.py` - 核心模块
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/tests/test_mermaid_planner.py` - 测试文件

## 后续依赖
- Task 24.5: Quality guardrails for hallucination and generic prose (依赖本任务)
