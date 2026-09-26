# 认证授权API

## 简介

本页聚焦 `probe_exporter` 仓库中的认证授权相关 API 实现。`probe_exporter` 是面向企业级的服务探针拨测与结果导出平台，支持**双模式探测**（Blackbox + Custom Probe）、灵活的验证引擎、多渠道导出，并提供完整的 Web 管理界面，✨ 核心特性 🎯 双模式探测。
<cite>controller.go:221-222</cite>

在 HTTP 入口层，平台通过 Bearer Token 解析函数从请求头中剥离凭证，供后续中间件完成鉴权决策。该机制与路由层、解码层、调度层松耦合，是认证授权子系统的基础原语之一。

## 项目结构

认证授权相关的源码集中在控制层（`controller` 包）以及辅助工具函数中。从提供的证据可见，关键源文件包括：
<cite>controller.go:220-221</cite>

`apiauth.go`：提供 `BearerToken` 解析工具函数。 `controller.go`：包含控制器 `Run` 入口、参数绑定错误类型 `paramBindError` 及其 `Error`、`Unwrap` 方法。
<cite>controller.go:52-154</cite>
<cite>controller.go:218-219</cite>

## 核心组件

`BearerToken(authorization string) string`：从 HTTP `Authorization` 头中剥离 `bearer ` 前缀并返回 token 文本；不区分大小写匹配前缀；当长度不足或未匹配时返回空串。<cite>apiauth.go:38-45</cite>。 `Controller.Run()`：控制器启动入口，负责日志打印、遗留端点开关设置以及后续 HTTP 服务的运行；其配置中包含 `LegacyEndpoints.WriteEnabled` 与 `LegacyEndpoints.ScheduleEnabled` 等开关。<cite>controller.go:52-154</cite>。 `paramBindError`：参数绑定阶段产生的错误包装类型，实现了 `Error()` 与 `Unwrap()`，可被 `errors.Is/As` 用于定位底层绑定失败原因。<cite>controller.go:218-219</cite><cite>controller.go:220-221</cite><cite>controller.go:221-222</cite>。

## 架构总览

认证授权在请求生命周期中处于早期阶段：`BearerToken` 作为轻量解析器，从请求头提取 token，随后由中间件基于该 token 完成身份与权限判定。`Controller.Run()` 在启动时统一加载 `LegacyEndpoints` 配置，决定遗留写入与调度端点是否对外开放，间接影响认证边界。绑定错误 `paramBindError` 则在参数解码链路尾部参与错误传播，使上层能识别“绑定失败”这一类别。
<cite>apiauth.go:38-45</cite>

## 详细组件分析

`BearerToken` 的实现先做 `TrimSpace` 清洗，再以 `EqualFold` 校验前 7 字节是否等于 `"bearer "`，匹配后截取剩余部分再次 `TrimSpace` 返回，从而兼容 `Bearer`、`bearer`、`BEARER` 等大小写形式与多余空白。<cite>apiauth.go:38-45</cite> 该函数刻意只做字符串解析、不做合法性校验，便于在中间件中以分层方式先取 token、再做签名/校验。

`Controller.Run()` 是平台 HTTP 入口装配点，其内部通过 `legacycutover.Set` 设置遗留端点的读写与调度开关，并打印相应状态日志；后续端点注册、`/v1/ops`、`/v1/tasks`、`/probe/*`、`/api/v1/biz/*`、`/api/v1/profile/*` 等众多路由在该运行期内挂载，构成完整的对外 API 面。<cite>controller.go:52-154</cite>

`paramBindError` 通过组合 `err error` 字段并实现 `Error()` 与 `Unwrap()`，使上层既可以透出底层错误信息，又能借助 `errors.Is/As` 区分“参数绑定失败”与其他错误，便于在认证授权链路中将绑定失败独立处理（例如记为 4xx 而非 5xx）。<cite>controller.go:218-219</cite><cite>controller.go:220-221</cite><cite>controller.go:221-222</cite>

## 附录：关键端点参考

| 方法   | 路径                              | 说明                         |
|--------|-----------------------------------|------------------------------|
| GET    | `/v1/ops`                         | 运维面查询                   |
| GET    | `/v1/tasks`                       | 任务列表                     |
| GET    | `/v1/tasks/diff`                  | 任务差异                     |
| GET    | `/probe/blackbox/get/:id`         | Blackbox 探测配置获取        |
| POST   | `/api/v1/biz/secret/create`       | 业务密钥创建（鉴权关联）     |
| GET    | `/api/v1/biz/secret/get/:id`      | 业务密钥读取（鉴权关联）     |
| GET    | `/live`                           | 存活探针                     |
| GET    | `/version`                        | 版本信息                     |

## API 分组

