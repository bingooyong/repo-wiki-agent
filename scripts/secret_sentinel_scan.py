#!/usr/bin/env python3
"""Deterministic artifact-wide secret sentinel scanner.

This script is intentionally local-only and dependency-free so CI can run it
against generated run/release artifacts before publication.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

MAX_TEXT_BYTES = 5 * 1024 * 1024
READ_BYTES = MAX_TEXT_BYTES + 1

IGNORED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".tox",
    ".nox",
    ".cache",
    "dist",
    "build",
    "site-packages",
    "coverage",
    ".coverage",
}

BINARY_EXTENSIONS = {
    ".7z",
    ".avif",
    ".bin",
    ".bmp",
    ".class",
    ".dll",
    ".dmg",
    ".docx",
    ".dylib",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".lockb",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".pyc",
    ".rar",
    ".so",
    ".sqlite",
    ".tar",
    ".tgz",
    ".wasm",
    ".webp",
    ".whl",
    ".zip",
}

TEXT_EXTENSIONS = {
    "",
    ".cfg",
    ".cmd",
    ".conf",
    ".css",
    ".csv",
    ".env",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsonl",
    ".log",
    ".md",
    ".mjs",
    ".py",
    ".rst",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

# Keep fixture sentinel values split so scanning this source file does not report
# its own test fixtures as artifact leaks.
SENTINEL_VALUES = (
    "repo-wiki-sentinel-" + "sk-" + "0123456789abcdef0123456789abcdef",
    "repo-wiki-sentinel-" + "token-abcdef0123456789abcdef0123456789",
    "repo-wiki-sentinel-"
    + "jwt-"
    + "eyJhbGciOiJIUzI1NiJ9"
    + "."
    + "eyJzdWIiOiJzZW50aW5lbCJ9"
    + ".signature",
)

_PLACEHOLDER_RE = re.compile(
    r"^(?:"
    r"<[^>]+>|"
    r"\$\{[^}]+\}|"
    r"\$[A-Z_][A-Z0-9_]*|"
    r"%[A-Z_][A-Z0-9_]*%|"
    r"\*+|"
    r"x+|"
    r"your[-_a-z0-9]*|"
    r"example[-_a-z0-9]*|"
    r"placeholder[-_a-z0-9]*|"
    r"redacted|"
    r"REDACTED"
    r")$",
    re.IGNORECASE,
)
_ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]
    secret_group: int = 1


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    column: int
    rule: str
    evidence: str


RULES: tuple[Rule, ...] = (
    Rule(
        "sentinel-value",
        re.compile("|".join(re.escape(value) for value in SENTINEL_VALUES)),
        secret_group=0,
    ),
    Rule("openai-style-sk", re.compile(r"\b(sk-[A-Za-z0-9_-]{20,})\b")),
    Rule("bearer-token", re.compile(r"(?i)\bbearer\s+([A-Za-z0-9._-]{24,})\b")),
    Rule(
        "labeled-api-key",
        re.compile(
            r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|password|credential)\b"
            r"\s*[:=]\s*['\"]?([^'\"\s,;]{16,})['\"]?"
        ),
        secret_group=2,
    ),
    Rule(
        "jwt-token",
        re.compile(r"\b(eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,})\b"),
    ),
    Rule("aws-access-key-id", re.compile(r"\b(AKIA[0-9A-Z]{16})\b")),
)


def is_probable_placeholder(value: str) -> bool:
    cleaned = value.strip().strip("'\"` ,;")
    if not cleaned:
        return True
    if _PLACEHOLDER_RE.match(cleaned):
        return True
    if _ENV_NAME_RE.match(cleaned):
        return True
    return False


def is_high_signal_secret(rule_name: str, value: str) -> bool:
    if rule_name == "sentinel-value":
        return True
    cleaned = value.strip().strip("'\"` ,;")
    if is_probable_placeholder(cleaned):
        return False
    if rule_name in {"openai-style-sk", "bearer-token", "jwt-token", "aws-access-key-id"}:
        return True
    has_letter = bool(re.search(r"[A-Za-z]", cleaned))
    has_digit = bool(re.search(r"\d", cleaned))
    long_enough = len(cleaned) >= 20
    return has_letter and has_digit and long_enough


def redact_evidence(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"[REDACTED len={len(value)} sha256={digest}]"


def redact_secret_substrings(value: str) -> str:
    """Redact high-signal secret substrings without hiding normal context."""

    spans: list[tuple[int, int]] = []
    for rule in RULES:
        for match in rule.pattern.finditer(value):
            secret = match.group(rule.secret_group)
            if is_high_signal_secret(rule.name, secret):
                spans.append(match.span(rule.secret_group))

    if not spans:
        return value

    redacted_parts: list[str] = []
    cursor = 0
    for start, end in sorted(spans, key=lambda span: (span[0], -(span[1] - span[0]))):
        if start < cursor:
            continue
        redacted_parts.append(value[cursor:start])
        redacted_parts.append(redact_evidence(value[start:end]))
        cursor = end
    redacted_parts.append(value[cursor:])
    return "".join(redacted_parts)


def render_path(path: Path) -> str:
    return redact_secret_substrings(path.as_posix())


def is_binary_bytes(data: bytes) -> bool:
    if not data:
        return False
    if b"\0" in data:
        return True
    sample = data[:4096]
    non_text = sum(1 for byte in sample if byte < 9 or (13 < byte < 32))
    return non_text / len(sample) > 0.20


def should_skip_path(path: Path) -> bool:
    return (
        any(part in IGNORED_DIR_NAMES for part in path.parts)
        or path.suffix.lower() in BINARY_EXTENSIONS
    )


def iter_files(paths: Sequence[Path]) -> Iterator[Path]:
    for input_path in paths:
        path = input_path.resolve()
        if not path.exists():
            raise FileNotFoundError(str(input_path))
        if path.is_file():
            if not should_skip_path(path):
                yield path
            continue
        for child in sorted(path.rglob("*")):
            if child.is_dir():
                continue
            if should_skip_path(child):
                continue
            if child.suffix.lower() not in TEXT_EXTENSIONS:
                # Unknown extensions are still binary-sniffed by scan_file if they
                # are explicitly passed, but recursive scans stay on reasonable text artifacts.
                continue
            yield child


def line_and_column(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    line_start = text.rfind("\n", 0, offset) + 1
    return line, offset - line_start + 1


def scan_text(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for rule in RULES:
        for match in rule.pattern.finditer(text):
            value = match.group(rule.secret_group)
            if not is_high_signal_secret(rule.name, value):
                continue
            line, column = line_and_column(text, match.start(rule.secret_group))
            findings.append(
                Finding(
                    path=path,
                    line=line,
                    column=column,
                    rule=rule.name,
                    evidence=redact_evidence(value),
                )
            )
    return findings


def scan_file(path: Path) -> list[Finding]:
    data = path.read_bytes()[:READ_BYTES]
    if len(data) > MAX_TEXT_BYTES or is_binary_bytes(data):
        return []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = data.decode("utf-16")
        except UnicodeDecodeError:
            return []
    return scan_text(path, text)


def scan_paths(paths: Sequence[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files(paths):
        findings.extend(scan_file(path))
    return sorted(
        findings, key=lambda item: (item.path.as_posix(), item.line, item.column, item.rule)
    )


def format_findings(findings: Iterable[Finding]) -> str:
    lines = []
    for finding in findings:
        lines.append(
            f"{render_path(finding.path)}:{finding.line}:{finding.column}: "
            f"{finding.rule}: {finding.evidence}"
        )
    return "\n".join(lines)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan generated artifacts for high-signal API key/token leaks."
    )
    parser.add_argument("paths", nargs="+", type=Path, help="File or directory paths to scan")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        findings = scan_paths(args.paths)
    except FileNotFoundError as exc:
        print(f"secret-sentinel: path not found: {exc}", file=sys.stderr)
        return 2

    if findings:
        print(format_findings(findings))
        print(f"secret-sentinel: FAIL ({len(findings)} finding(s))", file=sys.stderr)
        return 1

    print("secret-sentinel: OK (0 findings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
