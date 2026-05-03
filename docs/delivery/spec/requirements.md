# repo-wiki MVP — 功能需求文档（Requirements）

**文档编号：** REQ-001
**版本：** v1.0.0
**创建日期：** 2026-05-03
**最后更新：** 2026-05-03

---

## 1. 概述

本文档定义 repo-wiki MVP 功能需求，共 35 个 Phase 的完整实现记录。所有需求来源于 APM Implementation Plan。

---

## 2. REQ-001: CLI 命令集

**描述：** 提供完整的命令行接口，支持 init、index、update、verify、sync、search、graph、cost-estimate 等命令。

**优先级：** P0
**相关用户角色：** Developer, DevOps/Platform Engineer
**验收条件：**
- [x] `uv run repo-wiki --help` 成功输出
- [x] `uv run repo-wiki generate --profile qoder-like --run-id <id>` 生成文档
- [x] `uv run repo-wiki verify --profile qoder-like --ci --output <run>` 验证质量

---

## 3. REQ-002: Source-of-truth 产物

**描述：** 扫描仓库生成结构化 YAML/JSON 产物：repo-map.yaml、module-index.yaml、api-index.yaml、data-models.yaml。

**优先级：** P0
**相关用户角色：** Developer
**验收条件：**
- [x] 产物符合 MVP schema 定义
- [x] 确定性输出（相同输入产生相同输出）
- [x] Schema 验证通过

---

## 4. REQ-003: SQLite/FTS5 状态管理

**描述：** 使用 SQLite 作为本地操作状态存储，支持 FTS5 全文检索。

**优先级：** P0
**相关用户角色：** Developer, DevOps/Platform Engineer
**验收条件：**
- [x] 状态持久化到 `.repo-wiki/` 目录
- [x] WAL mode 支持并发读单 writer
- [x] FTS5 检索延迟 < 100ms

---

## 5. REQ-004: ChromaDB 向量存储

**描述：** 语义向量索引，支持语义检索。

**优先级：** P1
**相关用户角色：** Developer
**验收条件：**
- [ ] 向量存储实现
- [ ] 语义检索 pipeline

---

## 6. REQ-005: Module Graph

**描述：** 模块级依赖图和影响链分析。

**优先级：** P1
**相关用户角色：** Developer
**验收条件：**
- [x] 依赖边提取 (depends_on / depended_by)
- [x] 影响传播分析

---

## 7. REQ-006: Qoder-like 生成

**描述：** 支持 `--profile qoder-like` 输出模式，隔离输出到 `.repo-agent-eval/<run>/content/`。

**优先级：** P0
**相关用户角色：** Developer
**验收条件：**
- [x] 不修改目标仓库的 `.qoder`、`docs/` 等目录
- [x] 输出 manifest.json 和 navigation tree
- [x] 支持 80-220 页生成（可配置）

---

## 8. REQ-007: LLM Page Composer

**描述：** 7 种页面类型（Overview、Architecture、API Reference、Data Model、Operations、Development、Security），支持 Mermaid 图表生成。

**优先级：** P0
**相关用户角色：** Developer
**验收条件：**
- [x] 7 种 page prompt contracts
- [x] Skeleton builder with TOC
- [x] Mermaid diagram planner/renderer (6 types)
- [x] Quality guardrails (7 checks)
- [x] Incremental cache with input/output hashing

---

## 9. REQ-008: Evidence Builder

**描述：** 支持 file/line citations 和 symbol references，为页面提供证据追溯。

**优先级：** P1
**相关用户角色：** Developer
**验收条件：**
- [x] Source span extractor (Java/Python/TypeScript/SQL/YAML/Markdown)
- [x] Evidence SQLite schema (evidence_span, page_source_map, symbol_reference)
- [x] Citation block renderer
- [x] Citation verifier (WARN/FAIL gates)

---

## 10. REQ-009: Strict Verify

**描述：** 13 项严格质量门禁检查。

