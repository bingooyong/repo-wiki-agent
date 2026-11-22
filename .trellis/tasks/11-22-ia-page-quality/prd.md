# 信息架构与页面合同质量提升

## Goal

长文 Wiki 从"目录平铺 + 清单堆砌"升级为"按子系统组织、面向阅读路径、页面合同化"的文档中心。

## Requirements

- IA 对齐 Qoder 长文形态（截图基线）：按子系统分组，每个子系统含架构页、核心组件逐个详解、开发指南；页面标题采用"中文名 + 英文类名 + 职责"（如 `BaseAgent 基类与智能体生命周期`、`SourceEvidenceGate 来源证据检查`）。
- 保持通用顶层语义：项目概述/快速开始/架构设计/服务与模块/API参考/数据模型/前端应用/运行与部署/开发指南/安全与合规/测试与质量/故障排除与维护；目录由知识模型生成，不照搬 ai-testing 标题。
- 页面合同化：每页绑定页面类型、必备章节、证据需求、图需求与 fallback；API 页遵守既有 10 章节合同，禁止 endpoint dump。
- 生成质量：
  - prose 密度 ≥30%，列表只作辅助；
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

## References

- 基线：ai-testing 长文 Wiki 截图（项目概述/架构设计/智能体系统/执行引擎/质量门禁系统）
- 代码：`repo_wiki/planner/rule_first.py`、`repo_wiki/planner/service_subtopic_planner.py`、`repo_wiki/generator/composer.py`、`repo_wiki/generator/mermaid_planner.py`、`repo_wiki/prompts/skeleton.py`
- 规范：`docs/wiki-systematic-construction-master-plan.md` §4–§7、`docs/qoder-repo-wiki-design-analysis.md`
