# FastAPI RealWorld wiki 质量对照 wrap

**日期：** 2026-08-13–2026-08-14 CST  
**对照：** nsidnev/fastapi-realworld-example-app `029eb778` × MiniMax-M3  
**CLI：** r1 `9cadf85`（#40）→ r2 `c2407979`（#42 空 content 重试 + #43 FastAPI 扫描）→ r3 `a3d58b4`（#45 导入 router 前缀拼接）→ r4 `9328896`（#50；含 #48 `api_prefix` + #49 circuit-break）→ r5 `8912c89`（#52 README/身份优先于 init stub 与 eval notes）→ r6 `b0a06f4`（#54 README.rst 解析 + pyproject fallback）→ r7 `2e3a3f0`（#56 identity.description 流入 overview）

第一轮评测见 `docs/eval/2026-08-13-fastapi-realworld-round1.md`。  
第二轮评测见 `docs/eval/2026-08-13-fastapi-realworld-round2.md`。  
第三轮评测见 `docs/eval/2026-08-13-fastapi-realworld-round3.md`。  
第四轮评测见 `docs/eval/2026-08-14-fastapi-realworld-round4.md`。  
第五轮评测见 `docs/eval/2026-08-14-fastapi-realworld-round5.md`。  
第六轮评测见 `docs/eval/2026-08-14-fastapi-realworld-round6.md`。  
第七轮评测见 `docs/eval/2026-08-14-fastapi-realworld-round7.md`。

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

## 本回路已合并（#37–#56）

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
- **#50**（`9328896`）：Codex plugin workflow；r4 CLI SHA。不含 wiki 生成修复。
- **#51**：FastAPI RealWorld round-4 评测文档。
- **#52**（`8912c89`）：README/身份优先于 init stub 与 eval notes。r5：name 来自 pyproject（非 init-stub）；Overview 已无 init-stub / 知识管理 / product-name api-gateway；`AGENTS.md` / `round*-report.md` 作证据已消失。仍不是 Conduit：README.rst 解析器把 `|` 当 title、把缩进的 `:target:` 当 description；pyproject description 未读。
- **#53**：FastAPI RealWorld round-5 评测文档。
- **#54**（`b0a06f4`）：跳过 RST badge / `:target:` / `:alt:`，读 README 第一段产品句；README 无产品句时回退 pyproject description。r6：identity.description 含 “passing Conduit testsuite”，无 `:target:` 垃圾；pyproject description **未读**（README 已是产品句）。00 仍无 Conduit、无产品名 RealWorld（仅 slug）；identity.description **未流入** 00 正文。引言引用 `README.rst:32-73`（Quickstart），跳过 L28 Conduit NOTE。
- **#55**：FastAPI RealWorld round-6 评测文档。
- **#56**（`2e3a3f0`）：identity.description 流入 overview context / composer prompt。r7：Overview **HIT Conduit**（中文「通过 Conduit 测试套件」）；`project-overview` 在 circuit-break 前完成（5288 tokens，PASS），#56 检查有效。不要重开 overview-identity PR。

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

## r4 vs r5

| 项 | r4 | r5 |
|---|---|---|
| generate | 89/89 | 89/89 |
| cache | 0/89（r3 composer cache 挪开） | **0/89**（r4 composer cache 挪开） |
| 空壳 | 0/89 | **0/89**（守住） |
| 529 | 0；circuit-break **未触发** | **0**；circuit-break **false** |
| fallback / rejected | 3 | **5**（development-guide、python-service-apis、api-issues、core-data-models、db） |
| LLM | 89 / 345891 tokens | 89 / **308226** |
| evidence spans | 490 | **350** |
| endpoints | 19 `/api/*`；相对残留 **NONE** | **19 `/api/*`**；HIT `POST /api/users/login`、`GET /api/articles/feed` |
| wiki 中 UNRESOLVED | 0 | **0** |
| login 页命中 | `POST /api/users/login` **14 页** | `POST /api/users/login` **14 页** |
| verify | 12 HARD / 0 SOFT（`QODER_PROSE_TOO_LOW` PASS） | **13 HARD / 0 SOFT**（未放宽；`QODER_PROSE_TOO_LOW` **FAIL×2**） |
| 页质量 | PASS 86 / DEGRADED 3 | PASS **84** / DEGRADED **5** |
| 无效 citation | 62（`file:` 前缀） | **109**（列出的 30 条全部为 `file:README.rst`） |
| claim coverage | 51.51%（868/1685） | **51.62%**（909/1761） |
| page dumps | 48 | **42** |
| API mermaid 缺失 | 9 | 9 |
| data-model ER mermaid 缺失 | — | 5 |
| API aggregation | PASS 13/13 | PASS **13/13** |
| owner missing | 24（19 `/api/*` + 5 models） | **28**（19 `/api/*` + 9 models） |
| Overview Conduit | 否（init-stub / api-gateway；Conduit 只来自 eval 污染） | **否**（无 init-stub / 知识管理 / product-name api-gateway；仍不是 Conduit） |
| eval 产物作证据 | `AGENTS.md` / `round3-report.md` | **已消失** |
| wall | 19m48s（compose 1186.1s） | **19m18s**（compose 1156.3s） |

#52 去掉了 init-stub / 知识管理 / product-name api-gateway，以及 `AGENTS.md` / `round*-report.md` 作证据。00 仍不是 Conduit：README.rst 解析器把 `|` 当 title、把缩进的 `:target:` 当 description，从未读到 “passing Conduit testsuite”；pyproject description 未读。

## r5 vs r6

