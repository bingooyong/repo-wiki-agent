# 架构设计

## 进程角色

ccagent 是主 REST/Web 服务；probe-agent 是隧道客户端；ccprobe-control 是 gRPC 控制面服务。 <cite>cmd/ccagent/main.go:16-16</cite> <cite>cmd/ccprobe-control/main.go:23-23</cite> <cite>internal/control/expand.go:17-17</cite> <cite>internal/services/agent_ops.go:29-29</cite> <cite>internal/repository/agent_ops_repo.go:11-11</cite> <cite>internal/exporter/exporter.go:24-24</cite>

ccagent 是主 REST/Web 服务。 <cite>cmd/ccagent/main.go:24-24</cite>

probe-agent 是隧道客户端。 <cite>cmd/probe-agent/main.go:58-58</cite>

ccprobe-control 是 gRPC 控制面服务（`-serve -transport grpc`）。 <cite>cmd/ccprobe-control/main.go:23-23</cite>

## 简介

本页面向 `probe_exporter` 仓库,定位为面向企业级的服务探针拨测与结果导出平台,支持双模式探测(Blackbox + Custom Probe)、灵活的验证引擎、多渠道导出,并提供完整的 Web 管理界面。仓库以 Go 为主语言,主要服务入口包含控制面 `ccprobe-control` 与边缘 Agent `ccagent`,辅以 `custom-probe` 等可执行探针示例。架构上需要厘清控制面与 Agent 的职责边界、gRPC 与 HTTP 通道差异,以及运行时配置、审计、安全、导出等横切模块的协作关系。
<cite>cmd/ccprobe-control/serve.go:29-187</cite>

## 项目结构

仓库顶层模块按职责切分,关键包包括 `config.go`、`deploy`、`agent`、`audit`、`auth`、`contract`、`control`、`dbconn`、`exporter`、`legacycutover`、`metrics`、`models`、`netguard`、`opsmetrics`、`opsstore`、`probe`、`repository`、`secrets`、`security`、`services`、`validator` 以及顶层 `tls.go`。其中 `control` 承载控制面核心逻辑(隧道枢纽、会话、gRPC TLS),`services` 聚合领域用例,`repository` 负责持久化访问,`exporter` 负责指标导出,`agent` 负责 probe-agent 隧道客户端相关能力,`probe` 提供内置 Blackbox 探针实现。入口二进制分别位于 `cmd/ccprobe-control/`、`cmd/ccagent/`、`cmd/custom-probe/` 等目录,形成“控制面 + 隧道 Agent + 探针实现”的清晰分层。
<cite>cmd/custom-probe/main.go:20-27</cite>

## 核心组件

控制面 gRPC 服务是整个系统的中枢。`cmd/ccprobe-control/serve.go` 中的 `runGRPCServe` 同时监听 gRPC 与 Admin 端口,创建 `control.TunnelHub` 并将其注册到全局,通过对回调 `SetOnHeartbeat` 维护心跳映射 `heartbeats`,用于跟踪隧道会话活性与限流配合。控制面入口 `cmd/ccprobe-control/main.go` 提供 `-serve -transport grpc` 模式之外的探测相关命令行(例如 `-agent-url`、`-agent-token`、`-target`、`-service`),用于在不启动控制面时驱动快速拨测与 Agent 联动验证。边缘 Agent `cmd/ccagent/main.go` 在初始化阶段为 Alpine 容器强制启用纯 Go DNS 解析器,通过设置 `GODEBUG=netdns=go` 规避 musl libc 与 Go 网络轮询器的兼容性问题,体现对生产容器化部署的兜底处理。`cmd/custom-probe/main.go` 定义的 `ProbeResult` 结构体是 Custom Probe 的标准输出契约,字段包含 `success`、`status_code`、`response_time_ms`、`error_message`、`details`、`metrics`,供 `exporter` 与 `repository` 统一消费。
<cite>cmd/ccprobe-control/serve_test.go:9-24</cite>

## 详细分析

控制面与 Agent 通过隧道建立双向通道。`runGRPCServe` 在启动时构建 `control.NewTunnelHub(token, limits)`,并通过 `control.SetTunnelHub(hub)` 注入到进程内单例,后续 `internal/services` 层可基于该单例完成会话管理、心跳校验与软限流判定;Admin 端口通常用于本地运维访问,需结合 `control.GRPCTLSFiles` 决定是否启用 TLS,详见 <cite>cmd/ccprobe-control/serve.go:29-187</cite>。控制面 CLI 在不进入 `-serve` 模式时表现为带 `-agent-url` 与 `-agent-token` 的拨测客户端,默认 `target` 为 `https://www.baidu.com/`,并支持 `https://ip.cc/` 这种 IP 反查形式,直接面向最终拨测目标。Agent 端只暴露运行期前置约束(DNS 解析器选择),并不负责协议握手细节。Custom Probe 作为独立 `package main`,以 `ProbeResult` JSON 形态输出,保持与控制面解耦,避免类型在控制面被直接导入。

