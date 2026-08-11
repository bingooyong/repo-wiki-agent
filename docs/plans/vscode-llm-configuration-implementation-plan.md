# VS Code/Cursor LLM 配置实施计划

**状态：** Draft / ready for execution
**日期：** 2026-07-08
**对应规格：** `docs/specs/vscode-llm-configuration-spec.md`
**前置分析：** `docs/project-analysis.md`、`docs/repo-agent-next-tasks-and-vscode-llm-config-plan.md`

---

## 1. 实施原则

1. **插件负责 UX，Python CLI 负责生成。** 插件不直接调用 LLM HTTP API，不复制 provider 实现。
2. **安全默认值优先。** 真实 API Key 只进入 SecretStorage 与运行时 env，不进入仓库文件、命令文本或日志。
3. **最小兼容改动。** 保留 `repoWikiBrowser.generateCommand` 和现有 YAML 摘要展示。
4. **分阶段可发布。** 每个阶段都要有独立验收、回滚策略和安全检查。
5. **先 MVP 后增强。** 先完成 settings + SecretStorage + env 注入，再做 YAML 写回、多 provider 预设和更复杂 UI。

---

## 2. 分阶段路线图

### Phase 0：基线锁定与安全检查清单

**目标：** 把当前事实、配置契约和安全边界固化为实现前门禁。

**任务：**

1. 确认 `extensions/repo-wiki-browser/package.json` 当前只有 `repoWikiBrowser.generateCommand` 配置。
2. 确认 `extensions/repo-wiki-browser/src/extension.ts` 当前只读取 YAML LLM 摘要。
3. 确认 Python 侧 `repo_wiki/llm/config.py` 支持 `LLM_PROVIDER`、`LLM_MODEL`、`LLM_BASE_URL`、`LLM_API_KEY_ENV`。
4. 确认 CLI 诊断入口为 `repo-wiki config --ci`。
5. 建立安全审查清单：真实 key 不得进入 settings/YAML/命令/log/webview/manifest/snapshot。

**交付物：**

- 本 spec 与 plan；
- PR 模板或 issue checklist 中的安全门禁项。

**验收：**

- 文档明确 API Key 只允许存入 SecretStorage；
- 后续 PR 可直接引用安全检查清单。

---

### Phase 1：配置 schema 与 SecretStorage MVP

**目标：** 用户能在插件中保存非敏感 LLM 配置，并安全保存/清除 API Key。

**写域：**

- `extensions/repo-wiki-browser/package.json`
- `extensions/repo-wiki-browser/src/extension.ts`
- `extensions/repo-wiki-browser/README.md`
- 相关测试文件

**任务：**

1. 在 `package.json` 增加配置项：
   - `repoWikiBrowser.llm.provider`
   - `repoWikiBrowser.llm.model`
   - `repoWikiBrowser.llm.baseUrl`
   - `repoWikiBrowser.llm.apiKeyEnv`
   - `repoWikiBrowser.llm.source`
2. 增加命令 contribution 与 activationEvents：
   - `repoWikiBrowser.configureLlm`
   - `repoWikiBrowser.setApiKey`
   - `repoWikiBrowser.clearApiKey`
3. 在 extension 中实现 SecretStorage helper：
   - `getApiKey(context)`
   - `setApiKey(context, value)`
   - `clearApiKey(context)`
   - `hasApiKey(context)`
4. 实现 `apiKeyEnv` 校验：`^[A-Za-z_][A-Za-z0-9_]*$`。
5. 更新侧栏 LLM 面板，展示 provider/model/baseUrl/apiKeyEnv/key-present。
6. 更新 README，说明真实 key 不进入 settings/YAML。

**测试：**

- 单元测试：apiKeyEnv 合法/非法校验。
- 单元或集成测试：SecretStorage set/clear 后 key-present 状态变化。
- 静态扫描：settings schema 中不存在 `repoWikiBrowser.llm.apiKey`。

**验收：**

- 用户能配置 provider/model/baseUrl/apiKeyEnv；
- 用户能保存和清除 API Key；
- UI 不展示真实 key；
- settings 中不包含真实 key。

