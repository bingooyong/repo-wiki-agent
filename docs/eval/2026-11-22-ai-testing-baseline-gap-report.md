# ai-testing Qoder 基线差距报告（2026-11-22）

**任务：** `11-22-baseline-ai-testing-wiki`
**基线：** `ai-testing/.qoder/repowiki`（只读，commit `99e14d049fc3b7e0ea2e3d08e29dfd2eb4700b5a`，branch `main`）
**registry：** `ai/baselines/registry.json` · **校验：** `python scripts/verify_baseline_registry.py` → `REGISTRY PASS`
**机器结果：** `.repo-agent-eval/baseline-registry-verify.json` · **契约：** `docs/specs/qoder-knowledge-card-baseline-contract.md`

---

## 0. 两个前提修正

| 原判断 | 实测 | 影响 |
|--------|------|------|
| 长文 Wiki 只有截图、本机未落盘 | `.qoder/repowiki/zh/content/` 有 **70 页**，metadata `progress_status=completed`、`wiki_present_status=COMPLETED` | 长文基线可量化对标，不再是缺口 |
| `ai/source-of-truth/` 被 node_modules/测试夹具污染 | YAML **已净化**：41 个模型、0 条污染、`module-index.yaml` 职责为真实描述、`api-index.yaml` `endpoints: []` | 污染残留在**生成文档** `docs/0*.md`，任务 2 的重心是重生成与 composer 规则，不是重新净化扫描器 |

---

## 1. 基线实测

### 知识卡（`knowledge/zh`，88 文件，hash `10908d78…aa71e`）

| 指标 | 值 |
|------|-----|
| 模块节点 | 15（`_module.yaml` 15/15 匹配） |
| markdown 卡片 | 72 = 67 模块卡 + 5 仓库横切卡 |
| 模块卡覆盖 | overview / architecture_design / tech_stack / coding_conventions 各 15；unique_setup_and_commands **7**（条件卡） |
| 仓库卡 | build_system / configuration_system / dependency_management / error_handling / logging_system 各 1 |
| 关系 | depends_on **0**、related_to **6**、version_of **1** |
| reason 覆盖率 | **1.0**（7/7，reason 落到文件+调用） |
| 证据密度 | 175 处文件引用 / 44563 字符 = **3.927 refs/1k chars** |
| 缺失项 | `missing_module_yaml=[]`、`missing_card_files=[]` |

### 长文（`zh`，71 文件，hash `04889c47…0ff20`）

| 指标 | 值 |
|------|-----|
| 页面数 | 70 |
| 顶层 IA 条目 | 13（项目概述、快速开始、架构设计、智能体系统、执行引擎、质量门禁系统、产品包系统、交互式界面、数据模型和契约、Silver Needle 集成、扩展开发指南、测试策略、部署和运维） |
| catalog / item / relation | 70 / 70 / 57 |
| mermaid 覆盖 | **1.0**（70/70） |
| `<cite>` 块覆盖 | **1.0**（70/70） |
| `#L` 行号锚点覆盖 | **0.9857**（69/70） |
| 页面字符 min/median/max | 9675 / **17287** / 30988（合计 1252399） |

---

## 2. repo-wiki 当前产物

**没有 READY release**：`.repo-agent-eval/repowiki/zh/` 不存在，插件默认入口无内容可读。

现有最好的 run（过程产物，非产品）：`.repo-agent-eval/dogfood-fix-smoke`

| 指标 | 值 |
|------|-----|
| 页面数 | 8 |
| 顶层条目 | 2 |
| mermaid 覆盖 | 0.375（3/8） |
| `<cite>` 覆盖 | 1.0（8/8） |
| `#L` 行号锚点 | **0.0** |
| 页面字符 median | 2440 |

生成文档（`docs/`）残留问题，均有行号证据：

- `docs/01-architecture.md:171` 残留 `${incremental_governance}`；`:211` 技术栈写 `Javascript`，与 `pyproject.toml` 的 Python ≥3.11 不符。
- `docs/03-module-map.md:22,28,34,43,44` 职责退化为 `Handles API routes /path`、`Handles models instanceof, in`。
- `docs/05-data-model.md:14,54,274,275` 把 `extensions/repo-wiki-browser/node_modules/js-yaml/lib/schema.js` 的 `in`/`instanceof` 当核心实体；`:211,273` 把测试夹具 `dm_sales_facts` 当核心表。

---

## 3. 差距清单（逐项归属工作流）

