# Repo Wiki Generator — 方案设计文档 V2

> 基于 LLM 自动生成本地代码仓库 Wiki，兼容 Claude Code / OpenCode / Codex，支持 10 万行以上大型仓库，含本地向量索引与知识图谱。

---

## 前置调研：目标工具技术栈确认

在选型语言前，先明确"消费方"的技术实现，以便判断是否需要语言对齐。

| 工具 | 实现语言 | 运行时 | TUI 框架 | 关键说明 |
|------|----------|--------|----------|----------|
| **Claude Code** | TypeScript（严格模式）| Bun（非 Node.js） | React + Ink | 512K+ 行 TS，1900+ 文件，源码通过 sourcemap 意外暴露 |
| **OpenCode**（sst/opencode） | **双语言混合**：TypeScript（HTTP Server）+ **Go**（TUI） | Bun（JS 侧）+ Go 编译 | Go: Bubble Tea；JS: 自定义 | Client/Server 架构；Bun binary 内嵌 Go TUI 一起打包 |
| **Codex**（OpenAI） | TypeScript / Node.js | Node.js 20+ | 无 TUI，无头模式 | AGENTS.md 优先，支持 .codex/config.toml |

**结论：三个工具都是消费 Markdown 文件的"读者"，与生成工具的语言无关。`repo-wiki` 本身不需要语言对齐，只需输出标准文件结构即可。**

### 语言选型结论：Python（主体）+ TypeScript 可选绑定

| 维度 | Python | TypeScript/Bun |
|------|--------|----------------|
| LLM SDK 生态 | ✅ Anthropic Python SDK、LangChain、LlamaIndex 最完善 | ✅ 官方 TS SDK，但生态偏 API 调用 |
| 向量数据库 | ✅ chromadb、faiss-cpu、qdrant-client 均原生 Python | ⚠️ 大多数通过 HTTP 调用，绑定较弱 |
| AST/代码解析 | ✅ tree-sitter Python binding 最完整 | ✅ 本身就是 JS/TS 解析最强 |
| 知识图谱 | ✅ networkx、neo4j-python-driver 成熟 | ⚠️ 无对应生态 |
| Karpathy RAG 参考实现 | ✅ 全部 Python | — |
| 跨语言项目支持 | ✅ tree-sitter 支持 50+ 语言 | ⚠️ 偏 JS/TS 生态 |
| 打包发行 | ✅ pipx、uv 部署简单 | ✅ Bun 打包成单二进制 |

**选型：Python 3.11+，使用 `uv` 管理依赖，`typer` 做 CLI，可选通过 npm 发布薄包装调用 `repo-wiki` 命令（给 JS 生态用户友好安装）。**

---

## 一、目标与定位（继承 V1，补充大仓扩展）

### 核心目标

构建 CLI 工具 `repo-wiki`，能够：

1. **扫描**本地代码仓库，提取结构性信息
2. **索引**大型代码库（支持 10 万行以上），可选本地向量库或知识图谱
3. **调用 LLM**，Token 成本可控地生成标准化 Wiki 文档体系
4. **输出**兼容 Claude Code、OpenCode、Codex 的适配层文件
5. **持续同步**，在代码变更后增量更新文档

### 扩展目标（V2 新增）

- 大型仓库的本地向量索引（ChromaDB），支持语义搜索减少 Token 消耗
- 知识图谱构建（模块依赖图），可视化和机器可读两用
- Token 成本感知调度（参考 Karpathy RAG + Claude Code 压缩策略）
- 输出文件类型完整规格（精确到每一个文件）
- OpenCode 专项适配（`opencode.json` 的 `instructions` 字段）

---

## 二、整体架构（V2 扩充）

```
repo-wiki/
├── cli/                    # CLI 入口（init / update / verify / sync / index）
├── scanner/                # 仓库扫描器
│   ├── fs_scanner.py       # 文件系统遍历
│   ├── ast_extractor.py    # AST 解析（tree-sitter，50+ 语言）
│   ├── dep_extractor.py    # 依赖图提取
│   └── api_extractor.py    # 接口契约提取
├── indexer/                # ★ V2 新增：大型仓库索引层
│   ├── chunker.py          # 代码切块（按函数/类/模块）
│   ├── embedder.py         # 向量化（local: sentence-transformers / remote: API）
│   ├── vector_store.py     # 向量库封装（ChromaDB 本地优先）
│   └── knowledge_graph.py  # 知识图谱（networkx → GraphML / JSON-LD）
├── generator/              # LLM 调用层
│   ├── scheduler.py        # ★ V2 Token 感知调度器
│   ├── compressor.py       # ★ V2 上下文压缩（仿 Claude Code 三级策略）
│   ├── prompts/            # Jinja2 提示词模板目录
│   └── llm_client.py       # Anthropic SDK 封装（流式、重试、缓存）
├── adapter/                # AI 适配层生成器
│   ├── claude_adapter.py   # CLAUDE.md + settings.json + skills
│   ├── opencode_adapter.py # AGENTS.md + opencode.json instructions
│   └── codex_adapter.py    # AGENTS.md + .codex/ config
├── verifier/               # 文档校验器
└── templates/              # 文档骨架模板
```

### 五层知识体系（V2 升级为五层）

| 层级 | 内容 | 位置 | 更新频率 |
|------|------|------|----------|
| L0 索引层（★ V2 新增） | 代码向量索引、知识图谱、符号表 | `.repo-wiki/index/` | 代码变更时触发 |
| L1 知识底座层 | 项目概览、架构、模块、领域模型、接口规范、Runbook、ADR、任务目录 | `docs/` + `ai/source-of-truth/` | 随代码变更触发 |
| L2 AI 指令层 | Claude 入口、OpenCode 入口、Codex 入口 | `.claude/` + 根目录 + `.codex/` | L1 变更后自动生成 |
| L3 技能层 | repo-explain、change-impact、doc-refresh | `.claude/skills/` + `.agents/skills/` | 初始化后手动维护 |
| L4 治理层 | hooks、rules、CI 校验脚本 | `.claude/` + `.codex/` + `.github/` | 按需调整 |

