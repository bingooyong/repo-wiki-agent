---
agent: Agent_DocGen
task_ref: Task 7.1
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 7.1 - Domain-centered module map generation

## Summary

成功将 `03-module-map.md` 模板从扁平模块列表升级为领域组织的模块地图。按业务域（Domain）、服务族（Service Family）、运行时角色（Runtime Role）三层结构组织模块，并添加了跨域依赖关系展示和导航链接。

## Details

### 1. 重写 03-module-map.md.j2 模板

新模板包含以下固定章节：
- 域概览表格（业务域统计）
- 详细域分组（按服务族和运行时角色组织）
- 模块索引表格（快速查找）
- 跨域依赖关系
- 阅读导航链接

### 2. 更新 Module Map Contract Required Keys

扩展 `module_map` contract 的 `required_keys`：
- `repository_name` - 仓库名称
- `domain_overview_table` - 域概览表格
- `domain_groups_detail` - 详细域分组（多级嵌套结构）
- `module_index_table` - 模块索引表格
- `cross_domain_dependencies` - 跨域依赖关系

### 3. 更新 _build_core_context 方法

在 `engine.py` 中新增领域分组逻辑：
- 按 domain → service_family → runtime_role 三级组织模块
- 生成域概览表格（含业务域说明）
- 生成详细域分组（含模块职责、依赖关系、文档链接）
- 生成模块索引表格
- 生成跨域依赖关系列表

### 4. 添加模块地图验证函数

在 `contracts.py` 中新增验证函数：
- `validate_module_map_domain_grouped()` - 验证按领域组织而非平铺
- `validate_module_map_not_directory_flat()` - 验证不是目录平铺输出

验证规则：
- 必须有域概览表格
- 必须有 service_family 和 runtime_role 层级
- 必须包含模块职责描述
- 必须有导航链接到 overview 文档

### 5. 添加 validate_module_map_output 方法

在 `engine.py` 中新增验证方法，供外部调用验证模块地图输出质量。

## Output

### Modified Files

- `/templates/docs/03-module-map.md.j2` - 重写为领域地图模板
- `/repo_wiki/generator/contracts.py` - 扩展 module_map contract 和添加验证函数
- `/repo_wiki/generator/engine.py` - 更新 `_build_core_context` 生成领域分组上下文，添加 `validate_module_map_output` 方法

### Key Template Sections

```markdown
## 域概览

${domain_overview_table}

---

## 详细域分组

${domain_groups_detail}

---

## 模块索引

| 模块 | 路径 | 运行时角色 | 域 | 核心职责 |
|------|------|-----------|-----|---------|

---

## 跨域依赖关系

${cross_domain_dependencies}
```

### Validation Functions

```python
def validate_module_map_domain_grouped(content: str) -> tuple[bool, str]:
    # Check for domain grouping structure
    ...

def validate_module_map_not_directory_flat(
    content: str, has_domain_metadata: bool = True
) -> tuple[bool, str]:
    # Reject flat directory listings
    ...
```

## Issues

None

## Next Steps

Task 7.2 依赖 Task 6.2（域元数据）和 Task 6.4（架构叙事）。Task 7.2 将重写 `docs/04-api-contracts.md`，按服务族和主题域聚合 API。
