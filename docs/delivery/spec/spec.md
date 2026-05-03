# repo-wiki MVP — 项目规格文档（Spec）

**文档编号：** SPEC-001
**版本：** v1.0.0
**创建日期：** 2026-05-03
**最后更新：** 2026-05-03

---

## 项目背景 [必填]

repo-wiki 是一个本地优先（local-first）的 CLI 工具，专为后端仓库设计，无需 `.qoder` 目录即可生成结构化 wiki 文档。项目核心目标是替代 Qoder Repo Wiki，通过 AI_API_Atlas 的 strict verify 验证（13/13 checks, grade PASS），达成 **GO** 决策。

### 项目基本信息

| 属性 | 内容 |
|------|------|
| 项目名称 | repo-wiki |
| 项目代号 | repo-agent-qoder-replacement |
| 业务领域 | DevOps / Platform Engineering / Documentation Automation |
| 目标上线时间 | 2026-05-02 (Phase 35 GO 已达成) |

---

## 业务目标 [必填]

### 核心目标

1. **Qoder 替代能力：** 在 AI_API_Atlas 上通过 strict `repo-wiki verify --profile qoder-like --ci` 验证，达到 qoder 相同质量标准
2. **本地优先 Wiki 生成：** 为任意工程（无需 `.qoder` 目录）生成结构化 wiki 文档，输出到 `.repo-agent-eval/<run>/content/`
3. **增量更新：** 基于 git diff 实现页面级失效和增量 regeneration
4. **质量验证：** 内置 strict verify 门禁，包含 qoder-page-dumps、qoder-prose-density、qoder-stale-commit、qoder-content-empty、qoder-toc、qoder-citations、qoder-mermaid 等检查项

### 关键绩效指标（KPI）

| 指标编号 | 指标名称 | 目标值 | 衡量方式 |
|---------|---------|--------|---------|
| KPI-001 | Strict Verify 通过率 | 100% (13/13 checks) | `repo-wiki verify --profile qoder-like --ci` |
| KPI-002 | 页面生成数量 | 80-220 页（可配置） | manifest.json page_count |
| KPI-001 | 代理池支持 | OpenAI-compatible + Minimax | LLM provider abstraction |
| KPI-004 | 增量更新粒度 | 页面级（page-level invalidation） | git diff hash comparison |

---

## 用户角色与权限 [必填]

| 角色编号 | 角色名称 | 角色描述 | 权限范围 | 典型用户 |
|---------|---------|---------|---------|---------|
| ROLE-001 | 开发者 (Developer) | 使用 repo-wiki generate 生成文档 | 读写目标仓库，运行 CLI | 后端工程师 |
| ROLE-002 | DevOps/平台工程师 | 部署和配置 repo-wiki | 配置 LLM provider，维护运行 | Platform team |
| ROLE-003 | 技术写作者 | 审查和维护生成的文档 | 只读生成输出 | Technical writer |

---

## 功能范围 [必填]

### In Scope（包含的功能）

| 功能编号 | 功能名称 | 功能简述 | 优先级 |
|---------|---------|---------|--------|
| FEAT-001 | CLI 命令集 | init, index, update, verify, sync, search, graph, cost-estimate | P0 |
| FEAT-002 | Source-of-truth 产物 | repo-map.yaml, module-index.yaml, api-index.yaml, data-models.yaml | P0 |
| FEAT-003 | SQLite/FTS5 状态管理 | 本地操作状态、文本检索索引 | P0 |
| FEAT-004 | ChromaDB 向量存储 | 语义检索支持 | P1 |
| FEAT-005 | Module Graph | 模块级依赖和影响链 | P1 |
| FEAT-006 | Qoder-like 生成 | --profile qoder-like 输出到 `.repo-agent-eval/` | P0 |
| FEAT-007 | LLM Page Composer | 7 种页面类型，Mermaid 图表，质量 guardrails | P0 |
| FEAT-008 | Evidence Builder | File/line citations，symbol references | P1 |
| FEAT-009 | Strict Verify | qoder-like profile 的 13 项检查 | P0 |
| FEAT-010 | 增量更新 | Git-diff-based page invalidation | P1 |
| FEAT-011 | Generation State Machine | pending/running/completed/failed/retryable 状态跟踪 | P1 |
| FEAT-012 | Cost Estimator & Budget Gate | LLM 调用成本估算和预算控制 | P2 |
| FEAT-013 | Citation Relevance Verifier | 页面标题与引用相关性检查 | P2 |
| FEAT-014 | Low-confidence Fallback | 证据不足时生成 `待确认` 段落 | P2 |