按资源分组的接口：

### /

GET /（handler `r.GET`） <cite>controller.go:107</cite>。 GET /（handler `func`） <cite>cmd/custom-probe/main.go:424-434</cite>。

### api/v1/agent

GET /api/v1/agent/list（handler `AgentTopologyFacade.ServeList`） <cite>internal/services/serv_ccprobe.go:224-234</cite>。 GET /api/v1/agent/ops/:agent_id（handler `AgentTopologyFacade.ServeOps`） <cite>internal/services/agent_ops.go:215-225</cite>。 GET /api/v1/agent/routes（handler `AgentTopologyFacade.ServeRoutes`） <cite>internal/services/serv_ccprobe.go:314-324</cite>。

### api/v1/biz

POST /api/v1/biz/import/endpoints（handler `ServiceBizImport.ServeEndpoints`） <cite>internal/services/serv_biz_import.go:46-56</cite>。 POST /api/v1/biz/instance/create（handler `ServiceBizInstance.ServeCreate`） <cite>internal/services/serv_biz.go:341-351</cite>。 DELETE /api/v1/biz/instance/delete/:id（handler `ServiceBizInstance.ServeDelete`） <cite>internal/services/serv_biz.go:470-480</cite>。 GET /api/v1/biz/instance/list（handler `ServiceBizInstance.ServeList`） <cite>internal/services/serv_biz.go:315-325</cite>。 POST /api/v1/biz/instance/toggle/:id（handler `ServiceBizInstance.ServeToggle`） <cite>internal/services/serv_biz.go:498-508</cite>。 PUT /api/v1/biz/instance/update/:id（handler `ServiceBizInstance.ServeUpdate`） <cite>internal/services/serv_biz.go:422-432</cite>。 POST /api/v1/biz/policy/create（handler `ServiceBizPolicy.ServeCreate`） <cite>internal/services/serv_biz.go:733-743</cite>。 DELETE /api/v1/biz/policy/delete/:id（handler `ServiceBizPolicy.ServeDelete`） <cite>internal/services/serv_biz.go:851-861</cite>。 GET /api/v1/biz/policy/list（handler `ServiceBizPolicy.ServeList`） <cite>internal/services/serv_biz.go:693-703</cite>。 PUT /api/v1/biz/policy/update/:id（handler `ServiceBizPolicy.ServeUpdate`） <cite>internal/services/serv_biz.go:794-804</cite>。 POST /api/v1/biz/routing/create（handler `ServiceBizRouting.ServeCreate`） <cite>internal/services/serv_biz.go:914-924</cite>。 DELETE /api/v1/biz/routing/delete/:id（handler `ServiceBizRouting.ServeDelete`） <cite>internal/services/serv_biz.go:1025-1035</cite>。 GET /api/v1/biz/routing/list（handler `ServiceBizRouting.ServeList`） <cite>internal/services/serv_biz.go:884-894</cite>。 PUT /api/v1/biz/routing/update/:id（handler `ServiceBizRouting.ServeUpdate`） <cite>internal/services/serv_biz.go:983-993</cite>。 POST /api/v1/biz/secret/create（handler `ServiceBizSecret.ServeCreate`） <cite>internal/services/serv_biz_secret.go:129-139</cite>。 DELETE /api/v1/biz/secret/delete/:id（handler `ServiceBizSecret.ServeDelete`） <cite>internal/services/serv_biz_secret.go:209-219</cite>。 GET /api/v1/biz/secret/get/:id（handler `ServiceBizSecret.ServeGet`） <cite>internal/services/serv_biz_secret.go:105-115</cite>。 GET /api/v1/biz/secret/list（handler `ServiceBizSecret.ServeList`） <cite>internal/services/serv_biz_secret.go:80-90</cite>。 PUT /api/v1/biz/secret/update/:id（handler `ServiceBizSecret.ServeUpdate`） <cite>internal/services/serv_biz_secret.go:158-168</cite>。 POST /api/v1/biz/tree/create（handler `ServiceBizTree.ServeCreate`） <cite>internal/services/serv_biz.go:110-120</cite>。 DELETE /api/v1/biz/tree/delete/:id（handler `ServiceBizTree.ServeDelete`） <cite>internal/services/serv_biz.go:232-242</cite>。 GET /api/v1/biz/tree/list（handler `ServiceBizTree.ServeList`） <cite>internal/services/serv_biz.go:81-91</cite>。 GET /api/v1/biz/tree/tree（handler `ServiceBizTree.ServeTree`） <cite>internal/services/serv_biz.go:64-74</cite>。 PUT /api/v1/biz/tree/update/:id（handler `ServiceBizTree.ServeUpdate`） <cite>internal/services/serv_biz.go:155-165</cite>。

