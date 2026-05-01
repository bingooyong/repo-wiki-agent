# Data Model - repo-agent

本页面按领域聚合数据模型，展示核心实体、服务模型和持久化策略。详细模型定义请参考 `ai/source-of-truth/data-models.yaml`。

## 核心数据模型

核心模型是系统的基础数据结构，定义跨模块共享的实体类型。

**识别出 44 个核心实体**：

- **in** (ts_definition)
  - 所属模块: repo_wiki, tests, extensions
  - 核心评分: 18.0 (被 3 个模块共享 + 核心域 core-platform + API 参数类型 + API 参数类型 + API 参数类型 + API 参数类型 + API 参数类型 + API 参数类型 + API 参数类型 + API 参数类型 + API 参数类型)
  - 定义文件: `extensions/repo-wiki-browser/node_modules/js-yaml/lib/schema.js`

- **Endpoint** (python_class)
  - 所属模块: repo_wiki, tests
  - 核心评分: 15.0 (被 2 个模块共享 + 核心域 core-platform + API 参数类型 + API 参数类型 + API 参数类型 + API 参数类型 + API 参数类型 + API 参数类型 + API 参数类型 + API 参数类型)
  - 定义文件: `repo_wiki/core/contracts.py`

- **Module** (python_class)
  - 所属模块: repo_wiki, tests
  - 核心评分: 15.0 (被 2 个模块共享 + 核心域 core-platform + API 参数类型 + API 参数类型 + API 参数类型 + API 参数类型 + API 参数类型 + API 参数类型 + API 参数类型 + API 参数类型)
  - 定义文件: `repo_wiki/core/contracts.py`

- **statement** (migration_table)
  - 所属模块: repo_wiki, tests
  - 核心评分: 7.0 (被 2 个模块共享 + 核心域 core-platform)
  - 定义文件: `repo_wiki/scanner/database_migrations.py`

- **statement** (migration_table)
  - 所属模块: repo_wiki, tests
  - 核心评分: 7.0 (被 2 个模块共享 + 核心域 core-platform)
  - 定义文件: `tests/test_database_migrations.py`

- **DataModel** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 4.5 (核心域 core-platform + 名称暗示基础实体)
  - 定义文件: `repo_wiki/core/contracts.py`

- **RepositoryIdentity** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 4.5 (核心域 core-platform + 名称暗示基础实体)
  - 定义文件: `repo_wiki/planner/schema.py`

- **UserModel** (python_class)
  - 所属模块: tests
  - 核心评分: 4.5 (核心域 core-platform + 名称暗示基础实体)
  - 定义文件: `tests/test_scanner_artifacts.py`

- **instanceof** (ts_definition)
  - 所属模块: extensions
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `extensions/repo-wiki-browser/node_modules/js-yaml/lib/schema.js`

- **BootstrapResult** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/core/runtime.py`

- **ErrorCode** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/llm/models.py`

- **EvalManifest** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/orchestration/eval_layout.py`

- **EvalManifestEvidence** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/orchestration/eval_layout.py`

- **EvalManifestFile** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/orchestration/eval_layout.py`

- **EvalOutputProfile** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/orchestration/eval_layout.py`

- **GenerationMode** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/planner/schema.py`

- **ImpactSet** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/core/contracts.py`

- **IndexConfig** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/core/config.py`

- **LLMError** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/llm/models.py`

- **LLMProvider** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/llm/models.py`

- **LLMProviderConfig** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/llm/config.py`

- **LlmConfig** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/core/config.py`

- **NavNode** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/planner/schema.py`

- **NonRetryableError** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/llm/models.py`

- **OutputConfig** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/core/config.py`

- **ProjectConfig** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/core/config.py`

- **RepoWikiConfig** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/core/config.py`

- **RepositoryInfo** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/core/contracts.py`

- **RepositorySnapshot** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/core/contracts.py`

- **RepositoryStats** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/core/contracts.py`

- **RetryableError** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/llm/models.py`

- **ScanConfig** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/core/config.py`

- **SecurityConfig** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/core/config.py`

- **SourceRequirement** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/planner/schema.py`

- **VerifyResult** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/core/contracts.py`

- **WikiPagePlan** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/planner/schema.py`

- **WikiPlanManifest** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/planner/schema.py`

- **WikiTaxonomyCategory** (python_class)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/planner/schema.py`

- **body** (migration_table)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/scanner/database_migrations.py`

- **statements** (migration_table)
  - 所属模块: repo_wiki
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `repo_wiki/scanner/database_migrations.py`

- **dm_sales_facts** (migration_table)
  - 所属模块: tests
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `tests/test_database_migrations.py`