---

## 三、★ V2 核心新增：大型仓库处理策略

### 规模判断与策略决策树

```
仓库代码行数
    │
    ├── < 1 万行 ─────────────── 直接全量送入 LLM（单次调用）
    │                            无需向量索引
    │
    ├── 1 万 ~ 10 万行 ───────── 分模块送入 LLM
    │                            建轻量符号索引（YAML）
    │                            可选向量索引（建议开启）
    │
    └── > 10 万行 ──────────────── 强制分层处理
                    │
                    ├── 建本地向量库（ChromaDB）
                    ├── 建知识图谱（模块依赖图）
                    ├── LLM 只处理"检索后的相关片段"
                    └── 每次 LLM 调用上下文 ≤ 60K tokens
```

### 向量索引设计（参考 Karpathy RAG 最佳实践）

Karpathy 的 RAG 核心观点：**"检索质量决定生成质量"**，向量检索只是召回手段，真正关键的是分块策略（chunking）和元数据过滤（metadata filtering）。

#### 代码分块策略

与文档 RAG 不同，代码 RAG 需要保持语义完整性：

```python
# 分块粒度（优先级从高到低）
CHUNK_STRATEGIES = [
    "function",          # 函数/方法级别（最小有意义单元）
    "class",             # 类定义（含所有方法）
    "module",            # 模块文件（< 200 行时整体作为一个 chunk）
    "logical_section",   # 按注释/空行分割的逻辑段
]

# 每个 chunk 附带的元数据（关键：支持精确过滤）
CHUNK_METADATA = {
    "file_path": "src/modules/user/user.service.ts",
    "module_name": "UserModule",
    "chunk_type": "function",       # function / class / module
    "symbol_name": "createUser",
    "language": "typescript",
    "dependencies": ["AuthModule", "DatabaseModule"],
    "line_range": [45, 89],
    "last_modified": "2026-03-15",
    "owner": "@team-auth",
    "complexity": "medium",         # 圈复杂度分级
    "has_tests": True,
}
```

#### 向量化策略

```
本地优先（推荐，无 Token 消耗）
  └── sentence-transformers: "BAAI/bge-m3"（多语言，代码效果好）
  └── ollama: nomic-embed-text（本地模型）

远程备选（更高质量，有费用）
  └── voyage-code-3（代码专用，Anthropic 合作）
  └── text-embedding-3-large（OpenAI）
```

#### 向量库选型

| 方案 | 适用场景 | 优势 | 劣势 |
|------|----------|------|------|
| **ChromaDB**（推荐） | 10 万行以下 | 零配置、纯 Python、持久化 | 百万级以上性能下降 |
| **FAISS**（本地高性能） | 10 万行以上，无服务依赖 | 极快、离线 | 无元数据过滤，需自建 |
| **Qdrant**（生产级） | 多人团队、CI 集成 | 强元数据过滤、REST API | 需运行 Docker |
| **Lance**（列存储新秀） | 超大仓库 + 多媒体 | 与 pandas 无缝、Arrow 格式 | 较新，生态待完善 |

**默认选择：ChromaDB（本地持久化）；超大仓库可通过配置切换为 Qdrant。**

### 知识图谱设计

知识图谱解决的问题：**向量检索找到"相似代码"，但找不到"上下游影响链"**。对于"这个函数改了会影响什么"，图遍历比向量检索更精准。

#### 节点类型

```
Module（模块）
  ├── 属性：name, path, language, owner, risk_level
  └── 关系：DEPENDS_ON → Module
            EXPOSES → Interface
            OWNS → Function / Class

Function（函数）
  ├── 属性：name, signature, complexity, has_tests
  └── 关系：CALLS → Function
            IMPLEMENTS → Interface
            MODIFIES → DataModel

DataModel（数据模型）
  ├── 属性：name, type(orm/dto/schema), fields
  └── 关系：USED_BY → Function
            EXTENDS → DataModel

Interface（接口契约）
  ├── 属性：type(http/grpc/event), path, method
  └── 关系：IMPLEMENTED_BY → Function
            CONSUMED_BY → Module
```

#### 存储格式

```
.repo-wiki/
└── graph/
    ├── knowledge_graph.graphml    # 通用格式，可导入 Gephi / Neo4j
    ├── knowledge_graph.json       # JSON-LD，机器可读，给 LLM 用
    ├── dep_matrix.csv             # 模块依赖矩阵（快速扫描用）
    └── impact_cache.json          # 预计算的变更影响链缓存
```

#### 知识图谱用途

- **变更影响分析**：从修改的节点出发，沿 `CALLS`/`DEPENDS_ON`/`USED_BY` 边做 BFS，找出所有传递影响
- **文档生成上下文**：生成某模块文档时，从图中检索其直接上下游，注入 LLM 上下文
- **技术债检测**：找出无测试的高复杂度函数、循环依赖、孤立模块

---

## 四、★ V2 核心新增：Token 成本控制策略

### Claude Code 三级压缩策略参考

根据 Claude Code 泄露源码分析（wavespeed.ai）：

| 压缩级别 | 触发条件 | 策略 | Token 节省 |
|----------|----------|------|-----------|
| **MicroCompact** | 旧工具输出缓存时 | 本地编辑裁剪，零 API 调用 | 10-30% |
| **AutoCompact** | 接近 context window 上限 | 保留 13K token 缓冲，生成 ≤ 20K 结构化摘要 | 50-70% |
| **Full Compact** | 全量压缩 | 重压整个对话，重注入最近 5K/文件 + 活跃计划 + skill schema | 80-90% |

