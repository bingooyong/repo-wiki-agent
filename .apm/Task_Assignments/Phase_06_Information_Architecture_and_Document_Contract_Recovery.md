# Phase 06 – Information Architecture and Document Contract Recovery

## Task 6.1

```markdown
---
task_ref: "Task 6.1 - Document output contract refactor and document-center layer"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_1_Document_output_contract_refactor_and_document_center_layer.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Document output contract refactor and document-center layer

## Task Reference
Implementation Plan: **Task 6.1 - Document output contract refactor and document-center layer** assigned to **Agent_DocGen**

## Context from Dependencies
Build directly on your Task 3.1 document-contract baseline.

- Read `.apm/Memory/Phase_03_Documentation_Generation_and_Command_Orchestration/Task_3_1_Template_system_and_document_contracts.md` and reuse the existing contract registry, template coverage logic, and deterministic rendering assumptions.
- Read `docs/qoder-repo-wiki-design-analysis.md`, `docs/repo-wiki-qoder-gap-task-plan.md`, and `docs/phases/Phase_06_Information_Architecture_and_Document_Contract_Recovery.md` before changing any contract shape.
- Treat this task as an additive contract expansion. Do not break existing `docs/00~05` or `docs/modules/**` outputs while introducing `docs/sections/**` and `docs/phases/**`.

## Objective
Refactor the document output contract so repo-wiki produces a document center rather than only a flat export set.

## Detailed Instructions
- Complete all items in one response.
- Extend the current document contract model to distinguish overview docs, section docs, module docs, and phase docs.
- Introduce `docs/sections/` as the section layer between overview docs and module docs.
- Introduce `docs/phases/` as the reader-facing stage-governance layer.
- Define stable naming rules, path rules, and write-domain boundaries for overview, section, module, and phase outputs.
- Update template or contract registries so generation can validate the new outputs before render time.
- Add validation coverage proving the new contracts are additive and do not break the existing MVP doc set.
- Keep command surface unchanged; this task only expands output contracts and generation prerequisites.

## Expected Output
- Deliverables: updated document contracts, `docs/sections/**` and `docs/phases/**` output definitions, validation hooks, and write-domain rules.
- Success criteria: the generator now understands four document layers and can validate required section/phase contracts without removing existing MVP outputs.
- File locations: `repo_wiki/generator/**`, `templates/**`, contract or validation helpers, and any tests needed to enforce the new structure.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_1_Document_output_contract_refactor_and_document_center_layer.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 6.2

```markdown
---
task_ref: "Task 6.2 - Business-domain classifier and module mapping contracts"
agent_assignment: "Agent_Scanner"
memory_log_path: ".apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_2_Business_domain_classifier_and_module_mapping_contracts.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Business-domain classifier and module mapping contracts

## Task Reference
Implementation Plan: **Task 6.2 - Business-domain classifier and module mapping contracts** assigned to **Agent_Scanner**

## Context from Dependencies
This task depends on Task 6.1 implemented by Agent_DocGen.

**Integration Steps (complete in one response):**
1. Read `docs/phases/Phase_06_Information_Architecture_and_Document_Contract_Recovery.md` to understand the stage goals and the role of domain metadata in the new document-center model.
2. Read `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_1_Document_output_contract_refactor_and_document_center_layer.md` to identify the exact contract additions and write-domain boundaries introduced in Task 6.1.
3. Review the implementation files referenced in that log before extending scanner normalization or `module-index` output.
4. Adapt to the contract model created in Task 6.1 rather than inventing a parallel classifier output path.

**Producer Output Summary:**
- Task 6.1 defines the new overview/section/module/phase document layers and the structural contract that later generation tasks will consume.
- The new section and phase layers require stable domain metadata so documents can group modules semantically rather than by directory layout.

**Integration Requirements:**
- Extend normalized module outputs with at least `domain`, `service_family`, and `runtime_role`.
- Update `module-index.yaml` writing and validation without breaking existing consumers.
- Keep classification deterministic with a documented fallback for ambiguous modules.

**User Clarification Protocol:**
If Task 6.1 did not define stable contract hooks or phase/section output names, stop and ask whether the contract task should be refined before scanner changes proceed.

## Objective
Add semantic grouping metadata so modules can be organized by business domain instead of only by physical directory.

## Detailed Instructions
- Complete all items in one response.
- Define a deterministic business-domain classification strategy using module path, commands, frameworks, interfaces, data models, and ownership cues.
- Extend normalized module outputs with `domain`, `service_family`, and `runtime_role` metadata.
- Implement fallback behavior so every module still maps to a stable higher-level grouping when signals are weak.
- Update `module-index.yaml` writing logic and schema validation to include the new metadata.
- Emit diagnostics that explain low-confidence or fallback classifications.
- Add fixture coverage for mixed repositories with multiple service families and support modules.

## Expected Output
- Deliverables: domain classifier, module-to-domain mapping outputs, fallback rules, `module-index` contract extensions, and tests.
- Success criteria: every module maps to a stable higher-level grouping and the new fields are persisted without breaking the existing scanner contract.
- File locations: `repo_wiki/scanner/**`, `ai/source-of-truth/module-index.yaml` generation paths, and related tests or fixtures.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_2_Business_domain_classifier_and_module_mapping_contracts.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 6.3

```markdown
---
task_ref: "Task 6.3 - Prose-first overview contract and generation upgrade"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_3_Prose_first_overview_contract_and_generation_upgrade.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Prose-first overview contract and generation upgrade

## Task Reference
Implementation Plan: **Task 6.3 - Prose-first overview contract and generation upgrade** assigned to **Agent_DocGen**

## Context from Dependencies
This task depends on Task 6.1 and Task 6.2.

**Integration Steps (complete in one response):**
1. Read `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_1_Document_output_contract_refactor_and_document_center_layer.md` to confirm the exact overview/section/module/phase contract layout introduced in Task 6.1.
2. Read `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_2_Business_domain_classifier_and_module_mapping_contracts.md` to identify the new domain, service-family, and runtime-role metadata made available by Agent_Scanner.
3. Review the implementation files referenced in both logs before changing overview generation logic.
4. Read `docs/phases/Phase_06_Information_Architecture_and_Document_Contract_Recovery.md` and keep the overview page aligned with the stage goal of restoring a document-center entry page.

**Producer Output Summary:**
- Task 6.1 provides the expanded document contract and the new section-layer expectations.
- Task 6.2 provides the semantic grouping metadata that lets overview content explain the repository by domain rather than raw directory layout.

**Integration Requirements:**
- Redefine `docs/00-overview.md` around the fixed sections `项目定位`, `核心问题`, `核心能力`, `快速开始`, and `阅读导航`.
- Use domain groupings and section links to build navigation, not just repo stats.
- Add minimum prose and section-count validation so list-only outputs fail quality checks.

**User Clarification Protocol:**
If Task 6.2 does not expose stable domain metadata or Task 6.1 leaves overview contract names ambiguous, stop and ask whether the upstream tasks should be refined first.

## Objective
Recover `docs/00-overview.md` from a flat summary into a true introduction page for humans and agents.

## Detailed Instructions
- Complete all items in one response.
- Redefine the `00-overview.md` contract to require the fixed sections `项目定位`, `核心问题`, `核心能力`, `快速开始`, and `阅读导航`.
- Generate paragraph-first content using repository metadata, commands, domain groupings, and links into `docs/sections/**` and `docs/modules/**`.
- Keep navigation explicit so readers understand what to read next and why.
- Add minimum prose and section-count validation that rejects empty, list-only, or stats-only overview pages.
- Update generation tests or contract coverage to enforce these new requirements.

## Expected Output
- Deliverables: new overview contract, updated generation logic, prose-first overview template, and coverage tests.
- Success criteria: `docs/00-overview.md` becomes an introduction page with stable sections and real narrative content rather than a flat inventory.
- File locations: `repo_wiki/generator/**`, `templates/docs/00-overview.md.j2`, validation hooks, and related tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_3_Prose_first_overview_contract_and_generation_upgrade.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```

## Task 6.4

```markdown
---
task_ref: "Task 6.4 - Architecture contract recovery and three-layer Mermaid design"
agent_assignment: "Agent_DocGen"
memory_log_path: ".apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_4_Architecture_contract_recovery_and_three_layer_Mermaid_design.md"
execution_type: "single-step"
dependency_context: true
ad_hoc_delegation: false
---

# APM Task Assignment: Architecture contract recovery and three-layer Mermaid design

## Task Reference
Implementation Plan: **Task 6.4 - Architecture contract recovery and three-layer Mermaid design** assigned to **Agent_DocGen**

## Context from Dependencies
This task depends on Task 6.1, Task 6.2, and Task 6.3.

**Integration Steps (complete in one response):**
1. Read `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_1_Document_output_contract_refactor_and_document_center_layer.md` to confirm the new document-layer model.
2. Read `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_2_Business_domain_classifier_and_module_mapping_contracts.md` to identify the domain and service metadata that should appear in the architecture story.
3. Read `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_3_Prose_first_overview_contract_and_generation_upgrade.md` to keep architecture and overview aligned rather than creating a second disconnected intro page.
4. Review `docs/phases/Phase_06_Information_Architecture_and_Document_Contract_Recovery.md` and keep the architecture page centered on the three-layer model: `.repo-wiki`, `ai/source-of-truth`, and `docs`.

**Producer Output Summary:**
- Task 6.1 defines the document-center structure.
- Task 6.2 defines the semantic grouping metadata that helps explain system organization.
- Task 6.3 restores the overview page as the introduction and sets the tone for reader-facing narrative content.

**Integration Requirements:**
- Redefine `docs/01-architecture.md` around the fixed sections `系统分层`, `服务协作关系`, `核心数据流`, `存储与检索设计`, and `增量更新与治理闭环`.
- Include Mermaid as a required contract element, not an optional embellishment.
- Explicitly explain the relationship between runtime storage, source-of-truth artifacts, and human-readable docs.

**User Clarification Protocol:**
If overview or domain metadata is still unstable after reviewing the upstream logs, stop and ask whether Task 6.2 or 6.3 should be refined first.

## Objective
Rewrite `docs/01-architecture.md` as a real system-design document that explains the repo-wiki storage and reading model.

## Detailed Instructions
- Complete all items in one response.
- Redefine the `01-architecture.md` contract to require the fixed sections `系统分层`, `服务协作关系`, `核心数据流`, `存储与检索设计`, and `增量更新与治理闭环`.
- Add Mermaid generation rules for the three-layer architecture and the document-center flow.
- Use retrieval, graph, and artifact-layer signals to explain how `.repo-wiki`, `ai/source-of-truth`, and `docs` interact.
- Add validation that rejects architecture outputs missing Mermaid or the three-layer explanation.
- Keep the page focused on design reasoning instead of raw module or API enumeration.

## Expected Output
- Deliverables: new architecture contract, Mermaid-backed architecture template, generation logic, and coverage tests.
- Success criteria: `docs/01-architecture.md` becomes a true design document with Mermaid and explicit three-layer explanation.
- File locations: `repo_wiki/generator/**`, `templates/docs/01-architecture.md.j2`, validation helpers, and related tests.

## Memory Logging
Upon completion, you **MUST** log work in: `.apm/Memory/Phase_06_Information_Architecture_and_Document_Contract_Recovery/Task_6_4_Architecture_contract_recovery_and_three_layer_Mermaid_design.md`
Follow `.apm/guides/Memory_Log_Guide.md` instructions.

## Reporting Protocol
After logging, you **MUST** output a **Final Task Report** code block.
- **Format:** Use the exact template provided in your `.claude/commands/apm-3-initiate-implementation.md` instructions.
- **Perspective:** Write it from the User's perspective so they can copy-paste it back to the Manager.
```