- **posts** (migration_table)
  - 所属模块: tests
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `tests/test_database_migrations.py`

- **user_profiles** (migration_table)
  - 所属模块: tests
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `tests/test_database_migrations.py`

- **users** (migration_table)
  - 所属模块: tests
  - 核心评分: 3.0 (核心域 core-platform)
  - 定义文件: `tests/test_database_migrations.py`


核心模型是跨服务共享的基础实体，定义系统的基础数据结构。

### 核心模型列表

| 模型名称 | 类型 | 模块 | 定义文件 |
|----------|------|------|----------|
| BootstrapResult | python_class | repo_wiki | `repo_wiki/core/runtime.py` |
| DataModel | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| Endpoint | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| ErrorCode | python_class | repo_wiki | `repo_wiki/llm/models.py` |
| EvalManifest | python_class | repo_wiki | `repo_wiki/orchestration/eval_layout.py` |
| EvalManifestEvidence | python_class | repo_wiki | `repo_wiki/orchestration/eval_layout.py` |
| EvalManifestFile | python_class | repo_wiki | `repo_wiki/orchestration/eval_layout.py` |
| EvalOutputProfile | python_class | repo_wiki | `repo_wiki/orchestration/eval_layout.py` |
| GenerationMode | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| ImpactSet | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| IndexConfig | python_class | repo_wiki | `repo_wiki/core/config.py` |
| LLMError | python_class | repo_wiki | `repo_wiki/llm/models.py` |
| LLMProvider | python_class | repo_wiki | `repo_wiki/llm/models.py` |
| LLMProviderConfig | python_class | repo_wiki | `repo_wiki/llm/config.py` |
| LlmConfig | python_class | repo_wiki | `repo_wiki/core/config.py` |
| Module | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| NavNode | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| NonRetryableError | python_class | repo_wiki | `repo_wiki/llm/models.py` |
| OutputConfig | python_class | repo_wiki | `repo_wiki/core/config.py` |
| ProjectConfig | python_class | repo_wiki | `repo_wiki/core/config.py` |
| RepoWikiConfig | python_class | repo_wiki | `repo_wiki/core/config.py` |
| RepositoryIdentity | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| RepositoryInfo | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| RepositorySnapshot | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| RepositoryStats | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| RetryableError | python_class | repo_wiki | `repo_wiki/llm/models.py` |
| ScanConfig | python_class | repo_wiki | `repo_wiki/core/config.py` |
| SecurityConfig | python_class | repo_wiki | `repo_wiki/core/config.py` |
| SourceRequirement | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| UserModel | python_class | tests | `tests/test_scanner_artifacts.py` |
| VerifyResult | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| WikiPagePlan | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| WikiPlanManifest | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| WikiTaxonomyCategory | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| body | migration_table | repo_wiki | `repo_wiki/scanner/database_migrations.py` |
| dm_sales_facts | migration_table | tests | `tests/test_database_migrations.py` |
| in | ts_definition | extensions | `extensions/repo-wiki-browser/node_modules/js-yaml/lib/schema.js` |
| instanceof | ts_definition | extensions | `extensions/repo-wiki-browser/node_modules/js-yaml/lib/schema.js` |
| posts | migration_table | tests | `tests/test_database_migrations.py` |
| statement | migration_table | repo_wiki | `repo_wiki/scanner/database_migrations.py` |
| statement | migration_table | tests | `tests/test_database_migrations.py` |
| statements | migration_table | repo_wiki | `repo_wiki/scanner/database_migrations.py` |
| user_profiles | migration_table | tests | `tests/test_database_migrations.py` |
| users | migration_table | tests | `tests/test_database_migrations.py` |

---

## 服务数据模型

暂无服务模型定义。

服务模型是特定于服务或模块的实体，封装业务逻辑所需的数据结构。

### 按服务分组

- 无服务模型

---

## 数据库与迁移策略

**数据库形状概述**：

| 类型 | 数量 |
|------|------|
| migration_table | 8 |
| python_class | 34 |
| ts_definition | 2 |

### 数据库形状

**数据库形状概述**：

| 类型 | 数量 |
|------|------|
| migration_table | 8 |
| python_class | 34 |
| ts_definition | 2 |

### 迁移策略

**数据迁移策略**：

**迁移工具/方法**: 未知迁移策略（需要代码扫描）
- 迁移策略需要在代码扫描后确定

### 跨模块数据边界

**跨模块数据边界**：

核心实体在模块间的流动：

- **in**: 被以下模块使用
  - `repo_wiki`
  - `tests`
  - `extensions`
  - 数据流向: 跨 3 个模块共享
- **instanceof**: 被以下模块使用
  - `extensions`
- **BootstrapResult**: 被以下模块使用
  - `repo_wiki`
