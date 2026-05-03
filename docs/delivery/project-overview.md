# repo-wiki MVP — 项目概览（Project Overview）

**文档编号：** DOC-001
**版本：** v1.0.0
**创建日期：** 2026-05-03
**最后更新：** 2026-05-03

---

## 1. 项目简介

repo-wiki 是一个本地优先（local-first）的 CLI 工具，无需 `.qoder` 目录即可为任意后端仓库生成结构化 wiki 文档。

**核心能力：**
- 扫描仓库 → 生成 source-of-truth 产物（repo-map.yaml, module-index.yaml, api-index.yaml, data-models.yaml）
- 支持 SQLite/FTS5 状态管理和 ChromaDB 向量检索
- **Qoder-like 生成**：输出到 `.repo-agent-eval/<run>/content/`，不污染目标仓库
- **Strict Verify**：13 项质量门禁，确保输出达到 qoder 质量标准

---

## 2. 核心功能模块

| 模块 | 功能 | CLI 命令 |
|------|------|---------|
| 初始化 | 初始化仓库索引 | `repo-wiki init` |
| 索引构建 | 构建 SQLite/FTS5 状态和向量索引 | `repo-wiki index` |
| Wiki 生成 | 生成结构化文档（标准/qoder-like） | `repo-wiki generate --profile qoder-like` |
| 增量更新 | 基于 git diff 增量更新 | `repo-wiki update` |
| 质量验证 | Strict verify 质量门禁 | `repo-wiki verify --ci --profile qoder-like` |
| 搜索 | 语义搜索 | `repo-wiki search <query>` |
| 图可视化 | 模块依赖图 | `repo-wiki graph` |
| 成本估算 | LLM 成本估算 | `repo-wiki cost-estimate` |

---

## 3. 架构亮点

### 3.1 Local-first Design

```
SQLite/FTS5 (本地状态) + ChromaDB (向量检索) + 文件系统 (产物)
```

- 无需外部数据库服务
- 状态持久化在 `.repo-wiki/` 目录
- 向量检索使用嵌入式 ChromaDB

### 3.2 Qoder-like Output

```
.repo-agent-eval/<run-id>/
├── content/           # 生成的 Markdown 文件
├── manifest.json      # WikiPlanManifest (navigation tree, git metadata)
└── reports/           # Verify reports
```

- 隔离输出，不修改目标仓库
- Manifest 包含完整导航结构和 git commit 信息

### 3.3 Multi-Agent Architecture

| Agent | 职责 |
|-------|------|
| Scanner | 仓库扫描、语言检测、API/数据模型提取 |
| IndexGraph | SQLite/FTS5、向量索引、模块图 |
| DocGen | LLM Page Composer、Mermaid 图表、质量 guardrails |
| AdapterGovernance | 输出布局、Strict Verify、Citation 验证 |
| QualityRelease | GO/No-Go 决策、Golden Fixtures、趋势分析 |

---

## 4. 技术指标

| 指标 | 数值 |
|------|------|
| Strict Verify 通过率 | 13/13 checks (100%) |
| 页面生成数量 | 80-220 页（可配置） |
| LLM Provider 支持 | OpenAI-compatible, Minimax |
| 测试覆盖率 | 1200+ tests |
| SQLite 查询延迟 | < 100ms (FTS5) |

---

## 5. 应用场景

| 场景 | 说明 |
|------|------|
| 替代 Qoder Repo Wiki | 在 AI_API_Atlas 上通过 strict verify (GO 决策) |
| 仓库文档自动化 | 为任意工程生成结构化 wiki |
| 增量文档更新 | 基于 git diff 只更新变更页面 |
| 质量门禁 | CI/CD 集成 strict verify |

---

## 6. 快速开始

```bash
# 安装
cd repo-agent && uv venv .venv && source .venv/bin/activate && uv pip install -e .

# 配置 LLM
export MINIMAX_API_KEY="your_key_here"  # 或编辑 repo-wiki.yaml

# 生成 Wiki (qoder-like)
cd /path/to/your-repo && uv run repo-wiki generate --profile qoder-like --run-id my-run

# 验证质量
uv run repo-wiki verify --profile qoder-like --ci --output my-run
```

---

## 7. 参考文档

> 详见 [deployment-guide.md](./deployment-guide.md) 部署指南。
> 详见 [user-manual.md](./user-manual.md) 用户手册。
> 详见 [api-spec.md](./api-spec.md) API 规范。
> 详见 [spec.md](./spec/spec.md) 项目规格文档。