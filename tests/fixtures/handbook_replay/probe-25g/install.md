# 安装指南

## 这是什么

probe_exporter 是面向企业级的服务探针拨测与结果导出平台，支持双模式探测（Blackbox + Custom Probe）、灵活的验证引擎、多渠道导出，并提供完整的 Web 管理界面。<cite>README.md:69-70</cite> 本页面向需要将 probe_exporter 跑起来并连通数据库、Web 与 Agent 的运维与开发人员，按步骤完成后即可获得一个可拨测、可导出结果的运行实例。

## 环境要求

probe_exporter 的容器编排资产位于 `deploy/compose/ha/`，由仓库根 `docker-compose.ha.yml` 引用，因此本地需要有兼容的容器运行时与编排工具。<cite>deploy/compose/ha/README.md:1-12</cite> 文档中实际出现的是 `podman-compose` 与 `podman exec` 命令，说明该 HA 资产使用 Podman Compose 体系，而非原生 Docker Compose。<cite>deploy/compose/ha/README.md:1-12</cite>

源码组件使用 Go 编写，需要本地具备 Go 工具链用于编译控制面与 Agent 二进制，例如 `cmd/custom-probe/main.go` 需要通过 `go build` 产出二进制。<cite>cmd/custom-probe/README.md:17-22</cite>

数据库方面存在迁移文件，需要 MySQL 客户端在初始化阶段导入 `db/schema.sql`。<cite>db/migrations/README.md:1-2</cite>

## 安装步骤（容器路径与本地路径二选一）

1. 克隆仓库并进入项目根目录，后续命令均在仓库根执行。
2. 使用 Make 安装仓库内声明的构建产物：

```bash
podman-compose
podman-compose up -d
go build -o bin/ccagent ./cmd/ccagent
go build -o bin/ccprobe-control ./cmd/ccprobe-control
go build -o bin/probe-agent ./cmd/probe-agent
podman exec mysql-db mysql -uroot -prootpassword probe_exporter < db/schema.sql
curl http://localhost:1900/health
make install（该目标执行 `go install`，不会安装配置文件）
curl http://localhost:1900/version
```

3. 编译控制面与 Agent 二进制到 `bin/` 目录：
<cite>cmd/custom-probe/README.md:17-22</cite>

```bash
podman-compose
podman-compose up -d
go build -o bin/ccagent ./cmd/ccagent
go build -o bin/ccprobe-control ./cmd/ccprobe-control
go build -o bin/probe-agent ./cmd/probe-agent
podman exec mysql-db mysql -uroot -prootpassword probe_exporter < db/schema.sql
curl http://localhost:1900/health
make install
curl http://localhost:1900/version
```

4. 如需在主机上独立编译 Custom Probe，使用对应入口：

```bash
podman-compose
podman-compose up -d
go build -o bin/ccagent ./cmd/ccagent
go build -o bin/ccprobe-control ./cmd/ccprobe-control
go build -o bin/probe-agent ./cmd/probe-agent
podman exec mysql-db mysql -uroot -prootpassword probe_exporter < db/schema.sql
curl http://localhost:1900/health
make install
curl http://localhost:1900/version
```

5. 在首次启动前导入数据库结构，MySQL 服务需已运行且库名 `probe_exporter` 已建：
<cite>README.md:69-70</cite>



6. 启动 HA 编排资产：



## 启动与验证

`podman-compose up -d` 启动后，控制面默认监听 `1900` 端口，可通过健康检查与版本接口确认服务存活：
<cite>QUICKSTART.md:1-2</cite>



两个端点均返回成功响应，说明 probe_exporter 控制面已就绪，可继续接入 Agent Pool。<cite>deploy/compose/ha/README.md:1-12</cite>

## 常见问题

- HA 资产的拓扑由 `deploy/compose/ha/` 下的 YAML 文件定义，包含 `ccagent-a.yaml`、`ccagent-b.yaml`、`agent-pool-a.yaml`、`agent-pool-b.yaml`，两套 Agent Pool 分别绑定到不同的控制实例，部署前需确认双控共享同一 MySQL DSN。<cite>deploy/compose/ha/README.md:1-12</cite>
- HA 资产使用 `podman-compose` 而非 `docker compose`，混用 CLI 会导致编排文件不被识别。<cite>deploy/compose/ha/README.md:1-12</cite>
- 数据库初始化脚本 `db/schema.sql` 必须先于控制面与 Agent 首次启动导入，否则服务在连接建表失败时会直接退出。<cite>db/migrations/README.md:1-2</cite>
- `cmd/custom-probe/` 的 README 仅给出源码编译方式，未声明二进制产物路径，安装时需自行确认 `bin/custom-probe` 是否被上游调用方加载。<cite>cmd/custom-probe/README.md:17-22</cite>

## 目录

1. 这是什么
2. 环境要求
3. 安装步骤
4. 启动与验证
5. 常见问题

安装与启动步骤以仓库入口文档为准。 <cite>README.md:75-75</cite>
