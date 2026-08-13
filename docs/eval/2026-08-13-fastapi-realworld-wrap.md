# FastAPI RealWorld wiki 质量对照 wrap

**日期：** 2026-08-13 CST  
**对照：** nsidnev/fastapi-realworld-example-app `029eb778` × MiniMax-M3 × repo-wiki `9cadf85`（PR #40）

- generate 成功：89 页，0 次 529，0 fallback。
- 新主伤：60/89 空壳（HTTP 200 + 空 content，compact 1400）。
- PR #39：概述不再自称知识管理平台；污染换成 AGENTS.md。
- 04 没编造 /health，也没写出 /users/login、/articles 完整前缀。scanner 11 条相对 path 且 handler 错绑。
- verify 12 HARD / 0 SOFT。不要松阈值。generator-fix 另开 PR。
