# repo-wiki MVP — 概要设计文档（Design）

**文档编号：** DES-001
**版本：** v1.0.0
**创建日期：** 2026-05-03
**最后更新：** 2026-05-03

---

## 1. 系统架构概述

repo-wiki 采用分层架构，包含以下核心组件：

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                           │
│  init | index | update | generate | verify | search | ...  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Orchestration Layer                      │
│  Service | GenerationState | GenerationScheduler | Cost    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Agent Layer                            │
│  Scanner │ IndexGraph │ DocGen │ AdapterGovernance │ QA    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Storage Layer                          │
│    SQLite/FTS5    │    ChromaDB    │    File System         │
└─────────────────────────────────────────────────────────────┘
```

### 1.1 分层职责

| 层级 | 组件 | 职责 |
|------|------|------|
| CLI | repo_wiki/cli.py | 命令解析，入口点 |
| Orchestration | service.py, generation_*.py | 生成流程编排，状态管理 |
| Agent | Scanner, IndexGraph, DocGen, AdapterGovernance, QualityRelease | 各自领域实现 |
| Storage | SQLite, ChromaDB, File System | 状态持久化，向量存储，产物输出 |

---

## 2. 主要模块划分

### 2.1 Scanner Agent

**模块路径：** `repo_wiki/scanner/`

| 文件 | 职责 |
|------|------|
| `traverser.py` | 仓库遍历，.gitignore 过滤 |
| `language_detector.py` | 语言/框架检测 |
| `module_discovery.py` | 模块发现 (Python/Go/TS) |
| `extractor.py` | API/数据模型/依赖提取 |

### 2.2 IndexGraph Agent

**模块路径：** `repo_wiki/indexer/`, `repo_wiki/graph/`

| 文件 | 职责 |
|------|------|
| `sqlite_state.py` | SQLite/FTS5 状态管理 |
| `vector_index.py` | ChromaDB 向量索引 |
| `module_graph.py` | 模块依赖图 |
| `retrieval.py` | 检索 pipeline |

### 2.3 DocGen Agent

**模块路径：** `repo_wiki/generator/`, `repo_wiki/planner/`

| 文件 | 职责 |
|------|------|
| `page_composer.py` | LLM Page Composer |
| `skeleton_builder.py` | 页面骨架构建 |
| `mermaid_renderer.py` | Mermaid 图表渲染 |
| `quality_guardrails.py` | 质量 guardrails |
| `planner/*.py` | 各类 planner (rule-first, LLM-assisted, service, data-model) |

### 2.4 AdapterGovernance Agent

**模块路径：** `repo_wiki/adapter/`, `repo_wiki/verifier/`

| 文件 | 职责 |
|------|------|
| `output_layout.py` | 输出布局管理 |
| `qoder_strict_verifier.py` | Strict verify (13 checks) |
| `qoder_parity_metrics.py` | Qoder parity metrics |
| `citation_verifier.py` | Citation verification |

### 2.5 QualityRelease Agent

**模块路径：** `repo_wiki/quality/`, `repo_wiki/release/`

| 文件 | 职责 |
|------|------|
| `go_no_go_dossier.py` | GO/No-Go 决策文档 |
| `golden_fixtures.py` | Golden fixture suite |
| `trend_dashboard.py` | 趋势 dashboard |

---

## 3. 核心接口定义

### 3.1 LLM Provider Interface

```python
class LLMClient(Protocol):
    def chat(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        """Send chat request to LLM provider"""
        ...

class ChatMessage(NamedTuple):
    role: str  # "system", "user", "assistant"
    content: str

@dataclass
class ChatResponse:
    content: str
    usage: UsageInfo
    model: str
    provider: str
```

### 3.2 Page Composer Interface

```python
@dataclass
class ComposerInput:
    page_type: PageType  # overview, architecture, api, data_model, etc.
    topic: str
    context: dict[str, Any]
    evidence: list[EvidenceSpan]

@dataclass
class ComposerOutput:
    content: str
    citations: list[Citation]
    mermaid_diagrams: list[MermaidDiagram]
    low_confidence: bool = False
    uncertainty_reasons: list[str] = field(default_factory=list)
```

### 3.3 Verifier Interface

```python
@dataclass
class VerifyResult:
    grade: str  # "PASS", "FAIL", "WARN"
    exit_code: int
    reason_codes: dict[str, int]  # reason_code -> count
    gate_summary: GateSummary

class QoderLikeVerifierService:
    def verify(self, output_dir: Path, profile: str) -> VerifyResult:
        ...
```

---

## 4. 数据模型概要

### 4.1 SQLite Schema (Operational State)

| 表 | 用途 |
|---|------|
| `generation_runs` | 生成运行状态 |
| `page_generation_states` | 页面级状态跟踪 |
| `doc_hierarchy` | 文档层级结构 |
| `nav_graph` | 导航图 |
| `evidence_span` | 证据跨度 |
| `verify_runs` | 验证运行记录 |

### 4.2 Source-of-truth Artifacts

| 文件 | Schema |
|------|--------|
| `repo-map.yaml` | RepositorySnapshot |
| `module-index.yaml` | Module[] |
| `api-index.yaml` | Endpoint[] |
| `data-models.yaml` | DataModel[] |

### 4.3 Qoder-like Output

```
.repo-agent-eval/<run-id>/
├── content/           # Markdown 文件
│   ├── index.md
│   └── ...
├── manifest.json      # WikiPlanManifest
└── reports/           # Verify reports
    └── strict-verify-output.json
```

---

## 5. 集成点说明

### 5.1 LLM Provider Integration

| Provider | 实现 | 配置 |
|----------|------|------|
| OpenAI-compatible | `OpenAIClient` | base_url, api_key |
| Minimax | `MinimaxClient` | base_url, api_key |

### 5.2 Git Integration

- HEAD commit hash 记录到 manifest
- `git status --porcelain` 检测 dirty worktree
- `git diff` 触发 page-level invalidation

### 5.3 Target Repository

- **扫描范围：** 任意工程目录（无需 `.qoder`）
- **输出隔离：** `--profile qoder-like` 输出到 `.repo-agent-eval/`
- **保护机制：** `.qoder/`, `.repo-wiki/`, `docs/` 默认不被修改

---

## 6. 关键设计决策

### 6.1 Local-first 架构

所有状态存储在本地 SQLite，不依赖外部服务。向量检索使用 ChromaDB（嵌入式）。

### 6.2 Generator Agent Abstraction

Phase 22-26 的 specialized generators (API, DataModel) 通过统一的 `ComposerOutput` 接口输出，保证下游处理一致性。

### 6.3 Evidence Citation

Evidence Builder (Phase 23) 提供 file/line citations，Citation Verifier (Phase 33) 验证引用相关性，双层防护 hallucination。

### 6.4 Incremental Update

基于 git diff hash 的 page-level invalidation，避免全量重生成。

---

## 7. 参考文档

> 详见 [spec.md](./spec.md) 项目规格定义。
> 详见 [requirements.md](./requirements.md) 功能需求定义。
> 详见 [tasks.md](./tasks.md) 交付任务定义。