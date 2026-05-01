# Python Service Layer

本节涵盖 core-platform 等 4 个模块的内容。

---

## 专题内容

## 核心服务组件

本节深入介绍系统中的核心服务组件。这些模块承担着系统的主要业务逻辑，是实现功能的核心单元。下面的每个组件都有明确的职责边界和运行时角色，它们通过标准接口进行通信，共同维持系统的正常运转。

### extensions (core-platform)

**职责**: Handles models instanceof, in.
**运行时角色**: api-server
**依赖**: scripts, tests

### repo_wiki (core-platform)

**职责**: Handles API routes /path.
**运行时角色**: api-server

### scripts (core-platform)

**职责**: Handles exports AcceptanceEvidence, BaselineComparatorConfig.
**运行时角色**: api-server
**依赖**: repo_wiki

### tests (core-platform)

**职责**: Handles API routes /users, /users.
**运行时角色**: api-server
**依赖**: repo_wiki, scripts


## 模块列表

- **extensions** `extensions`
  - Handles models instanceof, in.
  - 域: core-platform
- **repo_wiki** `repo_wiki`
  - Handles API routes /path.
  - 域: core-platform
- **scripts** `scripts`
  - Handles exports AcceptanceEvidence, BaselineComparatorConfig.
  - 域: core-platform
- **tests** `tests`
  - Handles API routes /users, /users.
  - 域: core-platform

## API 端点

- **GET** `/path`
  - repo_wiki.__init__
- **GET** `/health`
  - tests.test_endpoint_inherits_module_service_family
- **GET** `/items`
  - tests.test_endpoint_inherits_module_service_family
- **POST** `/items`
  - tests.test_endpoint_inherits_module_service_family
- **GET** `/ready`
  - tests.test_endpoint_inherits_module_service_family
- **GET** `/status`
  - tests.test_endpoint_inherits_module_service_family
- **GET** `/users`
  - tests.test_endpoint_inherits_module_service_family
- **GET** `/users`
  - tests.test_scanner_and_source_of_truth_outputs
- **POST** `/users`
  - tests.test_endpoint_inherits_module_service_family
- **POST** `/webhook/github`
  - tests.test_endpoint_inherits_module_service_family

## 相关命令

- `build`: `npm run build`
- `lint`: `npm run lint`
- `start`: `npm run start`
- `test`: `npm run test`

---

## 导航

- Python Service Layer（当前页）
- [Overview](../../00-overview.md)
- [Core Services and Business Logic](../services/index.md)
- [API Reference and Contracts](../api/index.md)
- [Data Models and Persistence](../data-model/index.md)

---

## 阅读路径

## 推荐阅读路径

本文档建议按以下顺序阅读：

- [项目概览](../../00-overview.md) - 总览提供项目整体定位和能力（建议首先阅读）

## 相关专题

## 相关专题
- [项目概览](../../00-overview.md) - 总览提供项目整体定位和能力
