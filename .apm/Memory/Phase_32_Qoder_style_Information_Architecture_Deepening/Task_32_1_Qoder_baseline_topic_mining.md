---
task_ref: "Task 32.1 - Qoder baseline topic mining"
status: "completed"
date: "2026-05-03"
agent: "Agent_QualityRelease"
---

# Task 32.1: Qoder Baseline Topic Mining Report

## Baseline Source
- **Path**: `/Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas/.qoder/repowiki/zh/content`
- **Mode**: Read-only (DO NOT modify)
- **Completion Rule**: Qoder baseline remains unmodified

## Baseline Structure Statistics

| Metric | Value |
|--------|-------|
| Top-level directories | 8 |
| Total directories | 30 |
| Total markdown files | 180 |
| Maximum depth | 15 levels |
| Content size | ~54KB (metadata files) |

## 1. Generalized Topic Taxonomy

### Level 1 - Domain Categories (3 primary)

| Category | Sub-categories | File Count | Depth Range |
|----------|----------------|------------|-------------|
| **项目概览** (Overview) | 项目概述、快速开始 | ~70 | 12-14 |
| **技术实现** (Implementation) | Python服务、核心服务、API参考 | ~58 | 12-15 |
| **支撑体系** (Support) | 架构设计、开发指南、数据模型 | ~52 | 12-14 |

### Level 2 - Service Taxonomies

**Python Services (27 files, 4 services)**:
- TCSL生成服务 (7 files): 服务概述, 部署与配置, 模板引擎, 适配器与映射器, 维度生成器, 验证器与API接口
- 场景编排服务 (6 files): 场景编排服务, 场景生成器, 工作流引擎, 流程DSL处理, 场景定义与管理, 能力执行器
- 文档解析服务 (7 files): 服务概述, 文档解析器, 语义增强器, 架构设计, API接口文档, 部署配置
- 自然语言转DSL服务 (6 files): 服务概述与架构, NLP转换API接口, 工作流生成引擎, 提示工程与验证, 上下文与模板系统

**Core Services (13 files)**:
- AI服务能力API, API台账服务API, 契约管理服务API, 执行引擎服务API, 质量门禁服务API, 差异分析服务API

**Data Models (44 files, hierarchical)**:
- 核心数据模型 (7 files)
- 服务数据模型 (28 files): AI服务能力数据模型, API台账服务数据模型, 契约服务数据模型, 执行服务数据模型
- 数据库架构 (5 files)

### Level 3 - Document Type Patterns

| Pattern | Example | Count |
|---------|---------|-------|
| `<Service>概述/概览` | 服务概述、服务概览 | ~8 |
| `<Service>部署与配置` | 部署与配置、部署配置 | ~4 |
| `<Service>架构设计` | 架构设计、架构总览 | ~6 |
| `<Component>引擎` | 工作流引擎、模板引擎 | ~3 |
| `<Feature>管理` | 场景定义与管理、生命周期管理 | ~5 |
| `<Aspect>API接口` | 验证器与API接口、NLP转换API接口 | ~4 |

## 2. Path Pattern Report

### Pattern A: Flat Service Doc (最浅层)
```
<Category>/<Service>.md
```
- Example: `Python服务/Python服务.md`
- Depth: 12
- Files: 8

### Pattern B: Service + DocType
```
<Category>/<Service>/<DocType>.md
```
- Example: `Python服务/TCSL生成服务/服务概述.md`
- Depth: 13
- Files: ~45

### Pattern C: Service + Component + DocType
```
<Category>/<Service>/<Component>/<DocType>.md
```
- Example: `Python服务/场景编排服务/工作流引擎.md`
- Depth: 14
- Files: ~25

### Pattern D: Project Overview Flat
```
项目概述/模块组织结构/<Module>/<Feature>.md
```
- Example: `项目概述/模块组织结构/AI服务能力/AI服务能力.md`
- Depth: 14
- Files: ~40

### Pattern E: Deep Nested Service
```
数据模型/服务数据模型/<Service>数据模型/<Aspect>.md
```
- Example: `数据模型/服务数据模型/API台账服务数据模型/元数据管理模型.md`
- Depth: 15
- Files: ~28

### Depth Distribution

| Depth | Directory | File Count |
|-------|-----------|------------|
| 12 | content, API参考, Python服务, etc. | ~175 |
| 13 | Python服务API, TCSL生成服务, etc. | ~25 |
| 14 | AI服务能力, API台账服务, etc. | ~20 |
| 15 | OpenAPI解析引擎 | 1 |

## 3. Comparison Gap Notes

### Gap 1: Depth Imbalance
- **Issue**: Project overview pages are shallow (depth 12-13) while data models are deep (14-15)
- **Impact**: Navigation inconsistency between overview and technical docs
- **Recommendation**: Standardize depth for similar content types

### Gap 2: Naming Inconsistency
| Pattern | Used Terms |
|---------|-----------|
| Overview pages | "概述" (8), "概览" (3), "总览" (2) |
| Service root | "服务" (4), "服务.md" (1) |
| Component pages | Mixed: 引擎/器, 管理/处理 |

### Gap 3: Module Boundary Clarity
- **Issue**: "核心服务" contains 6 distinct service types without clear grouping
- **Impact**: Makes navigation and discovery harder
- **Recommendation**: Add intermediate grouping (e.g., `核心服务/AI能力/`, `核心服务/治理/`)

### Gap 4: Content Distribution Inequality
| Category | Files | Average per Sub-dir |
|----------|-------|---------------------|
| 项目概述 | 62 | ~8 per sub-dir |
| 数据模型 | 44 | ~5 per sub-dir |
| 架构设计 | 5 | ~1 per sub-dir |
| 开发指南 | 6 | ~1 per sub-dir |

### Gap 5: Cross-cutting Concerns
- **Issue**: Topics like "安全"、"监控"、"部署" appear in multiple places
- **Current**: Scattered across 服务概述, 项目概述, 独立文件
- **Recommendation**: Consider extracting as shared topics

### Gap 6: API Reference Flatness
- **Issue**: API docs are all at depth 12-13 with similar structure
- **Impact**: Doesn't reflect actual API hierarchy
- **Recommendation**: Mirror actual API structure (e.g., `API参考/核心服务API/契约管理/端点.md`)

## 4. Reusable Patterns Identified

### Document Template Pattern
Each doc page follows a consistent structure:
1. Title with `<cite>` block referencing source files
2. Table of Contents (目录)
3. Numbered sections (简介, 项目结构, 核心组件, etc.)
4. Mermaid diagrams
5. Conclusion and appendix sections

### Service Documentation Pattern
```
Service Root (概述/概览页)
├── 部署与配置
├── 架构设计
├── API接口
└── [Component-specific pages]
```

### Data Model Documentation Pattern
```
数据模型
├── 核心数据模型 (shared entities)
├── 服务数据模型/<Service>
│   ├── <Service>数据模型.md
│   └── <Aspect>模型.md
└── 数据库架构
```

## 5. Self-Test Verification

**Command**: `uv run repo-wiki --help`
**Result**: PASS - repo-wiki commands available

**Command**: `uv run pytest tests/test_qoder_comparator_paths.py tests/test_qoder_parity_metrics.py`
**Result**: PASS - 43 tests passed

## 6. Qoder Baseline Integrity Check

- [x] Baseline directory accessed read-only
- [x] No files modified
- [x] No new files created in baseline
- [x] Self-tests passed

---
**Status**: COMPLETED
**Agent**: Agent_QualityRelease
**Completed**: 2026-05-03