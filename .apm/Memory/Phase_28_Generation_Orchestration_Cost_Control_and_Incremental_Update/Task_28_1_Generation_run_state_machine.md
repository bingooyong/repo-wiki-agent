---
agent: "Agent_IndexGraph"
task_ref: "Task 28.1 - Generation run state machine"
status: "Completed"
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 28.1 - Generation run state machine

## Summary
已完成生成运行状态机增强并落库：支持 `pending/running/completed/failed/retryable`，实现页面级状态跟踪与中断恢复，恢复时不会重新生成已完成页面。

## Details
- 基于既有 SQLite 结构（Task 12.2 的 runtime/schema 约定）复核并延续了 `generation_runs` + `page_generation_states` 持久化模型。
- 在 `repo_wiki/orchestration/generation_state.py` 中补充 run 级 `RunState.RETRYABLE`，并在 `complete_run()` 中根据页面聚合状态将 run 标记为 `retryable`。
- 扩展 `_get_run_stats()`，新增 `retryable` 统计维度，保证 run 终态判断可覆盖“失败但可重试”的路径。
- 新增 `resume_run()`：
  - 将中断时处于 `running` 的页面转为 `retryable`
  - 保持 `completed/skipped` 页面不变
  - run 状态重置为 `running`，以便继续调度
- 更新 `get_resumable_runs()`，纳入 `retryable` run。
- 页面级状态跟踪沿用并验证 `pending/running/completed/failed/retryable/skipped`，满足“run 内页面状态追踪”要求。

## Output
- Modified: `repo_wiki/orchestration/generation_state.py`
- Modified: `tests/test_generation_state_machine.py`
- Test run:
  - `pytest tests/test_generation_state_machine.py tests/test_generation_scheduler.py -q`
  - 结果：全部通过

## Issues
None

## Next Steps
None
