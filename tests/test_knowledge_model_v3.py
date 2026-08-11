from __future__ import annotations

from pathlib import Path

from repo_wiki.orchestration import release_meta_schema as rms
from repo_wiki.scanner.knowledge_model_v3 import (
    build_knowledge_model_v3,
    diff_knowledge_models,
    export_model_summary_for_release_meta,
    is_model_stale,
    load_knowledge_model_v3,
    persist_knowledge_model_v3,
)


def _source_inventory() -> dict:
    return {
        "repository_root": "/repo",
        "services": [
            {"service_id": "svc-user", "runtime": "python", "evidence_path": "src/user.py"}
        ],
        "api_surfaces": [
            {
                "service_id": "svc-user",
                "method": "GET",
                "path": "/users",
                "evidence_path": "src/api.py",
            }
        ],
        "data_models": [
            {
                "name": "UserModel",
                "kind": "python_model",
                "service_id": "svc-user",
                "evidence_path": "src/models.py",
            }
        ],
        "frontend_callers": [{"target": "/users", "evidence_path": "web/app.ts"}],
        "deployment_assets": [{"kind": "dockerfile", "evidence_path": "Dockerfile"}],
        "tests": [{"framework_guess": "pytest", "evidence_path": "tests/test_api.py"}],
        "files": [{"path": "src/user.py"}],
    }


def _docs_inventory() -> dict:
    return {
        "documents": [
            {
                "path": "README.md",
                "doc_type": "readme",
                "authority_level": "source_backed",
                "authority_score": 0.9,
                "freshness_score": 1.0,
                "conflict_level": "aligned",
                "stale_references": [],
                "conflicting_claims": [],
                "content_sha256": "abc",
            }
        ]
    }


def _conflict_report() -> dict:
    return {
        "resolved_items": [],
        "deferred_items": [
            {
                "doc_path": "docs/plan.md",
                "reason_code": "MISSING_SOURCE_CONFIRMATION",
                "message": "claim not backed",
                "evidence": ["FutureService"],
            }
        ],
        "flagged_items": [],
    }


def test_build_model_has_all_9_record_types() -> None:
    model = build_knowledge_model_v3(_source_inventory(), _docs_inventory(), _conflict_report())
    assert model["schema_version"].startswith("repo_agent.knowledge_model_v3/")
    records = model["records"]
    for key in (
        "repository",
        "services",
        "api_surfaces",
        "data_models",
        "frontend_consumers",
        "operation_assets",
        "doc_artifacts",
        "evidence_spans",
        "conflicts",
    ):
        assert key in records
        assert isinstance(records[key], list)


def test_diff_between_two_snapshots() -> None:
    old = build_knowledge_model_v3(_source_inventory(), _docs_inventory(), _conflict_report())
    new_source = _source_inventory()
    new_source["services"].append(
        {"service_id": "svc-billing", "runtime": "go", "evidence_path": "svc/billing.go"}
    )
    new = build_knowledge_model_v3(new_source, _docs_inventory(), _conflict_report())
    diff = diff_knowledge_models(old, new)
    assert diff["record_diffs"]["services"]["added_count"] >= 1
    assert "service_count" in diff["summary_delta"]


def test_incremental_persistence_reuses_unchanged_model(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    source = _source_inventory()
    docs = _docs_inventory()
    conflicts = _conflict_report()

    model1, reused1 = persist_knowledge_model_v3(repo, source, docs, conflicts, incremental=True)
    assert reused1 is False
    model2, reused2 = persist_knowledge_model_v3(repo, source, docs, conflicts, incremental=True)
    assert reused2 is True
    assert model1["input_fingerprints"] == model2["input_fingerprints"]


def test_stale_invalidation_detects_changed_inputs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    source = _source_inventory()
    docs = _docs_inventory()
    conflicts = _conflict_report()
    model, _ = persist_knowledge_model_v3(repo, source, docs, conflicts, incremental=True)
    assert is_model_stale(model, source, docs, conflicts) is False

    changed_docs = _docs_inventory()
    changed_docs["documents"][0]["freshness_score"] = 0.7
    assert is_model_stale(model, source, changed_docs, conflicts) is True

    model2, reused = persist_knowledge_model_v3(
        repo, source, changed_docs, conflicts, incremental=True
    )
    assert reused is False
    loaded = load_knowledge_model_v3(repo)
    assert loaded is not None
    assert loaded["input_fingerprints"] == model2["input_fingerprints"]


def test_export_summary_is_quality_report_compatible() -> None:
    model = build_knowledge_model_v3(_source_inventory(), _docs_inventory(), _conflict_report())
    summary = export_model_summary_for_release_meta(model)
    assert rms.validate_quality_report(summary) == []
    assert "knowledge_model_v3" in summary["metrics"]
