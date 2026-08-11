# 展示层与 Wiki 生成层优化路线图

**状态：** Draft / backlog-ready
**日期：** 2026-07-08
**范围：** `repo-wiki` CLI、qoder-like Wiki 生成流水线、VS Code/Cursor 插件展示层
**关联文档：**

- `docs/project-analysis.md`
- `docs/operations/vscode-extension-manual-llm-configuration.md`
- `docs/specs/vscode-llm-configuration-spec.md`
- `docs/plans/vscode-llm-configuration-implementation-plan.md`

---

## 1. 总体目标

项目的核心目标不是“生成一堆 Markdown”，而是让用户在本地代码仓库中得到一个 **可信、可验证、可浏览、可持续更新的项目 Wiki**。因此优化应同时推进两层：

1. **展示层**：让用户在 VS Code/Cursor 中知道当前 Wiki 是否可用、是否过期、如何生成、如何定位源码证据。
2. **Wiki 生成层**：让生成内容更准确、更有证据、更少幻觉、更适合按模块/API/数据模型阅读。

---

## 2. 展示层优化路线

### P0：可用性闭环

#### 2.1 LLM 配置状态与引导

**问题：** 当前插件不支持可视化 LLM 配置，但 CLI 生成高质量 Wiki 需要 LLM。用户容易卡在“点击 Update Wiki 但生成失败”。

**目标：** 在插件 UI 中明确显示当前配置状态，并给出下一步。

**任务：**

- 显示当前是否发现 `repo-wiki.yaml` / `.repo-wiki.yaml`；
- 显示 provider、model、base_url、api_key_env；
- 显示 `API Key Present: Unknown/Yes/No`；
- 若当前版本无法检测 SecretStorage，则链接人工配置文档；
- 后续实现 `Test LLM Configuration`，调用 `repo-wiki config --ci`。

**验收：** 用户打开侧栏后能知道下一步是“配置 LLM”“生成 Wiki”“验证发布”还是“刷新浏览”。

#### 2.2 首次使用向导

**任务：**

- 检查 `uv` / `repo-wiki` 是否可用；
- 检查 LLM 配置是否存在；
- 检查 `.repo-agent-eval/repowiki/zh/manifest.json` 是否存在；
- 检查 manifest readiness 与 `navigation_tree`；
- 给出复制命令或一键执行入口。

**推荐提示链：**

```text
No READY Wiki found
→ Configure LLM
→ Run repo-wiki config --ci
→ Generate qoder-like Wiki
→ Verify
→ Release publish
→ Refresh sidebar
```

#### 2.3 READY 缺失状态解释

**问题：** 当前插件只读 READY release；用户只生成 run 目录时会误以为插件坏了。

**任务：**

- 明确区分：未生成、已生成未验证、已验证未发布、release 不 READY、navigation_tree 为空；
- 展示对应命令：
  - `uv run repo-wiki generate --profile qoder-like --output .repo-agent-eval`
  - `uv run repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval`
  - `uv run repo-wiki release-publish --output .repo-agent-eval`

---

### P1：浏览体验升级

#### 2.4 导航树信息架构增强

**任务：**

- 按页面类别分组：项目概览、架构、核心服务、API、数据模型、部署运维、故障排除；
- 页面标题搜索；
- 最近访问；
- 收藏 / Pin；
- 展示页面标签与生成模式。

**验收：** 大型仓库中用户能在 10 秒内定位关键页面。

#### 2.5 页面状态徽标

为每个页面或分组展示：

- fresh / stale；
- verify pass / warn / fail；
- citation coverage；
- LLM generated / rule generated / fallback；
- 页面最后生成时间；
- 对应 git commit。

**验收：** 用户无需打开报告文件即可判断哪些页面可信、哪些页面需要重生成。

#### 2.6 Release manifest 状态面板

展示：

- release readiness；
- wiki git commit / target git commit；
- 当前工作区 git drift；
- 页面数量；
- warning / issue 数；
- LLM provider/model 摘要；
- 最近一次生成 run。

