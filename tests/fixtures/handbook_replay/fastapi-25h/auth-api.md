# 认证授权API

## 简介

本仓库为 `fastapi-realworld-example-app`，其根说明文件 `README.rst` 明确指出 **"
<cite>app/api/routes/authentication.py:23-26</cite>

## 项目结构

认证授权相关源码集中在 `app/api/routes/`，并按资源维度拆分。`app/api/routes/authentication.py` 暴露 `POST /api/users/login` 与 `POST /api/users`，`login` 入口把请求体嵌入到 `user` 字段中 <cite>app/api/routes/authentication.py:23-26</cite>。文章子系统位于 `app/api/routes/articles/`，其中 `articles_common.py` 既承载 `GET /api/articles/feed` 的当前用户授权，也承载 `POST/DELETE /api/articles/{slug}/favorite` 的归属校验；用户档案子系统位于 `app/api/routes/profiles.py`，处理 `POST/DELETE /api/profiles/{username}/follow`。依赖注入装配则在 `app/api/dependencies/`、`app/db/`、`app/models/` 与 `app/core/config/` 中按层分布。

## 核心组件

`get_current_user_authorizer`：FastAPI 依赖，负责从请求头解析 JWT，并把 SQLAlchemy `User` 实例注入路由处理器，是所有需要登录态的端点的统一入口。 `UsersRepository` / `ArticlesRepository` / `ProfilesRepository`：仓储层抽象，由 `get_repository(...)` 工厂注入到路由签名中，把持久化细节与 HTTP 处理解耦 <cite>app/api/routes/authentication.py:23-26</cite>。 `get_article_by_slug_from_path` / `get_profile_by_username_from_path`：路径参数依赖，确保 `Article`、`Profile` 资源在进入业务逻辑前已经被加载好，便于在 `Depends` 链中复用 <cite>app/api/routes/articles/articles_common.py:27-31</cite><cite>app/api/routes/profiles.py:32-35</cite>。 `AppSettings`：通过 `Depends(get_app_settings)` 注入，主要承载 JWT 签名与过期相关配置 <cite>app/api/routes/authentication.py:23-26</cite>。

## 架构总览

整体采用"FastAPI 路由 + 依赖注入 + 仓储层"三层结构。请求进入后，先由路径依赖（路径参数 → 实体）解析出 `Article` / `Profile` 资源，再由 `get_current_user_authorizer` 把当前用户绑定到处理器上下文，最后由对应仓储执行写操作。`feed` 这类依赖当前用户的列表型接口，同样在签名中声明 `Depends(get_current_user_authorizer())` 来完成授权 <cite>app/api/routes/articles/articles_common.py:27-31</cite>。"关注/取关"与"收藏/取消收藏"动作则使用相同的"资源依赖 + 用户依赖 + 仓储依赖"组合 <cite>app/api/routes/profiles.py:32-35</cite><cite>app/api/routes/articles/articles_common.py:52-55</cite>。

## 详细组件分析

在登录路径上，`login` 将请求体通过 `Body(..., embed=True, alias="user")` 重新包装，配合 `UsersRepository` 与 `AppSettings` 完成凭据校验与 Token 签发；`AppSettings` 的注入保证了签名密钥和过期时间都在请求作用域内被显式使用，而不是从模块全局读取 <cite>app/api/routes/authentication.py:23-26</cite>。

Feed 与 Favorites 接口的设计思路高度一致：`get_articles_for_user_feed` 用 `Query` 校验 `limit`/`offset` 下界，并依赖当前用户以保证 Feed 是登录用户专属视图 <cite>app/api/routes/articles/articles_common.py:27-31</cite>；`mark_article_as_favorite` 在签名中先取到 `Article`，再取到当前 `User`，最后交给仓储写入中间表 <cite>app/api/routes/articles/articles_common.py:52-55</cite>。这种顺序保证了"先有资源、后有用户"的依赖级联，仓储层不需要再做权限判断。

社交图（follow / unfollow）的实现对称：`follow_for_user` 与 `unsubscribe_from_user` 都依赖 `get_profile_by_username_from_path` 与 `get_current_user_authorizer`，因此要操作的 `profile` 与执行动作的 `user` 在处理器执行前都已经是已加载实体，仓储调用只是把状态翻转到中间表 <cite>app/api/routes/profiles.py:32-35</cite><cite>app/api/routes/profiles.py:62-65</cite>。

