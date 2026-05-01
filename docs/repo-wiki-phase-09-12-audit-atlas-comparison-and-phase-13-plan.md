# Repo-Agent Phase 09-12 审计、Atlas 对比与 Phase 13 规划

文档属性：Manager 审计与下一阶段规划  
审计时间：2026-04-20  
审计范围：`Phase 09` - `Phase 12`（repo-agent 代码与 APM 资产）、`AI_API_Atlas` 目标仓库验收结果

## 1. 审计结论（先给结论）

`Phase 09-12` 在 repo-agent 代码层面已实现主要能力，且核心测试通过；但在 `AI_API_Atlas` 的落地验收仍未通过，当前**不能**宣称可替代 qoder repo-wiki。

关键结论：
- 实现成熟度：`中高`（合同层、验证层、运行时设计都已有代码和测试）
- 交付成熟度：`中低`（目标仓库文档质量与 section 结构不达标）
- 替代结论：`NO-GO`（暂不具备“可替代 qoder”发布条件）

## 2. Phase 09-12 审计结果

| Phase | 目标 | 代码证据 | 验收状态 | 主要风险 |
|---|---|---|---|---|
| Phase 09 | 输出 contract 与导航加固 | `repo_wiki/generator/contracts.py`（`TARGET_OUTPUT`/`GOVERNANCE_ONLY`、section alias）; `repo_wiki/verifier/service.py`（路径解析校验） | 部分达成 | 目标仓库仍存在 section 结构不兼容 |
| Phase 10 | narrative 与聚合质量提升 | `repo_wiki/generator/engine.py` 新聚合器与 narrative builder | 部分达成 | Atlas 产出仍偏列表，prose 不足 |
| Phase 11 | verify/compare 治理可信化 | `repo_wiki/verifier/service.py` hard/soft gate；`scripts/qoder_baseline_comparison.py` | 部分达成 | compare 目前仍以“规则基线”而非“外部 qoder 快照基线” |
| Phase 12 | SQLite-first 本地知识运行时 | `repo_wiki/orchestration/runtime_store.py`、`repo_wiki/orchestration/invalidation.py` | 未完成落地 | `runtime.sqlite3` 未在目标仓库生成，运行时未接入主流程 |

补充证据（本仓测试）：
- 执行 `pytest tests/test_verifier.py tests/test_baseline_comparator.py tests/test_phase12_sqlite_runtime.py tests/test_readiness_report.py tests/test_narrative_builder.py tests/test_section_narrative_builder.py tests/test_api_aggregator.py tests/test_data_model_aggregator.py -q`
- 结果：`133 passed`

## 3. Atlas 工程质量对比（生成结果 vs 目标能力）

### 3.1 `verify --ci`（针对 `AI_API_Atlas`）

通过 `AI_API_Atlas/.venv/bin/python` 加载 repo-agent verifier 实测：

| 指标 | 结果 |
|---|---|
| Grade | `FAIL` |
| Exit Code | `1` |
| 总检查数 | `12` |
| PASS/WARN/FAIL | `6 / 1 / 5` |
| Hard Gate | `STRUCT_MISSING_SECTIONS` |
| Soft Gate | `CONTENT_TOO_SHORT`, `ARCH_MERMAID_MISSING`, `AGG_API_NOT_GROUPED`, `AGG_DM_NOT_GROUPED` |

### 3.2 Baseline Compare（当前脚本口径）

执行：`python3 scripts/qoder_baseline_comparison.py --target AI_API_Atlas --baseline AI_API_Atlas --format json`

| 维度 | 结果 |
|---|---|
| Overall Score | `49.3%` |
| Overall Band | `POOR` |
| Structural Score | `66.7%` |
| Quality Score | `31.9%` |
| Passed / Failed / Partial | `2 / 2 / 2` |
| Acceptance Blocked | `true` |

说明：该次为 self-baseline（target=baseline），可用于“内部退化检测”，不能作为“与 qoder 外部基线等价”的最终证明。

### 3.3 Atlas 文档质量快照（核心 5 文档）

