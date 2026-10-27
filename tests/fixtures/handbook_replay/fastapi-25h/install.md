# 安装指南

## 这是什么

按照本指南，你将在本地完成 PostgreSQL 依赖、Python 依赖与数据库迁移，并启动一个可在浏览器访问 `/docs`（Swagger）或 `/redoc`（ReDoc）查看路由的 FastAPI 示例应用 <cite>README.rst:129-134</cite>。

## 环境要求

- **Python 包管理与依赖**：项目使用 Poetry 进行依赖管理，安装步骤中通过 `poetry install` 引入依赖 <cite>README.rst:135-157</cite>。
- **数据库**：依赖 PostgreSQL；Quickstart 段落示例中以 Docker 方式启动一个名为 `pgdb` 的容器，并使用 `POSTGRES_DB=rwdb`、`POSTGRES_PORT=5432` 等环境变量进行配置 <cite>README.rst:32-73</cite>。
- **容器化部署（可选）**：Deployment with Docker 段落要求本地已安装 `docker` 与 `docker-compose` 工具 <cite>README.rst:116-128</cite>。
- **数据库迁移工具**：使用 Alembic 执行迁移，运行命令为 `alembic upgrade head` <cite>README.rst:135-157</cite>。

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

完成依赖与迁移后，使用 Uvicorn 启动应用，并开启自动重载 <cite>README.rst:135-157</cite>：

服务启动后，可在浏览器打开 `/docs` 查看 Swagger 路由，或打开 `/redoc` 查看 ReDoc 路由文档 <cite>README.rst:129-134</cite>。

如果你使用项目自带的 Docker Compose 进行部署，则需要 `docker-compose`，并分别启动应用与数据库两个服务 <cite>README.rst:116-128</cite>：

## 常见问题

- **部署时数据库连不上**：在 Docker 部署场景下，`POSTGRES_HOST` 必须设置为 `db`（即 docker-compose 中的服务名），或在 `docker-compose.yml` 中相应修改 <cite>README.rst:116-128</cite>。
- **测试运行前缺少数据库连接**：必须在运行测试前设置环境变量 `DATABASE_URL`，或在 `app/core/settings/app.py` 中配置 `database_url`，否则 pytest 启动会因连接信息缺失而失败 <cite>README.rst:74-115</cite>。
- **环境变量未持久化**：如果修改了 `.env.example` 而未生成 `.env`，应用启动后可能读取不到所需的 Postgres 配置；需要按 Quickstart 一节准备一份 `.env` 文件 <cite>README.rst:116-128</cite>。

## 目录

1. 这是什么
2. 环境要求
3. 安装步骤
4. 启动与验证
5. 常见问题
