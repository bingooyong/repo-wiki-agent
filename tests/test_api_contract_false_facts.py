"""R12 leftover HARD: page-contract API dumps and schema `METHOD path:` false facts.

Real MiniMax-M3 r12-2026-08-17b emitted QODER_CRITICAL_FALSE_FACT for
`/api/articles*` on 故障排除/API问题.md, 核心服务/API.md, and 开发指南/API开发指南.md.
Those handlers exist. Two deterministic wiring bugs:

1. `_enforce_qoder_page_contract` treats any title/path containing the substring
   ``api`` as an API page, then injects the full scanned endpoint list (and schema
   summary) onto troubleshooting / core-service / dev-guide pages.
2. Schema lines are written as ``GET /api/articles: response_type=json``. The
   false-fact regex character class includes ``:``, so it claims path
   ``/api/articles:`` which is not in inventory.

Do not pass by relaxing QODER_CRITICAL_FALSE_FACT or the 95% coverage gate.
"""

from __future__ import annotations

import json
from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.generator.composer import ComposerContext
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory
from repo_wiki.verifier.qoder_strict_verifier import (
    QoderLikeSeverityThreshold,
    QoderLikeVerifierService,
)

ARTICLE_ENDPOINTS = [
    {
        "method": "GET",
        "path": "/api/articles",
        "module": "articles",
        "handler": "list_articles",
        "file_path": "app/api/routes/articles.py",
        "line_number": 7,
        "response_type": "json",
        "error_codes": [404],
    },
    {
        "method": "GET",
        "path": "/api/articles/{slug}",
        "module": "articles",
        "handler": "get_article",
        "file_path": "app/api/routes/articles.py",
        "line_number": 17,
        "response_type": "json",
    },
]


def _service(tmp_path: Path) -> RepoWikiService:
    cfg = RepoWikiConfig()
    cfg.project.root = str(tmp_path)
    return RepoWikiService(cfg)


def _context(tmp_path: Path) -> ComposerContext:
    return ComposerContext(
        repository_name="conduit",
        primary_language="python",
        framework="fastapi",
        repository_root=str(tmp_path),
        endpoints=ARTICLE_ENDPOINTS,
    )


def _render(tmp_path: Path, page: WikiPagePlan) -> str:
    return _service(tmp_path)._enforce_qoder_page_contract(
        page=page,
        markdown=f"# {page.title}\n\n## 简介\n\n短说明。\n",
        binding=None,
        add_mermaid=False,
        composition_context=_context(tmp_path),
    )


