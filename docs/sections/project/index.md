# Project Overview and Getting Started

本节涵盖 core-platform 等 4 个模块的内容。

---

## 专题内容

## Project Overview and Getting Started 内容概览

本节介绍 Project Overview and Getting Started 的相关内容。以下模块和组件共同构成了系统的 Project Overview and Getting Started 能力，了解它们有助于深入理解系统设计和实现细节。

- **extensions**: Handles models instanceof, in.
- **repo_wiki**: Handles API routes /path.
- **scripts**: Handles exports AcceptanceEvidence, BaselineComparatorConfig.
- **tests**: Handles API routes /users, /users.

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

- Project Overview and Getting Started（当前页）
- [Overview](../../00-overview.md)
- [Architecture and System Design](../architecture/index.md)
- [Development Guide](../development/index.md)

---

## 阅读路径

## 推荐阅读路径

本文档建议按以下顺序阅读：

- [项目概览](../../00-overview.md) - 总览提供项目整体定位和能力（建议首先阅读）
- [系统架构](../architecture/index.md) - 理解系统设计后，再深入模块细节
- [核心服务](../services/index.md) - 在了解架构后查看服务实现
- [开发指南](../development/index.md) - 开发前必读的编码规范

## 相关专题

## 相关专题
- [项目概览](../../00-overview.md) - 总览提供项目整体定位和能力
- [系统架构](../architecture/index.md) - 理解系统设计后，再深入模块细节
- [核心服务](../services/index.md) - 在了解架构后查看服务实现
- [开发指南](../development/index.md) - 开发前必读的编码规范
