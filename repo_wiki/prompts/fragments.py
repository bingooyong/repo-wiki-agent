"""Reusable prompt fragments for page composition.

Each fragment is a template string with placeholders for page-specific data.
Fragments include evidence requirements, citation patterns, style guidelines,
and anti-hallucination guardrails.

Phase 24 - Task 24.1: Page prompt contract and prompt fragments
"""

from __future__ import annotations

from typing import Any

# =============================================================================
# System Prompt Fragment
# =============================================================================

SYSTEM_PROMPT_FRAGMENT = """你是一个技术文档生成助手，专注于生成高质量、结构化、以证据为驱动的技术文档。

## 输出要求

1. **Markdown格式**: 使用标准Markdown语法，包括标题、列表、代码块、表格
2. **中文优先**: 中文技术术语保持中文，英文术语保留英文
3. **证据引用**: 所有事实性声明必须包含<cite>引用标记</cite>
4. **禁止幻觉**: 不要生成未经源代码验证的信息

## 证据引用格式

- 单行引用: <cite>file.py:123</cite>
- 多行引用: <cite>file.py:123-125</cite>
- 符号引用: <cite>file.py:123 (ClassName.method)</cite>

## 反幻觉规则

1. 只描述实际存在于源代码中的模块、类、函数、API端点
2. 所有版本号必须来自实际配置或代码
3. 所有文件路径必须可验证
4. 不要推测未在源代码中确认的行为
"""

# =============================================================================
# Overview Page Prompt Fragment
# =============================================================================

OVERVIEW_PROMPT_FRAGMENT = """## Overview Page Prompt Fragment

Generate a project overview page for `{repository_name}`.

### Source Context

Repository: {repository_name}
Primary Language: {primary_language}
Framework: {framework}
Module Count: {module_count}
Endpoint Count: {endpoint_count}
Model Count: {model_count}

### Evidence Requirements

- Minimum 8 evidence candidates required
- Use <cite> block citation style
- All symbols must have citations
- Repository-specific content only (no generic boilerplate)

### Required Heading Structure

# {repository_name} - 项目概览

## 项目定位

{project_positioning}

## 核心问题

{core_problem}

## 核心能力

{core_capabilities}

## 快速开始

### 环境要求

{environment_requirements}

### 启动命令

{startup_commands}

## 阅读导航

{reading_navigation}

## 技术概览

| 属性 | 值 |
|------|-----|
| 仓库根目录 | `{repository_root}` |
| 主要语言 | `{primary_language}` |
| 框架 | `{framework}` |
| 模块数量 | {module_count} |
| API 端点 | {endpoint_count} |
| 数据模型 | {model_count} |

## 领域分组

{domain_groups_markdown}

---

### Anti-Hallucination Rules

1. DO NOT use generic phrases like "这是一个基于" or "传统文档维护面临的主要挑战包括"
2. DO NOT mention modules not present in the module inventory
3. DO NOT claim capabilities not verified by source code
4. All factual claims MUST have <cite> citation
5. Repository name and specifics must appear in content

### Style Guidelines

- Prose density: At least 50% prose vs list/table content
- Average sentence length: 12+ words
- Avoid bullet-only pages
- Include explanatory prose between sections
"""

# =============================================================================
# Service Page Prompt Fragment
# =============================================================================

SERVICE_PROMPT_FRAGMENT = """## Service Page Prompt Fragment

Generate a service/section page for section `{section_slug}`.

### Source Context

Section: {section_title}
Description: {section_description}
Modules: {section_modules}
APIs: {section_apis}
Commands: {section_commands}

### Evidence Requirements

- Minimum 5 evidence candidates required
- Use <cite> block citation style
- All module references must have citations
- Service-specific content only

### Required Heading Structure

# {section_title}

## 服务概述

{section_description}

## 核心模块

{section_modules}

### Module Details

{module_details}

## API 端点

{section_apis}

## 数据模型

{section_data_models}

## 相关命令

{section_commands}

## 导航

- [返回概览](../../00-overview.md)
- [相关专题](../{related_section}/index.md)

---

### Anti-Hallucination Rules

1. DO NOT use generic phrases like "本服务采用" or "系统使用"
2. DO NOT describe modules outside the section scope
3. All factual claims MUST have <cite> citation
4. Commands must be verifiable in the repository

### Style Guidelines

- Prose density: At least 40% prose
- Clear section transitions with explanatory text
- Code examples where relevant
"""

