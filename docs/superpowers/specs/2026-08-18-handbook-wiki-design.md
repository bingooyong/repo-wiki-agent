# FastAPI RealWorld 样板手册 Wiki

**日期：** 2026-08-18  
**状态：** 待评审  
**范围：** 单库 `repo-wiki` 生成器。对照仓 nsidnev/fastapi-realworld-example-app 先做成样板手册；过关后再用同一套生成器给接手的项目出文档。  
**不在范围：** RAG、多仓知识、放宽现有 HARD/SOFT、把 95% 引用覆盖门改低、未评审就合现有产品 PR。

## 1. 问题

对照仓已经能生成完整中文 Wiki（约 81 页）。API / 路由 / 模型页大体能当说明书：有分层、有文件行号、不再编造不存在的 `DELETE /api/articles`。

新人真正先打开的页是反的。项目概述、安装、安全在模型写不够或服务 529 时，会落到 `_fallback_markdown_for_failed_page`：满篇「该页面对应 `page_id`，由 fallback composer 生成」，把 README Quickstart 证据埋在生成器自述里。这不是手册。

现有自动检查能拦住套话页（DEGRADED）、假路由、引用对不上，但：

- 过关不等于「按安装页能跑」或「改登录去哪个文件」
- 评测把 Wiki 写进对照仓目录时，目标仓会被判 dirty，和源码是否脏无关
- 引用覆盖大约七成，门仍是 95%

## 2. 目标与过关

**读者：** 接手一个仓库的人，靠 Wiki 知道这是什么、怎么跑、改一个功能去哪个文件。

**样板仓：** FastAPI RealWorld（Conduit 后端）。生成器在这本仓上过关后，再生成接手项目的文档。本 spec 的验收只绑样板仓。接手项目的生成是过关后的下一步，不写进本 spec 的实现任务。

**过关（唯一）：** `repo-wiki verify --profile qoder-like` 对样板仓 **自动检查全绿**。人读发现的问题记后续，不挡过关。

全绿包含：

1. **现有 HARD 全部通过，不放宽。** 包括但不限于：无 DEGRADED/fallback 页、无假路由/假事实、引用覆盖 ≥ 95%、引用相关、无 dump 页、owner 完整。`QODER_DIRTY_WORKTREE` 见第 6 节，不靠关掉这道门过关。
2. **新增手册 HARD**（第 5 节）。全绿必须同时满足这些，这样「全绿」才等于样板手册，而不是生成器自检自夸。

SOFT 保持现状。不为通过率改门槛。

## 3. 方案选择

曾考虑三条：

| | 做法 | 为何不采用 / 采用 |
|---|---|---|
| A | 只改 fallback 文案 | 页能读一些，但 DEGRADED 仍红，全绿过不了 |
| B | 只改概述/安装 prompt | 可能少几次 fallback，不管引用 95%，也不验「能指到文件」 |
| **C（采用）** | 生成（prompt + 证据 + 兜底）和验收（现有门 + 手册门）一起改 | 过关线和手册目标一致 |

采用 C。工期不作为裁剪依据。

## 4. 架构

仍走现有流水线：`scan → plan → evidence → compose → write → verify`。不新起生成器。

改三处，接口保持现有 CLI：

```
evidence (README / routes / models)
        ↓
compose  ← 入门页合同：身份、怎么跑、去哪个文件；禁止生成器套话
        ↓  失败
fallback ← 用证据写成可读入门页，仍记 DEGRADED，不能当 PASS
        ↓
verify   ← 现有 HARD + 手册 HARD；isolated --output 目录不计入 dirty
```

### 4.1 Compose（让模型写出手册页）

对 `PROJECT_OVERVIEW`、安装/Quickstart（`installation` / development-guide 里承担「怎么跑」的页）、`SECURITY_COMPLIANCE` 的入门页：

- 合同要求：用 README/pyproject 的产品身份；安装页必须写出可执行步骤（以证据里的 Quickstart / Docker / `DATABASE_URL` 为准）；禁止出现生成器元话语。
- 模型输出若含第 5.1 节禁用短语，视为 compose 失败（与 insufficient prose 同类），走 fallback，**质量状态仍是 DEGRADED**。
- API 页合同：至少把证据里的 `app/api/routes`（或库存里的等价路由文件）写成 `<cite>`，让「改登录/文章」能落到文件。

不在本 spec 发明新 taxonomy。用现有 page_id / category。

### 4.2 Fallback（模型失败时人还能读）

重写 `_fallback_markdown_for_failed_page`：

- 禁止：`page_id`、`repo-agent`、`fallback composer`、`evidence ranking`、`该页面对应`、插件验收、增量生成等元话语。
- 必须：用 `_summarize_evidence_for_fallback` 里的路径、符号、片段当正文。概述/安装优先摊开 README Quickstart / Docker / 测试；安全页只写证据里真正出现的鉴权（例如 `RWAPIKeyHeader`），不编合规体系。
- 有片段就引用 `<cite>path:start-end</cite>`，不发明证据里没有的路径。
- 没有证据时直说本页无法从仓库填满，仍然禁止元话语。

Fallback **不是**过关手段。有 fallback 页，现有 `QODER_PAGE_QUALITY_STATE_DEGRADED` 仍 FAIL。兜底只保证「生成失败时打开 Wiki 不是生成器说明书」。

### 4.3 Evidence

概述/安装页今天常只绑到 README 的一小段，模型写不够就 fallback。需要让这些页的 evidence ranking 稳定带上：

