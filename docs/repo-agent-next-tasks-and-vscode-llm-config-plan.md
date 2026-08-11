# repo-agent 后续任务与 VS Code/Cursor LLM 配置规划

## 目标

为 `repo-agent` / `repo-wiki` 下一阶段迭代建立可执行规划，重点补齐 VS Code/Cursor 插件的大模型配置能力：配置 LLM provider、API `base_url`、模型名称与 API Key，并安全传递给 Python CLI。

本规划以当前源码为事实基线：Python CLI 是核心生成器，VS Code/Cursor 插件 `Repo Wiki Browser` 当前主要负责浏览 READY release manifest、展示少量 LLM 摘要，并通过集成终端触发命令。

## 现状差距

1. **插件配置项不足**
   - `extensions/repo-wiki-browser/package.json` 当前只贡献了一个配置：`repoWikiBrowser.generateCommand`。
   - 该配置只控制 Update Wiki 发送到集成终端的 shell 命令，尚未提供 provider、model、base_url、API Key 或 api_key_env 的 UI/设置项。

2. **插件只展示 LLM 摘要，不管理 LLM 配置**
   - `extensions/repo-wiki-browser/src/extension.ts` 当前通过 `loadLlmDisplayInfo()` 仅读取工作区 `repo-wiki.yaml` / `.repo-wiki.yaml` 的 `llm` 段摘要。
   - 展示字段主要是 `provider`、`model_update`、`model_init`、`model_verify`、`model`，用于侧栏提示。
   - 插件没有读取、写入或安全保存真实 API Key，也没有把 LLM 配置组装为 CLI 环境变量。

3. **Python 侧已有配置基础，插件尚未对齐**
   - `repo_wiki/core/config.py` 的 `LlmConfig` 已包含 `provider`、`model`、`base_url`、`api_key_env`，并支持从 `repo-wiki.yaml` 加载。
   - `repo_wiki/llm/config.py` 的 `LLMProviderConfig` 同样支持 `provider`、`model`、`base_url`、`api_key_env`，并支持环境变量覆盖：`LLM_PROVIDER`、`LLM_MODEL`、`LLM_BASE_URL`、`LLM_API_KEY_ENV`。
   - `repo_wiki/llm/config.py` 通过 `get_api_key_from_env(api_key_env)` 读取真实 key，因此插件应传递“真实 key 所在环境变量名”和该变量的值，不把 key 写进 YAML 或命令文本。

4. **安全能力需要端到端闭环**
   - Python 侧已有一定 redaction 与 diagnostics 能力；`repo_wiki/llm/diagnostics.py` 输出诊断时会隐藏 `api_key_env` 并只展示 key 是否存在。
   - 但 VS Code/Cursor 插件端还没有 SecretStorage、日志脱敏、命令注入防护、设置迁移与故障诊断体验。

5. **用户路径不完整**
   - 项目分析指出插件当前更像“发布 Wiki 浏览器 + 终端命令触发器”，不是完整图形化生成器。
   - 用户若只会在 IDE 中操作，目前无法直接完成“选择 provider → 填 base_url → 保存 key → 选择模型 → 生成 Wiki”的闭环。

## 总体设计

采用“插件负责用户体验与密钥安全，Python CLI 继续作为执行内核”的设计。

```text
VS Code/Cursor UI
  ├─ 普通设置：provider / model / base_url / api_key_env / generateCommand
  ├─ SecretStorage：真实 API Key
  ├─ 状态面板：当前 provider/model/base_url/key-present/诊断结果
  └─ 命令入口：配置 LLM / 测试 LLM / Update Wiki
        │
        ▼
createTerminal({ env })
  ├─ LLM_PROVIDER=<provider>
  ├─ LLM_MODEL=<model>
  ├─ LLM_BASE_URL=<base_url>
  ├─ LLM_API_KEY_ENV=<secretEnvName>
  └─ <secretEnvName>=<actualKeyFromSecretStorage>
        │
        ▼
repo-wiki CLI
  ├─ resolve_llm_config()
  ├─ LLMProviderConfig(provider/model/base_url/api_key_env)
  ├─ get_api_key_from_env(api_key_env)
  └─ config diagnostics / generate / update / verify
```

设计原则：

