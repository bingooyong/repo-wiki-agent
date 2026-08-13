# FastAPI RealWorld 对照 Wiki 第四轮评测

**对照仓：** nsidnev/fastapi-realworld-example-app `029eb7781c60d5f563ee8990a0cbfb79b244538c`  
**CLI：** repo-wiki `0.1.0` @ `932889658434cb00f3fa53bc2fdec2a2e0009f7f`（PR #50；含 #48 `api_prefix` + #49 circuit-break）  
**模型：** MiniMax-M3 openai-compat；YAML timeout 180s；`max_concurrent=2`；`max_provider_failures=3`  
**时间：** 2026-08-14 00:32:37–00:52:25 CST（wall 19m48s；compose 1186.1s）  
**run id：** `run-1786638758226`  
**cache：** r3 composer cache 已挪开；本轮 **0/89** hits  
**verify JSON：** `docs/eval/2026-08-14-fastapi-realworld-round4-verify.json`

第三轮评测见 `docs/eval/2026-08-13-fastapi-realworld-round3.md`。  
对照 wrap 见 `docs/eval/2026-08-13-fastapi-realworld-wrap.md`。

## 生成

| 项 | r3 | r4 |
|---|---|---|
| generate | 89/89 | 89/89 |
| cache | 0/89 | **0/89**（fresh） |
| 空壳 “LLM composer did not return content” | 0/89 | **0/89**（守住） |
| 529 | 16 页，随后 `provider_disabled_after_failures=true` | **0**；`provider_disabled=false` |
| timeouts | — | **0** |
| fallback / rejected | 26（16×529 + 6×空 assistant + 4×insufficient prose） | **3**（3×insufficient prose） |
| 空 assistant content | 6 | **0** |
| insufficient prose | 4 | **3**（error-handling-status-codes、database-migration-strategy、resources） |
| LLM | 89 / 245251 tokens | 89 / **345891** |
| endpoints | 19 mounted（无 `/api`） | **19 `/api/*`** |
| wiki 中 UNRESOLVED | 0 | **0** |
| 页质量 | PASS 63 / DEGRADED 26 | PASS **86** / DEGRADED **3** |

Wiki API参考列出全部 19 条 `/api/*`；`POST /api/users/login` 出现在 **14 页**。Overview **仍不是** Conduit（仍是 api-gateway / repo-wiki-init-stub）。

## Circuit-break 诚实记录（#49）

#49 代码已装上，但本轮无 529/timeout 风暴，skip path **未证实**。不要声称 #49 “救了”本轮。

wall 长于 r3（19m48s vs 15m40s）是因为 r3 有 16×529 短失败；r4 完成了 89 次完整 LLM 调用（约 13s/页），没有 180s 等待。circuit-break **未触发**。

## Index（#48 证明）

r3 为 19 mounted（`POST /users/login` 等，`settings.api_prefix=/api` 仍缺）；r4 为 **19/19 `/api/*`**。scanner==v3。相对残留：**NONE**。

`/api/*` 19：

- `POST /api/users/login` `POST /api/users` `GET /api/user` `PUT /api/user`
- `GET /api/articles` `POST /api/articles` `GET /api/articles/feed` `GET /api/articles/{slug}` `PUT /api/articles/{slug}` `DELETE /api/articles/{slug}`
- `POST /api/articles/{slug}/favorite` `DELETE /api/articles/{slug}/favorite`
- `GET /api/articles/{slug}/comments` `POST /api/articles/{slug}/comments` `DELETE /api/articles/{slug}/comments/{comment_id}`
- `GET /api/profiles/{username}` `POST /api/profiles/{username}/follow` `DELETE /api/profiles/{username}/follow`
- `GET /api/tags`

HIT 含：`POST /api/users/login`、`GET /api/articles/feed`。

## Verify

exit 1，FAIL `NOT_READY`。**12 HARD / 0 SOFT**（r3 为 **13/0**）。未放宽任何阈值。`QODER_PROSE_TOO_LOW` 本轮 **PASS**（仍是 HARD gate）。

| 项 | r3 | r4 |
|---|---|---|
| 页质量 | PASS 63 / DEGRADED 26 | PASS **86** / DEGRADED **3** |
| 无效 citation | 27（26 为 `file:` 前缀） | **62**（`file:` 前缀） |
| claim coverage | 38.05%（613/1611） | **51.51%**（868/1685） |
| page dumps | 32 | **48** |
| API mermaid 缺失 | 9 | 9 |
| API aggregation | PASS 13/13 | PASS **13/13** |
| owner missing | 23（14 条 v3 相对 API + 9 models） | **24**（19 条 `/api/*` + 5 models） |
| `QODER_PROSE_TOO_LOW` | 2（`API参考.md`、`Python服务API.md`） | **PASS** |
| dirty-worktree | FAIL | FAIL（eval 产物） |

HARD codes（本轮无 `QODER_PROSE_TOO_LOW`）：`QODER_MANIFEST_PATH_INVALID`、`QODER_PAGE_QUALITY_STATE_MISSING`、`QODER_UNRESOLVED_FACT_CONFLICT`、`QODER_REQUIRED_INVENTORY_MISSING`、`QODER_CITATION_INVALID`、`QODER_CITATION_FACT_COVERAGE_LOW`、`QODER_OWNER_COVERAGE_MISSING`、`QODER_CITATION_RELEVANCE_MISMATCH`、`QODER_API_MERMAID_MISSING`、`QODER_DATA_MODEL_ER_MERMAID_MISSING`、`QODER_PAGE_DUMP`、`QODER_DIRTY_WORKTREE`。

## Must-check

1. Overview RealWorld/Conduit：**FAIL**（仍是 init-stub / api-gateway；Conduit 只来自 eval `AGENTS.md` / `round3-report.md` 污染）。
2. 真实 `/api` 路由、未编造 `/health` `/webhook` `/items`：**PASS**（本轮产品契约）。
3. tests/docs 不充当产品 api-server：**FAIL**（`核心服务/Tests.md` 仍在）。
4. Init stub 不当身份：**FAIL**。
5. eval 产物不当证据：**FAIL**（`file:AGENTS.md` / `file:round3-report.md`）。

## 残留（本 PR 不改 generator/scanner）

1. README/Conduit 仍输给 init stub；应忽略 eval 文件当产品证据。
2. citation `file:` 前缀（27→**62**）。
3. owner mapping 在正确的 `/api` 路径上仍 19/19 missing。
4. tests-as-product（`核心服务/Tests.md`）。
5. #49 skip path 本轮 **未证实**——除非 review 发现仍有 gather-all timeout，否则不另开 PR。
6. eval-layout HARD 是布局问题，不是产品失败——不要松阈值。
