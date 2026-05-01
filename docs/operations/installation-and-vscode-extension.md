# Installation and VS Code Extension Guide

This guide covers installation procedures for repo-wiki and the VS Code extension.

---

## 中文：安装、生成 Wiki、安装插件与更新

下面按**实际使用顺序**说明：先分清名字，再装 CLI、配 LLM、生成目录、装插件浏览，最后如何更新。

### 名称区分

| 名称 | 含义 |
|------|------|
| **repo-agent** | GitHub 上的**源代码仓库**（本仓库），内含 Python 包、文档、`extensions/repo-wiki-browser` 插件源码等。 |
| **repo-wiki** | **命令行工具名**，也是 PyPI 包名（`pip install repo-wiki`，若已发布）。你在终端里输入的是 `repo-wiki …`。 |
| **Repo Wiki Browser** | **VS Code / Cursor 插件**，只负责侧栏浏览与把命令发到集成终端；**不包含** Python 与 `repo-wiki` 本体，需本机单独安装。 |

### 1. 安装 repo-wiki（CLI）

在你要用来跑 Wiki 的机器上：

**方式 A：从本仓库安装（开发 / 贡献者常用）**

```bash
git clone https://github.com/bingooyong/repo-agent.git
cd repo-agent
# 需要 Python ≥ 3.11；建议使用 uv：https://docs.astral.sh/uv/
uv pip install -e .
# 或：pip install -e .
```

之后在**该仓库根目录**可用：

```bash
uv run repo-wiki --help
```

**方式 B：从 PyPI 安装（包发布后的常用方式）**

```bash
pip install repo-wiki
# 若已配置 uv：uv pip install repo-wiki
```

安装成功后，确保终端里能执行 `repo-wiki` 或在你目标项目里用 `uv run repo-wiki`（见下文）。

### 2. 配置 LLM（生成 Wiki 必需）

生成流程会调用 LLM，需要在**目标仓库根目录**放置配置文件（任选其一）：

- `repo-wiki.yaml`
- `.repo-wiki.yaml`

具体字段与提供商说明见：[LLM Provider Configuration](./llm-provider-configuration.md)。配置好 API Key 与环境变量后，可用诊断：

```bash
cd /path/to/your-target-repo
uv run repo-wiki config
```

### 3. 在目标仓库里生成 Wiki 目录与文件

以下命令都在**要被文档化的那个代码仓库根目录**执行（例如你的业务项目），而不是只在 `repo-agent` 克隆目录里演示——除非你就是在给 **repo-agent 自己**生成 Wiki。

推荐流程：

```bash
cd /path/to/your-target-repo

uv run repo-wiki init
uv run repo-wiki index
uv run repo-wiki generate --profile qoder-like
```

常见产出（随配置略有差异）：

- `docs/`：面向阅读的 Markdown Wiki
- `ai/source-of-truth/`：结构化索引（YAML 等）
- `.repo-wiki/`：运行时索引与本地状态

校验（不重新生成内容）：

```bash
uv run repo-wiki verify --ci
```

其它子命令（增量更新、同步等）仍可用 `repo-wiki update`、`repo-wiki sync` 等，详见 `uv run repo-wiki --help`。

### 4. 安装 VS Code / Cursor 插件并浏览

插件只负责**浏览与触发终端命令**，安装方式任选：

**预构建 VSIX**

1. 取得 `repo-wiki-browser-0.1.0.vsix`（构建产物或发布页）。
2. 在编辑器中：`Extensions: Install from VSIX`，选择该文件。

**从源码打包**

```bash
cd extensions/repo-wiki-browser
npm install && npm run compile
npx --yes @vscode/vsce package --out repo-wiki-browser-0.1.0.vsix
```

安装成功后：

1. 用编辑器**打开已生成 Wiki 的那个仓库文件夹**（工作区根目录即含 `docs/` 或 `.repo-agent-eval/` 等）。
2. 点击左侧活动栏 **Repo Wiki** 图标，打开侧栏。
3. 侧栏会显示文档树、Git 与 Wiki 版本差异提示、LLM 配置摘要（来自 `repo-wiki.yaml`）。
4. 点击任意条目，会用内置 Markdown 预览打开对应页面。

### 5. 如何更新 Wiki

**在编辑器里（推荐与文档一致）**

- 侧栏按钮 **「更新 Wiki」**，或命令面板：`Repo Wiki: Update Wiki`。
- 默认会在集成终端执行：**`uv run repo-wiki generate --profile qoder-like`**（与 CLI 文档一致）。
- 若本机不用 `uv`，可在设置里修改 **`Repo Wiki › Generate Command`**（配置键 `repoWikiBrowser.generateCommand`），改成你能运行的命令，例如全局安装的 `repo-wiki generate --profile qoder-like`。

**在终端里**

```bash
cd /path/to/your-target-repo
uv run repo-wiki generate --profile qoder-like
```

