# Troubleshooting and Maintenance

本节涵盖 core-platform 等 3 个模块的内容。

---

## 专题内容

## Troubleshooting and Maintenance 内容概览

本节介绍 Troubleshooting and Maintenance 的相关内容。以下模块和组件共同构成了系统的 Troubleshooting and Maintenance 能力，了解它们有助于深入理解系统设计和实现细节。

- **extensions**: Handles models instanceof, in.
- **repo_wiki**: Handles API routes /path.
- **scripts**: Handles exports AcceptanceEvidence, BaselineComparatorConfig.

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

- Troubleshooting and Maintenance（当前页）
- [Overview](../../00-overview.md)
- [Deployment and Operations](../operations/index.md)
- [Development Guide](../development/index.md)

---

## 阅读路径

## 推荐阅读路径

本文档建议按以下顺序阅读：

- [项目概览](../../00-overview.md) - 总览提供项目整体定位和能力（建议首先阅读）
- [运维](../operations/index.md) - 故障排查是运维的一部分
- [开发指南](../development/index.md) - 了解开发流程有助于诊断

## 相关专题

## 相关专题
- [项目概览](../../00-overview.md) - 总览提供项目整体定位和能力
- [运维](../operations/index.md) - 故障排查是运维的一部分
- [开发指南](../development/index.md) - 了解开发流程有助于诊断
