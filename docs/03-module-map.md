# Module Map - repo-wiki-agent

<cite>repo_wiki/cli.py:1</cite>

本页面按业务域（Business Domain）组织模块，揭示系统的高层划分和服务家族关系。每个域内模块按运行时角色（Runtime Role）进一步分组，帮助读者理解系统的职责边界和调用关系。

## 域概览

| 业务域 | 服务族数量 | 模块数量 | 说明 |
|--------|-----------|----------|------|
| agent-integration | 1 | 1 | 业务域: agent-integration |
| cli-core | 1 | 1 | 业务域: cli-core |
| editor-integration | 1 | 1 | 业务域: editor-integration |
| generation-and-release | 1 | 1 | 业务域: generation-and-release |
| quality-gates | 1 | 1 | 业务域: quality-gates |
| ready-release-viewing | 1 | 1 | 业务域: ready-release-viewing |
| source-of-truth | 1 | 1 | 业务域: source-of-truth |
| verification | 1 | 1 | 业务域: verification |

---

## 详细域分组

### agent-integration

服务族数量: 1
#### unknown

**unknown** (1 模块):
- **`plugins/repo-wiki`** `plugins/repo-wiki` → 依赖: repo_wiki, repo_wiki.orchestration, repo_wiki.verifier ← 被依赖: tests
  - 职责: Skills-only Codex plugin that routes repository Wiki lifecycle work through a deterministic local runner.
  - 文档: [README.md](../README.md)

### cli-core

服务族数量: 1
#### unknown

**unknown** (1 模块):
- **`repo_wiki`** `repo_wiki` → 依赖: repo_wiki.orchestration, repo_wiki.verifier, repo_wiki.viewer ← 被依赖: tests, extensions/repo-wiki-browser
  - 职责: Typer CLI entry point, configuration loading, orchestration facade, and public repo-wiki command surface.
  - 文档: [docs/03-module-map.md](../docs/03-module-map.md)

### editor-integration

服务族数量: 1
#### unknown

**unknown** (1 模块):
- **`extensions/repo-wiki-browser`** `extensions/repo-wiki-browser` → 依赖: repo_wiki.viewer, repo_wiki.orchestration
  - 职责: VS Code/Cursor sidebar and viewer for published READY repo-wiki releases plus terminal command shortcuts.
  - 文档: [docs/operations/vscode-extension-manual-llm-configuration.md](../docs/operations/vscode-extension-manual-llm-configuration.md)

### generation-and-release

服务族数量: 1
#### unknown

**unknown** (1 模块):
- **`repo_wiki.orchestration`** `repo_wiki/orchestration` → 依赖: repo_wiki.verifier ← 被依赖: repo_wiki, repo_wiki.viewer, extensions/repo-wiki-browser, tests
  - 职责: Generate qoder-like eval runs, write manifests, diagnose eval layouts, select latest runs, and publish READY releases.
  - 文档: [docs/plans/display-and-wiki-generation-optimization-roadmap.md](../docs/plans/display-and-wiki-generation-optimization-roadmap.md)

### quality-gates

服务族数量: 1
#### unknown

**unknown** (1 模块):
- **`repo_wiki.verifier`** `repo_wiki/verifier` → 依赖: repo_wiki.orchestration ← 被依赖: repo_wiki, tests
  - 职责: Strict qoder-like verification, path comparison, baseline registry, parity metrics, and readiness evidence.
  - 文档: [docs/04-api-contracts.md](../docs/04-api-contracts.md)

### ready-release-viewing

服务族数量: 1
#### unknown

**unknown** (1 模块):
- **`repo_wiki.viewer`** `repo_wiki/viewer` → 依赖: repo_wiki.orchestration ← 被依赖: extensions/repo-wiki-browser, tests
  - 职责: Static viewer and release viewer configuration for fixed READY release manifests.
  - 文档: [docs/00-overview.md](../docs/00-overview.md)

### source-of-truth

服务族数量: 1
#### unknown

**unknown** (1 模块):
- **`ai/source-of-truth`** `ai/source-of-truth` → 依赖: repo_wiki, extensions/repo-wiki-browser, plugins/repo-wiki ← 被依赖: repo_wiki, tests
  - 职责: Curated YAML contracts for repository map, module index, task catalog, API index, and data model index.
  - 文档: [docs/01-architecture.md](../docs/01-architecture.md)

### verification

服务族数量: 1
#### unknown

**unknown** (1 模块):
- **`tests`** `tests` → 依赖: repo_wiki, repo_wiki.orchestration, repo_wiki.verifier, repo_wiki.viewer, extensions/repo-wiki-browser, plugins/repo-wiki
  - 职责: Python unit and contract tests for CLI behavior, generation layouts, release contracts, verifier gates, and extension packaging.
  - 文档: [docs/03-module-map.md](../docs/03-module-map.md)

---

## 模块索引

