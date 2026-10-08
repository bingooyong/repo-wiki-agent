"""Program-rendered page parts and the adapter to the repository's page contract.

Lists the program can build from verified facts / routes (modules, entry points, env vars, entity
fields, relations, routes) are rendered here, never by the writer. They are rendered as one
sentence per line (not markdown tables) so the page keeps the prose density the existing gates
require. ``[Fn]`` / ``[Rn]`` ids become ``<cite>FILE:LINE</cite>`` citations of verified lines.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from repo_wiki.agent_loop.gates import ID_GROUP_RX
from repo_wiki.agent_loop.verifier import Fact, Route

H1_RX = re.compile(r"^#\s+\S")
H2_RX = re.compile(r"^##\s+(.+?)\s*$")
TOC_NAMES = {"目录", "table of contents", "contents", "toc"}


def fid(facts: list[Fact], f: Fact) -> str:
    return f"F{facts.index(f) + 1}"


def facts_block(facts: list[Fact], unresolved: list[str]) -> str:
    lines = [
        f"[F{i + 1}] ({f['item']}/{f['slot']}) value={f['value']!r} — {f['claim']}  "
        f"(evidence: {', '.join(f['evidence'])})"
        for i, f in enumerate(facts)
    ]
    out = "\n".join(lines)
    if unresolved:
        out += "\n\nUnresolved checklist items:\n" + "\n".join(f"- {u}" for u in unresolved)
    return out


def _code(v: str) -> str:
    return "`" + str(v).replace("`", "'") + "`"


# ------------------------------------------------------------------ fact pages
def render_tables(
    page_type: str, facts: list[Fact], mod_unresolved: dict[str, str] | None = None
) -> str:
    if page_type == "overview":
        return _render_overview(facts, mod_unresolved or {})
    if page_type == "install":
        envs = sorted((f for f in facts if f["slot"] == "env"), key=lambda x: x["value"])
        if not envs:
            return ""
        return "### 环境变量\n\n" + "\n\n".join(
            f"环境变量 {_code(f['value'])}：{f['claim']} [{fid(facts, f)}]" for f in envs
        )
    if page_type == "datamodel":
        return _render_datamodel(facts)
    return ""


def _render_overview(facts: list[Fact], mod_unresolved: dict[str, str]) -> str:
    mods = sorted((f for f in facts if f["slot"] == "module"), key=lambda x: x["value"])
    ents = [f for f in facts if f["slot"] == "entry"]
    out: list[str] = []
    if ents:
        out.append("### 入口")
        out += [f"入口 {_code(f['value'])}：{f['claim']} [{fid(facts, f)}]" for f in ents]
    if mods or mod_unresolved:
        out.append("### 模块一览")
        out += [f"模块 {_code(f['value'])}：{f['claim']} [{fid(facts, f)}]" for f in mods]
        out += [
            f"模块 {_code(k.split(' ', 1)[0])}：未能确认其职责（{str(v).split(':', 2)[-1].strip()[:100]}）。"
            for k, v in sorted(mod_unresolved.items())
        ]
    if len(mods) >= 2:
        nodes = ["```mermaid", "flowchart LR", '    repo["仓库"]']
        for i, f in enumerate(mods, 1):
            label = f["value"].replace('"', "'")
            nodes.append(f'    repo --> m{i}["{label}"]')
        nodes.append("```")
        out.append("\n".join(nodes))
    return "\n\n".join(out) or "未能从源码确认模块划分。"


def _render_datamodel(facts: list[Fact]) -> str:
    ents = [f for f in facts if f["slot"] == "entity"]
    if not ents:
        return "未能从源码确认任何持久化实体。"
    out: list[str] = []
    by_ent: dict[str, list[Fact]] = defaultdict(list)
    for f in facts:
        if f["slot"] == "field":
            by_ent[f["value"].partition(".")[0].lower()].append(f)
    keys = {f["value"].partition(":")[0].strip().lower(): f for f in facts if f["slot"] == "key"}
    rels = [f for f in facts if f["slot"] == "relation"]
    nor = {f["value"].lower(): f for f in facts if f["slot"] == "no_relation"}
    for e in ents:
        n = e["value"]
        out.append(f"### {_code(n)}")
        out.append(f"{e['claim']} [{fid(facts, e)}]")
        if n.lower() in keys:
            k = keys[n.lower()]
            out.append(f"主键/键：{k['claim']} [{fid(facts, k)}]")
        out += [
            f"字段 {_code(f['value'].partition('.')[2])}：{f['claim']} [{fid(facts, f)}]"
            for f in by_ent.get(n.lower(), [])
        ]
        if n.lower() in nor:
            out.append(f"外键：{nor[n.lower()]['claim']} [{fid(facts, nor[n.lower()])}]")
    cts = [f for f in facts if f["slot"] in ("code_type", "not_entity")]
    if cts:
        out.append("### 代码中的模型类型")
        out += [
            f"类型 {_code(f['value'])}（{'对应持久化实体' if f['slot'] == 'code_type' else '非持久化'}）："
            f"{f['claim']} [{fid(facts, f)}]"
            for f in cts
        ]
    if rels:
        out.append("### 实体关系")
        out += [f"关系 {_code(f['value'])}：{f['claim']} [{fid(facts, f)}]" for f in rels]
        names = {e["value"].lower(): re.sub(r"\W", "_", e["value"]) for e in ents}
        er = ["```mermaid", "erDiagram"]
        for f in rels:
            m = re.match(r"^\s*([\w]+)\.(\w+)\s*->\s*(\w+)", f["value"])
            if m and m.group(1).lower() in names and m.group(3).lower() in names:
                er.append(
                    f'    {names[m.group(3).lower()]} ||--o{{ {names[m.group(1).lower()]} : "{m.group(2)}"'
                )
        er.append("```")
        if len(er) > 3:
            out.append("\n".join(er))
    return "\n\n".join(out)


def render_conflicts(facts: list[Fact]) -> str:
    cs = [f for f in facts if f["slot"] == "conflict"]
    if not cs:
        return ""
    return "\n\n### 来源不一致\n\n" + "\n\n".join(f"{f['claim']} [{fid(facts, f)}]" for f in cs)


# ------------------------------------------------------------------ API page
def route_table(routes: list[Route]) -> str:
    groups: dict[tuple[str, str], list[tuple[int, Route]]] = defaultdict(list)
    for i, r in enumerate(routes):
        groups[(str(r.get("server") or "main"), str(r.get("reg_file") or "?"))].append((i, r))
    out: list[str] = []
    cur = None
    for g in sorted(groups):
        if g[0] != cur:
            cur = g[0]
            n = sum(len(v) for k, v in groups.items() if k[0] == cur)
            out.append(f"### 服务：{cur}（{n} 条）")
        out.append(f"#### 注册于 {_code(g[1])}")
        for i, r in sorted(groups[g], key=lambda x: (x[1]["path"], x[1]["method"])):
            handler = f"，处理函数 {_code(r['handler'])}" if r.get("handler") else ""
            out.append(f"接口 {_code(r['method'] + ' ' + r['path'])}{handler}。 [R{i + 1}]")
    mer = route_mermaid(routes)
    if mer:
        out.append(mer)
    return "\n\n".join(out)


def route_mermaid(routes: list[Route]) -> str:
    """Deterministic overview diagram: server -> path groups (or routes when there is one group)."""
    if len(routes) < 2:
        return ""
    by_srv: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in routes:
        segs = [s for s in r["path"].strip("/").split("/") if s]
        group = "/" + "/".join(segs[:2]) if len(segs) > 1 else "/" + (segs[0] if segs else "")
        by_srv[str(r.get("server") or "main")][group] += 1
    lines = ["```mermaid", "flowchart LR"]
    edges = 0
    for si, (srv, groups) in enumerate(sorted(by_srv.items()), 1):
        lines.append(f'    s{si}["{srv.replace(chr(34), chr(39))}"]')
        if len(groups) >= 2 or len(by_srv) >= 2:
            for gi, (g, n) in enumerate(sorted(groups.items()), 1):
                lines.append(f'    s{si} --> g{si}_{gi}["{g}（{n}）"]')
                edges += 1
        else:
            for ri, r in enumerate(sorted(routes, key=lambda x: x["path"])[:12], 1):
                if str(r.get("server") or "main") == srv:
                    lines.append(f'    s{si} --> r{si}_{ri}["{r["method"]} {r["path"]}"]')
                    edges += 1
    lines.append("```")
    return "\n".join(lines) if edges >= 2 else ""


def routes_summary(routes: list[Route], limit: int = 40) -> str:
    if len(routes) <= limit:
        return "\n".join(
            f"[R{i + 1}] {r['method']} {r['path']} server={r.get('server')} handler={r.get('handler')} "
            f"evidence: {', '.join(r['evidence'])}"
            for i, r in enumerate(routes)
        )
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, r in enumerate(routes):
        segs = r["path"].strip("/").split("/")
        g = "/" + "/".join(segs[:2]) if len(segs) > 1 else "/" + segs[0]
        groups[(str(r.get("server") or "main"), g)].append(i)
    per_srv: dict[str, int] = defaultdict(int)
    for (sv, _g), ids in groups.items():
        per_srv[sv] += len(ids)
    lines = [
        f"{len(routes)} verified routes (full table rendered by program, grouped by server). Routes "
        "belong ONLY to the server named; never attribute a route to another server."
    ]
    for sv in sorted(per_srv):
        lines.append(f"Server {sv}: {per_srv[sv]} routes")
        for (sv2, g), ids in sorted(groups.items()):
            if sv2 == sv:
                rep = ", ".join(
                    f"[R{j + 1}] {routes[j]['method']} {routes[j]['path']}" for j in ids[:2]
                )
                lines.append(f"  - {g}: {len(ids)} routes; e.g. {rep}")
    return "\n".join(lines)


def api_facts_block(facts: list[Fact], routes: list[Route], unresolved: list[str]) -> str:
    return (
        facts_block(facts, [])
        + "\n"
        + routes_summary(routes)
        + (
            "\n\nUnresolved checklist items:\n" + "\n".join(f"- {u}" for u in unresolved)
            if unresolved
            else ""
        )
    )


# ------------------------------------------------------------------ contract adapter
def _cite(ref: str) -> str:
    return f"<cite>{ref}</cite>"


def convert_ids(text: str, facts: list[Fact], routes: list[Route]) -> str:
    """[F3] / [R2] / [F1, F4] -> <cite>FILE:LINE</cite> of the verified evidence lines."""

    def refs_for(ident: str) -> list[str]:
        idx = int(ident[1:]) - 1
        if ident.startswith("F") and 0 <= idx < len(facts):
            return list(facts[idx]["evidence"][:2])
        if ident.startswith("R") and 0 <= idx < len(routes):
            ev = routes[idx]["evidence"]
            return [ev[-1]] if ev else []
        return []

    def repl(m: re.Match[str]) -> str:
        refs: list[str] = []
        for ident in re.findall(r"[FR]\d+", m.group(1)):
            for r in refs_for(ident):
                if r not in refs:
                    refs.append(r)
        return "".join(_cite(r) for r in refs)

    out: list[str] = []
    in_code = False
    for ln in text.splitlines():
        if ln.strip().startswith("```"):
            in_code = not in_code
            out.append(ln)
            continue
        if in_code:
            out.append(ln)
            continue
        if ln.lstrip().startswith("#"):
            out.append(ID_GROUP_RX.sub("", ln).rstrip())  # never cite inside headings
            continue
        out.append(ID_GROUP_RX.sub(repl, ln))
    return "\n".join(out)


def h2_headings(text: str) -> list[str]:
    heads: list[str] = []
    in_code = False
    for ln in text.splitlines():
        if ln.strip().startswith("```"):
            in_code = not in_code
            continue
        m = None if in_code else H2_RX.match(ln)
        if m and m.group(1).strip().lower() not in TOC_NAMES:
            heads.append(m.group(1).strip())
    return heads


def finalize_page(title: str, body: str, facts: list[Fact], routes: list[Route]) -> str:
    """Writer prose + rendered parts -> page in the repository's contract: one H1 title, a
    '## 目录' listing the real H2 headings, ``<cite>`` citations, no ids, no TOC from the writer."""
    lines = []
    in_code = False
    skipping_toc = False
    for ln in body.strip().splitlines():
        s = ln.strip()
        if s.startswith("```"):
            in_code = not in_code
        if not in_code and H1_RX.match(s):
            continue
        if not in_code:
            m = re.match(r"^#{1,6}\s+(.+?)\s*$", s)
            if m:
                skipping_toc = m.group(1).strip().lower() in TOC_NAMES
                if skipping_toc:
                    continue
        if skipping_toc:
            continue
        lines.append(ln)
    text = "\n".join(lines).strip()
    if not h2_headings(text):
        text = "## 概述\n\n" + text
    text = convert_ids(text, facts, routes)
    toc = ["## 目录", ""] + [f"{i}. {h}" for i, h in enumerate(h2_headings(text), 1)]
    page = f"# {title}\n\n" + "\n".join(toc) + "\n\n" + text
    return re.sub(r"\n{3,}", "\n\n", page).strip() + "\n"


def run_report_summary(result: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "page_type",
        "status",
        "iterations",
        "unresolved",
        "modules_unresolved",
        "aborted",
        "log",
        "stats",
    )
    out = {k: result.get(k) for k in keep if k in result}
    out["facts"] = len(result.get("facts") or [])
    out["routes"] = len(result.get("routes") or [])
    out["facts_rejected"] = len(result.get("facts_rejected") or [])
    hist = result.get("history") or []
    out["last_issues"] = (hist[-1].get("accepted_findings") if hist else []) or []
    return out
