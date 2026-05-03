---
agent: Agent_PlatformCore
task_ref: Task_33_X_Page_floor_fix
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Fix 120 page floor

## Summary

Removed the hard-coded **120** minimum planned pages and the **`max(120, env)`** behavior on `REPO_WIKI_QODER_LIKE_MAX_PAGES`. Introduced **`QoderLikeConfig`** (`qoder_like.min_pages` default **24**, `max_pages` default **220**) with **`REPO_WIKI_QODER_LIKE_MIN_PAGES`** / **`REPO_WIKI_QODER_LIKE_MAX_PAGES`** overrides. Small repos no longer get inflated to ~120 filler pages unless explicitly configured.

## Details

1. **定位**：`RepoWikiService._build_qoder_like_page_plan` 曾传入 `minimum_pages=120`；`_normalize_qoder_like_plan` 在不足时用 deep-dive 顶满；`_resolve_qoder_like_max_pages` 使用 `return max(120, value)`；`repo-wiki improve` 使用 `max(max_pages, 120)`。
2. **设计原因（旧）**：120 与 Qoder 体量 / Atlas 试点对齐，作为「最小覆盖率」经验值，但对微型仓库过度。
3. **实现**：新增 `_resolve_qoder_like_min_pages`、`_clamp_qoder_page_budget`；编排时 `min_budget = min(min_pages, max_budget)`；CLI 仅 `max(1, max_pages)`。
4. **验证**：`tests/test_qoder_like_page_floor.py` + 既有 `tests/test_qoder_like_profile.py`（小 fixture）通过；未在 workspace 内挂载 agent-skills 仓库，行为由配置与单测覆盖。
5. **文档**：`docs/configuration.md` §5.3；`docs/go-no-go-dossier.md` P1 行更新为已缓解。

## Output

- `repo_wiki/core/config.py`：`QoderLikeConfig`、`RepoWikiConfig.qoder_like`
- `repo_wiki/orchestration/service.py`：页预算解析与 `_build_qoder_like_page_plan` 接线
- `repo_wiki/cli.py`：`improve` 子命令环境注入
- `docs/configuration.md`、`docs/go-no-go-dossier.md`
- `tests/test_qoder_like_page_floor.py`

## Issues

None

## Next Steps

None
