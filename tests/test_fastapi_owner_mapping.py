"""Owner coverage must bind mounted FastAPI paths to defining file/handler.

R7: after #46/#48 prefixes were correct, HARD QODER_OWNER_COVERAGE_MISSING
still reported 19/19 `/api/*` owner-missing. Inventory identifiers were already
`POST /api/users/login`; owner keys never joined to that mounted pair.
"""

from __future__ import annotations

import json
from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.scanner.multi_runtime_scanner_v3 import scan_repository_source_inventory_v3
from repo_wiki.scanner.repository_scanner import RepositoryScanner
from repo_wiki.verifier.ownership_coverage import (
    OwnerInventoryItem,
    collect_owner_inventory_items,
    map_mounted_api_owners,
    owner_coverage_gaps,
    page_has_owner_or_warning,
)
from repo_wiki.verifier.qoder_strict_verifier import QoderLikeVerifierService
from tests.test_fastapi_router_inventory import (
    _endpoint_pairs,
    _v3_endpoint_pairs,
    _write_realworld_fastapi_tree,
)


def _scan(root: Path):
    cfg = RepoWikiConfig.model_validate({"project": {"root": str(root)}})
    return RepositoryScanner(cfg).scan()


def _write_scanned_meta(meta_root: Path, api_surfaces: list[dict]) -> None:
    meta_root.mkdir(parents=True, exist_ok=True)
    (meta_root / "source-inventory.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.source_inventory/1.0",
                "api_surfaces": api_surfaces,
            }
        ),
        encoding="utf-8",
    )


def test_owner_mapping_joins_mounted_login_to_defining_handler(tmp_path: Path) -> None:
    """Factory + settings.api_prefix=/api + /users + POST /login must own the mount."""
    _write_realworld_fastapi_tree(tmp_path)
    snapshot = _scan(tmp_path)
    inventory = scan_repository_source_inventory_v3(tmp_path, incremental=False)

    scanner_owners = map_mounted_api_owners(snapshot.endpoints)
    v3_owners = map_mounted_api_owners(inventory["api_surfaces"])

    for owners in (scanner_owners, v3_owners):
        login = owners["POST /api/users/login"]
        assert login.defining_handler == "login"
        assert login.defining_file.replace("\\", "/").endswith("app/api/routes/authentication.py")
        assert "POST /login" not in owners
        assert "POST /users/login" not in owners


def test_owner_coverage_does_not_report_mounted_login_missing(tmp_path: Path) -> None:
    """R7 shape: pages mention POST /api/users/login without owner prose; inventory has owner."""
    _write_realworld_fastapi_tree(tmp_path)
    inventory = scan_repository_source_inventory_v3(tmp_path, incremental=False)
    meta_root = tmp_path / "meta"
    _write_scanned_meta(meta_root, inventory["api_surfaces"])

    items = collect_owner_inventory_items(meta_root)
    login = next(item for item in items if item.identifier == "POST /api/users/login")
    assert login.kind == "api"
    assert login.defining_handler == "login"
    assert login.defining_file.replace("\\", "/").endswith("app/api/routes/authentication.py")

    pages = [
        "API参考列出 POST /api/users/login 与 GET /api/articles。",
    ]
    assert page_has_owner_or_warning(pages[0], "POST /api/users/login")[0] is False

    missing = owner_coverage_gaps(items, pages, warnings=set())
    missing_ids = {item.identifier for item in missing if item.kind == "api"}
    assert "POST /api/users/login" not in missing_ids


def test_owner_coverage_still_missing_without_defining_owner() -> None:
    """Do not relax HARD: path-only APIs without file/handler stay owner-missing."""
    orphan = OwnerInventoryItem(kind="api", identifier="GET /ghost", source="api-inventory.json")
    missing = owner_coverage_gaps(
        [orphan],
        ["GET /ghost is listed in the API reference."],
        warnings=set(),
    )
    assert [item.identifier for item in missing] == ["GET /ghost"]


def test_prefix_join_inventory_stays_mounted(tmp_path: Path) -> None:
    """Keep #43/#45/#46/#48 prefix-join behavior: inventory keys are /api/..., not /login."""
    _write_realworld_fastapi_tree(tmp_path)
    scanner_pairs = _endpoint_pairs(_scan(tmp_path))
    v3_pairs = _v3_endpoint_pairs(tmp_path)
    mounted = {("POST", "/api/users/login")}

    assert mounted <= scanner_pairs
    assert mounted <= v3_pairs
    assert ("POST", "/login") not in scanner_pairs
    assert ("POST", "/login") not in v3_pairs
    assert ("POST", "/users/login") not in scanner_pairs
    assert ("POST", "/users/login") not in v3_pairs


def test_qoder_owner_check_accepts_inventory_defining_owner(tmp_path: Path) -> None:
    """Verify HARD owner check must use the mounted-path → file/handler join."""
    _write_realworld_fastapi_tree(tmp_path)
    inventory = scan_repository_source_inventory_v3(tmp_path, incremental=False)

    run_dir = tmp_path / ".repo-agent-eval" / "runs" / "run-owner-map"
    content_dir = run_dir / "repowiki" / "zh" / "content"
    meta_dir = run_dir / "repowiki" / "zh" / "meta"
    content_dir.mkdir(parents=True)
    meta_dir.mkdir(parents=True)
    page_rel = "API参考/API参考.md"
    page = content_dir / page_rel
    page.parent.mkdir()
    page.write_text(
        "# API参考\n\n## 目录\n- [接口](#接口)\n\n## 接口\n\n"
        "POST /api/users/login is listed in the API reference.\n",
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
                "generated_at": "2026-08-14T00:00:00Z",
                "pages": [
                    {
                        "page_id": "api-reference",
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
    (meta_dir / "source-inventory.json").write_text(
        json.dumps(
            {
                "schema_version": "repo_agent.source_inventory/1.0",
                "services": [{"service_id": "api-server"}],
                "api_surfaces": inventory["api_surfaces"],
                "data_models": [],
                "runtime_entrypoints": [{"entrypoint": "uvicorn"}],
            }
        ),
        encoding="utf-8",
    )
    (meta_dir / "service-registry.json").write_text(
        json.dumps({"services": [{"service_id": "api-server"}]}),
        encoding="utf-8",
    )
    (meta_dir / "runtime-inventory.json").write_text(
        json.dumps({"runtime_entrypoints": [{"entrypoint": "uvicorn"}]}),
        encoding="utf-8",
    )
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "version": "1.1",
                "run_id": "run-owner-map",
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

    verifier = QoderLikeVerifierService(run_dir, strict=True)
    check = verifier._check_qoder_owner_inventory_coverage()
    missing = (check.details or {}).get("missing") or []
    missing_ids = {item.get("identifier") for item in missing}
    assert "POST /api/users/login" not in missing_ids