### api/v1/dryrun

POST /api/v1/dryrun/execute（handler `DryRunFacade.ServeExecute`） <cite>internal/services/serv_ccprobe.go:388-398</cite>。

### api/v1/internal

POST /api/v1/internal/agent/publish（handler `ServiceInternalAgent.ServePublish`） <cite>internal/services/serv_internal_publish.go:41-51</cite>。

### api/v1/profile

GET /api/v1/profile/:service_name/instances/list（handler `ServiceProfileFacade.ServeList`） <cite>internal/services/serv_ccprobe.go:79-89</cite>。 POST /api/v1/profile/:service_name/instances/sync（handler `ServiceProfileFacade.ServeSync`） <cite>internal/services/serv_ccprobe.go:114-124</cite>。 GET /api/v1/profile/list（handler `ServiceProfileFacade.ServeList`） <cite>internal/services/serv_ccprobe.go:79-89</cite>。 POST /api/v1/profile/sync/:service_name（handler `ServiceProfileFacade.ServeSync`） <cite>internal/services/serv_ccprobe.go:114-124</cite>。

### live

GET /live（handler `r.GET`） <cite>controller.go:88</cite>。

### probe

GET /probe（handler `server`） <cite>cmd/custom-probe/main.go:422-432</cite>。

### probe/blackbox

ANY /probe/blackbox/create（handler `ServiceProbeBlackbox.ServeCreate`） <cite>internal/services/serv_probe_blackbox.go:45-55</cite>。 DELETE /probe/blackbox/delete/:id（handler `ServiceProbeBlackbox.ServeDelete`） <cite>internal/services/serv_probe_blackbox.go:155-165</cite>。 GET /probe/blackbox/get/:id（handler `ServiceProbeBlackbox.ServeGet`） <cite>internal/services/serv_probe_blackbox.go:178-188</cite>。 ANY /probe/blackbox/getall（handler `ServiceProbeBlackbox.ServeGetAll`） <cite>internal/services/serv_probe_blackbox.go:253-263</cite>。 ANY /probe/blackbox/getbyname/:name（handler `ServiceProbeBlackbox.ServeGetByName`） <cite>internal/services/serv_probe_blackbox.go:202-212</cite>。 ANY /probe/blackbox/list（handler `ServiceProbeBlackbox.ServeList`） <cite>internal/services/serv_probe_blackbox.go:227-237</cite>。 ANY /probe/blackbox/update/:id（handler `ServiceProbeBlackbox.ServeUpdate`） <cite>internal/services/serv_probe_blackbox.go:95-105</cite>。

### probe/endpoint

ANY /probe/endpoint/activate/:id（handler `ServiceProbeEndpoint.ServeActivate`） <cite>internal/services/serv_probe_endpoint.go:748-758</cite>。 ANY /probe/endpoint/batchactivate（handler `ServiceProbeEndpoint.ServeBatchActivate`） <cite>internal/services/serv_probe_endpoint.go:818-828</cite>。 ANY /probe/endpoint/batchdeactivate（handler `ServiceProbeEndpoint.ServeBatchDeactivate`） <cite>internal/services/serv_probe_endpoint.go:851-861</cite>。 ANY /probe/endpoint/create（handler `ServiceProbeEndpoint.ServeCreate`） <cite>internal/services/serv_probe_endpoint.go:284-294</cite>。 ANY /probe/endpoint/deactivate/:id（handler `ServiceProbeEndpoint.ServeDeactivate`） <cite>internal/services/serv_probe_endpoint.go:783-793</cite>。 DELETE /probe/endpoint/delete/:id（handler `ServiceProbeEndpoint.ServeDelete`） <cite>internal/services/serv_probe_endpoint.go:638-648</cite>。 ANY /probe/endpoint/dryrun（handler `ServiceProbeEndpoint.ServeDryRun`） <cite>internal/services/serv_probe_endpoint.go:100-110</cite>。 GET /probe/endpoint/get/:id（handler `ServiceProbeEndpoint.ServeGet`） <cite>internal/services/serv_probe_endpoint.go:673-683</cite>。 ANY /probe/endpoint/list（handler `ServiceProbeEndpoint.ServeList`） <cite>internal/services/serv_probe_endpoint.go:705-715</cite>。 ANY /probe/endpoint/update/:id（handler `ServiceProbeEndpoint.ServeUpdate`） <cite>internal/services/serv_probe_endpoint.go:397-407</cite>。

### probe/result

