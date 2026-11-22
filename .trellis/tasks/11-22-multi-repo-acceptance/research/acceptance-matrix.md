# 多仓库验收矩阵（任务：multi-repo-acceptance）

## 仓库矩阵

| 仓库 | 覆盖形态 | 重点 |
|------|----------|------|
| ai-testing | 知识卡基线仓 | 双形态与基线逐指标对比 |
| repo-agent 本仓 | dogfood | 关闭历史 QODER_CONTENT_EMPTY 缺口 |
| 复杂 monorepo | 多服务多语言 | 服务归属与 IA 分组 |
| 小后端 | 单服务 | 页面合并策略 |
| 前端应用 | 前端 | 路由/调用链证据 |
| Python 服务 | FastAPI/Flask | 既有 eval 延续 |
| docs-heavy | 文档为主 | docs 权威性与冲突降级 |

## 每仓链路

```bash
repo-wiki config --ci
repo-wiki init && repo-wiki index
repo-wiki generate --profile qoder-like --output .repo-agent-eval
repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval
repo-wiki compare --target <content> --baseline <baseline> --output <report> --ci
repo-wiki release-publish --output .repo-agent-eval
```

记录：耗时、LLM 调用量、估算/实际成本、失败 reason codes；归档 manifest、strict 报告、compare 报告、成本记录。

## 卷宗结构

Qoder 兼容度 / 通用产品就绪度 / 已知限制 / 后续 backlog；NOT_READY 项必须有可复现原因。禁止为通过而放宽 strict 规则；profile 放宽需单独评审。真实 API Key 不得进入任何证据文件。

## 验收

矩阵内每仓证据齐全；本仓 dogfood 全链路通过；ai-testing 双形态对比达成任务 4/5 指标或列出差距；更新 `docs/go-no-go-dossier.md` 的通用产品成熟度结论。
