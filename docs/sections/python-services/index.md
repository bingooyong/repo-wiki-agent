# Python Service Layer

<!-- repo-wiki-init-stub -->

本节涵盖 cli-core、generation-and-release、quality-gates 等 3 个模块的内容。

---

## 专题内容

## 核心服务组件

本节深入介绍系统中的核心服务组件。这些模块承担着系统的主要业务逻辑，是实现功能的核心单元。下面的每个组件都有明确的职责边界和运行时角色，它们通过标准接口进行通信，共同维持系统的正常运转。

### repo_wiki (cli-core)

**职责**: Typer CLI entry point, configuration loading, orchestration facade, and public repo-wiki command surface.
**运行时角色**: unknown
**依赖**: repo_wiki.orchestration, repo_wiki.verifier, repo_wiki.viewer

### repo_wiki.orchestration (generation-and-release)

**职责**: Generate qoder-like eval runs, write manifests, diagnose eval layouts, select latest runs, and publish READY releases.
**运行时角色**: unknown
**依赖**: repo_wiki.verifier

### repo_wiki.verifier (quality-gates)

**职责**: Strict qoder-like verification, path comparison, baseline registry, parity metrics, and readiness evidence.
**运行时角色**: unknown
**依赖**: repo_wiki.orchestration


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
