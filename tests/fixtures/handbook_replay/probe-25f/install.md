# 安装指南

## 这是什么

probe_exporter 是面向企业级的服务探针拨测与结果导出平台。它支持**双模式探测**（Blackbox + Custom Probe），通过灵活的验证引擎与多渠道导出能力完成探测结果的采集与分发，并提供完整的 Web 管理界面，方便在生产环境中对可用性与拨测结果进行集中管控。本安装指南面向初次接触该仓库的工程师，按页面步骤执行后即可获得一份本地可运行的实例，并具备基础健康检查手段。

## 环境要求

- 容器与编排：使用 `podman-compose` 启动依赖的数据库与编排文件，仓库根目录存在 `docker-compose.ha.yml` 等 compose 资源用于 HA 部署 `<cite>deploy/compose/ha/README.md:1-12</cite>`。
- 语言与构建：自定义探针使用 Go 编译，命令为 `go build -o bin/custom-probe cmd/custom-probe/main.go` `<cite>cmd/custom-probe/README.md:17-22</cite>`。
- 数据库：初始化阶段使用 `mysql < db/schema.sql` 完成结构导入，对应仓库根目录的迁移说明 `<cite>db/migrations/README.md:1-2</cite>`。
- 快速开始入口：仓库根目录 README 顶部即给出 `## 🚀 快速开始` 章节，本页与之保持一致 `<cite>README.md:69-70</cite>`，并与独立的快速启动指南呼应 `<cite>QUICKSTART.md:1-2</cite>`。

## 安装步骤

1. 拉起容器化依赖。在仓库根目录执行编排命令，启动 MySQL 等基础组件：

   ```bash
   podman-compose up -d
   ```

   该命令与 `deploy/compose/ha/README.md` 中描述的 compose 资源配合使用，后者由仓库根 `docker-compose.ha.yml` 引用 `<cite>deploy/compose/ha/README.md:1-12</cite>`。

2. 初始化数据库结构。优先在宿主机通过管道导入 `db/schema.sql`：
<cite>cmd/custom-probe/README.md:17-22</cite>

   ```bash
   mysql < db/schema.sql
   ```

   若本地未装 `mysql` 客户端，可改为进入容器执行，库名固定为 `probe_exporter`，账号为 `root / rootpassword`：
<cite>README.md:69-70</cite>

   ```bash
   podman exec -i mysql-db mysql -uroot -prootpassword probe_exporter < db/schema.sql
   ```

   或在容器内以交互方式导入：

   ```bash
   podman exec mysql-db mysql -uroot -prootpassword probe_exporter < db/schema.sql
   ```

   以上方式与 `db/migrations/README.md` 描述的迁移说明保持一致 `<cite>db/migrations/README.md:1-2</cite>`。

3. 编译控制面与执行面二进制。按需构建以下组件，输出统一落到 `./bin/`：
<cite>QUICKSTART.md:1-2</cite>

   ```bash
   go build -o bin/ccagent ./cmd/ccagent
   go build -o bin/ccprobe-control ./cmd/ccprobe-control
   go build -o bin/probe-agent ./cmd/probe-agent
   ```

   自定义探针模块单独编译，与 `cmd/custom-probe/README.md` 描述一致 `<cite>cmd/custom-probe/README.md:17-22</cite>`。

4. 安装运行时模板与配置。仓库提供 `make install` 目标用于安装默认配置，使用方式与根 README 的快速开始一致 `<cite>README.md:69-70</cite>`：

   ```bash
   make install
   ```

## 启动与验证

按根 README 的快速开始章节流程启动控制面进程 `<cite>README.md:69-70</cite>`：

```bash
./bin/ccagent
```

服务暴露本地 HTTP 端口，使用健康检查路径确认进程已进入就绪状态：

```bash
curl http://localhost:1900/health
```

预期返回 2xx 表示控制面已正常接收请求，可继续接入 Web 管理界面与探针执行面。

## 常见问题

- 数据库账号与库名不匹配：`db/schema.sql` 导入时使用的固定账号为 `root / rootpassword`，库名为 `probe_exporter`，任一不一致都会导致导入失败，相关命令见 `db/migrations/README.md` `<cite>db/migrations/README.md:1-2</cite>`。
- 容器编排方式选择：本地开发通常直接使用 `podman-compose`；若要切换为仓库根 `docker-compose.ha.yml` 的 HA 部署，需要先阅读 `deploy/compose/ha/README.md` 中关于双 ccagent、双 agent pool 与可选 Caddy LB 的拓扑说明 `<cite>deploy/compose/ha/README.md:1-12</cite>`。
- 自定义探针构建：自定义探针是独立二进制，必须按 `cmd/custom-probe/README.md` 中的命令单独编译，不要与控制面共用同一个构建命令 `<cite>cmd/custom-probe/README.md:17-22</cite>`。

## 目录

1. 这是什么
2. 环境要求
3. 安装步骤
4. 启动与验证
5. 常见问题

安装与启动步骤以仓库入口文档为准。 <cite>README.md:71-71</cite>
