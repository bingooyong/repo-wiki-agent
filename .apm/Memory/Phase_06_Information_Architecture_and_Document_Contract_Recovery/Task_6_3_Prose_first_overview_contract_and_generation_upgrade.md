---
agent: Agent_DocGen
task_ref: Task 6.3
status: Completed
ad_hoc_delegation: false
compatibility_issues: false
important_findings: false
---

# Task Log: Task 6.3 - Prose-first overview contract and generation upgrade

## Summary

成功重写 `docs/00-overview.md` 契约和生成逻辑，添加固定章节约束（项目定位、核心问题、核心能力、快速开始、阅读导航），并将文档从扁平列表升级为人类可读的段落优先内容。

## Details

### 1. 重写 00-overview.md.j2 模板

新模板包含以下固定章节：
- 项目定位 (项目描述和定位)
- 核心问题 (项目解决的主要挑战)
- 核心能力 (自动化能力列表)
- 快速开始 (环境要求和启动命令)
- 阅读导航 (到 section 和模块的链接)
- 技术概览 (表格形式的技术统计)

### 2. 扩展 Overview Contract Required Keys

更新 `CORE_DOCUMENT_CONTRACTS` 中 overview 契约的 `required_keys`，新增字段：
- `project_description` - 项目描述段落
- `project_positioning` - 项目定位段落
- `core_problem` - 核心问题段落
- `core_capabilities` - 核心能力列表
- `environment_requirements` - 环境要求
- `startup_commands` - 启动命令列表
- `reading_navigation` - 阅读导航链接

### 3. 扩展 _build_core_context 方法

在 `engine.py` 中更新 `_build_core_context` 方法，生成新字段的上下文：
- 自动生成项目描述（基于语言和框架）
- 自动生成项目定位和核心问题描述
- 自动从模块/端点/模型数量生成核心能力列表
- 根据语言生成环境要求
- 从 commands 字典生成启动命令
- 生成到 sections 和其他文档的阅读导航链接

### 4. 添加验证约束

在 `contracts.py` 中添加验证函数：
- `validate_overview_prose()` - 验证最小段落数（至少 5 个章节标题）
- `validate_overview_not_list_only()` - 验证不是纯列表/表格内容（列表/表格比例 < 70%）

验证规则：
- 最小 prose 字符数: 200
- 最小章节数: 5
- 拒绝纯列表内容: True

## Output

### Modified Files

- `/templates/docs/00-overview.md.j2` - 重写为段落优先模板
- `/repo_wiki/generator/contracts.py` - 扩展 overview contract 的 required_keys 和添加验证函数
- `/repo_wiki/generator/engine.py` - 更新 `_build_core_context` 生成新字段

### Key Template Sections

```markdown
# ${repository_name} - 项目概览

## 项目定位
${project_positioning}

## 核心问题
${core_problem}

## 核心能力
${core_capabilities}

## 快速开始
### 环境要求
${environment_requirements}

### 启动命令
${startup_commands}

## 阅读导航
${reading_navigation}

## 技术概览
| 属性 | 值 |
|------|-----|
| ... |
```

### Validation Functions

```python
OVERVIEW_MIN_PROSE_CHARS = 200
OVERVIEW_MIN_SECTIONS = 5
OVERVIEW_REJECT_LIST_ONLY = True

def validate_overview_prose(content: str) -> tuple[bool, str]:
    ...

def validate_overview_not_list_only(content: str) -> tuple[bool, str]:
    ...
```

## Issues

None

## Next Steps

Task 6.4 依赖 Task 6.1, 6.2, 6.3。Task 6.4 将重写 `docs/01-architecture.md`，添加 Mermaid 架构图和三层结构说明。
