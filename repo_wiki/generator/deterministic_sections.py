"""Deterministic handbook sections derived from repository evidence.

Install steps, compose topology, role cites, and ER tables are built from
files, not from regex rewriting of LLM fences.
"""

from __future__ import annotations

import re
from pathlib import Path

from repo_wiki.verifier.handbook import (
    existing_readme_names,
    preferred_source_listen_port,
    read_readme_text,
)

_H2_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_FENCE_RE = re.compile(r"```(?:bash|sh|mermaid|sql|json)\n.*?```", re.IGNORECASE | re.DOTALL)
_META_IMPERATIVE_RE = re.compile(
    r"不要把测试|不要把 README|不要把 package|不要将|不要引用|不要声称|"
    r"don't treat|do not treat|不得视为|不要用测试",
    re.IGNORECASE,
)
_HEADER_CITE_RE = re.compile(
    r"<cite>\s*([^<:\s][^<]*?):1-([1-8])\s*</cite>",
    re.IGNORECASE,
)
_PLANNING_LEAK_RE = re.compile(
    r"页面规划与证据绑定|页面基于仓库扫描|从提供的证据可见|证据中可确认的"
)
_REQUIRED_GO_STRUCTS = ("ProbeEndpoint", "ProbeResult", "ProbeTag", "ProbeSecret")
_INSTALL_OWNER_IDS = frozenset({"installation"})
_INSTALL_SATELLITE_IDS = frozenset(
    {"quick-start", "quickstart", "getting-started", "local-setup", "environment-setup"}
)
_ARCH_OWNER_IDS = frozenset({"architecture-overview"})
_API_OWNER_IDS = frozenset({"api-overview", "api-reference", "api"})
_DATA_MODEL_OWNER_IDS = frozenset({"data-models-overview", "data-model", "data-models"})
_SECURITY_OWNER_IDS = frozenset({"security-overview", "security"})
_OPERATIONAL_ADVICE_RE = re.compile(
    r"不要混用|不要把这些|不要把它|不要误用|不要当作默认|不要把它当作"
)
_PAGE_ID_SUFFIX_RE = re.compile(r"[ \t]*\[[a-z0-9-]{8,}\]")
_MERMAID_FENCE_RE = re.compile(r"```mermaid\s*.*?```", re.IGNORECASE | re.DOTALL)
_README_ROUTE_CITE_RE = re.compile(
    r"((?:GET|POST|PUT|PATCH|DELETE)\s+(/\S+))([^<\n]*<cite>\s*README\.[^<]+:1-\d+\s*</cite>)",
    re.IGNORECASE,
)
_UNRESOLVED_API_RE = re.compile(r"UNRESOLVED_API_[A-Z_]+")
_EMPTY_NUMBERED_RE = re.compile(
    r"(?m)^(\d+)\.\s+\S[^\n]*\n(?:<cite>[^<]+</cite>\s*\n)?(?:[ \t]*\n){2,}"
)
_GO_SECURITY_HINTS = (
    "apiauth.go",
    "internal/auth",
    "internal/secrets",
    "internal/audit",
    "internal/netguard",
    "internal/security",
    "deploy/mtls",
)
_FASTAPI_SECURITY_HINTS = (
    "app/services/jwt.py",
    "app/services/security.py",
    "app/api/dependencies/authentication.py",
)


def is_install_owner_page(*, page_id: str = "", title: str = "") -> bool:
    pid = (page_id or "").lower().rsplit("/", 1)[-1]
    if pid in _INSTALL_SATELLITE_IDS:
        return False
    if pid in _INSTALL_OWNER_IDS:
        return True
    return any(token in (title or "") for token in ("安装与配置", "安装指南"))


def is_architecture_owner_page(*, page_id: str = "", title: str = "") -> bool:
    pid = (page_id or "").lower().rsplit("/", 1)[-1]
    if pid in _ARCH_OWNER_IDS:
        return True
    return (title or "") in {"整体架构概览", "架构设计"}


def is_api_catalog_owner_page(*, page_id: str = "", title: str = "") -> bool:
    pid = (page_id or "").lower().rsplit("/", 1)[-1]
    return pid in _API_OWNER_IDS or (title or "") in {"API参考", "API 参考"}


def is_security_owner_page(*, page_id: str = "", title: str = "") -> bool:
    pid = (page_id or "").lower().rsplit("/", 1)[-1]
    return pid in _SECURITY_OWNER_IDS or (title or "") in {"安全合规", "安全合规概览"}


def is_data_model_owner_page(*, page_id: str = "", title: str = "") -> bool:
    pid = (page_id or "").lower().rsplit("/", 1)[-1]
    return pid in _DATA_MODEL_OWNER_IDS or (title or "") in {"数据模型"}


def is_join_er_owner_page(*, page_id: str = "", title: str = "") -> bool:
    pid = (page_id or "").lower().rsplit("/", 1)[-1]
    title_s = title or ""
    if "迁移" in title_s or "问题" in title_s:
        return False
    return pid in {"database-schema", "database-architecture"} or title_s == "数据库架构"


_INVENTED_JOIN_ID_PK_RE = re.compile(
    r"(?P<head>(?:followers_to_followings|articles_to_tags|favorites)\s*\{)"
    r"(?P<body>[^}]*)"
    r"(?P<tail>\})",
    re.S,
)


def strip_invented_join_id_pk(content: str) -> str:
    """Drop renderer fallback ``string id PK`` from join tables that already have keys."""

    def _repl(match: re.Match[str]) -> str:
        body = re.sub(r"\n[ \t]*string id PK[ \t]*", "\n", match.group("body"))
        body = re.sub(r"[ \t]*string id PK[ \t]*", "", body)
        return f"{match.group('head')}{body}{match.group('tail')}"

    return _INVENTED_JOIN_ID_PK_RE.sub(_repl, content or "")


def strip_page_id_mermaid_suffixes(content: str) -> str:
    def _fix(match: re.Match[str]) -> str:
        return _PAGE_ID_SUFFIX_RE.sub("", match.group(0))

    return _MERMAID_FENCE_RE.sub(_fix, content or "")


def leftover_request_flow_is_untrustworthy(block: str) -> bool:
    text = block or ""
    if "ErrorWrapper" in text:
        return True
    if "/healthz" in text and ("X-Probe-Api-Token" in text or "APIAuth" in text):
        return True
    if re.search(r"GET\s+/force-resync", text):
        return True
    if "AuthenticationDep" in text and re.search(r"POST\s+/api/users(?!/login)", text):
        return True
    if "register" in text.lower() and "AuthenticationDep" in text:
        return True
    return False


def strip_untrustworthy_request_flow_mermaid(content: str) -> str:
    def _drop(match: re.Match[str]) -> str:
        block = match.group(0)
        return "" if leftover_request_flow_is_untrustworthy(block) else block

    return _MERMAID_FENCE_RE.sub(_drop, content or "")


def rewrite_join_tag_types(content: str) -> str:
    def _fix(match: re.Match[str]) -> str:
        block = match.group(0)
        if "erdiagram" not in block.lower():
            return block
        return re.sub(r"\bint tag\b", "string tag", block)

    return _MERMAID_FENCE_RE.sub(_fix, content or "")


