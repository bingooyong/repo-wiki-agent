from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo_wiki.knowledge_plan import attach_fingerprint, dump_plan_yaml, generate_plan
from repo_wiki.orchestration import release_meta_schema as rms
from repo_wiki.scanner.docs_scanner import (
    DocumentationScanner,
    scan_repository_docs_inventory,
    write_docs_inventory_json,
)


def _source_inventory_fixture() -> dict:
    return {
        "services": [
            {
                "service_id": "user-service",
                "name": "UserService",
                "evidence_path": "src/services/user_service.py",
            }
        ],
        "api_surfaces": [
            {
                "path": "/users",
                "method": "GET",
                "handler": "list_users",
                "evidence_path": "src/api/routes.py",
            }
        ],
        "data_models": [
            {"name": "UserModel", "kind": "python_model", "evidence_path": "src/models/user.py"}
        ],
        "frontend_callers": [],
        "deployment_assets": [],
        "tests": [],
    }


def test_docs_inventory_schema_and_doc_types(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Project\nuses `UserService` and `/users`\n", encoding="utf-8"
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "architecture.md").write_text(
        "# Architecture\n`src/services/user_service.py`\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "api.adoc").write_text("= API\n/users\n", encoding="utf-8")

    inv = scan_repository_docs_inventory(tmp_path, _source_inventory_fixture(), incremental=False)
    assert rms.validate_docs_inventory(inv) == []
    assert inv["documents"]
    types = {d["doc_type"] for d in inv["documents"]}
    assert "readme" in types
    assert "architecture" in types
    assert "api" in types


def test_authority_and_freshness_for_stale_and_conflicting_docs(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "roadmap.md").write_text(
        """
# Roadmap
LegacyService will replace all APIs.
Reference path: `src/legacy/service.py`
Deprecated endpoint: `/legacy/v1/users`
""".strip(),
        encoding="utf-8",
    )
    inv = scan_repository_docs_inventory(tmp_path, _source_inventory_fixture(), incremental=False)
    doc = next(d for d in inv["documents"] if d["path"].endswith("roadmap.md"))
    assert doc["doc_type"] == "planning"
    assert doc["authority_level"] in {"historical", "design_doc"}
    assert doc["freshness_score"] < 1.0
    assert doc["conflict_level"] in {"stale", "conflicting"}
    assert doc["stale_references"] or doc["conflicting_claims"]


def test_incremental_cache_skips_unchanged_docs(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Repo\n`UserService`\n", encoding="utf-8")
    scanner = DocumentationScanner(tmp_path)
    first = scanner.scan(_source_inventory_fixture(), incremental=True)
    assert first["scanner"]["stats"]["files_rescanned"] >= 1
    assert first["scanner"]["stats"]["files_cached"] == 0

    second = scanner.scan(_source_inventory_fixture(), incremental=True)
    assert second["scanner"]["stats"]["files_cached"] >= 1


def test_write_docs_inventory_json(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Repo\n", encoding="utf-8")
    out = write_docs_inventory_json(tmp_path, _source_inventory_fixture(), incremental=False)
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert rms.validate_docs_inventory(payload) == []


def test_docs_scanner_accepts_generated_knowledge_plan_filter(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "guides").mkdir()
    (tmp_path / "notes").mkdir()
    (tmp_path / "docs" / "allowed.md").write_text("# Allowed\n", encoding="utf-8")
    (tmp_path / "docs" / "excluded.md").write_text("# Excluded\n", encoding="utf-8")
    (tmp_path / "docs" / "excluded-allowlisted.md").write_text(
        "# Excluded allowlisted\n", encoding="utf-8"
    )
    (tmp_path / "guides" / "ops-runbook.md").write_text("# Ops\n", encoding="utf-8")
    (tmp_path / "notes" / "disallowed.md").write_text("# Disallowed\n", encoding="utf-8")

    knowledge_model = {
        "schema_version": "repo_agent.knowledge_model_v3/1.0",
        "records": {
            "doc_artifacts": [
                {
                    "doc_id": "doc:ops",
                    "path": "guides/ops-runbook.md",
                    "doc_type": "operations",
                    "authority": "source_backed",
                    "content_sha256": "ops-sha",
                },
                {
                    "doc_id": "doc:excluded",
                    "path": "docs/excluded-allowlisted.md",
                    "doc_type": "api",
                    "authority": "source_backed",
                    "content_sha256": "excluded-sha",
                },
            ]
        },
    }
    plan = generate_plan(knowledge_model)
    plan["include"] = ["docs/*.md"]
    plan["exclude"] = ["docs/excluded*.md"]

    inv = scan_repository_docs_inventory(
        tmp_path,
        _source_inventory_fixture(),
        incremental=False,
        docs_filter=plan,
    )

    docs_by_path = {doc["path"]: doc for doc in inv["documents"]}
    assert set(docs_by_path) == {"docs/allowed.md", "guides/ops-runbook.md"}
    assert docs_by_path["guides/ops-runbook.md"]["doc_type"] == "operations"
    assert docs_by_path["guides/ops-runbook.md"]["authority_level"] == "source_backed"
    assert "docs/excluded.md" not in docs_by_path
    assert "docs/excluded-allowlisted.md" not in docs_by_path
    assert "notes/disallowed.md" not in docs_by_path
    assert inv["scanner"]["docs_filter_active"] is True


def test_docs_scan_filter_allowlist_limits_and_includes_extra_docs(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Repo\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "kept.md").write_text("# Kept\n", encoding="utf-8")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "runbook.txt").write_text("Runbook\n", encoding="utf-8")

    inv = scan_repository_docs_inventory(
        tmp_path,
        _source_inventory_fixture(),
        incremental=False,
        docs_filter={
            "include": ["docs/kept.md"],
            "docs": {"allowlist": [{"path": "notes/runbook.txt"}]},
        },
    )

    assert {doc["path"] for doc in inv["documents"]} == {"docs/kept.md", "notes/runbook.txt"}
    assert inv["scanner"]["docs_filter_active"] is True


def test_docs_scan_filter_exclude_wins(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "kept.md").write_text("# Kept\n", encoding="utf-8")
    (tmp_path / "docs" / "hidden.md").write_text("# Hidden\n", encoding="utf-8")

    inv = scan_repository_docs_inventory(
        tmp_path,
        _source_inventory_fixture(),
        incremental=False,
        docs_filter={"include": ["docs/*.md"], "exclude": ["docs/hidden.md"]},
    )

    assert {doc["path"] for doc in inv["documents"]} == {"docs/kept.md"}


def test_docs_scan_filter_allowlist_overrides_authority_and_doc_type(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "note.md").write_text("# Note\n", encoding="utf-8")

    inv = scan_repository_docs_inventory(
        tmp_path,
        _source_inventory_fixture(),
        incremental=False,
        docs_filter={
            "docs_allowlist": [
                {
                    "path": "docs/note.md",
                    "doc_type": "operations",
                    "authority": "source_backed",
                    "authority_score": 0.77,
                }
            ]
        },
    )

    doc = inv["documents"][0]
    assert doc["path"] == "docs/note.md"
    assert doc["doc_type"] == "operations"
    assert doc["authority_level"] == "source_backed"
    assert doc["authority_score"] == 0.77


def test_docs_scan_filter_incremental_cache_tracks_filter_changes(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Repo\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "visible.md").write_text("# Visible\n", encoding="utf-8")
    (tmp_path / "docs" / "hidden.md").write_text("# Hidden\n", encoding="utf-8")

    scanner = DocumentationScanner(tmp_path)
    broad = scanner.scan(_source_inventory_fixture(), incremental=True)
    assert {doc["path"] for doc in broad["documents"]} == {
        "README.md",
        "docs/hidden.md",
        "docs/visible.md",
    }

    filtered = scanner.scan(
        _source_inventory_fixture(),
        incremental=True,
        docs_filter={"include": ["docs/visible.md"]},
    )
    assert {doc["path"] for doc in filtered["documents"]} == {"docs/visible.md"}
    assert filtered["scanner"]["stats"]["files_rescanned"] == 1
    assert filtered["scanner"]["stats"]["files_cached"] == 0

    filtered_again = scanner.scan(
        _source_inventory_fixture(),
        incremental=True,
        docs_filter={"include": ["docs/visible.md"]},
    )
    assert {doc["path"] for doc in filtered_again["documents"]} == {"docs/visible.md"}
    assert filtered_again["scanner"]["stats"]["files_cached"] == 1


def test_docs_scan_filter_rejects_traversal_patterns_without_scanning_outside(
    tmp_path: Path,
) -> None:
    outside = tmp_path.parent / "outside-secret-doc.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    try:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "inside.md").write_text("# Inside\n", encoding="utf-8")

        inv = scan_repository_docs_inventory(
            tmp_path,
            _source_inventory_fixture(),
            incremental=False,
            docs_filter={
                "include": ["../outside-secret-doc.md"],
                "docs": {"allowlist": [{"path": "../outside-secret-doc.md"}]},
            },
        )

        assert {doc["path"] for doc in inv["documents"]} == set()
    finally:
        outside.unlink(missing_ok=True)


def test_docs_scan_lifecycle_loads_default_knowledge_plan(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Repo\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "kept.md").write_text("# Kept\n", encoding="utf-8")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "ignored.md").write_text("# Ignored\n", encoding="utf-8")

    plan = generate_plan(
        {
            "records": {
                "doc_artifacts": [
                    {"path": "docs/kept.md", "doc_type": "operations", "authority": "source_backed"}
                ]
            }
        }
    )
    plan["include"] = []
    plan = attach_fingerprint(plan)
    plan_path = tmp_path / ".repo-wiki" / "knowledge-plan.yaml"
    plan_path.parent.mkdir()
    plan_path.write_text(dump_plan_yaml(plan), encoding="utf-8")

    inv = scan_repository_docs_inventory(tmp_path, _source_inventory_fixture(), incremental=False)

    assert {doc["path"] for doc in inv["documents"]} == {"docs/kept.md"}
    assert inv["scanner"]["docs_filter_active"] is True


def test_default_knowledge_plan_invalid_path_fails_closed(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "inside.md").write_text("# Inside\n", encoding="utf-8")
    plan_path = tmp_path / ".repo-wiki" / "knowledge-plan.yaml"
    plan_path.parent.mkdir()
    plan_path.write_text(
        "\n".join(
            [
                "schema_version: repo_agent.knowledge_plan/1.0",
                "include:",
                "  - ../outside.md",
                "overwrite_policy:",
                "  mode: protect_manual_edits",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Default knowledge plan is invalid"):
        scan_repository_docs_inventory(tmp_path, _source_inventory_fixture(), incremental=False)
