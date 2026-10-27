"""R13 leftover HARD: mermaid `entity` service, GitHub badge paths, API page scope.

Real MiniMax-M3 R13 (CLI with #72–#75+#82+#83) still failed:

- ``QODER_CRITICAL_FALSE_FACT`` — six API pages claim service ``entity``. The
  API relationship flowchart ends one edge on node id ``entity`` and starts the
  next line with node id ``service``. Claim extraction treats that cross-line
  ``entity\\n    service`` as prose "entity service".
- ``QODER_UNRESOLVED_FACT_CONFLICT`` — README.rst ``STALE_DOC_REFERENCE`` for
  GitHub badge URL fragments such as ``app/blob/master/license`` and
  ``app/workflows/api``. Those are ``example-app/blob/...`` URL tails, not repo
  files. ``.env`` / ``/docs`` / ``/redoc`` were a different leftover.
- ``QODER_API_AGGREGATION_LOW`` — ``aggregated_apis=5``, ``total_api_pages=9``.
  The metric counts any filename containing ``api``/``API``, so troubleshooting
  and core-service pages inflate the denominator.

Do not pass by relaxing HARD codes or the 95% coverage / 0.60 aggregation
thresholds.
"""

from __future__ import annotations

import json
from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.generator.composer import ComposerContext
from repo_wiki.generator.mermaid_planner import MermaidPlanner, MermaidRenderer
from repo_wiki.orchestration.service import RepoWikiService
from repo_wiki.planner.schema import WikiPagePlan, WikiTaxonomyCategory
from repo_wiki.scanner.conflict_resolver import resolve_source_docs_conflicts
from repo_wiki.scanner.docs_scanner import (
    _extract_claims,
    scan_repository_docs_inventory,
)
from repo_wiki.verifier.qoder_parity_metrics import (
    PARITY_METRICS,
    ParityMetricExtractor,
)
from repo_wiki.verifier.qoder_strict_verifier import (
    QoderLikeSeverityThreshold,
    QoderLikeVerifierService,
)

_MERMAID_RELATIONSHIP = """```mermaid
flowchart TD
    frontend[Frontend]
    controller[Controller]
    service[Service]
    repository[Repository]
    entity[Entity/DTO]
    frontend -->|API call| controller
    controller -->|orchestrate| service
    service -->|read/write| repository
    repository -->|map| entity
    service -->|DTO transform| entity
```
"""

_README_RST_BADGES = """
FastAPI RealWorld example
=========================

.. image:: https://github.com/nsidnev/fastapi-realworld-example-app/workflows/API/badge.svg
   :target: https://github.com/nsidnev/fastapi-realworld-example-app/actions?query=workflow%3AAPI

.. image:: https://img.shields.io/github/license/nsidnev/fastapi-realworld-example-app.svg
   :target: https://github.com/nsidnev/fastapi-realworld-example-app/blob/master/LICENSE

Quickstart
----------

The handler lives in ``app/main.py``.
The removed module was ``src/legacy/gone.py``.
""".strip()

_AGGREGATED_API_BODY = """# API参考

## 分组

GET /api/articles
POST /api/articles
DELETE /api/articles/{slug}

## Schema 摘要

```json
{"article": {}}
```
"""

_THIN_API_BODY = """# 错误处理与状态码

GET /api/articles returns 404 when missing.
"""


def _service(tmp_path: Path) -> RepoWikiService:
    cfg = RepoWikiConfig()
    cfg.project.root = str(tmp_path)
    return RepoWikiService(cfg)


def _source_inventory() -> dict:
    return {
        "services": [{"kind": "python_fastapi_app", "evidence_path": "app/main.py"}],
        "api_surfaces": [],
        "data_models": [],
        "frontend_callers": [],
        "deployment_assets": [],
        "tests": [],
    }


