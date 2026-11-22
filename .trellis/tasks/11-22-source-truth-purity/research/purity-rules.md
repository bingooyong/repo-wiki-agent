# 事实源净化规则（任务：source-truth-purity）

## 已证实污染（修复前证据）

- `docs/05-data-model.md`：`in`、`instanceof` 来自 `extensions/repo-wiki-browser/node_modules/js-yaml/lib/schema.js`，且被"API 参数类型"理由重复加分至榜首；`users`/`posts`/`dm_sales_facts` 来自 `tests/test_database_migrations.py`。
- `docs/03-module-map.md`：模块职责为 "Handles API routes /path"、"Handles models instanceof, in"；模块文档链接写成 `../docs/modules/...`（应为 `modules/...`）。
- `docs/01-architecture.md`：残留 `${incremental_governance}`；技术栈误写 Javascript/Express，实际为 Python + Typer CLI。

## 事实修正（2026-11-22 实测，任务 1 采集）

`ai/source-of-truth/` **当前已净化**：`data-models.yaml` 41 个模型、0 条 `node_modules`/`tests/` 污染，`module-index.yaml` 职责为真实描述（无 "Handles API routes"），`api-index.yaml` 为 `endpoints: []`。

因此本任务的重心不是"重新净化扫描器输出"，而是：

1. 上述污染仍活在**生成文档** `docs/0*.md` 里 → 必须走重生成链路修复，并加回归防止复发；
2. 扫描/评分规则仍需合同测试锁死，避免下一次 index 把污染带回来；
3. 验收以"重生成后的 docs"为准，不能只看 YAML 干净就宣布完成。

证据见 `docs/eval/2026-11-22-ai-testing-baseline-gap-report.md` §0、§2。

## 净化规则

1. 默认排除 `node_modules`、`.venv`、`dist`、`build`、`.mypy_cache`、`.ruff_cache` 及生成目录；排除规则必须有回归测试。
2. `tests/` 夹具、SQL 示例、解析器示例不得成为产品 API/数据模型/命令事实；保留时需标注 `test-harness` 并排除核心实体评分。
3. 核心评分对同一理由去重，禁止"API 参数类型"等标签无限叠加。
4. 事实冲突优先级：源码/包配置/CLI 行为/插件 manifest > README > `repo-wiki.yaml` > 历史 docs > 旧 source-of-truth；冲突打 `source-conflict`/`stale-doc`/`low-confidence`，正文写"以源码为准"。
5. 职责描述无证据时写"待确认"，禁止模板化敷衍句式。

## 代码集成点（仅供实现者自行阅读，不注入）

`repo_wiki/scanner/repository_scanner.py`、`docs_scanner.py`、`artifacts.py`、`database_migrations.py`、`repo_wiki/evidence/page_evidence_scorer.py`。

## 验收

```bash
repo-wiki index
grep -R "node_modules" ai/source-of-truth/        # 必须无命中
repo-wiki generate --profile qoder-like --output .repo-agent-eval
repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval
grep -R '\${' docs/01-architecture.md             # 必须无命中
```

另需新增合同测试：以本仓与 ai-testing 为夹具，伪事实用例必须判负；`docs/03-module-map.md` 相对链接可解析。
