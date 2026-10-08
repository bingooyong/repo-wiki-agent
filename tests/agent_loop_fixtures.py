"""Shared fixtures for the agent-loop tests: a tiny repository and a scripted tool-calling model."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

DEMO_FILES: dict[str, str] = {
    "README.md": (
        "# demo-shop\n"
        "\n"
        "demo-shop is a small order service.\n"
        "\n"
        "## Install\n"
        "\n"
        "```bash\n"
        "pip install -r requirements.txt\n"
        "```\n"
        "\n"
        "## Run\n"
        "\n"
        "```bash\n"
        "python app.py\n"
        "```\n"
    ),
    "requirements.txt": "flask==3.0.0\n",
    "app.py": (
        "from flask import Flask\n"
        "\n"
        "from shop.store import list_orders\n"
        "\n"
        "app = Flask(__name__)\n"
        "\n"
        "\n"
        '@app.route("/orders", methods=["GET"])\n'
        "def orders():\n"
        '    return {"orders": list_orders()}\n'
        "\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    app.run(port=5000)\n"
    ),
    "shop/__init__.py": '"""Order domain package."""\n',
    "shop/store.py": (
        '"""In-memory order store used by the HTTP handlers."""\n'
        "\n"
        "ORDERS = []\n"
        "\n"
        "\n"
        "def list_orders():\n"
        "    return list(ORDERS)\n"
    ),
    ".env.secret": "API_TOKEN=do-not-read\n",
}


def make_demo_repo(root: Path) -> Path:
    for rel, text in DEMO_FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def tool_call(name: str, args: dict[str, Any], idx: int = 0) -> dict[str, Any]:
    return {
        "id": f"call_{name}_{idx}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
    }


def reply(
    calls: list[dict[str, Any]] | None = None, content: str = "", prompt_tokens: int = 100
) -> dict[str, Any]:
    msg: dict[str, Any] = {"role": "assistant", "content": content}
    if calls:
        msg["tool_calls"] = calls
    return {
        "choices": [{"message": msg, "finish_reason": "tool_calls" if calls else "stop"}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 10},
    }


Rule = tuple[Callable[[str, str], bool], Callable[[int, dict[str, Any]], dict[str, Any]]]


class ScriptedModel:
    """Answers a chat body by the first rule whose predicate matches (system prompt, first user
    message); the responder gets the turn number within that agent run and the body."""

    def __init__(self, rules: list[Rule], default: dict[str, Any] | None = None) -> None:
        self.rules = rules
        self.default = default or reply(content="")
        self.calls: list[str] = []

    def __call__(self, body: dict[str, Any]) -> dict[str, Any]:
        msgs = body["messages"]
        system = str(msgs[0].get("content") or "")
        user = str(msgs[1].get("content") or "") if len(msgs) > 1 else ""
        turn = sum(1 for m in msgs if m.get("role") == "assistant")
        for i, (pred, respond) in enumerate(self.rules):
            if pred(system, user):
                self.calls.append(f"rule{i}:t{turn}")
                return respond(turn, body)
        self.calls.append(f"default:t{turn}")
        return self.default


def last_tool_output(body: dict[str, Any]) -> str:
    for m in reversed(body["messages"]):
        if m.get("role") == "tool":
            return str(m.get("content") or "")
    return ""