## 依赖关系分析

控制面是依赖汇聚点:`internal/control` 依赖 `internal/services` 与 `internal/repository` 完成隧道会话持久化与领域操作,`internal/exporter` 订阅 `internal/services` 产生的事件并推送至外部监控系统,`internal/metrics` 与 `internal/opsmetrics` 提供指标与运维观测。`internal/agent` 作为隧道客户端,反向连接控制面 gRPC,依赖 `internal/contract` 定义的协议契约;`internal/probe` 提供 Blackbox 探针实现,被 `internal/services` 在拨测任务调度时调用。`internal/security`/`internal/auth`/`internal/secrets`/`internal/netguard` 共同承担认证与安全边界,横切作用于控制面入口、gRPC 监听和导出通道。`internal/audit`、`internal/dbconn`、`internal/opsstore`、`internal/deploy`、`internal/legacycutover`、`internal/validator` 与 `models`、`config.go`、`tls.go` 配套提供审计、连接、运维存储、部署切换、参数校验、配置加载与传输加密能力。Custom Probe 作为独立二进制,不反向依赖控制面类型,仅按 `ProbeResult` 契约输出,降低耦合面。
<cite>cmd/ccprobe-control/main.go:23-80</cite>

## 性能考虑

控制面 `runGRPCServe` 同时持有 `heartMu` 与 `heartbeats` 映射,所有会话心跳都会触发回调写操作,需关注高并发会话下互斥锁粒度与热点 key 写入;`limits` 软限流配置直接决定并发上限,应在 `control.SoftLimits` 处合理设置连接与速率阈值。Agent 端在 Alpine 容器中强制启用纯 Go DNS 解析器会绕过 musl 缓存,首次解析延迟可能上升,需要权衡容器兼容性与 DNS 吞吐,可通过调整并发拨测规模或前置 DNS 预热缓解。Custom Probe 输出 `details` 与 `metrics` 字段均为可扩展负载,导出与持久化路径需对体积与字段数量做限流,避免单次结果过大导致 `repository` 与 `exporter` 出现 IO 抖动。gRPC TLS 配置通过 `control.GRPCTLSFiles` 注入,启用 TLS 会带来握手成本,建议在批拨测与长连接复用场景优先复用会话。
<cite>cmd/ccagent/main.go:16-22</cite>

## 故障排查指南

启动控制面时如未拉起隧道,先检查 <cite>cmd/ccprobe-control/serve.go:29-187</cite> 中 `runGRPCServe` 的 gRPC 与 Admin 监听地址,并确认 `control.SetTunnelHub` 是否成功注入;若仅做命令行拨测验证,可参考 <cite>cmd/ccprobe-control/main.go:23-80</cite> 的 `-agent-url`、`-agent-token`、`-target` 默认值核对连通性。Agent 在 Alpine 镜像下出现 DNS 解析异常时,确认 <cite>cmd/ccagent/main.go:16-22</cite> 中 `GODEBUG=netdns=go` 是否生效,必要时显式注入该变量。Custom Probe 输出无法被下游消费时,核对 <cite>cmd/custom-probe/main.go:20-27</cite> 的 `ProbeResult` 字段是否齐全且 JSON tag 命名匹配。启用 gRPC TLS 时优先确认 `internal/control` 的 `GRPCTLSFiles` 与 `tls.go` 配置一致性。

## 结论

本页面梳理了 `probe_exporter` 的控制面 + 隧道 Agent + Custom Probe 三层骨架及其横切模块依赖,明确了 `ccprobe-control` 作为主 REST/Web 与 gRPC 控制面的入口定位、`ccagent` 作为隧道客户端的兜底 DNS 处理,以及 `ProbeResult` 作为 Custom Probe 标准契约的价值。读者可据此理解模块边界、调用方向与关键风险点,为后续在 `internal/services`、`internal/repository`、`internal/exporter` 内的功能扩展提供稳定参照。
<cite>cmd/ccprobe-control/serve.go:29-187</cite>

## 研究文档（引用来源参考）

## 目录

1. 进程角色
2. 简介
3. 项目结构
4. 核心组件
5. 详细分析
6. 依赖关系分析
7. 性能考虑
8. 故障排查指南
9. 结论
10. 研究文档（引用来源参考）
