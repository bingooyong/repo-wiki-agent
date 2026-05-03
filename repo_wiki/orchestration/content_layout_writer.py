"""Content layout writer for Qoder-compatible output structure.

This module writes generated wiki pages into the qoder-like eval output structure:
    .repo-agent-eval/<run>/content/**/

Phase 27 - Task 27.2: Content layout writer

Key features:
- Write pages to content/** subdirectory
- Preserve Chinese taxonomy hierarchy
- Stable slugs for pages
- Safety checks for output paths
"""

from __future__ import annotations

import json
import sqlite3
import hashlib
import re
import time
from pathlib import Path
from typing import Any

from repo_wiki.generator.contracts import (
    CORE_DOCUMENT_CONTRACTS,
    DocumentContract,
    DocumentLayer,
    all_section_contracts,
    get_contracts_by_layer,
)
from repo_wiki.orchestration.eval_layout import EvalOutputProfile


# Chinese taxonomy hierarchy for Qoder-compatible output
TAXONOMY_ORDER: list[str] = [
    "项目概述",
    "架构设计",
    "核心服务",
    "Python服务",
    "前端应用",
    "数据模型",
    "API参考",
    "部署运维",
    "开发指南",
    "安全合规",
    "故障排除",
]


SERVICE_TITLE_OVERRIDES: dict[str, str] = {
    "api-atlas-agent": "API采集Agent",
    "api-gateway": "API网关",
    "api-gateway-1": "API网关",
    "doc-parser-service": "文档解析服务",
    "tcsl-generator-service": "TCSL生成服务",
    "nl-to-dsl-service": "自然语言转DSL服务",
    "scenario-orchestrator-service": "场景编排服务",
    "contract-service": "契约管理服务",
    "diff-service": "差异分析服务",
    "execution-service": "执行引擎服务",
    "gate-service": "质量门禁服务",
    "inventory-service": "API台账服务",
    "knowledge-graph-service": "知识图谱服务",
    "prd-reviewer": "PRD评审服务",
    "script-generator-service": "脚本生成服务",
    "security-audit-service": "安全审计服务",
    "security-scan-mcp-service": "安全扫描MCP服务",
    "test-data-factory-service": "测试数据工厂服务",
    "zentao-mcp-service": "禅道MCP服务",
    "jenkins-mcp-service": "Jenkins MCP服务",
    "gitlab-mcp-service": "GitLab MCP服务",
    "frontend": "前端应用",
    "silver-needle-coss": "Silver Needle COSS",
    "silver-needle-web": "Silver Needle Web",
    "vulnerable-app": "Vulnerable App",
}


PYTHON_SERVICE_SLUGS: set[str] = {
    "doc-parser-service",
    "tcsl-generator-service",
    "nl-to-dsl-service",
    "scenario-orchestrator-service",
}


PAGE_TITLE_OVERRIDES: dict[str, str] = {
    "00-overview": "项目概述",
    "01-architecture": "架构设计",
    "03-module-map": "模块组织结构",
    "04-api-contracts": "API参考",
    "05-data-model": "数据模型",
    "readme": "项目介绍与背景",
    "project-overview": "项目概述",
    "quick-start": "快速开始指南",
    "installation": "安装与配置",
    "key-features": "核心功能特性",
    "changelog": "版本与变更",
    "architecture-overview": "整体架构概览",
    "system-components": "系统组件",
    "module-relationships": "模块关系",
    "data-flow": "数据流与调用链",
    "api-gateway": "API网关架构",
    "service-mesh": "服务网格",
    "event-architecture": "事件驱动架构",
    "microservices-pattern": "微服务设计",
    "core-services-index": "核心服务",
    "ai-services-index": "AI服务能力",
    "frontend-applications-index": "前端应用",
    "python-services-index": "Python服务",
    "api-overview": "API参考",
    "core-service-apis": "核心服务API",
    "python-service-apis": "Python服务API",
    "api-gateway-api": "API网关API",
    "agent-proxy-api": "Agent代理API",
    "frontend-application-api": "前端应用API",
    "authentication-authorization-api": "认证授权API",
    "error-handling-status-codes": "错误处理与状态码",
    "data-models-overview": "数据模型",
    "core-data-models": "核心数据模型",
    "service-data-models": "服务数据模型",
    "database-architecture": "数据库架构",
    "database-migration-strategy": "数据迁移策略",
    "deployment-overview": "部署运维",
    "development-guide": "开发指南",
    "security-overview": "安全合规",
    "troubleshooting-overview": "故障排除",
    "troubleshooting-maintenance-overview": "故障排除",
}

