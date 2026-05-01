---
agent: Agent_IndexGraph
task_ref: Task 12.2
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 12.2 - SQLite schema for hierarchy, sections, navigation, and evidence

## Summary

在 Task 12.1 的双库架构基础上，通过 Migration 2 和 Migration 3 建立了完整的 SQLite 表结构来存储文档层级、section registry、导航图和验收证据。

## Details

### 1. Migration 2: 文档层级和 Section Registry 表

**doc_hierarchy 表:**
- 存储所有生成的文档 (overview, section, module, phase)
- 关键字段: doc_type, doc_slug, doc_path, layer, parent_slug
- 包含 generation 元数据 (input/output hash, generated_at)
- 索引: doc_type, doc_slug, doc_path, layer

**section_registry 表:**
- 规范 section 定义 (canonical_slug, title, description)
- 关联 phase (required_for_phase) 用于渐进式文档生成
- 支持 active/inactive 状态

**section_aliases 表:**
- 支持 AI_API_Atlas 的 Q01/S01 格式映射到规范 slug
- 例如: 'q01-architecture' -> 'architecture'

**doc_cross_links 表:**
- 存储文档间导航链接
- link_type: 'navigation', 'reference', 'cross_section'
- 可验证链接有效性

### 2. Migration 3: Nav Graph 和 Evidence 表

**nav_graph 表:**
- 每页的 incoming_links 和 outgoing_links (JSON)
- depth 字段: 0=overview, 1=section, 2=module
- affected_pages: 追踪哪些页面依赖此文档

**verify_run_details 表:**
- 完整 verify 结果持久化 (run_id, target_path, grade, score)
- hard_gate_failures, soft_gate_failures 计数
- hard_gate_codes_json, soft_gate_codes_json 详细错误码
- full_result_json 完整审计轨迹

**compare_run_details 表:**
- 完整 compare 结果持久化
- overall_score, overall_band, structural_score, quality_score
- delta_type_json, scores_json, gaps_json 用于趋势分析
- acceptance_blocked 布尔值用于回归检测

**page_invalidation 表:**
- 追踪页面失效状态
- invalidation_reason: 'file_changed', 'section_updated', 'nav_broken', 'evidence_stale'
- changed_files_json, impacted_modules_json 用于影响分析
- regeneration_status: 'pending', 'in_progress', 'completed', 'failed'

### 3. 完整性检查

**check_orphaned_docs():**
- 查找引用不存在文件的 section 页

**check_broken_section_mappings():**
- 查找无法解析的 section aliases

**check_stale_evidence():**
- 查找超过 30 天的 verify/compare 记录

### 4. 外部 Markdown 和 Source-of-Truth 工件

- SQLite 作为 operational metadata backbone
- 外部 Markdown 文件 (docs/00-overview.md 等) 作为输出产物
- ai/source-of-truth/*.yaml 作为事实层输入

## Output

- 扩展 `/repo_wiki/orchestration/runtime_store.py`:
  - MIGRATION_2: doc_hierarchy, section_registry, section_aliases, doc_cross_links
  - MIGRATION_3: nav_graph, verify_run_details, compare_run_details, page_invalidation
  - DocHierarchyRecord, SectionRegistryRecord, VerifyRunRecord, CompareRunRecord, PageInvalidationRecord dataclasses
  - 所有 CRUD 操作方法
  - 完整性检查方法

- 核心表结构:
  - doc_hierarchy: 文档层级和路径映射
  - section_registry: 规范 section 定义和 aliases
  - nav_graph: 页面依赖关系和失效追踪
  - verify_run_details: verify 结果历史
  - compare_run_details: compare 结果历史
  - page_invalidation: 增量失效追踪

## Issues

None

## Next Steps

Task 12.3 依赖本任务的 verify_run_details 和 compare_run_details 表，Task 12.4 依赖 page_invalidation 表。