# 事实源净化与源码优先冲突策略

## Goal

消除扫描与生成链路中的伪事实，保证 `ai/source-of-truth/` 与自生成 docs 只描述产品真实结构。

## 事实修正（2026-11-22）

任务 1 实测：`ai/source-of-truth/` 已净化（41 模型、0 污染、职责描述真实）。污染残留在生成文档 `docs/01/03/05`。本任务重心相应调整为**重生成 + 规则合同测试防复发**，而非重新净化事实源。详见 `research/purity-rules.md` 与 `docs/eval/2026-11-22-ai-testing-baseline-gap-report.md`。

## Requirements

- 扫描净化（`repo_wiki/scanner/`）：
  - 默认排除 `node_modules`、`.venv`、`dist`、`build`、各类缓存与生成目录；已有 deny 规则需补齐回归测试。
  - `tests/` 下夹具、SQL 示例、解析器示例不得作为产品 API/数据模型/命令事实；确需保留时显式标注 `test-harness` 角色并排除出核心实体评分。
  - 数据模型核心评分禁止被"API 参数类型"等理由无限叠加刷分（当前 `in`/`instanceof` 因此登顶）。
- 事实冲突策略（GEN-001）：来源优先级为 源码/包配置/CLI 实际行为/插件 manifest > README > `repo-wiki.yaml` > 历史 docs > 旧 source-of-truth；冲突项打 `source-conflict`/`stale-doc`/`low-confidence` 标签，composer 必须写"以源码为准"，不得传播旧结论。
- 模块职责生成禁止模板化敷衍（"Handles API routes /path"），无证据时写"待确认"。
- 用净化后的流水线重建本仓事实层与总览文档，修复：
  - `docs/01-architecture.md` 的 `${incremental_governance}` 占位符与 Javascript/Express 误判；
  - `docs/03-module-map.md` 的伪职责与 `../docs/modules/...` 错误相对链接；
  - `docs/05-data-model.md` 的 `in`/`instanceof`/测试 SQL 伪核心实体。

## Out of Scope

- 不重写全部历史 phase 文档，只保证新产物不再引用旧结论。
- 不实现 citation 门禁本体（属 `evidence-citation-gate`）。

## Acceptance Criteria

- [x] `repo-wiki index` 后，`ai/source-of-truth/` 全文检索不到 `node_modules`，核心实体列表无未标注的测试夹具条目（41 个产品模型，`tests` 在诊断中标为 test-harness）。
- [x] 新增扫描/评分合同测试：`tests/test_source_truth_purity.py` 27 项通过，伪事实用例（`in`/`instanceof`/`dm_sales_facts`）判负。
- [x] 重生成后 `docs/01-architecture.md` 无 `${...}` 残留，语言/框架为 Python / typer-cli，与 `pyproject.toml` 一致。
- [x] `repo-wiki verify --ci`（默认 profile）零 hard 失败（WARN，`acceptance_blocked=false`），新增 `unresolved-placeholders` HARD 检查对注入的 `${...}` 判 FAIL。
- [ ] **移交任务 6**：qoder-like 全链路 `generate → verify --profile qoder-like --ci → release-publish` 通过。

### 验收移交说明（2026-11-23）

原第 4 条要求 qoder-like strict verify 通过，但本仓不存在 READY release（`QODER_META_ROOT_MISSING`）。检查代理在 base commit `665408a` 上复现了同样的 NOT_READY 与相同 reason codes，证明该失败非本任务引入，而是任务 6 的交付缺口（差距报告 G11）。因此本任务以"默认 verify 零 hard 失败 + 新占位符门禁生效"收口，qoder-like 全链路验收由任务 6 承担。未放宽任何既有 strict 阈值。

## References

- 证据：`docs/05-data-model.md`、`docs/03-module-map.md`、`docs/01-architecture.md`
- 代码：`repo_wiki/scanner/repository_scanner.py`、`repo_wiki/scanner/docs_scanner.py`、`repo_wiki/scanner/artifacts.py`、`repo_wiki/evidence/page_evidence_scorer.py`
- 规范：`docs/plans/display-and-wiki-generation-optimization-roadmap.md` §3.1、`docs/project-analysis.md` §8.1
