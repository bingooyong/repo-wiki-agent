"""R12 leftover HARD: README path claims and package-dir compose service owners.

R12 MiniMax-M3 ``r12-2026-08-17b`` still failed:

- ``QODER_UNRESOLVED_FACT_CONFLICT`` — README.rst ``STALE_DOC_REFERENCE`` for
  ``.env`` / ``/docs`` / ``/redoc``. Those are a local env file and FastAPI
  HTTP routes, not missing source files. The same conflict JSON is also copied
  to ``reports/`` and ``meta/``.
- ``QODER_OWNER_COVERAGE_MISSING`` — docker-compose services ``app`` and ``db``.
  ``app`` is also the Python package directory. Inventory has
  ``evidence_path``; owner coverage never joined it.
"""

from __future__ import annotations

import json
from pathlib import Path

from repo_wiki.scanner.conflict_resolver import resolve_source_docs_conflicts
from repo_wiki.scanner.docs_scanner import (
    _extract_claims,
    scan_repository_docs_inventory,
)
from repo_wiki.scanner.multi_runtime_scanner_v3 import scan_repository_source_inventory_v3
from repo_wiki.verifier.ownership_coverage import (
    OwnerInventoryItem,
    collect_owner_inventory_items,
    owner_coverage_gaps,
)
from repo_wiki.verifier.qoder_strict_verifier import (
    QoderLikeSeverityThreshold,
    QoderLikeVerifierService,
)
from tests.test_fastapi_router_inventory import _write_realworld_fastapi_tree

_README_RST = """
Quickstart
----------

Then create ``.env`` file (or rename and modify ``.env.example``) in project root.

Ensure the DATABASE_URL variable is set correctly in the `.env` file.

Web routes
----------

All routes are available on ``/docs`` or ``/redoc`` paths with Swagger or ReDoc.

Project structure
-----------------

Files related to application are in the ``app`` or ``tests`` directories.
The handler lives in ``app/main.py``.
The removed module was ``src/legacy/gone.py``.
""".strip()

_COMPOSE_YML = """
version: '3'

services:
  app:
    build: .
    restart: on-failure
    ports:
      - "8000:8000"
    depends_on:
      - db
  db:
    image: postgres:11.5-alpine
    ports:
      - "5432:5432"
""".lstrip()


def _source_inventory() -> dict:
    return {
        "services": [
            {
                "kind": "python_fastapi_app",
                "evidence_path": "app/main.py",
            }
        ],
        "api_surfaces": [],
        "data_models": [],
        "frontend_callers": [],
        "deployment_assets": [],
        "tests": [],
    }


def _write_scanned_meta(meta_root: Path, inventory: dict) -> None:
    meta_root.mkdir(parents=True, exist_ok=True)
    (meta_root / "source-inventory.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.source_inventory/1.0",
                "services": inventory.get("services") or [],
                "api_surfaces": inventory.get("api_surfaces") or [],
                "data_models": inventory.get("data_models") or [],
                "runtime_entrypoints": [{"entrypoint": "uvicorn"}],
            }
        ),
        encoding="utf-8",
    )


