from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from typer.testing import CliRunner

from repo_wiki.cli import app
from repo_wiki.knowledge_plan import dump_plan_yaml, generate_plan

runner = CliRunner()


def _knowledge_model(*, extra_doc: bool = False) -> dict[str, Any]:
    docs = [
        {
            "doc_id": "doc:readme",
            "path": "README.md",
            "doc_type": "overview",
            "authority": "primary",
            "content_sha256": "abc123",
        }
    ]
    if extra_doc:
        docs.append(
            {
                "doc_id": "doc:ops",
                "path": "docs/ops.md",
                "doc_type": "operations",
                "authority": "secondary",
                "content_sha256": "def456",
            }
        )
    return {
        "schema_version": "repo_agent.knowledge_model_v3/1.0",
        "input_fingerprints": {"source_inventory": "srcfp", "docs_inventory": "docsfp"},
        "summary": {
            "repository_count": 1,
            "service_count": 1,
            "api_surface_count": 1,
            "data_model_count": 1,
            "operation_asset_count": 1,
            "conflict_count": 0,
        },
        "records": {
            "repository": [{"repository_id": "repo1"}],
            "services": [
                {
                    "service_id": "service:billing",
                    "runtime": "python-fastapi",
                    "evidence_path": "src/billing/app.py",
                }
            ],
            "api_surfaces": [
                {"api_id": "api:get:/orders", "path": "/orders", "evidence_path": "src/api.py"}
            ],
            "data_models": [
                {"model_id": "model:Order", "name": "Order", "evidence_path": "src/model.py"}
            ],
            "operation_assets": [
                {"asset_id": "ops:docker", "asset_type": "dockerfile", "path": "Dockerfile"}
            ],
            "doc_artifacts": docs,
            "conflicts": [],
        },
    }


def _write_cached_model(repo_root: Path, model: dict[str, Any] | None = None) -> None:
    cache_path = repo_root / ".repo-wiki" / "cache" / "knowledge_model_v3.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(model or _knowledge_model(), ensure_ascii=False), encoding="utf-8"
    )


def test_knowledge_plan_generate_stdout_uses_real_core_api(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["knowledge-plan-generate", "--repo-root", str(tmp_path), "--stdout"],
    )

    assert result.exit_code == 0, result.output
    plan = yaml.safe_load(result.output)
    assert plan["schema_version"] == "repo_agent.knowledge_plan/1.0"
    assert "include" in plan
    assert "page_templates" in plan


def test_knowledge_plan_init_writes_default_path_and_validate_ci_json_passes(
    tmp_path: Path,
) -> None:
    _write_cached_model(tmp_path)
    plan_path = tmp_path / ".repo-wiki" / "knowledge-plan.yaml"

    init_result = runner.invoke(
        app, ["knowledge-plan-init", "--repo-root", str(tmp_path), "--json"]
    )
    assert init_result.exit_code == 0, init_result.output
    assert plan_path.exists()
    assert (
        yaml.safe_load(plan_path.read_text(encoding="utf-8"))["schema_version"]
        == "repo_agent.knowledge_plan/1.0"
    )

    validate_result = runner.invoke(
        app,
        ["knowledge-plan-validate", "--repo-root", str(tmp_path), "--ci", "--json"],
    )
    assert validate_result.exit_code == 0, validate_result.output
    payload = json.loads(validate_result.output)
    assert payload == {"valid": True, "issues": []}


def test_knowledge_plan_refuses_manual_file_without_force_and_force_overwrites(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / ".repo-wiki" / "knowledge-plan.yaml"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text("manual: true\n", encoding="utf-8")

    result = runner.invoke(app, ["knowledge-plan-init", "--repo-root", str(tmp_path)])
    assert result.exit_code != 0
    assert "Refusing to overwrite" in result.output
    assert plan_path.read_text(encoding="utf-8") == "manual: true\n"

    result = runner.invoke(app, ["knowledge-plan-init", "--repo-root", str(tmp_path), "--force"])
    assert result.exit_code == 0, result.output
    written = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "repo_agent.knowledge_plan/1.0"
    assert "generated" in written


def test_knowledge_plan_validate_ci_json_exits_nonzero_for_invalid_real_plan(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / ".repo-wiki" / "knowledge-plan.yaml"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        "schema_version: repo_agent.knowledge_plan/9.9\ninclude: not-a-list\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["knowledge-plan-validate", "--repo-root", str(tmp_path), "--ci", "--json"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["valid"] is False
    codes = {issue["code"] for issue in payload["issues"]}
    assert "schema_version.unsupported" in codes
    assert "include.not_list" in codes


def test_knowledge_plan_impact_json_reports_changed_plan_sections(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline-plan.yaml"
    current_path = tmp_path / ".repo-wiki" / "knowledge-plan.yaml"
    baseline_path.write_text(
        dump_plan_yaml(generate_plan({"summary": {}, "records": {}})), encoding="utf-8"
    )
    current_path.parent.mkdir(parents=True)
    current_path.write_text(
        dump_plan_yaml(generate_plan(_knowledge_model(extra_doc=True))), encoding="utf-8"
    )

    result = runner.invoke(
        app,
        [
            "knowledge-plan-impact",
            "--repo-root",
            str(tmp_path),
            "--baseline",
            str(baseline_path),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "docs/ops.md" in payload["docs"]
    assert "service.module" in payload["templates"]
    assert "服务与模块/" in payload["directories"]
    assert "python-fastapi" in payload["domains"]
    assert any(page.startswith("服务与模块/") for page in payload["pages"])


def test_knowledge_plan_generate_preserves_manual_sections_by_default(tmp_path: Path) -> None:
    _write_cached_model(tmp_path)
    plan_path = tmp_path / ".repo-wiki" / "knowledge-plan.yaml"
    first = runner.invoke(app, ["knowledge-plan-generate", "--repo-root", str(tmp_path)])
    assert first.exit_code == 0, first.output

    stored = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    stored["manual_sections"] = [{"id": "local", "body": "keep"}]
    plan_path.write_text(dump_plan_yaml(stored), encoding="utf-8")
    _write_cached_model(tmp_path, _knowledge_model(extra_doc=True))

    second = runner.invoke(app, ["knowledge-plan-generate", "--repo-root", str(tmp_path)])
    assert second.exit_code == 0, second.output
    regenerated = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    assert regenerated["manual_sections"] == [{"id": "local", "body": "keep"}]
    assert "docs/ops.md" in [item["path"] for item in regenerated["docs"]["allowlist"]]


def test_knowledge_plan_validate_ci_exits_nonzero_for_dirty_managed_content(tmp_path: Path) -> None:
    _write_cached_model(tmp_path)
    init_result = runner.invoke(app, ["knowledge-plan-init", "--repo-root", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output

    plan_path = tmp_path / ".repo-wiki" / "knowledge-plan.yaml"
    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8"))
    plan["include"].append("API参考/")
    plan_path.write_text(dump_plan_yaml(plan), encoding="utf-8")

    result = runner.invoke(
        app, ["knowledge-plan-validate", "--repo-root", str(tmp_path), "--ci", "--json"]
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert "generated.fingerprint.mismatch" in {issue["code"] for issue in payload["issues"]}
