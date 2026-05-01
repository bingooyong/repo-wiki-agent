---
agent: Agent_IndexGraph
task_ref: Task 12.1
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 12.1 - Dual-database runtime architecture for state and evidence

## Summary

定义了双重数据库架构，将 Phase 2 的 SQLite state store 扩展为 dual-database 模型。确定了 state DB (state.sqlite3) 与 generation/evidence DB (runtime.sqlite3) 的边界职责，定义了迁移路径和运行时边界规则。

## Details

### 1. 双库职责定义

**Primary State DB (state.sqlite3):**
- 文件状态和 hash 追踪 (files, file_hashes)
- 代码块索引 (chunks, chunks_fts)
- 符号索引 (symbols)
- Verify runs 摘要 (verify_runs 表 - 仅 ID 和状态)
- 元数据 (metadata)

**Generation/Evidence DB (runtime.sqlite3):**
- 文档层级结构 (doc_hierarchy)
- Section registry 和 aliases (section_registry, section_aliases)
- Nav graph 和 cross-links (nav_graph, doc_cross_links)
- Verify/Compare 详细结果持久化 (verify_run_details, compare_run_details)
- Page invalidation 追踪 (page_invalidation)
- Generation cache (generation_cache)

### 2. 向后兼容

原有 state.sqlite3 的表结构保持不变:
- schema_migrations, files, file_hashes, chunks, chunks_fts, symbols, generation_cache, verify_runs, metadata

通过 migration 2/3 扩展新表到同一数据库文件或单独 runtime.sqlite3:
- Migration 2: doc_hierarchy, section_registry, section_aliases, doc_cross_links
- Migration 3: nav_graph, verify_run_details, compare_run_details, page_invalidation

### 3. 运行时边界规则

1. 文件/chunk/symbol 操作保留在 SQLiteStateStore
2. doc-level 元数据和 evidence 存储在 SQLiteRuntimeStore
3. generation_cache 可在两处共享 (state_store 有基础表，runtime_store 有扩展)
4. verify/compare 的详细结果存储在 runtime_store，state_store 只保留摘要

### 4. 迁移路径

Schema version 1 -> 2: 添加文档层级和 section registry 表
Schema version 2 -> 3: 添加 nav_graph 和 evidence 持久化表
每个 migration 幂等且确定性

### 5. 验证

- 多次 upgrade 不破坏现有数据
- rebuild 行为可重复
- 边界规则可强制执行

## Output

- `/repo_wiki/orchestration/runtime_store.py` - SQLiteRuntimeStore 实现，包含:
  - 双库边界规则的完整文档字符串
  - Migration 2 (doc_hierarchy, section_registry, section_aliases, doc_cross_links)
  - Migration 3 (nav_graph, verify_run_details, compare_run_details, page_invalidation)
  - DocHierarchyRecord, SectionRegistryRecord, VerifyRunRecord, CompareRunRecord, PageInvalidationRecord dataclasses
  - 完整性检查方法: check_orphaned_docs(), check_broken_section_mappings(), check_stale_evidence()
  - Export/rebuild 方法: export_runtime_artifacts(), rebuild_from_artifacts()

## Issues

None

## Next Steps

Task 12.2 需要为 docs/sections/navigation/acceptance 建立结构化表 (已在 runtime_store.py 中通过 migrations 2/3 实现)。Task 12.3 依赖本任务提供的 verify/compare 持久化基础设施。