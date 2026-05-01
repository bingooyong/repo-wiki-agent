---
agent: Agent_QualityRelease
task_ref: Task 16.1
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 16.1 - Replacement gate policy and rollback playbook

## Summary

定义了替换发布的正式门禁策略（replacement-gate-policy.md）、回滚预案（rollback-playbook.md）和 policy profiles 配置（policy-profiles.yaml）。策略基于 Phase 11 的 hard/soft gate 设计和 Phase 14 的外部基线比较机制构建。

## Details

### 1. 门禁策略定义

定义了三层门禁体系：
- **HARD Gate**: 结构失败（缺失文件、损坏路径、缺失 section）- 阻塞性
- **SOFT Gate**: 质量问题（prose 不足、列表过多、缺少聚合）- 非阻塞
- **TRANSITIONAL**: 兼容性过渡期宽限（legacy Qxx/Sxx 格式）

### 2. 证据链接规范

每个门禁判定必须链接到四类证据：
- `verify_result`: verify 命令的 grade/exit_code/checks
- `baseline_compare_result`: compare 命令的整体评分和维度评分
- `runtime_evidence`: SQLite 状态和增量变化
- `visual_evidence`: eval 输出和 wiki viewer 快照

### 3. 回滚策略

定义了回滚触发条件（CRITICAL/HIGH/MEDIUM）、决策权限（Manager/Agent_QualityRelease/Agent_AdapterGovernance）和执行步骤（止血→评估→决策→执行→验证）。

### 4. Policy Profiles

定义了三种 profile：
- `strict.profile`: 生产发布，零容忍
- `transitional.profile`: 过渡期，兼容 legacy 格式
- `pilot.profile`: 试点验证，探索性

## Output

### Created Files

- `/docs/operations/replacement-gate-policy.md` - 门禁策略主文档
- `/docs/operations/rollback-playbook.md` - 回滚执行手册
- `/docs/operations/policy-profiles.yaml` - 三种 profile 配置

### Key Content

**HARD Gate Codes**:
```python
HARD_GATE_CODES = {
    "STRUCT_SECTION_DIR_MISSING",
    "STRUCT_MISSING_SECTIONS",
    "STRUCT_NAVIGATION_BROKEN",
    "STRUCT_NAV_BAD_DEPTH",
    "STRUCT_NAV_TARGET_MISSING",
    "CONTENT_EMPTY",
}
```

**Profile Criteria**:
| Profile | HARD | SOFT | Score |
|---------|------|------|-------|
| strict | 0 | 0 | >= 0.85 |
| transitional | 0 | <= 3 | >= 0.70 |
| pilot | <= 1 | <= 5 | >= 0.60 |

## Issues

None - 所有依赖项已完成

## Next Steps

Task 16.1 完成。Task 16.2 (Agent_AdapterGovernance) 依赖 Task 16.1 和 Task 11.1，将构建 CI cutover 模板。