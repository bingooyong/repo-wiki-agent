"""Deterministic page gates of the agent loop.

They only ever add failure reasons; the existing repository gates (strict verifier / handbook
checks) still run unchanged as the final gate after the page is written.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from repo_wiki.agent_loop.evidence import is_doc_evidence, norm, shape, ws
from repo_wiki.agent_loop.inventory import ENV_NAME_RX, Item
from repo_wiki.agent_loop.verifier import Fact, Route

RECALL_MIN = 0.9
MAX_PAGE_CHARS = 40_000
JUNK_RX = re.compile(
    r"<function_calls>|<invoke\b|</invoke>|<parameter\b|\]<\]\w+\[>\[|</?think>|<tool_call>|"
    r"</?minimax:tool_call>|\uFFFD"
)
ROUTE_TOKEN = re.compile(
    r"(?:\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b[\s`|]*)?`?(/[A-Za-z0-9_\-{}<>:./*]*[A-Za-z0-9_}>/*])`?"
)
HTTP_ROW = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD", "ANY")
ID_GROUP_RX = re.compile(r"\[((?:[FR]\d+)(?:\s*[,，、;；]\s*[FR]\d+)*)\]")
UNRESOLVED_PREFIX = "未能从源码确认"


def cited_ids(text: str) -> list[str]:
    """Every [F3] / [R2] id, including grouped forms like [F1, F4]."""
    return [i for g in ID_GROUP_RX.findall(text or "") for i in re.findall(r"[FR]\d+", g)]


def has_junk(text: str) -> bool:
    return bool(JUNK_RX.search(text or "")) or len(text or "") > MAX_PAGE_CHARS


def checklist_id_of(entry: object) -> str:
    return str(entry).split(":")[0].strip()


# ------------------------------------------------------------------ code blocks
def _code_lines(text: str) -> list[tuple[bool, str, str]]:
    """(in_non_mermaid_code, fence_lang, line) for every line."""
    out = []
    in_code, lang = False, ""
    for ln in (text or "").splitlines():
        s = ln.strip()
        if s.startswith("```"):
            in_code, lang = (not in_code), (s[3:].strip() if not in_code else "")
            out.append((False, "", ln))
            continue
        out.append((in_code and lang != "mermaid", lang, ln))
    return out


def verified_commands(facts: list[Fact]) -> set[str]:
    return {norm(f["value"]) for f in facts if f["slot"] in ("command", "verify")}


def drop_unverified_code(prose: str, facts: list[Fact]) -> tuple[str, list[str]]:
    """Code-block lines that are not verified command/verify values are removed deterministically
    (removal never invents); empty code blocks disappear."""
    cmds = verified_commands(facts)
    out: list[str] = []
    dropped: list[str] = []
    for in_code, _lang, ln in _code_lines(prose):
        s = ln.strip()
        if in_code and s and not s.startswith("#") and norm(s.lstrip("$ ")) not in cmds:
            dropped.append(s)
            continue
        out.append(ln)
    text = re.sub(r"```[^\n]*\n```\n?", "", "\n".join(out))
    return text, dropped


def keep_declared_unresolved(prose: str, unresolved: list[str]) -> str:
    """'未能从源码确认' lines survive only for checklist items actually declared unresolved."""
    ids = {checklist_id_of(u) for u in unresolved if checklist_id_of(u)}
    return "\n".join(
        ln
        for ln in prose.splitlines()
        if not ln.strip().startswith(UNRESOLVED_PREFIX)
        or any(re.search(rf"\b{re.escape(i)}\b", ln) for i in ids)
    )


# ------------------------------------------------------------------ fact-page checks
def page_checks(
    prose: str, facts: list[Fact], checklist_ids: list[str], unresolved: list[str]
) -> list[str]:
    issues: list[str] = []
    junk = JUNK_RX.findall(prose)
    if junk or len(prose) > MAX_PAGE_CHARS:
        issues.append(
            f"page contains model/tool markup or runaway text ({len(junk)} markers, {len(prose)} chars); "
            "rewrite cleanly"
        )
    ids = {f"F{i + 1}" for i in range(len(facts))}
    for cid in sorted(set(cited_ids(prose))):
        if cid not in ids:
            issues.append(f"citation [{cid}] does not exist")
    cmds = verified_commands(facts)
    corpus = norm(
        " ".join(
            [f["value"] for f in facts]
            + [q for f in facts for q in f["quotes"]]
            + [f["claim"] for f in facts]
            + [e for f in facts for e in f["evidence"]]
        )
    )
    for in_code, _lang, ln in _code_lines(prose):
        s = ln.strip()
        if in_code:
            if s and not s.startswith("#") and norm(s.lstrip("$ ")) not in cmds:
                issues.append(f"code line is not a verified command: {s[:100]!r}")
            continue
        if s.startswith("```"):
            continue
        for tok in re.findall(r"`([^`]{2,120})`", ln):
            if norm(tok) not in corpus:
                issues.append(f"inline code not backed by verified facts: `{tok[:80]}`")
        for m in re.finditer(r"(?i)(端口|port|监听|listen)\D{0,8}(\d{2,5})\b", ln):
            if m.group(2) not in corpus:
                issues.append(f"port {m.group(2)} not in verified facts")
    have = {f["item"] for f in facts}
    for cid in checklist_ids:
        if cid not in have and not any(
            re.match(rf"\s*{re.escape(cid)}\b", str(u)) for u in unresolved
        ):
            issues.append(
                f"checklist item {cid} has no verified fact and is not declared unresolved"
            )
    return sorted(set(issues))[:40]


def doc_only_port_issues(facts: list[Fact]) -> list[str]:
    """A doc-only port/verify value that disagrees with the code port must be shown as a conflict."""
    issues: list[str] = []
    code_ports = {
        x["value"] for x in facts if x["slot"] == "port" and not is_doc_evidence(x["evidence"])
    }
    if not code_ports:
        return issues
    for f in facts:
        if f["slot"] not in ("port", "verify") or not is_doc_evidence(f["evidence"]):
            continue
        if any(cp in f["value"] for cp in code_ports):
            continue
        if any(
            x["slot"] == "conflict" and any(e in x["evidence"] for e in f["evidence"])
            for x in facts
        ):
            continue
        issues.append(
            f"{f['value']!r} comes from documentation only and disagrees with the code/config default "
            f"{sorted(code_ports)}; it must appear as a conflict"
        )
    return issues


def entity_field_issues(facts: list[Fact]) -> list[str]:
    with_fields = {f["value"].partition(".")[0].lower() for f in facts if f["slot"] == "field"}
    missing = [
        f["value"] for f in facts if f["slot"] == "entity" and f["value"].lower() not in with_fields
    ]
    return [f"entities without any verified field: {', '.join(missing[:10])}"] if missing else []


# ------------------------------------------------------------------ obligations / recall
def covered(obligations: dict[str, Item], facts: list[Fact], dismissed: dict[str, Any]) -> set[str]:
    idx: dict[str, set[int]] = defaultdict(set)
    mods = set()
    for f in facts:
        if f["slot"] == "module":
            mods.add(f["value"].strip().rstrip("/").removeprefix("./") or ".")
        for e in f["evidence"]:
            fl, _, ln = e.rpartition(":")
            if ln.isdigit():
                idx[fl].add(int(ln))
    env_vals = [norm(f["value"]) for f in facts if f["slot"] == "env"]
    cov: set[str] = set()
    for k, o in obligations.items():
        if k in dismissed:
            cov.add(k)
        elif o.get("module"):
            if (k.rstrip("/") or ".") in mods:
                cov.add(k)
        elif o.get("kind") in ("env", "dotenv"):
            # an env-var line is covered only by an env fact naming that variable
            names = set(ENV_NAME_RX.findall(o.get("text", "")))
            near = any(abs(o["line"] - x) <= 3 for x in idx.get(o["file"], ()))
            if (not names and near) or any(norm(n) in ev for n in names for ev in env_vals):
                cov.add(k)
        elif any(abs(o["line"] - x) <= 3 for x in idx.get(o["file"], ())):
            cov.add(k)
    return cov


def recall(
    obligations: dict[str, Item], facts: list[Fact], dismissed: dict[str, Any]
) -> tuple[float, list[str]]:
    """Obligations established by verified facts / obligations not validly dismissed."""
    denom = [k for k in obligations if k not in dismissed]
    by_fact = covered(obligations, facts, {})
    missing = [k for k in denom if k not in by_fact]
    return ((len(denom) - len(missing)) / len(denom) if denom else 1.0), missing


def norm_key(key: object, obligations: dict[str, Item]) -> str | None:
    """Map a dismiss key the model wrote ('FILE:LINE: text', './dir/', 'dir') onto an obligation."""
    if key is None:
        return None
    k = str(key).strip().strip("`")
    if k in obligations:
        return k
    m = re.match(r"\s*(?:\./)?([^\s:]+:\d+)", k)
    if m and m.group(1) in obligations:
        return m.group(1)
    k2 = k.removeprefix("./").rstrip("/")
    for cand in (k2, k2 + "/"):
        if cand in obligations:
            return cand
    for ok in obligations:  # module keys carry a description: '<dir>/ (root files: ...)'
        if obligations[ok].get("module") and ok.split(" ", 1)[0].rstrip("/") == k2 and " " in ok:
            return ok
    return None


BUDGET_RX = re.compile(
    r"(?i)budget|could not (read|verify|confirm)|unable to|not enough (time|calls)|ran out|validator|reject"
    r"|无法读取|预算|来不及|校验器|被拒"
)
COVERED_RX = re.compile(
    r"(?i)covered|merged|already (recorded|documented)|duplicate of|same as|included in|已合并|已覆盖|已记录|已包含|重复"
)
AUX_RX = re.compile(
    r"(?i)\btest|lint|format|prettier|coverage|\bci\b|tooling|example only|测试|格式化|示例"
)
MODULE_DISMISS_RX = re.compile(
    r"(?i)vendor|generated|third[- ]?party|build output|\bdist\b|node_modules|\bempty\b|no source|"
    r"docs?[- ]only|documentation only|static assets?|\bassets?\b|binary|cache|editor|\bide\b|\.github|"
    r"ci config|生成|第三方|空目录|仅文档|静态资源"
)


def vet_dismissal(
    item: object, obligations: dict[str, Item], facts: list[Fact]
) -> tuple[str | None, str | None]:
    """-> (obligation key, None) when the dismissal is acceptable, else (None, why refused)."""
    if not isinstance(item, dict):
        return None, "item must be 'KEY | reason'"
    k = norm_key(item.get("key"), obligations)
    reason = str(item.get("reason") or "")
    if not k:
        return None, (
            f"unknown key {str(item.get('key'))[:60]!r} (use the exact 'FILE:LINE' or directory key from "
            "the inventory list)"
        )
    if not reason.strip():
        return None, f"{k}: a dismissal needs a reason"
    if BUDGET_RX.search(reason):
        return None, (
            f"{k}: 'no budget / could not read' is not a reason; record the fact (a module role can be "
            "proven by one line of one file inside it)"
        )
    ob = obligations[k]
    if COVERED_RX.search(reason) and not ob.get("module"):
        cited = any(
            e.rpartition(":")[0] == ob.get("file")
            and e.rpartition(":")[2].isdigit()
            and abs(int(e.rpartition(":")[2]) - int(ob.get("line", -99))) <= 3
            for f in facts
            for e in f["evidence"]
        )
        if not cited:
            return None, (
                f"{k}: 'already covered/merged' is false — no recorded fact cites this line yet; record "
                "the fact that cites it"
            )
    if ob.get("kind") in ("env", "dotenv") and not AUX_RX.search(reason):
        names = set(ENV_NAME_RX.findall(ob.get("text", "")))
        have_env = {norm(f["value"]) for f in facts if f["slot"] == "env"}
        if names and not any(
            norm(n) in have_env or any(norm(n) in h for h in have_env) for n in names
        ):
            return None, (
                f"{k}: {sorted(names)[:3]} has no env fact yet — 'duplicate/covered elsewhere' only counts "
                "when an env fact for it exists; record it (cite the line that reads it), or dismiss only "
                "test/tooling-only variables"
            )
    if ob.get("module") and not MODULE_DISMISS_RX.search(reason):
        return None, (
            f"{k}: a source directory cannot be dismissed for this reason; record a module fact (role "
            "proven by a line of a file inside it). Only vendored/generated/build-output/asset/docs-only/"
            "empty directories may be dismissed."
        )
    return k, None


# ------------------------------------------------------------------ audit findings
def finding_ids(finding: dict[str, Any], prefix: str = "F") -> list[int]:
    ids = [int(x) for x in re.findall(rf"{prefix}(\d+)", str(finding.get("fact_id") or ""))]
    return ids or [
        int(x) for x in re.findall(rf"\[{prefix}(\d+)\]", str(finding.get("page_quote") or ""))
    ]


def audit_submit_guard(_submits: list[tuple[str, dict[str, Any]]], args: dict[str, Any]) -> str:
    bad = [
        f
        for f in (args.get("findings") or [])
        if isinstance(f, dict)
        and f.get("type") == "wrong"
        and not (finding_ids(f) or finding_ids(f, "R"))
    ]
    if not bad:
        return ""
    return (
        "submit refused once: every 'wrong' finding must name the disputed fact in fact_id (the [Fn] the "
        f"page cites); {len(bad)} do not. Add the ids, or re-type page text with no fact as 'invented' "
        "with page_quote."
    )


# ------------------------------------------------------------------ API page checks
def api_page_checks(page: str, facts: list[Fact], routes: list[Route]) -> list[str]:
    issues: list[str] = []
    junk = JUNK_RX.findall(page)
    if junk or len(page) > MAX_PAGE_CHARS:
        issues.append(
            f"page contains model/tool markup or runaway text ({len(junk)} markers, {len(page)} chars); "
            "rewrite cleanly"
        )
    ids = {f"F{i + 1}" for i in range(len(facts))} | {f"R{i + 1}" for i in range(len(routes))}
    for cid in sorted(set(cited_ids(page))):
        if cid not in ids:
            issues.append(f"citation [{cid}] does not exist")
    corpus = ws(" ".join(str(q) for f in facts for q in f.get("quotes", [])))
    vshapes = {shape(r["path"]) for r in routes}
    for in_code, _lang, ln in _code_lines(page):
        if in_code and ln.strip() and not ln.strip().startswith("#"):
            cmd = ws(ln.strip().lstrip("$ ").strip())
            if (
                cmd
                and cmd not in corpus
                and not (cmd.startswith("/") and shape(cmd.split()[-1]) in vshapes)
            ):
                issues.append(f"code line not backed by verified facts: {cmd[:100]!r}")
    for ln in page.splitlines():
        if ln.strip().startswith("|"):
            cells = [c.strip(" `*") for c in ln.strip().strip("|").split("|")]
            if cells and cells[0].upper() in HTTP_ROW and not re.search(r"\[R\d+\]", ln):
                issues.append(f"route table row without verified route id: {ln.strip()[:100]!r}")
    prefixes = {
        shape("/".join(s.split("/")[:k])) for s in vshapes for k in range(2, s.count("/") + 1)
    }
    for in_code, lang, ln in _code_lines(page):
        if in_code or lang == "mermaid":
            continue
        for m in ROUTE_TOKEN.finditer(ln):
            method, path = m.group(1), m.group(2)
            if "." in path.rsplit("/", 1)[-1] or len(path) < 2:
                continue  # looks like a file path
            sp = shape(path)
            if sp in vshapes or sp in prefixes:
                if method and not any(
                    r["method"] in (method, "ANY") and shape(r["path"]) == sp for r in routes
                ):
                    issues.append(f"method/path pair not verified: {method} {path}")
                continue
            if method:
                issues.append(f"route not in verified list: {method} {path}")
    return sorted(set(issues))[:40]


def covered_sites(
    sites: dict[tuple[str, int], str], routes: list[Route], dismissed: dict[tuple[str, int], str]
) -> set[tuple[str, int]]:
    """Literal-aware accounting: a site is covered when a verified route cites that exact line, or a
    line within 3 of it AND uses the site's '/...' literal as one of its parts (pure proximity would
    let an adjacent registration mask an omission), or when the site was dismissed."""
    from repo_wiki.agent_loop.inventory import site_literals

    cites: dict[str, list[tuple[int, set[str]]]] = defaultdict(list)
    for r in routes:
        parts = {p.strip("/") for p in r.get("parts", [])}
        for e in r["evidence"]:
            f, _, ln = e.rpartition(":")
            if ln.isdigit():
                cites[f].append((int(ln), parts))
    cov: set[tuple[str, int]] = set()
    for (f, line), text in sites.items():
        if (f, line) in dismissed:
            cov.add((f, line))
            continue
        lits = site_literals(text)
        for ln, parts in cites.get(f, []):
            if ln == line or (abs(ln - line) <= 3 and (not lits or lits & parts)):
                cov.add((f, line))
                break
    return cov


# existing-gate failures that only more facts can fix (the others are writer/presentation issues)
_FACT_GATE_CODES = (
    "QODER_HANDBOOK_INSTALL_RUN",
    "QODER_HANDBOOK_DATA_MODEL_SOURCE",
    "QODER_HANDBOOK_OVERVIEW_IDENTITY",
    "QODER_DATA_MODEL_ER_MERMAID_MISSING",
    "QODER_HANDBOOK_ROUTE_CROSSCHECK",
)


def needs_investigation(issue: str) -> bool:
    """Should a deterministic issue send investigators back to the repository (vs. only the
    writer)?"""
    if issue.startswith("existing gate"):
        return any(code in issue for code in _FACT_GATE_CODES)
    return not issue.startswith(
        ("page contains", "citation [", "code line", "inline code", "port ")
    )


# ------------------------------------------------------------------ existing handbook gates (pre-check)
_RELATION_TOKENS = (
    "relationship",
    "relations",
    "关联",
    "关系",
    "foreign key",
    "join",
    "belongs to",
    "has many",
    "references",
)


def existing_gate_issues(page_type: str, markdown: str, repo_root: Path) -> list[str]:
    """Run the repository's own per-page handbook gates on the final page inside the loop, so a page
    that the final gate would reject is reworked (or marked failed) instead of shipped. This only
    adds failure reasons; the gates themselves are unchanged and still run afterwards."""
    from repo_wiki.verifier import handbook as hb
    from repo_wiki.verifier.qoder_strict_verifier import (
        QoderLikeVerifierService,
        is_qoder_page_dump,
        qoder_prose_density,
    )

    issues: list[str] = []
    if is_qoder_page_dump(markdown, max_list_ratio=QoderLikeVerifierService.MAX_LIST_RATIO):
        issues.append(
            "existing gate QODER_PAGE_DUMP: the page is a list dump or repeats filler; write connected "
            "prose sentences instead of bullet lists"
        )
    density = qoder_prose_density(markdown)
    if density < QoderLikeVerifierService.MIN_PROSE_DENSITY:
        issues.append(
            f"existing gate QODER_PROSE_TOO_LOW: prose density {density:.2f} < "
            f"{QoderLikeVerifierService.MIN_PROSE_DENSITY:.2f}; explain in sentences, avoid tables and bare lists"
        )
    if hb.contains_generator_meta(markdown):
        issues.append(
            "existing gate QODER_HANDBOOK_GENERATOR_META: page contains generator meta text"
        )
    if hb.contains_evidence_meta_talk(markdown):
        issues.append(
            "existing gate: page talks about 'evidence' instead of the project (meta talk)"
        )
    if hb.handbook_page_is_fallback_stub(markdown):
        issues.append("existing gate: page matches a fallback-stub marker")
    if "<cite>" not in markdown:
        issues.append("existing gate QODER_CITATION_MISSING: page has no <cite> citation")
    if page_type == "overview" and not hb.overview_identity_satisfied(markdown, repo_root):
        issues.append(
            "existing gate QODER_HANDBOOK_OVERVIEW_IDENTITY: the page must state the project name as the "
            "repository declares it (README title / manifest name)"
        )
    if page_type == "install":
        readmes = hb.existing_readme_names(repo_root)
        if hb.install_run_clue_count(markdown, repo_root) < 2:
            issues.append(
                "existing gate QODER_HANDBOOK_INSTALL_RUN: fewer than two of the repository's own run clues "
                "(package manager / container / database commands documented in README or build files)"
            )
        if not hb.has_readme_citation(markdown, readmes):
            issues.append("existing gate QODER_HANDBOOK_INSTALL_RUN: no fact cites the README")
        if not hb.has_readme_run_section_citation(markdown, repo_root):
            issues.append(
                "existing gate QODER_HANDBOOK_INSTALL_RUN: no fact cites a line in the README's "
                "install/run/usage section"
            )
        if not hb.install_fenced_commands_are_grounded(markdown, repo_root):
            issues.append(
                "existing gate QODER_HANDBOOK_INSTALL_RUN: a fenced command is not grounded in the repo"
            )
        if not hb.install_go_builds_use_package_dir(markdown, repo_root):
            issues.append(
                "existing gate QODER_HANDBOOK_INSTALL_RUN: go build must target the package dir"
            )
        errs = hb.install_page_render_errors(markdown)
        if errs:
            issues.append(f"existing gate QODER_HANDBOOK_INSTALL_FENCE: {'; '.join(errs)[:200]}")
        if not hb.has_fenced_install_run_command(markdown, repo_root):
            issues.append(
                "existing gate QODER_HANDBOOK_INSTALL_FENCE: no fenced install/run command (record the "
                "README/Makefile command lines as 'command' facts)"
            )
    if page_type == "datamodel":
        offenders = hb.model_definition_cite_offenders(markdown, repo_root)
        if offenders or not hb.has_data_model_source_citation(markdown, repo_root):
            issues.append(
                "existing gate QODER_HANDBOOK_DATA_MODEL_SOURCE: every model class / schema source must be "
                f"named and cited at its definition; offenders: {', '.join(offenders[:8]) or 'source files'}"
            )
        low = markdown.lower()
        if any(t in low for t in _RELATION_TOKENS) and "erdiagram" not in low:
            issues.append(
                "existing gate QODER_DATA_MODEL_ER_MERMAID_MISSING: the page discusses relationships but has "
                "no ER diagram (only verified relation facts produce one)"
            )
    blocks = hb.extract_mermaid_blocks(markdown)
    for block in blocks:
        er = "erdiagram" in block.lower()
        if (er and hb.mermaid_edge_count(block) < 1 and block.lower().count("{") > 1) or (
            not er and hb.mermaid_edge_count(block) < 2
        ):
            issues.append("existing gate QODER_HANDBOOK_PLACEHOLDER_MERMAID: thin mermaid diagram")
            break
    issues += _content_dir_gate_issues(page_type, markdown, repo_root)
    return issues


PAGE_FILE_NAMES = {
    "overview": "project-overview.md",
    "install": "installation.md",
    "datamodel": "data-models-overview.md",
    "api": "api-overview.md",
}


_HYGIENE_HINTS = {
    "tiny_body": "the page body is under 800 characters; explain the verified facts in full sentences",
    "missing_h1": "the page needs a '# ' title",
    "instruction_voice": "do not address the reader with instructions about the documentation itself",
    "fact_disclaimer": "do not add disclaimers about facts or evidence",
    "meta_instructions": "remove meta instructions",
    "evidence_meta_talk": "talk about the project, not about evidence",
    "repeated_fences": "do not repeat the same code block",
    "header_only_cites": "cite lines with content, not only file headers",
}


def _fmt_offenders(found: object) -> str:
    if isinstance(found, dict):
        # keys are the failing rule names; values are scratch-dir page paths or offender details
        parts = []
        for k, vs in found.items():
            vals = [v for v in (vs if isinstance(vs, list) else [vs]) if "/content/" not in str(v)]
            hint = _HYGIENE_HINTS.get(str(k), "")
            parts.append(
                f"{k}"
                + (f" ({', '.join(str(v) for v in vals[:3])})" if vals else "")
                + (f" — {hint}" if hint else "")
            )
        return "; ".join(parts)[:300]
    if isinstance(found, list):
        return "; ".join(str(x) for x in found[:4])[:300]
    return str(found)[:300]


def _content_dir_gate_issues(page_type: str, markdown: str, repo_root: Path) -> list[str]:
    """The directory-level handbook gates, run on a scratch content dir holding only this page."""
    import tempfile

    from repo_wiki.generator.compose_evidence import (
        install_path_gaps,
        invented_compose_edges,
        is_placeholder_ops_diagram,
        load_compose_from_root,
    )
    from repo_wiki.verifier import handbook as hb
    from repo_wiki.verifier.handbook_routes import (
        ROUTE_COMPLETENESS_MIN,
        handbook_route_crosscheck_mismatches,
        iter_route_source_files,
        route_completeness_ratio,
    )
    from repo_wiki.verifier.source_facts import handbook_source_fact_offenders

    issues: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        content = Path(td) / "content"
        content.mkdir()
        (content / PAGE_FILE_NAMES.get(page_type, f"{page_type}.md")).write_text(
            markdown, encoding="utf-8"
        )
        checks: list[tuple[str, Any]] = [
            (
                "QODER_HANDBOOK_READER_HYGIENE",
                lambda: hb.handbook_reader_hygiene_offenders(content, repo_root),
            ),
            (
                "QODER_HANDBOOK_UNKNOWN_PROCESS",
                lambda: hb.handbook_unknown_process_offenders(content, repo_root),
            ),
            (
                "QODER_HANDBOOK_DOC_CODE_MISMATCH",
                lambda: hb.handbook_doc_code_mismatches(content, repo_root),
            ),
            (
                "QODER_HANDBOOK_SOURCE_FACTS",
                lambda: handbook_source_fact_offenders(content, repo_root, None),
            ),
            (
                "QODER_HANDBOOK_PLACEHOLDER_MERMAID",
                lambda: (
                    hb.handbook_placeholder_mermaid_pages(content)
                    + hb.handbook_reserved_mermaid_id_pages(content)
                ),
            ),
        ]
        for code, run in checks:
            try:
                found = run()
            except Exception:  # noqa: BLE001 - a crashing helper is reported by the final gate
                continue
            if found:
                issues.append(f"existing gate {code}: {_fmt_offenders(found)}")
    try:
        _names, allowed = load_compose_from_root(repo_root)
        if invented_compose_edges(markdown, allowed) or is_placeholder_ops_diagram(markdown):
            issues.append(
                "existing gate QODER_HANDBOOK_DIAGRAM_EVIDENCE: invented compose/ops diagram"
            )
        gaps = install_path_gaps(markdown)
        if gaps:
            issues.append(f"existing gate QODER_HANDBOOK_INSTALL_PATH: {'; '.join(gaps[:3])[:300]}")
        files = [
            f for f in iter_route_source_files(repo_root) if Path(f[0]).suffix in _ROUTE_SUFFIXES
        ]
        if files:
            api = page_type == "api"
            mism = handbook_route_crosscheck_mismatches(markdown, files, api_page=api)
            if mism:
                issues.append(
                    "existing gate QODER_HANDBOOK_ROUTE_CROSSCHECK: paths missing from the independent "
                    f"source extraction: {', '.join(mism[:8])}"
                )
            if api and route_completeness_ratio(markdown, files) < ROUTE_COMPLETENESS_MIN:
                issues.append(
                    "existing gate QODER_HANDBOOK_ROUTE_CROSSCHECK: the page misses too many source routes"
                )
    except Exception:  # noqa: BLE001
        pass
    return issues


_ROUTE_SUFFIXES = {".py", ".go", ".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx"}
