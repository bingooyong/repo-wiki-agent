# repo-wiki MVP — 应急响应手册（Incident Response Runbook）

**文档编号：** DOC-010
**版本：** v1.0.0
**创建日期：** 2026-05-03
**最后更新：** 2026-05-03

---

## 1. 故障分类

| 级别 | 说明 | 响应时间 |
|------|------|---------|
| P1 | 生成完全失败、verify 持续 FAIL | 立即 |
| P2 | 部分页面失败、偶发错误 | 24h |
| P3 | 性能问题、非阻塞错误 | 72h |

---

## 2. P1 故障处理

### 2.1 生成完全失败

**症状：** `repo-wiki generate` 报错退出，无输出

**诊断步骤：**
1. 检查 LLM API Key：`echo $MINIMAX_API_KEY`
2. 测试 API 连通性：`curl -I https://api.minimax.chat/v1`
3. 查看详细错误：`uv run repo-wiki generate --verbose`

**解决方案：**
- 确认 API Key 正确
- 确认网络可达
- 使用 Mock LLM 验证：`REPO_WIKI_FORCE_MOCK_LLM=1 uv run repo-wiki generate`

### 2.2 Verify 持续 FAIL

**症状：** 所有运行 verify grade 都是 FAIL

**诊断步骤：**
1. 检查具体 reason code：`cat .repo-agent-eval/<run>/reports/strict-verify-output.json`
2. 常见原因：
   - `QODER_PAGE_DUMP`：页面内容列表过重
   - `QODER_PROSE_TOO_LOW`：prose 密度不足 30%
   - `QODER_CONTENT_EMPTY`：生成内容为空

**解决方案：**
- QODER_PAGE_DUMP：使用 Phase 31.2 的 dump-page retry policy
- QODER_PROSE_TOO_LOW：使用 Phase 34 的 prose density repair
- QODER_CONTENT_EMPTY：检查 SQLite path normalization（Phase 31 X fix）

---

## 3. P2 故障处理

### 3.1 部分页面失败

**症状：** 大部分页面生成成功，少量页面失败

**诊断步骤：**
```bash
# 查看失败页面
sqlite3 .repo-wiki/state.sqlite3 "SELECT page_id, title, error_message FROM page_generation_states WHERE status='failed';"
```

**解决方案：**
1. 确认是否可重试：`uv run repo-wiki resume --run-id <run-id>`
2. 或手动修复后重新生成失败的页面

### 3.2 LLM API 限速

**症状：** API 429 Too Many Requests

**解决方案：**
```bash
# 减少并发数
uv run repo-wiki generate --profile qoder-like --concurrency 1

# 或使用 mock
REPO_WIKI_FORCE_MOCK_LLM=1 uv run repo-wiki generate
```

---

## 4. P3 故障处理

### 4.1 性能下降

**症状：** 生成速度明显变慢

**诊断步骤：**
1. 检查磁盘空间：`df -h .repo-wiki/`
2. 检查 SQLite 大小：`ls -lh .repo-wiki/state.sqlite3`
3. Vacuum 清理：`sqlite3 .repo-wiki/state.sqlite3 "VACUUM;"`

### 4.2 ChromaDB 问题

**症状：** 向量检索返回结果为空或不准确

**解决方案：**
```bash
# 删除向量库重建
rm -rf .repo-wiki/chroma_db/
uv run repo-wiki index
```

---

## 5. 回滚操作

### 5.1 回滚到之前的版本

```bash
# 查看 git 历史
git log --oneline -10

# 回滚（谨慎）
git checkout <commit-hash>

# 重新安装
uv pip install -e .
```

### 5.2 回滚生成输出

```bash
# 删除当前输出
rm -rf .repo-agent-eval/<run-id>/

# 使用历史 manifest 重新生成
uv run repo-wiki generate --profile qoder-like --run-id restored-run
```

---

## 6. 联系信息

| 角色 | 职责 | 联系方式 |
|------|------|---------|
| 技术负责人 | 紧急响应 | - |
| DevOps | 基础设施 | - |
| LLM Provider | API 问题 | Minimax/OpenAI 支持 |

---

## 7. 参考文档

> 详见 [operations-runbook.md](./operations-runbook.md) 运维手册。
> 详见 [logging-guide.md](./logging-guide.md) 日志指南。