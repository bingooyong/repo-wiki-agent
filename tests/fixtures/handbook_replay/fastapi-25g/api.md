# 认证授权API

## 简介

本页面围绕仓库 `fastapi-realworld-example-app` 中的认证与授权相关 API 接口进行梳理。该仓库定位为 RealWorld 规范（Conduit）参考实现，目前以一套完整的 FastAPI + Tortoise ORM 工程对外提供 Conduit 全套接口，因此角色应优先理解为 RealWorld 后端参考实现，而非通用业务平台。仓库根 README 中明确标注：该项目不再积极维护，因为示例本身已足够完整并能完整通过 Conduit 测试套件，更现代的样例可在其他仓库中获得<cite>README.rst:1-3</cite>。在本仓库内，认证授权主要体现在用户登录、获取当前用户，以及对文章订阅、收藏等敏感写操作的访问控制上，由专门的路由模块与依赖注入函数负责。

## 项目结构

仓库将 HTTP 路由按业务域拆分到 `app/api/routes/` 下，并在 `app/api/routes/articles/` 子包中聚合文章相关接口。认证相关实现位于 `app/api/routes/authentication.py`，文章写操作与订阅源相关接口位于 `app/api/routes/articles/articles_common.py`，用户关注/取关等社交操作位于 `app/api/routes/profiles.py`。所有路由都通过 FastAPI 的依赖注入系统获取仓库实例、当前用户以及配置对象，从而把认证授权机制以可复用的依赖函数形式集中在路由层调用方之前。
<cite>app/api/routes/authentication.py:23-26</cite>

## 核心组件

认证授权相关的关键入口主要由三类组件构成：登录端点、当前用户依赖、以及对受保护资源的依赖装饰。

- `login` 端点：处理 `POST /api/users/login` 请求，将请求体嵌入 `user` 字段，并注入 `UsersRepository` 与 `AppSettings`<cite>app/api/routes/authentication.py:23-26</cite>。
- `get_current_user_authorizer`：作为 FastAPI 依赖，在需要登录态的接口处统一解析当前用户，被以下三类接口复用为 `user: User = Depends(get_current_user_authorizer())`。
- `follow_for_user`、`unsubscribe_from_user`：用户关注与取消关注端点，先通过路径参数解析目标 `Profile`，再注入当前 `User` 与 `ProfilesRepository`，从而保证只允许已认证用户对其执行关注/取消关注<cite>app/api/routes/profiles.py:32-35</cite><cite>app/api/routes/profiles.py:62-65</cite>。
- `mark_article_as_favorite` 与 `get_articles_for_user_feed`：分别在收藏文章与拉取订阅源文章列表时复用相同的 `get_current_user_authorizer` 依赖，并配合 `ArticlesRepository` 完成写操作或带个性化过滤的读操作<cite>app/api/routes/articles/articles_common.py:27-31</cite><cite>app/api/routes/articles/articles_common.py:52-55</cite>。

## 架构总览

认证授权在请求链路中表现为一种"前置过滤器"，由依赖函数而非业务函数承担。具体而言，受保护的路由处理函数不再自行解析 JWT 或会话状态，而是在签名里通过 `Depends(...)` 声明所需依赖：路径参数解析（如 `get_article_by_slug_from_path` 与 `get_profile_by_username_from_path`）负责把 URI 段映射为领域模型对象<cite>app/api/routes/profiles.py:32-35</cite>；`get_current_user_authorizer` 负责把请求头中的凭证映射为已登录 `User`<cite>app/api/routes/articles/articles_common.py:27-31</cite>；仓库实现（如 `UsersRepository`、`ArticlesRepository`、`ProfilesRepository`）则通过 `Depends(get_repository(...))` 由请求作用域注入，使端点函数只关注业务编排<cite>app/api/routes/authentication.py:23-26</cite>。这种分层确保了认证与资源解析都可以被任意端点组合复用。

## 详细组件分析

从 `login` 端点可以看到凭证注入的形态：请求体被 `Body(..., embed=True, alias="user")` 包装以匹配 RealWorld 的 `{"user": {...}}` 嵌套结构，配置项则通过 `Depends(get_app_settings())` 注入，避免在端点内部硬编码密钥或过期时间<cite>app/api/routes/authentication.py:23-26</cite>。

在 `follow_for_user` 中，授权顺序是先解析路径对象再取出当前用户：函数签名依次声明 `profile`、`user`、`profiles_repo` 三个依赖，FastAPI 会按声明顺序解析它们，使得到达业务逻辑时，目标用户与操作者均已通过认证与存在性校验<cite>app/api/routes/profiles.py:32-35</cite>。`unsubscribe_from_user` 沿用相同的依赖链，只是语义变为取消关注<cite>app/api/routes/profiles.py:62-65</cite>。

