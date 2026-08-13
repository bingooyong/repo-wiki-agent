# VS Code 插件 LLM 配置：UI 主路径与终端后备

**状态：** 与本仓扩展源码对齐。插件 UI + SecretStorage 为推荐路径；本文保留 YAML/env 供 CI、纯终端、旧 VSIX。
**日期：** 2026-07-08
**适用对象：** 使用 `Repo Wiki Browser` VS Code/Cursor 插件触发 `repo-wiki` CLI 生成 Wiki 的用户
**完整 CLI 配置参考：** `docs/configuration.md`
**后续插件可视化配置规格：** `docs/specs/vscode-llm-configuration-spec.md`

---

## 1. 先说结论

本仓 `extensions/repo-wiki-browser` **已经支持**在插件 UI 中配置 LLM（Configure / Set Key / Clear / Test）。Key 进入 SecretStorage。真正调用 LLM 的仍是 `repo-wiki` CLI。
UI 逐步说明见 `extensions/repo-wiki-browser/README.md` 的 LLM configuration 一节。
在没有插件、CI、或只想用终端时，继续用下面的 YAML + 环境变量。旧 VSIX 若看不到这些命令，从本仓重新 `vsce package`。

---

## 2. 当前插件能力边界

| 能力 | 当前状态 | 说明 |
| --- | --- | --- |
| 插件 UI 配置 provider | 已支持（源码） | Configure LLM Settings。 |
| 插件 UI 配置 model | 已支持（源码） | Configure LLM Settings。 |
| 插件 UI 配置 base_url | 已支持（源码） | Configure LLM Settings。 |
| 插件 SecretStorage 保存 API Key | 已支持（源码） | Set / Clear LLM API Key。不要把 key 写入 VS Code settings。 |
| 插件自动注入 `LLM_*` env | 已支持（源码） | Update Wiki 按 source 策略注入非空 `LLM_*`。 |
| 展示 YAML 中 LLM 摘要 | 已支持 | 只展示 provider/model 等摘要，不管理 key。 |
| 自定义生成命令 | 已支持 | 设置项：`repoWikiBrowser.generateCommand`。 |

---

## 3. 推荐安全配置方式

无插件 UI 时用本节。有插件时优先 SecretStorage，不要把 key 写入 YAML。

### 3.1 在目标仓库写入非敏感 YAML

在目标代码仓库根目录创建 `repo-wiki.yaml`：

```yaml
llm:
  provider: openai
  model: gpt-4o-mini
  base_url: https://api.example.com/v1
  api_key_env: REPO_WIKI_LLM_API_KEY
  max_tokens: 4096
  temperature: 0.7
  timeout: 60.0
  max_retries: 3
```

注意：

- `api_key_env` 是环境变量名，不是 API Key 本身。
- 真实 API Key 不得写入 `repo-wiki.yaml`。
- `base_url` 仅用于 OpenAI-compatible / 私有网关 / 代理场景；如果 provider 默认地址可用，可以省略。

### 3.2 不使用 YAML：纯环境变量配置

如果你不想在仓库中创建 `repo-wiki.yaml`，也可以只在 VS Code 集成终端或 shell profile 中设置 `LLM_*` 环境变量：

```bash
export LLM_PROVIDER="openai"
export LLM_MODEL="gpt-4o-mini"
export LLM_BASE_URL="https://api.example.com/v1"
export LLM_API_KEY_ENV="REPO_WIKI_LLM_API_KEY"
export REPO_WIKI_LLM_API_KEY="<your-api-key>"

uv run repo-wiki config --ci
uv run repo-wiki generate --profile qoder-like --output .repo-agent-eval
```

这种方式适合临时调试或不希望在仓库留下任何 LLM 偏好配置的场景。缺点是团队成员无法从仓库配置中看到推荐 provider/model/base_url。

### 3.3 设置真实 API Key

优先使用 **方式 A：当前终端临时环境变量**。这是当前插件尚未实现 SecretStorage 前最少落盘的方式。

方式 B 和方式 C 会把 key 持久化到本机磁盘（shell profile 或本地 `.env`），只适合你接受本机持久化风险、确认文件不会被同步或提交的场景。无论哪种方式，都不得把真实 key 写入仓库配置、VS Code settings、命令字符串、日志或提交文件。

#### 方式 A：当前 VS Code 集成终端中临时 export（首选）

适合临时测试和最小本机留痕：

```bash
export REPO_WIKI_LLM_API_KEY="<your-api-key>"
uv run repo-wiki config --ci
uv run repo-wiki generate --profile qoder-like --output .repo-agent-eval
```

如果你随后点击插件的 **Update Wiki**，注意插件会创建/使用集成终端执行命令；该终端必须能看到同一个环境变量。不同终端会话之间的临时 `export` 不一定共享。

#### 方式 B：写入 shell 启动文件（本机落盘，谨慎使用）

适合个人开发机长期使用，但会把 key 写入本机磁盘。仅在你接受本机持久化风险、确认该文件不会被同步或提交时使用，例如 zsh：

```bash
# ~/.zshrc 或你的 shell profile
export REPO_WIKI_LLM_API_KEY="<your-api-key>"
```

然后重启 VS Code 或新建集成终端，再验证：

```bash
echo "$REPO_WIKI_LLM_API_KEY" | sed 's/./*/g' | head -c 8; echo
uv run repo-wiki config --ci
```

不要把真实 key 提交进仓库。

#### 方式 C：本地未提交 `.env`（本机落盘，谨慎使用）

适合每个目标仓库使用不同 key，但会把 key 写入目标仓库工作区的本机文件。仅在 `.env` 已被 `.gitignore` 排除、且你接受本机持久化风险时使用。目标仓库根目录创建 `.env`：

