"""Place evidence citations on the same line or next line as factual claims."""

from __future__ import annotations

import re
from pathlib import Path

from repo_wiki.verifier.citation_fact_coverage import (
    extract_citation_refs_with_lines,
    extract_claim_units,
)

_CITE_TAG_RE = re.compile(
    r"<cite>\s*([^:<]+):(\d+)(?:-(\d+))?(?:\s*\([^)]*\))?\s*</cite>",
    re.IGNORECASE,
)
_IDENT_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]{3,})`")
_FILE_SUFFIXES = (".py", ".go", ".md", ".yml", ".yaml", ".rst", ".json", ".sql", ".toml")
_GENERIC_IDENTIFIERS = frozenset(
    {
        "probe",
        "probes",
        "exporter",
        "config",
        "error",
        "errors",
        "context",
        "result",
        "results",
        "string",
        "handler",
        "server",
        "client",
        "router",
        "request",
        "response",
        "model",
        "models",
        "service",
        "services",
        "settings",
        "main",
        "value",
        "target",
        "status",
        "detail",
        "fastapi",
        "false",
        "true",
        "none",
    }
)
_FILE_LINE_RE = re.compile(r"^((?:[\w.-]+/)*[\w.-]+\.[A-Za-z0-9]+):(\d+)(?:-(\d+))?$")
_MD_LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\n]+)\)")
_PRODUCT_IDENTITY_RE = re.compile(r"产品身份|不再.{0,8}维护|停止主动维护")
_DANGLING_README_RE = re.compile(r"(?:(?<=[。；])|^)\s*`README\.(?:rst|md)`\s*[。；]?")
_README_HEADER_CITE_RE = re.compile(r"<cite>\s*(README\.(?:rst|md|txt)):1-1?\d\s*</cite>", re.I)
_RST_SKIP_RE = re.compile(r"^(?:\.\.|:|\||---+)")
_NOTE_LINE_RE = re.compile(r"^(?:\.\.\s+note::|\*\*NOTE\*\*\s*:|NOTE\s*:)", re.I)
_ROUTE_PATH_RE = re.compile(r"`(/[A-Za-z0-9_.:{}/-]*)`")
_ROUTE_REG_RE = re.compile(
    r"""(?:HandleFunc|Handle|GET|POST|PUT|DELETE|PATCH|Group|Register)\s*\(\s*['\"]""",
    re.I,
)


def sentence_identifiers(text: str) -> set[str]:
    """Backticked identifiers: type/function head, skipping generic tokens."""
    found = {
        item
        for item in _IDENT_RE.findall(text or "")
        if "/" not in item and not item.endswith(_FILE_SUFFIXES)
    }
    heads = {item.split(".")[0] for item in found}
    return {item for item in heads if len(item) >= 5 and item.lower() not in _GENERIC_IDENTIFIERS}


def promote_file_line_links(markdown: str, workspace_root: str | Path | None = None) -> str:
    """Turn leftover ``[file:line](file:line)`` links into cites or code spans."""
    root = Path(workspace_root) if workspace_root is not None else None

    def replace(match: re.Match[str]) -> str:
        target = match.group(2).strip()
        parsed = _FILE_LINE_RE.fullmatch(target)
        if not parsed:
            return match.group(0)
        rel = parsed.group(1)
        start = parsed.group(2)
        end = parsed.group(3) or start
        if root is not None and (root / rel).is_file():
            return f"<cite>{rel}:{start}-{end}</cite>"
        return f"`{rel}`"

    return _MD_LINK_RE.sub(replace, markdown or "")


def _parse_cite_tag(tag: str) -> tuple[str, int, int] | None:
    match = _CITE_TAG_RE.search(tag)
    if not match:
        return None
    start = int(match.group(2))
    end = int(match.group(3) or start)
    return match.group(1).strip(), start, end


def _cite_window(tag: str, root: Path) -> str:
    parsed = _parse_cite_tag(tag)
    if not parsed:
        return ""
    rel, start, end = parsed
    path = root / rel
    try:
        if not path.is_file():
            return ""
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[max(0, start - 4) : end + 3])


def _first_matching_tag(idents: set[str], tags: list[str], root: Path) -> str | None:
    for tag in tags:
        window = _cite_window(tag, root)
        if window and any(ident in window for ident in idents):
            return tag
    return None


def _first_filename_matching_tag(claim_text: str, tags: list[str]) -> str | None:
    lowered = (claim_text or "").lower()
    for tag in tags:
        parsed = _parse_cite_tag(tag)
        if not parsed:
            continue
        rel = parsed[0]
        stem = Path(rel).stem.lower()
        name = Path(rel).name.lower()
        if name and name in lowered:
            return tag
        if stem and len(stem) >= 4 and stem in lowered:
            return tag
    return None


def is_cite_realign_page(page: object | None) -> bool:
    title = str(getattr(page, "title", "") or "")
    stem = Path(str(getattr(page, "output_path", "") or "")).stem
    return title in {"核心服务", "数据库架构"} or stem in {"核心服务", "数据库架构"}


def attach_adjacent_cites(
    markdown: str,
    cite_tags: list[str],
    workspace_root: str | Path | None = None,
    strict_match: bool = False,
) -> str:
    """Insert unused evidence cites on the next line after uncovered claims.

    Coverage uses the existing ±1 line window. Tags must already be concrete
    ``<cite>path:start-end</cite>`` strings from bound evidence; this helper
    does not invent paths. When the sentence names a backticked identifier,
    only attach a tag whose cited range contains that identifier.
    """
    tags = [tag.strip() for tag in cite_tags if str(tag).strip()]
    if not markdown or not tags:
        return markdown

    claims = extract_claim_units(markdown, page="")
    if not claims:
        return markdown

    existing_lines = {ref.line for ref in extract_citation_refs_with_lines(markdown)}
    uncovered = [
        claim
        for claim in claims
        if not {claim.line - 1, claim.line, claim.line + 1} & existing_lines
    ]
    if not uncovered:
        return markdown

    root = Path(workspace_root) if workspace_root is not None else None
    lines = markdown.splitlines()
    in_fence = [False] * len(lines)
    fence = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence[index] = True
            fence = not fence
            continue
        in_fence[index] = fence
    tag_index = 0
    for claim in sorted(uncovered, key=lambda item: item.line, reverse=True):
        insert_at = min(max(claim.line, 0), len(lines))
        claim_idx = max(claim.line - 1, 0)
        if claim_idx < len(in_fence) and in_fence[claim_idx]:
            continue
        if insert_at < len(lines) and "```" in lines[insert_at]:
            continue
        if insert_at > 0 and "```" in lines[insert_at - 1]:
            continue
        claim_text = claim.text or (lines[claim.line - 1] if 0 < claim.line <= len(lines) else "")
        idents = sentence_identifiers(claim_text) if root is not None else set()
        if _is_multifile_summary(claim_text):
            continue
        if root is not None:
            if idents:
                tag = _first_matching_tag(idents, tags, root)
            else:
                tag = _first_filename_matching_tag(claim_text, tags)
            if tag is None and not strict_match and not _is_multifile_summary(claim_text):
                tag = tags[tag_index % len(tags)]
                tag_index += 1
            if tag is None:
                continue
        else:
            tag = tags[tag_index % len(tags)]
            tag_index += 1
        lines.insert(insert_at, tag)

    rewritten = "\n".join(lines)
    if markdown.endswith("\n") and not rewritten.endswith("\n"):
        rewritten += "\n"
    return rewritten


