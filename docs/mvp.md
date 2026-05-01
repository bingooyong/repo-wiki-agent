Repo-Wiki MVP 详细设计说明书

文档目标：将《Repo Wiki Generator 方案设计文档 V2》收敛为一份可直接指导第一阶段研发落地的 MVP 详细设计说明书。

适用范围：本地通用代码仓库知识库构建体系，服务于 Claude Code、OpenCode、Codex 等 AI 编码工具的统一知识底座建设。

⸻

1. 文档目的

本文档用于冻结 Repo-Wiki 的 MVP 研发范围、系统边界、模块设计、数据结构、执行流程、增量更新策略、质量验收标准与交付物，作为下一阶段设计与开发的正式基线。

本文档重点解决以下问题：
	1.	MVP 第一阶段到底做什么
	2.	第一阶段明确不做什么
	3.	各模块如何拆分与协作
	4.	输入、输出、索引、文档的结构如何定义
	5.	如何控制实现复杂度，避免过度设计
	6.	如何判断第一阶段是否开发成功

⸻

2. 产品定义

2.1 产品名称

repo-wiki

2.2 产品定位

Repo-Wiki 是一个面向本地代码仓库的知识底座生成工具。

其核心作用不是提供单次问答，而是通过扫描代码仓、抽取结构化知识、生成标准化文档、构建本地索引与模块依赖图，并同步输出 AI 工具适配层文件，使 Claude Code、OpenCode、Codex 等工具能够共享一套统一的、可持续更新的项目知识体系。

2.3 MVP 阶段核心目标

在一个真实的中型代码仓中，完成以下最小闭环：
	1.	扫描仓库目录、模块、依赖、接口、数据模型
	2.	生成基础 source-of-truth 文件
	3.	生成核心文档底座
	4.	建立本地语义索引
	5.	建立模块级知识图谱
	6.	输出 Claude Code / OpenCode 可消费的适配层文件
	7.	支持基于 Git Diff 的模块级增量更新
	8.	提供基础 verify 能力，检查知识与代码的一致性

2.4 MVP 成功标准

如果一个试点仓库在执行 repo-wiki init 后，能够自动生成可读、可查、可更新、可被至少两个 AI 工具消费的知识底座，并在代码变更后完成受影响模块的增量更新，则认为 MVP 成功。

⸻

3. MVP 范围冻结

3.1 本阶段纳入范围

3.1.1 支持语言
MVP 第一阶段仅支持以下三类主流后端仓库：
	•	TypeScript / JavaScript
	•	Python
	•	Go

3.1.2 支持仓库类型

优先支持以下仓库：
	•	单仓后端服务
	•	API 服务型项目
	•	模块边界相对清晰的业务仓
	•	有明确启动、构建、测试命令的工程仓库

3.1.3 支持的知识抽取对象

MVP 只做以下结构化抽取：
	•	仓库概览信息
	•	模块目录与模块边界
	•	模块间 import / package 依赖
	•	HTTP REST 接口
	•	常见 ORM / Schema / DTO 数据模型
	•	常用命令（start / build / test / lint）
	•	README / package 配置中的项目说明

3.1.4 支持的知识层输出

MVP 只交付以下层：
	•	L0 本地索引层
	•	L1 文档与 source-of-truth 层
	•	L2 AI 指令适配层
	•	L4 基础治理层

L3 技能层只做最小模板，不做复杂动态技能编排。

3.1.5 支持的 AI 工具适配目标

MVP 第一优先级：
	•	Claude Code
	•	OpenCode

MVP 第二优先级：
	•	Codex 仅输出基础配置文件，不作为第一阶段重点验收对象

⸻

4. MVP 明确不做的内容

为了控制第一阶段复杂度，以下内容明确排除在 MVP 范围外：

4.1 不做全面多语言支持

不支持 50+ 语言的全面 AST 能力，仅支持 TS/JS、Python、Go。

4.2 不做函数级全量调用图

MVP 不构建精确的函数级调用图，不做跨语言 symbol 级全局依赖追踪。

4.3 不做复杂事件流与消息流统一建模

暂不支持：
	•	Kafka / MQ 全链路事件拓扑
	•	gRPC 深度契约抽取
	•	GraphQL 全 schema 关系图

4.4 不做多向量后端并行支持

MVP 仅实现 ChromaDB 本地持久化。

以下后端后置：
	•	Qdrant
	•	FAISS
	•	Lance

4.5 不做 section patch 级文档更新