| 文档 | H2 数量 | Mermaid 数量 | Prose 字符 |
|---|---:|---:|---:|
| `docs/00-overview.md` | 3 | 0 | 133 |
| `docs/01-architecture.md` | 4 | 0 | 24 |
| `docs/03-module-map.md` | 0 | 0 | 0 |
| `docs/04-api-contracts.md` | 0 | 0 | 0 |
| `docs/05-data-model.md` | 0 | 0 | 0 |

section 结构：
- canonical slug section（`project/architecture/services/data-model/api/operations/development/security/troubleshooting`）均缺失
- 现存 `Q*/S*` 风格 section 文件：`23` 个

### 3.4 `.repo-wiki` 本地知识运行时对比

`AI_API_Atlas/.repo-wiki/index/state.sqlite3` 当前状态：
- 表数量：`15`
- `files=4534`, `chunks=17532`, `symbols=12998`, `file_hashes=4534`

但以下 Phase 12 关键表未在 Atlas 落盘：
- `doc_hierarchy`
- `section_registry`
- `nav_graph`
- `verify_run_details`
- `compare_run_details`
- `page_invalidation`

判定：Phase 12 代码已存在，但尚未完成在目标仓库的运行时接入与迁移执行。

## 4. 是否可替换 qoder repo-wiki

结论：**暂不可替换（NO-GO）**。

阻塞项是“文档中心体验与治理闭环”，不是扫描/索引底座：
1. Hard gate 未过（`STRUCT_MISSING_SECTIONS`）。
2. 核心文档仍偏清单导出，未达到 prose-first 聚合页要求。
3. Phase 12 SQLite 运行时尚未在目标仓库实际生效。
4. compare 缺少“外部 qoder snapshot 基线”对照。

## 5. 下一阶段建议：Phase 13（落地闭环阶段）

阶段名称建议：`Phase 13 – Atlas Cutover Readiness and Qoder Replacement Gate`

### Task 清单（8 项）

| Task | Owner | 目标 | 退出标准 |
|---|---|---|---|
| 13.1 | Agent_IndexGraph | 将 `runtime_store` 接入 `init/update/index/verify` 主流程，统一产出 `runtime.sqlite3` | Atlas 生成后存在 `runtime.sqlite3` 且含 6 张核心表 |
| 13.2 | Agent_DocGen | 建立 section alias 映射（`Q*/S* -> canonical slug`）并支持 overlay | `verify --ci` 的 `sections-exist` 在 Atlas 可 PASS |
| 13.3 | Agent_DocGen | 重写 5 个核心文档生成策略（prose-first + minimum narrative） | `00/01/03/04/05` 全部达到最小 prose/heading/mermaid 契约 |
| 13.4 | Agent_AdapterGovernance | 将导航校验扩展到全核心文档与 section 双向链路 | 断链/错链可被 hard gate 稳定拦截 |
| 13.5 | Agent_QualityRelease | 引入外部 qoder snapshot 作为 baseline fixture（非 self-baseline） | compare 报告可输出“与外部基线差距” |
| 13.6 | Agent_QualityRelease | 统一 readiness report（verify+compare+runtime evidence） | 单份报告给出 go/no-go 与阻塞证据 |
| 13.7 | Agent_QualityRelease | 在 `AI_API_Atlas` 执行完整回归（init/update/verify/compare） | `verify --ci` 达 `PASS/WARN`（无 hard fail） |
| 13.8 | Manager | 建立替代发布门禁（Replacement Gate） | 满足门禁后再对外声明“可替代 qoder” |

### Phase 13 Gate（建议）

必须同时满足：
1. `AI_API_Atlas` 上 `verify --ci` 无 hard gate fail。  
2. compare 对外部 qoder snapshot 达到约定阈值（建议 `>= 80%`）。  
3. `runtime.sqlite3` 关键表落盘并记录 verify/compare 趋势。  
4. 核心 5 文档全部通过 prose-first 结构化抽检。

## 6. Manager 决策建议

建议立即执行：
- 决策 A：采用 alias/overlay 兼容 `Q*/S*`，而不是强制 Atlas 先改目录命名。
- 决策 B：Phase 13 优先级按 `13.1 -> 13.2 -> 13.3 -> 13.7`，先清 hard gate 再提分。
- 决策 C：在替代声明前，强制执行“外部 qoder snapshot 对比”。

