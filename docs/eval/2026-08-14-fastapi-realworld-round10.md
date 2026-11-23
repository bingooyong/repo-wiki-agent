# FastAPI RealWorld 对照 Wiki 第十轮评测

**对照仓：** nsidnev/fastapi-realworld-example-app `029eb7781c60d5f563ee8990a0cbfb79b244538c`
**CLI：** `cc868d3` (#68 HEAD；含 #66 model owners + #67 README remap + #68 mermaid)
**时间：** 2026-08-14 22:01:51–22:13:27 CST（wall 11m36s）
**run：** run-1786716112241
**模型：** MiniMax-M3，cache 0/81
**verify JSON：** `docs/eval/2026-08-14-fastapi-realworld-round10-verify.json`

第九轮评测见 `docs/eval/2026-08-14-fastapi-realworld-round9.md`。  
对照 wrap 见 `docs/eval/2026-08-13-fastapi-realworld-wrap.md`。

## Hits

- #68 HIT: API mermaid 6→0, ER 3→0
- #66 HIT on first generate: owner models 9→0 (items=30); API owner still 0
- #67 HIT: invalid README.md 1→0; wiki 0 literal README.md cites
- No regress: think 0, relpath 0, Tests.md gone, empty taxonomy gone, 19 `/api/*` including POST /api/users/login

## Circuit-break defect

0×529. Circuit-break TRIPPED because 3 consecutive **Insufficient prose** rejects were counted as provider failures. 34 LLM / 55 fallback (8 prose reject + 47 skip). Overview `项目概述.md` is fallback (Conduit MISS on that page; HIT on 项目介绍与背景.md). Coverage 49.93%→17.95% is the skip, not a gate change.

## Verify

exit 1 / FAIL. HARD 9 / SOFT 0 (r9 13). Gates not relaxed. Dropped this run: owner, citation invalid, API mermaid, ER mermaid.

Leftover HARD: manifest path, quality state, fact conflict, required inventory, coverage low, relevance, page dump 14, prose ×6, dirty worktree.

不要声称门槛放松。不要再为 mermaid / owner / readme 开重复 PR。