MVP 增量更新采用“模块级整篇重生成”，不做文档小节级 patch。

4.6 不做完整前端可视化平台

MVP 可选提供简单的 CLI 输出，不做复杂 Web UI。

4.7 不做复杂自动化技能生成系统

只输出固定模板 skill 文件，不自动推理生成复杂技能。

⸻

5. 总体架构

5.1 MVP 架构原则

MVP 架构遵循以下原则：
	1.	本地优先
	2.	静态分析优先，LLM 作为增强层而非基础依赖
	3.	可解释优先，避免黑盒生成
	4.	模块级最小闭环优先
	5.	先正确，再优化
	6.	先单仓可用，再考虑多仓与平台化

5.2 MVP 逻辑架构

repo-wiki
├── cli/                    # 命令入口层
├── scanner/                # 静态扫描层
├── indexer/                # 本地索引层
├── graph/                  # 模块级依赖图构建层
├── generator/              # 文档生成层
├── adapter/                # AI 工具适配层
├── verifier/               # 校验层
├── templates/              # 文档/配置模板
└── core/                   # 配置、模型、缓存、公共能力

5.3 模块职责划分

cli/
负责：
	•	命令注册
	•	参数解析
	•	执行流程编排
	•	控制台输出

scanner/
负责：
	•	文件遍历
	•	语言与框架识别
	•	模块发现
	•	接口抽取
	•	数据模型抽取
	•	依赖关系抽取
	•	仓库统计信息汇总

indexer/
负责：
	•	代码切块
	•	Embedding 生成
	•	本地向量库写入
	•	symbols / hash / meta 文件写入

graph/
负责：
	•	构建模块级依赖图
	•	计算上下游依赖关系
	•	输出知识图谱 JSON 与依赖矩阵
	•	预计算 impact cache

generator/
负责：
	•	组织 LLM 输入上下文
	•	应用 prompt 模板
	•	按文档类型生成 Markdown / YAML / TXT
	•	执行缓存复用

adapter/
负责：
	•	生成 .claude/CLAUDE.md
	•	生成 AGENTS.md
	•	生成 .opencode/opencode.json
	•	生成 .codex/config.toml 的基础版本

verifier/
负责：
	•	检查 source-of-truth 是否完整
	•	检查 docs 是否覆盖模块
	•	检查接口/模型变更后文档是否同步
	•	输出校验结果和告警

⸻

6. 技术选型冻结

6.1 开发语言
	•	Python 3.11+

6.2 核心技术栈

能力	技术选型	备注
CLI	Typer + Rich	命令行与输出
配置管理	Pydantic v2 + YAML	配置校验
文件过滤	pathspec	对齐 .gitignore
AST / 代码解析	tree-sitter	TS/JS、Python、Go
向量库	ChromaDB	本地持久化
Embedding	sentence-transformers（本地）	本地优先
图谱构建	networkx	模块级依赖图
模板	Jinja2	文档模板渲染
LLM SDK	Anthropic Python SDK	主模型调用
缓存	SQLite + diskcache	结果缓存
哈希	xxhash	文件变更检测

6.3 技术取舍原则

对于所有可选方案，遵循以下取舍顺序：
	•	优先本地运行
	•	优先实现简单
	•	优先便于调试
	•	优先具备稳定 Python 生态
	•	优先适合单机单仓使用

⸻

7. 命令设计

7.1 MVP 命令清单

repo-wiki init
repo-wiki index
repo-wiki update
repo-wiki verify
repo-wiki sync
repo-wiki search <query>
repo-wiki graph <module>
repo-wiki cost-estimate

7.2 命令说明

repo-wiki init
用途：首次初始化知识底座。

执行内容：
	1.	扫描仓库
	2.	输出 source-of-truth
	3.	建立本地索引
	4.	构建模块级图谱
	5.	生成核心文档
	6.	生成 AI 适配层文件

repo-wiki index
用途：重建或增量更新本地索引与图谱。

repo-wiki update
用途：基于 git diff 执行模块级增量更新。

repo-wiki verify
用途：检查知识库完整性与一致性。

repo-wiki sync
用途：重生成 AI 适配层文件。

repo-wiki search
用途：在本地索引中做语义检索。

repo-wiki graph
用途：查看模块级依赖关系与影响链。

repo-wiki cost-estimate
用途：估算当前仓库初始化时的扫描规模、文档数量与大致 Token 成本。

⸻

8. 扫描器详细设计

8.1 扫描目标

