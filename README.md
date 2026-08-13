# repo-wiki

**Local-first repository wiki generator** — 无需 `.qoder` 目录即可为任意工程生成结构化 Wiki 文档。

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![CI](https://github.com/bingooyong/repo-wiki-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/bingooyong/repo-wiki-agent/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/bingooyong/repo-wiki-agent/branch/main/graph/badge.svg)](https://codecov.io/gh/bingooyong/repo-wiki-agent)

## 核心能力

- **Qoder-like 输出** — 提供隔离生成、发布清单和可配置的严格质量门禁
- **Local-first** — 无需外部数据库，SQLite + ChromaDB 嵌入式运行
- **隔离输出** — `--profile qoder-like` 输出到 `.repo-agent-eval/`，不污染目标仓库
- **增量更新** — 基于 git diff 实现页面级失效和选择性重生成
- **Strict Verify** — 13 项质量门禁（prose density、citations、Mermaid、stale commit 等）

## 快速开始

### 1. 安装 `repo-wiki` CLI

```bash
git clone https://github.com/bingooyong/repo-wiki-agent.git
cd repo-wiki-agent
uv venv .venv && source .venv/bin/activate
uv pip install -e .
```

在新项目中确认命令可用：

```bash
cd /path/to/your-repo
repo-wiki --help
```

### 2. 在目标项目配置 LLM

当前 VS Code/Cursor 插件还不支持可视化配置 LLM。生成 Wiki 前，需要先在目标项目中人工配置 CLI 的 LLM 接入。

在目标项目根目录创建 `repo-wiki.yaml`，只写非敏感配置：

```yaml
project:
  name: auto
  root: .

llm:
  provider: openai
  model: gpt-4o-mini
  base_url: https://api.example.com/v1
  api_key_env: REPO_WIKI_LLM_API_KEY
```

然后在当前 VS Code 集成终端或 shell 中设置真实 API Key：

```bash
export REPO_WIKI_LLM_API_KEY="<your-api-key>"
```

不要把真实 API Key 写入 `repo-wiki.yaml`、VS Code settings、命令字符串、日志、文档或已提交文件。当前插件实现 SecretStorage 前，推荐优先使用临时终端环境变量；shell profile 或未提交 `.env` 属于本机落盘方案，仅在你接受该风险时使用。

也可以不写 YAML，直接使用环境变量：

```bash
export LLM_PROVIDER="openai"
export LLM_MODEL="gpt-4o-mini"
export LLM_BASE_URL="https://api.example.com/v1"
export LLM_API_KEY_ENV="REPO_WIKI_LLM_API_KEY"
export REPO_WIKI_LLM_API_KEY="<your-api-key>"
```

### 3. 诊断、生成、验证、发布

```bash
# 检查 LLM 配置。FAIL 时会返回非零码，但仍会输出 JSON 诊断。
repo-wiki config --ci

# 初始化与索引
repo-wiki init
repo-wiki index

# 生成 Wiki（qoder-like 模式，隔离输出）
repo-wiki generate --profile qoder-like --output .repo-agent-eval

# 验证质量
repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval

# 发布 READY release，供 VS Code/Cursor 插件读取
repo-wiki release-publish --output .repo-agent-eval
```

插件默认读取：

```text
.repo-agent-eval/repowiki/zh/manifest.json
```

如果只生成 run 目录但未执行 `release-publish`，插件可能看不到可浏览 Wiki。

## CLI 命令

| 命令 | 说明 |
|------|------|
| `repo-wiki init` | 初始化仓库索引 |
| `repo-wiki index` | 构建搜索索引 |
| `repo-wiki generate [--profile qoder-like]` | 生成 Wiki 文档 |
| `repo-wiki update` | 增量更新（基于 git diff） |
| `repo-wiki verify --ci --profile qoder-like` | 质量验证 |
| `repo-wiki release-publish --output .repo-agent-eval` | 发布 READY release，供插件读取 |
| `repo-wiki config --ci` | LLM 配置诊断 |
| `repo-wiki search "<query>"` | 语义搜索 |
| `repo-wiki graph` | 模块依赖图 |
| `repo-wiki cost-estimate` | LLM 成本估算 |

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                            │
│         init | index | generate | verify | search | ...     │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Orchestration Layer                      │
│   Service │ GenerationStateMachine │ GenerationScheduler       │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Agent Layer                            │
│  Scanner │ IndexGraph │ DocGen │ AdapterGovernance │ QA      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Storage Layer                          │
│     SQLite/FTS5      │      ChromaDB      │    Files       │
└─────────────────────────────────────────────────────────────┘
```

## 输出模式

| 模式 | 输出位置 | 特点 |
|------|----------|------|
| **qoder-like run** | `.repo-agent-eval/runs/<run>/repowiki/zh/**` | 隔离运行产物，不碰目标工程 |
| **qoder-like release** | `.repo-agent-eval/repowiki/zh/{manifest.json,content,meta}` | READY 稳定发布面，VS Code/Cursor 插件默认读取 |
| **standard** | `docs/`, `.repo-wiki/` | 直接写入目标工程 |

## VS Code / Cursor 插件

插件目录：`extensions/repo-wiki-browser`。

当前插件能力：

- 浏览 `.repo-agent-eval/repowiki/zh/manifest.json` 中 READY release 的 `navigation_tree`；
- 打开生成的 Markdown 预览；
- 触发 `Repo Wiki: Update Wiki`，本质是向 VS Code 集成终端发送 `repoWikiBrowser.generateCommand`；
- 展示 `repo-wiki.yaml` / `.repo-wiki.yaml` 中的 LLM 摘要。

当前插件限制：

- 尚不支持可视化配置 LLM provider / model / base URL / API Key；
- 尚不支持 SecretStorage 保存 API Key；
- 尚不自动注入 `LLM_PROVIDER`、`LLM_MODEL`、`LLM_BASE_URL`、`LLM_API_KEY_ENV`；
- 使用插件前仍需按上文或 `docs/operations/vscode-extension-manual-llm-configuration.md` 手动配置 CLI 环境。

重新打包插件：

```bash
cd extensions/repo-wiki-browser
npm ci
npm run compile
npx @vscode/vsce package --out repo-wiki-browser-0.1.0.vsix
code --install-extension repo-wiki-browser-0.1.0.vsix --force
```

## Strict Verify 门禁（qoder-like）

| 检查项 | 说明 | 门禁 |
|--------|------|------|
| `qoder-page-dumps` | 无列表过重页面 | HARD |
| `qoder-prose-density` | prose 密度 >= 30% | HARD |
| `qoder-stale-commit` | git commit 最新 | HARD |
| `qoder-content-empty` | 内容非空 | HARD |
| `qoder-toc` | 有目录 | SOFT |
| `qoder-citations` | 有引用 | SOFT |
| `qoder-mermaid` | 有图表 | SOFT |
| `qoder-api-aggregation` | API 聚合质量 | HARD |
| `qoder-dm-aggregation` | Data model 聚合质量 | HARD |
| `qoder-citation-relevance` | 引用相关性 | HARD |
| `qoder-dirty-worktree` | 工作树干净 | HARD |

## 文档

- [新项目 / VS Code 插件人工 LLM 配置指南](./docs/operations/vscode-extension-manual-llm-configuration.md)
- [LLM 终端用户配置指南](./docs/configuration.md)
- [VS Code LLM 配置能力规格](./docs/specs/vscode-llm-configuration-spec.md)
- [VS Code LLM 配置实施计划](./docs/plans/vscode-llm-configuration-implementation-plan.md)
- [展示层与 Wiki 生成层优化路线图](./docs/plans/display-and-wiki-generation-optimization-roadmap.md)
- [项目交付文档包](./docs/delivery/index.md) — 完整的 14+4 份交付文档
- [用户手册](./docs/delivery/user-manual.md) — CLI 详细用法
- [部署指南](./docs/delivery/deployment-guide.md) — 安装和 CI/CD 集成
- [配置指南](./docs/delivery/configuration-guide.md) — YAML 配置详解

## 项目状态

| 指标 | 状态 |
|------|------|
| Strict Verify | 可通过 `repo-wiki verify --profile qoder-like --ci` 复现 |
| Release Gate | 仅发布通过当前门禁的 READY 产物 |
| Tests | 以公开 CI 结果为准 |

## 技术栈

- **Python 3.11+** with `uv` package manager
- **SQLite/FTS5** — 本地状态和全文检索
- **ChromaDB** — 语义向量存储
- **LLM** — OpenAI-compatible / Minimax
- **VS Code/Cursor Extension** — TypeScript sidebar for browsing READY Wiki releases

## License

Apache License 2.0 - see [LICENSE](LICENSE)
