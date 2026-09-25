#!/usr/bin/env python3
"""Handbook acceptance checks (standalone, python3 stdlib only).

usage: acceptance.py <handbook_dir> <source_dir> --repo go|fastapi [--render] [--golist] [--build] [--out FILE]

<handbook_dir> may be a run dir (containing repowiki/zh/content), repowiki/zh, or the content dir.
<source_dir> is a checkout of the documented repository at the generated revision.
Optional flags run external tools: --render (npx @mermaid-js/mermaid-cli + chrome), --golist (go list),
--build (compile every `go build` command found in the handbook into a temp dir).
Everything not automated is listed under "todo_manual" instead of being reported as passing.
"""
import argparse, collections, hashlib, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HTTP_METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "ANY")
CITE_RE = re.compile(r"<cite>\s*([^<:\s][^<:]*?):(\d+)(?:-(\d+))?\s*</cite>")
FENCE_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.S)
PAGE_ID_SUFFIX_RE = re.compile(r"[ \t]*\[[a-z0-9]+(?:-[a-z0-9]+)+\]|[ \t]+\[[a-z0-9]+\][ \t]*$", re.M)
ROUTE_IN_TEXT_RE = re.compile(r"\b(GET|POST|PUT|DELETE|PATCH|ANY|HEAD|OPTIONS)\s+`?(/[^\s（(，,`<|]*)")


# ----------------------------------------------------------------------------- loading
def resolve_content(h: Path) -> tuple[Path, Path | None]:
    for cand in (h / "repowiki/zh/content", h / "content", h):
        if cand.is_dir() and any(cand.rglob("*.md")):
            meta = None
            for m in (cand.parent / "meta", h / "repowiki/zh/meta", h / "meta"):
                if m.is_dir():
                    meta = m
                    break
            return cand, meta
    sys.exit(f"no markdown content under {h}")


def load_pages(content: Path) -> dict[str, str]:
    return {str(p.relative_to(content)): p.read_text(encoding="utf-8", errors="ignore") for p in sorted(content.rglob("*.md"))}


def strip_fences(t: str) -> str:
    return re.sub(r"```.*?```", "", t, flags=re.S)


def src_lines(src: Path, rel: str) -> list[str] | None:
    p = src / rel
    if not p.is_file():
        return None
    return p.read_text(encoding="utf-8", errors="ignore").splitlines()


# ----------------------------------------------------------------------------- text damage
GAP_RE = re.compile(r"[\u4e00-\u9fff，、（]\s{2,}[\u4e00-\u9fff（，。、]|[为用非是名在] [，。）]|选择 （")


def check_text_gaps(pages):
    hits, per_page, ex = 0, collections.Counter(), []
    for rel, t in pages.items():
        for line in strip_fences(t).splitlines():
            for m in GAP_RE.finditer(line):
                hits += 1
                per_page[rel] += 1
                if len(ex) < 15:
                    ex.append({"page": rel, "context": line[max(0, m.start() - 30): m.end() + 20]})
    return {"hits": hits, "pages": len(per_page), "examples": ex,
            "note": "dangling gaps: double spaces between CJK or a particle before punctuation, left by removed backtick tokens"}


# ----------------------------------------------------------------------------- mermaid
def extract_mermaid(pages):
    blocks = []
    for rel, t in pages.items():
        for m in FENCE_RE.finditer(t):
            blocks.append({"page": rel, "raw": m.group(1)})
    return blocks