| 项 | r5 | r6 |
|---|---|---|
| generate | 89/89 | 89/89 |
| cache | 0/89（r4 composer cache 挪开） | **0/89**（r5 composer cache 挪开） |
| 529 | 0；circuit-break **false** | **0**；circuit-break **false** |
| fallback / rejected | 5 | **3**（python-services-index、service-data-models、authorization） |
| LLM tokens | 308226 | **326406** |
| endpoints | 19 `/api/*`；HIT `POST /api/users/login` | **19 `/api/*`**；HIT `POST /api/users/login` |
| wiki 中 UNRESOLVED | 0 | **0** |
| login 页命中 | `POST /api/users/login` **14 页** | `POST /api/users/login` **14 页** |
| verify | 13 HARD / 0 SOFT（未放宽） | **13 HARD / 0 SOFT**（未放宽；同一组 codes） |
| 页质量 | PASS 84 / DEGRADED 5 | PASS **86** / DEGRADED **3** |
| 无效 citation | 109（列出的全部为 `file:README.rst`） | **51**（仍全部为 `file:README.rst`） |
| claim coverage | 51.62% | **49.94%** |
| owner missing | 28（19 `/api/*` + 9 models） | **28**（19 `/api/*` + 9 models） |
| Overview Conduit | 否（无 init-stub / 知识管理 / product-name api-gateway；仍不是 Conduit） | **否**（无 Conduit；无产品名 RealWorld，仅 slug） |
| identity.description | `:target:` 垃圾 ×3；未读到 “passing Conduit testsuite” | **含 “passing Conduit testsuite”**；无 `:target:` 垃圾；**未流入** 00 正文 |
| pyproject description | 未读 | **未读**（README 已是产品句） |
| eval 产物作证据 | 已消失 | **已消失** |
| `核心服务/Tests.md` | 仍在 | **仍在** |
| wall | 19m18s（compose 1156.3s） | **19m14s**（compose 1152.1s） |

#54 修好了 identity.description（“passing Conduit testsuite”，无 `:target:` 垃圾）。00 overview 仍无 Conduit、无产品名 RealWorld（仅 slug `fastapi-realworld`）：引言引用 `README.rst:32-73`（Quickstart），跳过 L28 Conduit NOTE；identity.description 未流入 00 正文。

## r6 vs r7

| 项 | r6 | r7 |
|---|---|---|
| generate | 89/89 | 89/89 |
| cache | 0/89（r5 cache 挪开） | **0/89**（r6 cache 挪开） |
| 529 | 0；circuit-break **false** | **4**；circuit-break **tripped**（#49） |
| fallback / rejected | 3 | **57**（52 skip + 4×529 + 1 prose） |
| LLM tokens | 89 / 326406 | **37** / **133487** |
| endpoints | 19 `/api/*`；HIT `POST /api/users/login` | **19 `/api/*`**；HIT `POST /api/users/login` |
| wiki 中 UNRESOLVED | 0 | **0** |
| login 页命中 | `POST /api/users/login` **14** | `POST /api/users/login` **14** |
| 空壳 | 0 | **0** |
| verify | 13 HARD / 0 SOFT（未放宽） | **13 HARD / 0 SOFT**（未放宽；同一组 codes） |
| 页质量 | PASS 86 / DEGRADED 3 | PASS **32** / DEGRADED **57** |
| 无效 citation | 51（仍全部为 `file:README.rst`） | **18**（仍全部为 `file:` / file does not exist） |
| claim coverage | 49.94% | **17.75%**（fallback storm） |
| owner missing | 28（19 `/api/*` + 9 models） | **28**（19 `/api/*` + 9 models） |
| Overview Conduit | 否（无 Conduit；无产品名 RealWorld，仅 slug） | **HIT**（中文「通过 Conduit 测试套件」；无产品名 RealWorld，仅 slug） |
| identity.description | 含 “passing Conduit testsuite”；无 `:target:` 垃圾；**未流入** 00 正文 | 含 “passing Conduit testsuite”；无 `:target:` 垃圾；**已流入** 00 正文 |
| eval 产物作证据 | 已消失 | **已消失** |
| `核心服务/Tests.md` | 仍在 | **仍在** |
| `QODER_PROSE_TOO_LOW` | HARD | **FAIL×3** |
| wall | 19m14s（compose 1152.1s） | **9m00s**（compose 538.5s；后页 skip LLM，**不是**更快 generate） |

#56 把 identity.description 写入 overview。r7 Overview **HIT Conduit**。`project-overview` 在 circuit-break 前完成（5288 tokens，PASS），#56 检查有效。不要重开 overview-identity PR。

#49 skip path 本轮 **已证实**（4×529 后熔断，随后 52 页 skip）。wall 9m00s **不是**更快 generate。fallback 3→57 **不是** #56 回归。

## 残留（r7；不改 generator/scanner）

- Overview Conduit：**HIT**（中文「通过 Conduit 测试套件」；无产品名 RealWorld，仅 slug；仍提及 core-platform / api-server。引言引用 README L28 NOTE）。Init stub 不当身份：**PASS**。eval 产物不当证据：**PASS**。不要重开 overview-identity PR——#56 已落地。
- citation `file:` 前缀 51→**18** HARD（仍全部为 `file:` / file does not exist）。
- owner mapping 在正确的 `/api` 路径上仍 19/19 missing（owner missing 28 = 19 `/api/*` + 9 models）。
- tests-as-product：`核心服务/Tests.md` 仍把 tests 当产品 api-server。
- taxonomy 幻觉：Agent代理API / API网关 / 前端应用。
- 可选：529 retry-before-circuit-break。不要松 HARD。
- 产品契约本轮 **PASS**：index 与 wiki 均为 19/19 `/api/*`；`POST /api/users/login` HIT 14；API参考全部 19 条 `/api/*`。
- r7 verify：**13 HARD / 0 SOFT**（与 r6 相同；未放宽）。不要松阈值。

