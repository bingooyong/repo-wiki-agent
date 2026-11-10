"""Tool loop shared by every agent role.

Behaviour (learned from the prototypes):
* record tools answer immediately with the deterministic verifier's verdict (a compiler error for
  the agent); a finish right after a batch with rejected items is refused once;
* an optional finish guard can refuse a stop call once (e.g. checklist ids unaccounted);
* unknown tool names get an error listing the available tools;
* when the tool budget runs out, one forced wrap-up call offers only the output tools; a JSON
  object in plain content is accepted as the stop tool's arguments.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from repo_wiki.agent_loop.llm import LLMSession, first_message, iter_tool_calls
from repo_wiki.agent_loop.tools import READ_TOOL_NAMES, ToolBox

# record handler: args -> (tool output, number of rejected items)
RecordHandler = Callable[[dict[str, Any]], tuple[str, int]]
FinishCheck = Callable[[list[tuple[str, dict[str, Any]]], dict[str, Any]], str]
TOOL_OUTPUT_MAX = 12000
THINK_RX = re.compile(r"<think>.*?</think>", re.S)


@dataclass
class AgentResult:
    submits: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    steps: int = 0
    exhausted: bool = False
    token_limited: bool = False
    text: str = ""

    def first(self, name: str) -> dict[str, Any] | None:
        return next((a for n, a in self.submits if n == name), None)

    def all(self, name: str) -> list[dict[str, Any]]:
        return [a for n, a in self.submits if n == name]


def _tool_names(tools: list[dict[str, Any]]) -> set[str]:
    return {t["function"]["name"] for t in tools}


def parse_args(raw: object) -> tuple[dict[str, Any], str | None]:
    if isinstance(raw, dict):
        return raw, None
    try:
        val = json.loads(str(raw or "{}") or "{}")
    except json.JSONDecodeError as exc:
        return {}, f"ERROR: arguments are not valid JSON ({exc.msg}); resend the call"
    return (val, None) if isinstance(val, dict) else ({}, "ERROR: arguments must be a JSON object")


class AgentRunner:
    def __init__(self, toolbox: ToolBox, session: LLMSession) -> None:
        self.toolbox = toolbox
        self.session = session
        self.trace: list[dict[str, Any]] = []

    def write(self, role: str, system: str, user: str, iteration: int = 0) -> str:
        """Single tool-less call (writer)."""
        res = self.run(role, system, user, [], 1, [], iteration)
        return THINK_RX.sub("", res.text or "").strip()

    def run(
        self,
        role: str,
        system: str,
        user: str,
        tools: list[dict[str, Any]],
        budget: int,
        stop_names: list[str],
        iteration: int = 0,
        handlers: Mapping[str, RecordHandler] | None = None,
        finish_check: FinishCheck | None = None,
        token_allowance: int | None = None,
    ) -> AgentResult:
        """``token_allowance`` caps the prompt tokens this agent may spend; once
        reached it stops exploring and goes straight to the record wrap-up, so a
        large repo is explored in bounded slices instead of hitting the page cap."""
        handlers = handlers or {}
        spent0 = self.session.stats.prompt_tokens
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        names = _tool_names(tools)
        res = AgentResult()
        stopped = guard_used = False
        pending = 0
        while not stopped and res.steps < budget:
            if (
                token_allowance is not None
                and res.steps
                and self.session.stats.prompt_tokens - spent0 >= token_allowance
            ):
                res.token_limited = True
                break
            data = self.session.chat(messages, tools, role, iteration, res.steps)
            msg = first_message(data)
            calls = list(iter_tool_calls(msg))
            res.text = str(msg.get("content") or "")
            am: dict[str, Any] = {"role": "assistant", "content": res.text}
            if calls:
                am["tool_calls"] = calls
            messages.append(am)
            if not calls:
                res.steps += 1
                if not tools:
                    break
                messages.append(
                    {
                        "role": "user",
                        "content": "Use the tools; finish with " + "/".join(stop_names) + ".",
                    }
                )
                continue
            for c in calls:
                res.steps += 1
                name = str(c["function"].get("name") or "")
                args, arg_err = parse_args(c["function"].get("arguments"))
                if name not in names:
                    out = f"ERROR: unknown tool {name}; available: {', '.join(sorted(names))}"
                elif arg_err:
                    out = arg_err
                elif name in READ_TOOL_NAMES:
                    out = self.toolbox.run(name, args)
                elif name in handlers:
                    res.submits.append((name, args))
                    out, pending = handlers[name](args)
                elif (
                    name in stop_names
                    and finish_check is not None
                    and not guard_used
                    and res.steps < budget
                    and finish_check(res.submits, args)
                ):
                    guard_used = True
                    out = finish_check(res.submits, args)
                elif name in stop_names and pending and not guard_used and res.steps < budget:
                    guard_used = True
                    out = (
                        f"finish refused once: {pending} items from your last record call were "
                        "rejected. Re-record corrected versions, or call finish again to give up on them."
                    )
                else:
                    res.submits.append((name, args))
                    n = next((len(v) for v in args.values() if isinstance(v, list)), 0)
                    out = f"ok ({n} items)"
                    if name in stop_names:
                        stopped = True
                self.trace.append(
                    {
                        "iter": iteration,
                        "role": role,
                        "step": res.steps,
                        "tool": name,
                        "args": {
                            k: (v if not isinstance(v, list) else f"<{len(v)} items>")
                            for k, v in args.items()
                        },
                        "out_chars": len(out),
                    }
                )
                left = budget - res.steps
                note = f"\n[budget left: {left}]" if left <= 3 else ""
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": c.get("id") or f"call_{res.steps}",
                        "content": out[:TOOL_OUTPUT_MAX] + note,
                    }
                )
        if not stopped and tools:
            self._wrap_up(role, messages, tools, stop_names, iteration, handlers, res)
        return res

    def _wrap_up(
        self,
        role: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        stop_names: list[str],
        iteration: int,
        handlers: Mapping[str, RecordHandler],
        res: AgentResult,
    ) -> None:
        res.exhausted = True
        wrap = [t for t in tools if t["function"]["name"] not in READ_TOOL_NAMES]
        messages.append(
            {
                "role": "user",
                "content": "Budget exhausted. Call the record/submit tools now with what you have "
                "confirmed, then finish.",
            }
        )
        data = self.session.chat(messages, wrap, role, iteration, res.steps + 1)
        msg = first_message(data)
        wrap_names = _tool_names(wrap)
        got = False
        for c in iter_tool_calls(msg):
            name = str(c["function"].get("name") or "")
            args, err = parse_args(c["function"].get("arguments"))
            if err or name not in wrap_names:
                continue
            got = True
            res.submits.append((name, args))
            if name in handlers:
                handlers[name](args)
        if not got and stop_names:
            m = re.search(r"\{.*\}", str(msg.get("content") or ""), re.S)
            if m:
                try:
                    val = json.loads(m.group(0))
                except json.JSONDecodeError:
                    val = None
                if isinstance(val, dict):
                    res.submits.append((stop_names[0], val))
        self.trace.append(
            {
                "iter": iteration,
                "role": role,
                "step": res.steps + 1,
                "tool": "forced_wrapup",
                "args": {},
                "out_chars": 0,
            }
        )


class PageBudget:
    """Shares what is left of a page's prompt-token cap between its agents.

    A reserve (``RESERVE`` of the cap) is kept back for writing and auditing;
    exploration agents (shards, repair, module closers, gap, rediscover) each get
    an equal slice of the rest, recomputed per call so unspent slices roll over.
    When nothing is left above the reserve, exploration is skipped (logged) so a
    large repository still ends with a written, audited draft instead of an
    abort. Disabled when the page has no prompt cap.
    """

    RESERVE = 0.3

    def __init__(self, session: Any) -> None:
        self.session = session
        cap = getattr(session, "page_prompt_cap", None)
        self.enabled = cap is not None
        # page_remaining() is min(page cap, what is left of the global cap)
        self.reserve = int(session.page_remaining() * self.RESERVE) if cap is not None else 0
        self.skipped: list[str] = []
        self.limited: list[str] = []
        self.cap = cap
        # tokens held back for essential steps that run after exploration (e.g. the API page's
        # server/auth/conventions facts): exploration may not spend them
        self.held: dict[str, int] = {}

    def remaining(self) -> int | None:
        return self.session.page_remaining() if self.enabled else None

    def hold(self, name: str, frac: float) -> None:
        """Keep ``frac`` of the page cap for the essential step ``name`` until it runs."""
        if self.enabled and self.cap is not None:
            self.held[name] = int(self.cap * frac)

    def allowance(self, slots_left: int, essential: str | None = None) -> int | None:
        """Token allowance for the next agent; 0 = skip it. Optional exploration may not touch the
        write/audit reserve nor what is held for essential steps; an essential step releases its
        hold and gets everything above the reserve (so it runs unless the reserve itself is hit)."""
        rem = self.remaining()
        if rem is None:
            return None
        if essential is not None:
            self.held.pop(essential, None)  # its share becomes available to it alone
            avail = rem - self.reserve - sum(self.held.values())
            return max(avail, 0)
        avail = rem - self.reserve - sum(self.held.values())
        if avail <= 0:
            return 0
        return max(avail // max(slots_left, 1), 1)

    def can_afford(self, cost: int) -> bool:
        rem = self.remaining()
        return rem is None or rem >= cost

    def log(self) -> dict[str, Any]:
        return {
            "reserve": self.reserve,
            "skipped": self.skipped,
            "token_limited": self.limited,
            "held": dict(self.held),
        }
