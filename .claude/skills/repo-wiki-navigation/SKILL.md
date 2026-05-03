# repo-wiki Delivery Skill

基于项目交付文档生成，用于为任意工程生成 wiki 文档。

## 功能说明

**repo-wiki** 是一个本地优先的 CLI 工具，可以为任意工程（无需 `.qoder` 目录）生成结构化 wiki 文档。支持：
- 增量更新（基于 git diff）
- 质量验证（strict verify）
- qoder-like 输出（隔离于目标工程）

## 快速开始

### 1. 安装

```bash
git clone https://github.com/bingooyong/repo-agent.git
cd repo-agent
uv venv .venv && source .venv/bin/activate
uv pip install -e .
repo-wiki --help
```

### 2. 配置 LLM

编辑 `repo-wiki.yaml` 或 `.repo-wiki.yaml`：

```yaml
llm:
  provider: minimax
  model: abab6-chat
  base_url: https://api.minimax.chat/v1
  api_key_env: MINIMAX_API_KEY
```

或通过环境变量：
```bash
export MINIMAX_API_KEY="your_key_here"
```

### 3. 生成 wiki

```bash
cd /path/to/your-repo
uv run repo-wiki generate --profile qoder-like
```

输出位置：`.repo-agent-eval/<run-id>/content/`

### 4. 验证质量

```bash
uv run repo-wiki verify --profile qoder-like --ci --output <run-id>
```

## 核心命令

| 命令 | 说明 |
|------|------|
| `repo-wiki init` | 初始化项目索引 |
| `repo-wiki index` | 构建搜索索引 |
| `repo-wiki generate --profile qoder-like` | 生成 qoder-like wiki |
| `repo-wiki update` | 增量更新 |
| `repo-wiki verify --ci` | 质量验证 |

## 输出模式

| 模式 | 输出位置 | 特点 |
|------|----------|------|
| **qoder-like** | `.repo-agent-eval/<run>/content/` | 隔离输出，不碰目标工程 |
| **标准模式** | `docs/`, `.repo-wiki/` | 直接写入目标工程 |

## 质量门禁（Strict Verify）

Strict 模式检查项：
- `qoder-page-dumps` - 无列表过重页面
- `qoder-prose-density` - prose 密度 >= 30%
- `qoder-stale-commit` - git commit 最新
- `qoder-content-empty` - 内容非空
- `qoder-toc` - 有目录
- `qoder-citations` - 有引用
- `qoder-mermaid` - 有图表

**通过标准**：grade PASS, exit code 0

## 配置文件

详见 `docs/configuration.md`

## 交付文档索引

- `docs/getting-started.md` - 快速开始
- `docs/configuration.md` - LLM 配置
- `docs/installation.md` - 安装指南
- `docs/release-gate-policy.md` - 发布门禁
- `docs/rollback-plan.md` - 回滚计划
- `docs/go-no-go-dossier.md` - 最终验收报告

## 注意事项

1. **不需要 `.qoder` 目录** - repo-wiki 可独立运行
2. **隔离输出** - qoder-like 模式输出到 `.repo-agent-eval/`，不污染目标工程
3. **使用 `uv run`** - 从目标工程根目录运行，避免 local `repo_wiki` shadowing
4. **配置优先级** - CLI 参数 > 环境变量 > YAML > 默认值