def package_strip_targets(content: str, root: Path) -> list[str]:
    known = known_go_package_names(root)
    targets: list[str] = []
    for match in re.finditer(r"`internal/([A-Za-z0-9_-]+)`", content or ""):
        if match.group(1) not in known and f"internal/{match.group(1)}" not in known:
            targets.append(match.group(0))
    for match in re.finditer(r"`([A-Za-z][A-Za-z0-9_-]{3,})`\s*包", content or ""):
        if match.group(1) not in known:
            targets.append(match.group(0))
    for match in re.finditer(
        r"(周边包如|子包如|内部包如|核心包如)\s*"
        r"((?:`[A-Za-z][A-Za-z0-9_-]{3,}`(?:[、,，]\s*)?)+)",
        content or "",
    ):
        for name in re.findall(r"`([A-Za-z][A-Za-z0-9_-]{3,})`", match.group(2)):
            if name not in known:
                targets.append(f"`{name}`")
    return targets


def known_go_package_names(root: Path) -> set[str]:
    names: set[str] = set()
    for base in ("internal", "cmd", "pkg"):
        directory = root / base
        if not directory.is_dir():
            continue
        for child in directory.iterdir():
            if child.is_dir():
                names.add(child.name)
                names.add(f"{base}/{child.name}")
    return names


def dangling_rewrite_artifacts(content: str) -> list[str]:
    """Flag gaps left when a backticked token was deleted (double spaces, bare particles)."""
    found: list[str] = []
    for match in re.finditer(r".{0,12}  .{0,12}", content or ""):
        snippet = match.group(0)
        if "  " in snippet and re.search(r"(使用|而非|以及|或者|并且|包)", snippet):
            found.append(snippet.strip())
    for match in re.finditer(r"使用\s{2,}而非", content or ""):
        found.append(match.group(0))
    return found


def audit_text_rewrite(before: str, after: str, *, target_spans: list[str]) -> dict[str, int]:
    """Count removed characters; anything outside an exact target span is collateral."""
    if before == after:
        return {"removed": 0, "targeted": 0, "collateral": 0}
    import difflib

    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
    removed = 0
    targeted = 0
    untargeted = []
    for tag, i1, i2, _j1, _j2 in matcher.get_opcodes():
        if tag not in {"delete", "replace"}:
            continue
        chunk = before[i1:i2]
        removed += len(chunk)
        covered = 0
        cores = [re.sub(r"[`\s、,，]", "", span) for span in target_spans if span]
        for span, core in zip(target_spans, cores, strict=False):
            if not span:
                continue
            if span in chunk or (core and core in chunk):
                covered = len(chunk)
                break
            if chunk in span and chunk.strip():
                covered = len(chunk)
                break
        targeted += min(len(chunk), covered)
        if covered == 0:
            untargeted.append(chunk)
    targeted = min(targeted, removed)
    leftover = max(0, removed - targeted)
    if leftover and re.fullmatch(r"[\s、,，`]*", "".join(untargeted) or ""):
        leftover = 0
        targeted = removed
    return {
        "removed": removed,
        "targeted": targeted,
        "collateral": leftover,
    }


def strip_unknown_go_packages(content: str, root: Path) -> str:
    """Remove only unknown names in an explicit package context; keep files/tables/commands."""
    known = known_go_package_names(root)
    if not known:
        return content or ""
    text = content or ""

    def _is_known(name: str) -> bool:
        return name in known or any(name == item.split("/")[-1] for item in known)

    def _internal(match: re.Match[str]) -> str:
        name = match.group(1)
        return match.group(0) if _is_known(name) or f"internal/{name}" in known else ""

    text = re.sub(r"`internal/([A-Za-z0-9_-]+)`", _internal, text)

    def _pkg_phrase(match: re.Match[str]) -> str:
        name = match.group(1)
        return match.group(0) if _is_known(name) else ""

    text = re.sub(r"`([A-Za-z][A-Za-z0-9_-]{3,})`(\s*包)", _pkg_phrase, text)

    def _pkg_list(match: re.Match[str]) -> str:
        names = re.findall(r"`([A-Za-z][A-Za-z0-9_-]{3,})`", match.group(2))
        kept = [f"`{name}`" for name in names if _is_known(name)]
        return match.group(1) + "、".join(kept)

    text = re.sub(
        r"(周边包如|子包如|内部包如|核心包如)\s*"
        r"((?:`[A-Za-z][A-Za-z0-9_-]{3,}`(?:[、,，]\s*)?)+)",
        _pkg_list,
        text,
    )
    text = re.sub(r"、\s*、", "、", text)
    text = re.sub(r"、{2,}", "、", text)
    text = re.sub(r"如\s*、", "如 ", text)
    if text != (content or ""):
        text = re.sub(r"(\S) {2,}(\S)", r"\1 \2", text)
    return text


def load_route_method_table(root: Path) -> dict[str, str]:
    """HTTP method by path from HandleFunc bodies and FastAPI decorators — not the LLM."""
    table: dict[str, str] = {}
    if not root.exists():
        return table
    handle = re.compile(r"""HandleFunc\(\s*["']([^"']+)["']""")
    fastapi = re.compile(
        r"""@(?:router|app)\.(post|get|put|patch|delete)\(\s*['"]([^'"]*)['"]""",
        re.I,
    )
    files: list[Path] = []
    for base in (root / "cmd", root / "internal", root / "app", root):
        if not base.exists():
            continue
        if base.is_file():
            continue
        files.extend(path for path in base.rglob("*.go") if not path.name.endswith("_test.go"))
        files.extend(base.rglob("*.py"))
    seen: set[Path] = set()
    for path in files:
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in handle.finditer(text):
            route = match.group(1)
            window = text[match.start() : match.start() + 480]
            if (
                "MethodPost" in window
                or 'Method != "POST"' in window
                or "http.MethodPost" in window
            ):
                table[route] = "POST"
            elif "MethodGet" in window or "http.MethodGet" in window:
                table[route] = "GET"
        for match in fastapi.finditer(text):
            route = match.group(2) or "/"
            table[route] = match.group(1).upper()
    return table


def rewrite_route_methods_from_table(content: str, root: Path) -> str:
    table = load_route_method_table(root)
    if not table:
        return content or ""

    def _repl(match: re.Match[str]) -> str:
        method, path = match.group(1).upper(), match.group(2)
        honest = table.get(path)
        if honest and honest != method:
            return f"{honest} {path}"
        return match.group(0)

    return re.sub(
        r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[A-Za-z0-9_/{}.:-]*)",
        _repl,
        content or "",
    )


def attach_missing_route_cites(content: str, endpoints: list[dict] | None) -> str:
    if not endpoints:
        return content or ""
    by_path: dict[str, dict] = {}
    for item in endpoints:
        path = str(item.get("path") or "")
        if path:
            by_path[path] = item
    out: list[str] = []
    claim = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[A-Za-z0-9_/{}.:-]*)")
    for line in (content or "").splitlines():
        if "<cite>" in line or not claim.search(line):
            out.append(line)
            continue
        match = claim.search(line)
        if match is None:
            out.append(line)
            continue
        found = by_path.get(match.group(2))
        if found is None:
            out.append(line)
            continue
        item = found
        file_path = str(item.get("file_path") or "")
        line_no = int(item.get("line_number") or item.get("line_start") or 0)
        if file_path and line_no > 0:
            out.append(f"{line.rstrip()} <cite>{file_path}:{line_no}-{line_no}</cite>")
        else:
            out.append(line)
    return "\n".join(out)


def leftover_mermaid_is_unusable(content: str) -> bool:
    blocks = re.findall(r"```mermaid\s*(.*?)```", content or "", flags=re.I | re.S)
    if not blocks:
        return False
    for block in blocks:
        if re.search(r"->>\s*\w+\s*:\s*$", block, flags=re.M):
            return True
        if "list flow" in block.lower():
            return True
        if "ErrorWrapper" in block:
            return True
        if re.search(r"\n    (users|articles|tags) \{\s*\n    \}", block):
            return True
        if "create_updated_at_trigger" in block and "commentaries" not in block.lower():
            return True
    return False


