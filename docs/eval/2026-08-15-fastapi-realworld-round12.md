# FastAPI RealWorld 对照 Wiki 第十二轮评测

**对照仓：** nsidnev/fastapi-realworld-example-app `029eb7781c60d5f563ee8990a0cbfb79b244538c`
**CLI（本地合入，未推进 main）：** `c8033aa` = main `1fe6840` + #72 `9693b16` + #73 `6253398` + #74 `23db73f` + #75 `6b69586`
**时间：** 2026-08-15 CST。generate **未跑**。
**模型：** MiniMax-M3（与 R11 相同；本环境无法调用）
**verify JSON：** `docs/eval/2026-08-15-fastapi-realworld-round12-verify.json`

第十一轮评测见 `docs/eval/2026-08-14-fastapi-realworld-round11.md`（#71，docs-only，未合入 main）。  
对照 wrap 见 `docs/eval/2026-08-13-fastapi-realworld-wrap.md`。

本 PR 只含评测文档。未改产品代码。未把 #72–#75 推进 main。未包含 #76。门槛未放宽。

## Blocked

本云环境 **没有 MiniMax / LLM 凭据**，generate 未执行，**没有编造指标**。

证据：

- `printenv` 无 `MINIMAX_API_KEY`、`LLM_*`、`OPENAI_API_KEY`、`APP_LLM_MINIMAX*`、`REPO_WIKI_LLM_API_KEY`
- 无 `repo-wiki.yaml` / `.repo-wiki.yaml` / `.env`
- Cursor environment-info：`environment: null`（无 linked environment / 无注入 secrets）
- 在本地合入 CLI `c8033aa` 上 `python3 -m repo_wiki.main config --ci` → `summary=FAIL`，`api_key_present=false`，`issues=["api_key_env: MISSING_API_KEY"]`（默认解析为 openai/gpt-4o-mini，因为 MiniMax env 也不存在）

未使用 MockLLM，未放宽 HARD/SOFT，未改 95% coverage 门。

## Local merge

从 main `1fe6840` 建本地分支，依次 merge #72 #73 #74 #75。**无冲突**（`qoder_strict_verifier.py` / `service.py` 由 ort 自动合并）。未把该 merge 推到 main，也未开产品 PR。

| PR | HEAD | 目标 HARD | 本轮 |
|---|---|---|---|
| #72 | `9693b16` | `QODER_PAGE_QUALITY_STATE_MISSING`, `QODER_MANIFEST_PATH_INVALID` | **N/A**（无 generate/verify） |
| #73 | `6253398` | `QODER_REQUIRED_INVENTORY_MISSING`, `QODER_UNRESOLVED_FACT_CONFLICT` | **N/A** |
| #74 | `23db73f` | `QODER_PAGE_DUMP`, `QODER_PROSE_TOO_LOW` | **N/A** |
| #75 | `6b69586` | `QODER_CITATION_FACT_COVERAGE_LOW`, `QODER_CITATION_RELEVANCE_MISMATCH` | **N/A** |
| #76 | — | host polish | 未纳入 eval CLI |

R11 leftover `QODER_DIRTY_WORKTREE` 是评测产物，本轮无 run，故 **N/A**。owner / mermaid / cite 回归检查同样 **N/A**。

## Compare（R11 基线；R12 无新数字）

| | R11 | **R12** |
|---|---|---|
| CLI | `1fe6840` / #70 | 本地 `c8033aa` / #72+#73+#74+#75（未进 main） |
| generate | EXIT=0；81/81；cache 0/81 | **未跑** |
| LLM PASS / DEGRADED | 71 / 10 | **N/A** |
| fallback | 10 prose + 0 skip | **N/A** |
| coverage | 50.87%（761/1496）仍 << 95% | **N/A**（门仍是 95%） |
| HARD / SOFT | 9 / 0 | **N/A**（门未放宽） |
| VERIFY_EXIT | 1 / FAIL NOT_READY | **未跑** |

R11 leftover HARD（本轮无法证实是否消失）：`QODER_MANIFEST_PATH_INVALID`, `QODER_PAGE_QUALITY_STATE_MISSING`, `QODER_UNRESOLVED_FACT_CONFLICT`, `QODER_REQUIRED_INVENTORY_MISSING`, `QODER_CITATION_FACT_COVERAGE_LOW`, `QODER_CITATION_RELEVANCE_MISMATCH`, `QODER_PAGE_DUMP`（25 detected, listed 10）, `QODER_PROSE_TOO_LOW`（×6）, `QODER_DIRTY_WORKTREE`。

## Next

注入 `MINIMAX_API_KEY`（`LLM_PROVIDER=minimax`，`LLM_MODEL=MiniMax-M3`）后，在同一合入 SHA `c8033aa` 上：挪开 composer cache，对对照仓跑 `generate --profile qoder-like --output .repo-agent-eval`，再 `verify --profile qoder-like --ci`。用真实 HARD codes / coverage / dump / prose 把上表 N/A 改成 HIT / MISS。不要松门槛。不要把 #72–#75 合进 main。
