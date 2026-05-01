# Qoder Repo-Wiki SQLite 设计分析

文档属性：设计分析  
分析对象：`/Users/bingooyong/Code/01Code/github.com/bingooyong/AI_API_Atlas/.repo-wiki/` 中 qoder 风格 repo-wiki 的 SQLite 使用方式  
分析目标：回答两个问题

1. qoder 风格 repo-wiki 为什么大量使用 SQLite  
2. `repo-agent` 后续是否需要继续把 SQLite 规划成一等能力

## 1. 结论先行

需要，而且不是“顺手加一个 SQLite 文件”这么简单，而是应该把 SQLite 明确规划成 **repo-wiki 的本地操作性知识底座**。

从 qoder 风格产物看，SQLite 承担的不是单一职责，而是三类职责：

- 本地状态库
- 全文检索与召回入口
- 生成缓存与运行元数据存储

这说明 qoder 风格并不是“文件生成完就结束”的思路，而是把 repo-wiki 视为一个持续运行、可增量更新、可检索、可缓存的本地知识系统。

如果只保留 YAML/Markdown/JSON 输出，而不把 SQLite 规划清楚，repo-wiki 最终很容易退化成：

- 一次性导出器
- 无法精细增量更新的静态产物集合
- 很难做稳定检索和缓存命中的知识快照

所以，从架构上看，SQLite 应该继续保留，并且需要被更明确地分层规划。

## 2. qoder 产物里的 SQLite 实际落点

在目标仓库中，`.repo-wiki/` 下已经可以看到两个 SQLite 文件：

```text
.repo-wiki/
├── cache/
│   └── generation_cache.sqlite3
└── index/
    └── state.sqlite3
```

同时还伴随：

- `state.sqlite3-shm`
- `state.sqlite3-wal`
- `diskcache/`
- `graph/*.json`
- `index/chroma/vectors.json`

这说明 qoder 风格不是用一个 SQLite 做所有事情，而是已经开始按职责分层：

- `index/state.sqlite3`：主状态库
- `cache/generation_cache.sqlite3`：生成缓存库
- `diskcache/`：辅助缓存层
- `graph/`：图谱和影响链落盘
- `chroma/`：向量索引落盘

## 3. `state.sqlite3` 的真实职责

从实际 schema 看，`state.sqlite3` 不是一个简单的 KV 库，而是完整的本地操作数据库。

### 3.1 实际表结构

当前 `state.sqlite3` 中可见的核心表包括：

| 表名 | 职责 |
|------|------|
| `schema_migrations` | 数据库版本与迁移记录 |
| `files` | 文件级状态、模块归属、hash、mtime |
| `file_hashes` | 文件 hash 快照 |
| `chunks` | 代码切块后的主数据 |
| `chunks_fts` | FTS5 全文检索虚表 |
| `symbols` | 符号级索引 |
| `generation_cache` | 运行态生成缓存元数据 |
| `verify_runs` | 验证执行记录 |
| `metadata` | 其他元数据 |

这套结构说明它解决的是“repo-wiki 运行时怎么知道自己当前处于什么状态”。

### 3.2 实际规模

在当前 `AI_API_Atlas` 样本中，`state.sqlite3` 已经存入了真实运行数据：

| 对象 | 数量 |
|------|------|
| `files` | 4534 |
| `chunks` | 17532 |
| `symbols` | 12998 |
| `file_hashes` | 4534 |
| `generation_cache` | 0 |
| `verify_runs` | 0 |

这说明 SQLite 在 qoder 风格里不是装饰物，而是真正在承载“可查询的本地知识状态”。

### 3.3 FTS5 的角色

`chunks_fts` 使用 FTS5 虚表，字段包括：

- `text`
- `module_name`
- `file_path`
- `symbol_name`

这代表 SQLite 在这里的作用，不只是存元数据，而是直接承担：

- lexical retrieval
- BM25/全文召回入口
- semantic retrieval 之前的硬过滤和文本召回

换句话说，qoder 风格并不是“全靠向量库找内容”，而是：

- SQLite 负责结构化状态和词法召回
- 向量库负责语义召回
- 图谱负责关系扩展

## 4. `generation_cache.sqlite3` 的真实职责

第二个 SQLite 文件 `cache/generation_cache.sqlite3` 很轻量，当前只有一张表：

| 表名 | 字段 |
|------|------|
| `generation_cache` | `key`, `value`, `created_at` |

当前样本里这张表有 `33` 条缓存记录。

这说明 qoder 风格把“生成缓存”从主状态库中拆出来了。这样做有几个明显好处：

1. 不污染主状态库
2. 缓存可以独立清理或失效
3. 生成链路可以单独优化
4. 更适合和 `diskcache` 形成两级缓存

这也是一个很重要的设计信号：

> qoder 风格不是把 SQLite 当成单一总库，而是把它按运行职责拆成多个本地数据库。

## 5. qoder 为什么要大量使用 SQLite

从实际产物反推，原因至少有六个。

### 5.1 需要一个稳定的本地 canonical operational store

YAML/JSON/Markdown 更适合：

- 工件输出
- 人类阅读
- Agent 引用

但不适合：

- 高频更新
- 增量变更判断
- FTS 查询
- 缓存命中
- 验证运行历史

SQLite 恰好填补这个空位。

### 5.2 需要在本地做强约束的增量更新

repo-wiki 不只是“全量生成一遍”，还需要知道：

