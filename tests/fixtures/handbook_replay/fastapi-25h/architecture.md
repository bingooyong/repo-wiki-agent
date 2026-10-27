# 架构设计

## 简介

本仓库 `fastapi-realworld-example-app` 是一个面向 RealWorld / Conduit 测试套件的 FastAPI 参考实现：自述指出该例程已“相当完备”，通过 Conduit 测试集是其主要目标，因此不再积极维护，更现代的实践请参考其他示例 。本页围绕 `api`、`core`、`db`、`models` 四个相关模块展开，说明 HTTP 层如何装配仓储依赖、如何通过设置对象注入配置，以及数据库会话如何在请求作用域内提供，从而帮助读者把握该 FastAPI 例程的运行时边界。
<cite>app/api/routes/authentication.py:23-26</cite>

## 项目结构

应用以 `app.main` 作为入口，组织上划分为四类：HTTP 路由模块 `app.api.routes`、领域模型 `app.models`、仓储层 `app.db.repositories` 与基础设施配置 `app.core`。`app.api.routes` 下按业务域拆分，每条路由都接收带类型的仓储依赖（通过 `Depends(get_repository(...))` 注入），例如 `authentication.py`、`comments.py`、`profiles.py`、`tags.py`、`users.py` 各自对应认证、文章评论、用户档案、标签与用户资源 <cite>app/api/routes/authentication.py:23-26</cite><cite>app/api/routes/comments.py:31-34</cite><cite>app/api/routes/profiles.py:21-22</cite><cite>app/api/routes/tags.py:11-12</cite><cite>app/api/routes/users.py:19-21</cite>。`app.models` 描述 SQLAlchemy 实体，`app.core` 则集中提供配置与安全等横切能力。

## 核心组件

`app.api.routes.authentication.login`：登录端点，使用嵌入式的 `user` Body 入参，并把 `UsersRepository` 与 `AppSettings` 注入到调用栈 <cite>app/api/routes/authentication.py:23-26</cite>。 `app.api.routes.comments.list_comments_for_article`：先经 `Depends(get_article_by_slug_from_path)` 解析路径中的文章，再按需注入当前用户，最后通过 `CommentsRepository` 列出评论 <cite>app/api/routes/comments.py:31-34</cite>。 `app.api.routes.profiles.retrieve_profile_by_username`：依赖 `get_profile_by_username_from_path` 取得 `Profile`，再交由服务层继续处理 <cite>app/api/routes/profiles.py:21-22</cite>。 `app.api.routes.tags.get_all_tags`：通过 `TagsRepository` 提供标签列表 <cite>app/api/routes/tags.py:11-12</cite>。 `app.api.routes.users.retrieve_current_user`：经过认证解析器 `get_current_user_authorizer()` 暴露当前会话用户，并附带 `AppSettings` <cite>app/api/routes/users.py:19-21</cite>。

## 详细分析

从公共路由的签名可见，HTTP 层把基础设施全部委托给了 FastAPI 的依赖注入：`get_repository(...)` 在每次请求时实例化对应的仓储，认证则统一由 `get_current_user_authorizer(required: bool)` 处理，可选布尔参数控制是否强制登录 <cite>app/api/routes/comments.py:31-34</cite><cite>app/api/routes/users.py:19-21</cite>。登录接口以 `Body(..., embed=True, alias="user")` 形式接收认证字段，使请求体结构与 Conduit 测试用例保持一致 <cite>app/api/routes/authentication.py:23-26</cite>。配置则集中在 `AppSettings`，通过 `Depends(get_app_settings)` 按需获取，避免路由直接读取全局状态 <cite>app/api/routes/authentication.py:23-26</cite><cite>app/api/routes/users.py:19-21</cite>。路径解析方面，`comments` 与 `profiles` 路由都在业务处理前先做实体解析（文章、档案），形成“路径参数 → 实体 → 仓储”的链式调用 <cite>app/api/routes/comments.py:31-34</cite><cite>app/api/routes/profiles.py:21-22</cite>。

## 依赖关系分析

路由层完全依赖下游三类能力：仓储（`UsersRepository`、`CommentsRepository`、`TagsRepository`）、实体解析（`get_article_by_slug_from_path`、`get_profile_by_username_from_path`）以及认证（`get_current_user_authorizer`），并通过 `get_repository`、`get_app_settings` 这类工厂函数解耦具体实现 <cite>app/api/routes/authentication.py:23-26</cite><cite>app/api/routes/comments.py:31-34</cite><cite>app/api/routes/profiles.py:21-22</cite>。`Tags` 路由只声明仓储依赖，是依赖图中最薄的一支 <cite>app/api/routes/tags.py:11-12</cite>。对实例代码而言，任何对 `AppSettings` 字段或仓储签名的修改都会直接影响所有相关路由。

## 性能考虑

每条路由都通过 `Depends(get_repository(...))` 获取仓储，若该工厂每次都新建数据库会话，请求量上升时会增加连接开销；同一条评论列表接口在一次调用内既解析文章实体又列出评论，存在多次往返数据库的可能 <cite>app/api/routes/comments.py:31-34</cite>。`tags` 接口返回全量标签，规模较小时可忽略，但若标签增长，应考虑缓存或分页 <cite>app/api/routes/tags.py:11-12</cite>。嵌入式 Body 加上别名映射，序列化层虽轻，仍需在 Pydantic 模型版本升级时留意字段一致性 <cite>app/api/routes/authentication.py:23-26</cite>。

## 故障排查指南

登录失败或 Body 解析异常：检查 `login` 的 `Body(..., embed=True, alias="user")` 是否仍与客户端字段一致 <cite>app/api/routes/authentication.py:23-26</cite>。 评论接口 404：先确认 `get_article_by_slug_from_path` 能否解析到文章，再排查 `CommentsRepository` <cite>app/api/routes/comments.py:31-34</cite>。 档案接口出错：核对 `get_profile_by_username_from_path` 解析逻辑与 `Profile` 模型字段 <cite>app/api/routes/profiles.py:21-22</cite>。 当前用户上下文异常：通过 `get_current_user_authorizer(required=False)` 与 `required=True` 两处用法比对，确认是否预期走可选分支 <cite>app/api/routes/comments.py:31-34</cite><cite>app/api/routes/users.py:19-21</cite>。 标签列表为空或加载慢：复核 `TagsRepository` 实现与会话生命周期，并视情况引入缓存 <cite>app/api/routes/tags.py:11-12</cite>。

## 结论

整体架构由“路由 → 依赖注入 → 仓储 / 配置”的标准化链式调用组成，路由层不直接耦合数据库或配置读取，使该示例在契合 Conduit 测试套件的同时保持较薄的服务边界；考虑到仓库已不再积极维护，读者更应把本仓库视为通过测试样例验证的参考实现，而非持续迭代的应用框架 。

HTTP 请求从路由包进入，再由模型与服务完成业务与持久化。 <cite>app/models/common.py:6-6</cite>

## 目录

1. 简介
2. 项目结构
3. 核心组件
4. 详细分析
5. 依赖关系分析
6. 性能考虑
7. 故障排查指南
8. 结论