| 模块 | 路径 | 运行时角色 | 域 | 核心职责 |
|------|------|-----------|-----|---------|
| `plugins/repo-wiki` | `plugins/repo-wiki` | unknown | agent-integration | Skills-only Codex plugin that routes repository Wiki lifecyc |
| `repo_wiki` | `repo_wiki` | unknown | cli-core | Typer CLI entry point, configuration loading, orchestration  |
| `extensions/repo-wiki-browser` | `extensions/repo-wiki-browser` | unknown | editor-integration | VS Code/Cursor sidebar and viewer for published READY repo-w |
| `repo_wiki.orchestration` | `repo_wiki/orchestration` | unknown | generation-and-release | Generate qoder-like eval runs, write manifests, diagnose eva |
| `repo_wiki.verifier` | `repo_wiki/verifier` | unknown | quality-gates | Strict qoder-like verification, path comparison, baseline re |
| `repo_wiki.viewer` | `repo_wiki/viewer` | unknown | ready-release-viewing | Static viewer and release viewer configuration for fixed REA |
| `ai/source-of-truth` | `ai/source-of-truth` | unknown | source-of-truth | Curated YAML contracts for repository map, module index, tas |
| `tests` | `tests` | unknown | verification | Python unit and contract tests for CLI behavior, generation  |

---

## 跨域依赖关系

- **source-of-truth** → **cli-core**: `ai/source-of-truth` 依赖 `repo_wiki`
- **source-of-truth** → **editor-integration**: `ai/source-of-truth` 依赖 `extensions/repo-wiki-browser`
- **source-of-truth** → **agent-integration**: `ai/source-of-truth` 依赖 `plugins/repo-wiki`
- **editor-integration** → **ready-release-viewing**: `extensions/repo-wiki-browser` 依赖 `repo_wiki.viewer`
- **editor-integration** → **generation-and-release**: `extensions/repo-wiki-browser` 依赖 `repo_wiki.orchestration`
- **agent-integration** → **cli-core**: `plugins/repo-wiki` 依赖 `repo_wiki`
- **agent-integration** → **generation-and-release**: `plugins/repo-wiki` 依赖 `repo_wiki.orchestration`
- **agent-integration** → **quality-gates**: `plugins/repo-wiki` 依赖 `repo_wiki.verifier`
- **cli-core** → **generation-and-release**: `repo_wiki` 依赖 `repo_wiki.orchestration`
- **cli-core** → **quality-gates**: `repo_wiki` 依赖 `repo_wiki.verifier`
- **cli-core** → **ready-release-viewing**: `repo_wiki` 依赖 `repo_wiki.viewer`
- **generation-and-release** → **quality-gates**: `repo_wiki.orchestration` 依赖 `repo_wiki.verifier`
- **quality-gates** → **generation-and-release**: `repo_wiki.verifier` 依赖 `repo_wiki.orchestration`
- **ready-release-viewing** → **generation-and-release**: `repo_wiki.viewer` 依赖 `repo_wiki.orchestration`
- **verification** → **cli-core**: `tests` 依赖 `repo_wiki`
- **verification** → **generation-and-release**: `tests` 依赖 `repo_wiki.orchestration`
- **verification** → **quality-gates**: `tests` 依赖 `repo_wiki.verifier`
- **verification** → **ready-release-viewing**: `tests` 依赖 `repo_wiki.viewer`
- **verification** → **editor-integration**: `tests` 依赖 `extensions/repo-wiki-browser`
- **verification** → **agent-integration**: `tests` 依赖 `plugins/repo-wiki`
- **source-of-truth** ← **verification**: `ai/source-of-truth` 被 `tests` 依赖
- **agent-integration** ← **verification**: `plugins/repo-wiki` 被 `tests` 依赖
- **cli-core** ← **verification**: `repo_wiki` 被 `tests` 依赖
- **cli-core** ← **editor-integration**: `repo_wiki` 被 `extensions/repo-wiki-browser` 依赖
- **generation-and-release** ← **cli-core**: `repo_wiki.orchestration` 被 `repo_wiki` 依赖
- **generation-and-release** ← **ready-release-viewing**: `repo_wiki.orchestration` 被 `repo_wiki.viewer` 依赖
- **generation-and-release** ← **editor-integration**: `repo_wiki.orchestration` 被 `extensions/repo-wiki-browser` 依赖
- **generation-and-release** ← **verification**: `repo_wiki.orchestration` 被 `tests` 依赖
- **quality-gates** ← **cli-core**: `repo_wiki.verifier` 被 `repo_wiki` 依赖
- **quality-gates** ← **verification**: `repo_wiki.verifier` 被 `tests` 依赖
- **ready-release-viewing** ← **editor-integration**: `repo_wiki.viewer` 被 `extensions/repo-wiki-browser` 依赖
- **ready-release-viewing** ← **verification**: `repo_wiki.viewer` 被 `tests` 依赖

---

## 阅读导航

- [项目概览](00-overview.md) - 快速了解项目定位和能力
- [系统架构](01-architecture.md) - 了解三层架构设计
- [API 契约](04-api-contracts.md) - 查看服务间接口定义
- [数据模型](05-data-model.md) - 了解核心实体关系
- [Section 页](sections/services/index.md) - 按服务专题深入阅读
