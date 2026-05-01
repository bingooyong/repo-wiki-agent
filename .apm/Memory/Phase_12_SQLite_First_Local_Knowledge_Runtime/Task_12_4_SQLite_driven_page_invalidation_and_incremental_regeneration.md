---
agent: Agent_IndexGraph
task_ref: Task 12.4
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 12.4 - SQLite-driven page invalidation and incremental regeneration

## Summary

实现了 SQLite 驱动的页面失效引擎和增量再生规划器。使用 nav_graph 和 doc_hierarchy 来追踪页面依赖关系，实现细粒度的页面失效和有序的增量再生。

## Details

### 1. PageInvalidationEngine

**invalidate_from_changes():**
- 基于 changed_files/deleted_files/renamed_files 触发失效
- 使用 nav_graph 的 affected_pages 字段确定受影响页面
- 模块级别影响分析
- 检测是否需要 full rebuild

**invalidate_from_section_change():**
- section 更新时触发相关页面失效
- 包括 incoming links (链接到该 section 的页面)
- 和 outgoing links (该 section 链接到的页面)

**invalidate_from_nav_broken():**
- 导航链接失效时触发
- 源页面和目标页面都需要重新生成

**invalidate_from_evidence_stale():**
- verify/compare evidence 陈旧时触发
- 所有 overview 和 section 页面都需要刷新

**invalidate_from_section_registry_change():**
- section registry 更新时触发
- added: 只需要更新 overview 和 nav
- removed: 需要 full rebuild
- alias_added: 更新 section 和 overview

### 2. 失效场景覆盖

- ADD: 新文件添加 -> 影响模块的页面失效
- MODIFY: 文件修改 -> 影响模块页面失效
- DELETE: 文件删除 -> 影响模块页面失效
- RENAME: 文件重命名 -> 两个路径相关的页面都失效
- SECTION_REGISTRY_CHANGE: section 结构变化 -> 导航相关页面失效

### 3. 增量再生规划

**RegenerationTask:**
- doc_slug, doc_type, priority, reason, dependencies
- 依赖必须在被依赖页面之前完成

**plan_regeneration():**
- 使用拓扑排序 (Kahn's algorithm) 计算再生顺序
- 无依赖页面优先再生
- 优先级: overview(1) > section(2) > module(3)

**execute_regeneration():**
- 按序执行再生任务
- 检查依赖完成状态
- 跟踪完成状态并更新 runtime_store

### 4. 缓存失效规则

基于 evidence-aware dependency rules:
- 文件变化: 只失效直接相关的模块页面
- section 更新: 失效该 section 及其导航相关页面
- nav 损坏: 失效源页面和所有引用目标
- evidence 陈旧: 失效所有依赖该 evidence 的页面

### 5. 替换就绪性

本地优先 repo-wiki 操作的支持:
- 生成 -> 验证 -> 比较 -> 回归 完整循环
- 增量更新基于 SQLite 状态追踪
- 可检测修复后的再验收

## Output

- `/repo_wiki/orchestration/invalidation.py`:
  - PageInvalidationEngine: 页面失效引擎
  - IncrementalRegenerationPlanner: 增量再生规划器
  - InvalidationResult, RegenerationTask dataclasses
  - 所有失效场景的处理方法

- 失效场景覆盖:
  - file_changed, section_updated, nav_broken, evidence_stale, section_registry_changed

- 缓存失效规则:
  - ADD, MODIFY, DELETE, RENAME, SECTION_REGISTRY_CHANGE

## Issues

None

## Next Steps

Phase 12 完成。所有四个任务已完成:
- Task 12.1: 双库架构定义
- Task 12.2: SQLite schema 扩展
- Task 12.3: Verify/compare 持久化
- Task 12.4: 页面失效和增量再生