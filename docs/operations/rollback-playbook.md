# Rollback Playbook

**文档属性**: 运营手册
**版本**: 1.0
**日期**: 2026-04-25
**Agent**: Agent_QualityRelease

## 1. 目的

本手册提供替换发布失败时的回滚执行指南。回滚是将系统恢复到上一稳定状态的过程，确保业务连续性。

## 2. 回滚场景

### 2.1 场景 A: 生成失败回滚

**症状**: `repo-wiki verify --ci` 返回 exit_code=1（HARD gate 失败）

**回滚步骤**:
1. 停止当前生成任务
2. 评估失败原因
3. 恢复到上一个成功版本

```bash
# 1. 停止任务
pkill -f "repo-wiki.*generate"
# 或 Ctrl+C

# 2. 找到最近的成功备份
ls -la .repo-wiki/backups/
# 选择最近的成功版本

# 3. 备份当前问题版本（不要直接删除）
cp -r docs docs.failed.$(date +%Y%m%d%H%M%S)
cp -r ai ai.failed.$(date +%Y%m%d%H%M%S)

# 4. 恢复上一版本
BACKUP_DIR=".repo-wiki/backups/2026-04-24-143000"
cp -r $BACKUP_DIR/docs docs
cp -r $BACKUP_DIR/ai ai

# 5. 验证恢复
repo-wiki verify --ci
```

### 2.2 场景 B: 质量问题回滚

**症状**: `repo-wiki compare` 评分下降 > 15%，或多个 SOFT gate 失败

**回滚步骤**:
1. 暂停生成任务
2. 分析质量下降原因
3. 决定是否回滚
4. 执行回滚（如需要）

```bash
# 1. 暂停生成
touch .repo-wiki/.pause_generation

# 2. 分析
repo-wiki compare --baseline qoder-style/ --target docs/
# 检查评分变化

# 3. 如果决定回滚
BACKUP_DIR=".repo-wiki/backups/2026-04-24-090000"
cp -r $BACKUP_DIR/docs docs.quality_rollback.$(date +%Y%m%d)
cp -r $BACKUP_DIR/docs $BACKUP_DIR

# 4. 重新验证
repo-wiki verify --ci
```

### 2.3 场景 C: 关键文档损坏

**症状**: 导航链接大面积断裂，或核心文档丢失

**回滚步骤**:
1. 立即停止所有写操作
2. 检查备份完整性
3. 完全回滚
4. 触发完整性检查

```bash
# 1. 立即停止
touch .repo-wiki/.emergency_stop

# 2. 检查备份
ls -la .repo-wiki/backups/
# 确认备份完整性

# 3. 执行完全回滚
BACKUP_DIR=".repo-wiki/backups/2026-04-24-080000"
rm -rf docs docs.broken
cp -r $BACKUP_DIR/docs docs

# 4. 验证完整性
repo-wiki verify --ci
repo-wiki compare --baseline qoder-style/ --target docs/

# 5. 发送通知
echo "CRITICAL: 回滚完成，docs/ 已恢复到 $BACKUP_DIR" | tee /dev/stderr
```

## 3. 回滚决策矩阵

| 严重级别 | 触发条件 | 响应时间 | 回滚范围 | 决策者 |
|----------|----------|----------|----------|--------|
| **P0 - CRITICAL** | HARD gate > 20% 失败率 | 立即 | 全量回滚 | Manager |
| **P1 - HIGH** | 评分下降 > 15% | 15 分钟 | 受影响模块 | Agent_QualityRelease |
| **P2 - MEDIUM** | SOFT gate > 3 个失败 | 30 分钟 | 记录观察 | Implementation Agent |
| **P3 - LOW** | 单一轻微问题 | 下一批次 | 无需回滚 | - |

## 4. 回滚后验证

回滚完成后必须执行以下验证：

```bash
# 1. 结构验证
repo-wiki verify --ci

# 2. 基线对比
repo-wiki compare --baseline qoder-style/ --target docs/ --output compare-result.json

# 3. 检查备份完整性
ls -la .repo-wiki/backups/

# 4. 确认决策日志
cat .apm/logs/rollback-decisions.log
```

### 验证检查点

- [ ] `verify --ci` 返回 grade: PASS
- [ ] 所有 HARD gate 通过
- [ ] 导航链接无损坏
- [ ] compare 评分恢复到回滚前水平

## 5. 通知机制

回滚发生时必须通知：

| 通知对象 | 通知方式 | 内容 |
|----------|----------|------|
| Manager Agent | APM Memory Log | 回滚原因、影响范围、恢复状态 |
| 相关 Agent | 消息 | 当前任务暂停，等待进一步指示 |
| Human User | CLI 输出 | 回滚完成，需要确认 |

```bash
# 通知示例
echo "[ROLLBACK] 已恢复到 2026-04-24-080000 版本"
echo "[ROLLBACK] HARD gate 失败已解决，verify --ci 返回 PASS"
echo "[ROLLBACK] 等待 Manager 确认后继续"
```

## 6. 事后复盘

回滚完成后 24 小时内必须完成复盘：

### 复盘报告模板

```yaml
---
rollback_report:
  date: "YYYY-MM-DD"
  trigger: "描述触发条件"
  severity: P0|P1|P2|P3
  affected_modules: [list]
  rollback_duration: "X minutes"
  verification_passed: true|false
  root_cause: "分析根本原因"
  prevention_actions:
    - "将要采取的预防措施"
  follow_up_tasks: [task IDs]
---
```

### 复盘要点

1. **触发分析**: 什么条件触发了回滚？
2. **时间线**: 从发现问题到恢复花了多少时间？
3. **影响评估**: 哪些模块/功能受到影响？
4. **根因分析**: 导致问题的根本原因是什么？
5. **预防措施**: 未来如何避免类似问题？
6. **改进建议**: 门禁策略是否需要调整？

## 7. 快速参考卡片

```
╔════════════════════════════════════════════════════════════════╗
║                    ROLLBACK QUICK REFERENCE                    ║
╠════════════════════════════════════════════════════════════════╣
║ CRITICAL (HARD gate > 20%):                                    ║
║   → 立即停止 → 全量回滚 → 通知 Manager                         ║
║                                                                ║
║ HIGH (评分下降 > 15%):                                         ║
║   → 暂停 → 评估 → 决定是否回滚 → 执行 → 验证                   ║
║                                                                ║
║ MEDIUM (SOFT gates > 3):                                       ║
║   → 记录 → 继续监控 → 下一批次评估                             ║
║                                                                ║
║ KEY COMMANDS:                                                  ║
║   repo-wiki verify --ci        # 验证结构                       ║
║   repo-wiki compare ...        # 对比基线                       ║
║   .repo-wiki/backups/          # 备份位置                       ║
╚════════════════════════════════════════════════════════════════╝
```

## 8. 备份保留策略

| 备份类型 | 保留时间 | 位置 |
|----------|----------|------|
| 成功版本备份 | 30 天 | `.repo-wiki/backups/YYYY-MM-DD-HHMMSS/` |
| 问题版本备份 | 7 天 | `docs.failed.*/` (在原位置) |
| 回滚前备份 | 永久 | 直到下一备份周期清理 |

## 9. 紧急联系人

| 角色 | Agent | 职责 |
|------|-------|------|
| 发布决策 | Manager Agent | 最终回滚授权 |
| 质量验证 | Agent_QualityRelease | 验证恢复状态 |
| CI 配置 | Agent_AdapterGovernance | profile 配置变更 |
| 技术执行 | Human User | 手动操作确认 |