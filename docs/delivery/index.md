# repo-wiki MVP — 交付文档包

**版本：** v1.0.0
**日期：** 2026-05-03
**项目：** repo-wiki Local-first Wiki Generation Tool

---

## 文档包结构

```
docs/delivery/
├── index.md                      # 本文档
├── spec/                         # 规格层
│   ├── spec.md                   # 项目规格文档
│   ├── requirements.md          # 功能需求
│   ├── design.md                # 概要设计
│   └── tasks.md                 # 任务拆解
└── *.md                          # 14 份交付文档
```

---

## 规格层文档

| 文档 | 说明 |
|------|------|
| [spec.md](./spec/spec.md) | 项目规格文档（背景、目标、功能范围、假设前提、待确认项） |
| [requirements.md](./spec/requirements.md) | 功能需求文档（REQ-XXX 编号，含优先级和验收条件） |
| [design.md](./spec/design.md) | 概要设计文档（架构、模块、接口定义、数据模型） |
| [tasks.md](./spec/tasks.md) | 任务拆解文档（TASK-XXX 编号，关联 REQ-XXX） |

---

## 交付文档（14 份）

### 必选文档

| 编号 | 文档 | 说明 |
|------|------|------|
| DOC-001 | [project-overview.md](./project-overview.md) | 项目概览 |
| DOC-002 | [deployment-guide.md](./deployment-guide.md) | 部署指南 |
| DOC-003 | [user-manual.md](./user-manual.md) | 用户手册 |
| DOC-004 | [functional-spec.md](./functional-spec.md) | 功能规格 |
| DOC-005 | [high-level-design.md](./high-level-design.md) | 高级设计 |
| DOC-006 | [api-spec.md](./api-spec.md) | API 规范 |
| DOC-007 | [database-design.md](./database-design.md) | 数据库设计 |
| DOC-008 | [configuration-guide.md](./configuration-guide.md) | 配置指南 |
| DOC-009 | [operations-runbook.md](./operations-runbook.md) | 运维手册 |
| DOC-010 | [incident-response-runbook.md](./incident-response-runbook.md) | 应急响应 |
| DOC-011 | [logging-guide.md](./logging-guide.md) | 日志指南 |
| DOC-012 | [security-auth-guide.md](./security-auth-guide.md) | 安全认证指南 |
| DOC-013 | [third-party-integration.md](./third-party-integration.md) | 第三方集成 |
| DOC-014 | [acceptance-checklist.md](./acceptance-checklist.md) | 验收清单 |

---

## 快速导航

### 面向用户

- [用户手册](./user-manual.md) — CLI 命令用法
- [部署指南](./deployment-guide.md) — 安装和配置
- [配置指南](./configuration-guide.md) — YAML 配置详解

### 面向开发

- [功能规格](./functional-spec.md) — 详细功能说明
- [API 规范](./api-spec.md) — CLI 和 Python API
- [高级设计](./high-level-design.md) — 系统架构

### 面向运维

- [运维手册](./operations-runbook.md) — 日常操作
- [应急响应](./incident-response-runbook.md) — 故障处理
- [日志指南](./logging-guide.md) — 日志分析

---

## 项目状态

| 指标 | 状态 |
|------|------|
| Strict Verify | ✅ PASS (13/13 checks) |
| GO 决策 | ✅ GO (2026-05-02) |
| 测试覆盖 | 1200+ tests |
| 文档完整性 | 14/14 docs |

---

## 参考信息

- **GO 决策文档**：`docs/go-no-go-dossier.md`
- **APM Memory Root**：`.apm/Memory/Memory_Root.md`
- **Implementation Plan**：`.apm/Implementation_Plan.md`
- **GitHub**：https://github.com/bingooyong/repo-agent