# 安装指南

## 这是什么

probe_exporter 是面向企业级的服务探针拨测与结果导出平台。它支持**双模式探测**（Blackbox + Custom Probe）、灵活的验证引擎、多渠道导出，并提供完整的 Web 管理界面 <cite>README.md:69-70</cite>。按照本指南完成安装与启动后，读者将在本机获得一个可用的 probe_exporter 实例，并能够通过健康检查端点确认服务存活 。

## 环境要求

本节只列出仓库文档中直接出现的运行时与依赖。custom-probe 子模块使用 Go 构建，因此需要本机安装 Go 工具链 <cite>cmd/custom-probe/README.md:17-22</cite>。容器化部署路径使用 `podman-compose` 作为编排工具，依赖 Podman 与 Compose 扩展 <cite>deploy/compose/ha/README.md:1-12</cite>。数据库使用 MySQL，初始化脚本通过容器内 `mysql` 客户端导入到 `probe_exporter` 数据库中 。

## 安装步骤

容器路径与本地路径二选一。

### 路径 A：容器编排

1. 启动编排服务。 <cite>README.md:75-75</cite>

```bash
podman-compose up -d
```

2. 导入一次数据库结构。 <cite>README.md:78-78</cite>

```bash
# 容器路径：导入一次结构
podman exec mysql-db mysql -uroot -prootpassword probe_exporter < db/schema.sql
```

3. 用源码监听端口检查健康状态。 <cite>README.md:109-109</cite>

```bash
curl http://localhost:1900/health
```

### 路径 B：本地编译

1. 先启动数据库，再导入结构。 <cite>README.md:78-78</cite>

```bash
# 本地路径：导入结构
podman exec mysql-db mysql -uroot -prootpassword probe_exporter < db/schema.sql
```

2. 编译主 REST/Web 服务。 <cite>README.md:101-101</cite>

```bash
go build -o bin/ccagent ./cmd/ccagent
```

3. 启动本地进程并检查健康状态。 <cite>README.md:102-102</cite> <cite>README.md:109-109</cite>

```bash
./bin/ccagent
curl http://localhost:1900/health
```

## 目录

1. 这是什么
2. 环境要求
3. 安装步骤
