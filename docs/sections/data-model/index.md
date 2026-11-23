# Data Models and Persistence

<!-- repo-wiki-init-stub -->

本节涵盖 cli-core、generation-and-release、quality-gates 等 3 个模块的内容。

---

## 专题内容

## 数据模型概述

本节介绍系统的数据模型设计。数据模型是系统状态管理的核心，定义了实体结构、关系约束和数据访问模式。良好的数据模型设计能够提高系统的一致性和可维护性。

**服务模型**: 本节涵盖 3 个服务模块的数据模型。

## 模块列表

- **repo_wiki** `repo_wiki`
  - Typer CLI entry point, configuration loading, orchestration facade, and public repo-wiki command surface.
  - 域: cli-core
- **repo_wiki.orchestration** `repo_wiki/orchestration`
  - Generate qoder-like eval runs, write manifests, diagnose eval layouts, select latest runs, and publish READY releases.
  - 域: generation-and-release
- **repo_wiki.verifier** `repo_wiki/verifier`
  - Strict qoder-like verification, path comparison, baseline registry, parity metrics, and readiness evidence.
  - 域: quality-gates

## API 端点

- 暂无 API 端点

## 相关命令

- `compare_qoder_like`: `repo-wiki compare --target <target-content-dir> --baseline <qoder-baseline-dir> --output <report-dir> --ci`
- `config`: `repo-wiki config --ci`
- `cost_estimate`: `repo-wiki cost-estimate`
- `eval_layout_report`: `repo-wiki eval-layout-report --output .repo-agent-eval`
- `generate_qoder_like`: `repo-wiki generate --profile qoder-like --output .repo-agent-eval`
- `graph`: `repo-wiki graph <module>`
- `index`: `repo-wiki index`
- `init`: `repo-wiki init`
- `release_publish`: `repo-wiki release-publish --output .repo-agent-eval`
- `search`: `repo-wiki search <query>`
- `sync`: `repo-wiki sync`
- `update`: `repo-wiki update`
- `verify_qoder_like`: `repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval`

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
