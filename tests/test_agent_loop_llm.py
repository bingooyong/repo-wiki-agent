"""Agent-loop model plumbing: HTTP client error policy, cassette, caps, tool runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from repo_wiki.agent_loop.llm import (
    BudgetExceeded,
    Cassette,
    CassetteMiss,
    CassetteVersionMismatch,
    ChatSettings,
    LLMSession,
    NoNetworkClient,
    OpenAICompatibleClient,
    ProviderError,
    ScriptedClient,
    request_key,
)
from repo_wiki.agent_loop.repo import RepoView
from repo_wiki.agent_loop.roles import FINISH, RECORD_FACTS
from repo_wiki.agent_loop.runner import AgentRunner
from repo_wiki.agent_loop.tools import READ_TOOLS, ToolBox
from tests.agent_loop_fixtures import make_demo_repo, reply, tool_call

SECRET = "unit-test-placeholder-credential-0123"
OK_BODY = {
    "choices": [{"message": {"role": "assistant", "content": "hi"}}],
    "usage": {"prompt_tokens": 7},
}


def _client(
    handler: Any, monkeypatch: pytest.MonkeyPatch, retries: int = 2
) -> tuple[OpenAICompatibleClient, list[float]]:
    monkeypatch.setenv("AGENT_LOOP_TEST_KEY", SECRET)
    sleeps: list[float] = []
    client = OpenAICompatibleClient(
        "https://llm.invalid/v1",
        "AGENT_LOOP_TEST_KEY",
        max_retries=retries,
        sleep=sleeps.append,
        transport=httpx.MockTransport(handler),
    )
    return client, sleeps


def test_client_sends_bearer_and_returns_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=OK_BODY)

    client, _ = _client(handler, monkeypatch)
    assert client.complete({"model": "m", "messages": []})["choices"]
    assert seen[0].url.path == "/v1/chat/completions"
    assert seen[0].headers["authorization"] == f"Bearer {SECRET}"


def test_quota_exhaustion_is_fatal_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(
            429, json={"base_resp": {"status_code": 2056, "status_msg": "usage limit exceeded"}}
        )

    client, sleeps = _client(handler, monkeypatch, retries=5)
    with pytest.raises(ProviderError) as exc:
        client.complete({"model": "m"})
    assert len(calls) == 1 and sleeps == []
    assert "2056" in str(exc.value) and SECRET not in str(exc.value)


def test_fatal_code_inside_http_200_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(
            200, json={"base_resp": {"status_code": 1008, "status_msg": "insufficient balance"}}
        )

    client, _ = _client(handler, monkeypatch, retries=4)
    with pytest.raises(ProviderError):
        client.complete({"model": "m"})
    assert len(calls) == 1


def test_transient_errors_are_retried_a_bounded_number_of_times(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(500, json={"error": {"message": "overloaded"}})
        return httpx.Response(200, json=OK_BODY)

    client, sleeps = _client(handler, monkeypatch, retries=2)
    assert client.complete({"model": "m"})["choices"]
    assert len(calls) == 3 and len(sleeps) == 2

    calls.clear()

    def always_429(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429, json={"error": {"message": "rate limited, slow down"}})

    client, _ = _client(always_429, monkeypatch, retries=2)
    with pytest.raises(ProviderError):
        client.complete({"model": "m"})
    assert len(calls) == 3  # rate limit (not quota): retried, but bounded — no 429 loop


def test_missing_key_is_a_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENT_LOOP_NO_SUCH_KEY", raising=False)
    client = OpenAICompatibleClient("https://llm.invalid/v1", "AGENT_LOOP_NO_SUCH_KEY")
    with pytest.raises(ProviderError, match="AGENT_LOOP_NO_SUCH_KEY"):
        client.complete({})


# ------------------------------------------------------------------ cassette
def _session(
    tmp_path: Path, mode: str, client: Any, version: str = "v1", fp: str = "repo1", **kw: Any
) -> LLMSession:
    cas = Cassette(tmp_path / "cas", mode, version, fp)
    return LLMSession(client, ChatSettings("m"), cas, ledger_path=tmp_path / "ledger.jsonl", **kw)


def test_request_key_is_canonical() -> None:
    assert request_key({"a": 1, "b": [1, 2]}) == request_key({"b": [1, 2], "a": 1})
    assert request_key({"a": 1}) != request_key({"a": 2})


def test_record_then_replay_without_network(tmp_path: Path) -> None:
    client = ScriptedClient(lambda body: reply(content="answer"))
    s = _session(tmp_path, "record", client)
    msgs = [{"role": "user", "content": "q"}]
    assert s.chat(msgs, [], "r")["choices"][0]["message"]["content"] == "answer"
    assert s.stats.live_calls == 1
    ledger = [json.loads(x) for x in (tmp_path / "ledger.jsonl").read_text().splitlines()]
    assert ledger[0]["role"] == "r" and "content" not in ledger[0]
    replay = _session(tmp_path, "replay", NoNetworkClient())
    assert replay.chat(msgs, [], "r")["choices"][0]["message"]["content"] == "answer"
    assert replay.stats.live_calls == 0 and replay.stats.calls == 1
    with pytest.raises(CassetteMiss):
        replay.chat([{"role": "user", "content": "other"}], [], "r")


def test_provider_errors_are_never_recorded(tmp_path: Path) -> None:
    def broken(body: dict[str, Any]) -> dict[str, Any]:
        return {"base_resp": {"status_code": 2056, "status_msg": "quota"}}

    s = _session(tmp_path, "record", ScriptedClient(broken))
    with pytest.raises(ProviderError):
        s.chat([{"role": "user", "content": "q"}], [], "r")
    assert not (tmp_path / "cas" / "cassette.jsonl").exists()


def test_resume_and_replay_refuse_a_cassette_from_other_code_or_repo(tmp_path: Path) -> None:
    s = _session(tmp_path, "record", ScriptedClient(lambda b: reply(content="x")))
    s.chat([{"role": "user", "content": "q"}], [], "r")
    for mode in ("resume", "replay"):
        with pytest.raises(CassetteVersionMismatch):
            Cassette(tmp_path / "cas", mode, "v2", "repo1")
        with pytest.raises(CassetteVersionMismatch):
            Cassette(tmp_path / "cas", mode, "v1", "repo2")
    assert Cassette(tmp_path / "cas", "resume", "v1", "repo1").get(
        request_key(s.body([{"role": "user", "content": "q"}], []))
    )
    rotated = Cassette(tmp_path / "cas", "record", "v2", "repo1")
    assert rotated.rotated == "cassette.v1.jsonl" and rotated.rows == {}
    assert (tmp_path / "cas" / "cassette.v1.jsonl").exists()


def test_prompt_caps_abort(tmp_path: Path) -> None:
    client = ScriptedClient(lambda body: reply(content="x", prompt_tokens=60))
    s = _session(tmp_path, "off", client, global_prompt_cap=1000)
    s.start_page(100)
    s.chat([{"role": "user", "content": "1"}], [], "r")
    s.chat([{"role": "user", "content": "2"}], [], "r")
    with pytest.raises(BudgetExceeded, match="page"):
        s.chat([{"role": "user", "content": "3"}], [], "r")
    s.start_page(None)
    s.global_prompt_cap = 120
    with pytest.raises(BudgetExceeded, match="global"):
        s.chat([{"role": "user", "content": "4"}], [], "r")


def test_tools_key_omitted_for_writer_calls(tmp_path: Path) -> None:
    s = _session(tmp_path, "off", ScriptedClient(lambda b: reply(content="x")))
    assert "tools" not in s.body([], [])
    assert "tools" in s.body([], [FINISH])


# ------------------------------------------------------------------ runner
def _runner(
    tmp_path: Path, responses: list[dict[str, Any]]
) -> tuple[AgentRunner, list[dict[str, Any]]]:
    seen: list[dict[str, Any]] = []

    def respond(body: dict[str, Any]) -> dict[str, Any]:
        seen.append(json.loads(json.dumps(body)))  # the runner keeps appending to its messages
        return responses[min(len(seen) - 1, len(responses) - 1)]

    root = make_demo_repo(tmp_path / "repo")
    session = _session(tmp_path, "off", ScriptedClient(respond))
    return AgentRunner(ToolBox(RepoView(root)), session), seen


def _tool_msgs(body: dict[str, Any]) -> list[str]:
    return [m["content"] for m in body["messages"] if m["role"] == "tool"]


def test_runner_reads_files_rejects_unknown_tools_and_bad_json(tmp_path: Path) -> None:
    bad_json = {
        "id": "c9",
        "type": "function",
        "function": {"name": "finish", "arguments": "{oops"},
    }
    runner, seen = _runner(
        tmp_path,
        [
            reply(
                [
                    tool_call("read_file", {"path": "app.py", "start": 13, "end": 14}, 0),
                    tool_call("rm_rf", {}, 1),
                ]
            ),
            reply([bad_json]),
            reply([tool_call("finish", {}, 2)]),
        ],
    )
    res = runner.run("t", "sys", "user", READ_TOOLS + [FINISH], 6, ["finish"])
    outs = _tool_msgs(seen[1])
    assert "app.run(port=5000)" in outs[0]
    assert outs[1].startswith("ERROR: unknown tool rm_rf")
    assert "not valid JSON" in _tool_msgs(seen[2])[-1]
    assert res.first("finish") == {} and not res.exhausted


def test_runner_finish_guard_refuses_once(tmp_path: Path) -> None:
    runner, seen = _runner(tmp_path, [reply([tool_call("finish", {}, i)]) for i in range(3)])
    res = runner.run(
        "t",
        "sys",
        "user",
        [FINISH],
        5,
        ["finish"],
        finish_check=lambda subs, args: "finish refused once: x",
    )
    assert _tool_msgs(seen[1])[-1] == "finish refused once: x"
    assert len(seen) == 2 and res.first("finish") == {}


def test_runner_pending_rejections_block_finish_once(tmp_path: Path) -> None:
    runner, seen = _runner(
        tmp_path,
        [
            reply([tool_call("record_facts", {"facts": ["bad"]}, 0), tool_call("finish", {}, 1)]),
            reply([tool_call("finish", {}, 2)]),
        ],
    )
    res = runner.run(
        "t",
        "sys",
        "user",
        [RECORD_FACTS, FINISH],
        5,
        ["finish"],
        handlers={"record_facts": lambda args: ("accepted 0/1; REJECTED", 1)},
    )
    assert "finish refused once: 1 items" in _tool_msgs(seen[1])[-1]
    assert res.first("finish") == {} and len(seen) == 2


def test_runner_wrap_up_uses_output_tools_and_json_fallback(tmp_path: Path) -> None:
    runner, seen = _runner(
        tmp_path,
        [
            reply([tool_call("list_dir", {"path": "."}, 0)]),
            reply([tool_call("list_dir", {"path": "shop"}, 1)]),
            reply(content='Here: {"unresolved": ["port: none"]}'),
        ],
    )
    res = runner.run("t", "sys", "user", READ_TOOLS + [FINISH], 2, ["finish"])
    assert res.exhausted
    assert [t["function"]["name"] for t in seen[-1]["tools"]] == ["finish"]
    assert res.first("finish") == {"unresolved": ["port: none"]}


def test_writer_strips_think_blocks(tmp_path: Path) -> None:
    runner, seen = _runner(tmp_path, [reply(content="<think>secret plan</think>\n## 页面\n正文")])
    assert runner.write("w", "sys", "user") == "## 页面\n正文"
    assert "tools" not in seen[0]
