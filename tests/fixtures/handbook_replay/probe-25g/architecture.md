# 架构设计

## 简介

`probe_exporter` 是面向企业级的服务探针拨测与结果导出平台。它支持**双模式探测**（Blackbox + Custom Probe）、灵活的验证引擎、多渠道导出，并提供完整的 Web 管理界面。控制面入口 `ccprobe-control` 提供 `-serve -transport grpc` 的 gRPC 服务模式，内部通过 `TunnelHub` 聚合 agent 隧道会话并以 `control.SoftLimits` 做资源约束<sup><cite>cmd/ccprobe-control/serve.go:29-187</cite></sup>。客户端 `ccagent` 在 Alpine 容器中通过 `GODEBUG=netdns=go` 规避 musl 与 Go 网络轮询器的兼容性问题<sup><cite>cmd/ccagent/main.go:16-22</cite></sup>。

## 项目结构

仓库按职责划分为入口层、领域包与基础组件三层。入口层位于 `cmd/`，包含 `ccagent`（REST/Web 客户端）、`ccprobe-control`（控制面 gRPC 服务与探针 CLI 模式）以及 `custom-probe`（独立自定义探针二进制）。领域包位于 `internal/`，包括 `control`（隧道会话中心）、`services`（业务服务）、`repository`（仓储层）、`exporter`（多渠道导出）、`probe`、`validator`、`netguard`、`metrics`、`models` 等。辅助子包覆盖配置 `config.go`、TLS 协商 `tls.go`、密钥 `secrets`、审计 `audit`、鉴权 `auth`、契约 `contract`、数据库连接 `dbconn`、运维指标 `opsmetrics` 与运维存储 `opsstore` 等横切关注点。
<cite>cmd/ccprobe-control/main.go:23-80</cite>

部署侧提供 `deploy/` 子树，承载 `agent` 相关的容器化与编排资产；历史过渡逻辑集中在 `legacycutover`。整体布局体现"入口-领域-基础设施"的清晰分层。
<cite>cmd/ccagent/main.go:16-22</cite>

## 核心组件

- **TunnelHub 与会话回调**：`runGRPCServe` 创建 `control.NewTunnelHub(token, limits)`，通过 `control.SetTunnelHub(hub)` 注入全局枢纽；`SetOnHeartbeat` 回调以 `sync.Mutex` 保护 `heartbeats` 映射，记录各会话心跳计数<sup><cite>cmd/ccprobe-control/serve.go:29-187</cite></sup>。
- **控制面入口与运行模式**：`ccprobe-control` 同时提供 `-serve`（gRPC 管理面）与默认探针 CLI 两种运行模式，后者通过 `-agent-url`、`-agent-token`、`-target`、`-service` 等标志与 `probe-agent` 交互<sup><cite>cmd/ccprobe-control/main.go:23-80</cite></sup>。
- **客户端初始化**：`ccagent` 在 `init()` 中按需设置 `GODEBUG=netdns=go`，保证 Alpine musl 环境下的 DNS 行为可预测<sup><cite>cmd/ccagent/main.go:16-22</cite></cite>。
- **自定义探针协议**：`custom-probe` 暴露 `ProbeResult` 结构体，包含 `Success`、`StatusCode`、`ResponseTimeMs`、`ErrorMessage`、`Details`、`Metrics` 字段，是 Custom Probe 模式的标准输出契约<sup><cite>cmd/custom-probe/main.go:20-27</cite></sup>。
- **Loopback 监听判定**：控制面在 TLS 与监听地址检查中复用 `isLoopbackListen` 用例（127.0.0.1、::1 通过；0.0.0.0、:19090 拒绝），用于管理面绑定策略<sup></sup>。

## 详细分析

控制面启动时，`runGRPCServe` 构造 `TunnelHub` 并以 `control.SetTunnelHub` 将其挂入进程内全局，再注册心跳回调。`heartbeats` 在回调中以写锁安全累加，作为后续健康度与限流策略的依据<sup><cite>cmd/ccprobe-control/serve.go:29-187</cite></sup>。`SoftLimits` 与 `GRPCTLSFiles` 一同传入，用于约束并发隧道与加密传输配置。

