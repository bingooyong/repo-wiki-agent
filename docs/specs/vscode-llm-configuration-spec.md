# VS Code/Cursor LLM 配置能力规格说明

**状态：** Draft / implementation-ready
**日期：** 2026-07-08
**适用范围：** `repo-agent` / `repo-wiki` 的 VS Code/Cursor 插件 `Repo Wiki Browser`
**关联规划：** `docs/repo-agent-next-tasks-and-vscode-llm-config-plan.md`
**后续实施计划：** `docs/plans/vscode-llm-configuration-implementation-plan.md`

---

## 1. 背景与问题

`repo-wiki` 的核心生成器是 Python CLI，VS Code/Cursor 插件当前主要承担 Wiki release 浏览和终端命令触发能力。现状中插件只贡献 `repoWikiBrowser.generateCommand`，并从 `repo-wiki.yaml` / `.repo-wiki.yaml` 读取少量 LLM 摘要用于展示；它尚未提供大模型 provider、API 地址、模型名称和 API Key 的端到端配置闭环。

Python 侧已经具备可复用的配置契约：`repo_wiki/llm/config.py` 支持 `provider`、`model`、`base_url`、`api_key_env`，并能通过 `LLM_PROVIDER`、`LLM_MODEL`、`LLM_BASE_URL`、`LLM_API_KEY_ENV` 环境变量覆盖 YAML。插件应复用该契约，而不是另起一套 CLI 参数或把敏感信息写入命令文本。

---

## 2. 目标

### 2.1 产品目标

让 VS Code/Cursor 用户无需手动编辑 YAML 或 shell 环境，即可在插件中完成：

1. 选择或输入 LLM provider；
2. 配置 OpenAI-compatible API `base_url` / API 地址；
3. 配置模型名称；
4. 安全保存 API Key；
5. 测试当前 LLM 配置；
6. 使用当前配置触发 `repo-wiki` 生成/更新 Wiki。

### 2.2 工程目标

- 复用 Python CLI 已有的 `LLM_*` 环境变量覆盖机制。
- 保持现有 `repoWikiBrowser.generateCommand` 的兼容性。
- 真实 API Key 只存储在 VS Code SecretStorage，不进入 settings、YAML、命令字符串、日志、manifest 或测试快照。
- 在侧栏明确展示配置来源、provider、model、base URL、key-present 状态和诊断结果。

---

## 3. 非目标

本规格不要求在第一阶段完成以下事项：

- 插件内直接实现 LLM HTTP 客户端；真实 LLM 调用仍由 Python CLI 执行。
- 插件打包或内置 Python `repo-wiki` CLI。
- 支持所有 provider 的高级参数 UI；MVP 只要求 provider、model、base URL、API Key 和 `apiKeyEnv`。
- 自动保留 YAML 注释的复杂写回；若实现写回，必须先做保守合并或提示用户可能改变格式。
- 将真实 API Key 写入任何仓库文件。

---

## 4. 用户故事

### US-001 Provider 与模型配置

作为 VS Code/Cursor 用户，我希望在插件中设置 LLM provider 和模型名称，以便无需手动编辑 `repo-wiki.yaml` 即可切换 OpenAI-compatible、Minimax、Anthropic-compatible 或自定义网关。

**验收标准：**

- 插件 settings 中存在 `repoWikiBrowser.llm.provider` 和 `repoWikiBrowser.llm.model`。
- 空值不会覆盖用户已有 YAML 或 shell 环境。
- Update Wiki 时非空值映射到 `LLM_PROVIDER` 和 `LLM_MODEL`。

### US-002 API 地址配置

作为团队用户，我希望配置 API base URL，以便通过企业代理、私有模型网关或 OpenAI-compatible 服务生成 Wiki。

**验收标准：**

- 插件 settings 中存在 `repoWikiBrowser.llm.baseUrl`。
- 非空值映射到 `LLM_BASE_URL`。
- UI 显示 base URL，但不把它当作 secret 处理。

### US-003 API Key 安全保存

作为安全敏感用户，我希望 API Key 只保存在 IDE 密钥库中，以避免密钥泄露到 settings、YAML、终端命令历史或日志。

**验收标准：**

- 插件提供 Set API Key 与 Clear API Key 命令。
- 真实 key 只进入 VS Code SecretStorage。
- 插件 UI 只显示 `API Key Present: Yes/No`，不展示真实 key。
- settings、YAML、output channel、webview HTML、manifest、测试快照中不得出现真实 key。