**repo-wiki 的对应策略：**

```python
class TokenBudgetScheduler:
    """
    Token 感知调度器：根据文件规模决定上下文组装策略
    """

    THRESHOLDS = {
        "direct":    10_000,   # < 1万 tokens：直接全量送入
        "chunked":   60_000,   # 1万~6万：分块 + 摘要头
        "rag_only": 200_000,   # > 6万：只送检索结果，不送原文
    }

    def build_context(self, module_info, source_files) -> str:
        total_tokens = self.estimate_tokens(source_files)

        if total_tokens < self.THRESHOLDS["direct"]:
            # 策略 A：直接注入完整源文件
            return self._full_context(module_info, source_files)

        elif total_tokens < self.THRESHOLDS["chunked"]:
            # 策略 B：注入文件摘要 + 关键函数签名
            return self._summarized_context(module_info, source_files)

        else:
            # 策略 C：向量检索相关 chunk，只送 Top-K 结果
            relevant_chunks = self.vector_store.search(
                query=module_info.description,
                filter={"module_name": module_info.name},
                top_k=20,
                max_tokens=40_000,
            )
            return self._rag_context(module_info, relevant_chunks)
```

### 模型分级调用策略（成本优化）

| 任务 | 模型 | 原因 |
|------|------|------|
| 全量 init（质量优先）| `claude-opus-4-5` | 首次生成，质量决定后续可用性 |
| 增量 update | `claude-sonnet-4-5` | 平衡质量与速度 |
| 文档覆盖率校验 | `claude-haiku-4-5-20251001` | 低成本结构化判断 |
| 向量化 embedding | `voyage-code-3`（本地替代 bge-m3） | 代码专用，无需 LLM 调用 |
| 知识图谱构建 | 无 LLM，纯静态分析 | 零 Token 消耗 |

### Token 消耗估算（10 万行 TypeScript 仓库）

```
初始化（全量）：
  • 模块扫描（静态，无 LLM）：0 tokens
  • 向量索引建设（本地 embedding）：0 tokens
  • 知识图谱构建（静态分析）：0 tokens
  • 文档生成（9 类文档 × 平均 3K tokens）：~27,000 tokens
  • 适配层生成（CLAUDE.md + AGENTS.md × 1K）：~2,000 tokens
  ─────────────────────────────────────────────────────
  总计：约 29,000 tokens（约 $0.87 @ Sonnet 4.5 定价）

增量更新（平均每次 PR）：
  • 变更影响分析（利用知识图谱，低 Token）：~500 tokens
  • 受影响文档重新生成（平均 2-3 个文档）：~6,000 tokens
  ─────────────────────────────────────────────────────
  总计：约 6,500 tokens（约 $0.20 @ Sonnet 4.5 定价）
```

---

## 五、CLI 设计（V2 补充 index 命令）

### 命令总览

```bash
repo-wiki init          # 首次初始化，全量扫描并生成 Wiki
repo-wiki index         # ★ V2 新增：建立/更新本地向量索引和知识图谱
repo-wiki update        # 基于 git diff 增量更新（自动调用 index --incremental）
repo-wiki verify        # 校验文档覆盖率与一致性
repo-wiki sync          # 将 L1 知识同步至 L2 适配层文件
repo-wiki search <query>  # ★ V2 新增：在本地向量库语义搜索
repo-wiki graph <module>  # ★ V2 新增：展示模块依赖图（ASCII 或 DOT 格式）
repo-wiki cost-estimate # ★ V2 新增：估算完整初始化的 Token 消耗
repo-wiki serve         # 启动本地预览服务（可选）
```

### `init` 流程（V2 扩充）

```
1. repo-wiki init [--no-index] [--no-graph] [--scale=auto|small|large]
   │
   ├── Phase 1: 静态扫描（零 Token）
   │   ├── 文件系统遍历（gitignore 过滤）
   │   ├── 语言/框架识别
   │   ├── AST 解析（tree-sitter）
   │   ├── 依赖图提取
   │   └── 写入 ai/source-of-truth/*.yaml
   │
   ├── Phase 2: 索引建设（★ V2，零 Token）
   │   ├── 代码分块（函数级/类级）
   │   ├── 本地 embedding（sentence-transformers）
   │   ├── 写入 ChromaDB（.repo-wiki/index/chroma/）
   │   └── 构建知识图谱（.repo-wiki/graph/）
   │
   ├── Phase 3: LLM 文档生成（Token 消耗主体）
   │   ├── Token 估算 → 选择上下文策略（A/B/C）
   │   ├── 并发生成（max_concurrent=3）
   │   └── 写入 docs/
   │
   └── Phase 4: 适配层同步
       ├── 生成 CLAUDE.md
       ├── 生成 AGENTS.md
       ├── 生成 opencode.json（★ V2）
       ├── 生成 skills/
       └── 生成 Makefile
```

---

## 六、完整输出文件规格（★ V2 精确到每一个文件）

### 6.1 L1 知识底座层：`docs/`

