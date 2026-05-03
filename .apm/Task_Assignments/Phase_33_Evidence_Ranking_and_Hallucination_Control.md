# Phase 33 - Evidence Ranking and Hallucination Control

## Task 33.1

```markdown
---
task_ref: "Task 33.1 - Service ownership resolver"
agent_assignment: "Agent_Scanner"
memory_log_path: ".apm/Memory/Phase_33_Evidence_Ranking_and_Hallucination_Control/Task_33_1_Service_ownership_resolver.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Service ownership resolver

## Task Reference
Implementation Plan: **Task 33.1 - Service ownership resolver** assigned to **Agent_Scanner**

## Context from Dependencies
Depends on Task 32.4 and Task 23.3. Use the deepened page hierarchy and existing evidence ranking implementation. Treat current API台账服务 output that says `inventory-service` but cites `ai-service` as a required failing fixture.

## Objective
Resolve service ownership from repository structure, package metadata, runtime signals, and docs.

## Detailed Instructions
- Use module paths, package names, ports, build files, and README cues to determine service ownership.
- Force API台账服务/API inventory topics to resolve to `inventory-service` evidence such as `EndpointsController.java`, `ApiEndpointEntity.java`, and related repositories.
- Prevent GitLab, Jenkins, MCP, and inventory-service pages from binding unrelated `ai-service` evidence.
- Emit confidence and rejection reasons for ambiguous ownership.
- Add fixtures covering similarly named services and unrelated evidence.

## Expected Output
- Deliverables: service ownership resolver, inventory-service ownership fixture, confidence model, fixtures, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_service_ownership.py tests/test_evidence_ranking.py`
- Completion rule: do not mark complete unless wrong-service evidence fixtures fail before the fix and pass after it, including API台账服务 -> inventory-service.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_33_Evidence_Ranking_and_Hallucination_Control/Task_33_1_Service_ownership_resolver.md`
```

## Task 33.2

```markdown
---
task_ref: "Task 33.2 - Page evidence scoring"
agent_assignment: "Agent_IndexGraph"
memory_log_path: ".apm/Memory/Phase_33_Evidence_Ranking_and_Hallucination_Control/Task_33_2_Page_evidence_scoring.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Page evidence scoring

## Task Reference
Implementation Plan: **Task 33.2 - Page evidence scoring** assigned to **Agent_IndexGraph**

## Context from Dependencies
Depends on Task 33.1 by Agent_Scanner and Task 23.3. Read ownership resolver outputs before changing page evidence scoring.

## Objective
Score evidence by page title, service slug, domain, runtime role, API relation, and data-model relation.

## Detailed Instructions
- Combine title, slug, domain, runtime role, API, and data-model features into a relevance score.
- Store top-N evidence and rejected candidates with reasons.
- Prefer service-local evidence over generic shared modules unless the page topic requires shared infrastructure.
- Add tests for positive matches and false-positive rejection.

## Expected Output
- Deliverables: page evidence scoring model, top-N evidence, rejection reasons, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_evidence_ranking.py tests/test_citation_verifier.py`
- Completion rule: do not mark complete unless evidence rejection reasons are persisted or inspectable.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_33_Evidence_Ranking_and_Hallucination_Control/Task_33_2_Page_evidence_scoring.md`
```

## Task 33.3

```markdown
---
task_ref: "Task 33.3 - Citation relevance verifier"
agent_assignment: "Agent_AdapterGovernance"
memory_log_path: ".apm/Memory/Phase_33_Evidence_Ranking_and_Hallucination_Control/Task_33_3_Citation_relevance_verifier.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Citation relevance verifier

## Task Reference
Implementation Plan: **Task 33.3 - Citation relevance verifier** assigned to **Agent_AdapterGovernance**

## Context from Dependencies
Depends on Task 33.2 by Agent_IndexGraph and Task 29.3. Use scored evidence and strict verifier reason-code conventions.

## Objective
Add strict verification for page-title to citation relevance.

## Detailed Instructions
- Compare page title, service slug, and topic type against citation file paths and symbols.
- Fail high-confidence mismatches in strict profile.
- Warn on ambiguous but explainable shared-infrastructure citations.
- Add regression cases for wrong-service evidence binding.

## Expected Output
- Deliverables: citation relevance verifier, WARN/FAIL gates, reason codes, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_citation_verifier.py tests/test_qoder_like_verifier.py`
- Completion rule: do not mark complete unless citation relevance is part of strict qoder-like verification.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_33_Evidence_Ranking_and_Hallucination_Control/Task_33_3_Citation_relevance_verifier.md`
```

## Task 33.4

```markdown
---
task_ref: "Task 33.4 - Low-confidence fallback"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_33_Evidence_Ranking_and_Hallucination_Control/Task_33_4_Low_confidence_fallback.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Low-confidence fallback

## Task Reference
Implementation Plan: **Task 33.4 - Low-confidence fallback** assigned to **Agent_DocGen**

## Context from Dependencies
Depends on Task 33.3 and Task 24.5. Use citation relevance failures and existing hallucination guardrails.

## Objective
Replace unsupported implementation claims with explicit low-confidence sections.

## Detailed Instructions
- Generate `待确认` sections when evidence is insufficient.
- Prohibit fabricated implementation details in low-confidence pages.
- Ensure uncertainty text does not dominate otherwise well-evidenced pages.
- Add tests for insufficient-evidence composition.

## Expected Output
- Deliverables: low-confidence composer behavior, prompt updates, tests.
- Compile command: `uv run repo-wiki --help`
- Self-test command: `uv run pytest tests/test_llm_page_composer.py tests/test_quality_guardrails.py`
- Completion rule: do not mark complete unless insufficient evidence produces explicit uncertainty rather than unsupported claims.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_33_Evidence_Ranking_and_Hallucination_Control/Task_33_4_Low_confidence_fallback.md`
```
