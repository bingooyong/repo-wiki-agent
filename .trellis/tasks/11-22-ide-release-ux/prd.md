# READY 发布与 IDE 浏览闭环

## Goal

用户在 VS Code/Cursor 中始终知道 Wiki 是否可用、是否过期、下一步该做什么，并能从引用跳到源码。

## Requirements

- READY 缺失引导：区分 未生成 / 已生成未验证 / 已验证未发布 / release 非 READY / `navigation_tree` 为空，分别给出 `generate`、`verify --profile qoder-like --ci`、`release-publish` 的复制或一键入口。
- 页面状态徽标：fresh/stale、verify pass/warn/fail、citation coverage、LLM/rule/fallback 生成模式、最后生成时间与对应 commit。
- Release manifest 状态面板：readiness、wiki/target commit、工作区 drift、页面数、warning 数、LLM provider/model 摘要、最近 run。
- Citation 点击跳源码：解析引用元数据，`vscode.open` 跳转，Markdown Preview 提供 fallback，引用失效给 warning。
- 术语统一：README、`docs/00-overview.md` 等明确 run（过程产物）/ strict verify（候选判定）/ release（稳定发布面）/ plugin（只读 `.repo-agent-eval/repowiki/zh/manifest.json`）。
- 若知识卡导出落地，插件提供知识卡与长文两种浏览入口，默认仍读 READY release。

## Out of Scope

- 插件不内嵌 Python、不直接调用 LLM；真实 key 仍只走 SecretStorage。

## Acceptance Criteria

- [ ] 五种 READY 缺失状态在侧栏均有明确文案与下一步命令，人工冒烟记录归档。
- [ ] manifest 状态面板与页面徽标数据来自真实 manifest，不编造字段。
- [ ] 引用跳转到正确文件与行号；失效引用有提示。
- [ ] README 与文档术语一致；Cursor 兼容性冒烟通过。

## References

- 代码：`extensions/repo-wiki-browser/src/extension.ts`、`extensions/repo-wiki-browser/package.json`、`repo_wiki/orchestration/release_publisher.py`、`repo_wiki/viewer/static_viewer.py`
- 规范：`docs/plans/display-and-wiki-generation-optimization-roadmap.md` §2、`docs/specs/vscode-llm-configuration-spec.md`
