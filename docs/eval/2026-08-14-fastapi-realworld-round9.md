# FastAPI RealWorld 对照 Wiki 第九轮评测

**对照仓：** nsidnev/fastapi-realworld-example-app `029eb7781c60d5f563ee8990a0cbfb79b244538c`
**CLI：** repo-wiki 0.1.0 @ `395e4c4ecee45ebc9ea98125a3223d3216686b3b`（#64 HEAD；含 #59 owner + #61 relpath + #63 think + #64 taxonomy）
**时间：** 2026-08-14 21:02:37–21:24:09 CST（wall **21m32s**）
**run：** run-1786712557785
**模型：** MiniMax-M3，cache 0/81
**verify JSON：** `docs/eval/2026-08-14-fastapi-realworld-round9-verify.json`

第八轮评测见 `docs/eval/2026-08-14-fastapi-realworld-round8.md`。  
对照 wrap 见 `docs/eval/2026-08-13-fastapi-realworld-wrap.md`。

## Index / identity

19 `/api/*` including POST /api/users/login. No relative leftovers. Identity Conduit HIT. No `:target:` junk.

## Generate vs r8

| 项 | r8 | **r9** |
|---|---|---|
| planned / written | 89 / 89 | **81 / 81** |
| LLM PASS / DEGRADED | 89 / 0 | **67 / 14** |
| fallback | 0 | **14**（Insufficient prose，不是 529） |
| 529 / circuit-break | 0 / false | **0 / false** |
| Tests.md | 在 | **gone** |
| Agent代理API / API网关 / 前端应用 / 服务网格 | 在 | **gone**（另少 微服务设计） |
| `<think>` pages | 89 | **0** |
| `file:` / `relpath:` leftover | 0 / 108 | **0 / 0** |
| owner missing API | 19 `/api/*` | **0** |
| Overview=Conduit | HIT | **HIT** |
| wall | 38m28s | **21m32s** |

#59 HIT（19 API owner 齐）. #61 HIT（relpath 0）. #63 HIT（think 0）. #64 HIT（8 个幻觉/测试页消失）.

## Verify

exit 1 / FAIL NOT_READY. HARD 13 / SOFT 0. Gates **not** relaxed. Prose HARD failed ×2 this run (r8 passed it).

| | r8 | **r9** |
|---|---|---|
| 无效 citation | 108 | **1**（`README.md:1-3`；仓里是 README.rst） |
| claim coverage | 42.28% | **49.93%**（764/1530）仍 << 95% |
| page dumps | 12 + 89 think | **26**；0 think |
| API / ER mermaid miss | 9 / 5 | **6 / 3** |
| owner missing | 29 | **9 models only** |
| QODER_PROSE_TOO_LOW | PASS | **FAIL ×2** |

残留 9 个 model：DateTimeModelMixin IDModelMixin RWModel ArticlesFilters JWTMeta JWTUser ProfileInResponse TagsInList UserInUpdate.

不要声称门槛放松。coverage 回升主要是 think 注水没了。
