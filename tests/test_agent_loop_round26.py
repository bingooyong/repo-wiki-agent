"""Round 26 (Nov 10 live acceptance, stages 1-4): loop-side false alarms, budget order on large
repositories, and reader essentials for install / datamodel pages. Offline, generic."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from repo_wiki.agent_loop import gates
from repo_wiki.agent_loop import inventory as inv
from repo_wiki.agent_loop.repo import RepoView


def _repo(tmp: Path, files: dict[str, str]) -> RepoView:
    root = tmp / "repo"
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return RepoView(root)


def _fact(item: str, slot: str, value: str, claim: str = "c", quotes: list[str] | None = None) -> dict[str, Any]:
    return {"item": item, "slot": slot, "value": value, "claim": claim, "evidence": ["x:1"], "quotes": quotes or [value]}


# ------------------------------------------------------------------ ER diagram gate
FLASK_DM = (
    "## 实体关系\n\n`user` 表没有其他实体，模型中不存在指向其他实体的外键或引用列。<cite>a</cite>\n\n"
    "`user` 表的复合主键由 `first_name` 与 `last_name` 组成。<cite>b</cite>\n"
)
GO_DM = "## 关系\n\n`album` 表的主键是 `id` 列。<cite>a</cite>\n"
REL_DM = "## 关系\n\n`token.user` 引用 `User` 集合（references User），一个用户有多个 token。<cite>a</cite>\n"


def _er(md: str, tmp: Path, **kw: Any) -> list[str]:
    return [i for i in gates.existing_gate_issues("datamodel", md, tmp, **kw) if "ER_MERMAID" in i]


def test_no_er_diagram_needed_when_the_page_states_there_are_no_relations(tmp_path: Path) -> None:
    assert not _er(FLASK_DM, tmp_path)  # Flask datamodel, Nov 10
    assert not _er(GO_DM, tmp_path)  # Go datamodel: a heading '关系' alone is not a relation claim


def test_er_diagram_still_required_when_relations_are_described(tmp_path: Path) -> None:
    assert _er(REL_DM, tmp_path)


def test_er_requirement_follows_verified_relation_facts_when_known(tmp_path: Path) -> None:
    assert not _er(REL_DM, tmp_path, has_relations=False)
    assert _er(GO_DM, tmp_path, has_relations=True)


def test_final_strict_verifier_uses_the_same_relation_reading() -> None:
    from repo_wiki.verifier.qoder_strict_verifier import page_asserts_relations

    assert not page_asserts_relations(FLASK_DM) and not page_asserts_relations(GO_DM)
    assert page_asserts_relations(REL_DM)


# ------------------------------------------------------------------ route-site noise
NODE_APP = (
    "const express = require('express');\n"
    "const app = express();\n"
    "app.use(helmet());\n"
    "app.use(express.json());\n"
    "app.use(errorHandler);\n"
    "app.use(cors());\n"
    "app.options('*', cors());\n"
    "app.use('/v1', routes);\n"
    "module.exports = app;\n"
)
NODE_MODEL = "const tokenSchema = mongoose.Schema(\n  {\n    token: {\n      type: String,\n    },\n  },\n);\n"
NODE_ROUTE = (
    "router\n  .route('/:userId')\n  .get(auth('getUsers'), userController.getUser)\n"
    "  .patch(auth('manageUsers'), userController.updateUser);\n"
)
# the Nov 10 node mechanism agent proposed these call-site patterns (two are far too broad)
NODE_EXTRA = [
    r"(?m)^\s*app\.(use|get|post|put|patch|delete|options|all)\s*\(",
    r"(?m)^\s*router\.use\(route\.path, route\.route\);|^\s*\{\s*$|^\s*path:\s*'/",
    r"(?m)^\s*\.route\(|^\s*\.(get|post|put|patch|delete)\(",
]


def test_middleware_and_model_lines_are_not_route_obligations(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"src/app.js": NODE_APP, "src/models/token.model.js": NODE_MODEL, "src/routes/user.route.js": NODE_ROUTE})
    sites = inv.find_sites(repo, NODE_EXTRA)
    lines = {(f, ln) for f, ln in sites}
    for ln in (3, 4, 5, 6):  # helmet / json / errorHandler / cors middleware
        assert ("src/app.js", ln) not in lines, ln
    assert not any(f == "src/models/token.model.js" for f, _ in lines)
    assert ("src/app.js", 7) in lines  # app.options('*', cors()) is a route
    assert ("src/app.js", 8) in lines  # mount with a path literal
    assert ("src/routes/user.route.js", 3) in lines  # chained .get( verb registration


# ------------------------------------------------------------------ budget order
def test_essential_step_keeps_its_share_while_exploration_is_throttled() -> None:
    from repo_wiki.agent_loop.runner import PageBudget

    class S:
        page_prompt_cap = 1000
        used = 0

        def page_remaining(self) -> int:
            return 1000 - self.used

    s = S()
    pb = PageBudget(s)
    pb.hold("facts", 0.15)
    s.used = 1000 - pb.reserve - pb.held["facts"]  # exploration spent everything it was allowed
    assert pb.allowance(5) == 0  # optional exploration is now skipped ...
    assert pb.allowance(1, essential="facts") >= 150  # ... but the essential facts step still runs


def test_api_facts_step_runs_even_when_route_shards_exhaust_the_page(tmp_path: Path) -> None:
    from agent_loop_fixtures import ScriptedModel, reply, tool_call
    from agent_loop_script import ROUTE, _starts, demo_rules
    from test_agent_loop_pages import _orch

    def endless(turn: int, body: dict[str, Any]) -> dict[str, Any]:
        if any(t["function"]["name"] == "read_file" for t in body.get("tools") or []):
            return reply([tool_call("read_file", {"path": "app.py"}, turn)], prompt_tokens=600)
        return reply([tool_call("record_routes", {"routes": [ROUTE]}, 0), tool_call("finish", {"notes": "ok"}, 1)])

    from agent_loop_fixtures import make_demo_repo

    root = make_demo_repo(tmp_path / "repo")
    for i in range(8):  # a "large" repository: many route files -> many route shards (probe had 11)
        (root / f"views{i}.py").write_text(
            "from app import app\n\n\n" + "".join(
                f'@app.route("/r{i}/{j}", methods=["GET"])\ndef h{i}_{j}():\n    return "x"\n\n\n' for j in range(12)
            ),
            encoding="utf-8",
        )
    rules = demo_rules()
    rules.insert(0, (_starts("You are a Route Investigator"), endless))
    orch = _orch(tmp_path, ScriptedModel(rules), page_prompt_cap=12000, budgets={"shard_lines": 40})
    res = orch.run_page("api")
    skipped = res["log"]["budget"]["skipped"]
    assert "api-facts" not in skipped, skipped
    assert any(f["item"] == "server" for f in res["facts"])


# ------------------------------------------------------------------ install essentials
def test_install_essentials_include_migrations_and_dev_script(tmp_path: Path) -> None:
    repo = _repo(
        tmp_path,
        {
            "package.json": '{\n  "scripts": {\n    "start": "pm2 start ecosystem.config.json",\n    "dev": "nodemon src/index.js"\n  }\n}\n',
            "README.md": "# x\n\n```bash\nyarn dev\n```\n",
            "Dockerfile": "FROM python:3.9\nCMD alembic upgrade head && uvicorn app.main:app\n",
            "alembic.ini": "[alembic]\n",
        },
    )
    ess = inv.reader_essentials(repo)
    assert ess["migrate"] and ess["dev"]


def test_install_page_without_migration_or_dev_command_fails(tmp_path: Path) -> None:
    ess = {"env_file": [], "port": [], "start": [], "migrate": [{"file": "Dockerfile", "line": 2, "text": "alembic upgrade head"}],
           "dev": [{"file": "package.json", "line": 4, "text": '"dev": "nodemon src/index.js"'}]}
    facts = [_fact("run", "command", "uvicorn app.main:app")]
    issues = gates.essentials_issues(facts, ess)
    assert any("migration" in i for i in issues) and any("dev" in i for i in issues)
    facts += [_fact("run", "command", "alembic upgrade head"), _fact("run", "command", "yarn dev")]
    assert not gates.essentials_issues(facts, ess)


def test_port_fact_must_give_the_default_number(tmp_path: Path) -> None:
    ess = {"env_file": [], "port": [{"file": "config.go", "line": 1, "text": "ServerPort int `envDefault:\"8080\"`"}], "start": []}
    assert gates.essentials_issues([_fact("port", "port", "server_port")], ess)  # Go install: no number
    assert not gates.essentials_issues([_fact("port", "port", "8080")], ess)


def test_migration_and_dev_are_not_required_when_the_repo_has_none(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"main.go": "package main\nfunc main() {}\n", "README.md": "# x\n\n```\ngo run .\n```\n"})
    ess = inv.reader_essentials(repo)
    assert not ess["migrate"] and not ess["dev"]


# ------------------------------------------------------------------ datamodel essentials
USER_MODEL = (
    "const userSchema = mongoose.Schema(\n"
    "  {\n"
    "    name: {\n      type: String,\n      required: true,\n    },\n"
    "    password: {\n      type: String,\n      required: true,\n      minlength: 8,\n      private: true,\n    },\n"
    "    role: {\n      type: String,\n      enum: roles,\n      default: 'user',\n    },\n"
    "  },\n"
    "  {\n    timestamps: true,\n  }\n"
    ");\n"
    "const User = mongoose.model('User', userSchema);\n"
)
GO_ENTITY = {
    "internal/entity/album.go": "package entity\n\ntype Album struct {\n\tID string `json:\"id\"`\n}\n",
    "internal/entity/user.go": "package entity\n\n// User represents a user.\ntype User struct {\n\tID string\n}\n",
    "migrations/1_init.up.sql": "CREATE TABLE album (\n  id VARCHAR PRIMARY KEY,\n  created_at TIMESTAMP NOT NULL\n);\n",
}


def test_datamodel_essentials_find_fields_timestamps_enums(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"src/models/user.model.js": USER_MODEL})
    ess = inv.datamodel_essentials(repo)
    assert {"name", "password", "role"} <= {x["field"] for x in ess["fields"]}
    assert ess["timestamps"] and ess["enums"]


def test_datamodel_page_missing_a_declared_field_timestamps_or_enum_fails(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"src/models/user.model.js": USER_MODEL})
    ess = inv.datamodel_essentials(repo)
    facts = [_fact("fields", "field", "User.name"), _fact("fields", "field", "User.role")]
    issues = gates.datamodel_essentials_issues(facts, ess)
    joined = " ".join(issues)
    assert "password" in joined and "timestamps" in joined and "enum" in joined
    facts = [
        _fact("fields", "field", "User.name"),
        _fact("fields", "field", "User.password", "required, minlength 8, private: true"),
        _fact("fields", "field", "User.role", "enum: roles, default 'user'"),
        _fact("fields", "field", "User.createdAt", "timestamps: true adds createdAt/updatedAt"),
        _fact("relations", "no_relation", "User"),
    ]
    assert not gates.datamodel_essentials_issues(facts, ess)


def test_types_in_entity_dirs_must_be_classified_and_relation_status_stated(tmp_path: Path) -> None:
    repo = _repo(tmp_path, GO_ENTITY)
    ess = inv.datamodel_essentials(repo)
    assert {"Album", "User"} <= {t["name"] for t in ess["types"]}
    facts = [
        _fact("types", "code_type", "Album"),
        _fact("fields", "field", "album.id", "VARCHAR PRIMARY KEY"),
        _fact("fields", "field", "album.created_at", "TIMESTAMP"),
    ]
    joined = " ".join(gates.datamodel_essentials_issues(facts, ess))
    assert "User" in joined  # Go: entity.User is not a table, the page must say so
    assert "relation" in joined  # no relation / no_relation fact at all
    facts += [_fact("types", "not_entity", "User"), _fact("relations", "no_relation", "album")]
    assert not gates.datamodel_essentials_issues(facts, ess)
