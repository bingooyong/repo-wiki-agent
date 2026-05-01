# AI_API_Atlas Repo-Wiki 与 Qoder 差距分析

文档属性：差距分析  
分析对象：`/Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas` 当前由 `repo-agent` 生成的 repo-wiki 输出  
对比目标：qoder 风格的“文档中心型知识库”输出  
用途：作为后续任务规划、验收收敛和 Manager 决策的统一输入

## 1. 结论先行

当前 `repo-agent` 为 `AI_API_Atlas` 生成的 repo-wiki，和 qoder 风格相比，**整体差距仍然较大**。

如果用当前 Phase 08 的量化结果表达：

- `verify --ci`：`FAIL`
- 失败 reason codes：`CONTENT_TOO_SHORT`、`ARCH_MERMAID_MISSING`、`STRUCT_MISSING_SECTIONS`、`AGG_API_NOT_GROUPED`、`AGG_DM_NOT_GROUPED`
- qoder 对比得分：`49.3%`

但这个 `49.3%` 不能机械理解为“只差一半”。更准确的说法是：

- **核心流水线能力已经有了**：必需文件、模块文档覆盖、交叉引用、适配器路径、基础导航都已经存在。
- **上层阅读体验和信息架构仍明显不达标**：overview、architecture、section 层、API 聚合页、数据模型聚合页都还没有达到 qoder 风格。
- **当前比较工具本身还有噪声**：section 检查只认 canonical slug 结构，不认 `Q01/S01` 这类现有专题页；baseline comparison 也还需要继续收敛。

所以，当前状态更接近：

> 底层知识底座已可用，但“文档中心层”仍未成型。  
> 这不是小修小补能解决的问题，但也不是推倒重来。

## 2. 定量快照

| 指标 | 当前结果 | 含义 |
|------|----------|------|
| `verify --ci` | `FAIL` | 说明当前输出还不能作为 repo-agent 的生产级知识库产物验收通过 |
| Fail reason codes | 5 个 | 问题集中在 prose、Mermaid、section、API 聚合、DataModel 聚合 |
| qoder 对比得分 | `49.3%` | 只能视为“粗粒度参考”，不能直接当最终成熟度分数 |
| 通过维度 | 2/6 | 目录层级、导航完整性基本可用 |
| 部分通过维度 | 2/6 | prose 密度、聚合质量有基础但明显不足 |
| 失败维度 | 2/6 | section 覆盖、heading 覆盖明显不达标 |

## 3. 差距总表

| 维度 | qoder 风格期望 | 当前 repo-agent 输出 | 差距等级 | 对用户的影响 | 建议后续任务 |
|------|----------------|----------------------|----------|--------------|--------------|
| 文档中心结构 | 有明确的总览层、专题层、模块层、平台文档中心层 | 目前已有总览层和模块层，缺少稳定的 canonical section 层 | 高 | 用户能看到文件，但无法形成稳定阅读路径 | 先补 canonical `docs/sections/**`，再补 section 导航与索引 |
| Section 结构 | `project / architecture / services / data-model / api / operations / development / security / troubleshooting` 这类稳定 slug | `AI_API_Atlas` 现有的是 `Q01-*`、`S01-*` 专题页，不能直接替代 canonical section | 高 | `verify --ci` 无法通过，后续 adapter 也没有稳定入口层 | 新增 canonical section 层，保留 `Q01/S01` 作为补充专题层 |
| 00-overview | prose-first，回答“是什么、为什么、怎么开始、先读什么” | 现在基本是命令、模块、库存列表 | 高 | 用户打开第一页仍然无法快速理解项目 | 重写 `00-overview.md`，固定 5 个章节，显著增加 prose |
| 01-architecture | 有 Mermaid，有三层结构解释，有核心链路 | 当前是模块和 API 清单，没有 Mermaid，没有三层叙述 | 高 | 架构页不能支撑 onboarding、评审和 AI 工具导航 | 重写 `01-architecture.md`，加入 Mermaid 和三层关系说明 |
| 03-module-map | 按业务域展示，不按物理目录平铺 | 当前仍偏向模块清单，没有形成“领域地图” | 中高 | 用户知道有哪些模块，但不知道为什么这么分组 | 加入 domain / service_family / runtime_role，重写域地图 |
| 04-api-contracts | 按服务/API 分组、调用约定、关键入口 API 聚合 | 当前是 endpoint 长列表 | 高 | 文档可查，但不可读，不适合产品/测试/集成方快速使用 | 重写 API 聚合页，固定“分组 + 调用约定 + 关键入口”结构 |
| 05-data-model | 有核心数据模型、服务数据模型、数据库/迁移策略三段 | 当前是模型名长列表，噪声大，重复多 | 高 | 无法提炼核心实体，阅读成本极高 | 重写数据模型总览，增加去重与聚合 |
| prose 密度 | 叙述性说明明显高于清单密度 | 现在 overview/architecture 仍明显是 list-first | 高 | 文档存在但不具备“介绍”和“解释”功能 | 对 overview、architecture、section 页都加 prose 约束 |
| heading 契约 | 标题即认知路径，稳定且可校验 | 当前标题还是 `Commands / Modules / Inventory / API Surface` 这种导出器风格 | 中高 | 用户看到标题也不知道应该读什么 | 引入固定 heading contract，并在 verify 中持续校验 |
| 导航与交叉链接 | overview -> section -> module -> detail 多层联通 | 当前导航基础存在，但更多是路径级跳转，不是阅读级导航 | 中 | 可点开，但不形成文档中心体验 | 补 section index 和横向导航 |
| source-of-truth / 底层索引 | 稳定、可机读、可用于生成和验证 | 这部分整体可用 | 低 | 不是主要瓶颈 | 保持，不作为下一轮主战场 |
| compare / verify 工具 | 能准确分辨“真实差距”和“历史结构差异” | 目前能发现大问题，但对 `Q01/S01` 兼容和 baseline 设定仍有噪声 | 中 | 会放大部分“结构不兼容”问题，影响决策精度 | 调整 comparison harness 与 verify 的解释层，而不是放松 canonical 标准 |