def normalize_block(raw: str) -> str:
    lines = []
    for line in raw.splitlines():
        if re.match(r"\s*Note\s+(over|left of|right of)\b", line):
            continue
        line = re.sub(r"<cite>[^<]*</cite>", "", line)
        line = PAGE_ID_SUFFIX_RE.sub("", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def h8(s):
    return hashlib.md5(s.encode()).hexdigest()[:8]


def check_mermaid(pages, blocks, render=False):
    total_pages = len(pages)
    raw_groups, norm_groups = collections.defaultdict(set), collections.defaultdict(set)
    kinds = collections.Counter()
    cite_in = []
    empty_msgs, edgeless, empty_entities = [], [], []
    for b in blocks:
        raw, norm = b["raw"].strip(), normalize_block(b["raw"])
        b["raw_hash"], b["norm_hash"] = h8(raw), h8(norm)
        b["kind"] = (norm.splitlines() or [""])[0].split(" ")[0]
        raw_groups[b["raw_hash"]].add(b["page"])
        norm_groups[b["norm_hash"]].add(b["page"])
        kinds[b["kind"]] += 1
        n = raw.count("<cite>")
        if n:
            cite_in.append({"page": b["page"], "hash": b["raw_hash"], "cite_tags": n})
        for line in raw.splitlines():
            if re.search(r"->>?[^:]*:\s*(\((list|detail) flow\))?\s*$", line):
                empty_msgs.append({"page": b["page"], "line": line.strip()})
        if b["kind"] in ("flowchart", "graph") and not re.search(r"--+>|==+>|-\.->", raw):
            edgeless.append({"page": b["page"], "hash": b["raw_hash"]})
        if b["kind"] == "erDiagram":
            for m in re.finditer(r"^\s*(\w+)\s*\{\s*\}", raw, re.M):
                empty_entities.append({"page": b["page"], "entity": m.group(1)})
    copies = [{"hash": k, "pages": sorted(v)} for k, v in norm_groups.items() if len(v) > 1]
    # also count identical blocks on the SAME page listed twice
    per_page_dupe = collections.Counter((b["page"], b["norm_hash"]) for b in blocks)
    same_page_dupes = [{"page": p, "hash": hsh, "count": c} for (p, hsh), c in per_page_dupe.items() if c > 1]
    # near duplicates: distinct normalized blocks sharing >=80% of body lines (same kind)
    uniq = {}
    for b in blocks:
        uniq.setdefault(b["norm_hash"], b)
    near = []
    items = list(uniq.values())
    for i in range(len(items)):
        a = set(items[i]["raw"] and normalize_block(items[i]["raw"]).splitlines()[1:])
        for j in range(i + 1, len(items)):
            if items[i]["kind"] != items[j]["kind"]:
                continue
            c = set(normalize_block(items[j]["raw"]).splitlines()[1:])
            if not a or not c:
                continue
            jac = len(a & c) / len(a | c)
            if jac >= 0.8:
                near.append({"a": items[i]["norm_hash"], "a_pages": sorted(norm_groups[items[i]["norm_hash"]]),
                             "b": items[j]["norm_hash"], "b_pages": sorted(norm_groups[items[j]["norm_hash"]]),
                             "jaccard": round(jac, 2)})
    # suffix-only distinct: raw distinct that collapse after normalization
    collapsed = len(raw_groups) - len(norm_groups)
    near_clusters = _clusters(len(norm_groups), near)
    res = {
        "blocks": len(blocks), "pages_with_mermaid": len({b["page"] for b in blocks}), "total_pages": total_pages,
        "distinct_raw": len(raw_groups), "distinct_normalized": len(norm_groups),
        "distinct_after_near_dup_merge": near_clusters,
        "coverage_raw_pct": round(100 * len(raw_groups) / total_pages, 1) if total_pages else 0,
        "coverage_honest_pct": round(100 * len(norm_groups) / total_pages, 1) if total_pages else 0,
        "coverage_strict_pct": round(100 * near_clusters / total_pages, 1) if total_pages else 0,
        "collapsed_by_normalization": collapsed, "kinds": dict(kinds),
        "copies_across_pages": copies, "same_page_duplicates": same_page_dupes, "near_duplicates": near,
        "raw_cite_in_mermaid": {"blocks": len(cite_in), "tags": sum(x["cite_tags"] for x in cite_in), "items": cite_in[:20]},
        "empty_messages": empty_msgs[:20], "empty_message_count": len(empty_msgs),
        "edgeless_flowcharts": edgeless, "empty_er_entities": empty_entities,
        "normalization": "strip <cite>, trailing [page-id] tags, Note lines, whitespace",
    }
    if render:
        res["render"] = render_mermaid(blocks)
    return res


def _clusters(n_nodes, near):
    parent = {}

    def f(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for e in near:
        parent[f(e["a"])] = f(e["b"])
    merged = len({f(x) for e in near for x in (e["a"], e["b"])})
    involved = len({x for e in near for x in (e["a"], e["b"])})
    return n_nodes - involved + merged


def render_mermaid(blocks):
    npx = shutil.which("npx")
    chrome = os.environ.get("ACCEPT_CHROME") or shutil.which("google-chrome") or shutil.which("chromium")
    if not npx or not chrome:
        return {"status": "skipped", "reason": "npx or chrome not found"}
    tmp = Path(tempfile.mkdtemp(prefix="accept-mmd-"))
    (tmp / "pp.json").write_text(json.dumps({"executablePath": chrome, "args": ["--no-sandbox"]}))
    seen, fails = {}, []
    for b in blocks:
        seen.setdefault(b["raw_hash"], b)
    for hsh, b in seen.items():
        (tmp / f"{hsh}.mmd").write_text(b["raw"])
        r = subprocess.run([npx, "-y", "@mermaid-js/mermaid-cli@11", "-p", str(tmp / "pp.json"), "-i", str(tmp / f"{hsh}.mmd"),
                            "-o", str(tmp / f"{hsh}.svg")], capture_output=True, text=True, timeout=180,
                           env={**os.environ, "PUPPETEER_SKIP_DOWNLOAD": "1"})
        if r.returncode:
            fails.append({"hash": hsh, "page": b["page"], "err": r.stderr[-300:]})
    return {"status": "ran", "distinct_rendered": len(seen), "failures": fails, "svg_dir": str(tmp)}


# ----------------------------------------------------------------------------- route tables
SKIP_DIRS = ("/.git/", "/vendor/", "/node_modules/", "/.repo-agent-eval/", "/api/proto/")


def go_files(src):
    for p in src.rglob("*.go"):
        s = "/" + str(p.relative_to(src)) + "/"
        if p.name.endswith("_test.go") or any(d in s for d in SKIP_DIRS) or p.name.endswith(".pb.go"):
            continue
        yield p


def go_func_body(lines, start_idx):
    depth, out = 0, []
    for i in range(start_idx, min(len(lines), start_idx + 400)):
        out.append(lines[i])
        depth += lines[i].count("{") - lines[i].count("}")
        if depth <= 0 and i > start_idx:
            break
    return "\n".join(out)


def go_auth_from_body(body, rel):
    hdr = set()
    if "checkControlAuth" in body:
        hdr.add("X-Agent-Token")
    for m in re.finditer(r'Header\.Get\("([^"]+)"\)', body):
        hdr.add(m.group(1))
    return sorted(hdr)


def build_go_routes(src, meta):
    routes = []
    all_src = {str(p.relative_to(src)): p.read_text(encoding="utf-8", errors="ignore").splitlines() for p in go_files(src)}
    func_index = {}
    for rel, L in all_src.items():
        for i, l in enumerate(L):
            m = re.match(r"func\s+(?:\([^)]*\)\s*)?(\w+)\s*\(", l)
            if m:
                func_index.setdefault(m.group(1), []).append((rel, i))
    # ccagent middleware: header and exempt list parsed from apiauth.go
    api_hdr, exempt, exempt_prefix = None, set(), []
    if "apiauth.go" in all_src:
        txt = "\n".join(all_src["apiauth.go"])
        m = re.search(r'APITokenHeader\s*=\s*"([^"]+)"', txt)
        api_hdr = m.group(1) if m else None
        m = re.search(r"func apiAuthExempt\(.*?\n}\n", txt, re.S)
        if m:
            body = m.group(0)
            for c in re.findall(r'case\s+([^:]+):', body):
                exempt.update(re.findall(r'"([^"]+)"', c))
            exempt_prefix = re.findall(r'HasPrefix\(path,\s*"([^"]+)"\)', body)

    def ccagent_auth(path):
        if not api_hdr:
            return []
        if path in exempt or any(path.startswith(p) for p in exempt_prefix):
            return []
        return [api_hdr, "Bearer"]

    def enclosing_func(L, i):
        for j in range(i, -1, -1):
            m = re.match(r"func\s+(?:\([^)]*\)\s*)?(\w+)\s*\(", L[j])
            if m:
                return m.group(1)
        return ""
    for rel, L in all_src.items():
        is_ccagent = "/" not in rel or rel.startswith("internal/services/")
        for i, l in enumerate(L):
            m = re.search(r'\b(\w+)\.HandleFunc\(\s*"([^"]*)"\s*,\s*([\w.]+)?', l)
            if m:
                path = m.group(2)
                body = go_func_body(L, i)
                named = m.group(3)
                if named and named != "func":
                    fn = named.split(".")[-1]
                    for frel, fi in func_index.get(fn, []):
                        body += "\n" + go_func_body(all_src[frel], fi)
                window = body.split("HandleFunc(", 2)
                own = "HandleFunc(".join(window[:2]) if len(window) > 2 else body
                mm = re.search(r"Method\s*!=\s*http\.Method(\w+)", own)
                method = mm.group(1).upper() if mm else "ANY"
                auth = go_auth_from_body(own, rel)
                routes.append({"method": method, "path": path, "file": rel, "line": i + 1, "handler": named if named and named != "func" else enclosing_func(L, i),
                               "component": enclosing_func(L, i), "auth": auth, "auth_optional": "apiKey != \"\"" in own or "if s.apiKey" in own,
                               "source": "source:net/http"})
            m = re.search(r'\b(\w+)\.(GET|POST|PUT|DELETE|PATCH|Any)\(\s*"([^"]*)"', l)
            if m and "gin" in "\n".join(L[:40]):
                method = "ANY" if m.group(2) == "Any" else m.group(2)
                path = m.group(3)
                routes.append({"method": method, "path": path, "file": rel, "line": i + 1, "handler": enclosing_func(L, i),
                               "component": enclosing_func(L, i), "auth": ccagent_auth(path) if is_ccagent else [],
                               "source": "source:gin"})
    # reflection-registered services: only the generator inventory knows the expansion today
    inv_used = 0
    if meta and (meta / "source-inventory.json").is_file():
        inv = json.load(open(meta / "source-inventory.json")).get("api_surfaces", [])
        have = {(r["path"], r["file"]) for r in routes}
        for s in inv:
            f, path = s.get("evidence_path"), s.get("path") or s.get("route")
            if not f or not path or (path, f) in have:
                continue
            inv_used += 1
            is_cc = "/" not in f or f.startswith("internal/services/")
            routes.append({"method": (s.get("method") or "ANY").upper(), "path": path, "file": f, "line": s.get("line"),
                           "handler": s.get("handler") or "", "component": s.get("handler") or "",
                           "auth": ccagent_auth(path) if is_cc else [], "source": "generator_inventory:" + str(s.get("kind"))})
    return routes, {"api_token_header": api_hdr, "exempt": sorted(exempt), "exempt_prefix": exempt_prefix,
                    "routes_from_generator_inventory": inv_used}


def build_fastapi_routes(src):
    routes = []
    api_prefix = ""
    for f in src.glob("app/core/settings/*.py"):
        m = re.search(r'\bapi_prefix:\s*str\s*=\s*"([^"]*)"', f.read_text())
        if m:
            api_prefix = m.group(1)
    # module -> prefix from include_router calls (one level of nesting)
    prefixes = {}

    def scan_api(api_file, base):
        txt = api_file.read_text()
        imports = {}
        for m in re.finditer(r"from\s+([\w.]+)\s+import\s+([^\n]+)", txt):
            for part in m.group(2).split(","):
                part = part.strip()
                if " as " in part:
                    name, alias = [x.strip() for x in part.split(" as ")]
                else:
                    name = alias = part
                imports[alias] = m.group(1) + "." + name
        for m in re.finditer(r"include_router\(\s*(\w+)\.router(.*?)\)\s*\n", txt, re.S):
            mod = imports.get(m.group(1))
            pm = re.search(r'prefix\s*=\s*"([^"]*)"', m.group(2))
            pre = base + (pm.group(1) if pm else "")
            if not mod:
                continue
            p = src / (mod.replace(".", "/") + ".py")
            if p.name == "api.py" or (src / mod.replace(".", "/")).is_dir():
                sub = src / (mod.replace(".", "/") + ".py")
                if sub.is_file() and "include_router" in sub.read_text():
                    scan_api(sub, pre)
                    continue
            prefixes[str(p.relative_to(src))] = pre
    # dependency functions that transitively require / optionally use the authorizer
    dep_req, dep_opt = set(), set()
    for f in sorted((src / "app").rglob("*.py")) if (src / "app").is_dir() else []:
        t = f.read_text(errors="replace")
        for m in re.finditer(r"^(?:async\s+)?def\s+(\w+)\((.*?)\)\s*(?:->[^:]*)?:", t, re.S | re.M):
            body = m.group(2)
            if re.search(r"get_current_user_authorizer\(\s*required\s*=\s*False\s*\)", body):
                dep_opt.add(m.group(1))
            elif "get_current_user_authorizer(" in body:
                dep_req.add(m.group(1))
    root_api = src / "app/api/routes/api.py"
    if root_api.is_file():
        scan_api(root_api, api_prefix)
    for rel, pre in prefixes.items():
        L = src_lines(src, rel) or []
        i = 0
        while i < len(L):
            m = re.match(r"\s*@router\.(get|post|put|delete|patch)\(", L[i])
            if not m:
                i += 1
                continue
            dec = i
            j = i
            while j < len(L) and not re.match(r"\s*(async\s+)?def\s+\w+", L[j]):
                j += 1
            chunk = "\n".join(L[dec:j])
            after = chunk.split("(", 1)[1].lstrip()
            pm = re.match(r'"([^"]*)"', after)
            sub = pm.group(1) if pm else ""
            dm = re.match(r"\s*(?:async\s+)?def\s+(\w+)", L[j]) if j < len(L) else None
            k = j
            sig = []
            while k < len(L):
                sig.append(L[k])
                if re.search(r"\)\s*(->[^:]*)?:\s*$", L[k]):
                    break
                k += 1
            sigt = "\n".join(sig)
            deps = set(re.findall(r"Depends\(\s*(?:\w+\.)*(\w+)", chunk + "\n" + sigt))
            if "get_current_user_authorizer(" in sigt and not re.search(r"get_current_user_authorizer\(\s*required\s*=\s*False\s*\)", sigt):
                auth, opt = ["Authorization"], False
            elif deps & dep_req:
                auth, opt = ["Authorization"], False
            elif re.search(r"get_current_user_authorizer\(\s*required\s*=\s*False\s*\)", sigt) or deps & dep_opt:
                auth, opt = ["Authorization"], True
            else:
                auth, opt = [], False
            routes.append({"method": m.group(1).upper(), "path": (pre + sub) or "/", "file": rel, "line": dec + 1,
                           "def_line": j + 1, "handler": dm.group(1) if dm else "", "component": dm.group(1) if dm else "",
                           "auth": auth, "auth_optional": opt, "source": "source:fastapi"})
            i = j + 1
    return routes, {"api_prefix": api_prefix, "router_files": prefixes}


def route_index(routes):
    idx = collections.defaultdict(list)
    for r in routes:
        idx[r["path"]].append(r)
    return idx


def norm_path(p):
    return p.rstrip("/。.，,") or "/"


def cite_matches_route(repo, r, f, a, b):
    if f != r["file"] or not r.get("line"):
        return False, False
    line = int(r["line"])
    if repo == "fastapi":
        lo, hi = line, int(r.get("def_line") or line)
        return lo <= a <= hi, a <= hi and b >= lo
    return a == line, a <= line <= b


# ----------------------------------------------------------------------------- sequence diagrams
AUTH_TOKENS = ("X-Probe-Api-Token", "X-Agent-Token", "X-API-Key", "Authorization", "Token", "Bearer")
GENERIC_NODES = {"Client", "Route", "Handler", "APIAuth", "AuthenticationDep", "Browser", "User", "Frontend", "Server", "server"}


def parse_seq(raw):
    msgs = []
    for line in raw.splitlines():
        m = re.match(r"\s*([\w.-]+)\s*-[->x)]+\+?-?\s*([\w.-]+)\s*:\s*(.*)$", line)
        if m:
            msgs.append((m.group(1), m.group(2), m.group(3).strip()))
    parts = re.findall(r"^\s*participant\s+(\S+)", raw, re.M)
    return msgs, parts


def node_matches(node, r, repo):
    n = node.replace("_", ".").lower()
    cands = {str(r.get("handler") or "").lower(), str(r.get("component") or "").lower()}
    cands |= {c.split(".")[-1] for c in list(cands) if c}
    f = r["file"].lower()
    if repo == "go":
        tokens = {Path(f).stem, Path(f).parent.name, Path(f).parent.as_posix().replace("/", ".")}
        if f.startswith("internal/services/") or "/" not in f:
            tokens |= {"controller", "r.get", "r.post", "ccagent", "internal.services", "controller.go"}
        if "custom-probe" in f:
            tokens |= {"custom.probe", "server", "probehandler", "healthhandler"}
        if "ccprobe-control" in f:
            tokens |= {"ccprobe.control", "rungrpcserve"}
        if f.startswith("internal/agent"):
            tokens |= {"internal.agent", "newhttphandler"}
        cands |= {t.lower() for t in tokens}
    variants = {n, node.lower()}
    return any(c and any(v == c or v.endswith("." + c) or c.endswith("." + v) for v in variants) for c in cands)


def check_sequences(blocks, routes, repo, src_ident):
    idx = route_index(routes)
    src_ident_norm = {re.sub(r"[-_.]", "", x).lower() for x in src_ident}
    src_ident_lower = {t.lower() for x in src_ident for t in re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+", x)}
    out = {"route_messages": 0, "unknown_routes": [], "method_mismatch": [], "auth_wrong": [], "auth_omitted": 0,
           "node_mismatch": [], "diagram_cite_checked": 0, "diagram_cite_wrong": [], "unknown_participants": []}
    for b in blocks:
        if b.get("kind") != "sequenceDiagram":
            continue
        msgs, parts = parse_seq(b["raw"])
        for p in set(parts) | {x for m in msgs for x in m[:2]}:
            pl = p.replace("_", ".")
            if p in GENERIC_NODES:
                continue
            norm = re.sub(r"[-_.]", "", p).lower()
            camel = [t.lower() for t in re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+", p) if len(t) > 2]
            known = norm in src_ident_norm or p in src_ident or pl in src_ident or (camel and all(t in src_ident_lower for t in camel))
            if not known:
                out["unknown_participants"].append({"page": b["page"], "participant": p})
        for k, (a, c, text) in enumerate(msgs):
            m = ROUTE_IN_TEXT_RE.search(text)
            if not m:
                continue
            out["route_messages"] += 1
            meth, path = m.group(1), norm_path(m.group(2))
            cands = idx.get(path, [])
            item = {"page": b["page"], "hash": b["raw_hash"], "msg": text[:140]}
            if not cands:
                out["unknown_routes"].append(item)
                continue
            mc = [r for r in cands if r["method"] in (meth, "ANY")]
            if not mc:
                out["method_mismatch"].append({**item, "claimed": meth, "source": sorted({r["method"] for r in cands})})
            # claimed auth hop: previous message from Client to the sender carries a header token
            claimed = None
            if k > 0:
                pa, pc, ptext = msgs[k - 1]
                if pc == a and any(tok.lower() in ptext.lower() for tok in AUTH_TOKENS):
                    claimed = re.sub(r"\s*\[[\w\-]+\]\s*$", "", ptext.strip())
            # handler node: receiver of this message, or receiver of following "dispatch"
            node = c
            if c == "Route" and k + 1 < len(msgs) and msgs[k + 1][0] == "Route":
                node = msgs[k + 1][1]
            # cite in message
            cm = CITE_RE.search(text)
            cited = None
            if cm:
                out["diagram_cite_checked"] += 1
                f, x, y = cm.group(1), int(cm.group(2)), int(cm.group(3) or cm.group(2))
                cited = [r for r in (mc or cands) if cite_matches_route(repo, r, f, x, y)[0]]
                if not cited:
                    exp = [f'{r["file"]}:{r["line"]}' + (f'-{r["def_line"]}' if r.get("def_line") else "") for r in (mc or cands)]
                    out["diagram_cite_wrong"].append({**item, "cited": f"{f}:{x}", "expected_one_of": exp})
            pool = cited or mc or cands
            if node not in GENERIC_NODES and not any(node_matches(node, r, repo) for r in pool):
                out["node_mismatch"].append({**item, "node": node, "owners": sorted({r["file"] for r in pool})})
            exp_auth = [r for r in pool]
            if claimed:
                ok = False
                for r in exp_auth:
                    if not r["auth"]:
                        continue
                    if any(h.lower() in claimed.lower() for h in r["auth"]) or (repo == "fastapi" and "authorization" in claimed.lower()):
                        ok = True
                if not ok:
                    out["auth_wrong"].append({**item, "claimed_header": claimed,
                                              "source_auth": [{"file": r["file"], "auth": r["auth"] or "none"} for r in exp_auth]})
            elif any(r["auth"] and not r.get("auth_optional") for r in exp_auth) and c == "Route":
                out["auth_omitted"] += 1
    for k in ("unknown_routes", "method_mismatch", "auth_wrong", "node_mismatch", "diagram_cite_wrong", "unknown_participants"):
        out[k + "_count"] = len(out[k])
        out[k] = out[k][:25]
    return out


def source_identifiers(src, repo):
    ident = set()
    exts = ("*.go",) if repo == "go" else ("*.py",)
    for e in exts:
        for p in src.rglob(e):
            s = "/" + str(p.relative_to(src)) + "/"
            if any(d in s for d in SKIP_DIRS):
                continue
            ident.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", p.read_text(errors="ignore")))
    for p in src.rglob("*"):
        if p.is_dir() and not any(d in "/" + str(p) + "/" for d in SKIP_DIRS):
            ident.add(p.name)
            ident.update(re.split(r"[-_.]", p.name))
    return ident


# ----------------------------------------------------------------------------- prose citations
def is_header_only_cite(rel, end, src):
    suffix = Path(rel).suffix.lower()
    if suffix in {".md", ".rst", ".txt", ".yml", ".yaml"}:
        return True
    L = src_lines(src, rel)
    window = "\n".join(L[:end]) if L else ""
    if suffix == ".sql":
        return not re.search(r"CREATE\s+TABLE", window, re.I)
    if L is None:
        return False
    if re.search(r"^(type\s+\w+\s+struct|func\s+main\b|func\s+\w+|def\s+\w+|class\s+\w+|podman-|docker-|poetry |alembic |uvicorn )", window, re.M):
        return False
    return not re.search(r"\S", window)


def check_citations(pages, src, routes, repo):
    idx = route_index(routes)
    header, cite_only, missing_file, out_of_range = [], 0, [], []
    route_total = route_exact = route_in_range = route_file = route_unknown = 0
    route_bad = []
    empty_handler, api_lines_without_cite = [], []
    for rel, t in pages.items():
        body = strip_fences(t)
        for m in re.finditer(r"<cite>\s*([^<:\s][^<]*?):1-([1-8])\s*</cite>", body):
            if is_header_only_cite(m.group(1), int(m.group(2)), src):
                header.append({"page": rel, "cite": m.group(0)})
        for line in body.splitlines():
            s = line.strip()
            if s and re.fullmatch(r"(\s*<cite>[^<]*</cite>\s*[。.，,]?)+", s):
                cite_only += 1
            if re.search(r"）\s*。", line) and "handler" in line:
                empty_handler.append({"page": rel, "line": s[:160]})
            if rel.startswith("API") and ROUTE_IN_TEXT_RE.search(line) and "<cite>" not in line and not s.startswith("|---"):
                api_lines_without_cite.append({"page": rel, "line": s[:160]})
        for m in CITE_RE.finditer(body):
            f, a, b = m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))
            L = src_lines(src, f)
            if L is None:
                missing_file.append({"page": rel, "cite": m.group(0)})
            elif a < 1 or b > len(L):
                out_of_range.append({"page": rel, "cite": m.group(0)})
        for m in re.finditer(r"\b(GET|POST|PUT|DELETE|PATCH|ANY|HEAD|OPTIONS)\s+`?(/[^\s（(，,`<|]*)`?[^\n<]{0,80}?<cite>([^<:]+):(\d+)(?:-(\d+))?</cite>", body):
            meth, path = m.group(1), norm_path(m.group(2))
            f, a, b = m.group(3), int(m.group(4)), int(m.group(5) or m.group(4))
            cands = [r for r in idx.get(path, []) if r["method"] in (meth, "ANY")] or idx.get(path, [])
            route_total += 1
            if not cands:
                route_unknown += 1
                continue
            res = [cite_matches_route(repo, r, f, a, b) for r in cands]
            if any(r["file"] == f for r in cands):
                route_file += 1
            if any(x[0] for x in res):
                route_exact += 1
            elif len(route_bad) < 25:
                route_bad.append({"page": rel, "route": f"{meth} {path}", "cited": f"{f}:{a}-{b}",
                                  "expected_one_of": [f'{r["file"]}:{r["line"]}' for r in cands]})
            if any(x[1] for x in res):
                route_in_range += 1
    known = route_total - route_unknown
    return {
        "header_cites": {"count": len(header), "pages": len({h["page"] for h in header}), "items": header[:20]},
        "citation_only_lines": cite_only,
        "cite_missing_file": {"count": len(missing_file), "items": missing_file[:10]},
        "cite_out_of_range": {"count": len(out_of_range), "items": out_of_range[:10]},
        "route_cites": {"total": route_total, "known_route": known, "unknown_route": route_unknown, "file_match": route_file,
                        "exact": route_exact, "range_covers": route_in_range,
                        "exact_pct": round(100 * route_exact / known, 1) if known else None, "bad_examples": route_bad},
        "missing_route_cites": {"empty_handler_cite": len(empty_handler), "examples": empty_handler[:10],
                                "api_route_lines_without_cite": len(api_lines_without_cite)},
        "definitions": {"exact": "go: cite start == registration line; fastapi: start within decorator..def",
                        "empty_handler_cite": "line mentions handler and ends with '）。' without a cite (legacy signal)"},
    }


# ----------------------------------------------------------------------------- compose
def parse_compose(path):
    """Minimal YAML reader for services.<name>.depends_on / env_file / container_name."""
    services, cur, key = {}, None, None
    in_services = False
    for raw in path.read_text(errors="ignore").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        ind = len(raw) - len(raw.lstrip())
        s = raw.strip()
        if ind == 0:
            in_services = s.startswith("services:")
            cur = None
            continue
        if not in_services:
            continue
        if ind == 2 and s.endswith(":"):
            cur = s[:-1].strip().strip("'\"")
            services[cur] = {"depends_on": set(), "env_file": set(), "container_name": None}
            key = None
            continue
        if cur is None:
            continue
        if ind == 4:
            k, _, v = s.partition(":")
            key = k.strip()
            v = v.strip()
            if key == "container_name":
                services[cur]["container_name"] = v.strip("'\"")
            elif key in ("depends_on", "env_file") and v:
                vals = [x.strip(" '\"") for x in v.strip("[]").split(",") if x.strip()]
                services[cur][key].update(vals)
            continue
        if ind >= 6 and key in ("depends_on", "env_file"):
            if s.startswith("- "):
                services[cur][key].add(s[2:].strip(" '\""))
            elif ind == 6 and s.endswith(":"):
                services[cur][key].add(s[:-1].strip(" '\""))
    return services


def check_compose(blocks, src):
    files = sorted([p for p in src.iterdir() if p.is_file() and re.search(r"compose.*\.ya?ml$", p.name)])
    comp = {p.name: parse_compose(p) for p in files}
    all_services = {s for c in comp.values() for s in c} | {c["container_name"] for cf in comp.values() for c in cf.values() if c["container_name"]}
    diagrams = []
    for b in blocks:
        if b.get("kind") not in ("flowchart", "graph"):
            continue
        labels = dict(re.findall(r"^\s*([\w-]+)\s*[\[(]+\s*\"?([^\]\)\"]+)", b["raw"], re.M))
        edges = re.findall(r"^\s*([\w-]+)\s*-+\.?-*>\s*(?:\|[^|]*\|\s*)?([\w-]+)", b["raw"], re.M)
        names = {k: labels.get(k, k) for e in edges for k in e}
        comp_nodes = [n for n in names.values() if n in all_services or n.startswith(".env")]
        if len(set(comp_nodes)) < 2:
            continue
        res = []
        for x, y in edges:
            a, c = names[x], names[y]
            real_in = []
            for fn, svc in comp.items():
                if a in svc and c in svc[a]["depends_on"]:
                    real_in.append(fn)
                elif a.startswith(".env") and c in svc and any(Path(e).name == a for e in svc[c]["env_file"]):
                    real_in.append(fn)
            res.append({"edge": f"{a} -> {c}", "declared_in": real_in})
        invented = [r["edge"] for r in res if not r["declared_in"]]
        full = [fn for fn in comp if all(fn in r["declared_in"] for r in res)] if res else []
        diagrams.append({"page": b["page"], "hash": b["raw_hash"], "edges": res, "invented": invented,
                         "all_edges_in_one_file": full})
    return {"compose_files": list(comp), "diagrams": diagrams,
            "invented_edges": sum(len(d["invented"]) for d in diagrams)}


# ----------------------------------------------------------------------------- ER
PY_TYPE = {"integer": "int", "biginteger": "int", "smallinteger": "int", "text": "string", "string": "string", "unicode": "string",
           "varchar": "string", "boolean": "bool", "datetime": "datetime", "timestamp": "datetime", "float": "float", "numeric": "float"}


def balanced_calls(txt, opener):
    for m in re.finditer(re.escape(opener), txt):
        i, depth = m.end(), 1
        while i < len(txt) and depth:
            depth += {"(": 1, ")": -1}.get(txt[i], 0)
            i += 1
        yield txt[m.end(): i - 1]


def split_top_level(args):
    parts, depth, cur = [], 0, []
    for ch in args:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur).strip())
    return parts


