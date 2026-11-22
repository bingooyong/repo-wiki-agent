# 基线契约与对比指标（任务：baseline-ai-testing-wiki）

## 基线来源（只读）

- 根：`/Users/bingooyong/Code/01Code/github.com/bingooyong/ai-testing/.qoder/repowiki/knowledge/zh/`
- commit `99e14d049fc3b7e0ea2e3d08e29dfd2eb4700b5a`，branch `main`，15 个模块节点。
- 长文 Wiki 仅有截图（70 页、生成中 61/70），本机未落盘；标记为基线缺口，禁止伪造页面清单。

## 字段契约

`_index.yaml`：`schema_version`、`locale`、`commit`、`branch`、`exported_at`、`modules.<id>`，模块字段为 `dir_name`、`title`、`scope[]`、`source_files[]`、`children[]`、`depends_on[]`、`related_to[{path,reason}]`、`version_of[{path,reason}]`。

`_module.yaml`：`schema_version`、`module_path`、`title`、`scope`、`source_files`、`depends_on`、`related_to`、`kk_module_id`、`kk_cards.<type>{id,title}`、`kk_repo_cards[]`。

卡片命名映射：overview→`概述.md`，architecture_design→`架构设计.md`，tech_stack→`技术栈.md`，coding_conventions→`编码规范.md`，unique_setup_and_commands→`特殊配置与命令.md`；仓库卡为 `build_system.md`、`configuration_system.md`、`dependency_management.md`、`error_handling.md`、`logging_system.md`。

## Registry 条目

`source_path`、`commit`、`exported_at`、`content_hash`（可复现算法需写明）、`stats{module_count, card_counts, relation_counts}`、`long_form_available: false`。

## 对比指标

- 知识卡：模块覆盖率、卡片类型覆盖率、关系 reason 覆盖率、卡片证据密度。
- 长文：顶层 IA 覆盖率、页面类型覆盖率、prose 密度、Mermaid 覆盖、citation 覆盖。

## 代码集成点（仅供实现者自行阅读，不注入）

- `repo_wiki/verifier/qoder_baseline_registry.py`：registry 扩展点。
- `repo_wiki/verifier/qoder_comparator_paths.py`、`reference_parity_runner.py`：对比执行。
- `repo_wiki/cli.py` 的 `compare`：报告产物路径。

## 验收

1. registry 与哈希校验脚本通过，重复运行哈希一致。
2. 契约文档与上述字段一致，可被任务 4 直接引用。
3. 差距报告写入 `docs/eval/`，覆盖双形态并注明长文基线缺失限制。
