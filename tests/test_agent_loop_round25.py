"""Round 25 (Nov 9 live acceptance): generic page-quality fixes, all offline.

1. generation-process text never reaches the reader page;
2. defaults are stated as defaults, auditor 'wrong' findings do not mint false conflicts, and a
   previous draft's [Fn] ids never point at other facts after a retraction;
3. reader essentials (.env file, listen port, start command) are required on the install page;
5. a page that runs out of its token budget keeps a usable partial draft (tested in
   test_agent_loop_round25_budget.py).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from repo_wiki.agent_loop import gates
from repo_wiki.agent_loop import inventory as inv
from repo_wiki.agent_loop.checklists import PAGES
from repo_wiki.agent_loop.evidence import default_overrides
from repo_wiki.agent_loop.fact_page import build_page_inventory
from repo_wiki.agent_loop.facts import FactStore, make_conflict
from repo_wiki.agent_loop.render import facts_block, render_tables
from repo_wiki.agent_loop.repo import RepoView
from repo_wiki.agent_loop.verifier import FactVerifier


def _fact(item: str, slot: str, value: str, ev: list[str], quotes: list[str], claim: str = "c"):
    return {
        "item": item,
        "slot": slot,
        "value": value,
        "claim": claim,
        "evidence": ev,
        "quotes": quotes,
    }


# ------------------------------------------------------------------ 1. process text
NOV9_FLASK_LEAK = (
    "模块 `src/routes`：未能确认其职责（两次尝试记录模块事实均被程序拒绝（提示 evidence 必须为 "
    "'FILE:LINE: exact quote' 形式），预算耗尽未能确认；src/routes/user.py 与 src/rout）。"
)


def test_unresolved_modules_render_without_the_generation_log() -> None:
    text = render_tables(
        "overview",
        [],
        {
            "src/routes/ (root files: user.py)": "modules: src/routes: 两次尝试记录模块事实均被程序拒绝，预算耗尽",
            "test": "role not established from the files inside it",
        },
    )
    assert "模块 `src/routes`：未能从源码确认其职责。" in text
    assert "模块 `test`：未能从源码确认其职责。" in text
    assert not gates.process_leak_issues(text)
    for bad in ("预算", "拒绝", "FILE:LINE", "role not established"):
        assert bad not in text


def test_process_leak_gate_flags_nov9_text_and_spares_domain_words() -> None:
    assert gates.process_leak_issues(NOV9_FLASK_LEAK)
    for leak in (
        "该模块的职责因预算耗尽未能确认。",
        "记录的 module 事实被校验器两次拒绝。",
        "以下内容来自已验证事实 F3。",
        "The auditor found no issue; budget exhausted.",
        "调用 record_facts 失败。",
    ):
        assert gates.process_leak_issues(leak), leak
    for fine in (
        "鉴权失败时请求被拒绝并返回 401。",
        "validate 中间件按 Joi 规则校验请求体。",
        "日志写入 `server.log`。",
        "未能从源码确认：auth",
        "限流器用于限制重复失败的请求。",
    ):
        assert not gates.process_leak_issues(fine), fine


def test_writer_prose_is_sanitised_of_process_lines() -> None:
    prose = "## 模块\n\n模块 A 处理路由 [F1]。\n" + NOV9_FLASK_LEAK + "\n模块 B 处理数据 [F2]。\n"
    clean, dropped = gates.strip_process_lines(prose)
    assert NOV9_FLASK_LEAK not in clean and dropped == [NOV9_FLASK_LEAK]
    assert "模块 A 处理路由 [F1]。" in clean and "模块 B 处理数据 [F2]。" in clean


# ------------------------------------------------------------------ 2. stale ids after retraction
def test_previous_draft_ids_are_remapped_and_retracted_lines_dropped() -> None:
    a = _fact("stack", "library", "Flask", ["requirements.txt:1"], ["Flask==1.1"])
    logging_f = _fact("stack", "library", "logging", ["src/config.py:20"], ["logging.basicConfig("])
    c = _fact("stack", "library", "setproctitle", ["requirements.txt:15"], ["setproctitle==1.1.10"])
    old = [a, logging_f, c]
    new = [a, c]  # logging retracted by the audit
    prose = "Web 框架 Flask [F1]。\n日志写入 `server.log` [F2]。\n依赖 setproctitle [F3]。\n组合 [F1, F3]。"
    out = gates.remap_prev_ids(prose, old, new)
    assert "Web 框架 Flask [F1]。" in out
    assert "server.log" not in out
    assert "依赖 setproctitle [F2]。" in out
    assert "组合 [F1, F2]。" in out


# ------------------------------------------------------------------ 2. defaults
def test_default_overrides_are_detected_in_common_languages() -> None:
    assert ("SERVICE_LOG", "server.log") in default_overrides(
        'filename=os.getenv("SERVICE_LOG", "server.log"),'
    )
    assert ("PORT", "3000") in default_overrides("port: process.env.PORT || 3000,")
    assert ("APP_ENV", "dev") in default_overrides('os.environ.get("APP_ENV", "dev")')
    assert ("HTTP_PORT", "8080") in default_overrides("      - ${HTTP_PORT:-8080}:8080")
    assert ("SERVER_PORT", "8080") in default_overrides(
        'ServerPort int `yaml:"server_port" env:"SERVER_PORT" envDefault:"8080"`'
    )
    assert default_overrides('LOG = "server.log"') == []


def _flask_repo(tmp_path: Path) -> RepoView:
    files = {
        "README.md": "# flask-api\n\nYou can check the logs in the `./server.log` file.\n",
        "src/config.py": (
            "import logging\nimport os\n"
            'PORT = os.getenv("APPLICATION_PORT", 3000)\n'
            "logging.basicConfig(\n"
            '    filename=os.getenv("SERVICE_LOG", "server.log"),\n'
            "    level=logging.DEBUG,\n)\n"
        ),
        "docker-compose.yml": (
            'version: "2"\nservices:\n  server:\n    env_file:\n      - .env\n'
            "    image: python:3.7\n    ports:\n      - 3000:3000\n"
            "    command: python src/server.py\n"
        ),
        "Makefile": "server.start:\n\tdocker-compose up server\n",
        "src/server.py": "server.run(host=config.HOST, port=config.PORT)\n",
    }
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return RepoView(tmp_path)


def test_verified_fact_from_a_default_is_marked_and_shown_to_the_writer(tmp_path: Path) -> None:
    repo = _flask_repo(tmp_path)
    store = FactStore(FactVerifier(repo, PAGES["install"]))
    acc, rej = store.add(
        [
            {
                "item": "config",
                "slot": "env",
                "value": "SERVICE_LOG",
                "claim": "日志文件名为 server.log",
                "ev": ['src/config.py:5: filename=os.getenv("SERVICE_LOG", "server.log"),'],
            }
        ]
    )
    assert acc == 1, rej
    f = store.live()[0]
    assert f["defaults"] == [["SERVICE_LOG", "server.log"]]
    assert "默认值" in facts_block(store.live(), []) and "SERVICE_LOG" in facts_block(store.live(), [])


def test_default_stated_as_fixed_behaviour_is_a_writer_issue() -> None:
    f = _fact(
        "config",
        "env",
        "SERVICE_LOG",
        ["src/config.py:5"],
        ['filename=os.getenv("SERVICE_LOG", "server.log"),'],
    )
    f["defaults"] = [["SERVICE_LOG", "server.log"]]
    bad = gates.default_wording_issues("日志通过 basicConfig 写入 `server.log` [F1]。", [f])
    assert bad and "server.log" in bad[0] and "SERVICE_LOG" in bad[0]
    assert not gates.needs_investigation(bad[0])
    ok = "日志默认写入 `server.log`，可由环境变量 `SERVICE_LOG` 覆盖 [F1]。"
    assert gates.default_wording_issues(ok, [f]) == []


def test_auditor_wrong_finding_without_a_competing_value_makes_no_conflict(tmp_path: Path) -> None:
    repo = _flask_repo(tmp_path)
    store = FactStore(FactVerifier(repo, PAGES["install"]))
    fact = _fact(
        "run",
        "service",
        "app",
        ["README.md:3"],
        ["You can check the logs in the `./server.log` file."],
    )
    store.ok.append(fact)
    # FastAPI Nov 9: '8000' vs 'localhost' and 'db' vs 'First, create .env' became conflicts
    evs = [{"file": "docker-compose.yml", "line": 3, "quote": "  server:"}]
    assert make_conflict(store, fact, evs) == 0
    port = _fact("port", "port", "8000", ["README.md:3"], ["runs on http://localhost:8000"])
    store.ok.append(port)
    assert make_conflict(store, port, [{"file": "docker-compose.yml", "line": 7, "quote": "ports:"}]) == 0
    # a real disagreement between a doc port and a code port is still kept as a conflict
    assert (
        make_conflict(
            store, port, [{"file": "docker-compose.yml", "line": 8, "quote": "- 3000:3000"}]
        )
        == 1
    )


def test_prompts_tell_writer_and_auditor_how_to_treat_defaults_and_equivalent_names() -> None:
    from repo_wiki.agent_loop import roles

    for text in (roles.ROLE_WRITER, roles.ROLE_API_WRITER):
        assert "默认" in text
    assert "local variable" in roles.ROLE_AUDITOR and "not a conflict" in roles.ROLE_AUDITOR


# ------------------------------------------------------------------ 3. reader essentials
def test_reader_essentials_find_env_file_port_and_start_command(tmp_path: Path) -> None:
    repo = _flask_repo(tmp_path)
    ess = inv.reader_essentials(repo)
    assert any(x["file"] == "docker-compose.yml" and ".env" in x["text"] for x in ess["env_file"])
    assert ess["port"] and ess["start"]


def test_compose_env_file_is_an_install_obligation(tmp_path: Path) -> None:
    repo = _flask_repo(tmp_path)
    d = build_page_inventory(repo, "install")
    assert any(k.startswith("docker-compose.yml:") and ".env" in str(v.get("text")) for k, v in d.oblig.items())


def test_install_page_without_env_file_fact_fails_the_essentials_gate(tmp_path: Path) -> None:
    repo = _flask_repo(tmp_path)
    ess = inv.reader_essentials(repo)
    facts = [
        _fact("port", "port", "3000", ["src/config.py:3"], ['PORT = os.getenv("APPLICATION_PORT", 3000)']),
        _fact("run", "command", "make server.start", ["Makefile:1"], ["server.start:"]),
    ]
    issues = gates.essentials_issues(facts, ess)
    assert len(issues) == 1 and ".env" in issues[0] and "docker-compose.yml:" in issues[0]
    assert gates.needs_investigation(issues[0])
    facts.append(
        _fact("config", "config_file", ".env", ["docker-compose.yml:4", "docker-compose.yml:5"], ["env_file:", "- .env"])
    )
    assert gates.essentials_issues(facts, ess) == []
    assert gates.essentials_issues([], ess) and len(gates.essentials_issues([], ess)) == 3


def test_config_files_are_rendered_by_the_program_on_the_install_page() -> None:
    facts = [
        _fact("config", "config_file", ".env", ["docker-compose.yml:5"], ["- .env"], "compose 的 server 服务从 .env 读取环境变量"),
        _fact("config", "env", "SERVICE_LOG", ["src/config.py:5"], ["x"], "日志文件名"),
    ]
    text = render_tables("install", facts)
    assert "配置文件 `.env`：compose 的 server 服务从 .env 读取环境变量 [F1]" in text
    assert "环境变量 `SERVICE_LOG`" in text


def test_essentials_absent_from_repo_are_not_required(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# x\n", encoding="utf-8")
    ess = inv.reader_essentials(RepoView(tmp_path))
    assert gates.essentials_issues([], ess) == []


def _unused(*_a: Any) -> None:  # keep imports referenced for linters
    return None


def test_config_file_named_by_compose_is_accepted_even_when_not_committed(tmp_path: Path) -> None:
    repo = _flask_repo(tmp_path)  # no .env in the repository (it is usually gitignored)
    store = FactStore(FactVerifier(repo, PAGES["install"]))
    acc, rej = store.add(
        [
            {
                "item": "config",
                "slot": "config_file",
                "value": ".env",
                "claim": "server 服务通过 env_file 读取 .env，仓库未提供该文件，需要自行创建",
                "ev": ["docker-compose.yml:4: env_file:", "docker-compose.yml:5: - .env"],
            },
            {
                "item": "config",
                "slot": "config_file",
                "value": "config/missing.yaml",
                "claim": "配置文件",
                "ev": ["docker-compose.yml:4: env_file:"],
            },
        ]
    )
    assert acc == 1, rej
    assert "does not exist" in "; ".join(rej[0][1])


def test_loop_strips_process_lines_from_the_writer_before_publishing(tmp_path: Path) -> None:
    from repo_wiki.agent_loop.llm import ScriptedClient
    from repo_wiki.agent_loop.orchestrator import AgentLoopOrchestrator
    from repo_wiki.core.config import AgentLoopConfig
    from tests.agent_loop_fixtures import ScriptedModel, make_demo_repo
    from tests.agent_loop_script import OVERVIEW_WRITER, demo_rules

    root = make_demo_repo(tmp_path / "repo")
    leak = "模块 `shop` 的职责因预算耗尽未能确认（记录的 module 事实被校验器两次拒绝）。"
    writer = OVERVIEW_WRITER.replace("## 模块职责", leak + "\n\n## 模块职责")
    conf = AgentLoopConfig(cassette_mode="off", max_iters=1)
    orch = AgentLoopOrchestrator(
        root, conf, tmp_path / "out", client=ScriptedClient(ScriptedModel(demo_rules(overview_writer=writer)))
    )
    res = orch.run_page("overview")
    assert res["status"] == "pass", res["history"][-1]["accepted_findings"]
    assert leak not in res["page"] and "预算" not in res["page"]
    assert res["history"][0]["dropped_process_lines"] == [leak]
