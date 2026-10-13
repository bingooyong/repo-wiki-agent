# 数据迁移策略

## 简介

## 核心数据模型

数据模型由两类组成：领域模型位于 `app/models/domain`，通用混入位于 `app/models/common`。它们是 Pydantic 模型而非 ORM 实体，因此读写层使用 asyncpg 直接执行原生 SQL。
<cite>app/models/common.py:6-17</cite>

`Article` 同时继承 `IDModelMixin` 与 `DateTimeModelMixin`，并在自身字段中组合了 `tags`、`author`、`favorited` 与 `favorites_count` 这类派生属性，体现出领域对象把"是否收藏"这类计数语义内聚到自身 <cite>app/models/domain/articles.py:8-16</cite>。`Comment` 同样继承上述两个混入，并以 `author: Profile` 形成与 `Profile` 的关联字段 <cite>app/models/domain/comments.py:6-8</cite>。

`IDModelMixin` 提供统一的 `id_: int = Field(0, alias="id")`，使得模型既能在序列化时输出 `id`，又能在内部以 `id_` 避免与 Python 关键字冲突 <cite>app/models/common.py:18-19</cite>。`DateTimeModelMixin` 通过 `default_datetime` 校验器在缺省时填充 `datetime.datetime.now()`，保证领域对象在创建时即具有完整的时间戳语义 <cite>app/models/common.py:6-17</cite>。

## 服务数据模型

服务层的实体边界遵循 RealWorld Conduit 规范，围绕 `users`/`profiles`、`articles`、`tags`、`favorites`、`comments` 展开。`Article` 与 `Comment` 均通过 `RWModel` 基类承载响应结构，并在字段层面把作者关系物化为 `Profile`，把多值标签建模为 `List[str]` <cite>app/models/domain/articles.py:8-16</cite><cite>app/models/domain/comments.py:6-8</cite>。这种以"反范式嵌入"的方式输出的设计，配合 asyncpg 的 raw SQL 访问，使读路径只需一次查询即可构造完整的领域对象，避免在服务层再做 JOIN 装配。

由于实体并非 ORM 映射，因此 `id` 与 `id_`、`updated_at` 的语义必须在数据库列与 Pydantic 别名两侧保持一致，否则迁移脚本与查询语句需要分别约定映射关系。
<cite>app/db/migrations/versions/fdf8821871d7_main_tables.py:20-34</cite>

## 数据库与迁移策略

迁移以 Alembic 管理，核心文件位于 `app/db/migrations/versions`，初始迁移 `fdf8821871d7_main_tables.py` 负责建立主表结构与时间戳维护机制。其关键并非单纯建表，而是注册一个 `BEFORE UPDATE` 触发器函数 `update_updated_at_column()`，由 `create_updated_at_trigger()` 在迁移中创建，确保任何 UPDATE 都会刷新 `updated_at` <cite>app/db/migrations/versions/fdf8821871d7_main_tables.py:20-34</cite>。

这意味着 `DateTimeModelMixin` 的 `updated_at` 默认值与数据库触发器形成了"双轨"语义：应用层在缺省时由 Pydantic 写入当前时间 <cite>app/models/common.py:6-17</cite>，而数据库层在 UPDATE 时由触发器强制覆盖 <cite>app/db/migrations/versions/fdf8821871d7_main_tables.py:20-34</cite>。迁移策略因此可归纳为三点：

- 迁移入口以 Alembic `op.execute` 注册 PL/pgSQL 函数，把列更新约束写入 schema，而非依赖应用代码 <cite>app/db/migrations/versions/fdf8821871d7_main_tables.py:20-34</cite>。
- 时间戳语义由 `DateTimeModelMixin` 与触发器共同维护，任一层缺失都会导致 `updated_at` 失真 <cite>app/models/common.py:6-17</cite>。
- 主键语义由 `IDModelMixin` 统一以别名 `id` 输出，读路径以一次 raw SQL 完成组装 <cite>app/models/common.py:18-19</cite>。

综上，迁移策略的核心是把"时间戳不可逆刷新"这类数据完整性约束下沉到数据库层，而把"形状校验"留给 Pydantic 混入，从而在缺乏 ORM 的栈下维持清晰的职责边界。

## 目录

1. 简介
2. 核心数据模型
3. 服务数据模型
4. 数据库与迁移策略