# =============================================================================
# API Page Prompt Fragment
# =============================================================================

API_PROMPT_FRAGMENT = """## API Page Prompt Fragment

Generate an API reference page with grouped endpoints and call conventions.

### Source Context

Repository: {repository_name}
API Groups: {api_groups}
Authentication: {authentication_patterns}
Error Handling: {error_status_behavior}

### Evidence Requirements

- Minimum 10 evidence candidates required
- Use markdown link citation style ([file:line](file://...))
- File:line references required for all endpoints
- Endpoints must be verifiable

### Required Heading Structure

# API 参考

## API 分组

{api_groups_table}

## 调用约定

### 认证

{authentication_patterns}

### 错误处理

{error_status_behavior}

## 关键入口 API

{key_entry_apis}

## 端点详情

{endpoint_details}

---

### Anti-Hallucination Rules

1. DO NOT include endpoints not found in source code
2. DO NOT claim authentication methods not implemented
3. All endpoint references MUST have file:line citations
4. HTTP methods and paths must match actual implementation

### Style Guidelines

- Prose density: At least 30% prose
- Table formatting for endpoint lists
- Explanatory text for complex behaviors
"""

# =============================================================================
# Data Model Page Prompt Fragment
# =============================================================================

DATA_PROMPT_FRAGMENT = """## Data Model Page Prompt Fragment

Generate a data model page with core models, service models, and migrations.

### Source Context

Repository: {repository_name}
Core Models: {core_models}
Service Models: {service_models}
Database: {database_shape}
Migration Strategy: {migration_strategy}

### Evidence Requirements

- Minimum 8 evidence candidates required
- Use <cite> block citation style
- All model definitions must have citations
- Database schema references required

### Required Heading Structure

# 数据模型

## 核心数据模型

{core_models_section}

## 服务数据模型

{service_models_section}

## 数据库与迁移策略

{database_migration_section}

## 模型索引

{model_index_table}

---

### Anti-Hallucination Rules

1. DO NOT include models not defined in source code
2. DO NOT describe database schemas without evidence
3. All model definitions MUST have <cite> citations
4. Field types must match actual implementation

### Style Guidelines

- Prose density: At least 35% prose
- Table formatting for model definitions
- Explanatory prose for relationships and migrations
"""

# =============================================================================
# Entity Page Prompt Fragment
# =============================================================================

ENTITY_PROMPT_FRAGMENT = """## Entity Page Prompt Fragment

Generate an entity page for individual data model `{entity_name}`.

### Source Context

Entity: {entity_name}
Fields: {fields}
Relationships: {relationships}
Source File: {source_file}

### Evidence Requirements

- Minimum 3 evidence candidates required
- Use source footer citation style
- Field definitions must have citations
- Relationship mappings must be verifiable

### Required Heading Structure

# {entity_name}

## 实体描述

{entity_description}

## 字段定义

{fields_table}

## 关系映射

{relationship_diagram}

## 迁移历史

{migration_history}

---

### Anti-Hallucination Rules

1. DO NOT include fields not in the entity definition
2. DO NOT claim relationships not defined in source
3. All field definitions MUST have citations
4. Migration history must be verifiable

### Style Guidelines

- Prose density: At least 40% prose
- Clear field documentation
- Entity relationship explanation
"""

# =============================================================================
# Ops Page Prompt Fragment
# =============================================================================

