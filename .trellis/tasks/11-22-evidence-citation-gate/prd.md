# 关键结论强制证据与引用门禁

## Goal

让每个关键结论都能回溯到文件/行号/符号；没有证据时宁可标"待确认"，也不允许编造。

## Requirements

- 页面计划声明 evidence requirements（`repo_wiki/planner/`），composer 只能使用 evidence bundle 内事实，prompt 明确"不得补全未证实接口"。
- API、配置项、命令、数据模型启用白名单：必须来自 scanner 或显式文档证据。
- Verifier 增强：
  - 引用文件路径与行号必须存在且落在声明的证据范围内；
  - **（2026-11-23 自对标新增）** 引用目标存在性 + 锚点行范围 HARD 校验：Qoder 本仓基线自身仍有 10 条 broken target 与 1 条越界锚点（`tests/test_codex_plugin_smoke.py#L65-L98`，文件仅 25 行），我们须严于基线；
  - **（2026-11-23 自对标新增）** 来源块标签统一为中文单一形式（`章节来源`/`图表来源`），拒绝 `Section sources`/`Diagram sources` 等漂移变体进入 READY；每个 mermaid 块必须有对应来源块（Qoder 479 图仅 427 来源块）；
  - 服务页 primary citation 必须来自该服务 `evidence_roots`，跨服务误绑判 FAIL；
  - 高幻觉风险页面不得进入 READY release。
- 低证据页面走 `待确认` 段落 + `low_confidence` 标记，禁止编造实现细节。
- 与知识卡工作流对齐：卡片正文中的事实性断言同样需要可追溯证据。
- **（2026-11-23 自对标新增）** 引用粒度对齐 Qoder：除页首 `<cite>` 文件清单外，每个章节与每张图必须带 `章节来源` / `图表来源` 块，引用格式 `file://<path>#L<start>-L<end>`。实测本仓 fallback run（`self-compare-20261123`）80/80 页有 `<cite>` 但 **0 页有 `#L` 行号**；Qoder 同仓 wiki 每节均有行号范围来源。
- **（2026-11-23 自对标新增）** manifest `page_registry` 必须携带每页引用元数据（cited_files、line_anchor_count、section_source_count），供门禁与插件徽标消费；当前每页只有 `absolutePath/path/slug/title/type`。
- **（2026-11-23 compare 首跑新增）** parity 引用指标粒度化：现有 `citation_coverage`/`file_line_reference_coverage` 只测 presence（实测我们纯文本 `<cite>path:line</cite>` 即得 1.0，而 `file://` 链接/`#L` 锚点/章节来源全 0，parity 仍 11/11 pass、0.97）。新增 HARD 粒度指标：link_form_coverage、line_anchor_coverage、section_source_coverage；presence 指标不得单独代表引用质量。
- **（2026-11-23 compare 首跑新增）** 引用归属排除过程目录：实测 `API参考.md` cite 指向 `.omx/tmp/openai-plugins/.../config_preflight.py:265-266`。白名单/`evidence_roots` 校验必须拒绝 `.omx/`、`.repo-agent-eval/`、`.repo-wiki/`、`tmp/` 等 scratch/过程路径作为产品页证据。

## Out of Scope

- 不做函数级全局调用图（spec 已列为非目标）。
- 不实现 IDE 端 citation 跳转 UI（属 `ide-release-ux`）。

## Acceptance Criteria

- [ ] 构造一个无证据/错证据的候选 run，strict verify 必须 NOT_READY 并给出明确 reason code。
- [ ] 本仓与 ai-testing 各跑一次生成，引用路径/行号校验 100% 通过；抽样人工复核记录归档。
- [ ] `qoder-citations`、`qoder-citation-relevance` 之外，新增的证据范围检查纳入 HARD 门禁并写入文档。
- [ ] 幻觉风险摘要进入 manifest `quality_summary`，发布器对高风险候选拒绝发布。
- [ ] 本仓真实 LLM run 的 `line_anchor_coverage` ≥ 0.9（Qoder 同仓基线为每节带行号来源；ai-testing 长文基线 0.9857），且 `章节来源`/`图表来源` 块覆盖所有含图页面。

## References

- 代码：`repo_wiki/evidence/ranking.py`、`repo_wiki/evidence/citation_renderer.py`、`repo_wiki/evidence/service_ownership.py`、`repo_wiki/verifier/qoder_strict_verifier.py`、`repo_wiki/orchestration/release_publisher.py`
- 规范：`docs/plans/display-and-wiki-generation-optimization-roadmap.md` §3.2–3.3、`docs/wiki-systematic-construction-master-plan.md` §8
- 基线示范：ai-testing `_index.yaml` 中 `related_to.reason` 均引用具体文件与调用关系