def _write_ready_run(run_dir: Path, *, pages: dict[str, str]) -> Path:
    content_dir = run_dir / "repowiki" / "zh" / "content"
    meta_dir = run_dir / "repowiki" / "zh" / "meta"
    content_dir.mkdir(parents=True)
    meta_dir.mkdir(parents=True)
    (run_dir / "src").mkdir()
    (run_dir / "src" / "app.py").write_text(
        "\n".join(f"line {i}" for i in range(1, 41)), encoding="utf-8"
    )
    registry_pages = []
    quality_pages = []
    for rel, body in pages.items():
        path = content_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        registry_pages.append(
            {
                "page_id": Path(rel).stem,
                "relative_path": rel,
                "category": "api" if "API" in rel or "api" in rel.lower() else "overview",
                "page_type": "content",
                "quality_state": "READY",
            }
        )
        quality_pages.append({"relative_path": rel, "quality_state": "READY"})
    (meta_dir / "quality-report.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.quality_report/1.0",
                "summary": {"profile": "qoder-like", "grade": "PASS", "strict_mode": True},
                "page_quality": quality_pages,
            }
        ),
        encoding="utf-8",
    )
    (meta_dir / "page-registry.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.page_registry/1.0",
                "generated_at": "2026-08-17T00:00:00Z",
                "pages": registry_pages,
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
                ],
                "data_models": [{"model_id": "user-entity"}],
                "runtime_entrypoints": [{"entrypoint": "repo-wiki"}],
            }
        ),
        encoding="utf-8",
    )
    (meta_dir / "source-docs-conflicts.json").write_text(
        json.dumps(
            {
                "schema_version": "source-docs-conflict-resolver-v1",
                "summary": {
                    "resolved_count": 0,
                    "deferred_count": 0,
                    "flagged_count": 0,
                    "total_items": 0,
                },
                "resolved_items": [],
                "deferred_items": [],
                "flagged_items": [],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "version": "1.1",
                "run_id": run_dir.name,
                "readiness_state": "READY",
                "readiness_reasons": [],
                "target_dirty": False,
                "git_fresh": True,
                "candidate_repowiki_zh_root": str(run_dir / "repowiki" / "zh"),
                "candidate_content_root": str(content_dir),
                "candidate_meta_root": str(meta_dir),
                "report_paths": {"strict_verify": "reports/strict-verify-output.json"},
                "files": [{"path": "reports/strict-verify-output.json"}],
                "evidence": [],
            }
        ),
        encoding="utf-8",
    )
    return meta_dir


def _api_page_markdown() -> str:
    return (
        "# API参考\n\n## 简介\n\nGET /health is owned by Service `api-gateway`.\n\n"
        + _MERMAID_RELATIONSHIP
        + "\n<cite>source:src/app.py:1-10</cite>\n"
    )


def test_mermaid_relationship_flowchart_does_not_claim_entity_service() -> None:
    """Cross-line mermaid `entity` then `service` is not an inventory service."""
    plan = MermaidPlanner()._plan_api_relationship_flowchart("api-ref", None, {"endpoints": []})
    rendered = MermaidRenderer().render_diagram(plan)
    assert "entity" in rendered
    assert "service" in rendered
    verifier = object.__new__(QoderLikeVerifierService)
    claims = QoderLikeVerifierService._extract_structured_name_claims(verifier, rendered, "service")
    assert "entity" not in {claim.lower() for claim in claims}


def test_api_contract_mermaid_does_not_claim_entity_service(tmp_path: Path) -> None:
    page = WikiPagePlan(
        page_id="api-reference",
        title="API参考",
        category=WikiTaxonomyCategory.API_REFERENCE,
        output_path="API参考/API参考.md",
    )
    rendered = _service(tmp_path)._enforce_qoder_page_contract(
        page=page,
        markdown="# API参考\n\n## 简介\n\n短说明。",
        binding=None,
        add_mermaid=True,
        composition_context=ComposerContext(
            repository_name="conduit",
            primary_language="python",
            framework="fastapi",
            repository_root=str(tmp_path),
            endpoints=[
                {
                    "method": "GET",
                    "path": "/api/articles",
                    "handler": "list_articles",
                    "file_path": "app/api/routes/articles.py",
                    "line_number": 7,
                    "response_type": "json",
                }
            ]
            * 3,
        ),
    )
    assert "```mermaid" in rendered
    verifier = object.__new__(QoderLikeVerifierService)
    claims = QoderLikeVerifierService._extract_structured_name_claims(verifier, rendered, "service")
    assert "entity" not in {claim.lower() for claim in claims}


