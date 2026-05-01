---
agent: "Agent_IndexGraph"
task_ref: "Task 27.3 - Manifest navigation tree and commit metadata"
status: "Completed"
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 27.3 - Manifest navigation tree and commit metadata

## Summary
已完成 manifest 导航树与提交元数据增强：写入 `navigation_tree`、`page_registry`、`wiki_git_commit`、`target_git_commit`，并在 git 不可用时回退到可复现哈希，同时补充 stale-detection 元数据和回归测试。

## Details
- 阅读并复用了 `ContentLayoutWriter.build_manifest_content()` 与 `build_navigation_tree()` 的输出契约，确保 manifest 中 `navigation_tree` / `page_registry` 与 content 实际落盘一致。
- 对接了 Task 12.2 的 SQLite 导航上下文（`runtime_store` 中 nav graph/doc hierarchy 结构）以确认本任务 manifest 字段命名与导航语义兼容既有 runtime 结构。
- 在 `eval_layout` 中新增 revision 解析能力：优先使用 git commit（full/short），失败时使用目录内容哈希回退，保证无 git 环境也能产出稳定 revision 标识。
- 在 `generate_manifest()` 中新增并写入：
  - `target_revision_source`
  - `wiki_revision_source`
  - `stale_detection`（含 `strategy` 与 `is_stale`）
- 在 `RepoWikiService.generate()` 与 `_generate_isolated_eval()` 中接入 revision fallback，并在 isolated 路径写入 `target_head_before/after` 与 `target_dirty`。
- 增加 stale-detection 与 manifest 兼容性测试，验证 hash fallback 与新字段存在性、结构合法性。

## Output
- Modified: `repo_wiki/orchestration/eval_layout.py`
- Modified: `repo_wiki/orchestration/service.py`
- Modified: `tests/test_eval_layout.py`
- Modified: `tests/test_eval_manifest.py`
- Test run:
  - `pytest tests/test_eval_layout.py tests/test_eval_manifest.py tests/test_content_layout_writer.py -q`
  - 结果：全部通过

## Issues
None

## Next Steps
None
