# IA 与页面合同（任务：ia-page-quality）

## 目标形态

- 按子系统组织：子系统架构页 → 核心组件逐个详解 → 开发指南；不按物理目录平铺。
- 标题规范：`中文名 + 英文类名 + 职责`，如 `BaseAgent 基类与智能体生命周期`、`SourceEvidenceGate 来源证据检查`。
- 顶层语义保持通用：项目概述、快速开始、架构设计、服务与模块、API参考、数据模型、前端应用、运行与部署、开发指南、安全与合规、测试与质量、故障排除与维护。目录由知识模型生成，禁止照搬 ai-testing 标题。
- 阅读路径：5 分钟了解项目 / 30 分钟理解架构 / 如何新增 API / 如何配置 LLM / 如何生成并发布 Wiki。

## 页面合同

每页绑定页面类型、必备章节、证据需求、图需求、fallback。API 页遵守既有 10 章节合同，禁止 endpoint dump；数据模型页按实体角色与关系组织，禁止字段清单。

## 质量检查

- prose 密度 ≥30%；
- Mermaid 由 diagram plan 驱动，无证据不编图；
- 新增 HARD 检查：未解析占位符（`${...}` 等）、相对链接不可解析；
- 禁止 "Handles API routes /path" 类敷衍句式，无证据写"待确认"。

## 代码集成点（仅供实现者自行阅读，不注入）

`repo_wiki/planner/rule_first.py`、`service_subtopic_planner.py`、`api_topic_planner.py`、`data_model_topic_planner.py`、`repo_wiki/generator/composer.py`、`mermaid_planner.py`、`repo_wiki/prompts/skeleton.py`、`repo_wiki/verifier/quality_guardrails.py`。

## 验收

本仓与 ai-testing 各生成一次：IA/页面类型覆盖达标或有合并理由；strict 全绿且两项新 HARD 检查生效；总览与架构页可独立理解项目；长文对比报告归档 `docs/eval/`。
