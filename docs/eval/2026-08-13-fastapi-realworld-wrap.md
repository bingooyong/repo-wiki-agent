# FastAPI RealWorld wiki 质量对照 wrap

**日期：** 2026-08-13 CST  
**对照：** nsidnev/fastapi-realworld-example-app `029eb778` × MiniMax-M3  
**CLI：** r1 `9cadf85`（#40）→ r2 `c2407979`（#42 空 content 重试 + #43 FastAPI 扫描）→ r3 `a3d58b4`（#45 导入 router 前缀拼接）

第一轮评测见 `docs/eval/2026-08-13-fastapi-realworld-round1.md`。  
第二轮评测见 `docs/eval/2026-08-13-fastapi-realworld-round2.md`。  
第三轮评测见 `docs/eval/2026-08-13-fastapi-realworld-round3.md`。

## r1 vs r2

| 项 | r1 | r2 |
|---|---|---|
| generate | 89/89 | 89/89 |
| 空壳 “LLM composer did not return content” | 60/89 | **0/89** |
| 529 | 0 | 0 |
| fallback / rejected | 0 | 2（Insufficient prose） |
| endpoints | 11 | **19**（仍无 include_router 前缀） |
| wiki 中 UNRESOLVED | 24 | **0** |

## r2 vs r3

| 项 | r2 | r3 |
|---|---|---|
| generate | 89/89 | 89/89 |
| cache | — | 0/89 |
| 空壳 | 0/89 | **0/89**（守住） |
| 529 | 0 | **16 页**，随后熔断 |
| fallback / rejected | 2 | **26** |
| LLM | 89 / 329668 tokens | 89 / 245251 |
| endpoints | 19 相对（`POST /login` `GET /feed` `GET /`） | **19 mounted**（`POST /users/login` 等；相对残留 **0**） |
| `settings.api_prefix=/api` | 无 | **仍缺**（不跟随 `get_app_settings()`） |
| wiki 中 UNRESOLVED | 0 | **0** |
| `/users/login` 页命中 | 无 | **14 页**；`POST /login` / `GET /feed` **0 hits** |
| verify | 13 HARD / 0 SOFT | **13 HARD / 0 SOFT**（同一组 codes，未放宽） |
| 页质量 | — | PASS 63 / DEGRADED 26 |
| 无效 citation | 56 | **27**（26 为 `file:` 前缀） |
| claim coverage | 51.28%（900/1755） | **38.05%**（613/1611，fallback 拉低） |
| page dumps | 10 | **32** |
| API aggregation | PASS 13/13 | PASS 13/13 |
| owner missing | 21 | **23**（14 条 v3 相对路径 + 9 models） |
| Overview Conduit | 否 | **否**（仍 api-gateway / init stub） |

## 本回路已合并（#37–#45）

- **#37**（`98aa8bd`）：packaged templates、长 citation 路径、LLM 页超时跟 YAML/300s cap。
- **#38**：Flask round-2 评测文档。
- **#39**：库仓 path roles、忽略 init stub、qoder meta 查找；概述不再自称知识管理平台。
- **#40**（`9cadf85`）：HTTP 529/429 重试。FastAPI r1：89 页、0 次 529、**60/89 空壳**。
- **#41**：FastAPI RealWorld round-1 评测文档。
- **#42**：空 `message.content` 当 retryable；compact `max_tokens` 不再 1400 饿死推理模型。r2 空壳 **60→0**。
- **#43**（`c2407979`）：FastAPI `include_router` 前缀拼接、按装饰器绑 handler、有产品 API 时禁止 04 UNRESOLVED。r2 endpoints 11→19，wiki UNRESOLVED 24→0。
- **#44**：FastAPI RealWorld round-2 评测文档。
- **#45**（`a3d58b4`）：导入 alias 的 `include_router` 字面量前缀 + `get_application()` 内 `FastAPI()`。r3 19 条变为 mounted（`POST /users/login` 等）；相对 `POST /login` `GET /feed` `GET /` 为 0。`get_app_settings()` 的 `api_prefix=/api` 仍未解析。

## 残留

- **v3 owner 与 wiki 路径不一致：** scanner 仍按文件 `extract_fastapi_endpoints`；verify owner 看到 `POST /login`，wiki 已是 `POST /users/login`。owner missing 21→23（14 条 v3 相对 API + 9 models）。
- **`settings.api_prefix=/api` 仍缺：** `settings = get_app_settings(); prefix=settings.api_prefix` 不跟随工厂，scanner 未解析到 `/api`。
- Overview **仍不是** Conduit；README 输给 init stub + `AGENTS.md`。00 仍是 api-gateway / core-platform / repo-wiki-init-stub。Init stub 不当身份：**FAIL**。`核心服务/Tests.md` 仍把 tests 当产品 api-server。
- citation `file:` 前缀还剩 27（26 条是该前缀）。
- **529 circuit-break：** 16 页 529 后 `provider_disabled_after_failures=true`；89 个 job 在 `gather` 前已全部入队，失败无法中途停跑。fallback 2→26，coverage 51.28%→38.05%，page dumps 10→32。空壳 0 守住；空 assistant content 6 页走 fallback，不是假 PASS。
- 产品契约本轮 **PASS**：API参考列出 19 mounted 路径，未编造 `/health` `/webhook` `/items`。
- r3 verify：**13 HARD / 0 SOFT**（与 r2 同一组 codes）。eval-layout HARD 是布局问题，不是产品失败。不要松阈值。generator-fix 另开 PR。
