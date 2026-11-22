# 页面级增量更新与 LLM 缓存降本

## Goal

变更只重建受影响页面，未变化页面零 LLM 调用，人工编辑不被覆盖。

## Requirements

- 页面级增量：git diff → 变更文件 → module/evidence/page index → 受影响页面与聚合页；只重建这些页面，manifest 记录本次增量范围。
- 人工编辑区保留：支持 `<!-- repo-wiki:manual:start/end -->`，重生成保留该区域，verifier 检查 marker 配对。
- LLM 缓存：key 至少包含 prompt hash、evidence hash、model、provider、temperature/max_tokens、composer version；命中缓存不计入 LLM 调用。
- 与知识卡对齐：卡片同样参与失效与缓存，避免双形态重复成本。
- 成本观测：`cost-estimate` 与 `improve-status` 能展示增量前后调用量与估算成本。

## Out of Scope

- 不引入外部缓存服务，保持 local-first（SQLite/diskcache）。

## Acceptance Criteria

- [ ] 构造仅改一个模块的提交，重跑只重生成受影响页面，其余页面哈希不变。
- [ ] 相同输入二次运行 LLM 调用数为 0（缓存命中），并有统计输出。
- [ ] 人工编辑区在重生成后内容不变，marker 不配对时验证失败。
- [ ] 输出增量范围与成本对比报告，供多仓库验收引用。

## References

- 代码：`repo_wiki/orchestration/invalidation.py`、`repo_wiki/orchestration/generation_invalidation.py`、`repo_wiki/generator/composer_cache.py`、`repo_wiki/llm/cache.py`、`repo_wiki/orchestration/cost_estimator.py`
- 规范：`docs/plans/display-and-wiki-generation-optimization-roadmap.md` §3.7–3.9