**回滚策略：**

- 移除新增 commands 与 settings；
- SecretStorage 中遗留 key 不影响旧功能，可提供清理命令或说明。

---

### Phase 2：Update Wiki env 注入

**目标：** 点击 Update Wiki 时，插件把 LLM 配置按 Python CLI 契约注入运行环境。

**写域：**

- `extensions/repo-wiki-browser/src/extension.ts`
- 插件测试文件

**任务：**

1. 扩展 `runTerminalCommand(name, command)` 为支持 `env` 参数。
2. 新增 `buildLlmEnv(context, workspaceRoot)`：
   - 读取 settings；
   - 校验 `apiKeyEnv`；
   - 从 SecretStorage 读取真实 key；
   - 按 source 策略决定是否注入；
   - 空 provider/model/baseUrl 不注入，避免覆盖用户环境。
3. 修改 `runUpdateWiki()`：
   - 使用专用终端名，例如 `Repo Wiki Generate`；
   - `createTerminal({ name, cwd, env })` 注入 env；
   - 命令文本保持原 `generateCommand`，不拼接密钥或 LLM 参数。
4. 对未受信任工作区禁用自动执行或提示用户确认。
5. 在终端执行后提示用户关闭专用终端，降低密钥 env 驻留时间。

**测试：**

- `buildLlmEnv` 输出包含 `LLM_PROVIDER`、`LLM_MODEL`、`LLM_BASE_URL`、`LLM_API_KEY_ENV` 与 `[apiKeyEnv]`。
- 空值不注入。
- source 为 `environment` 时不注入覆盖项。
- 非法 `apiKeyEnv` 阻止运行并提示错误。
- 命令文本不包含测试 key。

**验收：**

- Python CLI 可通过 `resolve_llm_config()` 读取插件注入的配置；
- 终端命令文本、日志、UI 不包含真实 key；
- 现有 `generateCommand` 自定义行为保持兼容。

**回滚策略：**

- 保留 settings 与 SecretStorage；
- 暂时恢复旧的 `createTerminal({ name, cwd })` 路径；
- 用户仍可手动设置 shell 环境变量运行。

---

### Phase 3：诊断 UI 与 redacted 输出

**目标：** 用户能在插件中测试配置，获得安全的诊断结果。

**写域：**

- `extensions/repo-wiki-browser/src/extension.ts`
- `extensions/repo-wiki-browser/package.json`
- 插件测试文件
- README / docs

**任务：**

1. 增加 `repoWikiBrowser.testLlmConfig` 命令。
2. 使用与 Phase 2 相同的 `buildLlmEnv()`。
3. 优先通过非交互式进程执行：
   - `repo-wiki config --ci`
   - 或用户配置的 CLI 包装命令的诊断等价路径。
   - 注意：`repo-wiki config --ci` 在配置 FAIL 时可能先输出 JSON 再以非零码退出；插件必须安全捕获 stdout/stderr，redaction 后再展示，不得因为非零退出丢弃可用诊断。
4. 解析 JSON 诊断输出，展示：
   - summary；
   - provider；
   - model；
   - base_url；
   - api_key_env；
   - api_key_present；
   - issues / reason codes。
5. 对输出做二次 redaction，防止异常堆栈中包含 secret。
6. 侧栏显示最近一次诊断状态。

**测试：**

- mock `repo-wiki config --ci` PASS/WARN/FAIL 输出。
- 诊断面板不包含测试 key。
- CLI 不存在时给出可操作提示，不误判为 provider 配置失败。

**验收：**

- 用户能运行 Test LLM Configuration；
- 诊断结果可读且不泄露真实 key；
- CLI 缺失、key 缺失、base URL 无效、provider/model 缺失等场景有明确提示。

**回滚策略：**

- 保留配置和 Update Wiki；
- 隐藏 Test 命令或降级为说明用户手动执行 `repo-wiki config --ci`。

---

### Phase 4：YAML 导入/写回协同

**目标：** 兼容偏好仓库配置的团队工作流，同时保证真实 key 不落盘。

**写域：**

