# Data Model - repo-wiki-agent

<cite>repo_wiki/cli.py:1</cite>

本页面按领域聚合数据模型，展示核心实体、服务模型和持久化策略。详细模型定义请参考 `ai/source-of-truth/data-models.yaml`。

## 核心数据模型

暂无核心模型定义。

核心模型是跨服务共享的基础实体，定义系统的基础数据结构。

### 核心模型列表

| 无核心模型 | | | |

---

## 服务数据模型

服务模型是特定于模块或域的业务数据结构。

**共有 41 个服务模型**

### extensions/repo-wiki-browser (editor-integration)

- **GitStatus** (ts_interface) - `extensions/repo-wiki-browser/src/extension.ts`
- **LlmDisplayInfo** (ts_interface) - `extensions/repo-wiki-browser/src/extension.ts`
- **ManifestRunSummary** (ts_interface) - `extensions/repo-wiki-browser/src/extension.ts`
- **NavigationTreeNode** (ts_interface) - `extensions/repo-wiki-browser/src/extension.ts`
- **WikiFile** (ts_interface) - `extensions/repo-wiki-browser/src/extension.ts`
- **WikiGroup** (ts_interface) - `extensions/repo-wiki-browser/src/extension.ts`
- **WikiNodeType** (ts_type) - `extensions/repo-wiki-browser/src/extension.ts`
- **WikiSource** (ts_interface) - `extensions/repo-wiki-browser/src/extension.ts`

### repo_wiki (cli-core)

- **BootstrapResult** (python_class) - `repo_wiki/core/runtime.py`
- **DataModel** (python_class) - `repo_wiki/core/contracts.py`
- **Endpoint** (python_class) - `repo_wiki/core/contracts.py`
- **ErrorCode** (python_class) - `repo_wiki/llm/models.py`
- **EvalManifest** (python_class) - `repo_wiki/orchestration/eval_layout.py`
- **EvalManifestEvidence** (python_class) - `repo_wiki/orchestration/eval_layout.py`
- **EvalManifestFile** (python_class) - `repo_wiki/orchestration/eval_layout.py`
- **EvalOutputProfile** (python_class) - `repo_wiki/orchestration/eval_layout.py`
- **GenerationMode** (python_class) - `repo_wiki/planner/schema.py`
- **ImpactSet** (python_class) - `repo_wiki/core/contracts.py`
- **IndexConfig** (python_class) - `repo_wiki/core/config.py`
- **LLMError** (python_class) - `repo_wiki/llm/models.py`
- **LLMProvider** (python_class) - `repo_wiki/llm/models.py`
- **LLMProviderConfig** (python_class) - `repo_wiki/llm/config.py`
- **LlmConfig** (python_class) - `repo_wiki/core/config.py`
- **Module** (python_class) - `repo_wiki/core/contracts.py`
- **NavNode** (python_class) - `repo_wiki/planner/schema.py`
- **NonRetryableError** (python_class) - `repo_wiki/llm/models.py`
- **OutputConfig** (python_class) - `repo_wiki/core/config.py`
- **ProjectConfig** (python_class) - `repo_wiki/core/config.py`
- **RepoWikiConfig** (python_class) - `repo_wiki/core/config.py`
- **RepositoryIdentity** (python_class) - `repo_wiki/planner/schema.py`
- **RepositoryInfo** (python_class) - `repo_wiki/core/contracts.py`
- **RepositorySnapshot** (python_class) - `repo_wiki/core/contracts.py`
- **RepositoryStats** (python_class) - `repo_wiki/core/contracts.py`
- **RetryableError** (python_class) - `repo_wiki/llm/models.py`
- **ScanConfig** (python_class) - `repo_wiki/core/config.py`
- **SecurityConfig** (python_class) - `repo_wiki/core/config.py`
- **SourceRequirement** (python_class) - `repo_wiki/planner/schema.py`
- **VerifyResult** (python_class) - `repo_wiki/core/contracts.py`
- **WikiPagePlan** (python_class) - `repo_wiki/planner/schema.py`
- **WikiPlanManifest** (python_class) - `repo_wiki/planner/schema.py`
- **WikiTaxonomyCategory** (python_class) - `repo_wiki/planner/schema.py`