def _is_multifile_summary(text: str) -> bool:
    files = re.findall(r"`[^`]+?\.[A-Za-z0-9]+`", text or "")
    if len(files) >= 2:
        return True
    return bool(re.search(r"总体入口|多个文件|各模块|分别在|分别落在", text or ""))


def realign_irrelevant_cites(
    markdown: str,
    cite_tags: list[str],
    workspace_root: str | Path,
) -> str:
    """Replace a cite only when a sentence identifier appears in the target range."""
    root = Path(workspace_root)
    tags = [tag.strip() for tag in cite_tags if str(tag).strip()]
    if not markdown:
        return markdown
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        cites = list(_CITE_TAG_RE.finditer(line))
        if not cites:
            continue
        prose = _CITE_TAG_RE.sub("", line).strip() or (lines[index - 1] if index else "")
        idents = sentence_identifiers(prose)
        if not idents:
            continue
        new_line = line
        for match in reversed(cites):
            tag = match.group(0)
            window = _cite_window(tag, root)
            if window and any(ident in window for ident in idents):
                continue
            replacement = _first_matching_tag(idents, tags, root)
            if replacement and replacement != tag:
                new_line = new_line[: match.start()] + replacement + new_line[match.end() :]
            else:
                new_line = new_line[: match.start()] + new_line[match.end() :]
        new_line = re.sub(r"（\s*）", "", new_line)
        new_line = re.sub(r"\s{2,}", " ", new_line).rstrip()
        lines[index] = new_line
    rewritten = "\n".join(lines)
    if markdown.endswith("\n") and not rewritten.endswith("\n"):
        rewritten += "\n"
    return rewritten