def schema_from_alembic(src):
    tables = {}
    for mig in sorted(src.glob("**/migrations/versions/*.py")):
        txt = mig.read_text()
        ts_cols = []
        for body in balanced_calls(txt, "def timestamps("):
            pass
        tm = re.search(r"def timestamps\(.*?\n(?=def |\Z)", txt, re.S)
        if tm:
            ts_cols = re.findall(r'sa\.Column\(\s*"(\w+)"', tm.group(0))
        for args in balanced_calls(txt, "op.create_table("):
            parts = split_top_level(args)
            if not parts:
                continue
            name = parts[0].strip("'\"")
            cols, fks = {}, []
            for part in parts[1:]:
                if part == "*timestamps()":
                    for tc in ts_cols:
                        cols[tc] = {"type": "datetime", "pk": False}
                    continue
                cm = re.match(r'sa\.Column\(\s*"(\w+)"\s*,\s*sa\.(\w+)', part)
                if not cm:
                    continue
                cols[cm.group(1)] = {"type": PY_TYPE.get(cm.group(2).lower(), cm.group(2).lower()), "pk": "primary_key=True" in part}
                fk = re.search(r'sa\.ForeignKey\(\s*"(\w+)\.(\w+)"', part)
                if fk:
                    fks.append({"column": cm.group(1), "ref_table": fk.group(1), "ref_column": fk.group(2)})
            tables[name] = {"columns": cols, "fks": fks, "file": str(mig.relative_to(src))}
        for args in balanced_calls(txt, "op.create_primary_key("):
            parts = split_top_level(args)
            if len(parts) >= 3:
                t = tables.get(parts[1].strip("'\""))
                for cn in re.findall(r'"(\w+)"', parts[2]):
                    if t and cn in t["columns"]:
                        t["columns"][cn]["pk"] = True
    return tables