- **密钥不落盘明文**：真实 API Key 只进入 VS Code SecretStorage 与运行时进程环境。
- **配置分层**：非敏感偏好可保存在 VS Code settings 或 `repo-wiki.yaml`；敏感 key 只保存在 SecretStorage。
- **Python 侧兼容优先**：优先使用现有 `LLM_*` 环境变量覆盖机制，不强迫重构 CLI。
- **终端行为透明**：继续通过专用/可丢弃集成终端执行 `repoWikiBrowser.generateCommand`，创建终端时注入 env；诊断/测试优先使用非交互式进程。
- **可诊断**：插件 UI 只展示 provider/model/base_url/key 是否存在，不显示真实 key。

## 配置模型

### 插件侧建议配置项

在 `package.json` 增加非敏感配置项：

| 配置项 | 类型 | 建议默认值 | 用途 | 是否敏感 |
| --- | --- | --- | --- | --- |
| `repoWikiBrowser.generateCommand` | string | 现状默认值 | Update Wiki 终端命令 | 否 |
| `repoWikiBrowser.llm.provider` | string | 空（不覆盖 CLI/YAML 默认） | LLM provider | 否 |
| `repoWikiBrowser.llm.model` | string | 空 | 通用模型名，映射 `LLM_MODEL` | 否 |
| `repoWikiBrowser.llm.baseUrl` | string | 空 | OpenAI-compatible API base URL，映射 `LLM_BASE_URL` | 否 |
| `repoWikiBrowser.llm.apiKeyEnv` | string | `REPO_WIKI_LLM_API_KEY` | 真实 key 注入到 CLI 时使用的环境变量名，映射 `LLM_API_KEY_ENV` | 否，但需校验格式 |
| `repoWikiBrowser.llm.source` | enum | `extension` | 选择使用插件配置、工作区 YAML 或环境变量优先 | 否 |

不建议新增 `repoWikiBrowser.llm.apiKey` setting；真实 key 不应写入 settings、YAML、命令文本、日志或 manifest。

### SecretStorage 键设计

建议使用稳定 secret key 命名：

```text
repoWikiBrowser.llm.apiKey.<workspaceHash>.<provider>
```

或在初期简化为：

```text
repoWikiBrowser.llm.apiKey
```

取舍：

- 简化键便于实现，但多工作区/多 provider 切换时可能覆盖。
- 带 workspace/provider 的键更安全清晰，但需要迁移和清理命令。

### CLI 环境变量映射

运行生成类命令时通过 `vscode.window.createTerminal({ env })` 注入。`createTerminal({ env })` 创建的是交互式终端，注入的环境变量会在该终端会话内持续存在；因此应使用专用、短生命周期、可丢弃的终端，不通过 `echo`、`env` dump 或命令文本暴露配置。诊断/测试命令如无需用户交互，优先使用非交互式进程。

```ts
const env = {
  LLM_PROVIDER: provider,
  LLM_MODEL: model,
  LLM_BASE_URL: baseUrl,
  LLM_API_KEY_ENV: apiKeyEnv,
  [apiKeyEnv]: actualApiKeyFromSecretStorage,
};

const terminal = vscode.window.createTerminal({
  name: 'Repo Wiki Generate',
  cwd: workspaceRoot,
  env,
});
```

注意：

- `LLM_API_KEY_ENV` 的值是环境变量名，例如 `REPO_WIKI_LLM_API_KEY`。
- `[apiKeyEnv]` 的值才是真实 API Key，只来自 SecretStorage。
- 若某项为空，不应注入空字符串覆盖用户已有环境；应跳过该项。
- `apiKeyEnv` 必须校验为合法环境变量名，例如 `^[A-Za-z_][A-Za-z0-9_]*$`。
- 终端应命名为 Repo Wiki 专用终端，执行后提示用户关闭或主动 dispose，避免密钥环境在长期复用终端中停留。

### 与 `repo-wiki.yaml` 的关系

`repo-wiki.yaml` 可继续保存非敏感 LLM 配置：

```yaml
llm:
  provider: openai
  model: gpt-4o-mini
  base_url: https://api.example.com/v1
  api_key_env: REPO_WIKI_LLM_API_KEY
```

但不保存真实 key。插件后续可支持三种模式：