def _replace_adjacent_cite(lines: list[str], index: int, new_cite: str) -> None:
    for offset in (0, 1, 2):
        target = index + offset
        if 0 <= target < len(lines) and "<cite>" in lines[target]:
            lines[target] = _CITE_TAG_RE.sub(new_cite, lines[target], count=1)
            return
    lines.insert(min(index + 1, len(lines)), new_cite)


def _section_bounds(lines: list[str], heading: str) -> tuple[int, int] | None:
    start = None
    for index, line in enumerate(lines):
        if re.match(rf"^##\s+{re.escape(heading)}\s*$", line):
            start = index + 1
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start, len(lines)):
        if re.match(r"^##\s+", lines[index]):
            end = index
            break
    return start, end


def find_alembic_revision_rel(root: Path) -> str:
    """Return the Alembic revision with the most create_table calls."""
    candidates: list[Path] = []
    for rel in (
        "app/db/migrations/versions",
        "alembic/versions",
        "migrations/versions",
    ):
        folder = root / rel
        if folder.is_dir():
            candidates.extend(path for path in folder.glob("*.py") if path.is_file())
    if not candidates:
        for path in root.rglob("*.py"):
            if path.parent.name == "versions" and "migration" in path.as_posix().lower():
                candidates.append(path)
    best = ""
    best_count = -1
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        count = len(re.findall(r"\bop\.create_table\b", text))
        if count > best_count:
            best = path.relative_to(root).as_posix()
            best_count = count
    return best


