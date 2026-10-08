"""Deterministic fact / route verification of the agent loop (no model involved)."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo_wiki.agent_loop.checklists import PAGES
from repo_wiki.agent_loop.evidence import is_doc_file, parse_ev, quote_ok
from repo_wiki.agent_loop.facts import (
    FactStore,
    add_doc_code_conflicts,
    make_conflict,
    parse_fact_str,
    salvage_facts,
    salvage_items,
    salvage_strings,
)
from repo_wiki.agent_loop.repo import RepoView
from repo_wiki.agent_loop.verifier import FactVerifier, apply_ops, verify_routes
from repo_wiki.core.config import SecurityConfig
from tests.agent_loop_fixtures import make_demo_repo


@pytest.fixture()
def repo(tmp_path: Path) -> RepoView:
    root = make_demo_repo(tmp_path / "repo")
    (root / "Makefile").write_text("run:\n\tpython app.py\n", encoding="utf-8")
    (root / "db").mkdir()
    (root / "db" / "schema.sql").write_text(
        "CREATE TABLE users (\n"
        "  id INTEGER PRIMARY KEY,\n"
        "  email TEXT NOT NULL\n"
        ");\n"
        "CREATE TABLE orders (\n"
        "  id INTEGER PRIMARY KEY,\n"
        "  user_id INTEGER REFERENCES users(id)\n"
        ");\n",
        encoding="utf-8",
    )
    sec = SecurityConfig()
    return RepoView(root, sec.deny_globs, sec.deny_dirs)


def _store(repo: RepoView, page: str) -> FactStore:
    from repo_wiki.agent_loop.inventory import dm_inventory

    sites = dm_inventory(repo) if page == "datamodel" else []
    return FactStore(FactVerifier(repo, PAGES[page], sites))


# ------------------------------------------------------------------ evidence / sandbox
def test_quote_ok_accepts_exact_and_relocates_unique_quote(repo: RepoView) -> None:
    assert quote_ok(repo, parse_ev("app.py:14: app.run(port=5000)")) == 14
    # off by more than the radius but unique in the file -> relocated to the real line
    assert quote_ok(repo, parse_ev("app.py:2: app.run(port=5000)")) == 14
    assert quote_ok(repo, parse_ev("app.py:14: app.run(port=8080)")) is None
    assert quote_ok(repo, parse_ev("missing.py:1: x")) is None


def test_repo_view_is_sandboxed_and_hides_denied_files(repo: RepoView) -> None:
    assert ".env.secret" not in repo.files()
    assert repo.lines(".env.secret") is None
    assert repo.safe("../outside.txt") is None
    assert repo.lines("/etc/passwd") is None
    assert "app.py" in repo.files()


def test_allow_globs_is_opt_in(tmp_path: Path) -> None:
    root = make_demo_repo(tmp_path / "r")
    (root / ".env.example").write_text("PORT=5000\n", encoding="utf-8")
    sec = SecurityConfig()
    strict = RepoView(root, sec.deny_globs, sec.deny_dirs)
    assert ".env.example" not in strict.files()
    opted = RepoView(root, sec.deny_globs, sec.deny_dirs, allow_globs=[".env.example"])
    assert ".env.example" in opted.files()
    assert ".env.secret" not in opted.files()


def test_manifest_txt_is_not_documentation() -> None:
    assert is_doc_file("README.md") and is_doc_file("docs/setup.txt")
    assert not is_doc_file("requirements.txt") and not is_doc_file("requirements-dev.txt")


# ------------------------------------------------------------------ fact slots
@pytest.mark.parametrize(
    ("fact", "ok"),
    [
        ("install | command | python app.py | 运行 app.py | README.md:14: python app.py", True),
        ("run | command | make run | 用 make run 启动 | Makefile:1: run:", True),
        ("run | command | python main.py | 启动 | README.md:14: python app.py", False),
        ("port | port | 5000 | 默认端口 5000 | app.py:14: app.run(port=5000)", True),
        ("port | port | 8080 | 默认端口 8080 | app.py:14: app.run(port=5000)", False),
        ("prereq | prereq | flask 3.0.0 | 需要 flask | requirements.txt:1: flask==3.0.0", True),
        ("prereq | wishful | flask | 需要 flask | requirements.txt:1: flask==3.0.0", False),
        ("prereq | prereq | flask | 需要 flask | requirements.txt:1: django==4", False),
    ],
)
def test_install_slots(repo: RepoView, fact: str, ok: bool) -> None:
    acc, rej = _store(repo, "install").add([parse_fact_str(fact)])
    assert (acc == 1) is ok, rej


def test_claim_tokens_must_be_grounded(repo: RepoView) -> None:
    st = _store(repo, "install")
    acc, rej = st.add(
        [
            parse_fact_str(
                "port | port | 5000 | 端口 5000，由 HOST_ADDR 决定 | app.py:14: app.run(port=5000)"
            )
        ]
    )
    assert acc == 0 and "HOST_ADDR" in rej[0][1][0]


def test_module_role_must_be_proven_inside_the_module(repo: RepoView) -> None:
    st = _store(repo, "overview")
    acc, _ = st.add(
        [
            parse_fact_str(
                "modules | module | shop | 订单存储 | app.py:3: from shop.store import list_orders"
            )
        ]
    )
    assert acc == 0
    acc, _ = st.add(
        [parse_fact_str("modules | module | shop | 订单存储 | shop/store.py:3: ORDERS = []")]
    )
    assert acc == 1


def test_datamodel_fields_attach_to_their_entity_block(repo: RepoView) -> None:
    st = _store(repo, "datamodel")
    acc, rej = st.add(
        [
            parse_fact_str(
                "fields | field | users.email | 邮箱非空 | db/schema.sql:3:   email TEXT NOT NULL"
            ),
            parse_fact_str(
                "entities | entity | users | 用户表 | db/schema.sql:1: CREATE TABLE users ("
            ),
        ]
    )
    assert acc == 2, rej  # entity sorted first within one call
    acc, rej = st.add(
        [
            parse_fact_str(
                "fields | field | users.user_id | 外键 | db/schema.sql:7:   user_id INTEGER REFERENCES users(id)"
            )
        ]
    )
    assert acc == 0 and "not inside the definition block" in rej[0][1][0]
    st.add(
        [
            parse_fact_str(
                "entities | entity | orders | 订单表 | db/schema.sql:5: CREATE TABLE orders ("
            )
        ]
    )
    acc, rej = st.add(
        [
            parse_fact_str(
                "relations | no_relation | orders | 无外键 | db/schema.sql:5: CREATE TABLE orders ("
            )
        ]
    )
    assert acc == 0 and "refuted" in rej[0][1][0]
    acc, _ = st.add(
        [
            parse_fact_str(
                "relations | relation | orders.user_id -> users.id | 订单属于用户 | db/schema.sql:7:   user_id INTEGER REFERENCES users(id)"
            )
        ]
    )
    assert acc == 1


# ------------------------------------------------------------------ store / conflicts / salvage
def test_retract_and_doc_code_conflict(repo: RepoView) -> None:
    (Path(repo.root) / "README.md").write_text(
        (Path(repo.root) / "README.md").read_text() + "\nOpen http://localhost:8000/orders\n"
    )
    repo._lines.clear()  # noqa: SLF001 - file changed under the cached view
    st = _store(repo, "install")
    st.add([parse_fact_str("port | port | 5000 | 默认端口 5000 | app.py:14: app.run(port=5000)")])
    st.add(
        [
            parse_fact_str(
                "verify | verify | http://localhost:8000/orders | 文档中的访问地址 | README.md:17: Open http://localhost:8000/orders"
            )
        ]
    )
    assert add_doc_code_conflicts(st) == 1
    conflict = [f for f in st.live() if f["slot"] == "conflict"][0]
    assert set(conflict["evidence"]) == {"README.md:17", "app.py:14"}
    doc_fact = [f for f in st.live() if f["slot"] == "verify"][0]
    st.retract(doc_fact)
    assert doc_fact not in st.live() and len(st.ok) == 3
    # an accepted 'wrong' finding with code evidence against a doc-only fact -> explicit conflict
    st2 = _store(repo, "install")
    st2.add(
        [
            parse_fact_str(
                "verify | verify | http://localhost:8000/orders | 访问地址 | README.md:17: Open http://localhost:8000/orders"
            )
        ]
    )
    fact = st2.live()[0]
    ev = parse_ev("app.py:14: app.run(port=5000)")
    assert make_conflict(st2, fact, [ev]) == 1


def test_salvage_degraded_provider_shapes() -> None:
    # shapes observed in recorded provider responses: flat $text runs with a one-key evidence dict
    degraded = [
        {"$text": "Dockerfile:1"},
        {"$text": "prereq"},
        {"$text": "python:3.9.10-slim"},
        {"$text": "Dockerfile 使用 python:3.9.10-slim 作为基础镜像。"},
        {"item": "Dockerfile:1: FROM python:3.9.10-slim"},
        {"$text": "store"},
        {"$text": "store"},
        {"$text": "postgresql"},
        {"$text": "存储为 PostgreSQL"},
        {"item": ["docker-compose.yml:16: image: postgres:11.5-alpine"]},
    ]
    out = salvage_facts(degraded)
    assert [(f["slot"], f["value"]) for f in out] == [
        ("prereq", "python:3.9.10-slim"),
        ("store", "postgresql"),
    ]
    assert out[0]["ev"] == ["Dockerfile:1: FROM python:3.9.10-slim"]
    nested = {
        "item": {"item": "fields: a not recorded\n", "$text": "relations: b\n"},
        "$text": "types: c",
    }
    assert salvage_strings([nested]) == ["fields: a not recorded", "relations: b", "types: c"]
    assert salvage_items(
        ["app.py:3 | test helper", {"$text": "x.py:1"}, {"$text": "docs only"}]
    ) == [
        {"key": "app.py:3", "reason": "test helper"},
        {"key": "x.py:1", "reason": "docs only"},
    ]
    assert parse_fact_str("a | b | c | d | f.py:1: q || g.py:2: r")["ev"] == [
        "f.py:1: q",
        "g.py:2: r",
    ]


# ------------------------------------------------------------------ routes
def test_route_literal_and_derived_parts(repo: RepoView) -> None:
    ok, bad = verify_routes(
        repo,
        [
            {
                "method": "GET",
                "path": "/orders",
                "method_ev": "app.py:8",
                "parts": ["/orders @ app.py:8"],
                "handler": "orders",
            },
            {
                "method": "POST",
                "path": "/orders",
                "method_ev": "app.py:8",
                "parts": ["/orders @ app.py:8"],
            },
            {
                "method": "GET",
                "path": "/v1/orders",
                "method_ev": "app.py:8",
                "parts": ["/orders @ app.py:8"],
            },
            {
                "method": "GET",
                "path": "/list-orders",
                "method_ev": "app.py:8",
                "parts": ["list-orders @ app.py:6 <= list_orders | kebab"],
            },
            {
                "method": "GET",
                "path": "/nope",
                "method_ev": "app.py:8",
                "parts": ["/nope @ app.py:8"],
                "handler": "ghost",
            },
        ],
    )
    assert [(r["method"], r["path"], r["handler"]) for r in ok] == [
        ("GET", "/orders", "orders"),
        ("GET", "/list-orders", None),
    ]
    reasons = {b["claimed"] + b["method"]: " ".join(b["reasons"]) for b in bad}
    assert "method POST" in reasons["/ordersPOST"]
    assert "!= joined parts" in reasons["/v1/ordersGET"]
    assert "not literally" in reasons["/nopeGET"]


def test_apply_ops() -> None:
    assert apply_ops("GetUserList", ["snake"]) == "get_user_list"
    assert apply_ops("ServeHTTPPost", ["strip_prefix:Serve", "upper"]) == "HTTPPOST"
    assert apply_ops("x", ["no_such_op"]) is None