GET /probe/result/get/:id（handler `ServiceProbeResult.ServeGet`） <cite>internal/services/serv_probe_result.go:136-146</cite>。 ANY /probe/result/latest（handler `ServiceProbeResult.ServeLatest`） <cite>internal/services/serv_probe_result.go:269-279</cite>。 ANY /probe/result/list（handler `ServiceProbeResult.ServeList`） <cite>internal/services/serv_probe_result.go:55-65</cite>。 ANY /probe/result/stats（handler `ServiceProbeResult.ServeStats`） <cite>internal/services/serv_probe_result.go:174-184</cite>。

### probe/schedule

ANY /probe/schedule/getjob/:id（handler `ServiceProbeSchedule.ServeGetJob`） <cite>internal/services/serv_probe_schedule.go:87-97</cite>。 ANY /probe/schedule/listjobs（handler `ServiceProbeSchedule.ServeListJobs`） <cite>internal/services/serv_probe_schedule.go:65-75</cite>。 ANY /probe/schedule/pausejob/:id（handler `ServiceProbeSchedule.ServePauseJob`） <cite>internal/services/serv_probe_schedule.go:111-121</cite>。 ANY /probe/schedule/reload（handler `ServiceProbeSchedule.ServeReload`） <cite>internal/services/serv_probe_schedule.go:40-50</cite>。 ANY /probe/schedule/resumejob/:id（handler `ServiceProbeSchedule.ServeResumeJob`） <cite>internal/services/serv_probe_schedule.go:134-144</cite>。

### tag/assign

ANY /tag/assign（handler `ServiceTag.ServeAssign`） <cite>internal/services/serv_tag.go:230-240</cite>。

### tag/endpointget

GET /tag/endpointget/:id（handler `ServiceTag.ServeEndpointGet`） <cite>internal/services/serv_tag.go:166-176</cite>。

### tag/endpoints

ANY /tag/endpoints（handler `ServiceTag.ServeEndpoints`） <cite>internal/services/serv_tag.go:400-410</cite>。

### tag/list

ANY /tag/list（handler `ServiceTag.ServeList`） <cite>internal/services/serv_tag.go:90-100</cite>。

### tag/tree

GET /tag/tree（handler `ServiceTag.ServeTree`） <cite>internal/services/serv_tag.go:49-59</cite>。

### tag/unassign

ANY /tag/unassign（handler `ServiceTag.ServeUnassign`） <cite>internal/services/serv_tag.go:350-360</cite>。

### v1/ops

GET /v1/ops（handler `func`） <cite>internal/agent/http_transport.go:44-54</cite>。

### v1/tasks

GET /v1/tasks（handler `func`） <cite>internal/agent/http_transport.go:28-38</cite>。 GET /v1/tasks/diff（handler `func`） <cite>internal/agent/http_transport.go:58-68</cite>。

### version

GET /version（handler `r.GET`） <cite>controller.go:90</cite>。

### debug/pprof

GET /debug/pprof/（handler `pprof`） <cite>xstats/pprof.go:48-58</cite>。 GET /debug/pprof/allocs（handler `Handle`） 。 GET /debug/pprof/block（handler `Handle`） 。 GET /debug/pprof/cmdline（handler `pprof`） 。 GET /debug/pprof/goroutine（handler `Handle`） <cite>xstats/pprof.go:50-60</cite>。 GET /debug/pprof/heap（handler `Handle`） <cite>xstats/pprof.go:49-59</cite>。 GET /debug/pprof/mutex（handler `Handle`） 。 GET /debug/pprof/profile（handler `pprof`） 。 GET /debug/pprof/symbol（handler `pprof`） 。 POST /debug/pprof/symbol（handler `pprof`） 。 GET /debug/pprof/threadcreate（handler `Handle`） 。 GET /debug/pprof/trace（handler `pprof`） 。

### debug/statsviz

GET /debug/statsviz/*filepath（handler `r.GET`） <cite>xstats/statsviz.go:39</cite>。

### hello/echo

ANY /hello/echo（handler `ServiceHello.ServeEcho`） <cite>serv_hello.go:41-51</cite>。

### hello/error

ANY /hello/error（handler `ServiceHello.ServeError`） <cite>serv_hello.go:57-67</cite>。

### hello/get

GET /hello/get/:id（handler `ServiceHello.ServeGet`） 。

### reflect/list

ANY /reflect/list（handler `ServiceReflect.ServeList`） <cite>serv_reflect.go:44-54</cite>。

## 调用约定

HTTP 方法: ANY, DELETE, GET, POST, PUT。 认证: bearer。

## Schema 摘要

本节 Schema 与 API 参考中已给出的摘要相同，见该节，避免重复粘贴。

UNRESOLVED_API_FLOW：缺少可验证调用链证据，不生成占位流程图。

## 目录

1. 简介
2. 项目结构
3. 核心组件
4. 架构总览
5. 详细组件分析
6. 附录：关键端点参考
7. API 分组
8. 调用约定
9. Schema 摘要