def leftover_compose_has_undeclared_env(content: str, root: Path) -> bool:
    from repo_wiki.generator.compose_evidence import (
        load_compose_from_root,
        mermaid_compose_edges,
    )

    _names, allowed = load_compose_from_root(root)
    allowed_set = set(allowed)
    for block in re.findall(r"```mermaid\s*(.*?)```", content or "", flags=re.I | re.S):
        if "erDiagram" in block or "sequenceDiagram" in block:
            continue
        for src, dest in mermaid_compose_edges(block):
            if src == ".env" and (src, dest) not in allowed_set:
                return True
    return False


def rewrite_readme_route_cites(content: str, endpoints: list[dict] | None) -> str:
    if not endpoints:
        return content or ""
    by_key: dict[tuple[str, str], dict] = {}
    for item in endpoints:
        method = str(item.get("method") or "").upper()
        path = str(item.get("path") or "")
        if method and path:
            by_key[(method, path)] = item

    def _repl(match: re.Match[str]) -> str:
        method = match.group(1).split()[0].upper()
        path = match.group(2)
        item = by_key.get((method, path))
        prefix = match.group(0).split("<cite>")[0].rstrip()
        if not item:
            return prefix
        file_path = str(item.get("file_path") or "")
        line = int(item.get("line_number") or item.get("line_start") or 0)
        if not file_path or line <= 0:
            return prefix
        return f"{prefix} <cite>{file_path}:{line}-{line}</cite>"

    return _README_ROUTE_CITE_RE.sub(_repl, content or "")


def has_runon_struct_cite_line(content: str) -> bool:
    for line in (content or "").splitlines():
        if line.count("<cite>") >= 8:
            return True
        if len(line) >= 400 and "<cite>" in line and "ProbeEndpoint" in line:
            return True
    return False


def rewrite_token_const_cite(content: str, root: Path) -> str:
    token = cite_first_match(root, "apiauth.go", r"EnvAPIToken\s*=")
    if not token:
        token = cite_first_match(root, "apiauth.go", r"PROBE_API_TOKEN")
    if not token:
        return content or ""
    return re.sub(r"<cite>\s*apiauth\.go:13-\d+\s*</cite>", token, content or "")


def rewrite_force_resync_method(content: str) -> str:
    return re.sub(r"GET(\s+/force-resync)", r"POST\1", content or "")


def sanitize_leftover_handbook_mermaid(content: str) -> str:
    text = strip_untrustworthy_request_flow_mermaid(content or "")
    text = strip_page_id_mermaid_suffixes(text)
    text = strip_invented_join_id_pk(text)
    text = rewrite_join_tag_types(text)
    return rewrite_force_resync_method(text)


def is_auth_identity_page(*, page_id: str = "", title: str = "") -> bool:
    pid = (page_id or "").lower().rsplit("/", 1)[-1]
    if "api" in pid or "授权" in (title or ""):
        return False
    return pid in {"identity-authentication", "authentication"} or (title or "") == "身份认证"


def cite_readme_line(root: Path, needle: str, *, last: bool = False) -> str:
    names = existing_readme_names(root)
    name = next((item for item in names if (root / item).is_file()), "")
    if not name:
        return ""
    found = ""
    for index, line in enumerate(read_readme_text(root).splitlines(), start=1):
        if needle in line:
            found = f"<cite>{name}:{index}-{index}</cite>"
            if not last:
                return found
    return found


def _line_is_comment_only(line: str) -> bool:
    stripped = (line or "").strip()
    return (
        stripped.startswith("//")
        or stripped.startswith("#")
        or stripped.startswith("/*")
        or stripped.startswith("*")
    )


def cite_first_match(root: Path, rel: str, pattern: str) -> str:
    path = root / rel
    if not path.is_file():
        return ""
    regex = re.compile(pattern)
    for index, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if _line_is_comment_only(line):
            continue
        if regex.search(line):
            return f"<cite>{rel}:{index}-{index}</cite>"
    return ""


def cite_existing_meaningful(root: Path, rel: str) -> str:
    """Cite the first definition line, never a file-header window."""
    path = root / rel
    if path.is_file():
        return cite_first_match(
            root,
            rel,
            r"^(func\s+|type\s+\w+|const\s+\w+|class\s+|def\s+)",
        ) or cite_first_match(root, rel, r"\S")
    if not path.exists():
        return ""
    for child in sorted(path.rglob("*")):
        if not child.is_file() or child.name.endswith("_test.go"):
            continue
        if child.suffix.lower() not in {".go", ".py", ".sql", ".ts"}:
            continue
        if child.name in {"__init__.py", "__main__.py"}:
            continue
        child_rel = child.relative_to(root).as_posix()
        cite = cite_first_match(
            root,
            child_rel,
            r"^(func\s+main\b|func\s+\w+|type\s+\w+\s+struct|class\s+\w+|def\s+\w+)",
        )
        if cite:
            return cite
    return ""


def replace_h2_section(content: str, title_prefixes: tuple[str, ...], replacement: str) -> str:
    """Replace the first H2 whose title starts with any prefix; insert before 目录 if missing."""
    matches = list(_H2_RE.finditer(content))
    start = end = None
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        if any(title.startswith(prefix) for prefix in title_prefixes):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            break
    block = replacement.strip() + "\n\n"
    if start is None:
        toc = re.search(r"^##\s+目录\s*$", content, re.MULTILINE)
        if toc:
            return content[: toc.start()] + block + content[toc.start() :]
        return content.rstrip() + "\n\n" + block
    return content[:start] + block + content[end:]


def rebuild_toc_from_h2s(content: str) -> str:
    headings: list[str] = []
    in_fence = False
    kept: list[str] = []
    skipping_toc = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            if not skipping_toc:
                kept.append(line)
            continue
        if skipping_toc:
            if not in_fence and re.match(r"^#{1,6}\s+\S", stripped):
                skipping_toc = False
            else:
                continue
        heading = re.match(r"^#{1,6}\s+(.+)$", stripped)
        if heading and heading.group(1).strip() in {"目录", "Table of Contents", "TOC"}:
            skipping_toc = True
            continue
        if (
            heading
            and stripped.startswith("## ")
            and heading.group(1).strip()
            not in {
                "目录",
                "Table of Contents",
                "TOC",
            }
        ):
            headings.append(heading.group(1).strip())
        kept.append(line)
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
    if not headings:
        return body + "\n"
    toc = ["## 目录", ""] + [f"{index}. {title}" for index, title in enumerate(headings[:10], 1)]
    return insert_toc_after_title(body, toc)


def insert_toc_after_title(body: str, toc: list[str]) -> str:
    lines = (body or "").splitlines()
    insert_at = 0
    for index, line in enumerate(lines):
        if line.startswith("# ") and not line.startswith("## "):
            insert_at = index + 1
            while insert_at < len(lines) and not lines[insert_at].strip():
                insert_at += 1
            break
    return "\n".join(lines[:insert_at] + [""] + toc + [""] + lines[insert_at:]).strip() + "\n"


def dedupe_identical_fences(content: str) -> str:
    seen: set[str] = set()

    def _keep(match: re.Match[str]) -> str:
        key = re.sub(r"\s+", " ", match.group(0)).strip().casefold()
        if key in seen:
            return ""
        seen.add(key)
        return match.group(0)

    return _FENCE_RE.sub(_keep, content)


def strip_header_only_cites(content: str, root: Path) -> str:
    def _keep(match: re.Match[str]) -> str:
        return "" if is_header_only_cite(match.group(0), root) else match.group(0)

    return _HEADER_CITE_RE.sub(_keep, content)


