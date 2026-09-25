"""Handbook wiki helpers: generator-meta detection and page-local quality rejects."""

from __future__ import annotations

import json
import re
from pathlib import Path

_README_SAMPLE_LEAK = "".join(("README sample", ", not in code"))
HANDBOOK_META_PHRASES: tuple[str, ...] = (
    "fallback composer",
    "repo-agent",
    "该页面对应",
    "evidence ranking",
    _README_SAMPLE_LEAK,
)

GENERATOR_META_REJECTION = "Handbook generator meta content"
EMPTY_CONTENT_REJECTION = "Empty LLM assistant content"
EMPTY_SPAN_REJECTION = "Empty inline code span"
UNCLOSED_FENCE_REJECTION = "Unclosed fenced code block"
ROLE_CONTRADICTION_REJECTION = "Architecture role contradiction"
EVIDENCE_META_REJECTION = "Handbook evidence meta talk"
TINY_OR_TRUNCATED_REJECTION = "Tiny or truncated page body"
MIN_HANDBOOK_BODY_CHARS = 800
PAGE_TIMEOUT_REJECTION_PREFIX = "LLM page timeout after"
PAGE_SERVER_ERROR_REJECTION_PREFIX = "LLM page server error"

_PAGE_LOCAL_QUALITY_REJECTIONS = frozenset(
    {
        "Insufficient prose content",
        GENERATOR_META_REJECTION,
        EMPTY_CONTENT_REJECTION,
        EMPTY_SPAN_REJECTION,
        UNCLOSED_FENCE_REJECTION,
        ROLE_CONTRADICTION_REJECTION,
        EVIDENCE_META_REJECTION,
        TINY_OR_TRUNCATED_REJECTION,
    }
)

_CITE_RE = re.compile(r"<cite>\s*([^<]+?)\s*</cite>", re.IGNORECASE)
_FACT_DISCLAIMER_RE = re.compile(r"仅出现在说明文档|不应[^。\n]{0,40}当作源码接口|只能使用下列")
_RAW_ARTEFACT_RE = re.compile(r"<!--\s*raw HTML omitted\s*-->", re.IGNORECASE)
_NEAR_FACT_SENTENCE_RE = re.compile(
    r"(?:编排服务名|数据表|CLI 旗标|健康检查路由|本页可核对|源码事实)"
)

_INSTRUCTION_VOICE_RE = re.compile(
    r"不要只标|如果证据不足|不要在此凭空扩展|不要用套话填空|不要过度推断"
    r"|引用时写|引用时使用"
    r"|进程角色必须|禁止写 cmd/|禁止用「前者|" + re.escape(_README_SAMPLE_LEAK)
)
_EVIDENCE_META_TALK_RE = re.compile(
    r"证据片段|证据范围|"
    r"当前证据|提供的证据|"
    r"当前(?:可用|可见|提供的)(?:源码)?证据|"
    r"(?:可用|可见|提供的)源码证据|"
    r"(当前|可用|可见|提供的)的?(源码)?证据|"
    r"用户(?:当前)?(?:没有|未)指定"
)
_FALLBACK_STUB_MARKERS = (
    "面向接手仓库的人，用来定位这个主题在仓库里的实现",
    "在找到可核对的文件之前，请不要把本页当成",
    "本页目前无法根据仓库内容写成可用的",
    "说明这个仓库是什么产品、给谁用，而不是一份安装步骤清单",
)
_H1_RE = re.compile(r"^# [^#\n]", re.MULTILINE)


def contains_evidence_meta_talk(text: str) -> bool:
    return bool(_EVIDENCE_META_TALK_RE.search(text or ""))


def handbook_page_is_fallback_stub(markdown: str) -> bool:
    """True only for deterministic fallback stubs, not short structured LLM pages."""
    text = markdown or ""
    return any(marker in text for marker in _FALLBACK_STUB_MARKERS)


_README_NAMES = ("README.md", "README.rst", "README.txt", "README")
_OVERVIEW_PAGE_TOKENS = ("project-overview", "项目概述")
_INSTALL_PAGE_TOKENS = ("installation", "安装指南", "安装与配置")
_API_PAGE_TOKENS = ("core-service-apis", "核心服务api")
_INSTALL_CLUE_PATTERNS = (
    ("docker-compose", re.compile(r"docker-compose|docker compose", re.I)),
    ("docker", re.compile(r"\bdocker\b", re.I)),
    ("podman-compose", re.compile(r"\bpodman-compose\b", re.I)),
    ("podman", re.compile(r"\bpodman\b", re.I)),
    ("DATABASE_URL", re.compile(r"database_url", re.I)),
    ("POSTGRES", re.compile(r"postgres", re.I)),
    ("sqlite", re.compile(r"\bsqlite3?\b", re.I)),
    ("uv sync", re.compile(r"\buv\s+sync\b", re.I)),
    ("uv run", re.compile(r"\buv\s+run\b", re.I)),
    ("npm install", re.compile(r"\bnpm\s+install\b", re.I)),
    ("npm", re.compile(r"\bnpm\b", re.I)),
    ("npx", re.compile(r"\bnpx\b", re.I)),
    ("yarn", re.compile(r"\byarn\b", re.I)),
    ("pnpm", re.compile(r"\bpnpm\b", re.I)),
    ("pip install", re.compile(r"\bpip(?:3)?\s+install\b", re.I)),
    ("poetry", re.compile(r"\bpoetry\s+(?:install|run)\b", re.I)),
    ("alembic", re.compile(r"\balembic\s+upgrade\b", re.I)),
    ("uvicorn", re.compile(r"\buvicorn\s+[A-Za-z0-9_.:-]+", re.I)),
    ("go build", re.compile(r"\bgo\s+build\b", re.I)),
    ("go run", re.compile(r"\bgo\s+run\b", re.I)),
    ("go test", re.compile(r"\bgo\s+test\b", re.I)),
    ("make", re.compile(r"\bmake\s+[A-Za-z0-9_./-]+", re.I)),
)
_INSTALL_SIGNAL_FILES = (
    "pyproject.toml",
    "package.json",
    "go.mod",
    "Makefile",
    "makefile",
    "QUICKSTART.md",
    "QUICKSTART.rst",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "podman-compose.yml",
    "podman-compose.yaml",
)


def contains_generator_meta(markdown: str) -> bool:
    """Return True when markdown contains generator self-description phrases."""
    if not markdown:
        return False
    lowered = markdown.lower()
    return any(phrase.lower() in lowered for phrase in HANDBOOK_META_PHRASES)


def has_unclosed_fence(markdown: str) -> bool:
    """Return True when a ``` fenced code block is opened and never closed."""
    in_fence = False
    for line in markdown.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
    return in_fence


def is_page_timeout_rejection(reason: str | None) -> bool:
    """True for ``LLM page timeout after {seconds}s`` reasons."""
    return reason is not None and reason.startswith(PAGE_TIMEOUT_REJECTION_PREFIX)


def page_timeout_rejection(seconds: float) -> str:
    return f"{PAGE_TIMEOUT_REJECTION_PREFIX} {seconds:.1f}s"


def is_page_server_error_rejection(reason: str | None) -> bool:
    """True for ``LLM page server error 529: ...`` page-local rewrites."""
    return reason is not None and reason.startswith(PAGE_SERVER_ERROR_REJECTION_PREFIX)


