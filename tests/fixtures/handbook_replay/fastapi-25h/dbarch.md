# 数据库架构

本仓库基于 FastAPI 实现 RealWorld 示例后端，数据访问层使用 asyncpg 直接执行手写 SQL，并通过 `app/db/migrations` 中的 Alembic 版本管理表结构演进，而领域模型则由 Pydantic 类承担序列化与校验职责。
<cite>app/db/migrations/versions/fdf8821871d7_main_tables.py:20-34</cite>

## 核心数据模型

核心数据模型由 `app/models/domain` 下的 Pydantic 类承担，它们既负责网络层 schema，也充当领域实体的载体，与数据库表一一对应。`Article` 继承自 `IDModelMixin` 与 `DateTimeModelMixin`，并聚合 `RWModel`，其字段覆盖 slug、title、description、body、tags 列表以及关联的 `Profile` 作者对象，同时携带 `favorited` 与 `favorites_count` 这类衍生统计字段 <cite>app/models/domain/articles.py:8-16</cite>。`Comment` 同样继承自 `IDModelMixin` 与 `DateTimeModelMixin`，持有 body 与嵌套的 author Profile，体现文章下评论的扁平结构 <cite>app/models/domain/comments.py:6-8</cite>。

为了让实体在 Pydantic 体系下保持稳定身份，`IDModelMixin` 将数据库主键 `id` 暴露为字段 `id_`，通过别名机制避免与 Python 关键字或内部命名冲突 <cite>app/models/common.py:18-19</cite>。`DateTimeModelMixin` 则定义 `created_at` 与 `updated_at` 两个时间字段，并在 `@validator(..., pre=True)` 中实现 `default_datetime`，当字段为空时由数据库侧的默认值或 Python 端兜底，保证时间戳在反序列化阶段总是有效 <cite>app/models/common.py:6-17</cite>。

## 服务数据模型

服务层并不依赖 ORM 实体，而是直接在路由处理函数内拼接 SQL，并通过 asyncpg 执行，将结果按列名映射回上述 Pydantic 模型。这种“SQL 字符串 + Pydantic 校验”模式让模型既是传输载体，也是服务返回结构，避免出现两套实体定义。`Article.tags` 字段以 `List[str]` 表达，意味着标签表通过多对多或数组结构与文章表建立联系 <cite>app/models/domain/articles.py:8-16</cite>；评论侧 `Comment.author` 以嵌套 `Profile` 表达作者信息 <cite>app/models/domain/comments.py:6-8</cite>。衍生字段如 `favorited`、`favorites_count` 在数据库层通常由 JOIN 与聚合查询给出，再由模型直接承载，便于接口层直接序列化。

## 数据库与迁移策略

迁移以 Alembic 版本脚本为单一事实来源，`app/db/migrations/versions` 中的 `fdf8821871d7_main_tables.py` 负责建立核心表结构，并在脚本内通过 `create_updated_at_trigger` 注册 PostgreSQL 触发器函数 `update_updated_at_column()`，在 `BEFORE UPDATE` 时将 `NEW.updated_at` 写为 `now()`，从而保证应用层即便不显式赋值，时间戳也会随更新自动推进 <cite>app/db/migrations/versions/fdf8821871d7_main_tables.py:20-34</cite>。这一机制与模型侧的 `DateTimeModelMixin` 相互呼应：数据库负责维护列，模型负责读取与展示 <cite>app/models/common.py:6-17</cite>。

迁移目录约定 users、profiles、articles、tags、favorites、comments 等主表在此脚本范围内建立；新建实体时应当新增 Alembic 版本文件，并在其中复用 `create_updated_at_trigger` 来保持更新语义一致。引入新字段时需同步检查 `IDModelMixin` 别名映射与 `DateTimeModelMixin` 的校验逻辑，避免模型与列定义错位 <cite>app/models/common.py:18-19</cite>。

## 目录

1. 核心数据模型
2. 服务数据模型
3. 数据库与迁移策略
