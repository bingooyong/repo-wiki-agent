# 增量与缓存设计（任务：incremental-llm-cache）

## 失效链

git diff → 变更文件 → module/evidence/page index → 受影响页面 + 聚合页 → 仅重建这些页面；manifest 记录增量范围（变更文件、失效页面、跳过页面及原因）。

## 人工编辑区

标记：`<!-- repo-wiki:manual:start -->` / `<!-- repo-wiki:manual:end -->`。重生成保留区块内容；marker 不配对时 verify 失败。

## LLM 缓存

key 至少含：prompt hash、evidence hash、model、provider、temperature、max_tokens、composer version。命中不计入 LLM 调用；`improve-status` 展示命中/未命中统计。存储沿用本地 SQLite/diskcache，不引入外部服务。知识卡与长文共用失效与缓存机制。

## 代码集成点（仅供实现者自行阅读，不注入）

`repo_wiki/orchestration/invalidation.py`、`generation_invalidation.py`、`generation_scheduler.py`、`repo_wiki/generator/composer_cache.py`、`repo_wiki/llm/cache.py`、`repo_wiki/orchestration/cost_estimator.py`。

## 验收

1. 单模块变更提交：仅受影响页面重生成，其余页面哈希不变。
2. 相同输入二次运行 LLM 调用数为 0，并输出统计。
3. 人工编辑区内容保持，marker 不配对判负。
4. 输出增量范围与成本对比报告，供 `11-22-multi-repo-acceptance` 引用。