| 文件路径 | 类型 | 生成方式 | 更新触发 |
|----------|------|----------|----------|
| `docs/00-overview.md` | Markdown | LLM 生成 | 项目描述/README 变更 |
| `docs/01-architecture.md` | Markdown | LLM 生成 | 架构级目录变更 |
| `docs/02-domain-model.md` | Markdown | LLM 生成 | ORM/Schema 文件变更 |
| `docs/03-module-map.md` | Markdown | LLM 生成 | 新增/删除模块 |
| `docs/04-api-contracts.md` | Markdown | LLM 生成 | 路由/Controller 变更 |
| `docs/05-data-model.md` | Markdown | LLM 生成 | Migration/DTO 变更 |
| `docs/06-deploy-ops.md` | Markdown | LLM 生成 | Dockerfile/CI 变更 |
| `docs/07-troubleshooting.md` | Markdown | LLM 生成 | 手动触发为主 |
| `docs/08-developer-onboarding.md` | Markdown | LLM 生成 | 初始化时生成，手动维护 |
| `docs/09-glossary.md` | Markdown | LLM 生成 | 领域模型变更 |
| `docs/modules/<name>.md` | Markdown | LLM 生成（每模块一文件）| 该模块文件变更 |
| `docs/adr/ADR-NNN-<title>.md` | Markdown | 手动维护模板 | 手动 |
| `docs/adr/_template.md` | Markdown | 工具预置模板 | 不更新 |

**`docs/modules/<name>.md` 标准结构（每个模块生成一个文件）：**

```markdown
# UserModule

## 职责
...

## 对外接口
| 函数名 | 签名 | 用途 |
|--------|------|------|
| createUser | `(dto: CreateUserDto): Promise<User>` | 创建用户 |

## 依赖关系
- 上游依赖：AuthModule, DatabaseModule
- 下游依赖：OrderModule, ProfileModule

## 关键数据流
...

## 风险点
...

## 常见操作示例
...

## 验证命令
```bash
make test-user
```

---
*由 repo-wiki 自动生成 | 最后更新：2026-04-15 | Owner: @team-auth*
```

### 6.2 L0 索引层（★ V2 新增）：`.repo-wiki/`

| 文件路径 | 格式 | 说明 |
|----------|------|------|
| `.repo-wiki/index/chroma/` | ChromaDB 目录 | 向量索引（函数/类级 chunk） |
| `.repo-wiki/index/symbols.json` | JSON | 全量符号表（函数、类、接口名 → 文件路径） |
| `.repo-wiki/index/file-hash.json` | JSON | 文件哈希表，用于增量检测 |
| `.repo-wiki/graph/knowledge_graph.graphml` | GraphML XML | 完整知识图谱，可导入 Gephi |
| `.repo-wiki/graph/knowledge_graph.json` | JSON-LD | 机器可读图谱，供 LLM 注入 |
| `.repo-wiki/graph/dep_matrix.csv` | CSV | 模块依赖矩阵（行=源，列=目标，值=依赖类型） |
| `.repo-wiki/graph/impact_cache.json` | JSON | 预计算变更影响链（键=文件路径） |
| `.repo-wiki/cache/doc-cache.sqlite` | SQLite | LLM 生成结果缓存（输入哈希 → 输出） |
| `.repo-wiki/cache/embedding-cache.sqlite` | SQLite | Embedding 缓存 |
| `.repo-wiki/meta/index.json` | JSON | 索引元数据（版本、模型、创建时间） |

**`.repo-wiki/` 应加入 `.gitignore`（索引是本地衍生物，不需提交）。**

### 6.3 L1 结构化索引层：`ai/source-of-truth/`

| 文件路径 | 格式 | 内容 | 生成方式 |
|----------|------|------|----------|
| `ai/source-of-truth/repo-map.yaml` | YAML | 仓库概览、入口、命令 | 静态扫描生成 |
| `ai/source-of-truth/module-index.yaml` | YAML | 模块列表（职责、依赖、owner） | 静态扫描 + LLM 补充描述 |
| `ai/source-of-truth/ownership.yaml` | YAML | 模块归属（团队/个人） | 扫描 CODEOWNERS + 推断 |
| `ai/source-of-truth/task-catalog.yaml` | YAML | 常见任务目录（步骤 + 验证命令） | LLM 生成 |
| `ai/source-of-truth/api-index.yaml` | YAML | 所有接口路径汇总 | 静态扫描生成 |
| `ai/source-of-truth/data-models.yaml` | YAML | 所有数据模型汇总 | 静态扫描生成 |
| `ai/source-of-truth/prompt-fragments/overview.txt` | TXT | 100 字项目摘要（供 AI 快速理解）| LLM 生成 |
| `ai/source-of-truth/prompt-fragments/architecture.txt` | TXT | 500 字架构摘要 | LLM 生成 |
| `ai/source-of-truth/prompt-fragments/module-<name>.txt` | TXT | 每模块 200 字摘要 | LLM 生成 |

### 6.4 L2 AI 指令层：适配层文件

| 文件路径 | 目标工具 | 格式 | 说明 |
|----------|----------|------|------|
| `.claude/CLAUDE.md` | Claude Code | Markdown | Claude 入口，路由到 L1 知识 |
| `.claude/settings.json` | Claude Code | JSON | 权限配置、环境设置 |
| `.claude/skills/repo-explain/SKILL.md` | Claude Code | Markdown | 项目解释 skill |
| `.claude/skills/change-impact/SKILL.md` | Claude Code | Markdown | 变更影响分析 skill |
| `.claude/skills/doc-refresh/SKILL.md` | Claude Code | Markdown | 文档刷新 skill |
| `AGENTS.md` | OpenCode / Codex | Markdown | 主入口，所有工具共用 |
| `.opencode/opencode.json` | OpenCode | JSON | ★ V2：instructions 字段指向 docs/ |
| `.codex/config.toml` | Codex | TOML | Codex 配置 |
| `.codex/hooks.json` | Codex | JSON | Codex 生命周期 hooks |
| `.codex/rules/default.rules` | Codex | 纯文本 | 命令白名单 |
| `.agents/skills/repo-explain/SKILL.md` | OpenCode | Markdown | 同 Claude 同名 skill |
| `.agents/skills/change-impact/SKILL.md` | OpenCode | Markdown | 同 Claude 同名 skill |
| `.agents/skills/doc-refresh/SKILL.md` | OpenCode | Markdown | 同 Claude 同名 skill |

