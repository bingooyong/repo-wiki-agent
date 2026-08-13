# FastAPI RealWorld 对照 Wiki 第二轮评测

**对照仓：** nsidnev/fastapi-realworld-example-app `029eb778`  
**CLI：** repo-wiki `c2407979`（含 PR #42 空 content 重试与 #43 FastAPI 扫描）  
**模型：** MiniMax-M3；timeout 180s；concurrency 2  
**时间：** 2026-08-13 22:42–23:02 CST（compose ≈19m）  
**verify JSON：** `docs/eval/2026-08-13-fastapi-realworld-round2-verify.json`

第一轮评测见 `docs/eval/2026-08-13-fastapi-realworld-round1.md`。

## 生成

| 项 | r1 | r2 |
|---|---|---|
| generate | 89/89 | 89/89 |
| 空壳 “LLM composer did not return content” | 60/89 | **0/89** |
| 529 | 0 | 0 |
| fallback / rejected | 0 | 2（Insufficient prose） |
| endpoints | 11 | **19**（仍无 include_router 前缀） |
| wiki 中 UNRESOLVED | 24 | **0** |

## Verify

13 HARD / 0 SOFT（r1 为 12/0，新加 `QODER_PROSE_TOO_LOW`）。claim coverage 43.5%→51.3%。API aggregation PASS 13/13。无效 citation 22→56（`file:` 前缀）。未放宽阈值。

## Must-check

- Overview **仍不是** Conduit；**没有**「知识管理平台」。
- API参考 **无** UNRESOLVED，**未编造** `/health` `/webhook` `/items`。**仍无** `/users/login` `/articles` 完整前缀（只有 `POST /login` `GET /feed` `GET /`）。handler 错绑已修。
- 数据模型有 User/Comment/Article DTO；ER 仍缺 User/Tag。

## #43 残留

本仓 `include_router` 形态：`get_application()` 内 `FastAPI()`；`application.include_router(api_router, prefix=settings.api_prefix)`（非字面量）；`router.include_router(authentication.router, prefix="/users")` 跨模块。#43 的字面量同文件夹具没覆盖到。
