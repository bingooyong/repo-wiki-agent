from copy import deepcopy

import pytest

from repo_wiki.knowledge_plan import (
    ManualEditConflictError,
    analyze_impact,
    dump_plan_yaml,
    generate_plan,
    load_plan,
    load_plan_yaml,
    write_plan,
)


def _model(extra_doc: bool = False) -> dict:
    docs = [
        {
            "doc_id": "doc:readme",
            "path": "README.md",
            "doc_type": "overview",
            "authority": "primary",
        }
    ]
    if extra_doc:
        docs.append(
            {
                "doc_id": "doc:ops",
                "path": "docs/ops.md",
                "doc_type": "operations",
                "authority": "secondary",
            }
        )
    return {
        "schema_version": "repo_agent.knowledge_model_v3/1.0",
        "input_fingerprints": {},
        "summary": {
            "repository_count": 1,
            "service_count": 1,
            "api_surface_count": 0,
            "data_model_count": 0,
        },
        "records": {
            "repository": [{"repository_id": "repo1"}],
            "services": [
                {"service_id": "service:web", "runtime": "python", "evidence_path": "src/web.py"}
            ],
            "doc_artifacts": docs,
            "operation_assets": [],
        },
    }


def test_yaml_round_trip() -> None:
    plan = generate_plan(_model())
    loaded = load_plan_yaml(dump_plan_yaml(plan))

    assert loaded == plan


def test_write_plan_refuses_dirty_managed_sections_and_allows_force(tmp_path) -> None:
    path = tmp_path / "knowledge-plan.yaml"
    plan = generate_plan(_model())
    write_plan(plan, path)

    dirty = load_plan(path)
    dirty["include"].append("API参考/")
    path.write_text(dump_plan_yaml(dirty), encoding="utf-8")

    replacement = generate_plan(_model(extra_doc=True))
    with pytest.raises(ManualEditConflictError):
        write_plan(replacement, path)

    forced = write_plan(replacement, path, overwrite=True)
    assert load_plan(path) == forced
    assert "docs/ops.md" in [item["path"] for item in forced["docs"]["allowlist"]]


def test_write_plan_merge_preserves_manual_sections_with_explicit_merge(tmp_path) -> None:
    path = tmp_path / "knowledge-plan.yaml"
    plan = generate_plan(_model())
    written = write_plan(plan, path)
    written["manual_sections"] = [{"id": "local-note", "body": "Keep this note."}]
    written["include"].append("API参考/")
    path.write_text(dump_plan_yaml(written), encoding="utf-8")

    merged = write_plan(generate_plan(_model(extra_doc=True)), path, merge=True)

    assert merged["manual_sections"] == [{"id": "local-note", "body": "Keep this note."}]
    assert "docs/ops.md" in [item["path"] for item in merged["docs"]["allowlist"]]


def test_impact_analysis_detects_plan_and_model_changes() -> None:
    old_model = _model()
    new_model = deepcopy(old_model)
    new_model["records"]["services"].append(
        {"service_id": "service:worker", "runtime": "python", "evidence_path": "src/worker.py"}
    )
    old_plan = generate_plan(old_model)
    new_plan = generate_plan(_model(extra_doc=True))
    new_plan["page_templates"][0]["title"] = "Updated title"

    impact = analyze_impact(
        old_plan=old_plan, new_plan=new_plan, old_model=old_model, new_model=new_model
    )

    assert "docs/ops.md" in impact["docs"]
    assert new_plan["page_templates"][0]["id"] in impact["templates"]
    assert "服务与模块/" in impact["directories"]
    assert any(
        reason["kind"] == "model" and reason["id"] == "services" for reason in impact["reasons"]
    )
    assert any(page.startswith("服务与模块/") for page in impact["pages"])


def test_write_plan_preserves_manual_sections_by_default_for_managed_plan(tmp_path) -> None:
    path = tmp_path / "knowledge-plan.yaml"
    written = write_plan(generate_plan(_model()), path)
    written["manual_sections"] = [{"id": "operator-note", "body": "Keep this note."}]
    path.write_text(dump_plan_yaml(written), encoding="utf-8")

    regenerated = write_plan(generate_plan(_model(extra_doc=True)), path)

    assert regenerated["manual_sections"] == [{"id": "operator-note", "body": "Keep this note."}]
    assert "docs/ops.md" in [item["path"] for item in regenerated["docs"]["allowlist"]]


def test_impact_analysis_detects_include_and_exclude_scope_changes() -> None:
    old_plan = generate_plan(_model(extra_doc=True))
    new_plan = deepcopy(old_plan)
    new_plan["include"] = [item for item in old_plan["include"] if item != "服务与模块/"]
    new_plan["exclude"] = ["docs/ops.md"]

    impact = analyze_impact(old_plan=old_plan, new_plan=new_plan)

    assert "服务与模块/" in impact["directories"]
    assert "service.module" in impact["templates"]
    assert any(page.startswith("服务与模块/") for page in impact["pages"])
    assert "docs/ops.md" in impact["docs"]
    assert any(reason["kind"] == "include" for reason in impact["reasons"])
    assert any(reason["kind"] == "exclude" for reason in impact["reasons"])
