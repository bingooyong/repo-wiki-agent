# Strict Threshold Gap Backlog and Ownership Plan

**文档属性**: Gap Backlog
**版本**: 1.0
**日期**: 2026-04-26
**Agent**: Agent_QualityRelease
**阶段**: Phase 20 Task 20.3

## 1. 背景

基于 Task 20.2 的 release-candidate pilot 对比结果 (Overall Score: 13.4%, 5 critical gaps, 3 major gaps)，本任务将剩余的 strict 85% 差距分解为可执行、可追踪、可归属的 backlog 项目。

## 2. Gap 分析摘要

### Compare 结果 (Task 20.2)

| Dimension | Status | Score | Gap Count |
|-----------|--------|-------|----------|
| Directory Hierarchy | FAIL | 0.0% | 1 critical |
| Section Coverage | FAIL | 0.0% | 1 critical |
| Heading Coverage | FAIL | 0.0% | 2 major |
| Prose Density | PARTIAL | 50.0% | 1 major |
| Navigation Completeness | FAIL | 0.0% | 1 critical |
| Aggregation Quality | PARTIAL | 50.0% | 2 critical |

**总计**: 5 critical + 3 major = 8 gaps

### 根本原因分类

| Category | Critical | Major | 说明 |
|----------|----------|-------|------|
| Generator | 4 | 3 | 内容生成能力不足 |
| Verifier | 1 | 0 | 验证规则需要更新 |
| Viewer | 0 | 0 | 视图层无问题 |
| Governance | 0 | 0 | 策略层无问题 |

## 3. Strict Gap Backlog

### 3.1 Generator Work Items (P0)

| ID | Gap | Severity | Owner | Acceptance Criteria |
|----|-----|----------|-------|-------------------|
| G-01 | 创建 docs/sections/ 目录结构 | CRITICAL | Agent_DocGen | docs/sections/ 存在，包含 9 个标准 section 子目录 |
| G-02 | 生成 9 个标准 section 页 | CRITICAL | Agent_DocGen | 每个 section 下有 index.md，内容 > 500 chars |
| G-03 | 修复 heading 覆盖 - 添加必需 heading | MAJOR | Agent_DocGen | 00-overview.md 包含 "项目定位","核心问题","核心能力" 等 9 个 heading |
| G-04 | 增加 overview prose 密度 | MAJOR | Agent_DocGen | 00-overview.md + 01-architecture.md 合计 prose > 2000 chars |
| G-05 | 补充 navigation 链接 | CRITICAL | Agent_DocGen | 每个 section index.md 包含 >= 3 个交叉链接 |
| G-06 | 修复 API aggregation 结构 | CRITICAL | Agent_DocGen | 04-api-contracts.md 包含服务分组章节 |
| G-07 | 修复 DataModel aggregation 结构 | CRITICAL | Agent_DocGen | 05-data-model.md 包含三段式结构 (Core/Service/DB) |

### 3.2 Verifier Work Items (P1)

| ID | Gap | Severity | Owner | Acceptance Criteria |
|----|-----|----------|-------|-------------------|
| V-01 | 更新 compare 工具路径处理 | CRITICAL | Agent_AdapterGovernance | compare 工具正确处理 docs/ vs docs/ 层级比较 |

### 3.3 Viewer Work Items

无 structural viewer gaps。

### 3.4 Governance Work Items

无 governance gaps。

## 4. Backlog 优先级排序

### Phase 21 (Immediate - 1 week)

```
P0 - Critical Blocking:
├── G-01: 创建 docs/sections/ 目录结构
├── G-02: 生成 9 个标准 section 页
├── V-01: 更新 compare 工具路径处理
└── G-05: 补充 navigation 链接
```

### Phase 22 (Short term - 2-4 weeks)

```
P1 - Major Quality:
├── G-03: 修复 heading 覆盖
├── G-04: 增加 overview prose 密度
├── G-06: 修复 API aggregation 结构
└── G-07: 修复 DataModel aggregation 结构
```

## 5. 评分预测

| 完成项 | 预期分数变化 |
|-------|-------------|
| G-01 + G-02 (sections 结构) | +15% (directory_hierarchy, section_coverage) |
| G-05 (navigation) | +10% (navigation_completeness) |
| G-03 (headings) | +5% (heading_coverage) |
| G-04 (prose density) | +5% (prose_density) |
| G-06 + G-07 (aggregation) | +5% (aggregation_quality) |
| **Total potential** | **+40%** |

当前 13.4% + 40% = 53.4% (仍低于 strict 85%)

**结论**: 即使完成所有 7 个 generator items，仍无法达到 strict 85% 阈值。需要额外的 content quality 工作。

## 6. 额外工作项 (用于达到 strict 85%)

| ID | Work Item | Owner | 说明 |
|----|-----------|-------|------|
| E-01 | Qoder-style narrative 重写 | Agent_DocGen | 当前 content 不是 qoder 风格，需要全面重写 |
| E-02 | Mermaid diagram 补充 | Agent_DocGen | 01-architecture.md 需要更多 Mermaid 图表 |
| E-03 | Cross-section prose 连接 | Agent_DocGen | 各 section 之间需要更多 prose 叙述而非列表 |
| E-04 | Content quality audit | Agent_QualityRelease | 人工审查确保达到 qoder 风格标准 |

## 7. Strict 85% 路径可行性评估

**当前状态**: 13.4%
**目标**: 85%
**Gap**: 71.6%

**可达到路径**:
1. 完成所有 G items (7 items) → +40% → 53.4%
2. 完成所有 E items (4 items) → +25% → 78.4%
3. 额外的 content 优化 → +7% → 85.4%

**结论**: Strict 85% 目标可达，但需要 Phase 21 + Phase 22 + Phase 23 三个阶段的持续工作。

## 8. Product-Decision vs Implementation Gaps

### Product-Decision Gaps (需要管理决策)

| Gap | 说明 | 决策者 |
|-----|------|--------|
| 是否采用 qoder section 命名 | 9 个标准 section vs 自定义 | Manager |
| 是否需要 Mermaid 图表 | qoder 风格要求 4+ diagrams | Manager |
| Content quality 标准 | 人工审查 vs 自动化阈值 | Manager |

### Implementation Gaps (可执行工作)

所有 G-01 到 G-07 和 E-01 到 E-04 都是 implementation gaps，可以立即分配执行。

## 9. 下一步

Task 20.4 将基于此 backlog 产出最终 transitional go/no-go dossier 和 manager handover。