- 哪些文件变了
- 哪些 chunk 失效了
- 哪些模块受影响
- 哪些缓存还能复用

这些状态如果全靠文件系统和 JSON 拼起来，复杂度会越来越高。  
SQLite 能把这些状态统一落到本地，并支持查询和事务。

### 5.3 需要 FTS5 做低成本词法检索

向量库适合语义召回，但不适合替代：

- 精确关键词
- 模块名/接口名定位
- symbol 名称检索
- 文件路径过滤

FTS5 是本地 repo-wiki 场景里性价比非常高的一层。

### 5.4 需要缓存，但又不想把缓存和工件绑死

生成缓存和 embedding 缓存，本质上都属于运行时状态，不应该直接放进：

- `docs/`
- `ai/source-of-truth/`
- 纯 JSON 工件

SQLite 更适合管理这些可失效、可重建、但必须高效查询的运行态数据。

### 5.5 需要低依赖、单机、本地优先

repo-wiki 的目标不是先上服务端，而是：

- 本地跑
- 单机跑
- 多工具共享
- 不依赖外部数据库

在这个约束下，SQLite 几乎是最自然的选择。

### 5.6 需要把“事实层”和“运行层”明确分开

qoder 风格里：

- `ai/source-of-truth/` 是事实层
- `.repo-wiki/*.sqlite` 是运行层

这两层分开之后，系统边界就很清晰：

- 事实层负责对外稳定契约
- 运行层负责检索、缓存、状态、增量

## 6. 这对 `repo-agent` 的启发

### 6.1 已经做对的部分

从当前 `repo-agent` 代码和设计文档看，SQLite 方向本身是对的，已经包括：

- `state.sqlite3` 作为状态库
- FTS5 全文检索
- `generation_cache.sqlite3`
- `diskcache`
- 向量库与图谱分层

所以问题不是“要不要 SQLite”，而是：

> 是否要把 SQLite 规划得更清楚、更稳定、更面向长期演进。

### 6.2 还需要进一步规划的部分

建议后续把 SQLite 规划明确到以下几个层面。

#### A. 明确双库职责

建议固定为：

- `index/state.sqlite3`
  - 文件状态
  - chunk
  - symbols
  - FTS
  - verify runs
  - metadata
- `cache/generation_cache.sqlite3`
  - 文档生成缓存
  - prompt hash / input hash / output hash
  - model/version/cache policy

不要把“事实层”塞回 SQLite，也不要把所有运行态都混成一个总库。

#### B. 明确 SQLite 是 operational layer，不是 source-of-truth

后续文档和实现里应持续强调：

- `ai/source-of-truth/*` 仍然是外部契约层
- SQLite 是内部运行层

否则后面很容易出现两套真相源互相漂移。

#### C. 明确索引链路顺序

建议固定表述为：

1. 扫描生成 `source-of-truth`
2. 写入 `state.sqlite3`
3. 重建 FTS
4. 更新 vector store
5. 更新 graph artifacts
6. 生成文档与适配层

SQLite 应该出现在这个链路的中间，而不是最后附带写一下。

#### D. 增强 SQLite 中与文档中心相关的元数据

如果后续要走 qoder 风格的文档中心路线，建议 SQLite 里逐步补充：

- module -> domain 映射
- section coverage 状态
- doc quality metrics
- regeneration reason
- compare / verify evidence snapshot

这样后面的 `verify --ci`、baseline comparison、incremental generation 才能更稳定。

#### E. 不建议把所有内容都塞进 SQLite

SQLite 很重要，但也不能滥用。

不建议放进去做 canonical truth 的内容：

- 最终 Markdown 文档正文作为唯一真相
- 事实层 YAML 的唯一来源
- 所有图谱最终展示工件

这些仍然应该保留文件工件，因为：

- 人要看
- Agent 要引用
- Git diff 要审阅

## 7. 推荐的 SQLite 规划结论

如果要把结论压缩成一句设计原则，就是：

> SQLite 应该被正式定义为 repo-wiki 的本地操作性知识底座，  
> 负责状态、词法检索、缓存和运行元数据；  
> 但它不替代 `ai/source-of-truth` 和 `docs` 这些外部工件层。

## 8. 建议的后续任务

如果下一步要继续深化 SQLite 规划，建议按下面顺序做。

### 任务 1：补 SQLite 架构说明

把以下内容写进正式设计文档：

- 双库职责
- SQLite / Chroma / Graph 的边界
- SQLite 与 `source-of-truth` 的边界
- SQLite 与文档生成链路的关系

### 任务 2：补 SQLite 运行观测

建议增加：

- 表级统计
- cache hit/miss
- FTS rebuild 时间
- incremental update 受影响行数

### 任务 3：补 SQLite 与文档中心的桥接元数据

尤其是：

- domain mapping
- canonical sections
- doc quality snapshot
- regeneration cause

### 任务 4：补 compare / verify 对 SQLite 的利用

把当前很多依赖文件扫描的质量检查，逐步迁移为：

- 文件工件 + SQLite 元数据 联合判断

这样后续质量门禁会更稳定。

## 9. 一句话回答

如果只回答你的原问题：

> 是，需要继续规划 SQLite，而且应该把它当成 qoder 风格 repo-wiki 的核心运行层来设计。  
> 不是为了“存点数据”，而是为了支撑状态、检索、缓存、增量和治理闭环。