def _write_ready_run(run_dir: Path, *, page_body: str, services: list[dict]) -> Path:
    content_dir = run_dir / "repowiki" / "zh" / "content"
    meta_dir = run_dir / "repowiki" / "zh" / "meta"
    content_dir.mkdir(parents=True)
    meta_dir.mkdir(parents=True)
    page_rel = "核心服务/服务.md"
    page = content_dir / page_rel
    page.parent.mkdir()
    page.write_text(
        "# 核心服务\n\n## 目录\n- [服务](#服务)\n\n## 服务\n\n" + page_body,
        encoding="utf-8",
    )
    (meta_dir / "quality-report.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.quality_report/1.0",
                "summary": {"profile": "qoder-like", "grade": "PASS", "strict_mode": True},
                "page_quality": [{"relative_path": page_rel, "quality_state": "READY"}],
                "warnings": [],
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
                        "page_id": "core-services",
                        "relative_path": page_rel,
                        "category": "core-service",
                        "page_type": "content",
                        "quality_state": "READY",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (meta_dir / "source-inventory.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.source_inventory/1.0",
                "services": services,
                "api_surfaces": [],
                "data_models": [],
                "runtime_entrypoints": [{"entrypoint": "uvicorn"}],
            }
        ),
        encoding="utf-8",
    )
    (meta_dir / "service-registry.json").write_text(
        json.dumps({"services": services}),
        encoding="utf-8",
    )
    (meta_dir / "runtime-inventory.json").write_text(
        json.dumps({"runtime_entrypoints": [{"entrypoint": "uvicorn"}]}),
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


def test_readme_env_and_openapi_ui_paths_are_not_source_file_claims() -> None:
    _names, path_like = _extract_claims(_README_RST)
    assert ".env" not in path_like
    assert ".env.example" not in path_like
    assert "/docs" not in path_like
    assert "/redoc" not in path_like
    assert "app/main.py" in path_like
    assert "src/legacy/gone.py" in path_like


def test_readme_rst_does_not_flag_env_or_openapi_ui_as_stale(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("app = True\n", encoding="utf-8")
    (tmp_path / "README.rst").write_text(_README_RST + "\n", encoding="utf-8")

    inv = scan_repository_docs_inventory(
        tmp_path, _source_inventory(), incremental=False, persist_cache=False
    )
    readme = next(doc for doc in inv["documents"] if doc["path"] == "README.rst")
    stale = set(readme["stale_references"])
    assert ".env" not in stale
    assert ".env.example" not in stale
    assert "/docs" not in stale
    assert "/redoc" not in stale
    assert "src/legacy/gone.py" in stale
    assert "app/main.py" not in stale


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
    assert report["summary"]["flagged_count"] + report["summary"]["deferred_count"] >= 1


def test_readme_env_openapi_scan_is_not_unresolved_fact_conflict(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("app = True\n", encoding="utf-8")
    (tmp_path / "README.rst").write_text(
        "Create ``.env``. Swagger UI is ``/docs`` or ``/redoc``.\nEntry: ``app/main.py``\n",
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

    run_dir = tmp_path / ".repo-agent-eval" / "runs" / "run-readme-conflict"
    meta_dir = _write_ready_run(
        run_dir,
        page_body="uvicorn entrypoint is owned by Platform Team.\n",
        services=[{"service_id": "api-server", "evidence_path": "app/main.py"}],
    )
    (meta_dir / "source-docs-conflicts.json").write_text(
        json.dumps(report),
        encoding="utf-8",
    )
    verifier = QoderLikeVerifierService(run_dir, strict=True)
    check = verifier._check_qoder_unresolved_fact_conflicts()
    assert check.status == "PASS"
    result = verifier.verify(ci=True)
    assert "QODER_UNRESOLVED_FACT_CONFLICT" not in result.get("hard_gate_codes", [])


def test_duplicate_conflict_json_in_reports_and_meta_is_counted_once(tmp_path: Path) -> None:
    payload = {
        "schema_version": "source-docs-conflict-resolver-v1",
        "summary": {
            "resolved_count": 0,
            "deferred_count": 0,
            "flagged_count": 1,
            "total_items": 1,
        },
        "resolved_items": [],
        "deferred_items": [],
        "flagged_items": [
            {
                "doc_path": "README.rst",
                "reason_code": "STALE_DOC_REFERENCE",
                "status": "flagged",
                "evidence": ["src/legacy/gone.py"],
            }
        ],
    }
    run_dir = tmp_path / ".repo-agent-eval" / "runs" / "run-dup-conflict"
    meta_dir = _write_ready_run(
        run_dir,
        page_body="uvicorn entrypoint is owned by Platform Team.\n",
        services=[{"service_id": "api-server", "evidence_path": "app/main.py"}],
    )
    encoded = json.dumps(payload)
    (meta_dir / "source-docs-conflicts.json").write_text(encoded, encoding="utf-8")
    reports = run_dir / "reports"
    reports.mkdir()
    (reports / "source-docs-conflicts.json").write_text(encoded, encoding="utf-8")

    verifier = QoderLikeVerifierService(run_dir, strict=True)
    check = verifier._check_qoder_unresolved_fact_conflicts()
    assert check.status == "FAIL"
    assert check.reason_code == "QODER_UNRESOLVED_FACT_CONFLICT"
    artifacts = (check.details or {}).get("artifacts") or []
    assert len(artifacts) == 1


def test_compose_services_join_package_dir_and_compose_file(tmp_path: Path) -> None:
    _write_realworld_fastapi_tree(tmp_path)
    (tmp_path / "docker-compose.yml").write_text(_COMPOSE_YML, encoding="utf-8")
    assert (tmp_path / "app").is_dir()

    inventory = scan_repository_source_inventory_v3(tmp_path, incremental=False)
    compose = [
        item for item in inventory["services"] if item.get("kind") == "docker_compose_service"
    ]
    names = {item.get("name") for item in compose}
    assert {"app", "db"} <= names
    by_name = {item["name"]: item for item in compose}
    assert by_name["app"]["evidence_path"].replace("\\", "/").endswith("docker-compose.yml")
    assert by_name["db"]["evidence_path"].replace("\\", "/").endswith("docker-compose.yml")

    meta_root = tmp_path / "meta"
    _write_scanned_meta(meta_root, inventory)
    items = collect_owner_inventory_items(meta_root)
    app = next(item for item in items if item.kind == "service" and item.identifier == "app")
    db = next(item for item in items if item.kind == "service" and item.identifier == "db")
    assert app.defining_file.replace("\\", "/").endswith("docker-compose.yml")
    assert db.defining_file.replace("\\", "/").endswith("docker-compose.yml")


def test_owner_coverage_does_not_report_compose_app_db_missing(tmp_path: Path) -> None:
    _write_realworld_fastapi_tree(tmp_path)
    (tmp_path / "docker-compose.yml").write_text(_COMPOSE_YML, encoding="utf-8")
    inventory = scan_repository_source_inventory_v3(tmp_path, incremental=False)
    meta_root = tmp_path / "meta"
    _write_scanned_meta(meta_root, inventory)

    items = collect_owner_inventory_items(meta_root)
    pages = ["The Python package directory app/ contains FastAPI handlers."]
    missing = owner_coverage_gaps(items, pages, warnings=set())
    missing_ids = {item.identifier for item in missing if item.kind == "service"}
    assert "app" not in missing_ids
    assert "db" not in missing_ids


def test_owner_coverage_still_missing_named_service_without_defining_owner() -> None:
    orphan = OwnerInventoryItem(kind="service", identifier="ghost", source="source-inventory.json")
    missing = owner_coverage_gaps(
        [orphan],
        ["ghost is listed among repository services."],
        warnings=set(),
    )
    assert [item.identifier for item in missing] == ["ghost"]


def test_qoder_owner_check_accepts_compose_service_defining_owner(tmp_path: Path) -> None:
    _write_realworld_fastapi_tree(tmp_path)
    (tmp_path / "docker-compose.yml").write_text(_COMPOSE_YML, encoding="utf-8")
    inventory = scan_repository_source_inventory_v3(tmp_path, incremental=False)

    run_dir = tmp_path / ".repo-agent-eval" / "runs" / "run-compose-owners"
    _write_ready_run(
        run_dir,
        page_body="FastAPI handlers live under the app package. Postgres is db.\n",
        services=inventory["services"],
    )
    verifier = QoderLikeVerifierService(run_dir, strict=True)
    check = verifier._check_qoder_owner_inventory_coverage()
    missing = (check.details or {}).get("missing") or []
    missing_ids = {item.get("identifier") for item in missing if item.get("kind") == "service"}
    assert "app" not in missing_ids
    assert "db" not in missing_ids


def test_conflict_and_owner_gates_remain_hard() -> None:
    threshold = QoderLikeSeverityThreshold()
    for code in (
        "QODER_UNRESOLVED_FACT_CONFLICT",
        "QODER_OWNER_COVERAGE_MISSING",
        "STALE_DOC_REFERENCE",
        "QODER_CITATION_FACT_COVERAGE_LOW",
    ):
        assert threshold.is_blocking(code) is True
        assert threshold.get_gate_type(code).value == "HARD"
    assert "QODER_UNRESOLVED_FACT_CONFLICT" in QoderLikeSeverityThreshold.STRICT_HARD_CODES
    assert "QODER_OWNER_COVERAGE_MISSING" in QoderLikeSeverityThreshold.STRICT_HARD_CODES
