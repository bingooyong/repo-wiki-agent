# 关键结论强制证据与引用门禁

## Goal

让每个关键结论都能回溯到文件/行号/符号；没有证据时宁可标"待确认"，也不允许编造。

## Requirements

- 页面计划声明 evidence requirements（`repo_wiki/planner/`），composer 只能使用 evidence bundle 内事实，prompt 明确"不得补全未证实接口"。
- API、配置项、命令、数据模型启用白名单：必须来自 scanner 或显式文档证据。
- Verifier 增强：
  - 引用文件路径与行号必须存在且落在声明的证据范围内；
  - 服务页 primary citation 必须来自该服务 `evidence_roots`，跨服务误绑判 FAIL；
  - 高幻觉风险页面不得进入 READY release。
- 低证据页面走 `待确认` 段落 + `low_confidence` 标记，禁止编造实现细节。
- 与知识卡工作流对齐：卡片正文中的事实性断言同样需要可追溯证据。

## Out of Scope

- 不做函数级全局调用图（spec 已列为非目标）。
- 不实现 IDE 端 citation 跳转 UI（属 `ide-release-ux`）。

## Acceptance Criteria

- [ ] 构造一个无证据/错证据的候选 run，strict verify 必须 NOT_READY 并给出明确 reason code。
- [ ] 本仓与 ai-testing 各跑一次生成，引用路径/行号校验 100% 通过；抽样人工复核记录归档。
- [ ] `qoder-citations`、`qoder-citation-relevance` 之外，新增的证据范围检查纳入 HARD 门禁并写入文档。
- [ ] 幻觉风险摘要进入 manifest `quality_summary`，发布器对高风险候选拒绝发布。

## References

- 代码：`repo_wiki/evidence/ranking.py`、`repo_wiki/evidence/citation_renderer.py`、`repo_wiki/evidence/service_ownership.py`、`repo_wiki/verifier/qoder_strict_verifier.py`、`repo_wiki/orchestration/release_publisher.py`
- 规范：`docs/plans/display-and-wiki-generation-optimization-roadmap.md` §3.2–3.3、`docs/wiki-systematic-construction-master-plan.md` §8
- 基线示范：ai-testing `_index.yaml` 中 `related_to.reason` 均引用具体文件与调用关系
