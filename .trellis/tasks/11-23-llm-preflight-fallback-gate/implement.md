# 执行计划：llm-preflight-fallback-gate

## 顺序

1. [x] 新增 `repo_wiki/llm/preflight.py`：协议一致性 + 最小探针 + 原因码（`LLM_ENDPOINT_MISMATCH`/`LLM_AUTH_INVALID`/`LLM_UNREACHABLE`/`OK`/`skipped_mock`，另含 `LLM_CLIENT_INIT_FAILED`/`LLM_EMPTY_RESPONSE`）；错误信息不含 key 值。
2. [x] `diagnostics.run_llm_diagnostics` 纳入 preflight；`config --ci` 对 404/401 类错配报 FAIL（summary 不再 OK）。离线段（协议一致性 + client 构造）默认执行；凭据探针经 `--probe` 显式开启，保持 `config --ci` 默认零网络（generate 始终探针）。
3. [x] `service._generate_isolated_eval` compose 前执行 preflight；非 OK 且非 mock → 中止并抛分类错误，不产出 fallback run。
4. [x] composer/manifest：每页 `generation_mode` + `rejection_reason`；metadata `effective_provider`/`preflight_status`/`preflight_reason_code`/`llm_success_ratio`（另含 `is_mock_run`/`llm_mode`/`min_llm_success_ratio`）。
5. [x] readiness：`llm_success_ratio < QoderLikeConfig.min_llm_success_ratio`（默认 0.5，YAML/env `REPO_WIKI_QODER_LIKE_MIN_LLM_SUCCESS_RATIO` 可配）或熔断 → NOT_READY + `FALLBACK_ONLY_RUN`/`LLM_PROVIDER_DISABLED`；mock run → NOT_READY + `MOCK_LLM_RUN` + metadata mock 标记。
6. [x] 统计并更新受 mock-readiness 变更影响的历史测试断言：base b8d9c90 上没有任何测试对 mock generate run 断言 READY（grep + git show 核实）；2 个 mock pilot 测试（test_eval_manifest、test_qoder_like_profile）收紧为 NOT_READY + mock 标记，2 个 config doctor 测试与 1 个 quality-artifacts 测试做环境隔离（proxy env / fake real provider），共 5 个；未删测试、未放宽阈值。
7. [x] 新增合同测试 `tests/test_llm_preflight_gate.py`：四类负例 + mock 豁免 + 阈值可配 + 每页 mode 字段存在（44 个测试，全部通过，零真实网络）。
8. [x] 按调度约束以离线演示替代真实网络验证（禁止真实 LLM 调用；真实 run 参照 `.repo-agent-eval/self-real2-20261123`）：错配 env 下 `config --ci` exit=1 + `LLM_ENDPOINT_MISMATCH`；`NO_PROXY='[::1]'` 下 exit=1 + `LLM_CLIENT_INIT_FAILED`（probe_attempted=False，零网络）。

## 验证命令

```bash
.venv/bin/python -m pytest tests/test_llm_preflight_gate.py -q
.venv/bin/python -m pytest tests -q -k "llm or composer or readiness or manifest or service"
.venv/bin/python -m pytest tests -q        # 全量，报告失败清单并与 base 对照
.venv/bin/python -m repo_wiki.main config --ci   # 错配 env 下必须 FAIL
```

## 评审门

- 错配/无效凭据不再烧完整轮生成；错误信息可操作且不含 key。
- 全 fallback 与 mock run 均非 READY；真实 LLM run 的 readiness 由质量门禁决定而非生成模式一刀切。
- 既有 prose/citation/mermaid 阈值零改动。
- `.env` 与任何跟踪文件不含真实 key。

## 回滚点

步骤 1-5 可单独 revert；步骤 6 的断言更新随门禁变更一起回滚。