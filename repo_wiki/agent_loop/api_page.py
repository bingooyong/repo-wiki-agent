"""The agent loop for the API reference page.

mechanism analyst -> deterministic candidate sites (+ the mechanisms' call-site regexes) -> outline
shards -> route investigators (record_routes verified immediately) -> repair pass -> second-opinion
sweep over the rule-based scanners' hypotheses (never obligations) -> server attribution -> fixed
checklist for non-route facts -> writer + program-rendered route list -> deterministic checks (incl.
the repository's handbook gates) + independent auditor -> bounded rework -> pass | failed.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from repo_wiki.agent_loop import gates
from repo_wiki.agent_loop import inventory as inv
from repo_wiki.agent_loop.checklists import PAGES
from repo_wiki.agent_loop.evidence import parse_ev, quote_ok, shape
from repo_wiki.agent_loop.fact_page import Budgets, accept_findings
from repo_wiki.agent_loop.facts import (
    FactStore,
    add_doc_code_conflicts,
    make_conflict,
    salvage_facts,
    salvage_strings,
)
from repo_wiki.agent_loop.render import (
    api_facts_block,
    finalize_page,
    render_conflicts,
    route_table,
    routes_summary,
)
from repo_wiki.agent_loop.repo import RepoView
from repo_wiki.agent_loop.roles import (
    DISMISS_SITES,
    FINISH_FACTS,
    FINISH_NOTES,
    RECORD_FACTS,
    RECORD_ROUTES,
    ROLE_API_FACTS,
    ROLE_API_WRITER,
    ROLE_ATTR,
    ROLE_AUDITOR,
    ROLE_MECH,
    ROLE_ROUTE_SHARD,
    SUBMIT_ATTR,
    SUBMIT_AUDIT,
    SUBMIT_MECH,
)
from repo_wiki.agent_loop.runner import AgentRunner
from repo_wiki.agent_loop.tools import READ_GREP
from repo_wiki.agent_loop.verifier import (
    UNATTRIBUTED,
    FactVerifier,
    Route,
    resolve_conflicts,
    verify_routes,
)

Site = tuple[str, int]
SPEC = PAGES["api"]
NO_ROUTES = "未能从源码确认任何 HTTP 接口。"


def scanner_hypotheses(repo: RepoView) -> list[dict[str, Any]]:
    """Routes proposed by the existing rule-based scanners. Hints / second opinion only: they are
    shown to investigators and swept, but never become obligations or page content unverified."""
    from repo_wiki.scanner.fastapi_routes import extract_fastapi_endpoints
    from repo_wiki.scanner.go_routes import extract_go_endpoints

    files = [
        (rel, "\n".join(repo.lines(rel) or []))
        for rel in repo.files()
        if rel.endswith((".go", ".py"))
    ]
    out: list[dict[str, Any]] = []
    for extract in (extract_go_endpoints, extract_fastapi_endpoints):
        try:
            eps: list[Any] = list(extract(files))
        except Exception:  # noqa: BLE001 - a scanner crash must not break the page
            continue
        for e in eps:
            out.append(
                {
                    "method": e.method,
                    "path": e.path,
                    "file": e.file_path,
                    "line": int(e.lineno),
                    "text": f"{e.method} {e.path}  ({e.file_path}:{e.lineno}, handler {e.handler})",
                }
            )
    return out


def _parse_site_dismissal(x: object) -> tuple[Site, str] | None:
    if isinstance(x, dict):
        try:
            return (str(x.get("file")), int(str(x.get("line")))), str(x.get("reason") or "")
        except (TypeError, ValueError):
            return None
    key, _, reason = str(x).partition("|")
    f, _, ln = key.strip().strip("`").rpartition(":")
    if not f or not ln.strip().isdigit():
        return None
    return (f.strip(), int(ln)), reason.strip()


class ApiPageLoop:
    def __init__(
        self,
        runner: AgentRunner,
        repo: RepoView,
        profile: dict[str, Any],
        budgets: Budgets,
        max_iters: int,
        seeds: list[dict[str, Any]] | None = None,
    ) -> None:
        self.runner = runner
        self.repo = repo
        self.profile = profile
        self.budgets = budgets
        self.max_iters = max_iters
        self.seeds = scanner_hypotheses(repo) if seeds is None else seeds
        self.raw_routes: list[Any] = []
        self.dismissed: dict[Site, str] = {}
        self.sites: dict[Site, str] = {}
        self.seed_only: set[Site] = set()
        self.shards: list[list[tuple[str, str]]] = []
        self.mech_text = "(none verified)"
        self.servers: list[dict[str, Any]] = []
        self.amap: dict[str, str] = {}
        self.store = FactStore(FactVerifier(repo, SPEC))
        self.unresolved: list[str] = []
        self.by_routes: set[str] = set()
        self.log: dict[str, Any] = {"scanner_hypotheses": len(self.seeds)}

    # ------------------------------------------------------------ handlers
    def _record_routes(self, args: dict[str, Any]) -> tuple[str, int]:
        rs = args.get("routes") or []
        if not isinstance(rs, list):
            rs = [rs]
        self.raw_routes += rs
        ok, bad = verify_routes(self.repo, rs)
        out = f"verified {len(ok)}/{len(rs)}"
        if bad:
            out += "; REJECTED (fix and re-record):\n" + "\n".join(
                f"- {b['method']} {b.get('claimed')}: {'; '.join(b['reasons'])[:400]}"
                for b in bad[:15]
            )
        return out, len(bad)

    def _dismiss_sites(self, args: dict[str, Any]) -> tuple[str, int]:
        raw = args.get("sites") or []
        n, bad = 0, []
        for x in raw if isinstance(raw, list) else [raw]:
            p = _parse_site_dismissal(x)
            if p is None or not p[1]:
                bad.append(f"{str(x)[:80]!r}: use 'FILE:LINE | reason'")
                continue
            self.dismissed[p[0]] = p[1]
            n += 1
        return f"dismissed {n}" + (
            "; REFUSED:\n" + "\n".join(f"- {b}" for b in bad[:10]) if bad else ""
        ), 0

    def _record_facts(self, args: dict[str, Any]) -> tuple[str, int]:
        fs = salvage_facts(args.get("facts") or [])
        acc, rej = self.store.add(fs)
        out = f"accepted {acc}/{len(fs)}"
        if rej:
            out += "; REJECTED (fix and re-record):\n" + "\n".join(
                f"- {str(f.get('value') if isinstance(f, dict) else f)[:60]}: {'; '.join(w)[:300]}"
                for f, w in rej[:12]
            )
        return out, len(rej)

    def _route_agent(
        self, role: str, user: str, budget: int, iteration: int = 0, extra_tools: bool = False
    ) -> None:
        tools = READ_GREP + [RECORD_ROUTES, DISMISS_SITES, FINISH_NOTES]
        handlers = {"record_routes": self._record_routes, "dismiss_sites": self._dismiss_sites}
        system = ROLE_ROUTE_SHARD
        if extra_tools:
            tools = READ_GREP + [RECORD_ROUTES, RECORD_FACTS, DISMISS_SITES, FINISH_NOTES]
            handlers["record_facts"] = self._record_facts
            system += (
                "\nYou may also record non-route facts with record_facts ('<checklist id> | <slot> | <value> | "
                f"<claim> | FILE:LINE: exact quote'); slots: {SPEC.slot_help}."
            )
        self.runner.run(
            f"api-{role}", system, user, tools, budget, ["finish"], iteration, handlers=handlers
        )

    # ------------------------------------------------------------ routes
    def routes(self) -> tuple[list[Route], list[Route]]:
        rs, bd = verify_routes(self.repo, self.raw_routes)
        multi = len(self.servers) > 1
        names = [str(s.get("name")) for s in self.servers if s.get("name")]
        for r in rs:
            if multi:
                r["server"] = self.amap.get(str(r.get("reg_file")), UNATTRIBUTED)
            else:
                r["server"] = names[0] if names else "main"
        return resolve_conflicts(rs, bd)

    def _outstanding(self, files: set[str]) -> tuple[list[Route], list[Site]]:
        routes, bad = verify_routes(self.repo, self.raw_routes)
        good_keys = {(r["method"], r["path"]) for r in routes}
        good_paths = {r["path"] for r in routes}
        s_bad = [
            b
            for b in bad
            if b["path"] not in good_paths
            and (b["method"], b["path"]) not in good_keys
            and any(e.rpartition(":")[0] in files for e in b["evidence"])
        ]
        oblig = {k: v for k, v in self.sites.items() if k not in self.seed_only}
        cov = gates.covered_sites(oblig, routes, self.dismissed)
        return s_bad, [k for k in oblig if k[0] in files and k not in cov]

    def repair_pass(self, label: str, iteration: int = 0) -> int:
        n = 0
        for si, sh in enumerate(self.shards):
            files = {f for f, _ in sh}
            s_bad, s_unacc = self._outstanding(files)
            if not s_bad and not s_unacc:
                continue
            n += 1
            seen: set[tuple[str, str]] = set()
            fb: list[str] = []
            for b in s_bad:
                if (b["method"], b["path"]) not in seen:
                    seen.add((b["method"], b["path"]))
                    fb.append(
                        f"- {b['method']} {b.get('claimed')}: {'; '.join(b['reasons'])[:300]}"
                    )
            un = "\n".join(
                f"- {f}:{ln}: {self.sites[(f, ln)][:140]}" for f, ln in sorted(s_unacc)[:40]
            )
            u = (
                f"Verified registration mechanisms:\n{self.mech_text}\n\nRepair pass for shard {si + 1} "
                f"({', '.join(sorted(files))}).\n"
                + (
                    "These routes are still unverified (the program's reasons follow; re-record corrected "
                    "versions):\n" + "\n".join(fb[:30]) + "\n"
                    if fb
                    else ""
                )
                + (
                    "\nThese candidate sites are still unaccounted (record the route citing them, or dismiss "
                    f"with a reason):\n{un}\n"
                    if un
                    else ""
                )
                + "\n"
                + "\n\n".join(o for _, o in sh)
                + f"\n\nTool-call budget: {self.budgets.repair}."
            )
            self._route_agent(f"{label}{si + 1}", u, self.budgets.repair, iteration)
        return n

    def discover_routes(self) -> None:
        repo, b = self.repo, self.budgets
        base_sites = inv.find_sites(repo)
        per_file: dict[str, list[int]] = defaultdict(list)
        for f, ln in base_sites:
            per_file[f].append(ln)
        seed_by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for s in self.seeds:
            seed_by_file[s["file"]].append(s)
        summary = [
            f"{f}: {len(ls)} sites; e.g. "
            + " | ".join(base_sites[(f, ln)][:90] for ln in sorted(ls)[:2])
            for f, ls in sorted(per_file.items(), key=lambda x: -len(x[1]))[:40]
        ]
        user = (
            f"Repository profile (verified):\n{json.dumps(self.profile, ensure_ascii=False)}\n\nCandidate "
            f"registration-like sites found by a deterministic literal scan ({len(base_sites)} sites; noisy, may "
            "include client code):\n" + "\n".join(summary)
        )
        if self.seeds:
            sf: dict[str, int] = defaultdict(int)
            for s in self.seeds:
                sf[s["file"]] += 1
            user += (
                "\n\nA rule-based scanner (second opinion, may be wrong) proposes routes in these files: "
                + ", ".join(f"{f} ({n})" for f, n in sorted(sf.items(), key=lambda x: -x[1])[:30])
            )
        user += f"\n\nTool-call budget: {b.mechanism}."
        res = self.runner.run(
            "api-mechanism",
            ROLE_MECH,
            user,
            READ_GREP + [SUBMIT_MECH],
            b.mechanism,
            ["submit_mechanisms"],
        )
        sub = res.first("submit_mechanisms") or {}
        mechs: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        raw_m = sub.get("mechanisms") or []
        for m in raw_m if isinstance(raw_m, list) else []:
            if not isinstance(m, dict):
                continue
            evs = m.get("evidence") or []
            evs = evs if isinstance(evs, list) else [evs]
            good = []
            for e in evs:
                pe = parse_ev(e)
                if pe is not None and quote_ok(repo, pe) is not None:
                    good.append(f"{pe['file']}:{pe['line']}")
            (mechs if good else rejected).append(
                {**m, "evidence": good or [str(e)[:80] for e in evs]}
            )
        servers = sub.get("servers") or []
        self.servers = (
            [s for s in servers if isinstance(s, dict)] if isinstance(servers, list) else []
        )
        extra = [str(m["call_site_regex"]) for m in mechs if m.get("call_site_regex")]
        self.sites = inv.find_sites(repo, extra)
        for s in self.seeds:  # hypotheses guide shard planning but are NOT accounting obligations
            k = (s["file"], s["line"])
            if repo.lines(s["file"]) is not None and k not in self.sites:
                self.sites[k] = s["text"]
                self.seed_only.add(k)
        self.mech_text = (
            "\n".join(
                f"- [{m.get('id')}] {m.get('summary')}\n  method: {m.get('method_rule')}\n  path: {m.get('path_rule')}\n"
                f"  params: {m.get('param_rule')}\n  evidence: {', '.join(m['evidence'])}"
                for m in mechs
            )
            or "(none verified)"
        )
        srv_text = "\n".join(
            f"- {s.get('name')}: {s.get('entry_file')} {s.get('notes') or ''}" for s in self.servers
        )
        per_file = defaultdict(list)
        for f, ln in self.sites:
            per_file[f].append(ln)
        self.shards = inv.plan_shards(repo, per_file, b.shard_lines)
        self.log.update(
            {
                "mechanisms": mechs,
                "mechanisms_rejected": rejected,
                "servers": self.servers,
                "sites": len(self.sites),
                "shards": [[f for f, _ in sh] for sh in self.shards],
            }
        )
        for si, sh in enumerate(self.shards):
            files = [f for f, _ in sh]
            site_lines = "\n".join(
                f"- {f}:{ln}: {self.sites[(f, ln)][:140]}"
                for f in files
                for ln in sorted(per_file[f])
            )
            hyp = "\n".join(f"- {s['text']}" for f in files for s in seed_by_file.get(f, []))
            u = (
                f"Reader question: {SPEC.question}\n\nVerified registration mechanisms:\n{self.mech_text}\n"
                + (f"\nServers:\n{srv_text}\n" if srv_text else "")
                + f"\nShard {si + 1}/{len(self.shards)} files: {', '.join(files)}\n\nCandidate sites to account "
                f"for:\n{site_lines}\n"
                + (
                    "\nScanner hypotheses for these files (second opinion; verify, correct prefixes/methods, never "
                    f"copy blindly):\n{hyp}\n"
                    if hyp
                    else ""
                )
                + "\n"
                + "\n\n".join(o for _, o in sh)
                + f"\n\nTool-call budget: {b.route_shard}."
            )
            self._route_agent(f"shard{si + 1}", u, b.route_shard)
        self.log["repair_passes"] = self.repair_pass("repair")
        routes, _ = verify_routes(repo, self.raw_routes)
        vshape = {shape(r["path"]) for r in routes}
        disagree = [s for s in self.seeds if shape(s["path"]) not in vshape]
        if disagree:
            u = (
                f"Verified registration mechanisms:\n{self.mech_text}\n\nA rule-based scanner proposes these routes "
                "that the investigation did not confirm. For each: open the cited line, and either record the "
                "correct route with evidence (fixing prefix/method), or leave it out if it is not a real server "
                "route. Do not record anything you cannot prove.\n"
                + "\n".join(f"- {s['text']}" for s in disagree[:40])
                + f"\n\nTool-call budget: {b.sweep}."
            )
            self._route_agent("sweep", u, b.sweep)
        self.log["disagreements_swept"] = len(disagree)

    def attribute_servers(self) -> None:
        names = [str(s.get("name")) for s in self.servers if s.get("name")]
        if len(names) <= 1:
            return
        routes, _ = verify_routes(self.repo, self.raw_routes)
        files: dict[str, list[Route]] = defaultdict(list)
        for r in routes:
            files[str(r.get("reg_file") or "?")].append(r)
        lst = "\n".join(
            f"- {f}: {len(rs)} routes, e.g. "
            + ", ".join(f"{x['method']} {x['path']}" for x in rs[:3])
            for f, rs in sorted(files.items())
        )
        srv = "\n".join(f"- {s.get('name')} (entry {s.get('entry_file')})" for s in self.servers)
        u = f"Servers:\n{srv}\n\nRegistration files:\n{lst}\n\nTool-call budget: {self.budgets.attribution}."
        res = self.runner.run(
            "api-attribution",
            ROLE_ATTR,
            u,
            READ_GREP + [SUBMIT_ATTR],
            self.budgets.attribution,
            ["submit_attribution"],
        )
        sub = res.first("submit_attribution") or {}
        rejected = 0
        raw = sub.get("assignments") or []
        for a in raw if isinstance(raw, list) else []:
            if not isinstance(a, dict):
                continue
            evs = a.get("evidence") or []
            evs = evs if isinstance(evs, list) else [evs]
            parsed = [parse_ev(e) for e in evs]
            if (
                a.get("server") in names
                and parsed
                and all(p is not None and quote_ok(self.repo, p) is not None for p in parsed)
            ):
                self.amap[str(a.get("file"))] = str(a["server"])
            else:
                rejected += 1
        self.log["attribution"] = dict(self.amap)
        self.log["attribution_rejected"] = rejected

    # ------------------------------------------------------------ non-route facts
    def investigate_facts(self, routes: list[Route]) -> None:
        ids = [i for i in SPEC.ids]

        def guard(subs: list[tuple[str, dict[str, Any]]], fargs: dict[str, Any]) -> str:
            done = {f["item"] for f in self.store.live()}
            done |= {gates.checklist_id_of(x) for x in salvage_strings(fargs.get("unresolved"))}
            done |= set(salvage_strings(fargs.get("covered_by_routes")))
            miss = [i for i in ids if i not in done]
            if not miss:
                return ""
            return (
                f"finish refused once: checklist ids {miss} are neither recorded facts, covered_by_routes, nor "
                "unresolved. Account for each, then call finish again."
            )

        u = (
            f"Reader question: {SPEC.question}\nChecklist:\n{SPEC.checklist_text()}\n\nRepository profile (verified):\n"
            f"{json.dumps(self.profile, ensure_ascii=False)}\n\nRoutes already established:\n{routes_summary(routes, 15)}\n"
            f"Servers: {json.dumps(self.servers, ensure_ascii=False)}\n\nTool-call budget: {self.budgets.api_facts}."
        )
        res = self.runner.run(
            "api-facts",
            ROLE_API_FACTS.format(slots=SPEC.slot_help),
            u,
            READ_GREP + [RECORD_FACTS, FINISH_FACTS],
            self.budgets.api_facts,
            ["finish"],
            handlers={"record_facts": self._record_facts},
            finish_check=guard,
        )
        fin = res.first("finish") or {}
        self.unresolved = salvage_strings(fin.get("unresolved"))
        self.by_routes = set(salvage_strings(fin.get("covered_by_routes")))

    # ------------------------------------------------------------ loop
    def run(self) -> dict[str, Any]:
        self.discover_routes()
        self.attribute_servers()
        routes, bad_routes = self.routes()
        self.log["routes_after_discovery"] = len(routes)
        self.investigate_facts(routes)
        history: list[dict[str, Any]] = []
        status, page, final_md, prose = "failed", "", "", ""
        unacc_prev: list[str] = []
        hint = ""
        ids = SPEC.ids
        for it in range(self.max_iters + 1):
            if it > 0 and unacc_prev:
                self.repair_pass("iter-repair", it)
            if it > 0 and hint:
                u = (
                    f"Reader question: {SPEC.question}\nChecklist:\n{SPEC.checklist_text()}\n\nAudit follow-up. "
                    f"Investigate these and record confirmed routes/facts:\n{hint}\n\nTool-call budget: "
                    f"{self.budgets.rediscover}."
                )
                self._route_agent("rediscover", u, self.budgets.rediscover, it, extra_tools=True)
            routes, bad_routes = self.routes()
            add_doc_code_conflicts(self.store)
            facts = self.store.live()
            have = {f["item"] for f in facts}
            if routes:
                have.add("routes")
            self.unresolved = [
                u
                for u in self.unresolved
                if gates.checklist_id_of(u) in ids and gates.checklist_id_of(u) not in have
            ]
            wr = (
                f"Page: {SPEC.title}\nReader question: {SPEC.question}\n\nVerified facts:\n"
                f"{api_facts_block(facts, routes, self.unresolved)}"
            )
            if history and history[-1]["accepted_findings"]:
                clean_prev = "\n".join(
                    ln for ln in prose.splitlines() if not gates.JUNK_RX.search(ln)
                )[:8000]
                wr += (
                    "\n\nThe previous draft had these problems; fix them:\n"
                    + "\n".join(history[-1]["accepted_findings"])
                    + "\n\nPrevious draft (prose only):\n"
                    + clean_prev
                )
            prose = self.runner.write("api-write", ROLE_API_WRITER, wr, it)
            if gates.has_junk(prose):
                prose = self.runner.write(
                    "api-write-clean",
                    ROLE_API_WRITER,
                    wr
                    + "\n\nYour previous output contained tool-call markup or runaway text. Output ONLY the "
                    "Markdown page, no tool calls, no XML.",
                    it,
                )
            prose = gates.keep_declared_unresolved(prose, self.unresolved)
            prose, dropped_code = gates.drop_unverified_code(prose, facts)
            table = (route_table(routes) if routes else NO_ROUTES) + render_conflicts(facts)
            ph = SPEC.placeholder
            page = (
                prose.replace(ph, table, 1)
                if ph in prose
                else prose + "\n\n## 接口清单\n\n" + table
            )
            det = gates.api_page_checks(page, facts, routes)
            covered_ids = {f["item"] for f in facts} | (
                {"routes"} | self.by_routes if routes else set()
            )
            declared = {gates.checklist_id_of(u) for u in self.unresolved}
            for item in SPEC.checklist:
                if item.id not in covered_ids and item.id not in declared:
                    det.append(
                        f"checklist item {item.id} neither established by a verified fact nor declared unconfirmed: "
                        f"{item.question}"
                    )
            if self.unresolved:
                det.append(
                    "checklist items unresolved: "
                    + ", ".join(sorted(declared))
                    + " — the page cannot pass; "
                    "establish them, or record an evidenced 'note' fact (value = the checklist id) if the item "
                    "does not apply"
                )
            if not routes:
                det.append("no verified HTTP route: the API page cannot pass")
            oblig = {k: v for k, v in self.sites.items() if k not in self.seed_only}
            cov = gates.covered_sites(oblig, routes, self.dismissed)
            unacc = sorted(f"{f}:{ln}" for (f, ln) in oblig if (f, ln) not in cov)
            if unacc:
                det.append(
                    f"{len(unacc)} candidate registration sites neither documented nor dismissed: "
                    + ", ".join(unacc[:15])
                )
            det += gates.doc_only_port_issues(facts)
            final_md = finalize_page(SPEC.title, page, facts, routes)
            det += gates.existing_gate_issues("api", final_md, self.repo.root)
            accepted, dropped, wrong = self._audit(prose, facts, routes, it)
            retracted = n_conf = 0
            for f_, evs in wrong:
                for r_ in gates.finding_ids(f_):
                    if 0 <= r_ - 1 < len(facts):
                        n_conf += make_conflict(self.store, facts[r_ - 1], evs)
                        self.store.retract(facts[r_ - 1])
                        retracted += 1
            acc_all = accepted + [f"[deterministic] {d}" for d in det]
            history.append(
                {
                    "iter": it,
                    "facts": len(facts),
                    "facts_rejected": len(self.store.bad),
                    "routes": len(routes),
                    "routes_rejected": len(bad_routes),
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
            unacc_prev = unacc
            hint = "\n".join(
                [x for x in accepted if x.startswith(("[omission]", "[wrong]"))]
                + [d for d in det if d.startswith(("checklist item", "no verified"))]
            )
        routes, bad_routes = self.routes()
        return {
            "page_type": "api",
            "status": status,
            "iterations": len(history),
            "history": history,
            "facts": self.store.live(),
            "facts_rejected": self.store.bad[-60:],
            "routes": routes,
            "routes_rejected": bad_routes[-80:],
            "unresolved": self.unresolved,
            "dismissed": {f"{f}:{ln}": r for (f, ln), r in self.dismissed.items()},
            "log": self.log,
            "page_draft": page,
            "page": final_md if status == "pass" else "",
        }

    def _audit(
        self, prose: str, facts: list[Any], routes: list[Route], it: int
    ) -> tuple[list[str], list[str], list[Any]]:
        au = (
            f"Page: {SPEC.title}\nReader question: {SPEC.question}\nChecklist:\n{SPEC.checklist_text()}\n\n"
            f"Verified facts:\n{api_facts_block(facts, routes, self.unresolved)}\n\n"
            "PAGE (the route list section was rendered by a program from the verified routes; focus on the prose, "
            f"on omissions of routes/prefixes that exist in source, and on wrong facts):\n{prose}\n\n"
            f"Tool-call budget: {self.budgets.audit}."
        )
        res = self.runner.run(
            "api-audit",
            ROLE_AUDITOR.format(title=SPEC.title),
            au,
            READ_GREP + [SUBMIT_AUDIT],
            self.budgets.audit,
            ["submit_audit"],
            it,
            finish_check=gates.audit_submit_guard,
        )
        audit = res.first("submit_audit") or {"findings": []}
        return accept_findings(self.repo, audit.get("findings") or [], prose)


def run_api_page(
    runner: AgentRunner,
    repo: RepoView,
    profile: dict[str, Any],
    budgets: Budgets,
    max_iters: int,
    seeds: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return ApiPageLoop(runner, repo, profile, budgets, max_iters, seeds).run()
