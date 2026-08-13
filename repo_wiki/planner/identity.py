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
_GENERIC_README_TITLES = frozenset({"readme", "overview", "index", "documentation", "docs"})
_RST_DECORATION_RE = re.compile(r"^[=\-`:.'\"~^_*+#]{3,}$")


def _iter_readme_files(root: Path) -> list[Path]:
    found: dict[str, Path] = {}
    for name in _README_CANDIDATE_NAMES:
        path = root / name
        if path.is_file():
            found[path.name] = path
    for path in sorted(root.glob("README*")):
        if path.is_file() and path.name not in found:
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


def _parse_readme_identity(content: str) -> tuple[str | None, str | None]:
    substantial: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("<!--") or stripped.startswith(".. "):
            continue
        if _RST_DECORATION_RE.fullmatch(stripped):
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
            if not stripped:
                continue
        substantial.append(stripped)
        if len(substantial) >= 4:
            break
    if not substantial:
        return None, None
    first = substantial[0]
    title: str | None = None if first.lower() in _GENERIC_README_TITLES else first
    body_parts = substantial[1:] if title else substantial
    if not body_parts and title:
        description: str | None = title
    else:
        joined = " ".join(body_parts).strip()
        description = joined or title
    if description:
        description = description[:200]
    return title, description


def resolve_repository_identity(root: Path) -> RepositoryIdentity:
    """Resolve repository identity from metadata files.

    This function reads multiple sources to build a complete picture
    of the repository identity, preferring explicit metadata over
    generic workspace names.

    Args:
        root: The repository root path

    Returns:
        RepositoryIdentity with resolved metadata
    """
    name_candidates: list[tuple[str, str | None]] = []

    # 1. Read package.json if exists
    package_json = root / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            if name := data.get("name"):
                name_candidates.append((name, "package.json"))
            if data.get("version"):
                pass  # handled below
        except (json.JSONDecodeError, OSError):
            pass

    # 2. Read pyproject.toml if exists
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8", errors="ignore")
        # Look for name in [project] section
        match = re.search(r'^\s*name\s*=\s*"([^"]+)"', content, re.MULTILINE)
        if match:
            name_candidates.append((match.group(1), "pyproject.toml"))
        # Look for version
        match = re.search(r'^\s*version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        if match:
            pass  # handled below

    # 3. Read pom.xml if exists
    pom_xml = root / "pom.xml"
    if pom_xml.exists():
        content = pom_xml.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"<artifactId>([^<]+)</artifactId>", content)
        if match:
            name_candidates.append((match.group(1), "pom.xml"))
        match = re.search(r"<version>([^<]+)</version>", content)
        if match and match.group(1) != "${project.version}":
            pass  # handled below

    # 4. Try git remote for name
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
                # Extract repo name from URL
                if match := re.search(r"/([^/]+?)(?:\.git)?$", url):
                    git_name = match.group(1)
                    name_candidates.append((git_name, "git-remote"))
        except (subprocess.TimeoutExpired, OSError):
            pass

    readme_title, readme_description = _readme_title_and_description(root)
    if readme_title:
        name_candidates.append((readme_title, "readme"))

    # 5. Fallback to directory name
    name_candidates.append((root.name, "directory-name"))

    # Select the best name (prefer explicit metadata, then README title, then git/directory)
    name_priority = [
        "package.json",
        "pyproject.toml",
        "pom.xml",
        "readme",
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

    # Read description from package.json first (explicit metadata)
    description: str | None = None
    version: str | None = None
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            if desc := data.get("description"):
                description = desc[:200]
        except (json.JSONDecodeError, OSError):
            pass

    # Then try README if no description from package.json. Never use AGENTS.md,
    # init stubs, or eval reports as product identity.
    if not description and readme_description:
        description = readme_description[:200]

    # Read version from various sources.
    for metadata_path in [package_json, pyproject, pom_xml]:
        if metadata_path.exists():
            content = metadata_path.read_text(encoding="utf-8", errors="ignore")
            if metadata_path.suffix == ".json":
                try:
                    data = json.loads(content)
                    if v := data.get("version"):
                        version = str(v)
                        break
                except json.JSONDecodeError:
                    continue
            elif metadata_path.name == "pyproject.toml":
                match = re.search(r'^\s*version\s*=\s*"([^"]+)"', content, re.MULTILINE)
                if match:
                    version = match.group(1)
                    break
            elif metadata_path.name == "pom.xml":
                match = re.search(r"<version>([^<]+)</version>", content)
                if match and match.group(1) != "${project.version}":
                    version = match.group(1)
                    break

    return RepositoryIdentity(
        name=best_name,
        display_name=best_name if best_source == "readme" else _human_readable_name(best_name),
        root_path=str(root.resolve()),
        language="unknown",
        framework="unknown",
        package_manager="unknown",
        version=version,
        description=description,
        entry_points=[],
        source_digest=None,
    )


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
