"""Repository identity resolver.

Resolves real repository identity from metadata and source evidence.
Reads: git root, README, pom.xml, package.json, pyproject.toml, directory names.

Preference order for name resolution:
1. Explicit metadata (package.json name, pom.xml artifactId, etc.)
2. Git remote URL
3. Directory name fallback
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from repo_wiki.planner.schema import RepositoryIdentity

_README_CANDIDATE_NAMES = (
    "README.md",
    "README.rst",
    "README.txt",
    "README",
    "README.zh.md",
    "README_CN.md",
    "README_en.md",
)
_GENERIC_README_TITLES = frozenset(
    {
        "readme",
        "overview",
        "index",
        "documentation",
        "docs",
        "quickstart",
        "installation",
        "install",
        "usage",
    }
)
_README_COMMAND_RE = re.compile(
    r"^(export |docker |podman |poetry |alembic |uvicorn |touch |echo |mysql |git |go |\$ )"
)
_SECONDARY_README_MARKERS = (
    "scaffold",
    "template",
    "boilerplate",
    "podman",
    "docker",
    "contrib",
)
_RST_DECORATION_RE = re.compile(r"^[=\-`:.'\"~^_*+#]{3,}$")
_RST_FIELD_LIST_RE = re.compile(r"^:[a-zA-Z][-a-zA-Z0-9_]*:")
_HTTP_URL_RE = re.compile(r"https?://[^\s)<>\"'\]]+", re.IGNORECASE)
_IMG_SHIELDS_HOST = "img.shields.io"


def has_img_shields_io_url(text: str) -> bool:
    """True only when a URL hostname is exactly img.shields.io."""
    for raw in _HTTP_URL_RE.findall(text):
        hostname = (urlparse(raw).hostname or "").lower()
        if hostname == _IMG_SHIELDS_HOST:
            return True
    return False


_RST_SUBSTITUTION_LINE_RE = re.compile(r"^(\|[^|]+\|\s*)+$")
_README_NOTE_RE = re.compile(
    r"More modern and relevant examples can be found in",
    re.IGNORECASE,
)
_PYPROJECT_STRING_FIELD_RE = re.compile(
    r'^\s*(name|version|description)\s*=\s*"([^"]+)"', re.MULTILINE
)


def _iter_readme_files(root: Path) -> list[Path]:
    found: dict[str, Path] = {}
    for name in _README_CANDIDATE_NAMES:
        path = root / name
        if path.is_file():
            found[path.name] = path
    for path in sorted(root.glob("README*")):
        if not path.is_file() or path.name in found:
            continue
        lowered = path.name.lower()
        if any(marker in lowered for marker in _SECONDARY_README_MARKERS):
            continue
        found[path.name] = path
    ordered: list[Path] = []
    for name in _README_CANDIDATE_NAMES:
        candidate = found.get(name)
        if candidate is not None:
            ordered.append(candidate)
    for extra in found.values():
        if extra not in ordered:
            ordered.append(extra)
    return ordered


def _pyproject_string_fields(content: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for match in _PYPROJECT_STRING_FIELD_RE.finditer(content):
        fields.setdefault(match.group(1), match.group(2))
    return fields


def _is_markdown_badge_line(stripped: str) -> bool:
    if stripped.startswith("[![") or stripped.startswith("![]("):
        return True
    return has_img_shields_io_url(stripped)


def _is_rst_noise_line(stripped: str) -> bool:
    if not stripped or stripped.startswith("<!--") or stripped.startswith(".. "):
        return True
    if _is_markdown_badge_line(stripped):
        return True
    if stripped in {"|", ".."}:
        return True
    if _RST_DECORATION_RE.fullmatch(stripped):
        return True
    if _RST_FIELD_LIST_RE.match(stripped):
        return True
    if _RST_SUBSTITUTION_LINE_RE.fullmatch(stripped):
        return True
    return False


def _is_product_sentence(text: str | None) -> bool:
    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.casefold() in _GENERIC_README_TITLES:
        return False
    if _README_COMMAND_RE.match(stripped):
        return False
    if ":target:" in stripped or ":alt:" in stripped:
        return False
    if _is_markdown_badge_line(stripped):
        return False
    if _RST_FIELD_LIST_RE.match(stripped) or _RST_SUBSTITUTION_LINE_RE.fullmatch(stripped):
        return False
    if re.search(
        r"more modern|other repositories|can be found in|changelog"
        r"|^(?:first,|then |run |set environment|create database|for example using|a stray \d)",
        stripped,
        flags=re.I,
    ):
        return False
    return True


def _looks_like_heading(line: str) -> bool:
    if line.lower() in _GENERIC_README_TITLES:
        return False
    if _is_rst_noise_line(line) or _RST_SUBSTITUTION_LINE_RE.fullmatch(line):
        return False
    if line.startswith("|") and line.endswith("|"):
        return False
    if len(line) > 80 or line.endswith("."):
        return False
    return True


def _readme_title_and_description(root: Path) -> tuple[str | None, str | None]:
    """Extract product title and description from README, never from stubs or eval notes."""
    for readme in _iter_readme_files(root):
        try:
            content = readme.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        title, description = _parse_readme_identity(content)
        if title or description:
            return title, description
    return None, None


def _trim_identity_description(text: str, limit: int = 200) -> str:
    """Keep a complete sentence/word. Never emit a mid-word stump like ``in oth``."""
    stripped = (text or "").strip()
    if len(stripped) <= limit:
        return stripped
    cut = stripped[:limit]
    sentence = max(cut.rfind("。"), cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if sentence >= 40:
        return cut[: sentence + 1].strip()
    space = cut.rfind(" ")
    if space >= 40:
        return cut[:space].rstrip(" ,;:") + "."
    return cut.rstrip()


_HTML_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_HTML_ALIGN_P_RE = re.compile(r"<p[^>]*align[^>]*>.*?</p>", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"</?[^>]+>")
_NOTE_LINE_RE = re.compile(
    r"^(?:\*\*)?(?:NOTE|WARNING|IMPORTANT|CAUTION)\b",
    re.IGNORECASE,
)
_CHANGELOG_BULLET_RE = re.compile(r"^[-*]\s+v?\d+")
_ARCHIVED_LINE_RE = re.compile(r"\barchiv|\bunmaintained|no longer maintained", re.I)
_NUMBERED_HEADING_RE = re.compile(r"^\d+\.\s+\S")
_VERSION_BULLET_RE = re.compile(
    r"^(?:[-*]\s+)?(?:\*\*)?v\d+(?:\.\d+)*(?:\*\*)?\s*[:：]",
    re.IGNORECASE,
)


def _flatten_h1(match: re.Match[str]) -> str:
    title = " ".join(_HTML_TAG_RE.sub(" ", match.group(1)).split()).strip()
    return f"# {title}\n" if title else ""


def _readme_visible_lines(content: str) -> list[str]:
    text = _HTML_ALIGN_P_RE.sub("", content or "")
    text = _HTML_H1_RE.sub(_flatten_h1, text)
    text = _HTML_TAG_RE.sub(" ", text)
    lines: list[str] = []
    in_note_block = False
    for raw in text.splitlines():
        stripped = " ".join(raw.split()).strip()
        if not stripped or re.fullmatch(r"#+", stripped):
            in_note_block = False
            continue
        if (
            stripped.startswith(">")
            or _NOTE_LINE_RE.match(stripped)
            or _README_NOTE_RE.search(stripped)
        ):
            in_note_block = True
            continue
        if in_note_block:
            continue
        if _ARCHIVED_LINE_RE.search(stripped) or _CHANGELOG_BULLET_RE.match(stripped):
            continue
        heading = stripped.lstrip("#").strip()
        if heading and (
            _is_rst_noise_line(heading)
            or _RST_SUBSTITUTION_LINE_RE.fullmatch(heading)
            or _NUMBERED_HEADING_RE.match(heading)
            or _VERSION_BULLET_RE.match(heading)
        ):
            continue
        if _VERSION_BULLET_RE.match(stripped) or _NUMBERED_HEADING_RE.match(
            stripped.lstrip("#").strip()
        ):
            continue
        if (
            _is_rst_noise_line(stripped)
            or _README_COMMAND_RE.match(stripped)
            or _is_markdown_badge_line(stripped)
            or stripped.startswith(("- ", "* ", "+ "))
        ):
            continue
        lines.append(stripped)
    return lines


def _parse_readme_identity(content: str) -> tuple[str | None, str | None]:
    lines = _readme_visible_lines(content)
    title: str | None = None
    body: list[str] = []
    for line in lines:
        heading = line.lstrip("#").strip() if line.startswith("#") else ""
        if heading:
            if heading.casefold() in _GENERIC_README_TITLES:
                break
            if (
                _is_rst_noise_line(heading)
                or _NUMBERED_HEADING_RE.match(heading)
                or _VERSION_BULLET_RE.match(heading)
                or not _looks_like_heading(heading)
            ):
                continue
            if title is None:
                title = heading
            continue
        if line.casefold() in _GENERIC_README_TITLES:
            break
        if _VERSION_BULLET_RE.match(line) or _NUMBERED_HEADING_RE.match(line):
            continue
        if _looks_like_heading(line) and title is None:
            title = line
            continue
        if _is_product_sentence(line):
            body.append(line)
            break
    description = body[0] if body else title
    if description:
        description = _trim_identity_description(description)
    if not _is_product_sentence(description):
        description = None
    return title, description


def resolve_repository_identity(root: Path) -> RepositoryIdentity:
    """Resolve identity from README h1, then package manifests, then directory name."""
    name_candidates: list[tuple[str, str | None]] = []

    package_json = root / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            if name := data.get("name"):
                name_candidates.append((name, "package.json"))
        except (json.JSONDecodeError, OSError):
            pass

    pyproject = root / "pyproject.toml"
    pyproject_fields: dict[str, str] = {}
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8", errors="ignore")
        pyproject_fields = _pyproject_string_fields(content)
        if name := pyproject_fields.get("name"):
            name_candidates.append((name, "pyproject.toml"))

    pom_xml = root / "pom.xml"
    if pom_xml.exists():
        content = pom_xml.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"<artifactId>([^<]+)</artifactId>", content)
        if match:
            name_candidates.append((match.group(1), "pom.xml"))

    git_root = root / ".git"
    if git_root.exists():
        try:
            remote_url = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if remote_url.returncode == 0:
                url = remote_url.stdout.strip()
                if match := re.search(r"/([^/]+?)(?:\.git)?$", url):
                    git_name = match.group(1)
                    name_candidates.append((git_name, "git-remote"))
        except (subprocess.TimeoutExpired, OSError):
            pass

    readme_title, readme_description = _readme_title_and_description(root)
    if readme_title:
        name_candidates.append((readme_title, "readme"))

    name_candidates.append((root.name, "directory-name"))

    name_priority = [
        "readme",
        "package.json",
        "pyproject.toml",
        "pom.xml",
        "git-remote",
        "directory-name",
    ]
    best_name = None
    best_source = None
    for source in name_priority:
        for candidate, src in name_candidates:
            if src == source and candidate:
                best_name = candidate
                best_source = source
                break
        if best_name:
            break

    if not best_name:
        best_name = "unknown"
        best_source = "fallback"

    package_name = next(
        (
            candidate
            for candidate, src in name_candidates
            if src in {"package.json", "pyproject.toml", "pom.xml"}
        ),
        None,
    )

    description: str | None = None
    description_source = ""
    version: str | None = None
    version_source = ""
    if _is_product_sentence(readme_description):
        description = (readme_description or "")[:200]
        description_source = "readme"
    if not description and package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            if desc := data.get("description"):
                description = desc[:200]
                description_source = "package.json"
        except (json.JSONDecodeError, OSError):
            pass
    if not _is_product_sentence(description):
        pyproject_description = pyproject_fields.get("description")
        if _is_product_sentence(pyproject_description):
            description = (pyproject_description or "")[:200]
            description_source = "pyproject.toml"

    for metadata_path in [package_json, pyproject, pom_xml]:
        if metadata_path.exists():
            content = metadata_path.read_text(encoding="utf-8", errors="ignore")
            if metadata_path.suffix == ".json":
                try:
                    data = json.loads(content)
                    if v := data.get("version"):
                        version = str(v)
                        version_source = "package.json"
                        break
                except json.JSONDecodeError:
                    continue
            elif metadata_path.name == "pyproject.toml":
                if v := pyproject_fields.get("version"):
                    version = v
                    version_source = "pyproject.toml"
                    break
            elif metadata_path.name == "pom.xml":
                match = re.search(r"<version>([^<]+)</version>", content)
                if match and match.group(1) != "${project.version}":
                    version = match.group(1)
                    version_source = "pom.xml"
                    break

    if not version:
        version = _latest_product_version(root)
        if version:
            version_source = "git-tag"

    return RepositoryIdentity(
        name=package_name or best_name,
        display_name=best_name if best_source == "readme" else _human_readable_name(best_name),
        root_path=str(root.resolve()),
        language="unknown",
        framework="unknown",
        package_manager="unknown",
        version=version,
        description=description,
        entry_points=[],
        source_digest=None,
        identity_sources={
            "name": str(
                next(
                    (
                        src
                        for candidate, src in name_candidates
                        if candidate == (package_name or best_name) and src
                    ),
                    best_source,
                )
                or ""
            ),
            "display_name": "readme" if best_source == "readme" else (best_source or ""),
            "version": version_source,
            "description": description_source,
        },
    )


def _latest_product_version(root: Path) -> str | None:
    """Git tag only. Never read README/changelog prose or go.mod toolchain lines."""
    try:
        tagged = subprocess.run(
            ["git", "-C", str(root), "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            check=False,
        )
        if tagged.returncode == 0:
            hit = re.search(r"v?(\d+\.\d+(?:\.\d+)?)", tagged.stdout.strip())
            if hit:
                return hit.group(1)
    except OSError:
        return None
    return None


def _human_readable_name(name: str) -> str:
    """Convert a slug/name to human-readable format.

    Examples:
        repo-wiki -> Repo Wiki
        reference-repo -> Reference Repo
        my-awesome-project -> My Awesome Project
    """
    # Replace hyphens, underscores, dots with spaces
    result = re.sub(r"[-_.]+", " ", name)

    # Preserve uppercase acronyms (like AI, API, WIKI) by protecting them
    # First, replace spaces around them with a placeholder
    protected = re.sub(r"\b([A-Z]{2,})\b", lambda m: m.group(1).replace(" ", "_"), result)

    # Split and capitalize each word, preserving known acronyms
    def capitalize_word(word: str) -> str:
        # If word is all uppercase (acronym), preserve it
        if word.isupper() and len(word) > 1:
            return word
        return word.capitalize()

    result = " ".join(capitalize_word(word) for word in result.split())
    return result if result else name


def detect_language_and_framework(root: Path) -> tuple[str, str]:
    """Detect primary language and framework from file patterns.

    Returns:
        tuple of (language, framework)
    """
    language_counts: dict[str, int] = {}
    framework_signals: dict[str, list[str]] = {
        "fastapi": ["fastapi"],
        "flask": ["flask"],
        "django": ["django"],
        "nestjs": ["@nestjs"],
        "express": ["express"],
        "fastify": ["fastify"],
        "gin": ["gin-gonic/gin"],
        "fiber": ["gofiber/fiber"],
    }
    detected_framework = "unknown"

    for path in root.rglob("*"):
        if not path.is_file() or path.name.startswith("."):
            continue
        suffix = path.suffix.lower()
        if suffix == ".py":
            language_counts["python"] = language_counts.get("python", 0) + 1
        elif suffix in {".ts", ".tsx"}:
            language_counts["typescript"] = language_counts.get("typescript", 0) + 1
        elif suffix in {".js", ".jsx"}:
            language_counts["javascript"] = language_counts.get("javascript", 0) + 1
        elif suffix == ".go":
            language_counts["golang"] = language_counts.get("golang", 0) + 1
        elif suffix in {".java", ".kt"}:
            language_counts["jvm"] = language_counts.get("jvm", 0) + 1

        # Check for framework signals in package files
        if path.name in {"package.json", "requirements.txt", "go.mod"}:
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
            for framework, signals in framework_signals.items():
                if detected_framework == "unknown" and any(signal in content for signal in signals):
                    detected_framework = framework

    language = "unknown"
    if language_counts:
        language = max(language_counts, key=lambda name: language_counts[name])
    return language, detected_framework


def detect_package_manager(root: Path) -> str:
    """Detect primary package manager from lock files.

    Returns:
        package manager name or "unknown"
    """
    checks = {
        "pnpm": "pnpm-lock.yaml",
        "yarn": "yarn.lock",
        "npm": "package-lock.json",
        "poetry": "poetry.lock",
        "pip": "requirements.txt",
        "go": "go.sum",
        "maven": "pom.xml",
        "gradle": "build.gradle",
    }
    for manager, marker in checks.items():
        if (root / marker).exists():
            return manager
    return "unknown"