SQL_TYPE = [("int", "int"), ("bigint", "int"), ("tinyint", "int"), ("smallint", "int"), ("varchar", "string"), ("char", "string"),
            ("text", "string"), ("json", "json"), ("enum", "string"), ("datetime", "datetime"), ("timestamp", "datetime"),
            ("date", "datetime"), ("decimal", "float"), ("double", "float"), ("float", "float"), ("bool", "bool"), ("blob", "bytes"),
            ("varbinary", "bytes"), ("binary", "bytes")]


def schema_from_sql(src):
    tables = {}
    for sql in [src / "db/schema.sql"] if (src / "db/schema.sql").is_file() else []:
        txt = sql.read_text(errors="ignore")
        for m in re.finditer(r"CREATE TABLE(?: IF NOT EXISTS)?\s+`?(\w+)`?\s*\((.*?)\n\)\s*[^;]*;", txt, re.S | re.I):
            name, body = m.group(1), m.group(2)
            cols, fks, pks = {}, [], set()
            for line in body.splitlines():
                s = line.strip().rstrip(",")
                cm = re.match(r"`?(\w+)`?\s+(\w+)", s)
                if re.match(r"PRIMARY KEY", s, re.I):
                    pks.update(re.findall(r"`?(\w+)`?", s.split("(", 1)[1]))
                elif re.search(r"FOREIGN KEY", s, re.I):
                    fm = re.search(r"FOREIGN KEY\s*\(`?(\w+)`?\)\s*REFERENCES\s*`?(\w+)`?\s*\(`?(\w+)`?\)", s, re.I)
                    if fm:
                        fks.append({"column": fm.group(1), "ref_table": fm.group(2), "ref_column": fm.group(3)})
                elif cm and not re.match(r"(KEY|UNIQUE|INDEX|CONSTRAINT|CHECK)\b", s, re.I):
                    ty = cm.group(2).lower()
                    t = next((v for k, v in SQL_TYPE if ty.startswith(k)), ty)
                    cols[cm.group(1)] = {"type": t, "pk": "PRIMARY KEY" in s.upper()}
            for p in pks:
                if p in cols:
                    cols[p]["pk"] = True
            tables[name] = {"columns": cols, "fks": fks, "file": str(sql.relative_to(src))}
    return tables


