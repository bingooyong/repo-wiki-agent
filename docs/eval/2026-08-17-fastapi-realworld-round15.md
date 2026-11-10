# FastAPI RealWorld 对照 Wiki 第十五轮评测

**对照仓：** nsidnev/fastapi-realworld-example-app `029eb7781c60d5f563ee8990a0cbfb79b244538c`
**CLI：** `6b966d447b0a7b1fde569ff3a96d630dc08a0bb2`（本地分支 `r15-eval-local`；r14-eval-local `278164e` = r13 栈 #72–#75+#82+#83 @ `3053586` + #85 `550782c`，两处 keep-both，再 merge #87 `e1073f6`；`qoder_strict_verifier.py` keep-both 保留 r14 helpers 与 #87 `api_claim_in_inventory`；仅用于叠评测；**未推送**）
**时间：** 2026-08-17 CST（generate 16:39:32–16:50:42 CST，wall **11m10s**；verify 16:51:23–16:51:26 CST，wall 3s）
**run：** r15-2026-08-17
**模型：** MiniMax-M3，host `api.minimaxi.com`，timeout 180，cache 0/81
**verify JSON：** `docs/eval/2026-08-17-fastapi-realworld-round15-verify.json`

本轮是真实 MiniMax generate，不是 MockLLM。

第十四轮评测见 `docs/eval/2026-08-17-fastapi-realworld-round14.md`（#86，docs-only）。  
对照 wrap 见 `docs/eval/2026-08-13-fastapi-realworld-wrap.md`。

本 PR 只含评测文档。未改产品代码。未编辑 #71–#87。未把 #72–#75+#82+#83+#85+#87 推进 main。未叠到 #86。门槛未放宽。不要声称 leftover HARD 已清。HARD 计数 5→4。

## Hits / Misses（相对 R14 leftover HARD）

| leftover code | R14 | **R15** | |
|---|---|---|---|
| `QODER_PAGE_QUALITY_STATE_DEGRADED` | FAIL（13 fallback） | FAIL（11 fallback） | **MISS** |
| `QODER_CRITICAL_FALSE_FACT` | FAIL（`DELETE /api/articles`，页 `API参考/核心服务API/API API.md`） | **PASS**（"Structured inventory claims are consistent"；inventory_types sources, apis, services, models, runtimes；claim_count 0） | **HIT（#87）** |
| `QODER_CITATION_FACT_COVERAGE_LOW` | FAIL **64.44%**（928/1440）；门仍是 95% | FAIL **67.02%**（951/1419）；门仍是 95% | **MISS**（略升，仍 << 95%） |
| `QODER_CITATION_RELEVANCE_MISMATCH` | FAIL（message 27 / details 20） | FAIL（message 25 / details 20） | **MISS** |
| `QODER_DIRTY_WORKTREE` | FAIL（untracked `.repo-agent-eval/`） | FAIL（untracked `.repo-agent-eval/`） | **MISS** |
| `QODER_API_AGGREGATION_LOW` | PASS 6/6 | **PASS 6/6** | 与 R14 同一 leftover-clear |
| Overview Conduit | HIT（两张 overview 页） | **HIT**（两张 overview 页） | 与 R14 相同 |

#87 目标是 trailing path param false-fact（R14 形态 `DELETE /api/articles`）。本轮 `QODER_CRITICAL_FALSE_FACT` **HIT / PASS**。不要声称 leftover HARD 已清。HARD 5→4，计数下降但未清场。

## Generate

GENERATE_EXIT=0。Cold cache：cache_hits=0，cache_misses=81。isolated=true。

| 项 | R14 | **R15** |
|---|---|---|
| planned / written | 81 / 81 | **81 / 81** |
| LLM PASS / DEGRADED | 68 / 13 | **70 / 11** |
| llm_call_count / tokens | 81 / 312531 | **81 / 302995** |
| fallback | 13（全部 insufficient prose） | **11**（全部 insufficient prose） |
| 529 / circuit-break | 0 / false | **0 / false** |
| MiniMax 1004 | 0 | **0** |
| provider_failure_count | 0 | **0** |
| empty-content | 0 | **0** |
| Overview Conduit | HIT（两张 overview 页） | **HIT**（两张 overview 页） |
| wall | 13m13s generate + 4s verify | **11m10s** generate + 3s verify |

DEGRADED 11 页（全部 Insufficient prose content）：event-architecture、database-architecture、authentication-authorization-api、api-development、core-data-models、services、kubernetes-deployment、deployment-issues、vulnerability-management、testing-guide、performance-optimization。R14 为 13；本轮多过的两页属于更早 fallback 集合，不点名。

## Compare

| | R14 | **R15** |
|---|---|---|
| CLI | `278164e` / r13 栈 + #85 `550782c`（本地 `r14-eval-local`；未推送；未进 main） | **`6b966d4`** / r14 栈 + #87 `e1073f6`（本地 `r15-eval-local`；未推送；未进 main） |
| coverage | 64.44%（928/1440）；门仍是 95% | **67.02%**（951/1419）仍 << 95% |
| HARD / SOFT | 5 / 0 | **4 / 0**（未放宽） |
| owner missing | 0 | **0** |
| API aggregation | PASS 6/6 | **PASS 6/6** |
| conflict | PASS | **PASS** |
| Overview Conduit | HIT（两张 overview 页） | **HIT**（两张 overview 页） |
| false-fact | `DELETE /api/articles`（1 claim） | **PASS**（#87 HIT；claim_count 0） |

## Verify

VERIFY_EXIT=1 / FAIL。HARD 4 / SOFT 0。Gates **not** relaxed。95% coverage 门未改。Checks：total 25，pass 20，warn 1，fail 4（R14 为 pass 19 / warn 1 / fail 5）。

WARN（不是 extra HARD）：`QODER_MANIFEST_NOT_READY`（target_dirty=true）— 与 R14 同一形态。

Leftover HARD：

1. `QODER_PAGE_QUALITY_STATE_DEGRADED`（11 fallback，全部 insufficient prose）
2. `QODER_CITATION_FACT_COVERAGE_LOW` 67.02%（951/1419）vs R14 64.44%；门仍是 95%
3. `QODER_CITATION_RELEVANCE_MISMATCH`（message 25 / details 20；details 全部 "citation path indicates different service"：Db.md ×5 → `app/models/domain/users.py`（expected database）；API.md ×1 → `tests/test_schemas/test_rw_model.py`（expected api）；API参考.md ×3 `app/db/queries/tables.py` + ×1 `app/models/domain/users.py`（expected api）；API API.md ×2 `app/db/queries/tables.py` + ×2 `tests/test_schemas/test_rw_model.py`（expected api）；核心服务API.md ×3 `app/db/queries/tables.py` + ×2 `tests/test_schemas/test_rw_model.py`（expected api）；Python服务API.md ×1 `app/db/queries/tables.py`（expected api））
4. `QODER_DIRTY_WORKTREE`（untracked `.repo-agent-eval/`）

SOFT none。

不要把 HARD 5→4 解读成 leftover HARD 清场，也不要解读成门槛放松。#87 只 HIT 了 `QODER_CRITICAL_FALSE_FACT`。

不要在本评测 PR 里改产品代码。不要把 #72–#75+#82+#83+#85+#87 合进 main。
