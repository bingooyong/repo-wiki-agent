# repo-agent - 项目概览

repo-agent 是一个基于 Javascript (express) 的知识管理和文档生成平台。系统提供 知识管理和语义检索、文档自动生成、核心平台基础设施 等核心能力。

## 项目定位

该项目面向 技术写作者和开发者，致力于解决 文档维护和知识同步 中的效率问题。通过结构化知识组织和自动化工具，提升代码理解和维护效率。

## 核心问题

repo-agent 旨在解决以下核心问题：文档与代码不同步，维护成本高；传统文档难以发现和检索；代码结构复杂，难以快速理解。

## 核心能力

repo-agent 提供以下核心能力：模块分析和依赖关系构建（4 个模块）；RESTful API 接口（10 个端点，跨越 2 个模块）。

## 快速开始

### 环境要求

- **Javascript**: Node.js 18+ 和 npm

### 启动命令

- `npm run build`
- `npm run start`
- `npm run test`

## 阅读导航

- [项目架构](sections/architecture/index.md) - 了解系统设计和技术栈
- [核心服务](sections/services/index.md) - 查看主要业务模块
- [API 参考](sections/api/index.md) - 查阅接口文档
- [模块详情](03-module-map.md) - 浏览所有模块

---

## 技术概览

| 属性 | 值 |
|------|-----|
| 仓库根目录 | `/Users/bingooyong/Code/01Code/github.com/bingooyong/repo-agent` |
| 主要语言 | `javascript` |
| 框架 | `express` |
| 模块数量 | 4 |
| API 端点 | 10 |
| 数据模型 | 44 |

## 领域分组

### core-platform

- **extensions** (typescript-frontend) - Handles models instanceof, in.
- **repo_wiki** (python-backend) - Handles API routes /path.
- **scripts** (python-backend) - Handles exports AcceptanceEvidence, BaselineComparatorConfig.
- **tests** (python-backend) - Handles API routes /users, /users.
