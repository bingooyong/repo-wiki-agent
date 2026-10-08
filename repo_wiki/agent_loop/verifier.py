"""Deterministic verifiers: typed facts (``FILE:LINE: quote`` evidence) and HTTP routes.

Every accepted fact / route re-verifies from the repository alone. The verdict (with reasons and
the value a derivation actually computed) is fed straight back to the recording agent.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from repo_wiki.agent_loop.checklists import PageSpec
from repo_wiki.agent_loop.evidence import (
    claim_tokens,
    join_parts,
    norm,
    norm_path,
    parse_ev,
    quote_ok,
    ws,
)
from repo_wiki.agent_loop.repo import RepoView, norm_rel

Fact = dict[str, Any]
Route = dict[str, Any]

LANG_EXT: dict[str, tuple[str, ...]] = {
    "python": (".py",),
    "go": (".go",),
    "golang": (".go",),
    "javascript": (".js", ".mjs", ".cjs"),
    "typescript": (".ts",),
    "node.js": (".js", ".ts"),
    "nodejs": (".js",),
    "java": (".java",),
    "sql": (".sql",),
    "vue": (".vue",),
}
FK_RX = re.compile(
    r"(?i)REFERENCES|ForeignKey|FOREIGN KEY|\bref\s*:|relationship\(|belongsTo|hasMany|references\s*\("
)
NOT_PERSISTED_CLAIM_RX = re.compile(
    r"(?i)不对应|不是|并非|非持久|not (a |an )?(persisted|table|entity)|no (table|collection)"
    r"|does not (map|correspond)"
)
# a definition block that names its own table (DDL / migration) belongs to that table only
NAMED_TABLE_RX = re.compile(
    r"""(?i)create\s+table\s+(?:if\s+not\s+exists\s+)?[`"\[]?(?:\w+\.)?(\w+)|create_table\(\s*["'](\w+)"""
)
PATH_SLOTS = frozenset({"module", "location", "entry", "config_file"})


@dataclass
class FactCheck:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    fact: Fact | None = None


class FactVerifier:
    """Slot-aware verification of one recorded fact against the repository."""

    def __init__(self, repo: RepoView, spec: PageSpec, dm_sites: Iterable[dict[str, Any]] = ()):
        self.repo = repo
        self.spec = spec
        self.slots = {s for c in spec.checklist for s in c.slots} | {"note", "conflict"}
        if spec.page_type == "overview":
            self.slots |= {"name", "purpose"}
        self.sites: dict[str, list[int]] = defaultdict(list)
        for s in dm_sites:
            self.sites[s["file"]].append(int(s["line"]))
        for f in self.sites:
            self.sites[f].sort()

    def block_end(self, rel: str, line: int) -> int:
        nxt = [ln for ln in self.sites.get(rel, []) if ln > line]
        return nxt[0] if nxt else 10**9

    def check(self, fact: Fact, entities: dict[str, list[tuple[str, int]]]) -> FactCheck:
        repo = self.repo
        reasons: list[str] = []
        slot = str(fact.get("slot") or "").strip()
        val = str(fact.get("value") or "").strip().strip("`")
        claim = str(fact.get("claim") or "").strip()
        raw_ev = fact.get("ev") or fact.get("evidence") or []
        if isinstance(raw_ev, str):
            raw_ev = [raw_ev]
        evs = [parse_ev(e) for e in raw_ev] if isinstance(raw_ev, list) else [None]
        if not evs or any(e is None for e in evs):
            return FactCheck(False, ["evidence must be 'FILE:LINE: exact quote' strings"])
        if not claim or not val:
            return FactCheck(False, ["value and claim are required"])
        if slot not in self.slots:
            return FactCheck(
                False, [f"unknown slot {slot!r}; use one of: {', '.join(sorted(self.slots))}"]
            )
        good: list[dict[str, Any]] = []
        wins: list[str] = []
        for e in evs:
            assert e is not None
            line = quote_ok(repo, e)
            if line is None:
                reasons.append(
                    f"quote not found at {e['file']}:{e['line']} (+-2): {e['quote'][:70]!r}"
                )
                continue
            e = {**e, "line": line}
            good.append(e)
            wins.append((repo.window(e["file"], line, 2) or "") + "\n" + e["file"])
        if reasons:
            return FactCheck(False, reasons)
        win = norm("\n".join(wins))
        win_ns = re.sub(r"\s", "", win)
        files = [e["file"] for e in good]
        v = norm(val)
        ext_lang = slot == "language" and any(f.endswith(LANG_EXT.get(v, ("\x00",))) for f in files)

        def has(x: str) -> bool:
            nx = norm(x)
            if not nx:
                return False
            if nx in win or (len(nx) >= 4 and re.sub(r"\s", "", nx) in win_ns):
                return True
            # composed names (an env prefix on one line and the key on another): accept only when
            # split right after a separator and both parts are in the evidence
            return any(
                nx[i - 1] in "_-./"
                and len(nx[:i]) >= 2
                and len(nx[i:]) >= 2
                and nx[:i] in win
                and nx[i:] in win
                for i in range(2, len(nx) - 1)
            )

        if slot in PATH_SLOTS:
            target = norm_rel(val).rstrip("/") or "."
            if not repo.exists(target):
                reasons.append(f"path {val!r} does not exist")
            elif (
                slot == "module"
                and target != "."
                and not any(f.startswith(target + "/") for f in files)
            ):
                inside = [f for f in repo.files() if f.startswith(target + "/")][:6]
                reasons.append(
                    f"module role must be proven by a file inside {val!r} (cite a line from a file "
                    f"under it, e.g. one of: {', '.join(inside)})"
                )
            elif slot == "entry" and not any(
                f == target or has(target.rsplit("/", 1)[-1]) or has(target) for f in files
            ):
                reasons.append(
                    f"entry {val!r}: cite a line in that file or a line that references it"
                )
        elif slot == "command":
            ok = has(val)
            m = re.match(r"^make\s+([\w.\-]+)$", val)
            if not ok and m:
                target_rx = rf"(^|\n){re.escape(m.group(1).lower())}\s*:"
                ok = bool(re.search(target_rx, "\n".join(wins).lower()))
            m = re.match(r"^(?:yarn|npm run|npm|pnpm)\s+([\w:.\-]+)$", val)
            if not ok and m:
                ok = f'"{m.group(1).lower()}"' in win
            if not ok:
                reasons.append(
                    f"command {val!r} is not verbatim in the evidence (cite the line that contains "
                    "it, or the Makefile target / package script line)"
                )
        elif slot == "port":
            if not re.fullmatch(r"\d{2,5}", val) or val not in win:
                reasons.append(f"port {val!r} not in evidence lines")
        elif slot == "field":
            reasons += self._check_field(val, good, entities, has)
        elif slot == "relation":
            m = re.match(r"^\s*([\w.]+)\s*->\s*([\w]+)(?:\.(\w+))?\s*$", val)
            if not m:
                reasons.append("relation value must be 'entity.col -> other_entity.col'")
            else:
                col = m.group(1).split(".")[-1]
                if not has(col) or not has(m.group(2)):
                    reasons.append(
                        f"relation: {col!r} and {m.group(2)!r} must both appear in the evidence lines"
                    )
        elif slot == "no_relation":
            reasons += self._check_no_relation(val, entities)
        elif slot == "key":
            _ent, _, cols = val.partition(":")
            cl = [c.strip() for c in cols.split(",") if c.strip()]
            if not cl or not all(has(c) for c in cl):
                reasons.append(
                    "key value must be 'entity: col1, col2' with every column in the evidence"
                )
        elif slot == "entity":
            if not has(val):
                reasons.append(f"entity name {val!r} not in evidence lines")
            elif any(self.sites.values()) and not any(
                any(abs(e["line"] - ln) <= 3 for ln in self.sites.get(e["file"], [])) for e in good
            ):
                reasons.append(
                    "an entity must be cited at a persistence definition (DDL / migration "
                    "create_table / ORM-ODM model declaration); none of your evidence lines is one. "
                    f"If {val!r} is not persisted, use slot not_entity"
                )
        elif slot == "code_type":
            if not has(val):
                reasons.append(f"type name {val!r} not in evidence lines (cite its declaration)")
            elif NOT_PERSISTED_CLAIM_RX.search(claim):
                reasons.append(
                    "the claim says this type does not represent a persisted entity: record it "
                    "with slot not_entity instead"
                )
            elif entities and not any(
                re.search(rf"(?i)(?<![\w]){re.escape(en)}(?![\w])", claim) for en in entities
            ):
                reasons.append(
                    "code_type claim must name the verified persisted entity (table/collection) "
                    f"this type represents; known entities: {', '.join(sorted(entities)[:12])}. "
                    "If it represents none, use slot not_entity"
                )
        elif slot in ("purpose", "note"):
            pass
        elif slot == "conflict":
            if len({e["file"] for e in good}) < 2:
                reasons.append(
                    "a conflict fact must cite both disagreeing lines, from two different files"
                )
        elif slot == "verify":
            if not (has(val) or has(re.sub(r"^https?://[^/]+", "", val))):
                reasons.append(f"verify target {val!r} not in evidence lines")
        else:  # name, language, framework, library, prereq, env, service, store, auth, ...
            toks = [t for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.+\-]*", val) if len(t) >= 2]
            if not ext_lang and not all(has(t) for t in toks):
                miss = [t for t in toks if not has(t)]
                reasons.append(f"value tokens {miss} not in evidence lines")
        miss_claim = [
            t
            for t in claim_tokens(claim)
            if not has(t) and norm(t) not in v and not any(norm(t) in norm(f) for f in files)
        ]
        if miss_claim:
            reasons.append(f"claim tokens not grounded in the evidence lines: {miss_claim[:6]}")
        if reasons:
            return FactCheck(False, reasons)
        return FactCheck(
            True,
            [],
            {
                "item": str(fact.get("item") or "").strip(),
                "slot": slot,
                "value": val,
                "claim": claim,
                "evidence": [f"{e['file']}:{e['line']}" for e in good],
                "quotes": [e["quote"] for e in good],
            },
        )

    def _check_field(
        self,
        val: str,
        good: list[dict[str, Any]],
        entities: dict[str, list[tuple[str, int]]],
        has: Any,
    ) -> list[str]:
        ent, _, fld = val.partition(".")
        if not fld or not has(fld):
            return [f"field name {fld!r} not in evidence; value must be 'entity.field'"]
        eevs = entities.get(ent.lower())
        if eevs is None:
            return [f"entity {ent!r} is not (yet) a verified entity; record the entity first"]
        inside = any(
            e["file"] == ef and el - 3 <= e["line"] < self.block_end(ef, el)
            for e in good
            for ef, el in eevs
        )
        if inside:
            return []
        # schema declared in one block and registered elsewhere in the same file: accept a field
        # inside any definition block of that file when the file holds exactly one verified entity
        efiles = {ef for ef, _ in eevs}
        solo = all(
            sum(1 for v2 in entities.values() for ff, _ in v2 if ff == ef) == 1 for ef in efiles
        )

        def other_table(rel: str, site_line: int) -> bool:
            ls = self.repo.lines(rel) or []
            text = ls[site_line - 1] if 0 < site_line <= len(ls) else ""
            m = NAMED_TABLE_RX.search(text)
            name = (m.group(1) or m.group(2)) if m else None
            return bool(name) and str(name).lower() != ent.lower()

        in_blk = any(
            e["file"] in efiles
            and any(
                sl - 3 <= e["line"] < self.block_end(e["file"], sl)
                and not other_table(e["file"], sl)
                for sl in self.sites.get(e["file"], [])
            )
            for e in good
        )
        if solo and in_blk:
            return []
        return [f"field evidence is not inside the definition block of {ent!r}"]

    def _check_no_relation(self, val: str, entities: dict[str, list[tuple[str, int]]]) -> list[str]:
        eevs = entities.get(val.lower())
        if not eevs:
            return [f"no_relation: {val!r} is not a verified entity"]
        for ef, el in eevs:
            ls = self.repo.lines(ef) or []
            end = min(len(ls), self.block_end(ef, el) - 1, el + 80)
            hit = next((i for i in range(el, end + 1) if FK_RX.search(ls[i - 1])), None)
            if hit:
                return [
                    f"no_relation refuted: {ef}:{hit} has a reference marker: "
                    f"{ls[hit - 1].strip()[:80]!r}"
                ]
        return []


# ------------------------------------------------------------------ routes
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD", "ANY")
DERIVE_OP_RX = re.compile(
    r"^(lower|upper|snake|kebab|ends_with_method|starts_with_method|strip_prefix:.*|"
    r"strip_suffix:.*|add_prefix:.*|add_suffix:.*)$"
)
_ROUTE_EV_RX = re.compile(r"^\s*(?P<file>[^\s]+?):(?P<line>\d+)\s*(?:<=\s*(?P<rest>.*))?$")
UNATTRIBUTED = "未归属（未能从源码确认所属服务）"


def apply_ops(text: str, ops: Iterable[str]) -> str | None:
    """Closed set of derive ops; any other op (or a non-matching strip) fails the derivation."""
    t = text
    for op in ops or []:
        name, _, arg = str(op).partition(":")
        if name == "lower":
            t = t.lower()
        elif name == "upper":
            t = t.upper()
        elif name == "snake":
            t = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", t).lower()
        elif name == "kebab":
            t = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", t).lower().replace("_", "-")
        elif name == "strip_prefix":
            if not t.startswith(arg):
                return None
            t = t[len(arg) :]
        elif name == "strip_suffix":
            if not t.endswith(arg):
                return None
            t = t[: len(t) - len(arg)]
        elif name == "add_prefix":
            t = arg + t
        elif name == "add_suffix":
            t = t + arg
        elif name in ("ends_with_method", "starts_with_method"):
            continue
        else:
            return None
    return t


def parse_route_ev(raw: object) -> dict[str, Any] | None:
    """``'FILE:LINE'`` or ``'FILE:LINE <= SOURCE_TEXT | op1,op2'``."""
    s = str(raw or "").strip().strip("`")
    m = _ROUTE_EV_RX.match(s)
    if not m:
        return None
    d: dict[str, Any] = {"file": norm_rel(m.group("file")), "line": int(m.group("line"))}
    rest = m.group("rest")
    if rest:
        src, ops = rest, []
        if "|" in rest:
            a, _, b = rest.rpartition("|")
            cand = [x.strip() for x in b.split(",") if x.strip()]
            if cand and all(DERIVE_OP_RX.match(c) for c in cand):
                src, ops = a, cand
        d["source_text"] = src.strip().strip("`'\"")
        d["derive"] = ops
    return d


def from_compact(r: object) -> dict[str, Any] | None:
    """Compact record (``parts: ['VALUE @ FILE:LINE ...']``) -> verifier dict."""
    if not isinstance(r, dict):
        return None
    if "path_parts" in r:
        return r
    me = parse_route_ev(r.get("method_ev")) or {}
    parts = []
    for p in r.get("parts") or []:
        p = str(p)
        if " @ " not in p:
            parts.append({"value": p, "file": "", "line": -1})
            continue
        val, _, ev = p.partition(" @ ")
        e = parse_route_ev(ev) or {"file": "", "line": -1}
        parts.append({"value": val.strip().strip("`'\""), **e})
    return {
        "method": r.get("method"),
        "full_path": r.get("path"),
        "method_evidence": me,
        "path_parts": parts,
        "handler": r.get("handler"),
    }


def _in_window(repo: RepoView, rel: object, line: object, text: str, radius: int) -> bool:
    w = repo.window(str(rel or ""), line, radius)
    return w is not None and ws(text) in ws(w)


def _check_method(
    repo: RepoView, method: str, me: dict[str, Any]
) -> tuple[list[str], str | None, bool]:
    reasons: list[str] = []
    any_basis: str | None = None
    derived = False
    w = repo.window(str(me.get("file", "")), me.get("line"), 2)
    st, ops = str(me.get("source_text") or ""), list(me.get("derive") or [])
    name_derived = any(o in ops for o in ("ends_with_method", "starts_with_method"))
    if w is None:
        return ["method evidence line missing"], None, False
    if method == "ANY":
        if st and name_derived:
            any_basis = "derivation"
            d = (
                apply_ops(st, ops)
                if _in_window(repo, me.get("file"), me.get("line"), st, 2)
                else None
            )
            if d is None:
                reasons.append(
                    f"ANY: derivation source {st!r} not at {me.get('file')}:{me.get('line')} or ops invalid"
                )
            else:
                du = d.upper()
                hit = [
                    mm
                    for mm in ("GET", "POST", "PUT", "DELETE", "PATCH")
                    if (du.endswith(mm) if "ends_with_method" in ops else du.startswith(mm))
                ]
                if hit:
                    reasons.append(
                        f"ANY contradicts derivation: ops give {du!r}, which matches {hit[0]}; "
                        f"method should be {hit[0]}"
                    )
        elif re.search(r"\bAny\b|\bANY\b|\.all\s*\(", w):
            any_basis = "any_token"
        elif re.search(
            r"\.use\s*\(|HandleFunc\s*\(|\.Handle\s*\(|\.route\s*\(|\bmatch\b|Methods?\s*[=:(]", w
        ):
            any_basis = "accept_all_heuristic"
        else:
            reasons.append(
                "ANY needs either a derivation (token | ops,ends_with_method) or an accept-all "
                f"registration at {me.get('file')}:{me.get('line')}"
            )
        return reasons, any_basis, derived
    title, low = method.title(), method.lower()
    literal = re.search(rf"(?<![A-Za-z]){method}(?![A-Za-z])", w) or re.search(
        rf"[.@]{low}\s*\(|[.@]{title}\s*\(|Method{title}\b|def {low}\s*\(|async def {low}\s*\("
        rf"|@{title}Mapping|\b{title}\s*\(",
        w,
    )
    if literal:
        return reasons, None, False
    d = apply_ops(st, ops) if st else None
    near = bool(st) and _in_window(repo, me.get("file"), me.get("line"), st, 2)
    if st and d is not None and near:
        du = d.upper()
        if "ends_with_method" in ops:
            derived = du.endswith(method)
        elif "starts_with_method" in ops:
            derived = du.startswith(method)
        else:
            derived = du == method
    if derived:
        return reasons, None, True
    if st:
        where = "" if near else f"; {st!r} is not within 2 lines of the cited line"
        reasons.append(
            f"method {method}: derive({st!r}, {ops}) = {d!r}{where}; it must end/start with "
            f"{method} (add e.g. strip_suffix ops) or the method is wrong"
        )
    else:
        reasons.append(
            f"method {method} not literally at {me.get('file')}:{me.get('line')} and no derivation given"
        )
    return reasons, None, False


def verify_routes(repo: RepoView, raw_routes: Iterable[object]) -> tuple[list[Route], list[Route]]:
    """Verify recorded routes; de-duplicate by (method, normalised path)."""
    ok: list[Route] = []
    bad: list[Route] = []
    seen: set[tuple[str, str]] = set()
    for r in map(from_compact, raw_routes):
        if not isinstance(r, dict):
            continue
        reasons: list[str] = []
        method = str(r.get("method") or "").upper().strip()
        if method not in HTTP_METHODS:
            reasons.append(f"bad method {method}")
        me = r.get("method_evidence") if isinstance(r.get("method_evidence"), dict) else {}
        assert isinstance(me, dict)
        m_reasons, any_basis, derived_method = _check_method(repo, method, me)
        if method in HTTP_METHODS:
            reasons += m_reasons
        parts = [p for p in (r.get("path_parts") or []) if isinstance(p, dict)]
        if not parts:
            reasons.append("no path parts")
        derived_parts = 0
        for part in parts:
            val = str(part.get("value", ""))
            pw = repo.window(str(part.get("file", "")), part.get("line"), 3)
            if pw is None:
                reasons.append(f"part {val!r}: line missing")
                continue
            if not val.strip() or val in pw or val.strip("/") in pw:
                continue
            st, ops = str(part.get("source_text") or ""), list(part.get("derive") or [])
            d = apply_ops(st, ops) if st else None
            if st and d is not None and ws(st) in ws(pw) and d.strip("/") == val.strip("/"):
                derived_parts += 1
                continue
            detail = ""
            if st:
                detail = f"; derive({st!r}, {ops}) = {d!r}" + (
                    "" if ws(st) in ws(pw) else " and source_text not found there"
                )
            reasons.append(
                f"part {val!r} not literally within 3 lines of {part.get('file')}:{part.get('line')}"
                + detail
            )
        full = join_parts([str(p.get("value", "")) for p in parts])
        if parts and norm_path(str(r.get("full_path", ""))) != full:
            reasons.append(f"full_path {r.get('full_path')!r} != joined parts {full!r}")
        handler = str(r.get("handler") or "").strip()
        if handler:
            idents = re.findall(r"[A-Za-z_]\w*", handler)
            files = {str(me.get("file", ""))} | {str(p.get("file", "")) for p in parts}
            text = "\n".join("\n".join(repo.lines(f) or []) for f in files if f)
            if not idents or not re.search(rf"\b{re.escape(idents[-1])}\b", text):
                handler = ""  # an unverifiable handler name is dropped, not trusted
        ev = [f"{me.get('file')}:{me.get('line')}"] + [
            f"{p.get('file')}:{p.get('line')}" for p in parts
        ]
        rec: Route = {
            "method": method,
            "path": full,
            "claimed": r.get("full_path"),
            "handler": handler or None,
            "evidence": ev,
            "derived": derived_parts + (1 if derived_method else 0),
            "any_basis": any_basis,
            "reg_file": (parts[-1].get("file") if parts else me.get("file")),
            "parts": [str(p.get("value", "")).strip("/") for p in parts],
        }
        if reasons:
            rec["reasons"] = reasons
            bad.append(rec)
        elif (method, full) not in seen:
            seen.add((method, full))
            ok.append(rec)
    return ok, bad


def resolve_conflicts(routes: list[Route], bad: list[Route]) -> tuple[list[Route], list[Route]]:
    """Per server: an ANY inferred from absence/heuristic loses to a positively proven method."""
    specific = {(r.get("server"), r["path"]) for r in routes if r["method"] != "ANY"}
    keep: list[Route] = []
    for r in routes:
        if (
            r["method"] == "ANY"
            and r.get("any_basis") in ("accept_all_heuristic", "derivation")
            and (r.get("server"), r["path"]) in specific
        ):
            bad.append(
                {
                    **r,
                    "reasons": [
                        "conflict: ANY inferred from absence/heuristic while a specific method is "
                        "proven for the same path on the same server"
                    ],
                }
            )
        else:
            keep.append(r)
    return keep, bad