### US-004 使用插件配置运行 CLI

作为 IDE 用户，我希望点击 Update Wiki 时自动使用插件中的 LLM 配置，以便不需要手动 export 环境变量。

**验收标准：**

- 插件创建专用/可丢弃终端或非交互式子进程时注入 env。
- 注入项包括 `LLM_PROVIDER`、`LLM_MODEL`、`LLM_BASE_URL`、`LLM_API_KEY_ENV` 和 `apiKeyEnv` 指向的真实 key 环境变量。
- 命令文本本身不包含真实 key。
- 用户选择 Environment-first 时，插件不注入覆盖项。

### US-005 配置诊断

作为新用户，我希望测试当前 LLM 配置，并得到下一步修复建议。

**验收标准：**

- 插件提供 Test LLM Configuration 命令。
- 诊断调用当前 CLI 入口 `repo-wiki config --ci` 或等价非交互式流程。
- 诊断结果展示 provider、model、base_url、api_key_env、key-present、issues/reason codes。
- 诊断结果不展示真实 key。

---

## 5. 配置契约

### 5.1 VS Code settings

插件新增以下非敏感配置项：

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `repoWikiBrowser.generateCommand` | string | 现状默认值 | Update Wiki 发送到终端的命令，保持兼容。 |
| `repoWikiBrowser.llm.provider` | string | 空 | LLM provider；空值不覆盖 CLI/YAML 默认。 |
| `repoWikiBrowser.llm.model` | string | 空 | 通用模型名；映射 `LLM_MODEL`。 |
| `repoWikiBrowser.llm.baseUrl` | string | 空 | OpenAI-compatible API base URL；映射 `LLM_BASE_URL`。 |
| `repoWikiBrowser.llm.apiKeyEnv` | string | `REPO_WIKI_LLM_API_KEY` | 真实 key 注入 CLI 时使用的环境变量名；映射 `LLM_API_KEY_ENV`。 |
| `repoWikiBrowser.llm.source` | enum | `extension` | 配置来源策略：`extension`、`yaml`、`environment`。 |

禁止新增 `repoWikiBrowser.llm.apiKey` setting。

### 5.2 SecretStorage

MVP secret key：

```text
repoWikiBrowser.llm.apiKey
```

后续可演进为 workspace/provider 维度：

```text
repoWikiBrowser.llm.apiKey.<workspaceHash>.<provider>
```

迁移要求：若从 MVP key 迁移到 workspace/provider key，必须保留读旧 key 的兼容路径，并提供清理旧 key 的命令或提示。

### 5.3 CLI 环境变量映射

插件执行生成类命令时应按以下规则组装 env：

| 插件输入 | CLI 环境变量 | 是否可为空 | 说明 |
| --- | --- | --- | --- |
| provider | `LLM_PROVIDER` | 是 | 空值不注入。 |
| model | `LLM_MODEL` | 是 | 空值不注入。 |
| baseUrl | `LLM_BASE_URL` | 是 | 空值不注入。 |
| apiKeyEnv | `LLM_API_KEY_ENV` | 否 | 必须为合法环境变量名。 |
| SecretStorage API Key | `[apiKeyEnv]` | 是 | 只有存在真实 key 时注入。 |

`apiKeyEnv` 必须匹配：

```regex
^[A-Za-z_][A-Za-z0-9_]*$
```

### 5.4 YAML 协同

`repo-wiki.yaml` / `.repo-wiki.yaml` 可保存非敏感配置：

```yaml
llm:
  provider: openai
  model: gpt-4o-mini
  base_url: https://api.example.com/v1
  api_key_env: REPO_WIKI_LLM_API_KEY
```

但不得保存真实 API Key。

插件支持三种来源策略：

1. `extension`：settings + SecretStorage 优先，并通过 env 覆盖 CLI/YAML。
2. `yaml`：只读 YAML 摘要；不注入 provider/model/baseUrl，但可提示 key-present 状态。
3. `environment`：尊重用户 shell 环境；插件不注入 LLM 覆盖项。

---

## 6. 交互设计

### 6.1 命令

新增命令：

