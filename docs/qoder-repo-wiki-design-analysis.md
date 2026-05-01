# Qoder 风格 Repo-Wiki 设计分析

文档属性：设计分析  
分析对象：`/Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas` 的 qoder 风格知识库输出  
分析目标：总结 qoder 风格 `repo-wiki` 的存储结构、知识组织方式、文档中心规划原则，并作为后续 `repo-agent` 重构基线

## 1. 结论先行

当前我们生成的结果质量低，核心不是“少写了几段话”，而是**设计目标错了**。

我们现在的实现更像：

- 一个把扫描结果直接平铺成几份 Markdown 的导出器
- 一个以模块为中心的结构化索引器
- 一个能过部分治理检查的最小流水线

而 qoder 风格的输出更像：

- 一个“文档中心”
- 一个“面向人阅读的知识库”
- 一个“运行时索引层 + 读者视图层”明确分离的双层系统

这两者的差别不在于模板，而在于**信息架构**。

## 2. 实际产物盘点

基于目标仓库的实际输出，可以把 qoder 风格 `repo-wiki` 划分为四层。

### 2.1 运行时存储层

隐藏目录 `.repo-wiki/` 负责索引、缓存和图谱，不直接面向人阅读。

实际结构如下：

```text
.repo-wiki/
├── cache/
│   ├── generation_cache.sqlite3
│   └── diskcache/
├── graph/
│   ├── knowledge_graph.json
│   ├── impact_cache.json
│   └── dep_matrix.csv
└── index/
    ├── state.sqlite3
    ├── state.sqlite3-shm
    ├── state.sqlite3-wal
    └── chroma/
        └── vectors.json
```

这一层的职责非常明确：

- `index/` 是操作性知识底座，保存 chunk、符号、哈希、FTS、向量索引状态
- `graph/` 是依赖关系和影响链缓存
- `cache/` 是生成缓存，不是事实源

结论：`.repo-wiki/` 不是文档中心，而是**知识引擎的存储层**。

### 2.2 结构化事实层

`ai/source-of-truth/` 是扫描后稳定落盘的结构化事实层。

实际结构如下：

```text
ai/source-of-truth/
├── repo-map.yaml
├── module-index.yaml
├── api-index.yaml
├── data-models.yaml
├── task-catalog.yaml
├── task-catalog.generated.json
└── prompt-fragments/
    ├── overview.txt
    └── architecture.txt
```

这一层面向机器和 Agent，职责是：

- 提供统一事实源
- 作为文档生成、适配器生成、治理检查的输入
- 在运行时存储层和面向人的文档层之间做稳定过渡

结论：这一层是**契约层**，不是最终阅读层。

### 2.3 文档中心层

真正的 qoder 风格价值不在 `.repo-wiki/`，而在 `docs/` 作为“平台文档中心”的组织方式。

目标仓库里已经存在一个成熟的文档中心结构：

```text
docs/
├── ATLAS_平台文档中心/
│   ├── 01_战略规划/
│   ├── 02_平台总览/
│   ├── 03_模块设计/
│   ├── 04_Phase演进/
│   ├── 05_验收报告/
│   └── 06_规范标准/
├── Audit/
├── agent-guides/
├── api-atlas-agent/
├── operations/
├── onboarding/
├── sections/
└── ...
```

这个结构说明 qoder 风格知识库不是简单输出五份总览文档，而是把文档划分为：

- 平台总览
- 模块设计
- Phase 演进
- 运维与交接
- 规范标准
- 审计与专题章节

结论：`docs/` 是**面向人和 Agent 的导航层**，而不是 `source-of-truth` 的镜像。

### 2.4 工具适配层

目标仓库还包含：

- `.claude/CLAUDE.md`
- `.claude/settings.json`
- `.codex/config.toml`
- `.codex/hooks.json`
- `.opencode/opencode.json`
- `AGENTS.md`