---

### P2：源码联动体验

#### 2.7 Citation 点击跳源码

**目标：** Wiki 中的文件/行号引用可以直接打开源码。

**任务：**

- 解析 citation metadata；
- Webview 中支持 `vscode.open` 跳转；
- Markdown Preview 路径下提供 fallback 链接；
- 引用失效时显示 warning。

#### 2.8 当前文件对应 Wiki 页面

**任务：**

- 在 Explorer / editor title / context menu 添加 “Show in Repo Wiki”；
- 通过 manifest 或 evidence index 找到当前文件关联页面；
- 若页面 stale，提示重新生成。

#### 2.9 变更影响分析展示

**任务：**

- 基于 git diff 和 evidence index，列出受影响页面；
- 支持 “Regenerate affected pages” 的后续能力；
- 在侧栏显示当前变更影响范围。

---

## 3. Wiki 生成层优化路线

### P0：准确性与证据优先

#### 3.1 源码优先的冲突策略

**问题：** 当前历史文档中曾出现语言/框架误判，例如旧文档称项目为 JavaScript/Express，但源码和 `pyproject.toml` 显示核心是 Python CLI。

**规则：** 当事实冲突时，生成层应按以下优先级取证：

```text
源码 / 包配置 / CLI 实际行为 / 插件 manifest
> 当前 README / installation 文档
> repo-wiki.yaml
> 历史 docs
> 旧 ai/source-of-truth 产物
```

**任务：**

- 在 scanner / docs scanner 中记录事实来源与时间；
- 为冲突项打标签：source-conflict、stale-doc、low-confidence；
- Composer 遇到冲突时必须写出“以源码为准”的解释，不传播旧结论。

#### 3.2 强制 evidence/citation

**目标：** 每个关键结论都有证据。

**任务：**

- 页面计划声明 evidence requirements；
- Composer 只能使用 evidence bundle 内事实；
- 关键章节必须附文件路径/行号；
- Verifier 检查引用路径和行号存在；
- 无证据时输出“未在源码中发现”，而不是编造。

#### 3.3 幻觉控制

**任务：**

- 对 API、配置项、命令、数据模型启用严格白名单：必须来自 scanner 或显式文档证据；
- LLM prompt 中加入“不得补全未证实接口”；
- Verifier 检查页面中出现的 API path、class、function、env var 是否可追溯；
- hallucination risk 高的页面不允许 READY 发布。

---

### P1：信息架构和页面质量

#### 3.4 从文件树 Wiki 升级为领域 Wiki

**目标：** 用户按系统理解项目，而不是按目录猜。

**页面族建议：**

- 项目概览；
- 架构设计；
- 核心服务；
- API 参考；
- 数据模型；
- 配置与 LLM 接入；
- 生成/发布工作流；
- VS Code 插件使用；
- 部署运维；
- 故障排除；
- 安全与合规。

#### 3.5 页面类型模板化

不同页面使用不同结构：

| 页面类型 | 必备章节 |
| --- | --- |
| 项目概览 | 项目目标、用户路径、核心命令、输出物 |
| 架构页 | 分层图、数据流、关键模块、边界 |
| 模块页 | 职责、入口、依赖、配置、测试 |
| API 页 | endpoint、请求/响应、鉴权、错误码、源码引用 |
| 数据模型页 | 模型字段、来源文件、关系、迁移/存储 |
| 运维页 | 命令、配置、诊断、发布、回滚 |
| 故障排除 | 症状、原因、诊断命令、修复步骤 |

#### 3.6 阅读路径生成

自动生成面向不同角色的入口：

- 5 分钟了解项目；
- 30 分钟理解架构；
- 如何新增一个 API；
- 如何配置 LLM；
- 如何生成并发布 Wiki；
- 如何排查插件看不到 Wiki。

---

### P1：增量生成与成本控制

