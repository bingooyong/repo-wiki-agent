# Phase 07 – Domain-Centered Content Generation

## Task 7.1

```markdown
---
task_ref: "Task 7.1 - Domain-centered module map generation"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_1_Domain_centered_module_map_generation.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Domain-centered module map generation

## Task Reference
Implementation Plan: **Task 7.1 - Domain-centered module map generation** assigned to **Agent_DocGen**

## Context from Dependencies
This task depends on Task 6.2 and Task 6.4.

**Integration Steps (complete in one response):**
1. Read `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_2_Business_domain_classifier_and_module_mapping_contracts.md` to identify the exact domain/service/runtime metadata exposed by Agent_Scanner.
2. Read `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_4_Architecture_contract_recovery_and_three_layer_Mermaid_design.md` to keep the module-map page aligned with the new document-center and architecture narrative.
3. Review `docs/phases/Phase_07_Domain_Centered_Content_Generation.md` before changing the module-map contract or generation logic.
4. Reuse the domain metadata and new contract layers rather than falling back to directory-based grouping.

**Producer Output Summary:**
- Task 6.2 provides the semantic grouping metadata needed for domain maps.
- Task 6.4 provides the upgraded architecture framing and document-center expectations that the module map should reinforce.

**Integration Requirements:**
- Organize `03-module-map.md` by domain, service family, and runtime role.
- Show responsibilities and relationships within each domain group.
- Link domain groups to section docs and module docs instead of leaving them as isolated headings.

**User Clarification Protocol:**
If domain metadata is incomplete or the architecture contract is still unstable, stop and ask whether Phase 06 outputs should be refined before module-map generation proceeds.

## Objective
Replace the flat module list with a domain map that reflects how readers should understand the repository.

## Detailed Instructions
- Complete all items in one response.
- Redefine `03-module-map.md` to organize modules by business domain, service family, and runtime role.
- Show module responsibilities, upstream/downstream relationships, and entry docs within each domain group.
- Require at least three top-level domain groups when the repository has enough modules to support them.
- Add navigation links to related section pages and module docs.
- Add validation that rejects directory-flat output when domain metadata is available.

## Expected Output
- Deliverables: updated `03-module-map.md` contract, domain-grouped generation logic, navigation links, and tests.
- Success criteria: the module map becomes a domain-oriented reader aid instead of a directory mirror.
- File locations: `repo_wiki/generator/**`, `templates/docs/03-module-map.md.j2`, validation helpers, and related tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_1_Domain_centered_module_map_generation.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 7.2

```markdown
---
task_ref: "Task 7.2 - Aggregated API contracts generation"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_2_Aggregated_API_contracts_generation.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Aggregated API contracts generation

## Task Reference
Implementation Plan: **Task 7.2 - Aggregated API contracts generation** assigned to **Agent_DocGen**

## Context from Dependencies
Build directly on the Phase 06 domain and architecture outputs.

- Read `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_2_Business_domain_classifier_and_module_mapping_contracts.md` to reuse the new grouping metadata when aggregating API surfaces.
- Read `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_4_Architecture_contract_recovery_and_three_layer_Mermaid_design.md` to align API organization with the document-center narrative.
- Read `docs/phases/Phase_07_Domain_Centered_Content_Generation.md` before redesigning the API overview.
- Keep this page as an aggregated overview; detailed endpoint facts remain available in `ai/source-of-truth/api-index.yaml` and module docs.

## Objective
Rebuild `04-api-contracts.md` around service and usage groups instead of a raw endpoint dump.

## Detailed Instructions
- Complete all items in one response.
- Group APIs by service family, domain theme, and authentication or gateway pattern.
- Add fixed sections for `服务/API 分组` and `调用约定`.
- Summarize authentication, error/status behavior, and key entry APIs instead of rendering every endpoint verbatim.
- Preserve links to lower-level source-of-truth or module docs where deeper detail is needed.
- Add validation that rejects unbounded raw endpoint lists as overview content.

## Expected Output
- Deliverables: API grouping rules, updated API contracts template, call-convention summary, and tests.
- Success criteria: `04-api-contracts.md` becomes a reader-oriented API overview rather than a raw endpoint export.
- File locations: `repo_wiki/generator/**`, `templates/docs/04-api-contracts.md.j2`, validation helpers, and related tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_2_Aggregated_API_contracts_generation.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 7.3

```markdown
---
task_ref: "Task 7.3 - Domain-aggregated data model generation"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_3_Domain_aggregated_data_model_generation.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Domain-aggregated data model generation

## Task Reference
Implementation Plan: **Task 7.3 - Domain-aggregated data model generation** assigned to **Agent_DocGen**

## Context from Dependencies
Build directly on the Phase 06 domain and architecture outputs.

- Read `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_2_Business_domain_classifier_and_module_mapping_contracts.md` to reuse domain and service-family groupings for data-model aggregation.
- Read `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_4_Architecture_contract_recovery_and_three_layer_Mermaid_design.md` so the data-model page aligns with the storage narrative in architecture.
- Read `docs/phases/Phase_07_Domain_Centered_Content_Generation.md` before redesigning the data-model overview.
- Treat `ai/source-of-truth/data-models.yaml` as the detail layer; this page must remain an aggregated summary.

## Objective
Rebuild `05-data-model.md` so it highlights core domain entities and storage strategy instead of dumping every model symbol.

## Detailed Instructions
- Complete all items in one response.
- Group models into `核心数据模型`, `服务数据模型`, and `数据库/迁移策略`.
- Deduplicate low-signal repeated types and surface the core entities that define repository behavior.
- Summarize database shape, migration strategy, and notable cross-module data boundaries.
- Link aggregated sections back to source-of-truth artifacts and detailed module docs where needed.
- Add validation that flags model-dump outputs with no aggregation or migration summary.

## Expected Output
- Deliverables: data-model grouping rules, deduplication logic, updated template, and tests.
- Success criteria: `05-data-model.md` becomes a domain-oriented data summary rather than a symbol inventory.
- File locations: `repo_wiki/generator/**`, `templates/docs/05-data-model.md.j2`, validation helpers, and related tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_3_Domain_aggregated_data_model_generation.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 7.4

```markdown
---
task_ref: "Task 7.4 - Section page generation and navigation stitching"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_4_Section_page_generation_and_navigation_stitching.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Section page generation and navigation stitching

## Task Reference
Implementation Plan: **Task 7.4 - Section page generation and navigation stitching** assigned to **Agent_DocGen**

## Context from Dependencies
Build directly on your Task 7.1, Task 7.2, and Task 7.3 outputs.

- Read `.apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_1_Domain_centered_module_map_generation.md`, `.apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_2_Aggregated_API_contracts_generation.md`, and `.apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_3_Domain_aggregated_data_model_generation.md`.
- Reuse the domain groups, API groupings, and data-model aggregations already introduced.
- Read `docs/phases/Phase_07_Domain_Centered_Content_Generation.md` and keep section pages focused on navigation and reader orientation.
- Do not duplicate overview or module pages verbatim; section pages should bridge the two.

## Objective
Generate the section-layer pages that make the repo-wiki output behave like a document center.

## Detailed Instructions
- Complete all items in one response.
- Generate at minimum the section pages for `project`, `architecture`, `services`, `data-model`, `api`, `operations`, `development`, and `security`.
- Ensure section pages link to overview docs, related section pages, and relevant module docs.
- Provide stable directory naming and index-style navigation so adapter files can point readers into the document center.
- Add validation that section pages exist and cross-link correctly when the repository meets the minimum data threshold.
- Keep content aggregated and reader-oriented rather than duplicating lower-level docs verbatim.

## Expected Output
- Deliverables: section templates, section generation logic, navigation stitching, and coverage tests.
- Success criteria: the repo-wiki output now includes a stable section layer with cross-links into overview and module docs.
- File locations: `repo_wiki/generator/**`, `templates/**`, `docs/sections/**`, and related tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_07_Domain_Centered_Content_Generation/Task_7_4_Section_page_generation_and_navigation_stitching.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```
