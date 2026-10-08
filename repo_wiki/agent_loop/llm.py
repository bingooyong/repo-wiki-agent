"""Tool-calling chat client, request-hash cassette and token budgets for the agent loop.

* The API key is read from the environment variable named in the config, sent only as an
  ``Authorization`` header and never logged, recorded or included in errors.
* Provider errors (quota, rate limit after retries, outage, malformed reply) are never recorded in
  the cassette and never handed to an agent as a "response": they raise :class:`ProviderError`,
  which aborts the run (no 429 loops).
* The cassette key is the sha256 of the canonical request body. Replay never touches the network
  and a miss is an error naming role/iteration/step. A cassette carries the runner version and the
  repository fingerprint; replay / resume refuse a mismatch (a resume after a code change would
  silently miss every call and become a paid rerun).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import httpx

CASSETTE_MODES = ("off", "record", "resume", "replay")
_QUOTA_RX = re.compile(
    r"(?i)insufficient[_ ]quota|quota|usage limit|用量上限|余额不足|exceeded your current|billing"
)
_FATAL_PROVIDER_CODES = {1004, 1008, 2049, 2056}  # auth / balance / invalid key / plan quota


class AgentLoopError(RuntimeError):
    """Base class for errors that abort an agent-loop run."""


class ProviderError(AgentLoopError):
    """The model provider failed (quota, outage, malformed reply). Never recorded, never retried
    by an agent; aborts the run."""


class BudgetExceeded(AgentLoopError):
    """A prompt-token cap was reached; the page (or run) is aborted, never passed."""


class CassetteMiss(AgentLoopError):
    """Replay mode needed a response that is not in the cassette."""


class CassetteVersionMismatch(AgentLoopError):
    """Replay / resume refused: the cassette was recorded by different runner code or repo."""


class ToolChatClient(Protocol):
    def complete(self, body: dict[str, Any]) -> dict[str, Any]: ...


# ------------------------------------------------------------------ HTTP client
def _provider_code(data: dict[str, Any]) -> tuple[int | None, str]:
    base = data.get("base_resp") if isinstance(data.get("base_resp"), dict) else None
    err = data.get("error")
    code: Any = None
    msg = ""
    if base:
        code, msg = base.get("status_code"), str(base.get("status_msg") or "")
    if isinstance(err, dict):
        code = err.get("code", code)
        msg = str(err.get("message") or err.get("type") or msg)
    elif err:
        msg = str(err)
    try:
        return (int(code) if code is not None else None), msg
    except (TypeError, ValueError):
        return None, msg


class OpenAICompatibleClient:
    """Minimal OpenAI-compatible ``/chat/completions`` client with tool calls."""

    def __init__(
        self,
        base_url: str,
        api_key_env: str,
        timeout: float = 240.0,
        max_retries: int = 3,
        chat_path: str = "/chat/completions",
        sleep: Callable[[float], None] = time.sleep,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.url = base_url.rstrip("/") + "/" + chat_path.lstrip("/")
        self.api_key_env = api_key_env
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.sleep = sleep
        self.transport = transport

    def _key(self) -> str:
        key = os.environ.get(self.api_key_env or "", "")
        if not key:
            raise ProviderError(f"API key environment variable {self.api_key_env!r} is not set")
        return key

    def complete(self, body: dict[str, Any]) -> dict[str, Any]:
        headers = {"Authorization": "Bearer " + self._key(), "Content-Type": "application/json"}
        last = "no attempt"
        with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
            for attempt in range(self.max_retries + 1):
                if attempt:
                    self.sleep(min(30.0, 3.0 * attempt))
                try:
                    r = client.post(self.url, headers=headers, json=body)
                except httpx.HTTPError as exc:
                    last = f"network error {type(exc).__name__}"
                    continue
                try:
                    data = r.json()
                except ValueError:
                    data = {}
                if not isinstance(data, dict):
                    data = {}
                code, msg = _provider_code(data)
                if r.status_code == 200 and data.get("choices") and not (code and code != 0):
                    return data
                last = f"HTTP {r.status_code} code={code} {msg[:160]}".strip()
                fatal = (
                    r.status_code in (400, 401, 403, 404)
                    or (code in _FATAL_PROVIDER_CODES)
                    or (r.status_code == 429 and bool(_QUOTA_RX.search(msg)))
                )
                if fatal:
                    break
        raise ProviderError(f"provider error: {last}")


class ScriptedClient:
    """Offline client: answers from a callable (tests / fixtures). Counts calls."""

    def __init__(self, respond: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self.respond = respond
        self.calls = 0

    def complete(self, body: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        return self.respond(body)


class NoNetworkClient:
    """Used in replay mode: any call is a bug."""

    def complete(self, body: dict[str, Any]) -> dict[str, Any]:
        raise CassetteMiss("network call attempted in replay mode")


# ------------------------------------------------------------------ cassette
def request_key(body: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def runner_version() -> str:
    """Hash of the agent-loop sources: prompts, tool schemas and loop control are all in here."""
    here = Path(__file__).resolve().parent
    h = hashlib.sha256()
    for p in sorted(here.glob("*.py")):
        h.update(p.name.encode() + b"\0" + p.read_bytes())
    return h.hexdigest()[:12]


class Cassette:
    """``cassette.jsonl`` (one row per response) + ``cassette.meta.json`` (version stamp)."""

    def __init__(self, directory: Path, mode: str, version: str, repo_fingerprint: str) -> None:
        if mode not in CASSETTE_MODES:
            raise ValueError(f"cassette mode must be one of {CASSETTE_MODES}")
        self.dir = Path(directory)
        self.mode = mode
        self.path = self.dir / "cassette.jsonl"
        self.meta_path = self.dir / "cassette.meta.json"
        self.version = version
        self.repo_fingerprint = repo_fingerprint
        self.rows: dict[str, dict[str, Any]] = {}
        self.rotated: str | None = None
        if mode != "off":
            self._open()

    def _open(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        have = self.path.exists() and self.path.stat().st_size > 0
        meta: dict[str, Any] = {}
        if self.meta_path.exists():
            try:
                meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
            except ValueError:
                meta = {}
        if self.mode == "replay" and not have:
            raise CassetteMiss(f"replay requested but no cassette at {self.path}")
        if have:
            old = (meta.get("runner_version"), meta.get("repo_fingerprint"))
            if old != (self.version, self.repo_fingerprint):
                if self.mode in ("replay", "resume"):
                    raise CassetteVersionMismatch(
                        f"REFUSED: cassette recorded by runner {old[0]} on repo {old[1]}; current "
                        f"runner {self.version} on repo {self.repo_fingerprint}. A {self.mode} would "
                        "miss every call."
                    )
                tag = str(old[0] or "unversioned")
                target = self.dir / f"cassette.{tag}.jsonl"
                n = 1
                while target.exists():
                    target = self.dir / f"cassette.{tag}.{n}.jsonl"
                    n += 1
                self.path.rename(target)
                self.rotated = target.name
            else:
                for ln in self.path.read_text(encoding="utf-8").splitlines():
                    if ln.strip():
                        row = json.loads(ln)
                        self.rows[row["key"]] = row
        self.meta_path.write_text(
            json.dumps(
                {"runner_version": self.version, "repo_fingerprint": self.repo_fingerprint},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def get(self, key: str) -> dict[str, Any] | None:
        row = self.rows.get(key)
        return row["response"] if row else None

    def put(self, key: str, response: dict[str, Any], role: str) -> None:
        if self.mode in ("off", "replay"):
            return
        row = {"key": key, "role": role, "response": response}
        self.rows[key] = row
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------ session (budget + stats)
@dataclass
class UsageStats:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    live_calls: int = 0
    live_prompt_tokens: int = 0
    live_completion_tokens: int = 0

    def snapshot(self) -> dict[str, int]:
        return dict(self.__dict__)

    def minus(self, other: dict[str, int]) -> dict[str, int]:
        return {k: v - other.get(k, 0) for k, v in self.__dict__.items()}


@dataclass
class ChatSettings:
    model: str
    temperature: float = 0.1
    max_tokens: int = 8192
    extra_body: dict[str, Any] = field(default_factory=dict)


class LLMSession:
    """All agent-loop model calls go through here: cassette, caps, usage, live ledger."""

    def __init__(
        self,
        client: ToolChatClient,
        settings: ChatSettings,
        cassette: Cassette | None = None,
        global_prompt_cap: int = 2_000_000,
        ledger_path: Path | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.cassette = cassette
        self.global_prompt_cap = global_prompt_cap
        self.page_prompt_cap: int | None = None
        self._page_start = 0
        self.ledger_path = ledger_path
        self.stats = UsageStats()
        self.context: dict[str, Any] = {}

    def start_page(self, prompt_cap: int | None) -> None:
        self.page_prompt_cap = prompt_cap
        self._page_start = self.stats.prompt_tokens

    def body(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.settings.model,
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
            "messages": messages,
        }
        if tools:
            body["tools"] = tools
        body.update(self.settings.extra_body)
        return body

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        role: str,
        iteration: int = 0,
        step: int = 0,
    ) -> dict[str, Any]:
        if self.stats.prompt_tokens >= self.global_prompt_cap:
            raise BudgetExceeded(f"global prompt-token cap {self.global_prompt_cap} reached")
        if (
            self.page_prompt_cap is not None
            and self.stats.prompt_tokens - self._page_start >= self.page_prompt_cap
        ):
            raise BudgetExceeded(f"page prompt-token cap {self.page_prompt_cap} reached")
        body = self.body(messages, tools)
        key = request_key(body)
        data = self.cassette.get(key) if self.cassette else None
        live = data is None
        if data is None:
            if self.cassette is not None and self.cassette.mode == "replay":
                raise CassetteMiss(
                    f"cassette miss in replay mode: role={role} iteration={iteration} step={step}"
                )
            data = self.client.complete(body)
            if not isinstance(data, dict) or not data.get("choices"):
                raise ProviderError("provider returned no choices")
            if self.cassette is not None:
                self.cassette.put(key, data, role)
        usage = data.get("usage") or {}
        p, c = int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
        self.stats.calls += 1
        self.stats.prompt_tokens += p
        self.stats.completion_tokens += c
        if live:
            self.stats.live_calls += 1
            self.stats.live_prompt_tokens += p
            self.stats.live_completion_tokens += c
            if self.ledger_path is not None:
                self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
                with self.ledger_path.open("a", encoding="utf-8") as fh:
                    row = {
                        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "role": role,
                        "prompt_tokens": p,
                        "completion_tokens": c,
                        **self.context,
                    }
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return data


def first_message(data: dict[str, Any]) -> dict[str, Any]:
    choices = data.get("choices") or [{}]
    msg = (choices[0] or {}).get("message") if isinstance(choices[0], dict) else None
    return msg if isinstance(msg, dict) else {}


def iter_tool_calls(msg: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for c in msg.get("tool_calls") or []:
        if isinstance(c, dict) and isinstance(c.get("function"), dict):
            yield c