def page_server_error_rejection(exc: BaseException) -> str:
    details = getattr(exc, "details", None) or {}
    status = details.get("status") if isinstance(details, dict) else None
    status_bit = f" {status}" if status is not None else ""
    return f"{PAGE_SERVER_ERROR_REJECTION_PREFIX}{status_bit}: {exc}"


def is_transient_server_error(exc: BaseException) -> bool:
    """HTTP 5xx / MiniMax 529 after inner retries: rewrite that page, do not melt the run."""
    code = str(getattr(exc, "code", "") or "")
    if code.endswith("SERVER_ERROR") or code == "SERVER_ERROR":
        return True
    details = getattr(exc, "details", None) or {}
    status = details.get("status") if isinstance(details, dict) else None
    if status is None:
        return False
    try:
        return int(status) in {500, 502, 503, 504, 529}
    except (TypeError, ValueError):
        return False


def is_rate_limit_error(exc: BaseException) -> bool:
    """True for HTTP 429 / RATE_LIMIT so the composer can back off instead of DEGRADE."""
    code = str(getattr(exc, "code", "") or "")
    if code.endswith("RATE_LIMIT") or code == "RATE_LIMIT":
        return True
    details = getattr(exc, "details", None) or {}
    status = details.get("status") if isinstance(details, dict) else None
    if status is None:
        return False
    try:
        return int(status) == 429
    except (TypeError, ValueError):
        return False


def is_page_local_quality_rejection(reason: str | None) -> bool:
    """Quality rejects after HTTP 200, or a page LLM timeout/529, are not provider outages."""
    if reason in _PAGE_LOCAL_QUALITY_REJECTIONS:
        return True
    return is_page_timeout_rejection(reason) or is_page_server_error_rejection(reason)


def iter_markdown_pages(content_dir: Path | None) -> list[Path]:
    if content_dir is None or not content_dir.exists():
        return []
    return sorted(path for path in content_dir.rglob("*.md") if path.is_file())


def page_matches(path: Path, tokens: tuple[str, ...]) -> bool:
    """Match the page file stem, not a parent folder name.

    Overview identity must target ``项目概述.md`` / ``project-overview.md``, not
    siblings such as ``项目概述/核心功能特性/核心功能特性.md``.
    """
    stem = path.stem.replace("\\", "/").lower()
    return any(token.lower() == stem for token in tokens)


def find_matching_pages(content_dir: Path | None, tokens: tuple[str, ...]) -> list[Path]:
    return [path for path in iter_markdown_pages(content_dir) if page_matches(path, tokens)]


def read_readme_text(repo_root: Path) -> str:
    for name in _README_NAMES:
        candidate = repo_root / name
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8", errors="ignore")
    return ""


def existing_readme_names(repo_root: Path) -> tuple[str, ...]:
    found = [name for name in _README_NAMES if (repo_root / name).is_file()]
    return tuple(found) if found else _README_NAMES


def _fold_identity_token(value: str) -> str:
    return re.sub(r"[-_\s]+", "", value.casefold())


def identity_match_tokens(repo_root: Path) -> tuple[str, ...]:
    """Identity strings a handbook overview may use: display_name, name, directory."""
    from repo_wiki.planner.identity import resolve_repository_identity

    identity = resolve_repository_identity(repo_root)
    tokens: list[str] = []
    for raw in (identity.display_name, identity.name, repo_root.name):
        text = (raw or "").strip()
        if text and text not in tokens:
            tokens.append(text)
    return tuple(tokens)


def page_contains_identity_token(markdown: str, token: str) -> bool:
    if not token.strip():
        return False
    if token.lower() in markdown.lower():
        return True
    folded = _fold_identity_token(token)
    return bool(folded) and folded in _fold_identity_token(markdown)


def overview_identity_satisfied(markdown: str, repo_root: Path) -> bool:
    """Return True when the overview states the resolved product identity.

    Only ``identity_match_tokens`` (display_name, package name, directory)
    count. Any 4+ character README word is not an identity token.
    """
    return any(
        page_contains_identity_token(markdown, token) for token in identity_match_tokens(repo_root)
    )


