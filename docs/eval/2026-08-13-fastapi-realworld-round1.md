# FastAPI RealWorld 对照 Wiki 第一轮评测

**对照仓：** nsidnev/fastapi-realworld-example-app `029eb7781c60d5f563ee8990a0cbfb79b244538c`  
**模型：** MiniMax-M3（openai-compat `https://api.minimaxi.com/v1`）  
**超时：** YAML 180s；无 HTTP 529/429  
**并发：** 2  
**CLI：** repo-wiki @ `9cadf853858cbd4cbf19b0eb568b92c7562ebafc`（PR #40）  
**时间：** 2026-08-13 22:07–22:18 CST（compose 675s）  
**verify JSON：** `docs/eval/2026-08-13-fastapi-realworld-round1-verify.json`

## 生成结果

| 项 | 值 |
|---|---|
| generate | success，89/89 页 |
| 529 / 429 | 0 / 0（#40 retry 未触发） |
| fallback | 0；provider 未熔断 |
| “LLM composer did not return content” | **60 / 89**（HTTP 200 + 空 content，仍记 PASS） |
| index | modules=9，endpoints=11，data_models=29 |

空壳机制：compact prompt 把 `max_tokens` cap 在 1400；MiniMax-M3 推理输出常把 `message.content` 留空；`chat_with_retry` 不把空内容当 retryable。

## Verify

run-scoped：`verify --profile qoder-like --ci --output run-1786630053017`

| | FastAPI r1 | Flask r2 |
|---|---|---|
| HARD / SOFT | 12 / 0 | 12 / 0 |
| claim coverage | 43.50% | 15.06% |
| 无效 citation | 22 | 31 |
| API aggregation | PASS 9/13 | FAIL 8/14 |

HARD：`QODER_MANIFEST_PATH_INVALID`（`run-*` vs `runs/<run>`）、duplicate quality entries、74 fact conflicts、缺 apis/models/runtimes 库存、citation/coverage/owner、API/ER mermaid、page dump、dirty-worktree。未放宽阈值。

## Rubric（事实/证据/结构/边界）

| 页 | 事实 | 证据 | 结构 | 边界 | 注 |
|---|---|---|---|---|---|
| 项目概述 | 0 | 1 | 1 | 0 | 未称知识管理平台（#39）。未识别 Conduit。叙事是 api-gateway 平台 |
| 整体架构 | 0 | 1 | 0 | 0 | 空壳 |
| 模块关系 | 1 | 2 | 1 | 0 | ArticlesRepository 对；mermaid 含 docs/tests |
| API参考 | 1 | 1 | 0 | 2 | 未编造 /health；UNRESOLVED；缺 /users /articles 前缀 |
| 数据模型 | 1 | 1 | 0 | 1 | 总览空壳；子页有 User/Article/Comment/Tag |

## 幻觉（摘要）

- 把仓库说成 api-gateway 平台，而不是 Conduit users/articles
- 把 init 的 AGENTS.md / repo-wiki 命令当产品
- 04 UNRESOLVED，尽管已有 11 条扫描端点
- handler 错绑：list_articles → DELETE /{slug}
- POST /login 缺 /users 前缀；GET /feed 缺 /articles

## 建议修（本 PR 不改代码）

1. 空 content 当 retryable；抬高 reasoning 模型 max_tokens
2. FastAPI include_router prefix + 按装饰器绑 handler
3. 有产品 endpoints 时禁止 04 UNRESOLVED
4. 降权 AGENTS.md / init stub
