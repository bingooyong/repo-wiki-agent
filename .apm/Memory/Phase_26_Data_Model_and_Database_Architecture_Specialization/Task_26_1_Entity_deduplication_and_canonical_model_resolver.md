---
task_ref: "Task 26.1 - Entity deduplication and canonical model resolver"
status: "completed"
important_findings: false
compatibility_issue: false
compatibility_issues: false
---

## 任务完成报告

### 交付物

#### 1. Canonical Model Resolver
**文件**: `repo_wiki/generator/engine.py`

新增 `CanonicalModelResolver` 类（Phase 26 - Task 26.1），功能包括：
- 分辨核心实体（core_entity）、DTOs、请求/响应类型（request_response）、重复投影（duplicated_projection）和基础设施（infrastructure）
- 增强 `DataModel` 类，添加以下元数据字段：
  - `model_category`: 模型分类
  - `canonical_name`: 规范名称
  - `is_canonical`: 是否为规范表示
  - `projections`: 其他已知名称列表
- 添加 `ModelCategory` 常量类，定义所有模型分类常量

#### 2. 模型元数据
增强的 `DataModel` 类包含完整的 Phase 26 元数据：
```python
@dataclass
class DataModel:
    # ... 原有字段 ...
    model_category: str = "unknown"  # core_entity, dto, request_response, duplicated_projection, infrastructure
    canonical_name: str = ""        # The canonical name this model resolves to
    is_canonical: bool = False      # Whether this is the canonical representation
    projections: list[str] = None   # Other names this entity is known by
```

#### 3. 高频模型 Fixtures
`CanonicalModelResolver` 自动识别高频模型：
- 跨 3+ 模块共享的模型自动标记为高频
- 高频名称模式（如 user, config, settings, base, common, session, token, auth, error, result 等）
- 高频模型排在首位，确保在输出中不会被 DTO 主导

#### 4. 测试文件
创建了两个测试文件：
- `tests/test_model_deduplication.py`: 17 个测试用例
- `tests/test_data_models.py`: 18 个测试用例

### 验证结果

**编译命令**: `uv run repo-wiki --help` - 通过

**测试命令**: `uv run pytest tests/test_model_deduplication.py tests/test_data_models.py` - 通过（35 个测试）

### 关键设计决策

1. **归一化策略**: 移除常见后缀（_dto, _entity, _model, _builder, _factory, _request, _response 等），无论大小写
2. **权威表示优先级**: SQLAlchemy > Pydantic > Dataclass > Other
3. **分类优先级**: 先按名称后缀，再按类型，最后按域
4. **高频模型排序**: 高频模型优先，按投影数量和 dedup_key 排序

### 技术细节

- 规范模型通过 `dedup_key` 分组，支持跨语言（Java entities, TypeScript types, Python classes）
- 修复了 `DataModelAggregator._deduplicate_models` 中的正则表达式，使其与 `CanonicalModelResolver._normalize_name` 一致