def go_model_structs(src, sql_tables):
    """entity name -> {columns: fieldname->{pk}, fks} using internal/models structs, TableName() and schema.sql FKs."""
    out = {}
    for p in sorted((src / "internal/models").glob("*.go")) if (src / "internal/models").is_dir() else []:
        if p.name.endswith("_test.go"):
            continue
        L = p.read_text(errors="ignore").splitlines()
        txt = "\n".join(L)
        for i, l in enumerate(L):
            m = re.match(r"type\s+(\w+)\s+struct\s*\{", l)
            if not m:
                continue
            name, cols = m.group(1), {}
            for j in range(i + 1, len(L)):
                if re.match(r"^}", L[j]):
                    break
                fm = re.match(r"\s*(\w+)\s+([\w.*\[\]]+)(.*)", L[j])
                if fm and not L[j].strip().startswith("//"):
                    tag = fm.group(3)
                    cols[fm.group(1)] = {"pk": "primaryKey" in tag or "primary_key" in tag, "type_go": fm.group(2)}
            tn = re.search(r"func \(\w*\s*\*?%s\) TableName\(\) string \{\s*return \"(\w+)\"" % name, txt, re.S)
            table = tn.group(1) if tn else None
            out[name] = {"columns": cols, "table": table, "fks": [], "file": str(p.relative_to(src))}
    by_table = {v["table"]: k for k, v in out.items() if v["table"]}
    for tname, t in sql_tables.items():
        for fk in t["fks"]:
            a, c = by_table.get(fk["ref_table"]), by_table.get(tname)
            if a and c:
                out[c]["fks"].append({"column": fk["column"], "ref_table": a, "ref_column": fk["ref_column"]})
    return out


