# FastAPI RealWorld 对照 Wiki 第七轮评测

**对照仓：** nsidnev/fastapi-realworld-example-app `029eb7781c60d5f563ee8990a0cbfb79b244538c`  
**CLI：** repo-wiki `0.1.0` @ `2e3a3f01fc9bb0cc636d4739c8ae08c2c5e2e3c7`（PR #56）  
**时间：** 2026-08-14 13:38:01–13:47:01 CST（wall 9m00s；compose 538.5s）  
**run id：** `run-1786685881739`  
**cache：** r6 composer cache 已挪开；本轮 **0/89** hits  
**verify JSON：** `docs/eval/2026-08-14-fastapi-realworld-round7-verify.json`

第六轮评测见 `docs/eval/2026-08-14-fastapi-realworld-round6.md`。  
对照 wrap 见 `docs/eval/2026-08-13-fastapi-realworld-wrap.md`。

## 生成前身份（#56）

| 项 | 值 |
|---|---|
| name | `fastapi-realworld-example-app` |
| description | 含 “passing Conduit testsuite”；**无** `:target:` 垃圾 |
| Overview 产品名 RealWorld | **否**（仅 slug `fastapi-realworld`） |
| Overview Conduit | **HIT** |
| init-stub | **否** |
| `AGENTS.md` / eval 作 citation source | **否** |

#56 把 identity.description 写入 overview context。00 正文 **HIT Conduit**。原文：「fastapi-realworld 是面向 Conduit 测试套件的实现示例，**当前仓库不再积极维护**，因为该示例已较为完整并达成其核心目标——通过 Conduit 测试套件」。另 HIT 中文「通过 Conduit 测试套件」。无产品名 RealWorld（仅 slug）。仍提及 core-platform / api-server。引言引用 README L28 NOTE。`AGENTS.md` / eval cites **已消失**。

`project-overview` 在 circuit-break **之前**完成（5288 tokens，PASS），故 #56 检查有效。不要重开 overview-identity PR——#56 已落地。

## 生成

| 项 | r6 | r7 |
|---|---|---|
| generate | 89/89 | 89/89 |
| cache | 0/89（r5 cache 挪开） | **0/89**（r6 cache 挪开） |
| 529 | 0；circuit-break **false** | **4**；circuit-break **tripped**（#49） |
| fallback / rejected | 3 | **57**（52 skip + 4×529 + 1 prose） |
| LLM tokens | 89 / 326406 | **37** / **133487** |
| endpoints | 19 `/api/*` | **19 `/api/*`** |
| wiki 中 UNRESOLVED | 0 | **0** |
| login 页命中 | `POST /api/users/login` **14** | `POST /api/users/login` **14** |
| 空壳 | 0 | **0** |
| 页质量 | PASS 86 / DEGRADED 3 | PASS **32** / DEGRADED **57** |
| `AGENTS.md` / eval 作证据 | 已消失 | **已消失** |

Overview **HIT Conduit**（见上引文 + 中文「通过 Conduit 测试套件」）。无产品名 RealWorld（仅 slug）。仍提及 core-platform / api-server。引言引用 README L28 NOTE。API参考列出全部 19 条 `/api/*`。

**不要**把 wall 9m00s 写成“更快 generate”——后页跳过 LLM。**不要**把 fallback 3→57 当成 #56 回归（#56 只把 identity.description 写入 overview；熔断与 skip 来自 529 + #49）。

## Index

**19/19 `/api/*`**。HIT：`POST /api/users/login`。

`/api/*` 19：

- `POST /api/users/login` `POST /api/users` `GET /api/user` `PUT /api/user`
- `GET /api/articles` `POST /api/articles` `GET /api/articles/feed` `GET /api/articles/{slug}` `PUT /api/articles/{slug}` `DELETE /api/articles/{slug}`
- `POST /api/articles/{slug}/favorite` `DELETE /api/articles/{slug}/favorite`
- `GET /api/articles/{slug}/comments` `POST /api/articles/{slug}/comments` `DELETE /api/articles/{slug}/comments/{comment_id}`
- `GET /api/profiles/{username}` `POST /api/profiles/{username}/follow` `DELETE /api/profiles/{username}/follow`
- `GET /api/tags`

## Verify

exit 1，FAIL `NOT_READY`。**13 HARD / 0 SOFT**（与 r6 相同）。未放宽任何阈值。

| 项 | r6 | r7 |
|---|---|---|
| 页质量 | PASS 86 / DEGRADED 3 | PASS **32** / DEGRADED **57** |
| 无效 citation | 51（仍全部为 `file:README.rst`） | **18**（仍全部为 `file:` / file does not exist） |
| claim coverage | 49.94% | **17.75%**（fallback storm） |
| owner missing | 28（19 条 `/api/*` + 9 models） | **28**（19 条 `/api/*` + 9 models） |
| `核心服务/Tests.md` | 仍在 | **仍在** |
| `QODER_PROSE_TOO_LOW` | HARD | **FAIL×3** |

HARD codes（与 r6 同一组，未放宽）：`QODER_MANIFEST_PATH_INVALID`、`QODER_PAGE_QUALITY_STATE_MISSING`、`QODER_UNRESOLVED_FACT_CONFLICT`、`QODER_REQUIRED_INVENTORY_MISSING`、`QODER_CITATION_INVALID`、`QODER_CITATION_FACT_COVERAGE_LOW`、`QODER_OWNER_COVERAGE_MISSING`、`QODER_CITATION_RELEVANCE_MISMATCH`、`QODER_API_MERMAID_MISSING`、`QODER_DATA_MODEL_ER_MERMAID_MISSING`、`QODER_PAGE_DUMP`、`QODER_PROSE_TOO_LOW`、`QODER_DIRTY_WORKTREE`。

## Must-check

1. Overview RealWorld/Conduit：**HIT Conduit**（中文「通过 Conduit 测试套件」；无产品名 RealWorld，仅 slug。仍提及 core-platform / api-server。引言引用 README L28 NOTE。`project-overview` 在熔断前完成，#56 有效）。
2. 真实 `/api` 路由：**PASS**（index 与 wiki 均为 19/19 `/api/*`；`POST /api/users/login` HIT 14；API参考全部 19 条 `/api/*`）。
3. tests/docs 不充当产品 api-server：**FAIL**（`核心服务/Tests.md` 仍在）。
4. Init stub 不当身份：**PASS**（name=`fastapi-realworld-example-app`；无 `:target:` 垃圾）。
5. eval 产物不当证据：**PASS**（`AGENTS.md` / eval cites 已消失）。

## 残留（本 PR 不改 generator/scanner）

1. citation `file:` 前缀仍是 HARD（51→**18**；仍全部为 `file:` / file does not exist）。
2. owner mapping 在正确的 `/api` 路径上仍 19/19 missing（owner missing 28 = 19 `/api/*` + 9 models）。
3. tests-as-product（`核心服务/Tests.md`）。
4. taxonomy 幻觉（Agent代理API / API网关 / 前端应用）。
5. 可选：529 retry-before-circuit-break。不要松 HARD。

不要重开 overview-identity PR——#56 已落地。不要松阈值。
