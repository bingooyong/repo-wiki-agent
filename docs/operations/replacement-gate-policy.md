# Replacement Gate Policy and Rollback Playbook

**文档属性**: 运营策略
**版本**: 1.0
**日期**: 2026-04-25
**Agent**: Agent_QualityRelease

## 1. 背景

Phase 16 是 Qoder-Replacement 的最终阶段。本文档定义了替代发布的正式门禁策略和回滚预案，确保发布可控、可追溯、可回退。

基于 Phase 11 的 hard/soft gate 设计和 Phase 14-15 的外部基线校准结果，构建完整的替换决策体系。

## 2. 门禁策略定义

### 2.1 门禁类型

| 类型 | 描述 | 阻塞级别 | 默认行为 |
|------|------|----------|----------|
| **HARD Gate** | 结构失败，必须修复 | 阻塞发布 | fail_on_hard=True |
| **SOFT Gate** | 质量问题，建议改进 | 非阻塞 | warn_on_soft=True |
| **TRANSITIONAL** | 兼容性过渡期宽限 | 条件阻塞 | 依赖 profile 配置 |

### 2.2 HARD Gate 判定标准

HARD Gate 失败项（来自 verify 命令 ReasonCode）：

```python
HARD_GATE_CODES = {
    "STRUCT_SECTION_DIR_MISSING",      # 缺少 section 目录
    "STRUCT_MISSING_SECTIONS",         # 缺少必需 section 页
    "STRUCT_NAVIGATION_BROKEN",        # 导航链接损坏
    "STRUCT_NAV_BAD_DEPTH",            # 路径深度错误
    "STRUCT_NAV_TARGET_MISSING",       # 引用的文件不存在
    "CONTENT_EMPTY",                   # 空文件
}
```

### 2.3 SOFT Gate 判定标准

SOFT Gate 失败项（质量警告）：

```python
SOFT_GATE_CODES = {
    "CONTENT_LIST_ONLY",               # 纯列表无 prose
    "CONTENT_TOO_SHORT",               # prose 不足
    "CONTENT_MISSING_SECTIONS",        # 缺少子章节
    "AGG_API_NOT_GROUPED",             # API 未聚合
    "AGG_API_ENDPOINT_DUMP",          # API 端点过多
    "AGG_DM_NOT_GROUPED",             # 数据模型未聚合
    "AGG_DM_MODEL_DUMP",              # 模型条目过多
    "ARCH_MERMAID_MISSING",           # 缺少 Mermaid 图
    "ARCH_MERMAID_INSUFFICIENT",      # Mermaid 图表不足
    "ARCH_LAYER_EXPLANATION_MISSING",  # 缺少三层架构说明
}
```

### 2.4 TRANSITIONAL 判定标准

TRANSITIONAL 状态适用于从旧系统迁移到新系统的过渡期：

| 条件 | 判定 |
|------|------|
| legacy Qxx/Sxx section 满足兼容性阈值 | TRANSITIONAL |
| 新旧格式混合存在 | TRANSITIONAL |
| 部分验证规则尚未覆盖 | TRANSITIONAL |

## 3. 证据链接规范

每个门禁判定必须链接到可验证的证据：

### 3.1 verify 命令证据

```yaml
verify_result:
  grade: FAIL|PASS|WARN
  exit_code: 0|1|2
  hard_gate_failures: ["STRUCT_MISSING_SECTIONS"]
  soft_gate_failures: ["CONTENT_TOO_SHORT"]
  checks:
    - name: sections-exist
      status: FAIL
      reason_code: STRUCT_MISSING_SECTIONS
      gate_type: HARD
      evidence_path: docs/sections/
```

### 3.2 compare 命令证据

```yaml
baseline_compare_result:
  overall_score: 0.73
  score_band: GOOD
  acceptance_blocked: false
  dimensions:
    - dimension: directory_hierarchy
      status: PASS
      score: 1.0
      delta_type: STRUCTURAL
    - dimension: section_coverage
      status: PARTIAL
      score: 0.5
      delta_type: STRUCTURAL
```

### 3.3 runtime 证据

```yaml
runtime_evidence:
  sqlite_state_db: .repo-wiki/state.sqlite3
  last_verified_at: "2026-04-25T10:30:00Z"
  incremental_changes: ["src/billing/"]
```

