---
task_ref: "Task 23.2 - Evidence SQLite schema"
status: "Completed"
important_findings: false
compatibility_issue: false
compatibility_issues: false
---

# Task Log: Task 23.2 - Evidence SQLite schema

## Summary

在 Task 23.1 Source Span Extractor 输出的基础上，通过 Migration 4 扩展了 SQLite schema，添加了 evidence_span、page_source_map 和 symbol_reference 三张表，用于存储证据跨度及页面来源关联。

## Details

### 1. Migration 4: Evidence Span 表结构

**evidence_span 表:**
- digest: SHA256 哈希用于去重
- file_path: 源文件路径
- line_start/line_end: 行号范围
- language: 语言类型 (python/typescript/java/sql/yaml/markdown)
- symbol: 符号名 (函数、类、变量)
- span_text: 实际源码文本
- confidence: 提取置信度 0.0-1.0
- UNIQUE(digest) 保证去重

**page_source_map 表:**
- doc_slug/doc_type: 维基页面标识
- evidence_id: FK 关联 evidence_span
- citation_order: 页面中引用顺序
- context_hint: 可选上下文提示

**symbol_reference 表:**
- source_file_path/line_start/line_end: 引用位置
- source_symbol/target_symbol: 源符号和目标符号
- target_file_path/line_start/line_end: 目标定义位置
- ref_type: 引用类型 (call/import/inheritance/type_ref/variable_ref)

### 2. 新增 dataclass

- EvidenceSpanRecord: 证据跨度记录
- PageSourceMapRecord: 页面来源映射记录
- SymbolReferenceRecord: 符号引用记录

### 3. Repository APIs

**Evidence Span Operations:**
- upsert_evidence_span(record): 插入或更新证据跨度
- get_evidence_span(evidence_id): 按 ID 获取
- get_evidence_span_by_digest(digest): 按摘要获取
- list_evidence_spans(...): 带过滤条件的列表查询
- count_evidence_spans(): 计数

**Page Source Map Operations:**
- map_evidence_to_page(...): 将证据映射到页面
- list_page_sources(doc_slug, doc_type): 列出页面所有证据源
- list_pages_for_evidence(evidence_id): 列出引用某证据的所有页面
- unmap_evidence_from_page(...): 解除映射
- clear_page_sources(...): 清除页面所有映射

**Symbol Reference Operations:**
- upsert_symbol_reference(record): 插入符号引用
- list_symbol_references(...): 带过滤条件的列表查询
- get_symbol_targets(source_file_path, source_line): 获取指定位置的引用目标
- count_symbol_references(): 计数

### 4. 测试覆盖

创建了 tests/test_evidence_schema.py，包含:
- test_schema_version_includes_migration_4: Schema 版本验证
- test_evidence_span_crud: 证据跨度 CRUD
- test_evidence_span_upsert_idempotent: 去重验证
- test_evidence_span_filter_by_language: 按语言过滤
- test_evidence_span_filter_by_file_path: 按文件路径过滤
- test_count_evidence_spans: 计数功能
- test_map_evidence_to_page: 证据到页面映射
- test_list_pages_for_evidence: 多页面引用
- test_unmap_evidence_from_page: 解除映射
- test_clear_page_sources: 清除页面映射
- test_symbol_reference_crud: 符号引用 CRUD
- test_symbol_reference_filter_by_target: 按目标符号过滤
- test_symbol_reference_filter_by_type: 按引用类型过滤
- test_get_symbol_targets_at_line: 位置查询
- test_count_symbol_references: 计数功能
- test_evidence_with_page_sources_and_symbol_refs: 完整工作流
- test_migration_4_idempotent: 迁移幂等性
- test_upsert_idempotent_forEvidenceSpans: UPSERT 幂等性

## Output

- 扩展 `/repo_wiki/orchestration/runtime_store.py`:
  - MIGRATION_4: evidence_span, page_source_map, symbol_reference 表
  - EvidenceSpanRecord, PageSourceMapRecord, SymbolReferenceRecord dataclasses
  - 所有 CRUD 操作方法

- 新增 `/tests/test_evidence_schema.py`:
  - 18 个测试用例，全部通过

## Self-Test Results

```
uv run pytest tests/test_evidence_schema.py tests/test_phase12_sqlite_runtime.py -v --tb=short
...
tests/test_evidence_schema.py ..................                         [ 45%]
tests/test_phase12_sqlite_runtime.py ......................              [100%]
============================== 40 passed in 0.38s ==============================
```

## Compilation Check

```
uv run repo-wiki --help
# 输出正常，显示所有命令
```

## Issues

None

## Next Steps

Task 23.3 依赖本任务的 evidence_span 和 page_source_map 表进行证据排名和页面匹配。