TAXONOMY_ALIASES: dict[str, str] = {
    "故障排除与维护": "故障排除",
}


def compute_stable_slug(title: str, max_length: int = 50) -> str:
    """Compute a stable slug from a title.

    Args:
        title: The page title (supports Chinese and ASCII)
        max_length: Maximum slug length

    Returns:
        URL-safe slug preserving Chinese characters
    """
    import re

    slug = title.lower()

    # Replace spaces and underscores with dashes
    slug = slug.replace(" ", "-")
    slug = slug.replace("_", "-")

    # Keep alphanumeric (including Chinese), dashes, and essential punctuation
    # Chinese characters pass the regex \w in Unicode mode
    slug = re.sub(r"[^\w\-]", "", slug, flags=re.UNICODE)

    # Collapse multiple dashes
    while "--" in slug:
        slug = slug.replace("--", "-")

    slug = slug.strip("-")

    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")

    return slug


def get_taxonomy_category(file_path: str) -> str:
    """Determine taxonomy category from file path.

    Args:
        file_path: Relative file path

    Returns:
        Taxonomy category name (Chinese)
    """
    path_lower = file_path.lower()
    title = path_lower  # For consistency with extension.ts logic

    # 项目概述
    if "00-overview" in path_lower or "quick" in path_lower or "/project/" in path_lower:
        return "项目概述"

    # Python服务 - check early since "python" might appear in path
    if "python" in title:
        return "Python服务"

    # 前端应用
    if "/frontend/" in path_lower or "frontend" in title or "web-ui" in title:
        return "前端应用"

    # 架构设计
    if "01-architecture" in path_lower or "/architecture/" in path_lower:
        return "架构设计"

    # 核心服务 - modules, sections, services
    if "03-module" in path_lower or "/services/" in path_lower or "/modules/" in path_lower:
        return "核心服务"
    if "02-" in path_lower or "section" in path_lower:
        return "核心服务"

    # 数据模型
    if "data-model" in path_lower or "database" in path_lower or "migration" in path_lower or "entity" in path_lower:
        return "数据模型"

    # API参考
    if "api" in title:
        return "API参考"

    # 部署运维
    if "operations" in path_lower or "deploy" in path_lower:
        return "部署运维"

    # 开发指南
    if "development" in path_lower:
        return "开发指南"

    # 安全合规
    if "security" in path_lower:
        return "安全合规"

    # 故障排除与维护
    if "troubleshooting" in path_lower or "maintenance" in path_lower:
        return "故障排除"

    return "其他文档"


def organize_content_by_taxonomy(
    files: list[str],
    content_dir: Path,
) -> dict[str, list[str]]:
    """Organize content files by taxonomy category.

    Args:
        files: List of file paths
        content_dir: Base content directory

    Returns:
        Dictionary mapping category to list of file paths
    """
    organized: dict[str, list[str]] = {}

    for category in TAXONOMY_ORDER:
        organized[category] = []

    organized["其他文档"] = []

    for file_path in files:
        category = get_taxonomy_category(file_path)
        organized[category].append(file_path)

    return organized


def build_navigation_tree(
    files: list[str],
    content_root: Path,
) -> list[dict[str, Any]]:
    """Build navigation tree structure from file list.

    Args:
        files: List of file paths
        content_root: Root directory for content

    Returns:
        Hierarchical navigation tree
    """
    if not files:
        return [
            {
                "type": "category",
                "label": category,
                "children": [],
            }
            for category in TAXONOMY_ORDER
        ]

    roots: list[dict[str, Any]] = []
    root_by_label: dict[str, dict[str, Any]] = {}

    def get_category(parent_children: list[dict[str, Any]], label: str) -> dict[str, Any]:
        for child in parent_children:
            if child.get("type") == "category" and child.get("label") == label:
                return child
        node = {
            "type": "category",
            "label": label,
            "children": [],
        }
        parent_children.append(node)
        return node

    for file_path in sorted(files, key=_content_path_sort_key):
        if not file_path.endswith(".md"):
            continue
        parts = Path(file_path).parts
        abs_path = _resolve_content_path(content_root, file_path)
        title = _extract_title_from_file(abs_path) if abs_path.exists() else _title_from_path(file_path)
        page_node = {
            "type": "page",
            "id": compute_stable_slug(title),
            "label": title,
            "path": file_path,
            "absolutePath": str(abs_path.resolve()),
        }

        if len(parts) == 1:
            roots.append(page_node)
            continue

        parent_children = roots
        for segment in parts[:-1]:
            if parent_children is roots:
                category_node = root_by_label.get(segment)
                if category_node is None:
                    category_node = get_category(parent_children, segment)
                    root_by_label[segment] = category_node
            else:
                category_node = get_category(parent_children, segment)
            parent_children = category_node["children"]
        parent_children.append(page_node)

    _sort_navigation_nodes(roots)
    return roots