def strip_meta_instructions(content: str) -> str:
    kept: list[str] = []
    for line in content.splitlines():
        if _OPERATIONAL_ADVICE_RE.search(line):
            kept.append(line)
            continue
        if _META_IMPERATIVE_RE.search(line) and (
            "package main" in line or "custom-probe" in line or "测试 settings" in line
        ):
            continue
        if _PLANNING_LEAK_RE.search(line):
            continue
        if "安装与启动步骤以仓库入口文档为准" in line:
            continue
        kept.append(line)
    return "\n".join(kept)


def _go_local_db_start_lines(root: Path) -> list[str]:
    lines: list[str] = []
    readme = read_readme_text(root).splitlines()
    index = 0
    while index < len(readme):
        stripped = readme[index].strip()
        if stripped.startswith(("podman run", "docker run")) and any(
            token in stripped for token in ("mysql", "blackbox", "postgres")
        ):
            chunk = [stripped]
            while chunk[-1].endswith("\\") and index + 1 < len(readme):
                index += 1
                nxt = readme[index].rstrip()
                chunk.append(nxt if nxt.startswith((" ", "\t")) else nxt.strip())
            lines.extend(chunk)
        index += 1
    if not lines:
        lines = [
            "podman run --name mysql-db -d -e MYSQL_ROOT_PASSWORD=rootpassword "
            "-e MYSQL_DATABASE=probe_exporter -p 3306:3306 mysql:8.0",
        ]
    return lines


def build_go_install_section(root: Path) -> str:
    port = preferred_source_listen_port(root) or 1900
    compose = cite_readme_line(root, "podman-compose up")
    schema = cite_readme_line(root, "schema.sql")
    build = cite_readme_line(root, "go build -o bin/ccagent")
    run = cite_readme_line(root, "./bin/ccagent")
    health = cite_readme_line(root, "/health")
    schema_cmd = "podman exec mysql-db mysql -uroot -prootpassword probe_exporter < db/schema.sql"
    if (root / "db" / "schema.sql").is_file() is False:
        schema_cmd = "mysql < db/schema.sql"
    return "\n".join(
        [
            "## 安装步骤",
            "",
            "容器路径与本地路径二选一。",
            "",
            "### 路径 A：容器编排",
            "",
            f"1. 启动编排服务。 {compose}",
            "",
            "```bash",
            "podman-compose up -d",
            "```",
            "",
            f"2. 导入一次数据库结构。 {schema}",
            "",
            "```bash",
            "# 容器路径：导入一次结构",
            schema_cmd,
            "```",
            "",
            f"3. 用源码监听端口检查健康状态。 {health}",
            "",
            "```bash",
            f"curl http://localhost:{port}/health",
            "```",
            "",
            "### 路径 B：本地编译",
            "",
            f"1. 先按 README 启动本地 MySQL（以及 blackbox-exporter）。 {cite_readme_line(root, 'podman run')}",
            "",
            "```bash",
            *_go_local_db_start_lines(root),
            "```",
            "",
            f"2. 再导入结构。 {cite_readme_line(root, 'podman exec mysql-db', last=True) or schema}",
            "",
            "```bash",
            "# 本地路径：导入结构",
            schema_cmd,
            "```",
            "",
            f"3. 编译主 REST/Web 服务。 {build}",
            "",
            "```bash",
            "go build -o bin/ccagent ./cmd/ccagent",
            "```",
            "",
            f"4. 启动本地进程并检查健康状态。 {run} {health}",
            "",
            "```bash",
            "./bin/ccagent",
            f"curl http://localhost:{port}/health",
            "```",
            "",
        ]
    )


def build_fastapi_install_section(root: Path) -> str:
    env = cite_readme_line(root, "APP_ENV") or cite_readme_line(root, "SECRET_KEY")
    poetry = cite_readme_line(root, "poetry install")
    alembic = cite_readme_line(root, "alembic upgrade")
    uvicorn = cite_readme_line(root, "uvicorn app.main:app")
    pg = cite_readme_line(root, "docker run --name pgdb") or cite_readme_line(root, "POSTGRES")
    compose_db = cite_readme_line(root, "docker-compose up -d db") or cite_readme_line(
        root, "docker-compose up"
    )
    compose_app = cite_readme_line(root, "docker-compose up -d app")
    return "\n".join(
        [
            "## 安装步骤",
            "",
            "容器路径与本地路径二选一。",
            "",
            "### 路径 A：本地开发",
            "",
            f"1. 创建 `.env`（alembic `env.py` 会加载应用设置，必须先有 APP_ENV、DATABASE_URL、SECRET_KEY）。 {env}",
            "",
            "```bash",
            "touch .env",
            "echo APP_ENV=dev >> .env",
            "echo DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/rwdb >> .env",
            "echo SECRET_KEY=change-me >> .env",
            "```",
            "",
            f"2. 先启动 PostgreSQL。 {pg}",
            "",
            "```bash",
            "docker run --name pgdb --rm -e POSTGRES_USER=postgres "
            "-e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=rwdb -p 5432:5432 postgres",
            "```",
            "",
            f"3. 安装依赖。 {poetry}",
            "",
            "```bash",
            "poetry install",
            "```",
            "",
            f"4. 迁移数据库。 {alembic}",
            "",
            "```bash",
            "poetry run alembic upgrade head",
            "```",
            "",
            f"5. 启动应用。 {uvicorn}",
            "",
            "```bash",
            "poetry run uvicorn app.main:app --reload",
            "```",
            "",
            "### 路径 B：Compose",
            "",
            f"1. 先创建 `.env`（compose 通过 env_file 注入 APP_ENV、DATABASE_URL、SECRET_KEY）。 {env}",
            "",
            "```bash",
            "touch .env",
            "echo APP_ENV=dev >> .env",
            "echo DATABASE_URL=postgresql://postgres:postgres@db:5432/rwdb >> .env",
            "echo SECRET_KEY=change-me >> .env",
            "```",
            "",
            f"2. 先启动数据库服务，再启动应用服务。 {compose_db} {compose_app}",
            "",
            "```bash",
            "docker-compose up -d db",
            "docker-compose up -d app",
            "```",
            "",
        ]
    )


def build_install_section(root: Path) -> str:
    if (root / "cmd" / "ccagent").is_dir():
        return build_go_install_section(root)
    if (root / "app" / "main.py").is_file():
        return build_fastapi_install_section(root)
    return ""


def build_go_role_section(root: Path) -> str:
    ccagent = (
        cite_first_match(root, "controller.go", r"return server\.ListenAndServe\(\)")
        or cite_first_match(root, "controller.go", r"ListenAndServe")
        or cite_first_match(
            root, "cmd/ccagent/main.go", r"NewController|ListenAndServe|http\.Server"
        )
        or cite_first_match(root, "cmd/ccagent/main.go", r"func\s+main\b")
    )
    probe = (
        cite_first_match(root, "internal/agent/grpc_transport.go", r"grpc\.DialContext")
        or cite_first_match(root, "cmd/probe-agent/main.go", r"grpcTransport\.Connect|DialContext")
        or cite_first_match(root, "cmd/probe-agent/main.go", r"func\s+main\b")
    )
    control = ""
    for rel in ("cmd/ccprobe-control/serve.go", "cmd/ccprobe-control/main.go"):
        control = cite_first_match(
            root, rel, r"func runGRPCServe|ListenAndServeGRPC|transport grpc|-serve|-transport"
        )
        if control:
            break
    if not (ccagent or probe or control):
        return ""
    return (
        "## 进程角色\n\n"
        f"ccagent 是主 REST/Web 服务，监听 HTTP 并挂载业务路由。 {ccagent}\n\n"
        f"probe-agent 是隧道客户端，向控制面拨号并维持心跳。 {probe}\n\n"
        f"ccprobe-control 是 gRPC 控制面服务（`-serve -transport grpc`），负责 TunnelHub。 {control}\n"
    )


