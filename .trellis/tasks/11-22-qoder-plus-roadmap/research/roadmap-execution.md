# 路线图执行约束（任务：qoder-plus-roadmap）

## 执行顺序

1 → 2 → 3 →（4 与 5 可并行）→（6、7 可并行）→ 8。
子任务编号对应父任务 PRD 的 Requirements 表；跨任务产出物引用关系：

- 1 产出基线契约，被 4 直接引用；
- 2 产出净化事实源，被 3/4/5 共用；
- 3 产出证据门禁，被 4/5/8 共用；
- 7 的增量与成本报告被 8 引用。

## 跨任务硬约束

- LLM 只表达，不发现事实、不决定目录、不补足证据；无证据写"待确认"。
- ai-testing 基线只读，不硬编码进生成逻辑，不修改该仓库。
- 真实 API Key 只进 SecretStorage 或临时环境变量，禁止落盘。
- run 是过程，release 是产品；插件唯一默认入口 `.repo-agent-eval/repowiki/zh/manifest.json`。
- 不得为通过验收而放宽 strict 门禁；profile 变更需单独评审。

## 完成定义

八个子任务全部 archive 且验收命令有记录；本仓与 ai-testing 双链路通过；知识卡 schema 校验与对比报告落盘；多仓库 dossier 归档并更新通用产品成熟度结论。