扫描器输出的核心目的是生成一份可被索引器、图谱构建器、文档生成器共同消费的结构化仓库中间表示。

8.2 扫描输入

输入对象：
	•	本地 Git 仓库目录
	•	默认读取 .gitignore
	•	默认读取常见工程文件，如 README、package.json、pyproject.toml、go.mod、Dockerfile、Makefile

8.3 扫描输出中间模型

中间模型统一命名为 RepositorySnapshot。

结构草案

repository:
  name: payment-service
  root_path: /workspace/payment-service
  primary_language: typescript
  framework: nestjs
  package_manager: pnpm
  commands:
    start: pnpm start:dev
    test: pnpm test
    build: pnpm build
    lint: pnpm lint
  stats:
    total_files: 432
    total_lines: 124583
    modules: 12
    endpoints: 89
    data_models: 23
modules:
  - name: PaymentModule
    path: src/modules/payment
    language: typescript
    files:
      - src/modules/payment/payment.controller.ts
      - src/modules/payment/payment.service.ts
    exports:
      - PaymentService
      - PaymentController
    depends_on:
      - AuthModule
      - OrderModule
    endpoints:
      - method: POST
        path: /payments
        handler: createPayment
    data_models:
      - Payment
      - Refund

8.4 模块发现策略

MVP 中，模块发现以目录结构与语言约定为主，不做复杂语义推断。

