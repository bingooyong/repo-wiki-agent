"""Test/doc trees and empty taxonomy slots must not become product wiki pages.

R8: after prefixes and identity were correct, generate still emitted
``核心服务/Tests.md`` plus empty-slot pages (Agent代理API / API网关 / 前端应用).
This is a planner/taxonomy classification bug, not a verify-gate skip.
"""

from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.orchestration.content_layout_writer import _qoder_like_relative_path
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.schema import WikiTaxonomyCategory
from repo_wiki.scanner.repository_scanner import RepositoryScanner

_EMPTY_SLOT_TITLES = frozenset(
    {
        "前端应用",
        "前端应用API",
        "API网关",
        "API网关API",
        "API网关架构",
        "Agent代理API",
        "服务网格",
        "微服务模式",
        "微服务设计",
    }
)
_EMPTY_SLOT_PAGE_IDS = frozenset(
    {
        "frontend-applications-index",
        "frontend-application-api",
        "api-gateway",
        "api-gateway-api",
        "agent-proxy-api",
        "service-mesh",
        "microservices-pattern",
    }
)
_PRODUCT_PAGE_CATEGORIES = frozenset(
    {
        WikiTaxonomyCategory.CORE_SERVICES,
        WikiTaxonomyCategory.PYTHON_SERVICES,
        WikiTaxonomyCategory.API_REFERENCE,
    }
)


def _write_fastapi_app_with_tests(root: Path) -> None:
    """Small FastAPI app + tests/ package; no frontend and no gateway."""
    app_dir = root / "app"
    tests_dir = root / "tests"
    app_dir.mkdir()
    tests_dir.mkdir()
    (app_dir / "__init__.py").write_text("", encoding="utf-8")
    (app_dir / "main.py").write_text(
        """
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/items")
def create_item():
    return {"id": 1}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / "test_main.py").write_text(
        """
from app.main import app


def test_health():
    assert app is not None
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    (root / "README.md").write_text("# conduit-lite\n\nA tiny FastAPI app.\n", encoding="utf-8")


def _scan(root: Path):
    cfg = RepoWikiConfig.model_validate({"project": {"root": str(root)}})
    return RepositoryScanner(cfg).scan()


def _plan_pages(root: Path):
    cfg = RepoWikiConfig.model_validate(
        {
            "project": {"root": str(root)},
            "qoder_like": {"min_pages": 8, "max_pages": 220},
        }
    )
    return RepoWikiService(cfg)._build_qoder_like_page_plan(_scan(root))


def _mapped_paths(pages) -> set[str]:
    return {
        _qoder_like_relative_path(page.output_path, f"# {page.title}\n").as_posix()
        for page in pages
    }


def _is_tests_owned_product_page(page) -> bool:
    if page.category not in _PRODUCT_PAGE_CATEGORIES:
        return False
    title = str(page.title).strip()
    page_id = str(page.page_id).strip().lower()
    if title.lower() == "tests" or page_id in {"tests", "test"}:
        return True
    modules = [str(name).replace("\\", "/").lower() for name in page.source_requirements.modules]
    files = [str(path).replace("\\", "/").lower() for path in page.source_requirements.files]
    if any(name == "tests" or name.startswith("tests/") for name in modules):
        return True
    return any(path == "tests" or path.startswith("tests/") for path in files)


def test_plan_does_not_emit_tests_as_core_service_or_api_page(tmp_path: Path) -> None:
    _write_fastapi_app_with_tests(tmp_path)
    plan = _plan_pages(tmp_path)

    offenders = [page for page in plan.pages if _is_tests_owned_product_page(page)]
    assert offenders == [], "tests/ must not own a core-service/API product page: " + ", ".join(
        f"{page.page_id}:{page.title}" for page in offenders
    )
    assert "核心服务/Tests.md" not in _mapped_paths(plan.pages)


def test_plan_does_not_emit_empty_taxonomy_slot_pages(tmp_path: Path) -> None:
    _write_fastapi_app_with_tests(tmp_path)
    plan = _plan_pages(tmp_path)

    offenders = [
        page
        for page in plan.pages
        if page.page_id in _EMPTY_SLOT_PAGE_IDS or page.title in _EMPTY_SLOT_TITLES
    ]
    assert offenders == [], "empty taxonomy slots must not become pages: " + ", ".join(
        f"{page.page_id}:{page.title}" for page in offenders
    )
    mapped = _mapped_paths(plan.pages)
    assert "前端应用/前端应用.md" not in mapped
    assert "前端应用.md" not in mapped
    assert "API参考/Agent代理API.md" not in mapped
    assert "架构设计/API网关.md" not in mapped
    assert "架构设计/API网关架构.md" not in mapped


def test_plan_still_emits_product_app_module_page(tmp_path: Path) -> None:
    _write_fastapi_app_with_tests(tmp_path)
    snapshot = _scan(tmp_path)
    plan = _plan_pages(tmp_path)

    app_modules = [
        module
        for module in snapshot.modules
        if module.path.replace("\\", "/").split("/")[0] == "app"
    ]
    assert app_modules, "fixture must expose a product module under app/"
    app_names = {module.name for module in app_modules}

    product_pages = [
        page
        for page in plan.pages
        if page.category in _PRODUCT_PAGE_CATEGORIES
        and app_names.intersection(page.source_requirements.modules)
        and "index" not in page.page_id
    ]
    assert product_pages, "a real product module under app/ must still get a page"
