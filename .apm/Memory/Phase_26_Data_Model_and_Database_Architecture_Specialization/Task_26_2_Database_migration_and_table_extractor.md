---
task_ref: "Task 26.2 - Database migration and table extractor"
status: "completed"
important_findings: true
compatibility_issue: false
compatibility_issues: []
---

## 完成状态
- 状态: completed
- 完成时间: 2026/04/26

## 交付物

### 1. Migration Extractor (repo_wiki/scanner/database_migrations.py)
- `DatabaseMigrationExtractor` 类: 从仓库中提取数据库迁移和表模式
- 支持提取:
  - SQL CREATE TABLE 语句及其列定义
  - 主键、外键约束
  - 迁移文件元数据 (Alembic version, down_revision, up_revision)
  - CREATE INDEX 语句
  - 文件/行号引用

### 2. Schema Contracts
- `write_schema_contracts()` 函数: 将模式契约写入 ai/source-of-truth 目录
- 生成文件:
  - `table-schemas.yaml`: 表模式定义
  - `migrations.yaml`: 迁移元数据
  - `table-model-links.yaml`: 表到规范模型的链接

### 3. Tests (tests/test_database_migrations.py)
- 12 个测试用例覆盖:
  - 简单和复杂 CREATE TABLE 语句提取
  - 多表和外键关系
  - Alembic 迁移元数据提取
  - 规范模型名称推断
  - 文件/行号引用保留
  - 迁移文件模式检测
  - Schema contracts 写入

## 关键发现

### 1. 列提取逻辑修复
- 问题: `_extract_primary_keys` 函数接收完整的 CREATE TABLE 语句而不是仅列定义部分
- 解决: 在提取主键之前先提取括号内的列定义部分

### 2. Python 迁移文件处理
- Alembic Python 迁移文件使用 SQLAlchemy 的 `op.create_table()` 而不是 SQL CREATE TABLE
- 当前实现专注于 SQL 表定义提取，Python 迁移文件仅提取元数据
- 如果需要支持 SQLAlchemy 表定义提取，需要额外的解析逻辑

### 3. 迁移文件检测策略
- SQL 文件 (.sql): 直接扫描
- Python 文件 (.py): 仅在路径包含 "alembic", "migration", "versions" 时扫描
- 避免将普通 schema.py 文件误识别为迁移文件

## 测试结果
```
tests/test_database_migrations.py ............                           [ 75%]
tests/test_scanner_artifacts.py ...                                      [ 93%]
tests/test_scanner_normalization.py .                                    [100%]
============================== 16 passed in 0.11s
```

## 编译验证
`uv run repo-wiki --help` - 通过