def extract_alembic_tables(text: str) -> list[dict[str, object]]:
    tables: list[dict[str, object]] = []
    starts = list(re.finditer(r'op\.create_table\(\s*"(\w+)"', text or ""))
    by_name: dict[str, dict[str, object]] = {}
    for index, match in enumerate(starts):
        name = match.group(1)
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text or "")
        body = (text or "")[match.end() : end]
        attrs: list[str] = []
        types: list[str] = []
        pks: list[str] = []
        for col in re.finditer(
            r'sa\.Column\(\s*"(\w+)"\s*,\s*sa\.(\w+)',
            body,
        ):
            attrs.append(col.group(1))
            types.append(col.group(2))
            window_end = min(len(body), col.end() + 80)
            if "primary_key=True" in body[col.start() : window_end]:
                pks.append(col.group(1))
        for extra in re.findall(r"sa\.PrimaryKeyConstraint\(\s*([^)]+)\)", body):
            pks.extend(re.findall(r'"(\w+)"', extra))
        if "*timestamps()" in body or "timestamps()" in body:
            for stamp, stamp_type in (("created_at", "TIMESTAMP"), ("updated_at", "TIMESTAMP")):
                if stamp not in attrs:
                    attrs.append(stamp)
                    types.append(stamp_type)
        fks = re.findall(
            r'sa\.Column\(\s*"(\w+)"[^)]*sa\.ForeignKey\(\s*"(\w+)\.(\w+)"',
            body,
        )
        if not fks:
            fks = [
                ("", dest, col)
                for dest, col in re.findall(r'sa\.ForeignKey\(\s*"(\w+)\.(\w+)"', body)
            ]
        relationships = []
        for col_name, dest, _dest_col in fks:
            label = col_name or _dest_col
            relationships.append(f"belongs_to:{dest}:{label}" if label else f"belongs_to:{dest}")
        table = {
            "name": name,
            "type": "migration_table",
            "attributes": attrs,
            "attribute_types": types,
            "primary_key": pks[0] if len(pks) == 1 else "",
            "primary_keys": list(dict.fromkeys(pks)),
            "relationships": relationships,
            "file_path": "",
            "table_name": name,
        }
        tables.append(table)
        by_name[name] = table
    for match in re.finditer(
        r'op\.create_primary_key\(\s*"[^"]+"\s*,\s*"(\w+)"\s*,\s*\[([^\]]+)\]',
        text or "",
    ):
        current = by_name.get(match.group(1))
        if current is None:
            continue
        extra = re.findall(r'"(\w+)"', match.group(2))
        raw_pks = current.get("primary_keys")
        pks = [str(item) for item in raw_pks] if isinstance(raw_pks, list) else []
        for col in extra:
            if col not in pks:
                pks.append(col)
        current["primary_keys"] = pks
        current["primary_key"] = pks[0] if len(pks) == 1 else ""
    return tables


def load_alembic_migration_models(root: Path) -> list[dict[str, object]]:
    versions = root / "app" / "db" / "migrations" / "versions"
    if not versions.is_dir():
        return []
    models: list[dict[str, object]] = []
    for path in sorted(versions.glob("*.py")):
        tables = extract_alembic_tables(path.read_text(encoding="utf-8", errors="ignore"))
        rel = path.relative_to(root).as_posix()
        for table in tables:
            table["file_path"] = rel
            models.append(table)
    return models


def go_struct_end_line(lines: list[str], start: int) -> int:
    depth = 0
    for index in range(start - 1, len(lines)):
        depth += lines[index].count("{") - lines[index].count("}")
        if depth <= 0 and index >= start - 1:
            return index + 1
    return min(len(lines), start)


def go_struct_cite(root: Path, name: str) -> str:
    models = root / "internal" / "models"
    if not models.is_dir():
        return ""
    pattern = re.compile(rf"^type\s+{re.escape(name)}\s+struct\s*\{{")
    for path in sorted(models.rglob("*.go")):
        if path.name.endswith("_test.go"):
            continue
        rel = path.relative_to(root).as_posix()
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for index, line in enumerate(lines, 1):
            if pattern.match(line):
                return f"<cite>{rel}:{index}-{go_struct_end_line(lines, index)}</cite>"
    return ""


def all_go_model_struct_cites(root: Path) -> list[str]:
    models = root / "internal" / "models"
    if not models.is_dir():
        return []
    pattern = re.compile(r"^type\s+([A-Z][A-Za-z0-9_]*)\s+struct\s*\{")
    cites: list[str] = []
    seen: set[str] = set()
    for path in sorted(models.rglob("*.go")):
        if path.name.endswith("_test.go"):
            continue
        rel = path.relative_to(root).as_posix()
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for index, line in enumerate(lines, 1):
            match = pattern.match(line)
            if not match or match.group(1) in seen:
                continue
            seen.add(match.group(1))
            cites.append(
                f"{match.group(1)} <cite>{rel}:{index}-{go_struct_end_line(lines, index)}</cite>"
            )
    return cites


def build_data_model_cite_block(root: Path) -> str:
    if (root / "internal" / "models").is_dir():
        named = all_go_model_struct_cites(root)
        required = [go_struct_cite(root, name) for name in _REQUIRED_GO_STRUCTS]
        required = [item for item in required if item]
        if not named and not required:
            return ""
        migrations = ""
        mig_dir = root / "db" / "migrations"
        if mig_dir.is_dir():
            sqls = sorted(path for path in mig_dir.glob("*.sql"))
            if sqls:
                rel = sqls[0].relative_to(root).as_posix()
                migrations = f" `db/migrations` 含 {len(sqls)} 个 SQL 迁移，例如 {cite_first_match(root, rel, r'CREATE TABLE|create table') or f'<cite>{rel}:1-1</cite>'}。"
        items = named or required
        listing = "\n".join(f"- {item}" for item in items)
        return (
            "## 实体定义\n\n"
            "GORM 结构体定义在 internal/models：\n\n"
            f"{listing}\n\n"
            f"表结构见 db/schema.sql。{migrations}\n"
        )
    models = load_alembic_migration_models(root)
    if not models:
        return ""
    rel = str(models[0].get("file_path") or "app/db/migrations")
    names = "、".join(str(item.get("name")) for item in models)
    domain = ""
    domain_dir = root / "app" / "models" / "domain"
    if domain_dir.is_dir():
        domain = cite_existing_meaningful(root, "app/models/domain")
    migration_cite = cite_first_match(root, rel, r'op\.create_table\(\s*"users"') or (
        f"<cite>{rel}:1-1</cite>" if (root / rel).is_file() else ""
    )
    return (
        "## 持久化表\n\n"
        f"持久化表以 `{rel}` 为准，当前迁移定义 {names}，外键按迁移列声明。"
        f" 不存在 profiles 表。 {migration_cite} "
        f"app/models/domain 是 Pydantic 领域模型，不是 ORM 实体。 {domain}\n"
    )