def _content_path_sort_key(file_path: str) -> tuple[int, str]:
    first = Path(file_path).parts[0] if Path(file_path).parts else file_path
    return (_taxonomy_sort_index(first), file_path)


def _taxonomy_sort_index(label: str) -> int:
    label = TAXONOMY_ALIASES.get(label, label)
    if label.endswith(".md"):
        label = Path(label).stem
    label = TAXONOMY_ALIASES.get(label, label)
    try:
        return TAXONOMY_ORDER.index(label)
    except ValueError:
        return len(TAXONOMY_ORDER)


def _sort_navigation_nodes(nodes: list[dict[str, Any]]) -> None:
    nodes.sort(key=lambda node: (_taxonomy_sort_index(str(node.get("label", ""))), node.get("type") != "category", str(node.get("label", ""))))
    for node in nodes:
        children = node.get("children")
        if isinstance(children, list):
            _sort_navigation_nodes(children)


def _resolve_content_path(content_root: Path, file_path: str) -> Path:
    path = Path(file_path)
    if path.is_absolute():
        return path
    return content_root / path


def _extract_title_from_file(file_path: Path) -> str:
    """Extract title from markdown file.

    Args:
        file_path: Path to markdown file

    Returns:
        Title string or derived from path
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        # Match first # heading
        import re
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
    except Exception:
        pass
    return _title_from_path(str(file_path))


def _extract_title_from_markdown(markdown: str) -> str | None:
    match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def _title_from_path(file_path: str) -> str:
    """Derive title from file path.

    Args:
        file_path: Relative file path

    Returns:
        Title string
    """
    stem = Path(file_path).stem
    # Remove common prefixes like numbers
    stem = stem.replace("00-", "").replace("01-", "").replace("02-", "").replace("03-", "")
    stem = stem.replace("04-", "").replace("05-", "")
    # Replace dashes and underscores with spaces
    stem = stem.replace("-", " ").replace("_", " ")
    return stem.strip()


def _slug_from_source_path(source_path: str) -> str:
    return Path(source_path).stem


def _canonical_title(source_path: str, markdown: str | None = None) -> str:
    slug = _slug_from_source_path(source_path)
    if slug in PAGE_TITLE_OVERRIDES:
        return PAGE_TITLE_OVERRIDES[slug]

    service_slug = _strip_known_suffixes(slug)
    if service_slug in SERVICE_TITLE_OVERRIDES:
        title = SERVICE_TITLE_OVERRIDES[service_slug]
        if slug.endswith("-api-reference"):
            return f"{title}API"
        if slug.endswith("-data-models") or slug.endswith("-models"):
            return f"{title}数据模型"
        return title

    if markdown:
        title = _extract_title_from_markdown(markdown)
        if title:
            return title

    return _title_from_path(source_path)


def _strip_known_suffixes(slug: str) -> str:
    for suffix in (
        "-api-reference",
        "-data-models",
        "-models",
        "-endpoints",
    ):
        if slug.endswith(suffix):
            return slug[: -len(suffix)]
    return slug


def _safe_markdown_filename(title: str) -> str:
    clean = title.strip().replace("/", "／").replace("\\", "＼")
    clean = re.sub(r"\s+", " ", clean)
    return f"{clean or '未命名页面'}.md"


def _qoder_like_relative_path(source_path: str, markdown: str | None = None) -> Path:
    """Map planner source paths to the Qoder-like Chinese information architecture."""
    normalized = source_path[5:] if source_path.startswith("docs/") else source_path
    slug = _slug_from_source_path(normalized)
    title = _canonical_title(source_path, markdown)
    filename = _safe_markdown_filename(title)

    if normalized.startswith("00-overview") or normalized.startswith("pages/overview/"):
        if slug == "key-features":
            return Path("项目概述") / "核心功能特性" / filename
        return Path("项目概述") / filename

    if normalized.startswith("01-architecture") or normalized.startswith("pages/architecture/"):
        return Path("架构设计") / filename

    if normalized.startswith("pages/python-services/"):
        return Path("Python服务") / filename

    if normalized.startswith("pages/frontend/"):
        return Path(filename) if slug == "frontend-applications-index" else Path("前端应用") / filename

    if normalized.startswith("03-module") or normalized.startswith("pages/services/"):
        service_slug = _strip_known_suffixes(slug)
        if service_slug in PYTHON_SERVICE_SLUGS:
            service_title = SERVICE_TITLE_OVERRIDES.get(service_slug, title)
            return Path("Python服务") / service_title / filename
        return Path("核心服务") / filename

    if normalized.startswith("05-data-model") or normalized.startswith("pages/data-models/"):
        if slug == "data-models-overview":
            return Path("数据模型") / "数据模型.md"
        if slug == "core-data-models":
            return Path("数据模型") / "核心数据模型" / "核心数据模型.md"
        if slug == "service-data-models":
            return Path("数据模型") / "服务数据模型" / "服务数据模型.md"
        if slug == "database-architecture":
            return Path("数据模型") / "数据库架构" / "数据库架构.md"
        if slug == "database-migration-strategy":
            return Path("数据模型") / "数据迁移策略.md"
        service_slug = _strip_known_suffixes(slug)
        service_title = SERVICE_TITLE_OVERRIDES.get(service_slug, title.replace(" 数据模型", "").replace("数据模型", ""))
        return Path("数据模型") / "服务数据模型" / service_title / filename

    if normalized.startswith("04-api") or normalized.startswith("pages/api/"):
        if slug == "api-overview":
            return Path("API参考") / "API参考.md"
        if slug == "core-service-apis":
            return Path("API参考") / "核心服务API" / "核心服务API.md"
        if slug == "python-service-apis":
            return Path("API参考") / "Python服务API" / "Python服务API.md"
        if slug in {
            "api-gateway-api",
            "agent-proxy-api",
            "frontend-application-api",
            "authentication-authorization-api",
            "error-handling-status-codes",
        }:
            return Path("API参考") / filename
        service_slug = _strip_known_suffixes(slug)
        service_title = SERVICE_TITLE_OVERRIDES.get(service_slug, title.replace(" API", "").replace("API", ""))
        if service_slug in PYTHON_SERVICE_SLUGS:
            return Path("API参考") / "Python服务API" / service_title / filename
        return Path("API参考") / "核心服务API" / service_title / filename

    if normalized.startswith("pages/development/"):
        return Path("开发指南") / filename

    if normalized.startswith("pages/deployment/"):
        if slug == "deployment-overview":
            return Path("部署运维.md")
        return Path("部署运维") / filename

    if normalized.startswith("pages/security/"):
        if slug == "security-overview":
            return Path("安全合规.md")
        return Path("安全合规") / filename

    if normalized.startswith("pages/troubleshooting/"):
        if slug in {"troubleshooting-overview", "troubleshooting-maintenance-overview"}:
            return Path("故障排除.md")
        return Path("故障排除") / filename

    category = get_taxonomy_category(source_path)
    if category in TAXONOMY_ORDER:
        return Path(category) / filename
    return Path(filename)


def _normalize_doc_path_for_filter(doc_path: str, project_root: Path | None) -> str:
    """Map stored doc_path (absolute or relative) to a stable repo-relative POSIX path."""
    raw = Path(doc_path)
    if project_root is not None:
        try:
            root = project_root.resolve()
            if raw.is_absolute():
                resolved = raw.resolve()
            else:
                resolved = (root / raw).resolve()
            rel = resolved.relative_to(root)
            return rel.as_posix()
        except (ValueError, OSError):
            pass
    return raw.as_posix()


def _dedupe_relative_path(relative_path: Path, used_paths: set[str], source_path: str) -> Path:
    path = relative_path
    counter = 2
    while str(path) in used_paths:
        suffix = compute_stable_slug(_slug_from_source_path(source_path), max_length=24) or str(counter)
        path = relative_path.with_name(f"{relative_path.stem}-{suffix}-{counter}{relative_path.suffix}")
        counter += 1
    used_paths.add(str(path))
    return path


class ContentLayoutWriter:
    """Writes generated content to Qoder-compatible layout.

    This writer organizes wiki content under:
        .repo-agent-eval/<run>/content/**/

    Preserving Chinese taxonomy hierarchy.
    """

    def __init__(
        self,
        profile: EvalOutputProfile,
        run_id: str,
    ) -> None:
        """Initialize the content layout writer.

        Args:
            profile: Eval output profile
            run_id: Run identifier
        """
        self.profile = profile
        self.run_id = run_id
        self._run_dir = profile.get_run_dir(run_id)
        self._content_dir = profile.get_content_dir(run_id)

    @property
    def content_dir(self) -> Path:
        """Get the content directory for this profile."""
        return self._content_dir

    @property
    def run_dir(self) -> Path:
        """Get the eval run directory for this profile."""
        return self._run_dir

    def get_output_path(self, source_path: str) -> Path:
        """Map a source path to the eval output path.

        Args:
            source_path: Original path like 'docs/00-overview.md'

        Returns:
            Resolved output path under eval content directory
        """
        # For qoder-like profile, content goes under content/ subdirectory
        if self.profile.content_subdir:
            return self._content_dir / _qoder_like_relative_path(source_path)
        # Otherwise use the content_dir (which includes run_id subdirectory)
        return self._content_dir / source_path

    def get_content_relative_path(self, source_path: str) -> Path:
        """Map a source path to a path relative to the content directory."""
        output_path = self.get_output_path(source_path)
        try:
            return output_path.resolve().relative_to(self._content_dir.resolve())
        except ValueError:
            return Path(output_path.name)

    def _output_path_for_markdown(self, source_path: str, markdown: str) -> tuple[Path, Path]:
        """Map a source path and Markdown body to absolute and content-relative paths."""
        if self.profile.content_subdir:
            relative_path = _qoder_like_relative_path(source_path, markdown)
            return self._content_dir / relative_path, relative_path
        output_path = self.get_output_path(source_path)
        return output_path, self.get_content_relative_path(source_path)

    def load_selected_paths_from_manifest(self, manifest_path: Path) -> set[str]:
        """Load selected planner output paths from a manifest JSON file."""
        if not manifest_path.exists():
            return set()
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return set()
        pages = payload.get("pages")
        if not isinstance(pages, list):
            return set()
        selected: set[str] = set()
        for page in pages:
            if not isinstance(page, dict):
                continue
            output_path = page.get("output_path")
            if isinstance(output_path, str) and output_path.endswith(".md"):
                selected.add(output_path)
        return selected

    def load_selected_paths_from_sqlite(
        self,
        sqlite_path: Path,
        project_root: Path | None = None,
    ) -> set[str]:
        """Load selected planner output paths from runtime SQLite doc_hierarchy.

        Paths in ``doc_hierarchy`` are often **absolute** (see runtime sync). Qoder-like
        composition uses **repo-relative** paths like ``docs/pages/...``. Without
        normalization, filtering in :meth:`write_markdown_pages` drops every page.

        Args:
            sqlite_path: Path to ``runtime.sqlite3``
            project_root: Repository root; when set, absolute ``doc_path`` values are
                converted to POSIX paths relative to this root when possible.
        """
        if not sqlite_path.exists():
            return set()
        selected: set[str] = set()
        try:
            with sqlite3.connect(sqlite_path) as conn:
                rows = conn.execute("SELECT doc_path FROM doc_hierarchy WHERE doc_path LIKE '%.md'").fetchall()
            for row in rows:
                doc_path = row[0]
                if isinstance(doc_path, str) and doc_path.endswith(".md"):
                    selected.add(_normalize_doc_path_for_filter(doc_path, project_root))
        except Exception:
            return set()
        return selected

    def write_content(
        self,
        source_dir: Path,
        files: list[str],
        selected_source_paths: set[str] | None = None,
    ) -> tuple[list[str], dict[str, Any]]:
        """Write content files to eval output directory.

        Args:
            source_dir: Source directory containing generated files
            files: List of file paths to copy

        Returns:
            Tuple of (content-relative written paths, stats)
        """
        written: list[str] = []
        stats: dict[str, Any] = {
            "files_written": 0,
            "bytes_written": 0,
            "by_category": {},
        }
        used_paths: set[str] = set()

        for file_path in files:
            if selected_source_paths is not None and file_path not in selected_source_paths:
                continue
            if self.profile.content_subdir and (
                not file_path.startswith("docs/") or not file_path.endswith(".md")
            ):
                continue

            source_file = source_dir / file_path
            if not source_file.exists():
                continue

            markdown = source_file.read_text(encoding="utf-8")
            output_file, relative_path = self._output_path_for_markdown(file_path, markdown)
            relative_path = _dedupe_relative_path(relative_path, used_paths, file_path)
            output_file = self._content_dir / relative_path

            self._assert_safe_output_path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(markdown, encoding="utf-8")
            written.append(str(relative_path))

            stats["files_written"] += 1
            stats["bytes_written"] += output_file.stat().st_size

            category = get_taxonomy_category(file_path)
            if category not in stats["by_category"]:
                stats["by_category"][category] = 0
            stats["by_category"][category] += 1

        return written, stats

    def write_markdown_pages(
        self,
        pages: list[tuple[str, str]],
        selected_source_paths: set[str] | None = None,
    ) -> tuple[list[str], dict[str, Any]]:
        """Write already-composed Markdown pages into the content directory.

        Args:
            pages: List of (source-style output path, markdown) tuples. Paths such as
                `docs/pages/api/foo.md` are mapped under `content/pages/api/foo.md`.

        Returns:
            Tuple of (content-relative written paths, stats)
        """
        written: list[str] = []
        stats: dict[str, Any] = {
            "files_written": 0,
            "bytes_written": 0,
            "by_category": {},
        }
        used_paths: set[str] = set()

        for source_path, markdown in pages:
            if not source_path.endswith(".md"):
                continue
            if selected_source_paths is not None and source_path not in selected_source_paths:
                continue
            output_file, relative_path = self._output_path_for_markdown(source_path, markdown)
            relative_path = _dedupe_relative_path(relative_path, used_paths, source_path)
            output_file = self._content_dir / relative_path if self.profile.content_subdir else output_file

            self._assert_safe_output_path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(markdown, encoding="utf-8")
            written.append(str(relative_path))

            stats["files_written"] += 1
            stats["bytes_written"] += output_file.stat().st_size

            category = get_taxonomy_category(source_path)
            if category not in stats["by_category"]:
                stats["by_category"][category] = 0
            stats["by_category"][category] += 1

        return written, stats

    def _assert_safe_output_path(self, output_file: Path) -> None:
        content_root = self._content_dir.resolve()
        resolved_output = output_file.resolve()
        try:
            resolved_output.relative_to(content_root)
        except ValueError as exc:
            raise ValueError(
                f"Refusing to write outside content root: {output_file}"
            ) from exc

    def build_page_registry(self, written_files: list[str]) -> list[dict[str, Any]]:
        """Build page registry entries for content-relative Markdown files."""
        registry: list[dict[str, Any]] = []
        for file_path in written_files:
            if not file_path.endswith(".md"):
                continue
            abs_path = _resolve_content_path(self._content_dir, file_path)
            title = _extract_title_from_file(abs_path) if abs_path.exists() else _title_from_path(file_path)
            registry.append({
                "path": file_path,
                "slug": compute_stable_slug(Path(file_path).stem),
                "type": "markdown",
                "title": title,
                "absolutePath": str(abs_path.resolve()),
            })
        return registry

    def build_manifest_content(
        self,
        written_files: list[str],
    ) -> dict[str, Any]:
        """Build manifest content structure.

        Args:
            written_files: List of written file paths

        Returns:
            Manifest content metadata
        """
        navigation_tree = build_navigation_tree(written_files, self._content_dir)
        page_registry = self.build_page_registry(written_files)

        return {
            "content_root": str(self._content_dir.resolve()),
            "run_id": self.run_id,
            "profile": self.profile.name,
            "navigation_tree": navigation_tree,
            "page_registry": page_registry,
            "file_count": len(written_files),
        }


def create_content_writer(
    profile: EvalOutputProfile,
    run_id: str,
) -> ContentLayoutWriter:
    """Create a content layout writer.

    Args:
        profile: Eval output profile
        run_id: Run identifier

    Returns:
        ContentLayoutWriter instance
    """
    return ContentLayoutWriter(profile=profile, run_id=run_id)


def write_qoder_like_content(
    source_dir: Path,
    profile: EvalOutputProfile,
    run_id: str,
    files: list[str],
) -> tuple[list[str], dict[str, Any]]:
    """Convenience function to write content in qoder-like layout.

    Args:
        source_dir: Source directory with generated files
        profile: Eval output profile
        run_id: Run identifier
        files: List of file paths to copy

    Returns:
        Tuple of (written_paths, stats)
    """
    writer = create_content_writer(profile, run_id)
    return writer.write_content(source_dir, files)
