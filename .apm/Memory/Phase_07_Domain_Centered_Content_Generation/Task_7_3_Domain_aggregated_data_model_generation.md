---
agent: Agent_DocGen
task_ref: Task 7.3
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 7.3 - Domain-aggregated data model generation

## Summary

成功将 `05-data-model.md` 模板从扁平模型列表升级为三段式数据模型页面（核心数据模型、服务数据模型、数据库与迁移策略）。添加了模型去重、跨模块数据边界文档和迁移策略说明。

## Details

### 1. 重写 05-data-model.md.j2 模板

新模板包含以下固定章节：
- 核心数据模型（跨模块共享的基础实体）
- 服务数据模型（按模块分组的业务数据结构）
- 数据库与迁移策略（存储形状、迁移方式、跨边界）
- 模型索引表格
- 阅读导航链接

### 2. 更新 Data Models Contract Required Keys

扩展 `data_models` contract 的 `required_keys`：
- `repository_name` - 仓库名称
- `core_models_section` - 核心模型说明
- `core_models_table` - 核心模型列表
- `service_models_section` - 服务模型说明
- `service_models_by_module` - 按模块分组的服务模型
- `database_migration_section` - 数据库迁移章节标题
- `database_shape` - 数据库形状说明
- `migration_strategy` - 迁移策略说明
- `cross_module_boundaries` - 跨模块数据边界
- `model_index_table` - 模型索引表格

### 3. 更新 _build_core_context 方法

在 `engine.py` 中新增数据模型聚合逻辑：
- 识别核心模型（Module, Endpoint, DataModel, RepositoryInfo 等）
- 分离核心模型和服务模型
- 生成核心模型表格
- 按模块生成服务模型分组
- 生成数据库形状说明（按类型统计）
- 生成迁移策略说明
- 生成跨模块数据边界文档
- 生成模型索引表格

### 4. 添加数据模型验证函数

在 `contracts.py` 中新增验证函数：
- `validate_data_model_grouped()` - 验证三段式结构
- `validate_data_model_not_dump()` - 验证不是模型倾倒

验证规则：
- 必须有核心数据模型、服务数据模型、数据库与迁移策略三个章节
- 必须有迁移策略文档
- 原始模型行数不超过 30 行
- 必须有跨模块边界文档
- 必须引用 source-of-truth

### 5. 添加 validate_data_model_output 方法

在 `engine.py` 中新增验证方法，供外部调用验证数据模型输出质量。

## Output

### Modified Files

- `/templates/docs/05-data-model.md.j2` - 重写为三段式数据模型模板
- `/repo_wiki/generator/contracts.py` - 扩展 data_models contract 和添加验证函数
- `/repo_wiki/generator/engine.py` - 更新 `_build_core_context` 生成数据模型聚合上下文，添加 `validate_data_model_output` 方法

### Key Template Sections

```markdown
## 核心数据模型

${core_models_section}

### 核心模型列表

${core_models_table}

---

## 服务数据模型

${service_models_section}

### 按服务分组

${service_models_by_module}

---

## 数据库与迁移策略

${database_migration_section}

### 数据库形状

${database_shape}

### 迁移策略

${migration_strategy}

### 跨模块数据边界

${cross_module_boundaries}
```

### Validation Functions

```python
DATA_MODEL_MIN_CORE_MODELS = 1
DATA_MODEL_MAX_RAW_MODELS = 30

def validate_data_model_grouped(content: str) -> tuple[bool, str]:
    # Check for three required sections
    ...

def validate_data_model_not_dump(content: str) -> tuple[bool, str]:
    # Reject model dumps with no aggregation
    ...
```

## Issues

None

## Next Steps

Task 7.4 依赖 Task 7.1、7.2、7.3 的输出。Task 7.4 将生成 `docs/sections/**` 专题页并完成导航拼接。
