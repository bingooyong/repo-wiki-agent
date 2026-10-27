"""R14 leftover HARD: truncated DELETE /api/articles vs DELETE /api/articles/{slug}.

Claim extraction/matching drops a trailing ``{param}``, so inventory cannot match
``DELETE /api/articles`` to the real FastAPI route ``DELETE /api/articles/{slug}``
(handler ``delete_article_by_slug``). Unknown routes such as ``POST /ghost`` must
still fail HARD. Do not pass by relaxing QODER_CRITICAL_FALSE_FACT or 95% coverage.
"""

from __future__ import annotations

import json
from pathlib import Path

from repo_wiki.verifier.qoder_strict_verifier import (
    QoderLikeSeverityThreshold,
    QoderLikeVerifierService,
    api_claim_in_inventory,
    extract_http_method_paths,
    normalize_claimed_api_path,
)


def _write_release_candidate(
    tmp_path: Path,
    *,
    page_rel: str,
    page_extra: str,
    endpoints: list[dict[str, str]],
) -> None:
    content_dir = tmp_path / "repowiki" / "zh" / "content"
    meta_dir = tmp_path / "repowiki" / "zh" / "meta"
    content_dir.mkdir(parents=True)
    meta_dir.mkdir(parents=True)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("\n".join(f"line {i}" for i in range(1, 41)))
    page = content_dir / page_rel
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        """# API API

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
                        "page_id": "api-api",
                        "relative_path": page_rel,
                        "category": "api",
                        "page_type": "content",
                        "quality_state": "READY",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    api_payload = {"endpoints": endpoints}
    (meta_dir / "api-inventory.json").write_text(json.dumps(api_payload), encoding="utf-8")
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
                "api_surfaces": endpoints,
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
                "run_id": "run-trailing-path-param",
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


ARTICLE_INVENTORY = [
    {"method": "GET", "path": "/health"},
    {"method": "GET", "path": "/api/articles"},
    {"method": "POST", "path": "/api/articles"},
    {"method": "GET", "path": "/api/articles/{slug}"},
    {"method": "PUT", "path": "/api/articles/{slug}"},
    {"method": "DELETE", "path": "/api/articles/{slug}"},
]


def test_normalize_keeps_trailing_path_param() -> None:
    """``{slug}`` is a path param, not schema punctuation to strip."""
    assert normalize_claimed_api_path("/api/articles/{slug}") == "/api/articles/{slug}"
    assert normalize_claimed_api_path("/api/articles/{slug:path}") == "/api/articles/{slug:path}"
    assert normalize_claimed_api_path("/api/articles:") == "/api/articles"


def test_claimed_delete_articles_matches_inventory_slug_route() -> None:
    """Missing trailing ``{slug}`` still matches the scanned delete-by-slug route."""
    apis = {(item["method"], item["path"]) for item in ARTICLE_INVENTORY}
    assert api_claim_in_inventory("DELETE", "/api/articles", apis) is True
    assert api_claim_in_inventory("DELETE", "/api/articles/{slug}", apis) is True
    assert extract_http_method_paths("DELETE /api/articles deletes one article.\n") == [
        ("DELETE", "/api/articles")
    ]


def test_delete_articles_without_slug_is_not_a_critical_false_fact(tmp_path: Path) -> None:
    """Wiki claim ``DELETE /api/articles`` is the truncated slug route, not a ghost API."""
    _write_release_candidate(
        tmp_path,
        page_rel="API参考/核心服务API/API API.md",
        page_extra="\nDELETE /api/articles removes the article identified by slug.\n",
        endpoints=ARTICLE_INVENTORY,
    )
    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    assert "QODER_CRITICAL_FALSE_FACT" not in result.get("hard_gate_codes", [])
    check = next(c for c in result["checks"] if c["name"] == "qoder-critical-false-facts")
    assert check["status"] == "PASS"
    offenders = (check.get("details") or {}).get("offenders") or []
    assert not any(str(item.get("claim", "")) == "DELETE /api/articles" for item in offenders)


def test_unknown_route_still_fails_critical_false_fact(tmp_path: Path) -> None:
    """Do not relax HARD: routes that are not in inventory still fail."""
    _write_release_candidate(
        tmp_path,
        page_rel="API参考/核心服务API/API API.md",
        page_extra="\nPOST /ghost is not a scanned route.\n",
        endpoints=ARTICLE_INVENTORY,
    )
    result = QoderLikeVerifierService(tmp_path, strict=True).verify(ci=True)
    assert "QODER_CRITICAL_FALSE_FACT" in result.get("hard_gate_codes", [])
    check = next(c for c in result["checks"] if c["name"] == "qoder-critical-false-facts")
    assert check["reason_code"] == "QODER_CRITICAL_FALSE_FACT"
    assert check["gate_type"] == "HARD" or str(check["gate_type"]).endswith("HARD")
    offenders = (check.get("details") or {}).get("offenders") or []
    assert any(str(item.get("claim", "")) == "POST /ghost" for item in offenders)


def test_static_remainder_is_still_a_false_fact() -> None:
    """``DELETE /api`` must not match ``DELETE /api/articles/{slug}``."""
    apis = {("DELETE", "/api/articles/{slug}")}
    assert api_claim_in_inventory("DELETE", "/api", apis) is False
    assert api_claim_in_inventory("POST", "/ghost", apis) is False


def test_critical_false_fact_gate_and_coverage_remain_hard() -> None:
    """Do not hide leftover R14 false facts by dropping HARD codes or the 95% floor."""
    threshold = QoderLikeSeverityThreshold()
    assert threshold.is_blocking("QODER_CRITICAL_FALSE_FACT") is True
    assert "QODER_CRITICAL_FALSE_FACT" in threshold.STRICT_HARD_CODES
    assert "QODER_CITATION_FACT_COVERAGE_LOW" in threshold.STRICT_HARD_CODES
    verifier_src = Path("repo_wiki/verifier/qoder_strict_verifier.py").read_text(encoding="utf-8")
    assert "if ratio < 0.95:" in verifier_src