探测数据流上，`ccprobe-control` 默认以 CLI 模式直接对目标执行探测，结果通过 `ProbeResult` 形态落入 Custom Probe 输出；而在服务模式下，控制面接收 `ccagent` 经由 `-agent-url` 上报的数据。`ccagent` 自身依赖 Alpine 环境的 DNS 兜底，规避 musl 解析差异带来的不确定性<sup><cite>cmd/ccagent/main.go:16-22</cite></sup>。结果导出与多渠道分发由 `internal/exporter` 承担，业务编排位于 `internal/services`，持久化通过 `internal/repository` 与 `internal/dbconn` 协作完成。

## 依赖关系分析

`cmd/ccprobe-control/serve.go` 强依赖 `internal/control` 中的 `TunnelHub`、`SoftLimits`、`GRPCTLSFiles` 与 `TunnelSession` 类型，是连接入口层与领域层的关键耦合点<sup><cite>cmd/ccprobe-control/serve.go:29-187</cite></sup>。`ccagent` 的 `init` 行为体现运行时依赖：仅当 `GODEBUG` 未设置时启用 `netdns=go`，意味着上层配置可被显式覆盖<sup><cite>cmd/ccagent/main.go:16-22</cite></sup>。变更影响上，修改 `SoftLimits` 或 `TunnelHub` 行为会同时波及 `ccprobe-control` 服务模式与通过其注册的任何外部客户端。

## 性能考虑

`runGRPCServe` 在心跳路径上每次加锁 `sync.Mutex`，高频率心跳可能成为热点；评估是否需要分片锁或原子计数对吞吐至关重要<sup><cite>cmd/ccprobe-control/serve.go:29-187</cite></sup>。`SoftLimits` 的具体阈值需结合 `services` 与 `repository` 的批处理粒度校准，避免限流误触发。`exporter` 多渠道写出时，IO 抖动会回压到探测链路，建议在 `metrics` 与 `opsmetrics` 中观测导出 P95 延迟。

## 故障排查指南

首先确认控制面是否以 `-serve -transport grpc` 模式启动，并验证管理面仅绑定 loopback（参考 `isLoopbackListen` 用例）以避免公网暴露<sup></sup>。在 Alpine 部署出现 DNS 异常时，检查 `GODEBUG` 是否被显式覆盖导致 `netdns=go` 未生效<sup><cite>cmd/ccagent/main.go:16-22</cite></sup>。自定义探针结果缺失字段时，比对 `ProbeResult` 的 JSON tag 与 `validator` 期望的契约<sup><cite>cmd/custom-probe/main.go:20-27</cite></sup>。心跳停滞时，查看 `TunnelHub.SetOnHeartbeat` 回调是否被正确注册，以及 `SoftLimits` 是否过早拒绝新会话<sup><cite>cmd/ccprobe-control/serve.go:29-187</cite></sup>。

## 结论

本页围绕 `probe_exporter` 的控制面与服务拆分，串联 `ccprobe-control` gRPC 服务、`ccagent` 客户端、`custom-probe` 输出契约与各 `internal/*` 领域包，明确了 TunnelHub 会话中心、`SoftLimits` 资源约束与 `ProbeResult` 探测契约三条主线。读者可据此理解 Blackbox 与 Custom Probe 双模式如何被采集、验证与多渠道导出，以及在 Alpine 与 gRPC 模式下需要关注的兼容性与安全边界。
<cite>cmd/ccprobe-control/serve.go:29-187</cite>

## 目录

1. 简介
2. 项目结构
3. 核心组件
4. 详细分析
5. 依赖关系分析
6. 性能考虑
7. 故障排查指南
8. 结论

ccagent 是主 REST/Web 服务；probe-agent 是隧道客户端；控制面通过 gRPC（ccprobe-control -serve -transport grpc）调度 services → repository → exporter。不要把 package main 的 custom-probe 当成可导入库。 <cite>cmd/ccagent/main.go:1-8</cite> <cite>cmd/ccprobe-control/main.go:1-8</cite> <cite>internal/control/expand.go:1-8</cite> <cite>internal/services/agent_ops.go:1-8</cite> <cite>internal/repository/agent_ops_repo.go:1-8</cite> <cite>internal/exporter/exporter.go:1-8</cite> <cite>internal/agent/buffer/ring.go:1-8</cite> <cite>internal/probe/agent_auth.go:1-8</cite>
