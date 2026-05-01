---
agent: Agent_QualityRelease
task_ref: Task 20.3
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: true
---

# Task Log: Task 20.3 - Strict threshold gap backlog and ownership plan

## Summary

将 Task 20.2 的 compare 结果 (Overall Score: 13.4%, 5 critical gaps, 3 major gaps) 分解为结构化的 backlog items，按 category (generator/verifier/viewer/governance) 和 owner 组织，并提供了 strict 85% 路径可行性评估。

## Details

### 1. Gap 分类

| Category | Critical | Major | 说明 |
|----------|----------|-------|------|
| Generator | 4 | 3 | Agent_DocGen 负责 |
| Verifier | 1 | 0 | Agent_AdapterGovernance 负责 |
| Viewer | 0 | 0 | 无问题 |
| Governance | 0 | 0 | 无问题 |

### 2. Backlog Items

**P0 Critical (Phase 21)**:
- G-01: 创建 docs/sections/ 目录结构
- G-02: 生成 9 个标准 section 页
- V-01: 更新 compare 工具路径处理
- G-05: 补充 navigation 链接

**P1 Major (Phase 22)**:
- G-03: 修复 heading 覆盖
- G-04: 增加 overview prose 密度
- G-06: 修复 API aggregation 结构
- G-07: 修复 DataModel aggregation 结构

### 3. Strict 85% 路径评估

当前 13.4% + 40% (所有 generator items) + 25% (额外优化) = 78.4%
需要 Phase 21 + 22 + 23 才能达到 85%

### 4. Product-Decision vs Implementation

- Product-Decision gaps: 需要 Manager 决策 (section 命名、Mermaid 要求)
- Implementation gaps: G-01 到 G-07, E-01 到 E-04 可立即执行

## Output

- `docs/operations/strict-gap-backlog-and-ownership-plan.md` - 完整的 backlog 文档

## Next Steps

Task 20.4 将基于此 backlog 产出最终 transitional go/no-go dossier。
