# FastAPI RealWorld 对照 Wiki 第十二轮评测

**对照仓：** nsidnev/fastapi-realworld-example-app `029eb7781c60d5f563ee8990a0cbfb79b244538c`
**CLI：** `6c98b06`（本地合入 #72→#73→#74→#75 onto main `1fe6840`；未推进 main）
**时间：** 2026-08-17 09:16:30–09:32:43 CST（generate wall **16m13s**；verify wall 4s）
**run：** r12-2026-08-17b
**模型：** MiniMax-M3，host `api.minimaxi.com`（`LLM_BASE_URL=https://api.minimaxi.com/v1`），cache 0/81
**verify JSON：** `docs/eval/2026-08-15-fastapi-realworld-round12-verify.json`

本文件替换 #77 先前的凭据阻断文案。本轮是真实 MiniMax generate，不是 MockLLM。

第十一轮评测见 `docs/eval/2026-08-14-fastapi-realworld-round11.md`（#71，docs-only）。  
对照 wrap 见 `docs/eval/2026-08-13-fastapi-realworld-wrap.md`。

本 PR 只含评测文档。未改产品代码。未把 #72–#75 推进 main。未包含 #76。门槛未放宽。不要声称 #72–#75 全部清掉。

## Hits / Misses（相对 R11 leftover HARD）

| leftover code | R11 | **R12** | |
|---|---|---|---|
| `QODER_MANIFEST_PATH_INVALID` | HARD | 未发出（WARN `QODER_MANIFEST_NOT_READY` target_dirty=true） | **HIT** |
| `QODER_PAGE_QUALITY_STATE_MISSING` | HARD | 未发出（`QODER_PAGE_QUALITY_STATE_DEGRADED` 因 16 fallback） | **HIT** |
| `QODER_UNRESOLVED_FACT_CONFLICT` | HARD | FAIL（README.rst `STALE_DOC_REFERENCE`；unresolved_count 2，同一 JSON 在 `reports/` 与 `meta/`） | **MISS** |
| `QODER_REQUIRED_INVENTORY_MISSING` | HARD | 未发出（owner 洞改为 `QODER_OWNER_COVERAGE_MISSING`） | **HIT** |
| `QODER_CITATION_FACT_COVERAGE_LOW` | HARD 50.87% | FAIL **66.51%**（1017/1529）；门仍是 95% | **MISS**（改善，仍低于门） |
| `QODER_CITATION_RELEVANCE_MISMATCH` | HARD | FAIL（message 28 / details 20） | **MISS** |
| `QODER_PAGE_DUMP` | HARD（25 detected） | PASS | **HIT** |
| `QODER_PROSE_TOO_LOW` | HARD ×6 | PASS（6 页 insufficient-prose 走 fallback；该 leftover code 未发出） | **HIT** |
| `QODER_DIRTY_WORKTREE` | HARD | FAIL（untracked `.repo-agent-eval/`） | **MISS** |

#72 HIT（两条 leftover code 均未再以原名发出）。#73 MIXED（inventory HIT / conflict MISS）。#74 HIT（dump + prose leftover code 未发出）。#75 MISS（coverage + relevance 仍 HARD）。不要声称四张产品 PR 全部清掉。

## Generate

GENERATE_EXIT=0。Cold cache：cache_hits=0，cache_misses=81。

| 项 | R11 | **R12** |
|---|---|---|
| planned / written | 81 / 81 | **81 / 81** |
| LLM PASS / DEGRADED | 71 / 10 | **65 / 16** |
| generation_mode | llm 71（fallback 10 仍计 LLM 调用后 prose reject） | llm=65 fallback=16 |
| llm_call_count / tokens | 81 / — | **71 / 279211** |
| fallback | 10 prose + 0 skip | **10 timeout 60s + 6 insufficient prose** |
| 529 / circuit-break | 0 / false | **0 / false** |
| provider_failure_count | 0 | **0** |
| empty-content | 0 | **0** |
| Overview Conduit | HIT | **MISS**（overview 页是 fallback） |
| wall | 22m26s | **16m13s** generate + 4s verify |

16 fallback：

- timeout 60s ×10：readme, installation, data-models-overview, deployment-overview, database-migration-strategy, core, logging, authentication, common-issues, error-codes
- insufficient prose ×6：project-overview, api-overview, system-components, models, services, ide-setup

## Compare

| | R11 | **R12** |
|---|---|---|
| CLI | `1fe6840` / #70 | **`6c98b06`** / #72+#73+#74+#75（未进 main） |
| coverage | 50.87%（761/1496） | **66.51%**（1017/1529）仍 << 95% |
| HARD / SOFT | 9 / 0 | **7 / 0**（未放宽） |
| page dump | HARD | **PASS** |
| prose too low | HARD ×6 | **PASS**（code 未发出） |
| owner missing | 0（items=30） | **2**（services `app`, `db`） |
| mermaid API / ER miss | 0 / 0 | **0 / 0** |
| invalid cites / file: / relpath / think | 0 / 0 / 0 / 0 | **0 / 0 / 0 / 0** |
| empty taxonomy | 0 | **0** |

## Verify

VERIFY_EXIT=1 / FAIL。HARD 7 / SOFT 0。Gates **not** relaxed。95% coverage 门未改。

Leftover HARD：

1. `QODER_PAGE_QUALITY_STATE_DEGRADED`（16 fallback）
2. `QODER_UNRESOLVED_FACT_CONFLICT`（README.rst STALE_DOC_REFERENCE；count 2 = reports/ + meta/）
3. `QODER_CRITICAL_FALSE_FACT`（`/api/articles*` on `故障排除/API问题.md`, `核心服务/API.md`, `开发指南/API开发指南.md`）
4. `QODER_CITATION_FACT_COVERAGE_LOW` 66.51%（1017/1529）
5. `QODER_OWNER_COVERAGE_MISSING` services `app`, `db`
6. `QODER_CITATION_RELEVANCE_MISMATCH`（message 28 / details 20）
7. `QODER_DIRTY_WORKTREE`（untracked `.repo-agent-eval/`）

WARN：`QODER_MANIFEST_NOT_READY`（target_dirty=true）。SOFT none。

新残差（R11 没有、本轮 HARD）：`QODER_CRITICAL_FALSE_FACT`、`QODER_PAGE_QUALITY_STATE_DEGRADED`、`QODER_OWNER_COVERAGE_MISSING`。不要把 HARD 9→7 解读成门槛放松。

不要在本评测 PR 里改产品代码。不要把 #72–#75 合进 main。