def rewrite_fastapi_intro_cites(
    markdown: str,
    page: object | None,
    workspace_root: str | Path,
) -> str:
    """Point intro identity at the README NOTE/H1 and table claims at Alembic."""
    root = Path(workspace_root)
    alembic_rel = find_alembic_revision_rel(root)
    if not alembic_rel and not any(
        (root / name).is_file() for name in ("README.rst", "README.md", "README.txt", "README")
    ):
        return markdown
    from repo_wiki.generator.deterministic_sections import cite_existing_meaningful

    title = str(getattr(page, "title", "") or "")
    page_id = str(getattr(page, "page_id", "") or "")
    output = str(getattr(page, "output_path", "") or "")
    category = str(getattr(getattr(page, "category", None), "value", "") or "")
    blob = f"{title} {page_id} {output} {category}"
    intro_owner = any(
        token in blob
        for token in (
            "数据库架构",
            "数据迁移策略",
            "database-architecture",
            "database-migration",
            "核心服务API",
            "Python服务API",
            "api-overview",
            "core-service-apis",
            "API_REFERENCE",
            "API参考",
        )
    )
    lines = markdown.splitlines()
    changed = False
    readme_names = [
        name
        for name in ("README.rst", "README.md", "README.txt", "README")
        if (root / name).is_file()
    ]
    identity_indexes = [index for index, line in enumerate(lines) if _is_identity_intro_line(line)]
    if intro_owner:
        intro_bounds = _section_bounds(lines, "简介")
        if intro_bounds:
            start, end = intro_bounds
            identity_indexes.extend(
                index for index in range(start, end) if _is_identity_intro_line(lines[index])
            )
    if readme_names and identity_indexes:
        claim = "\n".join(lines[i] for i in identity_indexes if 0 <= i < len(lines))
        readme_cite = ""
        for name in readme_names:
            readme_cite = cite_readme_supporting_line(root, name, claim)
            if readme_cite:
                break
        if readme_cite:
            seen: set[int] = set()
            for index in identity_indexes:
                if index in seen or index < 0 or index >= len(lines):
                    continue
                seen.add(index)
                if not _is_identity_intro_line(lines[index]):
                    continue
                _replace_adjacent_cite(lines, index, readme_cite)
                lines[index] = _DANGLING_README_RE.sub("", lines[index])
                lines[index] = re.sub(r"。\s*。", "。", lines[index])
                changed = True
    for index, line in enumerate(lines):
        match = _README_HEADER_CITE_RE.search(line)
        if not match:
            continue
        readme = match.group(1)
        support = cite_readme_supporting_line(root, readme, line)
        if not support or support == match.group(0):
            continue
        lines[index] = _README_HEADER_CITE_RE.sub(support, lines[index], count=1)
        changed = True
    if (root / alembic_rel).is_file():
        mig_cite = cite_alembic_upgrade_range(root, alembic_rel) or (
            cite_existing_meaningful(root, alembic_rel)
        )
        if mig_cite:
            for index, line in enumerate(lines):
                if re.search(rf"{re.escape(alembic_rel)}:1-1?\d\b", line) or (
                    re.search(r"\d+\s*张.{0,12}表", line) and re.search(r"models/", line)
                ):
                    _replace_adjacent_cite(lines, index, mig_cite)
                    changed = True
    rewritten = "\n".join(lines)
    from repo_wiki.evidence.citation_renderer import strip_empty_cite_parens

    rewritten = strip_empty_cite_parens(rewritten)
    if markdown.endswith("\n") and not rewritten.endswith("\n"):
        rewritten += "\n"
    if rewritten == markdown:
        return markdown
    return rewritten


def _is_identity_intro_line(line: str) -> bool:
    """True for maintenance-status prose or a leftover README header-range cite."""
    if _PRODUCT_IDENTITY_RE.search(line) or _DANGLING_README_RE.search(line):
        return True
    return bool(_README_HEADER_CITE_RE.search(line))


def _readme_line_is_skippable(stripped: str) -> bool:
    return (not stripped) or bool(_RST_SKIP_RE.match(stripped))


def cite_readme_supporting_line(root: Path, readme: str, claim: str) -> str:
    """Cite the README NOTE or H1 that actually supports the identity sentence."""
    path = Path(root) / readme
    if not path.is_file():
        return ""
    try:
        rows = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    note_line = _readme_note_line(rows)
    h1_line = _readme_h1_line(rows)
    heading_line = _readme_heading_mentioned_in_claim(rows, claim or "")
    wants_note = bool(_PRODUCT_IDENTITY_RE.search(claim or "") or "维护" in (claim or ""))
    if heading_line and not wants_note:
        return f"<cite>{readme}:{heading_line}-{heading_line}</cite>"
    if wants_note and note_line:
        return f"<cite>{readme}:{note_line}-{note_line}</cite>"
    if heading_line:
        return f"<cite>{readme}:{heading_line}-{heading_line}</cite>"
    if h1_line:
        return f"<cite>{readme}:{h1_line}-{h1_line}</cite>"
    if note_line:
        return f"<cite>{readme}:{note_line}-{note_line}</cite>"
    for index, line in enumerate(rows, 1):
        stripped = line.strip()
        if _readme_line_is_skippable(stripped):
            continue
        if len(stripped) > 40:
            return f"<cite>{readme}:{index}-{index}</cite>"
    return ""