### 6.5 L4 治理层：CI 与自动化

| 文件路径 | 格式 | 说明 |
|----------|------|------|
| `Makefile`（ai-* targets） | Makefile | ai-init / ai-update / ai-verify / ai-sync |
| `.github/workflows/verify-docs.yml` | YAML | PR 文档一致性校验 |
| `.github/workflows/ai-index-refresh.yml` | YAML | ★ V2：每周定时重建索引 |
| `.git/hooks/post-commit` | Shell | 提交后提示文档更新 |
| `repo-wiki.config.yaml` | YAML | 工具主配置文件（根目录） |

### 文件总数统计

| 层级 | 文件数 | 说明 |
|------|--------|------|
| docs/ | 10 + N（N=模块数） | 文档底座 |
| .repo-wiki/ | ~10 固定 + 动态索引 | 本地索引（gitignore） |
| ai/source-of-truth/ | 6 + N×1（N=模块数） | 结构化索引 |
| 适配层（.claude/ + .agents/ + .codex/）| 14 | AI 工具配置 |
| 治理层 | 5 | CI + 脚本 |
| **合计** | **约 50 + 2N 个文件** | N 为模块数 |

---

## 七、扫描器设计（继承 V1，补充 AST 细节）

### 扫描器能力矩阵

| 扫描目标 | 提取内容 | 实现方式 |
|----------|----------|----------|
| 目录结构 | 模块边界、入口文件、配置文件 | 文件系统遍历 + `.gitignore` 过滤（pathspec） |
| 语言识别 | 主语言、框架、包管理器 | 特征文件检测（package.json/go.mod/pyproject.toml/pom.xml） |
| AST 解析 | 函数签名、类定义、接口 | **tree-sitter**（支持 Python/TS/Go/Java/Rust/C/C++ 等 50+ 语言） |
| 依赖关系 | 外部依赖、内部模块依赖图 | 解析 lock 文件 + import 分析 |
| 接口契约 | HTTP routes、gRPC、事件、消息队列 | 框架特定解析（Express/FastAPI/gin/Spring/NestJS） |
| 数据模型 | ORM 模型、DB Schema、DTO | 解析 ORM 定义 / migration 文件 |
| 配置项 | 环境变量、特性开关、外部服务 | 解析 `.env.example` / config 文件 |
| CODEOWNERS | 模块归属 | 解析 `.github/CODEOWNERS` |

### 扫描输出结构（`ai/source-of-truth/`）

```yaml
# repo-map.yaml（示例）
name: payment-service
language: TypeScript
framework: NestJS
package_manager: pnpm
entry_points:
  - src/main.ts
  - src/app.module.ts
key_directories:
  src/modules: 业务模块（12 个）
  src/shared: 公共工具库
  src/config: 配置层
  src/migrations: 数据库迁移
commands:
  start: pnpm start:dev
  test: pnpm test
  build: pnpm build
  lint: pnpm lint
stats:
  total_lines: 124_583
  total_files: 432
  modules: 12
  api_endpoints: 89
  data_models: 23
repo_wiki_version: "2.0"
last_scanned: "2026-04-15T10:30:00Z"
```

```yaml
# module-index.yaml（示例）
modules:
  - name: PaymentModule
    path: src/modules/payment
    responsibility: 处理支付下单、退款、对账
    exports:
      - PaymentService
      - PaymentController
      - PaymentRepository
    depends_on:
      - AuthModule
      - OrderModule
      - DatabaseModule
    depended_by:
      - ReconcileModule
      - WebhookModule
    interfaces:
      - POST /payments
      - POST /payments/:id/refund
      - GET /payments/:id
    data_models:
      - Payment
      - Refund
    risk_level: critical      # low / medium / high / critical
    owner: "@team-payment"
    test_coverage: 87.3       # 百分比
    has_integration_tests: true
    doc_path: docs/modules/PaymentModule.md
    last_reviewed: "2026-01-20"
```

---

## 八、LLM 生成层设计（V2 补充压缩策略）

### 文档生成策略

每类文档有独立的生成 prompt 模板，采用以下原则：

- **上下文分级注入**：按 Token 预算自动选择策略 A/B/C（见第四章）
- **分段生成**：大型模块拆分多次调用，避免超出 context window
- **增量更新**：`update` 模式只重新生成变更片段，非全量覆盖
- **幂等设计**：相同输入总是产生结构一致的输出（通过模板约束）
- **缓存优先**：SQLite 缓存已生成内容，输入哈希命中则直接返回

### Prompt 模板结构（以 module-doc 为例）

```
system:
  你是一个技术文档工程师，正在为一个生产级代码仓库生成模块文档。
  仓库基本信息：
  <repo_overview>{{ prompt_fragments/overview.txt }}</repo_overview>
  架构摘要：
  <architecture>{{ prompt_fragments/architecture.txt }}</architecture>

user:
  请为以下模块生成标准文档：
  <module_info>{{ module_index_entry }}</module_info>

  [策略 A：直接注入] <source_files>{{ full_source }}</source_files>
  [策略 B：摘要注入] <file_summaries>{{ summaries }}</file_summaries>
  [策略 C：RAG 注入] <relevant_chunks>{{ top_k_chunks }}</relevant_chunks>

  知识图谱中的上下游关系：
  <graph_context>{{ graph_neighbors_json }}</graph_context>

  文档需包含：
  1. 模块职责（2-3 句话，避免废话）
  2. 对外接口（函数签名 + 用途，表格格式）
  3. 依赖关系（上游/下游，说明为什么依赖）
  4. 关键数据流（主链路，步骤列表）
  5. 风险点与注意事项（列举已知陷阱）
  6. 常见操作示例（代码片段）
  7. 验证命令（具体的 make/npm/go 命令）

  输出格式：标准 Markdown，不要加额外解释，直接输出文档正文。
```

