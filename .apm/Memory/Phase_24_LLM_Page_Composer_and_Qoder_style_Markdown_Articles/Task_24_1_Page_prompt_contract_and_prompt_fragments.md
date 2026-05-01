---
task_ref: "Task 24.1 - Page prompt contract and prompt fragments"
status: "completed"
important_findings: false
compatibility_issue: false
compatibility_issues: false
---

## 交付物

### Prompt Contracts (repo_wiki/prompts/contracts.py)
- 定义了7种页面类型的prompt contract: overview, service, api, data, entity, ops, development
- 每个contract包含:
  - heading_structure: 标题结构要求
  - evidence: 证据和引用要求 (min_candidates, citation_style等)
  - style: 风格要求 (prose_density_min, max_list_ratio等)
  - anti_hallucination: 反幻觉规则 (cite_all_symbols, validate_file_paths等)
  - snapshot_test_pattern: 快照测试路径模式
  - secret_redaction_required: 是否需要secret脱敏

### Prompt Fragments (repo_wiki/prompts/fragments.py)
- SYSTEM_PROMPT_FRAGMENT: 系统级prompt
- OVERVIEW_PROMPT_FRAGMENT: 项目概览页prompt
- SERVICE_PROMPT_FRAGMENT: 服务/专题页prompt
- API_PROMPT_FRAGMENT: API参考页prompt
- DATA_PROMPT_FRAGMENT: 数据模型页prompt
- ENTITY_PROMPT_FRAGMENT: 实体页prompt
- OPS_PROMPT_FRAGMENT: 运维页prompt
- DEVELOPMENT_PROMPT_FRAGMENT: 开发指南页prompt
- get_prompt_fragment(name): 获取fragment的函数
- render_prompt_fragment(name, context): 渲染fragment的函数

### 快照测试 (tests/test_page_prompts.py)
- 76个测试全部通过
- 测试覆盖:
  - PagePromptType枚举
  - CitationStyle枚举
  - PagePromptContract实例
  - get_contract_for_page_type()
  - get_contract_for_doc_type()
  - Prompt fragments存在性和内容
  - get_prompt_fragment()
  - render_prompt_fragment()
  - Snapshot test patterns
  - Secret redaction
  - Evidence requirements
  - Anti-hallucination requirements
  - Heading structure

### 编译命令
`uv run repo-wiki --help` - 通过

### 自测命令
`uv run pytest tests/test_page_prompts.py tests/test_llm_config.py` - 76 passed