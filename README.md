# repo-wiki

**Local-first repository wiki generator** — 无需 `.qoder` 目录即可为任意工程生成结构化 Wiki 文档。

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Strict Verify: PASS](https://img.shields.io/badge/Strict%20Verify-PASS-brightgreen)](#)
[![Tests: 1200+](https://img.shields.io/badge/Tests-1200%2B-blue)](#)
[![GO Decision: 2026-05-02](https://img.shields.io/badge/GO-2026--05--02-green)](#)

## 核心能力

- **Qoder 替代** — 在 AI_API_Atlas 上通过 strict verify（13/13 checks），达到与 Qoder Repo Wiki 相同质量标准
- **Local-first** — 无需外部数据库，SQLite + ChromaDB 嵌入式运行
- **隔离输出** — `--profile qoder-like` 输出到 `.repo-agent-eval/`，不污染目标仓库
- **增量更新** — 基于 git diff 实现页面级失效和选择性重生成
- **Strict Verify** — 13 项质量门禁（prose density、citations、Mermaid、stale commit 等）

## 快速开始

```bash
# 安装
git clone https://github.com/bingooyong/repo-agent.git
cd repo-agent
uv venv .venv && source .venv/bin/activate
uv pip install -e .

# 配置 LLM（Minimax 或 OpenAI-compatible）
export MINIMAX_API_KEY="your_key_here"

# 进入目标仓库
cd /path/to/your-repo

# 生成 Wiki（qoder-like 模式，隔离输出）
uv run repo-wiki generate --profile qoder-like --run-id my-run

# 验证质量
uv run repo-wiki verify --profile qoder-like --ci --output my-run
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `repo-wiki init` | 初始化仓库索引 |
| `repo-wiki index` | 构建搜索索引 |
| `repo-wiki generate [--profile qoder-like]` | 生成 Wiki 文档 |
| `repo-wiki update` | 增量更新（基于 git diff） |
| `repo-wiki verify --ci --profile qoder-like` | 质量验证 |
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
| **qoder-like** | `.repo-agent-eval/<run>/content/` | 隔离输出，不碰目标工程 |
| **standard** | `docs/`, `.repo-wiki/` | 直接写入目标工程 |

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

- [项目交付文档包](./docs/delivery/index.md) — 完整的 14+4 份交付文档
- [用户手册](./docs/delivery/user-manual.md) — CLI 详细用法
- [部署指南](./docs/delivery/deployment-guide.md) — 安装和 CI/CD 集成
- [配置指南](./docs/delivery/configuration-guide.md) — YAML 配置详解
- [GO/No-Go 决策](./docs/go-no-go-dossier.md) — Phase 35 决策文档

## 项目状态

| 指标 | 状态 |
|------|------|
| Strict Verify | ✅ PASS (13/13) |
| GO Decision | ✅ GO (Atlas strict benchmark) |
| Tests | 1200+ |
| Phases | 35 Completed |

## 技术栈

- **Python 3.10+** with `uv` package manager
- **SQLite/FTS5** — 本地状态和全文检索
- **ChromaDB** — 语义向量存储
- **LLM** — OpenAI-compatible / Minimax

## License

Apache License 2.0 - see [LICENSE](LICENSE)