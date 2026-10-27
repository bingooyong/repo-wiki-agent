# 安装指南

## 这是什么

本仓库是 `fastapi-realworld-example-app`，是一个面向 Conduit/RealWorld API 规范 的 FastAPI 参考实现（用 sqlalchemy/fastapi-realworld-example-app，识别为官方 RealWorld 后端参考示例 的副本）。其设计目的是完整通过 Conduit 测试套件，而不是作为持续维护的产品；仓库维护者明确表示该示例已完成其首要目标，因此不再主动迭代 <cite>README.rst:1-3</cite>。读者按本页完成安装与启动后，应当得到一个本地可访问的 RealWorld 后端 API 实例，路由可通过 `/docs`（Swagger）和 `/redoc` 查看 <cite>README.rst:129-134</cite>。

## 环境要求

根据 `README.rst`，运行本项目需要准备 PostgreSQL 作为数据库，可使用 Docker 启动；测试与运行需要使用 `pytest`；部署章节还需要 `docker` 与 `docker-compose` 工具 <cite>README.rst:32-73</cite><cite>README.rst:74-115</cite><cite>README.rst:116-128</cite>。除此之外，项目使用 Poetry 管理依赖（见安装步骤中的 `poetry install`），并通过 `alembic` 进行数据库迁移。文档未对 Python 版本做强制要求，证据中也未出现具体 Python 版本号，因此此处不予补充。

## 安装步骤

1. 启动 PostgreSQL。`README.rst` 给出的是基于 Docker 的方式：在 shell 中先导出 `POSTGRES_DB`、`POSTGRES_PORT`、`POSTGRES_USER`、`POSTGRES_PASSWORD` 环境变量，再以 `docker run` 启动容器 <cite>README.rst:32-73</cite>。示例命令如下：

```bash
export POSTGRES_DB=rwdb
export POSTGRES_PORT=5432
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres
docker run --name pgdb --rm -e POSTGRES_USER="$POSTGRES_USER" -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" -e POSTGRES_DB="$POSTGRES_DB" -p "$POSTGRES_PORT":5432 -d postgres
```

2. 在 `app/core/settings/test.py` 中配置 `database_url`，或设置 `DATABASE_URL` 环境变量，使应用能够连到步骤 1 中的数据库 <cite>README.rst:74-115</cite>。

3. 使用 Poetry 安装 Python 依赖：

```bash
poetry install
```

4. 执行数据库迁移，初始化 schema：

```bash
alembic upgrade head
```

5. （可选）若采用 Docker 部署方式，则需要 `docker` 与 `docker-compose`，并先按 `Quickstart` 创建 `.env` 文件或修改 `.env.example`；其中 `POSTGRES_HOST` 必须为 `db` 或同步修改 `docker-compose.yml` <cite>README.rst:116-128</cite>。

## 启动与验证

开发模式下使用 `uvicorn` 启动 FastAPI 应用：
<cite>README.rst:32-73</cite>

```bash
uvicorn app.main:app --reload
```

若使用 Docker Compose，则分别拉起应用与数据库服务：

```bash
docker-compose up -d app
docker-compose up -d db
```

服务启动后，可访问 `http://localhost:8000/docs`（Swagger）或 `http://localhost:8000/redoc`（ReDoc）查看并验证所有 Web 路由是否注册成功 <cite>README.rst:129-134</cite>。

## 常见问题

- **数据库连接失败**：常见原因是 `DATABASE_URL` 环境变量未设置，或 `app/core/settings/test.py` 中的 `database_url` 未正确指向步骤 1 中的 PostgreSQL <cite>README.rst:74-115</cite>。
- **Docker 部署下连不上数据库**：`POSTGRES_HOST` 必须为 `db`，否则需要同步修改 `docker-compose.yml`，否则容器内应用无法解析数据库主机 <cite>README.rst:116-128</cite>。
- **`.env` 缺失或字段不全**：Docker 部署要求先按 `Quickstart` 创建 `.env`，或参考 `.env.example` 修改，否则 `docker-compose up` 时变量为空 <cite>README.rst:116-128</cite>。
- **测试运行前未配置连接**：`README.rst` 强调跑 `tests/` 下的用例前必须设置 `DATABASE_URL` 或 `app/core/settings/test.py` 中的 `database_url`，否则 `pytest` 会因数据库不可用而失败 <cite>README.rst:74-115</cite>。

## 目录

1. 这是什么
2. 环境要求
3. 安装步骤
4. 启动与验证
5. 常见问题