1. **YAML-only**：只展示 YAML 摘要，沿用当前行为。
2. **Extension override**：用插件 settings + SecretStorage 注入环境变量覆盖 YAML。
3. **Environment-first**：尊重用户 shell 环境，不由插件注入密钥。

## 安全策略

1. **Key 存储**
   - 必须使用 VS Code SecretStorage 保存真实 API Key。
   - 禁止把真实 key 写入 VS Code settings、`repo-wiki.yaml`、`.repo-wiki.yaml`、命令字符串、日志、release manifest、诊断 JSON、README 示例或测试快照。

2. **Key 传递**
   - 只在执行 CLI 的专用/可丢弃终端或非交互式子进程中注入；若使用 `createTerminal({ env })`，需视为该终端会话内持续可见。
   - 注入变量包括 `LLM_PROVIDER`、`LLM_MODEL`、`LLM_BASE_URL`、`LLM_API_KEY_ENV` 与 `LLM_API_KEY_ENV` 指向的真实 key 环境变量。

3. **展示与日志**
   - UI 可展示 `Provider`、`Model`、`Base URL`、`API Key Present: Yes/No`。
   - UI 不展示真实 key；必要时最多展示尾号，例如 `••••abcd`，但默认建议不展示。
   - 所有错误提示、output channel、webview HTML、telemetry 事件都不得包含真实 key。

4. **命令注入防护**
   - `generateCommand` 继续允许用户自定义，但插件自动注入的 env 不应拼接到 shell 命令文本中。
   - provider/model/base_url 作为 env 传递，不插入命令行参数，降低 shell escaping 风险。

5. **诊断对齐**
   - 插件侧诊断应复用 Python 侧语义：展示 provider/model/base_url/api_key_env/key-present，不展示 key。
   - 当前 CLI 诊断入口是 `repo-wiki config`；源码已支持 `--ci` 输出机器可读 JSON，因此插件测试配置调用 `repo-wiki config --ci`。不要引用不存在的 `repo-wiki llm diagnostics` 命令。

6. **工作区信任**
   - 对未受信任工作区，应禁用自动执行命令与 SecretStorage 写入提示，只允许只读展示。

## 用户故事

1. **作为 VS Code/Cursor 用户，我想在插件中选择 provider 和模型**，以便无需手动编辑 YAML 就能切换 OpenAI-compatible、Minimax、Anthropic 或自定义 provider。

2. **作为使用私有网关的团队用户，我想配置 API base_url**，以便 repo-wiki 通过企业代理、私有模型服务或兼容 OpenAI API 的网关生成内容。

3. **作为安全敏感用户，我想 API Key 只保存在 IDE 密钥库**，以避免 key 出现在 settings、YAML、终端命令历史、日志或 manifest 中。

4. **作为新用户，我想点击“测试 LLM 配置”**，看到 provider/model/base_url/key 是否有效以及下一步修复建议。

5. **作为高级用户，我想继续使用 `repo-wiki.yaml` 和 shell 环境变量**，并让插件不要覆盖已有环境。

6. **作为 Cursor 用户，我希望插件配置行为与 VS Code 一致**，因为 Cursor 兼容 VS Code extension API，但仍需验证 SecretStorage 与 terminal env 行为。

## 分阶段任务 P0-P5

### P0：事实基线与安全边界确认

- 确认插件当前仅有 `repoWikiBrowser.generateCommand` 配置项。
- 确认插件当前只读取 `repo-wiki.yaml` 的 llm 摘要并显示 provider/model 系列信息。
- 确认 Python 侧配置链路支持 `provider/model/base_url/api_key_env`。
- 明确真实 API Key 的唯一允许存储位置：VS Code SecretStorage。
- 输出安全约束清单，作为后续 PR 审查门槛。

验收：文档、issue 或设计记录中明确“key 不得进入 settings/YAML/命令/log/manifest”。

### P1：插件配置 schema 与 SecretStorage 基础

- 在 `package.json` 增加非敏感 LLM 配置项：provider、model、baseUrl、apiKeyEnv、source。
- 在 extension 中增加命令：
  - `Repo Wiki: Configure LLM Provider`
  - `Repo Wiki: Set API Key`
  - `Repo Wiki: Clear API Key`
- 使用 SecretStorage 保存、读取、删除真实 key。
- 增加 apiKeyEnv 格式校验与错误提示。

