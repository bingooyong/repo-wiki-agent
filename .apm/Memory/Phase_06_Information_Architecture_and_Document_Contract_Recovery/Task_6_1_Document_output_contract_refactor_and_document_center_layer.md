---
agent: Agent_DocGen
task_ref: Task 6.1
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 6.1 - Document output contract refactor and document-center layer

## Summary

成功重构文档输出契约，引入 `docs/sections/` 专题层和 `docs/phases/` 阶段治理层，建立四层文档中心架构。现有 MVP 输出（`docs/00~05` 和 `docs/modules/**`）保持不变。

## Details

### 1. 扩展 DocumentContract 模型

- 新增 `DocumentLayer` 枚举，区分 `OVERVIEW`、`SECTION`、`MODULE`、`PHASE` 四层
- `DocumentContract` 新增 `layer` 字段标识所属层
- 核心契约（00-05）标记为 `OVERVIEW` 层
- 新增 `SECTION_DEFINITIONS` 和 `PHASE_DEFINITIONS` 定义稳定命名

### 2. 新增 Section 层 (`docs/sections/`)

10 个专题节(section)定义:
- `project`: 项目概览与快速开始
- `architecture`: 架构与系统设计
- `services`: 核心服务与业务逻辑
- `python-services`: Python 服务层
- `data-model`: 数据模型与持久化
- `api`: API 参考与契约
- `operations`: 部署与运维
- `development`: 开发指南
- `security`: 安全与合规
- `troubleshooting`: 故障排查

路径规则: `docs/sections/<section-slug>/index.md`

### 3. 新增 Phase 层 (`docs/phases/`)

6 个阶段文档:
- `phase-01-setup` through `phase-06-architecture`

路径规则: `docs/phases/<phase-slug>.md`

### 4. 命名规则与写域边界

- Section slug: 小写、连字符分隔 (如 `python-services`)
- Phase slug: 小写、连字符分隔 (如 `phase-06-architecture`)
- 模块 slug: 基于模块名，`/` 替换为 `-`
- 写域: 新契约仅写入 `docs/sections/` 和 `docs/phases/`，不修改现有 `docs/00~05`

### 5. 更新模板和契约注册表

- 新增 `templates/docs/section.md.j2` 专题页模板
- 新增 `templates/docs/phase.md.j2` 阶段页模板
- `validate_contract_coverage()` 扩展支持新层验证
- 新增 `all_section_contracts()`、`all_phase_contracts()`、`get_contracts_by_layer()` 辅助函数

### 6. 更新生成引擎

- `_generate_section_docs()`: 生成专题层文档
- `_generate_phase_docs()`: 生成阶段层文档
- `_build_section_context()`: 根据专题类型聚合模块、API、导航
- `_build_phase_context()`: 构建阶段目标、交付物、依赖、状态

### 7. 加性验证

- 核心文档契约 (`CORE_DOCUMENT_CONTRACTS`) 保持不变
- Section 和 Phase 层为可选增强层
- 现有 `verify --ci` 命令不受影响
- 命令表面保持不变

## Output

### Modified Files

- `/repo_wiki/generator/contracts.py` - 扩展契约模型，新增层分类和辅助函数
- `/repo_wiki/generator/engine.py` - 新增 section/phase 层生成逻辑

### New Files

- `/templates/docs/section.md.j2` - 专题页模板
- `/templates/docs/phase.md.j2` - 阶段页模板

### Key Code Changes

**contracts.py 新增:**
```python
class DocumentLayer(Enum):
    OVERVIEW = "overview"
    SECTION = "section"
    MODULE = "module"
    PHASE = "phase"

SECTION_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("project", "Project Overview and Getting Started"),
    ("architecture", "Architecture and System Design"),
    ...
)

PHASE_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("phase-01-setup", "Phase 01: Initial Setup..."),
    ...
)

def section_contract(section_slug: str) -> DocumentContract:
    ...

def phase_contract(phase_slug: str) -> DocumentContract:
    ...

def get_contracts_by_layer(layer: DocumentLayer) -> tuple[DocumentContract, ...]:
    ...
```

**engine.py 新增:**
```python
def _generate_section_docs(self, core_context, snapshot) -> tuple[list[str], int, int]
def _generate_phase_docs(self, core_context) -> tuple[list[str], int, int]
def _build_section_context(self, section_slug, section_title, modules, endpoints, commands, core_context) -> dict
def _build_phase_context(self, phase_slug, phase_title, all_phases, current_index) -> dict
```

## Issues

None

## Next Steps

Task 6.2 依赖 Task 6.1 的输出。Task 6.2 将基于此扩展的契约系统添加业务域分类器元数据。
