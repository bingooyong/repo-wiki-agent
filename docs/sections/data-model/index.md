# Data Models and Persistence

本节涵盖 core-platform 等 3 个模块的内容。

---

## 专题内容

## 数据模型概述

本节介绍系统的数据模型设计。数据模型是系统状态管理的核心，定义了实体结构、关系约束和数据访问模式。良好的数据模型设计能够提高系统的一致性和可维护性。

**核心模型**: 核心模型是系统的基础数据结构，定义跨模块共享的实体类型。

**识别出 44 个核心实体**：

- **in** (ts_definition)
  - 所属模块: repo_wiki, tests, extensions
  - 核心评分: 18.0 (被 3 个模块共享 + 核心域 core-platform + API 参数类型 + API 参数类型 + API 参数类型 + API 参数...

**服务模型**: 本节涵盖 3 个服务模块的数据模型。

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

- Data Models and Persistence（当前页）
- [Overview](../../00-overview.md)
- [Core Services and Business Logic](../services/index.md)
- [API Reference and Contracts](../api/index.md)
- [Architecture and System Design](../architecture/index.md)

---

## 阅读路径

## 推荐阅读路径

本文档建议按以下顺序阅读：

- [项目概览](../../00-overview.md) - 总览提供项目整体定位和能力（建议首先阅读）
- [核心服务](../services/index.md) - 数据模型被服务使用
- [系统架构](../architecture/index.md) - 数据库设计是架构的一部分

## 相关专题

## 相关专题
- [项目概览](../../00-overview.md) - 总览提供项目整体定位和能力
- [核心服务](../services/index.md) - 数据模型被服务使用
- [系统架构](../architecture/index.md) - 数据库设计是架构的一部分