### 调用模型选择

| 任务 | 推荐模型 | 理由 |
|------|----------|------|
| 全量初始化 | `claude-opus-4-5` | 质量优先，首次生成 |
| 增量更新 | `claude-sonnet-4-5` | 速度与质量平衡 |
| 快速验证 | `claude-haiku-4-5-20251001` | 低成本快速校验覆盖率 |
| 知识图谱上下文压缩 | `claude-haiku-4-5-20251001` | 把大图谱摘要成小摘要 |

---

## 九、AI 适配层生成（V2 新增 OpenCode 适配）

### CLAUDE.md 生成模板（继承 V1）

```markdown
# Project AI Guide

## Source of truth
<!-- 由 repo-wiki sync 自动填充 -->
- docs/00-overview.md
- docs/01-architecture.md
- docs/03-module-map.md
- ai/source-of-truth/repo-map.yaml
- ai/source-of-truth/module-index.yaml
- ai/source-of-truth/task-catalog.yaml

## Working rules
- 修改代码前必须先读取相关模块文档（docs/modules/<name>.md）
- 修改公共接口必须同步更新 docs/04-api-contracts.md
- 修改数据模型必须同步更新 docs/05-data-model.md
- 完成后运行验证命令（见下方）

## Verification commands
{{ verification_commands }}

## Preferred skills
- 理解项目结构：repo-explain skill
- 评估变更影响：change-impact skill
- 补充/更新文档：doc-refresh skill
```

### AGENTS.md 生成模板（兼容 OpenCode + Codex）

```markdown
# Repository Expectations

## Read first
- docs/00-overview.md
- docs/01-architecture.md
- ai/source-of-truth/repo-map.yaml
- ai/source-of-truth/module-index.yaml

## Before changing code
- 定位模块 owner 和上下游依赖（见 module-index.yaml）
- 涉及接口/数据库/配置变更时必须做 change impact review
- 涉及公共行为变化时必须更新对应 docs/

## Verify
{{ verification_commands }}

## Definition of done
- [ ] 代码通过所有验证命令
- [ ] 变更影响已评估并说明
- [ ] 相关文档已同步更新
- [ ] owner 已告知（如跨模块变更）
```

### ★ V2 OpenCode 专项适配：`.opencode/opencode.json`

OpenCode（sst/opencode）支持通过 `instructions` 字段直接引用文档文件数组，比在 AGENTS.md 中手写引用更干净：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    "docs/00-overview.md",
    "docs/01-architecture.md",
    "ai/source-of-truth/repo-map.yaml",
    "ai/source-of-truth/module-index.yaml",
    "ai/source-of-truth/task-catalog.yaml"
  ],
  "agents": {
    "primary": {
      "model": "claude-sonnet-4-5",
      "maxTokens": 8096
    },
    "task": {
      "model": "claude-haiku-4-5-20251001",
      "maxTokens": 4096
    }
  }
}
```

> OpenCode 官方文档确认：`instructions` 数组中的文件路径会被合并注入 context，优先级高于 AGENTS.md 中的手动引用。同时 OpenCode 支持 CLAUDE.md 作为 AGENTS.md 的 fallback（两者共存时 AGENTS.md 优先）。

### Skill 文件结构（以 change-impact 为例）

```markdown
<!-- .claude/skills/change-impact/SKILL.md（.agents/skills/同内容） -->
# change-impact

**触发时机**：当需要分析一个变更可能影响的范围时调用

**输入**
- 变更的文件列表（git diff --name-only）
- 变更目标描述

**执行步骤**
1. 读取 ai/source-of-truth/module-index.yaml，定位变更模块
2. 读取 .repo-wiki/graph/impact_cache.json，检查预计算影响链
3. 若缓存未命中，读取 .repo-wiki/graph/knowledge_graph.json 做图遍历
4. 找出所有 depended_by 模块（直接和间接依赖，BFS 深度 ≤ 3）
5. 检查变更是否涉及对外接口（exports）
6. 检查变更是否影响数据模型（关联 docs/05-data-model.md）
7. 生成影响分析报告

**输出**
- 受影响模块列表（含 owner）
- 受影响接口/数据结构
- 需要补充或新增的测试
- 需要同步更新的文档清单
- 风险评级（low / medium / high / critical）
```

---

## 十、技术实现选型（V2 更新）

### 核心依赖

| 组件 | 技术选型 | 理由 |
|------|----------|------|
| CLI 框架 | **Python 3.11 + Typer + Rich** | 快速开发，Rich 提供好看的终端输出 |
| 包管理 | **uv**（替代 pip/poetry） | Rust 实现，10x 速度，lockfile 完整 |
| LLM 调用 | **Anthropic Python SDK**（主）+ 兼容 OpenAI | 官方 SDK，async 原生支持 |
| AST 解析 | **tree-sitter** + 各语言 binding | 50+ 语言统一 API |
| 向量数据库 | **ChromaDB**（默认）/ Qdrant（大仓）| 零依赖本地运行 |
| 嵌入模型 | **sentence-transformers BAAI/bge-m3**（本地）/ voyage-code-3（云端）| 本地优先，无 Token 消耗 |
| 知识图谱 | **networkx**（构建）+ GraphML 导出 | Python 原生，无服务依赖 |
| 模板引擎 | **Jinja2** | 成熟稳定，支持复杂模板逻辑 |
| 配置管理 | **YAML + Pydantic v2** | 类型安全的配置验证 |
| 缓存层 | **SQLite + diskcache** | 轻量本地缓存，支持 LRU |
| 并发控制 | **asyncio + anyio + semaphore** | 控制 LLM 调用并发数 |
| 哈希/指纹 | **xxhash**（文件哈希）| 增量检测，比 md5 快 3x |
| npm 薄包装 | `repo-wiki` npm 包（调用 Python CLI） | 给 JS 生态用户友好安装 |

### `repo-wiki.config.yaml` 配置示例（V2 更新）

```yaml
project:
  name: payment-service
  language: auto
  framework: auto