对受保护读操作而言，`get_articles_for_user_feed` 在拉取订阅源时同样依赖 `get_current_user_authorizer`，从而把"取登录用户的关注者所发文章列表"这一业务规则收敛到服务层或仓储实现中，路由层只负责拼装分页参数<cite>app/api/routes/articles/articles_common.py:27-31</cite>。

对受保护写操作而言，`mark_article_as_favorite` 通过 `get_article_by_slug_from_path` 先确认文章存在，再叠加当前用户依赖，最后交给 `ArticlesRepository` 完成收藏行为。这种"路径对象 + 当前用户 + 仓储"的三段式签名在仓库内多处出现，反映出一种统一的授权与编排风格<cite>app/api/routes/articles/articles_common.py:52-55</cite>。

## 附录：关键端点表

| 方法 | 路径 | 认证来源证据 |
| --- | --- | --- |
| POST | /api/users/login | <cite>app/api/routes/authentication.py:23-26</cite> |
| GET | /api/articles/feed | <cite>app/api/routes/articles/articles_common.py:27-31</cite> |
| POST | /api/articles/{slug}/favorite | <cite>app/api/routes/articles/articles_common.py:52-55</cite> |
| DELETE | /api/articles/{slug}/favorite | <cite>app/api/routes/articles/articles_common.py:52-55</cite> |
| POST | /api/profiles/{username}/follow | <cite>app/api/routes/profiles.py:32-35</cite> |
| DELETE | /api/profiles/{username}/follow | <cite>app/api/routes/profiles.py:62-65</cite> |

## 目录

1. 简介
2. 项目结构
3. 核心组件
4. 架构总览
5. 详细组件分析
6. 附录：关键端点表

## API 分组

按资源分组的接口：

### api/articles

- GET /api/articles（handler `list_articles`） <cite>app/api/routes/articles/articles_resource.py:31-41</cite>
- POST /api/articles（handler `create_new_article`） <cite>app/api/routes/articles/articles_resource.py:59-69</cite>
- DELETE /api/articles/{slug}（handler `delete_article_by_slug`） 
- GET /api/articles/{slug}（handler `retrieve_article_by_slug`） <cite>app/api/routes/articles/articles_resource.py:83-93</cite>
- PUT /api/articles/{slug}（handler `update_article_by_slug`） <cite>app/api/routes/articles/articles_resource.py:95-105</cite>

### api/articles/comments

- GET /api/articles/{slug}/comments（handler `list_comments_for_article`） <cite>app/api/routes/comments.py:31-41</cite>
- POST /api/articles/{slug}/comments（handler `create_comment_for_article`） <cite>app/api/routes/comments.py:46-56</cite>
- DELETE /api/articles/{slug}/comments/{comment_id}（handler `delete_comment_from_article`） 

### api/articles/favorite

- DELETE /api/articles/{slug}/favorite（handler `remove_article_from_favorites`） <cite>app/api/routes/articles/articles_common.py:82-92</cite>
- POST /api/articles/{slug}/favorite（handler `mark_article_as_favorite`） <cite>app/api/routes/articles/articles_common.py:52-62</cite>

### api/articles/feed

- GET /api/articles/feed（handler `get_articles_for_user_feed`） <cite>app/api/routes/articles/articles_common.py:27-37</cite>

### api/profiles

- GET /api/profiles/{username}（handler `retrieve_profile_by_username`） <cite>app/api/routes/profiles.py:21-31</cite>

### api/profiles/follow

- DELETE /api/profiles/{username}/follow（handler `unsubscribe_from_user`） <cite>app/api/routes/profiles.py:62-72</cite>
- POST /api/profiles/{username}/follow（handler `follow_for_user`） <cite>app/api/routes/profiles.py:32-42</cite>

### api/tags

- GET /api/tags（handler `get_all_tags`） 

### api/user

- GET /api/user（handler `retrieve_current_user`） <cite>app/api/routes/users.py:19-29</cite>
- PUT /api/user（handler `update_current_user`） <cite>app/api/routes/users.py:39-49</cite>

### api/users

- POST /api/users（handler `register`） <cite>app/api/routes/authentication.py:62-72</cite>

### api/users/login

- POST /api/users/login（handler `login`） <cite>app/api/routes/authentication.py:23-33</cite>

## 调用约定

- HTTP 方法: DELETE, GET, POST, PUT
- 认证: bearer

## Schema 摘要

本节 Schema 与 API 参考中已给出的摘要相同，见该节，避免重复粘贴。

UNRESOLVED_API_FLOW：缺少可验证调用链证据，不生成占位流程图。