这一层不是知识本体，而是入口和引用层，职责是：

- 告诉不同工具先读哪里
- 保证路径统一
- 把“阅读顺序”显式化

结论：适配层应该引用文档中心，而不是替代文档中心。

## 3. qoder 风格的核心设计原则

从目标仓库的文档中心和截图导航可以抽象出五条原则。

### 3.1 运行时结构和阅读结构分离

qoder 风格里：

- `.repo-wiki/` 解决“怎么存”
- `ai/source-of-truth/` 解决“什么是真实事实”
- `docs/` 解决“人怎么理解”

我们之前的问题是把这三件事压成了一层，结果就是：

- 能生成
- 能索引
- 但不能读

### 3.2 文档中心优先于模块清单

截图里的导航不是“模块列表”，而是“认知路径”：

- 项目概述
- 架构设计
- 核心服务
- Python 服务
- 数据模型
- API 参考
- 部署运维
- 开发指南
- 安全合规
- 故障排查与维护

这说明 qoder 风格设计的是**读者任务流**，不是代码目录树。

### 3.3 业务域分组优先于物理目录分组

目标仓库的模块很多，但文档中心不会直接按所有仓库顶层目录铺开，而是会重组为更高层的业务域：

- 核心 Java 微服务
- Python AI 服务
- 前端应用
- 数据模型
- API 参考

这意味着 repo-wiki 不能只做“文件夹转模块名”的映射，必须有一层**语义分类层**。

### 3.4 总览文档必须是 prose-first

`docs/00-overview.md`、`docs/01-architecture.md`、`docs/03-module-map.md` 这类文档不能只是列表。

至少要回答：

- 平台是什么
- 解决什么问题
- 主链路是什么
- 模块如何协作
- 当前仓库里哪些能力已经落地
- 读者接下来该读哪里

这类文档的主输出应是段落、表格、章节结构，列表只是辅助。

### 3.5 文档必须有“导航价值”

qoder 风格输出的核心不是把所有事实都塞进一页，而是让用户和 Agent 都能快速定位：

- 先看总览
- 再看某条业务线
- 再看某类 API
- 再下钻到模块或专题

所以真正需要的不只是 Markdown 文件，而是**文档信息架构**。

## 4. 对当前实现的差距诊断

对比 qoder 风格，当前实现至少有六个明确缺口。

### 4.1 缺少文档中心层

我们现在只有：

- `docs/00-overview.md`
- `docs/01-architecture.md`
- `docs/03-module-map.md`
- `docs/04-api-contracts.md`
- `docs/05-data-model.md`
- `docs/modules/*.md`

缺少：

- 文档目录规划
- 分类索引页
- 章节型专题页
- 业务域导航

### 4.2 缺少语义分组层

当前模块发现更接近物理目录归类，因此会把一些目录直接当成模块输出。  
qoder 风格需要的是：

- 业务域
- 服务族
- 数据模型域
- API 域

这一层必须独立设计，不能依赖扫描器的直接输出。

### 4.3 总览文档缺少文字叙述

你指出的这个问题是对的。  
当前总览文档大多只是：

- 命令列表
- 模块列表
- API 列表
- 数据模型列表

这不足以构成“介绍文档”。

### 4.4 文档粒度不对

当前粒度主要是：

- 仓库级五份总览
- 模块级单页

缺少中间层：

- 服务族级
- 业务域级
- 数据域级
- API 主题级

### 4.5 校验只检查“存在性”，不检查“可读性”

当前 `verify --ci` 主要关注：

- 文件是否存在
- 引用是否有效
- 交叉引用是否成立

但没有检查：

- 总览文档是否包含必要叙述段落
- 目录结构是否完整
- 导航页是否覆盖核心主题
- 数据模型/API 是否经过合理聚合

### 4.6 生成策略仍是“结构化导出器”思维

当前生成层更像：

- 用模板把结构化字段填进去

