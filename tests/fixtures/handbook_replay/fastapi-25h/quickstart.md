# 快速开始

## 这是什么

本仓库是 FastAPI 实现 RealWorld 示例应用（Conduit 测试套件）的参考工程，目标读者是想把 FastAPI 落地为一个完整 REST 后端并通过 RealWorld/Conduit 一致性测试的开发者。完成本页步骤后，你将得到一个跑在本地、可通过 `/docs` 与 `/redoc` 暴露路由、并能在 Docker 环境中完成数据库迁移与运行测试的 FastAPI 项目骨架。<cite>README.rst:129-134</cite>

## 环境要求

仓库文档对运行环境的硬性依赖集中在 PostgreSQL 与 Python 包管理两个层面。PostgreSQL 用于提供 RealWorld 业务数据持久化，推荐通过 Docker 启动，端口为 `5432`，默认数据库/用户/口令为 `rwdb / postgres / postgres`。<cite>README.rst:32-73</cite>

Python 依赖通过 Poetry 管理（`pyproject.toml` 与 `poetry.lock`），应用入口为 `app.main:app`，由 `uvicorn` 提供 ASGI 服务。测试与部署章节额外要求 `pytest`、`docker` 与 `docker-compose` 工具链存在。<cite>README.rst:74-157</cite>

## 安装步骤

容器路径与本地路径二选一。

### 路径 A：本地开发

1. 创建 `.env`（alembic `env.py` 会加载应用设置，必须先有 APP_ENV、DATABASE_URL、SECRET_KEY）。 <cite>README.rst:52-52</cite>

```bash
touch .env
echo APP_ENV=dev >> .env
echo DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/rwdb >> .env
echo SECRET_KEY=change-me >> .env
```

2. 先启动 PostgreSQL。 <cite>README.rst:38-38</cite>

```bash
docker run --name pgdb --rm -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=rwdb -p 5432:5432 postgres
```

3. 安装依赖。 <cite>README.rst:46-46</cite>

```bash
poetry install
```

4. 迁移数据库。 <cite>README.rst:58-58</cite>

```bash
poetry run alembic upgrade head
```

5. 启动应用。 <cite>README.rst:59-59</cite>

```bash
poetry run uvicorn app.main:app --reload
```

### 路径 B：Compose

先启动数据库服务，再启动应用服务。 <cite>README.rst:124-124</cite> <cite>README.rst:125-125</cite>

```bash
docker-compose up -d db
docker-compose up -d app
```

## 启动与验证

本地开发以 `uvicorn` 热重载方式启动 `app.main:app`，命令如下：
<cite>README.rst:32-73</cite>

<cite>README.rst:74-115</cite>

服务启动后，所有路由会在 Swagger UI（`/docs`）与 ReDoc（`/redoc`）上自动暴露，这是仓库给出的“服务已就绪”确认方式。<cite>README.rst:129-134</cite>

## 常见问题

- 数据库连不上：未设置 `DATABASE_URL` 时，`alembic upgrade head` 与 `uvicorn` 都会失败，需显式导出或在 `app/core/settings/app.py` 里指定 `database_url`。<cite>README.rst:74-115</cite>
- Docker 部署下 Postgres 连不通：`POSTGRES_HOST` 必须写成 `db`（即 `docker-compose.yml` 中 db 服务的服务名），否则应用容器无法解析到数据库容器。<cite>README.rst:116-128</cite>
- 测试无法运行：本项目测试定义在 `tests/` 目录，使用 `pytest` 运行，需先确保 `DATABASE_URL` 已正确指向测试库。<cite>README.rst:74-115</cite>
- 想确认接口是否完整：直接打开 `/docs` 或 `/redoc`，README 明确说明全部路由都通过这两个路径以 Swagger 或 ReDoc 形式提供。<cite>README.rst:129-134</cite>

## 目录

1. 这是什么
2. 环境要求
3. 安装步骤
4. 启动与验证
5. 常见问题
