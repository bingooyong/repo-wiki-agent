# Deployment and Operations

<!-- repo-wiki-init-stub -->

本节涵盖 cli-core、generation-and-release、quality-gates 等 3 个模块的内容。

---

## 专题内容

## Deployment and Operations 内容概览

本节介绍 Deployment and Operations 的相关内容。以下模块和组件共同构成了系统的 Deployment and Operations 能力，了解它们有助于深入理解系统设计和实现细节。

- **repo_wiki**: Typer CLI entry point, configuration loading, orchestration facade, and public repo-wiki command surface.
- **repo_wiki.orchestration**: Generate qoder-like eval runs, write manifests, diagnose eval layouts, select latest runs, and publish READY releases.
- **repo_wiki.verifier**: Strict qoder-like verification, path comparison, baseline registry, parity metrics, and readiness evidence.

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

- Deployment and Operations（当前页）
- [Overview](../../00-overview.md)
- [Development Guide](../development/index.md)
- [Security and Compliance](../security/index.md)

---

## 阅读路径

## 推荐阅读路径

本文档建议按以下顺序阅读：

- [项目概览](../../00-overview.md) - 总览提供项目整体定位和能力（建议首先阅读）
- [开发指南](../development/index.md) - 运维建立在开发规范之上
- [故障排查](../troubleshooting/index.md) - 出现问题时的诊断流程

## 相关专题

## 相关专题
- [项目概览](../../00-overview.md) - 总览提供项目整体定位和能力
- [开发指南](../development/index.md) - 运维建立在开发规范之上
- [故障排查](../troubleshooting/index.md) - 出现问题时的诊断流程
