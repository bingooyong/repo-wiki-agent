# repo-wiki MVP — 日志指南（Logging Guide）

**文档编号：** DOC-011
**版本：** v1.0.0
**创建日期：** 2026-05-03
**最后更新：** 2026-05-03

---

## 1. 日志输出

### 1.1 CLI 日志级别

| 级别 | 说明 | 触发方式 |
|------|------|---------|
| ERROR | 错误信息 | 默认 |
| WARNING | 警告信息 | 默认 |
| INFO | 一般信息 | `--verbose` |
| DEBUG | 调试信息 | `--debug` |

### 1.2 环境变量控制

```bash
# 启用 debug 日志
export REPO_WIKI_DEBUG=1

# 启用详细输出
uv run repo-wiki generate --verbose
```

---

## 2. 日志位置

### 2.1 标准输出

CLI 默认输出到 stdout：
```bash
uv run repo-wiki generate 2>&1 | tee generate.log
```

### 2.2 SQLite 日志

Verify 运行记录存储在 SQLite：
```sql
sqlite3 .repo-wiki/state.sqlite3 "SELECT * FROM verify_runs ORDER BY executed_at DESC LIMIT 10;"
```

### 2.3 生成日志

LLM 生成过程日志：
```
.repo-agent-eval/<run>/reports/generate.log
```

---

## 3. 关键日志事件

### 3.1 生成事件

| 事件 | 日志关键词 |
|------|-----------|
| 生成开始 | `Starting generation for run <run-id>` |
| 页面完成 | `Page <page_id> completed` |
| 生成失败 | `Page <page_id> failed: <error>` |
| 生成完成 | `Generation completed: <n> pages` |

### 3.2 Verify 事件

| 事件 | 日志关键词 |
|------|-----------|
| Verify 开始 | `Starting verify for run <run-id>` |
| 检查项 | `<check_name>: PASS/FAIL` |
| Verify 完成 | `Verify grade: <grade>, exit_code: <code>` |

---

## 4. 日志分析

### 4.1 常见错误分析

**LLM API 错误：**
```
ERROR: LLM API error: 401 Unauthorized
→ 检查 API Key 配置
```

**SQLite 锁定：**
```
ERROR: database is locked
→ 减少并发数，避免多进程同时写入
```

**磁盘空间不足：**
```
ERROR: No space left on device
→ 清理 .repo-agent-eval/ 旧输出
```

### 4.2 日志提取脚本

```bash
# 提取所有失败页面
grep "failed:" generate.log | awk '{print $4}'

# 统计各检查项通过率
grep -E "(PASS|FAIL):" verify.log | sort | uniq -c
```

---

## 5. 参考文档

> 详见 [operations-runbook.md](./operations-runbook.md) 运维手册。
> 详见 [incident-response-runbook.md](./incident-response-runbook.md) 应急响应手册。