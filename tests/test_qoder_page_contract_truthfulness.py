from __future__ import annotations

import re

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.generator.composer import ComposerContext
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.schema import SourceRequirement, WikiPagePlan, WikiTaxonomyCategory
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeVerifierService


def _service(tmp_path):
    cfg = RepoWikiConfig()
    cfg.project.root = str(tmp_path)
    return RepoWikiService(cfg)


def _api_page() -> WikiPagePlan:
    return WikiPagePlan(
        page_id="inventory-api",
        title="Inventory API",
        category=WikiTaxonomyCategory.API_REFERENCE,
        output_path="docs/pages/api/inventory-api.md",
    )


def test_qoder_page_contract_does_not_emit_unsupported_generic_api_claims(tmp_path):
    service = _service(tmp_path)
    markdown = """# Inventory API

## 简介

短说明。

- GET /resources：读取资源列表或健康状态。
- POST /resources：创建资源或触发处理任务。
- 认证: 需要 Bearer Token

```json
{"request": {"auth": "Bearer token"}}
```
"""

    rendered = service._enforce_qoder_page_contract(
        page=_api_page(),
        markdown=markdown,
        binding=None,
        add_mermaid=True,
        composition_context=ComposerContext(
            repository_name="repo",
            primary_language="python",
            framework="unknown",
            repository_root=str(tmp_path),
        ),
    )

    assert "/resources" not in rendered
    assert '"auth": "Bearer token"' not in rendered
    assert "需要 Bearer Token" not in rendered
    assert "UNRESOLVED_API_AUTH" in rendered
    assert "UNRESOLVED_API_ENDPOINTS" in rendered
    assert "UNRESOLVED_API_FLOW" in rendered
    assert "API网关" not in rendered
    assert "路由并鉴权" not in rendered


def test_qoder_page_contract_preserves_evidence_backed_endpoint_data(tmp_path):
    service = _service(tmp_path)
    context = ComposerContext(
        repository_name="repo",
        primary_language="python",
        framework="fastapi",
        repository_root=str(tmp_path),
        endpoints=[
            {
                "method": "GET",
                "path": "/inventory/items",
                "module": "inventory",
                "handler": "list_items",
                "file_path": "src/inventory/api.py",
                "line_number": 42,
                "auth_type": "api-key",
                "response_type": "json",
                "error_codes": [404],
            }
        ],
    )

    rendered = service._enforce_qoder_page_contract(
        page=_api_page(),
        markdown="# Inventory API\n\n## 简介\n\n短说明。",
        binding=None,
        add_mermaid=False,
        composition_context=context,
    )

    assert "GET /inventory/items" in rendered
    assert "handler `list_items`" in rendered
    assert "`src/inventory/api.py`:42" in rendered
    assert "认证: api-key" in rendered
    assert "response_type=json" in rendered
    assert "error_codes=[404]" in rendered
    assert "/resources" not in rendered
    assert "Bearer token" not in rendered


def test_qoder_api_page_does_not_empty_state_when_product_endpoints_exist(tmp_path):
    """Planner stores 'METHOD path'; empty-state must not fire if those endpoints exist."""
    service = _service(tmp_path)
    page = WikiPagePlan(
        page_id="api-reference",
        title="API参考",
        category=WikiTaxonomyCategory.API_REFERENCE,
        output_path="API参考/API参考.md",
        source_requirements=SourceRequirement(
            endpoints=["POST /login", "GET /feed", "GET /{slug}"],
        ),
    )
    context = ComposerContext(
        repository_name="conduit",
        primary_language="python",
        framework="fastapi",
        repository_root=str(tmp_path),
        endpoints=[
            {
                "method": "POST",
                "path": "/login",
                "module": "authentication",
                "handler": "login",
                "file_path": "app/api/routes/authentication.py",
                "line_number": 12,
            },
            {
                "method": "GET",
                "path": "/feed",
                "module": "articles",
                "handler": "articles_feed",
                "file_path": "app/api/routes/articles_common.py",
                "line_number": 8,
            },
            {
                "method": "GET",
                "path": "/{slug}",
                "module": "articles",
                "handler": "get_article",
                "file_path": "app/api/routes/articles.py",
                "line_number": 40,
            },
        ],
    )

    rendered = service._enforce_qoder_page_contract(
        page=page,
        markdown="# API参考\n\n## 简介\n\n短说明。",
        binding=None,
        add_mermaid=False,
        composition_context=context,
    )

    assert "UNRESOLVED_API_ENDPOINTS" not in rendered
    assert "POST /login" in rendered
    assert "GET /feed" in rendered
    assert "GET /{slug}" in rendered


def _error_codes_page() -> WikiPagePlan:
    return WikiPagePlan(
        page_id="error-codes",
        title="错误码参考",
        category=WikiTaxonomyCategory.TROUBLESHOOTING,
        output_path="docs/pages/troubleshooting/error-codes.md",
    )


def test_error_code_page_drops_test_only_wrong_path_api_claim(tmp_path):
    """Test 404 fixtures must not ship as product APIs after page contract."""
    service = _service(tmp_path)
    context = ComposerContext(
        repository_name="conduit",
        primary_language="python",
        framework="fastapi",
        repository_root=str(tmp_path),
        endpoints=[
            {
                "method": "GET",
                "path": "/api/articles",
                "module": "articles",
                "handler": "list_articles",
                "file_path": "app/api/routes/articles.py",
                "line_number": 18,
            },
            {
                "method": "POST",
                "path": "/api/users/login",
                "module": "authentication",
                "handler": "login",
                "file_path": "app/api/routes/authentication.py",
                "line_number": 12,
            },
        ],
    )
    markdown = """# 错误码参考

## 404 Not Found

客户端访问 GET /wrong_path/asd 会得到 404，这不是产品路由。
真实文章列表是 GET /api/articles。
登录也可写为 POST /users/login。
"""

    rendered = service._enforce_qoder_page_contract(
        page=_error_codes_page(),
        markdown=markdown,
        binding=None,
        add_mermaid=False,
        composition_context=context,
    )

    assert "GET /wrong_path/asd" not in rendered
    assert "/wrong_path/asd" not in rendered
    assert "GET /api/articles" in rendered
    assert "POST /users/login" in rendered


def test_error_code_page_without_test_fixture_does_not_trip_critical_false_fact(tmp_path):
    """After contract, unmatched test paths are gone so CRITICAL_FALSE_FACT stays quiet."""
    service = _service(tmp_path)
    context = ComposerContext(
        repository_name="conduit",
        primary_language="python",
        framework="fastapi",
        repository_root=str(tmp_path),
        endpoints=[
            {
                "method": "GET",
                "path": "/api/articles",
                "handler": "list_articles",
            }
        ],
    )
    markdown = """# 错误码参考

## 常见状态码

GET /wrong_path/asd 被测试当成 404 夹具。
产品接口 GET /api/articles 返回文章列表。
"""
    rendered = service._enforce_qoder_page_contract(
        page=_error_codes_page(),
        markdown=markdown,
        binding=None,
        add_mermaid=False,
        composition_context=context,
    )

    apis = {("GET", "/api/articles")}
    verifier = QoderLikeVerifierService(tmp_path, strict=True)
    leftover = []
    for method, api_path in re.findall(
        r"\b(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+(/[-A-Za-z0-9_./{}:]+)",
        rendered,
    ):
        if not verifier._api_claim_in_inventory(method.upper(), api_path, apis):
            leftover.append(f"{method.upper()} {api_path}")
    assert leftover == []
