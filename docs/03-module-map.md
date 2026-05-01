# Module Map - repo-agent

本页面按业务域（Business Domain）组织模块，揭示系统的高层划分和服务家族关系。每个域内模块按运行时角色（Runtime Role）进一步分组，帮助读者理解系统的职责边界和调用关系。

## 域概览

| 业务域 | 服务族数量 | 模块数量 | 说明 |
|--------|-----------|----------|------|
| core-platform | 2 | 4 | 核心平台基础设施，包括核心运行时和存储层 |

---

## 详细域分组

### core-platform

服务族数量: 2
#### python-backend

**api-server** (3 模块):
- **`repo_wiki`** `repo_wiki` ← 被依赖: scripts, tests
  - 职责: Handles API routes /path.
  - 文档: [docs/modules/repo_wiki.md](../docs/modules/repo_wiki.md)
- **`scripts`** `scripts` → 依赖: repo_wiki ← 被依赖: extensions, tests
  - 职责: Handles exports AcceptanceEvidence, BaselineComparatorConfig.
  - 文档: [docs/modules/scripts.md](../docs/modules/scripts.md)
- **`tests`** `tests` → 依赖: repo_wiki, scripts ← 被依赖: extensions
  - 职责: Handles API routes /users, /users.
  - 文档: [docs/modules/tests.md](../docs/modules/tests.md)
#### typescript-frontend

**api-server** (1 模块):
- **`extensions`** `extensions` → 依赖: scripts, tests
  - 职责: Handles models instanceof, in.
  - 文档: [docs/modules/extensions.md](../docs/modules/extensions.md)

---

## 模块索引

| 模块 | 路径 | 运行时角色 | 域 | 核心职责 |
|------|------|-----------|-----|---------|
| `extensions` | `extensions` | api-server | core-platform | Handles models instanceof, in. |
| `repo_wiki` | `repo_wiki` | api-server | core-platform | Handles API routes /path. |
| `scripts` | `scripts` | api-server | core-platform | Handles exports AcceptanceEvidence, BaselineComparatorConfig |
| `tests` | `tests` | api-server | core-platform | Handles API routes /users, /users. |

---

## 跨域依赖关系

- 暂无跨域依赖关系

---

## 阅读导航

- [项目概览](00-overview.md) - 快速了解项目定位和能力
- [系统架构](01-architecture.md) - 了解三层架构设计
- [API 契约](04-api-contracts.md) - 查看服务间接口定义
- [数据模型](05-data-model.md) - 了解核心实体关系
- [Section 页](sections/services/index.md) - 按服务专题深入阅读
