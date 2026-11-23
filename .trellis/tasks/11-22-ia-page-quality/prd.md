# 信息架构与页面合同质量提升

## Goal

长文 Wiki 从"目录平铺 + 清单堆砌"升级为"按子系统组织、面向阅读路径、页面合同化"的文档中心。

## Requirements

- IA 对齐 Qoder 长文形态（ai-testing 落盘基线 + 本仓 Qoder 71 页基线，registry id `ai-testing-longform-zh` / 导出快照 `repo-agent-qoder-zh`）：按子系统分组，每个子系统含架构页、核心组件逐个详解、开发指南；页面标题采用"中文名 + 英文类名 + 职责"（如 `BaseAgent 基类与智能体生命周期`、`SourceEvidenceGate 来源证据检查`）。本仓 Qoder 基线顶层 18 条目（11 个子系统 section + 7 篇独立文档），可作通用 IA 的参照而非照搬。
- **（2026-11-23 自对标新增）IA 命名唯一性**：同一顶层语义不得同时存在目录与同名 `.md`（实测 fallback run 出现 `安全合规/` + `安全合规.md`、`部署运维/` + `部署运维.md`、`故障排除/` + `故障排除.md` + `故障排除-troubleshooting-maintena-2.md`）；slug 不得截断退化或追加 `-2` 消歧后缀。新增 HARD 检查。
- **（2026-11-23 自对标新增）页面体量**：真实 LLM run 的页面行数 median 目标 ≥300 行（本仓 Qoder 基线 median ≈672 行、min 452 行；当前 fallback run median 82 行）。体量必须由证据与章节合同驱动，禁止灌水凑行数。
- 保持通用顶层语义：项目概述/快速开始/架构设计/服务与模块/API参考/数据模型/前端应用/运行与部署/开发指南/安全与合规/测试与质量/故障排除与维护；目录由知识模型生成，不照搬 ai-testing 标题。
- 页面合同化：每页绑定页面类型、必备章节、证据需求、图需求与 fallback；API 页遵守既有 10 章节合同，禁止 endpoint dump。
- 生成质量：
  - prose 密度口径**排除 fenced code 正文**（2026-11-23 实测：Qoder 本仓基线 naive prose 36.6% 中约六成是 mermaid 代码，排除后 median 仅 8.75%）；产品目标 prose_excl_code ≥0.20，高于基线但不灌水；列表只作辅助；
  - Mermaid 由 diagram plan 驱动，无证据不编图；
  - 模板变量必须渲染完成，`${...}` 等未解析占位符新增 HARD 检查；
  - 文档内相对链接可解析（修复 `../docs/modules/...` 这类错误）。
- 阅读路径：提供"5 分钟了解项目 / 30 分钟理解架构 / 如何新增一个 API / 如何配置 LLM / 如何生成并发布 Wiki"入口。

## Out of Scope

- 不做专用 Webview Wiki Viewer 重构（仅必要修复）。
- 不实现知识卡（属任务 4）与增量机制（属任务 7）。

## Acceptance Criteria

- [ ] 本仓与 ai-testing 各生成一次，顶层 IA 与页面类型覆盖达到基线指标，缺页有合并理由。
- [ ] strict verify 全绿，且新增"未解析占位符"与"相对链接可解析"检查生效。
- [ ] 总览/架构页可独立让新读者理解项目，抽查无 "Handles API routes /path" 类敷衍句式。
- [ ] 与基线的长文对比报告归档 `docs/eval/`。
- [ ] 顶层 IA 无目录/同名文件并存、无退化 slug；真实 LLM run 页面行数 median ≥300 且 prose 密度 ≥30%（fallback run 实测 prose 0.426 但行数 median 82，说明密度达标不等于体量达标）。

## References

- 基线：ai-testing 长文 Wiki 截图（项目概述/架构设计/智能体系统/执行引擎/质量门禁系统）
- 代码：`repo_wiki/planner/rule_first.py`、`repo_wiki/planner/service_subtopic_planner.py`、`repo_wiki/generator/composer.py`、`repo_wiki/generator/mermaid_planner.py`、`repo_wiki/prompts/skeleton.py`
- 规范：`docs/wiki-systematic-construction-master-plan.md` §4–§7、`docs/qoder-repo-wiki-design-analysis.md`
