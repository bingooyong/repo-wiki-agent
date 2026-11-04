# 认证授权API

## 简介

本仓库 probe_exporter 是面向企业级的服务探针拨测与结果导出平台，支持 **双模式探测**（Blackbox + Custom Probe）、灵活的验证引擎、多渠道导出，并提供完整的 Web 管理界面。

本页面聚焦于平台对外提供的认证授权相关 API 能力。在源码层面，`apiauth.go` 中提供了 Bearer Token 的解析函数 `BearerToken`，用于从 `Authorization` 头中剥离前缀并返回原始令牌字符串，构成平台认证授权的最小处理单元 <cite>apiauth.go:38-45</cite>。其余业务端点（探针配置、任务调度、结果查询、Agent 管理、业务实例/策略/路由/密钥/标签树等）则由控制器统一装配，并对请求参数进行绑定与校验 <cite>controller.go:52-154</cite>。

## 项目结构

与认证授权 API 直接相关的源码集中在以下文件：

`apiauth.go`：提供 `BearerToken` 解析函数，是请求入口识别调用方凭证的辅助工具。 `controller.go`：作为 HTTP 控制器基座，在 `Run()` 中启动服务并装配所有路由（包含 `/api/v1/biz/secret/*` 等敏感资源端点），同时定义 `paramBindError` 用于在参数绑定失败时透传原始错误 <cite>controller.go:218-219</cite>。

其余路由按业务域分布在 `probe/*`、`/api/v1/biz/*`、`/api/v1/profile/*`、`/api/v1/agent/*`、`/tag/*` 等分组中（参见附录），这些端点在控制器层共用同一套中间件与错误处理路径，因此认证授权能力对它们具备一致的作用面。
<cite>controller.go:218-219</cite>

## 核心组件

`BearerToken(authorization string) string`：解析 `Authorization` 头。大小写不敏感地匹配 `bearer ` 前缀并返回剥离后的令牌；当头部为空或前缀不匹配时返回空串 <cite>apiauth.go:38-45</cite>。 `Controller.Run()`：控制器启动入口，负责加载配置、设置遗留端点开关（`LegacyEndpoints.WriteEnabled`、`LegacyEndpoints.ScheduleEnabled`）并装配全部 HTTP 路由 <cite>controller.go:52-154</cite>。 `paramBindError`：参数绑定阶段的错误类型，实现了 `Error()` 与 `Unwrap()`，便于在调用栈中将底层绑定错误（如参数缺失、类型不匹配）原样向上抛出 <cite>controller.go:218-222</cite>。

## 架构总览

平台对外暴露的 HTTP 服务由 `Controller.Run()` 统一引导；请求进入后，认证中间件优先读取 `Authorization` 头并调用 `BearerToken` 提取凭证 <cite>apiauth.go:38-45</cite>。验证通过后，请求按路由分组（探针、Agent、业务、标签、profile 等）分发到对应处理函数；处理函数通过 `paramBindError` 风格的错误通道反馈参数绑定问题，最终由控制器统一序列化响应 <cite>controller.go:52-154</cite>。

由于 `BearerToken` 仅负责解析而不做签名校验或权限判定，授权决策通常落在各业务 handler 或后续中间件中；密钥（secret）等敏感资源的 CRUD 端点（参见附录）尤其依赖该链路完成调用方身份核验。
<cite>apiauth.go:38-45</cite>

## 详细组件分析

### Bearer Token 解析

`BearerToken` 的实现采用 `strings.TrimSpace` 先归一化头部空白，再通过长度检查与 `strings.EqualFold` 实现大小写不敏感的前缀比对，从而兼容 `Bearer`、`bearer` 等写法。匹配成功后，使用 `strings.TrimSpace` 二次清理令牌两端的空白以避免下游误判；未匹配时返回空串，调用方据此判断是否进入匿名分支或直接拒绝 <cite>apiauth.go:38-45</cite>。

### 控制器与参数绑定错误

`Controller.Run()` 在启动期通过 `legacycutover.Set` 控制遗留写入与调度端点的开关，使新旧接口在同一进程内可灰度共存 <cite>controller.go:52-154</cite>。`paramBindError` 作为绑定阶段的统一错误包装，通过 `Error()` 直接转发错误文本并通过 `Unwrap()` 暴露底层错误，便于上层中间件按错误类型进行差异化的 4xx 响应处理 <cite>controller.go:218-222</cite>。

### 与业务端点的协同

平台在 `/api/v1/biz/secret/*` 中暴露了密钥的创建、查询、列表、更新与删除能力，这些端点通常要求调用方提供具备相应权限的 Bearer Token；与此同时，`/api/v1/profile/*` 与 `/api/v1/agent/*` 等端点同样依赖控制器装配的同一套认证授权链路，从而在认证解析与参数绑定两个维度保持一致行为 <cite>controller.go:52-154</cite>。

## 附录：关键端点

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/biz/secret/create` | 创建业务密钥 |
| DELETE | `/api/v1/biz/secret/delete/:id` | 删除业务密钥 |
| GET | `/api/v1/biz/secret/get/:id` | 获取单个业务密钥 |
| GET | `/api/v1/biz/secret/list` | 列出业务密钥 |
| PUT | `/api/v1/biz/secret/update/:id` | 更新业务密钥 |
| POST | `/api/v1/dryrun/execute` | 试运行探测任务 |
| GET | `/api/v1/profile/list` | 列出 profile |
| POST | `/api/v1/profile/sync/:service_name` | 同步指定服务的 profile |

## 目录

1. 简介
2. 项目结构
3. 核心组件
4. 架构总览
5. 详细组件分析
6. 附录：关键端点

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
