---
agent: Agent_AdapterGovernance
task_ref: Task 8.1
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 8.1 - Content-quality verify and CI gate upgrade

## Summary

成功将 `verify --ci` 从存在性校验升级为内容质量校验。添加了 6 个新的质量检查方法，扩展了 CheckResult 以支持精确原因码，并添加了 12 个 fixture-based 测试覆盖空模板、纯列表文档、损坏导航和缺失 section 层等场景。

## Details

### 1. 扩展 CheckResult 添加 ReasonCode 支持

在 `repo_wiki/verifier/service.py` 中新增 ReasonCode 类，定义精确的原因码体系：

- **1xxx**: 内容质量码 (CONTENT_EMPTY, CONTENT_LIST_ONLY, CONTENT_TOO_SHORT, CONTENT_MISSING_SECTIONS)
- **2xxx**: 结构质量码 (STRUCT_MISSING_SECTIONS, STRUCT_SECTION_DIR_MISSING, STRUCT_NAVIGATION_BROKEN)
- **3xxx**: 聚合质量码 (AGG_API_NOT_GROUPED, AGG_API_ENDPOINT_DUMP, AGG_DM_NOT_GROUPED, AGG_DM_MODEL_DUMP)
- **4xxx**: 架构质量码 (ARCH_MERMAID_MISSING, ARCH_MERMAID_INSUFFICIENT, ARCH_LAYER_EXPLANATION_MISSING)

CheckResult 新增 `reason_code` 字段，verify() 方法在 ci=True 时返回 `reason_codes` 数组。

### 2. 新增质量检查方法

- `_check_overview_prose_quality()`: 检查最小 200 字符 prose、最少 5 个 section、列表比例 <70%
- `_check_architecture_prose_quality()`: 检查至少 2 个 Mermaid 块和三层架构解释
- `_check_sections_exist()`: 检查 docs/sections/ 存在性和 8 个必需 section 页
- `_check_api_aggregated()`: 检查 API 聚合（分组章节、调用约定、关键 API、<50 raw endpoints）
- `_check_data_model_aggregated()`: 检查数据模型聚合（三段式、迁移策略、<30 raw models）
- `_check_navigation_links()`: 检查 section 页链接到 overview 和至少有 2 个内部导航链接

### 3. 新增 Fixture-based 测试

添加 12 个测试用例覆盖新质量规则：

- `test_overview_prose_quality_fail_on_empty` - 空模板
- `test_overview_prose_quality_fail_on_list_only` - 纯列表文档
- `test_architecture_prose_quality_fail_on_missing_mermaid` - 缺少 Mermaid
- `test_architecture_prose_quality_fail_on_missing_layer_explanation` - 缺少三层解释
- `test_sections_exist_fail_on_missing_sections_dir` - 缺少 section 目录
- `test_sections_exist_fail_on_partial_sections` - 部分 section 页
- `test_api_aggregated_fail_on_endpoint_dump` - API 端点倾倒
- `test_api_aggregated_fail_on_missing_grouping` - API 缺少分组
- `test_data_model_aggregated_fail_on_missing_sections` - 数据模型缺少章节
- `test_navigation_links_fail_on_broken_nav` - 损坏的导航
- `test_quality_pass_with_proper_content` - 正确内容通过所有检查
- `test_ci_output_includes_reason_codes` - CI 输出包含原因码
- `test_reason_codes_are_precise` - 原因码精确性

## Output

### Modified Files

- `/repo_wiki/verifier/service.py` - 新增 ReasonCode 类、Phase 08 检查方法、更新 verify()
- `/tests/test_verifier.py` - 新增 12 个 fixture-based 测试用例

### Key Code: ReasonCode Class

```python
class ReasonCode:
    CONTENT_EMPTY = "CONTENT_EMPTY"            # 1001
    CONTENT_LIST_ONLY = "CONTENT_LIST_ONLY"    # 1002
    CONTENT_TOO_SHORT = "CONTENT_TOO_SHORT"    # 1003
    CONTENT_MISSING_SECTIONS = "CONTENT_MISSING_SECTIONS"  # 1004
    STRUCT_MISSING_SECTIONS = "STRUCT_MISSING_SECTIONS"    # 2001
    STRUCT_SECTION_DIR_MISSING = "STRUCT_SECTION_DIR_MISSING"  # 2002
    STRUCT_NAVIGATION_BROKEN = "STRUCT_NAVIGATION_BROKEN"  # 2003
    AGG_API_NOT_GROUPED = "AGG_API_NOT_GROUPED"            # 3001
    AGG_API_ENDPOINT_DUMP = "AGG_API_ENDPOINT_DUMP"       # 3002
    AGG_DM_NOT_GROUPED = "AGG_DM_NOT_GROUPED"             # 3003
    AGG_DM_MODEL_DUMP = "AGG_DM_MODEL_DUMP"              # 3004
    ARCH_MERMAID_MISSING = "ARCH_MERMAID_MISSING"         # 4001
    ARCH_MERMAID_INSUFFICIENT = "ARCH_MERMAID_INSUFFICIENT"  # 4002
    ARCH_LAYER_EXPLANATION_MISSING = "ARCH_LAYER_EXPLANATION_MISSING"  # 4003
```

### CI Output Format (example)

```json
{
  "grade": "FAIL",
  "ci_mode": true,
  "checks": [...],
  "summary": {"total": 12, "pass": 6, "warn": 0, "fail": 6},
  "reason_codes": ["STRUCT_SECTION_DIR_MISSING", "CONTENT_TOO_SHORT"]
}
```

## Issues

None

## Next Steps

Task 8.1 已完成。Task 8.2 依赖 Task 8.1，将建立 qoder 基线对比脚本和 gap report 格式。
