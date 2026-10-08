"""Verified fact store (with retractions and program-built conflict facts) + argument salvage."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from repo_wiki.agent_loop.checklists import PageSpec
from repo_wiki.agent_loop.evidence import is_doc_evidence, norm
from repo_wiki.agent_loop.verifier import Fact, FactVerifier

RUN_RX = re.compile(
    r"(?i)\b(start|run|up|serve|server|daemon|dev|migrate|upgrade|exec|watch)\b|^\./|uvicorn|gunicorn"
)


def norm_item(spec: PageSpec, fact: Fact) -> str:
    """Facts must land on a checklist id; stray item labels are mapped via the slot."""
    ids = spec.ids
    if fact.get("item") in ids:
        return str(fact["item"])
    if spec.page_type == "install" and fact.get("slot") == "command":
        return "run" if RUN_RX.search(str(fact.get("value", ""))) else "install"
    for c in spec.checklist:
        if fact.get("slot") in c.slots:
            return c.id
    return str(fact.get("item") or "")


class FactStore:
    """Facts accepted by the verifier. Retracted facts stay in the log but are no longer live."""

    def __init__(self, verifier: FactVerifier) -> None:
        self.verifier = verifier
        self.ok: list[Fact] = []
        self.bad: list[Fact] = []
        self.retracted: set[int] = set()

    def live(self) -> list[Fact]:
        return [f for i, f in enumerate(self.ok) if i not in self.retracted]

    def entities(self) -> dict[str, list[tuple[str, int]]]:
        idx: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for f in self.live():
            if f["slot"] == "entity":
                for e in f["evidence"]:
                    fl, _, ln = e.rpartition(":")
                    idx[f["value"].lower()].append((fl, int(ln)))
        return idx

    def add(self, raw: list[Any]) -> tuple[int, list[tuple[Any, list[str]]]]:
        """Verify and add; entities first so fields in the same call can attach."""
        accepted = 0
        rejected: list[tuple[Any, list[str]]] = []
        if not isinstance(raw, list):
            return 0, []
        order = sorted(raw, key=lambda f: 0 if str((f or {}).get("slot")) == "entity" else 1)
        for f in order:
            if not isinstance(f, dict):
                rejected.append(
                    (f, ["fact must be one 'item | slot | value | claim | evidence' string"])
                )
                continue
            res = self.verifier.check(f, self.entities())
            if res.ok and res.fact is not None:
                nf = res.fact
                nf["item"] = norm_item(self.verifier.spec, nf)
                key = (nf["slot"], norm(nf["value"]))
                if not any((x["slot"], norm(x["value"])) == key for x in self.live()):
                    self.ok.append(nf)
                accepted += 1
            else:
                self.bad.append({**f, "reasons": res.reasons})
                rejected.append((f, res.reasons))
        return accepted, rejected

    def retract(self, fact: Fact) -> None:
        for i, f in enumerate(self.ok):
            if f is fact:
                self.retracted.add(i)

    def add_program_fact(self, fact: Fact) -> bool:
        if any(
            x["slot"] == fact["slot"] and set(x["evidence"]) == set(fact["evidence"])
            for x in self.live()
        ):
            return False
        self.ok.append(fact)
        return True


# ------------------------------------------------------------------ conflicts
def conflict_fact(subject: str, ev1: str, q1: str, ev2: str, q2: str, item: str) -> Fact:
    return {
        "item": item,
        "slot": "conflict",
        "value": subject,
        "claim": f"来源不一致：{ev1} 为“{q1.strip()[:120]}”；{ev2} 为“{q2.strip()[:120]}”。",
        "evidence": [ev1, ev2],
        "quotes": [q1, q2],
        "program": True,
    }


def make_conflict(store: FactStore, fact: Fact, evs: list[dict[str, Any]]) -> int:
    """An accepted 'wrong' finding about a fact where exactly one side is documentation: keep both
    sides on the page as an explicit conflict instead of silently dropping one."""
    for e in evs:
        e_s = f"{e['file']}:{e['line']}"
        if e_s in fact["evidence"] or is_doc_evidence(fact["evidence"]) == is_doc_evidence([e_s]):
            continue
        cf = conflict_fact(
            fact["value"], fact["evidence"][0], fact["quotes"][0], e_s, e["quote"], fact["item"]
        )
        if store.add_program_fact(cf):
            return 1
    return 0


def add_doc_code_conflicts(store: FactStore) -> int:
    """A port/URL documented only in docs that differs from the code/config port -> conflict."""
    live = store.live()
    code = [x for x in live if x["slot"] == "port" and not is_doc_evidence(x["evidence"])]
    if not code:
        return 0
    added = 0
    for f in live:
        if f["slot"] not in ("port", "verify") or not is_doc_evidence(f["evidence"]):
            continue
        if any(c["value"] in f["value"] for c in code) or not re.search(r"\d{2,5}", f["value"]):
            continue
        if any(x["slot"] == "conflict" and f["evidence"][0] in x["evidence"] for x in store.live()):
            continue
        c = code[0]
        cf = conflict_fact(
            f"port: {f['value']} vs {c['value']}",
            f["evidence"][0],
            f["quotes"][0],
            c["evidence"][0],
            c["quotes"][0],
            "port",
        )
        added += int(store.add_program_fact(cf))
    return added


# ------------------------------------------------------------------ salvage of tool arguments
def _flat(x: object) -> bool:
    return isinstance(x, dict) and set(x) == {"$text"}


def parse_fact_str(x: object) -> dict[str, Any]:
    parts = [p.strip() for p in str(x).split(" | ", 4)]
    if len(parts) < 5:
        parts = [p.strip() for p in str(x).split("|", 4)]
    if len(parts) < 5:
        return {"item": "", "slot": "", "value": "", "claim": str(x), "ev": []}
    evs = [e.strip() for e in re.split(r"\s*\|\|\s*", parts[4]) if e.strip()]
    return {"item": parts[0], "slot": parts[1], "value": parts[2], "claim": parts[3], "ev": evs}


def salvage_facts(fs: object) -> list[Any]:
    """Facts arrive as flat strings (preferred) or objects. Some providers degrade nested objects
    into a flat run ``{$text:item},{$text:slot},{$text:value},{$text:claim},{x:[ev...]}``;
    regroup such runs."""
    if isinstance(fs, (str, dict)):
        fs = [fs]
    if not isinstance(fs, list):
        return []
    items = [parse_fact_str(x) if isinstance(x, str) else x for x in fs]
    if not any(_flat(x) for x in items):
        return items
    out: list[Any] = []
    buf: list[str] = []
    for x in items:
        if _flat(x):
            buf.append(str(x["$text"]))
        elif (
            isinstance(x, dict)
            and len(x) == 1
            and buf
            and isinstance(next(iter(x.values())), (list, str))
        ):
            ev = next(iter(x.values()))
            ev = [ev] if isinstance(ev, str) else ev
            t = buf[-4:] if len(buf) >= 4 else [""] * (4 - len(buf)) + buf
            out.append(
                {"item": t[0].split("/")[0], "slot": t[1], "value": t[2], "claim": t[3], "ev": ev}
            )
            buf = []
        else:
            out.append(x)
    return out


def salvage_items(items: object) -> list[Any]:
    """Dismiss items: ``'KEY | reason'`` strings, objects, or degraded ``$text`` runs."""
    if isinstance(items, (str, dict)):
        items = [items]
    if not isinstance(items, list):
        return []
    parsed: list[Any] = []
    for x in items:
        if isinstance(x, str):
            key, sep, reason = x.partition("|")
            parsed.append({"key": key.strip(), "reason": reason.strip() if sep else ""})
        else:
            parsed.append(x)
    if not any(_flat(x) for x in parsed):
        return parsed
    texts = [str(x["$text"]) for x in parsed if _flat(x)]
    return [x for x in parsed if not _flat(x)] + [
        {"key": texts[i], "reason": texts[i + 1]} for i in range(0, len(texts) - 1, 2)
    ]


def salvage_strings(x: object) -> list[str]:
    """String lists (finish.unresolved, covered_by_routes) sometimes arrive as nested
    ``{"item": {..., "$text": "..."}, "$text": "..."}`` objects; collect every string leaf."""
    out: list[str] = []
    if isinstance(x, str):
        if x.strip():
            out.append(x.strip())
    elif isinstance(x, dict):
        for v in x.values():
            out += salvage_strings(v)
    elif isinstance(x, list):
        for v in x:
            out += salvage_strings(v)
    return out
