# 固化 ai-testing Qoder Wiki 对标基线与差距报告

## Goal

把 ai-testing 的 Qoder 产物固化为只读、可版本化、可机器比较的对标基线，让后续每个工作流都有量化差距可追。

## Requirements

- 盘点并登记基线数据：
  - 知识卡：`ai-testing/.qoder/repowiki/knowledge/zh/`，含 `_index.yaml`（15 个模块节点、commit `99e14d0`）、每模块 `_module.yaml`、模块卡与仓库横切卡。
  - 长文 Wiki：当前只有截图（70 页、生成中 61/70），本机未落盘；记录为缺口，尝试通过 Qoder 导出补齐，补齐前不得伪造页面清单。
- 在 `tests/fixtures/` 或 `ai/baselines/` 下建立 baseline registry 条目：来源路径、commit、导出时间、内容哈希、模块/卡片/页面统计；原仓库只读。
- 定义两类产物的机器可比指标：
  - 知识卡：模块覆盖率、卡片类型覆盖率（overview/architecture_design/tech_stack/coding_conventions/unique_setup_and_commands + 5 类仓库卡）、`depends_on`/`related_to` reason 覆盖率、卡片证据密度。
  - 长文：顶层 IA 覆盖率、页面类型覆盖率、prose 密度、Mermaid 覆盖、citation 覆盖。
- 输出差距报告到 `docs/eval/`，逐项列出 repo-wiki 当前产物与基线的差异及归属工作流。

## Out of Scope

- 不修改 ai-testing 仓库；不把基线内容硬编码进 planner/composer。
- 不在本任务内实现知识卡生成（属 `knowledge-card-contract`）。

## Acceptance Criteria

- [ ] baseline registry 落盘且带校验脚本，哈希可复现。
- [ ] 知识卡 schema 要点（`_index.yaml`、`_module.yaml` 字段与卡片命名）写成契约文档，供任务 4 直接引用。
- [ ] `docs/eval/` 新增差距报告，覆盖知识卡与长文两类形态，并标注长文基线未落盘的限制。
- [ ] `repo-wiki compare` 能消费该基线或明确记录暂不支持的维度。

## References

- 基线：`/Users/bingooyong/Code/01Code/github.com/bingooyong/ai-testing/.qoder/repowiki/knowledge/zh/_index.yaml`
- 现有对比能力：`repo_wiki/verifier/qoder_baseline_registry.py`、`repo_wiki/verifier/qoder_comparator_paths.py`、`repo_wiki/cli.py` 的 `compare` 命令
- 既有评估样例：`docs/eval/2026-08-13-fastapi-realworld-round*.md`
