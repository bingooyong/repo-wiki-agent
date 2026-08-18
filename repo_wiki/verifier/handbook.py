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

_PAGE_LOCAL_QUALITY_REJECTIONS = frozenset(
    {
        "Insufficient prose content",
        GENERATOR_META_REJECTION,
        EMPTY_CONTENT_REJECTION,
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
)


def contains_generator_meta(markdown: str) -> bool:
    """Return True when markdown contains generator self-description phrases."""
    if not markdown:
        return False
    lowered = markdown.lower()
    return any(phrase.lower() in lowered for phrase in HANDBOOK_META_PHRASES)


def is_page_local_quality_rejection(reason: str | None) -> bool:
    """Quality rejects after HTTP 200 are page-local, not provider outages."""
    return reason in _PAGE_LOCAL_QUALITY_REJECTIONS


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


def overview_identity_satisfied(markdown: str, repo_root: Path) -> bool:
    """Return True when overview page states sample identity or resolved identity."""
    readme = read_readme_text(repo_root)
    page_lower = markdown.lower()
    readme_lower = readme.lower()
    if "conduit" in readme_lower or "realworld" in readme_lower:
        has_product = "conduit" in page_lower or "realworld" in page_lower
        has_fastapi = "fastapi" in page_lower
        return has_product and has_fastapi
    from repo_wiki.planner.identity import resolve_repository_identity

    identity = resolve_repository_identity(repo_root)
    token = (identity.display_name or identity.name or "").strip()
    if not token:
        return False
    return token.lower() in page_lower


def install_run_clue_count(markdown: str) -> int:
    return sum(1 for _name, pattern in _INSTALL_CLUE_PATTERNS if pattern.search(markdown))


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
