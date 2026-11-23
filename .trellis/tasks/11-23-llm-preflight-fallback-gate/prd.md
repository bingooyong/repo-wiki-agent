# LLM 协议/凭据预检与 fallback 不得 READY

## Context

2026-11-23 对本仓执行 `generate --profile qoder-like --run-id self-compare-20261123`（真实 LLM 意图）暴露两个 P0 缺陷：

1. **协议/凭据错配无预检**：`.env` 为 `LLM_PROVIDER=openai` + `LLM_BASE_URL=https://api.minimaxi.com/anthropic` + `LLM_API_KEY_ENV=ANTHROPIC_AUTH_TOKEN`（`sk-cp-…`）。OpenAI 兼容适配器向 `{base}/chat/completions` 发请求 → **404**；改用 MiniMax OpenAI 端点 `https://api.minimaxi.com/v1` → **401 invalid api key**（该 key 只服务于 Anthropic 协议网关）。composer 连续 3 次 `tokens=0 rejected=True` 后熔断，80 页全部 fallback。`config --ci` 却报 `summary: OK`——诊断只校验字段格式，不校验协议连通性与凭据有效性。
2. **全 fallback 仍标 READY**：该 run 的 `manifest.json` `readiness_state=READY`、`readiness_reasons=[]`，且 `page_registry` 每页只有 `absolutePath/path/slug/title/type`，**没有 generation_mode、没有证据/引用覆盖字段**。下游插件徽标与 release 门禁因此无法区分 LLM 正文与规则兜底正文。

## Goal

让"配置错"在烧掉整轮生成之前被看见，让"兜底产物"永远进不了 READY。

## Requirements

- 预检（generate 与 config --ci 共用）：
  - 协议一致性：`provider=openai` 时 base_url 不得指向 Anthropic 协议路径（如 `/anthropic`）；给出可操作提示（改 base 或改 provider）。
  - 连通性/凭据：用最小请求（max_tokens≤8）探测一次；401/403/404 分类报错，指明是凭据还是端点问题；探测失败不得静默进入 compose。
  - 预检结果写入 run 的 metadata 与 diagnostics，含 `effective_provider`、`preflight_status`、失败原因码。
- 熔断与降级语义：
  - 保留连续失败熔断，但熔断后 run 的 `readiness_state` 必须为 `NOT_READY`，reason 含 `LLM_PROVIDER_DISABLED` / `FALLBACK_ONLY_RUN`。
  - 单页 fallback 允许存在，但 manifest 每页必须记录 `generation_mode`（llm / rule / fallback）与 `rejection_reason`（若有）。
- READY 门禁：全页 fallback 或 LLM 成功页占比低于阈值（建议 <0.5，可配置）时禁止 READY；不得通过放宽既有 prose/citation 阈值实现。
- 插件/ viewer 消费 `generation_mode` 展示徽标的数据契约同步定义（实现归任务 6）。

## Out of Scope

- 不替用户选择或写入真实 API Key；不修改 `.env`。
- 不实现知识卡导出（任务 4）、不做 IA 重写（任务 5）。

## Acceptance Criteria

- [ ] 错配配置（openai + /anthropic base）下 `config --ci` 与 `generate` 预检均 FAIL 并给出端点/凭据分类原因，不再产出 80 页 fallback。
- [ ] 凭据无效（401）时预检 FAIL，原因码区分 `LLM_AUTH_INVALID` 与 `LLM_ENDPOINT_MISMATCH`。
- [ ] 强制 mock（`REPO_WIKI_FORCE_MOCK_LLM`）路径不受预检阻塞，但 run 标 `NOT_READY` 或明确 `mock` 标记，不得 READY。
- [ ] 全 fallback run 的 manifest `readiness_state=NOT_READY`，`page_registry[*].generation_mode` 全为 fallback/rule。
- [ ] 新增合同测试覆盖上述四类负例；既有 strict 阈值不变。

## References

- 证据 run：`.repo-agent-eval/self-compare-20261123/manifest.json`、生成日志（composer `provider disabled consecutive_failures=3`）
- 代码：`repo_wiki/llm/qoder_like_provider.py:31`、`repo_wiki/llm/diagnostics.py:17`、`repo_wiki/llm/adapters.py:22`、composer 熔断与 readiness 判定（`repo_wiki/orchestration/service.py`）
- 关联：任务 3（证据门禁）、任务 6（徽标与发布闭环）