# FastAPI RealWorld 对照 Wiki 第十六轮评测

**对照仓：** nsidnev/fastapi-realworld-example-app `029eb7781c60d5f563ee8990a0cbfb79b244538c`
**CLI：** `c8a30a690a95ab13692f186c6ee59190dec4ead4`（本地分支 `r16-eval-local`；r15-eval-local `6b966d4` = r14 `278164e` + #87 `e1073f6`，再 merge #89 `025d7d2272836cea6c6416e4bd04131a9ec5bd8e`（`cursor/fix-fastapi-sibling-layer-relevance-2e1d`）；auto-merge，无需 keep-both；仅用于叠评测；**未推送、未进 origin/main**）
**时间：** 2026-08-18 CST（generate 08:58:39–09:14:35 CST，wall **15m56s** / compose 955.3s；verify 09:15:16–09:15:19 CST，wall 3s）
**run：** r16-2026-08-18
**模型：** MiniMax-M3，host `api.minimaxi.com`，timeout 180，cache 0/81
**verify JSON：** `docs/eval/2026-08-18-fastapi-realworld-round16-verify.json`

本轮是真实 MiniMax generate，不是 MockLLM。

第十五轮评测见 `docs/eval/2026-08-17-fastapi-realworld-round15.md`（#88，docs-only）。  
对照 wrap 见 `docs/eval/2026-08-13-fastapi-realworld-wrap.md`。

本 PR 只含评测文档。未改产品代码。未编辑 #71–#89。未把 #72–#75+#82+#83+#85+#87+#89 推进 main。未叠到 #88。门槛未放宽。不要声称 leftover HARD 已清。HARD 计数 4→3。

## Hits / Misses（相对 R15 leftover HARD）

| leftover code | R15 | **R16** | |
|---|---|---|---|
| `QODER_PAGE_QUALITY_STATE_DEGRADED` | FAIL（11 fallback） | FAIL（4 fallback） | **MISS**（11→4，仍是 HARD） |
| `QODER_CITATION_FACT_COVERAGE_LOW` | FAIL **67.02%**（951/1419）；门仍是 95% | FAIL **68.76%**（940/1367）；门仍是 95% | **MISS**（略升，仍 << 95%） |
| `QODER_CITATION_RELEVANCE_MISMATCH` | FAIL（message 25 / details 20） | **PASS**（"All citations appear relevant to their pages"；mismatches n=0） | **HIT（#89）** |
| `QODER_DIRTY_WORKTREE` | FAIL（untracked `.repo-agent-eval/`） | FAIL（untracked `.repo-agent-eval/`） | **MISS** |
| `QODER_API_AGGREGATION_LOW` | PASS 6/6 | **PASS 6/6** | 与 R15 同一 leftover-clear |

#89 目标是 sibling-layer citation relevance（R15 形态 `QODER_CITATION_RELEVANCE_MISMATCH`）。本轮该门 **HIT / PASS**。1×529 是单页 provider blip（`security-best-practices`），不是 relevance 接线漏。不要声称 leftover HARD 已清。HARD 4→3，计数下降但未清场。

## Generate

GENERATE_EXIT=0。Cold cache：cache_hits=0，cache_misses=81。isolated=true。不是 81-fallback auth-1004 run。

| 项 | R15 | **R16** |
|---|---|---|
| planned / written | 81 / 81 | **81 / 81** |
| LLM PASS / DEGRADED | 70 / 11 | **77 / 4** |
| llm_call_count / tokens | 81 / 302995 | **81 / 323357** |
| fallback | 11（全部 insufficient prose） | **4**（insufficient prose 3 + http 529 1） |
| 529 / circuit-break | 0 / false | **1 / false** |
| MiniMax 1004 | 0 | **0** |
| provider_failure_count | 0 | **0** |
| empty-content | 0 | **0** |
| wall | 11m10s generate + 3s verify | **15m56s** generate + 3s verify |

DEGRADED 4 页：

- project-overview / `项目概述/项目概述.md` — Insufficient prose content
- installation / `项目概述/安装与配置.md` — Insufficient prose content
- security-overview / `安全合规.md` — Insufficient prose content
- security-best-practices / `安全合规/安全最佳实践.md` — Composition error: Server error: 529

## Compare

| | R15 | **R16** |
|---|---|---|
| CLI | `6b966d4` / r14 栈 + #87 `e1073f6`（本地 `r15-eval-local`；未推送；未进 main） | **`c8a30a6`** / r15 栈 + #89 `025d7d2`（本地 `r16-eval-local`；未推送；未进 main） |
| coverage | 67.02%（951/1419）；门仍是 95% | **68.76%**（940/1367）仍 << 95% |
| HARD / SOFT | 4 / 0 | **3 / 0**（未放宽） |
| owner missing | 0 | **0** |
| API aggregation | PASS 6/6 | **PASS 6/6** |
| conflict | PASS | **PASS** |
| page dumps | PASS | **PASS** |
| prose density | PASS | **PASS** |
| false-fact | PASS（#87 HIT） | **PASS** |
| relevance | FAIL（message 25 / details 20） | **PASS**（#89 HIT；n=0） |

## Verify

VERIFY_EXIT=1 / FAIL。HARD 3 / SOFT 0。Gates **not** relaxed。95% coverage 门未改。Checks：total 25，pass 21，warn 1，fail 3（R15 为 pass 20 / warn 1 / fail 4）。

WARN（不是 extra HARD）：`QODER_MANIFEST_NOT_READY`（target_dirty=true）— 与 R15 同一形态。

Leftover HARD：

1. `QODER_PAGE_QUALITY_STATE_DEGRADED`（4 fallback：insufficient prose 3 + http 529 1）
2. `QODER_CITATION_FACT_COVERAGE_LOW` 68.76%（940/1367）vs R15 67.02%；门仍是 95%
3. `QODER_DIRTY_WORKTREE`（untracked `.repo-agent-eval/`）

SOFT none。

不要把 HARD 4→3 解读成 leftover HARD 清场，也不要解读成门槛放松。#89 只 HIT 了 `QODER_CITATION_RELEVANCE_MISMATCH`。

不要在本评测 PR 里改产品代码。不要把 #72–#75+#82+#83+#85+#87+#89 合进 main。
