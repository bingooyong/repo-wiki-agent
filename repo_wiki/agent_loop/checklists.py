"""Fixed, generic page intents and checklists (no per-repo planning step)."""

from __future__ import annotations

from dataclasses import dataclass

PAGE_TYPES = ("overview", "install", "datamodel", "api")


@dataclass(frozen=True)
class ChecklistItem:
    id: str
    question: str
    slots: tuple[str, ...]


@dataclass(frozen=True)
class PageSpec:
    page_type: str
    title: str
    question: str
    checklist: tuple[ChecklistItem, ...]
    slot_help: str
    table_desc: str
    placeholder: str

    @property
    def ids(self) -> list[str]:
        return [c.id for c in self.checklist]

    def checklist_text(self) -> str:
        return "\n".join(
            f"- {c.id}: {c.question} (slots: {', '.join(c.slots)})" for c in self.checklist
        )


COMMON_SLOTS = (
    " | note (value=checklist id; an evidenced 'not applicable' for that item)"
    " | conflict (value=subject; two sources disagree — cite BOTH lines, from different files)"
)

PAGES: dict[str, PageSpec] = {
    "overview": PageSpec(
        page_type="overview",
        title="项目概览",
        question=(
            "读者第一次接触这个仓库：它是什么、用来做什么、用什么语言/框架/关键依赖、从哪些入口启动、"
            "代码按哪些模块组织以及各模块职责。"
        ),
        checklist=(
            ChecklistItem(
                "identity",
                "project name and one-sentence purpose (README title/description or manifest)",
                ("name", "purpose"),
            ),
            ChecklistItem(
                "stack",
                "primary language(s), main framework, and the key library for EACH role that is "
                "present — database/driver/ORM (and the database product), migrations, auth, "
                "validation, API docs, logging, process manager/app server — one library fact per "
                "role, proven by manifests/imports (not just the first entries of the dependency list)",
                ("language", "framework", "library"),
            ),
            ChecklistItem(
                "entry",
                "every entry point (executable/main/start file) and what it starts",
                ("entry",),
            ),
            ChecklistItem(
                "modules",
                "every top-level source module/directory and its role (role proven by code inside it)",
                ("module",),
            ),
        ),
        slot_help=(
            "name | purpose | language | framework | library | entry (value=file path) | "
            "module (value=directory path)"
        ),
        table_desc="the module table (module, role, evidence ids) and the entry-point list",
        placeholder="{{MODULE_TABLE}}",
    ),
    "install": PageSpec(
        page_type="install",
        title="安装与运行",
        question=(
            "读者要在本机把它跑起来：需要哪些前置工具及版本、如何获取与安装依赖、需要哪些配置文件/环境变量、"
            "用什么命令启动（含数据库准备）、默认监听端口、如何确认已运行。"
        ),
        checklist=(
            ChecklistItem(
                "prereq",
                "required tools/runtimes and their versions (manifests, Dockerfiles, compose images, README)",
                ("prereq",),
            ),
            ChecklistItem(
                "config",
                "configuration files and environment variables the app reads (names, defaults, where read)",
                ("config_file", "env"),
            ),
            ChecklistItem(
                "install",
                "get-the-code and dependency install / build commands (verbatim)",
                ("command",),
            ),
            ChecklistItem(
                "run",
                "start commands incl. database preparation/migrations and container option (verbatim)",
                ("command", "service"),
            ),
            ChecklistItem(
                "port",
                "default listen port/address from source/config (and conflicts with docs, if any)",
                ("port",),
            ),
            ChecklistItem(
                "verify",
                "how to confirm it is running (health/docs URL, curl) consistent with the port",
                ("verify",),
            ),
        ),
        slot_help=(
            "prereq (value='tool version'; only tools the reader installs on the host — a container "
            "base image is a service/note, not a host prereq) | config_file (value=path) | "
            "env (value=VAR_NAME) | command (value=the exact command line) | port (value=number) | "
            "verify (value=URL or path) | service (value=compose service name) | note"
        ),
        table_desc="the environment-variable table (name, meaning, evidence ids)",
        placeholder="{{ENV_TABLE}}",
    ),
    "datamodel": PageSpec(
        page_type="datamodel",
        title="数据模型",
        question=(
            "读者要理解持久化数据：用什么存储、表/集合/实体有哪些、每个实体的字段与约束、实体之间的关系"
            "（外键/引用），以及哪些类型不是持久化实体。"
        ),
        checklist=(
            ChecklistItem(
                "store",
                "concrete storage engine (database product, proven by driver/DSN/image) and where the "
                "schema is defined (DDL, migrations, ORM/ODM models)",
                ("store", "location"),
            ),
            ChecklistItem("entities", "every persisted table/collection/entity", ("entity",)),
            ChecklistItem(
                "fields",
                "fields of each entity with type/constraints (PK, unique, nullable, default)",
                ("field", "key"),
            ),
            ChecklistItem(
                "relations",
                "relationships/foreign keys/references between entities, or an explicit proof that "
                "an entity has none",
                ("relation", "no_relation"),
            ),
            ChecklistItem(
                "types",
                "code types (struct/class/model) that represent each persisted entity, and "
                "look-alike types that are NOT persisted",
                ("code_type", "not_entity"),
            ),
        ),
        slot_help=(
            "store | location (value=path) | entity (value=table/collection name) | "
            "field (value='entity.field') | key (value='entity: col1, col2') | "
            "relation (value='entity.col -> other_entity.col') | no_relation (value=entity) | "
            "code_type (value=type name that represents a persisted entity) | "
            "not_entity (value=type name that is NOT persisted)"
        ),
        table_desc="the per-entity field tables, the relation list and an ER diagram",
        placeholder="{{MODEL_TABLES}}",
    ),
    "api": PageSpec(
        page_type="api",
        title="API 参考",
        question=(
            "读者想知道这个服务对外暴露哪些 HTTP 接口——每个接口的方法、完整路径（含所有前缀）、"
            "处理函数定义在哪里、服务在哪里监听、如何鉴权。"
        ),
        checklist=(
            ChecklistItem(
                "routes",
                "every HTTP route (method + full path incl. prefixes) and its handler location — "
                "answered by the verified route list",
                ("route",),
            ),
            ChecklistItem(
                "server",
                "where the HTTP application/server is created and the default listen address/port",
                ("server", "port", "entry"),
            ),
            ChecklistItem(
                "auth",
                "how requests are authenticated/authorised (middleware, dependency, header, token "
                "scheme), or evidence that no authentication exists",
                ("auth",),
            ),
            ChecklistItem(
                "conventions",
                "request/response conventions shared by the routes (content type, error format, "
                "pagination, versioned prefix)",
                ("convention",),
            ),
        ),
        slot_help=(
            "server (value=file path or app object) | port (value=number) | entry (value=file path) "
            "| auth (value=mechanism name, e.g. the header/dependency/middleware identifier) | "
            "convention (value=identifier the convention is expressed by)"
        ),
        table_desc="the route table grouped by server and registration file",
        placeholder="{{ROUTE_TABLE}}",
    ),
}