**优先级：** P0
**相关用户角色：** Developer, Technical Writer
**验收条件：**
- [x] qoder-page-dumps: 无列表过重页面
- [x] qoder-prose-density: prose 密度 >= 30%
- [x] qoder-stale-commit: git commit 最新
- [x] qoder-content-empty: 内容非空
- [x] qoder-toc: 有目录
- [x] qoder-citations: 有引用
- [x] qoder-mermaid: 有图表
- [x] qoder-api-aggregation: API 聚合质量
- [x] qoder-dm-aggregation: Data model 聚合质量
- [x] qoder-citation-relevance: 引用相关性
- [x] qoder-dirty-worktree: 工作树干净
- [x] grade PASS / exit code 0

---

## 11. REQ-010: 增量更新

**描述：** 基于 git diff 实现页面级失效和增量 regeneration。

**优先级：** P1
**相关用户角色：** Developer
**验收条件：**
- [x] PageInvalidationEngine with Kahn's algorithm
- [x] Git diff hash comparison
- [x] 选择性重生成

---

## 12. REQ-011: Generation State Machine

**描述：** 生成运行状态跟踪，支持中断恢复。

**优先级：** P1
**相关用户角色：** Developer
**验收条件：**
- [x] 状态: pending / running / completed / failed / retryable
- [x] 页面级状态跟踪
- [x] resume_run() 支持

---

## 13. REQ-012: Cost Estimator & Budget Gate

**描述：** LLM 调用成本估算和预算控制。

**优先级：** P2
**相关用户角色：** DevOps/Platform Engineer
**验收条件：**
- [ ] Cost estimation per page/composition
- [ ] Budget gate before LLM calls

---

## 14. REQ-013: Citation Relevance Verifier

**描述：** 页面标题与引用文件路径的相关性检查。

**优先级：** P2
**相关用户角色：** Developer
**验收条件：**
- [x] High-confidence mismatch → FAIL
- [x] Shared infrastructure → WARN
- [x] QODER_CITATION_RELEVANCE_MISMATCH reason code

---

## 15. REQ-014: Low-confidence Fallback

**描述：** 证据不足时生成 `待确认` 段落，禁止编造实现细节。

**优先级：** P2
**相关用户角色：** Developer
**验收条件：**
- [x] ComposerOutput.low_confidence flag
- [x] `待确认` section generation
- [x] Prohibit fabrication in low-confidence pages

---

## 16. REQ-015: Service Subtopic Planner

**描述：** 服务文档细分为多个子主题（服务概述、架构设计、API接口文档、部署配置、核心组件）。

**优先级：** P1
**相关用户角色：** Developer
**验收条件：**
- [x] 5 种服务子主题类型
- [x] Navigation ordering preservation
- [x] Service subtopic expansion tests

---

## 17. REQ-016: Data-model Entity Topic Planner

**描述：** 数据模型文档细分为 entity、migration、table-structure、index-performance、audit、security 等主题。

**优先级：** P1
**相关用户角色：** Developer
**验收条件：**
- [x] 6 种数据模型主题类别
- [x] Duplicate page guard
- [x] Entity drill-down links

---

## 18. REQ-017: Module Hierarchy Planner

**描述：** 4 层目录深度的项目概览模块层级。

**优先级：** P1
**相关用户角色：** Developer
**验收条件：**
- [x] Directory depth target: 4
- [x] Qoder path common count toward 80
- [x] Page count ratio 90%-120% of Qoder baseline

---

## 19. REQ-018: Service Ownership Resolver

**描述：** 基于模块路径、包名、端口等确定服务归属，防止跨服务错误绑定。

**优先级：** P2
**相关用户角色：** Developer
**验收条件：**
- [x] Infrastructure service detection (GitLab, Jenkins, MCP, etc.)
- [x] AI service pattern recognition
- [x] Confidence scoring with rejection reasons

---

## 20. REQ-019: Page Evidence Scoring

