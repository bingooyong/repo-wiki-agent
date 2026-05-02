---
task_ref: "Task 31.1 - Commit freshness preflight"
status: "completed"
important_findings: false
compatibility_issue: false
compatibility_issues: false
---

# Task 31.1 - Commit Freshness Preflight

## 状态: 完成

## 执行时间
2026-05-02

## 任务目标
Record and verify target repository freshness around qoder-like generation.

## 完成的工作

### 1. QODER_STALE_GIT_COMMIT 已有实现
- 位于 `repo_wiki/verifier/qoder_strict_verifier.py` 的 `_check_qoder_stale_commit()` 方法
- 比较当前 git HEAD 与 manifest 中记录的 wiki_git_commit
- 不匹配时触发 `QODER_STALE_GIT_COMMIT` 硬失败

### 2. 新增 QODER_DIRTY_WORKTREE 检测
- 在 `QoderLikeSeverityThreshold.STRICT_HARD_CODES` 中添加了 `QODER_DIRTY_WORKTREE`
- 新增 `_check_qoder_dirty_worktree()` 方法检查工作树是否脏
- 新增 `_git_dirty()` 辅助方法使用 `git status --porcelain` 检测未提交变更
- 脏工作树触发 `QODER_DIRTY_WORKTREE` 硬失败

### 3. 验证检查清单更新
在 `QoderLikeVerifierService.verify()` 中添加了新的检查:
- `_check_qoder_stale_commit()` - 已存在
- `_check_qoder_dirty_worktree()` - 新增

### 4. 测试覆盖
新增 `TestStaleCommitAndDirtyTree` 测试类，包含以下测试:
- `test_dirty_worktree_detected` - 检测脏工作树
- `test_stale_commit_detection` - 检测过期 git commit
- `test_clean_worktree_passes_dirty_check` - 干净工作树无假阳性
- `test_stale_hard_code_is_defined` - QODER_STALE_GIT_COMMIT 已定义
- `test_dirty_worktree_hard_code_is_defined` - QODER_DIRTY_WORKTREE 已定义

## 验证结果

### 编译测试
```
uv run repo-wiki --help  # 成功
```

### 单元测试
```
uv run pytest tests/test_qoder_like_verifier.py tests/test_manifest_navigation.py -v
# 33 passed
```

## 相关文件
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/repo_wiki/verifier/qoder_strict_verifier.py`
- `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent/tests/test_qoder_like_verifier.py`

## 门禁行为
- Strict mode 下，脏工作树会导致验证失败 (grade=FAIL)
- 过期 wiki commit 会导致验证失败 (grade=FAIL)
- 两个错误码都是 HARD 类型，不可忽略

## 备注
- `.qoder/**` 目录在验证时被正确忽略 (read-only eval 输出)
- Target HEAD 元数据通过 manifest.json 的 `wiki_git_commit` 字段记录
- Dirty state 通过 `git status --porcelain` 检测