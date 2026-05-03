# repo-wiki MVP — 验收清单（Acceptance Checklist）

**文档编号：** DOC-014
**版本：** v1.0.0
**创建日期：** 2026-05-03
**最后更新：** 2026-05-03

---

## 1. 项目信息

| 属性 | 内容 |
|------|------|
| 项目名称 | repo-wiki MVP |
| 替代目标 | Qoder Repo Wiki (Atlas) |
| GO 决策日期 | 2026-05-02 |
| 验证基准 | AI_API_Atlas strict verify (13/13 PASS) |

---

## 2. 功能验收

### 2.1 核心功能

- [x] **CLI 命令集**：`init`, `index`, `generate`, `verify`, `update`, `search`, `graph`, `cost-estimate`
- [x] **Source-of-truth 产物**：repo-map.yaml, module-index.yaml, api-index.yaml, data-models.yaml
- [x] **SQLite/FTS5 状态**：状态持久化，全文检索
- [x] **ChromaDB 向量存储**：语义检索支持
- [x] **Module Graph**：依赖图，影响分析
- [x] **LLM Provider 抽象**：OpenAI-compatible, Minimax

### 2.2 Qoder-like 生成

- [x] **隔离输出**：`.repo-agent-eval/<run>/content/`
- [x] **Manifest**：WikiPlanManifest with nav tree
- [x] **保护路径**：`.qoder/`, `.repo-wiki/`, `docs/` 默认不修改
- [x] **Page Count**：24-220 可配置

### 2.3 LLM Page Composer

- [x] **7 种页面类型**：Overview, Architecture, API, Data Model, Operations, Development, Security
- [x] **Mermaid 图表**：6 种图表类型
- [x] **质量 Guardrails**：7 项检查
- [x] **增量缓存**：input/output hash

### 2.4 Evidence & Citation

- [x] **Source Span Extractor**：Java/Python/TypeScript/SQL/YAML/Markdown
- [x] **Evidence SQLite**：evidence_span, page_source_map, symbol_reference
- [x] **Citation Verifier**：WARN/FAIL gates

### 2.5 Strict Verify

- [x] **13 项检查**：qoder-page-dumps, qoder-prose-density, qoder-stale-commit, qoder-content-empty, qoder-toc, qoder-citations, qoder-mermaid, qoder-api-aggregation, qoder-dm-aggregation, qoder-citation-relevance, qoder-dirty-worktree, qoder-broken-links, qoder-page-count
- [x] **Grade PASS**：13/13 checks
- [x] **Exit code 0**：CI 友好

---

## 3. 质量验收

### 3.1 测试覆盖率

- [x] Phase 28 后 1200+ tests pass
- [x] 各 Phase 回归测试通过

### 3.2 GO 决策验证

- [x] AI_API_Atlas strict verify PASS
- [x] QODER_PAGE_DUMP: PASS (3 pages rewritten)
- [x] QODER_CONTENT_EMPTY: PASS (SQLite path normalization)
- [x] QODER_PROSE_TOO_LOW: PASS (2 pages repaired)
- [x] QODER_STALE_GIT_COMMIT: PASS
- [x] QODER_DIRTY_WORKTREE: PASS (new gate)

---

## 4. 文档完整性

- [x] **spec.md**：项目规格文档
- [x] **requirements.md**：功能需求
- [x] **design.md**：概要设计
- [x] **tasks.md**：任务拆解（Phase 1-35 记录）
- [x] **project-overview.md**：项目概览
- [x] **deployment-guide.md**：部署指南
- [x] **user-manual.md**：用户手册
- [x] **functional-spec.md**：功能规格
- [x] **high-level-design.md**：高级设计
- [x] **api-spec.md**：API 规范
- [x] **database-design.md**：数据库设计
- [x] **configuration-guide.md**：配置指南
- [x] **operations-runbook.md**：运维手册
- [x] **incident-response-runbook.md**：应急响应
- [x] **logging-guide.md**：日志指南
- [x] **security-auth-guide.md**：安全指南
- [x] **third-party-integration.md**：第三方集成
- [x] **acceptance-checklist.md**：本验收清单

---

## 5. 一致性检查

### 5.1 术语一致性

- [ ] 文档中使用统一的术语表
- [ ] 无同名不同义现象

### 5.2 接口一致性

- [ ] api-spec.md 与 functional-spec.md 一致
- [ ] api-spec.md 与 design.md 一致

### 5.3 数据库一致性

- [ ] database-design.md 与实际 SQLite schema 一致

### 5.4 部署一致性

- [ ] deployment-guide.md 与 operations-runbook.md 一致
- [ ] deployment-guide.md 与 configuration-guide.md 一致

---

## 6. 签署

| 角色 | 姓名 | 日期 | 签名 |
|------|------|------|------|
| 项目负责人 | | | |
| 技术负责人 | | | |
| 产品负责人 | | | |
| 质量负责人 | | | |

---

## 7. 参考文档

> 详见 [project-overview.md](./project-overview.md) 项目概览。
> 详见 [go-no-go-dossier.md](./go-no-go-dossier.md) GO 决策文档。
> 详见 APM Memory Root: `.apm/Memory/Memory_Root.md`