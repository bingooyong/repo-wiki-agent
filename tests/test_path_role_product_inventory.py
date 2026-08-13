"""Library/framework trees must not treat tests/examples/docs as product HTTP APIs."""

from __future__ import annotations

from pathlib import Path

import yaml

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.scanner.artifacts import write_source_of_truth
from repo_wiki.scanner.multi_runtime_scanner_v3 import scan_repository_source_inventory_v3
from repo_wiki.scanner.repository_scanner import RepositoryScanner

_PRODUCT_API_ROLES = frozenset({"api-server", "api-gateway"})
_PRODUCT_CORE_DOMAINS = frozenset({"core-platform", "api-gateway"})


def _write_library_tree(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / "src" / "lib.py").write_text(
        "def add(left: int, right: int) -> int:\n    return left + right\n",
        encoding="utf-8",
    )
    (root / "examples").mkdir()
    (root / "examples" / "app.py").write_text(
        """
from flask import Flask

app = Flask(__name__)


@app.route("/")
def index():
    return "ok"


@app.route("/result/<id>")
def result(id):
    return id
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_app.py").write_text(
        """
from flask import Flask

app = Flask(__name__)


@app.route("/")
def test_index():
    return "test"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir()
    (root / "docs" / "conf.py").write_text(
        "project = 'lib'\nextensions = ['sphinx.ext.autodoc']\n# Sphinx API docs\n",
        encoding="utf-8",
    )


def test_examples_tests_docs_are_not_product_api_services(tmp_path: Path) -> None:
    _write_library_tree(tmp_path)
    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    snapshot = RepositoryScanner(cfg).scan()

    by_path = {module.path: module for module in snapshot.modules}
    assert (
        "src" in by_path or "src/lib" in by_path or any("lib" in m.path for m in snapshot.modules)
    )

    for name in ("examples", "tests", "docs"):
        module = by_path.get(name)
        assert module is not None, f"expected {name}/ to remain a citable module"
        assert module.runtime_role not in _PRODUCT_API_ROLES, (
            f"{name}/ must not be a product api-server (got {module.runtime_role})"
        )
        assert module.domain not in _PRODUCT_CORE_DOMAINS, (
            f"{name}/ must not be a core/api-gateway product service (got {module.domain})"
        )

    product_paths = {endpoint.path for endpoint in snapshot.endpoints}
    assert "/" not in product_paths
    assert "/result/<id>" not in product_paths
    assert all(
        "examples/" not in endpoint.file_path
        and "tests/" not in endpoint.file_path
        and "docs/" not in endpoint.file_path
        for endpoint in snapshot.endpoints
    )


def test_product_api_index_omits_example_and_test_routes(tmp_path: Path) -> None:
    _write_library_tree(tmp_path)
    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    snapshot = RepositoryScanner(cfg).scan()
    write_source_of_truth(tmp_path, snapshot)

    api_index = yaml.safe_load((tmp_path / "ai" / "source-of-truth" / "api-index.yaml").read_text())
    endpoints = api_index.get("endpoints") or []
    assert endpoints == []

    module_index = yaml.safe_load(
        (tmp_path / "ai" / "source-of-truth" / "module-index.yaml").read_text()
    )
    for module in module_index["modules"]:
        if module["path"] in {"examples", "tests", "docs"}:
            assert module["runtime_role"] not in _PRODUCT_API_ROLES
            assert module["domain"] not in _PRODUCT_CORE_DOMAINS


def test_multi_runtime_inventory_keeps_example_routes_out_of_product_apis(
    tmp_path: Path,
) -> None:
    _write_library_tree(tmp_path)
    inventory = scan_repository_source_inventory_v3(tmp_path, incremental=False)

    api_paths = {
        (item.get("path"), item.get("evidence_path")) for item in inventory["api_surfaces"]
    }
    assert not any(
        evidence and ("examples/" in evidence or "tests/" in evidence or "docs/" in evidence)
        for _path, evidence in api_paths
    )
    service_evidence = [item.get("evidence_path", "") for item in inventory["services"]]
    assert not any(
        path.startswith("examples/") or path.startswith("tests/") or path.startswith("docs/")
        for path in service_evidence
    )
