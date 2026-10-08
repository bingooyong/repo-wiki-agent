"""Offline end-to-end runs of the agent loop with a scripted model (no network, no live calls)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from repo_wiki.agent_loop.__main__ import main as cli_main
from repo_wiki.agent_loop.llm import ScriptedClient
from repo_wiki.agent_loop.orchestrator import AgentLoopOrchestrator
from repo_wiki.core.config import AgentLoopConfig, RepoWikiConfig
from tests.agent_loop_fixtures import ScriptedModel, make_demo_repo, reply, tool_call
from tests.agent_loop_script import AUDIT_OK, demo_rules


def _orch(tmp_path: Path, model: Any, mode: str = "record", **cfg: Any) -> AgentLoopOrchestrator:
    root = tmp_path / "repo"
    if not root.exists():
        make_demo_repo(root)
    conf = AgentLoopConfig(
        cassette_mode=mode, cassette_dir=str(tmp_path / "cassette"), max_iters=1, **cfg
    )
    client = ScriptedClient(model) if model is not None else None
    return AgentLoopOrchestrator(root, conf, tmp_path / "out", client=client)


def test_overview_and_api_pages_pass_and_render_the_contract(tmp_path: Path) -> None:
    orch = _orch(tmp_path, ScriptedModel(demo_rules()))
    over = orch.run_page("overview")
    api = orch.run_page("api")
    assert over["status"] == "pass", over["history"][-1]["accepted_findings"]
    assert api["status"] == "pass", api["history"][-1]["accepted_findings"]
    page = over["page"]
    assert page.startswith("# 项目概览\n\n## 目录\n\n1. ")
    assert "<cite>README.md:1</cite>" in page and "[F" not in page
    assert "模块 `shop`" in page and "flowchart" in page
    assert "接口 `GET /orders`，处理函数 `orders`。 <cite>app.py:8</cite>" in api["page"]
    assert [(r["method"], r["path"]) for r in api["routes"]] == [("GET", "/orders")]
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert report["summary"]["overview"]["status"] == "pass"
    assert report["profile"]["frameworks"] == [{"name": "Flask"}]
    assert (tmp_path / "out" / "page-api.md").read_text() == api["page"]


def test_record_then_replay_is_byte_identical_and_offline(tmp_path: Path) -> None:
    rec = _orch(tmp_path, ScriptedModel(demo_rules()))
    recorded = {p: rec.run_page(p)["page"] for p in ("overview", "api")}
    live = rec.session.stats.live_calls
    assert live > 0
    replay = _orch(tmp_path, None, mode="replay")  # NoNetworkClient: any miss raises
    replayed = {p: replay.run_page(p) for p in ("overview", "api")}
    assert {p: r["page"] for p, r in replayed.items()} == recorded
    assert replay.session.stats.live_calls == 0
    assert replay.session.stats.calls == live


def test_replay_and_resume_are_refused_after_a_code_or_repo_change(tmp_path: Path) -> None:
    rec = _orch(tmp_path, ScriptedModel(demo_rules()))
    rec.run_page("overview")
    (tmp_path / "repo" / "shop" / "new.py").write_text("X = 1\n", encoding="utf-8")
    out = tmp_path / "cli-out"
    for mode in ("replay", "resume"):
        rc = cli_main(
            [
                str(tmp_path / "repo"),
                "--pages",
                "overview",
                "--out",
                str(out),
                "--cassette-mode",
                mode,
                "--cassette-dir",
                str(tmp_path / "cassette"),
            ]
        )
        assert rc == 2


def test_tool_markup_every_time_fails_the_page_and_ships_nothing(tmp_path: Path) -> None:
    junk = '<minimax:tool_call><invoke name="x"></invoke></minimax:tool_call>\n## 页面\n正文 [F1]'
    model = ScriptedModel(demo_rules(overview_writer=junk))
    res = _orch(tmp_path, model).run_page("overview")
    assert res["status"] == "failed" and res["page"] == ""
    assert res["iterations"] == 2  # max_iters=1 -> first draft + one rework
    assert any("markup" in x for x in res["history"][-1]["accepted_findings"])
    writer_calls = [c for c in model.calls if c.startswith("rule3:")]
    assert len(writer_calls) == 4  # one clean rewrite per draft, never an endless loop


def test_auditor_wrong_finding_retracts_the_fact_and_recloses_the_module(tmp_path: Path) -> None:
    wrong = reply(
        [
            tool_call(
                "submit_audit",
                {
                    "findings": [
                        {
                            "type": "wrong",
                            "fact_id": "F7",
                            "detail": "the root module is the HTTP layer, not only app creation",
                            "ev": ['app.py:8: @app.route("/orders", methods=["GET"])'],
                        }
                    ],
                    "verdict": "fix",
                },
            )
        ]
    )
    rules = demo_rules(overview_audit=wrong)
    closer_hits: list[str] = []

    def closer(turn: int, body: dict[str, Any]) -> dict[str, Any]:
        closer_hits.append(body["messages"][1]["content"])
        fact = 'modules | module | . | 根目录的 app.py 注册 HTTP 路由 | app.py:8: @app.route("/orders", methods=["GET"])'
        return reply([tool_call("record_facts", {"facts": [fact]}, 0), tool_call("finish", {}, 1)])

    rules.insert(
        0, (lambda s, u: s.startswith("You are an Investigator") and "Module closer" in u, closer)
    )
    res = _orch(tmp_path, ScriptedModel(rules)).run_page("overview")
    assert res["history"][0]["retracted"] == 1
    assert res["retracted"][0]["value"] == "." and res["retracted"][0]["evidence"] == ["app.py:5"]
    assert closer_hits and "retracted by the audit" in closer_hits[0]
    # the re-closed fact was recorded (and, in this script, disputed again by the auditor)
    assert res["retracted"][1]["evidence"] == ["app.py:8"]
    assert res["status"] == "failed" and res["page"] == ""


def test_wrong_finding_without_fact_id_is_refused_once(tmp_path: Path) -> None:
    no_id = {"type": "wrong", "detail": "x", "ev": ["app.py:14: app.run(port=5000)"]}
    seen: list[str] = []

    def audit(turn: int, body: dict[str, Any]) -> dict[str, Any]:
        seen.append(str(body["messages"][-1].get("content")))
        return reply([tool_call("submit_audit", {"findings": [no_id], "verdict": "fix"}, turn)])

    rules = demo_rules()
    rules.insert(0, (lambda s, u: s.startswith("You are the Auditor"), audit))
    res = _orch(tmp_path, ScriptedModel(rules)).run_page("overview")
    assert any("submit refused once" in s for s in seen)
    assert res["history"][0]["retracted"] == 0


def test_provider_outage_aborts_the_run_without_more_calls(tmp_path: Path) -> None:
    from repo_wiki.agent_loop.llm import ProviderError

    calls: list[int] = []

    def down(body: dict[str, Any]) -> dict[str, Any]:
        calls.append(1)
        raise ProviderError("provider error: HTTP 429 code=2056 usage limit exceeded")

    orch = _orch(tmp_path, down)
    first = orch.run_page("overview")
    second = orch.run_page("install")
    assert first["status"] == second["status"] == "aborted-provider"
    assert len(calls) == 1
    assert not (tmp_path / "cassette" / "cassette.jsonl").exists()


def test_page_budget_overrun_aborts_only_that_page(tmp_path: Path) -> None:
    model = ScriptedModel(demo_rules())
    orch = _orch(tmp_path, model, page_prompt_cap=250)
    res = orch.run_page("overview")
    assert res["status"] == "aborted" and "page prompt-token cap" in res["aborted"]
    orch.cfg = orch.cfg.model_copy(update={"page_prompt_cap": 10**9})
    assert orch.run_page("api")["status"] == "pass"


def test_unresolved_checklist_item_fails_the_page(tmp_path: Path) -> None:
    rules = demo_rules()
    unresolved = reply(
        [
            tool_call("record_facts", {"facts": []}, 0),
            tool_call(
                "finish",
                {
                    "covered_by_routes": ["routes"],
                    "unresolved": ["auth: unknown", "conventions: unknown", "server: unknown"],
                },
                1,
            ),
        ]
    )
    rules.insert(
        0,
        (
            lambda s, u: s.startswith("You are the Investigator for the non-route facts"),
            lambda t, b: unresolved,
        ),
    )
    res = _orch(tmp_path, ScriptedModel(rules)).run_page("api")
    assert res["status"] == "failed" and res["page"] == ""
    assert any("checklist items unresolved" in x for x in res["history"][-1]["accepted_findings"])


def test_agent_loop_is_off_by_default() -> None:
    cfg = RepoWikiConfig()
    assert cfg.agent_loop.enabled is False
    assert cfg.agent_loop.allow_globs == []
    assert set(cfg.agent_loop.page_map.values()) == {"overview", "install", "datamodel", "api"}


def test_audit_ok_constant_is_a_submit() -> None:
    assert AUDIT_OK["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "submit_audit"


def test_cli_rejects_unknown_page_types(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        cli_main([str(tmp_path), "--pages", "routes", "--out", str(tmp_path / "o")])
