"""Generate writes scanner-shaped inventories; verify must read those aliases.

R11 leftover HARD after #72 still included QODER_REQUIRED_INVENTORY_MISSING and
QODER_UNRESOLVED_FACT_CONFLICT. Generate emits source-inventory.json with
api_surfaces / data_models / kind-only FastAPI services — not split
api-inventory.json. README prose like "this service implements the API" was
flagged as unresolved conflicts. Gates are not relaxed.
"""

from __future__ import annotations

import json
from pathlib import Path

from repo_wiki.core.config import RepoWikiConfig
from repo_wiki.orchestration.quality_artifacts import write_generation_conflict_artifacts
from repo_wiki.scanner.conflict_resolver import resolve_source_docs_conflicts
from repo_wiki.scanner.docs_scanner import scan_repository_docs_inventory
from repo_wiki.scanner.multi_runtime_scanner_v3 import scan_repository_source_inventory_v3
from repo_wiki.verifier.qoder_strict_verifier import (
    QoderLikeSeverityThreshold,
    QoderLikeVerifierService,
)


def _write_fastapi_repo(root: Path) -> None:
    (root / "app").mkdir(parents=True)
    (root / "app" / "main.py").write_text(
        "from fastapi import FastAPI\n"
        "from pydantic import BaseModel\n\n"
        "app = FastAPI()\n\n"
        "class User(BaseModel):\n"
        "    id: str\n\n"
        "@app.post('/api/users/login')\n"
        "def login():\n"
        "    return {}\n\n"
        "@app.get('/api/articles')\n"
        "def list_articles():\n"
        "    return []\n",
        encoding="utf-8",
    )
    (root / "README.rst").write_text(
        "Conduit RealWorld API\n"
        "=====================\n\n"
        "This FastAPI service implements the RealWorld API for users, articles, "
        "comments, and tags.\n"
        "The model layer uses Pydantic.\n",
        encoding="utf-8",
    )


def _write_release_skeleton(run_dir: Path, meta_dir: Path, content_dir: Path) -> None:
    content_dir.mkdir(parents=True)
    meta_dir.mkdir(parents=True)
    (content_dir / "overview.md").write_text(
        "# Overview\n\n"
        "## Table of Contents\n"
        "- [Intro](#intro)\n\n"
        "## Intro\n\n"
        "Conduit is the FastAPI RealWorld backend.\n",
        encoding="utf-8",
    )
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "version": "1.1",
                "run_id": "run-inventory-wiring",
                "readiness_state": "READY",
                "readiness_reasons": [],
                "target_dirty": False,
                "git_fresh": True,
                "candidate_repowiki_zh_root": str(run_dir / "repowiki" / "zh"),
                "candidate_content_root": str(content_dir),
                "candidate_meta_root": str(meta_dir),
            }
        ),
        encoding="utf-8",
    )


def test_required_inventory_and_conflict_gates_remain_hard() -> None:
    threshold = QoderLikeSeverityThreshold()
    assert threshold.is_blocking("QODER_REQUIRED_INVENTORY_MISSING") is True
    assert threshold.is_blocking("QODER_UNRESOLVED_FACT_CONFLICT") is True


def test_scanner_shaped_source_inventory_is_not_missing_required_inventories(
    tmp_path: Path,
) -> None:
    """api_surfaces/data_models/kind-only services must populate required inventories."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_fastapi_repo(repo)
    run_dir = repo / ".repo-agent-eval" / "runs" / "run-x"
    meta_dir = run_dir / "repowiki" / "zh" / "meta"
    content_dir = run_dir / "repowiki" / "zh" / "content"
    reports_dir = run_dir / "reports"
    _write_release_skeleton(run_dir, meta_dir, content_dir)
    reports_dir.mkdir(parents=True)

    cfg = RepoWikiConfig()
    cfg.project.root = str(repo)
    cfg.project.exclude = [".repo-agent-eval/**"]
    write_generation_conflict_artifacts(
        config=cfg,
        repo_root=repo,
        meta_dir=meta_dir,
        reports_dir=reports_dir,
        persist_scanner_cache=False,
    )

    assert not (meta_dir / "api-inventory.json").exists()
    source = json.loads((meta_dir / "source-inventory.json").read_text(encoding="utf-8"))
    assert source["api_surfaces"]
    assert source["data_models"]
    assert source["services"]
    assert "endpoints" not in source
    assert "models" not in source
    assert not any("service_id" in item for item in source["services"])

    verifier = QoderLikeVerifierService(run_dir, strict=True)
    inventories = verifier._load_structured_inventory_sets()
    missing = [
        name
        for name in ("sources", "apis", "services", "models", "runtimes")
        if not inventories[name]
    ]
    assert missing == [], missing

    result = verifier.verify(ci=True)
    assert "QODER_REQUIRED_INVENTORY_MISSING" not in result.get("hard_gate_codes", [])


def test_readme_generic_vocabulary_is_not_an_unresolved_fact_conflict(tmp_path: Path) -> None:
    """Bare 'API'/'service'/'model' and FastAPI framework mentions are not fact conflicts."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_fastapi_repo(repo)

    source = scan_repository_source_inventory_v3(repo, incremental=False)
    docs = scan_repository_docs_inventory(repo, source, incremental=False, persist_cache=False)
    readme = next(doc for doc in docs["documents"] if doc["path"] == "README.rst")
    generic = {"api", "service", "model", "router"}
    assert generic.isdisjoint({c.lower() for c in readme.get("conflicting_claims") or []})

    report = resolve_source_docs_conflicts(source, docs)
    deferred_evidence = {
        str(item).lower()
        for entry in report["deferred_items"]
        for item in entry.get("evidence") or []
    }
    assert generic.isdisjoint(deferred_evidence)
    assert "fastapi" not in deferred_evidence

    run_dir = repo / ".repo-agent-eval" / "runs" / "run-x"
    meta_dir = run_dir / "repowiki" / "zh" / "meta"
    content_dir = run_dir / "repowiki" / "zh" / "content"
    reports_dir = run_dir / "reports"
    _write_release_skeleton(run_dir, meta_dir, content_dir)
    reports_dir.mkdir(parents=True)
    cfg = RepoWikiConfig()
    cfg.project.root = str(repo)
    cfg.project.exclude = [".repo-agent-eval/**"]
    write_generation_conflict_artifacts(
        config=cfg,
        repo_root=repo,
        meta_dir=meta_dir,
        reports_dir=reports_dir,
        persist_scanner_cache=False,
    )
    result = QoderLikeVerifierService(run_dir, strict=True).verify(ci=True)
    assert "QODER_UNRESOLVED_FACT_CONFLICT" not in result.get("hard_gate_codes", [])


def test_named_missing_service_claim_still_unresolved(tmp_path: Path) -> None:
    """A specific *Service claim that is not in source inventory still defers."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_fastapi_repo(repo)
    (repo / "docs").mkdir()
    (repo / "docs" / "roadmap.md").write_text(
        "# Roadmap\n\nLegacyBillingService will replace the current handlers.\n",
        encoding="utf-8",
    )
    source = scan_repository_source_inventory_v3(repo, incremental=False)
    docs = scan_repository_docs_inventory(repo, source, incremental=False, persist_cache=False)
    report = resolve_source_docs_conflicts(source, docs)
    evidence = [
        str(item).lower()
        for entry in report["deferred_items"]
        for item in entry.get("evidence") or []
    ]
    assert any("legacybillingservice" in token for token in evidence)
