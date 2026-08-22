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
    return bool(reason) and reason.startswith(PAGE_TIMEOUT_REJECTION_PREFIX)


def page_timeout_rejection(seconds: float) -> str:
    return f"{PAGE_TIMEOUT_REJECTION_PREFIX} {seconds:.1f}s"


def is_page_server_error_rejection(reason: str | None) -> bool:
    """True for ``LLM page server error 529: ...`` page-local rewrites."""
    return bool(reason) and reason.startswith(PAGE_SERVER_ERROR_REJECTION_PREFIX)


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
    for rel in ("pyproject.toml", "package.json"):
        path = repo_root / rel
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
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


def has_api_routes_citation(markdown: str) -> bool:
    for match in _CITE_RE.finditer(markdown):
        path = match.group(1).split(":")[0].replace("\\", "/").lower()
        if "api/routes" in path:
            return True
    return False
