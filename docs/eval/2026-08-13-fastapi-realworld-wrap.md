# FastAPI RealWorld wiki 质量对照 wrap

**日期：** 2026-08-13 CST  
**对照：** nsidnev/fastapi-realworld-example-app `029eb778` × MiniMax-M3  
**CLI：** r1 `9cadf85`（#40）→ r2 `c2407979`（#42 空 content 重试 + #43 FastAPI 扫描）

第一轮评测见 `docs/eval/2026-08-13-fastapi-realworld-round1.md`。

## r1 vs r2

| 项 | r1 | r2 |
|---|---|---|
| generate | 89/89 | 89/89 |
| 空壳 “LLM composer did not return content” | 60/89 | **0/89** |
| 529 | 0 | 0 |
| fallback / rejected | 0 | 2（Insufficient prose） |
| endpoints | 11 | **19**（仍无 include_router 前缀） |
| wiki 中 UNRESOLVED | 24 | **0** |

## 本回路已合并（#37–#43）

- **#37**（`98aa8bd`）：packaged templates、长 citation 路径、LLM 页超时跟 YAML/300s cap。
- **#38**：Flask round-2 评测文档。
- **#39**：库仓 path roles、忽略 init stub、qoder meta 查找；概述不再自称知识管理平台。
- **#40**（`9cadf85`）：HTTP 529/429 重试。FastAPI r1：89 页、0 次 529、**60/89 空壳**。
- **#41**：FastAPI RealWorld round-1 评测文档。
- **#42**：空 `message.content` 当 retryable；compact `max_tokens` 不再 1400 饿死推理模型。r2 空壳 **60→0**。
- **#43**（`c2407979`）：FastAPI `include_router` 前缀拼接、按装饰器绑 handler、有产品 API 时禁止 04 UNRESOLVED。r2 endpoints 11→19，wiki UNRESOLVED 24→0。

## 残留

- **Prefix join 仍残留：** 对照仓是 `get_application()` 内 `FastAPI()`；`application.include_router(api_router, prefix=settings.api_prefix)`（非字面量）；`router.include_router(authentication.router, prefix="/users")` 跨模块。#43 字面量同文件夹具未覆盖。仍无 `/users/login`、`/articles` 完整前缀（只有 `POST /login` `GET /feed` `GET /`）。
- Overview **仍不是** Conduit（未再出现「知识管理平台」）。
- 数据模型有 User/Comment/Article DTO；ER 仍缺 User/Tag。
- r2 verify：**13 HARD / 0 SOFT**（r1 为 12/0，新加 `QODER_PROSE_TOO_LOW`）。claim coverage 43.5%→51.3%。API aggregation PASS 13/13。无效 citation 22→56（`file:` 前缀）。2 页 fallback/rejected（Insufficient prose）。不要松阈值。generator-fix 另开 PR。
