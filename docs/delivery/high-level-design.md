# repo-wiki MVP — 高级设计文档（High-Level Design）

**文档编号：** DOC-005
**版本：** v1.0.0
**创建日期：** 2026-05-03
**最后更新：** 2026-05-03

---

## 1. 系统架构

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                            │
│         repo-wiki init | index | generate | verify          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Orchestration Layer                       │
│   Service │ GenerationStateMachine │ GenerationScheduler    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Agent Layer                            │
│  ┌─────────┐  ┌──────────┐  ┌────────┐  ┌────────────────┐ │
│  │ Scanner │  │IndexGraph │  │ DocGen │  │AdapterGovernance│ │
│  └─────────┘  └──────────┘  └────────┘  └────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Storage Layer                          │
│     SQLite/FTS5      │      ChromaDB      │    Files       │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 数据流

```
Repository
    │
    ▼
┌─────────┐     ┌──────────┐     ┌────────┐     ┌──────────────┐
│ Scanner │────▶│IndexGraph│────▶│ DocGen │────▶│AdapterGovern.│
└─────────┘     └──────────┘     └────────┘     └──────────────┘
    │                │                │                  │
    ▼                ▼                ▼                  ▼
source-of-truth  SQLite/FTS5     LLM Composer      Output Layout
    YAML/JSON         +ChromaDB    (Markdown)     (.repo-agent-eval)
```

---

## 2. 核心组件设计

### 2.1 Scanner Agent

**职责：** 仓库扫描、信息提取

**子模块：**
- Traverser（文件遍历，.gitignore 过滤）
- LanguageDetector（语言/框架检测）
- ModuleDiscovery（模块发现）
- Extractor（API、数据模型、依赖提取）

**输出：** RepositorySnapshot → source-of-truth YAML/JSON

### 2.2 IndexGraph Agent

**职责：** 状态管理和检索

**子模块：**
- SQLiteState（操作状态，FTS5 索引）
- VectorIndex（ChromaDB 向量索引）
- ModuleGraph（依赖图，影响分析）
- RetrievalPipeline（检索 pipeline）

### 2.3 DocGen Agent

**职责：** 文档生成

**子模块：**
- PageComposer（LLM 页面生成）
- SkeletonBuilder（页面骨架，TOC）
- MermaidRenderer（Mermaid 图表）
- QualityGuardrails（质量守卫）
- Planner（页面规划：RuleFirst, LLMAssisted, Service, DataModel）

### 2.4 AdapterGovernance Agent

**职责：** 输出布局和验证

**子模块：**
- OutputLayout（输出目录管理）
- QoderStrictVerifier（13 项质量检查）
- QoderParityMetrics（与 Qoder 对比）
- CitationVerifier（引用验证）

### 2.5 QualityRelease Agent

**职责：** 质量发布决策

**子模块：**
- GoNoGoDossier（GO/No-Go 决策）
- GoldenFixtures（基准测试套件）
- TrendDashboard（趋势分析）

---

## 3. 关键流程

### 3.1 Qoder-like 生成流程

```
1. Service.generate(qoder-like profile)
   │
   ▼
2. Load manifest (WikiPlanManifest)
   │
   ▼
3. For each page in manifest:
   │
   ├── a) Load evidence (PageEvidenceScorer)
   │
   ├── b) Compose with LLM (PageComposer)
   │
   ├── c) Quality check (QualityGuardrails)
   │       │
   │       └── If FAIL → retry or mark retryable
   │
   └── d) Write to .repo-agent-eval/<run>/content/
   │
   ▼
4. Update manifest (nav tree, git commit)
   │
   ▼
5. Return GenerationResult
```

### 3.2 Incremental Update 流程

```
1. Service.update()
   │
   ▼
2. Compute git diff hash
   │
   ▼
3. PageInvalidationEngine.analyze(diff_hash)
   │
   ▼
4. Kahn's algorithm topological sort
   │
   ▼
5. Re-generate only invalidated pages
   │
   ▼
6. Update SQLite + manifest
```

### 3.3 Strict Verify 流程

```
1. QoderLikeVerifierService.verify(output_dir)
   │
   ▼
2. For each check in STRICT_HARD_CODES:
   │
   ├── qoder-page-dumps
   ├── qoder-prose-density
   ├── qoder-stale-commit
   ├── qoder-content-empty
   ├── qoder-toc
   ├── qoder-citations
   ├── qoder-mermaid
   ├── qoder-api-aggregation
   ├── qoder-dm-aggregation
   ├── qoder-citation-relevance
   ├── qoder-dirty-worktree
   │
   ▼
3. Aggregate results → VerifyResult
   │
   ▼
4. If HARD gate FAIL → grade: FAIL, exit_code: non-zero
```

---

## 4. 扩展性设计

### 4.1 LLM Provider 扩展

新增 Provider 只需：
1. 实现 `LLMClient` Protocol
2. 在 `resolve_qoder_like_llm()` 注册
3. 添加配置支持

### 4.2 Page Type 扩展

新增页面类型：
1. 在 `PageType` enum 添加新类型
2. 创建对应的 prompt template
3. 添加 SkeletonBuilder support

### 4.3 Verifier Check 扩展

新增检查项：
1. 在 `STRICT_HARD_CODES` 添加 reason code
2. 实现 `_check_xxx()` 方法
3. 添加测试用例

---

## 5. 参考文档

> 详见 [design.md](./spec/design.md) 概要设计。
> 详见 [api-spec.md](./api-spec.md) API 规范。
> 详见 [database-design.md](./database-design.md) 数据库设计。