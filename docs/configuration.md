# repo-wiki 终端用户配置指南（LLM）

本文档说明如何为 **repo-wiki** 配置大模型（LLM）接入：读写配置的位置、`repo-wiki config` 诊断命令、各厂商与本地兼容方案，以及 **Mock / 真实调用** 的差异与常见问题。**请勿**将真实 API 密钥写入仓库；示例中的密钥均为占位符。

## 1. 配置文件与环境变量

### 1.1 配置文件路径

默认按以下顺序查找 YAML（也可用 `--config /path/to/file.yaml` 指定）：

| 优先级 | 文件 |
|--------|------|
| 1 | 命令行 `--config` 指向的文件 |
| 2 | 当前工作目录下的 `repo-wiki.yaml` |
| 3 | 当前工作目录下的 `.repo-wiki.yaml` |

YAML 顶层结构与代码中的 `RepoWikiConfig` 对应；与 LLM 相关的字段位于 **`llm:`** 下，并与 `LLMProviderConfig` 对齐（见下文字段说明）。

此外，目标仓库根目录存在 **`.env`** 时，会在加载配置后尝试加载（**不覆盖**已在进程中设置的环境变量）。

### 1.2 `llm` 字段说明（YAML）

| 字段 | 含义 | 示例 |
|------|------|------|
| `provider` | 提供商标识：`openai`、`minimax`、`anthropic` 等 | `minimax` |
| `model` | 模型 ID（厂商相关） | `abab6-chat`、`gpt-4o-mini` |
| `base_url` | HTTP API 根地址（兼容网关、Azure、Ollama 等必填） | `https://api.minimax.chat/v1` |
| `api_key_env` | **存放密钥的环境变量名**（不是密钥本身） | `MINIMAX_API_KEY` |
| `max_tokens` | 单次回复 token 上限 | `4096` |
| `temperature` | 采样温度 | `0.7` |
| `timeout` | 单次请求超时（秒） | `60` |
| `max_retries` | 失败重试次数 | `3` |

### 1.3 环境变量覆盖（与实现对齐）

除 YAML 外，可通过下列变量覆盖（解析优先级见第 2 节）。名称来自 `repo_wiki.llm.config.resolve_llm_config`：

| 环境变量 | 映射到配置键 |
|----------|----------------|
| `LLM_PROVIDER` | `provider` |
| `LLM_MODEL` | `model` |
| `LLM_BASE_URL` | `base_url` |
| `LLM_API_KEY_ENV` | `api_key_env` |
| `LLM_MAX_TOKENS` | `max_tokens` |
| `LLM_TEMPERATURE` | `temperature` |
| `LLM_TIMEOUT` | `timeout` |
| `LLM_MAX_RETRIES` | `max_retries` |

**Minimax 兼容别名（历史 `.env`）：** 若存在 `APP_LLM_MINIMAXI_API_KEY` 或 `APP_LLM_MINIMAX_API_KEY`，会自动将 `provider` 设为 `minimax`，并可用同前缀的 `_MODEL`、`_BASE_URL` 覆盖模型与地址。

### 1.4 临时终端注入（不写入文件）

```bash
# 输入不会回显；关闭终端后变量失效
read -rsp "Minimax API key: " MINIMAX_API_KEY && echo
read -rsp "OpenAI API key: " OPENAI_API_KEY && echo
read -rsp "Anthropic API key: " ANTHROPIC_API_KEY && echo
export MINIMAX_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY
```

---

## 2. 配置解析优先级

由高到低（与 `resolve_llm_config` 一致）：

1. **`repo-wiki config` 的命令行参数**（见第 3 节）
2. **上述 `LLM_*` 及 Minimax 别名环境变量**
3. **YAML 中的 `llm:`**
4. **内置默认值**（如未指定 `provider` / `model` 等）

此外，当 `provider` 为 **`minimax`** 且仍使用 OpenAI 的默认模型占位时，解析逻辑会将默认模型调整为 **`abab6-chat`**，并将默认 `api_key_env` 调整为 **`MINIMAX_API_KEY`**（若你未显式配置）。

---

## 3. 配置诊断：`repo-wiki config`

对应实现：`repo_wiki.cli.config_command`。用于校验字段、检查密钥是否在环境中可用（输出侧会做脱敏）。

```bash
# 人类可读（默认）
repo-wiki config --config /path/to/repo-wiki.yaml

# 机器可读 JSON（CI / 脚本）
repo-wiki config --config /path/to/repo-wiki.yaml --ci
```

常用临时覆盖（与实现对齐）：

