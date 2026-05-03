# repo-wiki MVP — 数据库设计文档（Database Design）

**文档编号：** DOC-007
**版本：** v1.0.0
**创建日期：** 2026-05-03
**最后更新：** 2026-05-03

---

## 1. 概述

repo-wiki 使用 SQLite 作为本地状态存储，支持 FTS5 全文检索。ChromaDB 用于向量存储。

---

## 2. SQLite Schema

### 2.1 Operational State Database

**路径：** `.repo-wiki/state.sqlite3`

**表结构：**

```sql
-- 生成运行状态
CREATE TABLE generation_runs (
    run_id TEXT PRIMARY KEY,
    profile TEXT NOT NULL,
    status TEXT NOT NULL,  -- pending, running, completed, failed, retryable
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    page_count INTEGER,
    completed_pages INTEGER DEFAULT 0,
    failed_pages INTEGER DEFAULT 0
);

-- 页面级状态
CREATE TABLE page_generation_states (
    page_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    FOREIGN KEY (run_id) REFERENCES generation_runs(run_id)
);

-- 文档层级
CREATE TABLE doc_hierarchy (
    page_id TEXT PRIMARY KEY,
    parent_id TEXT,
    title TEXT NOT NULL,
    slug TEXT NOT NULL,
    page_type TEXT,
    content_path TEXT,
    FOREIGN KEY (parent_id) REFERENCES doc_hierarchy(page_id)
);

-- 导航图
CREATE TABLE nav_graph (
    page_id TEXT PRIMARY KEY,
    prev_page_id TEXT,
    next_page_id TEXT,
    depth INTEGER,
    ordering INTEGER
);

-- 证据跨度
CREATE TABLE evidence_span (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    symbol TEXT,
    evidence_type TEXT,  -- file, line, symbol
    confidence REAL
);

-- 验证运行记录
CREATE TABLE verify_runs (
    run_id TEXT PRIMARY KEY,
    profile TEXT NOT NULL,
    grade TEXT,  -- PASS, FAIL, WARN
    exit_code INTEGER,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2.2 FTS5 Virtual Table

```sql
-- 全文检索索引
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    chunk_id,
    content,
    tokenize='porter unicode61'
);
```

---

## 3. ChromaDB Schema

**路径：** `.repo-wiki/chroma_db/`

**Collection：** `repo_wiki_chunks`

| Field | Type | Description |
|-------|------|-------------|
| id | string | chunk identifier |
| embedding | float[768] | vector embedding |
| document | string | chunk text content |
| metadata | dict | file_path, page_id, chunk_index |

---

## 4. Source-of-truth Artifacts

### 4.1 repo-map.yaml

```yaml
repo_id: "ai-api-atlas"
name: "AI_API_Atlas"
language: "Python"
framework: "FastAPI"
module_count: 12
endpoint_count: 45
data_model_count: 28
```

### 4.2 module-index.yaml

```yaml
modules:
  - name: "auth-service"
    path: "src/auth"
    responsibility: "Authentication and authorization"
    exports: ["AuthService", "TokenValidator"]
    depends_on: ["user-service", "notification-service"]
    depended_by: ["api-gateway"]
```

### 4.3 api-index.yaml

```yaml
endpoints:
  - path: "/api/v1/auth/login"
    method: "POST"
    service_family: "auth"
    auth: "none"
    request_schema: "LoginRequest"
    response_schema: "LoginResponse"
```

### 4.4 data-models.yaml

```yaml
data_models:
  - name: "User"
    type: "entity"
    persistence: "PostgreSQL"
    table_name: "users"
    fields:
      - name: "id"
        type: "UUID"
        constraints: ["PRIMARY KEY"]
```

---

## 5. Qoder-like Output Schema

```
.repo-agent-eval/<run-id>/
├── content/
│   ├── index.md
│   ├── api/
│   │   └── reference.md
│   └── ...
├── manifest.json
└── reports/
    └── strict-verify-output.json
```

### 5.1 manifest.json

```json
{
  "version": "1.0",
  "run_id": "task-35-1-reverify-20260502",
  "wiki_git_commit": "7be2e094cb6133e88a5ce5f774f240e66e301fb9",
  "page_count": 169,
  "nav_tree": [...]
}
```

---

## 6. 参考文档

> 详见 [api-spec.md](./api-spec.md) API 规范。
> 详见 [design.md](./spec/design.md) 系统设计。