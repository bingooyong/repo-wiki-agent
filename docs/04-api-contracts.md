# API Contracts - repo-agent

本页面按服务族（Service Family）和主题域（Domain Theme）聚合 API 端点，展示认证模式、调用约定和关键入口点。详细端点列表请参考 `ai/source-of-truth/api-index.yaml`。

## 服务/API 分组

| 服务族/域 | 端点数 | 认证模式 | 暴露类型 |
|-----------|--------|----------|---------|
| python-backend/core-platform | 10 | bearer/none | internal/public/webhook |

---

## 分组详情

### python-backend/core-platform

**主题域**: core-platform | **服务族**: python-backend | **运行时角色**: api-server
**端点数量**: 10

**python-backend/core-platform** 接口调用约定：

- HTTP 方法: GET, POST
- 认证: 需要 Bearer Token
- 请求体: JSON 格式
- 响应格式: JSON
- 关键入口: `/path`, `/health`, `/items`

**关键入口点**：
- **POST** `/webhook/github` (POST 操作 + 根级路径)
- **GET** `/health` (公开接口 + 根级路径)
- **GET** `/ready` (公开接口 + 根级路径)
- **GET** `/status` (公开接口 + 根级路径)
- **POST** `/items` (POST 操作 + 根级路径)


---

## 调用约定

### 认证方式

系统 API 认证约定：
- **repo_wiki**: bearer
- **tests**: none

### 错误与状态码

API 错误与状态码约定：

| 状态码 | 含义 | 使用场景 |
|--------|------|---------|
| 200 | OK | 成功响应 |
| 400 | Bad Request | 请求参数错误 |
| 401 | Unauthorized | 未认证或认证失败 |
| 403 | Forbidden | 无权限访问 |
| 404 | Not Found | 资源不存在 |
| 500 | Internal Server Error | 服务器内部错误 |

**常见错误码**: 400, 401, 403, 404, 500

### 关键入口 API

系统中的关键入口 API：

- **POST** `/webhook/github` (tests.test_endpoint_inherits_module_service_family) - POST 操作 + 根级路径
- **GET** `/health` (tests.test_endpoint_inherits_module_service_family) - 公开接口 + 根级路径
- **GET** `/ready` (tests.test_endpoint_inherits_module_service_family) - 公开接口 + 根级路径
- **GET** `/status` (tests.test_endpoint_inherits_module_service_family) - 公开接口 + 根级路径
- **POST** `/items` (tests.test_endpoint_inherits_module_service_family) - POST 操作 + 根级路径
- **POST** `/users` (tests.test_endpoint_inherits_module_service_family) - POST 操作 + 根级路径
- **GET** `/path` (repo_wiki.__init__) - 需要认证 + 根级路径
- **GET** `/items` (tests.test_endpoint_inherits_module_service_family) - 根级路径
- **GET** `/users` (tests.test_endpoint_inherits_module_service_family) - 根级路径
- **GET** `/users` (tests.test_scanner_and_source_of_truth_outputs) - 根级路径

---

## 完整端点索引

| 方法 | 路径 | 模块 | 处理器 | 文档 |
|------|------|------|--------|------|
| GET | `/path` | repo_wiki | `__init__` | [模块文档](modules/repo_wiki.md) |
| GET | `/health` | tests | `test_endpoint_inherits_module_service_family` | [测试模块](modules/tests.md) |
| GET | `/items` | tests | `test_endpoint_inherits_module_service_family` | [测试模块](modules/tests.md) |
| POST | `/items` | tests | `test_endpoint_inherits_module_service_family` | [测试模块](modules/tests.md) |
| GET | `/ready` | tests | `test_endpoint_inherits_module_service_family` | [测试模块](modules/tests.md) |
| GET | `/status` | tests | `test_endpoint_inherits_module_service_family` | [测试模块](modules/tests.md) |
| GET | `/users` | tests | `test_endpoint_inherits_module_service_family` | [测试模块](modules/tests.md) |
| GET | `/users` | tests | `test_scanner_and_source_of_truth_outputs` | [测试模块](modules/tests.md) |
| POST | `/users` | tests | `test_endpoint_inherits_module_service_family` | [测试模块](modules/tests.md) |
| POST | `/webhook/github` | tests | `test_endpoint_inherits_module_service_family` | [测试模块](modules/tests.md) |

---

## 阅读导航

- [项目概览](00-overview.md) - 快速了解项目定位和能力
- [系统架构](01-architecture.md) - 了解三层架构设计
- [模块地图](03-module-map.md) - 查看模块依赖关系
- [数据模型](05-data-model.md) - 了解核心实体关系
- [Section 页](sections/api/index.md) - 按 API 专题深入阅读