## 附录：关键端点

| 方法 | 路径 | 主要授权来源 |
| --- | --- | --- |
| POST | `/api/users/login` | `UsersRepository` + `AppSettings` <cite>app/api/routes/authentication.py:23-26</cite> |
| GET | `/api/articles/feed` | `get_current_user_authorizer` <cite>app/api/routes/articles/articles_common.py:27-31</cite> |
| POST | `/api/articles/{slug}/favorite` | `Article` + 当前 `User` <cite>app/api/routes/articles/articles_common.py:52-55</cite> |
| POST | `/api/profiles/{username}/follow` | `Profile` + 当前 `User` <cite>app/api/routes/profiles.py:32-35</cite> |
| DELETE | `/api/profiles/{username}/follow` | `Profile` + 当前 `User` <cite>app/api/routes/profiles.py:62-65</cite> |

## API 分组

按资源分组的接口：

### api/articles

GET /api/articles（handler `list_articles`） <cite>app/api/routes/articles/articles_resource.py:31-41</cite>。 POST /api/articles（handler `create_new_article`） <cite>app/api/routes/articles/articles_resource.py:59-69</cite>。 DELETE /api/articles/{slug}（handler `delete_article_by_slug`） 。 GET /api/articles/{slug}（handler `retrieve_article_by_slug`） <cite>app/api/routes/articles/articles_resource.py:83-93</cite>。 PUT /api/articles/{slug}（handler `update_article_by_slug`） <cite>app/api/routes/articles/articles_resource.py:95-105</cite>。

### api/articles/comments

GET /api/articles/{slug}/comments（handler `list_comments_for_article`） <cite>app/api/routes/comments.py:31-41</cite>。 POST /api/articles/{slug}/comments（handler `create_comment_for_article`） <cite>app/api/routes/comments.py:46-56</cite>。 DELETE /api/articles/{slug}/comments/{comment_id}（handler `delete_comment_from_article`） 。

### api/articles/favorite

DELETE /api/articles/{slug}/favorite（handler `remove_article_from_favorites`） <cite>app/api/routes/articles/articles_common.py:82-92</cite>。 POST /api/articles/{slug}/favorite（handler `mark_article_as_favorite`） <cite>app/api/routes/articles/articles_common.py:52-62</cite>。

### api/articles/feed

GET /api/articles/feed（handler `get_articles_for_user_feed`） <cite>app/api/routes/articles/articles_common.py:27-37</cite>。

### api/profiles

GET /api/profiles/{username}（handler `retrieve_profile_by_username`） <cite>app/api/routes/profiles.py:21-31</cite>。

### api/profiles/follow

DELETE /api/profiles/{username}/follow（handler `unsubscribe_from_user`） <cite>app/api/routes/profiles.py:62-72</cite>。 POST /api/profiles/{username}/follow（handler `follow_for_user`） <cite>app/api/routes/profiles.py:32-42</cite>。

### api/tags

GET /api/tags（handler `get_all_tags`） 。

### api/user

GET /api/user（handler `retrieve_current_user`） <cite>app/api/routes/users.py:19-29</cite>。 PUT /api/user（handler `update_current_user`） <cite>app/api/routes/users.py:39-49</cite>。

### api/users

POST /api/users（handler `register`） <cite>app/api/routes/authentication.py:62-72</cite>。

### api/users/login

POST /api/users/login（handler `login`） <cite>app/api/routes/authentication.py:23-33</cite>。

## 调用约定

HTTP 方法: DELETE, GET, POST, PUT。 认证: bearer。

## Schema 摘要

本节 Schema 与 API 参考中已给出的摘要相同，见该节，避免重复粘贴。

UNRESOLVED_API_FLOW：缺少可验证调用链证据，不生成占位流程图。

## 目录

1. 简介
2. 项目结构
3. 核心组件
4. 架构总览
5. 详细组件分析
6. 附录：关键端点
7. API 分组
8. 调用约定
9. Schema 摘要
