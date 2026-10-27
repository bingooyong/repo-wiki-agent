# FastAPI RealWorld 对照 Wiki 第十四轮评测

**对照仓：** nsidnev/fastapi-realworld-example-app `029eb7781c60d5f563ee8990a0cbfb79b244538c`
**CLI：** `278164eff0e1de710d960356eaac95156ea8f7ad`（本地分支 `r14-eval-local`；r13 栈 #72–#75+#82+#83 @ `3053586` + #85 `550782c`；两处 keep-both 冲突解决，仅用于叠评测；**未推送**）
**时间：** 2026-08-17（generate wall **13m13s**；verify wall 4s）
**run：** r14-2026-08-17
**模型：** MiniMax-M3，host `api.minimaxi.com`，timeout 180，cache 0/81
**verify JSON：** `docs/eval/2026-08-17-fastapi-realworld-round14-verify.json`

本轮是真实 MiniMax generate，不是 MockLLM。

第十三轮评测见 `docs/eval/2026-08-17-fastapi-realworld-round13.md`（#84，docs-only）。  
对照 wrap 见 `docs/eval/2026-08-13-fastapi-realworld-wrap.md`。

本 PR 只含评测文档。未改产品代码。未编辑 #71–#85。未把 #72–#75+#82+#83+#85 推进 main。未叠到 #84。门槛未放宽。不要声称 #85 全部清掉 HARD。HARD 计数 7→5。

## Hits / Misses（相对 R13 leftover HARD）

| leftover code | R13 | **R14** | |
|---|---|---|---|
| `QODER_PAGE_QUALITY_STATE_DEGRADED` | HARD | FAIL（13 fallback） | **MISS** |
| `QODER_UNRESOLVED_FACT_CONFLICT` | FAIL（GitHub badges） | **PASS** | **HIT** |
| `QODER_CRITICAL_FALSE_FACT` | FAIL（mermaid entity） | FAIL（1 claim `DELETE /api/articles`，页 `API参考/核心服务API/API API.md`；真实路由是 `DELETE /api/articles/{slug}`），**不是** R13 mermaid entity | **MISS**（新形态） |
| `QODER_CITATION_FACT_COVERAGE_LOW` | FAIL **65.08%**；门仍是 95% | FAIL **64.44%**（928/1440）；门仍是 95% | **MISS** |
| `QODER_CITATION_RELEVANCE_MISMATCH` | FAIL | FAIL（message 27 / details 20） | **MISS** |
| `QODER_API_AGGREGATION_LOW` | FAIL | **PASS 6/6** | **HIT** |
| `QODER_DIRTY_WORKTREE` | FAIL（untracked `.repo-agent-eval/`） | FAIL（untracked `.repo-agent-eval/`） | **MISS** |
| mermaid entity shape | HARD 证据 | **gone** | **HIT** |
| owner missing | 0 | **0** | **HIT** |
| dump / prose leftover codes | PASS | **PASS** | **HIT** |

Overview Conduit：**HIT**（两张 overview 页）。

#85 目标含 mermaid entity、GitHub badges、API filename HARD。本轮 conflict **HIT**、aggregation **HIT 6/6**、mermaid entity shape **gone**。`QODER_CRITICAL_FALSE_FACT` 仍 HARD，证据换成 `DELETE /api/articles`（缺 `{slug}`）。不要声称 #85 全部清掉 HARD。HARD 7→5，计数下降但未清场。

## Generate

GENERATE_EXIT=0。Cold cache：cache_hits=0，cache_misses=81。

| 项 | R13 | **R14** |
|---|---|---|
| planned / written | 81 / 81 | **81 / 81** |
| LLM PASS / DEGRADED | — | **68 / 13** |
| llm_call_count / tokens | — | **81 / 312531** |
| fallback | — | **13**（全部 insufficient prose） |
| 529 / circuit-break | — | **0 / false** |
| MiniMax 1004 | — | **0** |
| provider_failure_count | — | **0** |
| empty-content | — | **0** |
| Overview Conduit | HIT（两张 overview 页） | **HIT**（两张 overview 页） |
| wall | — | **13m13s** generate + 4s verify |

表中 R13 生成细项未在本评测任务里给出，不补造。

## Compare

| | R13 | **R14** |
|---|---|---|
| CLI | `3053586` / #72+#73+#74+#75+#82+#83（本地 `r13-eval-local`；未推送；未进 main） | **`278164e`** / r13 栈 + #85 `550782c`（本地 `r14-eval-local`；未推送；未进 main） |
| coverage | 65.08%；门仍是 95% | **64.44%**（928/1440）仍 << 95% |
| HARD / SOFT | 7 / 0 | **5 / 0**（未放宽） |
| owner missing | 0 | **0** |
| API aggregation | HARD | **PASS 6/6** |
| conflict（GitHub badges） | HARD | **PASS** |
| false-fact | mermaid entity | **新形态** `DELETE /api/articles`（1 claim） |

## Verify

VERIFY_EXIT=1 / FAIL。HARD 5 / SOFT 0。Gates **not** relaxed。95% coverage 门未改。

Leftover HARD：

1. `QODER_PAGE_QUALITY_STATE_DEGRADED`（13 fallback）
2. `QODER_CRITICAL_FALSE_FACT` — 1 claim `DELETE /api/articles`，页 `API参考/核心服务API/API API.md`（**不是** R13 mermaid entity）。真实路由是 `DELETE /api/articles/{slug}`
3. `QODER_CITATION_FACT_COVERAGE_LOW` 64.44%（928/1440）vs R13 65.08%；门仍是 95%
4. `QODER_CITATION_RELEVANCE_MISMATCH`（message 27 / details 20）
5. `QODER_DIRTY_WORKTREE`（untracked `.repo-agent-eval/`）

SOFT none。

不要把 HARD 7→5 解读成 #85 清场，也不要解读成门槛放松。

不要在本评测 PR 里改产品代码。不要把 #72–#75+#82+#83+#85 合进 main。