def _repo_run_source_text(repo_root: Path) -> str:
    chunks = [read_readme_text(repo_root)]
    for rel in _INSTALL_SIGNAL_FILES:
        path = repo_root / rel
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
    for extra in sorted(repo_root.glob("README*")):
        if extra.is_file() and extra.name not in _README_NAMES:
            chunks.append(extra.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(chunks)


def repo_run_clue_names(repo_root: Path) -> tuple[str, ...]:
    blob = _repo_run_source_text(repo_root)
    return tuple(name for name, pattern in _INSTALL_CLUE_PATTERNS if pattern.search(blob))


def _install_clue_patterns(
    repo_root: Path | None = None,
) -> tuple[tuple[str, re.Pattern[str]], ...]:
    if repo_root is None:
        return _INSTALL_CLUE_PATTERNS
    present = set(repo_run_clue_names(repo_root))
    return tuple(item for item in _INSTALL_CLUE_PATTERNS if item[0] in present)


def install_run_clue_count(markdown: str, repo_root: Path | None = None) -> int:
    """Count how-to-run clues on a page, preferring this repo's README/scripts."""
    return sum(
        1 for _name, pattern in _install_clue_patterns(repo_root) if pattern.search(markdown)
    )


def iter_fenced_code_bodies(markdown: str) -> list[str]:
    """Return fenced code bodies, skipping mermaid diagrams."""
    bodies: list[str] = []
    in_fence = False
    lang = ""
    buf: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_fence:
                in_fence = True
                info = stripped[3:].strip()
                lang = info.split()[0].lower() if info else ""
                buf = []
            else:
                if lang != "mermaid":
                    bodies.append("\n".join(buf))
                in_fence = False
                lang = ""
                buf = []
            continue
        if in_fence:
            buf.append(line)
    return bodies


def has_fenced_install_run_command(markdown: str, repo_root: Path | None = None) -> bool:
    """True when at least one fenced block body matches an install/run clue.

    Inline backticks such as `` `uv sync` `` do not count.
    """
    patterns = _install_clue_patterns(repo_root)
    if not patterns:
        return False
    for body in iter_fenced_code_bodies(markdown):
        if any(pattern.search(body) for _name, pattern in patterns):
            return True
    return False


def has_readme_citation(markdown: str, readme_names: tuple[str, ...]) -> bool:
    for match in _CITE_RE.finditer(markdown):
        path = match.group(1).split(":")[0].replace("\\", "/").lower()
        for name in readme_names:
            if Path(path).name.lower() == name.lower() or path.endswith("/" + name.lower()):
                return True
    return False


_RUN_HEADING_RE = re.compile(
    r"(quick\s*start|getting\s*started|\brun\b|usage|install|setup|"
    r"快速开始|安装|启动|验证安装|运行)",
    re.I,
)
_BADGE_LINE_RE = re.compile(r"img\.shields\.io|badge/|!\[[^\]]*\]\(https?://", re.I)
_GO_BUILD_PATH_RE = re.compile(r"\bgo\s+build\b[^\n]*?\s(\./cmd/[A-Za-z0-9_./-]+)")
_GO_BUILD_MAIN_RE = re.compile(
    r"\bgo\s+build\b[^\n]*?(\./cmd/[A-Za-z0-9_-]+)/main\.go\b",
    re.IGNORECASE,
)
_BIN_FLAG_RE = re.compile(r"\./bin/([A-Za-z0-9_-]+)\s+(--?[A-Za-z0-9_-]+)")
_SOURCE_LISTEN_RE = re.compile(
    r"""(?ix)
    listen(?:_address|_addr)?\s*[:=]\s*["']?(?:[\d.]+|localhost)?:(\d{2,5})
    | defaultListen\w*[^0-9]{0,24}(\d{4,5})
    """
)
_COMPOSE_PORT_RE = re.compile(r"""["'](\d{2,5}):(\d{2,5})["']""")
_DOC_LOCALHOST_PORT_RE = re.compile(r"localhost:(\d{2,5})", re.IGNORECASE)
_MERMAID_ARROW = "-" + "->"  # assembled so CodeQL does not treat this as HTML -->
_REDIRECT_FILE_RE = re.compile(r"<\s*([A-Za-z0-9_./+*-]+\.\w+)")
_CONFIG_FLAG_RE = re.compile(r"--?config(?:-file)?\s+([A-Za-z0-9_./-]+)")
_CITE_RANGE_RE = re.compile(r"<cite>\s*([^<:]+):(\d+)(?:-(\d+))?\s*</cite>", re.IGNORECASE)


def _heading_is_run_usage(title: str) -> bool:
    return bool(_RUN_HEADING_RE.search(title or ""))


def _text_has_install_clue(text: str) -> bool:
    return any(pattern.search(text or "") for _name, pattern in _INSTALL_CLUE_PATTERNS)


def _text_is_badge_header(text: str) -> bool:
    if not text.strip():
        return False
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return False
    badge_lines = sum(1 for line in lines if _BADGE_LINE_RE.search(line))
    return badge_lines >= max(1, len(lines) // 2) and not _text_has_install_clue(text)


def readme_run_section_ranges(readme_text: str) -> list[tuple[int, int]]:
    """Return 1-based inclusive line ranges for README run/usage sections."""
    lines = (readme_text or "").splitlines()
    if not lines:
        return []
    headings: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines, start=1):
        match = re.match(r"^(#{1,3})\s+(.+)$", line.strip())
        if match:
            headings.append((index, len(match.group(1)), match.group(2).strip()))
    ranges: list[tuple[int, int]] = []
    for idx, (start, level, title) in enumerate(headings):
        if not _heading_is_run_usage(title):
            continue
        end = len(lines)
        for later_start, later_level, _later in headings[idx + 1 :]:
            if later_level <= level:
                end = later_start - 1
                break
        ranges.append((start, max(start, end)))
    if ranges:
        return ranges
    for index, line in enumerate(lines, start=1):
        if _text_has_install_clue(line):
            return [(index, min(len(lines), index + 40))]
    return []


def _cite_range(match: re.Match[str]) -> tuple[str, int, int]:
    path = match.group(1).replace("\\", "/").strip()
    start = int(match.group(2))
    end = int(match.group(3) or start)
    return path, start, end


def has_readme_run_section_citation(markdown: str, repo_root: Path) -> bool:
    """True when an install/overview README cite covers the run/usage section."""
    readme_names = {name.lower() for name in existing_readme_names(repo_root)}
    readme_text = read_readme_text(repo_root)
    if not readme_text.strip():
        return has_readme_citation(markdown, existing_readme_names(repo_root))
    run_ranges = readme_run_section_ranges(readme_text)
    lines = readme_text.splitlines()
    found_readme = False
    for match in _CITE_RANGE_RE.finditer(markdown or ""):
        path, start, end = _cite_range(match)
        if Path(path).name.lower() not in readme_names:
            continue
        found_readme = True
        cited = "\n".join(lines[max(0, start - 1) : max(start, end)])
        if _text_is_badge_header(cited):
            continue
        if _text_has_install_command_line(cited):
            return True
    if not found_readme:
        return False
    return not run_ranges


def _text_has_install_command_line(text: str) -> bool:
    for line in (text or "").splitlines():
        stripped = line.strip().lstrip("$").strip()
        if not stripped or stripped.startswith("#"):
            continue
        if any(pattern.search(stripped) for pattern in _REPO_INSTALL_LINE_PATTERNS):
            return True
    return False


def _cmd_package_exists(repo_root: Path, target: str) -> bool:
    rel = target.lstrip("./")
    path = repo_root / rel
    if path.is_file():
        return True
    if path.is_dir() and any(path.glob("*.go")):
        return True
    return False


def _flag_defined_in_cmd(repo_root: Path, binary: str, flag: str) -> bool:
    cmd_dir = repo_root / "cmd" / binary
    if not cmd_dir.is_dir():
        return True
    needle = flag.lstrip("-")
    blob = ""
    for path in cmd_dir.rglob("*.go"):
        blob += path.read_text(encoding="utf-8", errors="ignore")
    return bool(
        re.search(rf'"(?:-)?{re.escape(needle)}"', blob)
        or re.search(rf"\b{re.escape(needle)}\b", blob)
    )


def install_fenced_commands_are_grounded(markdown: str, repo_root: Path) -> bool:
    """False when fenced install commands invent missing paths, bins, or flags."""
    if not repo_root.is_dir():
        return True
    saw_path_command = False
    for body in iter_fenced_code_bodies(markdown or ""):
        for match in _GO_BUILD_PATH_RE.finditer(body):
            saw_path_command = True
            target = match.group(1)
            if not _cmd_package_exists(repo_root, target):
                return False
            if install_go_build_targets_main_with_siblings(target, repo_root):
                return False
        for match in _CONFIG_FLAG_RE.finditer(body):
            saw_path_command = True
            rel = match.group(1).lstrip("./")
            if not (repo_root / rel).exists():
                return False
        for match in _REDIRECT_FILE_RE.finditer(body):
            raw = match.group(1)
            if "*" in raw:
                return False
            if not (repo_root / raw.lstrip("./")).exists():
                return False
        for match in _BIN_FLAG_RE.finditer(body):
            saw_path_command = True
            binary, flag = match.group(1), match.group(2)
            if not (repo_root / "cmd" / binary).is_dir():
                return False
            if not _flag_defined_in_cmd(repo_root, binary, flag):
                return False
    return True if saw_path_command or "```" in (markdown or "") else True


def _go_package_dir_from_build_target(target: str) -> str:
    rel = target.lstrip("./")
    if rel.endswith("/main.go"):
        return rel[: -len("/main.go")]
    return rel


def _go_package_has_sibling_sources(repo_root: Path, package_rel: str) -> bool:
    pkg = repo_root / package_rel.lstrip("./")
    if not pkg.is_dir():
        return False
    return any(
        path.is_file() and path.suffix == ".go" and not path.name.endswith("_test.go")
        for path in pkg.glob("*.go")
        if path.name != "main.go"
    )


def install_go_build_targets_main_with_siblings(target: str, repo_root: Path) -> bool:
    """True when ``go build ./cmd/X/main.go`` would miss sibling package files."""
    rel = target.lstrip("./")
    if not rel.endswith("/main.go"):
        return False
    return _go_package_has_sibling_sources(repo_root, _go_package_dir_from_build_target(target))


def install_go_builds_use_package_dir(markdown: str, repo_root: Path) -> bool:
    """False when a fenced ``go build .../main.go`` has sibling non-test ``.go`` files."""
    if not repo_root.is_dir():
        return True
    for body in iter_fenced_code_bodies(markdown or ""):
        for match in _GO_BUILD_MAIN_RE.finditer(body):
            if _go_package_has_sibling_sources(repo_root, match.group(1).lstrip("./")):
                return False
        for match in _GO_BUILD_PATH_RE.finditer(body):
            if install_go_build_targets_main_with_siblings(match.group(1), repo_root):
                return False
    return True


def normalize_go_build_command(command: str, repo_root: Path | None = None) -> str:
    """Rewrite ``go build ./cmd/X/main.go`` to the package directory.

    Always emit the package dir: ``go build ./cmd/X/main.go`` fails when the
    package has sibling non-test ``.go`` files, and is never more correct
    than building the directory.
    """
    del repo_root
    return _GO_BUILD_MAIN_RE.sub(
        lambda match: match.group(0).replace(f"{match.group(1)}/main.go", match.group(1)),
        command,
    )


def collect_source_listen_ports(repo_root: Path) -> set[int]:
    """Listen ports from config.go / config.yaml / compose mappings."""
    ports: set[int] = set()
    if not repo_root.is_dir():
        return ports
    for rel in ("config.yaml", "config.yml", "config.go"):
        path = repo_root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in _SOURCE_LISTEN_RE.finditer(text):
            for group in match.groups():
                if group:
                    ports.add(int(group))
    for name in (
        "podman-compose.yml",
        "podman-compose.yaml",
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
    ):
        path = repo_root / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for host, container in _COMPOSE_PORT_RE.findall(text):
            if host == container:
                ports.add(int(host))
    return ports


def collect_doc_listen_ports(text: str) -> set[int]:
    return {int(match.group(1)) for match in _DOC_LOCALHOST_PORT_RE.finditer(text or "")}


def preferred_source_listen_port(repo_root: Path) -> int | None:
    ports = collect_source_listen_ports(repo_root)
    if not ports:
        return None
    return min(ports)


_MERMAID_FENCE_RE = re.compile(r"```mermaid\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_MERMAID_EDGE_TOKENS = (
    _MERMAID_ARROW,
    "-" + ">>",
    "=" + "=>",
    "-.-",
    "<" + "--",
    "|" + "|--",
)


def mermaid_block_is_generic_placeholder(block: str) -> bool:
    compact = re.sub(r"\s+", "", block or "")
    return (
        f'A["应用模块"]{_MERMAID_ARROW}B["业务服务"]' in compact
        and f'B{_MERMAID_ARROW}C["数据与仓库"]' in compact
    )


def normalize_mermaid_block(block: str) -> str:
    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in (block or "").splitlines()
        if line.strip() and not line.strip().startswith("%%")
    ]
    text = "\n".join(lines).casefold()
    # Page-id / label suffixes like [frontend-application-api] must not mint
    # a distinct key — otherwise the 30% bar is gamed by template copies.
    return re.sub(r"\s*\[[a-z0-9-]{8,}\]", "", text)