OPS_PROMPT_FRAGMENT = """## Ops Page Prompt Fragment

Generate an operations page covering deployment and运维.

### Source Context

Environment: {environment}
Deployment: {deployment_config}
Monitoring: {monitoring_config}

### Evidence Requirements

- Minimum 5 evidence candidates required
- Use markdown link citation style
- Configuration references required
- Must be environment-specific

### Required Heading Structure

# 部署运维

## 环境配置

{environment_config}

## 部署流程

{deployment_flow}

## 监控告警

{monitoring_alerts}

## 故障恢复

{disaster_recovery}

---

### Anti-Hallucination Rules

1. DO NOT use generic phrases like "生产环境" or "建议使用"
2. DO NOT describe configuration not in source
3. All config references MUST have file citations
4. Version info must be locked to actual versions

### Style Guidelines

- Prose density: At least 35% prose
- Step-by-step procedures with explanation
- Command examples with context
"""

# =============================================================================
# Development Page Prompt Fragment
# =============================================================================

DEVELOPMENT_PROMPT_FRAGMENT = """## Development Page Prompt Fragment

Generate a development guide page with setup and contribution info.

### Source Context

Repository: {repository_name}
Setup: {setup_instructions}
Testing: {testing_strategy}
Contributing: {contribution_guide}

### Evidence Requirements

- Minimum 4 evidence candidates required
- Use markdown link citation style
- Command references required
- Must match actual project setup

### Required Heading Structure

# 开发指南

## 环境搭建

{setup_instructions}

## 开发规范

{development_standards}

## 测试策略

{testing_strategy}

## 贡献流程

{contribution_guide}

---

### Anti-Hallucination Rules

1. DO NOT describe setup steps not in actual documentation
2. DO NOT claim testing frameworks not present
3. All commands MUST be verifiable
4. Version requirements must match actual

### Style Guidelines

- Prose density: At least 30% prose
- Clear numbered steps
- Code examples with context
"""


# =============================================================================
# Fragment Registry
# =============================================================================

_FRAGMENT_REGISTRY: dict[str, str] = {
    "system": SYSTEM_PROMPT_FRAGMENT,
    "overview": OVERVIEW_PROMPT_FRAGMENT,
    "service": SERVICE_PROMPT_FRAGMENT,
    "api": API_PROMPT_FRAGMENT,
    "data": DATA_PROMPT_FRAGMENT,
    "entity": ENTITY_PROMPT_FRAGMENT,
    "ops": OPS_PROMPT_FRAGMENT,
    "development": DEVELOPMENT_PROMPT_FRAGMENT,
}


def get_prompt_fragment(fragment_name: str) -> str:
    """Get a prompt fragment by name.

    Args:
        fragment_name: Name of the fragment (system, overview, service, api, data, entity, ops, development)

    Returns:
        The prompt fragment template string

    Raises:
        ValueError: If fragment_name is not recognized
    """
    if fragment_name not in _FRAGMENT_REGISTRY:
        raise ValueError(
            f"Unknown fragment name: {fragment_name}. "
            f"Available: {list(_FRAGMENT_REGISTRY.keys())}"
        )
    return _FRAGMENT_REGISTRY[fragment_name]


def render_prompt_fragment(fragment_name: str, context: dict[str, Any]) -> str:
    """Render a prompt fragment with the given context.

    Args:
        fragment_name: Name of the fragment
        context: Context dictionary for template substitution

    Returns:
        Rendered prompt fragment string

    Raises:
        ValueError: If fragment_name is not recognized
    """
    fragment = get_prompt_fragment(fragment_name)

    # Simple template substitution using format
    try:
        return fragment.format(**context)
    except KeyError as e:
        raise ValueError(f"Missing context key: {e}")


# Aliases for compatibility
OVERVIEW_PROMPT_FRAGMENT = OVERVIEW_PROMPT_FRAGMENT
SERVICE_PROMPT_FRAGMENT = SERVICE_PROMPT_FRAGMENT
API_PROMPT_FRAGMENT = API_PROMPT_FRAGMENT
DATA_PROMPT_FRAGMENT = DATA_PROMPT_FRAGMENT
ENTITY_PROMPT_FRAGMENT = ENTITY_PROMPT_FRAGMENT
OPS_PROMPT_FRAGMENT = OPS_PROMPT_FRAGMENT
DEVELOPMENT_PROMPT_FRAGMENT = DEVELOPMENT_PROMPT_FRAGMENT