- **DataModel**: 被以下模块使用
  - `repo_wiki`
- **Endpoint**: 被以下模块使用
  - `repo_wiki`
  - `tests`
  - 数据流向: 跨 2 个模块共享

**数据一致性机制**：
- 使用 ORM 模型作为单一事实源

---

## 模型索引

| 模型名称 | 类型 | 模块 | 定义文件 |
|----------|------|------|----------|
| in **[核心]** | ts_definition | extensions | `extensions/repo-wiki-browser/node_modules/js-yaml/lib/schema.js` |
| instanceof **[核心]** | ts_definition | extensions | `extensions/repo-wiki-browser/node_modules/js-yaml/lib/schema.js` |
| BootstrapResult **[核心]** | python_class | repo_wiki | `repo_wiki/core/runtime.py` |
| DataModel **[核心]** | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| Endpoint **[核心]** | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| ErrorCode **[核心]** | python_class | repo_wiki | `repo_wiki/llm/models.py` |
| EvalManifest **[核心]** | python_class | repo_wiki | `repo_wiki/orchestration/eval_layout.py` |
| EvalManifestEvidence **[核心]** | python_class | repo_wiki | `repo_wiki/orchestration/eval_layout.py` |
| EvalManifestFile **[核心]** | python_class | repo_wiki | `repo_wiki/orchestration/eval_layout.py` |
| EvalOutputProfile **[核心]** | python_class | repo_wiki | `repo_wiki/orchestration/eval_layout.py` |
| GenerationMode **[核心]** | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| ImpactSet **[核心]** | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| IndexConfig **[核心]** | python_class | repo_wiki | `repo_wiki/core/config.py` |
| LLMError **[核心]** | python_class | repo_wiki | `repo_wiki/llm/models.py` |
| LLMProvider **[核心]** | python_class | repo_wiki | `repo_wiki/llm/models.py` |
| LLMProviderConfig **[核心]** | python_class | repo_wiki | `repo_wiki/llm/config.py` |
| LlmConfig **[核心]** | python_class | repo_wiki | `repo_wiki/core/config.py` |
| Module **[核心]** | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| NavNode **[核心]** | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| NonRetryableError **[核心]** | python_class | repo_wiki | `repo_wiki/llm/models.py` |
| OutputConfig **[核心]** | python_class | repo_wiki | `repo_wiki/core/config.py` |
| ProjectConfig **[核心]** | python_class | repo_wiki | `repo_wiki/core/config.py` |
| RepoWikiConfig **[核心]** | python_class | repo_wiki | `repo_wiki/core/config.py` |
| RepositoryIdentity **[核心]** | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| RepositoryInfo **[核心]** | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| RepositorySnapshot **[核心]** | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| RepositoryStats **[核心]** | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| RetryableError **[核心]** | python_class | repo_wiki | `repo_wiki/llm/models.py` |
| ScanConfig **[核心]** | python_class | repo_wiki | `repo_wiki/core/config.py` |
| SecurityConfig **[核心]** | python_class | repo_wiki | `repo_wiki/core/config.py` |
| SourceRequirement **[核心]** | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| VerifyResult **[核心]** | python_class | repo_wiki | `repo_wiki/core/contracts.py` |
| WikiPagePlan **[核心]** | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| WikiPlanManifest **[核心]** | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| WikiTaxonomyCategory **[核心]** | python_class | repo_wiki | `repo_wiki/planner/schema.py` |
| body **[核心]** | migration_table | repo_wiki | `repo_wiki/scanner/database_migrations.py` |
| statement **[核心]** | migration_table | repo_wiki | `repo_wiki/scanner/database_migrations.py` |
| statements **[核心]** | migration_table | repo_wiki | `repo_wiki/scanner/database_migrations.py` |
| UserModel **[核心]** | python_class | tests | `tests/test_scanner_artifacts.py` |
| dm_sales_facts **[核心]** | migration_table | tests | `tests/test_database_migrations.py` |
| posts **[核心]** | migration_table | tests | `tests/test_database_migrations.py` |
| statement **[核心]** | migration_table | tests | `tests/test_database_migrations.py` |
| user_profiles **[核心]** | migration_table | tests | `tests/test_database_migrations.py` |
| users **[核心]** | migration_table | tests | `tests/test_database_migrations.py` |

---

## 阅读导航

- [项目概览](00-overview.md) - 快速了解项目定位和能力
- [系统架构](01-architecture.md) - 了解三层架构设计
- [模块地图](03-module-map.md) - 查看模块依赖关系
- [API 契约](04-api-contracts.md) - 了解服务间接口
- [Section 页](sections/data-model/index.md) - 按数据模型专题深入阅读