TypeScript / JS
优先识别：
	•	src/modules/*
	•	src/features/*
	•	src/domains/*
	•	packages/*

Python
优先识别：
	•	一级业务包目录
	•	app/modules/*
	•	services/*
	•	domains/*

Go
优先识别：
	•	internal/*
	•	pkg/*
	•	cmd/*
	•	service/*

8.5 接口抽取策略

MVP 只支持 HTTP REST 接口，采用“框架规则 + AST 解析”结合方式。

TypeScript / JS
优先支持：
	•	NestJS Controller / Decorator
	•	Express Router
	•	Fastify Route 声明

Python
优先支持：
	•	FastAPI 路由
	•	Flask Blueprint / route decorator
	•	Django 基础 URL 映射可选支持

Go
优先支持：
	•	Gin 路由注册
	•	Fiber 路由注册
	•	原生 net/http 简单路由

8.6 数据模型抽取策略

MVP 仅抽取以下对象：
	•	ORM Model
	•	DTO / Schema
	•	Migration 中的数据表信息摘要

不过第一阶段不要求完整字段血缘分析，只需要输出数据模型名称、来源文件、所属模块。

8.7 依赖关系抽取策略

MVP 依赖关系只做模块级：
	•	import / require 引用
	•	package / module 引用
	•	跨模块调用痕迹

最终输出：
	•	depends_on
	•	depended_by

不要求函数级调用图。

8.8 扫描器优先级实现顺序

必须按以下顺序落地：
	1.	文件遍历与过滤
	2.	语言识别与仓库元信息抽取
	3.	模块发现
	4.	模块级依赖抽取
	5.	接口抽取
	6.	数据模型抽取
	7.	命令与工程配置抽取

⸻

9. 索引层详细设计

9.1 索引层目标

索引层目标不是取代文档，而是为以下能力提供支撑：
	•	本地语义搜索
	•	大仓库场景下的上下文裁剪
	•	模块文档生成时的相关片段召回
	•	增量更新时的受影响内容定位

9.2 索引存储位置

.repo-wiki/
├── index/
│   ├── chroma/
│   ├── symbols.json
│   ├── file-hash.json
│   └── meta.json

9.3 代码切块策略

MVP 仅支持三种切块粒度，按顺序选择：
	1.	function
	2.	class
	3.	module

实际规则
	•	能稳定识别函数时，按函数切块
	•	类文件较强时，按类切块
	•	小文件或无法细分时，按文件级 module chunk

9.4 Chunk 结构定义

{
  "chunk_id": "src/modules/payment/payment.service.ts#createPayment",
  "file_path": "src/modules/payment/payment.service.ts",
  "module_name": "PaymentModule",
  "language": "typescript",
  "chunk_type": "function",
  "symbol_name": "createPayment",
  "line_start": 45,
  "line_end": 102,
  "text": "...",
  "dependencies": ["AuthModule", "OrderModule"]
}

9.5 Embedding 策略

MVP 默认：
	•	本地 embedding 模型
	•	不依赖外部 API
	•	支持离线使用

9.6 Hash 策略

file-hash.json 用于判断文件是否变化。

规则：
	•	每个已纳入知识库的文件生成 xxhash
	•	update 时仅处理 hash 变化文件
	•	被删除文件触发索引删除与模块重算

⸻

10. 图谱层详细设计

10.1 MVP 图谱目标

MVP 图谱只解决一个核心问题：

模块变更后，会影响哪些上下游模块。

10.2 图谱粒度冻结

MVP 仅构建模块级知识图谱，不构建函数级调用图。

10.3 节点类型

MVP 节点只包含：
	•	Module
	•	Interface
	•	DataModel

10.4 边类型

MVP 只包含：
	•	Module -> Module: DEPENDS_ON
	•	Module -> Interface: EXPOSES
	•	Module -> DataModel: USES
	•	Interface -> Module: BELONGS_TO

10.5 图谱输出文件

.repo-wiki/graph/
├── knowledge_graph.json
├── dep_matrix.csv
└── impact_cache.json

10.6 impact_cache 设计

为每个模块预计算以下内容：
	•	直接上游模块
	•	直接下游模块
	•	深度 2 的间接影响模块
	•	该模块暴露的接口清单
	•	该模块关联的数据模型

示例：

{
  "PaymentModule": {
    "upstream": ["AuthModule", "OrderModule"],
    "downstream": ["ReconcileModule", "WebhookModule"],
    "depth2": ["NotificationModule"],
    "interfaces": ["POST /payments", "GET /payments/:id"],
    "models": ["Payment", "Refund"]
  }
}


⸻

11. 文档生成层详细设计

11.1 文档生成目标

MVP 文档生成层用于建立统一知识底座，而不是生成面面俱到的百科式描述。

文档重点要求：
	•	结构清晰
	•	可快速理解
	•	可指导 AI 消费
	•	可被工程人员人工校验
	•	支持后续增量更新

11.2 MVP 生成文档范围

docs/
	•	docs/00-overview.md
	•	docs/01-architecture.md
	•	docs/03-module-map.md
	•	docs/04-api-contracts.md
	•	docs/05-data-model.md
	•	docs/modules/<module>.md

ai/source-of-truth/
	•	repo-map.yaml
	•	module-index.yaml
	•	api-index.yaml
	•	data-models.yaml
	•	task-catalog.yaml
	•	prompt-fragments/overview.txt
	•	prompt-fragments/architecture.txt

11.3 每类文档的生成方式

静态生成优先
以下文档优先由扫描器直接生成：
	•	repo-map.yaml
	•	api-index.yaml
	•	data-models.yaml

静态 + LLM 增强
以下文档采用静态信息为主、LLM 润色与组织为辅：
	•	module-index.yaml
	•	00-overview.md
	•	01-architecture.md
	•	03-module-map.md
	•	04-api-contracts.md
	•	05-data-model.md
	•	docs/modules/.md

11.4 模块文档标准结构

# PaymentModule

## 职责

## 模块边界

## 对外接口

## 核心数据模型

## 依赖关系

## 关键处理流程

## 风险点与注意事项

## 常用验证命令

11.5 上下文构建策略

MVP 不做过于复杂的 Token 调度器，采用简单三段式策略：

小模块
直接注入完整代码摘要

中等模块
注入：
	•	模块元数据
	•	接口列表
	•	数据模型列表
	•	Top-K 检索结果

大模块
仅注入：
	•	模块摘要
	•	图谱上下游
	•	Top-K 代码块
	•	关键配置/接口摘要

11.6 缓存策略

文档生成前计算输入哈希：
	•	若输入未变化，则跳过生成
	•	若输入变化，则整篇重生成

⸻

12. AI 适配层详细设计

12.1 适配层目标

适配层的目的不是复制知识，而是为不同 AI 工具提供统一入口，使其能优先读取 Repo-Wiki 生成的知识底座。

12.2 Claude Code 输出

.claude/
├── CLAUDE.md
├── settings.json
└── skills/
    ├── repo-explain/SKILL.md
    ├── change-impact/SKILL.md
    └── doc-refresh/SKILL.md

12.3 OpenCode 输出

AGENTS.md
.opencode/
└── opencode.json
.agents/skills/

12.4 Codex 输出

MVP 仅输出基础文件：

.codex/
├── config.toml
└── hooks.json

不将 Codex 作为第一阶段重点联调对象。

12.5 适配层内容原则

适配层文件必须满足：
	•	不重复承载大段项目知识
	•	只做导航、规则、引用
	•	所有关键知识都指向 docs/ 与 source-of-truth/
	•	规则应尽量简明，避免指令过载

⸻

13. 增量更新设计

13.1 增量更新目标

在代码仓发生局部变更后，不重新全量生成整个知识底座，而只更新受影响的模块与文档。

13.2 MVP 增量更新粒度冻结

MVP 增量更新最小粒度为：

文件级检测，模块级更新。

13.3 增量更新流程

git diff / file hash compare
    ↓
识别变更文件
    ↓
映射到所属模块
    ↓
基于依赖图计算受影响模块
    ↓
更新相关 chunk / hash / graph
    ↓
重生成受影响模块文档
    ↓
必要时重生成全局文档
    ↓
同步适配层

13.4 全局文档更新规则

以下文档在模块变化时按规则判断是否重生成：
	•	03-module-map.md：新增/删除模块时重生成
	•	04-api-contracts.md：接口发生变化时重生成
	•	05-data-model.md：数据模型发生变化时重生成
	•	01-architecture.md：架构目录或主依赖关系变化时重生成
	•	00-overview.md：仅在项目元信息变化时重生成

13.5 不做的能力

MVP 不做：
	•	symbol 级精确变更更新
	•	文档 section patch
	•	多轮自动修复生成

⸻

14. 校验与治理设计

14.1 verify 目标

verify 命令用于检查知识库是否具备最基本的一致性与可用性。

14.2 verify 检查项

MVP 检查以下内容：
	1.	必需文件是否存在
	2.	所有模块是否有对应模块文档
	3.	接口索引与模块索引是否能互相映射
	4.	数据模型索引是否存在悬空引用
	5.	代码变更后对应文档是否过期
	6.	AI 适配层文件是否引用正确路径

14.3 校验结果分级
	•	PASS：通过
	•	WARN：存在风险，但不阻断
	•	FAIL：必须修复

14.4 CI 集成范围

MVP 只要求支持基础 CI 集成：
	•	运行 repo-wiki verify --ci
	•	输出机器可读结果
	•	对 FAIL 场景返回非零退出码

⸻

15. 安全与过滤设计

15.1 安全原则

Repo-Wiki 是企业内部知识底座工具，MVP 必须默认保守。

15.2 默认排除内容

以下内容默认不进入知识库：
	•	.env*
	•	node_modules/
	•	dist/
	•	build/
	•	coverage/
	•	大型日志文件
	•	编译生成物
	•	二进制文件
	•	明显包含密钥、token、证书的文件

15.3 内容级过滤

在索引与文档生成前，执行轻量级敏感信息扫描，至少检测：
	•	API Key
	•	Access Token
	•	私钥内容
	•	数据库连接串
	•	生产域名/IP 模式

15.4 脱敏策略

发现敏感片段时：
	•	默认不写入索引正文
	•	在摘要中以 [REDACTED] 代替
	•	记录告警，但不暴露原始值

⸻

16. 配置文件设计

16.1 配置文件路径

repo-wiki.config.yaml

16.2 MVP 配置结构

project:
  name: auto
  language: auto
  framework: auto

scan:
  include_patterns: []
  exclude:
    - node_modules/
    - dist/
    - build/
    - coverage/
    - .git/
    - .env
    - .env.*

index:
  enabled: true
  vector_backend: chromadb
  embedding_model: local
  chunk_strategy: auto

llm:
  provider: anthropic
  model_init: claude-opus-4-5
  model_update: claude-sonnet-4-5
  model_verify: claude-haiku-4-5-20251001
  max_concurrent: 3
  cache: true

output:
  docs_dir: docs/
  ai_dir: ai/source-of-truth/
  index_dir: .repo-wiki/
  claude_dir: .claude/

security:
  redact_secrets: true
  skip_binary_files: true
  max_file_size_kb: 512


⸻

17. 数据结构与 Schema 冻结

17.1 RepositorySnapshot

作用：扫描阶段统一中间模型。

核心字段：
	•	repository
	•	modules
	•	endpoints
	•	data_models
	•	commands
	•	stats

17.2 repo-map.yaml

用途：仓库总览。

必须字段：
	•	name
	•	language
	•	framework
	•	package_manager
	•	entry_points
	•	key_directories
	•	commands
	•	stats
	•	last_scanned

17.3 module-index.yaml

用途：模块目录。

每个模块必须字段：
	•	name
	•	path
	•	responsibility
	•	exports
	•	depends_on
	•	depended_by
	•	interfaces
	•	data_models
	•	owner
	•	doc_path

17.4 api-index.yaml

每个接口必须字段：
	•	method
	•	path
	•	module
	•	handler
	•	file_path

17.5 data-models.yaml

每个模型必须字段：
	•	name
	•	type
	•	module
	•	file_path

⸻

18. 试点仓库验收方案

18.1 试点仓库要求

首个试点仓库应具备：
	•	中型规模
	•	模块划分较清晰
	•	有 REST API
	•	有 README
	•	有 build / test / lint 命令
	•	有真实业务模块关系

18.2 试点验收步骤

步骤 1：初始化
执行：

repo-wiki init

验证：
	•	目录是否生成完整
	•	source-of-truth 是否可读
	•	文档是否结构化
	•	AI 适配层是否生成

步骤 2：检索
执行：

repo-wiki search "支付退款逻辑在哪里"

验证：
	•	Top-3 结果是否基本相关
	•	结果是否可解释

步骤 3：图谱
执行：

repo-wiki graph PaymentModule

验证：
	•	是否能展示上下游模块
	•	影响链是否符合人工认知

步骤 4：增量更新
修改一个模块后执行：

repo-wiki update

验证：
	•	仅受影响模块是否被更新
	•	全局文档是否按规则更新

步骤 5：校验
执行：

repo-wiki verify

验证：
	•	是否能发现缺失文档或引用错误

⸻

19. MVP 验收指标

19.1 功能验收指标

指标	目标
模块识别准确率	≥ 85%
REST 接口抽取准确率	≥ 90%
模块文档覆盖率	≥ 80%
Top-3 语义检索命中率	≥ 70%
模块级影响链合理性	主要模块人工认可
初始化成功率	试点仓库 100% 可运行

19.2 工程验收指标

指标	目标
本地初始化可执行	是
update 可执行	是
verify 可执行	是
Claude Code 适配可用	是
OpenCode 适配可用	是
关键输出文件完整	是


⸻

20. 开发里程碑与阶段闸门

20.1 里程碑 M1：设计冻结

交付物：
	•	MVP 详细设计说明书
	•	Schema 规范
	•	配置规范
	•	试点仓库清单

通过条件：
	•	范围冻结
	•	数据结构冻结
	•	验收标准冻结

20.2 里程碑 M2：扫描器可用

交付物：
	•	scanner 初版
	•	repo-map.yaml
	•	module-index.yaml

通过条件：
	•	可识别模块
	•	可输出基础 source-of-truth

20.3 里程碑 M3：索引与图谱可用

交付物：
	•	indexer 初版
	•	graph 初版
	•	search / graph 命令

通过条件：
	•	能构建本地索引
	•	能输出模块依赖图

20.4 里程碑 M4：文档生成可用

交付物：
	•	docs/
	•	prompt-fragments/
	•	task-catalog.yaml

通过条件：
	•	overview / architecture / module docs 可生成

20.5 里程碑 M5：适配层与校验闭环

交付物：
	•	Claude / OpenCode 适配层
	•	verify 命令
	•	基础 CI 集成

通过条件：
	•	两个 AI 工具可消费知识底座
	•	verify 能识别基础不一致问题

⸻

21. 最终实施建议

21.1 研发策略建议

第一阶段务必坚持：
	•	单仓先跑通
	•	模块级先跑通
	•	文档可读先跑通
	•	检索可用先跑通
	•	增量更新能用即可，不追求过度精细

21.2 研发风险控制建议

重点防止以下问题：
	•	一开始支持过多语言和框架
	•	图谱做得过深过细
	•	过早追求函数级精确变更分析
	•	适配层承载过多内容导致维护困难
	•	没有试点仓库就泛化设计

21.3 一句话执行原则

MVP 的核心不是把 Repo-Wiki 做成“最强”，而是尽快做成“真实仓库可用、知识底座可复用、两个 AI 工具可消费、更新机制可闭环”。

⸻

22. 结论

本说明书冻结后的 Repo-Wiki MVP，已经具备直接进入第一阶段研发的条件。

建议下一步基于本文档继续输出两份配套文档：
	1.	《Repo-Wiki 数据结构与 Schema 规范》
	2.	《Repo-Wiki 开发排期与任务分解表》

这样就可以从方案评审，正式切换到研发实施。

⸻

文档属性：MVP 详细设计说明书
适用阶段：第一阶段设计冻结与开发实施
输出格式：Markdown，可直接导出归档