### 3.4 visual 证据

```yaml
visual_evidence:
  eval_output: .repo-agent-eval/repo-agent-2026-04-25/
  wiki_viewer_snapshot: docs/sections/.snapshot/
  benchmark_matrix: .repo-agent-eval/benchmark-matrix.json
```

## 4. 回滚策略

### 4.1 回滚触发条件

| 触发条件 | 严重级别 | 回滚动作 |
|----------|----------|----------|
| HARD gate 失败率 > 20% | CRITICAL | 立即回滚到上一稳定版本 |
| 整体评分下降 > 15% | CRITICAL | 暂停替换，恢复基线 |
| 关键文档损坏（导航断裂） | HIGH | 停止生成，回滚输出 |
| 试点仓库出现 regression | HIGH | 扩展回滚范围 |
| 超过 3 个 SOFT gate 失败 | MEDIUM | 记录但不放行 |
| 用户报告可读性问题集中 | MEDIUM | 触发内容审查 |

### 4.2 回滚决策权限

| 决策者 | 权限范围 |
|--------|----------|
| Agent_QualityRelease | 批准/拒绝 PILOT 阶段 |
| Agent_AdapterGovernance | CI profile 配置变更 |
| Manager Agent | 全量回滚决策 |
| Human User | 最终回滚确认 |

### 4.3 回滚动作矩阵

```
触发 → 评估 → 决策 → 执行 → 验证

[CRITICAL 触发]
  → 立即停止生成
  → 恢复上一版本备份
  → 通知相关 Agent
  → 运行 verify 验证
  → 报告 Manager

[HIGH 触发]
  → 暂停当前批处理
  → 评估影响范围
  → 决定是否回滚
  → 执行回滚（如需要）
  → 记录事件

[MEDIUM 触发]
  → 记录警告
  → 继续监控
  → 下一批次评估
```

### 4.4 回滚执行步骤

1. **立即止血**
   - 停止正在运行的生成任务
   - 锁定当前输出版本

2. **评估影响**
   - 检查 `.repo-wiki/backups/` 找到上一稳定版本
   - 评估受影响的功能模块

3. **执行回滚**
   ```bash
   # 回滚到上一版本
   cp -r .repo-wiki/backups/YYYY-MM-DD-HHMMSS/docs docs.bak
   cp -r .repo-wiki/backups/YYYY-MM-DD-HHMMSS/ai ai.bak
   ```

4. **验证恢复**
   - 运行 `repo-wiki verify --ci`
   - 确认 HARD gate 通过
   - 通知相关方

5. **复盘改进**
   - 分析触发原因
   - 更新门禁规则（如需要）
   - 记录到 Phase 16 决策日志

## 5. Policy Profiles

### 5.1 strict.profile - 生产发布

```yaml
profile: strict
description: 生产环境使用的严格门禁
criteria:
  hard_gate_failures: 0        # 必须无 HARD gate 失败
  soft_gate_failures: 0        # 必须无 SOFT gate 失败
  overall_score: >= 0.85       # 整体评分 >= 85%
  structural_score: >= 0.90    # 结构评分 >= 90%
  quality_score: >= 0.80       # 质量评分 >= 80%
actions:
  on_fail: BLOCK_AND_ROLLBACK
  on_warn: BLOCK_WITH_REVIEW
exit_code_policy:
  0: ALL_PASS
  1: HARD_GATE_FAIL
  2: SOFT_GATE_FAIL
```

### 5.2 transitional.profile - 过渡期

```yaml
profile: transitional
description: 兼容性过渡期使用的宽松门禁
criteria:
  hard_gate_failures: 0
  soft_gate_failures: <= 3
  overall_score: >= 0.70
  acceptance_blocked: false
  legacy_compatibility: true
actions:
  on_fail: REVIEW_AND_APPROVE
  on_warn: ALLOW_WITH_LOG
exit_code_policy:
  0: ALL_PASS
  1: HARD_GATE_FAIL
  2: SOFT_GATE_FAIL (review required)
```

### 5.3 pilot.profile - 试点验证

```yaml
profile: pilot
description: 试点阶段使用的探索性门禁
criteria:
  hard_gate_failures: <= 1
  soft_gate_failures: <= 5
  overall_score: >= 0.60
  pilot_repos: [repo-agent, AI_API_Atlas]
actions:
  on_fail: LOG_AND_CONTINUE
  on_warn: LOG_AND_CONTINUE
exit_code_policy:
  0: ALL_PASS
  1: HARD_GATE_FAIL (log only)
  2: SOFT_GATE_FAIL (log only)
```

