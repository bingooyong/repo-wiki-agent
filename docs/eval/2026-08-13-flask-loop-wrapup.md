# Flask wiki 质量回路 wrap-up

**日期：** 2026-08-13 CST  
**对照：** pallets/flask `2a8a38b` × MiniMax-M3 × repo-wiki `98aa8bd`（PR **#37** 已合并：templates 进 wheel、citation 路径过长、LLM 页超时 20s→YAML/300s cap）

## 本回路已合并

- **#37**（`98aa8bd`）：packaged templates、generate 可收尾、`page_timeout_seconds=180`。round-2 `init`+`generate` 成功，84 页 + `manifest.json`。

## 残留

- MiniMax **529** → 22 fallback，provider 被熔断；另 42 页出现 “LLM composer did not return content”。
- `init` 写入对照仓的 `docs/00-*.md` stub 被当作证据，overview 把 Flask 说成知识管理平台。
- 扫描器把 `docs/` `tests/` `examples/` 标成 `api-server` / 业务模块；`Python服务.md` 仍把 examples 路由当产品 API。
- 04 框架空态已生效（不编造 `/health` `/webhook` `/items`），但 qoder 页计划仍含网关/K8s/健康检查。
- run-scoped verify：**12 HARD / 0 SOFT**。citation 458→31，coverage 0%→15%。质量 JSON 在 `meta/` 但 HARD 仍报 missing。dirty-worktree 为 eval 产物。

## 第三语料建议

**要，且应是小型 FastAPI 应用（不是 fastapi/fastapi）。** FastAPI RealWorld 第一轮评测见 `docs/eval/2026-08-13-fastapi-realworld-round1.md`。不要 push pallets/flask，不要把 Flask 加为 submodule。
