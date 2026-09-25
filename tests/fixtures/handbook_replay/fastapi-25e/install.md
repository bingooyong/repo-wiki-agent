# 安装指南

## 这是什么

本仓库 `fastapi-realworld-example-app` 是一个示例性质的 FastAPI 项目骨架，核心目标是通过 Conduit 测试套件，因此**仓库已不再积极维护**（作者认为该示例已足够完整地达成其首要目标），更现代、更贴近实战的示例可前往其他项目获取<cite>README.rst:1-3</cite>。读者按本页面操作完成后，将得到一个可在本机或 Docker 环境中通过 PostgreSQL 启动的 FastAPI 应用，并可访问 `/docs` 或 `/redoc` 查看 Swagger/ReDoc 形式的 Web 路由<cite>README.rst:129-134</cite>。

## 环境要求

仓库文档未明确给出 Python 语言版本下限或包管理器（如 Poetry/pip-tools）的硬性要求，但要求快速开始前必须先运行 PostgreSQL，并设置一组与数据库相关的环境变量<cite>README.rst:32-73</cite>。如使用 Docker 部署，则本机需要预先安装 `docker` 与 `docker-compose` 两个工具<cite>README.rst:116-128</cite>。运行测试时除了数据库外，还需要安装 `pytest`，因为项目以 `pytest` 来定义测试用例<cite>README.rst:74-115</cite>。

## 安装步骤

1. 启动 PostgreSQL，并通过 `export` 设置 `POSTGRES_DB`、`POSTGRES_PORT`、`POSTGRES_USER`、`POSTGRES_PASSWORD` 等环境变量，然后使用与上述变量同名的 `-e` 参数启动容器，使数据库名、端口和账号与后续应用配置一致<cite>README.rst:32-73</cite>：

```bash
export POSTGRES_DB=rwdb
export POSTGRES_PORT=5432
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres
docker run --name pgdb --rm \
  -e POSTGRES_USER="$POSTGRES_USER" \
  -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  -e POSTGRES_DB="$POSTGRES_DB" \
  -p "$POSTGRES_PORT":5432 \
  -d postgres
```

2. 在项目根目录创建 `.env` 文件（可参考 `Quickstart` 段或直接修改 `.env.example`），并按照应用期望的方式填入上述数据库变量<cite>README.rst:116-128</cite>。

3. 使用 Docker Compose 启动应用栈；由于容器之间通过服务名访问数据库，`POSTGRES_HOST` 必须指定为 `db`（或同步修改 `docker-compose.yml` 中对应的服务名）<cite>README.rst:116-128</cite>：

```bash
docker-compose up --build
```

4. （可选）若要运行测试，请先设置 `DATABASE_URL` 环境变量，或在 `app/core/settings/test.py` 中配置 `database_url`，然后在 `tests/` 目录下使用 `pytest` 触发测试<cite>README.rst:74-115</cite>：

```bash
pytest
```

## 启动与验证

应用启动成功后，所有 Web 路由可通过 `GET /docs` 或 `GET /redoc` 获取，前者呈现 Swagger UI，后者呈现 ReDoc 文档<cite>README.rst:129-134</cite>。在浏览器中打开其中任一路径并能正常渲染路由列表，即可确认服务已正常起来。

## 常见问题

- **数据库连不上**：在 Docker 部署方式下，应用容器访问 PostgreSQL 时 `POSTGRES_HOST` 必须写成 `db`，否则会找不到主机；如修改了 `docker-compose.yml` 中的服务名，也需同步修改该变量<cite>README.rst:116-128</cite>。
- **测试无法运行**：执行 `pytest` 前若未设置 `DATABASE_URL`，需在 `app/core/settings/test.py` 中显式配置 `database_url`，否则测试用数据库连接无法建立<cite>README.rst:74-115</cite>。
- **环境变量缺失**：快速开始和 Docker 部署都依赖 `.env` 文件（参考 `Quickstart` 或 `.env.example`），缺省会导致 PostgreSQL 容器或应用启动失败<cite>README.rst:32-73</cite>。

## 目录

1. 这是什么
2. 环境要求
3. 安装步骤
4. 启动与验证
5. 常见问题
