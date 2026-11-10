"""Round 25 class 5: a page on a large repository must end with a usable draft
inside its prompt-token cap, never an abort that throws all the work away."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_loop_fixtures import reply, tool_call
from agent_loop_script import (
    IDENTITY_FACTS,
    OVERVIEW_WRITER,
    ROUTE,
    _starts,
    demo_rules,
)
from test_agent_loop_pages import _orch

from agent_loop_fixtures import ScriptedModel


def _has_read(body: dict[str, Any]) -> bool:
    return any(t["function"]["name"] == "read_file" for t in body.get("tools") or [])


def _endless_reader(wrap: dict[str, Any]) -> Any:
    """An investigator that keeps reading (a huge repo) until it is told to wrap up."""

    def respond(turn: int, body: dict[str, Any]) -> dict[str, Any]:
        if _has_read(body):
            return reply([tool_call("read_file", {"path": "app.py"}, turn)])
        return wrap

    return respond


IDENTITY_WRAP = reply(
    [tool_call("record_facts", {"facts": IDENTITY_FACTS}, 0), tool_call("finish", {}, 1)]
)


def test_session_reports_what_is_left_of_the_page_cap(tmp_path: Path) -> None:
    orch = _orch(tmp_path, ScriptedModel(demo_rules()), page_prompt_cap=1000)
    s = orch.session
    s.start_page(1000)
    assert s.page_used() == 0 and s.page_remaining() == 1000
    s.stats.prompt_tokens += 300
    assert s.page_used() == 300 and s.page_remaining() == 700


def test_token_allowance_cuts_an_endless_shard_and_the_page_still_passes(tmp_path: Path) -> None:
    rules = demo_rules()
    rules.insert(0, (_starts("You are an Investigator", "Identity + stack"), _endless_reader(IDENTITY_WRAP)))
    orch = _orch(tmp_path, ScriptedModel(rules), page_prompt_cap=4000)
    res = orch.run_page("overview")
    assert res["status"] == "pass", res.get("aborted") or res["history"][-1]["accepted_findings"]
    assert res["stats"]["prompt_tokens"] < 4000
    assert any("shard" in r for r in res["log"]["budget"]["token_limited"])


def test_without_the_allowance_the_same_shard_would_have_blown_the_cap(tmp_path: Path) -> None:
    # Guard for the test above: the endless reader really does exceed the cap uncut.
    import pytest

    from repo_wiki.agent_loop.llm import BudgetExceeded
    from repo_wiki.agent_loop.tools import READ_TOOLS

    rules = demo_rules()
    rules.insert(0, (_starts("You are an Investigator", "Identity + stack"), _endless_reader(IDENTITY_WRAP)))
    orch = _orch(tmp_path, ScriptedModel(rules), page_prompt_cap=4000)
    orch.session.start_page(4000)
    with pytest.raises(BudgetExceeded):
        for _ in range(4):
            orch.runner.run("probe", "You are an Investigator", "Identity + stack", READ_TOOLS, 40, ["finish"])


def test_exploration_is_skipped_not_fatal_once_only_the_write_reserve_is_left(tmp_path: Path) -> None:
    rules = demo_rules()
    rules.insert(0, (_starts("You are an Investigator", "Identity + stack"), _endless_reader(IDENTITY_WRAP)))
    # The module shard is a huge reader too: with a small cap it gets skipped or cut.
    rules.insert(0, (_starts("You are an Investigator", "Module shard"), _endless_reader(reply([tool_call("finish", {}, 0)]))))
    orch = _orch(tmp_path, ScriptedModel(rules), page_prompt_cap=900)
    res = orch.run_page("overview")
    assert res["status"] != "aborted", res.get("aborted")
    b = res["log"]["budget"]
    assert b["skipped"] or b["token_limited"]
    assert res["page_draft"] and "demo-shop" in res["page_draft"]
    assert (tmp_path / "out" / "page-overview.draft.md").read_text(encoding="utf-8") == res["page_draft"]


def test_cap_hit_after_writing_returns_the_written_draft(tmp_path: Path) -> None:
    rules = demo_rules()
    # the writer's prompt is enormous: the audit call then hits the cap
    rules.insert(0, (_starts("You are the Writer of the page"), lambda t, b: reply(content=OVERVIEW_WRITER, prompt_tokens=10**6)))
    orch = _orch(tmp_path, ScriptedModel(rules), page_prompt_cap=5000)
    res = orch.run_page("overview")
    assert res["status"] == "aborted" and "page prompt-token cap" in res["aborted"]
    assert res["page"] == ""
    assert "demo-shop" in res["page_draft"]  # the writer's draft, not an empty page
    assert (tmp_path / "out" / "page-overview.draft.md").exists()


def test_cap_hit_before_writing_returns_a_program_rendered_draft_from_facts(tmp_path: Path) -> None:
    rules = demo_rules()
    # the identity shard records facts but its reply is enormous: everything after it aborts
    rules.insert(0, (
        _starts("You are an Investigator", "Identity + stack"),
        lambda t, b: {**IDENTITY_WRAP, "usage": {"prompt_tokens": 10**6, "completion_tokens": 1}},
    ))
    orch = _orch(tmp_path, ScriptedModel(rules), page_prompt_cap=5000)
    res = orch.run_page("overview")
    assert res["status"] == "aborted"
    assert res["page_draft"].startswith("# ") and len(res["facts"]) >= 1


def test_api_route_shard_on_a_huge_repo_is_cut_and_the_routes_it_found_survive(tmp_path: Path) -> None:
    rules = demo_rules()
    route_wrap = reply(
        [tool_call("record_routes", {"routes": [ROUTE]}, 0), tool_call("finish", {"notes": "ok"}, 1)]
    )
    rules.insert(0, (_starts("You are a Route Investigator"), _endless_reader(route_wrap)))
    orch = _orch(tmp_path, ScriptedModel(rules), page_prompt_cap=4000)
    res = orch.run_page("api")
    assert res["status"] != "aborted", res.get("aborted")
    assert res["stats"]["prompt_tokens"] < 4000
    assert any(r["path"] == "/orders" for r in res["routes"])
    assert "/orders" in (res["page"] or res["page_draft"])
    assert res["log"]["budget"]["token_limited"]


def test_api_cap_hit_keeps_verified_routes_in_the_draft(tmp_path: Path) -> None:
    rules = demo_rules()
    rules.insert(0, (_starts("You are the Writer."), lambda t, b: reply(content="x", prompt_tokens=10**6)))
    orch = _orch(tmp_path, ScriptedModel(rules), page_prompt_cap=5000)
    res = orch.run_page("api")
    assert res["status"] == "aborted"
    assert "/orders" in res["page_draft"]


def test_no_second_round_when_it_would_not_fit(tmp_path: Path) -> None:
    bad = OVERVIEW_WRITER + "\n\n另外它写入日志 [F99]。\n"
    rules = demo_rules(overview_writer=bad)
    orch = _orch(tmp_path, ScriptedModel(rules), page_prompt_cap=650)
    orch.cfg = orch.cfg.model_copy(update={"max_iters": 3})
    res = orch.run_page("overview")
    assert res["status"] == "failed", res.get("aborted")
    assert res["log"].get("budget_stopped_before_iter")
    assert res["page_draft"]
