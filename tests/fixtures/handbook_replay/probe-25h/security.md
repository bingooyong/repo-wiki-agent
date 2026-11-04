# 安全合规概览

## 简介

probe_exporter 是面向企业级的服务探针拨测与结果导出平台，支持 **双模式探测**（Blackbox + Custom Probe）、灵活的验证引擎、多渠道导出，并提供完整的 Web 管理界面 ✨ 核心特性 🎯 双模式探测。本页聚焦其在源码与运维文档中可见的安全合规要点，覆盖依赖安全升级、传输层安全策略以及社区贡献治理三类内容，划定当前仓库可被直接验证的合规边界。

## 服务概述

安全合规在 probe_exporter 中并未集中在一个独立的模块内，而是散落在依赖升级策略、Web 反向代理配置与社区治理三类资产中。这种分布意味着合规落点需要结合 Go 模块、NPM 锁定文件与反向代理头统一审视。

## 核心模块

- **依赖安全升级基线**：Phase 6 文档定义了对 Go 模块与 Web 应用锁文件的安全相关 bump 规则，是处理 Dependabot 与 `govulncheck` 报告的统一入口 。
- **传输层安全策略**：运维手册中通过 Nginx `add_header` 指令下发 HSTS，对所有响应强制启用 HTTPS 严格传输安全 <cite>docs/OPERATIONS_MANUAL.md:1525-1527</cite>。
- **贡献治理入口**：仓库根目录的贡献指南是社区合规、行为准则与提交流程的统一来源 。

## 依赖安全升级

Phase 6 文档明确将 Dependabot 与 `govulncheck` 的告警作为输入，要求在 Go 模块层面修复漏洞，并在评估可行性的前提下刷新 npm Web 应用锁文件。文档强调“优先进行安全相关的 bump”，并禁止为了升级而引入明显破坏应用的主版本变更 。这意味着升级动作必须兼顾安全性与稳定性，并对破坏性变更做出人工判断。
<cite>docs/CC_PROBE_PHASE6_DEPS.md:1-6</cite>

## 传输层安全（HSTS）

在运维手册第 1525-1527 行，部署侧通过反向代理配置为所有响应附加 `Strict-Transport-Security: max-age=31536000; includeSubDomains` <cite>docs/OPERATIONS_MANUAL.md:1525-1527</cite>。一年有效期的 `max-age` 与 `includeSubDomains` 覆盖子域名，体现了对浏览器端 HTTPS 升级的强制约束，是当前仓库可见的最直接的传输层合规策略。

## 贡献与社区治理

仓库根 `CONTRIBUTING.md` 顶部即声明了贡献流程，并将“行为准则”列在目录的第一项，作为社区治理的入口 <cite>CONTRIBUTING.md:7-21</cite>。从合规视角看，行为准则是开源项目对外承担责任的最低公开承诺，应当与许可证、安全披露与漏洞报告流程共同阅读。该文件同时规定了贡献、开发环境、代码规范、提交规范与 Pull Request 流程 <cite>CONTRIBUTING.md:7-19</cite>，为审计代码来源、追溯变更提供了制度化的入口。

---

需要注意的是，仓库当前可被直接引用的安全证据集中在依赖升级文档、HSTS 反向代理头与贡献治理三类文件上；尚未在本批证据中观察到 RBAC、审计日志、密钥管理或数据脱敏等更细粒度合规模块的源码说明，后续若有新的证据可再行补充。

安全实现见  <cite>internal/auth/api_gateway_aksk_auth.go:25-25</cite> <cite>internal/secrets/aes_store.go:20-20</cite> <cite>internal/audit/audit.go:13-13</cite> <cite>internal/netguard/netguard.go:30-30</cite> <cite>internal/security/redaction.go:32-32</cite>。

## 目录

1. 简介
2. 服务概述
3. 核心模块
4. 依赖安全升级
5. 传输层安全（HSTS）
6. 贡献与社区治理