**描述：** 多维证据评分模型（title、slug、domain、runtime role、API、data-model）。

**优先级：** P2
**相关用户角色：** Developer
**验收条件：**
- [x] Multi-dimensional scoring
- [x] Top-N evidence storage
- [x] Rejection reasons persistence

---

## 21. REQ-020: LLM Provider Abstraction

**描述：** 支持 OpenAI-compatible 和 Minimax provider 的统一接口。

**优先级：** P0
**相关用户角色：** DevOps/Platform Engineer
**验收条件：**
- [x] LLMClient interface
- [x] OpenAI-compatible provider
- [x] Minimax provider
- [x] Token budgeting/retry/cache policy
- [x] CLI diagnostics (repo-wiki config)

---

## 22. REQ-021: API Reference Specialization

**描述：** API 清单富化、service-family 分组、prose-first articles、auth/error convention、flow diagrams。

**优先级：** P1
**相关用户角色：** Developer, Technical Writer
**验收条件：**
- [x] API inventory enrichment (service_family, auth, request/response metadata)
- [x] API topic planner (15+ pages grouped by service family)
- [x] Service-family API composer
- [x] API quality verifier (AGG_API_NOT_GROUPED, AGG_API_ENDPOINT_DUMP reason codes)

---

## 23. REQ-022: Data Model Specialization

**描述：** 实体解析、数据库迁移提取、ER diagrams、data model quality verifier。

**优先级：** P1
**相关用户角色：** Developer, Technical Writer
**验收条件：**
- [x] Canonical model resolver (core entity/DTO/RequestResponse)
- [x] Database migration extractor (SQL/Alembic)
- [x] Data model topic planner (10+ pages)
- [x] Data model quality verifier (AGG_DM_MODEL_DUMP, AGG_DM_NOT_GROUPED)

---

## 24. 需求汇总表

| REQ-XXX | 需求名称 | 优先级 | 实现状态 |
|---------|---------|--------|---------|
| REQ-001 | CLI 命令集 | P0 | ✅ Done |
| REQ-002 | Source-of-truth 产物 | P0 | ✅ Done |
| REQ-003 | SQLite/FTS5 状态管理 | P0 | ✅ Done |
| REQ-004 | ChromaDB 向量存储 | P1 | ⚠️ Partial |
| REQ-005 | Module Graph | P1 | ✅ Done |
| REQ-006 | Qoder-like 生成 | P0 | ✅ Done |
| REQ-007 | LLM Page Composer | P0 | ✅ Done |
| REQ-008 | Evidence Builder | P1 | ✅ Done |
| REQ-009 | Strict Verify | P0 | ✅ Done |
| REQ-010 | 增量更新 | P1 | ✅ Done |
| REQ-011 | Generation State Machine | P1 | ✅ Done |
| REQ-012 | Cost Estimator & Budget Gate | P2 | ⚠️ Partial |
| REQ-013 | Citation Relevance Verifier | P2 | ✅ Done |
| REQ-014 | Low-confidence Fallback | P2 | ✅ Done |
| REQ-015 | Service Subtopic Planner | P1 | ✅ Done |
| REQ-016 | Data-model Entity Topic Planner | P1 | ✅ Done |
| REQ-017 | Module Hierarchy Planner | P1 | ✅ Done |
| REQ-018 | Service Ownership Resolver | P2 | ✅ Done |
| REQ-019 | Page Evidence Scoring | P2 | ✅ Done |
| REQ-020 | LLM Provider Abstraction | P0 | ✅ Done |
| REQ-021 | API Reference Specialization | P1 | ✅ Done |
| REQ-022 | Data Model Specialization | P1 | ✅ Done |

---

## 25. 参考文档

> 详见 [spec.md](./spec.md) 项目规格定义。
> 详见 [design.md](./design.md) 系统设计定义。
> 详见 [tasks.md](./tasks.md) 交付任务定义。