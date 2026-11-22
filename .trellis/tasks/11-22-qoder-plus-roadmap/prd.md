# Qoder-plus 迭代总线：事实纯度、知识卡契约与发布闭环

## Context

`repo-wiki` 的目标是"仓库知识编译器"：先把代码仓库编译成结构化知识模型，再生成可信、可验证、可浏览、可持续更新的项目 Wiki。Qoder 是 baseline，不是天花板。

当前主要矛盾已从"能不能生成"转为"生成内容的事实纯度与信息架构质量"：

- `docs/05-data-model.md` 把 `extensions/repo-wiki-browser/node_modules/js-yaml` 的 `in`/`instanceof`、测试里的 `users`/`posts` SQL 当成核心实体。
- `docs/03-module-map.md` 模块职责退化为 "Handles API routes /path"、"Handles models instanceof, in"。
- `docs/01-architecture.md` 残留 `${incremental_governance}` 占位符，技术栈误写为 Javascript/Express。
- README 与文档中 run / release 术语仍混用。

本次新增的 ai-testing 参考数据揭示了 Qoder 的两种产物形态：

1. **知识卡**（已落盘）：`ai-testing/.qoder/repowiki/knowledge/zh/`
   - `_index.yaml`：15 个模块节点，含 `scope`、`children`、`depends_on`、`related_to`（带 `path` + `reason`，reason 引用具体文件与调用关系）、`version_of`；记录 `commit=99e14d0`、`branch`、`exported_at`。
   - 每模块 `_module.yaml`：`module_path`、`title`、`scope`、`kk_module_id`、`kk_cards`、`kk_repo_cards`。
   - 模块卡：`概述.md`(overview)、`架构设计.md`(architecture_design)、`技术栈.md`(tech_stack)、`编码规范.md`(coding_conventions)，root 另有 `特殊配置与命令.md`(unique_setup_and_commands)。
   - 仓库横切卡（`kk_repo_cards`）：`build_system`、`configuration_system`、`dependency_management`、`error_handling`、`logging_system`。
   - 卡片是精炼段落（概述卡一句话、架构卡一段讲清模块编排与契约），不是长列表。
2. **长文 Wiki**（**已落盘且已完成**：70 页、13 个顶层 IA 条目、`progress_status=completed`，commit `99e14d0`）：按子系统组织——项目概述/快速开始/架构设计/智能体系统/执行引擎/质量门禁系统/产品包系统/交互式界面/数据模型和契约/Silver Needle 集成/扩展开发指南/测试策略/部署和运维。页面标题采用"中文名 + 英文类名 + 职责"，每页带 `<cite>` 引用块，mermaid 覆盖 100%、`#L` 行号锚点覆盖 98.57%。早期"仅截图 61/70、尚未落盘"的判断已被任务 1 实测推翻。

repo-agent 当前**没有 READY release**（`.repo-agent-eval/repowiki/zh/` 不存在，最好的 run 只有 8 页），也**没有知识卡导出契约**，这是本轮迭代最重要的新方向。另需注意：`ai/source-of-truth/` 已净化，伪实体污染残留在生成文档 `docs/01/03/05`，任务 2 以重生成与防复发合同测试为主。基线实测与差距清单见 `docs/eval/2026-11-22-ai-testing-baseline-gap-report.md`。

## Goal

在保持现有 strict verify 与 READY release 门禁不回退的前提下，完成八条工作流，使 repo-wiki 在 ai-testing 与本仓 dogfood 上同时达到：

- 事实源无伪模块/伪实体，关键结论可追溯；
- 长文 Wiki 与知识卡双形态输出，且与 Qoder baseline 可机器对比；
- 插件只读 READY release，用户路径闭环；
- 真实 LLM 多仓库验收有成本与质量证据。

## Requirements

按依赖顺序执行（同层可并行）：

| # | 子任务 | 优先级 | 依赖 |
|---|--------|--------|------|
| 1 | `11-22-baseline-ai-testing-wiki` 固化对标基线与差距报告 | P0 | 无 |
| 2 | `11-22-source-truth-purity` 事实源净化与源码优先冲突策略 | P0 | 1 |
| 3 | `11-22-evidence-citation-gate` 关键结论强制证据与引用门禁 | P0 | 2 |
| 4 | `11-22-knowledge-card-contract` Qoder 知识卡输出契约 | P1 | 1、2、3 |
| 5 | `11-22-ia-page-quality` 信息架构与页面合同质量提升 | P1 | 2、3 |
| 6 | `11-22-ide-release-ux` READY 发布与 IDE 浏览闭环 | P1 | 5 |
| 7 | `11-22-incremental-llm-cache` 页面级增量与 LLM 缓存降本 | P2 | 5 |
| 8 | `11-22-multi-repo-acceptance` 真实 LLM 多仓库验收与 GO 卷宗 | P2 | 4、5、6、7 |

约束：

- LLM 只负责表达，不负责发现事实、决定目录或补足证据；无证据输出"待确认"。
- ai-testing baseline 只读，不硬编码进生成逻辑，不修改 ai-testing 仓库任何文件。
- 真实 API Key 只进 SecretStorage 或临时环境变量，禁止落盘到 YAML/settings/日志/manifest/测试快照。
- run 是过程，release 是产品；`.repo-agent-eval/repowiki/zh/manifest.json` 仍是插件唯一默认读取入口。

## Acceptance Criteria

- [ ] 八个子任务全部 archive，各自验收命令有记录。
- [ ] 本仓执行 `repo-wiki index` 后，`ai/source-of-truth/` 不再出现 `node_modules` 路径与未标注的测试夹具实体。
- [ ] 本仓 qoder-like 全链路 `generate → verify --profile qoder-like --ci → release-publish` 通过，`docs/01-architecture.md` 无 `${...}` 占位符、技术栈与 `pyproject.toml` 一致。
- [ ] 知识卡导出通过 schema 校验，并与 ai-testing baseline 输出对比报告（模块覆盖、卡片类型覆盖、关系 reason 覆盖）。
- [ ] 多仓库验收 dossier 归档，明确区分 Qoder 兼容、通用产品就绪度与已知限制。

## Notes

- 每个子任务按 trellis 工作流走 Plan → Implement → Check；复杂任务补 `design.md` / `implement.md`。
- 历史依据：`docs/wiki-systematic-construction-master-plan.md`、`docs/wiki-source-code-and-docs-intelligence-plan.md`、`docs/plans/display-and-wiki-generation-optimization-roadmap.md`、`docs/project-analysis.md`、`docs/go-no-go-dossier.md`。
- 基线路径：`/Users/bingooyong/Code/01Code/github.com/bingooyong/ai-testing/.qoder/repowiki`（只读）。
