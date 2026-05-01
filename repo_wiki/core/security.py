from __future__ import annotations

import re
from fnmatch import fnmatch
from pathlib import Path
from typing import NamedTuple

from repo_wiki.core.config import RepoWikiConfig


class SecurityWarning(NamedTuple):
    code: str
    message: str
    path: str | None = None


_SENSITIVE_PATTERNS: dict[str, re.Pattern[str]] = {
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "api_key_assignment": re.compile(
        r"(?i)\b(api[_-]?key)\b\s*[:=]\s*[\"']?([A-Za-z0-9_\-]{12,})[\"']?"
    ),
    "token_assignment": re.compile(
        r"(?i)\b(access[_-]?token|auth[_-]?token|secret|password)\b\s*[:=]\s*[\"']?([^\s\"']{8,})[\"']?"
    ),
    "private_key_block": re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
    ),
    "connection_string": re.compile(r"\b(?:postgres|mysql|mongodb|redis)://[^\s\"']+"),
    "prod_domain_hint": re.compile(
        r"(?i)\b(?:prod|production)\.[a-z0-9.-]+\.[a-z]{2,}\b"
    ),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}

_BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".zip",
    ".gz",
    ".jar",
    ".class",
    ".so",
    ".dylib",
    ".exe",
    ".dll",
    ".bin",
}


def should_scan(path: Path, config: RepoWikiConfig, root: Path | None = None) -> bool:
    rel = path
    if root is not None:
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path
    rel_str = rel.as_posix()

    for deny_dir in config.security.deny_dirs:
        normalized = deny_dir.strip("/")
        if rel_str == normalized or rel_str.startswith(f"{normalized}/"):
            return False

    for pattern in config.security.deny_globs:
        if fnmatch(rel_str, pattern) or fnmatch(rel.name, pattern):
            return False

    return True


def is_binary_path(path: Path) -> bool:
    return path.suffix.lower() in _BINARY_EXTENSIONS


def is_binary_bytes(data: bytes) -> bool:
    if not data:
        return False
    if b"\0" in data:
        return True
    sample = data[:2048]
    non_text_ratio = sum(1 for byte in sample if byte < 9 or (13 < byte < 32)) / len(sample)
    return non_text_ratio > 0.2


def sanitize_text(text: str, path: str | None = None) -> tuple[str, list[SecurityWarning]]:
    sanitized = text
    warnings: list[SecurityWarning] = []
    for code, pattern in _SENSITIVE_PATTERNS.items():
        if pattern.search(sanitized):
            sanitized = pattern.sub("[REDACTED]", sanitized)
            warnings.append(SecurityWarning(code=code, message=f"Sensitive content redacted ({code})", path=path))
    return sanitized, warnings


def security_warnings(text: str, path: str | None = None) -> list[SecurityWarning]:
    _, warnings = sanitize_text(text, path=path)
    return warnings