## 4. 已确认的真实差距

下面这些不是工具噪声，而是已经从实际文档内容中确认的真实问题。

### 4.1 `00-overview.md` 仍是导出器视角

当前页面主要只有：

- 仓库路径
- 主语言和框架
- Commands
- Modules
- Inventory

缺少 qoder 风格要求的：

- 项目定位
- 核心问题
- 核心能力
- 快速开始
- 阅读导航

这说明当前页面更像“扫描结果摘要”，不是“项目入口文档”。

### 4.2 `01-architecture.md` 仍是模块/API 摘要

当前页面虽然叫 architecture，但主体仍然是：

- System Summary
- Module Boundaries
- API Surface
- Data Models

缺少：

- Mermaid 图
- 系统分层解释
- `.repo-wiki` / `ai/source-of-truth` / `docs` 三层关系
- 核心数据流和增量治理闭环

### 4.3 `04-api-contracts.md` 和 `05-data-model.md` 仍是原始清单

当前两个文档的问题不是“文件不存在”，而是“文件内容形态错误”：

- `04-api-contracts.md` 是 endpoint dump
- `05-data-model.md` 是 model dump

这说明 Phase 08 报告中“聚合质量不足”是成立的。  
报告里提到的 `raw_count = 0` 更像 comparison 脚本统计口径问题，不影响对“文档结构错误”的判断。

### 4.4 section 层存在，但不是 canonical section 层

`AI_API_Atlas` 并不是没有 `docs/sections/`，而是已经有一整套 `Q01-*` 和 `S01-*` 专题页。  
这说明目标仓库并不缺“专题页意识”，真正缺的是和 repo-agent 新契约对齐的 **canonical section 层**。

这两类结构的关系应该定义为：

- canonical section 层：repo-agent 的主导航层
- `Q01/S01` 层：专题审计/专项治理层

而不是二选一。

## 5. 工具层噪声与判读修正

当前验收结果里，有两类需要你在规划时单独看待的“工具噪声”。

### 5.1 section 对比口径过窄

当前 verifier 和 qoder comparison 工具默认 section 结构必须是：

- `docs/sections/project/index.md`
- `docs/sections/architecture/index.md`
- ...

但 `AI_API_Atlas` 当前的专题页是：

- `docs/sections/Q01-代码质量与可维护性.md`
- `docs/sections/S01-Injection-Checklist.md`
- ...

所以当前工具会把它们判成“section 不存在”。  
这个判定对于“是否满足 canonical section 契约”是对的，但对于“仓库是否已经有专题页积累”是不完整的。

### 5.2 qoder baseline comparison 还不够纯

现有 comparison harness 已经有价值，但还不足以作为最终成熟度评分器。  
至少还需要继续收敛这两点：

- baseline 输入应该更明确地区分“目标仓库现状”和“qoder 期望结构”
- comparison 结果应该把“canonical 缺失”和“已有专题页但未对齐”拆开报告

所以，在后续规划里：

- `49.3%` 可以作为“当前大致位置”
- 不能把它当成绝对精确分数

## 6. 建议的任务分层

为了便于排后续任务，建议把差距分成三层。

### P0：先解决“不能验收”的问题

| 任务 | 目标 |
|------|------|
| P0-1 | 新增 canonical `docs/sections/**` 层，不删除 `Q01/S01` |
| P0-2 | 重写 `docs/00-overview.md`，从 list-first 变为 prose-first |
| P0-3 | 重写 `docs/01-architecture.md`，补 Mermaid 和三层结构 |

### P1：解决“能生成但不可读”的问题

| 任务 | 目标 |
|------|------|
| P1-1 | 重写 `docs/04-api-contracts.md` 为聚合页 |
| P1-2 | 重写 `docs/05-data-model.md` 为三段式聚合页 |
| P1-3 | 重写 `docs/03-module-map.md` 为领域地图 |
| P1-4 | 补 canonical section 页之间的导航、索引和回链 |

### P2：解决“验收工具不够准”的问题

| 任务 | 目标 |
|------|------|
| P2-1 | 调整 qoder comparison harness，拆分 canonical 差距与历史结构差距 |
| P2-2 | 调整 readiness report 表达，避免把工具噪声写成事实缺失 |
| P2-3 | 为 `Q01/S01` 增加“补充专题层”定位，而不是把它们算作错误结构 |

## 7. 推荐的执行顺序

建议下一轮按下面顺序推进：

1. 先补 canonical section 层
2. 再重写 `00-overview.md`
3. 再重写 `01-architecture.md`
4. 然后重写 `04-api-contracts.md` 和 `05-data-model.md`
5. 最后再调 comparison harness 和 readiness report

原因是：

- 先修工具，不能改善实际阅读体验
- 先修文档结构，才能让下一次 compare/verify 更接近真实质量

## 8. 一句话总结

如果用一句话概括当前差距：

> `repo-agent` 已经能为 `AI_API_Atlas` 生成“可落盘、可校验、可导航的知识底座”，  
> 但距离 qoder 风格的“文档中心型知识库”还差一层 canonical section 导航、两页高质量总览文档，以及两页高质量聚合文档。

从任务角度看，下一轮最值得做的，不是继续扩扫描能力，而是把阅读层补完整。
