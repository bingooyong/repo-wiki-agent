# FastAPI RealWorld 对照 Wiki 第三轮评测

**对照仓：** nsidnev/fastapi-realworld-example-app `029eb7781c60d5f563ee8990a0cbfb79b244538c`  
**CLI：** repo-wiki `0.1.0` @ `a3d58b4f196a8189d822fc0f2b5a3aa7b26071e2`（PR #45 已合并）  
**模型：** MiniMax-M3 openai-compat；YAML timeout 180s；`max_concurrent=2`  
**时间：** 2026-08-13 23:20:26–23:36:06 CST（约 15m40s）  
**run id：** `run-1786634426299`  
**verify JSON：** `docs/eval/2026-08-13-fastapi-realworld-round3-verify.json`

第二轮评测见 `docs/eval/2026-08-13-fastapi-realworld-round2.md`。第四轮评测见 `docs/eval/2026-08-14-fastapi-realworld-round4.md`。

## 生成

| 项 | r2 | r3 |
|---|---|---|
| generate | 89/89 | 89/89 |
| cache | — | 0/89 |
| 空壳 “LLM composer did not return content” | 0/89 | **0/89**（守住） |
| 529 | 0 | **16 页**，随后 `provider_disabled_after_failures=true` |
| fallback / rejected | 2 | **26**（16×529 + 6×空 assistant content + 4×insufficient prose） |
| LLM | 89 calls / 329668 tokens | 89 / 245251 |
| endpoints | 19（相对路径） | **19 mounted** |
| wiki 中 UNRESOLVED | 0 | **0** |

空 assistant content 6 页走了 fallback，**不是**假 PASS 空壳。insufficient prose 4 页未点名。

**529 页：** configuration, environment-setup, monitoring, logging, container-deployment, kubernetes-deployment, cicd-pipeline, backup-recovery, scaling, deployment-issues, authentication, authorization, data-protection, encryption, audit-logging, compliance-frameworks。

**空 content fallback：** local-setup, testing-guide, code-style, contribution, security-best-practices, vulnerability-management。

Wiki API参考列出全部 19 条 mounted 路径；`/users/login` 出现在 **14 页**；`POST /login` 与 `GET /feed` **0 hits**。Overview **仍不是** Conduit（仍是 api-gateway / repo-wiki-init-stub）。

## Index（#45 证明）

r2 为 19 条相对路径；r3 为 **19 mounted**。相对残留 `POST /login` `GET /feed` `GET /`：**无**。`settings.api_prefix=/api`：**仍缺**（scanner 不跟随 `get_app_settings()` 工厂）。

Mounted 19：

- `POST /users/login` `POST /users` `GET /user` `PUT /user`
- `GET /articles` `POST /articles` `GET /articles/feed` `GET /articles/{slug}` `PUT /articles/{slug}` `DELETE /articles/{slug}`
- `POST /articles/{slug}/favorite` `DELETE /articles/{slug}/favorite`
- `GET /articles/{slug}/comments` `POST /articles/{slug}/comments` `DELETE /articles/{slug}/comments/{comment_id}`
- `GET /profiles/{username}` `POST /profiles/{username}/follow` `DELETE /profiles/{username}/follow`
- `GET /tags`

HIT 含：`POST /users/login`、`GET /articles/feed`、`GET /articles/{slug}`、`POST /users`、`GET/PUT /user`、`GET/POST /articles`、favorite/comments、profiles、`GET /tags`。

## Verify

exit 1，FAIL `NOT_READY`。**13 HARD / 0 SOFT**（与 r2 **同一组** reason code）。未放宽任何阈值。

| 项 | r2 | r3 |
|---|---|---|
| 页质量 | — | PASS **63** / DEGRADED **26** |
| 无效 citation | 56 | **27**（其中 26 为 `file:` 前缀） |
| claim coverage | 51.28%（900/1755） | **38.05%**（613/1611，fallback 拉低） |
| page dumps | 10 | **32** |
| API mermaid 缺失 | — | 9 |
| API aggregation | PASS 13/13 | PASS **13/13** |
| owner missing | 21 | **23**（14 条 v3 相对 API 路径 + 9 models） |
| `QODER_PROSE_TOO_LOW` | — | 2（`API参考.md`、`Python服务API.md`） |
| dirty-worktree | FAIL | FAIL（eval 产物） |

HARD codes（与 r2 相同）：`QODER_MANIFEST_PATH_INVALID`、`QODER_PAGE_QUALITY_STATE_MISSING`、`QODER_UNRESOLVED_FACT_CONFLICT`、`QODER_REQUIRED_INVENTORY_MISSING`、`QODER_CITATION_INVALID`、`QODER_CITATION_FACT_COVERAGE_LOW`、`QODER_OWNER_COVERAGE_MISSING`、`QODER_CITATION_RELEVANCE_MISMATCH`、`QODER_API_MERMAID_MISSING`、`QODER_DATA_MODEL_ER_MERMAID_MISSING`、`QODER_PAGE_DUMP`、`QODER_PROSE_TOO_LOW`、`QODER_DIRTY_WORKTREE`。

## Must-check

1. Overview RealWorld/Conduit：**FAIL**（00 仍是 api-gateway / core-platform / repo-wiki-init-stub）。
2. 真实路由、未编造 `/health` `/webhook` `/items`：**PASS**（本轮产品契约）。
3. tests/docs 不充当产品 api-server：**FAIL**（`核心服务/Tests.md` 仍在）。
4. Init stub 不当身份：**FAIL**。

## 残留（本 PR 不改 generator/scanner）

1. v3 scanner 仍按文件 `extract_fastapi_endpoints`；verify owner 看到 `POST /login`，wiki 已是 `POST /users/login`。
2. `settings = get_app_settings(); prefix=settings.api_prefix` 未解析到 `/api`。
3. README/Conduit 仍输给 init stub + `AGENTS.md`。
4. citation `file:` 前缀（还剩 27）。
5. 529 circuit-break：89 个 job 在 `gather` 前已全部入队，失败无法中途停跑。
6. eval-layout HARD 是布局问题，不是产品失败——不要松阈值。
