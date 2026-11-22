# 设计：ai-testing 对标基线固化

## 事实修正（相对 PRD 初稿）

采集结果推翻了 PRD 的一个前提：ai-testing 长文 Wiki **已落盘且已完成**。

- `.qoder/repowiki/zh/content/`：70 个 markdown 页面，13 个顶层目录条目。
- `.qoder/repowiki/zh/meta/repowiki-metadata.json`：`wiki_repo.progress_status=completed`、`wiki_present_status=COMPLETED`、`last_commit_id=99e14d0…`、70 条 `wiki_catalogs`、70 条 `wiki_items`、57 条 `knowledge_relations`。
- 页面形态：`<cite>` 引用块 + `file://` 链接，69/70 页含 `#L` 行号锚点，70/70 页含 mermaid，页面字符数 min/median/max = 9675 / 17287 / 30988。

因此本任务同时固化**知识卡**与**长文**两个基线，不再把长文记为缺口。PRD 与 research 已同步修正。

## 边界

- 基线仓库只读：所有代码只 `read_text` / `read_bytes`，不写 ai-testing 任何路径。
- 基线内容不进入 planner/composer：registry 是 `ai/baselines/` 下的数据文件，只被 verifier 与脚本消费。
- 不实现知识卡生成（任务 4），不改 strict 门禁阈值。

## 组件

| 组件 | 职责 |
|------|------|
| `ai/baselines/registry.json` | 两条基线条目：来源、commit、exported_at、content_hash、file_count、stats、compare 支持度 |
| `repo_wiki/verifier/external_baseline_registry.py` | 加载 registry、解析基线根、采集统计、复算哈希并校验 |
| `scripts/verify_baseline_registry.py` | 校验入口；`--update` 重算哈希与统计，`--json` 输出机器结果，失败退出码 1 |
| `docs/specs/qoder-knowledge-card-baseline-contract.md` | 知识卡字段/命名/关系/指标契约，供任务 4 直接引用 |
| `docs/eval/2026-11-22-ai-testing-baseline-gap-report.{md,json}` | 双形态差距报告，逐项标注归属工作流 |
| `tests/test_external_baseline_registry.py` | 合成夹具测试；ai-testing 缺席时跳过真实基线用例 |

## 哈希契约

复用 `qoder_baseline_registry.compute_baseline_fingerprint`：对 `sorted(root.rglob('*') if file)` 依次 `update(relpath_posix)`、`update(b"\0")`、`update(bytes)`、`update(b"\0")`，取 sha256 hexdigest，同时返回 file_count。跨机器可复现，不依赖 mtime。

## 路径可移植性

registry 记录 `source_repo_root`（本机绝对路径，仅作 hint）与 `source_path`（仓库内相对路径）。校验脚本支持 `--baseline-root <id>=<path>` 覆盖，便于他人把 ai-testing 检出到别处。

## compare 支持度（诚实边界）

`cli.py:734` 的 `compare` 经 `register_single_qoder_baseline` 强制 `baseline == <target 所在仓库>/.qoder/repowiki/zh`（`qoder_baseline_registry.py:65-81`）。推论：

- 长文基线**形态兼容**，但只能在 ai-testing 仓内生成 target 后比较；本任务禁止向 ai-testing 写文件，故不执行跨仓 compare。
- 知识卡维度 compare **完全不支持**（无 `knowledge/` 解析、无卡片指标）。

两者都写入 registry 的 `compare_support` 与差距报告，不假装已支持。

## 指标定义（机器可算，后续任务复用）

知识卡：`module_count`、`card_type_counts`、`module_card_counts`、`repo_card_counts`、`markdown_file_count`、`relation_counts{depends_on,related_to,version_of}`、`relation_reason_coverage`、`evidence{file_ref_count,total_chars,refs_per_1k_chars}`。

长文：`page_count`、`catalog_count`、`root_catalog_count`、`knowledge_relation_count`、`mermaid_coverage`、`cite_block_coverage`、`line_anchor_coverage`、`page_chars{min,median,max,total}`、`progress_status`。