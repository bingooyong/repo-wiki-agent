from __future__ import annotations

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.generator.composer import ComposerContext
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory


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