def check_er(blocks, tables, strict_types=True):
    out = []
    for b in blocks:
        if b.get("kind") != "erDiagram":
            continue
        ents = {}
        for m in re.finditer(r"^\s*(\w+)\s*\{(.*?)\}", b["raw"], re.S | re.M):
            fields = []
            for fl in m.group(2).strip().splitlines():
                parts = fl.split()
                if len(parts) >= 2:
                    fields.append({"type": parts[0].lower(), "name": parts[1], "keys": [p for p in parts[2:] if p in ("PK", "FK", "UK")]})
            ents[m.group(1)] = fields
        rels = re.findall(r"^\s*(\w+)\s*[|}o]{1,2}--[|{o]{1,2}\s*(\w+)\s*:\s*\"?([\w ]+?)\"?\s*$", b["raw"], re.M)
        issues = []
        for en, fields in ents.items():
            t = tables.get(en)
            if not t:
                issues.append(f"entity {en} not in schema")
                continue
            if not fields:
                issues.append(f"entity {en} empty")
            for f in fields:
                col = t["columns"].get(f["name"])
                if not col:
                    issues.append(f"{en}.{f['name']} invented column")
                    continue
                col_pk = col["pk"] or (f["name"] == "ID" and "type_go" in col)
                if ("PK" in f["keys"]) != col_pk:
                    issues.append(f"{en}.{f['name']} PK flag {'PK' in f['keys']} vs schema {col['pk']}")
                if strict_types and col["type"] in ("int", "string", "datetime", "bool", "float") and f["type"] in ("int", "string", "datetime", "bool", "float") and f["type"] != col["type"]:
                    issues.append(f"{en}.{f['name']} type {f['type']} vs schema {col['type']}")
            if fields:
                pk_cols = {c for c, v in t["columns"].items() if v["pk"] or (c == "ID" and "type_go" in v)}
                shown_pk = {f["name"] for f in fields if "PK" in f["keys"]}
                if pk_cols - shown_pk:
                    issues.append(f"{en} missing PK columns {sorted(pk_cols - shown_pk)}")
        real_fk = {(fk["ref_table"], tn, fk["column"]) for tn, t in tables.items() for fk in t["fks"]}
        rel_real, rel_bad = 0, []
        for a, c, lab in rels:
            lab = lab.strip()
            if (a, c, lab) in real_fk or any({x[0], x[1]} == {a, c} for x in real_fk):
                rel_real += 1
            else:
                rel_bad.append(f"{a} -> {c} : {lab}")
        shown = set(ents) | {x for r in rels for x in r[:2]}
        expected = {x for x in real_fk if x[0] in shown and x[1] in shown}
        missing = sorted(f"{x[0]} -> {x[1]} : {x[2]}" for x in expected if not any({r[0], r[1]} == {x[0], x[1]} for r in rels))
        out.append({"page": b["page"], "hash": b["raw_hash"], "entities": len(ents), "relationships": len(rels),
                    "relationships_real": rel_real, "relationships_invented": rel_bad, "fks_missing_among_shown": missing,
                    "issues": issues})
    return {"schema_tables": len(tables), "diagrams": out, "issue_count": sum(len(d["issues"]) + len(d["relationships_invented"]) for d in out)}