def test_api_pages_with_relationship_mermaid_are_not_critical_false_facts(
    tmp_path: Path,
) -> None:
    """The six R13 API pages failed because injected mermaid claimed service entity."""
    pages = {
        "API参考/API参考.md": _api_page_markdown(),
        "API参考/错误处理与状态码.md": "# 错误处理与状态码\n\n" + _MERMAID_RELATIONSHIP,
        "API参考/认证授权API.md": "# 认证授权API\n\n" + _MERMAID_RELATIONSHIP,
        "API参考/核心服务API.md": "# 核心服务API\n\n" + _MERMAID_RELATIONSHIP,
        "API参考/Python服务API.md": "# Python服务API\n\n" + _MERMAID_RELATIONSHIP,
        "API参考/核心服务API/API API.md": "# API API\n\n" + _MERMAID_RELATIONSHIP,
    }
    run_dir = tmp_path / ".repo-agent-eval" / "runs" / "run-entity-mermaid"
    _write_ready_run(run_dir, pages=pages)
    result = QoderLikeVerifierService(run_dir, strict=True).verify(ci=True)
    assert "QODER_CRITICAL_FALSE_FACT" not in result.get("hard_gate_codes", [])
    check = next(c for c in result["checks"] if c["name"] == "qoder-critical-false-facts")
    assert check["status"] == "PASS"
    offenders = (check.get("details") or {}).get("offenders") or []
    assert not any(
        item.get("claim_type") == "service" and str(item.get("claim", "")).lower() == "entity"
        for item in offenders
    )


def test_prose_unknown_service_still_fails_critical_false_fact(tmp_path: Path) -> None:
    run_dir = tmp_path / ".repo-agent-eval" / "runs" / "run-ghost-service"
    _write_ready_run(
        run_dir,
        pages={
            "项目概述/00-overview.md": (
                "# Overview\n\nService `ghost-svc` is not in inventory.\n"
                "<cite>source:src/app.py:1-10</cite>\n"
            )
        },
    )
    result = QoderLikeVerifierService(run_dir, strict=True).verify(ci=True)
    assert "QODER_CRITICAL_FALSE_FACT" in result.get("hard_gate_codes", [])
    check = next(c for c in result["checks"] if c["name"] == "qoder-critical-false-facts")
    assert check["reason_code"] == "QODER_CRITICAL_FALSE_FACT"
    assert check["gate_type"] == "HARD" or str(check["gate_type"]).endswith("HARD")


def test_github_badge_urls_are_not_source_file_claims() -> None:
    _names, path_like = _extract_claims(_README_RST_BADGES)
    assert "app/blob/master/license" not in path_like
    assert "app/workflows/api" not in path_like
    assert "app/workflows/api/badge.svg" not in path_like
    assert "app/actions" not in path_like
    assert "app/main.py" in path_like
    assert "src/legacy/gone.py" in path_like


