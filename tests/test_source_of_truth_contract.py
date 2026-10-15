from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path

import yaml

from repo_wiki.cli import app
from repo_wiki.core.contracts import DataModel, Endpoint, Module, RepositoryInfo, RepositorySnapshot
from repo_wiki.scanner.artifacts import write_source_of_truth

ROOT = Path(__file__).resolve().parents[1]
SOURCE_OF_TRUTH = ROOT / "ai" / "source-of-truth"

COMMAND_CONTRACT = {
    "init": ("init", "repo-wiki init"),
    "index": ("index", "repo-wiki index"),
    "update": ("update", "repo-wiki update"),
    "sync": ("sync", "repo-wiki sync"),
    "search": ("search", "repo-wiki search <query>"),
    "graph": ("graph", "repo-wiki graph <module>"),
    "generate": (
        "generate",
        "repo-wiki generate --profile qoder-like --output .repo-agent-eval",
    ),
    "verify": (
        "verify",
        "repo-wiki verify --profile qoder-like --ci --output .repo-agent-eval",
    ),
    "compare": (
        "compare",
        "repo-wiki compare --target <target-content-dir> "
        "--baseline <qoder-baseline-dir> --output <report-dir> --ci",
    ),
    "release_publish": (
        "release-publish",
        "repo-wiki release-publish --output .repo-agent-eval",
    ),
    "eval_layout_report": (
        "eval-layout-report",
        "repo-wiki eval-layout-report --output .repo-agent-eval",
    ),
    "cost_estimate": ("cost-estimate", "repo-wiki cost-estimate"),
    "config": ("config", "repo-wiki config --ci"),
}