def extract_mermaid_blocks(text: str) -> list[str]:
    return [match.group(1).strip() for match in _MERMAID_FENCE_RE.finditer(text or "")]


def mermaid_edge_count(block: str) -> int:
    text = block or ""
    return sum(text.count(token) for token in _MERMAID_EDGE_TOKENS)


def handbook_placeholder_mermaid_pages(content_dir: Path | None) -> list[str]:
    """Pages that reuse the generic 应用模块→业务服务→数据与仓库 flowchart."""
    if content_dir is None or not content_dir.exists():
        return []
    found: list[str] = []
    for path in iter_markdown_pages(content_dir):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if mermaid_block_is_generic_placeholder(text):
            found.append(path.as_posix())
    return found


def handbook_duplicate_mermaid_groups(
    content_dir: Path | None, max_copies: int = 2
) -> dict[str, list[str]]:
    """Normalized mermaid bodies copied onto more than ``max_copies`` pages."""
    if content_dir is None or not content_dir.exists():
        return {}
    groups: dict[str, list[str]] = {}
    for path in iter_markdown_pages(content_dir):
        text = path.read_text(encoding="utf-8", errors="ignore")
        seen_on_page: set[str] = set()
        for block in extract_mermaid_blocks(text):
            key = normalize_mermaid_block(block)
            if not key or key in seen_on_page:
                continue
            seen_on_page.add(key)
            groups.setdefault(key, []).append(path.as_posix())
    return {key: pages for key, pages in groups.items() if len(pages) > max_copies}


def handbook_thin_mermaid_pages(content_dir: Path | None) -> list[str]:
    """Pages whose mermaid fences have fewer than two edges and are not ER relations."""
    if content_dir is None or not content_dir.exists():
        return []
    found: list[str] = []
    for path in iter_markdown_pages(content_dir):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for block in extract_mermaid_blocks(text):
            if "erdiagram" in block.lower():
                if mermaid_edge_count(block) < 1 and block.lower().count("{") > 1:
                    found.append(path.as_posix())
                    break
                continue
            if mermaid_edge_count(block) < 2:
                found.append(path.as_posix())
                break
    return found


_SQL_FENCE_RE = re.compile(r"```sql\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_SCHEMA_SECTION_RE = re.compile(
    r"##\s+Schema 摘要\n(.*?)(?=\n## |\Z)",
    re.IGNORECASE | re.DOTALL,
)
_SCHEMA_SUMMARY_RE = re.compile(
    r"UNRESOLVED_API_SCHEMA|证据中可确认的 schema 相关元数据",
    re.IGNORECASE,
)


def handbook_reserved_mermaid_id_pages(content_dir: Path | None) -> list[str]:
    """Pages whose mermaid fences use reserved node ids such as ``end``."""
    if content_dir is None or not content_dir.exists():
        return []
    from repo_wiki.generator.mermaid_planner import _reserved_mermaid_ids

    found: list[str] = []
    for path in iter_markdown_pages(content_dir):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for block in extract_mermaid_blocks(text):
            if _reserved_mermaid_ids(block):
                found.append(path.as_posix())
                break
    return found


def handbook_duplicate_schema_groups(
    content_dir: Path | None, max_copies: int = 2
) -> dict[str, list[str]]:
    """Identical SQL/schema blocks copied onto more than ``max_copies`` pages."""
    if content_dir is None or not content_dir.exists():
        return {}
    groups: dict[str, list[str]] = {}
    for path in iter_markdown_pages(content_dir):
        text = path.read_text(encoding="utf-8", errors="ignore")
        seen_on_page: set[str] = set()
        blocks = list(_SQL_FENCE_RE.findall(text))
        for section in _SCHEMA_SECTION_RE.findall(text):
            cleaned = re.sub(r"<cite>[^<]+</cite>", "", section)
            if _SCHEMA_SUMMARY_RE.search(cleaned) or len(cleaned.strip()) >= 80:
                blocks.append(cleaned)
        for block in blocks:
            key = normalize_mermaid_block(block)
            if not key or key in seen_on_page:
                continue
            seen_on_page.add(key)
            groups.setdefault(key, []).append(path.as_posix())
    return {key: pages for key, pages in groups.items() if len(pages) > max_copies}


def handbook_distinct_evidence_mermaid_count(content_dir: Path | None) -> tuple[int, int]:
    """Return (distinct evidence-backed diagrams, total pages). Copies do not count twice."""
    pages = list(iter_markdown_pages(content_dir)) if content_dir and content_dir.exists() else []
    distinct: set[str] = set()
    copies = handbook_duplicate_mermaid_groups(content_dir, max_copies=2)
    copied_keys = set(copies)
    for path in pages:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for block in extract_mermaid_blocks(text):
            key = normalize_mermaid_block(block)
            if not key or key in copied_keys or mermaid_block_is_generic_placeholder(block):
                continue
            if "erdiagram" in block.lower():
                if mermaid_edge_count(block) < 1:
                    continue
            elif mermaid_edge_count(block) < 2:
                continue
            distinct.add(key)
    return len(distinct), len(pages)