def test_readme_rst_github_badges_are_not_stale_doc_references(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("app = True\n", encoding="utf-8")
    (tmp_path / "README.rst").write_text(_README_RST_BADGES + "\n", encoding="utf-8")
    inv = scan_repository_docs_inventory(
        tmp_path, _source_inventory(), incremental=False, persist_cache=False
    )
    readme = next(doc for doc in inv["documents"] if doc["path"] == "README.rst")
    stale = set(readme["stale_references"])
    assert "app/blob/master/license" not in stale
    assert "app/workflows/api" not in stale
    assert "app/workflows/api/badge.svg" not in stale
    assert "src/legacy/gone.py" in stale
    assert "app/main.py" not in stale


def test_github_badge_scan_is_not_unresolved_fact_conflict(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("app = True\n", encoding="utf-8")
    (tmp_path / "README.rst").write_text(
        "Badge: https://github.com/nsidnev/fastapi-realworld-example-app/blob/master/LICENSE\n"
        "Workflow: https://github.com/nsidnev/fastapi-realworld-example-app/workflows/API/badge.svg\n"
        "Entry: ``app/main.py``\n",
        encoding="utf-8",
    )
    docs = scan_repository_docs_inventory(
        tmp_path, _source_inventory(), incremental=False, persist_cache=False
    )
    report = resolve_source_docs_conflicts(_source_inventory(), docs)
    readme_items = [
        item
        for bucket in (report["flagged_items"], report["deferred_items"])
        for item in bucket
        if item.get("doc_path") == "README.rst"
    ]
    assert readme_items == []

    run_dir = tmp_path / ".repo-agent-eval" / "runs" / "run-badge-conflict"
    meta_dir = _write_ready_run(
        run_dir,
        pages={"项目概述/00-overview.md": "# Overview\n\nService `api-gateway`.\n"},
    )
    (meta_dir / "source-docs-conflicts.json").write_text(json.dumps(report), encoding="utf-8")
    result = QoderLikeVerifierService(run_dir, strict=True).verify(ci=True)
    assert "QODER_UNRESOLVED_FACT_CONFLICT" not in result.get("hard_gate_codes", [])


def test_missing_source_path_still_unresolved_conflict(tmp_path: Path) -> None:
    (tmp_path / "README.rst").write_text(
        "Removed handler: ``src/legacy/gone.py``\n",
        encoding="utf-8",
    )
    docs = scan_repository_docs_inventory(
        tmp_path, _source_inventory(), incremental=False, persist_cache=False
    )
    report = resolve_source_docs_conflicts(_source_inventory(), docs)
    evidence = {
        item
        for bucket in (report["flagged_items"], report["deferred_items"])
        for row in bucket
        for item in row.get("evidence", [])
    }
    assert "src/legacy/gone.py" in evidence


def test_api_aggregation_ignores_non_reference_api_filenames(tmp_path: Path) -> None:
    """R13 5/9: troubleshooting/core-service *API* files must not be the denominator."""
    content = tmp_path / "content"
    (content / "API参考").mkdir(parents=True)
    (content / "故障排除").mkdir()
    (content / "开发指南").mkdir()
    (content / "核心服务").mkdir()
    for name in (
        "API参考.md",
        "认证授权API.md",
        "核心服务API.md",
        "Python服务API.md",
        "错误处理与状态码.md",
    ):
        body = _THIN_API_BODY if name == "错误处理与状态码.md" else _AGGREGATED_API_BODY
        (content / "API参考" / name).write_text(body, encoding="utf-8")
    (content / "API参考" / "核心服务API").mkdir()
    (content / "API参考" / "核心服务API" / "API API.md").write_text(
        _AGGREGATED_API_BODY, encoding="utf-8"
    )
    for rel in ("故障排除/API问题.md", "开发指南/API开发指南.md", "核心服务/API.md"):
        (content / rel).write_text("# 说明\n\nNo endpoint catalog.\n", encoding="utf-8")

    metric = ParityMetricExtractor(content)._measure_api_aggregation()
    details = metric.details or {}
    assert details["total_api_pages"] == 6
    assert details["aggregated_apis"] == 5
    assert metric.measured_value >= PARITY_METRICS["api_aggregation"].threshold
    assert metric.status.value != "fail"

    verifier = QoderLikeVerifierService(tmp_path, strict=True)
    check = verifier._check_qoder_api_aggregation()
    assert check.status == "PASS"
    assert check.reason_code != "QODER_API_AGGREGATION_LOW"


def test_api_aggregation_still_fails_when_reference_pages_are_thin(tmp_path: Path) -> None:
    content = tmp_path / "content"
    (content / "API参考").mkdir(parents=True)
    (content / "API参考" / "API参考.md").write_text(_AGGREGATED_API_BODY, encoding="utf-8")
    (content / "API参考" / "认证授权API.md").write_text(_THIN_API_BODY, encoding="utf-8")
    (content / "API参考" / "错误处理与状态码.md").write_text(_THIN_API_BODY, encoding="utf-8")
    (content / "故障排除").mkdir()
    (content / "故障排除" / "API问题.md").write_text(_AGGREGATED_API_BODY, encoding="utf-8")

    metric = ParityMetricExtractor(content)._measure_api_aggregation()
    details = metric.details or {}
    assert details["total_api_pages"] == 3
    assert details["aggregated_apis"] == 1
    assert metric.measured_value < PARITY_METRICS["api_aggregation"].threshold
    verifier = QoderLikeVerifierService(tmp_path, strict=True)
    check = verifier._check_qoder_api_aggregation()
    assert check.status == "FAIL"
    assert check.reason_code == "QODER_API_AGGREGATION_LOW"
    assert check.gate_type == "HARD" or str(check.gate_type).endswith("HARD")


def test_r13_leftover_hard_gates_remain_hard() -> None:
    threshold = QoderLikeSeverityThreshold()
    for code in (
        "QODER_CRITICAL_FALSE_FACT",
        "QODER_UNRESOLVED_FACT_CONFLICT",
        "QODER_API_AGGREGATION_LOW",
        "STALE_DOC_REFERENCE",
        "QODER_CITATION_FACT_COVERAGE_LOW",
    ):
        assert threshold.is_blocking(code) is True
        assert threshold.get_gate_type(code).value == "HARD"
    assert PARITY_METRICS["api_aggregation"].threshold == 0.60
    verifier_src = Path("repo_wiki/verifier/qoder_strict_verifier.py").read_text(encoding="utf-8")
    assert "if ratio < 0.95:" in verifier_src
    assert "QODER_CRITICAL_FALSE_FACT" in QoderLikeSeverityThreshold.STRICT_HARD_CODES
    assert "QODER_API_AGGREGATION_LOW" in QoderLikeSeverityThreshold.STRICT_HARD_CODES
