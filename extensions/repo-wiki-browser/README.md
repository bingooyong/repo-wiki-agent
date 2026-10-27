# Repo Wiki Browser - VS Code Extension

A VS Code extension for browsing repo-wiki READY wiki outputs from a dedicated Activity Bar entry.

## 使用流程（概要）

1. **安装 `repo-wiki` CLI**：克隆 [repo-wiki-agent](https://github.com/bingooyong/repo-wiki-agent) 后在该仓库根目录执行 `uv pip install -e .`（或 PyPI 发布后 `pip install repo-wiki`）；需要 Python ≥ 3.11，建议使用 `uv`。
2. **配置 LLM**：在活动栏 **Repo Wiki** 侧栏点击「配置」选择 LLM source。默认 `extension` 仅注入非空 provider/model/base URL；`yaml` 保留 `repo-wiki.yaml` 的非敏感字段；`environment` 不注入任何 LLM 覆盖变量。点击「设置 Key」可把真实 API Key 保存到 VS Code SecretStorage。扩展不直接调用 LLM。
3. **生成并发布 Wiki**：在目标仓库执行 `uv run repo-wiki init`、`index`、`generate --profile qoder-like --output .repo-agent-eval`。候选 run 产出在 `.repo-agent-eval/runs/<run>/repowiki/zh/**`；通过门禁后发布到 `.repo-agent-eval/repowiki/zh/content` 与 `.repo-agent-eval/repowiki/zh/meta`。
4. **安装本插件**：VSIX「Install from VSIX」，或在本目录 `npm run compile` + `vsce package`。
5. **浏览**：用编辑器打开该目标仓库 → 活动栏 **Repo Wiki** → 侧栏点文档打开 Markdown 预览。
6. **更新 Wiki**：侧栏「更新 Wiki」或命令 `Repo Wiki: Update Wiki`，默认运行 `uv run repo-wiki generate --profile qoder-like --output .repo-agent-eval`。进度与失败原因显示在侧栏和 **Repo Wiki** 输出通道。生成不会自动发布 READY；验证通过后用侧栏「发布 READY」或 `Repo Wiki: Release Publish READY`。

**完整步骤与说明（中英）**：[docs/operations/installation-and-vscode-extension.md](../../docs/operations/installation-and-vscode-extension.md) 开头的「中文：安装、生成 Wiki、安装插件与更新」一节。

## Features

- **Repo Wiki Activity Bar**: Adds a dedicated Repo Wiki icon in the left Activity Bar.
- **Qoder-style Sidebar**: Shows the published release or why READY is missing (not generated / verify failed / not published), LLM configuration status, generate progress/failure, language selector, update/verify/publish/sync actions, and manifest navigation tree.
- **Rendered Markdown Preview**: Click any wiki item to open VS Code's Markdown preview instead of raw markdown text.
- **Release-only default**: The extension only loads `.repo-agent-eval/repowiki/zh/manifest.json` when it is READY, and does not auto-fallback to `.repo-agent-eval/runs/*`.

## Release contract (plugin + Python viewer)

- **Canonical default surface**: both the VS Code extension and `create_viewer_for_workspace_release()` read **only**
  `[workspace]/.repo-agent-eval/repowiki/zh/manifest.json`. There is **no recursive scan** of `.repo-agent-eval/runs/*/`
  for the default tree.
- **READY gate**: manifests must advertise release readiness in a form consistent with Python (e.g.
  `release_status`, `readiness_state`, plain `readiness` string, or nested `readiness.readiness_state`) and MUST be `READY`;
  otherwise the UI shows NO_RELEASE / generation guidance rather than silently using a stale run.
- **`navigation_tree`**: required for browsing; empty or missing tree is treated as no release.
- **Diagnostic / tooling path**: to inspect an arbitrary on-disk manifest (e.g. a run directory), use
  `create_viewer_for_directory(root_dir, manifest_path=...)` in Python or point your own tooling at that manifest;
  this is **not** the extension default.
- **Git Drift Prompt**: Compares current git commit with manifest `wiki_git_commit` / `target_git_commit` and prompts when wiki is stale.
- **Commands**:
  - `Repo Wiki: Open Wiki Viewer` - Opens the wiki overview
  - `Repo Wiki: Refresh Wiki Tree` - Refreshes the navigation tree
  - `Repo Wiki: Run Verification (--ci)` - Runs `uv run repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval` with captured progress/failure
  - `Repo Wiki: Update Wiki` - Runs the configured generate command with captured progress/failure (default: `uv run repo-wiki generate --profile qoder-like --output .repo-agent-eval`; see **CLI environment** below)
  - `Repo Wiki: Release Publish READY` - Runs `uv run repo-wiki release-publish --output .repo-agent-eval` so the sidebar can read the READY wiki
  - `Repo Wiki: Sync Wiki` - Runs `repo-wiki sync`
  - `Repo Wiki: Configure LLM Settings` - Sets the source strategy plus optional provider/model/base URL/API key environment variable name in VS Code settings
  - `Repo Wiki: Set LLM API Key` - Stores the actual API key in VS Code SecretStorage
  - `Repo Wiki: Clear LLM API Key` - Removes the stored API key from SecretStorage
  - `Repo Wiki: Test LLM Configuration` - Runs `repo-wiki config --ci` with the same injected environment and redacted diagnostics

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
3. The extension will be activated when you open a workspace containing a READY `.repo-agent-eval` release

## Requirements

- VS Code 1.75.0 or higher
- A workspace with a READY repo-wiki release manifest at `.repo-agent-eval/repowiki/zh/manifest.json`

## LLM configuration

The extension now provides a visual LLM configuration loop while preserving the security boundary: **only the Python `repo-wiki` CLI calls the LLM**. The TypeScript extension stores UI preferences, launches terminals, and runs CLI diagnostics.

Visual workflow:

1. Open a target repository in VS Code/Cursor.
2. Open the **Repo Wiki** Activity Bar view.
3. In the **LLM Settings** panel, click **Configure** or run `Repo Wiki: Configure LLM Settings`.
4. Set:
   - `repoWikiBrowser.llm.source` → `extension` (default), `yaml`, or `environment`
   - `repoWikiBrowser.llm.provider` → optional; injected as `LLM_PROVIDER` only for `source=extension` and only when non-empty
   - `repoWikiBrowser.llm.model` → optional; injected as `LLM_MODEL` only for `source=extension` and only when non-empty
   - `repoWikiBrowser.llm.baseUrl` → optional; injected as `LLM_BASE_URL` only for `source=extension` and only when non-empty
   - `repoWikiBrowser.llm.apiKeyEnv` → environment variable name for the real key; empty falls back to `REPO_WIKI_LLM_API_KEY`
5. Click **Set Key** or run `Repo Wiki: Set LLM API Key`. The real key is saved in VS Code SecretStorage under the extension account, not in settings or YAML.
6. Click **Test** or run `Repo Wiki: Test LLM Configuration`. The extension runs `repo-wiki config --ci` with the same environment injection, captures stdout/stderr, redacts defensively, and shows OK/FAIL plus provider/model/base URL/key-present status.
7. Click **Update Wiki**. Generate progress and the failure reason appear in the sidebar and the **Repo Wiki** output channel (not only a silent terminal dump). The visible command remains the configured generate command; any selected short-lived LLM values are injected into that process environment. Generate does **not** auto-publish READY.
8. After verify passes, click **Publish READY** or run `Repo Wiki: Release Publish READY` (`uv run repo-wiki release-publish --output .repo-agent-eval`), then refresh the sidebar.

Source strategies:

- **`extension`**: injects only non-empty visual settings (`LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`), always injects `LLM_API_KEY_ENV`, and injects the actual API key into the selected env var only when SecretStorage contains a key.
- **`yaml`**: does not inject provider/model/base URL, so `repo-wiki.yaml` remains authoritative for non-secret LLM fields. If SecretStorage contains a key, the extension may inject only the actual key into `repoWikiBrowser.llm.apiKeyEnv` (default `REPO_WIKI_LLM_API_KEY`).
- **`environment`**: injects no LLM override variables and no SecretStorage key; the CLI sees the shell/process environment exactly as configured by the user.

Empty provider/model/base URL settings are intentional and safe: they mean “use the CLI/YAML/shell default”, not Anthropic or any other provider.

Security rules:

- Do **not** put a real API key in VS Code settings, `repo-wiki.yaml`, command strings, README examples, logs, or committed files.
- The extension manifest exposes only non-secret settings. There is intentionally no `repoWikiBrowser.llm.apiKey` setting.
- SecretStorage is the only extension-managed location for the actual API key.
- Generated commands stay secret-free; the key is passed only as a process environment variable named by `repoWikiBrowser.llm.apiKeyEnv` when the selected source allows SecretStorage injection.
- YAML files may still exist for CLI users; choose `source=yaml` to avoid overriding YAML non-sensitive fields from the extension UI.

References:

- Manual fallback flow: [`docs/operations/vscode-extension-manual-llm-configuration.md`](../../docs/operations/vscode-extension-manual-llm-configuration.md)
- Full CLI configuration reference: [`docs/configuration.md`](../../docs/configuration.md)


## CLI environment (generate / update)

The extension is **TypeScript-only** and **does not bundle** the `repo-wiki` Python package, embeddings, or LLM runtime. After installation, **Update Wiki** runs the configured generate command as a tracked process (sidebar progress + Output channel). For the default command to work you typically need:

1. **`uv`** installed and on the PATH seen by VS Code’s terminal (sometimes differs from GUI apps on macOS — configure shell integration or use an absolute path if needed).
2. **A resolvable `repo-wiki` entrypoint** in that workspace context — most commonly `uv run repo-wiki …` from a repo that declares `repo-wiki` (e.g. local editable install / project `pyproject.toml`). Global installs (`pipx`, `pip install`) also work if your terminal finds them.

If you cannot use `uv`, set **Settings → Repo Wiki → Generate Command** (`repoWikiBrowser.generateCommand`) to whatever matches your machine, for example:

- `pipx run repo-wiki generate --profile qoder-like --output .repo-agent-eval` (if published on PyPI and pipx has it)
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
  - `Repo Wiki: Release Publish READY`
  - `Repo Wiki: Sync Wiki`
  - `Repo Wiki: Configure LLM Settings`
  - `Repo Wiki: Set LLM API Key`
  - `Repo Wiki: Clear LLM API Key`
  - `Repo Wiki: Test LLM Configuration`

## Extension Points

The extension integrates with:

- **Webview View Provider**: `RepoWikiSidebarProvider` class
- **Commands**: Registered via `vscode.commands.registerCommand`
- **Markdown Preview**: Uses VS Code's built-in markdown preview command

## Known Limitations

- **PATH / CLI**: The extension host runs the configured generate/verify/publish commands and shows progress/failure in the sidebar. `uv` and `repo-wiki` must still resolve in that process environment.
- Git drift detection depends on manifest `wiki_git_commit` / `target_git_commit` and local git history availability.
- The language selector is currently UI state only; content localization depends on generated wiki files.
- If no READY release manifest with `navigation_tree` is found at `.repo-agent-eval/repowiki/zh/manifest.json`, the sidebar explains whether generate has not run, verify failed, or `release-publish` has not run.
- Mermaid blocks are rendered by VS Code Markdown preview from published release content files (`repowiki/zh/content/**`).

## Future Enhancements

- Extension host tests
- Offline Mermaid asset bundling for custom viewer mode
