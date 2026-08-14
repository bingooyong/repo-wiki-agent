"""Test/doc trees and empty taxonomy slots must not become product wiki pages.

R8: after prefixes and identity were correct, generate still emitted
``核心服务/Tests.md`` plus empty-slot pages (Agent代理API / API网关 / 前端应用).
This is a planner/taxonomy classification bug, not a verify-gate skip.
"""

from __future__ import annotations

from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.core.contracts import Endpoint, Module, RepositoryInfo, RepositorySnapshot
from repo_wiki.orchestration.content_layout_writer import _qoder_like_relative_path
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.identity import RepositoryIdentity
from repo_wiki.planner.rule_first import RuleFirstPlanner
from repo_wiki.planner.schema import WikiTaxonomyCategory
from repo_wiki.scanner.artifacts import has_frontend_wiki_surface, is_product_wiki_module
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


def test_is_product_wiki_module_rejects_test_doc_and_fixture_trees() -> None:
    assert is_product_wiki_module("") is False
    assert is_product_wiki_module("tests") is False
    assert is_product_wiki_module("app/tests/helpers") is False
    assert is_product_wiki_module("docs/guide") is False
    assert is_product_wiki_module("fixtures/sample") is False
    assert is_product_wiki_module("app/test_api.py", name="test_api.py") is False
    assert is_product_wiki_module("app/foo_test.py", name="foo_test") is False
    assert is_product_wiki_module("app/foo_tests.py", name="foo_tests") is False
    assert is_product_wiki_module("docs", name="docs") is False
    assert is_product_wiki_module("app/docs/guide") is False
    assert is_product_wiki_module("app/test/helpers") is False
    assert is_product_wiki_module("app/helpers", name="docs") is False
    assert is_product_wiki_module("app", name="app", domain="testing") is False
    assert is_product_wiki_module("app", name="app", runtime_role="test-harness") is False
    assert (
        is_product_wiki_module("app", name="app", domain="core-platform", runtime_role="api-server")
        is True
    )


def test_has_frontend_wiki_surface_requires_real_frontend_inventory() -> None:
    assert has_frontend_wiki_surface(None) is False
    assert has_frontend_wiki_surface([]) is False
    tests_only = [
        _module(name="tests", path="tests", domain="testing", runtime_role="test-harness"),
        _module(name="frontend-tests", path="tests/frontend", domain="frontend"),
    ]
    assert has_frontend_wiki_surface(tests_only) is False
    assert has_frontend_wiki_surface(
        [_module(name="web", path="web", domain="frontend", family="typescript-frontend")]
    )
    assert has_frontend_wiki_surface(
        [_module(name="web", path="web", family="typescript-frontend")]
    )
    assert has_frontend_wiki_surface([_module(name="frontend-app", path="packages/frontend-app")])


def test_plan_does_not_emit_docs_as_core_service_page(tmp_path: Path) -> None:
    _write_fastapi_app_with_tests(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "conf.py").write_text("project = 'conduit-lite'\n", encoding="utf-8")
    plan = _plan_pages(tmp_path)
    offenders = [
        page
        for page in plan.pages
        if page.category in _PRODUCT_PAGE_CATEGORIES
        and (page.title.lower() == "docs" or page.page_id == "docs")
    ]
    assert offenders == []


def test_plan_emits_inventory_backed_gateway_agent_frontend_and_mesh() -> None:
    snapshot = _snapshot(
        modules=[
            _module(name="api-gateway", path="services/api-gateway", domain="core-platform"),
            _module(name="agent-proxy", path="services/agent-proxy", domain="core-platform"),
            _module(name="service-mesh", path="ops/service-mesh", domain="operations"),
            _module(name="billing-microservice", path="services/billing-microservice"),
            _module(name="web", path="web", domain="frontend", family="typescript-frontend"),
        ],
        endpoints=[
            _endpoint(
                module="api-gateway", path="/gw/health", file_path="services/api-gateway/api.py"
            ),
            _endpoint(
                module="agent-proxy", path="/agent/run", file_path="services/agent-proxy/api.py"
            ),
            _endpoint(module="web", path="/ui", file_path="web/src/api.ts"),
            _endpoint(module="tests", path="/gateway", file_path="tests/test_gateway.py"),
        ],
    )
    planner = RuleFirstPlanner(_identity(), snapshot)
    assert planner._has_surface_token() is False
    titles = {page.title for page in planner.generate().pages}
    assert "API网关" in titles
    assert "API网关API" in titles
    assert "Agent代理API" in titles
    assert "服务网格" in titles
    assert "微服务模式" in titles
    assert "前端应用API" in titles


