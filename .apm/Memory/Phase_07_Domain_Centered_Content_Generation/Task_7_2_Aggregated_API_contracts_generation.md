---
agent: Agent_DocGen
task_ref: Task 7.2
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 7.2 - Aggregated API contracts generation

## Summary

成功将 `04-api-contracts.md` 模板从原始端点列表升级为按服务族和主题域聚合的 API 契约页面。添加了服务/API 分组、调用约定（认证、错误状态码）、关键入口 API 摘要等固定章节。

## Details

### 1. 重写 04-api-contracts.md.j2 模板

新模板包含以下固定章节：
- 服务/API 分组概览表格
- 分组详情（按模块和主题域组织）
- 调用约定（认证模式、错误与状态码）
- 关键入口 API
- 完整端点索引表格
- 阅读导航链接

### 2. 更新 API Contracts Contract Required Keys

扩展 `api_contracts` contract 的 `required_keys`：
- `repository_name` - 仓库名称
- `api_groups_table` - API 分组概览表格
- `api_groups_detail` - 详细 API 分组
- `authentication_patterns` - 认证模式说明
- `error_status_behavior` - 错误与状态码约定
- `key_entry_apis` - 关键入口 API 摘要
- `endpoint_index_table` - 完整端点索引

### 3. 更新 _build_core_context 方法

在 `engine.py` 中新增 API 聚合逻辑：
- 按模块分组端点
- 生成 API 分组概览表格（含认证模式）
- 生成详细 API 分组（按模块和主题域）
- 生成认证模式说明
- 生成错误与状态码约定表格
- 生成关键入口 API 列表
- 生成完整端点索引表格

### 4. 添加 API 契约验证函数

在 `contracts.py` 中新增验证函数：
- `validate_api_contract_grouped()` - 验证按服务族/域组织
- `validate_api_contract_not_endpoint_dump()` - 验证不是无限端点列表

验证规则：
- 必须有服务/API 分组章节
- 必须有调用约定章节（认证、错误）
- 必须有关键入口 API 摘要（而非全部端点）
- 原始端点行数不超过 50 行

### 5. 添加 validate_api_contract_output 方法

在 `engine.py` 中新增验证方法，供外部调用验证 API 契约输出质量。

## Output

### Modified Files

- `/templates/docs/04-api-contracts.md.j2` - 重写为聚合 API 契约模板
- `/repo_wiki/generator/contracts.py` - 扩展 api_contracts contract 和添加验证函数
- `/repo_wiki/generator/engine.py` - 更新 `_build_core_context` 生成 API 聚合上下文，添加 `validate_api_contract_output` 方法

### Key Template Sections

```markdown
## 服务/API 分组

${api_groups_table}

---

## 调用约定

### 认证方式

${authentication_patterns}

### 错误与状态码

${error_status_behavior}

### 关键入口 API

${key_entry_apis}
```

### Validation Functions

```python
API_CONTRACT_MAX_RAW_ENDPOINTS = 50

def validate_api_contract_grouped(content: str) -> tuple[bool, str]:
    # Check for required sections and content
    ...

def validate_api_contract_not_endpoint_dump(content: str) -> tuple[bool, str]:
    # Reject unbounded raw endpoint lists
    ...
```

## Issues

None

## Next Steps

Task 7.3 依赖 Task 6.2（域和服务族分组）和 Task 6.4（存储叙事）。Task 7.3 将重写 `docs/05-data-model.md`，分为核心数据模型、服务数据模型、数据库/迁移策略三段。