def build_security_cite_block(root: Path) -> str:
    cites: list[str] = []
    hints: tuple[str, ...] = (
        _GO_SECURITY_HINTS if (root / "cmd" / "ccagent").is_dir() else _FASTAPI_SECURITY_HINTS
    )
    for rel in hints:
        path = root / rel
        if path.exists():
            cite = cite_existing_meaningful(root, rel)
            if cite:
                cites.append(cite)
    if not cites:
        return ""
    if (root / "cmd" / "ccagent").is_dir():
        token = cite_first_match(
            root, "apiauth.go", r"EnvAPIToken|PROBE_API_TOKEN|apiAuthMiddleware"
        ) or next((item for item in cites if "apiauth.go" in item), "")
        secrets = next((item for item in cites if "secrets" in item), "")
        audit = next((item for item in cites if "audit" in item), "")
        netguard = next((item for item in cites if "netguard" in item), "")
        return (
            "## 安全实现\n\n"
            f"请求鉴权走 `apiauth` 中间件，校验环境变量 `PROBE_API_TOKEN`"
            f"（`X-Probe-Api-Token` 或 Bearer）。 {token}\n\n"
            f"密钥以 AES/Vault 存储，不把明文写进配置。 {secrets}\n\n"
            f"审计事件写入 internal/audit，出站目标由 netguard 约束，敏感字段在日志中脱敏。"
            f" {audit} {netguard}\n"
        )
    return (
        "## 安全实现\n\n"
        f"路由依赖从 Authorization 头读取 JWT（前缀见 settings.jwt_token_prefix）。 {cites[0]}\n\n"
        f"口令哈希与令牌校验在 app/services/security.py 与 authentication 依赖中完成。"
        f" {' '.join(cites[1:])}\n"
    )


def build_feature_prose(root: Path) -> str:
    if (root / "app" / "api" / "routes").is_dir():
        routes = sorted(
            path.stem
            for path in (root / "app" / "api" / "routes").glob("*.py")
            if path.name != "__init__.py"
        )
        if routes:
            return (
                "核心功能由路由模块实现，包括 "
                + "、".join(routes)
                + " 等请求入口，再进入服务与仓储完成读写。"
            )
    if (root / "internal" / "services").is_dir():
        return "核心功能由 ccagent 对外提供 REST/Web 接口，并由 services 与 repository 完成探针、策略和结果处理。"
    return ""


def is_header_only_cite(raw: str, repo_root: Path | None) -> bool:
    match = _HEADER_CITE_RE.search(raw)
    if not match:
        return False
    rel = match.group(1).replace("\\", "/")
    end = int(match.group(2))
    suffix = Path(rel).suffix.lower()
    if suffix in {".md", ".rst", ".txt", ".yml", ".yaml"}:
        return True
    window = ""
    path = (repo_root / rel) if repo_root is not None else None
    if path is not None and path.is_file():
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        window = "\n".join(lines[:end])
    if suffix == ".sql":
        return not re.search(r"CREATE\s+TABLE", window, re.I)
    if repo_root is None or path is None or not path.is_file():
        return False
    if re.search(
        r"^(type\s+\w+\s+struct|func\s+main\b|func\s+\w+|def\s+\w+|class\s+\w+|"
        r"podman-|docker-|poetry |alembic |uvicorn )",
        window,
        re.M,
    ):
        return False
    return not re.search(r"\S", window)


def page_has_repeated_fences(content: str) -> bool:
    seen: dict[str, int] = {}
    for match in _FENCE_RE.finditer(content or ""):
        key = re.sub(r"\s+", " ", match.group(0)).strip().casefold()
        if len(key) < 40:
            continue
        seen[key] = seen.get(key, 0) + 1
        if seen[key] >= 2:
            return True
    return False


def page_has_meta_instruction(content: str) -> bool:
    for line in (content or "").splitlines():
        if _OPERATIONAL_ADVICE_RE.search(line):
            continue
        if _PLANNING_LEAK_RE.search(line):
            return True
        if _META_IMPERATIVE_RE.search(line) and ("package main" in line or "custom-probe" in line):
            return True
    return False


def strip_dangling_colon_leads(content: str) -> str:
    lines = (content or "").splitlines()
    kept: list[str] = []
    for index, line in enumerate(lines):
        if re.search(r"[：:]\s*$", line):
            nxt = next((item for item in lines[index + 1 :] if item.strip()), "")
            continues = bool(
                nxt.startswith(("-", "*", "```", "    ", "\t")) or re.match(r"^\d+\.", nxt)
            )
            if not nxt or nxt.startswith("#") or not continues:
                kept.append(re.sub(r"[：:]\s*$", "。", line))
                continue
        kept.append(line)
    return "\n".join(kept)


def strip_empty_sections_and_footnotes(content: str) -> str:
    text = re.sub(r"^\[\^[^\]]+\]:\s*$", "", content or "", flags=re.M)
    parts = re.split(r"(?=^##\s+)", text, flags=re.M)
    kept: list[str] = []
    for part in parts:
        if part.startswith("## "):
            title, _, body = part.partition("\n")
            if title.strip() in {"## 目录", "## 架构图"}:
                kept.append(part)
                continue
            if not re.search(r"\S", body or "") and title.strip() not in {"## 目录"}:
                continue
        kept.append(part)
    return "".join(kept)


ARCHITECTURE_ROLE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"边缘 Agent\s*`?cmd/ccagent", "主 REST/Web 服务 `cmd/ccagent"),
    (r"边缘 Agent\s*`?ccagent`?", "主 REST/Web 服务 ccagent"),
    (r"边缘 Agent ccagent", "主 REST/Web 服务 ccagent"),
    (r"`ccagent`\s*作为隧道客户端", "`ccagent` 作为主 REST/Web 服务"),
    (r"ccagent 作为隧道客户端", "ccagent 作为主 REST/Web 服务"),
    (r"`ccprobe-control`\s*作为主 REST/Web", "`ccprobe-control` 作为 gRPC 控制面"),
    (r"ccprobe-control 作为主 REST/Web", "ccprobe-control 作为 gRPC 控制面"),
    (r"ccagent / agent：客户端代理", "ccagent：主 REST/Web 服务；probe-agent：隧道客户端"),
    (r"single Go backend process", "four Go binaries under cmd/"),
    (r"单一 Go 后端进程", "cmd/ 下多个独立二进制"),
    (r"未提供显式迁移脚本", "db/migrations 提供 SQL 迁移"),
    (r"核心表包括 `users`、`profiles`", "核心表包括 `users`"),
    (r"、`profiles`", ""),
    (r"不存在 ORM 映射实体", "Pydantic 领域模型不是 ORM"),
    (
        r"`?internal/control`?\s*依赖\s*`?internal/services`?\s*与\s*`?internal/repository`?",
        "`internal/services` 依赖 `internal/control`；`internal/control` 不依赖 services/repository",
    ),
    (
        r"`?ccprobe-control`?[^。\n]{0,80}via services/repository/exporter",
        "ccprobe-control 的 import 图不含 services/repository/exporter",
    ),
    (r"via services/repository/exporter", "不经过 services/repository/exporter"),
    (
        r"`cmd/ccagent`（探针 Agent，作为隧道客户端连接到控制面）",
        "`cmd/ccagent`（主 REST/Web 服务）",
    ),
    (r"cmd/ccagent`?（探针 Agent，作为隧道客户端[^）]*）", "`cmd/ccagent`（主 REST/Web 服务）"),
    (r"\*\*ccagent 隧道客户端\*\*", "**ccagent 主 REST/Web 服务**"),
    (r"ccagent 隧道客户端", "ccagent 主 REST/Web 服务"),
    (
        r"`?ccagent`?[^。\n]{0,40}通过 `-agent-url`/`-agent-token` 与 `ccprobe-control` 建立反向控制链路",
        "ccagent 作为主 REST/Web 服务对外提供 HTTP，不反连控制面",
    ),
    (
        r"作为外部进程被拉起以返回 JSON 探针结果",
        "由 `internal/probe` 经 HTTP 调用并解析 JSON 结果",
    ),
    (r"由 `internal/probe` 拉起并解析 JSON", "由 `internal/probe` 经 HTTP 调用并解析 JSON"),
    (r"internal/probe 拉起", "internal/probe 经 HTTP 调用"),
    (r"主进程负责隧道客户端", "主进程负责 REST/Web 服务"),
    (r"负责隧道客户端与运行环境适配", "负责 REST/Web 服务与运行环境适配"),
    (r"作为隧道客户端入口", "作为主 REST/Web 入口"),
    (r"带隧道能力的主 REST/Web 服务", "gRPC 控制面"),
    (r"作为隧道客户端连向", "作为主 REST/Web 服务对外提供"),
    (r"`cmd/ccagent` 是与采集端配套的客户端入口", "`cmd/ccagent` 是主 REST/Web 入口"),
    (r"是与采集端配套的客户端入口", "是主 REST/Web 入口"),
    (r"\*\*客户端入口 `cmd/ccagent`\*\*", "**主 REST/Web 入口 `cmd/ccagent`**"),
    (r"客户端入口 `cmd/ccagent`", "主 REST/Web 入口 `cmd/ccagent`"),
    (
        r"隧道客户端\s*\(`?probe-agent`?\)\s*不在仓库范围内",
        "隧道客户端 `probe-agent` 位于 `cmd/probe-agent`",
    ),
    (r"`?probe-agent`?[^。\n]{0,24}不在仓库范围内", "`probe-agent` 位于 `cmd/probe-agent`"),
    (r"不在仓库范围内，由 `ccprobe-control`", "位于 `cmd/probe-agent`，由 `ccprobe-control`"),
)