- `extensions/repo-wiki-browser/src/extension.ts`
- `extensions/repo-wiki-browser/package.json`
- README / docs
- 插件测试文件

**任务：**

1. 增加 `repoWikiBrowser.importLlmFromYaml`：
   - 读取 `repo-wiki.yaml` / `.repo-wiki.yaml`；
   - 导入 provider/model/base_url/api_key_env 到 settings；
   - 不读取或导入真实 key。
2. 增加 `repoWikiBrowser.writeLlmToYaml`：
   - 只写非敏感字段；
   - 不写 API Key；
   - 写回前展示 diff 或提示；
   - 若不能保留注释，明确提示用户。
3. 保守 merge `llm` 字段，不覆盖其他配置段。
4. 增加 YAML 中误放 key 的检测提示；默认不自动删除，避免破坏用户文件。

**测试：**

- 导入 YAML 成功。
- 写回只改变 `llm.provider/model/base_url/api_key_env`。
- 测试 key 不被写入 YAML。
- YAML parse error 有清晰提示。

**验收：**

- 团队可把非敏感 provider/model/base_url/api_key_env 固化到仓库；
- 真实 key 仍只在 SecretStorage 或用户 shell 环境中；
- YAML 写回不破坏无关配置。

**回滚策略：**

- 禁用写回命令，仅保留导入；
- 用户可继续手动编辑 YAML。

---

### Phase 5：多 provider 体验、Cursor 验证与发布门禁

**目标：** 完成生产可发布体验，覆盖主流 provider 和 Cursor 兼容性。

**任务：**

1. Provider 预设：
   - OpenAI-compatible；
   - Minimax；
   - Anthropic-compatible；
   - Custom。
2. 为不同 provider 提供 base URL 提示，但不强制写死。
3. Cursor 冒烟测试：
   - SecretStorage；
   - QuickInput；
   - Webview；
   - Terminal env 注入；
   - 诊断命令。
4. 发布前安全门禁：
   - 扫描测试 key；
   - 检查 settings/YAML/log/webview/manifest/snapshot；
   - 检查 README 示例没有真实 key 形态。
5. 更新插件 README、CHANGELOG、marketplace 描述。

**验收：**

- VS Code 与 Cursor 均可完成配置、测试、更新 Wiki；
- 安全回归测试通过；
- 发布说明包含配置与故障排除。

---

## 3. 推荐任务拆分

### PR-A：配置 schema 与 key 管理

**范围：** Phase 1
**建议提交内容：**

- package.json 新增 settings 和 commands；
- extension.ts 新增 SecretStorage helper 与命令处理；
- 侧栏显示 key-present；
- README 更新；
- 基础测试。

**Definition of Done：**

- 能保存/清除 key；
- settings 不含真实 key；
- 现有 open/refresh/update/verify/sync 命令不回归。

### PR-B：Update Wiki env 注入

**范围：** Phase 2
**建议提交内容：**

- `buildLlmEnv()`；
- `runTerminalCommand()` 支持 env；
- `runUpdateWiki()` 注入 LLM env；
- env 注入测试；
- 安全扫描测试。

**Definition of Done：**

- 命令文本不包含真实 key；
- CLI 可读取 env 覆盖；
- 非法 apiKeyEnv 阻止执行。

### PR-C：诊断体验

**范围：** Phase 3
**建议提交内容：**

- Test LLM Configuration 命令；
- 非交互式诊断执行；
- redacted diagnostics UI；
- CLI 缺失与配置错误提示；
- README 故障排除。

**Definition of Done：**

- PASS/WARN/FAIL 均能展示；
- 诊断输出不泄露 key；
- 用户能根据提示修复配置。

### PR-D：YAML 协同

**范围：** Phase 4
**建议提交内容：**

- YAML 导入命令；
- 非敏感 YAML 写回命令；
- YAML 安全扫描；
- 文档更新。

**Definition of Done：**

- YAML 只保存 provider/model/base_url/api_key_env；
- 不保存真实 key；
- parse/merge 错误可恢复。

### PR-E：发布硬化

**范围：** Phase 5
**建议提交内容：**