服务模型是特定于服务或模块的实体，封装业务逻辑所需的数据结构。

### 按服务分组

### extensions/repo-wiki-browser (editor-integration)

- **GitStatus** (ts_interface) - `extensions/repo-wiki-browser/src/extension.ts`
- **LlmDisplayInfo** (ts_interface) - `extensions/repo-wiki-browser/src/extension.ts`
- **ManifestRunSummary** (ts_interface) - `extensions/repo-wiki-browser/src/extension.ts`
- **NavigationTreeNode** (ts_interface) - `extensions/repo-wiki-browser/src/extension.ts`
- **WikiFile** (ts_interface) - `extensions/repo-wiki-browser/src/extension.ts`
- **WikiGroup** (ts_interface) - `extensions/repo-wiki-browser/src/extension.ts`
- **WikiNodeType** (ts_type) - `extensions/repo-wiki-browser/src/extension.ts`
- **WikiSource** (ts_interface) - `extensions/repo-wiki-browser/src/extension.ts`

### repo_wiki (cli-core)

- **BootstrapResult** (python_class) - `repo_wiki/core/runtime.py`
- **DataModel** (python_class) - `repo_wiki/core/contracts.py`
- **Endpoint** (python_class) - `repo_wiki/core/contracts.py`
- **ErrorCode** (python_class) - `repo_wiki/llm/models.py`
- **EvalManifest** (python_class) - `repo_wiki/orchestration/eval_layout.py`
- **EvalManifestEvidence** (python_class) - `repo_wiki/orchestration/eval_layout.py`
- **EvalManifestFile** (python_class) - `repo_wiki/orchestration/eval_layout.py`
- **EvalOutputProfile** (python_class) - `repo_wiki/orchestration/eval_layout.py`
- **GenerationMode** (python_class) - `repo_wiki/planner/schema.py`
- **ImpactSet** (python_class) - `repo_wiki/core/contracts.py`
- **IndexConfig** (python_class) - `repo_wiki/core/config.py`
- **LLMError** (python_class) - `repo_wiki/llm/models.py`
- **LLMProvider** (python_class) - `repo_wiki/llm/models.py`
- **LLMProviderConfig** (python_class) - `repo_wiki/llm/config.py`
- **LlmConfig** (python_class) - `repo_wiki/core/config.py`
- **Module** (python_class) - `repo_wiki/core/contracts.py`
- **NavNode** (python_class) - `repo_wiki/planner/schema.py`
- **NonRetryableError** (python_class) - `repo_wiki/llm/models.py`
- **OutputConfig** (python_class) - `repo_wiki/core/config.py`
- **ProjectConfig** (python_class) - `repo_wiki/core/config.py`
- **RepoWikiConfig** (python_class) - `repo_wiki/core/config.py`
- **RepositoryIdentity** (python_class) - `repo_wiki/planner/schema.py`
- **RepositoryInfo** (python_class) - `repo_wiki/core/contracts.py`
- **RepositorySnapshot** (python_class) - `repo_wiki/core/contracts.py`
- **RepositoryStats** (python_class) - `repo_wiki/core/contracts.py`
- **RetryableError** (python_class) - `repo_wiki/llm/models.py`
- **ScanConfig** (python_class) - `repo_wiki/core/config.py`
- **SecurityConfig** (python_class) - `repo_wiki/core/config.py`
- **SourceRequirement** (python_class) - `repo_wiki/planner/schema.py`
- **VerifyResult** (python_class) - `repo_wiki/core/contracts.py`
- **WikiPagePlan** (python_class) - `repo_wiki/planner/schema.py`
- **WikiPlanManifest** (python_class) - `repo_wiki/planner/schema.py`
- **WikiTaxonomyCategory** (python_class) - `repo_wiki/planner/schema.py`

---

## 数据库与迁移策略

**数据库形状概述**：

| 类型 | 数量 |
|------|------|
| python_class | 33 |
| ts_interface | 7 |
| ts_type | 1 |

### 数据库形状

**数据库形状概述**：

