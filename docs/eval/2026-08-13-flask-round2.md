# Flask 对照 Wiki 第二轮评测

**对照仓：** pallets/flask `2a8a38b051fc248865730bf3511bf2e2ea325e81`  
**模型：** MiniMax-M3（openai-compat adapter，`https://api.minimaxi.com/v1`；`config --ci` 解析为 provider=`minimax`，apiKeyPresent=yes）  
**超时：** YAML 180s（未上调；`page_timeout_seconds=180.0`，失败原因是 HTTP 529 而非超时）  
**CLI：** repo-wiki 0.1.0 @ `98aa8bd38394ca252b4109b3b00b2003b5613cc9`（PR #37 merge commit）  
**时间：** 2026-08-13 21:13–21:24 CST  
**verify JSON：** `docs/eval/2026-08-13-flask-round2-verify.json`

## 生成结果

| 项 | 值 |
|---|---|
| generate | **success**（exit 0，写出 `manifest.json`） |
| 耗时 | 约 5m53s |
| 计划/写出页 | 84 / 84 markdown |
| LLM | real MiniMax-M3，非 MockLLM，非 abab6-chat |
| 并发 | 3 |
| fallback | 22 页（全部 `Server error: 529`，随后 `provider_disabled_after_failures=true`） |
| “LLM composer did not return content” | 42 页（含 22 个 529 fallback） |
| 核心页路径 | qoder-like 中文布局：`项目概述/项目概述.md`、`架构设计/整体架构概览.md`、`架构设计/模块关系.md`、`API参考/API参考.md`、`数据模型/数据模型.md` |
| 独立 `app.py` / `blueprints.py` 模块页 | **无**；用 `核心服务/Flask.md` 与 `Python服务/Python服务.md` 代替抽检 |

`init` 成功（wheel 内 `templates/` 存在）。`index` 成功：modules=4，endpoints=148，data_models=0。

## Verify

字面 `verify --output .repo-agent-eval` 会把 eval **根目录**当 release-candidate，落到最旧 run（与 round-1 同一套 11 HARD），**不能代表本轮 wiki**。本轮主结果指向新 run。

| | round-1（部分 run，eval 根） | round-2（完整 run） |
|---|---|---|
| exit | 1 | **1** |
| grade / status | FAIL / NOT_READY | FAIL / NOT_READY |
| HARD / SOFT | 11 / 0 | **12 / 0** |
| 页数 | 83（无 manifest） | 84（有 manifest） |
| 无效 citation | 458 | **31** |
| claim coverage | 0.00% | **15.06%**（105/697） |
| page dumps | 23 | 16 |
| 低散文密度 | 6 | 4 |
| API mermaid 缺失 | 10 | 10 |
| dirty-worktree | FAIL | FAIL（对照仓未提交 eval 产物，非产品 bug） |

HARD 条数略差于 round-1 的 11（+1），但 round-1 是崩溃后的部分 run。实质变好：generate 收尾成功、citation 458→31、coverage 0→15%。新 HARD：`QODER_QUALITY_ARTIFACT_MISSING`（quality JSON 在 `repowiki/zh/meta/`，verifier 按 release 布局找）、`QODER_API_AGGREGATION_LOW`（8/14）、`QODER_UNRESOLVED_FACT_CONFLICT`（406）。未放宽任何阈值。

## 人工 rubric（0–2：事实 / 证据 / 结构 / 边界）

| 页 | 事实 | 证据 | 结构 | 边界 | 注 |
|---|---|---|---|---|---|
| 项目概述（00） | 1 | 1 | 1 | 1 | README 正确说 WSGI 框架；**未**宣称订单/用户部署服务。但把 `init` 写入的 `docs/00-overview.md` 当成产品事实，说 flask 是「知识管理和文档生成平台」 |
| 整体架构概览（01） | 0 | 1 | 0 | 0 | 「LLM composer did not return content」空壳 |
| 模块关系（03） | 1 | 1 | 1 | 0 | Flask=WSGI 对；把 `tests/` `docs/` `examples/` 当业务模块 / `api-server` |
| API参考（04） | 2 | 1 | 1 | 2 | **未编造** `/health` `/webhook` `/items`；走框架空态 |
| 数据模型（05） | 0 | 1 | 0 | 0 | 总览页空壳；主叙事是 tutorial `flaskr` SQL，不是 Request/Response/Session/Config |
| Flask.md | 1 | 2 | 1 | 1 | 引用真实 `src/flask/cli.py` `testing.py` |
| Python服务.md | 0 | 1 | 1 | 0 | 把 examples 写成产品 API：`/` 与 `/result/<id>` |

Must-check：Overview 未说 Flask 是已部署订单服务（通过，但有「知识管理平台」污染）。04 未发明 `/health` `/webhook` `/items`（通过）。05 未捏造 User/Item ORM，也未把框架对象写成主模型。03 把 docs/tests 当业务模块（未通过）。

## Round-1 点名缺陷

| # | 缺陷 | 本轮 |
|---|---|---|
| 1 | init 缺少 packaged templates | **gone** |
| 2 | generate 在长 CHANGES.rst citation 上 `OSError: File name too long` | **gone** |
| 3 | LLM 单页 timeout 硬编码 20s | **gone**（`min(configured, 300)`；本 run 180s） |

## 原质量缺陷（残留）

1. 扫描器仍把 tests/examples 路由灌进页面计划；`Python服务.md` 把 examples 的 `/`、`/result/<id>` 写成 core-platform API。
2. `docs/` `tests/` `examples/` 被登记为 `api-server` / `api-gateway`。
3. 04 框架空态已生效。
4. `init` 往对照仓写入 stub（「知识管理与文档生成平台」「RESTful API 接口（12 个端点）」），generate 再引用，循环幻觉。
5. MiniMax 529：22 页 fallback，另有大量空壳页。

## 幻觉表

| Wiki quote | why false | source path |
|---|---|---|
| 「本仓库是一个基于 Python 与 Flask 的轻量级 Web 应用框架项目，同时承担知识管理与文档生成平台的角色。」 | Flask 是 WSGI 微框架，不是知识管理/文档生成平台。后半句来自 `repo-wiki init` stub。 | 项目概述；污染源 `docs/00-overview.md` |
| 「tests (core-platform) 模块：负责处理 API 路由 … 运行时角色为 `api-server`」 | `tests/` 是测试套件，不是业务 API 服务。 | 项目概述、模块关系 |
| 「examples (core-platform) … `/` 与 `/result/<id>` … api-server」 | `examples/` 是教程/示例，不是 Flask 产品 REST。 | Python服务.md |
| 「`docs` 是仓库中以 `api-gateway` 身份注册的核心服务之一」 | `docs/` 是 Sphinx 文档，不是 API 网关。 | 核心服务/Docs.md |
| 「核心数据模型以纯 SQL 形式表达」 | Flask 核心模型应是 Request/Response/Session/Config；tutorial `schema.sql` 不是框架数据模型。 | 数据模型 ← `examples/tutorial/flaskr/db.py` |

## HARD 是否比 round-1 更差？

条数上是（12 vs 11），质量上不是简单变差。citation 与 coverage 明显改善。不建议为此放宽阈值。

## 是否需要第三语料？

**值得，但本任务未启动。** 下一轮用很小的 FastAPI **应用**（自有路由/模型），不是 fastapi/fastapi。Flask 库已证明崩溃修复和「无产品 REST」空态；测不出真 HTTP API 合同页质量。