```bash
REPO_WIKI_LLM_API_KEY=<your-api-key>
```

并确认 `.gitignore` 包含：

```gitignore
.env
.env.*
```

`repo-wiki` 配置加载路径会尝试读取目标仓库本地 `.env`。`.env` 只应留在本机，不应进入 git，也不应进入云同步/备份策略不受控的位置。

---

## 4. Provider 示例

### 4.1 OpenAI-compatible / 私有网关

`repo-wiki.yaml`：

```yaml
llm:
  provider: openai
  model: gpt-4o-mini
  base_url: https://api.example.com/v1
  api_key_env: REPO_WIKI_LLM_API_KEY
```

环境变量：

```bash
export REPO_WIKI_LLM_API_KEY="<your-api-key>"
```

### 4.2 Minimax

`repo-wiki.yaml`：

```yaml
llm:
  provider: minimax
  model: abab6-chat
  api_key_env: MINIMAX_API_KEY
```

环境变量：

```bash
export MINIMAX_API_KEY="<your-minimax-key>"
```

### 4.3 本地 Ollama / OpenAI-compatible local server

`repo-wiki.yaml`：

```yaml
llm:
  provider: openai
  model: llama3.3
  base_url: http://localhost:11434/v1
  api_key_env: OLLAMA_API_KEY
```

如果本地服务不需要 key，可以设置一个非敏感占位环境变量以通过 key-present 诊断，或使用项目后续支持的 no-key local mode：

```bash
export OLLAMA_API_KEY="local-dev-placeholder"
```

---

## 5. 诊断与生成命令

### 5.1 诊断 LLM 配置

推荐先运行：

```bash
uv run repo-wiki config --ci
```

说明：

- `summary` 为 `OK` 表示基础配置可用；
- `summary` 为 `FAIL` 时命令会以非零码退出，但仍会输出 JSON 诊断；
- 诊断只显示 key 是否存在，不应显示真实 key。

如果你需要人工阅读格式：

```bash
uv run repo-wiki config
```

### 5.2 生成 Wiki

```bash
uv run repo-wiki generate --profile qoder-like --output .repo-agent-eval
```

生成后执行验证与发布：

```bash
uv run repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval
uv run repo-wiki release-publish --output .repo-agent-eval
```

插件默认只读取：

```text
.repo-agent-eval/repowiki/zh/manifest.json
```

如果只生成 run 目录但未发布到 READY release，插件侧栏可能仍显示未检测到可浏览 Wiki。

---

## 6. 与 VS Code 插件配合

### 6.1 使用默认 Update Wiki

插件默认执行：

```bash
uv run repo-wiki generate --profile qoder-like
```

它不会自动配置 LLM。请确保 VS Code 集成终端能看到：

- `repo-wiki.yaml`；
- 真实 API Key 对应的环境变量；
- `uv` 和 `repo-wiki` 命令。

### 6.2 自定义生成命令

如果你的环境需要固定输出目录或完整链路，可以在 VS Code settings 中配置：

```json
{
  "repoWikiBrowser.generateCommand": "uv run repo-wiki generate --profile qoder-like --output .repo-agent-eval"
}
```

当前插件的 Update Wiki 只发送一条命令；若你希望同时 verify / release-publish，建议先在终端手动执行，或后续把命令封装成脚本：

```json
{
  "repoWikiBrowser.generateCommand": "./scripts/update-repo-wiki.sh"
}
```

脚本内部可以执行：

```bash
#!/usr/bin/env bash
set -euo pipefail
uv run repo-wiki config --ci
uv run repo-wiki generate --profile qoder-like --output .repo-agent-eval
uv run repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval
uv run repo-wiki release-publish --output .repo-agent-eval
```

不要在脚本里写真实 API Key；只读取环境变量。

---

## 7. 常见问题

### Q1：我在 YAML 里写了 provider/model，但插件 Update Wiki 仍然失败？

检查真实 API Key 环境变量是否在 VS Code 集成终端中可见：

```bash
uv run repo-wiki config --ci
```

如果诊断显示 key missing，说明 `api_key_env` 指向的变量没有设置。

### Q2：为什么插件不直接让我输入 API Key？

当前版本尚未实现 SecretStorage 配置 UI。后续实现应按照 `docs/specs/vscode-llm-configuration-spec.md`：真实 API Key 只进入 VS Code SecretStorage，并在运行 CLI 时通过环境变量注入。

### Q3：可以把 API Key 写进 `repo-wiki.yaml` 吗？

不可以。`repo-wiki.yaml` 只能写 `api_key_env`，真实 key 应放在本机环境变量、shell profile 或未提交 `.env`。

### Q4：我运行了 generate，但插件仍看不到 Wiki？

插件只读取 READY release：

```text
.repo-agent-eval/repowiki/zh/manifest.json
```

请确认你已经执行：

```bash
uv run repo-wiki release-publish --output .repo-agent-eval
```

并且 release manifest 的 readiness 状态为 READY。

---

## 8. 后续演进

当前人工配置路径是插件可视化 LLM 配置前的 P0 可用性保障。后续实现优先级：

1. 插件 settings 支持 provider/model/baseUrl/apiKeyEnv；
2. API Key 使用 VS Code SecretStorage；
3. Update Wiki 时注入 `LLM_PROVIDER`、`LLM_MODEL`、`LLM_BASE_URL`、`LLM_API_KEY_ENV` 与真实 key env；
4. 插件提供 `Test LLM Configuration`，调用 `repo-wiki config --ci`；
5. 侧栏展示配置来源与 key-present 状态。