| 类型 | 数量 |
|------|------|
| python_class | 33 |
| ts_interface | 7 |
| ts_type | 1 |

### 迁移策略

**数据迁移策略**：

**迁移工具/方法**: 未知迁移策略（需要代码扫描）
- 迁移策略需要在代码扫描后确定

### 跨模块数据边界

暂无跨模块数据边界定义

---

## 模型索引

| 模型名称 | 类型 | 模块 | 定义文件 |
|----------|------|------|----------|
| GitStatus  | ts_interface | extensions/repo-wiki-browser | `extensions/repo-wiki-browser/src/extension.ts` |
| LlmDisplayInfo  | ts_interface | extensions/repo-wiki-browser | `extensions/repo-wiki-browser/src/extension.ts` |
| ManifestRunSummary  | ts_interface | extensions/repo-wiki-browser | `extensions/repo-wiki-browser/src/extension.ts` |
| NavigationTreeNode  | ts_interface | extensions/repo-wiki-browser | `extensions/repo-wiki-browser/src/extension.ts` |
| WikiFile  | ts_interface | extensions/repo-wiki-browser | `extensions/repo-wiki-browser/src/extension.ts` |
| WikiGroup  | ts_interface | extensions/repo-wiki-browser | `extensions/repo-wiki-browser/src/extension.ts` |
| WikiNodeType  | ts_type | extensions/repo-wiki-browser | `extensions/repo-wiki-browser/src/extension.ts` |
| WikiSource  | ts_interface | extensions/repo-wiki-browser | `extensions/repo-wiki-browser/src/extension.ts` |
| BootstrapResult  | python_class | repo_wiki | `repo_wiki/core/runtime.py` |
| DataModel  | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| Endpoint  | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| ErrorCode  | python_class | repo_wiki | `repo_wiki/llm/models.py` |
| EvalManifest  | python_class | repo_wiki | `repo_wiki/orchestration/eval_layout.py` |
| EvalManifestEvidence  | python_class | repo_wiki | `repo_wiki/orchestration/eval_layout.py` |
| EvalManifestFile  | python_class | repo_wiki | `repo_wiki/orchestration/eval_layout.py` |
| EvalOutputProfile  | python_class | repo_wiki | `repo_wiki/orchestration/eval_layout.py` |
| GenerationMode  | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| ImpactSet  | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| IndexConfig  | python_class | repo_wiki | `repo_wiki/core/config.py` |
| LLMError  | python_class | repo_wiki | `repo_wiki/llm/models.py` |
| LLMProvider  | python_class | repo_wiki | `repo_wiki/llm/models.py` |
| LLMProviderConfig  | python_class | repo_wiki | `repo_wiki/llm/config.py` |
| LlmConfig  | python_class | repo_wiki | `repo_wiki/core/config.py` |
| Module  | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| NavNode  | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| NonRetryableError  | python_class | repo_wiki | `repo_wiki/llm/models.py` |
| OutputConfig  | python_class | repo_wiki | `repo_wiki/core/config.py` |
| ProjectConfig  | python_class | repo_wiki | `repo_wiki/core/config.py` |
| RepoWikiConfig  | python_class | repo_wiki | `repo_wiki/core/config.py` |
| RepositoryIdentity  | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| RepositoryInfo  | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| RepositorySnapshot  | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| RepositoryStats  | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| RetryableError  | python_class | repo_wiki | `repo_wiki/llm/models.py` |
| ScanConfig  | python_class | repo_wiki | `repo_wiki/core/config.py` |
| SecurityConfig  | python_class | repo_wiki | `repo_wiki/core/config.py` |
| SourceRequirement  | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| VerifyResult  | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| WikiPagePlan  | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| WikiPlanManifest  | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| WikiTaxonomyCategory  | python_class | repo_wiki | `repo_wiki/planner/schema.py` |

---

## 阅读导航

- [项目概览](00-overview.md) - 快速了解项目定位和能力
- [系统架构](01-architecture.md) - 了解三层架构设计
- [模块地图](03-module-map.md) - 查看模块依赖关系
- [API 契约](04-api-contracts.md) - 了解服务间接口
- [Section 页](sections/data-model/index.md) - 按数据模型专题深入阅读
