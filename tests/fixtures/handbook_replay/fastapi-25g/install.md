# 安装指南

## 这是什么

## 环境要求

项目以 Python 应用形式组织，源码位于 `app/` 目录，并通过 `docker-compose` 与 PostgreSQL 协作 <cite>README.rst:116-128</cite><cite>README.rst:135-157</cite>。本地开发需要 Python 运行环境与 Poetry 包管理器，用于执行 `poetry install` 与 `poetry run uvicorn app.main:app --reload` 等命令。Docker 方式部署则要求本机已安装 `docker` 与 `docker-compose` 工具 <cite>README.rst:116-128</cite>。测试环节依赖 `DATABASE_URL` 环境变量或 `app/core/settings/app.py` 中的 `database_url` 配置 <cite>README.rst:74-115</cite>。

## 安装步骤

1. 启动 PostgreSQL，并通过环境变量指定数据库名、端口、用户名与密码，例如使用 `docker` 运行一次性容器 <cite>README.rst:32-73</cite>：

```bash
export POSTGRES_DB=rwdb
export POSTGRES_PORT=5432
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres
docker run --name pgdb --rm -e POSTGRES_USER="$POSTGRES_USER" -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" -e POSTGRES_DB="$POSTGRES_DB" -p "$POSTGRES_PORT":5432 -d postgres
```

2. 使用 Poetry 安装项目依赖 <cite>README.rst:116-128</cite>：

```bash
poetry install
```

3. 执行数据库迁移，使表结构到位：

```bash
alembic upgrade head
```

4. （可选）复制 `.env.example` 为 `.env`，并按 Quickstart 中的变量补齐；若使用 Docker 部署，需将 `POSTGRES_HOST` 设为 `db` 或同步修改 `docker-compose.yml` <cite>README.rst:116-128</cite>。

## 启动与验证

开发模式下可直接通过 Poetry 启动 Uvicorn，并启用热重载 <cite>README.rst:116-128</cite>：

```bash
poetry run uvicorn app.main:app --reload
```

Docker 方式则可以分别拉起应用与数据库两个服务 <cite>README.rst:116-128</cite>：

```bash
docker-compose up -d app
docker-compose up -d db
```

服务起来后，可访问 `/docs` 或 `/redoc` 查看 Swagger 或 ReDoc 形式的全部 Web 路由，确认应用已正常响应 <cite>README.rst:129-134</cite>。

## 常见问题

- **数据库连接配置缺失**：运行测试前必须设置 `DATABASE_URL` 环境变量，或在 `app/core/settings/app.py` 中维护 `database_url`，否则测试无法连接 PostgreSQL <cite>README.rst:74-115</cite>。
- **Docker 部署中的主机名**：使用 `docker-compose` 部署时，`POSTGRES_HOST` 必须为 `db`，否则应用容器无法解析到 PostgreSQL 服务 <cite>README.rst:116-128</cite>。
- **环境变量未生效**：Quickstart 中导出的 `POSTGRES_DB`、`POSTGRES_PORT`、`POSTGRES_USER`、`POSTGRES_PASSWORD` 同时被 `docker run` 命令引用，遗漏任意一项都会导致容器启动失败或应用连接错误 <cite>README.rst:32-73</cite>。

## 目录

1. 这是什么
2. 环境要求
3. 安装步骤
4. 启动与验证
5. 常见问题

本地路径用 `poetry install` 后进入 `poetry shell`，或直接 `poetry run`；先启动数据库，再 `alembic upgrade head`，最后 `poetry run uvicorn app.main:app --reload`。
<cite>README.rst:32-73</cite>
