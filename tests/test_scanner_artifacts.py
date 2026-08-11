from __future__ import annotations

import json
import shutil
from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.orchestration import release_meta_schema as rms
from repo_wiki.scanner.artifacts import REQUIRED_SOURCE_OF_TRUTH_FILES, write_source_of_truth
from repo_wiki.scanner.conflict_resolver import resolve_source_docs_conflicts
from repo_wiki.scanner.docs_scanner import scan_repository_docs_inventory
from repo_wiki.scanner.multi_runtime_scanner_v3 import (
    MultiRuntimeSourceScannerV3,
    scan_repository_source_inventory_v3,
    write_source_inventory_json,
)
from repo_wiki.scanner.repository_scanner import RepositoryScanner

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "scanner_v3"


def test_scanner_and_source_of_truth_outputs(tmp_path: Path) -> None:
    (tmp_path / "src" / "users").mkdir(parents=True)
    (tmp_path / "src" / "users" / "routes.py").write_text(
        """
from fastapi import APIRouter

router = APIRouter()

@router.get("/users")
def list_users():
    return []
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "src" / "users" / "models.py").write_text(
        """
from pydantic import BaseModel

class UserModel(BaseModel):
    id: int
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "src" / "users" / "migration.sql").write_text(
        "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY);",
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("fastapi\npydantic\n", encoding="utf-8")

    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    scanner = RepositoryScanner(cfg)
    snapshot = scanner.scan()
    assert snapshot.modules
    assert snapshot.endpoints
    model_names = {m.name for m in snapshot.data_models}
    assert "IF" not in model_names
    assert "users" in model_names

    outputs = write_source_of_truth(tmp_path, snapshot)
    for required in REQUIRED_SOURCE_OF_TRUTH_FILES:
        assert (tmp_path / "ai" / "source-of-truth" / required).exists()
    assert "repo-map.yaml" in outputs


def test_source_of_truth_includes_domain_classification_metadata(tmp_path: Path) -> None:
    """Test that module-index.yaml includes domain classification metadata."""
    (tmp_path / "repo_wiki" / "ai").mkdir(parents=True)
    (tmp_path / "repo_wiki" / "ai" / "embeddings.py").write_text(
        "class EmbeddingProvider:\n    def embed(self): pass\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("fastapi\npydantic\n", encoding="utf-8")

    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    scanner = RepositoryScanner(cfg)
    snapshot = scanner.scan()

    outputs = write_source_of_truth(tmp_path, snapshot)

    # Read module-index.yaml
    import yaml

    module_index_path = tmp_path / "ai" / "source-of-truth" / "module-index.yaml"
    with open(module_index_path) as f:
        module_index = yaml.safe_load(f)

    # Check that modules have domain classification fields
    for module in module_index["modules"]:
        assert "domain" in module, f"Module {module['name']} missing 'domain' field"
        assert "service_family" in module, f"Module {module['name']} missing 'service_family' field"
        assert "runtime_role" in module, f"Module {module['name']} missing 'runtime_role' field"
        assert "domain_confidence" in module, (
            f"Module {module['name']} missing 'domain_confidence' field"
        )
        assert "domain_classification_reason" in module, (
            f"Module {module['name']} missing 'domain_classification_reason' field"
        )


def test_classification_diagnostics_for_mixed_repository(tmp_path: Path) -> None:
    """Test classification diagnostics for mixed repositories with multiple service families."""
    # Create Python backend service
    (tmp_path / "backend" / "api").mkdir(parents=True)
    (tmp_path / "backend" / "api" / "routes.py").write_text(
        "from flask import Flask\nrouter = {}\nrouter.get('/api/users', handler)\n",
        encoding="utf-8",
    )
    (tmp_path / "backend" / "models.py").write_text(
        "class UserModel:\n    pass\n",
        encoding="utf-8",
    )

    # Create TypeScript frontend
    (tmp_path / "frontend" / "src").mkdir(parents=True)
    (tmp_path / "frontend" / "src" / "app.tsx").write_text(
        "const App = () => <div>Hello</div>\nexport default App;\n",
        encoding="utf-8",
    )

    # Create AI service
    (tmp_path / "ai" / "embeddings").mkdir(parents=True)
    (tmp_path / "ai" / "embeddings" / "provider.py").write_text(
        "class EmbeddingProvider:\n    def embed(self): pass\n",
        encoding="utf-8",
    )

    # Create tooling/scripts
    (tmp_path / "scripts").mkdir(parents=True)
    (tmp_path / "scripts" / "run.py").write_text(
        "def run_command():\n    pass\n",
        encoding="utf-8",
    )

    cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path)}})
    scanner = RepositoryScanner(cfg)
    snapshot = scanner.scan()

    outputs = write_source_of_truth(tmp_path, snapshot)

    # Check diagnostics file exists
    diagnostics_path = tmp_path / "ai" / "source-of-truth" / "classification-diagnostics.json"
    assert diagnostics_path.exists(), "Classification diagnostics file should be generated"

    # Read and verify diagnostics
    import json

    with open(diagnostics_path) as f:
        diagnostics = json.load(f)

    assert diagnostics["total_modules"] >= 4, "Should have at least 4 modules"
    assert "service_family_coverage" in diagnostics
    assert "runtime_role_coverage" in diagnostics

    # Check that we have coverage across multiple service families
    sf_coverage = diagnostics["service_family_coverage"]
    assert "python-backend" in sf_coverage or len(sf_coverage) > 0

    # Check runtime role coverage
    rr_coverage = diagnostics["runtime_role_coverage"]
    assert len(rr_coverage) > 0, "Should have runtime role coverage data"