验收：能保存/清除 key；settings 中没有真实 key；无日志泄露。

### P2：终端 env 注入与 Update Wiki 对齐

- 扩展 `runTerminalCommand()`，支持可选 env 参数。
- `runUpdateWiki()` 在执行 `generateCommand` 时组装 LLM env。
- 注入 `LLM_PROVIDER`、`LLM_MODEL`、`LLM_BASE_URL`、`LLM_API_KEY_ENV` 和真实 key 对应 env var。
- 空值不覆盖已有环境；用户选择 Environment-first 时不注入。

验收：Python CLI 能通过现有 `resolve_llm_config()` 读取插件注入的配置；终端命令文本不包含真实 key。

### P3：侧栏 UI 与诊断体验

- 将当前 LLM 摘要面板升级为“配置来源 + provider + model + base_url + key-present + 诊断入口”。
- 显示配置优先级：Extension override / YAML / Environment。
- 增加“测试配置”命令，执行轻量诊断或 dry-run。
- 将 Python diagnostics 的 redacted 输出映射到 VS Code notification / webview 面板。

验收：用户能在侧栏判断当前配置是否可用，且看不到真实 key。

### P4：YAML 同步与迁移

- 增加“写入非敏感配置到 repo-wiki.yaml”命令，只写 provider/model/base_url/api_key_env。
- 不写真实 key。
- 对已有 YAML 的 llm 字段做保守 merge，避免覆盖用户注释以外的重要配置；如无法保留注释，需提示用户。
- 增加从 YAML 读取到插件 settings 的导入命令。

验收：YAML 中只出现 env var 名，不出现真实 key；导入/导出不会破坏其他配置字段。

### P5：多 provider、测试与发布质量

- 补齐 OpenAI-compatible、Minimax、Anthropic、自定义 base_url 的端到端测试矩阵。
- 验证 VS Code 与 Cursor 的 SecretStorage、createTerminal env 行为。
- 增加安全回归测试：settings、YAML、日志、webview、manifest 中不得出现测试 key。
- 更新用户文档、README、插件 marketplace 描述与故障排除。

验收：测试覆盖主要 provider 路径；发布说明包含安全配置指南。

## 近期 Task Pack A/B/C

### Task Pack A：最小安全配置闭环

目标：让用户安全保存 key，并在插件 UI 中看到当前配置状态。

任务：

1. 扩展插件 configuration schema，新增 provider/model/baseUrl/apiKeyEnv/source。
2. 实现 SecretStorage helper：`getApiKey()`、`setApiKey()`、`clearApiKey()`、`hasApiKey()`。
3. 增加命令 `Set API Key` / `Clear API Key`，并在 `extensions/repo-wiki-browser/package.json` 同时补齐 `activationEvents` 与 `contributes.commands`。
4. 侧栏 LLM 面板显示：Provider、Model、Base URL、API Key Present。
5. 加入 key 不落盘的手工验证步骤。

交付物：插件代码、单元测试或手工测试记录、文档片段。

### Task Pack B：运行 CLI 时注入 LLM 环境

目标：让 Update Wiki 能使用插件配置的大模型参数。

任务：

1. 修改终端创建逻辑为 `createTerminal({ name, cwd, env })`，使用专用/可丢弃终端。
2. 从 settings 与 SecretStorage 组装 env。
3. 注入 `LLM_PROVIDER`、`LLM_MODEL`、`LLM_BASE_URL`、`LLM_API_KEY_ENV`。
4. 使用 `apiKeyEnv` 指定的变量名注入真实 key。
5. 确保命令文本、日志和 UI 不包含真实 key。
6. 用 Python 侧 `resolve_llm_config()` 路径验证环境变量覆盖生效。

交付物：插件代码、端到端验证记录、安全检查结果。

### Task Pack C：诊断与 YAML 协同

目标：降低用户配置错误成本，并兼容现有 YAML 工作流。

任务：

1. 增加“Test LLM Configuration”命令，并在 `package.json` 同时加入 `activationEvents` 与 `contributes.commands`。
2. 调用当前 CLI 入口 `repo-wiki config --ci`（JSON 输出已支持）或等价非交互式进程，设计 redacted diagnostics 面板，展示 provider/model/base_url/api_key_env/key-present/issues。
3. 增加从 `repo-wiki.yaml` 导入非敏感 LLM 配置的命令。
4. 增加写回非敏感 LLM 配置到 YAML 的命令，禁止写真实 key。
5. 补充用户文档：插件配置、YAML 配置、环境变量配置三种路径。