# ----------------------------------------------------------------------------- structs
CORE_GO_STRUCTS = ("ProbeEndpoint", "ProbeResult", "ProbeTag", "ProbeSecret", "ProbeBlackboxModule", "BizTreeNode",
                   "BizInstanceEndpoint", "ProbePolicy", "ProbeRoutingBinding", "AgentRegistry", "AgentOpsSample")


def check_structs(pages, src):
    seen, exact, off = set(), 0, []
    names, models_total, models_exact = {}, [0], [0]
    for rel, t in pages.items():
        for m in CITE_RE.finditer(t):
            f, a, b = m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))
            if not f.endswith(".go"):
                continue
            L = src_lines(src, f)
            if not L or a > len(L):
                continue
            sm = re.match(r"\s*type\s+(\w+)\s+struct\s*\{", L[a - 1])
            if not sm or (f, a, b) in seen:
                continue
            seen.add((f, a, b))
            if L[a - 1].rstrip().endswith("}"):
                end = a
            else:
                end = next((i + 1 for i in range(a - 1, len(L)) if re.match(r"^}", L[i])), None)
            names[sm.group(1)] = end == b
            if f.startswith("internal/models/"):
                models_total[0] += 1
                models_exact[0] += end == b
            if end == b:
                exact += 1
            else:
                off.append({"struct": sm.group(1), "cite": f"{f}:{a}-{b}", "real_end": end})
    runon = [rel for rel, t in pages.items() for line in t.splitlines() if line.count("<cite>") >= 8]
    return {"struct_cites": len(seen), "exact": exact, "models_struct_cites": models_total[0], "models_exact": models_exact[0],
            "off": off[:20],
            "core_present_exact": {n: names.get(n) for n in CORE_GO_STRUCTS},
            "runon_cite_lines_pages": sorted(set(runon))}


# ----------------------------------------------------------------------------- go package edges
def check_go_edges(blocks, src, enable):
    if not enable:
        return {"status": "skipped", "reason": "pass --golist to run `go list` in the source dir"}
    if not shutil.which("go"):
        return {"status": "skipped", "reason": "go not found"}
    mod = re.search(r"^module\s+(\S+)", (src / "go.mod").read_text(), re.M).group(1)
    r = subprocess.run(["go", "list", "-f", "{{.ImportPath}} {{join .Imports \" \"}}", "./..."], cwd=src, capture_output=True, text=True, timeout=300)
    if r.returncode:
        return {"status": "error", "stderr": r.stderr[-400:]}
    imports = {}
    for line in r.stdout.splitlines():
        parts = line.split()
        if parts:
            imports[parts[0].replace(mod + "/", "").replace(mod, ".")] = {p.replace(mod + "/", "") for p in parts[1:] if p.startswith(mod)}
    total, bad = 0, []
    for b in blocks:
        if b.get("kind") not in ("flowchart", "graph"):
            continue
        labels = dict(re.findall(r"^\s*([\w-]+)\s*\[\s*\"?([^\]\"]+)", b["raw"], re.M))
        for x, y in re.findall(r"^\s*([\w-]+)\s*-+>\s*([\w-]+)", b["raw"], re.M):
            a, c = labels.get(x, x), labels.get(y, y)
            if a in imports and (c in imports or c.startswith(("internal/", "cmd/"))):
                total += 1
                if c not in imports.get(a, set()):
                    bad.append({"page": b["page"], "edge": f"{a} -> {c}"})
    return {"status": "ran", "package_edges": total, "not_imported": bad}


def check_go_builds(pages, src, enable):
    cmds = sorted({m.group(0).strip() for t in pages.values() for m in re.finditer(r"go build[^\n`<]*", t)})
    if not enable:
        return {"status": "skipped", "commands_found": cmds}
    tmp = Path(tempfile.mkdtemp(prefix="accept-gobuild-"))
    res = []
    segs = []
    for c in cmds:
        for seg in re.split(r"\s*(?:&&|;|\|\|)\s*", c):
            seg = seg.strip()
            if seg.startswith("go build"):
                segs.append((c, seg))
    for c, seg in segs:
        parts = seg.split()
        if "-o" in parts:
            i = parts.index("-o")
            parts[i + 1] = str(tmp / Path(parts[i + 1]).name)
        else:
            parts[2:2] = ["-o", str(tmp / "out")]
        if parts[-1] in ("build", "bin/...") or parts[-1].endswith("..."):
            res.append({"cmd": seg if seg == c else f"{seg}  (from: {c})", "ok": False, "err": "incomplete command"})
            continue
        r = subprocess.run(parts, cwd=src, capture_output=True, text=True, timeout=300)
        res.append({"cmd": seg if seg == c else f"{seg}  (from: {c})", "ok": r.returncode == 0, "err": r.stderr[-200:] if r.returncode else ""})
    return {"status": "ran", "results": res, "failed": [x for x in res if not x["ok"]]}


# ----------------------------------------------------------------------------- front-end flow (go)
def check_frontend(blocks, src, routes):
    fetched = set()
    for d in ("web/src", "static"):
        for p in (src / d).rglob("*") if (src / d).is_dir() else []:
            if p.suffix in (".js", ".ts", ".tsx", ".vue", ".html"):
                fetched.update(re.findall(r"['\"`](/(?:api|probe|tag|hello|reflect|metrics)[^'\"`?\s]*)", p.read_text(errors="ignore")))
    fetched = {re.sub(r"\$\{[^}]*\}", ":param", f).rstrip("/") for f in fetched}
    if not fetched:
        return {"status": "n/a"}
    bad, checked = [], 0
    for b in blocks:
        if "前端" not in b["page"] or b.get("kind") != "sequenceDiagram":
            continue
        for m in ROUTE_IN_TEXT_RE.finditer(b["raw"]):
            path = norm_path(m.group(2))
            checked += 1
            pat = re.sub(r":\w+", ":param", path)
            if pat not in fetched:
                bad.append({"page": b["page"], "route": f"{m.group(1)} {path}"})
    return {"status": "ran", "frontend_fetch_paths": len(fetched), "diagram_routes_checked": checked, "not_fetched_by_frontend": bad}