#### 3.7 页面级增量更新

**任务：**

- 从 git diff 得到变更文件；
- 通过 module/evidence/page index 找到受影响页面；
- 只重建受影响页面和聚合页；
- manifest 记录本次增量范围。

#### 3.8 保留人工编辑区

支持人工维护内容：

```md
<!-- repo-wiki:manual:start -->
人工补充内容
<!-- repo-wiki:manual:end -->
```

重生成时保留该区域，并在 verifier 中检查 marker 配对。

#### 3.9 LLM 缓存

缓存 key 建议包含：

- prompt hash；
- evidence hash；
- model；
- provider；
- temperature/max_tokens；
- composer version。

**验收：** 未变化页面不重复消耗 LLM 调用。

---

### P2：质量门禁与发布治理

#### 3.10 页面质量评分

每页计算：

- citation coverage；
- source freshness；
- section completeness；
- API coverage；
- data model coverage；
- hallucination risk；
- manual review required。

#### 3.11 READY release gate

READY 前必须满足：

- manifest 存在且 schema 有效；
- `navigation_tree` 非空；
- 引用路径/行号有效；
- 关键页面质量分达标；
- 无高风险 hallucination；
- LLM 配置诊断通过，或显式声明 mock 模式；
- VS Code 插件能读取 release manifest。

#### 3.12 Baseline 对比

保留 qoder-like baseline 对比：

- 页面数量；
- 信息架构完整度；
- 引用密度；
- API / 数据模型覆盖；
- 可读性；
- stale risk。

---

## 4. 推荐优先级

### 近期必须做

1. 当前版本补人工 LLM 配置文档，并在插件 README 链接；
2. 插件实现 LLM 可视化配置 + SecretStorage；
3. READY 缺失状态下显示 generate / verify / release-publish 引导；
4. 生成层实现源码优先冲突策略；
5. 页面关键结论强制 citation。

### 中期增强

1. 页面状态徽标；
2. manifest 状态面板；
3. citation 点击跳源码；
4. 页面级增量更新；
5. LLM 缓存。

### 长期能力

1. 专用 Webview Wiki Viewer；
2. 当前文件到 Wiki 的双向联动；
3. 自动阅读路径；
4. 质量评分趋势；
5. 多仓库 / 多 release 对比。

---

## 5. Backlog 切片

| ID | 任务 | 层级 | 优先级 | 主要产物 |
| --- | --- | --- | --- | --- |
| UX-001 | 人工 LLM 配置文档与插件 README 链接 | 展示层 | P0 | docs + README |
| UX-002 | 插件 LLM 设置与 SecretStorage | 展示层 | P0 | extension settings/commands |
| UX-003 | READY 缺失引导 | 展示层 | P0 | sidebar state UI |
| GEN-001 | 源码优先冲突策略 | 生成层 | P0 | scanner/composer/verifier rules |
| GEN-002 | 强制 citation 覆盖 | 生成层 | P0 | evidence/verifier |
| UX-004 | 页面状态徽标 | 展示层 | P1 | manifest + sidebar |
| GEN-003 | 页面模板体系 | 生成层 | P1 | planner/composer templates |
| GEN-004 | 页面级增量更新 | 生成层 | P1 | impact analyzer |
| UX-005 | Citation 跳源码 | 展示层 | P2 | webview/markdown links |
| GEN-005 | 质量评分与 READY gate | 生成层 | P2 | quality metrics/release gate |

---

## 6. 验收方式

每个优化项都必须提供：

- 用户可见行为；
- 机器可验证测试或命令；
- 文档说明；
- 回滚路径；
- 安全检查，尤其是 LLM/API Key 相关功能。

对当前阶段，最低验收是：

1. 用户知道当前插件不支持 LLM UI 配置；
2. 用户能通过文档完成人工 LLM 配置；
3. 用户知道生成后还需要 verify / release-publish 才能在插件中浏览；
4. 后续实现有明确 backlog 与优先级。