### Out of Scope（不包含的功能）

- GraphML export
- Qdrant / FAISS / Lance 向量后端
- `repo-wiki serve` HTTP 服务
- `ownership.yaml` 所有权文件
- Per-module prompt fragment files（如 `module-<name>.txt`）
- Function-level global call graphs
- Dynamic skill synthesis beyond fixed templates
- 文档发布到 Confluence / Notion / Wiki 等外部平台

---

## 非功能要求 [必填]

### 性能要求

| 要求编号 | 要求项 | 目标指标 | 说明 |
|---------|--------|---------|------|
| NFR-001 | CLI 响应时间 | < 2s (不含 LLM 调用) | init, index, verify 等命令 |
| NFR-002 | LLM 生成吞吐量 | 取决于 API 限速 | 并发调度器控制 |
| NFR-003 | SQLite 查询延迟 | < 100ms | FTS5 检索 |

### 安全要求

| 要求编号 | 要求项 | 说明 |
|---------|--------|------|
| NFR-004 | 敏感信息过滤 | API keys, tokens, private keys 自动脱敏 [REDACTED] |
| NFR-005 | 输出隔离 | qoder-like 输出到 `.repo-agent-eval/` 不污染目标仓库 |
| NFR-006 | LLM Secret 管理 | 通过环境变量或 YAML 配置，CLI 不打印明文 |

### 可用性要求

| 要求编号 | 要求项 | 目标指标 | 说明 |
|---------|--------|---------|------|
| NFR-007 | 命令可用性 | `uv run repo-wiki --help` 必须成功 | 部署验证 |
| NFR-008 | 测试覆盖率 | Phase 28 后 1200+ tests pass | 回归防护 |

### 可扩展性要求

| 要求编号 | 要求项 | 说明 |
|---------|--------|------|
| NFR-009 | LLM Provider 抽象 | 支持 OpenAI-compatible 和 Minimax | Provider interface |
| NFR-010 | 模块化架构 | Scanner / IndexGraph / DocGen / AdapterGovernance / QualityRelease agents |

---

## 技术约束 [可选]

| 约束编号 | 约束项 | 约束内容 | 原因 |
|---------|--------|---------|------|
| TC-001 | 编程语言 | Python | 快速迭代和 AI 生态 |
| TC-002 | 数据库 | SQLite/FTS5 + ChromaDB | 本地优先，无需外部服务 |
| TC-003 | 部署环境 | 任意工程根目录（不含 `.qoder` 要求） | 通用性 |
| TC-004 | 包管理 | uv (Python package manager) | 项目规范 |
| TC-005 | LLM | OpenAI-compatible API / Minimax | 支持多种 provider |

---

## 假设前提汇总表 [必填]

| 假设编号 | 缺失信息项 | 假设内容 | 信心等级 | 待确认 |
|---------|-----------|---------|---------|--------|
| AS-001 | 目标仓库类型 | 假设目标为后端仓库（Python/Go/Java/TypeScript） | 高 | 否 |
| AS-002 | LLM API Key | 假设用户自行提供 API key，通过环境变量注入 | 高 | 否 |
| AS-003 | 输出位置 | qoder-like 固定输出到 `.repo-agent-eval/<run>/content/` | 高 | 否 |

---

## 待确认项汇总表 [必填]

| 编号 | 待确认内容 | 影响文档 | 优先级 |
|------|-----------|---------|--------|
| TBC-001 | 跨仓库泛化性 | 目前仅 AI_API_Atlas 验证 GO，其他仓库需更多 pilot | 低 |
| TBC-002 | 成本基准数据 | 真实 Minimax 成本曲线尚未在多仓库验证 | 低 |

---

## 关键干系人 [可选]

| 干系人角色 | 姓名/团队 | 职责 | 联系方式 |
|-----------|----------|------|---------|
| 项目负责人 | Agent_PlatformCore | 项目整体协调 | - |
| 技术负责人 | Agent_IndexGraph / Agent_DocGen | 架构和实现 | - |
| 产品负责人 | Agent_QualityRelease | GO/No-Go 决策，质量门禁 | - |

---

## 参考文档

> 详见 [requirements.md](./requirements.md) 功能需求定义。
> 详见 [design.md](./design.md) 系统设计定义。
> 详见 [tasks.md](./tasks.md) 交付任务定义。
>
> 原始项目信息：
> - APM Memory Root: `.apm/Memory/Memory_Root.md`
> - Implementation Plan: `.apm/Implementation_Plan.md`
> - GO Decision: `docs/go-no-go-dossier.md`