def rewrite_architecture_role_claims(content: str) -> str:
    text = content or ""
    for pattern, repl in ARCHITECTURE_ROLE_REPLACEMENTS:
        text = re.sub(pattern, repl, text)
    return text


FRONTEND_CONSUMER_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (
        r"ccprobe-control 模块面向前端应用的 HTTP API 入口",
        "ccagent 面向前端应用的 HTTP API 入口",
    ),
    (
        r"围绕 `ccprobe-control` 的 Go handler 与请求/响应结构展开 API 参考说明",
        "围绕 `web/` 与 `static/` 对 ccagent `/probe`、`/tag`、`/api/v1` 的调用展开 API 参考说明",
    ),
    (
        r"前端应用通过 HTTP 调用 ccprobe-control 暴露的查询与控制端点（`/force-resync`、`/healthz`、`/publish`、`/status`）",
        "前端应用通过 `web/`、`static/` 调用 ccagent 的 `/probe`、`/tag`、`/api/v1` 路由",
    ),
    (
        r"整体链路是“前端 → 控制面 handler → TunnelHub/服务 → 响应”",
        "整体链路是“前端 fetch → ccagent `/probe` `/tag` `/api/v1` → 响应”",
    ),
    (
        r"前端应用通过一组轻量的查询与控制端点完成状态查看、强制再同步与探测任务发布",
        "前端应用通过 `/probe`、`/tag`、`/api/v1` 完成状态查看与标签查询",
    ),
)


def rewrite_frontend_consumer_claims(
    content: str,
    root: Path,
    *,
    page_id: str = "",
    title: str = "",
) -> str:
    blob = f"{page_id} {title} {content[:80]}"
    if not any(token in blob for token in ("前端", "frontend", "web")):
        return content or ""
    text = content or ""
    for pattern, repl in FRONTEND_CONSUMER_REPLACEMENTS:
        text = re.sub(pattern, repl, text)
    from repo_wiki.generator.mermaid_planner import frontend_fetch_paths

    fetches = frontend_fetch_paths(root)
    if fetches and "ccprobe-control 暴露的查询与控制端点" in text:
        listed = "、".join(f"`{path}`" for path in fetches[:6])
        text = text.replace(
            "ccprobe-control 暴露的查询与控制端点",
            f"ccagent 的 {listed} 路由",
        )
    return text


def strip_reader_unresolved_markers(content: str) -> str:
    text = _UNRESOLVED_API_RE.sub("", content or "")
    text = re.sub(r"^## API 证据状态\n\n<!-- repo-wiki:unresolved[^>]+-->\n?", "", text, flags=re.M)
    text = re.sub(r"<!-- repo-wiki:unresolved[^>]+-->\s*", "", text)
    text = re.sub(
        r"：未解析到证据支持的 API 端点；现有结构内容均不得视为已验证接口事实。", "", text
    )
    text = re.sub(
        r"：未在证据上下文中解析到接口端点；本节仅为结构占位，不得视为已验证 API 清单。",
        "本组接口见 API参考。",
        text,
    )
    text = re.sub(
        r"：缺少端点、认证、幂等和错误处理证据；本节不声明 Bearer、网关、重试或 CRUD 语义。",
        "认证与错误处理见各端点源码。",
        text,
    )
    text = re.sub(
        r"：缺少请求体、响应体或 OpenAPI/源码字段证据；本节不合成通用 request/response/error schema。",
        "字段摘要见 API参考。",
        text,
    )
    text = re.sub(
        r"：端点证据未提供请求体、响应体或错误码字段；未生成通用 schema。",
        "字段摘要见 API参考。",
        text,
    )
    text = re.sub(r"：缺少可验证调用链证据，不生成占位流程图。\n?", "", text)
    text = re.sub(r"（缺少认证证据，不能视为 Bearer Token 事实）", "", text)
    text = re.sub(r"（证据中未声明认证方式）", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def strip_empty_numbered_steps(content: str) -> str:
    lines = (content or "").splitlines()
    kept: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r"^(\d+)\.\s+\S", line)
        if match:
            body: list[str] = []
            look = index + 1
            while (
                look < len(lines)
                and not re.match(r"^(\d+)\.\s+", lines[look])
                and not lines[look].startswith("## ")
            ):
                if lines[look].strip():
                    body.append(lines[look])
                look += 1
            meaningful = [
                item for item in body if not re.fullmatch(r"<cite>[^<]+</cite>", item.strip())
            ]
            if not meaningful and not re.search(r"`[^`]+`|```", line):
                index = look
                continue
        kept.append(line)
        index += 1
    return "\n".join(kept)


def strip_placeholder_ops_fences(content: str) -> str:
    from repo_wiki.generator.compose_evidence import is_placeholder_ops_diagram

    def _drop(match: re.Match[str]) -> str:
        block = match.group(0)
        return "" if is_placeholder_ops_diagram(block) else block

    return re.sub(r"```mermaid\s*.*?```", _drop, content or "", flags=re.I | re.S)


def expand_truncated_build_commands(content: str, root: Path) -> str:
    text = content or ""
    names: list[str] = []
    ci = root / ".github" / "workflows" / "ci.yml"
    if ci.is_file():
        names = re.findall(
            r"go build -o (bin/[A-Za-z0-9_-]+)", ci.read_text(encoding="utf-8", errors="ignore")
        )
    if not names:
        for cmd in ("ccagent", "ccprobe-control", "probe-agent"):
            if (root / "cmd" / cmd).is_dir():
                names.append(f"bin/{cmd}")
    if not names:
        names = ["bin/ccagent", "bin/ccprobe-control", "bin/probe-agent"]
    listing = "、".join(f"`{name}`" for name in names[:6])
    commands = " && ".join(
        f"go build -o {name} ./cmd/{name.rsplit('/', 1)[-1]}" for name in names[:6]
    )
    if "bin/probe-..." in text:
        text = text.replace("bin/probe-...", listing)
    return re.sub(r"go build -o bin/\.\.\.", commands, text)


