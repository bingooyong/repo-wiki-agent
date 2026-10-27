# FastAPI RealWorld 对照 Wiki 第十三轮评测

**对照仓：** nsidnev/fastapi-realworld-example-app `029eb7781c60d5f563ee8990a0cbfb79b244538c`
**CLI：** `3053586069ff4a285a989821939c27f866502f5c`（本地分支 `r13-eval-local`；把 #72 #73 #74 #75 #82 #83 合到 main `1fe6840`；两处 keep-both 冲突解决，仅用于叠评测；**未推送**）
**时间：** 2026-08-17（generate wall **16m42s**；verify wall 4s）
**run：** r13-2026-08-17
**模型：** MiniMax-M3，host `api.minimaxi.com`，timeout 180，cache 0/81
**verify JSON：** `docs/eval/2026-08-17-fastapi-realworld-round13-verify.json`

本轮是真实 MiniMax generate，不是 MockLLM。

第十二轮评测见 `docs/eval/2026-08-15-fastapi-realworld-round12.md`（#77，docs-only）。  
第十一轮评测见 `docs/eval/2026-08-14-fastapi-realworld-round11.md`（#71，docs-only）。  
对照 wrap 见 `docs/eval/2026-08-13-fastapi-realworld-wrap.md`。

本 PR 只含评测文档。未改产品代码。未编辑 #71–#83。未把 #72–#75+#82+#83 推进 main。未叠到 #77。门槛未放宽。不要声称 #72–#75+#82+#83 全部清掉。HARD 计数未下降。

## Hits / Misses（相对 R12 leftover HARD）

| leftover code | R12 | **R13** | |
|---|---|---|---|
| `QODER_PAGE_QUALITY_STATE_DEGRADED` | HARD（16 fallback） | FAIL（12 fallback） | **MISS** |
| `QODER_UNRESOLVED_FACT_CONFLICT` | FAIL（README.rst `STALE_DOC_REFERENCE`；unresolved_count 2 = `reports/` + `meta/`；证据 `.env` / `/docs` / `/redoc`） | FAIL（README.rst `STALE_DOC_REFERENCE`；unresolved_count 2 = `reports/` + `meta/` 重复）。证据是 GitHub badge/path tokens（`app/blob/master/license`，`app/workflows/api`），**不是** R12 的 `.env` / `/docs` / `/redoc` | **MISS**（新证据） |
| `QODER_CRITICAL_FALSE_FACT` | FAIL（`/api/articles*` dump：`故障排除/API问题.md`，`核心服务/API.md`，`开发指南/API开发指南.md`） | FAIL（6 张 API 页声称 service `entity`，**不是** R12 `/api/articles*` dump）：`API参考/错误处理与状态码.md`，`认证授权API.md`，`API参考.md`，`核心服务API/API API.md`，`核心服务API.md`，`Python服务API.md` | **MISS**（新形态） |
| `QODER_CITATION_FACT_COVERAGE_LOW` | FAIL **66.51%**（1017/1529）；门仍是 95% | FAIL **65.08%**（874/1343）；门仍是 95% | **MISS** |
| `QODER_OWNER_COVERAGE_MISSING` | FAIL（services `app`, `db`） | owner check **PASS**，0 missing | **HIT** |
| `QODER_CITATION_RELEVANCE_MISMATCH` | FAIL（message 28 / details 20） | FAIL（message 36 / details 20） | **MISS** |
| `QODER_DIRTY_WORKTREE` | FAIL（untracked `.repo-agent-eval/`） | FAIL（untracked `.repo-agent-eval/`） | **MISS** |
| `QODER_PAGE_DUMP` | PASS | 该 leftover code 未作为本轮 HARD 发出 | **HIT**（相对 R12 leftover） |
| `QODER_PROSE_TOO_LOW` | PASS（code 未发出） | 该 leftover code 未作为本轮 HARD 发出 | **HIT**（相对 R12 leftover） |