class TestMultiRuntimeSourceScannerV3:
    """Scanner v3 — structured source inventory + release meta compatibility."""

    def test_source_inventory_validates_and_has_distinct_signal_buckets(
        self, tmp_path: Path
    ) -> None:
        shutil.copytree(_FIXTURES / "python_fastapi_service", tmp_path / "repo")
        inv = scan_repository_source_inventory_v3(tmp_path / "repo", incremental=False)
        assert rms.validate_source_inventory(inv) == []
        assert inv["services"], "expected service signals"
        assert inv["api_surfaces"], "expected API surface signals"
        assert inv["data_models"], "expected data model signals (pydantic)"
        assert inv["deployment_assets"], "expected deployment signals"
        assert inv["tests"], "expected test harness signals"

    def test_reference_stub_fixture_covers_multi_stack_signals(self, tmp_path: Path) -> None:
        shutil.copytree(_FIXTURES / "reference_repo_stub", tmp_path / "repo")
        inv = scan_repository_source_inventory_v3(tmp_path / "repo", incremental=False)
        assert rms.validate_source_inventory(inv) == []
        assert len(inv["services"]) >= 2
        assert inv["api_surfaces"]
        assert inv["data_models"]
        assert inv["frontend_callers"]
        assert inv["deployment_assets"]

    def test_ts_express_fixture_frontend_and_api(self, tmp_path: Path) -> None:
        shutil.copytree(_FIXTURES / "ts_express_service", tmp_path / "repo")
        inv = scan_repository_source_inventory_v3(tmp_path / "repo", incremental=False)
        assert rms.validate_source_inventory(inv) == []
        assert inv["api_surfaces"]
        assert inv["frontend_callers"]

    def test_incremental_scan_skips_unchanged_files(self, tmp_path: Path) -> None:
        shutil.copytree(_FIXTURES / "python_fastapi_service", tmp_path / "repo")
        root = tmp_path / "repo"
        cfg = RepoWikiConfig.model_validate({"project": {"root": str(root)}})
        s1 = MultiRuntimeSourceScannerV3(cfg).scan(incremental=True)
        assert s1["scanner"]["stats"]["files_rescanned"] >= 1
        assert s1["scanner"]["stats"]["files_cached"] == 0

        s2 = MultiRuntimeSourceScannerV3(cfg).scan(incremental=True)
        assert s2["scanner"]["stats"]["files_cached"] >= 1
        assert s2["scanner"]["stats"]["files_rescanned"] == 0

        main_py = root / "src" / "main.py"
        main_py.write_text(main_py.read_text(encoding="utf-8") + "\n# touch\n", encoding="utf-8")
        s3 = MultiRuntimeSourceScannerV3(cfg).scan(incremental=True)
        assert s3["scanner"]["stats"]["files_rescanned"] >= 1

    def test_write_source_inventory_json_default_path(self, tmp_path: Path) -> None:
        shutil.copytree(_FIXTURES / "python_fastapi_service", tmp_path / "repo")
        cfg = RepoWikiConfig.model_validate({"project": {"root": str(tmp_path / "repo")}})
        out = write_source_inventory_json(cfg, incremental=False)
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert rms.validate_source_inventory(data) == []

    def test_source_docs_conflict_report_has_resolved_deferred_flagged(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "repo"
        shutil.copytree(_FIXTURES / "python_fastapi_service", repo)
        (repo / "docs").mkdir(parents=True, exist_ok=True)
        (repo / "docs" / "stale-plan.md").write_text(
            "# Planning\n\nLegacy `src/ghost/service.py` and FutureService details.\n",
            encoding="utf-8",
        )
        source_inv = scan_repository_source_inventory_v3(repo, incremental=False)
        docs_inv = scan_repository_docs_inventory(repo, source_inv, incremental=False)
        report = resolve_source_docs_conflicts(source_inv, docs_inv)

        assert "resolved_items" in report
        assert "deferred_items" in report
        assert "flagged_items" in report
        assert "reason_codes" in report
