from __future__ import annotations

import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"
WORKFLOWS_DIR = ROOT / ".github" / "workflows"
EDITABLE_INSTALL_WORKFLOWS = (
    "verify-docs.yml",
    "repo-wiki-strict.yml",
    "repo-wiki-transitional.yml",
    "repo-wiki-pilot.yml",
)


def test_stage0_exit_gate_is_explicit_in_ci() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    gate = workflow["jobs"]["stage0-contract-gate"]
    commands = "\n".join(
        str(step.get("run", "")) for step in gate["steps"] if isinstance(step, dict)
    )

    required_tests = {
        "tests/test_qoder_like_profile.py",
        "tests/test_fixture_ingestion.py",
        "tests/test_benchmark_matrix.py",
        "tests/test_large_repo_fixture.py",
        "tests/test_large_repo_benchmark.py",
        "tests/test_cli_config_doctor.py",
        "tests/test_llm_config.py",
        "tests/test_eval_manifest.py",
        "tests/test_release_meta_schema.py",
        "tests/test_cli_qoder_like.py",
        "tests/test_secret_sentinel_artifacts.py",
        "tests/test_source_of_truth_contract.py",
    }

    assert required_tests <= set(commands.split())
    assert "python -m repo_wiki.main config --ci" in commands
    assert "--api-key-env REPO_WIKI_CI_API_KEY" in commands
    assert "python scripts/secret_sentinel_scan.py" in commands
    assert "README.md docs .github repo_wiki scripts" in commands


def test_stage0_config_gate_uses_only_a_non_secret_placeholder() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    gate = workflow["jobs"]["stage0-contract-gate"]
    config_step = next(
        step for step in gate["steps"] if step.get("name") == "Validate CLI configuration contract"
    )

    assert config_step["env"] == {"REPO_WIKI_CI_API_KEY": "ci-config-placeholder"}


def test_docs_verify_targets_eval_artifacts_not_committed_docs() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    docs_verify = workflow["jobs"]["docs-verify"]
    commands = "\n".join(
        str(step.get("run", "")) for step in docs_verify["steps"] if isinstance(step, dict)
    )

    assert "--profile qoder-like" in commands
    assert "--output" in commands
    assert ".repo-agent-eval" in commands
    assert "Skipping qoder-like verify" in commands
    assert "python -m repo_wiki.main verify --ci --profile qoder-like\n" not in commands
    assert "python -m repo_wiki.main verify --ci --profile qoder-like\r" not in commands


def test_ruff_excludes_markdown_from_format_and_lint_discovery() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extend_exclude = pyproject["tool"]["ruff"].get("extend-exclude", [])
    assert "*.md" in extend_exclude


def test_github_workflows_parse_as_yaml() -> None:
    workflow_files = sorted(WORKFLOWS_DIR.glob("*.yml"))
    assert workflow_files, "expected GitHub workflow YAML files"
    for path in workflow_files:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(loaded, dict), path.name
        assert "jobs" in loaded, path.name


def test_repo_wiki_workflows_install_editable_package() -> None:
    for name in EDITABLE_INSTALL_WORKFLOWS:
        text = (WORKFLOWS_DIR / name).read_text(encoding="utf-8")
        assert "uv pip install --system -e ." in text, name
        assert "pip install pydantic PyYAML rich typer pathspec pytest" not in text, name
