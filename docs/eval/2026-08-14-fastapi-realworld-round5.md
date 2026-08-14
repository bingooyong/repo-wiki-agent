# FastAPI RealWorld 对照 Wiki 第五轮评测

**对照仓：** nsidnev/fastapi-realworld-example-app `029eb7781c60d5f563ee8990a0cbfb79b244538c`  
**CLI：** repo-wiki `0.1.0` @ `8912c89e77d16da0403111526eda3c5409899891`（PR #52）  
**模型：** MiniMax-M3 openai-compat；YAML timeout 180s；`max_concurrent=2`  
**时间：** 2026-08-14 08:38:49–08:58:07 CST（wall 19m18s；compose 1156.3s）  
**run id：** `run-1786667929776`  
**cache：** r4 composer cache 已挪开；本轮 **0/89** hits  
**verify JSON：** `docs/eval/2026-08-14-fastapi-realworld-round5-verify.json`

第四轮评测见 `docs/eval/2026-08-14-fastapi-realworld-round4.md`。  
对照 wrap 见 `docs/eval/2026-08-13-fastapi-realworld-wrap.md`。

## 生成前身份（#52）

| 项 | 值 |
|---|---|
| name | `fastapi-realworld-example-app`（来自 pyproject，**不是** init-stub） |
| display | `Fastapi Realworld Example App` |
| description | RST badge 垃圾：`:target: https://github.com/nsidnev/fastapi-realworld-example-app` ×3 |
| Conduit | **否** |
| init-stub | **否** |
| `AGENTS.md` / `round*-report.md` 作 citation source | **否** |
| `docs/00-overview.md` | `is_init_generated` |
| pyproject description | **未读**（原文：`Backend logic implementation for https://github.com/gothinkster/realworld with awesome FastAPI`） |

README.rst 解析器把 `|` 当 title、把缩进的 `:target:` 当 description，从未读到 “passing Conduit testsuite”。

## 生成

| 项 | r4 | r5 |
|---|---|---|
| generate | 89/89 | 89/89 |
| cache | 0/89（fresh） | **0/89**（r4 cache 挪开） |
| 空壳 “LLM composer did not return content” | 0/89 | **0/89**（守住） |
| 529 | 0；`provider_disabled=false` | **0**；circuit-break **false** |
| fallback / rejected | 3（3×insufficient prose） | **5**（5×insufficient prose） |
| insufficient prose | 3（error-handling-status-codes、database-migration-strategy、resources） | **5**（development-guide、python-service-apis、api-issues、core-data-models、db） |
| LLM | 89 / 345891 tokens | 89 / **308226** |
| evidence spans | 490 | **350** |
| endpoints | 19 `/api/*` | **19 `/api/*`** |
| wiki 中 UNRESOLVED | 0 | **0** |
| 页质量 | PASS 86 / DEGRADED 3 | PASS **84** / DEGRADED **5** |

Wiki API参考列出全部 19 条 `/api/*`；`POST /api/users/login` 出现在 **14 页**。

Overview **仍不是** Conduit。已无 init-stub / 知识管理 / product-name api-gateway。原文：「该项目以 FastAPI 作为运行时入口（运行时角色标注为 api-server），并在文档中被引用为 fastapi-realworld」。另有「python-backend/core-platform 域下归集了 19 个端点」。`AGENTS.md` / `round*-report.md` 作证据：**已消失**。

## Index

与 r4 相同：**19/19 `/api/*`**。HIT 含：`POST /api/users/login`、`GET /api/articles/feed`。

`/api/*` 19：

- `POST /api/users/login` `POST /api/users` `GET /api/user` `PUT /api/user`
- `GET /api/articles` `POST /api/articles` `GET /api/articles/feed` `GET /api/articles/{slug}` `PUT /api/articles/{slug}` `DELETE /api/articles/{slug}`
- `POST /api/articles/{slug}/favorite` `DELETE /api/articles/{slug}/favorite`
- `GET /api/articles/{slug}/comments` `POST /api/articles/{slug}/comments` `DELETE /api/articles/{slug}/comments/{comment_id}`
- `GET /api/profiles/{username}` `POST /api/profiles/{username}/follow` `DELETE /api/profiles/{username}/follow`
- `GET /api/tags`

## Verify

exit 1，FAIL `NOT_READY`。**13 HARD / 0 SOFT**（r4 为 **12/0**——本轮 `QODER_PROSE_TOO_LOW` **FAIL×2**）。未放宽任何阈值。`QODER_PROSE_TOO_LOW` 仍是 HARD gate。

| 项 | r4 | r5 |
|---|---|---|
| 页质量 | PASS 86 / DEGRADED 3 | PASS **84** / DEGRADED **5** |
| 无效 citation | 62（`file:` 前缀） | **109**（列出的 30 条全部为 `file:README.rst`） |
| claim coverage | 51.51%（868/1685） | **51.62%**（909/1761） |
| page dumps | 48 | **42** |
| API mermaid 缺失 | 9 | 9 |
| data-model ER mermaid 缺失 | — | 5 |
| API aggregation | PASS 13/13 | PASS **13/13** |
| owner missing | 24（19 条 `/api/*` + 5 models） | **28**（19 条 `/api/*` + 9 models） |
| `QODER_PROSE_TOO_LOW` | PASS | **FAIL×2** |
| dirty-worktree | FAIL（eval 产物） | FAIL（eval 产物） |

HARD codes（相对 r4 多回 `QODER_PROSE_TOO_LOW`）：`QODER_MANIFEST_PATH_INVALID`、`QODER_PAGE_QUALITY_STATE_MISSING`、`QODER_UNRESOLVED_FACT_CONFLICT`、`QODER_REQUIRED_INVENTORY_MISSING`、`QODER_CITATION_INVALID`、`QODER_CITATION_FACT_COVERAGE_LOW`、`QODER_OWNER_COVERAGE_MISSING`、`QODER_CITATION_RELEVANCE_MISMATCH`、`QODER_API_MERMAID_MISSING`、`QODER_DATA_MODEL_ER_MERMAID_MISSING`、`QODER_PAGE_DUMP`、`QODER_PROSE_TOO_LOW`、`QODER_DIRTY_WORKTREE`。

## Must-check

1. Overview RealWorld/Conduit：**FAIL**（仍不是 Conduit；#52 已去掉 init-stub / 知识管理 / product-name api-gateway）。
2. 真实 `/api` 路由：**PASS**（API参考列出全部 19 条 `/api/*`）。
3. tests/docs 不充当产品 api-server：**FAIL**（`核心服务/Tests.md` 仍在）。
4. Init stub 不当身份：**PASS**（name 来自 pyproject；Overview 无 init-stub）。
5. eval 产物不当证据：**PASS**（`AGENTS.md` / `round*-report.md` 作证据已消失）。

## 残留（本 PR 不改 generator/scanner）

1. README.rst 解析器 + 未读 pyproject description，故 00 仍不是 Conduit。
2. citation `file:` 前缀（62→**109** HARD）。
3. owner mapping 在正确的 `/api` 路径上仍 19/19 missing（owner missing 28 = 19 `/api/*` + 9 models）。
4. tests-as-product（`核心服务/Tests.md`）。
5. taxonomy 幻觉（Agent代理API / API网关 / 前端应用）。
6. eval-layout HARD 是布局问题，不是产品失败——不要松阈值。
