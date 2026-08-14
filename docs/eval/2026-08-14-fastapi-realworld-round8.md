# FastAPI RealWorld 对照 Wiki 第八轮评测

**对照仓：** nsidnev/fastapi-realworld-example-app `029eb7781c60d5f563ee8990a0cbfb79b244538c`
**产品：** RealWorld Conduit 后端（`/api/users` `/api/users/login` `/api/user` `/api/articles` … + JWT）
**模型：** MiniMax-M3（openai-compat；非 MockLLM）
**超时 / 并发：** YAML 180s，`max_concurrent=2`；circuit-break `max_provider_failures=3`
**CLI：** repo-wiki 0.1.0 @ `05bb3b8c98d4e1634f5b227922b1952977c81b17`（PR **#58** / main）
**时间：** 2026-08-14 16:04:18–16:42:46 CST（wall **38m28s**；compose 2306.3s）
**run：** run-1786694659163

Fresh LLM run：0/89 cache.

## Index proof（#48 仍成立）

`repo-wiki index` → 19 endpoints。scanner 19 `/api/*`。

| | r7 (2e3a3f0 / #56) | **r8 (05bb3b8 / #58)** |
|---|---|---|
| endpoints | 19 `/api/*` | **19 `/api/*`** |
| `POST /api/users/login` | HIT | **HIT** |
| `GET /api/articles/feed` | HIT | **HIT** |
| relative leftovers (`POST /login` `GET /feed`) | NONE | **NONE** |

## Identity

`resolve_repository_identity` after reinstall @ `05bb3b8`:
- name: `fastapi-realworld-example-app`（pyproject.toml）
- description includes "passing Conduit testsuite"
- no `:target:` junk, no init-stub, no AGENTS.md / round*-report as product source

## Generate

exit 0。provider=openai（MiniMax-M3） mode=real。

| 项 | r7 (#56) | **r8 (#58)** |
|---|---|---|
| generate | written 89/89；LLM 仅 37 | **written 89/89；LLM 89** |
| LLM calls / tokens | 37 / 133487 | **89 / 366430** |
| cache | 0/89 | **0/89** |
| evidence spans | 350 | **350** |
| empty LLM shells | 0 | **0** |
| fallback | 57 | **0** |
| 529 | 4 | **0** |
| timeouts (180s) | 0 | **0** |
| circuit-break tripped | `true`（#49 触发） | **`false`** |
| empty assistant content | 0 | **0** |
| UNRESOLVED_API_ENDPOINTS | 0 | **0** |
| `POST /api/users/login` in wiki | 14 页 HIT | **14 页 HIT**；API参考列出全部 19 条 `/api/*` |
| Overview=Conduit | HIT | **HIT**（简介 verbatim `passing Conduit testsuite` +「通过 Conduit 测试套件」） |
| wall | ~9m00s | **~38m28s**（MiniMax 健康，打完全部 89 页） |

quality: PASS 89 / DEGRADED 0。`failed_pages=[]`。

**本轮未触发 circuit-break。** wall 38m vs r7 9m 不是变慢回归，是 r7 被 529 熔断砍掉后半程。不要把 fallback 57→0 或 coverage 回升解读成 #58 质量跃迁。

## Verify

verify_exit=**1**。HARD/SOFT **未放宽**。

| | r7 | **r8** |
|---|---|---|
| exit / grade | 1 / FAIL NOT_READY | **1 / FAIL NOT_READY** |
| HARD / SOFT | 13 / 0 | **12 / 0** |
| 页数 | 89（PASS 32 / DEGRADED 57） | **89（PASS 89 / DEGRADED 0）** |
| 无效 citation | 18（全部 `file:`） | **108**（listed 30；**`file:` = 0**；全部是字面量 `relpath:…`） |
| claim coverage | **17.75%**（298/1679） | **42.28%**（1885/4458）— MiniMax 健康回升，仍远低于 95% |
| page dumps | 25（listed 10） | **12**（listed 10）；全文 **89** 页含泄漏 `<think>` |
| API mermaid 缺失 | 9 | **9** |
| API aggregation | PASS | **PASS 13/13** |
| owner missing | 28（19 `/api/*` + 9 models） | **29（19 `/api/*` + 9 models + 1 service `db`）** |
| dirty-worktree | FAIL | FAIL（eval 产物） |
| QODER_PROSE_TOO_LOW | FAIL ×3 | **PASS**（门仍是 HARD，本轮过了，不是门槛放松） |

HARD codes: `QODER_MANIFEST_PATH_INVALID` `QODER_PAGE_QUALITY_STATE_MISSING` `QODER_UNRESOLVED_FACT_CONFLICT` `QODER_REQUIRED_INVENTORY_MISSING` `QODER_CITATION_INVALID` `QODER_CITATION_FACT_COVERAGE_LOW` `QODER_OWNER_COVERAGE_MISSING` `QODER_CITATION_RELEVANCE_MISMATCH` `QODER_API_MERMAID_MISSING` `QODER_DATA_MODEL_ER_MERMAID_MISSING` `QODER_PAGE_DUMP` `QODER_DIRTY_WORKTREE`。

### #58 citation 结论

**#58 HIT。** wiki 2680 个 `<cite>`：**0** 个 `file:` scheme；**962** 个裸 `README.rst:…`。r7 的 `file:README.rst` 「file does not exist」已消失。

本轮 108 条无效 cite 是新残差：LLM 把 prompt 模板抄进正文——83 条字面量 `<cite>relpath:start-end</cite>`，15 条 `<cite>relpath:app/main.py:…</cite>`。值得另开 PR 剥 `relpath:`（对称 #58），**不要**再为 `file:` 开重复 PR。

Owner：19 条 API 仍无 owner mapping（#59 later binds inventory defining file/handler; this eval predates #59 merge）。

## Must-check

1. Overview 是 RealWorld/Conduit？ **通过（#56 仍 HIT）。** 9 处 Conduit。无 init-stub。
2. API 真实路由含 `/api`、不发明 `/health` `/webhook`？ **产品合同本轮通过。** UNRESOLVED 0。
3. 数据模型 User/Article/Comment/Tag？ ER mermaid 仍缺 5 页。
4. tests/docs 不当产品 api-server？ **未通过。** `核心服务/Tests.md` 仍在。
5. Init stub 不当身份？ **通过。**
6. eval 产物不当证据？ **#52 仍通过。**
7. `file:` 前缀不当路径？ **#58 目标通过。**

## 残留

1. citation 字面量 `relpath:` — 108 HARD
2. owner mapping 对已前缀的 `/api/*` 仍 19/19 缺失（this eval predates #59）
3. tests-as-product — `核心服务/Tests.md`
4. taxonomy 幻觉页
5. 泄漏 `<think>` — 89 页
6. coverage 42.28% 仍 << 95%
7. eval-layout HARD
8. API mermaid 缺 9 / ER 缺 5

不要松 HARD/SOFT。coverage 回升是 provider 健康，不要声称 #58 修好了 coverage。
