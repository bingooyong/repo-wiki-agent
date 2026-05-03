# repo-wiki MVP — 运维手册（Operations Runbook）

**文档编号：** DOC-009
**版本：** v1.0.0
**创建日期：** 2026-05-03
**最后更新：** 2026-05-03

---

## 1. 日常运维

### 1.1 每日检查项

- [ ] 检查 `uv run repo-wiki --help` 是否正常
- [ ] 检查 `.repo-wiki/` 目录磁盘使用
- [ ] 检查 ChromaDB 向量库大小
- [ ] 查看最近的 verify 结果

### 1.2 每周检查项

- [ ] 分析 verify 报告 trend
- [ ] 检查 SQLite 数据库大小，必要时 VACUUM
- [ ] 审查 LLM 成本（如有日志）

---

## 2. 生成操作

### 2.1 启动 Qoder-like 生成

```bash
# 设置 LLM API Key
export MINIMAX_API_KEY="your_key_here"

# 进入目标仓库
cd /path/to/your-repo

# 初始化（如首次）
uv run repo-wiki init

# 生成 qoder-like wiki
uv run repo-wiki generate --profile qoder-like --run-id weekly-run

# 验证质量
uv run repo-wiki verify --profile qoder-like --ci --output weekly-run
```

### 2.2 增量更新

```bash
# 检测 git 变更并更新
uv run repo-wiki update --profile qoder-like --run-id weekly-run

# 或使用新的 run-id
uv run repo-wiki update --profile qoder-like --run-id incremental-run
```

### 2.3 中断恢复

```bash
# 查看可恢复的运行
uv run repo-wiki list-runs

# 恢复特定运行
uv run repo-wiki resume --run-id <run-id>
```

---

## 3. 状态管理

### 3.1 清理旧状态

```bash
# 删除 SQLite 数据库（危险！）
rm .repo-wiki/state.sqlite3

# 删除 ChromaDB 向量库
rm -rf .repo-wiki/chroma_db/

# 重新初始化
uv run repo-wiki init
```

### 3.2 导出状态

```bash
# 备份 SQLite
cp .repo-wiki/state.sqlite3 .repo-wiki/state.sqlite3.backup

# 导出 source-of-truth 产物
tar -czf source-of-truth-backup.tar.gz ai/source-of-truth/
```

### 3.3 SQLite 维护

```bash
# Vacuum 清理碎片
sqlite3 .repo-wiki/state.sqlite3 "VACUUM;"

# 查看表大小
sqlite3 .repo-wiki/state.sqlite3 "SELECT name, page_count * page_size / 1024 as size_kb FROM dbstat;"
```

---

## 4. 监控

### 4.1 关键指标

| 指标 | 告警阈值 |
|------|---------|
| verify grade | FAIL 时告警 |
| 生成失败页面数 | > 0 时告警 |
| SQLite 大小 | > 1GB 时告警 |
| 磁盘使用率 | > 80% 时告警 |

### 4.2 日志位置

- CLI 输出：stdout/stderr
- SQLite：`.repo-wiki/state.sqlite3`
- Verify 报告：`.repo-agent-eval/<run>/reports/`

---

## 5. 参考文档

> 详见 [deployment-guide.md](./deployment-guide.md) 部署指南。
> 详见 [incident-response-runbook.md](./incident-response-runbook.md) 应急响应手册。
> 详见 [logging-guide.md](./logging-guide.md) 日志指南。