"""Handbook wiki helpers: generator-meta detection and page-local quality rejects."""

from __future__ import annotations

import re
from pathlib import Path

HANDBOOK_META_PHRASES: tuple[str, ...] = (
    "fallback composer",
    "repo-agent",
    "该页面对应",
    "evidence ranking",
)

GENERATOR_META_REJECTION = "Handbook generator meta content"
EMPTY_CONTENT_REJECTION = "Empty LLM assistant content"
UNCLOSED_FENCE_REJECTION = "Unclosed fenced code block"
PAGE_TIMEOUT_REJECTION_PREFIX = "LLM page timeout after"
PAGE_SERVER_ERROR_REJECTION_PREFIX = "LLM page server error"

_PAGE_LOCAL_QUALITY_REJECTIONS = frozenset(
    {
        "Insufficient prose content",
        GENERATOR_META_REJECTION,
        EMPTY_CONTENT_REJECTION,
        UNCLOSED_FENCE_REJECTION,
    }
)

_CITE_RE = re.compile(r"<cite>\s*([^<]+?)\s*</cite>", re.IGNORECASE)
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
    """Return True when overview page states sample identity or resolved identity."""
    readme = read_readme_text(repo_root)
    page_lower = markdown.lower()
    readme_lower = readme.lower()
    if "conduit" in readme_lower or "realworld" in readme_lower:
        has_product = "conduit" in page_lower or "realworld" in page_lower
        has_fastapi = "fastapi" in page_lower
        return has_product and has_fastapi
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
_BIN_FLAG_RE = re.compile(r"\./bin/([A-Za-z0-9_-]+)\s+(--?[A-Za-z0-9_-]+)")
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
        if _text_has_install_clue(cited):
            return True
        for run_start, run_end in run_ranges:
            if start <= run_end and end >= run_start:
                return True
    if not found_readme:
        return False
    return not run_ranges


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
            if not _cmd_package_exists(repo_root, match.group(1)):
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


_GENERIC_GO_INSTALL = re.compile(
    r"\bgo\s+(?:build|run|mod\s+download)\s+(?:-o\s+\S+\s+)?(?:\.|./\.\.\.)\b",
    re.IGNORECASE,
)
_DEMO_CMD_NAMES = frozenset({"custom-probe", "example", "demo", "scaffold", "hello"})
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
)


def _install_command_priority(command: str) -> tuple[int, str]:
    low = command.lower()
    score = 50
    if "podman-compose" in low or "docker compose" in low or "docker-compose" in low:
        score = 0
    elif "schema.sql" in low:
        score = 1
    elif "ccagent" in low:
        score = 2
    elif "curl" in low and "health" in low:
        score = 3
    elif low.startswith("make "):
        score = 4
    elif "go build" in low:
        score = 5
    if any(token in low for token in _DEMO_CMD_NAMES):
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
                _add(line)
        if re.search(r"^install:", text, re.M):
            _add("make install")
        if re.search(r"^up:", text, re.M):
            _add("make up")
    core_mains: list[Path] = []
    demo_mains: list[Path] = []
    for main in sorted(root.glob("cmd/*/main.go")):
        if main.parent.name.lower() in _DEMO_CMD_NAMES:
            demo_mains.append(main)
        else:
            core_mains.append(main)
    for main in core_mains or demo_mains:
        rel = main.relative_to(root).as_posix()
        _add(f"go build -o bin/{main.parent.name} ./{rel}")
    if (root / "db" / "schema.sql").is_file():
        _add("mysql < db/schema.sql")
    for name in ("README.md", "QUICKSTART.md"):
        path = root / name
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip().lstrip("$").strip()
            if not line or line.startswith("#"):
                continue
            for pattern in _REPO_INSTALL_LINE_PATTERNS:
                match = pattern.search(line)
                if not match:
                    continue
                command = " ".join(match.group(0).split()).rstrip(".,;:)")
                if command and len(command) <= 120:
                    _add(command)
    commands.sort(key=_install_command_priority)
    return commands[:limit]


def architecture_core_packages(repo_root: Path) -> list[str]:
    """Product packages an architecture page should cite when they exist."""
    preferred = (
        "cmd/ccagent",
        "internal/control",
        "internal/services",
        "internal/repository",
        "internal/exporter",
        "internal/agent",
        "internal/probe",
        "app/api/routes",
        "app/models",
    )
    found: list[str] = []
    for rel in preferred:
        if (repo_root / rel).exists():
            found.append(rel)
    return found


def has_architecture_core_citation(markdown: str, repo_root: Path) -> bool:
    """True when an architecture page cites real core packages, not only demos."""
    cores = architecture_core_packages(repo_root)
    if len(cores) < 2:
        return True
    cited = " ".join(
        match.group(1).replace("\\", "/") for match in _CITE_RE.finditer(markdown or "")
    ).lower()
    hits = sum(1 for rel in cores if rel.lower() in cited)
    return hits >= min(2, len(cores))


def has_data_model_source_citation(markdown: str, repo_root: Path) -> bool:
    """True when a data-model page cites models/ or schema.sql when those exist."""
    needs: list[str] = []
    if (repo_root / "internal" / "models").is_dir():
        needs.append("internal/models")
    if (repo_root / "db" / "schema.sql").is_file():
        needs.append("db/schema.sql")
    if (repo_root / "app" / "models").is_dir():
        needs.append("app/models")
    if not needs:
        return True
    cited = " ".join(
        match.group(1).replace("\\", "/") for match in _CITE_RE.finditer(markdown or "")
    ).lower()
    return any(need.lower() in cited for need in needs)


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
