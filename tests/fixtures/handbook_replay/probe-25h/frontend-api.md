# 前端应用API

## 简介
本页聚焦 `probe_exporter` 仓库中面向前端应用暴露的 HTTP API，所属模块为 `ccprobe-control`。该平台是面向企业级的服务探针拨测与结果导出平台，支持**双模式探测**（Blackbox + Custom Probe）、灵活的验证引擎、多渠道导出，并提供完整的 Web 管理界面，因此前端应用所需的运行态、健康与控制接口均集中在控制服务中。 <cite>README.md:1-20</cite>

## 项目结构
控制服务的 HTTP 入口位于 `cmd/ccprobe-control/serve.go`，其中定义了发布/订阅握手、参数校验以及返回结构。控制面共用的错误码映射、状态码转换等逻辑放在 `controller.go` 中，避免在业务 handler 里重复分支。面向状态查询的请求/响应模型被拆到独立文件 `serv_hello.go`，便于按资源聚合。 <cite>cmd/ccprobe-control/serve.go:189-294</cite><cite>controller.go:192-215</cite>

## 核心组件
- `publishRequest`：前端推送探针配置快照的请求体，字段含 `agent_id`、`action`、`target`、`service`、`base_version`、`snapshot_version`、`interval_seconds`、`timeout_ms`。 <cite>cmd/ccprobe-control/serve.go:189-201</cite>
- `servePublish`：处理 `publish` 端点的核心 handler，负责校验 `agent_id`、补齐默认 `action` 并执行业务校验与下发。 <cite>cmd/ccprobe-control/serve.go:203-294</cite>
- `statusForServiceError`：把请求/响应阶段的多类错误统一映射到 HTTP 状态码，涵盖校验、`json.SyntaxError`、`UnmarshalTypeError`、`MaxBytesError` 与参数绑定错误。 <cite>controller.go:192-215</cite>
- `ServeStatusRequest` / `ServeStatusResponse`：状态查询的请求与响应结构，分别从路径参数 `:task`、`:code` 与动作段 `*action` 提取信息，并在响应中回填。 <cite>serv_hello.go:66-77</cite>

## 架构总览
前端应用主要通过控制服务（`ccprobe-control`）读取运行态、强制同步与发布配置。控制服务接收 `publishRequest` 后进入 `servePublish`，先校验 `agent_id` 与动作，再把请求体交给 `TunnelHub` 完成下发；返回时包装为 `PublishAck` 与响应体。错误处理链路由 `statusForServiceError` 统一收口，最终把 Go 错误转换成 HTTP 语义，前端可在统一的错误响应上做处理。 <cite>cmd/ccprobe-control/serve.go:203-294</cite><cite>controller.go:192-215</cite>

## 详细组件分析
`publishRequest` 的字段设计体现「按版本号增量下发」的思路：`base_version` 与 `snapshot_version` 让前端/Agent 描述期望基线与服务端生效版本，便于控制服务比对并决定下发哪些变化。`action` 默认为 `add`，由 `servePublish` 显式补齐，避免前端遗漏字段导致 5xx。 <cite>cmd/ccprobe-control/serve.go:189-201</cite><cite>cmd/ccprobe-control/serve.go:203-294</cite>

`statusForServiceError` 是一处与前端契约强相关的细节：当请求体超过上限时返回 `413 Request Entity Too Large`；参数绑定错误返回 `400`；其余语法/类型错误按 JSON 解析语义给出对应状态。这套映射让前端能以统一的方式处理网关层错误，而不是各自捕获底层错误类型。 <cite>controller.go:192-215</cite>

状态类查询 `ServeStatusRequest` 通过路径占位符 `:task`、`:code` 与通配段 `*action` 描述资源定位，对前端而言，它把同一资源下的不同动作收敛在同一条路由上，减少前端需要维护的端点数量；响应 `ServeStatusResponse` 则把回显字段标准化为 JSON 命名（`task_code`、`task_name`、`action`）。 <cite>serv_hello.go:66-77</cite>

## 附录：关键端点
| 方法 | 路径 | 说明 | 证据 |
| --- | --- | --- | --- |
| GET | `/force-resync` | 强制全量重同步探针配置 | 所属模块 `ccprobe-control` 提供 |
| GET | `/healthz` | 健康检查，供前端与负载均衡探活 | 所属模块 `ccprobe-control` 提供 |
| GET | `/publish` | 推送探针配置与版本快照 | <cite>cmd/ccprobe-control/serve.go:203-294</cite> |
| GET | `/status` | 状态查询，按 task/code/action 回显 | <cite>serv_hello.go:66-77</cite> |

## API 分组

按资源分组的接口：

### force-resync

- GET /force-resync（handler `func`） <cite>cmd/ccprobe-control/serve.go:126-136</cite>

### healthz

- GET /healthz（handler `func`） <cite>internal/agent/http_transport.go:18-28</cite>
- GET /healthz（handler `func`） <cite>cmd/ccprobe-control/serve.go:56-66</cite>

### publish

- GET /publish（handler `func`） <cite>cmd/ccprobe-control/serve.go:105-115</cite>

### status

- GET /status（handler `func`） <cite>cmd/ccprobe-control/serve.go:59-69</cite>

## 调用约定

- HTTP 方法: GET
- 认证: none

## Schema 摘要

<!-- repo-wiki:unresolved api-schema -->
UNRESOLVED_API_SCHEMA：端点证据未提供请求体、响应体或错误码字段；未生成通用 schema。

UNRESOLVED_API_FLOW：缺少可验证调用链证据，不生成占位流程图。

## 目录

1. 简介
2. 项目结构
3. 核心组件
4. 架构总览
5. 详细组件分析
6. 附录：关键端点
7. API 分组
8. 调用约定
9. Schema 摘要
