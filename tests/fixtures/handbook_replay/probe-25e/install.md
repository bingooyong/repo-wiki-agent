# 安装指南

## 这是什么

probe_exporter 是面向企业级的服务探针拨测与结果导出平台。它支持 **双模式探测**（Blackbox + Custom Probe）、灵活的验证引擎、多渠道导出，并提供完整的 Web 管理界面。本安装页面向需要在本地或容器环境完成首次部署的读者，按照本页步骤完成后即可获得一个可对外提供探测与导出能力的最小运行实例 <cite>README.md:69-70</cite>。

## 环境要求

probe_exporter 的快速启动依赖 Go 语言构建链路、容器运行时以及 MySQL 实例。Go 模块用于编译 `ccagent`、`ccprobe-control`、`probe-agent` 与 `custom-probe` 等二进制；容器侧需要 `podman-compose` 拉起数据库与控制面；后端存储要求一个可执行 `db/schema.sql` 的 MySQL 实例，且默认数据库名为 `probe_exporter`，root 账户口令默认为 `rootpassword`（与 `docker-compose.ha.yml` 中的约定一致） <cite>deploy/compose/ha/README.md:1-12</cite>。

## 安装步骤

1. **准备数据库 Schema**：将仓库提供的建表脚本导入 MySQL。脚本由 `db/schema.sql` 提供，可直接通过 `mysql` 客户端或 `podman exec` 注入 MySQL 容器 <cite>db/migrations/README.md:1-2</cite>。

   ```bash
   podman exec -i mysql-db mysql -uroot -prootpassword probe_exporter < db/schema.sql
   ```

   也可在宿主机上以等价的 `mysql < db/schema.sql` 形式完成导入。
<cite>README.md:69-70</cite>

2. **编译主控制面二进制 `ccagent`**：使用 Go 工具链构建仓库根目录下的 `cmd/ccagent`，产物输出到 `./bin/ccagent` <cite>QUICKSTART.md:1-2</cite>。

   ```bash
   go build -o bin/ccagent ./cmd/ccagent/main.go
   ```

3. **编译探测 Agent 二进制 `probe-agent`**：将控制面与执行探针分离部署时使用，产物位于 `./bin/probe-agent` <cite>QUICKSTART.md:1-2</cite>。

   ```bash
   go build -o bin/probe-agent ./cmd/probe-agent/main.go
   ```

4. **编译探测控制服务 `ccprobe-control`**：用于 Web 管理界面与导出能力的控制服务组件 <cite>QUICKSTART.md:1-2</cite>。

   ```bash
   go build -o bin/ccprobe-control ./cmd/ccprobe-control/main.go
   ```

5. **编译 Custom Probe 入口（可选）**：若启用自定义探针模式，需额外编译 `cmd/custom-probe` 下的入口，产物输出到 `bin/custom-probe` <cite>cmd/custom-probe/README.md:17-22</cite>。

   ```bash
   go build -o bin/custom-probe cmd/custom-probe/main.go
   ```

6. **安装依赖与运行入口（可选 Make 目标）**：仓库根 `Makefile` 提供 `make install` 目标，可作为一键安装入口 <cite>QUICKSTART.md:1-2</cite>。

   ```bash
   make install
   ```

## 启动与验证

通过容器编排启动完整的控制面与依赖栈，仓库根的 `docker-compose.ha.yml` 与 `deploy/compose/ha/` 下的 HA 资源已经为这套流程预置好基础配置 <cite>deploy/compose/ha/README.md:1-12</cite>。

```bash
podman-compose up -d
```

数据库 Schema 在启动前或启动后立即导入均可，建议在容器起来后第一时间注入：

```bash
podman exec mysql-db mysql -uroot -prootpassword probe_exporter < db/schema.sql
```

主控制面进程以前台/后台方式启动：

```bash
./bin/ccagent
```

验证探针控制服务已对外暴露健康检查端点，本地监听 `8000` 端口：
<cite>QUICKSTART.md:1-2</cite>

```bash
curl http://localhost:8000/health
```

## 常见问题

- **数据库连接失败**：默认 DSN 假设数据库名为 `probe_exporter`、root 口令 `rootpassword`。若 HA compose 中 `ccagent-a.yaml` / `ccagent-b.yaml` 使用了不同账号或端口，需同步修改对应 YAML 的 MySQL DSN，否则双控实例无法接入同一库 <cite>deploy/compose/ha/README.md:1-12</cite>。
- **Schema 未导入导致接口报错**：若未先执行 `db/schema.sql`，`/health` 可能返回异常或表不存在错误，可按启动与验证一节中的 `podman exec ... < db/schema.sql` 命令补救 <cite>db/migrations/README.md:1-2</cite>。
- **找不到二进制路径**：所有编译产物统一输出到仓库根的 `./bin/` 目录（如 `bin/ccagent`、`bin/probe-agent`、`bin/ccprobe-control`、`bin/custom-probe`），请确认运行目录位于仓库根 <cite>QUICKSTART.md:1-2</cite> <cite>cmd/custom-probe/README.md:17-22</cite>。
- **双控制实例配置漂移**：`agent-pool-a.yaml` 与 `agent-pool-b.yaml` 必须分别 pinned 到各自的控制实例，混用会导致探测调度错位，这是 Phase 7 HA compose 资产隐含的约束 <cite>deploy/compose/ha/README.md:1-12</cite>。

## 目录

1. 这是什么
2. 环境要求
3. 安装步骤
4. 启动与验证
5. 常见问题
