---
agent: Agent_IndexGraph
task_ref: Task 12.3
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 12.3 - Verify and compare persistence with trend analysis

## Summary

在 Task 12.2 的 SQLite 表基础上，实现了 verify 和 compare 运行结果的持久化存储，并支持趋势分析查询。

## Details

### 1. Verify Run 持久化

**save_verify_run():**
- 接收 verify_result dict 和 duration_ms
- 提取 summary 中的 grade, exit_code, hard/soft gate failures
- 计算 score = pass_count / total
- 存储 hard_gate_codes_json 和 soft_gate_codes_json 数组
- 存储 full_result_json 完整审计轨迹

**list_verify_runs():**
- 支持按 target_path 过滤
- 默认返回最近 100 条记录
- 按 created_at DESC 排序

**get_verify_trend():**
- 返回最近 N 条 verify 运行的分数和错误码趋势
- 用于检测回归或改进

### 2. Compare Run 持久化

**save_compare_run():**
- 存储 overall_score, overall_band
- 分离 structural_score 和 quality_score
- 存储 delta_type_json 和 scores_json 用于维度分析
- 存储 gaps_json 用于详细问题追踪
- acceptance_blocked 布尔值用于回归检测

**list_compare_runs():**
- 支持按 target_path 过滤
- 返回完整 compare 运行历史

**get_compare_trend():**
- 返回最近 N 条 compare 运行的分数趋势
- 分离 structural 和 quality 维度趋势

### 3. 与单次运行工作流兼容

- verify() 和 compare() 仍然返回即时结果
- 结果可通过 save_verify_run()/save_compare_run() 持久化
- 不影响现有的 CI 模式工作流

### 4. 本地优先和确定性

- 所有数据存储在 .repo-wiki/index/runtime.sqlite3
- 不依赖外部服务
- 时间戳使用 ISO 格式保证确定性

### 5. 趋势分析查询

**Verify 趋势:**
- 分数变化: score 从低到高或从高到低
- hard_gate_failures 变化: 回归检测
- soft_gate_failures 变化: 质量漂移检测

**Compare 趋势:**
- overall_score 趋势: 整体质量变化
- structural_score 趋势: 结构性差距变化
- quality_score 趋势: 质量性差距变化
- acceptance_blocked 趋势: 阻塞问题变化

## Output

- 扩展 `/repo_wiki/orchestration/runtime_store.py`:
  - save_verify_run(), list_verify_runs(), get_verify_run(), get_verify_trend()
  - save_compare_run(), list_compare_runs(), get_compare_trend()
- 所有方法支持持久化和历史分析

## Issues

None

## Next Steps

Task 12.4 依赖本任务的 verify_run_details 和 compare_run_details 表来检测 evidence staleness 并触发 page invalidation。