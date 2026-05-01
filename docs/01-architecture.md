# repo-agent - 系统架构

repo-agent 采用三层架构设计，将运行时存储层、结构化事实层和文档中心层分离。这种设计确保了知识的持久化、可追溯性和可读性的平衡。

## 系统分层

**第一层：运行时存储层 (`.repo-wiki/`)**
负责支撑系统运行时操作的临时状态存储。
- **索引存储** (SQLite + FTS): 全文搜索和精确查询
- **知识图谱** (JSON): 模块间依赖关系和影响链
- **向量缓存** (Chroma): 语义检索的向量表示
- **生成缓存**: 避免重复生成，节省计算资源
**为什么需要这一层？** 这一层处理的是高频变化的运行时状态，不适合与稳定的结构化事实混在一起。

**第二层：结构化事实层 (`ai/source-of-truth/`)**
代表系统的"真理之源"，记录扫描后沉淀的结构化信息。
- **module-index.yaml**: 所有模块的元信息（名称、路径、依赖、域分类）
- **api-index.yaml**: API 端点注册表（路径、方法、处理器）
- **data-models.yaml**: 数据模型定义（类型、字段、关系）
- **repo-map.yaml**: 仓库级元数据和命令注册表
**为什么需要这一层？** 事实需要稳定、可追溯、可验证。结构化格式支持机器消费（生成器、适配器、治理检查）和自动化处理。

**第三层：文档中心层 (`docs/`)**
真正面向读者（人或者 AI agent）的知识导航界面。
- **总览文档** (00-05): 快速定位和能力了解
- **专题文档** (sections/): 按业务主题聚合的相关内容
- **模块文档** (modules/): 单个模块的详细参考
**为什么需要这一层？** 源代码和结构化事实都不是面向读者的最优格式。文档中心通过选择性的信息呈现（而非全量导出）来提升可读性。

### 三层架构图

```mermaid
graph TB
    subgraph "Layer 1: Runtime Storage (.repo-wiki/)"
        R1[("Index Store<br/>(SQLite + FTS)")]
        R2[("Knowledge Graph<br/>(JSON)")]
        R3[("Vector Cache<br/>(Chroma)")]
        R4[("Generation Cache<br/>(SQLite)")]
    end

    subgraph "Layer 2: Source of Truth (ai/source-of-truth/)"
        S1["module-index.yaml<br/>Module Registry"]
        S2["api-index.yaml<br/>API Registry"]
        S3["data-models.yaml<br/>Data Model Registry"]
        S4["repo-map.yaml<br/>Repository Metadata"]
        S5["task-catalog.yaml<br/>Task Definitions"]
    end

    subgraph "Layer 3: Document Center (docs/)"
        D1["00-overview.md<br/>Project Overview"]
        D2["01-architecture.md<br/>System Design"]
        D3["03-module-map.md<br/>Module Map"]
        D4["docs/sections/<br/>Section Docs"]
        D5["docs/modules/<br/>Module Docs"]
        D6["docs/phases/<br/>Phase Docs"]
    end

    R1 --> S1
    R2 --> S2
    R3 --> S3
    S1 --> D1
    S2 --> D3
    S3 --> D3
    S1 --> D4
    S2 --> D4
    D1 --> D2
    D2 --> D4
    D4 --> D5
    D1 -.-> D6
```

## 服务协作关系

系统包含以下核心服务组件：
- **extensions** (API 服务器): Handles models instanceof, in.
- **repo_wiki** (API 服务器): Handles API routes /path.
- **scripts** (API 服务器): Handles exports AcceptanceEvidence, BaselineComparatorConfig.
- **tests** (API 服务器): Handles API routes /users, /users.

### 服务交互流程

```mermaid
sequenceDiagram
    participant Scanner
    participant Indexer
    participant Generator
    participant Adapter
    participant Docs

    Scanner->>Indexer: Scan repository
    Indexer->>Indexer: Extract modules, APIs, models
    Indexer->>Indexer: Build knowledge graph
    Indexer->>Indexer: Store index state

    Indexer->>Generator: Source of truth (module-index, etc.)
    Generator->>Generator: Generate overview docs
    Generator->>Generator: Generate section docs
    Generator->>Generator: Generate module docs
    Generator->>Docs: Write markdown files

    Adapter->>Adapter: Generate .claude/CLAUDE.md
    Adapter->>Adapter: Generate .codex/config.toml
```

