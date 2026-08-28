"""Handbook chapters must be product topics, not source-file dumps.

Reader-visible FastAPI failure: 核心服务 listed Init .py / Main.py / Models.
Directory sections listed 简介/项目结构 even when those H2s did not exist.
"""

from __future__ import annotations

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.core.contracts import (
    DataModel,
    Endpoint,
    Module,
    RepositoryInfo,
    RepositorySnapshot,
)
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.identity import RepositoryIdentity
from repo_wiki.planner.rule_first import RuleFirstPlanner
from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeVerifierService

_CANNED_OUTLINE = ("简介", "项目结构", "核心组件", "详细分析", "结论")


def _identity() -> RepositoryIdentity:
    return RepositoryIdentity(
        name="fastapi-handbook",
        display_name="FastAPI Handbook",
        root_path="/tmp/fastapi-handbook",
        language="python",
        framework="fastapi",
    )


def _module(*, name: str, path: str, domain: str = "core-platform") -> Module:
    return Module(
        name=name,
        path=path,
        responsibility=name,
        owner="unknown",
        doc_path=f"docs/modules/{name.replace('/', '-')}.md",
        domain=domain,
        service_family="python-backend",
        runtime_role="api-server",
        data_models=["Article"] if name == "models" else [],
    )


def _filename_module_snapshot() -> RepositorySnapshot:
    return RepositorySnapshot(
        repository=RepositoryInfo(
            name="fastapi-handbook",
            root_path="/tmp/fastapi-handbook",
            language="python",
            framework="fastapi",
        ),
        modules=[
            _module(name="__init__.py", path="app/__init__.py"),
            _module(name="main.py", path="app/main.py"),
            _module(name="models", path="app/models"),
            _module(name="db", path="app/db"),
            _module(name="core", path="app/core"),
            _module(name="services", path="app/services"),
            _module(name="gate-service", path="services/gate-service"),
        ],
        endpoints=[
            Endpoint(
                method="GET",
                path="/health",
                module="main.py",
                handler="health",
                file_path="app/main.py",
            )
        ],
        data_models=[
            DataModel(
                name="Article",
                type="python_class",
                module="models",
                file_path="app/models/article.py",
            )
        ],
    )


def _filename_like_titles(pages: list[WikiPagePlan]) -> list[str]:
    banned_exact = {
        "init.py",
        "init .py",
        "main.py",
        "models",
        "core",
        "db",
        "services",
        "init",
        "main",
    }
    offenders: list[str] = []
    for page in pages:
        compact = " ".join(str(page.title).split()).strip().lower()
        compact = compact.removesuffix(".md")
        if ".py" in compact.replace(" ", "") or compact in banned_exact:
            offenders.append(page.title)
    return offenders


def test_planner_folds_filename_modules_into_core_services() -> None:
    planner = RuleFirstPlanner(_identity(), _filename_module_snapshot())
    manifest = planner.generate()

    offenders = _filename_like_titles(manifest.pages)
    assert offenders == [], f"handbook pages must not be filenames: {offenders}"

    core_index = next(page for page in manifest.pages if page.page_id == "core-services-index")
    assert core_index.title == "核心服务"
    folded = set(core_index.source_requirements.modules)
    assert {"__init__.py", "main.py", "models", "db"}.issubset(folded)
    assert any(page.title == "质量门禁服务" for page in manifest.pages)


def test_filter_drops_filename_like_qoder_pages(tmp_path) -> None:
    cfg = RepoWikiConfig()
    cfg.project.root = str(tmp_path)
    service = RepoWikiService(cfg)
    pages = [
        WikiPagePlan(
            page_id="core-services-index",
            title="核心服务",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/pages/services/core-services-index.md",
        ),
        WikiPagePlan(
            page_id="init.py",
            title="Init .py",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/pages/services/init.py.md",
        ),
        WikiPagePlan(
            page_id="main.py",
            title="Main.py",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/pages/services/main.py.md",
        ),
        WikiPagePlan(
            page_id="models",
            title="Models",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="docs/pages/services/models.md",
        ),
    ]

    kept = service._filter_qoder_like_pages(pages)
    titles = [page.title for page in kept]
    assert titles == ["核心服务"]


