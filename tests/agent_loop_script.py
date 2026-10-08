"""Scripted model turns for the demo repository (overview + API pages pass, no live calls)."""

from __future__ import annotations

from typing import Any

from agent_loop_fixtures import Rule, ScriptedModel, reply, tool_call

AUDIT_OK = reply([tool_call("submit_audit", {"findings": [], "verdict": "ok"})])

OVERVIEW_WRITER = (
    "## 项目简介\n\n"
    "demo-shop 是一个小型订单服务，项目名称取自 README 标题 [F1]。它对外提供订单查询能力，"
    "整个仓库的说明文字也围绕这个用途展开 [F2]。\n\n"
    "## 技术栈\n\n"
    "项目使用 Python 编写，所有源码文件都是 Python 模块 [F3]。Web 层基于 Flask 框架构建，"
    "依赖在 requirements.txt 中声明 [F4]。依赖清单只有 Flask 这一项，并且固定了具体版本，"
    "因此安装依赖时会得到与开发者相同的框架版本，减少因为框架升级带来的行为差异 [F4]。"
    "应用对象通过 Flask 类构造，模块名作为应用名称传入，这是 Flask 项目最常见的装配方式 [F7]。"
    "除了 Flask 之外仓库没有引入数据库驱动、ORM 或任务队列等其他运行时依赖，"
    "整个服务只依靠框架自带的能力处理请求 [F4]。\n\n"
    "## 入口与模块\n\n"
    "应用从 app.py 启动，在主程序分支中调用 app.run 并监听 5000 端口 [F5]。"
    "也就是说，直接用 Python 解释器执行这个文件就会启动内置的开发服务器，"
    "服务启动后会持续监听该端口并处理进入的 HTTP 请求 [F5]。\n\n"
    "## 代码组织\n\n"
    "仓库的代码分成两个层次：根目录承担应用装配的职责，在 app.py 中创建 Flask 应用对象 [F7]；"
    "shop 包则负责订单数据本身，它在内存中维护订单列表，供 HTTP 处理函数读取 [F6]。"
    "这种划分让 Web 层与数据层保持分离：Web 层只关心如何把请求映射到处理函数，"
    "数据层只关心订单如何保存与读取，两者之间通过普通的函数调用连接起来 [F6]。"
    "由于订单只保存在进程内存中，服务重启后数据不会保留，这一点在阅读 shop 包时需要特别注意 [F6]。\n\n"
    "## 模块职责\n\n"
    "下面按模块说明代码的组织方式以及每个模块承担的职责，模块清单由源码扫描得到 [F6]。\n\n"
    "{{MODULE_TABLE}}\n"
)

API_WRITER = (
    "## 接口概览\n\n"
    "服务通过 Flask 装饰器注册 HTTP 接口，当前只有一个订单查询接口，"
    "由 orders 处理函数返回订单列表 [R1]。\n\n"
    "## 服务与监听\n\n"
    "Flask 应用在 app.py 中创建，并在主程序分支里启动，默认监听 5000 端口 [F1]。"
    "源码中没有为这个接口配置任何鉴权逻辑，请求会直接进入处理函数 [F2]。"
    "处理函数直接返回字典，由框架负责把它序列化为响应体 [F3]。\n\n"
    "## 请求处理流程\n\n"
    "一次请求的处理过程很直接：客户端访问订单路径后，Flask 根据装饰器登记的路径与方法找到 orders 处理函数 [R1]。"
    "处理函数调用 shop 包提供的订单查询函数，拿到当前保存的订单列表，再把它放进一个字典中返回 [F3]。"
    "框架随后把这个字典转换成响应体发送给客户端，整个过程中没有额外的中间件或鉴权步骤参与 [F2]。"
    "由于只有一个接口，服务对外的契约非常小：调用方只需要知道监听端口与订单路径即可完成调用 [F1]。"
    "接口只接受 GET 方法，其他方法不会被路由到这个处理函数 [R1]。"
    "如果后续增加新的接口，同样需要通过装饰器登记路径与方法，并在接口清单中出现 [R1]。\n\n"
    "## 部署与调用注意事项\n\n"
    "服务在主程序分支中启动，因此以模块方式导入 app.py 时不会自动监听端口 [F1]。"
    "调用方在本机访问时应使用默认端口，返回的数据结构就是处理函数返回的字典 [F3]。"
    "由于没有鉴权，任何能访问该端口的客户端都可以读取订单列表，部署到共享网络时需要额外的网络隔离 [F2]。\n\n"
    "## 返回数据\n\n"
    "订单查询接口返回的字典只有一个键，对应的值是订单列表，列表内容来自 shop 包维护的内存数据 [F3]。"
    "处理函数本身不做分页、过滤或排序，调用方拿到的是当前全部订单 [F3]。"
    "因为数据保存在进程内存里，同一进程内多次调用会看到一致的结果，而不同进程之间不会共享订单数据 [F3]。"
    "需要持久化或多实例部署时，应先在 shop 包中替换存储实现，再考虑扩展接口 [F3]。"
    "这种设计让接口层保持很薄，大部分行为都可以通过阅读处理函数与 shop 包直接确认 [R1]。\n\n"
    "## 接口清单\n\n"
    "{{ROUTE_TABLE}}\n"
)

