"""The six-step loop for fact pages (overview / install / data model).

recognize (shared) -> fixed checklist -> deterministic inventory + outline shards -> shard
investigators record typed facts verified immediately -> repair pass for unaccounted obligations
-> module closer -> gap closer (finish guard) -> writer prose + program-rendered parts ->
deterministic checks (incl. the repository's own handbook gates) + independent auditor with tools
-> bounded rework (retract / re-close / rediscover) -> pass | failed.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from repo_wiki.agent_loop import gates
from repo_wiki.agent_loop import inventory as inv
from repo_wiki.agent_loop.checklists import PageSpec
from repo_wiki.agent_loop.evidence import norm, parse_ev, quote_ok
from repo_wiki.agent_loop.facts import (
    FactStore,
    add_doc_code_conflicts,
    make_conflict,
    salvage_facts,
    salvage_items,
    salvage_strings,
)
from repo_wiki.agent_loop.render import facts_block, finalize_page, render_conflicts, render_tables
from repo_wiki.agent_loop.repo import RepoView
from repo_wiki.agent_loop.roles import (
    DISMISS,
    FINISH,
    RECORD_FACTS,
    ROLE_AUDITOR,
    ROLE_GAP,
    ROLE_SHARD,
    ROLE_WRITER,
    SUBMIT_AUDIT,
)
from repo_wiki.agent_loop.runner import AgentResult, AgentRunner
from repo_wiki.agent_loop.tools import READ_GREP, READ_TOOLS
from repo_wiki.agent_loop.verifier import Fact, FactVerifier


@dataclass
class Budgets:
    """Per-role tool-call budgets (a tool call is one step)."""

    recognize: int = 12
    shard: int = 7
    repair: int = 5
    module: int = 3
    gap: int = 8
    audit: int = 6
    rediscover: int = 6
    mechanism: int = 10
    route_shard: int = 7
    sweep: int = 6
    attribution: int = 8
    api_facts: int = 7
    shard_lines: int = 240


@dataclass
class PageInventory:
    oblig: dict[str, dict[str, Any]] = field(default_factory=dict)
    shards: list[tuple[str, list[str]]] = field(default_factory=list)
    dm_sites: list[dict[str, Any]] = field(default_factory=list)
    pre_dismissed: dict[str, str] = field(default_factory=dict)


def _lines_of(items: list[dict[str, Any]]) -> str:
    return "\n".join(f"- {x['file']}:{x['line']}: {x['text']}" for x in items)


def build_page_inventory(repo: RepoView, page_type: str, shard_lines: int = 240) -> PageInventory:
    d = PageInventory()
    if page_type == "overview":
        o = inv.overview_inventory(repo)
        mods = [m for m in o["modules"] if m["oblig"]]
        for m in mods:
            d.oblig[inv.module_path(m)] = {"module": True, "text": m["key"]}
        for e in o["entries"]:
            d.oblig[f"{e['file']}:{e['line']}"] = {
                "file": e["file"],
                "line": e["line"],
                "text": e["text"],
            }
        ent_txt = _lines_of(o["entries"])
        d.shards.append(
            (
                "Identity + stack + entry points shard.\n"
                + inv.identity_outline(repo)
                + "\n\nEntry-point candidates (inventory):\n"
                + ent_txt,
                [f"{e['file']}:{e['line']}" for e in o["entries"]],
            )
        )
        outs = [(m, inv.module_outline(repo, m)) for m in mods]
        for grp in inv.chunk(outs, lambda x: max(x[1].count("\n") + 1, 20), 200):
            d.shards.append(
                (
                    "Module shard: record one 'module' fact per listed directory (value = the directory path "
                    "exactly as listed, role proven by a line from a file inside it), or dismiss it.\n"
                    + "\n".join(o_ for _, o_ in grp),
                    [inv.module_path(m) for m, _ in grp],
                )
            )
    elif page_type == "install":
        cmds: list[dict[str, Any]] = []
        for i, f in enumerate(inv.doc_files(repo)[:3]):
            cs = inv.doc_commands(repo, f)
            cmds += cs
            if i == 0:
                for c in cs:
                    d.oblig[f"{c['file']}:{c['line']}"] = c
        b = inv.build_inventory(repo)
        for x in b:
            root_docker = (
                x["kind"] == "docker"
                and "/" not in x["file"]
                and re.match(r"\s*(FROM|EXPOSE|CMD|ENTRYPOINT)\b", x["text"])
            )
            if (x["kind"] in ("pkg", "runtime") or root_docker) and not re.match(
                r'\s*"(scripts|engines)"\s*:', x["text"]
            ):
                d.oblig[f"{x['file']}:{x['line']}"] = x
        cfg = inv.config_inventory(repo)
        env_files: dict[str, int] = defaultdict(int)
        for c in cfg:
            if c["kind"] == "env":
                env_files[c["file"]] += 1
        for c in cfg:
            if (
                c["kind"] == "dotenv"
                or (c["kind"] == "env" and env_files[c["file"]] >= 3)
                or (c["kind"] == "default" and len(d.oblig) < 400)
            ):
                d.oblig[f"{c['file']}:{c['line']}"] = c
        for grp in inv.chunk(cmds, lambda x: 1, 120):
            d.shards.append(
                (
                    "Documentation shard: commands in fenced/indented code blocks of the docs (with line numbers). "
                    "Record the prerequisites, install/run/verify commands and documented ports they show; dismiss "
                    "commands that are not part of installing/running (tests, lint, formatting, release).\n"
                    + _lines_of(grp),
                    [f"{x['file']}:{x['line']}" for x in grp],
                )
            )
        for grp in inv.chunk(b, lambda x: 1, 140):
            d.shards.append(
                (
                    "Build/runtime shard: Makefile targets (target ⟶ first recipe line), package scripts/engines, "
                    "Dockerfile, compose services/images/ports, runtime versions. Record prerequisites/versions, "
                    "commands (value = how a user invokes it, e.g. 'make <target>' or 'yarn <script>'), services and "
                    "ports.\n" + _lines_of(grp),
                    [f"{x['file']}:{x['line']}" for x in grp],
                )
            )
        for grp in inv.chunk(cfg, lambda x: 1, 140):
            d.shards.append(
                (
                    "Configuration shard: environment variables read by the code, .env files, default listen/port "
                    "literals. Record config files, env vars (name + default + meaning) and the default port; dismiss "
                    "variables that are test-only or belong to auxiliary tooling.\n"
                    + _lines_of(grp),
                    [f"{x['file']}:{x['line']}" for x in grp],
                )
            )
        if not d.shards:
            d.shards.append(
                (
                    "No install/run inventory was found by the deterministic scan. Use the tools to find how the "
                    "project is installed and started; record only what the repository states.",
                    [],
                )
            )
    else:
        sites = inv.dm_inventory(repo)
        d.dm_sites = sites
        d.pre_dismissed = inv.dedupe_ddl(repo, sites)
        per: dict[str, list[int]] = defaultdict(list)
        for s in sites:
            k = f"{s['file']}:{s['line']}"
            if k in d.pre_dismissed:
                continue  # still a valid citation site (verifier uses dm_sites), not re-investigated
            per[s["file"]].append(s["line"])
            d.oblig[k] = s
        dm_outs = [(f, inv.dm_outline(repo, f, ls)) for f, ls in sorted(per.items())]
        for grp in inv.chunk(dm_outs, lambda x: x[1].count("\n") + 1, shard_lines):
            d.shards.append(
                (
                    "Definition shard: persistence definitions found by a deterministic scan. Record every persisted "
                    "entity (cite its definition line), each field (value 'entity.field', cite the field line; "
                    "type/constraints in the claim), keys, and relations (cite the FK/ref line) or no_relation; dismiss "
                    "definitions that are not persisted tables (base classes, settings, duplicates of the same table "
                    "in later migrations — say which).\n" + "\n\n".join(o for _, o in grp),
                    [k for f, _ in grp for k in d.oblig if k.startswith(f + ":")],
                )
            )
        types_all = inv.model_type_inventory(repo, cap=200)
        types = [t for t in types_all if inv.has_persist_marker(repo, t)][:60]
        other_t = [t for t in types_all if t not in types]
        hints = inv.store_hints(repo)
        for gi in range(0, max(len(types), 1 if hints else 0), 25):
            grp_t, hints_ = types[gi : gi + 25], (hints if gi == 0 else [])
            tl = []
            for t in grp_t:
                d.oblig[f"{t['file']}:{t['line']}"] = t
                ls_ = repo.lines(t["file"]) or []
                body = " | ".join(
                    f"{j}: {ls_[j - 1].strip()[:70]}"
                    for j in range(t["line"] + 1, min(len(ls_), t["line"] + 8) + 1)
                    if ls_[j - 1].strip()
                )
                tl.append(f"{t['file']}:{t['line']}: {t['text']}\n    {body}")
            others = ""
            if gi == 0 and other_t:
                others = (
                    "\n\nOther types in model directories WITHOUT a persistence marker (no obligation; record "
                    "not_entity only for ones a reader could mistake for a table):\n"
                    + ", ".join(f"{t['text'][:60]} ({t['file']}:{t['line']})" for t in other_t[:40])
                )
            d.shards.append(
                (
                    "Code-model shard. (a) Storage-engine hints from manifests/compose/env — record the concrete engine "
                    "as a store fact (cite the driver/DSN/image line). (b) Type declarations in model/entity/domain "
                    "directories: for each, record slot code_type (value = type name; claim says which persisted "
                    "entity it represents, citing its declaration line) or slot not_entity when it is not persisted "
                    "(DTO, request/response, base/meta class, in-memory demo object).\n"
                    + ("Engine hints:\n" + "\n".join(hints_) + "\n\n" if hints_ else "")
                    + ("Types:\n" + "\n".join(tl) if tl else "")
                    + others,
                    [f"{t['file']}:{t['line']}" for t in grp_t],
                )
            )
        if not sites:
            d.shards.append(
                (
                    "No DDL/ORM definitions were found by the deterministic scan. Find how data is persisted (if at "
                    "all) with the tools; if nothing is persisted, record that as a store/note fact with evidence.",
                    [],
                )
            )
    return d


def accept_findings(
    repo: RepoView, findings: list[Any], page_text: str
) -> tuple[list[str], list[str], list[tuple[dict[str, Any], list[dict[str, Any]]]]]:
    """Auditor findings are accepted only when supported: 'invented' must quote the page, the
    others must carry evidence that verifies; low-severity omissions are logged only."""
    accepted: list[str] = []
    dropped: list[str] = []
    wrong: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        t = f.get("type")
        raw = f.get("ev") or f.get("evidence") or []
        evs = [parse_ev(e) for e in (raw if isinstance(raw, list) else [raw])]
        good = [e for e in evs if e is not None]
        if t == "invented":
            ok = bool(f.get("page_quote")) and norm(f["page_quote"])[:60] in norm(page_text)
        elif t in ("omission", "wrong"):
            ok = bool(evs) and all(e is not None and quote_ok(repo, e) is not None for e in evs)
        else:
            ok = False
        if ok and t == "omission" and f.get("severity") != "high":
            ok = False
        line = (
            f"[{t}] {f.get('detail')} "
            + (f"page: {f.get('page_quote')!r} " if f.get("page_quote") else "")
            + ", ".join(f"{e['file']}:{e['line']}" for e in good)
        )
        (accepted if ok else dropped).append(line.strip())
        if ok and t == "wrong":
            wrong.append((f, good))
    return accepted, dropped, wrong


class FactPageLoop:
    def __init__(
        self,
        runner: AgentRunner,
        repo: RepoView,
        spec: PageSpec,
        profile: dict[str, Any],
        budgets: Budgets,
        max_iters: int,
    ) -> None:
        self.runner = runner
        self.repo = repo
        self.spec = spec
        self.profile = profile
        self.budgets = budgets
        self.max_iters = max_iters
        self.invd = build_page_inventory(repo, spec.page_type, budgets.shard_lines)
        self.store = FactStore(FactVerifier(repo, spec, self.invd.dm_sites))
        self.dismissed: dict[str, str] = dict(self.invd.pre_dismissed)
        self.dismissed = {k: v for k, v in self.dismissed.items() if k in self.invd.oblig}
        self.unresolved: list[str] = []
        self.mod_unres: dict[str, str] = {}
        slots = spec.slot_help + (
            " | note (value=checklist id; an evidenced 'not applicable' for that item) | conflict (value=subject; "
            "two sources disagree — cite BOTH lines, from different files)"
        )
        self.slots = slots
        self.role = ROLE_SHARD.format(title=spec.title, question=spec.question, slots=slots)
        self.tools = READ_TOOLS + [RECORD_FACTS, DISMISS, FINISH]
        self.log: dict[str, Any] = {
            "inventory_obligations": len(self.invd.oblig),
            "shards": len(self.invd.shards),
        }

    # -------------------------------------------------------------- tool handlers
    def _record(self, args: dict[str, Any]) -> tuple[str, int]:
        fs = salvage_facts(args.get("facts") or [])
        acc, rej = self.store.add(fs)
        out = f"accepted {acc}/{len(fs)}"
        if rej:
            out += "; REJECTED (fix and re-record):\n" + "\n".join(
                f"- [{(f or {}).get('slot') if isinstance(f, dict) else '?'}] "
                f"{str((f or {}).get('value') if isinstance(f, dict) else f)[:60]}: {'; '.join(w)[:300]}"
                for f, w in rej[:12]
            )
        return out, len(rej)

    def _dismiss(self, args: dict[str, Any]) -> tuple[str, int]:
        ok, bad = [], []
        for it in salvage_items(args.get("items") or []):
            k, why = gates.vet_dismissal(it, self.invd.oblig, self.store.live())
            if k:
                self.dismissed[k] = str(it.get("reason") or "")
                ok.append(k)
            else:
                bad.append(str(why))
        out = f"dismissed {len(ok)}"
        if bad:
            out += "; REFUSED:\n" + "\n".join(f"- {b}" for b in bad[:12])
        return out, 0

    def _handlers(self) -> dict[str, Any]:
        return {"record_facts": self._record, "dismiss": self._dismiss}

    def _absorb(self, res: AgentResult) -> None:
        for a in res.all("finish"):
            for u in salvage_strings(a.get("unresolved")):
                if u not in self.unresolved:
                    self.unresolved.append(u)

    def _agent(
        self,
        role: str,
        user: str,
        budget: int,
        iteration: int = 0,
        finish_check: Any = None,
        system: str | None = None,
    ) -> AgentResult:
        res = self.runner.run(
            f"{self.spec.page_type}-{role}",
            system or self.role,
            user,
            self.tools,
            budget,
            ["finish"],
            iteration,
            handlers=self._handlers(),
            finish_check=finish_check,
        )
        self._absorb(res)
        return res

    # -------------------------------------------------------------- helpers
    def covered(self, dismissed: dict[str, Any] | None = None) -> set[str]:
        return gates.covered(
            self.invd.oblig, self.store.live(), self.dismissed if dismissed is None else dismissed
        )

    def ob_text(self, keys: list[str]) -> str:
        o = self.invd.oblig
        return "\n".join(
            f"- {k}" + ("" if o[k].get("module") else f": {str(o[k].get('text', ''))[:120]}")
            for k in keys
            if k in o
        )

    def _module_closer(self, key: str, iteration: int, why: list[str] | None = None) -> None:
        mp = key.rstrip("/") or "."
        if why is None:
            u = (
                f"Page: {self.spec.title}\nModule closer for ONE top-level module: `{key}`.\nRecord one 'module' fact "
                f"(item modules, value = {key!r}) whose role is proven by a line from a file INSIDE `{mp}` (shown "
                f"below) — not by a file that uses it. If these files cannot establish its role, call finish with "
                f"unresolved ['modules: {key}: <why>'].\n\n{inv.module_head(self.repo, mp)}\n\n"
                f"Tool-call budget: {self.budgets.module}."
            )
        else:
            u = (
                f"Page: {self.spec.title}\nModule closer for ONE top-level module: `{key}` (its previous fact was "
                "retracted by the audit"
                + (": " + " / ".join(w[:400] for w in why) if why else "")
                + f").\nRecord one corrected 'module' fact (item modules, value = {key!r}) whose role covers the "
                f"module's main contents, proven by lines from files INSIDE `{mp}`, or call finish with unresolved "
                f"['modules: {key}: <why>'].\n\n{inv.module_outline(self.repo, {'key': key})}\n"
                f"{inv.module_head(self.repo, mp)}\n\nTool-call budget: {self.budgets.module}."
            )
        res = self._agent("module", u, self.budgets.module, iteration)
        if key not in self.covered():
            self.mod_unres[key] = next(
                (
                    str(x)
                    for a in res.all("finish")
                    for x in (a.get("unresolved") or [])
                    if mp in str(x)
                ),
                "role not established from the files inside it",
            )

    # -------------------------------------------------------------- discovery
    def discover(self) -> None:
        spec, b = self.spec, self.budgets
        cl_text = spec.checklist_text()
        prof = json.dumps(self.profile, ensure_ascii=False)
        n = len(self.invd.shards)
        for si, (outline, keys) in enumerate(self.invd.shards):
            items = f"Inventory items to account for:\n{self.ob_text(keys)}\n\n" if keys else ""
            u = (
                f"Page: {spec.title}\nChecklist:\n{cl_text}\n\nRepository profile (verified):\n{prof}\n\n"
                f"Shard {si + 1}/{n}.\n{items}{outline}\n\nTool-call budget: {b.shard}."
            )
            self._agent(f"shard{si + 1}", u, b.shard)
        cov = self.covered()
        un = [k for k in self.invd.oblig if k not in cov]
        self.log["unaccounted_after_shards"] = len(un)
        for gi in range(0, min(len(un), 80), 40):
            grp = un[gi : gi + 40]
            u = (
                f"Page: {spec.title}\nChecklist:\n{cl_text}\n\nRepair pass. These inventory items are still "
                "unaccounted: record the fact that cites each (or the module fact for a directory), or dismiss it "
                f"with a reason.\n{self.ob_text(grp)}\n\nTool-call budget: {b.repair}."
            )
            self._agent(f"repair{gi // 40 + 1}", u, b.repair)
        mods = [
            k
            for k in self.invd.oblig
            if self.invd.oblig[k].get("module") and k not in self.covered()
        ]
        for k in mods[:10]:
            self._module_closer(k, 0)
        self.log["modules_unresolved"] = dict(self.mod_unres)
        gaps = [c for c in spec.checklist if c.id not in {f["item"] for f in self.store.live()}]
        if gaps:

            def guard(_subs: list[tuple[str, dict[str, Any]]], fargs: dict[str, Any]) -> str:
                have = {f["item"] for f in self.store.live()}
                declared = {
                    gates.checklist_id_of(x) for x in salvage_strings(fargs.get("unresolved"))
                }
                miss = [c.id for c in gaps if c.id not in have and c.id not in declared]
                if not miss:
                    return ""
                return (
                    f"finish refused once: checklist ids {miss} have no verified fact and are not listed as "
                    "unresolved."
                )

            u = (
                "Checklist items without verified facts:\n"
                + "\n".join(f"- {c.id}: {c.question} (slots: {', '.join(c.slots)})" for c in gaps)
                + f"\n\nAlready verified facts (do not repeat):\n{facts_block(self.store.live(), [])[:6000]}"
                + f"\n\nRepository profile:\n{prof}\n\nTool-call budget: {b.gap}."
            )
            system = ROLE_GAP.format(title=spec.title, question=spec.question, slots=self.slots)
            self._agent("gap", u, b.gap, finish_check=guard, system=system)

    # -------------------------------------------------------------- write / check / audit
    def run(self) -> dict[str, Any]:
        spec, b = self.spec, self.budgets
        self.discover()
        ids = spec.ids
        history: list[dict[str, Any]] = []
        status, page_text, final_md, prose = "failed", "", "", ""
        writer_sys = ROLE_WRITER.format(
            title=spec.title, tables=spec.table_desc, placeholder=spec.placeholder
        )
        for it in range(self.max_iters + 1):
            add_doc_code_conflicts(self.store)
            live = self.store.live()
            have = {f["item"] for f in live}
            self.unresolved = [
                u
                for u in self.unresolved
                if gates.checklist_id_of(u) in ids and gates.checklist_id_of(u) not in have
            ]
            wr = (
                f"Page: {spec.title}\nReader question: {spec.question}\nChecklist ids: {', '.join(ids)}\n\n"
                f"Verified facts:\n{facts_block(live, self.unresolved)}"
            )
            if history and history[-1]["accepted_findings"]:
                clean_prev = "\n".join(
                    ln for ln in prose.splitlines() if not gates.JUNK_RX.search(ln)
                )[:8000]
                wr += (
                    "\n\nThe previous draft had these problems; fix them:\n"
                    + "\n".join(history[-1]["accepted_findings"])
                    + "\n\nPrevious draft (prose):\n"
                    + clean_prev
                )
            prose = self.runner.write(f"{spec.page_type}-write", writer_sys, wr, it)
            if gates.has_junk(prose):  # tool markup leaked: one clean rewrite before any audit
                prose = self.runner.write(
                    f"{spec.page_type}-write-clean",
                    writer_sys,
                    wr
                    + "\n\nYour previous output contained tool-call markup or runaway text. Output ONLY the "
                    "Markdown page, no tool calls, no XML.",
                    it,
                )
            prose = gates.keep_declared_unresolved(prose, self.unresolved)
            prose, dropped_code = gates.drop_unverified_code(prose, live)
            tables = render_tables(spec.page_type, live, self.mod_unres) + render_conflicts(live)
            ph = spec.placeholder
            page_text = prose.replace(ph, tables, 1) if ph in prose else prose + "\n\n" + tables
            det = gates.page_checks(prose.replace(ph, ""), live, ids, self.unresolved)
            self.mod_unres = {
                k: v
                for k, v in self.mod_unres.items()
                if k not in gates.covered(self.invd.oblig, live, {})
            }
            cov = gates.covered(self.invd.oblig, live, {**self.dismissed, **self.mod_unres})
            un = [k for k in self.invd.oblig if k not in cov]
            if un:
                det.append(
                    f"{len(un)} inventory items neither documented nor dismissed: "
                    + ", ".join(un[:12])
                )
            rec, missing = gates.recall(self.invd.oblig, live, self.dismissed)
            self.log.setdefault("recall", []).append(round(rec, 3))
            if rec < gates.RECALL_MIN:
                det.append(
                    f"inventory recall {rec:.0%} < {gates.RECALL_MIN:.0%}: "
                    + ", ".join(missing[:12])
                )
            if self.mod_unres:
                det.append(
                    "modules whose role is not established (shown as 未能确认): "
                    + ", ".join(list(self.mod_unres)[:8])
                )
            if self.unresolved:
                ids_un = ", ".join(sorted({gates.checklist_id_of(u) for u in self.unresolved}))
                det.append(
                    f"checklist items unresolved: {ids_un} — the page cannot pass; establish them, or record an "
                    "evidenced 'note' fact (value = the checklist id) if the item does not apply"
                )
            det += gates.doc_only_port_issues(live)
            if spec.page_type == "datamodel":
                det += gates.entity_field_issues(live)
            final_md = finalize_page(spec.title, page_text, live, [])
            det += gates.existing_gate_issues(spec.page_type, final_md, self.repo.root)
            accepted, dropped, retract = self._audit(page_text, live, it)
            n_conf = 0
            retracted = 0
            for f_, evs in retract:
                for r_ in gates.finding_ids(f_):
                    if 0 <= r_ - 1 < len(live):
                        n_conf += make_conflict(self.store, live[r_ - 1], evs)
                        self.store.retract(live[r_ - 1])
                        retracted += 1
            acc_all = accepted + [f"[deterministic] {d}" for d in det]
            history.append(
                {
                    "iter": it,
                    "facts": len(live),
                    "facts_rejected": len(self.store.bad),
                    "retracted": retracted,
                    "conflicts_made": n_conf,
                    "dropped_code_lines": dropped_code,
                    "deterministic_issues": det,
                    "accepted_findings": acc_all,
                    "dropped_auditor_findings": dropped,
                }
            )
            if not acc_all:
                status = "pass"
                break
            if it == self.max_iters:
                break
            self._rework(accepted, det, it)
        live = self.store.live()
        return {
            "page_type": spec.page_type,
            "status": status,
            "iterations": len(history),
            "history": history,
            "facts": live,
            "modules_unresolved": self.mod_unres,
            "facts_rejected": self.store.bad[-60:],
            "retracted": [self.store.ok[i] for i in sorted(self.store.retracted)],
            "unresolved": self.unresolved,
            "dismissed": self.dismissed,
            "log": self.log,
            "page_draft": page_text,
            "page": final_md if status == "pass" else "",
        }

    def _audit(
        self, page_text: str, live: list[Fact], it: int
    ) -> tuple[list[str], list[str], list[Any]]:
        spec = self.spec
        au = (
            f"Page: {spec.title}\nReader question: {spec.question}\nChecklist:\n{spec.checklist_text()}\n\n"
            f"Verified facts:\n{facts_block(live, self.unresolved)}\n\n"
            f"PAGE (lists were rendered by a program from the verified facts):\n{page_text}\n\n"
            f"Tool-call budget: {self.budgets.audit}."
        )
        res = self.runner.run(
            f"{spec.page_type}-audit",
            ROLE_AUDITOR.format(title=spec.title),
            au,
            READ_GREP + [SUBMIT_AUDIT],
            self.budgets.audit,
            ["submit_audit"],
            it,
            finish_check=gates.audit_submit_guard,
        )
        audit = res.first("submit_audit") or {"findings": [], "verdict": "none"}
        return accept_findings(self.repo, audit.get("findings") or [], page_text)

    def _rework(self, accepted: list[str], det: list[str], it: int) -> None:
        spec = self.spec
        all_dismissed = {**self.dismissed, **self.mod_unres}
        lost = [
            k
            for k in self.invd.oblig
            if self.invd.oblig[k].get("module")
            and k not in gates.covered(self.invd.oblig, self.store.live(), all_dismissed)
        ]
        for k in lost[:6]:  # re-close modules whose fact was retracted
            mp = k.rstrip("/") or "."
            self._module_closer(k, it + 1, [x for x in accepted if mp in x][:2])
        hint = [x for x in accepted if x.startswith(("[omission]", "[wrong]"))] + [
            d for d in det if gates.needs_investigation(d)
        ]
        un_now = [k for k in self.invd.oblig if k not in self.covered()]
        if hint or un_now:
            still = (
                f"\n\nStill unaccounted inventory items (record or dismiss):\n{self.ob_text(un_now[:30])}"
                if un_now
                else ""
            )
            u = (
                f"Page: {spec.title}\nChecklist:\n{spec.checklist_text()}\n\nAudit follow-up. Investigate and record "
                "corrected/missing facts:\n"
                + "\n".join(hint)
                + still
                + f"\n\nVerified facts so far:\n{facts_block(self.store.live(), [])[:5000]}\n\n"
                f"Tool-call budget: {self.budgets.rediscover}."
            )
            self._agent("rediscover", u, self.budgets.rediscover, it + 1)


def run_fact_page(
    runner: AgentRunner,
    repo: RepoView,
    spec: PageSpec,
    profile: dict[str, Any],
    budgets: Budgets,
    max_iters: int,
) -> dict[str, Any]:
    return FactPageLoop(runner, repo, spec, profile, budgets, max_iters).run()


def repo_root_of(repo: RepoView) -> Path:
    return repo.root
