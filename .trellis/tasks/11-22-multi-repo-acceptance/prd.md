# 真实 LLM 多仓库验收与 GO 卷宗

## Goal

用真实 LLM 在多类仓库上证明 repo-wiki 是通用产品，而不是只对单一标杆仓有效，并形成最终 GO / NOT_READY 卷宗。

## Requirements

- 仓库矩阵至少覆盖：ai-testing（知识卡基线仓）、repo-agent 本仓 dogfood、复杂 monorepo、小后端、前端应用、Python 服务、docs-heavy 仓库。
- 每仓执行完整链路：`config --ci → init/index → generate → verify --profile qoder-like --ci → compare → release-publish`，记录耗时、LLM 调用量、成本、失败原因。
- 知识卡与长文双形态各自产出对比报告；ai-testing 与任务 1 基线逐指标对比。
- 成本基准：真实 provider 的成本/耗时曲线落盘，替换此前以 mock 为主的结论。
- 最终 dossier 明确区分：Qoder 兼容度、通用产品就绪度、已知限制与后续 backlog；NOT_READY 项必须给出可复现原因。

## Out of Scope

- 不为通过门禁而放宽 strict 规则；任何 profile 放宽必须单独评审。
- 不在文档或快照中写入真实 API Key。

## Acceptance Criteria

- [ ] 矩阵内每仓都有归档证据（manifest、strict 报告、compare 报告、成本记录）。
- [ ] 本仓 dogfood 全链路通过，关闭历史 `QODER_CONTENT_EMPTY` 等 dogfood 缺口。
- [ ] ai-testing 上知识卡与长文对比报告达成任务 4/5 指标，或列出明确差距。
- [ ] 最终 dossier 归档并更新 `docs/go-no-go-dossier.md` 的通用产品成熟度结论。

## References

- 依赖：任务 4、5、6、7 全部完成
- 既有卷宗：`docs/go-no-go-dossier.md`、`docs/operations/multi-repo-pilot-report.md`、`docs/operations/pilot-acceptance-playbook.md`
- 配置与安全：`docs/configuration.md`、`docs/operations/secret-sentinel-regression.md`