| 命令 ID | 标题 | 行为 |
| --- | --- | --- |
| `repoWikiBrowser.configureLlm` | `Repo Wiki: Configure LLM Provider` | 快速输入 provider、model、base URL、apiKeyEnv，并保存非敏感 settings。 |
| `repoWikiBrowser.setApiKey` | `Repo Wiki: Set API Key` | 通过 password input 获取 key 并保存到 SecretStorage。 |
| `repoWikiBrowser.clearApiKey` | `Repo Wiki: Clear API Key` | 删除 SecretStorage 中的 key。 |
| `repoWikiBrowser.testLlmConfig` | `Repo Wiki: Test LLM Configuration` | 注入 redacted-safe env 后运行 `repo-wiki config --ci` 并展示诊断。 |
| `repoWikiBrowser.importLlmFromYaml` | `Repo Wiki: Import LLM Settings from YAML` | 从 YAML 读取非敏感 LLM 配置到 settings。 |
| `repoWikiBrowser.writeLlmToYaml` | `Repo Wiki: Write LLM Settings to YAML` | 将非敏感配置写入 YAML；不得写真实 key。 |

### 6.2 侧栏状态面板

侧栏 LLM 面板应展示：

- Config Source：Extension / YAML / Environment；
- Provider；
- Model；
- Base URL；
- API Key Env；
- API Key Present：Yes/No；
- Diagnostics Summary：PASS/WARN/FAIL/Not tested；
- 操作入口：Configure / Set Key / Test / Clear Key。

默认不展示 key 尾号。若未来展示尾号，必须只在用户明确请求下展示，且不可写入日志或 telemetry。

---

## 7. 安全要求

### 7.1 禁止项

真实 API Key 禁止出现在：

- VS Code settings JSON；
- `repo-wiki.yaml` / `.repo-wiki.yaml`；
- 终端命令字符串；
- output channel / console / extension host 日志；
- webview HTML；
- release manifest；
- diagnostics JSON；
- README 示例；
- 测试快照；
- git tracked 文件。

### 7.2 运行时暴露边界

使用 `vscode.window.createTerminal({ env })` 时，env 会在该终端会话内持续存在。因此：

- 生成命令必须使用 Repo Wiki 专用终端；
- 终端执行后应提示用户关闭，或在可行时主动 dispose；
- 不得自动执行 `env`、`printenv`、`echo $KEY` 等可能泄露密钥的命令；
- 未受信任工作区中应禁用自动执行命令，并对写入 SecretStorage 做明确提示。

### 7.3 日志与诊断脱敏

- 所有错误消息在展示前必须经过 secret redaction 或只显示结构化 reason code。
- 诊断只显示 `api_key_env` 与 key 是否存在，不显示 key 值。
- 安全回归测试必须包含测试 key 哨兵字符串，并验证它未出现在 settings/YAML/log/webview/manifest/snapshots 中。

---

## 8. 兼容性要求

- 未配置新 LLM settings 时，现有侧栏 YAML 摘要展示保持可用。
- `repoWikiBrowser.generateCommand` 继续作为用户可覆盖的命令入口。
- Python CLI、`repo-wiki.yaml`、用户 shell 环境变量仍可独立使用。
- Cursor 兼容性必须通过实际冒烟验证，至少覆盖 SecretStorage、QuickInput、Webview、Terminal env 注入。

---

## 9. 验收矩阵

| 类别 | 验收项 | 证据 |
| --- | --- | --- |
| 配置 | settings 存在 provider/model/baseUrl/apiKeyEnv/source | package manifest 或插件测试 |
| 密钥 | SecretStorage 可 set/get/clear | 单元测试或手工记录 |
| 注入 | Update Wiki 注入 `LLM_*` 与 `[apiKeyEnv]` | 插件测试或 e2e 记录 |
| 安全 | key 不出现在 settings/YAML/命令/log/webview/manifest/snapshot | 安全扫描测试 |
| 诊断 | `repo-wiki config --ci` 结果可在 UI 中 redacted 展示 | 插件测试或手工记录 |
| 兼容 | 未配置新 settings 时旧行为不破坏 | 回归测试 |
| Cursor | Cursor 中 SecretStorage 与 terminal env 冒烟通过 | 手工验证记录 |

---

## 10. Definition of Done

本能力达到 Done 需要满足：

1. 用户可在 VS Code/Cursor 插件中配置 provider、API base URL、模型名称、apiKeyEnv；
2. 用户可安全保存和清除 API Key；
3. Update Wiki 能把配置安全注入 Python CLI；
4. Test LLM Configuration 能返回 redacted 诊断；
5. 所有新增测试通过；
6. 安全扫描未发现测试 key 泄露；
7. 用户文档说明三种配置路径：插件、YAML、环境变量；
8. 发布说明明确插件不内置 Python CLI，仍依赖本地 `repo-wiki` 命令可用。