qoder 风格需要：

- 先做信息架构规划
- 再做章节规划
- 最后再做文本填充

## 5. qoder 风格 repo-wiki 目标蓝图

后续我们应该把 repo-wiki 的目标文档结构调整为三层。

### 5.1 第 1 层：固定总览层

保留固定入口，但重写内容职责：

- `docs/00-overview.md`
  - 项目定位
  - 核心问题
  - 快速开始
  - 阅读导航
- `docs/01-architecture.md`
  - 系统分层
  - 服务协作
  - 核心链路
  - 存储与索引设计
- `docs/03-module-map.md`
  - 业务域分组
  - 服务到业务域映射
  - 上下游关系
- `docs/04-api-contracts.md`
  - 服务族 API 分组
  - 认证与状态码约定
  - 关键入口
- `docs/05-data-model.md`
  - 核心实体
  - 服务专属模型
  - 迁移与持久化结构

### 5.2 第 2 层：文档中心分组层

新增专题层，例如：

- `docs/sections/project/`
- `docs/sections/architecture/`
- `docs/sections/services/`
- `docs/sections/data-model/`
- `docs/sections/api/`
- `docs/sections/operations/`
- `docs/sections/development/`
- `docs/sections/security/`
- `docs/sections/troubleshooting/`

这一层对应截图中的左侧导航。

### 5.3 第 3 层：模块与证据下钻层

保留但收敛用途：

- `docs/modules/<module>.md`
- `ai/source-of-truth/*`
- `.repo-wiki/graph/*`

这层用于追踪事实和技术细节，不承担第一阅读入口职责。

## 6. 对 repo-agent 的设计要求

如果要做出接近 qoder 风格的输出，`repo-agent` 后续必须新增四类能力。

### 6.1 文档信息架构规划器

输入：

- `module-index.yaml`
- `api-index.yaml`
- `data-models.yaml`
- 现有 `docs/`

输出：

- 文档中心目录树
- 章节分类
- 每个章节的来源事实与摘要目标

### 6.2 语义分类器

负责把物理模块归并为：

- 核心服务
- Python 服务
- 前端应用
- 数据模型
- API 参考
- 运维治理

### 6.3 prose-first 文档生成器

要求生成：

- 介绍性段落
- 设计动机
- 关键职责说明
- 读者导航语句

而不是只有清单。

### 6.4 质量校验器升级

新增检查：

- 总览页必须有最小段落数
- 各总览页必须包含固定章节
- section 层必须存在
- 模块不能直接污染一级导航
- API 和数据模型输出必须经过聚合而不是全文枚举

## 7. 建议的验收标准

后续如果按 qoder 风格迭代，建议用下面的标准验收。

### 7.1 结构验收

- 运行时存储层、事实层、文档中心层、适配层边界清晰
- `docs/` 至少包含总览层 + section 层 + 模块层

### 7.2 内容验收

- `00-overview` 和 `01-architecture` 至少能独立让新读者理解项目
- `03-module-map` 不只是模块列表，而是域级映射
- `04-api-contracts` 是按服务族或主题分组，不是原始 endpoint 平铺
- `05-data-model` 是按核心域聚合，不是全量模型长列表

### 7.3 导航验收

- 左侧导航可被静态目录结构推导
- 从总览到专题再到模块的路径清晰

### 7.4 治理验收

- `verify --ci` 同时检查存在性和内容质量
- 生成结果可稳定增量更新

## 8. 最终判断

qoder 风格 `repo-wiki` 的关键不是“生成更多文档”，而是把知识库分成三层：

1. `.repo-wiki/` 负责存储与检索  
2. `ai/source-of-truth/` 负责结构化事实  
3. `docs/` 负责面向人的知识组织与导航

我们当前实现第一层和第二层已经有基础，但第三层仍然明显不足。  
后续重构必须以“文档中心设计”而不是“模板补字数”为主线。