llm:
  provider: anthropic
  model_init: claude-opus-4-5
  model_update: claude-sonnet-4-5
  model_verify: claude-haiku-4-5-20251001
  max_concurrent: 3
  cache: true
  cache_ttl_days: 7

# ★ V2 索引配置
index:
  enabled: true
  vector_backend: chromadb       # chromadb | qdrant | faiss
  embedding_model: local         # local（bge-m3）| voyage-code-3 | text-embedding-3-large
  chunk_strategy: function       # function | class | module
  max_chunk_tokens: 1500
  knowledge_graph: true

# Token 成本控制
token_budget:
  strategy: auto                 # auto | direct | chunked | rag_only
  max_context_tokens: 60000      # 每次 LLM 调用最大上下文
  force_rag_above_lines: 100000  # 超过此行数强制使用 RAG 模式

scan:
  exclude:
    - "node_modules/"
    - "dist/"
    - ".git/"
    - "*.test.ts"
    - "*.spec.ts"
    - "coverage/"
  include_patterns:
    - "src/**/*.ts"

output:
  docs_dir: docs/
  ai_dir: ai/source-of-truth/
  claude_dir: .claude/
  agents_skill_dir: .agents/skills/
  index_dir: .repo-wiki/

generation:
  documents:
    - overview
    - architecture
    - module-map
    - api-contracts
    - data-model
    - deploy-ops
    - troubleshooting
    - onboarding
    - glossary
    - modules          # 每模块单独文件
  skip: []
```

---

## 十一、自动化与持续同步（继承 V1，补充 V2 CI）

### Makefile 目标

```makefile
# 知识库相关
ai-init:       ## 首次初始化 Wiki（含向量索引）
	repo-wiki init

ai-index:      ## 重建本地向量索引和知识图谱
	repo-wiki index

ai-update:     ## 基于 git diff 增量更新
	repo-wiki update

ai-verify:     ## 校验文档覆盖率
	repo-wiki verify

ai-sync:       ## 同步适配层文件
	repo-wiki sync

ai-cost:       ## 估算 Token 消耗
	repo-wiki cost-estimate

# 验证命令（由 LLM 适配层引用）
verify-docs:   ## 校验代码与文档的一致性
	repo-wiki verify --strict

lint test build: ...
```

### Git Hooks（post-commit）

```bash
#!/bin/bash
# .git/hooks/post-commit
CHANGED=$(git diff HEAD~1 --name-only)

if echo "$CHANGED" | grep -qE "(routes|controller|schema|migration)"; then
  echo "⚠️  检测到接口/模型变更，建议运行: make ai-update"
fi
```

### CI 校验（GitHub Actions，V2 补充索引刷新）

```yaml
# .github/workflows/verify-docs.yml
name: Verify Docs Consistency
on: [pull_request]
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install repo-wiki
        run: pip install repo-wiki
      - name: Check doc coverage
        run: repo-wiki verify --ci
        # 规则：
        # - 修改接口文件但未更新 docs/04-api-contracts.md → 失败
        # - 新增模块但未在 module-index.yaml 登记 → 失败
        # - docs/ 文件超过 30 天未更新且对应模块有变更 → 警告

---
# .github/workflows/ai-index-refresh.yml（★ V2）
name: Refresh AI Index（Weekly）
on:
  schedule:
    - cron: '0 2 * * 1'   # 每周一凌晨 2 点
jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Rebuild knowledge graph（无 Token 消耗）
        run: repo-wiki index --no-embed
      - name: Commit updated graph
        run: |
          git add ai/source-of-truth/
          git commit -m "chore: refresh AI knowledge index [skip ci]"
          git push
```

---

## 十二、安全与权限设计（继承 V1）

### 知识分级

文档生成时自动打标，控制 AI 读取范围：

| 等级 | 内容 | AI 默认可见 |
|------|------|-------------|
| `public-docs` | 概览、架构、模块说明、接口规范 | 是 |
| `internal-dev` | 排障手册、任务目录、开发者入门 | 是 |
| `restricted-ops` | 生产环境拓扑、密钥管理、数据修复 | 否（需显式 include） |

### 不进入知识库的内容

- 任何 `.env` 文件中的真实密钥
- 生产数据库连接字符串
- 内部服务真实 IP 或域名
- 用户个人数据样本
- **★ V2：向量索引中不存储超过 5000 行的日志文件、生成代码（如 protobuf 生成物）**

---

## 十三、扩展性设计（继承 V1，补充向量后端插件）

### 支持更多语言/框架（通过 Scanner 插件）

```python
class SpringBootScanner(BaseScanner):
    def extract_routes(self) -> List[Route]: ...
    def extract_models(self) -> List[Model]: ...
    def extract_dependencies(self) -> DependencyGraph: ...
```

### 支持更多向量后端（★ V2）

```python
class QdrantVectorStore(BaseVectorStore):
    def upsert(self, chunks: List[CodeChunk]) -> None: ...
    def search(self, query: str, filter: dict, top_k: int) -> List[SearchResult]: ...
    def delete_by_file(self, file_path: str) -> None: ...

class FAISSVectorStore(BaseVectorStore):
    """离线高性能，适合 CI 环境"""
    ...
```

### 支持更多 AI Agent（通过 Adapter 插件）

```python
class GeminiCodeAdapter(BaseAgentAdapter):
    def generate_entry_file(self, knowledge_base) -> str: ...
    def generate_skills(self, knowledge_base) -> List[Skill]: ...