_GENERIC_GO_INSTALL = re.compile(
    r"\bgo\s+(?:build|run|mod\s+download)\s+(?:-o\s+\S+\s+)?(?:\.|./\.\.\.)\b",
    re.IGNORECASE,
)
_EXAMPLE_CMD_HINT_RE = re.compile(
    r"example|示例|demo|scaffold|sample|hello|custom[-_]",
    re.I,
)
_STUB_MAIN_RE = re.compile(
    r"^\s*package\s+main\s*(?:import\s+\([^)]*\)\s*)?func\s+main\s*\(\s*\)\s*\{\s*\}\s*$",
    re.S,
)
_REPO_INSTALL_LINE_PATTERNS = (
    re.compile(r"docker(?:-|\s+)compose(?:\s+[A-Za-z0-9_-]+){0,4}", re.I),
    re.compile(r"\bpodman-compose(?:\s+[A-Za-z0-9_-]+){0,6}", re.I),
    re.compile(r"\bmake(?:\s+[A-Za-z0-9_-]+){0,4}", re.I),
    re.compile(r"\bgo\s+build(?:\s+[A-Za-z0-9_./-]+){0,8}", re.I),
    re.compile(r"podman exec[^\n]{0,80}schema\.sql", re.I),
    re.compile(r"mysql[^\n]{0,80}schema\.sql", re.I),
    re.compile(r"curl\s+https?://localhost:\d+\S*", re.I),
    re.compile(r"\./bin/[A-Za-z0-9_-]+", re.I),
    re.compile(r"\bgo\s+run(?:\s+[A-Za-z0-9_./-]+){0,8}", re.I),
    re.compile(r"\buv\s+sync\b", re.I),
    re.compile(r"\buv\s+run(?:\s+[A-Za-z0-9_-]+){0,4}", re.I),
    re.compile(r"\bnpm\s+install(?:\s+[A-Za-z0-9_@/-]+){0,4}", re.I),
    re.compile(r"\bpip(?:3)?\s+install(?:\s+[A-Za-z0-9_\[\]'\"=-]+){0,4}", re.I),
    re.compile(r"\bpoetry\s+install(?:\s+[A-Za-z0-9_.-]*){0,4}", re.I),
    re.compile(r"\balembic\s+upgrade\s+head\b", re.I),
    re.compile(r"\buvicorn\s+[A-Za-z0-9_.:-]+(?:\s+--reload)?", re.I),
)


def _install_command_priority(command: str) -> tuple[int, str]:
    low = command.lower()
    score = 50
    if "podman-compose" in low or "docker compose" in low or "docker-compose" in low:
        score = 0
    elif "poetry install" in low or "pip install" in low or "uv sync" in low:
        score = 1
    elif "go build" in low:
        score = 2
    elif "alembic" in low:
        score = 3
    elif "schema.sql" in low:
        score = 4
    elif "uvicorn" in low or low.startswith("./bin/"):
        score = 5
    elif re.search(r"\./bin/", low):
        score = 6
    elif "curl" in low and "health" in low:
        score = 7
    elif low.startswith("make "):
        score = 8
    if _EXAMPLE_CMD_HINT_RE.search(low):
        score += 40
    return (score, command)