## 6. 验证检查清单

### 6.1 发布前检查

- [ ] 所有 HARD gate 通过（exit_code = 0）
- [ ] 整体评分满足 profile 要求
- [ ] compare 结果已保存到 evidence bundle
- [ ] verify JSON 输出已归档
- [ ] 回滚预案已就绪
- [ ] 决策者已确认

### 6.2 回滚后检查

- [ ] 恢复的版本可正常生成
- [ ] verify --ci 返回 PASS
- [ ] compare 评分恢复基线水平
- [ ] 通知所有相关方

### 6.3 决策模板

```yaml
---
decision:
  date: "YYYY-MM-DD"
  profile: strict|transitional|pilot
  overall_score: X.XX
  hard_gates: [list of failures]
  soft_gates: [list of warnings]
  decision: GO|NO-GO|REVIEW
  authority: Agent_QualityRelease|Manager
  evidence_bundle: /path/to/evidence/
---
```

## 7. Legacy Compatibility Mode Coverage Warning

### 7.1 警告背景

Legacy compatibility mode (Q01/Sxx section format) enables side-by-side evaluation of qoder-style navigation structures. However, certain coverage limitations exist that teams must be aware of.

### 7.2 覆盖限制

| 限制项 | 描述 | 影响范围 |
|--------|------|----------|
| QODER_TO_CANONICAL 映射表 | 仅覆盖预定义的 section 别名，不支持动态别名 | Q01-S09 格式 |
| 路径解析 | legacy 格式的嵌套路径解析可能失败 | 深层嵌套的文档 |
| 向后兼容性 | 新功能（如 Phase 13+ 的动态生成）不适用于 legacy 格式 | 增量更新场景 |

### 7.3 已知未覆盖场景

1. **动态别名**: QODER_TO_CANONICAL 映射表不包含用户自定义的 section 别名
2. **嵌套路径**: legacy 格式下的多级嵌套路径 (如 `docs/sections/a/b/c/index.md`) 可能无法正确解析
3. **增量更新**: legacy mode 下的增量更新可能触发不必要的重新生成

### 7.4 缓解措施

```yaml
legacy_compatibility:
  fallback: strict  # 无法解析时降级到 strict 模式
  warn_on_unknown_alias: true  # 遇到未知别名时发出警告
  log_unmapped_nodes: true    # 记录所有未映射的节点
```

### 7.5 验证方法

使用 qoder_adapter 的兼容性检查功能：

```python
from repo_wiki.adapter.qoder_adapter import check_qoder_compatibility

result = check_qoder_compatibility(qoder_data, root_dir)
if not result["compatible"]:
    warnings = result.get("import_result", {}).get("warnings", [])
    for w in warnings:
        if w["code"] == "QODER_NODE_UNMAPPED":
            print(f"Warning: {w['node_id']} not mapped to canonical section")
```

### 7.6 相关文件

- `repo_wiki/adapter/qoder_adapter/__init__.py` - QODER_TO_CANONICAL 映射表定义
- `repo_wiki/generator/contracts.py` - section 别名解析逻辑
- `docs/operations/ci-cutover-template-pack.md` - CI 配置中的 legacy 支持选项

## 8. 文件输出

| 文件 | 描述 |
|------|------|
| `docs/operations/replacement-gate-policy.md` | 本文档 - 门禁策略和回滚预案 |
| `docs/operations/rollback-playbook.md` | 独立回滚执行手册 |
| `docs/operations/policy-profiles.yaml` | 三种 profile 配置 |
| `.apm/Memory/Phase_16/.../Task_16_1_...` | Memory Log |

## 9. 与之前阶段的关系

- **Phase 11**: 提供了 hard/soft gate 的技术基础（GateType, SeverityThreshold）
- **Phase 14**: 提供了外部基线比较和评分机制
- **Phase 15**: 提供了可视化验收和 IDE 集成路径
- **本文档**: 将上述能力整合为可执行的发布策略

## 10. 下一步

本文档为 Task 16.2 提供基础，Task 16.2 将把此策略打包为 CI 模板。