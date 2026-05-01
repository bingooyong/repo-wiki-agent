# Phase 25 - API Reference Specialization

## Task 25.1

```markdown
---
task_ref: "Task 25.1 - API inventory enrichment"
agent_assignment: "Agent_Scanner"
memory_log_path: ".apm/Memory/Phase_25_API_Reference_Specialization/Task_25_1_API_inventory_enrichment.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: API inventory enrichment

## Task Reference
Implementation Plan: **Task 25.1 - API inventory enrichment** assigned to **Agent_Scanner**

## Context from Dependencies
Read `docs/phases/Phase_25_API_Reference_Specialization.md` and Phase 24 composer contracts.

## Objective
Enrich API inventory with service, handler, auth, request, and response metadata.

## Detailed Instructions
- Extract controller/router/handler locations across Java, Python, and TypeScript fixtures.
- Infer service ownership, auth sources, request/response models, and error handling references.
- Preserve handler file/line citations for later pages.

## Expected Output
- Deliverables: enriched API scanner, contracts, fixtures, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_api_inventory.py tests/test_scanner.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_25_API_Reference_Specialization/Task_25_1_API_inventory_enrichment.md`
```

## Task 25.2

```markdown
---
task_ref: "Task 25.2 - API topic planner"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_25_API_Reference_Specialization/Task_25_2_API_topic_planner.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: API topic planner

## Task Reference
Implementation Plan: **Task 25.2 - API topic planner** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 25.1 by Agent_Scanner and Task 22.6. Use enriched API metadata and planner persistence.

## Objective
Plan API-specific Wiki pages by service family and topic.

## Detailed Instructions
- Plan API参考、核心服务API、Python服务API、认证授权API、错误处理 pages.
- Generate at least 15 AI_API_Atlas API planned pages.
- Group by service family/topic, not raw endpoint count.

## Expected Output
- Deliverables: API topic planner, fixture expectations, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_api_topic_planner.py tests/test_rule_first_planner.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_25_API_Reference_Specialization/Task_25_2_API_topic_planner.md`
```

## Task 25.3

```markdown
---
task_ref: "Task 25.3 - Service-family API composer"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_25_API_Reference_Specialization/Task_25_3_Service_family_API_composer.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Service-family API composer

## Task Reference
Implementation Plan: **Task 25.3 - Service-family API composer** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 25.2 and Task 24.3. Use API page plans and composer pipeline.

## Objective
Generate prose-first API articles by service family.

## Detailed Instructions
- Explain service purpose, core flows, representative endpoints, auth, and error behavior.
- Keep endpoint tables bounded and secondary.
- Include citations for handlers, schemas, and call sites.

## Expected Output
- Deliverables: service-family API composer and tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_service_family_api_composer.py tests/test_llm_page_composer.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_25_API_Reference_Specialization/Task_25_3_Service_family_API_composer.md`
```

## Task 25.4

```markdown
---
task_ref: "Task 25.4 - Auth and error convention generator"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_25_API_Reference_Specialization/Task_25_4_Auth_and_error_convention_generator.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Auth and error convention generator

## Task Reference
Implementation Plan: **Task 25.4 - Auth and error convention generator** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 25.3. Reuse enriched API metadata and source citations.

## Objective
Generate authentication, authorization, error code, and status code topic pages.

## Detailed Instructions
- Cite configuration, middleware, controller, and frontend/backend client files.
- Explain common request patterns and failure modes.
- Document missing-evidence behavior instead of inventing conventions.

## Expected Output
- Deliverables: auth/error convention generator, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_auth_error_generator.py tests/test_service_family_api_composer.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_25_API_Reference_Specialization/Task_25_4_Auth_and_error_convention_generator.md`
```

## Task 25.5

```markdown
---
task_ref: "Task 25.5 - API flow diagram generation"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_25_API_Reference_Specialization/Task_25_5_API_flow_diagram_generation.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: API flow diagram generation

## Task Reference
Implementation Plan: **Task 25.5 - API flow diagram generation** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 25.4 and Task 24.4. Use diagram planner and API flow evidence.

## Objective
Generate sequence diagrams for core API service families.

## Detailed Instructions
- Generate at least one sequence diagram per core API service family where evidence exists.
- Cite handlers and downstream calls used in diagrams.
- Validate Mermaid syntax before writing output.

## Expected Output
- Deliverables: API flow diagram generator, Mermaid tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_api_flow_diagrams.py tests/test_mermaid_planner.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_25_API_Reference_Specialization/Task_25_5_API_flow_diagram_generation.md`
```

## Task 25.6

```markdown
---
task_ref: "Task 25.6 - API quality verifier"
agent_assignment: "Agent_AdapterGovernance"
memory_log_path: ".apm/Memory/Phase_25_API_Reference_Specialization/Task_25_6_API_quality_verifier.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: API quality verifier

## Task Reference
Implementation Plan: **Task 25.6 - API quality verifier** assigned to **Agent_AdapterGovernance**

## Context from Dependencies
Depends on Task 25.5 by Agent_DocGen. Read generated API article contracts and flow diagram outputs.

## Objective
Enforce API aggregation quality for qoder-like output.

## Detailed Instructions
- Detect endpoint-dump pages, missing service-family grouping, missing auth/error coverage, and missing citations.
- Fail endpoint dump regressions in strict profile.
- Add quality gate tests.

## Expected Output
- Deliverables: API quality gates, reason codes, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_api_quality_verifier.py tests/test_verifier.py`
- Completion rule: do not mark complete unless compile and self-test pass.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_25_API_Reference_Specialization/Task_25_6_API_quality_verifier.md`
```