def load_yaml(name: str) -> dict:
    data = yaml.safe_load((SOURCE_OF_TRUTH / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_repo_map_tracks_current_python_cli_and_typescript_extension() -> None:
    repo_map = load_yaml("repo-map.yaml")

    repository = repo_map["repository"]
    assert repository["primary_language"] == "python"
    assert "typescript" in repository["secondary_languages"]
    assert repository["framework"] == "typer-cli"
    assert "repo_wiki/cli.py" in repository["entry_points"]
    assert "extensions/repo-wiki-browser/src/extension.ts" in repository["entry_points"]

    root_path = Path(repository["root_path"])
    assert not root_path.is_absolute()
    assert (ROOT / root_path).resolve() == ROOT

    stale_values = json.dumps(repo_map, ensure_ascii=False).lower()
    assert "express" not in stale_values
    assert '"primary_language": "javascript"' not in stale_values


def test_task_catalog_matches_live_cli_and_extension_release_flow() -> None:
    task_catalog = load_yaml("task-catalog.yaml")
    live_commands = {command.name for command in app.registered_commands}

    required_cli_commands = {cli_name for cli_name, _ in COMMAND_CONTRACT.values()}
    assert required_cli_commands <= live_commands

    configured_commands = task_catalog["commands"]
    for catalog_key, (_, expected_command) in COMMAND_CONTRACT.items():
        assert configured_commands[catalog_key] == expected_command

    tasks = {task["name"]: task for task in task_catalog["tasks"]}
    assert {
        "generate-qoder-like",
        "verify-qoder-like",
        "compare-qoder-baseline",
        "inspect-eval-layout",
        "publish-ready-release",
        "extension-browse-ready-release",
    } <= set(tasks)
    publish_text = json.dumps(tasks["publish-ready-release"], ensure_ascii=False)
    assert "READY" in publish_text
    assert (
        ".repo-agent-eval/repowiki/zh/manifest.json"
        in tasks["extension-browse-ready-release"]["inputs"]
    )

    package_json = json.loads(
        (ROOT / "extensions/repo-wiki-browser/package.json").read_text(encoding="utf-8")
    )
    default_generate = package_json["contributes"]["configuration"]["properties"][
        "repoWikiBrowser.generateCommand"
    ]["default"]
    assert task_catalog["commands"]["extension_update_default"] == default_generate


def test_module_index_covers_importable_symbols_and_ready_release_contract() -> None:
    module_index = load_yaml("module-index.yaml")
    modules = {module["name"]: module for module in module_index["modules"]}

    assert {
        "repo_wiki",
        "repo_wiki.orchestration",
        "repo_wiki.verifier",
        "repo_wiki.viewer",
        "extensions/repo-wiki-browser",
        "ai/source-of-truth",
        "tests",
    } <= set(modules)

    cli_exports = set(modules["repo_wiki"]["commands"])
    assert {cli_name for cli_name, _ in COMMAND_CONTRACT.values()} <= cli_exports

    symbol_groups = {
        group["module"]: group
        for module in modules.values()
        for group in module.get("public_symbols", [])
    }
    required_symbol_modules = {
        "repo_wiki.orchestration.release_publisher",
        "repo_wiki.orchestration.latest_run_selector",
        "repo_wiki.orchestration.readiness_schema",
        "repo_wiki.orchestration.release_meta_schema",
        "repo_wiki.viewer.static_viewer",
    }
    assert required_symbol_modules == set(symbol_groups)

    kind_checks = {"class": inspect.isclass, "function": inspect.isfunction}
    for module_name, group in symbol_groups.items():
        imported_module = importlib.import_module(module_name)
        assert group["symbols"]
        for symbol_spec in group["symbols"]:
            symbol_name = symbol_spec["name"]
            assert not symbol_name.startswith("_")
            symbol = getattr(imported_module, symbol_name)
            assert kind_checks[symbol_spec["kind"]](symbol)
            assert symbol.__module__ == module_name

    orchestration_symbols = json.dumps(
        modules["repo_wiki.orchestration"]["release_symbols"], ensure_ascii=False
    )
    assert ".repo-agent-eval/repowiki/zh/manifest.json" in orchestration_symbols
    assert "release_status" in orchestration_symbols
    assert "readiness_state" in orchestration_symbols
    assert "readiness" in orchestration_symbols
    assert "READY" in orchestration_symbols

    extension_symbols = json.dumps(
        modules["extensions/repo-wiki-browser"]["release_symbols"], ensure_ascii=False
    )
    assert ".repo-agent-eval/repowiki/zh/manifest.json" in extension_symbols
    assert "navigation_tree" in extension_symbols
    assert "READY" in extension_symbols

    serialized = json.dumps(module_index, ensure_ascii=False)
    assert "node_modules" not in serialized


def assert_no_excluded_source_paths(payload: dict) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    for forbidden in (
        "node_modules",
        "tests/test_",
        "tests/fixtures",
        "fixtures/",
        "repo_wiki/scanner/repository_scanner.py",
        "repo_wiki/scanner/database_migrations.py",
    ):
        assert forbidden not in serialized


def test_api_and_data_model_indexes_exclude_non_product_facts() -> None:
    api_index = load_yaml("api-index.yaml")
    data_models = load_yaml("data-models.yaml")

    assert api_index["endpoints"] == []
    assert_no_excluded_source_paths(api_index)
    assert_no_excluded_source_paths(data_models)

    model_names = {model["name"] for model in data_models["models"]}
    assert {
        "RepoWikiConfig",
        "RepositorySnapshot",
        "NavigationTreeNode",
        "WikiSource",
    } <= model_names
    assert {"in", "instanceof", "body", "statement", "statements", "UserModel"}.isdisjoint(
        model_names
    )


def test_generated_task_catalog_tracks_cli_extension_and_excludes_tests() -> None:
    task_catalog = json.loads(
        (SOURCE_OF_TRUTH / "task-catalog.generated.json").read_text(encoding="utf-8")
    )
    live_commands = {command.name for command in app.registered_commands}

    generated_commands = task_catalog["commands"]
    for catalog_key, (cli_name, expected_command) in COMMAND_CONTRACT.items():
        assert cli_name in live_commands
        assert generated_commands[catalog_key] == expected_command
    assert (
        generated_commands["improve"]
        == "repo-wiki improve --profile qoder-like --output .repo-agent-eval"
    )
    assert (
        generated_commands["improve_status"] == "repo-wiki improve-status --output .repo-agent-eval"
    )
    assert (
        generated_commands["extension_update_default"]
        == "uv run repo-wiki generate --profile qoder-like --output .repo-agent-eval"
    )

    assert "tests" not in task_catalog["module_references"]
    serialized = json.dumps(task_catalog, ensure_ascii=False)
    assert "npm run" not in serialized
    assert "node_modules" not in serialized
    assert ".repo-agent-eval/repowiki/zh/manifest.json" in serialized
    assert "repoWikiBrowser.updateWiki" in serialized


def test_write_source_of_truth_filters_tests_vendor_and_parser_pseudo_facts(tmp_path: Path) -> None:
    module = Module(
        name="repo_wiki",
        path="repo_wiki",
        responsibility="CLI package",
        owner="core",
        doc_path="docs/modules/repo_wiki.md",
    )
    snapshot = RepositorySnapshot(
        repository=RepositoryInfo(name="sample", root_path=".", language="python"),
        modules=[module],
        endpoints=[
            Endpoint(
                method="GET",
                path="/real",
                module="repo_wiki",
                handler="real",
                file_path="repo_wiki/api.py",
            ),
            Endpoint(
                method="GET",
                path="/test",
                module="tests",
                handler="test",
                file_path="tests/test_api.py",
            ),
            Endpoint(
                method="GET",
                path="/pseudo",
                module="repo_wiki",
                handler="__init__",
                file_path="repo_wiki/scanner/repository_scanner.py",
            ),
        ],
        data_models=[
            DataModel(
                name="RepoWikiConfig",
                type="python_class",
                module="repo_wiki",
                file_path="repo_wiki/core/config.py",
            ),
            DataModel(
                name="VendoredSchema",
                type="ts_definition",
                module="extensions",
                file_path="extensions/repo-wiki-browser/node_modules/pkg/schema.js",
            ),
            DataModel(
                name="statement",
                type="migration_table",
                module="repo_wiki",
                file_path="repo_wiki/scanner/database_migrations.py",
            ),
        ],
    )

    write_source_of_truth(tmp_path, snapshot)

    api_index = yaml.safe_load(
        (tmp_path / "ai/source-of-truth/api-index.yaml").read_text(encoding="utf-8")
    )
    data_models = yaml.safe_load(
        (tmp_path / "ai/source-of-truth/data-models.yaml").read_text(encoding="utf-8")
    )

    assert [endpoint["path"] for endpoint in api_index["endpoints"]] == ["/real"]
    assert [model["name"] for model in data_models["models"]] == ["RepoWikiConfig"]