def test_page_contract_does_not_seed_canned_outline_for_body_only(tmp_path) -> None:
    cfg = RepoWikiConfig()
    cfg.project.root = str(tmp_path)
    service = RepoWikiService(cfg)
    page = WikiPagePlan(
        page_id="debug-tools",
        title="调试工具",
        category=WikiTaxonomyCategory.TROUBLESHOOTING,
        output_path="docs/pages/troubleshooting/debug-tools.md",
    )
    markdown = "# 调试工具\n\n仓库 README 说明如何用日志定位请求失败，没有二级标题。\n"

    rendered = service._enforce_qoder_page_contract(
        page=page,
        markdown=markdown,
        binding=None,
        add_mermaid=False,
    )

    assert "简介" not in rendered.split("## 目录", 1)[-1] if "## 目录" in rendered else True
    for heading in _CANNED_OUTLINE:
        assert f"{heading}" not in _toc_item_texts(rendered)
    if "## 目录" in rendered:
        raise AssertionError("body-only page must omit 目录 instead of inventing one")


def test_page_contract_builds_toc_from_real_h2s(tmp_path) -> None:
    cfg = RepoWikiConfig()
    cfg.project.root = str(tmp_path)
    service = RepoWikiService(cfg)
    page = WikiPagePlan(
        page_id="quick-start",
        title="快速开始",
        category=WikiTaxonomyCategory.PROJECT_OVERVIEW,
        output_path="docs/pages/overview/quick-start.md",
    )
    markdown = """# 快速开始

## 环境要求

需要 Python 3.11。

## 启动与验证

运行 uvicorn。
"""
    rendered = service._enforce_qoder_page_contract(
        page=page,
        markdown=markdown,
        binding=None,
        add_mermaid=False,
    )
    assert "## 目录" in rendered
    toc_items = _toc_item_texts(rendered)
    assert "环境要求" in toc_items
    assert "启动与验证" in toc_items
    for heading in _CANNED_OUTLINE:
        assert heading not in toc_items


def test_qoder_toc_presence_passes_when_real_h2s_have_toc(tmp_path) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "quick-start.md").write_text(
        """# 快速开始

## 目录

1. 环境要求
2. 启动与验证

## 环境要求

需要 Python 3.11。

## 启动与验证

运行 uvicorn。
""",
        encoding="utf-8",
    )
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_qoder_toc_presence()
    assert result.status == "PASS"


def test_qoder_toc_presence_still_fails_headed_page_missing_toc(tmp_path) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "overview.md").write_text(
        """# 项目概述

## 这是什么

这是一个 FastAPI 服务。
""",
        encoding="utf-8",
    )
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_qoder_toc_presence()
    assert result.status == "FAIL"
    assert result.reason_code == "QODER_TOC_MISSING"


def test_qoder_toc_presence_does_not_hard_fail_body_only_page(tmp_path) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "debug-tools.md").write_text(
        "# 调试工具\n\n仓库 README 说明如何用日志定位请求失败。\n",
        encoding="utf-8",
    )
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_qoder_toc_presence()
    assert result.status != "FAIL"


def test_qoder_toc_presence_fails_when_toc_targets_are_missing(tmp_path) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "models.md").write_text(
        """# Models

## 目录

1. 简介
2. 项目结构
3. 核心组件
4. 详细分析
5. 结论

正文只有 README 摘录，没有这些标题。
""",
        encoding="utf-8",
    )
    result = QoderLikeVerifierService(tmp_path, strict=True)._check_qoder_toc_presence()
    assert result.status == "FAIL"


def _toc_item_texts(markdown: str) -> list[str]:
    if "## 目录" not in markdown and "## Table of Contents" not in markdown:
        return []
    start = markdown.find("## 目录")
    if start < 0:
        start = markdown.find("## Table of Contents")
    rest = markdown[start:].splitlines()[1:]
    items: list[str] = []
    for line in rest:
        stripped = line.strip()
        if stripped.startswith("#"):
            break
        if not stripped:
            continue
        text = stripped.lstrip("0123456789.-* ").strip()
        if text:
            items.append(text)
    return items
