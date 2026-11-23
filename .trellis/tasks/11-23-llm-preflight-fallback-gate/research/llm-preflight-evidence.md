# LLM 预检与 fallback 门禁证据（2026-11-23）

## 复现命令与实测

```bash
.venv/bin/python -m repo_wiki.main config --ci          # summary: OK（只校验字段格式）
.venv/bin/python -m repo_wiki.main generate --profile qoder-like \
    --output .repo-agent-eval --run-id self-compare-20261123
```

日志关键行：

```text
INFO compose configured provider=openai model=MiniMax-M2.7 pages=80
INFO llm page completed attempt=1 page_id=project-overview tokens=0 rejected=True
INFO llm page completed attempt=2 page_id=architecture-overview tokens=0 rejected=True
INFO llm page completed attempt=3 page_id=api-overview tokens=0 rejected=True
INFO compose provider disabled consecutive_failures=3 max_failures=3
```

结果：80 页全部 fallback；`manifest.json` 仍 `readiness_state=READY`、`readiness_reasons=[]`。

## 端点/凭据探针（最小请求 max_tokens=8）

| base_url | 结果 | 结论 |
|----------|------|------|
| `https://api.minimaxi.com/anthropic` + `/chat/completions` | HTTP 404 `404 page not found` | OpenAI 协议打到 Anthropic 协议端点 |
| `https://api.minimaxi.com/v1` + `/chat/completions` | HTTP 401 `invalid api key (2049)` | `sk-cp-…`（env `ANTHROPIC_AUTH_TOKEN`）只对 Anthropic 协议网关有效 |

`.env` 现状：`LLM_PROVIDER=openai`、`LLM_BASE_URL=https://api.minimaxi.com/anthropic`、`LLM_MODEL=MiniMax-M2.7`、`LLM_API_KEY_ENV=ANTHROPIC_AUTH_TOKEN`。**不修改 .env**；修复方向是预检报错与降级语义，不是替用户改凭据。

## manifest 字段缺口

`page_registry[*]` 仅含 `absolutePath/path/slug/title/type`；无 `generation_mode`、`rejection_reason`、引用元数据。metadata 无 `effective_provider`/`preflight_status`。

## 代码集成点（仅供实现者自行阅读，不注入）

- `repo_wiki/llm/qoder_like_provider.py:31` `resolve_qoder_like_llm`
- `repo_wiki/llm/diagnostics.py:17` `create_provider_from_config`、`run_llm_diagnostics`
- `repo_wiki/llm/adapters.py:22` `OpenAICompatibleProvider`（`chat` 在 providers 基类 :62）
- composer 熔断与 readiness：`repo_wiki/orchestration/service.py`（`_generate_isolated_eval`、readiness 判定）
- 既有 mock 开关：`REPO_WIKI_FORCE_MOCK_LLM` / `LlmConfig.force_mock_llm`

## 验收负例清单

1. openai + `/anthropic` base → 预检 FAIL，原因码 `LLM_ENDPOINT_MISMATCH`。
2. 正确 base + 无效 key → 预检 FAIL，原因码 `LLM_AUTH_INVALID`。
3. 强制 mock → 不阻塞，但 run 不得 READY（或显式 mock 标记）。
4. 全 fallback run → `NOT_READY` + `FALLBACK_ONLY_RUN`，每页 `generation_mode=fallback`。