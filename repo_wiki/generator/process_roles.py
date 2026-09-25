"""Derive process/binary role facts from the repository being documented."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_DATA_PLANE_RE = re.compile(
    r"data-plane|dataplane|execution pool|probe execution",
    re.IGNORECASE,
)
_CONTROL_PLANE_RE = re.compile(
    r"control-plane|control plane|EstablishTunnel|grpc-listen",
    re.IGNORECASE,
)
_TUNNEL_CLIENT_RE = re.compile(
    r"tunnel client|DialContext|grpc\.Dial\b",
    re.IGNORECASE,
)
_REST_ENTRY_RE = re.compile(
    r"NewController|ListenAndServe|http\.Handle|gin\.Default|fastapi\b",
    re.IGNORECASE,
)
_KEBAB_NAME_RE = re.compile(
    r"\b[a-z][a-z0-9]*-(?:agent|control|probe|server|daemon|exporter|worker)"
    r"(?:-[a-z0-9]+)*\b"
)
_ROLE_CLAIM_RE = re.compile(
    r"(?<![A-Za-z0-9_/])([A-Za-z][A-Za-z0-9_-]{2,})"
    r"(?:\s*(?:是|承担|负责|作为))"
    r"(?:\s*(?:主\s*)?(?:REST|数据面|控制面|隧道|gRPC|拨测))?",
)
_CMD_PATH_RE = re.compile(r"cmd/([A-Za-z][A-Za-z0-9_-]+)")
_CLAUSE_SPLIT_RE = re.compile(r"[，,；;。]")
_GENERIC_ROLE_SUBJECTS = frozenset(
    {
        "this",
        "that",
        "app",
        "api",
        "web",
        "http",
        "grpc",
        "rest",
        "main",
        "core",
        "the",
        "and",
        "for",
        "with",
        "from",
        "service",
        "server",
        "client",
        "router",
        "fastapi",
        "python",
        "conduit",
        "realworld",
        "readme",
        "alembic",
        "uvicorn",
    }
)


@dataclass(frozen=True)
class RepoProcess:
    name: str
    rel_main: str
    text: str


def discover_cmd_processes(root: Path | str | None) -> list[RepoProcess]:
    """Return cmd/* binaries that have Go sources."""
    if root is None:
        return []
    cmd = Path(root) / "cmd"
    if not cmd.is_dir():
        return []
    found: list[RepoProcess] = []
    for child in sorted(cmd.iterdir()):
        if not child.is_dir():
            continue
        gos = sorted(
            path
            for path in child.glob("*.go")
            if path.is_file() and not path.name.endswith("_test.go")
        )
        if not gos:
            continue
        main = next((path for path in gos if path.name == "main.go"), gos[0])
        try:
            text = main.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        extra: list[str] = []
        for sibling in gos:
            if sibling == main:
                continue
            try:
                extra.append(sibling.read_text(encoding="utf-8", errors="ignore")[:4000])
            except OSError:
                continue
        found.append(
            RepoProcess(
                name=child.name,
                rel_main=main.relative_to(Path(root)).as_posix(),
                text="\n".join([text, *extra]),
            )
        )
    return found


def derive_repo_process_names(root: Path | str | None) -> set[str]:
    """Names of binaries, packages, and process-like tokens found in this repo."""
    names = {item.name for item in discover_cmd_processes(root)}
    if root is None:
        return names
    base = Path(root)
    for folder in ("internal", "pkg", "app"):
        path = base / folder
        if not path.is_dir():
            continue
        names.add(folder)
        for child in path.iterdir():
            if child.is_dir() and child.name not in {"__pycache__", "tests", "test"}:
                names.add(child.name)
    for path in base.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {
            ".go",
            ".py",
            ".md",
            ".rst",
            ".yml",
            ".yaml",
            ".toml",
            ".sh",
        }:
            continue
        rel = path.relative_to(base).as_posix()
        if rel.startswith(".") or "/." in rel or ".repo-agent-eval" in rel.split("/"):
            continue
        if any(part in {"vendor", "node_modules", "__pycache__", ".git"} for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        names.update(_KEBAB_NAME_RE.findall(text))
    return names


def derive_process_role_facts(root: Path | str | None) -> str:
    """Positive role facts derived from cmd/* comments and what each serves/dials."""
    processes = discover_cmd_processes(root)
    if not processes:
        return ""
    control = next((item for item in processes if _is_control_plane(item)), None)
    rest = next((item for item in processes if _is_rest_entry(item)), None)
    facts: list[str] = []
    for item in processes:
        fact = _fact_for(item, control)
        if fact:
            facts.append(fact)
    data_plane = next((item for item in processes if _is_data_plane(item)), None)
    if data_plane and control and rest and data_plane.name != rest.name:
        facts.append(
            f"{data_plane.name} 主动拨号连向 {control.name} 的隧道，"
            f"不是被 {rest.name} 调度的拨测执行单元"
        )
    return "；".join(facts) + "。" if facts else ""


def unknown_process_mentions(markdown: str, allowed: set[str]) -> list[str]:
    """Process/binary names claimed in prose that are not in the documented repo."""
    text = markdown or ""
    found: set[str] = set()
    for match in _CMD_PATH_RE.finditer(text):
        name = match.group(1)
        if name not in allowed:
            found.add(name)
    for match in _KEBAB_NAME_RE.finditer(text):
        name = match.group(0)
        if name not in allowed and name.lower() not in _GENERIC_ROLE_SUBJECTS:
            found.add(name)
    for match in _ROLE_CLAIM_RE.finditer(text):
        name = match.group(1)
        if name.lower() in _GENERIC_ROLE_SUBJECTS:
            continue
        if name not in allowed:
            found.add(name)
    return sorted(found)


def strip_unknown_process_clauses(markdown: str, allowed: set[str]) -> str:
    """Drop clauses that name a process/binary absent from this repo."""
    if not markdown or not unknown_process_mentions(markdown, allowed):
        return markdown
    out_lines: list[str] = []
    for line in markdown.splitlines():
        if line.strip().startswith("```") or line.startswith("#"):
            out_lines.append(line)
            continue
        kept = _keep_known_process_clauses(line, allowed)
        if kept.strip() or not line.strip():
            out_lines.append(kept)
    rewritten = "\n".join(out_lines)
    rewritten = re.sub(r"[；;]{2,}", "；", rewritten)
    rewritten = re.sub(r"（\s*）", "", rewritten)
    if markdown.endswith("\n") and not rewritten.endswith("\n"):
        rewritten += "\n"
    return rewritten


def _keep_known_process_clauses(line: str, allowed: set[str]) -> str:
    if not unknown_process_mentions(line, allowed):
        return line
    parts = re.split(r"([，,；;。])", line)
    kept: list[str] = []
    index = 0
    while index < len(parts):
        chunk = parts[index]
        delim = parts[index + 1] if index + 1 < len(parts) else ""
        if chunk and unknown_process_mentions(chunk, allowed):
            index += 2
            continue
        kept.append(chunk)
        if delim:
            kept.append(delim)
        index += 2
    text = "".join(kept)
    text = re.sub(r"^[，,；;。\s]+", "", text)
    text = re.sub(r"[，,；;]{2,}", "；", text)
    return text.rstrip()


def _is_data_plane(item: RepoProcess) -> bool:
    return bool(_DATA_PLANE_RE.search(item.text))


def _is_control_plane(item: RepoProcess) -> bool:
    return bool(_CONTROL_PLANE_RE.search(item.text))


def _is_tunnel_client(item: RepoProcess) -> bool:
    return bool(_TUNNEL_CLIENT_RE.search(item.text))


def _is_rest_entry(item: RepoProcess) -> bool:
    return bool(_REST_ENTRY_RE.search(item.text))


def _fact_for(item: RepoProcess, control: RepoProcess | None) -> str:
    bits: list[str] = []
    if _is_data_plane(item):
        bits.append("是数据面进程")
        if re.search(r"execution pool", item.text, re.IGNORECASE):
            bits.append("运行探测执行池")
        if _is_tunnel_client(item) and control is not None:
            bits.append(f"并拨号连向 {control.name} 的隧道")
    elif _is_control_plane(item):
        if re.search(r"gRPC|grpc", item.text):
            bits.append("是 gRPC 控制面")
        else:
            bits.append("是控制面")
    elif _is_rest_entry(item):
        bits.append("是主 REST/Web 服务与管理入口")
    if not bits:
        return ""
    return f"{item.name} {'，'.join(bits)}"