```bash
repo-wiki config \
  --provider minimax \
  --model abab6-chat \
  --api-key-env MINIMAX_API_KEY \
  --ci
```

说明：

- **`--ci`**：输出结构化 JSON，便于自动化；密钥不会明文打印。
- 若摘要为 **`FAIL`**，退出码为非零（适合 CI）。

---

## 4. 按场景配置示例（YAML + 环境）

以下示例中的密钥均为占位符；**仅通过 `api_key_env` 引用环境变量名**。

### 4.1 Minimax（原生 Chat Completion）

默认 HTTP 根路径未设置时，适配器使用 **`https://api.minimax.chat/v1`**，请求路径为 Minimax 文档中的 chat completion（实现见 `MinimaxProvider`）。

```yaml
llm:
  provider: minimax
  model: abab6-chat
  api_key_env: MINIMAX_API_KEY
  base_url: null
  timeout: 60
  max_retries: 3
```

```bash
export MINIMAX_API_KEY="YOUR_KEY_PLACEHOLDER"
```

### 4.2 Minimax（Anthropic 兼容网关）

当 **`base_url` 中包含路径片段 `/anthropic`** 时，适配器走 **Anthropic 兼容** 请求路径（用于厂商提供的 Anthropic 风格接口）。

```yaml
llm:
  provider: minimax
  model: MiniMax-M2.7
  api_key_env: MINIMAX_API_KEY
  base_url: https://api.minimax.chat/v1/anthropic
```

### 4.3 OpenAI 兼容（官方 OpenAI / Azure OpenAI / 任意兼容网关）

非 `minimax` 时，运行时通过 **`OpenAICompatibleProvider`**，请求 **`POST {base_url}/chat/completions`**（OpenAI Chat Completions 形状）。

**官方 OpenAI（默认 base）：**

```yaml
llm:
  provider: openai
  model: gpt-4o-mini
  api_key_env: OPENAI_API_KEY
  # base_url 省略则默认为 https://api.openai.com/v1
```

```bash
read -rsp "OpenAI API key: " OPENAI_API_KEY && echo
export OPENAI_API_KEY
```

**兼容网关 / Azure（自定义 base_url）：**

```yaml
llm:
  provider: openai
  model: gpt-4o
  base_url: https://YOUR_RESOURCE.openai.azure.com/openai/deployments/YOUR_DEPLOYMENT
  api_key_env: AZURE_OPENAI_API_KEY
```

请将 `base_url` 配成你的网关实际前缀（是否包含 `/v1` 依网关而定）。

### 4.4 Anthropic 兼容（经 OpenAI 兼容适配器）

代码路径上 **`anthropic` 与 `openai` 一样走 `OpenAICompatibleProvider`**（`/chat/completions`）。因此直连 **Anthropic 原生 Messages API**（`/v1/messages`）时，需要前置 **兼容层**（例如 LiteLLM、私有网关），对外仍暴露 OpenAI 形态的 `chat/completions`。

```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-20250514
  base_url: https://your-litellm-or-proxy.example.com/v1
  api_key_env: ANTHROPIC_API_KEY
```

若网关要求使用 OpenAI 字段名，请同时核对网关文档中的 **model** 命名。

### 4.5 本地模型（Ollama / LM Studio 等）

本地服务通常提供 **OpenAI 兼容** 接口；将 **`base_url`** 设为服务暴露的 **`.../v1`** 根路径。

```yaml
llm:
  provider: openai
  model: llama3.3
  base_url: http://127.0.0.1:11434/v1
  api_key_env: OLLAMA_DUMMY_KEY
```

多数本地进程不要求密钥，可设占位 env 或在网关关闭鉴权；若 `api_key_env` 指向的变量为空，诊断会报 **`MISSING_API_KEY`**，但不影响部分本地栈——以你的网关为准。

---

## 5. Mock 与真实调用（为何生成仍是占位正文）

### 5.1 qoder-like 生成路径中的策略

在 **`resolve_qoder_like_llm`**（由 **`RepoWikiService._resolve_qoder_like_llm`** 调用，qoder-like / LLM 编排路径）中：

- **真实 HTTP 调用**：`api_key_env` 指向的环境变量**已设置非空**，且**未**强制 mock → 使用 **`create_provider_from_config`**（`minimax` → Minimax；其它 provider → OpenAI 兼容客户端，可配合 `base_url` 对接网关或本地 Ollama 等）。
- **Mock**：无 API key，或强制 mock（见下）。Mock 与真实路径共用同一套 page-plan、证据绑定与 composer，但 **token/耗时/成本为合成或占位**，**不宜与真实 pilot 直接对比**。