PROFILE = {
    "languages": ["Python"],
    "frameworks": [{"name": "Flask", "evidence": ["requirements.txt:1: flask==3.0.0"]}],
    "entry_points": [
        {"file": "app.py", "role": "starts the app", "evidence": ["app.py:14: app.run(port=5000)"]}
    ],
    "layout": [{"dir": "shop", "purpose": "order store"}],
}

IDENTITY_FACTS = [
    "identity | name | demo-shop | 项目名称为 demo-shop | README.md:1: # demo-shop",
    "identity | purpose | small order service | demo-shop 是一个小型订单服务 | "
    "README.md:3: demo-shop is a small order service.",
    "stack | language | Python | 项目使用 Python 编写 | app.py:1: from flask import Flask",
    "stack | framework | Flask | Web 层使用 Flask 框架 | requirements.txt:1: flask==3.0.0",
    "entry | entry | app.py | app.py 调用 app.run 启动服务，端口 5000 | app.py:14: app.run(port=5000)",
]
MODULE_FACTS = [
    "modules | module | shop | shop 包提供内存中的订单存储 | "
    'shop/store.py:1: """In-memory order store used by the HTTP handlers."""',
    "modules | module | . | 根目录的 app.py 创建 Flask 应用 | app.py:5: app = Flask(__name__)",
]
API_FACTS = [
    "server | server | app.py | Flask 应用在 app.py 中创建并通过 app.run 监听 5000 端口 | "
    "app.py:14: app.run(port=5000)",
    "auth | note | auth | 路由装饰器未声明任何鉴权，处理函数直接执行 | "
    'app.py:8: @app.route("/orders", methods=["GET"])',
    "conventions | note | conventions | 处理函数直接返回字典作为响应体 | "
    'app.py:10:     return {"orders": list_orders()}',
]
ROUTE = {
    "method": "GET",
    "path": "/orders",
    "method_ev": "app.py:8",
    "parts": ["/orders @ app.py:8"],
    "handler": "orders",
}


def _turns(*turns: dict[str, Any]) -> Any:
    def respond(turn: int, _body: dict[str, Any]) -> dict[str, Any]:
        return turns[min(turn, len(turns) - 1)]

    return respond


def _starts(prefix: str, needle: str = "") -> Any:
    return lambda system, user: system.startswith(prefix) and needle in user


def demo_rules(
    overview_writer: str = OVERVIEW_WRITER,
    api_writer: str = API_WRITER,
    overview_audit: dict[str, Any] | None = None,
) -> list[Rule]:
    finish = reply([tool_call("finish", {"notes": "done"})])
    return [
        (
            _starts("You are the Recognizer"),
            _turns(reply([tool_call("submit_profile", PROFILE)])),
        ),
        # overview: identity shard, module shard (one turn each: record + finish)
        (
            _starts("You are an Investigator", "Identity + stack"),
            _turns(
                reply(
                    [
                        tool_call("record_facts", {"facts": IDENTITY_FACTS}, 0),
                        tool_call("finish", {}, 1),
                    ]
                )
            ),
        ),
        (
            _starts("You are an Investigator", "Module shard"),
            _turns(
                reply(
                    [
                        tool_call("record_facts", {"facts": MODULE_FACTS}, 0),
                        tool_call("finish", {}, 1),
                    ]
                )
            ),
        ),
        (_starts("You are the Writer of the page"), _turns(reply(content=overview_writer))),
        (
            _starts("You are the Auditor", "Page: 项目概览"),
            _turns(overview_audit or AUDIT_OK),
        ),
        # API page
        (
            _starts("You are the Route-Mechanism Analyst"),
            _turns(
                reply(
                    [
                        tool_call(
                            "submit_mechanisms",
                            {
                                "mechanisms": [
                                    {
                                        "id": "flask-route",
                                        "summary": "Flask app.route decorator",
                                        "method_rule": "methods list literal",
                                        "path_rule": "literal path argument",
                                        "evidence": [
                                            'app.py:8: @app.route("/orders", methods=["GET"])'
                                        ],
                                    }
                                ],
                                "servers": [{"name": "app", "entry_file": "app.py"}],
                            },
                        )
                    ]
                )
            ),
        ),
        (
            _starts("You are a Route Investigator"),
            _turns(
                reply(
                    [
                        tool_call("record_routes", {"routes": [ROUTE]}, 0),
                        tool_call("finish", {"notes": "ok"}, 1),
                    ]
                ),
                finish,
            ),
        ),
        (
            _starts("You are the Investigator for the non-route facts"),
            _turns(
                reply(
                    [
                        tool_call("record_facts", {"facts": API_FACTS}, 0),
                        tool_call("finish", {"covered_by_routes": ["routes"]}, 1),
                    ]
                )
            ),
        ),
        (_starts("You are the Writer."), _turns(reply(content=api_writer))),
        (_starts("You are the Auditor", "Page: API 参考"), _turns(AUDIT_OK)),
    ]


def demo_model(**kw: Any) -> ScriptedModel:
    return ScriptedModel(demo_rules(**kw))