# ----------------------------------------------------------------------------- misc reader hygiene
def check_misc(pages, src):
    res = {}
    res["unresolved_markers"] = sum(t.count("UNRESOLVED") for t in pages.values())
    res["truncated_commands"] = [{"page": r, "text": m.group(0)} for r, t in pages.items() for m in re.finditer(r"bin/[\w-]*\.\.\.|bin/probe-…", t)]
    bad_toc = []
    for r, t in pages.items():
        L = t.splitlines()
        hi = next((i for i, l in enumerate(L) if l.startswith("# ")), None)
        ti = next((i for i, l in enumerate(L) if l.startswith("## 目录")), None)
        if hi is None or ti is None or ti - hi > 4:
            bad_toc.append(r)
    res["toc_not_after_title"] = {"count": len(bad_toc), "pages": bad_toc[:10]}
    leaks = collections.Counter()
    for r, t in pages.items():
        for k in ("当前证据", "提供的证据", "证据片段", "页面规划", "证据绑定", "evidence"):
            if k in strip_fences(t):
                leaks[k] += strip_fences(t).count(k)
    res["model_voice_leaks"] = dict(leaks)
    paras = collections.defaultdict(set)
    for r, t in pages.items():
        for para in re.split(r"\n\s*\n", t):
            k = re.sub(r"\s+", " ", para).strip()
            if len(k) >= 80 and "```" not in k:
                paras[k].add(r)
    res["repeated_paragraphs_4plus_pages"] = sum(1 for v in paras.values() if len(v) >= 4)
    res["source_dir_name_leaks"] = sum(t.count(src.name) for t in pages.values()) if src.name.endswith("-eval") else 0
    return res


def check_security_go(pages, src):
    sec = {r: t for r, t in pages.items() if r.startswith("安全")}
    txt = "\n".join(sec.values())
    return {"pages": len(sec), "mentions_PROBE_API_TOKEN": "PROBE_API_TOKEN" in txt,
            "aksk_claims": len(re.findall(r"AK/SK|AccessKey", txt)),
            "token_const_cite": re.findall(r"apiauth\.go:\d+(?:-\d+)?", txt)[:4]}


# ----------------------------------------------------------------------------- main
TODO_MANUAL = [
    "install paths self-sufficient: read 项目概述/安装与配置 path A/B against README + compose (use --build for go build commands)",
    "verify commands reasoned against code (route exists, port, auth exemption)",
    "architecture / role prose vs deterministic roles and `go list` (e.g. ccagent REST server, probe-agent tunnel client)",
    "security prose semantics beyond token-name presence",
    "request-flow semantics beyond method/auth/node/cite (e.g. whether an error-mapping step really happens)",
    "Go RegisterService reflection routes: method/path come from the generator inventory (meta/source-inventory.json), not an independent parser",
    "human-style read of ~10 sampled pages",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("handbook_dir")
    ap.add_argument("source_dir")
    ap.add_argument("--repo", choices=["go", "fastapi"], required=True)
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--golist", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    content, meta = resolve_content(Path(a.handbook_dir).resolve())
    src = Path(a.source_dir).resolve()
    pages = load_pages(content)
    blocks = extract_mermaid(pages)
    report = {"handbook": str(content), "source": str(src), "repo": a.repo, "pages": len(pages)}
    report["text_gaps"] = check_text_gaps(pages)
    report["mermaid"] = check_mermaid(pages, blocks, render=a.render)
    if a.repo == "go":
        routes, rmeta = build_go_routes(src, meta)
    else:
        routes, rmeta = build_fastapi_routes(src)
    report["route_table"] = {"routes": len(routes), "by_source": dict(collections.Counter(r["source"].split(":")[0] + ":" + r["source"].split(":")[1] if ":" in r["source"] else r["source"] for r in routes)), **rmeta}
    ident = source_identifiers(src, a.repo)
    report["request_flow"] = check_sequences(blocks, routes, a.repo, ident)
    report["citations"] = check_citations(pages, src, routes, a.repo)
    report["compose"] = check_compose(blocks, src)
    if a.repo == "fastapi":
        report["er"] = check_er(blocks, schema_from_alembic(src), strict_types=True)
    else:
        report["er"] = check_er(blocks, go_model_structs(src, schema_from_sql(src)), strict_types=False)
        report["er"]["schema_source"] = "internal/models structs (fields, gorm primaryKey) + schema.sql FKs mapped via TableName()"
    if a.repo == "go":
        report["structs"] = check_structs(pages, src)
        report["go_package_edges"] = check_go_edges(blocks, src, a.golist)
        report["go_builds"] = check_go_builds(pages, src, a.build)
        report["frontend_flow"] = check_frontend(blocks, src, routes)
        report["security"] = check_security_go(pages, src)
    report["misc"] = check_misc(pages, src)
    if not a.render:
        report["mermaid"]["render"] = {"status": "skipped", "reason": "pass --render"}
    report["todo_manual"] = TODO_MANUAL
    m, rf, c = report["mermaid"], report["request_flow"], report["citations"]
    report["summary"] = {
        "text_gaps": report["text_gaps"]["hits"],
        "mermaid_distinct_normalized": m["distinct_normalized"], "coverage_honest_pct": m["coverage_honest_pct"],
        "coverage_strict_pct": m["coverage_strict_pct"],
        "copied_diagrams": len(m["copies_across_pages"]), "near_duplicate_pairs": len(m["near_duplicates"]),
        "raw_cite_in_mermaid_tags": m["raw_cite_in_mermaid"]["tags"], "empty_messages": m["empty_message_count"],
        "method_mismatch": rf["method_mismatch_count"], "auth_wrong": rf["auth_wrong_count"], "node_mismatch": rf["node_mismatch_count"],
        "diagram_cite_wrong": f'{rf["diagram_cite_wrong_count"]}/{rf["diagram_cite_checked"]}',
        "unknown_participants": rf["unknown_participants_count"],
        "header_cites": c["header_cites"]["count"], "citation_only_lines": c["citation_only_lines"],
        "route_exact_pct": c["route_cites"]["exact_pct"], "route_exact": f'{c["route_cites"]["exact"]}/{c["route_cites"]["known_route"]}',
        "empty_handler_cite": c["missing_route_cites"]["empty_handler_cite"],
        "compose_invented_edges": report["compose"]["invented_edges"], "er_issues": report["er"]["issue_count"],
    }
    if a.repo == "go":
        report["summary"]["struct_cites_exact"] = f'{report["structs"]["exact"]}/{report["structs"]["struct_cites"]}'
        report["summary"]["models_struct_cites_exact"] = f'{report["structs"]["models_exact"]}/{report["structs"]["models_struct_cites"]}'
        report["summary"]["frontend_routes_not_fetched"] = len(report["frontend_flow"].get("not_fetched_by_frontend", []))
    js = json.dumps(report, ensure_ascii=False, indent=1, default=list)
    if a.out:
        Path(a.out).write_text(js)
    print(js)


if __name__ == "__main__":
    main()
