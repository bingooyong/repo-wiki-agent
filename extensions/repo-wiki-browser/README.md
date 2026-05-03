# Repo Wiki Browser - VS Code Extension

A VS Code extension for browsing repo-agent wiki outputs from a dedicated Activity Bar entry.

## 使用流程（概要）

1. **安装 `repo-wiki` CLI**：克隆 [repo-agent](https://github.com/bingooyong/repo-agent) 后在该仓库根目录执行 `uv pip install -e .`（或 PyPI 发布后 `pip install repo-wiki`）；需要 Python ≥ 3.11，建议使用 `uv`。
2. **在目标代码仓库配置 LLM**：根目录添加 `repo-wiki.yaml`，参见仓库内 `docs/operations/llm-provider-configuration.md`。
3. **生成并发布 Wiki**：在目标仓库执行 `uv run repo-wiki init`、`index`、`generate --profile qoder-like --output .repo-agent-eval`。候选 run 产出在 `.repo-agent-eval/runs/<run>/repowiki/zh/**`；通过门禁后发布到 `.repo-agent-eval/repowiki/zh/content` 与 `.repo-agent-eval/repowiki/zh/meta`。
4. **安装本插件**：VSIX「Install from VSIX」，或在本目录 `npm run compile` + `vsce package`。
5. **浏览**：用编辑器打开该目标仓库 → 活动栏 **Repo Wiki** → 侧栏点文档打开 Markdown 预览。
6. **更新 Wiki**：侧栏「更新 Wiki」或命令 `Repo Wiki: Update Wiki`，默认终端命令为 `uv run repo-wiki generate --profile qoder-like`（可在设置 `repoWikiBrowser.generateCommand` 修改）。

**完整步骤与说明（中英）**：`[docs/operations/installation-and-vscode-extension.md](../../docs/operations/installation-and-vscode-extension.md)` 开头的「中文：安装、生成 Wiki、安装插件与更新」一节。

## Features

- **Repo Wiki Activity Bar**: Adds a dedicated Repo Wiki icon in the left Activity Bar.
- **Qoder-style Sidebar**: Shows the published release, update status, language selector, update/sync actions, and manifest navigation tree.
- **Rendered Markdown Preview**: Click any wiki item to open VS Code's Markdown preview instead of raw markdown text.
- **Git Drift Prompt**: Compares current git commit with manifest `wiki_git_commit` / `target_git_commit` and prompts when wiki is stale.
- **Commands**:
  - `Repo Wiki: Open Wiki Viewer` - Opens the wiki overview
  - `Repo Wiki: Refresh Wiki Tree` - Refreshes the navigation tree
  - `Repo Wiki: Run Verification (--ci)` - Runs `repo-wiki verify --ci`
  - `Repo Wiki: Update Wiki` - Runs the configured generate/regenerate command (default: `uv run repo-wiki generate --profile qoder-like`; see **CLI environment** below)
  - `Repo Wiki: Sync Wiki` - Runs `repo-wiki sync`

## Installation

### From Source

1. Navigate to the extension directory:
  ```bash
   cd extensions/repo-wiki-browser
  ```
2. Install dependencies:
  ```bash
   npm install
  ```
3. Compile TypeScript:
  ```bash
   npm run compile
  ```
4. Package or run in Extension Development Host.
  Development:
   Then press `F5`.
   Packaging can be done with `vsce`:

### For Development

1. Open the extension directory in VS Code:
  ```bash
   code extensions/repo-wiki-browser
  ```
2. Press `F5` to launch the Extension Development Host
3. The extension will be activated when you open a workspace containing a repo-agent project

## Requirements

- VS Code 1.75.0 or higher
- A workspace with a READY repo-agent release manifest at `.repo-agent-eval/repowiki/zh/manifest.json`

## CLI environment (generate / update)

The extension is **TypeScript-only** and **does not bundle** the `repo-wiki` Python package, embeddings, or LLM runtime. After installation, **Update Wiki** sends a shell command to the **integrated terminal** (same as typing it yourself). For the default command to work you typically need:

1. `**uv`** installed and on the PATH seen by VS Code’s terminal (sometimes differs from GUI apps on macOS — configure shell integration or use an absolute path if needed).
2. **A resolvable `repo-wiki` entrypoint** in that workspace context — most commonly `uv run repo-wiki …` from a repo that declares `repo-wiki` (e.g. local editable install / project `pyproject.toml`). Global installs (`pipx`, `pip install`) also work if your terminal finds them.

If you cannot use `uv`, set **Settings → Repo Wiki → Generate Command** (`repoWikiBrowser.generateCommand`) to whatever matches your machine, for example:

- `pipx run repo-wiki generate --profile qoder-like` (if published on PyPI and pipx has it)
- Path to a venv Python module if your project documents it

**Bundling repo-wiki inside the VSIX** would mean shipping Python, native wheels, and optional large deps across OS/architectures — high maintenance and poor fit for a lightweight sidebar extension. The supported model remains: **browser UI in VS Code + CLI in your environment** (optionally standardized via Dev Containers / tasks.json for repeatable PATH).

## Project Structure

```
extensions/repo-wiki-browser/
├── package.json          # Extension manifest
├── tsconfig.json         # TypeScript configuration
├── README.md             # This file
└── src/
    └── extension.ts      # Main extension code
```

## Usage

1. Open a workspace with repo-agent wiki content
2. Click the Repo Wiki icon in the Activity Bar
3. Use the left sidebar to browse the published release `navigation_tree`
4. Click on any page to open the rendered Markdown preview
5. Use commands from the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`):
  - `Repo Wiki: Open Wiki Viewer`
  - `Repo Wiki: Refresh Wiki Tree`
  - `Repo Wiki: Run Verification (--ci)`
  - `Repo Wiki: Update Wiki`
  - `Repo Wiki: Sync Wiki`

## Extension Points

The extension integrates with:

- **Webview View Provider**: `RepoWikiSidebarProvider` class
- **Commands**: Registered via `vscode.commands.registerCommand`
- **Markdown Preview**: Uses VS Code's built-in markdown preview command

## Known Limitations

- **PATH / CLI**: The extension process does not run `uv` itself; only the integrated terminal does. There is no guaranteed preflight check (extension host PATH often differs from the terminal).
- Git drift detection depends on manifest `wiki_git_commit` / `target_git_commit` and local git history availability.
- The language selector is currently UI state only; content localization depends on generated wiki files.
- If no READY release manifest with `navigation_tree` is found at `.repo-agent-eval/repowiki/zh/manifest.json`, the sidebar only shows generation guidance.

## Future Enhancements

- Extension host tests
- Offline Mermaid asset bundling for custom viewer mode
