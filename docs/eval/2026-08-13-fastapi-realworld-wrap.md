# FastAPI RealWorld wiki 质量对照 wrap

**日期：** 2026-08-13–2026-08-14 CST  
**对照：** nsidnev/fastapi-realworld-example-app `029eb778` × MiniMax-M3  
**CLI：** r1 `9cadf85`（#40）→ r2 `c2407979`（#42 空 content 重试 + #43 FastAPI 扫描）→ r3 `a3d58b4`（#45 导入 router 前缀拼接）→ r4 `9328896`（#50；含 #48 `api_prefix` + #49 circuit-break）

第一轮评测见 `docs/eval/2026-08-13-fastapi-realworld-round1.md`。  
第二轮评测见 `docs/eval/2026-08-13-fastapi-realworld-round2.md`。  
第三轮评测见 `docs/eval/2026-08-13-fastapi-realworld-round3.md`。  
第四轮评测见 `docs/eval/2026-08-14-fastapi-realworld-round4.md`。

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

## 本回路已合并（#37–#50）

- **#37**（`98aa8bd`）：packaged templates、长 citation 路径、LLM 页超时跟 YAML/300s cap。
- **#38**：Flask round-2 评测文档。
- **#39**：库仓 path roles、忽略 init stub、qoder meta 查找；概述不再自称知识管理平台。
- **#40**（`9cadf85`）：HTTP 529/429 重试。FastAPI r1：89 页、0 次 529、**60/89 空壳**。
- **#41**：FastAPI RealWorld round-1 评测文档。
- **#42**：空 `message.content` 当 retryable；compact `max_tokens` 不再 1400 饿死推理模型。r2 空壳 **60→0**。
- **#43**（`c2407979`）：FastAPI `include_router` 前缀拼接、按装饰器绑 handler、有产品 API 时禁止 04 UNRESOLVED。r2 endpoints 11→19，wiki UNRESOLVED 24→0。
- **#44**：FastAPI RealWorld round-2 评测文档。
- **#45**（`a3d58b4`）：导入 alias 的 `include_router` 字面量前缀 + `get_application()` 内 `FastAPI()`。r3 19 条变为 mounted（`POST /users/login` 等）；相对 `POST /login` `GET /feed` `GET /` 为 0。`get_app_settings()` 的 `api_prefix=/api` 仍未解析。
- **#46**（`24b36a1`）：v3 FastAPI scan 拼接前缀并尝试解析 settings factory `api_prefix`。r3 评测 SHA 仍是 #45；r4 证据以 #48 为准。
- **#47**：FastAPI RealWorld round-3 评测文档。
- **#48**（`8f0d1f5`）：env factory `return config()` 不再丢掉 annotated `AppSettings`，`settings.api_prefix=/api` 解析到。r4 index **19/19 `/api/*`**；HIT `POST /api/users/login`、`GET /api/articles/feed`；相对残留 **NONE**。
- **#49**（`0121f9b`）：circuit-break 后不再把剩余页全部 `gather`。代码已装上；本轮无 529/timeout 风暴，skip path **未证实**。不要声称 #49 “救了”本轮。
- **#50**（`9328896`）：Codex plugin workflow；本轮 CLI SHA。不含 wiki 生成修复。

## r3 vs r4

| 项 | r3 | r4 |
|---|---|---|
| generate | 89/89 | 89/89 |
| cache | 0/89 | **0/89**（r3 composer cache 挪开） |
| 空壳 | 0/89 | **0/89**（守住） |
| 529 | 16 页，随后熔断 | **0**；circuit-break **未触发**（`provider_disabled=false`） |
| timeouts | — | **0** |
| fallback / rejected | 26 | **3** |
| 空 assistant content | 6 | **0** |
| insufficient prose | 4 | **3**（error-handling-status-codes、database-migration-strategy、resources） |
| LLM | 89 / 245251 tokens | 89 / **345891** |
| endpoints | 19 mounted（无 `/api`） | **19 `/api/*`**；相对残留 **NONE** |
| `settings.api_prefix=/api` | 仍缺 | **已解析**（scanner==v3） |
| wiki 中 UNRESOLVED | 0 | **0** |
| login 页命中 | `POST /users/login` **14 页** | `POST /api/users/login` **14 页** |
| verify | 13 HARD / 0 SOFT | **12 HARD / 0 SOFT**（未放宽；`QODER_PROSE_TOO_LOW` 本轮 PASS） |
| 页质量 | PASS 63 / DEGRADED 26 | PASS **86** / DEGRADED **3** |
| 无效 citation | 27（26 为 `file:` 前缀） | **62**（`file:` 前缀） |
| claim coverage | 38.05%（613/1611） | **51.51%**（868/1685） |
| page dumps | 32 | **48** |
| API mermaid 缺失 | 9 | 9 |
| API aggregation | PASS 13/13 | PASS **13/13** |
| owner missing | 23（14 条 v3 相对 + 9 models） | **24**（19 条 `/api/*` + 5 models） |
| Overview Conduit | 否 | **否**（init-stub / api-gateway；Conduit 只来自 eval 污染） |
| wall | 15m40s | **19m48s**（89 次完整 LLM，约 13s/页；非 #49 救命） |

#49 代码已装上，但本轮无 529/timeout 风暴，skip path **未证实**。wall 长于 r3 是因为 r3 16×529 短失败，r4 完成了 89 次完整 LLM，没有 180s 等待。

## 残留（r4；不改 generator/scanner）

- README/Conduit 仍输给 init stub；应忽略 eval 文件（`AGENTS.md` / `round3-report.md`）当产品证据。Overview Conduit：**FAIL**。Init stub 不当身份：**FAIL**。
- citation `file:` 前缀 27→**62**。
- owner mapping 在正确的 `/api` 路径上仍 19/19 missing（owner missing 24 = 19 `/api/*` + 5 models）。
- tests-as-product：`核心服务/Tests.md` 仍把 tests 当产品 api-server。
- **#49 skip path 本轮未证实**——除非 review 发现仍有 gather-all timeout，否则不另开 PR。
- 产品契约本轮 **PASS**：API参考列出全部 19 条 `/api/*`，未编造 `/health` `/webhook` `/items`。
- r4 verify：**12 HARD / 0 SOFT**（r3 为 13/0；`QODER_PROSE_TOO_LOW` 本轮 PASS，仍是 HARD gate）。eval-layout HARD 是布局问题，不是产品失败。不要松阈值。
