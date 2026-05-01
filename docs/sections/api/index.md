# API Reference and Contracts

本节涵盖 core-platform 等 3 个模块的内容。

---

## 专题内容

## API 端点概述

本节提供系统 API 接口的完整参考。API 是系统与外部交互的契约，定义了请求格式、响应结构和调用约定。理解 API 设计有助于集成开发和第三方对接。

**端点总数**: 10

**按模块分布**:
- tests: 9 个端点
- repo_wiki: 1 个端点

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

- API Reference and Contracts（当前页）
- [Overview](../../00-overview.md)
- [Core Services and Business Logic](../services/index.md)
- [Data Models and Persistence](../data-model/index.md)
- [Security and Compliance](../security/index.md)

---

## 阅读路径

## 推荐阅读路径

本文档建议按以下顺序阅读：

- [项目概览](../../00-overview.md) - 总览提供项目整体定位和能力（建议首先阅读）
- [核心服务](../services/index.md) - API 是服务的对外接口
- [安全考虑](../security/index.md) - 使用 API 时需要关注安全

## 相关专题

## 相关专题
- [项目概览](../../00-overview.md) - 总览提供项目整体定位和能力
- [核心服务](../services/index.md) - API 是服务的对外接口
- [安全考虑](../security/index.md) - 使用 API 时需要关注安全
