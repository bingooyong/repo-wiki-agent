# repo-wiki 总览

`repo-wiki` 是 local-first 的仓库 Wiki 生成器（Python CLI）。本 GitHub 仓库是 `bingooyong/repo-wiki-agent`，内含 CLI、VS Code/Cursor 浏览插件 `extensions/repo-wiki-browser`、策管文档与 `ai/source-of-truth/`。

## 名称对照

| 名称 | 指什么 | 不要当成 |
|------|--------|----------|
| `bingooyong/repo-wiki-agent` | GitHub 源代码仓库 | CLI 命令名 |
| `repo-wiki` | PyPI 包名 / 终端命令 | GitHub 仓名 |
| `.repo-agent-eval/` | 隔离评估与 READY 发布根目录（历史契约名） | 仓库 git clone 路径 |

`.repo-agent-eval` **不会**在本变更中改名。插件默认只读：

`.repo-agent-eval/repowiki/zh/manifest.json`

## 三层落盘

1. **运行时** `.repo-wiki/` — SQLite/FTS、图谱、向量或 JSON fallback
2. **事实层** `ai/source-of-truth/` — 策管 YAML（module/api/data-model/repo-map/task-catalog）
3. **文档层** `docs/` — 给人与 Agent 读；本页为策管入口，不是 generate 产物

## 主路径

```bash
git clone https://github.com/bingooyong/repo-wiki-agent.git
cd repo-wiki-agent
uv pip install -e .

repo-wiki config --ci
repo-wiki init
repo-wiki index
repo-wiki generate --profile qoder-like --output .repo-agent-eval
repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval
repo-wiki release-publish --output .repo-agent-eval
```

插件在目标仓库看到 READY + `navigation_tree` 后才展示侧栏。未 `release-publish` 时可能显示无 Wiki。

## 下一步

- 现行规划：`docs/plans/current-roadmap.md`
- 中期 Phase 09–12：`docs/repo-wiki-phase-09-12-roadmap.md`
- 架构：`docs/01-architecture.md`
- 配置：`docs/configuration.md`；插件可配 LLM（Key 进 SecretStorage），见扩展 README 与 `docs/operations/vscode-extension-manual-llm-configuration.md`
- 安装与插件：`docs/operations/installation-and-vscode-extension.md`
- Agent 入口：仓库根 `AGENTS.md`
