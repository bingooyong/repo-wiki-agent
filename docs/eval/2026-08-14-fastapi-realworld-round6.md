# FastAPI RealWorld 对照 Wiki 第六轮评测

**对照仓：** nsidnev/fastapi-realworld-example-app `029eb7781c60d5f563ee8990a0cbfb79b244538c`  
**CLI：** repo-wiki `0.1.0` @ `b0a06f40f74a5c35701fb0d92cde244af4a12de1`（PR #54）  
**时间：** 2026-08-14 10:00:27–10:19:41 CST（wall 19m14s；compose 1152.1s）  
**run id：** `run-1786672827615`  
**cache：** r5 composer cache 已挪开；本轮 **0/89** hits  
**verify JSON：** `docs/eval/2026-08-14-fastapi-realworld-round6-verify.json`

第五轮评测见 `docs/eval/2026-08-14-fastapi-realworld-round5.md`。  
对照 wrap 见 `docs/eval/2026-08-13-fastapi-realworld-wrap.md`。

## 生成前身份（#54）

| 项 | 值 |
|---|---|
| name | `fastapi-realworld-example-app` |
| description | 含 “passing Conduit testsuite”；**无** `:target:` 垃圾 |
| Overview 产品名 RealWorld | **否**（仅 slug `fastapi-realworld`） |
| Overview Conduit | **否** |
| init-stub | **否** |
| `AGENTS.md` / eval 作 citation source | **否** |
| pyproject description | **未读**（README 已是产品句） |

#54 解析到 README 产品句后，identity.description 已含 “passing Conduit testsuite”，不再是 `:target:` 垃圾。00 overview 引言引用 `README.rst:32-73`（Quickstart），跳过 L28 Conduit NOTE；identity.description **未流入** 00 正文。

## 生成

| 项 | r5 | r6 |
|---|---|---|
| generate | 89/89 | 89/89 |
| cache | 0/89（r4 cache 挪开） | **0/89**（r5 cache 挪开） |
| 529 | 0；circuit-break **false** | **0**；circuit-break **false** |
| fallback / rejected | 5（5×insufficient prose） | **3**（python-services-index、service-data-models、authorization） |
| LLM tokens | 308226 | **326406** |
| endpoints | 19 `/api/*` | **19 `/api/*`** |
| wiki 中 UNRESOLVED | 0 | **0** |
| login 页命中 | `POST /api/users/login` **14** | `POST /api/users/login` **14** |
| 页质量 | PASS 84 / DEGRADED 5 | PASS **86** / DEGRADED **3** |
| `AGENTS.md` / eval 作证据 | 已消失 | **已消失** |

Overview 原文：「本仓库为一个名为 `fastapi-realworld` 的 FastAPI 后端项目…常见主题域包括 `python-backend/core-platform`」+「共包含 19 个端点」。**无 Conduit。无产品名 RealWorld**（仅 slug）。引言引用 `README.rst:32-73`（Quickstart），跳过 L28 Conduit NOTE。

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

exit 1，FAIL `NOT_READY`。**13 HARD / 0 SOFT**（与 r5 相同）。未放宽任何阈值。

| 项 | r5 | r6 |
|---|---|---|
| 页质量 | PASS 84 / DEGRADED 5 | PASS **86** / DEGRADED **3** |
| 无效 citation | 109（列出的全部为 `file:README.rst`） | **51**（仍全部为 `file:README.rst`） |
| claim coverage | 51.62% | **49.94%** |
| owner missing | 28（19 条 `/api/*` + 9 models） | **28**（19 条 `/api/*` + 9 models） |
| `核心服务/Tests.md` | 仍在 | **仍在** |

HARD codes（与 r5 同一组，未放宽）：`QODER_MANIFEST_PATH_INVALID`、`QODER_PAGE_QUALITY_STATE_MISSING`、`QODER_UNRESOLVED_FACT_CONFLICT`、`QODER_REQUIRED_INVENTORY_MISSING`、`QODER_CITATION_INVALID`、`QODER_CITATION_FACT_COVERAGE_LOW`、`QODER_OWNER_COVERAGE_MISSING`、`QODER_CITATION_RELEVANCE_MISMATCH`、`QODER_API_MERMAID_MISSING`、`QODER_DATA_MODEL_ER_MERMAID_MISSING`、`QODER_PAGE_DUMP`、`QODER_PROSE_TOO_LOW`、`QODER_DIRTY_WORKTREE`。

## Must-check

1. Overview RealWorld/Conduit：**FAIL**（无 Conduit；无产品名 RealWorld，仅 slug。identity.description 已含 “passing Conduit testsuite”，但未流入 00 正文；引言引用 Quickstart，跳过 L28 Conduit NOTE）。
2. 真实 `/api` 路由：**PASS**（index 与 wiki 均为 19/19 `/api/*`；`POST /api/users/login` HIT）。
3. tests/docs 不充当产品 api-server：**FAIL**（`核心服务/Tests.md` 仍在）。
4. Init stub 不当身份：**PASS**（name=`fastapi-realworld-example-app`；无 `:target:` 垃圾）。
5. eval 产物不当证据：**PASS**（`AGENTS.md` / eval cites 已消失）。

## 残留（本 PR 不改 generator/scanner）

1. identity.description 未流入 00 overview 正文。
2. citation `file:` 前缀（109→**51** HARD；仍全部为 `file:README.rst`）。
3. owner mapping 在正确的 `/api` 路径上仍 19/19 missing（owner missing 28 = 19 `/api/*` + 9 models）。
4. tests-as-product（`核心服务/Tests.md`）。
5. taxonomy 幻觉（Agent代理API / API网关 / 前端应用）。

eval-layout HARD 是布局问题，不是产品失败——不要松阈值。
