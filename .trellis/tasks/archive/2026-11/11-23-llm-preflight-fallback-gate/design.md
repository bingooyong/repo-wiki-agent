# 设计：LLM 预检与 fallback 门禁

## 组件

| 组件 | 职责 |
|------|------|
| `repo_wiki/llm/preflight.py`（新增） | 协议一致性检查 + 最小连通性/凭据探针，返回结构化 `PreflightResult` |
| `repo_wiki/llm/diagnostics.py` | `run_llm_diagnostics` 纳入 preflight，`config --ci` 对错配/无效凭据报 FAIL |
| `repo_wiki/orchestration/service.py` | `_generate_isolated_eval` 在 compose 前执行 preflight；失败即中止（不产出 fallback run） |
| composer / manifest | 每页 `generation_mode`（llm/rule/fallback/mock）+ `rejection_reason`；metadata 增加 `effective_provider`、`preflight_status`、`llm_success_ratio` |
| readiness 判定 | `llm_success_ratio < min_llm_success_ratio`（默认 0.5，YAML/env 可配）或 provider 熔断 → `NOT_READY` + `FALLBACK_ONLY_RUN`/`LLM_PROVIDER_DISABLED` |

## 预检规则

1. **协议一致性**（不发网络请求）：
   - `provider=openai` 且 `base_url` 路径以 `/anthropic` 结尾（或含 `/anthropic/`）→ `LLM_ENDPOINT_MISMATCH`，提示改 base 或改 provider。
   - `provider=minimax` 且 base 指向非 MiniMax host → 警告级提示（不硬失败，host 可自建代理）。
2. **最小探针**：`max_tokens=8`、单条 user 消息，超时沿用 config.timeout 但上限 15s。
   - HTTP 401/403 → `LLM_AUTH_INVALID`
   - HTTP 404/405 → `LLM_ENDPOINT_MISMATCH`
   - 连接/DNS/超时 → `LLM_UNREACHABLE`
   - 2xx 且有 content → `OK`
3. **mock 豁免**：`force_mock_llm` / `REPO_WIKI_FORCE_MOCK_LLM` 时跳过探针，`preflight_status=skipped_mock`。
4. 探针只读、不写任何文件；错误信息**不得包含 key 值**（只报 env 名与状态码）。
5. **client 构造失败单独归类** `LLM_CLIENT_INIT_FAILED`：捕获 `httpx.InvalidURL` 等构造期异常，提示检查 `HTTP(S)_PROXY`/`NO_PROXY`（裸 IPv6/CIDR 条目会被 httpx 当 URL 解析而崩溃，实测 `Invalid port: ':1]'`）。适配器 `_get_client`（`adapters.py:62`）同样捕获并抛含 env 变量名的可操作错误，不得让 composer 的宽泛 `except Exception` 把它吞成 `Composition error` 后熔断烧完整轮。

## fallback 语义与兼容性决策

- 单页 fallback 仍允许（局部降级），但必须记录 mode 与 reason。
- 全 fallback / 低成功率 run → `NOT_READY`。这是门禁收紧，不是放宽。
- **mock run 不得 READY**：metadata 标 `generation_mode=mock` 且 `readiness_state=NOT_READY`（reason `MOCK_LLM_RUN`）。历史 mock pilot 的 READY 叙事作废；受影响测试需同步更新断言（改为断言 NOT_READY + mock 标记），**不得**通过放宽阈值或删测试变绿。实现者须先统计受影响测试数量并报告。
- 既有 prose/citation/mermaid 阈值一律不动。

## 数据契约

`page_registry[*]` 增加：`generation_mode`、`rejection_reason`（可空）、`cited_files`、`line_anchor_count`、`section_source_count`（后三者为任务 3/6 预留，本轮至少填 mode/reason，引用元数据若 composer 已有则顺带填充，否则留空数组/0 并在 PRD 注明由任务 3 补齐）。

`metadata` 增加：`effective_provider`、`preflight_status`、`preflight_reason_code`（可空）、`llm_success_ratio`。

## 边界

- 不修改 `.env`、不写入任何真实 key。
- 不新增 Anthropic 协议适配器（用户未选该选项）。
- 不做知识卡/IA/插件 UI。

## 回滚

新增模块 + 判定收紧均可单独 revert；mock readiness 变更若引发大面积历史断言冲突，回滚点为"仅加 mock 标记、readiness 保持旧值"的中间态——但该中间态不满足 PRD，需用户确认后才可采用。