def _write_release_candidate(tmp_path: Path, page_extra: str = "") -> Path:
    content_dir = tmp_path / "repowiki" / "zh" / "content"
    meta_dir = tmp_path / "repowiki" / "zh" / "meta"
    content_dir.mkdir(parents=True)
    meta_dir.mkdir(parents=True)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("\n".join(f"line {i}" for i in range(1, 41)))
    page_rel = "项目概述/00-overview.md"
    page = content_dir / page_rel
    page.parent.mkdir()
    page.write_text(
        """# Project Overview

## Table of Contents
- [Intro](#intro)

## Intro

GET /health is the supported health endpoint for Service `api-gateway` and Model `user-entity`.
"""
        + page_extra
        + """
```mermaid
graph LR
  A --> B
```

<cite>source:src/app.py:1-10</cite>
""",
        encoding="utf-8",
    )
    (meta_dir / "quality-report.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.quality_report/1.0",
                "summary": {"profile": "qoder-like", "grade": "PASS", "strict_mode": True},
                "page_quality": [{"relative_path": page_rel, "quality_state": "READY"}],
            }
        ),
        encoding="utf-8",
    )
    (meta_dir / "page-registry.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.page_registry/1.0",
                "generated_at": "2026-08-17T00:00:00Z",
                "pages": [
                    {
                        "page_id": "overview",
                        "relative_path": page_rel,
                        "category": "overview",
                        "page_type": "content",
                        "quality_state": "READY",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (meta_dir / "api-inventory.json").write_text(
        json.dumps(
            {
                "endpoints": [
                    {"method": "GET", "path": "/health"},
                    {"method": "GET", "path": "/api/articles"},
                    {"method": "GET", "path": "/api/articles/{slug}"},
                    {"method": "GET", "path": "/api/articles/{slug:path}"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (meta_dir / "service-registry.json").write_text(
        json.dumps({"services": [{"service_id": "api-gateway"}]}), encoding="utf-8"
    )
    (meta_dir / "data-model-inventory.json").write_text(
        json.dumps({"models": [{"model_id": "user-entity"}]}), encoding="utf-8"
    )
    (meta_dir / "runtime-inventory.json").write_text(
        json.dumps({"runtime_entrypoints": [{"entrypoint": "repo-wiki"}]}),
        encoding="utf-8",
    )
    (meta_dir / "source-inventory.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.source_inventory/1.0",
                "services": [{"service_id": "api-gateway"}],
                "api_surfaces": [
                    {"method": "GET", "path": "/health"},
                    {"method": "GET", "path": "/api/articles"},
                    {"method": "GET", "path": "/api/articles/{slug}"},
                    {"method": "GET", "path": "/api/articles/{slug:path}"},
                ],
                "data_models": [{"model_id": "user-entity"}],
                "runtime_entrypoints": [{"entrypoint": "repo-wiki"}],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "version": "1.1",
                "run_id": "run-api-false-facts",
                "readiness_state": "READY",
                "readiness_reasons": [],
                "target_dirty": False,
                "git_fresh": True,
                "candidate_repowiki_zh_root": str(tmp_path / "repowiki" / "zh"),
                "candidate_content_root": str(content_dir),
                "candidate_meta_root": str(meta_dir),
                "report_paths": {"strict_verify": "reports/strict-verify-output.json"},
                "files": [{"path": "reports/strict-verify-output.json"}],
                "evidence": [],
            }
        ),
        encoding="utf-8",
    )
    return page


def test_troubleshooting_api_page_does_not_dump_scanned_article_routes(tmp_path: Path) -> None:
    """故障排除/API问题.md is not an API reference page; do not inject /api/articles*."""
    rendered = _render(
        tmp_path,
        WikiPagePlan(
            page_id="api-issues",
            title="API问题",
            category=WikiTaxonomyCategory.TROUBLESHOOTING,
            output_path="故障排除/API问题.md",
        ),
    )
    assert "GET /api/articles" not in rendered
    assert "API 分组" not in rendered


def test_core_service_and_dev_guide_api_pages_do_not_dump_article_routes(
    tmp_path: Path,
) -> None:
    """Substring 'API' in 核心服务/开发指南 titles must not dump the article catalog."""
    for page in (
        WikiPagePlan(
            page_id="core-api",
            title="API",
            category=WikiTaxonomyCategory.CORE_SERVICES,
            output_path="核心服务/API.md",
        ),
        WikiPagePlan(
            page_id="api-dev-guide",
            title="API开发指南",
            category=WikiTaxonomyCategory.DEVELOPMENT_GUIDE,
            output_path="开发指南/API开发指南.md",
        ),
    ):
        rendered = _render(tmp_path, page)
        assert "GET /api/articles" not in rendered, page.output_path
        assert "API 分组" not in rendered, page.output_path


def test_api_reference_page_still_emits_evidence_backed_article_routes(tmp_path: Path) -> None:
    """API参考 pages still receive evidence-backed grouping; facts are not dropped."""
    rendered = _render(
        tmp_path,
        WikiPagePlan(
            page_id="api-reference",
            title="API参考",
            category=WikiTaxonomyCategory.API_REFERENCE,
            output_path="API参考/API参考.md",
        ),
    )
    assert "GET /api/articles" in rendered
    assert "GET /api/articles/{slug}" in rendered
    assert "handler `list_articles`" in rendered
    assert "API 分组" in rendered


def test_schema_summary_colon_is_not_a_critical_false_fact(tmp_path: Path) -> None:
    """`GET /api/articles:` schema punctuation must not invent path `/api/articles:`."""
    _write_release_candidate(
        tmp_path,
        page_extra=(
            "\nGET /api/articles: response_type=json, error_codes=[404]\n"
            "GET /api/articles/{slug}: response_type=json\n"
            "GET /api/articles/{slug:path} is the catch-all converter route.\n"
        ),
    )
    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    assert "QODER_CRITICAL_FALSE_FACT" not in result.get("hard_gate_codes", [])
    check = next(c for c in result["checks"] if c["name"] == "qoder-critical-false-facts")
    assert check["status"] == "PASS"
    offenders = (check.get("details") or {}).get("offenders") or []
    assert not any(str(item.get("claim", "")).endswith(":") for item in offenders)


def test_unknown_route_still_fails_critical_false_fact(tmp_path: Path) -> None:
    """Do not relax HARD: routes that are not in inventory still fail."""
    _write_release_candidate(tmp_path, page_extra="\nPOST /ghost is not a scanned route.\n")
    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    assert "QODER_CRITICAL_FALSE_FACT" in result.get("hard_gate_codes", [])
    check = next(c for c in result["checks"] if c["name"] == "qoder-critical-false-facts")
    assert check["reason_code"] == "QODER_CRITICAL_FALSE_FACT"
    assert check["gate_type"] == "HARD" or str(check["gate_type"]).endswith("HARD")


def test_critical_false_fact_gate_remains_hard() -> None:
    """Do not hide leftover R12 false facts by dropping the HARD code."""
    threshold = QoderLikeSeverityThreshold()
    assert threshold.is_blocking("QODER_CRITICAL_FALSE_FACT") is True
    assert "QODER_CRITICAL_FALSE_FACT" in threshold.STRICT_HARD_CODES
    assert "QODER_CITATION_FACT_COVERAGE_LOW" in threshold.STRICT_HARD_CODES
    verifier_src = Path("repo_wiki/verifier/qoder_strict_verifier.py").read_text(encoding="utf-8")
    assert "if ratio < 0.95:" in verifier_src