- provider presets；
- Cursor 验证记录；
- 安全门禁脚本或测试；
- CHANGELOG / marketplace 文案。

**Definition of Done：**

- VS Code 与 Cursor 冒烟通过；
- 安全门禁通过；
- 发布文档完整。

---

## 4. 测试策略

### 4.1 单元测试

- `apiKeyEnv` 校验；
- settings 解析；
- SecretStorage helper；
- `buildLlmEnv()` 空值、非法值、source 策略；
- redaction helper；
- YAML import/write model。

### 4.2 插件集成测试

- 命令注册存在；
- Configure/Set/Clear/Test 命令可执行；
- 侧栏状态正确渲染；
- Update Wiki 创建终端时传入 env。

### 4.3 CLI 契约测试

在 Python 侧或端到端测试中验证：

```bash
LLM_PROVIDER=openai \
LLM_MODEL=gpt-4o-mini \
LLM_BASE_URL=https://api.example.com/v1 \
LLM_API_KEY_ENV=REPO_WIKI_LLM_API_KEY \
REPO_WIKI_LLM_API_KEY=test-sentinel-value \
uv run repo-wiki config --ci
```

期望：

- 诊断知道 key present；
- 输出不包含 `test-sentinel-value`；
- provider/model/base_url/api_key_env 与注入一致。

### 4.4 安全回归测试

使用固定测试哨兵：

```text
repo-wiki-test-key-sentinel-should-never-leak
```

扫描范围：

- settings JSON mock；
- YAML 输出；
- output channel mock；
- webview HTML；
- manifest fixtures；
- test snapshots；
- README 示例。

任一命中即失败。

### 4.5 手工冒烟

VS Code：

1. 安装插件开发版；
2. 配置 provider/model/baseUrl；
3. Set API Key；
4. Test LLM Configuration；
5. Update Wiki；
6. 刷新侧栏；
7. Clear API Key。

Cursor：重复以上流程，并记录差异。

---

## 5. 发布门禁

发布前必须满足：

- TypeScript 编译通过；
- 插件测试通过；
- Python CLI 诊断契约测试通过；
- 安全扫描无 key 泄露；
- VS Code 冒烟通过；
- Cursor 冒烟通过或记录明确限制；
- README / CHANGELOG / marketplace 描述更新；
- 回滚路径明确。

---

## 6. 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| SecretStorage 在 Cursor 中行为差异 | 用户无法保存 key | Phase 5 做 Cursor 冒烟；失败时文档说明使用环境变量。 |
| 终端 env 长时间驻留 | 本机进程可能读取 key | 使用专用/可丢弃终端；提示关闭；诊断优先非交互式进程。 |
| YAML 写回破坏格式 | 用户配置受损 | 初期优先导入；写回前提示；保守 merge；保留备份。 |
| 用户自定义 generateCommand 不兼容诊断 | Test 命令无法找到 CLI | 诊断路径可配置或提示用户手动运行 `repo-wiki config --ci`。 |
| provider/base URL 差异 | 配置失败 | 提供 provider presets 与诊断 reason code。 |
| 密钥泄露到测试快照 | 安全事故 | 引入 sentinel 扫描作为 CI 门禁。 |

---

## 7. 里程碑建议

| 周期 | 目标 | 产出 |
| --- | --- | --- |
| M1 | Phase 1 | settings + SecretStorage + key-present UI |
| M2 | Phase 2 | Update Wiki env 注入 |
| M3 | Phase 3 | Test LLM Configuration |
| M4 | Phase 4 | YAML 导入/写回 |
| M5 | Phase 5 | provider presets + Cursor 验证 + 发布文档 |

---

## 8. 实施顺序建议

1. 从 PR-A 开始，不触碰 Python CLI；
2. PR-B 打通插件到 CLI 的环境变量契约；
3. PR-C 增加诊断，降低用户配置错误；
4. PR-D 处理团队 YAML 协作；
5. PR-E 做 provider presets、Cursor 验证和发布硬化。

如果资源有限，MVP 可只发布 PR-A + PR-B + 基础文档；但不得省略 SecretStorage 与 key 不落盘安全要求。