## 核心链路

**代码扫描**：Scanner 遍历源代码，发现 4 个模块
**信息提取**：Indexer 从代码中提取 10 个 API 端点、44 个数据模型
**状态持久化**：索引状态、图谱关系、向量嵌入分别存储
**文档生成**：Generator 根据模板和事实数据生成 Markdown
**质量验证**：Verifier 检查文档结构和引用的有效性

### 数据流图

```mermaid
flowchart LR
    A[("Source Code<br/>Files")] --> B[("Scanner<br/>Extract")]
    B --> C[("Indexer<br/>Transform")]
    C --> D[("State Store<br/>Persist")]
    C --> E[("Graph Store<br/>Persist")]
    C --> F[("Vector Store<br/>Persist")]

    D --> G[("Source of Truth<br/>yaml/json")]
    G --> H[("Generator<br/>Template Render")]
    H --> I[("Document Center<br/>docs/")]

    F --> J[("Retrieval<br/>Query")]
    J --> H
```

## 存储与检索设计

系统采用多模态存储策略以支持不同的访问模式：

**向量存储 (Chroma)**：支持语义相似性搜索，当用户用自然语言查询时，系统将查询转换为向量，在已存储的代码块中寻找最相似的内容。

**全文索引 (SQLite FTS)**：支持精确的关键词匹配，当用户知道要查找的术语时，可以直接通过关键词找到所有包含该术语的代码位置。

**知识图谱 (JSON)**：支持结构化的依赖关系查询，例如查找某个模块的所有上游依赖，或者确定修改某段代码会影响到哪些其他模块。

### 存储层次说明

| 存储位置 | 职责 | 格式 |
|---------|------|------|
| `.repo-wiki/index/` | 操作知识底座 | SQLite (FTS) |
| `.repo-wiki/graph/` | 依赖关系和影响链 | JSON |
| `.repo-wiki/cache/` | 生成缓存 | SQLite + diskcache |
| `ai/source-of-truth/` | 结构化事实源 | YAML |

### 检索流程

```mermaid
flowchart TD
    A[("Query")] --> B{Retrieval Strategy}
    B -->|Vector Search| C[("Embedding<br/>Model")]
    C --> D[("Chroma<br/>Vector DB")]
    D --> E[("Top-K<br/>Results")]

    B -->|Keyword Search| F[("FTS<br/>Full-Text")]
    F --> E

    B -->|Graph Walk| G[("Knowledge<br/>Graph")]
    G --> E

    E --> H[("Context<br/>Builder")]
    H --> I[("LLM<br/>Generation")]
```

## 增量更新与治理闭环

${incremental_governance}

### 增量更新流程

```mermaid
flowchart TD
    A[("Git Change<br/>Detection")] --> B{Impact Analysis}
    B -->|Module Changed| C[("Expand Impacted<br/>Modules")]
    B -->|API Changed| D[("Update<br/>API Index")]
    B -->|Model Changed| E[("Update<br/>Model Index")]

    C --> F{Regeneration<br/>Needed?}
    F -->|Yes| G[("Regenerate<br/>Affected Docs")]
    F -->|No| H[("Skip<br/>Generation")]

    G --> I[("Verify<br/>Output Quality")]
    I -->|Pass| J[("Commit<br/>Documentation")]
    I -->|Fail| K[("Log<br/>Issue")]

    H --> J
```

### 治理检查点

- **模板覆盖**: 所有核心文档都有对应模板
- **契约验证**: 生成前验证 required_keys
- **Prose 约束**: 验证最小段落数和章节数
- **引用检查**: 验证文档间交叉引用有效性

## 模块概览

| extensions | core-platform | api-server | Handles models instanceof, in.... |
| repo_wiki | core-platform | api-server | Handles API routes /path.... |
| scripts | core-platform | api-server | Handles exports AcceptanceEvidence, BaselineCompar... |
| tests | core-platform | api-server | Handles API routes /users, /users.... |

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 语言 | Javascript | 主要实现语言 |
| 框架 | express | Web/应用框架 |
| 存储 | SQLite | 状态和缓存存储 |
| 向量 | Chroma | 语义检索向量数据库 |
