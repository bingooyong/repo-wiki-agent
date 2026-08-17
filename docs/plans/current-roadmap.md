# 当前规划（2026-08）

**状态：** 现行
**范围：** 单库 local-first Repo Wiki。不是企业知识引擎。
**关联：** `docs/repo-wiki-phase-09-12-roadmap.md`（中期替代 Qoder 的 Phase 09–12）、`docs/plans/display-and-wiki-generation-optimization-roadmap.md`（展示层 backlog）、`docs/00-overview.md`

2026-08-14 维护者锁定了下一周期：本仓继续做 local-first、Qoder-like 的 **Repo Wiki**（一个仓库 → 一份可验收 Wiki）。本周期不启动 RAGFlow、QMind、团队云共享、多项目知识或「十万文件」宣传。知识卡片现在不需要；若以后做，从已可信的 Wiki 页派生。

已有长程文档 `docs/repo-wiki-phase-09-12-roadmap.md`（Phase 09–12，替代 Qoder）保持有效。本文是它前面的现行周期计划，做完单库 Wiki 再进入那份中期路线。

## 定位

`repo-wiki` 把**一个**仓库做成可验收的结构化 Wiki。三条入口共用同一 CLI：

- Python CLI：`init → index → generate --profile qoder-like → verify → release-publish`
- VS Code/Cursor：`extensions/repo-wiki-browser` 浏览 READY release
- Codex plugin（已落地，`plugins/repo-wiki`，#50）：skills-only，`repo-wiki` / `repo-wiki-generate` / `repo-wiki-verify` / `repo-wiki-maintain`。复用本机已装 CLI。生成停在验证过的 candidate；替换本地 READY 需 G005 证据并确认同一 run ID。v1 不加 MCP。

对照 Qoder Desktop 的「Repo Wiki / Knowledge Card / Memory」三页：本仓只对齐 **Repo Wiki**。

## 已经落地（到 2026-08-14 main）

- qoder-like 隔离输出与 HARD/SOFT 门禁（不放宽）
- FastAPI 对照闭环里已修：路由前缀 / `settings.api_prefix`、产品身份（README/pyproject → overview）、`file:` 引用、mounted `/api` owner 绑定（#43–#59）
- Codex plugin #50；R8 评测见 `docs/eval/2026-08-14-fastapi-realworld-round8.md`；R9 评测见 `docs/eval/2026-08-14-fastapi-realworld-round9.md`；R10 评测见 `docs/eval/2026-08-14-fastapi-realworld-round10.md`；R12 评测见 `docs/eval/2026-08-15-fastapi-realworld-round12.md`

## 本周期（先把单库 Wiki 做准）

按这个顺序，不要并行开企业平台：

1. 合或落地 #61：剥 `relpath:` 占位引用，并改掉 prompt 里教模型抄模板的句子
2. 去掉 tests/docs 被当成产品服务，以及 API网关 / 前端应用等幻觉页
3. 落盘前剥模型泄漏的 `<think>`
4. 模型 owner、API/ER mermaid、引用覆盖率（对照仓约 42%，门仍是 95%）
5. 再跑一轮 FastAPI RealWorld，确认 #59+#61 后 owner / citation 是否下降
6. 宿主补齐：Codex 本地 marketplace 装法写清楚；VS Code 生成进度 / 失败原因 / 一键 `release-publish`（可引用 display roadmap 的 P0，不要重写整份）

## 中期（仍在本仓，不另起产品）

执行已有 `docs/repo-wiki-phase-09-12-roadmap.md`：

- Phase 09 输出 contract 与导航
- Phase 10 叙事与聚合
- Phase 11 验收与 baseline
- Phase 12 SQLite 本地知识运行时（增量、证据、检索）

未满足该文档「替代 qoder 的阶段性判断标准」前，对外定位仍是「具备底座的本地实现，不是完整替代」。

## 本周期不做

这些是 Qoder 知识引擎 / QMind 的上一层产品，等单库 Wiki 可信、且有真实企业库需求时再**单独立项**，不要写进本周期任务：

- 对接企业 RAGFlow
- 团队项目知识共享、多项目知识共享、云端 QMind
- 知识卡片（现在不需要；以后如做，从已可信的 Wiki 页派生，不先做一种新文档类型）
- 「十万文件大库」宣传目标（尚未在中型对照仓上把幻觉和引用做干净）
- 为通过率放宽 HARD/SOFT
- Codex 自动发布 READY；本周期不加 MCP

## 退出本周期的标准

- FastAPI RealWorld（或同等对照）上：产品身份稳定、mounted 路由正确、`file:`/`relpath:` 引用残差清掉、幻觉页明显下降
- Codex / VS Code 能按 README 走通 generate → verify → 浏览
- Phase 09 可以开工，而不是被生成质量拖住