| # | 维度 | 基线 | repo-wiki | 差距 | 归属任务 |
|---|------|------|-----------|------|----------|
| G1 | 知识卡形态 | 15 模块 / 72 卡 | **0**（无导出） | 形态完全缺失 | 4 knowledge-card-contract |
| G2 | 关系索引 | related_to 6 + version_of 1，reason 1.0 | 无 | 需可追溯 reason，禁止发明 depends_on | 4（依赖 3） |
| G3 | 卡片证据密度 | 3.927 refs/1k chars | 无卡片 | 导出需带文件级证据 | 3 + 4 |
| G4 | 条件卡 | unique_setup_and_commands 7/15 | 无 | 需按证据条件生成，不能全量补齐 | 4 |
| G5 | 页面规模 | 70 | 8（run） | 8/70 = 0.114，远低于 compare 的 0.80 门槛 | 5 ia-page-quality |
| G6 | 顶层 IA | 13 子系统条目 | 2 | 需子系统化 IA，而非扁平列表 | 5 |
| G7 | 正文体量 | median 17287 字符 | median 2440 | 0.141，prose 密度不足 | 5 |
| G8 | mermaid 覆盖 | 1.0 | 0.375 | 图计划未覆盖多数页 | 5 |
| G9 | 行号引用 | 0.9857 | **0.0** | cite 只有文件级，无行号 | 3 evidence-citation-gate |
| G10 | cite 块形式 | 1.0 | 1.0 | 形式已对齐，内容深度不足（见 G9） | 3 |
| G11 | READY release | COMPLETED | 不存在 | 插件无内容可浏览 | 6 ide-release-ux |
| G12 | 事实纯度 | 无伪实体 | 生成文档含 node_modules/夹具实体、占位符、错误技术栈 | 事实源已净化但文档未重生成 | 2 source-truth-purity |
| G13 | 模块职责表达 | 中文职责 + 英文类名 | `Handles API routes /path` | composer 模板退化 | 2 + 5 |
| G14 | 对标可执行性 | 双形态可量化 | compare 不支持（见 §4） | 需扩展或明确边界 | 4 + 8 |

---

## 4. `repo-wiki compare` 支持度（诚实边界）

代码证据：`repo_wiki/cli.py:734` 调用 `register_single_qoder_baseline`，后者在 `repo_wiki/verifier/qoder_baseline_registry.py:65-81` 强制 `baseline == <target 所在仓库>/.qoder/repowiki/zh`，否则抛错。

| 维度 | 支持 | 原因 |
|------|------|------|
| 长文形态 | **形态兼容，跨仓不可用** | 基线路径形态匹配 canonical，但 target 必须位于 ai-testing 仓内；本任务禁止向 ai-testing 写文件，故未执行跨仓 compare |
| 知识卡 | **不支持** | compare 无 `knowledge/` 解析、无卡片类型/关系/证据密度指标 |
| 页面数 / 目录深度 / prose / mermaid / citation | 支持 | 既有 `qoder_parity_metrics` 与 `_compare_readiness_failures` 已覆盖（阈值 0.80 / 0.70） |

结论：本任务**不扩展 compare**，把不支持维度写入 registry 的 `compare_support` 与本节。知识卡对比能力随任务 4 落地，跨仓对比策略在任务 8 决策。

---

## 5. 限制与风险

1. ai-testing 的 `.qoder/` 在该仓 **untracked**，基线是本地导出而非提交产物；`commit` 指导出时源仓 HEAD。冻结依据是本仓 registry 的 `content_hash`，不是 ai-testing 的 git 历史。
2. ai-testing 工作树存在与本任务无关的既有改动（`.trellis/…/task.json`、`test_os/workers/base_worker.py`）；本次全程只读，两次哈希复算一致，基线内容未被触碰。
3. 本仓无 READY release，§2 的 run 数据只代表过程产物质量，不能当作产品结论。
4. 长文基线的 `#L` 锚点覆盖 0.9857 而非 1.0，说明 Qoder 自身也允许少量页无行号；任务 3 的门禁阈值应据此校准，不盲目要求 100%。

---

## 6. 复现命令

```bash
python scripts/verify_baseline_registry.py --update   # 重算哈希与统计（只写本仓 registry）
python scripts/verify_baseline_registry.py --json .repo-agent-eval/baseline-registry-verify.json
.venv/bin/python -m pytest tests/test_external_baseline_registry.py -q
```

本机实测：`REGISTRY PASS`，两次运行哈希一致；新增测试 8 项通过，`-k "baseline or comparator or parity"` 回归 126 项通过。`ruff` 未安装于 `.venv`，本轮未执行 lint。