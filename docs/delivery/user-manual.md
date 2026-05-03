# repo-wiki MVP — 用户手册（User Manual）

**文档编号：** DOC-003
**版本：** v1.0.0
**创建日期：** 2026-05-03
**最后更新：** 2026-05-03

---

## 1. 概述

repo-wiki 是本地优先的 wiki 生成工具，适用于需要自动化文档生成的开发团队。

**前提条件：**
- Python 3.10+
- uv 包管理器
- LLM API Key（OpenAI-compatible 或 Minimax）

---

## 2. 快速开始

### 2.1 安装

```bash
git clone https://github.com/bingooyong/repo-agent.git
cd repo-agent
uv venv .venv && source .venv/bin/activate
uv pip install -e .
```

### 2.2 配置

```bash
export MINIMAX_API_KEY="your_key_here"
```

### 2.3 生成 Wiki

```bash
cd /path/to/your-repo

# 初始化
uv run repo-wiki init

# 生成文档（qoder-like 模式，隔离输出）
uv run repo-wiki generate --profile qoder-like --run-id my-first-run

# 验证质量
uv run repo-wiki verify --profile qoder-like --ci --output my-first-run
```

---

## 3. CLI 命令参考

### 3.1 repo-wiki init

初始化仓库索引：

```bash
uv run repo-wiki init [选项]
```

| 选项 | 说明 |
|------|------|
| `--force` | 强制重新初始化 |

### 3.2 repo-wiki index

构建搜索索引：

```bash
uv run repo-wiki index [选项]
```

### 3.3 repo-wiki generate

生成 Wiki 文档：

```bash
uv run repo-wiki generate [选项]
```

| 选项 | 说明 |
|------|------|
| `--profile {standard,qoder-like}` | 生成模式（默认 standard） |
| `--run-id <id>` | 运行 ID，用于输出目录命名 |
| `--config <path>` | 指定配置文件 |
| `--llm-model <model>` | 指定 LLM 模型 |
| `--max-pages <n>` | 最大页面数（默认 220） |
| `--min-pages <n>` | 最小页面数（默认 24） |

**示例：**

```bash
# 标准模式（输出到 docs/）
uv run repo-wiki generate

# Qoder-like 隔离模式
uv run repo-wiki generate --profile qoder-like --run-id my-run --max-pages 150

# 使用真实 LLM（默认）
uv run repo-wiki generate --profile qoder-like --run-id real-llm-run

# 强制使用 mock LLM
REPO_WIKI_FORCE_MOCK_LLM=1 uv run repo-wiki generate --profile qoder-like
```

### 3.4 repo-wiki verify

验证输出质量：

```bash
uv run repo-wiki verify [选项]
```

| 选项 | 说明 |
|------|------|
| `--profile {standard,transitional,qoder-like}` | 验证模式 |
| `--ci` | CI 模式（非 PASS 则 exit code 非 0） |
| `--output <run-id>` | 指定验证的运行 ID |

**示例：**

```bash
uv run repo-wiki verify --profile qoder-like --ci --output my-first-run
```

### 3.5 repo-wiki update

增量更新（基于 git diff）：

```bash
uv run repo-wiki update [选项]
```

| 选项 | 说明 |
|------|------|
| `--profile <profile>` | 指定 profile |
| `--run-id <id>` | 运行 ID |

### 3.6 repo-wiki search

语义搜索：

```bash
uv run repo-wiki search "<query>" [选项]
```

**示例：**

```bash
uv run repo-wiki search "API endpoint authentication"
```

### 3.7 repo-wiki graph

生成模块依赖图：

```bash
uv run repo-wiki graph [选项]
```

| 选项 | 说明 |
|------|------|
| `--format {text,mermaid,dot}` | 输出格式 |
| `--output <file>` | 输出文件 |

### 3.8 repo-wiki cost-estimate

LLM 成本估算：

```bash
uv run repo-wiki cost-estimate [选项]
```

| 选项 | 说明 |
|------|------|
| `--profile <profile>` | 指定 profile |
| `--pages <n>` | 预估页面数 |

### 3.9 repo-wiki config

查看/验证配置：

```bash
uv run repo-wiki config [选项]
```

---

## 4. 配置文件

### 4.1 repo-wiki.yaml 示例

```yaml
llm:
  provider: minimax
  model: abab6-chat
  base_url: https://api.minimax.chat/v1
  api_key_env: MINIMAX_API_KEY

generation:
  profile: qoder-like
  min_pages: 24
  max_pages: 220
  concurrency: 4

output:
  eval_dir: .repo-agent-eval
  protect_patterns:
    - .qoder/**
    - .repo-wiki/**
    - docs/**
```

---

## 5. 常见问题

### Q: 生成失败怎么办？

1. 检查 LLM API Key 是否正确配置
2. 查看日志确认错误原因
3. 使用 `--llm-model` 指定其他模型
4. 减少 `--max-pages` 降低单次生成量

### Q: 如何只生成部分页面？

目前不支持选择性生成。可通过 `--min-pages` 和 `--max-pages` 控制生成数量范围。

### Q: 如何自定义页面模板？

页面模板在 `repo_wiki/generator/prompts/` 目录，后续版本支持自定义。

---

## 6. 参考文档

> 详见 [project-overview.md](./project-overview.md) 项目概览。
> 详见 [deployment-guide.md](./deployment-guide.md) 部署指南。
> 详见 [api-spec.md](./api-spec.md) API 规范。