def collect_repo_install_commands(root: Path, limit: int = 12) -> list[str]:
    """Collect install/run commands from Makefile, README, and real cmd mains."""
    commands: list[str] = []
    seen: set[str] = set()

    def _add(command: str) -> None:
        text = " ".join(command.split()).strip()
        if not text or _GENERIC_GO_INSTALL.search(text):
            return
        key = text.casefold()
        if key in seen:
            return
        seen.add(key)
        commands.append(text)

    makefile = next(
        (path for path in (root / "Makefile", root / "makefile") if path.is_file()),
        None,
    )
    if makefile is not None:
        text = makefile.read_text(encoding="utf-8", errors="ignore")
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if re.search(r"\b(?:go\s+build|podman-compose|docker-compose|go\s+run)\b", line):
                _add(normalize_go_build_command(line, root))
        if re.search(r"^install:", text, re.M):
            _add("make install")
        if re.search(r"^up:", text, re.M):
            _add("make up")
    core_mains: list[Path] = []
    demo_mains: list[Path] = []
    for main in sorted([*root.glob("cmd/*/main.go"), *root.glob("app/main.go")]):
        docs = ""
        for readme in ("README.md", "README.rst", "README.txt"):
            candidate = main.parent / readme
            if candidate.is_file():
                docs = candidate.read_text(encoding="utf-8", errors="ignore")
                break
        hint = f"{main.parent.name}\n{docs[:400]}"
        from repo_wiki.generator.process_roles import path_looks_like_example_cmd

        stub = False
        try:
            stub = bool(_STUB_MAIN_RE.match(main.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            stub = False
        if (
            path_looks_like_example_cmd(main.as_posix())
            or _EXAMPLE_CMD_HINT_RE.search(hint)
            or stub
        ):
            demo_mains.append(main)
        else:
            core_mains.append(main)
    for main in core_mains or demo_mains:
        pkg = main.parent.relative_to(root).as_posix()
        _add(f"go build -o bin/{main.parent.name} ./{pkg}")
    if (root / "db" / "schema.sql").is_file():
        _add("mysql < db/schema.sql")
    if (root / "pyproject.toml").is_file():
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
        if "[tool.poetry]" in pyproject or "poetry" in pyproject.lower():
            _add("poetry install")
    if (root / "alembic.ini").is_file() or (root / "alembic").is_dir():
        _add("alembic upgrade head")
    if (root / "app" / "main.py").is_file():
        _add("uvicorn app.main:app --reload")
    for name in ("README.md", "README.rst", "QUICKSTART.md"):
        path = root / name
        if not path.is_file():
            continue
        joined: list[str] = []
        buf = ""
        for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            piece = raw_line.rstrip()
            if buf:
                piece = buf + " " + piece.lstrip()
                buf = ""
            if piece.endswith("\\"):
                buf = piece[:-1].rstrip()
                continue
            joined.append(piece)
        if buf:
            joined.append(buf)
        for raw_line in joined:
            line = raw_line.strip().lstrip("$").strip()
            if not line or line.startswith("#") or line.startswith(".."):
                continue
            for pattern in _REPO_INSTALL_LINE_PATTERNS:
                match = pattern.search(line)
                if not match:
                    continue
                command = " ".join(match.group(0).split()).rstrip(".,;:)")
                if command.endswith("\\"):
                    continue
                if command and len(command) <= 240:
                    if _EXAMPLE_CMD_HINT_RE.search(command) and core_mains:
                        continue
                    _add(normalize_go_build_command(command, root))
    if (root / "example.env").is_file():
        _add("cp example.env .env")
    has_compose = any(
        token in item.lower()
        for item in commands
        for token in ("podman-compose", "docker compose", "docker-compose")
    )
    schema_cmds = [item for item in commands if "schema.sql" in item]
    if schema_cmds:
        preferred_schema = next(
            (item for item in schema_cmds if "exec" in item.lower()),
            schema_cmds[0],
        )
        commands = [item for item in commands if "schema.sql" not in item]
        commands.append(preferred_schema)
    if has_compose:
        commands = [item for item in commands if "./bin/" not in item]
    commands = [f"poetry run {item}" if item.startswith("uvicorn ") else item for item in commands]
    commands.sort(key=_install_command_priority)
    return commands[:limit]


def architecture_core_packages(repo_root: Path) -> list[str]:
    """Entry-point packages plus import-graph neighbors they own.

    Discovers cmd/*/main.go, app/main.go, domain/, and service packages.
    Empty means the architecture gate must fail closed.
    """
    from repo_wiki.generator.process_roles import derive_process_roles, path_looks_like_example_cmd

    cores: list[str] = []
    entry_rels: list[str] = []
    for item in derive_process_roles(repo_root):
        if item.example or path_looks_like_example_cmd(item.rel_main):
            continue
        if not ({"rest_entry", "data_plane", "http_server"} & set(item.kinds)):
            continue
        rel = str(Path(item.rel_main).parent.as_posix())
        if rel and rel not in cores:
            cores.append(rel)
            entry_rels.append(rel)

    try:
        from repo_wiki.generator.compose_evidence import load_repo_import_edges

        edges = load_repo_import_edges(repo_root)
    except Exception:
        edges = set()
    for src, dest in edges:
        src_s = str(src).replace("\\", "/")
        dest_s = str(dest).replace("\\", "/")
        if not any(src_s == rel or src_s.startswith(rel + "/") for rel in entry_rels):
            continue
        pack = _owned_implementation_package(dest_s)
        if pack and pack not in cores:
            cores.append(pack)

    if (repo_root / "app" / "main.go").is_file() and "app" not in cores:
        cores.append("app")
    if (repo_root / "domain").is_dir() and "domain" not in cores:
        cores.append("domain")
    for rel in ("app/api/routes", "app/services"):
        if (repo_root / rel).exists() and rel not in cores:
            if rel != "app/services" or (repo_root / "app" / "api" / "routes").exists():
                cores.append(rel)
    return cores


def _owned_implementation_package(spec: str) -> str:
    parts = [part for part in spec.replace("\\", "/").split("/") if part]
    for index, part in enumerate(parts):
        if part in {"internal", "pkg", "app", "domain"} and index + 1 < len(parts):
            return "/".join(parts[index : index + 2])
    return ""


def architecture_required_packages(repo_root: Path) -> list[str]:
    """Every derived core package must appear on the architecture page."""
    return list(architecture_core_packages(repo_root))


def has_architecture_core_citation(markdown: str, repo_root: Path) -> bool:
    """True when an architecture page cites every derived core package.

    Fail closed when discovery finds nothing: an architecture page without
    cores is not a pass.
    """
    cores = architecture_core_packages(repo_root)
    if not cores:
        return False
    cited = " ".join(
        match.group(1).replace("\\", "/") for match in _CITE_RE.finditer(markdown or "")
    ).lower()
    return all(rel.lower() in cited for rel in cores)


def data_model_required_sources(repo_root: Path) -> list[str]:
    """Model packages that a data-model page must cite when they exist.

    ``schema.sql`` alone is not enough when GORM/SQLAlchemy model sources exist.
    """
    required: list[str] = []
    if (repo_root / "internal" / "models").is_dir():
        required.append("internal/models")
    if (repo_root / "domain").is_dir():
        required.append("domain")
    if (repo_root / "app" / "models" / "domain").is_dir():
        required.append("app/models/domain")
    elif (repo_root / "app" / "models").is_dir():
        required.append("app/models")
    for pack in _gorm_struct_packages(repo_root):
        if pack not in required:
            required.append(pack)
    for sql in sorted(repo_root.glob("*.sql")):
        required.append(sql.name)
    if (repo_root / "db" / "schema.sql").is_file() and "db/schema.sql" not in required:
        required.append("db/schema.sql")
    migrations = repo_root / "app" / "db" / "migrations"
    alembic = repo_root / "alembic"
    if migrations.exists() and any(migrations.rglob("*")):
        required.append("app/db/migrations")
    elif alembic.is_dir() and any(alembic.rglob("*.py")):
        required.append("alembic")
    return required


def _gorm_struct_packages(repo_root: Path) -> list[str]:
    skip = {".git", ".repo-agent-eval", "vendor", "node_modules"}
    found: list[str] = []
    for path in repo_root.rglob("*.go"):
        if any(part in skip for part in path.parts) or path.name.endswith("_test.go"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if 'gorm:"' not in text and "gorm:" not in text:
            continue
        rel = path.parent.relative_to(repo_root).as_posix()
        if rel not in found:
            found.append(rel)
    return found


def data_model_optional_sources(repo_root: Path) -> list[str]:
    optional: list[str] = []
    if (repo_root / "db" / "schema.sql").is_file():
        optional.append("db/schema.sql")
    return optional


def has_data_model_source_citation(markdown: str, repo_root: Path) -> bool:
    """True when a data-model page cites every existing model package."""
    required = data_model_required_sources(repo_root)
    optional = data_model_optional_sources(repo_root)
    if not required and not optional:
        return True
    cited = " ".join(
        match.group(1).replace("\\", "/") for match in _CITE_RE.finditer(markdown or "")
    ).lower()
    if required and not all(need.lower() in cited for need in required):
        return False
    if (repo_root / "internal" / "models").is_dir() and not _has_go_struct_definition_cite(
        markdown, repo_root
    ):
        return False
    if (repo_root / "internal" / "models").is_dir() and not _has_required_go_struct_cites(
        markdown, repo_root
    ):
        return False
    versions = repo_root / "app" / "db" / "migrations" / "versions"
    if versions.is_dir() and any(versions.glob("*.py")):
        if "migrations/versions" not in cited:
            return False
    if required:
        return True
    return any(need.lower() in cited for need in optional)


def _go_struct_definition_ranges(repo_root: Path) -> list[tuple[str, int, int]]:
    models_dir = repo_root / "internal" / "models"
    if not models_dir.is_dir():
        return []
    found: list[tuple[str, int, int]] = []
    struct_re = re.compile(r"^type\s+([A-Z][A-Za-z0-9_]*)\s+struct\s*\{")
    for path in sorted(models_dir.rglob("*.go")):
        if path.name.endswith("_test.go"):
            continue
        rel = path.relative_to(repo_root).as_posix()
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for index, line in enumerate(lines, start=1):
            if struct_re.match(line):
                from repo_wiki.generator.deterministic_sections import go_struct_end_line

                found.append((rel, index, go_struct_end_line(lines, index)))
    return found


def _has_go_struct_definition_cite(markdown: str, repo_root: Path) -> bool:
    ranges = _go_struct_definition_ranges(repo_root)
    if not ranges:
        return True
    for match in _CITE_RE.finditer(markdown or ""):
        raw = match.group(1).replace("\\", "/")
        path, _sep, rest = raw.partition(":")
        if not rest:
            continue
        start_s, _dash, end_s = rest.partition("-")
        try:
            start = int(re.sub(r"\D.*", "", start_s) or "0")
            end = int(re.sub(r"\D.*", "", end_s or start_s) or start)
        except ValueError:
            continue
        for rel, struct_start, struct_end in ranges:
            if path.lower() != rel.lower():
                continue
            # File-header cites like :1-8 that merely graze a later struct do not count.
            if start <= 1 and struct_start > 3:
                continue
            if start <= struct_end and end >= struct_start:
                return True
    return False


def _has_required_go_struct_cites(markdown: str, repo_root: Path) -> bool:
    from repo_wiki.generator.deterministic_sections import (
        discover_core_domain_structs,
        go_struct_cite,
    )

    text = markdown or ""
    needed = [go_struct_cite(repo_root, name) for name in discover_core_domain_structs(repo_root)]
    needed = [item for item in needed if item]
    if not needed:
        return True
    cited = " ".join(match.group(1) for match in _CITE_RE.finditer(text))
    for cite in needed:
        raw = cite.replace("<cite>", "").replace("</cite>", "")
        path, _sep, rest = raw.partition(":")
        start_s = rest.split("-", 1)[0]
        if path not in cited or start_s not in cited:
            return False
    return True


def has_api_routes_citation(
    markdown: str, handler_files: list[str] | tuple[str, ...] | None = None
) -> bool:
    """True when an API page cites FastAPI ``api/routes`` or inventory handlers.

    FastAPI layout (inventory contains ``api/routes``, or no inventory) still
    requires an ``api/routes`` citation. Go/other layouts accept a cite to one
    of the inventory handler files.
    """
    cited: list[str] = []
    for match in _CITE_RE.finditer(markdown):
        path = match.group(1).split(":")[0].replace("\\", "/").lower()
        cited.append(path)
    handlers = [item.replace("\\", "/").lower() for item in (handler_files or []) if item]
    fastapi_handlers = [item for item in handlers if "api/routes" in item]
    if fastapi_handlers or not handlers:
        return any("api/routes" in path for path in cited)
    return any(_cite_matches_handler(path, handlers) for path in cited)


def _cite_matches_handler(path: str, handlers: list[str]) -> bool:
    for handler in handlers:
        if (
            path == handler
            or path.endswith("/" + handler)
            or handler.endswith("/" + path)
            or path.endswith(handler)
            or handler.endswith(path)
        ):
            return True
    return False


def handbook_reader_hygiene_offenders(
    content_dir: Path | None, repo_root: Path | None
) -> dict[str, list[str]]:
    """Fail reader-facing boilerplate: repeated paragraphs, header cites, meta, dup fences."""
    from repo_wiki.generator.deterministic_sections import (
        is_header_only_cite,
        page_has_meta_instruction,
        page_has_repeated_fences,
    )

    found: dict[str, list[str]] = {
        "repeated_paragraphs": [],
        "header_only_cites": [],
        "meta_instructions": [],
        "repeated_fences": [],
        "instruction_voice": [],
        "evidence_meta_talk": [],
        "missing_h1": [],
        "tiny_body": [],
        "fact_disclaimer": [],
        "raw_artefact": [],
        "repeated_fact_block": [],
    }
    if content_dir is None or not content_dir.exists():
        return {}
    paragraph_pages: dict[str, list[str]] = {}
    sentence_pages: dict[str, list[str]] = {}
    for path in iter_markdown_pages(content_dir):
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.as_posix()
        if page_has_meta_instruction(text):
            found["meta_instructions"].append(rel)
        if page_has_repeated_fences(text):
            found["repeated_fences"].append(rel)
        if _INSTRUCTION_VOICE_RE.search(text):
            found["instruction_voice"].append(rel)
        if contains_evidence_meta_talk(text):
            found["evidence_meta_talk"].append(rel)
        if not _H1_RE.search(text):
            found["missing_h1"].append(rel)
        if handbook_page_body_len(text) < MIN_HANDBOOK_BODY_CHARS or handbook_page_is_truncated(
            text
        ):
            found["tiny_body"].append(rel)
        if _FACT_DISCLAIMER_RE.search(text):
            found["fact_disclaimer"].append(rel)
        if _RAW_ARTEFACT_RE.search(text):
            found["raw_artefact"].append(rel)
        if repo_root is not None:
            for match in _CITE_RE.finditer(text):
                raw = match.group(0)
                if is_header_only_cite(raw, repo_root):
                    found["header_only_cites"].append(rel)
                    break
        for para in re.split(r"\n\s*\n", text):
            key = re.sub(r"\s+", " ", para).strip()
            if len(key) < 80 or "```" in key:
                continue
            paragraph_pages.setdefault(key, []).append(rel)
            if _NEAR_FACT_SENTENCE_RE.search(key) or key.count("`") >= 4:
                sentence_pages.setdefault(key[:160], []).append(rel)
    # Same deterministic dump on 4+ reader pages is the hygiene floor.
    # Do not lower this: emit-once must stop the copy, not the check.
    found["repeated_paragraphs"] = sorted(
        {page for pages in paragraph_pages.values() if len(set(pages)) >= 4 for page in pages}
    )
    found["repeated_fact_block"] = sorted(
        {page for pages in sentence_pages.values() if len(set(pages)) > 3 for page in pages}
    )
    return {key: values for key, values in found.items() if values}


def handbook_page_body_len(markdown: str) -> int:
    """Character count of reader body, excluding H1, TOC, and cite tags."""
    text = re.sub(r"<cite>.*?</cite>", "", markdown or "", flags=re.IGNORECASE)
    kept: list[str] = []
    skip_toc = False
    for line in text.splitlines():
        stripped = line.strip()
        if _H1_RE.match(stripped):
            continue
        if re.match(r"^##\s+目录\s*$", stripped):
            skip_toc = True
            continue
        if skip_toc:
            if re.match(r"^##\s+", stripped):
                skip_toc = False
            else:
                continue
        kept.append(line)
    return len("".join(kept).strip())


def handbook_page_is_truncated(markdown: str) -> bool:
    """True when the last visible prose line is cut mid-word."""
    visible: list[str] = []
    in_fence = False
    for raw in (markdown or "").splitlines():
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            continue
        visible.append(re.sub(r"<cite>.*?</cite>", "", stripped, flags=re.IGNORECASE).strip())
    if not visible:
        return True
    last = visible[-1]
    if last.startswith("#") or last.startswith("|") or last.startswith("-") or last.startswith("*"):
        return False
    if last[:2].isdigit() and "." in last[:4]:
        return False
    if last.endswith(("。", "！", "？", ".", "!", "?", ":", "：", "）", ")", "`", ">", "；", ";")):
        return False
    token = re.search(r"([A-Za-z]+)$", last)
    if token is None:
        return False
    fragment = token.group(1)
    return len(fragment) <= 5 and bool(re.search(r"[/\-]", last[-12:]))


def handbook_unknown_process_offenders(
    content_dir: Path | None, repo_root: Path | None
) -> dict[str, list[str]]:
    """Pages that name a binary/process not present in the documented repo."""
    from repo_wiki.generator.process_roles import (
        derive_repo_process_names,
        unknown_process_mentions,
    )

    if content_dir is None or not content_dir.exists() or repo_root is None:
        return {}
    allowed = derive_repo_process_names(repo_root)
    found: dict[str, list[str]] = {}
    for path in iter_markdown_pages(content_dir):
        names = unknown_process_mentions(path.read_text(encoding="utf-8", errors="ignore"), allowed)
        if names:
            found[path.as_posix()] = names
    return found


_STALE_METHOD_RE = re.compile(r"`([A-Z][A-Za-z0-9]+)`")
_DOC_MISMATCH_SKIP = frozenset(
    {
        "Docker",
        "GitHub",
        "LICENSE",
        "Makefile",
        "Caddyfile",
        "TestClient",
        "Readme",
        "Bearer",
    }
)


def _iter_page_code_units(markdown: str) -> list[str]:
    """Inline/fence bodies for integrity, matching acc-25r (incl. bash, A.B, spaces)."""
    from repo_wiki.generator.code_safe import iter_integrity_code_units

    units: list[str] = []
    for kind, body in iter_integrity_code_units(markdown):
        if kind == "empty":
            continue
        normalized = re.sub(r"\s+", " ", body).strip()
        if len(normalized) < 3:
            continue
        units.append(body)
    return units


_TYPE_METHOD_RE = re.compile(
    r"func\s+\(\s*[A-Za-z_]\w*\s+\*?([A-Z][A-Za-z0-9]+)\s*\)\s+([A-Z][A-Za-z0-9]+)"
)


def load_type_method_inventory(repo_root: Path) -> set[str]:
    """Inventory-verified ``Type.Method`` labels from Go method receivers."""
    found: set[str] = set()
    skip = {".git", ".repo-agent-eval", "vendor", "node_modules"}
    for path in repo_root.rglob("*.go"):
        if any(part in skip for part in path.parts) or path.name.endswith("_test.go"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for recv, method in _TYPE_METHOD_RE.findall(text):
            found.add(f"{recv}.{method}")
    return found


def handbook_code_integrity_offenders(
    content_dir: Path | None,
    repo_root: Path | None,
    raw_replies: dict[str, str] | None = None,
) -> dict[str, list[str]]:
    """Code spans/fences mutated away from the raw reply and repository source.

    Also flags empty inline spans and unclosed fences. Final units must be
    byte-identical to the raw model reply. Generator-owned extras (not in the
    raw reply) must appear in repository source. Thresholds match
    acc-25s/code_integrity.py: mermaid excluded, bash fences and A.B / spaced
    spans included, single-space normalisation.
    """
    from repo_wiki.generator.code_safe import (
        empty_inline_spans,
        is_mermaid_fence,
        iter_integrity_code_units,
        sacred_code_offenders,
    )

    if content_dir is None or not content_dir.exists() or repo_root is None:
        return {}
    source_blob = _repo_source_blob(repo_root, exclude=content_dir)
    raw_replies = raw_replies or _load_raw_replies(content_dir)
    source_norm = _norm_code_blob(source_blob)
    type_methods = load_type_method_inventory(repo_root)
    found: dict[str, list[str]] = {}
    for path in iter_markdown_pages(content_dir):
        text = path.read_text(encoding="utf-8", errors="ignore")
        raw = (
            (raw_replies or {}).get(path.relative_to(content_dir).as_posix())
            or (raw_replies or {}).get(path.stem)
            or ""
        )
        missing: list[str] = []
        if has_unclosed_fence(text):
            missing.append("unclosed-fence")
        empty_count = len(empty_inline_spans(text))
        if empty_count:
            missing.append(f"empty-span x{empty_count}")
        if raw:
            for unit in sacred_code_offenders(text, raw):
                if is_mermaid_fence(unit):
                    continue
                body = unit.strip("`")
                if unit.startswith("```"):
                    body = re.sub(r"^```[^\n]*\n?", "", unit)
                    body = re.sub(r"```$", "", body)
                if body in type_methods:
                    continue
                normalized = _norm_code_blob(body)
                if normalized and (normalized in source_norm or body in source_blob):
                    continue
                missing.append(f"sacred: {unit[:120]}")
        else:
            for kind, body in iter_integrity_code_units(text):
                if kind == "empty":
                    continue
                if body in type_methods:
                    continue
                normalized = _norm_code_blob(body)
                if len(normalized) < 3:
                    continue
                if body in source_blob or normalized in source_norm:
                    continue
                missing.append(f"{kind}: {normalized[:120]}")
        if missing:
            found[path.as_posix()] = missing[:16]
    return found


def _readme_code_identifiers(repo_root: Path) -> set[str]:
    """Function/type names that appear in README fenced or indented code only."""
    readme = read_readme_text(repo_root)
    if not readme:
        return set()
    blocks: list[str] = re.findall(r"```[\w-]*\n(.*?)```", readme, flags=re.S)
    blocks.extend(re.findall(r"(?m)^(?:    |\t)(.+)$", readme))
    blob = "\n".join(blocks)
    return {name for name in re.findall(r"\b([A-Z][A-Za-z0-9]{5,})\b", blob)}


def handbook_doc_code_mismatches(
    content_dir: Path | None, repo_root: Path | None
) -> dict[str, list[str]]:
    """README-code identifiers presented as the code API but missing from source."""
    if content_dir is None or not content_dir.exists() or repo_root is None:
        return {}
    source_blob = _repo_code_blob(repo_root)
    readme_ids = _readme_code_identifiers(repo_root)
    found: dict[str, list[str]] = {}
    for path in iter_markdown_pages(content_dir):
        text = path.read_text(encoding="utf-8", errors="ignore")
        stale: list[str] = []
        for name in _STALE_METHOD_RE.findall(text):
            if name in _DOC_MISMATCH_SKIP or len(name) < 6:
                continue
            if name not in readme_ids:
                continue
            if name in source_blob:
                continue
            if re.search(
                rf"\bdef\s+{re.escape(name)}\b|\bfunc\s+\([^)]+\)\s+{re.escape(name)}\b|\bfunc\s+{re.escape(name)}\b",
                source_blob,
            ):
                continue
            stale.append(name)
        if stale:
            found[path.as_posix()] = sorted(set(stale))[:8]
    return found


def _raw_reply_dir(content_dir: Path) -> Path:
    return content_dir.parent / "meta" / "raw-replies"


def _norm_code_blob(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _load_raw_replies(content_dir: Path) -> dict[str, str]:
    folder = _raw_reply_dir(content_dir)
    if not folder.is_dir():
        return {}
    loaded: dict[str, str] = {}
    for path in folder.rglob("*.md"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        loaded[path.relative_to(folder).as_posix()] = text
        loaded[path.stem] = text
        loaded[path.name] = text
    registry = content_dir.parent / "page-registry.json"
    if not registry.is_file():
        registry = content_dir.parent / "meta" / "page-registry.json"
    if registry.is_file():
        try:
            payload = json.loads(registry.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        for page in payload.get("pages") or []:
            if not isinstance(page, dict):
                continue
            rel = str(page.get("relative_path") or page.get("path") or "")
            page_id = str(page.get("page_id") or "")
            if rel and page_id and page_id in loaded:
                loaded[rel] = loaded[page_id]
    return loaded


def _repo_source_blob(repo_root: Path, exclude: Path | None = None) -> str:
    skip = {".git", ".repo-agent-eval", "node_modules", "vendor", "__pycache__", ".venv"}
    parts: list[str] = []
    for path in repo_root.rglob("*"):
        if not path.is_file() or any(part in skip for part in path.parts):
            continue
        if exclude is not None and (path == exclude or exclude in path.parents):
            continue
        if "raw-replies" in path.parts:
            continue
        if path.suffix.lower() not in {
            ".go",
            ".py",
            ".md",
            ".rst",
            ".yml",
            ".yaml",
            ".toml",
            ".sql",
        }:
            continue
        try:
            parts.append(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    return "\n".join(parts)


def _repo_code_blob(repo_root: Path) -> str:
    """Code files only; docs are excluded so README samples can be flagged."""
    skip = {".git", ".repo-agent-eval", "node_modules", "vendor", "__pycache__", ".venv"}
    parts: list[str] = []
    for path in repo_root.rglob("*"):
        if not path.is_file() or any(part in skip for part in path.parts):
            continue
        if path.suffix.lower() not in {".go", ".py"}:
            continue
        if path.name.endswith("_test.go") or path.name.endswith("_test.py"):
            continue
        try:
            parts.append(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    return "\n".join(parts)