Overview Conduit：**HIT**（两张 overview 页）。R12 是 MISS（overview fallback）。

#82 目标是 R12 的 `/api/articles*` dump 形态；本轮 `QODER_CRITICAL_FALSE_FACT` 仍 HARD，证据换成 service `entity`。#83 owner **HIT**；conflict **MISS**（新证据）。不要声称 #72–#75+#82+#83 全部清掉。HARD 仍是 7，计数未下降。

## Generate

GENERATE_EXIT=0。Cold cache：cache_hits=0，cache_misses=81。

| 项 | R12 | **R13** |
|---|---|---|
| planned / written | 81 / 81 | **81 / 81** |
| LLM PASS / DEGRADED | 65 / 16 | **69 / 12** |
| llm_call_count / tokens | 71 / 279211 | **81 / 316375** |
| fallback | 10 timeout 60s + 6 insufficient prose | **12**（9 insufficient prose + 3 composition Server error 529） |
| 60s page timeout | 10 | **0** |
| 529 / circuit-break | 0 / false | **3 composition 529 / false** |
| MiniMax 1004 | — | **0** |
| provider_failure_count | 0 | **0** |
| empty-content | 0 | **0** |
| Overview Conduit | MISS（overview fallback） | **HIT**（两张 overview 页） |
| wall | 16m13s generate + 4s verify | **16m42s** generate + 4s verify |

## Compare

| | R12 | **R13** |
|---|---|---|
| CLI | `6c98b06` / #72+#73+#74+#75（未进 main） | **`3053586`** / #72+#73+#74+#75+#82+#83（本地 `r13-eval-local`；未推送；未进 main） |
| coverage | 66.51%（1017/1529）仍 << 95% | **65.08%**（874/1343）仍 << 95% |
| HARD / SOFT | 7 / 0 | **7 / 0**（同一计数，不同 mix；未放宽） |
| owner missing | 2（services `app`, `db`） | **0**（owner check PASS） |
| page dump / prose too low leftover code | PASS / PASS | **PASS / PASS**（code 未发出） |
| API aggregation | 未作为本轮 HARD | **NEW HARD** `QODER_API_AGGREGATION_LOW`（aggregated_apis=5，total_api_pages=9） |

## Verify

VERIFY_EXIT=1 / FAIL。HARD 7 / SOFT 0。Gates **not** relaxed。95% coverage 门未改。

Leftover HARD：

1. `QODER_PAGE_QUALITY_STATE_DEGRADED`（12 fallback）
2. `QODER_UNRESOLVED_FACT_CONFLICT` — README.rst `STALE_DOC_REFERENCE`；unresolved_count 2（`reports/` + `meta/` 重复）。证据是 GitHub badge/path tokens（`app/blob/master/license`，`app/workflows/api`），**不是** R12 的 `.env` / `/docs` / `/redoc`
3. `QODER_CRITICAL_FALSE_FACT` — 6 张 API 页声称 service `entity`（**不是** R12 `/api/articles*` dump）：`API参考/错误处理与状态码.md`，`认证授权API.md`，`API参考.md`，`核心服务API/API API.md`，`核心服务API.md`，`Python服务API.md`
4. `QODER_CITATION_FACT_COVERAGE_LOW` 65.08%（874/1343）vs R12 66.51%；门仍是 95%
5. `QODER_CITATION_RELEVANCE_MISMATCH`（message 36 / details 20）
6. `QODER_API_AGGREGATION_LOW` **NEW** vs R12；aggregated_apis=5，total_api_pages=9
7. `QODER_DIRTY_WORKTREE`（untracked `.repo-agent-eval/`）

SOFT none。

新残差（R12 leftover 表里没有、本轮 HARD）：`QODER_API_AGGREGATION_LOW`。不要把 HARD 计数仍为 7 解读成 #82+#83 清场，也不要解读成门槛放松。

不要在本评测 PR 里改产品代码。不要把 #72–#75+#82+#83 合进 main。
