# FastAPI RealWorld 对照 Wiki 第十一轮评测

**对照仓：** nsidnev/fastapi-realworld-example-app `029eb7781c60d5f563ee8990a0cbfb79b244538c`
**CLI：** `1fe6840`（#70 HEAD；含 #66/#67/#68 + #70 prose rejects 不消耗 provider failure budget）
**时间：** 2026-08-14 22:43:54–23:06:20 CST（wall 22m26s）
**run：** run-1786718634433
**模型：** MiniMax-M3，cache 0/81
**verify JSON：** `docs/eval/2026-08-14-fastapi-realworld-round11-verify.json`

第十轮评测见 `docs/eval/2026-08-14-fastapi-realworld-round10.md`。  
对照 wrap 见 `docs/eval/2026-08-13-fastapi-realworld-wrap.md`。

## Hits

- #70 HIT: 0×529; circuit-break NOT tripped（`provider_disabled_after_failures=false`, `provider_failure_count=0`）；81 LLM = 81 planned
- fallback 10（全部 Insufficient prose，page-local）+ **0 skip**。R10 是 34 LLM / 55 fallback（8 prose + 47 skip），因为连续 3 次 Insufficient prose 被算成 provider failure
- Overview `项目概述.md` Conduit HIT（LLM PASS，verbatim "passing Conduit testsuite"）。R10 是 MISS（fallback）
- Coverage 17.95% → **50.87%**（761/1496）。R9 是 49.93%。仍 << 95% HARD。这是 skip recovery，不是门槛变化
- No regress vs R9–R10: API mermaid miss 0（checked 6）；ER mermaid miss 0（checked 7）；owner missing 0（items=30；API 0 + models 0）；invalid citations 0；wiki 0 literal README.md cites；relpath 0；file: 0；think 0；Tests.md gone；empty taxonomy（API网关 / 前端应用 / 服务网格 / Agent代理API）gone；19 `/api/*` including POST /api/users/login（10 pages）

## Compare

| | R9 | R10 | R11 |
|---|---|---|---|
| planned/written | 81/81 | 81/81 | 81/81 |
| LLM PASS / DEGRADED | 67 / 14 | 26 / 55 | 71 / 10 |
| fallback | 14 prose | 8 prose + 47 skip | 10 prose + 0 skip |
| 529 / circuit-break | 0 / false | 0 / **true** | 0 / **false** |
| coverage | 49.93% | 17.95% | 50.87% |
| HARD / SOFT | 13 / 0 | 9 / 0 | 9 / 0 |
| Overview Conduit | HIT | MISS | HIT |

## Verify

GENERATE_EXIT=0. VERIFY_EXIT=1 / FAIL NOT_READY. HARD 9 / SOFT 0（与 R10 同一组 leftover names）。Gates not relaxed.

Leftover HARD: QODER_MANIFEST_PATH_INVALID, QODER_PAGE_QUALITY_STATE_MISSING, QODER_UNRESOLVED_FACT_CONFLICT, QODER_REQUIRED_INVENTORY_MISSING, QODER_CITATION_FACT_COVERAGE_LOW, QODER_CITATION_RELEVANCE_MISMATCH, QODER_PAGE_DUMP（25 detected, listed 10; not think）, QODER_PROSE_TOO_LOW（×6, same 6 pages as R10）, QODER_DIRTY_WORKTREE（eval artifacts）.

不要声称门槛放松。不要再开一轮 generate。不要在本评测 PR 里改产品代码。