def test_plan_detects_agent_surface_from_product_endpoint_path() -> None:
    snapshot = _snapshot(
        modules=[_module(name="app", path="app", domain="core-platform")],
        endpoints=[_endpoint(module="app", path="/agent/status", file_path="app/main.py")],
    )
    planner = RuleFirstPlanner(_identity(), snapshot)
    assert planner._has_surface_token("agent") is True
    titles = {page.title for page in planner.generate().pages}
    assert "Agent代理API" in titles


def test_has_surface_token_skips_test_endpoint_and_known_non_product_module() -> None:
    snapshot = _snapshot(
        modules=[
            _module(name="app", path="app", domain="core-platform"),
            _module(name="tests", path="tests", domain="testing", runtime_role="test-harness"),
        ],
        endpoints=[
            _endpoint(module="tests", path="/gateway", file_path="tests/test_gateway.py"),
            _endpoint(module="tests", path="/login", file_path="app/main.py"),
        ],
    )
    planner = RuleFirstPlanner(_identity(), snapshot)
    assert planner._has_surface_token("gateway") is False
    pages = planner.generate().pages
    assert not any(page.page_id == "api-gateway" for page in pages)
    assert not any(page.page_id.startswith("tests") for page in pages)


def test_plan_ignores_orphan_test_module_endpoints() -> None:
    snapshot = _snapshot(
        modules=[_module(name="app", path="app", domain="core-platform")],
        endpoints=[
            _endpoint(module="tests", path="/login", file_path=""),
            _endpoint(module="app", path="/health", file_path="app/main.py"),
        ],
    )
    pages = RuleFirstPlanner(_identity(), snapshot).generate().pages
    assert not any(page.page_id.startswith("tests") for page in pages)


def test_normalize_keeps_frontend_root_when_inventory_has_frontend(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# web\n", encoding="utf-8")
    snapshot = _snapshot(
        modules=[_module(name="web", path="web", domain="frontend", family="typescript-frontend")]
    )
    plan = RuleFirstPlanner(_identity(), snapshot).generate()
    cfg = RepoWikiConfig.model_validate(
        {"project": {"root": str(tmp_path)}, "qoder_like": {"min_pages": 8, "max_pages": 220}}
    )
    normalized = RepoWikiService(cfg)._normalize_qoder_like_plan(
        plan, minimum_pages=8, snapshot=snapshot
    )
    assert any(page.page_id == "frontend-applications-index" for page in normalized.pages)


def _identity() -> RepositoryIdentity:
    return RepositoryIdentity(name="fixture", display_name="Fixture", root_path="/tmp/fixture")


def _module(
    *,
    name: str,
    path: str,
    domain: str = "unknown",
    runtime_role: str = "api-server",
    family: str = "python-backend",
) -> Module:
    return Module(
        name=name,
        path=path,
        responsibility=name,
        owner="unknown",
        doc_path=f"docs/modules/{name}.md",
        domain=domain,
        service_family=family,
        runtime_role=runtime_role,
    )


def _endpoint(*, module: str, path: str, file_path: str) -> Endpoint:
    return Endpoint(
        method="GET",
        path=path,
        module=module,
        handler="handle",
        file_path=file_path,
    )


def _snapshot(
    *,
    modules: list[Module],
    endpoints: list[Endpoint] | None = None,
) -> RepositorySnapshot:
    return RepositorySnapshot(
        repository=RepositoryInfo(name="fixture", root_path="/tmp/fixture"),
        modules=modules,
        endpoints=endpoints or [],
        data_models=[],
    )