交付物：诊断 UI、YAML 导入/导出能力、用户文档。

## 验收清单

### 功能验收

- [ ] 插件 settings 中有 provider/model/baseUrl/apiKeyEnv/source 等非敏感配置项。
- [ ] 插件只通过 SecretStorage 保存真实 API Key。
- [ ] Update Wiki 通过专用/可丢弃的 `createTerminal({ env })` 注入 LLM 环境变量，且不通过 echo/env-dump 暴露。
- [ ] 注入变量包含 `LLM_PROVIDER`、`LLM_MODEL`、`LLM_BASE_URL`、`LLM_API_KEY_ENV` 和真实 key 对应 env var。
- [ ] Python CLI 能读取插件注入的 env 并覆盖 YAML 默认值。
- [ ] 侧栏能展示 provider/model/base_url/key-present 与配置来源。
- [ ] 用户可清除 API Key。

### 安全验收

- [ ] settings JSON 不包含真实 key。
- [ ] `repo-wiki.yaml` / `.repo-wiki.yaml` 不包含真实 key。
- [ ] 终端命令文本不包含真实 key；诊断/测试优先使用非交互式进程或短生命周期专用终端。
- [ ] output channel、console、diagnostics、webview HTML 不包含真实 key。
- [ ] release manifest 不包含真实 key。
- [ ] 测试快照不包含真实 key。
- [ ] `apiKeyEnv` 通过合法环境变量名校验。

### 兼容验收

- [ ] 未配置插件 LLM 时，保持现有 `repo-wiki.yaml` 摘要展示行为。
- [ ] 现有 `repoWikiBrowser.generateCommand` 行为不破坏。
- [ ] 用户已有 shell 环境变量可继续生效。
- [ ] VS Code 与 Cursor 中 SecretStorage、terminal env 行为均通过验证。

## 风险

1. **SecretStorage 与 Cursor 兼容性差异**
   - Cursor 通常兼容 VS Code API，但仍需实际验证 SecretStorage 与 terminal env 注入行为。

2. **集成终端环境变量可见性**
   - `createTerminal({ env })` 比命令拼接安全，但变量会在该交互式终端会话内保留，且子进程环境仍可能被本机调试工具或恶意脚本读取。应使用专用/可丢弃终端，避免 echo/env-dump，并提醒用户只在可信工作区执行。

3. **配置优先级混乱**
   - YAML、settings、环境变量、CLI overrides 并存时容易让用户困惑。需要明确 UI 显示“当前来源”和“最终值”。

4. **base_url 误配置**
   - 不同 provider 的路径要求不同，例如 OpenAI-compatible 常见 `/v1`。诊断应给出 provider-specific 提示。

5. **历史文档事实陈旧**
   - `docs/project-analysis.md` 已指出部分生成文档与当前 Python CLI + TS 插件现实不一致。后续实施应继续以源码、包配置和 CLI 行为为准。

6. **YAML 写回破坏用户格式**
   - 若使用普通 YAML dump，可能丢失注释和格式。初期可只做导入，不急于自动写回；写回前需提示。

## 下一步建议

1. 实施 **Task Pack A**：安全保存 API Key，补齐非敏感配置 schema。
2. 实施 **Task Pack B**：打通专用 `createTerminal({ env })` 到 Python CLI；诊断/测试优先使用非交互式 `repo-wiki config --ci`。
3. 实施 **Task Pack C**：补齐诊断、YAML 协同和用户文档。
4. 每个 PR 加入安全检查：搜索测试 key，检查 settings/YAML/log/webview/manifest 不含真实 key。
5. 对外文档中明确推荐配置方式：
   - provider/model/base_url/api_key_env 可写 settings 或 YAML；
   - 真实 API Key 只存 SecretStorage；
   - 运行 CLI 时由插件注入 `LLM_PROVIDER`、`LLM_MODEL`、`LLM_BASE_URL`、`LLM_API_KEY_ENV` 和真实 key 对应 env var。
