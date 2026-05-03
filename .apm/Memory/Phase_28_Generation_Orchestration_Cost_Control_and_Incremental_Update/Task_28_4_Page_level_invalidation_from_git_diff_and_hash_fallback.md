---
agent: "Agent_IndexGraph"
task_ref: "Task 28.4 - Page-level invalidation from git diff and hash fallback"
status: "Completed"
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 28.4 - Page-level invalidation from git diff and hash fallback

## Summary
已实现页面级失效能力：优先用 git diff 检测改动，git 无改动或不可用时回退到哈希比对；并通过 evidence span/source map 反向映射受影响页面，仅重置受影响页面为可再生状态，不触发整 run 重生。

## Details
- 依赖集成：
  - 阅读并对接 `generation_scheduler.py` 的页面执行模型（基于 `get_pending_pages()` 调度）。
  - 复用 Phase 12.4 的增量失效思路，并结合当前 generation state machine 做页面粒度恢复。
- 关键实现（`repo_wiki/orchestration/generation_invalidation.py`）：
  - 修复 git diff 清洁判断语义（`is_clean`）。
  - git 变更检测补充 untracked 文件纳入。
  - 文件哈希由 MD5 升级到 SHA256。
  - 新增 `invalidate_with_git_or_hash_fallback()`：git-diff 优先，hash fallback 次之。
  - 新增 evidence 驱动映射 `_map_file_to_pages_via_evidence()`：通过 runtime SQLite 的 `evidence_span` + `page_source_map` 定位受影响页面。
  - 失效动作从“skip”改为“重置为 pending”，确保仅受影响页面进入再生成队列。
- 状态机配套（`repo_wiki/orchestration/generation_state.py`）：
  - 新增 `reset_page_for_regeneration()`，用于将页面重置到 `pending`，清理完成标记并保留运行上下文。
- 验证“改单服务仅影响相关页面”：
  - 新增测试覆盖服务 A 改动只失效服务 A 页面，服务 B 与 overview 不受影响。

## Output
- Modified: `repo_wiki/orchestration/generation_invalidation.py`
- Modified: `repo_wiki/orchestration/generation_state.py`
- Modified: `tests/test_page_invalidation.py`
- Test run:
  - `pytest tests/test_page_invalidation.py tests/test_generation_state_machine.py -q`
  - 结果：全部通过

## Issues
None

## Next Steps
None