- README.rst 的定位、Quickstart、Docker、测试
- 入口（如 `app/main.py`）和设置（`database_url` / `DATABASE_URL`）
- 安全入门页带上 `app/api/dependencies/authentication.py` 这类真实鉴权文件，而不是只用 README Quickstart 冒充安全

不改扫描器去「发现更多服务」。只修这些入门页的绑定优先级。

## 5. 新增手册 HARD

新 reason code，全部进 `STRICT_HARD_CODES`。不删除、不降级现有 HARD。95% 引用门不动。

### 5.1 `QODER_HANDBOOK_GENERATOR_META`

任一 Markdown 页出现生成器元话语则 FAIL。禁用短语至少包括：

- `fallback composer`
- `repo-agent`
- `该页面对应`
- `evidence ranking`
- `page_id` 作为给读者看的说明（代码块里的标识符除外：实现时按整词/整句匹配上述中文套话，避免误伤普通英文）

这条保证 fallback 改文案之后，模型也不能把同一套话写进 PASS 页。

### 5.2 `QODER_HANDBOOK_OVERVIEW_IDENTITY`

项目概述页（`project-overview` 及对照仓实际写出的概述主页）必须出现对照仓 README 里的产品身份。样板仓验收词：`Conduit` 或 `RealWorld`，以及 `FastAPI`。缺一则 FAIL。

不把这段写成通用 NLP。样板仓用固定身份词；实现放在 qoder-like 对照配置或页面合同里，避免每个仓写死 Conduit。对非样板仓：用库存/README 解析出的 `identity` 字符串，缺身份则 FAIL。

### 5.3 `QODER_HANDBOOK_INSTALL_RUN`

安装页（`installation` 及对照仓「安装与配置」类页）必须同时：

- 出现可运行线索：`docker` / `docker-compose` / `DATABASE_URL` / `POSTGRES` 中至少两项（大小写不敏感），且能在引用或正文中对上 README 证据
- 至少一条仓库内引用指向 `README.rst`（或该仓实际 README 路径）

禁止只写「阅读入口文件再追踪模型层」这类空步骤。

### 5.4 `QODER_HANDBOOK_API_ROUTE_FILE`

核心 API 页（样板仓：`API参考/核心服务API` 下承担路由说明的页，以及 `core-service-apis` / `api` 合同页）必须至少有一条 `<cite>` 指向 `app/api/routes/` 下文件（或库存里记录的等价路由模块）。只有 `app/db`、`app/models`、`tests/` 不够。这是「改登录/文章去哪个文件」的自动近似。

## 6. Dirty worktree

现状：`--output .repo-agent-eval` 写在对照仓内，verify 把目标仓未提交变更判 HARD。

**改法：** `QODER_DIRTY_WORKTREE` 忽略 **本次 verify 的 isolated output 目录**（以及其 `runs/`）。目标仓其它未提交源码变更仍 HARD。

不在对照仓乱加 gitignore 当过关手段。不关闭 dirty 门。

## 7. 引用覆盖 95%

门不变。样板仓要从约 69% 做到 ≥ 95%，靠：

- 入门页证据补全（第 4.3 节），让概述/安装的论断旁边有可引用片段
- compose 对有 file+line 的论断继续同行输出 `<cite>`（已有 API 分组先例，扩到概述/安装步骤）
- 不可验证论断仍不算覆盖。禁止用放宽窗口或把非论断算进去刷高百分比

若某页没有证据，应少写论断，而不是写空话再报未覆盖。

## 8. 验收步骤（样板仓）

1. 单元测试：fallback 无元话语、有 README 片段；四条手册 HARD 的正/反例；dirty 忽略 output 目录、源码脏仍 FAIL；95% 门仍在 `STRICT_HARD_CODES`。
2. 冷缓存、真实模型、对照仓 SHA 固定，`generate --profile qoder-like` 再 `verify`。
3. 过关：verify 退出码 0，HARD 0，SOFT 不新增。手册四条为 PASS。无 DEGRADED 页。引用 ≥ 95%。
4. 本 spec 不要求合入未评审的历史产品 PR；实现从当时 `main` 拉出，需要的历史修复按评审后的 main 为准。若评测必须叠未合 PR，在实现 plan 里单列「叠哪些 SHA」，不在本 spec 里默许合入。

## 9. 测试要点

- `tests/` 覆盖 4.2、5.1–5.4、第 6 节。不依赖对照仓 checkout 也能跑（用 tmp_path 写假 Wiki + 假 README 身份）。
- 样板仓实跑是验收，不是单测。
- 现有 billing 引用 auth、假 `POST /ghost`、trailing `{slug}` 等用例保持 FAIL。

## 10. 明确不做

- 放宽 95%、把 DEGRADED 当 WARN、把 fallback 当 PASS
- 为通过手册检查去改对照仓业务代码
- 本 spec 内生成接手项目 Wiki（样板全绿之后另开）
- 企业 RAG、多仓、知识卡片、MCP

## 11. 实现顺序（给后续 plan）

1. Fallback 文案（人能读，仍 DEGRADED）
2. Compose 拒绝元话语
3. 入门页证据绑定 + 页面合同（身份、怎么跑、路由文件 cite）
4. 手册四条 HARD
5. Dirty 忽略 isolated output
6. 引用覆盖：入门页同行 cite，门仍 95%
7. 样板仓冷跑 generate + verify 直到第 8 节过关