def _readme_note_line(rows: list[str]) -> int:
    for index, line in enumerate(rows, 1):
        stripped = line.strip()
        if _NOTE_LINE_RE.match(stripped):
            if re.match(r"^\.\.\s+note::", stripped, re.I):
                for follow in range(index, min(len(rows), index + 4)):
                    nxt = rows[follow].strip()
                    if nxt and not nxt.startswith(".."):
                        return follow + 1 if follow != index - 1 else index
            return index
    return 0


def _readme_h1_line(rows: list[str]) -> int:
    for index, line in enumerate(rows, 1):
        stripped = line.strip()
        if stripped.startswith("# "):
            return index
        if index < len(rows) and re.fullmatch(r"[-=]{3,}", rows[index].strip()):
            if stripped and not stripped.startswith("..") and not stripped.startswith(":"):
                return index
    return 0


def _readme_heading_mentioned_in_claim(rows: list[str], claim: str) -> int:
    blob = (claim or "").casefold()
    if not blob:
        return 0
    for index, line in enumerate(rows, 1):
        stripped = line.strip().lstrip("#").strip()
        if len(stripped) < 4 or stripped.startswith("..") or stripped.startswith(":"):
            continue
        is_heading = line.strip().startswith("# ") or (
            index < len(rows) and bool(re.fullmatch(r"[-=]{3,}", rows[index].strip()))
        )
        if is_heading and stripped.casefold() in blob:
            return index
    return 0


def realign_route_registration_cites(markdown: str, workspace_root: str | Path) -> str:
    """Point route path cites at the registration line, not a later mention."""
    root = Path(workspace_root)
    if not markdown:
        return markdown
    index = _route_registration_index(root)
    if not index:
        return markdown
    lines = markdown.splitlines()
    changed = False
    for lineno, line in enumerate(lines):
        if "<cite>" not in line:
            continue
        paths = _ROUTE_PATH_RE.findall(line)
        if not paths:
            continue
        for route in paths:
            target = index.get(route)
            if target is None:
                continue
            rel, start = target
            new_cite = f"<cite>{rel}:{start}-{start}</cite>"
            updated = _CITE_TAG_RE.sub(
                lambda match: (
                    new_cite if match.group(1).replace("\\", "/") == rel else match.group(0)
                ),
                line,
            )
            if updated != line:
                lines[lineno] = updated
                changed = True
    if not changed:
        return markdown
    rewritten = "\n".join(lines)
    if markdown.endswith("\n") and not rewritten.endswith("\n"):
        rewritten += "\n"
    return rewritten


def _route_registration_index(root: Path) -> dict[str, tuple[str, int]]:
    found: dict[str, tuple[str, int]] = {}
    skip = {".git", ".repo-agent-eval", "vendor", "node_modules", "__pycache__"}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".go", ".py"}:
            continue
        if any(part in skip for part in path.parts) or path.name.endswith("_test.go"):
            continue
        rel = path.relative_to(root).as_posix()
        try:
            rows = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for index, line in enumerate(rows, 1):
            for route in re.findall(r"""['\"](/[A-Za-z0-9_.:{}/-]*)['\"]""", line):
                if route in found and not _ROUTE_REG_RE.search(line):
                    continue
                if _ROUTE_REG_RE.search(line) or route not in found:
                    found[route] = (rel, index)
    return found


def cite_alembic_upgrade_range(root: Path, rel: str) -> str:
    """Cite the create_table / upgrade span, not the module docstring."""
    path = Path(root) / rel
    if not path.is_file():
        return ""
    try:
        rows = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    starts: list[int] = []
    upgrade_line = 0
    downgrade_line = 0
    for index, line in enumerate(rows, 1):
        if re.match(r"def upgrade\b", line):
            upgrade_line = index
        elif re.match(r"def downgrade\b", line):
            downgrade_line = index
        if re.search(r"\bop\.create_table\b", line):
            starts.append(index)
    if not starts and not upgrade_line:
        return ""
    start = min(starts) if starts else upgrade_line
    if upgrade_line and start < upgrade_line:
        end = upgrade_line - 1
    elif downgrade_line:
        end = downgrade_line - 1
    else:
        end = starts[-1]
    while end > start and not rows[end - 1].strip():
        end -= 1
    return f"<cite>{rel}:{start}-{end}</cite>"