或使用增量命令（与「全量 generate」语义不同，按项目习惯选择）：

```bash
uv run repo-wiki update
```

**说明**：插件不会内置 Python；`uv`、`repo-wiki` 必须在**集成终端**所用环境中可用（PATH、虚拟环境、`pyproject` 等）。详见插件 README「CLI environment」一节。

---

## CLI Installation

### From PyPI (when published)

```bash
pip install repo-wiki
```

### From Source

```bash
# Clone the repository
git clone https://github.com/bingooyong/repo-agent.git
cd repo-agent

# Install with uv
uv pip install -e .

# Or install with pip
pip install -e .
```

### Verify Installation

```bash
uv run repo-wiki --help
```

Expected output:
```
 Usage: repo-wiki [OPTIONS] COMMAND [ARGS]...

 repo-wiki: local-first repository wiki generator

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.      │
│ --show-completion             Show completion for the current shell, to copy │
│                               it or customize the installation.              │
│ --help                        Show this message and exit.                    │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ init                                                                           │
│ index                                                                        │
│ update                                                                        │
│ sync                                                                         │
│ search                                                                       │
│ graph                                                                        │
│ generate       Generate wiki content using specified eval profile.           │
│ verify         Run wiki verification checks without regenerating content.     │
│ cost-estimate                                                                │
│ config         Run LLM configuration diagnostics.                            │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## VS Code Extension Installation

### Pre-built VSIX

Install the pre-built extension:

1. Download `repo-wiki-browser-0.1.0.vsix`
2. In VS Code, run: `Extensions: Install from VSIX`
3. Select the downloaded `.vsix` file

### Build from Source

```bash
# Navigate to extension directory
cd extensions/repo-wiki-browser

# Compile TypeScript
npm run compile

# Package VSIX
npx --yes @vscode/vsce package --out repo-wiki-browser-0.1.0.vsix
```

The VSIX will be created at `extensions/repo-wiki-browser/repo-wiki-browser-0.1.0.vsix`

### Extension Commands

After installation, the following commands are available:

| Command | Description |
|---------|-------------|
| `Repo Wiki: Open Viewer` | Open the wiki browser sidebar |
| `Repo Wiki: Refresh Wiki Tree` | Refresh the wiki file tree |
| `Repo Wiki: Run Verification` | Run wiki verification in CI mode |
| `Repo Wiki: Update Wiki` | Run configured generate command in terminal (default: `uv run repo-wiki generate --profile qoder-like`; see setting `repoWikiBrowser.generateCommand`) |
| `Repo Wiki: Sync Wiki` | Sync wiki with repository |

## Workflow Reference

### Generate Workflow

```bash
# Initialize repo-wiki in a repository
uv run repo-wiki init

# Index existing documentation
uv run repo-wiki index

# Generate wiki content
uv run repo-wiki generate --profile qoder-like

# View generated wiki
uv run repo-wiki open
```

### Verify Workflow

```bash
# Run verification in CI mode (strict)
uv run repo-wiki verify --ci --profile qoder-like

# Run with custom profile
uv run repo-wiki verify --ci --profile development
```

### Update Workflow

```bash
# Update wiki content
uv run repo-wiki update

# Sync with remote
uv run repo-wiki sync

# Search content
uv run repo-wiki search "authentication"
```

### Extension Workflow

1. Open VS Code
2. Press `Ctrl+Shift+P` / `Cmd+Shift+P`
3. Type "Repo Wiki: Open Viewer"
4. The REPO WIKI sidebar will appear in the activity bar

## Extension Rebuild/Reinstall

If you've modified the extension and need to rebuild:

```bash
# Remove old extension
# In VS Code: Extensions view -> Right-click repo-wiki-browser -> Uninstall

# Rebuild
cd extensions/repo-wiki-browser
npm run compile
npx --yes @vscode/vsce package --out repo-wiki-browser-0.1.0.vsix

# Reinstall from VSIX
# In VS Code: Extensions view -> ... -> Install from VSIX
```

## Troubleshooting

### Extension not loading

1. Check VS Code version (requires ^1.75.0)
2. Verify the VSIX is properly installed
3. Check the extension log in Output panel (View -> Output -> Repo Wiki)

### CLI command not found

```bash
# Reinstall
uv pip install -e .

# Check installation
which repo-wiki
```

### Generate fails

1. Check LLM configuration: `uv run repo-wiki config`
2. Verify API key is set: `echo $MINIMAX_API_KEY`
3. Check network connectivity

## Extension Smoke Test

```bash
# Verify extension builds correctly
cd extensions/repo-wiki-browser
npm run compile  # Should exit with code 0

# Package test
npx --yes @vscode/vsce package --out repo-wiki-browser-0.1.0.vsix
ls -la repo-wiki-browser-0.1.0.vsix  # Should exist and be non-empty
```