def rewrite_checkout_directory_name(content: str, root: Path) -> str:
    from repo_wiki.generator.compose_evidence import derive_product_name

    product = derive_product_name(root)
    if not product:
        return content or ""
    text = content or ""
    leaks = {root.name, f"{product}-eval"}
    for leak in leaks:
        if leak and leak != product:
            text = re.sub(rf"\b{re.escape(leak)}\b", product, text)
    return text


def build_verify_section(root: Path) -> str:
    if (root / "cmd" / "ccagent").is_dir():
        from repo_wiki.verifier.handbook import preferred_source_listen_port

        port = preferred_source_listen_port(root) or 1900
        health = cite_readme_line(root, "/health")
        return (
            "## 启动与验证\n\n"
            f"1. 按安装步骤完成编排或本地编译。\n\n"
            f"2. 用源码健康检查确认进程存活：`curl http://localhost:{port}/health` {health}\n"
        )
    if (root / "app" / "main.py").is_file():
        return (
            "## 启动与验证\n\n"
            "1. 按安装步骤准备 `.env` 并完成迁移。\n\n"
            "2. 用真实路由确认进程存活：`curl http://127.0.0.1:8000/api/tags`\n"
        )
    return ""


def build_core_service_section(root: Path, *, page_id: str = "", title: str = "") -> str:
    blob = f"{page_id} {title}".lower()
    if "ccprobe-control" in blob or title.strip() in {"Ccprobe Control", "ccprobe-control"}:
        serve = cite_existing_meaningful(root, "cmd/ccprobe-control/serve.go")
        main = cite_existing_meaningful(root, "cmd/ccprobe-control/main.go")
        hub = cite_existing_meaningful(root, "internal/control")
        return (
            "## 服务概述\n\n"
            f"`ccprobe-control` 是 gRPC 控制面，通过 `-serve -transport grpc` 启动 TunnelHub，"
            f"不把探测执行委托给 `cmd/custom-probe` 子进程。 {serve} {main}\n\n"
            f"会话与心跳由 `internal/control` 维护。 {hub}\n"
        )
    if "probe-agent" in blob or title.strip() in {"Probe Agent", "probe-agent"}:
        agent = cite_existing_meaningful(root, "cmd/probe-agent/main.go")
        transport = cite_existing_meaningful(root, "internal/agent")
        return (
            "## 服务概述\n\n"
            f"`probe-agent` 是隧道客户端，从 `cmd/probe-agent` 启动并向控制面拨号。"
            f" 本页不描述 `cmd/custom-probe`。 {agent}\n\n"
            f"传输与心跳实现见 `internal/agent`。 {transport}\n"
        )
    return ""


def apply_deterministic_rewrites(
    content: str,
    root: Path,
    *,
    title: str = "",
    category: str = "",
    page_id: str = "",
) -> str:
    """Replay structural compose rewrites without LLM or fence-wide substitution."""
    text = content or ""
    text = sanitize_leftover_handbook_mermaid(text)
    text = rewrite_token_const_cite(text, root)
    text = rewrite_checkout_directory_name(text, root)
    text = rewrite_route_methods_from_table(text, root)
    text = strip_unknown_go_packages(text, root)
    text = strip_meta_instructions(text)
    text = strip_header_only_cites(text, root)
    text = strip_reader_unresolved_markers(text)
    text = strip_placeholder_ops_fences(text)
    text = expand_truncated_build_commands(text, root)
    text = rewrite_architecture_role_claims(text)
    text = rewrite_frontend_consumer_claims(text, root, page_id=page_id, title=title)
    try:
        from repo_wiki.generator.compose_evidence import (
            load_repo_import_edges,
            rewrite_false_import_claims,
        )

        text = rewrite_false_import_claims(text, load_repo_import_edges(root))
    except Exception:
        pass
    text = re.sub(r"^.*安全实现见.*$", "", text, flags=re.M)
    text = re.sub(r"<cite>\s*[^<]*_test\.go:[^<]*</cite>", "", text, flags=re.I)
    install_like = any(token in (title or "") for token in ("安装", "快速开始", "环境配置"))
    if is_install_owner_page(page_id=page_id, title=title) or (
        not page_id
        and (title in {"安装与配置", "安装指南"} or "## 安装步骤" in text)
        and not any(token in title for token in ("快速开始", "环境配置"))
    ):
        section = build_install_section(root)
        if section:
            text = replace_h2_section(text, ("安装步骤",), section)
    elif install_like or "## 安装步骤" in text:
        text = replace_h2_section(
            text,
            ("安装步骤",),
            "## 安装步骤\n\n完整步骤见安装与配置，本页不重复命令。\n",
        )
    arch_like = "架构" in (category or "") or "架构" in (title or "")
    if arch_like and is_architecture_owner_page(page_id=page_id, title=title):
        role = build_go_role_section(root)
        if role:
            text = replace_h2_section(text, ("进程角色",), role)
        text = strip_meta_instructions(text)
    elif arch_like:
        text = replace_h2_section(
            text,
            ("进程角色",),
            "## 角色说明\n\n进程角色见整体架构概览。\n",
        )
    if "数据模型" in (title or "") or "data" in (category or "").lower():
        block = build_data_model_cite_block(root)
        if block and "ProbeEndpoint" not in text and "fdf8821871d7" not in text:
            text = replace_h2_section(text, ("实体定义", "持久化表", "数据模型"), block)
    if is_security_owner_page(page_id=page_id, title=title) or (
        not page_id and title in {"安全合规", "安全合规概览"}
    ):
        block = build_security_cite_block(root)
        if block:
            text = replace_h2_section(text, ("安全实现",), block)
    jwt_owner = title in {"认证授权API", "认证授权"} or page_id in {
        "authentication-authorization-api",
    }
    if not jwt_owner and "JWTService" in text:
        text = re.sub(
            r"```mermaid\s*sequenceDiagram[^`]*JWTService[^`]*```",
            "",
            text,
            flags=re.I | re.S,
        )
    if is_auth_identity_page(page_id=page_id, title=title):
        token = cite_first_match(
            root, "apiauth.go", r"EnvAPIToken|PROBE_API_TOKEN|apiAuthMiddleware"
        )
        if token and "PROBE_API_TOKEN" not in text:
            text = replace_h2_section(
                text,
                ("身份认证", "认证实现", "核心组件"),
                "## 认证实现\n\n"
                f"管理接口鉴权读取环境变量 `PROBE_API_TOKEN`，"
                f"请求头为 `X-Probe-Api-Token` 或 Bearer。 {token}\n",
            )
    core = build_core_service_section(root, page_id=page_id, title=title)
    if core:
        text = replace_h2_section(text, ("服务概述",), core)
    if is_install_owner_page(page_id=page_id, title=title) or (
        not page_id and title in {"安装与配置", "安装指南"}
    ):
        verify = build_verify_section(root)
        if verify:
            text = replace_h2_section(text, ("启动与验证",), verify)
    if not is_api_catalog_owner_page(page_id=page_id, title=title) and (
        "API" in title or "api" in (page_id or "").lower() or "API" in (category or "")
    ):
        if "按资源分组的接口" in text:
            text = replace_h2_section(text, ("API 分组",), "## API 分组\n\n本组接口见 API参考。\n")
    if (
        not is_data_model_owner_page(page_id=page_id, title=title)
        and "followers_to_followings" in text
    ):
        text = re.sub(r"```mermaid\s*erDiagram.*?```", "", text, flags=re.I | re.S)
    text = strip_invented_join_id_pk(text)
    text = strip_empty_numbered_steps(text)
    text = strip_dangling_colon_leads(text)
    text = strip_empty_sections_and_footnotes(text)
    text = strip_reader_unresolved_markers(text)
    text = dedupe_identical_fences(text)
    return rebuild_toc_from_h2s(text)
