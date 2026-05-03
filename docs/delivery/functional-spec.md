# repo-wiki MVP — 功能规格文档（Functional Spec）

**文档编号：** DOC-004
**版本：** v1.0.0
**创建日期：** 2026-05-03
**最后更新：** 2026-05-03

---

## 1. 概述

本文档详细描述 repo-wiki MVP 的功能规格，基于 35 个 Phase 的实现记录。

---

## 2. CLI 命令功能

### 2.1 init

**功能：** 初始化仓库索引，生成 source-of-truth 产物。

**输入：** 目标仓库根目录
**输出：** `.repo-wiki/` 目录（SQLite 状态 + source-of-truth YAML/JSON）

**处理流程：**
1. 遍历仓库文件（应用 .gitignore 过滤）
2. 检测语言/框架
3. 提取模块、API、数据模型
4. 生成 source-of-truth 产物
5. 写入 SQLite 状态

### 2.2 index

**功能：** 构建搜索索引。

**输入：** source-of-truth 产物
**输出：** FTS5 索引 + ChromaDB 向量索引

### 2.3 generate

**功能：** 生成 Wiki 文档。

**Profile：** standard / qoder-like

| Profile | 输出位置 |
|--------|---------|
| standard | `docs/`, `.repo-wiki/` |
| qoder-like | `.repo-agent-eval/<run>/content/` |

**处理流程（qoder-like）：**
1. 解析 manifest 获取页面计划
2. 对每个页面调用 LLM Page Composer
3. 生成 Markdown 内容 + Mermaid 图表
4. 写入 content/ 目录
5. 更新 manifest

**页面类型：**
- Overview（项目概览）
- Architecture（架构设计）
- API Reference（API 参考）
- Data Model（数据模型）
- Operations（运维手册）
- Development（开发指南）
- Security（安全）

### 2.4 verify

**功能：** 验证生成质量。

**Profile：** standard / transitional / qoder-like

**13 项检查（qoder-like）：**

| 检查项 | 说明 | 门禁类型 |
|--------|------|---------|
| qoder-page-dumps | 无列表过重页面 | HARD |
| qoder-prose-density | prose 密度 >= 30% | HARD |
| qoder-stale-commit | git commit 最新 | HARD |
| qoder-content-empty | 内容非空 | HARD |
| qoder-toc | 有目录 | SOFT |
| qoder-citations | 有引用 | SOFT |
| qoder-mermaid | 有图表 | SOFT |
| qoder-api-aggregation | API 聚合质量 | HARD |
| qoder-dm-aggregation | Data model 聚合质量 | HARD |
| qoder-citation-relevance | 引用相关性 | HARD |
| qoder-dirty-worktree | 工作树干净 | HARD |
| qoder-broken-links | 无死链 | SOFT |
| qoder-page-count | 页面数量合规 | SOFT |

### 2.5 update

**功能：** 基于 git diff 增量更新。

**处理流程：**
1. 计算 git diff hash
2. PageInvalidationEngine 判断哪些页面失效
3. 只重生成失效页面
4. 更新 manifest 和 SQLite 状态

### 2.6 search

**功能：** 语义搜索。

**处理流程：**
1. 接收查询字符串
2. 精确检索（FTS5）
3. 向量检索（ChromaDB）
4. 图扩展（Module Graph）
5. 返回排序结果

### 2.7 graph

**功能：** 生成模块依赖图。

**输出格式：** text / mermaid / dot

### 2.8 cost-estimate

**功能：** 估算 LLM 生成成本。

**计算依据：** 预估页面数 × 平均 token 消耗 × 单价

---

## 3. 数据处理功能

### 3.1 Source-of-truth 生成

| 产物 | Schema |
|------|--------|
| repo-map.yaml | RepositorySnapshot |
| module-index.yaml | Module[] |
| api-index.yaml | Endpoint[] |
| data-models.yaml | DataModel[] |

### 3.2 Evidence Builder

**功能：** 为页面内容提供证据追溯。

**Source Span Extractor 支持语言：**
- Java
- Python
- TypeScript
- SQL
- YAML
- Markdown

**证据类型：**
- file citations
- line citations
- symbol references

### 3.3 Citation Verification

**功能：** 验证引用的准确性和相关性。

**规则：**
- 高置信度不匹配 → FAIL
- 共享基础设施引用 → WARN
- 错误服务绑定 → FAIL

---

## 4. LLM 集成功能

### 4.1 Provider Abstraction

| Provider | 实现 |
|----------|------|
| OpenAI-compatible | OpenAIClient |
| Minimax | MinimaxClient |

### 4.2 Token Budgeting

- 请求前估算 token 消耗
- 超出预算则拒绝
- 支持重试和退避

### 4.3 Cache

- Input hash + output hash 缓存
- 相同输入跳过 LLM 调用

---

## 5. 质量控制功能

### 5.1 Page Composer Quality Guardrails

1. No placeholder text
2. No hallucinated facts
3. Prose density >= 30%
4. No list-dominant content
5. Citation coverage
6. Mermaid diagram presence
7. Service-appropriate detail level

### 5.2 Low-confidence Fallback

当证据不足时：
- 生成 `待确认` 段落
- 禁止编造实现细节
- 标注不确定性原因

---

## 6. 参考文档

> 详见 [requirements.md](./spec/requirements.md) 功能需求。
> 详见 [design.md](./spec/design.md) 系统设计。
> 详见 [acceptance-checklist.md](./acceptance-checklist.md) 验收清单。