**强制使用 Mock（CI / 可重复测试）**

- 环境变量 **`REPO_WIKI_FORCE_MOCK_LLM=1`**（或 `true` / `yes` / `on`）。
- 配置 **`llm.force_mock_llm: true`**（`repo-wiki.yaml` / `.repo-wiki.yaml`）。

强制 mock 时会在日志中说明原因；因**缺少密钥**而回退 mock 时会 **`warn`**，避免静默误以为已在调用真实模型。

### 5.2 Mock 行为概要

- **无网络**、**无密钥**。
- 返回可预测的占位 Markdown，用于结构与门禁测试。
- `repo-wiki config` 仍会按你声明的 provider 校验缺失项；与运行时是否 Mock 无关。

### 5.3 qoder-like 计划页规模（下限 / 上限）

独立评估输出（`--profile qoder-like`）在编排层会**先补齐固定分类根页**，再按需要插入「专题」页，使计划页数不低于 **下限**，再按 **上限** 做裁剪。历史上曾用 **120** 作为硬编码下限，导致**极小仓库**被大量「专题」页顶满，信息密度与成本不匹配；当前默认改为 **较保守的下限**。

| 来源 | 说明 |
|------|------|
| **YAML** `qoder_like.min_pages` | 默认 **24**（约 20–30 篇量级，可按仓库调大） |
| **YAML** `qoder_like.max_pages` | 默认 **220**（与 Qoder 体量对标时的常见上限） |
| **环境变量** `REPO_WIKI_QODER_LIKE_MIN_PAGES` | 若设置，**覆盖** YAML 中的 `min_pages` |
| **环境变量** `REPO_WIKI_QODER_LIKE_MAX_PAGES` | 若设置，**覆盖** YAML 中的 `max_pages`（**不再有**旧的 `max(120, env)` 下限） |

编排时会取 **`min(下限, 上限)`** 作为实际下限，避免二者冲突。需要对标杆仓复制「大而全」树时，可提高 `min_pages` 或仅拉高 `max_pages`（例如 Reference 试点）。

---

## 6. 常见问题排查

| 现象 | 可能原因 | 处理方向 |
|------|----------|----------|
| `MISSING_API_KEY` | `api_key_env` 未设置或对应变量为空 | `export YOUR_ENV="..."`；与 YAML 中名称一致 |
| `401` / `AUTH_FAILURE` | 密钥错误或无权访问模型 | 轮换密钥；检查厂商控制台权限 |
| `429` / `RATE_LIMIT` | 限速 | 降低并发；增大 `max_retries`；稍后再试 |
| 超时 | 网络或模型慢 | 增大 `timeout`；检查 `base_url` 可达性 |
| 本地连接失败 | `base_url` 错误或未监听 | 确认 Ollama `ollama serve`；端口与 `/v1` 路径 |
| qoder-like 输出仍是占位说明 | 无 API key、或 `force_mock_llm` / `REPO_WIKI_FORCE_MOCK_LLM` | 见第 5.1 节；检查日志中的 mock 原因 |
| qoder-like 计划页过多 / 过少 | `qoder_like.min_pages` / `max_pages` 或 `REPO_WIKI_QODER_LIKE_*` | 见第 5.3 节 |
| 插件未显示 Wiki | 未发布 READY release 到固定目录 | 运行 `repo-wiki release-publish --output .repo-agent-eval --run <run-id>` |
| 不确定旧 run 是否为旧版 `content/` 布局 | 仍为评估目录、非发布迁移 | 运行 `repo-wiki eval-layout-report --output .repo-agent-eval`（仅报告，不改动） |
| `config` 显示 FAIL | 见诊断 `issues` 列表 | 优先修复 API key 与 provider/model |

---

## 7. 与其它文档的关系

- 回归与治理看板（趋势导出等）依赖仓库扫描与索引配置；本文仅覆盖 **LLM 接入**。
- 更偏运维的叙述也可参见 `docs/operations/llm-provider-configuration.md`（首页已指向本文为准）。

---

## 8. 最小可用 YAML 模板（复制后自行改）

```yaml
project:
  root: .
  name: my-repo

llm:
  provider: minimax
  model: abab6-chat
  api_key_env: MINIMAX_API_KEY
  max_tokens: 4096
  temperature: 0.7
  timeout: 60
  max_retries: 3
```

配合：

```bash
export MINIMAX_API_KEY="REPLACE_ME"
repo-wiki config --ci
```

确认 `summary` 为 **`OK`** 后，再执行 `repo-wiki generate --profile qoder-like` 等工作流。
