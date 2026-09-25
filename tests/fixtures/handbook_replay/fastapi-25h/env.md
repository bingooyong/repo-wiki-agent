# 环境配置

## 这是什么

## 环境要求

CI 在 `ubuntu-18.04` 上以 `python-version: [3.9]` 矩阵执行测试，并使用 `postgres:11.5-alpine` 作为服务依赖<cite>.github/workflows/conduit.yml:12-68</cite><cite>.github/workflows/tests.yml:12-70</cite>，因此本地推荐使用 Python 3.9 与 PostgreSQL 11.5。仓库以 Poetry 管理依赖，依赖 PostgreSQL 提供 `DATABASE_URL`<cite>docker-compose.yml:3-22</cite><cite>README.rst:74-115</cite>，并通过 Docker Compose 同时编排应用与数据库容器。

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

在容器启动后，也可选择本地以 Poetry 方式运行，便于开发期热重载：

如使用 Docker Compose 整体启动，可执行：

完成后，通过 `http://localhost:8000` 访问应用根路径即可确认服务已正常响应；数据库侧可使用 `pg_isready` 或 `psql` 连接 `db:5432` 进行健康检查，这与 CI 中 PostgreSQL 服务的健康探测方式一致<cite>.github/workflows/conduit.yml:12-68</cite>。测试可通过 `DATABASE_URL` 环境变量或 `app/core/settings/app.py` 中的 `database_url` 配置数据库连接<cite>README.rst:74-115</cite>。

## 常见问题

- **数据库连接失败**：请确认 `DATABASE_URL` 与 `db` 服务的主机名、端口一致，Compose 默认使用 `postgresql://postgres:postgres@db/postgres`<cite>docker-compose.yml:3-22</cite>。
- **迁移未执行**：若接口访问出现表缺失错误，需重新执行 `alembic upgrade head`。
- **测试环境数据库**：运行测试前需设置 `DATABASE_URL`，或在 `app/core/settings/app.py` 中配置 `database_url`<cite>README.rst:74-115</cite>。
- **Python 版本不匹配**：CI 仅验证 Python 3.9，使用其他版本可能出现依赖或语法差异<cite>.github/workflows/conduit.yml:12-68</cite>。

## 目录

1. 这是什么
2. 环境要求
3. 安装步骤
4. 启动与验证
5. 常见问题
