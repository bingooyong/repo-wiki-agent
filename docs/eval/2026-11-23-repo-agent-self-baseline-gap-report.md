# repo-agent 自对标差距报告：repo-wiki vs QoderCN（2026-11-23）

**对标对象：** QoderCN 为本仓生成的 Repo Wiki（71 页，18 顶层条目）与知识卡（40 模块 / 173 卡）
**我们侧产物：** `.repo-agent-eval/self-compare-20261123`（qoder-like，80 页，**全 fallback**，见 §1）
**Qoder 长文快照：** `.repo-agent-eval/baselines/repo-agent-qoder-zh/`（gitignored；content sha256 `964f6bea…5bb`，71 文件）
**知识卡基线：** registry `repo-agent-knowledge-zh`（hash `61bb4c50…da3a`，214 文件）
**机器指标：** 同目录 `2026-11-23-repo-agent-self-baseline-gap-report.json`

---

## 1. 我们侧本轮不是真实 LLM 产物（必须先声明）

`generate --profile qoder-like` 时 composer 连续 3 次 `tokens=0 rejected=True` 后熔断，80 页全部规则兜底。根因已实测：

| 探针 | 结果 |
|------|------|
| `LLM_BASE_URL=https://api.minimaxi.com/anthropic` + `/chat/completions`（openai provider） | HTTP 404 |
| `https://api.minimaxi.com/v1` + `/chat/completions`，key=`sk-cp-…`（`ANTHROPIC_AUTH_TOKEN`） | HTTP 401 invalid api key |

即协议错配 + 凭据只服务于 Anthropic 协议网关。`config --ci` 仍报 OK。**更严重的是该全 fallback run 的 manifest 仍为 `READY`**，且 `page_registry` 无 `generation_mode`/引用元数据。归属新任务 `11-23-llm-preflight-fallback-gate`（P0）。

因此下表是"Qoder 真实产物 vs 我们规则兜底产物"的差距，**不是公平的质量终判**；真实 LLM 对比待凭据修复后在任务 8 复跑。

## 2. 同口径指标对比

口径统一：prose 密度**排除 fenced code 正文**（否则 mermaid 代码会被算成 prose）；来源块接受变体标签（`本节来源`/`分节来源`/`图示来源`/`Section sources`/`Diagram sources`）。

| 指标 | QoderCN（71 页） | repo-wiki fallback（80 页） | 差距归属 |
|------|------------------|------------------------------|----------|
| 顶层 IA 条目 | 18（11 section + 7 文档） | 15，含目录/同名文件并存与退化 slug | 5 |
| 页面行数 min/median/max | 399 / **615** / 1068 | 78 / **82** / 131 | 5 + 9 |
| 页面字符 median | **22984** | 2904 | 5 + 9 |
| mermaid 覆盖 | **1.0**（479 块） | 0.4125（33 页） | 5 |
| `<cite>` 块覆盖 | 1.0 | 1.0 | 持平 |
| `file://` 引用链接数 | **4931**（233 个不同文件） | **0** | 3 + 6 |
| `#L` 行号锚点覆盖 | **1.0** | **0.0** | 3 |
| 章节来源覆盖（变体归一） | **0.9155** | 0.0 | 3 |
| 图表来源覆盖（变体归一） | **1.0** | 0.0 | 3 |
| TOC 覆盖 | 1.0 | 1.0 | 持平 |
| prose 密度（排除代码，median） | **0.0875** | 0.4259 | 5（口径修正） |
| 知识卡 | 40 模块 / 173 卡，reason 覆盖 1.0 | **无导出** | 4 |

## 3. Qoder 基线自身的缺陷（我们不应照抄的部分）

1. **引用完整性不完美**：4931 条链接中 10 条目标不存在、1 条锚点越界（`/Codex 插件与 Skills` 引 `tests/test_codex_plugin_smoke.py#L65-L98`，该文件仅 25 行）。
2. **字符级损坏**：`/系统架构与设计总览` 出现 `file://repo_wiki/or orchestration/...`（注入空格）；`/主题规划与知识计划/知识工作计划生成` 出现 `kimestamp/io.py`；`主题规划总览` 标签写 `api_topic_planner.py` 而 href 写 `plancer`。
3. **来源标签漂移**：严格 `章节来源`/`图表来源` 仅 73%/63%，归一后 92%/100%；4 页仍用未翻译的 `Section sources`/`Diagram sources`。479 个 mermaid 块只有 427 个来源块。
4. **图重文轻**：排除代码后 prose median 仅 8.75%；`/编排系统与运行时存储/编排服务与工作流` 单页 14 张图。

结论：我们的门禁应**严于** Qoder——引用目标存在性 + 锚点范围校验进 HARD（任务 3），来源标签统一为中文单一形式（任务 3/5），prose 口径排除代码且产品目标高于基线（任务 5）。"Qoder-plus" 不是复制它的缺点。

## 4. 差距清单与归属

| # | 差距 | 归属任务 |
|---|------|----------|
| G1 | 知识卡导出缺失（0 vs 40 模块/173 卡） | 4 knowledge-card-contract |
| G2 | 行号锚点 0 vs 1.0 | 3 evidence-citation-gate |
| G3 | 章节/图表来源 0 vs 0.92/1.0 | 3 |
| G4 | `file://` 链接 0 vs 4931（IDE 跳转无数据） | 3 + 6 |
| G5 | mermaid 0.4125 vs 1.0 | 5 ia-page-quality |
| G6 | 页面体量 82 行 vs 615 行 | 5 + 9（真实 LLM） |
| G7 | IA 目录/同名文件并存、退化 slug | 5 |
| G8 | 全 fallback 仍 READY、无 generation_mode | 9 llm-preflight-fallback-gate |
| G9 | LLM 协议/凭据无预检（404/401 烧完整轮） | 9 |
| G10 | prose 口径含 mermaid 代码，目标需重定义 | 5 |
| G11 | 引用完整性/标签统一门禁（严于 Qoder） | 3 |
| G12 | 条件卡与开放横切类型集（`frontend_style`、37/40） | 4 |

## 5. 方法与限制

- Qoder 长文不在磁盘：`list_wiki` 枚举 71 页后 `read_wiki` 返回 `run_active`（增量 run `9200a38f`），改从插件 SQLite 的**已发布快照 `828bbdfa`** 只读导出；71 页行数与 `list_wiki` 逐一吻合，工作快照 `12dcc886` 字节一致。未伪造任何正文。
- 快照位于 gitignored eval 目录，**不登记为 canonical baseline**（compare 的 canonical 守卫拒绝 eval 路径）；冻结依据为本报告记录的 content sha256。
- 知识卡基线已登记 registry（`repo-agent-knowledge-zh`），可复算校验。
- 我们侧为 fallback 产物，§2 不构成真实 LLM 质量终判。
- 导出与度量脚本：`.repo-agent-eval/baselines/repo-agent-qoder-zh/export_and_measure.py`。

## 6. 复现

```bash
.venv/bin/python scripts/verify_baseline_registry.py
.venv/bin/python .repo-agent-eval/baselines/repo-agent-qoder-zh/export_and_measure.py   # 重新度量快照
```