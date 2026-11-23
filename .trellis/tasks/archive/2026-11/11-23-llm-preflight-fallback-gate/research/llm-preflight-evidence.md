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
| `https://api.minimaxi.com/v1` + `/chat/completions`（旧 `sk-cp-…`/`ANTHROPIC_AUTH_TOKEN`） | HTTP 401 `invalid api key (2049)` | 旧 key 只对 Anthropic 协议网关有效 |
| `https://platform.minimaxi.com/v1` + `/chat/completions`（用户新提供 key） | HTTP 404 **HTML 控制台页** | `platform.` 是 Web 控制台域名，不是 API host |
| `https://api.minimax.io/v1`（新 key） | HTTP 401 | 国际站 host 不接受该 key |
| `https://api.minimaxi.com/v1`（新 key，2026-11-23 用户提供） | **HTTP 200** | 可用组合：openai provider + `api.minimaxi.com/v1` |

**可用配置（非敏感部分）**：`LLM_PROVIDER=openai`、`LLM_BASE_URL=https://api.minimaxi.com/v1`、`LLM_MODEL=MiniMax-M2.7`、key 走临时环境变量。真实 key 不落盘；用户已在对话中暴露该 key，**须轮换**。

预检设计启示：404 需区分"HTML 控制台页"与"JSON API 错误"——前者是 host 选错（控制台域名），后者才是路径/协议错配；两者都归 `LLM_ENDPOINT_MISMATCH` 但提示文案不同。

## 第三个缺陷：环境代理/NO_PROXY 使 httpx client 构造崩溃（2026-11-23 实测）

凭据与端点都正确（探针 200）后，generate 仍 80 页全 fallback，manifest 记录 `Composition error: Invalid port: ':1]'`。

traceback 定位：`repo_wiki/llm/adapters.py:62` `httpx.AsyncClient(base_url=…)` → httpx `_client.py:1413` `URLPattern(key)` → `_urlparse.py:411` `InvalidURL`。base_url 本身合法；崩溃来自 **trust_env 读取的环境代理配置**：本机 `NO_PROXY=localhost,.localhost,127.0.0.1,127.0.0.0/8,[::1],::1` 中的裸 IPv6 条目被 httpx 当 URL 解析，端口解析出 `':1]'`。

- 复现：任意合法 base_url + 上述 NO_PROXY → `httpx.InvalidURL: Invalid port: ':1]'`。
- 绕过：临时 `NO_PROXY='localhost,127.0.0.1' no_proxy='localhost,127.0.0.1'` 后重跑（run `self-real2-20261123`）。
- 缺陷本质：client 构造期的环境错误被 composer 的宽泛 `except Exception` 吞成 `Composition error`，连续 3 次后熔断，烧完整轮且无 actionable 提示。

预检必须覆盖：client 构造失败单独归类 `LLM_CLIENT_INIT_FAILED`，提示检查 `HTTP(S)_PROXY`/`NO_PROXY`（尤其裸 IPv6/ CIDR 条目），并在 compose 前失败快。适配器侧应在 `_get_client` 捕获 `httpx.InvalidURL` 并给出含 env 变量名的可操作错误（不含 proxy 凭据）。

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