```

---

## 十四、落地节奏（五周计划，V2 调整）

### 第 1 周：核心骨架

- [ ] CLI 基础框架（typer + rich，命令注册）
- [ ] 文件系统扫描器（pathspec 过滤，语言识别）
- [ ] LLM 调用层（Anthropic SDK async 封装、流式、重试）
- [ ] `cost-estimate` 命令（扫描后估算 Token 消耗）
- [ ] 生成第一个文档：`docs/00-overview.md`

### 第 2 周：文档生成能力

- [ ] tree-sitter AST 解析器（TS/Python/Go 优先）
- [ ] 模块提取器（module-index 生成）
- [ ] 接口提取器（API contracts 生成）
- [ ] 全套 9 类文档的 Jinja2 prompt 模板
- [ ] SQLite 缓存层（diskcache）
- [ ] `docs/modules/<name>.md` 每模块文档生成

### 第 3 周（★ V2 新增）：索引与图谱

- [ ] 代码分块器（chunker，函数/类级）
- [ ] 本地 embedding（sentence-transformers bge-m3）
- [ ] ChromaDB 向量存储封装
- [ ] `repo-wiki index` 命令
- [ ] networkx 知识图谱构建
- [ ] impact_cache.json 预计算
- [ ] `repo-wiki search` 和 `repo-wiki graph` 命令

### 第 4 周：适配层与自动化

- [ ] CLAUDE.md / AGENTS.md / opencode.json 自动生成（sync 命令）
- [ ] 3 个核心 Skill 文件模板
- [ ] `update` 增量模式（git diff + 向量索引增量更新）
- [ ] Makefile 生成
- [ ] post-commit hook 生成

### 第 5 周：校验与治理

- [ ] `verify` 命令（文档覆盖率、一致性检查）
- [ ] CI 集成（GitHub Actions workflow 生成）
- [ ] `.codex/config.toml` + `hooks.json` 生成
- [ ] `.claude/settings.json` 权限配置生成
- [ ] npm 薄包装（`npm install -g repo-wiki`）
- [ ] 文档：README + 使用示例 + Token 成本指南

---

## 附：目标体验示例（V2）

```bash
# 在一个 10 万行 TypeScript 仓库中运行
$ cd ~/projects/payment-service
$ repo-wiki cost-estimate

📊 Cost Estimate for payment-service:
   Lines of code:  124,583
   Modules:        12
   API endpoints:  89
   Strategy:       RAG mode (> 100K lines threshold)

   Embedding (local bge-m3): FREE (no API calls)
   Graph building (static):  FREE
   LLM doc generation:       ~31,000 tokens (~$0.93 @ Sonnet 4.5)
   ─────────────────────────────────────────────────────
   Total estimate:  $0.93 USD
   Time estimate:   ~60 seconds

Proceed? [y/N]: y

$ repo-wiki init

🔍 Phase 1: Scanning repository...
   ✓ Detected: TypeScript / NestJS / pnpm
   ✓ Found 12 modules, 89 API endpoints, 23 DB models
   ✓ Wrote ai/source-of-truth/repo-map.yaml
   ✓ Wrote ai/source-of-truth/module-index.yaml

🔢 Phase 2: Building local index (zero tokens)...
   ✓ Chunked 432 files → 2,847 code chunks
   ✓ Embedded chunks locally (bge-m3, ~45s)
   ✓ Stored in .repo-wiki/index/chroma/
   ✓ Built knowledge graph: 12 modules, 89 interfaces, 156 functions
   ✓ Wrote .repo-wiki/graph/knowledge_graph.json
   ✓ Pre-computed impact chains for all 12 modules

📝 Phase 3: Generating documentation (RAG mode, 3 workers)...
   ✓ docs/00-overview.md
   ✓ docs/01-architecture.md
   ✓ docs/03-module-map.md  (12 modules)
   ✓ docs/04-api-contracts.md  (89 endpoints)
   ✓ docs/05-data-model.md  (23 models)
   ✓ docs/modules/PaymentModule.md
   ✓ docs/modules/OrderModule.md
   ... (10 more module docs)
   ✓ docs/07-troubleshooting.md
   ✓ ai/source-of-truth/task-catalog.yaml

🔗 Phase 4: Syncing AI adapter layers...
   ✓ .claude/CLAUDE.md
   ✓ .claude/skills/  (3 skills)
   ✓ AGENTS.md
   ✓ .opencode/opencode.json  (★ V2: instructions 字段)
   ✓ .agents/skills/  (3 skills)
   ✓ .codex/config.toml
   ✓ Makefile  (ai-* targets added)
   ✓ .github/workflows/verify-docs.yml

✅ Done in 68s. Actual token usage: 29,847 tokens ($0.89)
   51 files created, 0 existing files overwritten.

# 现在在该项目中启动 claude 或 opencode，直接享有完整上下文 ✨
# 语义搜索示例：
$ repo-wiki search "用户权限校验在哪里"
Top 3 results:
  1. src/modules/auth/guards/jwt.guard.ts:45 (similarity: 0.94)
  2. src/modules/user/decorators/roles.decorator.ts:12 (similarity: 0.87)
  3. src/shared/middleware/auth.middleware.ts:23 (similarity: 0.82)
```

---

*文档版本：v2.0 | 生成工具：repo-wiki | 知识底座：可被 Claude Code / OpenCode / Codex 直接复用*
*参考来源：Claude Code 源码分析（TypeScript/Bun，512K+ 行）| OpenCode 架构（Go TUI + TypeScript Server）| Karpathy RAG 最佳实践 | Claude Code 三级压缩策略（MicroCompact / AutoCompact / Full Compact）*
