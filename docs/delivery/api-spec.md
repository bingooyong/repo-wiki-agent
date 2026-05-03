# repo-wiki MVP — API 规范（API Spec）

**文档编号：** DOC-006
**版本：** v1.0.0
**创建日期：** 2026-05-03
**最后更新：** 2026-05-03

---

## 1. CLI API

### 1.1 repo-wiki init

```bash
repo-wiki init [OPTIONS]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `--force` | flag | 强制重新初始化 |

### 1.2 repo-wiki generate

```bash
repo-wiki generate [OPTIONS]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `--profile` | enum | `standard`, `qoder-like` |
| `--run-id` | string | 运行 ID |
| `--config` | path | 配置文件路径 |
| `--llm-model` | string | LLM 模型名称 |
| `--max-pages` | int | 最大页面数 (默认 220) |
| `--min-pages` | int | 最小页面数 (默认 24) |
| `--concurrency` | int | 并发数 |

### 1.3 repo-wiki verify

```bash
repo-wiki verify [OPTIONS]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `--profile` | enum | `standard`, `transitional`, `qoder-like` |
| `--ci` | flag | CI 模式 |
| `--output` | string | 运行 ID |

### 1.4 repo-wiki update

```bash
repo-wiki update [OPTIONS]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `--profile` | string | profile 名称 |
| `--run-id` | string | 运行 ID |

### 1.5 repo-wiki search

```bash
repo-wiki search <QUERY> [OPTIONS]
```

### 1.6 repo-wiki graph

```bash
repo-wiki graph [OPTIONS]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `--format` | enum | `text`, `mermaid`, `dot` |
| `--output` | path | 输出文件 |

### 1.7 repo-wiki cost-estimate

```bash
repo-wiki cost-estimate [OPTIONS]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `--profile` | string | profile 名称 |
| `--pages` | int | 预估页面数 |

---

## 2. Python Module API

### 2.1 LLM Provider

```python
from repo_wiki.llm.base import LLMClient, ChatMessage, ChatResponse

# 初始化
client: LLMClient = resolve_qoder_like_llm(provider="minimax")

# 发送请求
response: ChatResponse = client.chat([
    ChatMessage(role="user", content="Hello")
])
```

### 2.2 Page Composer

```python
from repo_wiki.generator.composer import PageComposer, ComposerInput, PageType

composer = PageComposer(llm_client=client)

input = ComposerInput(
    page_type=PageType.ARCHITECTURE,
    topic="系统架构",
    context={"repo_snapshot": snapshot},
    evidence=[evidence_span]
)

output = await composer.compose(input)
```

### 2.3 Verifier

```python
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeVerifierService

verifier = QoderLikeVerifierService()
result = verifier.verify(output_dir=Path("content"), profile="qoder-like")
# result.grade: "PASS" | "FAIL" | "WARN"
# result.exit_code: 0 | non-zero
```

### 2.4 State Management

```python
from repo_wiki.indexer.sqlite_state import SQLiteState

state = SQLiteState(db_path=".repo-wiki/state.sqlite3")
state.save_run(run_id="my-run", status="running")
state.get_run_stats(run_id="my-run")
```

---

## 3. 数据模型 API

### 3.1 Source-of-truth Schema

```python
@dataclass
class RepositorySnapshot:
    repo_id: str
    name: str
    language: str
    framework: str | None
    modules: list[Module]
    endpoints: list[Endpoint]
    data_models: list[DataModel]
    stats: RepositoryStats

@dataclass
class Module:
    name: str
    path: str
    responsibility: str
    exports: list[str]
    depends_on: list[str]
    depended_by: list[str]
    interfaces: list[str]
    data_models: list[str]
    owner: str | None
    doc_path: str | None
```

### 3.2 Manifest Schema

```python
@dataclass
class WikiPlanManifest:
    version: str
    run_id: str
    created_at: datetime
    wiki_git_commit: str
    page_count: int
    nav_tree: list[NavNode]
    pages: list[PagePlan]

@dataclass
class PagePlan:
    page_id: str
    title: str
    slug: str
    page_type: str
    content_path: str
    parent_id: str | None
    children: list[str]
```

---

## 4. 参考文档

> 详见 [functional-spec.md](./functional-spec.md) 功能规格。
> 详见 [high-level-design.md](./high-level-design.md) 高级设计。
> 详见 [configuration-guide.md](./configuration-guide.md) 配置指南。